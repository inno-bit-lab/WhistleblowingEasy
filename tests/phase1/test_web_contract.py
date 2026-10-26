import unittest
from types import SimpleNamespace
from unittest.mock import patch

from globaleaks.rest.api import APIResourceWrapper
from globaleaks.state import State


class DevelopmentTransportTests(unittest.TestCase):
    def redirects(self, host, split, opt_in):
        request = SimpleNamespace(hostname=host, path=b'/api/health', isSecure=lambda: False)
        with patch.object(State.settings, 'separate_frontend', split), patch.object(State.settings, 'dev_http', opt_in):
            return APIResourceWrapper.should_redirect_https(None, request)

    def test_http_requires_both_explicit_flags(self):
        for split, opt_in in [(False, False), (False, True), (True, False)]:
            self.assertTrue(self.redirects(b'127.0.0.1', split, opt_in))
        self.assertFalse(self.redirects(b'127.0.0.1', True, True))
        self.assertFalse(self.redirects(b'localhost', True, True))

    def test_external_host_never_uses_development_exception(self):
        self.assertTrue(self.redirects(b'reports.example.org', True, True))
        self.assertTrue(self.redirects(b'localhost.attacker.invalid', True, True))

class ExternalDatabaseConfigurationTests(unittest.TestCase):
    def test_empty_explicit_secret_never_falls_back_to_sqlite(self):
        import tempfile
        from globaleaks.orm import configured_db_uri
        with tempfile.NamedTemporaryFile() as secret:
            with patch.dict('os.environ', {'WBE_DATABASE_URL_FILE': secret.name}, clear=True):
                with self.assertRaisesRegex(ValueError, 'must not be empty'):
                    configured_db_uri()

    def test_wrong_dialect_refused_without_secret_disclosure(self):
        from globaleaks.orm import configured_db_uri
        with patch.dict('os.environ', {'WBE_DATABASE_URL': 'mysql://user:private-secret@localhost/db'}, clear=True):
            with self.assertRaises(ValueError) as error:
                configured_db_uri()
            self.assertNotIn('private-secret', str(error.exception))

class DatabaseMaintenanceTests(unittest.TestCase):
    def test_postgresql_cleaning_leaves_vacuum_to_database(self):
        from globaleaks.db import compact_db
        with patch('globaleaks.db.is_postgresql', return_value=True), patch('globaleaks.db.get_engine') as engine:
            compact_db()
            engine.assert_not_called()

if __name__ == '__main__': unittest.main()
