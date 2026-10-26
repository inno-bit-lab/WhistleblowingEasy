import unittest
from types import SimpleNamespace
from unittest.mock import patch
from globaleaks.settings import Settings
from io import StringIO
Settings.eval_paths()
with patch.object(Settings, "logfile", "/tmp/rehearsal-test.log", create=True), patch("globaleaks.utils.log.openLogFile", return_value=StringIO()):
    from globaleaks.backend import Service

class RehearsalTests(unittest.TestCase):
    def test_rehearsal_starts_only_local_delivery_no_tor_or_cleanup(self):
        state = SimpleNamespace(settings=SimpleNamespace(rehearsal=True), jobs=[], services=[], jobs_monitor=None)
        with patch('globaleaks.backend.delivery.Delivery', return_value='delivery') as delivery, \
             patch('globaleaks.backend.tor.Tor') as tor, \
             patch('globaleaks.backend.job.JobsMonitor') as monitor, \
             patch('globaleaks.backend.jobs_list', [lambda: self.fail('ordinary scheduler started')]):
            Service.start_jobs(SimpleNamespace(state=state))
            delivery.assert_called_once_with()
            tor.assert_not_called()
            monitor.assert_called_once_with(['delivery'])
            self.assertEqual(state.services, [])

if __name__=='__main__': unittest.main()
