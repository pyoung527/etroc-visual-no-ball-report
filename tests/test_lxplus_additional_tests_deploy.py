from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "hybrid-bbqc" / "openshift" / "deploy_additional_tests_lxplus.sh"


class LxplusAdditionalTestsDeployTests(unittest.TestCase):
    def test_helper_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exact_candidate_image_uses_real_startup_probe_contract(self):
        script = SCRIPT.read_text(encoding="utf-8")
        required = (
            "PROBE_BASE_DB=",
            "PROBE_BASE_SHA256=",
            "NEW_WEB_IMAGE",
            "candidate-startup-probe",
            "emptyDir",
            "'startupProbe'",
            "'failureThreshold':60",
            "'HOST','value':'127.0.0.1'",
            "PROBE_READY_SECONDS",
            "restartCount",
            "EXACT_CANDIDATE_STARTUP",
            "BBQC_STARTUP_OK",
            "host=127.0.0.1",
        )
        for value in required:
            self.assertIn(value, script)
        self.assertNotIn("'HOST','value':'0.0.0.0'", script)
        self.assertNotRegex(script, re.compile(r"(?m)^\s*assert\b"))

    def test_candidate_probe_precedes_production_mutation(self):
        script = SCRIPT.read_text(encoding="utf-8")
        probe = script.index("EXACT_CANDIDATE_STARTUP")
        dry_run = script.index(
            'oc -n "$PROJECT" replace --save-config=false --dry-run=server ', probe
        )
        mutation = script.index(
            'oc -n "$PROJECT" replace --save-config=false -f ', dry_run
        )
        self.assertLess(probe, dry_run)
        self.assertLess(dry_run, mutation)

    def test_forward_deployment_normalizes_localhost_probes(self):
        script = SCRIPT.read_text(encoding="utf-8")
        forward_start = script.index("desired_metadata={key: metadata[key]")
        forward_end = script.index("json.dump(desired, sys.stdout", forward_start)
        forward = script[forward_start:forward_end]
        self.assertIn("'HOST','value':'127.0.0.1'", forward)
        self.assertIn("web['startupProbe']", forward)
        self.assertIn("web['readinessProbe']", forward)
        self.assertIn("web['livenessProbe']", forward)
        self.assertIn("http://127.0.0.1:8080/api/health", forward)


if __name__ == "__main__":
    unittest.main()
