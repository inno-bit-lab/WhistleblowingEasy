import random
import time
import sqlite3
import os
import threading
from pathlib import Path
from sqlalchemy.engine import make_url

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from twisted.internet import reactor
from twisted.internet.threads import deferToThreadPool

from globaleaks.models import AuditLog


_PG_ENGINES = {}
_PG_ENGINE_LOCK = threading.Lock()


def configured_db_uri():
    path = os.environ.get("WBE_DATABASE_URL_FILE")
    value = Path(path).read_text().strip() if path else os.environ.get("WBE_DATABASE_URL")
    if path and not value:
        raise ValueError('WBE database URL file must not be empty')
    if value:
        try:
            if make_url(value).get_backend_name() != 'postgresql':
                raise ValueError()
        except Exception:
            raise ValueError('WBE external database URL must select PostgreSQL') from None
    return value


def is_postgresql(db_uri=None):
    return make_url(db_uri or get_db_uri()).get_backend_name() == "postgresql"


def dispose_engines():
    with _PG_ENGINE_LOCK:
        for engine in _PG_ENGINES.values():
            engine.dispose()
        _PG_ENGINES.clear()


_ORM_DEBUG = False
_ORM_DB_URI = "sqlite:///:memory:"
_ORM_THREAD_POOL = None
_ORM_TRANSACTION_RETRIES = 20


SQLITE_DELETE=9
SQLITE_FUNCTION=31
SQLITE_INSERT=18
SQLITE_READ=20
SQLITE_SELECT=21
SQLITE_TRANSACTION=22
SQLITE_UPDATE=23


def make_db_uri(db_file):
    return 'sqlite:////' + db_file


def set_db_uri(db_uri):
    global _ORM_DB_URI
    _ORM_DB_URI = db_uri


def get_db_uri():
    return _ORM_DB_URI


def get_engine(db_uri=None, foreign_keys=True, orm_lockdown=True):
    if db_uri is None:
        db_uri = get_db_uri()

    dialect = make_url(db_uri).get_backend_name()
    if dialect == 'postgresql':
        # One bounded pool per process, shared by the Twisted transaction threads.
        # Never echo SQL/bind parameters on the remote database path.
        with _PG_ENGINE_LOCK:
            if db_uri not in _PG_ENGINES:
                _PG_ENGINES[db_uri] = create_engine(
                    db_uri, pool_size=8, max_overflow=8, pool_timeout=15,
                    pool_pre_ping=True, hide_parameters=True,
                    connect_args={'connect_timeout': 10,
                                  'options': '-c timezone=UTC -c search_path=public -c statement_timeout=30000 -c lock_timeout=10000'})
            return _PG_ENGINES[db_uri]
    if dialect != 'sqlite':
        raise ValueError('Unsupported WBE database dialect')
    engine = create_engine(db_uri, connect_args={'timeout': 30}, echo=_ORM_DEBUG)

    def authorizer_callback(action, table, column, sql_location, ignore):
        if action in [SQLITE_DELETE,
                      SQLITE_INSERT,
                      SQLITE_READ,
                      SQLITE_SELECT,
                      SQLITE_TRANSACTION,
                      SQLITE_UPDATE] or \
           (action == SQLITE_FUNCTION and column in ['count',
                                                     'length',
                                                     'lower',
                                                     'min',
                                                     'max',
                                                     'substr']):
            return sqlite3.SQLITE_OK
        else:
            return sqlite3.SQLITE_DENY

    @event.listens_for(engine, "connect")
    def do_connect(conn, connection_record):
        conn.execute('PRAGMA journal_mode=DELETE')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('PRAGMA cache_size=-32000')
        conn.execute('PRAGMA secure_delete=ON')
        conn.execute('PRAGMA trusted_schema=OFF')
        conn.execute('PRAGMA temp_store=MEMORY')
        conn.execute('PRAGMA dqs_ddl=0')
        conn.execute('PRAGMA dqs_dml=0')

        if hasattr(conn, 'setconfig'):  # Python 3.12+
            conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, False)
            conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_VIEW, False)
            conn.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)

        if foreign_keys:
            conn.execute('PRAGMA foreign_keys=ON')

        if orm_lockdown:
            conn.set_authorizer(authorizer_callback)

    return engine


def get_session(db_uri=None, foreign_keys=True):
    return sessionmaker(bind=get_engine(db_uri, foreign_keys))()



def enable_orm_debug():
    global _ORM_DEBUG
    _ORM_DEBUG = True


def set_thread_pool(thread_pool):
    global _ORM_THREAD_POOL
    _ORM_THREAD_POOL = thread_pool


def get_thread_pool():
    return _ORM_THREAD_POOL


def db_add(session, model_class, model_fields):
    obj = model_class(model_fields)
    session.add(obj)
    session.flush()
    return obj


def db_query(session, selector, filter=None):
    if isinstance(selector, tuple):
        q = session.query(*selector)
    else:
        q = session.query(selector)

    if filter is None:
        return q

    if isinstance(filter, tuple):
        return q.filter(*filter)
    else:
        return q.filter(filter)


def db_get(session, selector, filter=None):
    return db_query(session, selector, filter).one()


def db_del(session, selector, filter=None):
    db_query(session, selector, filter).delete(synchronize_session=False)


def db_log(session, **kwargs):
    entry = AuditLog()

    for key, value in kwargs.items():
         setattr(entry, key, value)

    session.add(entry)


class transact:
    """
    Class decorator for managing transactions.
    """

    def __init__(self, method):
        self.method = method
        self.instance = None

    def __get__(self, instance, owner):
        self.instance = instance
        return self

    def __call__(self, *args, **kwargs):
        return self.run(self._wrap, self.method, *args, **kwargs)

    def run(self, function, *args, **kwargs):
        return deferToThreadPool(reactor,
                                 get_thread_pool(),
                                 function,
                                 *args,
                                 **kwargs)

    def _wrap(self, function, *args, **kwargs):
        """
        Wrap provided function calling it inside a thread and
        passing the ORM session to it.
        """
        session = get_session()

        retries = 0

        try:
            while True:
                try:
                    if self.instance:
                        result = function(self.instance, session, *args, **kwargs)
                    else:
                        result = function(session, *args, **kwargs)

                    session.commit()
                except OperationalError as e:
                    session.rollback()

                    if "database is locked" not in str(e):
                        raise

                    retries += 1

                    if retries >= _ORM_TRANSACTION_RETRIES:
                        raise Exception("Transaction failed with too many retries")

                    time.sleep(0.2 * random.uniform(1, 2 ** retries))  # noqa: S311 - non-crypto backoff jitter
                except Exception:
                    session.rollback()
                    raise
                else:
                    return result
        finally:
            session.close()


class transact_sync(transact):
    def run(self, function, *args, **kwargs):
        return function(*args, **kwargs)


@transact
def tw(session, f, *args, **kwargs):
    return f(session, *args, **kwargs)
