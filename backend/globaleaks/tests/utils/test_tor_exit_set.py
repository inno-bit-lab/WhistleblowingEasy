from twisted.trial import unittest
from globaleaks.utils.tor_exit_set import TorExitSet


class TestTorExitSet(unittest.TestCase):
    def test_plaintext_feed_ignores_comments_and_invalid_lines(self):
        exits = TorExitSet()
        exits.processData(b'# Tor bulk exit list\n192.0.2.1\n2001:db8::1\nnot-an-ip\n\n')
        self.assertEqual(exits, {'192.0.2.1', '2001:db8::1'})

    def test_refresh_replaces_previous_addresses(self):
        exits = TorExitSet({'192.0.2.1'})
        exits.processData(b'198.51.100.1\n')
        self.assertEqual(exits, {'198.51.100.1'})
