"""Explicit schema-69 PostgreSQL baseline and offline SQLite importer.

No application startup DDL, credential logging, or automatic production access.
The caller must provide a frozen SQLite snapshot and a separate empty database.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from sqlalchemy import Boolean, Column, Integer, MetaData, Table, UnicodeText, create_engine, func, inspect, select, text
from sqlalchemy.orm import Session

from globaleaks import DATABASE_VERSION, models

REVISION = 2
LOCK_ID = 1463960881
revision = Table('wbe_schema_revision', MetaData(),
                 Column('revision', Integer, primary_key=True),
                 Column('application_schema', Integer, nullable=False))


class MigrationError(RuntimeError):
    """Operator-safe error containing no source data or database credentials."""


def _postgres(engine):
    if engine.dialect.name != 'postgresql' or DATABASE_VERSION != 69:
        raise MigrationError('This command requires PostgreSQL and application schema 69')


def _empty(conn):
    if inspect(conn).get_table_names(schema='public'):
        raise MigrationError('Target public schema must contain no tables')


def _lock(conn):
    conn.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': LOCK_ID})


def _mark(conn):
    revision.create(conn)
    conn.execute(revision.insert().values(revision=REVISION, application_schema=DATABASE_VERSION))


def _protect_revision(conn, runtime_role):
    if runtime_role is None:
        return
    if not conn.execute(text('SELECT 1 FROM pg_roles WHERE rolname = :role'),
                        {'role': runtime_role}).first():
        raise MigrationError('Requested runtime role does not exist')
    if runtime_role == conn.execute(text('SELECT current_user')).scalar():
        raise MigrationError('Runtime role must differ from the schema owner')
    role = conn.dialect.identifier_preparer.quote_identifier(runtime_role)
    # Table is migrator-owned; runtime needs readiness SELECT, never DML/DDL.
    conn.execute(text('REVOKE ALL ON TABLE public.wbe_schema_revision FROM ' + role))
    conn.execute(text('GRANT SELECT ON TABLE public.wbe_schema_revision TO ' + role))


def _check(conn):
    tables = set(inspect(conn).get_table_names(schema='public'))
    if not set(models.Base.metadata.tables).union({revision.name}).issubset(tables):
        raise MigrationError('PostgreSQL baseline is absent or incomplete; run init or import-sqlite')
    if [tuple(row) for row in conn.execute(select(revision))] != [(REVISION, DATABASE_VERSION)]:
        raise MigrationError('Unsupported PostgreSQL schema revision')
    cfg = models.Config.__table__
    versions = list(conn.execute(select(cfg.c.value).where(cfg.c.tid == 1, cfg.c.var_name == 'version_db')).scalars())
    if versions != [DATABASE_VERSION]:
        raise MigrationError('Application schema version is not 69')


def check_schema(engine):
    _postgres(engine)
    with engine.connect() as conn:
        _check(conn)
    return {'revision': REVISION, 'application_schema': DATABASE_VERSION}


def initialize(engine, runtime_role=None):
    """Create both DDL and application defaults atomically, including revision."""
    from globaleaks.handlers.admin.tenant import db_create
    _postgres(engine)
    with engine.begin() as conn:
        _lock(conn)
        _empty(conn)
        models.Base.metadata.create_all(conn)
        with Session(bind=conn) as session:
            db_create(session, {'active': True, 'mode': 'default', 'name': 'GLOBALEAKS', 'subdomain': ''})
            session.flush()
        _mark(conn)
        _protect_revision(conn, runtime_role)
        conn.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
        _check(conn)
    return {'revision': REVISION, 'application_schema': DATABASE_VERSION, 'initialized': True}


def _canonical(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return {'date': value.isoformat()}
    if isinstance(value, bytes):
        return {'bytes': value.hex()}
    raise TypeError('Unsupported database value')


def _rows(conn, table):
    # PostgreSQL locale collation can differ from SQLite BINARY ordering.
    ordering = [column.collate('C') if conn.dialect.name == 'postgresql'
                and isinstance(column.type, UnicodeText) else column
                for column in table.primary_key.columns]
    return conn.execute(select(table).order_by(*ordering)).mappings()


def _digest(conn, table):
    digest = hashlib.sha256()
    count = 0
    for row in _rows(conn, table):
        encoded = json.dumps(dict(row), default=_canonical, sort_keys=True,
                             ensure_ascii=True, separators=(',', ':')).encode('ascii')
        digest.update(len(encoded).to_bytes(8, 'big'))
        digest.update(encoded)
        count += 1
    return {'count': count, 'sha256': digest.hexdigest()}


def _validate_source(conn):
    # A read transaction pins one consistent snapshot for validation and copying.
    conn.exec_driver_sql('BEGIN')
    if list(conn.exec_driver_sql('PRAGMA integrity_check')) != [('ok',)]:
        raise MigrationError('SQLite integrity check failed')
    if conn.exec_driver_sql('PRAGMA foreign_key_check').first() is not None:
        raise MigrationError('SQLite contains invalid foreign keys')
    inspector = inspect(conn)
    tables = set(inspector.get_table_names()) - {'sqlite_sequence'}
    if tables != set(models.Base.metadata.tables):
        raise MigrationError('Source does not match the complete schema-69 table set')
    for table in models.Base.metadata.tables.values():
        if {c['name'] for c in inspector.get_columns(table.name)} != set(table.columns.keys()):
            raise MigrationError('Source columns do not match schema 69')
        for column in table.columns:
            if isinstance(column.type, Boolean):
                quote = conn.dialect.identifier_preparer.quote_identifier
                name = quote(column.name)
                invalid = ('SELECT 1 FROM ' + quote(table.name) + ' WHERE ' + name
                           + ' IS NOT NULL AND ' + name + ' NOT IN (0,1) LIMIT 1')
                if conn.exec_driver_sql(invalid).first() is not None:
                    raise MigrationError('Source contains a non-boolean value in a boolean column')
    cfg = models.Config.__table__
    versions = list(conn.execute(select(cfg.c.value).where(cfg.c.tid == 1, cfg.c.var_name == 'version_db')).scalars())
    if versions != [DATABASE_VERSION]:
        raise MigrationError('SQLite must already be upgraded to application schema 69')
    tip = models.InternalTip.__table__
    mixed = select(tip.c.tid).group_by(tip.c.tid).having(
        (func.max(func.length(tip.c.receipt_hash)) >= 64)
        & (func.min(func.length(tip.c.receipt_hash)) < 64))
    if conn.execute(mixed).first() is not None:
        raise MigrationError('Mixed receipt hash formats: normalize with the legacy workflow before snapshotting')


def _sequences(source, target):
    sqlite_sequences = {}
    if source.exec_driver_sql("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").first():
        sqlite_sequences = dict(source.exec_driver_sql('SELECT name, seq FROM sqlite_sequence').all())
    for table in models.Base.metadata.tables.values():
        keys = list(table.primary_key.columns)
        if len(keys) != 1 or not isinstance(keys[0].type, Integer) or keys[0].foreign_keys:
            continue
        column = keys[0]
        seq = target.execute(text('SELECT pg_get_serial_sequence(:table, :column)'),
                             {'table': table.name, 'column': column.name}).scalar()
        if seq:
            # Model-controlled identifiers only; never interpolate source values.
            maximum = target.execute(select(func.max(column))).scalar() or 0
            maximum = max(maximum, sqlite_sequences.get(table.name, 0))
            target.execute(text('SELECT setval(CAST(:seq AS regclass), :value, :called)'),
                           {'seq': seq, 'value': max(1, maximum), 'called': maximum > 0})


def import_sqlite(source_path, engine, dry_run=False, runtime_role=None):
    """Copy typed rows, validate every value and FK, commit only on full success."""
    _postgres(engine)
    path = Path(source_path).resolve(strict=True)
    if not path.is_file():
        raise MigrationError('Source must be a SQLite snapshot file')
    # URI mode=ro never creates a missing source or writes journal settings.
    source_engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(
        path.as_uri() + '?mode=ro', uri=True), hide_parameters=True)
    try:
        with source_engine.connect() as source, engine.begin() as target:
            _validate_source(source)
            _lock(target)
            _empty(target)
            before = {table.name: _digest(source, table)
                      for table in models.Base.metadata.sorted_tables}
            if dry_run:
                return {'dry_run': True, 'tables': before, 'application_schema': DATABASE_VERSION}
            models.Base.metadata.create_all(target)
            target.execute(text('SET CONSTRAINTS ALL DEFERRED'))
            for table in models.Base.metadata.sorted_tables:
                result = _rows(source, table)
                while True:
                    batch = result.fetchmany(500)
                    if not batch:
                        break
                    target.execute(table.insert(), [dict(row) for row in batch])
            target.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
            after = {table.name: _digest(target, table)
                     for table in models.Base.metadata.sorted_tables}
            if before != after:
                raise MigrationError('Imported row counts or canonical digests differ')
            _sequences(source, target)
            _mark(target)
            _protect_revision(target, runtime_role)
            _check(target)
            return {'dry_run': False, 'tables': after, 'application_schema': DATABASE_VERSION}
    finally:
        source_engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'check', 'import-sqlite'])
    parser.add_argument('--working-path', default='/var/globaleaks')
    parser.add_argument('--source')
    parser.add_argument('--runtime-role', help='Separate runtime role granted SELECT only on revision metadata')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'import-sqlite' and not args.source:
        parser.error('import-sqlite requires --source')
    if args.runtime_role and args.command == 'check':
        parser.error('--runtime-role is supported only for init and import-sqlite')
    if args.dry_run and args.command != 'import-sqlite':
        parser.error('--dry-run is supported only for import-sqlite')
    try:
        from globaleaks.orm import configured_db_uri, get_engine, set_db_uri
        url = configured_db_uri()
        if not url:
            raise MigrationError('Set WBE_DATABASE_URL_FILE or WBE_DATABASE_URL explicitly')
        set_db_uri(url)
        engine = get_engine()
        _postgres(engine)
        if args.command == 'init':
            from globaleaks.settings import Settings
            from globaleaks.state import State
            Settings.working_path = args.working_path
            State.init_environment()
            result = initialize(engine, args.runtime_role)
        elif args.command == 'check':
            result = check_schema(engine)
        else:
            result = import_sqlite(args.source, engine, args.dry_run, args.runtime_role)
        print(json.dumps(result, sort_keys=True))
        return 0
    except MigrationError as exc:
        print('Migration refused: ' + str(exc), file=sys.stderr)
    except Exception as exc:
        # SQLAlchemy exceptions include SQL, parameters, and potentially secrets.
        print('Migration failed (' + type(exc).__name__ + '); verify target state before retrying', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
