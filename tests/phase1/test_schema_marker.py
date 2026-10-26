"""Regression for schema upgrades that retain the application release version."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from globaleaks import DATABASE_VERSION, __version__, models
from globaleaks.db import migration


class SchemaMarkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'synthetic.db'
        self.engine = create_engine('sqlite:///' + str(self.path))
        self.addCleanup(self.engine.dispose)
        models.Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session:
            for tid in (1, 2):
                for key, value in {
                    'version': __version__, 'version_db': DATABASE_VERSION - 1,
                    'latest_version': 'keep-existing-release-metadata',
                    'smtp_password': 'synthetic-existing-secret',
                    'smtp_authentication': False,
                }.items():
                    session.add(models.Config({'tid': tid, 'var_name': key, 'value': value}))
            session.commit()

    def snapshot(self):
        with self.sessions() as session:
            return {(row.tid, row.var_name): (row.value, row.update_date)
                    for row in session.query(models.Config)}

    def test_same_application_version_updates_schema_marker_only(self):
        before = self.snapshot()
        with patch.object(migration, 'get_session', side_effect=lambda *a, **kw: self.sessions()), \
             patch.object(migration, 'load_appdata', return_value={}), \
             patch.object(migration.config, 'update_defaults') as defaults, \
             patch.object(migration, 'db_load_defaults') as load_defaults, \
             patch.object(migration, 'db_log') as log:
            migration.perform_data_update(str(self.path))
        defaults.assert_not_called()
        load_defaults.assert_not_called()
        log.assert_not_called()
        after = self.snapshot()
        self.assertEqual(before.keys(), after.keys())
        for key in before:
            if key[1] == 'version_db':
                self.assertEqual(after[key][0], DATABASE_VERSION)
            else:
                self.assertEqual(after[key], before[key])

    def test_failed_data_upgrade_does_not_advance_marker(self):
        with self.sessions() as session:
            session.query(models.Config).filter_by(var_name='version').update({'value': 'old-release'})
            session.commit()
        before = self.snapshot()
        with patch.object(migration, 'get_session', side_effect=lambda *a, **kw: self.sessions()), \
             patch.object(migration, 'load_appdata', return_value={}), \
             patch.object(migration, 'db_load_defaults', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                migration.perform_data_update(str(self.path))
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
