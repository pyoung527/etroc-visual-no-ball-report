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
            "SOURCE_REVISION='90b648221739588a373be9231be45743c40d66e1'",
            script,
        )
        expected = {
            "index.html": "63abb3062d2a65656066e1ced955f9b78357e76ece08cc223b5e6d0bec4956a7",
            "dashboard.css": "5f9d7e3bab4ac732d6e7800f2c2a70fe75184db6f00a6e41da2d677e1d1a5b8f",
            "dashboard.js": "317e358631a8cea15ea4dabe6369ab1f5480454baf6e7ddcfae66d9c1b3d1644",
            "etroc-optical.css": "e29d616a56987dc38039fe416c97d76651bee02cb59c4e9c3bcfc6465ea1c619",
            "etroc-optical.js": "64a372a7f1b3214d78e3724abe67f50e939c423e05ba4f355f01901f9a3ed4f3",
            "ETROC_MANIFEST_SHA256": "96de00c344aabb3152a0d44323cc52c26e1e930dad63f25ae1d59fb4be5d3f9e",
        }
        for filename, digest in expected.items():
            self.assertIn(filename, script)
            self.assertIn(digest, script)
        self.assertIn("sha256sum -c", script)
        self.assertIn("raw.githubusercontent.com/pyoung527/etroc-visual-no-ball-report", script)

    def test_helper_pins_complete_etroc_dataset_and_runtime_verification(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "ETROC_DATASET_REL='data/etroc-optical/ETROC_OI_2608'",
            "unexpected ETROC dataset manifest cardinality",
            "unsafe ETROC dataset manifest entry",
            "sum(path.startswith('montages/') for path in seen) != 36",
            "sum(path.startswith('previews/') for path in seen) != 36",
            "cd '/app/static/${ETROC_DATASET_REL}' && sha256sum -c SHA256SUMS",
            "payload.get('position_record_count') != 9216",
            "len(set(assets)) != 72",
        ):
            self.assertIn(required, script)
        self.assertIn('"${RAW_ROOT}/hybrid-bbqc/${ETROC_DATASET_REL}/${relative}"', script)

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
        self.assertIn("u=rwX,go=rX", script)
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
            "/app/static/etroc-optical.css",
            "/app/static/etroc-optical.js",
            "/app/static/${ETROC_DATASET_REL}/SHA256SUMS",
            "if runtime_schema_sha256 != os.environ['BACKUP_SCHEMA_SHA256']:",
            "if comments < int(os.environ['BEFORE_COMMENTS']):",
            "BBQC_STARTUP_OK|Serving /app/static with comments API on :8080;",
            "if grep -Eiq 'Traceback|unhandled exception|migration failed'",
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
