import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock
from twisted.internet.defer import Deferred, succeed, fail
from globaleaks.services.tor import Tor


class TorIngressTests(unittest.TestCase):
    def service(self, publish=True):
        service=object.__new__(Tor)
        service.state=SimpleNamespace(settings=SimpleNamespace(onion_publish=publish,onion_target_port=8085),tenants={1:SimpleNamespace(cache=SimpleNamespace(tor_onion_key='synthetic-key',onionservice='synthetic.onion'))})
        service.tor_conn=SimpleNamespace(protocol=Mock())
        return service

    def test_disabled_publication_preserves_connection_without_creating_service(self):
        service=self.service(False)
        with patch('globaleaks.services.tor.TorConfig') as config:
            service.load_all_onion_services()
            service.load_onion_service(1,'synthetic.onion','synthetic-key')
        config.assert_not_called()
        self.assertIsNotNone(service.tor_conn)
        self.assertFalse(hasattr(service.state.tenants[1],'ephs'))

    def test_target_is_frontend_loopback_port(self):
        service=self.service()
        onion=SimpleNamespace(hostname='synthetic.onion')
        with patch('globaleaks.services.tor.TorConfig'), patch('txtorcon.onion.EphemeralOnionService.create',return_value=succeed(onion)) as create:
            service.load_all_onion_services()
        self.assertEqual(create.call_args.args[2], ['80 127.0.0.1:8085'])
        self.assertIs(service.state.tenants[1].ephs,onion)
        service.reset()
        self.assertFalse(hasattr(service.state.tenants[1],'ephs'))
        self.assertIsNone(service.tor_conn)

    def test_failed_creation_clears_pending_marker(self):
        service=self.service()
        with patch('globaleaks.services.tor.TorConfig'), patch('txtorcon.onion.EphemeralOnionService.create',return_value=fail(RuntimeError('synthetic failure'))):
            service.load_all_onion_services()
        self.assertFalse(hasattr(service.state.tenants[1],'ephs'))

    def test_unload_removes_service_and_marker(self):
        service=self.service()
        onion=SimpleNamespace(remove=Mock(return_value=succeed(None)))
        service.state.tenants[1].ephs=onion
        result=service.unload_onion_service(1)
        self.assertTrue(result.called)
        onion.remove.assert_called_once_with()
        self.assertFalse(hasattr(service.state.tenants[1],'ephs'))

    def test_reconnect_reconciles_stale_ephemeral_markers(self):
        service=self.service()
        service.state.settings.tor_control='/synthetic/control'
        service.state.tenants[1].ephs=object()
        service.tor=succeed(None)
        connection=SimpleNamespace(protocol=SimpleNamespace())
        service.load_all_onion_services=Mock()
        with patch('globaleaks.services.tor.os.path.exists',return_value=True), patch('globaleaks.services.tor.os.access',return_value=True), patch('globaleaks.services.tor.build_local_tor_connection',return_value=succeed(connection)):
            service.operation()
        self.assertFalse(hasattr(service.state.tenants[1],'ephs'))
        self.assertIs(service.tor_conn,connection)
        service.load_all_onion_services.assert_called_once_with()

    def test_late_callback_cannot_reinstall_marker_from_previous_connection(self):
        service=self.service()
        pending=Deferred()
        with patch('globaleaks.services.tor.TorConfig'), patch('txtorcon.onion.EphemeralOnionService.create',return_value=pending):
            service.load_all_onion_services()
        service.reset()
        pending.callback(SimpleNamespace(hostname='synthetic.onion'))
        self.assertFalse(hasattr(service.state.tenants[1],'ephs'))
