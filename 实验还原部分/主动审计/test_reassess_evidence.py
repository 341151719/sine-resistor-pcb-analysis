"""Ensure solver exit 0 alone cannot turn failed evidence into a valid result."""
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import reassess_evidence as audit


class EvidenceValidationTests(unittest.TestCase):
    def test_finite_measurement(self):
        self.assertEqual(audit.metric("ip_avg = -2.362349e-02 from=2e-4", "ip_avg"), -0.02362349)

    def test_missing_or_nonfinite_measurements_fail(self):
        for log in ("ngspice-42 done", "latepp = nan", "latepp = inf", "latepp = 1e999"):
            with self.subTest(log=log), self.assertRaises(RuntimeError):
                audit.metric(log, "latepp")

    def test_failed_or_incomplete_solver_output_is_rejected(self):
        cases = [
            (0, "ngspice-42 done"),
            (0, "latepp = 0\ntran simulation(s) aborted"),
            (0, "latepp = 0\nError: invalid command"),
            (0, "latepp = 0\ntimestep too small"),
            (1, "latepp = 0"),
        ]
        with tempfile.TemporaryDirectory() as directory, patch.object(audit, "OUTPUT", Path(directory)):
            for code, log in cases:
                result = SimpleNamespace(returncode=code, stdout=log)
                with self.subTest(code=code, log=log), patch.object(audit.subprocess, "run", return_value=result):
                    with self.assertRaises(RuntimeError):
                        audit.simulate("invalid", "* diagnostic\n.end\n", ("latepp",))

    def test_timeout_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audit, "OUTPUT", Path(directory)):
            with patch.object(audit.subprocess, "run", side_effect=subprocess.TimeoutExpired("ngspice", 60)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    audit.simulate("timeout", "* diagnostic\n.end\n", ("latepp",))


if __name__ == "__main__":
    unittest.main()
