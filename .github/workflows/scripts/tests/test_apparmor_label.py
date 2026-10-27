"""Regression checks for the real AppArmor labels observed on CI runners."""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'check_apparmor_label.sh'


class AppArmorLabelTests(unittest.TestCase):
    def test_enforced_standalone_and_observed_stacked_profile(self):
        for label in ('usr.bin.globaleaks (enforce)',
                      'unconfined//&usr.bin.globaleaks (enforce)'):
            with self.subTest(label=label):
                self.assertEqual(subprocess.run(['sh', str(SCRIPT), label], capture_output=True).returncode, 0)

    def test_missing_wrong_or_non_enforcing_profile_is_rejected(self):
        for label in ('', 'unconfined', 'usr.bin.globaleaks (complain)',
                      'unconfined//&usr.bin.globaleaks (complain)',
                      'usr.bin.globaleaks-other (enforce)',
                      'docker-default (enforce)',
                      'unconfined//&usr.bin.globaleaks (mixed)'):
            with self.subTest(label=label):
                self.assertNotEqual(subprocess.run(['sh', str(SCRIPT), label], capture_output=True).returncode, 0)
