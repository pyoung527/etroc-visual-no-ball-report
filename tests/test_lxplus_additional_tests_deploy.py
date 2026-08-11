from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
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

    def test_rollback_renderer_rejects_same_name_with_new_uid(self):
        script = SCRIPT.read_text(encoding="utf-8")
        anchor = script.index('CURRENT_DEPLOYMENT="$current" ROLLBACK_DEPLOYMENT="$rendered"')
        code_start = script.index("import json, os", anchor)
        code_end = script.index("\nPY\n", code_start)
        renderer = script[code_start:code_end]
        stable_uid = "stable-deployment-uid"
        base_metadata = {
            "name": "etl-hybrid-bbqc",
            "namespace": "etroc-solder-inspection",
            "labels": {"app": "etl-hybrid-bbqc"},
            "annotations": {},
            "finalizers": [],
            "ownerReferences": [],
        }
        old = {
            "metadata": {**base_metadata, "uid": stable_uid, "resourceVersion": "100"},
            "spec": {"template": {"old": True}},
        }
        forward = {
            "metadata": {**base_metadata, "resourceVersion": "101"},
            "spec": {"template": {"candidate": True}},
        }
        current = {
            "metadata": {
                **base_metadata,
                "uid": "recreated-deployment-uid",
                "resourceVersion": "999",
            },
            "spec": forward["spec"],
        }
        with tempfile.TemporaryDirectory() as directory:
            paths = {
                "OLD_DEPLOYMENT_FILE": Path(directory) / "old.json",
                "FORWARD_DEPLOYMENT_FILE": Path(directory) / "forward.json",
                "CURRENT_DEPLOYMENT": Path(directory) / "current.json",
                "ROLLBACK_DEPLOYMENT": Path(directory) / "rendered.json",
            }
            for key, payload in (
                ("OLD_DEPLOYMENT_FILE", old),
                ("FORWARD_DEPLOYMENT_FILE", forward),
                ("CURRENT_DEPLOYMENT", current),
            ):
                paths[key].write_text(json.dumps(payload), encoding="utf-8")
            environment = os.environ.copy()
            environment.update({key: str(value) for key, value in paths.items()})
            environment["DEPLOYMENT_UID"] = stable_uid
            result = subprocess.run(
                [sys.executable, "-I", "-c", renderer],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            current["metadata"]["uid"] = stable_uid
            paths["CURRENT_DEPLOYMENT"].write_text(json.dumps(current), encoding="utf-8")
            accepted = subprocess.run(
                [sys.executable, "-I", "-c", renderer],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rollback target UID changed", result.stderr)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)


if __name__ == "__main__":
    unittest.main()
