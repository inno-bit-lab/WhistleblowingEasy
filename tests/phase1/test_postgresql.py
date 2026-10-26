"""Destructive integration tests restricted to the dedicated synthetic test DB.

Run with WBE_TEST_DATABASE_URL or WBE_TEST_DATABASE_URL_FILE naming
wbe_phase1_test. No default DSN and no access to the application database.
"""
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from globaleaks import models
from globaleaks.db import postgresql as pg


class PostgreSQLMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        secret = os.environ.get('WBE_TEST_DATABASE_URL_FILE')
        url = Path(secret).read_text().strip() if secret else os.environ.get('WBE_TEST_DATABASE_URL')
        if not url:
            raise unittest.SkipTest('Set WBE_TEST_DATABASE_URL_FILE for PostgreSQL integration tests')
        parsed = make_url(url)
        if parsed.get_backend_name() != 'postgresql' or parsed.database != 'wbe_phase1_test':
            raise RuntimeError('Refusing destructive test outside wbe_phase1_test')
        cls.engine = create_engine(url, hide_parameters=True)
        cls.fixture = Path(models.__file__).resolve().parent.parent / 'tests/db/empty/globaleaks-69.db'

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(text('DROP SCHEMA public CASCADE'))
            conn.execute(text('CREATE SCHEMA public'))
        self.tmp = tempfile.TemporaryDirectory(prefix='wbe-pg-fixture-')
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'snapshot.db'
        shutil.copyfile(self.fixture, self.source)

    def test_import_preserves_all_typed_values_and_resets_sequences(self):
        with sqlite3.connect(self.source) as conn:
            conn.execute("UPDATE sqlite_sequence SET seq=1234 WHERE name='tenant'")
        result = pg.import_sqlite(self.source, self.engine)
        self.assertFalse(result['dry_run'])
        self.assertGreater(result['tables']['config']['count'], 100)
        self.assertEqual(pg.check_schema(self.engine)['application_schema'], 69)
        with self.engine.begin() as conn:
            generated = conn.execute(models.Tenant.__table__.insert().values(active=False).returning(models.Tenant.id)).scalar_one()
            self.assertGreater(generated, 1234)
        with self.assertRaises(pg.MigrationError):
            pg.import_sqlite(self.source, self.engine)

    def test_dry_run_does_not_write_source_or_target(self):
        original = self.source.read_bytes()
        result = pg.import_sqlite(self.source, self.engine, dry_run=True)
        self.assertTrue(result['dry_run'])
        self.assertEqual(inspect(self.engine).get_table_names(), [])
        self.assertEqual(original, self.source.read_bytes())

    def test_wrong_source_version_fails_without_target_tables(self):
        with sqlite3.connect(self.source) as conn:
            conn.execute("UPDATE config SET value='68' WHERE tid=1 AND var_name='version_db'")
        with self.assertRaises(pg.MigrationError):
            pg.import_sqlite(self.source, self.engine)
        self.assertEqual(inspect(self.engine).get_table_names(), [])

    def test_orphan_source_fails_without_target_tables(self):
        with sqlite3.connect(self.source) as conn:
            conn.execute("UPDATE config SET tid=999 WHERE tid=1 AND var_name='version_db'")
        with self.assertRaises(pg.MigrationError):
            pg.import_sqlite(self.source, self.engine)
        self.assertEqual(inspect(self.engine).get_table_names(), [])

    def test_late_failure_rolls_back_data_and_ddl(self):
        with patch.object(pg, '_mark', side_effect=pg.MigrationError('injected failure')):
            with self.assertRaises(pg.MigrationError):
                pg.import_sqlite(self.source, self.engine)
        self.assertEqual(inspect(self.engine).get_table_names(), [])
        pg.import_sqlite(self.source, self.engine)
        pg.check_schema(self.engine)

    def test_digest_mismatch_rolls_back_everything(self):
        original = pg._digest
        def mismatch(conn, table):
            result = original(conn, table)
            if conn.dialect.name == 'postgresql' and table.name == 'tenant':
                result['sha256'] = 'mismatch'
            return result
        with patch.object(pg, '_digest', side_effect=mismatch):
            with self.assertRaises(pg.MigrationError):
                pg.import_sqlite(self.source, self.engine)
        self.assertEqual(inspect(self.engine).get_table_names(), [])

    def test_missing_or_wrong_revision_is_not_ready(self):
        with self.assertRaises(pg.MigrationError):
            pg.check_schema(self.engine)
        pg.import_sqlite(self.source, self.engine)
        with self.engine.begin() as conn:
            conn.execute(pg.revision.update().values(revision=999))
        with self.assertRaises(pg.MigrationError):
            pg.check_schema(self.engine)

    def test_receiver_file_size_preserves_integer_and_encrypted_text(self):
        source_engine = create_engine('sqlite:///' + str(self.source))
        try:
            with source_engine.begin() as conn:
                questionnaire_id = conn.execute(select(models.Questionnaire.id)).scalar()
                conn.execute(models.Context.__table__.insert().values(
                    id='size-context', tid=1, questionnaire_id=questionnaire_id))
                conn.execute(models.InternalTip.__table__.insert().values(
                    id='size-tip', tid=1, context_id='size-context', receipt_hash='x' * 64))
                for name, size in [('plain', 12345), ('encrypted', 'QmFzZTY0L2NyeXB0bw==')]:
                    conn.execute(models.ReceiverFile.__table__.insert().values(
                        id=name, internaltip_id='size-tip', name='synthetic', size=size,
                        content_type='application/octet-stream'))
        finally:
            source_engine.dispose()
        report = pg.import_sqlite(self.source, self.engine)
        self.assertEqual(report['tables']['receiverfile']['count'], 2)
        with Session(bind=self.engine) as session:
            values = dict(session.query(models.ReceiverFile.id, models.ReceiverFile.size).all())
            self.assertEqual(values, {'plain': 12345, 'encrypted': 'QmFzZTY0L2NyeXB0bw=='})
            # A newly submitted encrypted string containing only digits must
            # remain a string rather than being inferred as a plaintext count.
            row = session.query(models.ReceiverFile).filter_by(id='encrypted').one()
            row.size = b'123456'
            session.commit()
            session.expire_all()
            self.assertEqual(row.size, '123456')
            self.assertIsInstance(row.size, str)


    def test_invalid_sqlite_boolean_text_is_rejected(self):
        with sqlite3.connect(self.source) as conn:
            conn.execute("UPDATE tenant SET active='garbage'")
        with self.assertRaisesRegex(pg.MigrationError, 'non-boolean'):
            pg.import_sqlite(self.source, self.engine)
        self.assertEqual(inspect(self.engine).get_table_names(), [])

    def test_mixed_receipt_formats_are_rejected_without_rewriting(self):
        source_engine = create_engine('sqlite:///' + str(self.source))
        try:
            with source_engine.begin() as conn:
                questionnaire_id = conn.execute(select(models.Questionnaire.id)).scalar()
                conn.execute(models.Context.__table__.insert().values(
                    id='synthetic-context', tid=1, questionnaire_id=questionnaire_id))
                for index, length in enumerate([32, 64]):
                    conn.execute(models.InternalTip.__table__.insert().values(
                        id='synthetic-tip-' + str(index), tid=1,
                        context_id='synthetic-context', progressive=index + 1,
                        receipt_hash='x' * length))
        finally:
            source_engine.dispose()
        original = self.source.read_bytes()
        with self.assertRaisesRegex(pg.MigrationError, 'Mixed receipt'):
            pg.import_sqlite(self.source, self.engine)
        self.assertEqual(inspect(self.engine).get_table_names(), [])
        self.assertEqual(original, self.source.read_bytes())


    def test_runtime_role_can_read_but_not_modify_revision(self):
        pg.import_sqlite(self.source, self.engine, runtime_role='wbe_runtime')
        with self.engine.connect() as conn:
            self.assertTrue(conn.execute(text(
                "SELECT has_table_privilege('wbe_runtime', 'wbe_schema_revision', 'SELECT')")).scalar())
            for privilege in ['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'TRIGGER']:
                self.assertFalse(conn.execute(text(
                    "SELECT has_table_privilege('wbe_runtime', 'wbe_schema_revision', :privilege)"),
                    {'privilege': privilege}).scalar())

    def test_invalid_runtime_role_rolls_back_import(self):
        with self.assertRaises(pg.MigrationError):
            pg.import_sqlite(self.source, self.engine, runtime_role='missing";DROP SCHEMA public;--')
        self.assertEqual(inspect(self.engine).get_table_names(), [])

    def test_concurrent_submission_counters_are_unique(self):
        from globaleaks.handlers.whistleblower.submission import db_assign_submission_progressive
        pg.import_sqlite(self.source, self.engine)
        with Session(bind=self.engine) as session:
            baseline = session.query(models.Config.value).filter_by(
                tid=1, var_name='counter_submissions').scalar()
        barrier = threading.Barrier(8)
        def assign(_):
            with Session(bind=self.engine) as session:
                barrier.wait(timeout=10)
                number = db_assign_submission_progressive(session, 1)
                session.commit()
                return number
        with ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(assign, range(8)))
        self.assertEqual(sorted(numbers), list(range(baseline + 1, baseline + 9)))
        with Session(bind=self.engine) as session:
            counter = session.query(models.Config.value).filter_by(
                tid=1, var_name='counter_submissions').scalar()
            self.assertEqual(counter, baseline + 8)

    def test_concurrent_identical_archived_schema_is_idempotent(self):
        from globaleaks.handlers.whistleblower.submission import db_archive_questionnaire_schema
        pg.import_sqlite(self.source, self.engine)
        questionnaire = {'synthetic_concurrency_test': True, 'steps': []}
        barrier = threading.Barrier(8)
        def archive(_):
            with Session(bind=self.engine) as session:
                barrier.wait(timeout=10)
                digest = db_archive_questionnaire_schema(session, questionnaire)
                session.commit()
                return digest
        with ThreadPoolExecutor(max_workers=8) as pool:
            digests = list(pool.map(archive, range(8)))
        self.assertEqual(len(set(digests)), 1)
        with Session(bind=self.engine) as session:
            rows = session.query(models.ArchivedSchema).filter_by(hash=digests[0]).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].schema, questionnaire)


    def test_initialize_uses_one_atomic_transaction(self):
        # Bootstrap resources are supplied by the development runtime.
        from globaleaks.settings import Settings
        from globaleaks.state import State
        Settings.working_path = self.tmp.name
        State.init_environment()
        with patch.object(pg, '_mark', side_effect=pg.MigrationError('injected failure')):
            with self.assertRaises(pg.MigrationError):
                pg.initialize(self.engine)
        self.assertEqual(inspect(self.engine).get_table_names(), [])
        pg.initialize(self.engine)
        pg.check_schema(self.engine)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(select(models.Tenant.id)).scalars().all(), [1])
        with self.assertRaises(pg.MigrationError):
            pg.initialize(self.engine)


if __name__ == '__main__':
    unittest.main()
