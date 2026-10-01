"""Check that channel document routing never rewrites application API paths."""
import json
import re
import unittest
from pathlib import Path


class ChannelRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = Path(__file__).resolve().parents[1] / 'dynamic/25-wbe-channel-aliases.yml'
        rule = json.loads(config.read_text())['http']['routers']['wbe-channel-slugs']['rule']
        cls.allowed = re.compile(re.search(r'(?<!!)PathRegexp\(`([^`]+)`\)', rule).group(1))
        cls.excluded = re.compile(re.search(r'!PathRegexp\(`([^`]+)`\)', rule).group(1))

    def matches(self, path):
        return bool(self.allowed.search(path) and not self.excluded.search(path))

    def test_channel_documents_and_admin_sections(self):
        for path in ['/zeverino/report', '/innobitlab/admin', '/zeverino/admin/settings',
                     '/innobitlab/login/passwordreset']:
            with self.subTest(path=path):
                self.assertTrue(self.matches(path))

    def test_application_endpoints_are_not_channel_documents(self):
        for path in ['/api/admin/node', '/api/admin/users', '/api/admin/contexts',
                     '/api/admin/network', '/api/auth/authentication', '/api/user/preferences',
                     '/api/public/channels/zeverino', '/s/logo', '/js/main.js', '/l10n/it']:
            with self.subTest(path=path):
                self.assertFalse(self.matches(path))

    def test_base_slug_redirect_and_reserved_paths(self):
        config = Path(__file__).resolve().parents[1] / 'dynamic/25-wbe-channel-aliases.yml'
        data = json.loads(config.read_text())['http']
        rule = data['routers']['wbe-channel-base']['rule']
        allowed = re.compile(re.search(r'(?<!!)PathRegexp\(`([^`]+)`\)', rule).group(1))
        excluded = re.compile(re.search(r'!PathRegexp\(`([^`]+)`\)', rule).group(1))
        for path in ['/lama-distribuzione', '/innobitlab/', '/zeverino']:
            self.assertTrue(allowed.search(path) and not excluded.search(path))
        for path in ['/', '/api', '/login', '/admin', '/submission', '/wizard', '/l10n']:
            self.assertFalse(allowed.search(path) and not excluded.search(path))
        redirect = data['middlewares']['wbe-channel-report-redirect']['redirectRegex']
        for suffix in ['', '/', '?lang=en', '/?lang=en']:
            match = re.match(redirect['regex'], 'https://wbe.kronosfinance.it/lama-distribuzione' + suffix)
            self.assertIsNotNone(match)
            self.assertEqual(match.group(1), 'lama-distribuzione')
            self.assertEqual(match.group(2) or '', '?lang=en' if '?' in suffix else '')


if __name__ == '__main__':
    unittest.main()
