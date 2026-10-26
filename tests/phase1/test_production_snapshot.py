"""Recovery contract of the operator snapshot helper; no live service access."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('snapshot', Path(__file__).resolve().parents[2] / 'scripts/dev/snapshot-production.py')
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


class SnapshotRecoveryTests(unittest.TestCase):
    def test_copy_timeout_restarts_app_and_timer_without_touching_live_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (source / 'globaleaks.db').write_bytes(b'synthetic')
            imports = root / 'imports'
            states = {snapshot.APP: True, snapshot.TIMER: True, snapshot.MONITOR: False}
            actions = []
            def control(action, *units):
                actions.append((action, units))
                for unit in units:
                    states[unit] = action == 'start'
            with patch.object(snapshot, 'SOURCE', source), patch.object(snapshot, 'IMPORTS', imports), \
                 patch.object(snapshot.os, 'geteuid', return_value=0), \
                 patch.object(snapshot, 'active', side_effect=lambda u: states[u]), \
                 patch.object(snapshot, 'control', side_effect=control), \
                 patch.object(snapshot.subprocess, 'run', side_effect=subprocess.TimeoutExpired('cp', 120)), \
                 patch.object(snapshot.sys, 'argv', ['snapshot-production.py']):
                with self.assertRaises(subprocess.TimeoutExpired):
                    snapshot.main()
            self.assertTrue(states[snapshot.APP])
            self.assertTrue(states[snapshot.TIMER])
            self.assertEqual(actions[-2:], [('start', (snapshot.APP,)), ('start', (snapshot.TIMER,))])
            self.assertEqual((source / 'globaleaks.db').read_bytes(), b'synthetic')
            self.assertEqual(list(imports.rglob('snapshot.json')), [])

    def test_non_privileged_execution_refused_before_service_access(self):
        with patch.object(snapshot.os, 'geteuid', return_value=1002), \
             patch.object(snapshot, 'active') as active, \
             patch.object(snapshot.sys, 'argv', ['snapshot-production.py']):
            with self.assertRaises(SystemExit) as result:
                snapshot.main()
            self.assertEqual(result.exception.code, 2)
            active.assert_not_called()


if __name__ == '__main__':
    unittest.main()
