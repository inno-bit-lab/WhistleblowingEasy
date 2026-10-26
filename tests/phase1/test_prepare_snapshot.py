"""Offline-only preparation tests using the actual schema-69 model metadata."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from globaleaks import models

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/production/prepare-snapshot.py'
spec = importlib.util.spec_from_file_location('prepare_snapshot', SCRIPT)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PrepareSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / '.local/imports/synthetic/appdata'
        self.source.mkdir(parents=True)
        self.db = self.source / 'globaleaks.db'
        engine = create_engine('sqlite:///' + str(self.db))
        models.Base.metadata.create_all(engine)
        engine.dispose()
        with sqlite3.connect(self.db) as conn:
            self.ddl = conn.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC,name").fetchall()
        self.seed()
        (self.source / 'files').mkdir()
        (self.source / 'files/synthetic').write_bytes(b'synthetic encrypted file placeholder')

    def seed(self, marker=68):
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO tenant VALUES(1,'2026-01-01 00:00:00',1)")
            conn.execute("INSERT INTO config VALUES(1,'version_db',?,'2026-01-01 00:00:00')", (json.dumps(marker),))
            conn.execute("INSERT INTO config VALUES(1,'synthetic_keep',?,'2026-01-01 00:00:00')", ('"unchanged"',))

    def rebuild(self, change):
        self.db.unlink()
        with sqlite3.connect(self.db) as conn:
            for kind, name, sql in self.ddl:
                modified = change(kind, name, sql)
                if modified:
                    conn.execute(modified)
        self.seed()

    def run_prepare(self):
        return prepare.prepare(self.source, self.root)

    def assert_refused(self):
        before = prepare.digest(self.db)
        with self.assertRaises(prepare.PreparationError):
            self.run_prepare()
        self.assertEqual(before, prepare.digest(self.db))
        parent = self.root / '.local/production/imports'
        self.assertFalse(parent.exists() and list(parent.iterdir()))

    def test_68_only_marker_changes_and_source_files_unchanged(self):
        before = prepare.digest(self.db)
        with sqlite3.connect(self.db) as conn:
            original_rows = conn.execute('SELECT * FROM config ORDER BY var_name').fetchall()
        output = self.run_prepare()
        self.assertEqual(prepare.digest(self.db), before)
        with sqlite3.connect(output / 'appdata/globaleaks.db') as conn:
            rows = conn.execute('SELECT * FROM config ORDER BY var_name').fetchall()
        expected = [tuple('69' if i == 2 and row[1] == 'version_db' else value for i, value in enumerate(row)) for row in original_rows]
        self.assertEqual(rows, expected)
        self.assertEqual((output / 'appdata/files/synthetic').read_bytes(), (self.source / 'files/synthetic').read_bytes())
        self.assertEqual(json.loads((output / 'preparation.json').read_text())['normalized_marker_count'], 1)
        for path in [output, *output.rglob('*')]:
            self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_69_is_accepted_without_db_rewrite(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE config SET value='69' WHERE var_name='version_db'")
        before = prepare.digest(self.db)
        output = self.run_prepare()
        self.assertEqual(prepare.digest(output / 'appdata/globaleaks.db'), before)
        self.assertEqual(json.loads((output / 'preparation.json').read_text())['normalized_marker_count'], 0)

    def test_column_type_nullability_default_pk_and_fk_changes_rejected(self):
        variants = [
            ('type', lambda sql: sql.replace('value TEXT', 'value BLOB')),
            ('nullability', lambda sql: sql.replace('value TEXT NOT NULL', 'value TEXT')),
            ('default', lambda sql: sql.replace('value TEXT NOT NULL', "value TEXT DEFAULT 'x' NOT NULL")),
            ('primary_key', lambda sql: sql.replace('PRIMARY KEY (tid, var_name)', 'PRIMARY KEY (var_name, tid)')),
            ('foreign_key', lambda sql: sql.replace('ON DELETE CASCADE', 'ON DELETE RESTRICT')),
            ('deferrable', lambda sql: sql.replace('INITIALLY DEFERRED', 'INITIALLY IMMEDIATE')),
        ]
        for name, transform in variants:
            with self.subTest(name=name):
                original = next(sql for kind, table, sql in self.ddl if table == 'config')
                self.assertNotEqual(original, transform(original), 'fixture must change schema')
                self.rebuild(lambda kind, table, sql: transform(sql) if table == 'config' else sql)
                self.assert_refused()

    def test_missing_index_rejected(self):
        index = next(name for kind, name, sql in self.ddl if kind == 'index')
        self.rebuild(lambda kind, name, sql: None if name == index else sql)
        self.assert_refused()

    def test_added_check_constraint_rejected(self):
        self.rebuild(lambda kind, name, sql: sql.replace('value TEXT NOT NULL', 'value TEXT NOT NULL CHECK(length(value)>0)') if name == 'config' else sql)
        self.assert_refused()

    def test_extra_table_with_sqlite_like_name_rejected(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE sqliteX_extra (id INTEGER)')
        self.assert_refused()

    def test_extra_trigger_rejected(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TRIGGER unexpected AFTER UPDATE ON config BEGIN SELECT 1; END')
        self.assert_refused()

    def test_invalid_fk_and_marker_rejected(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE config SET tid=99 WHERE var_name='synthetic_keep'")
        self.assert_refused()
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE config SET tid=1 WHERE var_name='synthetic_keep'")
            conn.execute("UPDATE config SET value='67' WHERE var_name='version_db'")
        self.assert_refused()

    def test_pending_attachment_rejected(self):
        engine = create_engine('sqlite:///' + str(self.db))
        try:
            with engine.begin() as conn:
                conn.execute(models.Questionnaire.__table__.insert().values(id='q', tid=1))
                conn.execute(models.Context.__table__.insert().values(id='c', tid=1, questionnaire_id='q'))
                conn.execute(models.InternalTip.__table__.insert().values(id='t', tid=1, context_id='c', progressive=1, receipt_hash='synthetic-receipt'))
                conn.execute(models.InternalFile.__table__.insert().values(id='f', internaltip_id='t', name='synthetic', new=True))
        finally:
            engine.dispose()
        self.assert_refused()

    def test_source_symlink_and_sidecar_rejected(self):
        (self.source / 'files/link').symlink_to(self.source / 'files/synthetic')
        self.assert_refused()
        (self.source / 'files/link').unlink()
        (self.source / 'globaleaks.db-wal').write_bytes(b'')
        self.assert_refused()

    def test_live_and_outside_paths_refused_before_schema_access(self):
        with patch.object(prepare, 'canonical_structure', side_effect=AssertionError('must not inspect')):
            for path in ('/opt/apps/wbe/node1/appdata', self.root / 'unapproved'):
                with self.subTest(path=str(path)), self.assertRaises(prepare.PreparationError):
                    prepare.prepare(path, self.root)

    def test_destination_symlink_and_existing_directory_refused(self):
        local = self.root / '.local'
        (local / 'production').symlink_to(self.root, target_is_directory=True)
        self.assert_refused()
        (local / 'production').unlink()
        output = self.run_prepare()
        with patch.object(prepare.uuid, 'uuid4') as uid, patch.object(prepare.datetime, 'datetime') as date:
            date.now.return_value.strftime.return_value = output.name.split('-')[0]
            uid.return_value.hex = output.name.split('-')[1]
            with self.assertRaises(FileExistsError):
                self.run_prepare()
        self.assertTrue((output / 'preparation.json').is_file())

    def test_source_change_during_copy_removes_output(self):
        original_copy = prepare.shutil.copyfileobj
        def changing_copy(source, target):
            original_copy(source, target)
            if Path(source.name).name == 'synthetic':
                (self.source / 'files/synthetic').write_bytes(b'changed during copy')
        with patch.object(prepare.shutil, 'copyfileobj', side_effect=changing_copy):
            with self.assertRaisesRegex(prepare.PreparationError, 'Source changed'):
                self.run_prepare()
        self.assertEqual(list((self.root / '.local/production/imports').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
