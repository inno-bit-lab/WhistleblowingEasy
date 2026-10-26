import os
import tempfile
import unittest
from types import SimpleNamespace

from twisted.internet.address import IPv4Address, UNIXAddress
from twisted.web.http_headers import Headers
from globaleaks.utils.frontend_ingress import (
    FrontendWebRequest, FrontendOnionRequest, frontend_socket_paths, request_identity)


class FrontendIngressTests(unittest.TestCase):
    def request(self, ingress=None, values=None, path=b'/api/authentication', port=8080):
        return SimpleNamespace(frontend_ingress=ingress, path=path,
            requestHeaders=Headers({b'x-wbe-client-ip': values} if values is not None else {}),
            getClientAddress=lambda: IPv4Address('TCP', '192.0.2.1', 54321),
            getHost=lambda: SimpleNamespace(port=port))

    def test_tcp_cannot_forge_proxy_identity(self):
        req=self.request(values=[b'203.0.113.8'])
        self.assertEqual(request_identity(req,set()), ('192.0.2.1',False))
        self.assertEqual(request_identity(req,{'192.0.2.1'}), ('192.0.2.1',True))
        self.assertEqual(request_identity(self.request(port=8083),set()), ('192.0.2.1',True))

    def test_web_requires_one_valid_client_address(self):
        for values in (None, [], [b'invalid'], [b'1.2.3.4, 5.6.7.8'], [b'1.2.3.4',b'5.6.7.8'], [b'fe80::1%eth0']):
            with self.subTest(values=values), self.assertRaises(ValueError):
                request_identity(self.request('web',values),set())
        self.assertEqual(request_identity(self.request('web',[b'::ffff:203.0.113.8']),set()),('203.0.113.8',False))
        self.assertEqual(request_identity(self.request('web',[b'2001:db8::1']),{'2001:db8::1'}),('2001:db8::1',True))

    def test_only_exact_health_allows_missing_ip(self):
        self.assertEqual(request_identity(self.request('web',path=b'/api/health'),set()),('127.0.0.1',False))
        with self.assertRaises(ValueError):
            request_identity(self.request('web',path=b'/api/health/'),set())

    def test_onion_ignores_header_and_unix_address_has_no_port(self):
        req=self.request('onion',[b'invalid'])
        req.getHost=lambda: UNIXAddress('/tmp/onion.sock')
        req.getClientAddress=lambda: UNIXAddress(None)
        self.assertEqual(request_identity(req,set()),('127.0.0.1',True))
        req.frontend_ingress=None
        self.assertEqual(request_identity(req,set()),('',False))
        self.assertTrue(FrontendWebRequest.isSecure(None))
        self.assertEqual(FrontendOnionRequest.frontend_ingress,'onion')

    def test_socket_paths_require_private_owned_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(frontend_socket_paths(directory),(directory+'/web.sock',directory+'/onion.sock'))
            os.chmod(directory,0o750)
            with self.assertRaises(ValueError): frontend_socket_paths(directory)
        with self.assertRaises(ValueError): frontend_socket_paths('relative')
