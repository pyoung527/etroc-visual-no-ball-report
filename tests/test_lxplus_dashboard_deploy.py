from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "hybrid-bbqc" / "openshift" / "deploy_dashboard_overlay_lxplus.sh"


class LxplusDashboardDeployTests(unittest.TestCase):
    def test_helper_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_helper_pins_release_and_download_checksums(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            "SOURCE_REVISION='d720aaff176f70e539d9833fec7ba3ca12ca2dcf'",
            script,
        )
        expected = {
            "index.html": "1437ad8b600151f188a6cd1c344251fdf5cdf58b41d4f60e12e4443bf81afe05",
            "dashboard.css": "45c9e4ea6ebba50a6021bda5d2298b7cd4fa4dc581d3839402017f999522e053",
            "dashboard.js": "139367fcf30f4df939d5e83bc606379e045ea0c735238d44f8167386e2e5ed31",
        }
        for filename, digest in expected.items():
            self.assertIn(filename, script)
            self.assertIn(digest, script)
        self.assertIn("sha256sum -c", script)
        self.assertIn("raw.githubusercontent.com/pyoung527/etroc-visual-no-ball-report", script)

    def test_helper_fails_closed_on_context_and_permissions(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "set -Eeuo pipefail",
            "api.paas.okd.cern.ch",
            "EXPECTED_USER='ypark'",
            "PROJECT='etroc-solder-inspection'",
            "verify_context",
            "oc auth can-i create builds/build.openshift.io",
            "oc auth can-i update deployments.apps",
            "strategy.type",
            "Recreate",
            "DEPLOYMENT_UID",
            "select_single_app_pod.py",
        ):
            self.assertIn(required, script)
        self.assertNotRegex(script, re.compile(r"(?m)^\s*assert\b"))

    def test_helper_uses_immutable_overlay_build_with_allowlisted_context(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertRegex(script, r"OLD_WEB_IMAGE=.*imageID")
        self.assertIn("case \"$OLD_WEB_IMAGE\" in *@sha256:*)", script)
        self.assertIn("FROM ${OLD_WEB_IMAGE}", script)
        self.assertIn("COPY overlay/ /app/static/", script)
        self.assertIn("u=rw,go=r", script)
        self.assertIn("--from-dir=\"$BUILD_CONTEXT\"", script)
        self.assertNotIn("--from-dir=.", script)
        self.assertNotIn("oc rollout undo", script)
        self.assertIn("BUILD_CONTEXT_SHA256", script)
        self.assertIn("EXPECTED_TOP_LEVEL", script)

    def test_helper_verifies_backup_and_preserves_rollback_coordinates(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "source.backup(target)",
            "PRAGMA integrity_check",
            "BEFORE_COMMENTS",
            "LOCAL_BACKUP",
            "BACKUP_SHA256",
            "BACKUP_SCHEMA_SHA256",
            "sqlite_master",
            "runtime_schema_sha256",
            "OLD_DEPLOYMENT_FILE",
            "OLD_DEPLOYMENT_SHA256",
            "OLD_PROXY_IMAGE",
            "FORWARD_DEPLOYMENT_FILE",
            "FORWARD_DEPLOYMENT_SHA256",
            "DEPLOYMENT_RESOURCE_VERSION",
            "current-release.env",
            "rollback_deployment",
        ):
            self.assertIn(required, script)
        self.assertNotIn("rollback_deployment ||", script)
        self.assertIn('test "$(sha256sum "$OLD_DEPLOYMENT_FILE"', script)
        runtime_gate = script[script.index('oc -n "$PROJECT" exec -i "$POD" -c web -- env BEFORE_COMMENTS='):]
        self.assertNotIn("hybrid_registry", runtime_gate)
        self.assertNotIn("hybrid_target_aliases", runtime_gate)

    def test_helper_pins_and_verifies_rollout_and_static_files(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "NEW_WEB_IMAGE",
            "BUILD_OUTPUT_DIGEST",
            'get "isimage/etl-hybrid-bbqc@${BUILD_OUTPUT_DIGEST}"',
            "test \"$NEW_WEB_IMAGE\" != \"$OLD_WEB_IMAGE\"",
            'oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$FORWARD_DEPLOYMENT_FILE"',
            'oc -n "$PROJECT" replace --save-config=false -f "$FORWARD_DEPLOYMENT_FILE"',
            "oc -n \"$PROJECT\" rollout status",
            "POD_WEB_IMAGE",
            "test \"$POD_WEB_IMAGE\" = \"$NEW_WEB_IMAGE\"",
            "/app/static/index.html",
            "/app/static/dashboard.css",
            "/app/static/dashboard.js",
            "if runtime_schema_sha256 != os.environ['BACKUP_SCHEMA_SHA256']:",
            "if comments < int(os.environ['BEFORE_COMMENTS']):",
            "SSO_PROXY_GATE PASS",
        ):
            self.assertIn(required, script)
        self.assertNotIn("get istag etl-hybrid-bbqc:latest", script)

    def test_helper_bootstraps_official_device_flow_without_printing_tokens(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("d049ae2182f795c4f5dec15dfb8dbef8971518da", script)
        self.assertIn("67b6eebc40f8b36e44124bfcec3fc526e29f93830fa203d0c8feeedfd99e9ca3", script)
        self.assertIn("179d62436395bd82aa67a1cc4a902ec6e17a12e07d53c1a71f1298079a4b041c", script)
        self.assertIn("oc sso-login --server=\"$API_SERVER\"", script)
        self.assertIn("--require-hashes", script)
        self.assertIn("--only-binary=:all:", script)
        self.assertIn("python3 -I", script)
        self.assertIn("command and output omitted because they may contain a bearer token", script)
        self.assertIn("-u PYTHONOPTIMIZE", script)
        self.assertIn('install_root="${WORK_DIR}/oc-sso-login"', script)
        self.assertNotIn("command -v oc-sso_login", script)
        self.assertNotRegex(script, re.compile(r"echo.*(?:token|password|secret)", re.I))

    def test_helper_handles_interrupts_and_preserves_full_replace_metadata(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "trap 'on_signal HUP 129' HUP",
            "trap 'on_signal INT 130' INT",
            "trap 'on_signal TERM 143' TERM",
            "attempt_rollback",
            "finalizers",
            "ownerReferences",
            "image.openshift.io/triggers",
            "BUILDCONFIG_RESOURCE_VERSION",
            ".status.output.to.imageDigest",
            "kubectl.kubernetes.io/last-applied-configuration",
            "--save-config=false",
        ):
            self.assertIn(required, script)
        self.assertNotIn("exit 1", script)

    def test_helper_allows_build_controller_status_updates_but_rejects_config_drift(self):
        script = SCRIPT.read_text(encoding="utf-8")
        start_build = script.index('BUILD_NAME="$(oc -n "$PROJECT" start-build')
        digest_read = script.index('BUILD_OUTPUT_DIGEST="$(oc -n "$PROJECT" get "$BUILD_NAME"')
        post_build = script[start_build:digest_read]
        self.assertNotIn(
            "buildconfig/\"$BUILDCONFIG\" -o jsonpath='{.metadata.resourceVersion}'",
            post_build,
        )
        for required in (
            "CURRENT_BUILDCONFIG_FILE",
            "captured BuildConfig UID changed after build",
            "captured BuildConfig spec changed after build",
            "captured BuildConfig metadata changed after build",
        ):
            self.assertIn(required, post_build)
        self.assertNotIn("captured BuildConfig generation changed after build", post_build)


if __name__ == "__main__":
    unittest.main()
