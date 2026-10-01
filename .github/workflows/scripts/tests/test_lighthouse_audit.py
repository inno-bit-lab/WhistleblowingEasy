import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location("lighthouse_audit", Path(__file__).parents[1] / "lighthouse_audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LighthouseAuditTest(unittest.TestCase):
    def run_case(self, results):
        with tempfile.TemporaryDirectory() as directory:
            prefix = str(Path(directory) / "audit")
            calls = []

            def run(command):
                calls.append(command)
                status, report = results[len(calls) - 1]
                Path(prefix + ".report.json").write_text(json.dumps(report))
                return SimpleNamespace(returncode=status)

            status = module.audit(["https://localhost/#/login", f"--output-path={prefix}"], run)
            return status, len(calls)

    def test_missing_trace_is_retried(self):
        self.assertEqual(self.run_case([(1, {"runtimeError": {"code": "NO_NAVSTART"}}), (0, {})]), (0, 2))

    def test_missing_trace_eventually_fails(self):
        self.assertEqual(self.run_case([(1, {"runtimeError": {"code": "NO_NAVSTART"}})] * 3), (1, 3))

    def test_other_runtime_errors_are_not_retried(self):
        self.assertEqual(self.run_case([(1, {"runtimeError": {"code": "NO_FCP"}})]), (1, 1))

    def test_low_performance_score_is_not_retried(self):
        self.assertEqual(self.run_case([(0, {"categories": {"performance": {"score": 0.1}}})]), (0, 1))
