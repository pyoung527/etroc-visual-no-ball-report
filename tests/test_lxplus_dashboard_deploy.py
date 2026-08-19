from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "hybrid-bbqc" / "openshift" / "deploy_dashboard_overlay_lxplus.sh"


class LxplusDashboardDeployTests(unittest.TestCase):
    def test_dashboard_headroom_gate_accepts_sufficient_numeric_space(self):
        # Given: a database, PVC, and AFS quota with room beyond every explicit margin.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index(
                "measure_dashboard_headroom() {"
            )
        ]

        # When: the gate receives strict numeric KiB measurements.
        result = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1048576 1049600 5000000 1000000 0"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: it permits the release and emits only numeric headroom evidence.
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"DASHBOARD_HEADROOM PASS db_bytes=1048576 .*afs_free_kib=4000000")

    def test_dashboard_headroom_gate_rejects_low_pvc_space(self):
        # Given: the same-filesystem SQLite backup would not fit with its safety margin.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index(
                "measure_dashboard_headroom() {"
            )
        ]

        # When: PVC available KiB is below the required backup headroom.
        result = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1048576 1000 5000000 1000000 0"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: the gate fails closed before the backup can start.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PVC backup headroom is insufficient", result.stderr)

    def test_dashboard_headroom_gate_rejects_low_afs_space(self):
        # Given: AFS has less free KiB than the copied DB, evidence allowance, and margin.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index(
                "measure_dashboard_headroom() {"
            )
        ]

        # When: the exact quota/used values leave inadequate free space.
        result = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1048576 1049600 1000 999 0"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: no release artifacts are permitted.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AFS release-evidence headroom is insufficient", result.stderr)

    def test_dashboard_headroom_gate_rejects_malformed_or_overflow_values(self):
        # Given: quota tooling can return corrupted, negative, or overflow-like values.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index(
                "measure_dashboard_headroom() {"
            )
        ]

        # When: each untrusted measurement crosses the numeric boundary.
        malformed = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1KiB 1000 5000000 1 0"],
            check=False,
            capture_output=True,
            text=True,
        )
        negative = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1024 -1 5000000 1 0"],
            check=False,
            capture_output=True,
            text=True,
        )
        overflow = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 999999999999999999999999 1000 5000000 1 0"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: all malformed values fail closed without arithmetic wraparound.
        for result in (malformed, negative, overflow):
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid numeric headroom measurement", result.stderr)

    def test_dashboard_headroom_gate_rejects_malformed_web_container_output(self):
        # Given: the production pod command returns extra text instead of two numeric values.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index("verify_context() {")
        ]

        # When: the measurement gate consumes that command output.
        result = subprocess.run(
            [
                "bash",
                "-c",
                (
                    f"{gate}\n"
                    "PROJECT=fixture; POD=fixture; BACKUP_DIR=/nonexistent; "
                    "oc() { printf '1024 999999 unexpected\\n'; }\n"
                    "measure_dashboard_headroom"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: it fails before it can inspect AFS or create any evidence.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed web-container DB/PVC output", result.stderr)

    def test_dashboard_headroom_gate_rejects_retention_cap_without_deleting_evidence(self):
        # Given: the configured count of release evidence sets already exists.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index(
                "measure_dashboard_headroom() {"
            )
        ]

        # When: another set would exceed the no-auto-delete retention cap.
        result = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1048576 1049600 5000000 1000000 20"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: the operator is told to archive or clean up manually.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manual archive/cleanup", result.stderr)

    def test_dashboard_headroom_gate_precedes_backup_and_release_artifact_writes(self):
        # Given: backup and captured-object writes are production evidence.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: deployment ordering is inspected.

        # Then: the gate runs before both the remote backup and the first BACKUP_DIR write.
        gate = script.index("measure_dashboard_headroom\ninstall -d -m 700 \"$BACKUP_DIR\"")
        backup = script.index('oc -n "$PROJECT" exec -i "$POD" -c web -- env BACKUP=')
        artifact_write = script.index('oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$CAPTURED_DEPLOYMENT_FILE"')
        self.assertLess(gate, backup)
        self.assertLess(gate, artifact_write)
        self.assertLess(gate, script.index('install -d -m 700 "$BACKUP_DIR"'))
        self.assertNotIn("rm -f \"$BACKUP_DIR", script)

    def test_helper_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_helper_retries_transient_asset_downloads(self):
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("download() {")
        end = script.index("\n}\n", start) + 3
        download_function = script[start:end]
        payload = b"immutable-dashboard-asset"

        class Handler(BaseHTTPRequestHandler):
            attempts = 0

            def do_GET(self):
                Handler.attempts += 1
                if Handler.attempts < 3:
                    self.send_response(502)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                del format, args
                return

        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except PermissionError as error:
            self.skipTest(f"loopback fixture unavailable in this sandbox: {error}")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "asset"
                url = f"http://127.0.0.1:{server.server_port}/asset"
                command = (
                    f"{download_function}\n"
                    f"download {shlex.quote(url)} {shlex.quote(str(destination))}"
                )
                result = subprocess.run(
                    ["bash", "-c", command], check=False,
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(destination.read_bytes(), payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(Handler.attempts, 3)

    def test_helper_fails_after_permanent_or_exhausted_download_errors(self):
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("download() {")
        end = script.index("\n}\n", start) + 3
        download_function = script[start:end]

        def run_case(status_code):
            class Handler(BaseHTTPRequestHandler):
                attempts = 0

                def do_GET(self):
                    Handler.attempts += 1
                    self.send_response(status_code)
                    self.end_headers()

                def log_message(self, format, *args):
                    del format, args
                    return

            try:
                server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            except PermissionError as error:
                self.skipTest(f"loopback fixture unavailable in this sandbox: {error}")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory) / "asset"
                    url = f"http://127.0.0.1:{server.server_port}/asset"
                    command = (
                        f"{download_function}\n"
                        f"download {shlex.quote(url)} {shlex.quote(str(destination))}"
                    )
                    result = subprocess.run(
                        ["bash", "-c", command], check=False,
                        capture_output=True, text=True,
                    )
                    exists = destination.exists()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            return result, Handler.attempts, exists

        permanent, permanent_attempts, permanent_exists = run_case(404)
        exhausted, exhausted_attempts, exhausted_exists = run_case(502)
        self.assertNotEqual(permanent.returncode, 0)
        self.assertEqual(permanent_attempts, 1)
        self.assertFalse(permanent_exists)
        self.assertNotEqual(exhausted.returncode, 0)
        self.assertEqual(exhausted_attempts, 6)
        self.assertFalse(exhausted_exists)

    def test_helper_pins_release_and_download_checksums(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            "SOURCE_REVISION='4e30f825ea9d2c72c905993fd171ed08c5b6963f'",
            script,
        )
        expected = {
            "index.html": "af5dbe0db30b41bb231be3248a4c9a1aebd831988759d839aece1c07c996e2ae",
            "dashboard.css": "5f9d7e3bab4ac732d6e7800f2c2a70fe75184db6f00a6e41da2d677e1d1a5b8f",
            "dashboard.js": "317e358631a8cea15ea4dabe6369ab1f5480454baf6e7ddcfae66d9c1b3d1644",
            "etroc-optical.css": "d34af84b4828f6b354813c3356fce1d1f064cbc09826c0d4abd999451bf49d1d",
            "etroc-optical.js": "cf44ffb22cde59e6f527e02711db01f594c69081cc53ec275758b77ec7f35ecd",
            "etroc-review.js": "2c1bcdd76b0fec0b05c32807b23526b1da543b9adde1429f87a1ce64dbce7809",
            "lgad-optical-stats.js": "e3cfb2eff6b8391cdae80b19cf75740bb5680c12434402594eb894ce36796a02",
            "ETROC_MANIFEST_SHA256": "616a369eb3861a0d3c57e855a8136a0843fde658934537edfedad8f32644cc29",
            "SERVER_PY_SHA256": "45c822200ea03ae433619b457c8764aec52a94b7716c2241d8f8e88feeb1056e",
            "ETROC_REVIEWS_PY_SHA256": "0da4caf6bc275941c00bda485daf1bdc9475646e1c1528af0a941cfea0b35984",
            "DEPLOYMENT_MANIFEST_SHA256": "0b102e22bd2a3ee08f9bde197da4a6fdad105beb1425e1ed91e604c98ad5b809",
            "SERVICE_MANIFEST_SHA256": "84b99d048fcf52d5dfbe9ee919287b36197429818228682fccbcc4ad4e5dcf5c",
            "ROUTE_MANIFEST_SHA256": "23b1dbfa7cd930754ebc70eef3c853e164e55c43dbb8e05e5d0affad71ec8f43",
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

    def test_helper_packages_pinned_review_frontend_and_backend_runtime(self):
        # Given: the release needs the ETROC review UI and its server-side schema code.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the immutable release context is assembled.

        # Then: every changed runtime artifact is downloaded, hashed, and copied next to
        # the server entry point used by the image.
        for required in (
            "ETROC_REVIEW_JS_SHA256=",
            "SERVER_PY_SHA256=",
            "ETROC_REVIEWS_PY_SHA256=",
            '"${RAW_ROOT}/hybrid-bbqc/${file}"',
            '"${RAW_ROOT}/hybrid-bbqc/server.py"',
            '"${RAW_ROOT}/hybrid-bbqc/etroc_reviews.py"',
            '"$ETROC_REVIEW_JS_SHA256"',
            '"$SERVER_PY_SHA256"',
            '"$ETROC_REVIEWS_PY_SHA256"',
            "runtime/server.py",
            "runtime/etroc_reviews.py",
            "COPY runtime/ /app/static/",
            "/app/static/etroc-review.js",
            "/app/static/server.py",
            "/app/static/etroc_reviews.py",
        ):
            self.assertIn(required, script)
        self.assertLess(script.index("COPY runtime/ /app/static/"), script.index("USER app"))

    def test_helper_probes_content_addressed_montage_from_publication(self):
        # Given: the ETROC publication identifies montage assets by digest.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: post-rollout HTTP assets are verified.

        # Then: the probe derives a URI from chips.json rather than using the obsolete
        # serial-addressed montage location.
        probe_start = script.index("RUNTIME_HTTP_ASSETS PASS") - 3000
        probe_end = script.index("ETROC_REVIEW_RUNTIME_CONTRACT PASS")
        probe = script[probe_start:probe_end]
        self.assertIn("record['montage_uri']", probe)
        self.assertIn("content-addressed montage", probe)
        self.assertNotIn("montages/W02G4-44.jpg", probe)

    def test_helper_preflights_candidate_review_migration_and_legacy_comments_before_rollout(self):
        # Given: a backed-up legacy comments database and the previously deployed image.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the script prepares a release.

        # Then: it migrates only a disposable copy, validates exact schema and integrity,
        # reruns the migration, and exercises old Hybrid comments reads/writes before any
        # Deployment replacement can mutate production.
        for required in (
            "CANDIDATE_DB",
            "CANDIDATE_ETROC_SCHEMA PASS",
            "CANDIDATE_LEGACY_COMMENTS_COMPAT PASS",
            "init_schema(candidate)",
            "etroc_reviews.validate_schema(db)",
            "PRAGMA foreign_key_check",
            "PRAGMA integrity_check",
            "OLD_RUNTIME_SERVER",
            "oc image extract \"$OLD_WEB_IMAGE\" --path \"/app/static/server.py:${OLD_RUNTIME_DIR}\"",
            "previous-binary comments",
        ):
            self.assertIn(required, script)
        candidate_gate = script.index("CANDIDATE_LEGACY_COMMENTS_COMPAT PASS")
        mutation = script.index('ROLLOUT_MUTATED=1')
        self.assertLess(candidate_gate, mutation)

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
            "/app/static/lgad-optical-stats.js",
            "/app/static/${ETROC_DATASET_REL}/SHA256SUMS",
            "if runtime_hybrid_schema_sha256 != os.environ['BACKUP_HYBRID_SCHEMA_SHA256']:",
            "if comments < int(os.environ['BEFORE_COMMENTS']):",
            "BBQC_STARTUP_OK|Serving /app/static with comments API on :8080;",
            "if grep -Eiq 'Traceback|unhandled exception|migration failed'",
            "SSO_PROXY_GATE PASS",
        ):
            self.assertIn(required, script)
        self.assertNotIn("get istag etl-hybrid-bbqc:latest", script)
        self.assertIn("external trusted-header spoof was accepted", script)
        self.assertIn("internal proxy-derived allowlisted identity was not accepted", script)

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
            "validated Build output image digest is invalid",
            "kubectl.kubernetes.io/last-applied-configuration",
            "--save-config=false",
        ):
            self.assertIn(required, script)
        self.assertNotIn("exit 1", script)

    def test_rollback_renderer_rejects_same_name_with_new_uid(self):
        script = SCRIPT.read_text(encoding="utf-8")
        anchor = script.index('CURRENT_DEPLOYMENT="$current_file" ROLLBACK_DEPLOYMENT="$rendered_file"')
        code_start = script.index("import copy, json, os", anchor)
        code_end = script.index("\nPY\n", code_start)
        renderer = script[code_start:code_end]
        stable_uid = "stable-deployment-uid"
        base_metadata = {
            "name": "etl-hybrid-bbqc",
            "namespace": "etroc-solder-inspection",
            "uid": stable_uid,
            "labels": {"app": "etl-hybrid-bbqc"},
            "annotations": {},
            "finalizers": [],
            "ownerReferences": [],
        }
        old = {
            "kind": "Deployment",
            "metadata": {**base_metadata, "resourceVersion": "100"},
            "spec": {"template": {"old": True}},
        }
        forward = {
            "kind": "Deployment",
            "metadata": {**base_metadata, "resourceVersion": "101"},
            "spec": {"template": {"candidate": True}},
        }
        current = {
            "kind": "Deployment",
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
                "ROLLBACK_ACTION_FILE": Path(directory) / "action",
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
            environment["EXPECTED_UID"] = stable_uid
            rejected = subprocess.run(
                [sys.executable, "-I", "-c", renderer], check=False,
                capture_output=True, text=True, env=environment,
            )
            current["metadata"]["uid"] = stable_uid
            paths["CURRENT_DEPLOYMENT"].write_text(json.dumps(current), encoding="utf-8")
            accepted = subprocess.run(
                [sys.executable, "-I", "-c", renderer], check=False,
                capture_output=True, text=True, env=environment,
            )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("rollback target UID changed", rejected.stderr)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_rollback_renderer_recovers_each_partial_forward_state(self):
        # Given: forward replacement can stop after any independently replaced object.
        script = SCRIPT.read_text(encoding="utf-8")
        anchor = script.index('CURRENT_DEPLOYMENT="$current_file" ROLLBACK_DEPLOYMENT="$rendered_file"')
        code_start = script.index("import copy, json, os", anchor)
        code_end = script.index("\nPY\n", code_start)
        renderer = script[code_start:code_end]

        # When: each current object is classified against its captured and forward forms.
        stable_uid = "stable-resource-uid"
        metadata = {
            "name": "etl-hybrid-bbqc",
            "namespace": "etroc-solder-inspection",
            "uid": stable_uid,
            "labels": {"app": "etl-hybrid-bbqc"},
            "annotations": {"bbqc.cern.ch/release-mode": "immutable-overlay"},
            "finalizers": [],
            "ownerReferences": [],
        }
        scenarios = (
            ("all forward", {"Deployment": "forward", "Service": "forward", "Route": "forward"}, 0),
            ("service only forward", {"Deployment": "old", "Service": "forward", "Route": "old"}, 0),
            ("service and route forward", {"Deployment": "old", "Service": "forward", "Route": "forward"}, 0),
            ("all already old", {"Deployment": "old", "Service": "old", "Route": "old"}, 0),
            ("foreign drift", {"Deployment": "old", "Service": "foreign", "Route": "old"}, 1),
            ("recreated uid", {"Deployment": "old", "Service": "recreated", "Route": "old"}, 1),
        )
        for name, states, expected_returncode in scenarios:
            for kind, state in states.items():
                with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as directory:
                    old = {"apiVersion": "v1", "kind": kind, "metadata": {**metadata, "resourceVersion": "10"}, "spec": {"release": "old", "kind": kind}}
                    forward = {"apiVersion": "v1", "kind": kind, "metadata": {**metadata, "resourceVersion": "11"}, "spec": {"release": "forward", "kind": kind}}
                    current = {"old": old, "forward": forward, "foreign": {**forward, "spec": {"release": "foreign", "kind": kind}}, "recreated": {**forward, "metadata": {**forward["metadata"], "uid": "recreated-resource-uid"}}}[state]
                    paths = {
                        "CAPTURED_OBJECT_FILE": Path(directory) / "old.json",
                        "FORWARD_OBJECT_FILE": Path(directory) / "forward.json",
                        "CURRENT_DEPLOYMENT": Path(directory) / "current.json",
                        "ROLLBACK_DEPLOYMENT": Path(directory) / "rendered.json",
                        "ROLLBACK_ACTION_FILE": Path(directory) / "action",
                    }
                    for key, payload in (("CAPTURED_OBJECT_FILE", old), ("FORWARD_OBJECT_FILE", forward), ("CURRENT_DEPLOYMENT", current)):
                        paths[key].write_text(json.dumps(payload), encoding="utf-8")
                    environment = os.environ.copy()
                    environment.update({key: str(value) for key, value in paths.items()})
                    environment["OLD_DEPLOYMENT_FILE"] = str(paths["CAPTURED_OBJECT_FILE"])
                    environment["EXPECTED_UID"] = stable_uid
                    result = subprocess.run(
                        [sys.executable, "-I", "-c", renderer], check=False,
                        capture_output=True, text=True, env=environment,
                    )

                    # Then: only forward-owned state produces a resourceVersion-aware restore.
                    self.assertEqual(result.returncode, expected_returncode if state in {"foreign", "recreated"} else 0, result.stderr)
                    if state not in {"foreign", "recreated"}:
                        expected_action = "restore" if state == "forward" else "unchanged"
                        self.assertEqual(paths["ROLLBACK_ACTION_FILE"].read_text(encoding="utf-8").strip(), expected_action)
                        if expected_action == "restore":
                            rendered = json.loads(paths["ROLLBACK_DEPLOYMENT"].read_text(encoding="utf-8"))
                            self.assertEqual(rendered["spec"], old["spec"])
                            self.assertEqual(rendered["metadata"]["resourceVersion"], "11")

    def test_rollback_replaces_only_restore_marked_objects(self):
        # Given: rollback actions are persisted as machine-readable files.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the rollback applies its server dry-runs and replacements.
        rollback = script[script.index("rollback_deployment() {") : script.index("attempt_rollback() {")]

        # Then: conditional markers, not command-output text, gate every replacement.
        self.assertIn("ROLLBACK_ACTION_FILE", script)
        self.assertIn('test "$(cat "$deployment_action")" = restore', rollback)
        self.assertIn('test "$(cat "$service_action")" = restore', rollback)
        self.assertIn('test "$(cat "$route_action")" = restore', rollback)

    def test_helper_runs_pinned_executable_build_provenance_validator(self):
        script = SCRIPT.read_text(encoding="utf-8")
        start_build = script.index('BUILD_NAME="$(oc -n "$PROJECT" start-build')
        validator_run = script.index('python3 -I "$VALIDATOR"', start_build)
        image_lookup = script.index('NEW_WEB_IMAGE="$(oc -n "$PROJECT" get "isimage/', validator_run)
        post_validation = script[validator_run:image_lookup]
        for required in (
            "VALIDATOR_SHA256='ecec82614fdc8c6524c722fd5809886d8fbe1e7799d6b04a0da2f50cfdd1f9f8'",
            '"${RAW_ROOT}/hybrid-bbqc/openshift/validate_build_provenance.py"',
            'printf \'%s  %s\\n\' "$VALIDATOR_SHA256" "$VALIDATOR" | sha256sum -c -',
            "CURRENT_BUILDCONFIG_FILE",
            "BUILD_FILE",
            'python3 -I "$VALIDATOR"',
            '--captured "$BUILDCONFIG_FILE" --current "$CURRENT_BUILDCONFIG_FILE"',
            '--build "$BUILD_FILE" --name "$BUILDCONFIG" --namespace "$PROJECT"',
        ):
            self.assertIn(required, script)
        self.assertIn('BUILD_OUTPUT_DIGEST="$(python3 -I - "$BUILD_FILE"', post_validation)
        self.assertNotIn('oc -n "$PROJECT" get "$BUILD_NAME"', post_validation)

    def test_helper_exercises_etroc_assets_through_runtime_http(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "RUNTIME_HTTP_ASSETS PASS",
            "http://127.0.0.1:8080/",
            "etroc-optical.js",
            "etroc-optical.css",
            "lgad-optical-stats.js",
            "data/etroc-optical/ETROC_OI_2608/chips.json",
            "record['preview_uri']",
            "record['montage_uri']",
            "montages/sha256/",
        ):
            self.assertIn(required, script)
        mutation = script.index('oc -n "$PROJECT" replace --save-config=false -f "$FORWARD_DEPLOYMENT_FILE"')
        http_gate = script.index("RUNTIME_HTTP_ASSETS PASS")
        release_pass = script.index("DEPLOYMENT PASS")
        self.assertLess(mutation, http_gate)
        self.assertLess(http_gate, release_pass)

    def test_canonical_manifests_define_one_verified_oauth_exposure_boundary(self):
        # Given: one canonical manifest is required for each OpenShift object kind.
        manifests = {
            "Deployment": ROOT / "hybrid-bbqc" / "openshift" / "deployment.yaml",
            "Service": ROOT / "hybrid-bbqc" / "openshift" / "service.yaml",
            "Route": ROOT / "hybrid-bbqc" / "openshift" / "route.yaml",
        }

        # When: each baseline manifest is safely loaded independently.
        objects = {
            kind: yaml.safe_load(path.read_text(encoding="utf-8"))
            for kind, path in manifests.items()
        }

        # Then: it contains exactly its declared kind and the Route can expose only oauth.
        self.assertEqual({payload["kind"] for payload in objects.values()}, set(manifests))
        self.assertEqual(objects["Deployment"]["kind"], "Deployment")
        self.assertEqual(objects["Service"]["kind"], "Service")
        self.assertEqual(objects["Route"]["kind"], "Route")
        self.assertEqual(
            objects["Service"]["spec"]["ports"],
            [{"name": "oauth", "port": 4180, "targetPort": "oauth", "protocol": "TCP"}],
        )
        self.assertEqual(objects["Route"]["spec"]["to"], {"kind": "Service", "name": "etl-hybrid-bbqc"})
        self.assertEqual(objects["Route"]["spec"]["port"], {"targetPort": "oauth"})
        self.assertEqual(objects["Route"]["spec"]["tls"], {
            "termination": "edge",
            "insecureEdgeTerminationPolicy": "Redirect",
        })
        self.assertNotIn("targetPort: web", manifests["Service"].read_text(encoding="utf-8"))

    def test_helper_preflights_normalized_reviewer_allowlist_without_logging_values(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "ETROC_REVIEWER_USERS",
            "ETROC_REVIEWER_USERS_NORMALIZED",
            "ETROC_REVIEWER_USERS_COUNT",
            "ETROC_REVIEWER_USERS_SHA256",
            "ETROC_REVIEWER_ALLOWLIST PASS count=",
            "ETROC_REVIEWER_USERS must contain at least one normalized identity",
            'env ETROC_REVIEWER_USERS="$ETROC_REVIEWER_USERS_NORMALIZED"',
        ):
            self.assertIn(required, script)
        self.assertNotIn("ETROC_REVIEWER_USERS_NORMALIZED}>", script)

    def test_helper_gates_content_addressed_montages_and_publication_hash(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "CHIPS_PUBLICATION_SHA256",
            "hashlib.sha256((root / 'chips.json').read_bytes()).hexdigest()",
            "montages/sha256/",
            "path_digest != montage_sha256",
            "hashlib.sha256(montage_path.read_bytes()).hexdigest() != montage_sha256",
            "len(evidence) != 36",
            "duplicate ETROC acquisition_id",
            "duplicate canonical ETROC evidence key",
        ):
            self.assertIn(required, script)

    def test_helper_gates_exact_review_runtime_contract_and_identity_boundary(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "ETROC_REVIEW_RUNTIME_CONTRACT PASS",
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608",
            "record_count') != 36",
            "len(evidence) != 36",
            "publication_sha256') != os.environ['CHIPS_PUBLICATION_SHA256']",
            "etroc_review_schema",
            "etroc_review_events",
            "external trusted-header spoof was accepted",
            "internal proxy-derived allowlisted identity was not accepted",
            "X-Forwarded-Email: attacker@cern.ch",
            "X-Forwarded-Email: ${ETROC_REVIEWER_TEST_USER}",
        ):
            self.assertIn(required, script)
        self.assertNotIn("X-ETROC-Author", script)

    def test_deployment_declares_the_exact_loopback_oauth2_proxy_boundary(self):
        # Given: the production Deployment contains no Service or Route resources.
        deployment = (ROOT / "hybrid-bbqc" / "openshift" / "deployment.yaml").read_text(
            encoding="utf-8"
        )

        # When: the deployment manifest is inspected locally.

        # Then: the proxy digest/listener and loopback-only backend contract are pinned.
        for required in (
            "quay.io/oauth2-proxy/oauth2-proxy@sha256:",
            "containerPort: 4180",
            "--http-address=0.0.0.0:4180",
            "--upstream=http://127.0.0.1:8080",
            "value: \"127.0.0.1\"",
        ):
            self.assertIn(required, deployment)
        self.assertNotIn("kind: Service", deployment)
        self.assertNotIn("kind: Route", deployment)

    def test_helper_packages_applies_and_validates_all_three_canonical_manifests(self):
        # Given: Deployment, Service, and Route are separate mandatory release inputs.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the helper packages, renders, and deploys the release topology.

        # Then: every manifest has an independent checksum, server dry-run, apply, and
        # rendered/live fail-closed topology verification.
        for required in (
            "DEPLOYMENT_MANIFEST_SHA256",
            "SERVICE_MANIFEST_SHA256",
            "ROUTE_MANIFEST_SHA256",
            "MANIFESTS_DIR",
            '"${RAW_ROOT}/hybrid-bbqc/openshift/${manifest}"',
            'oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$FORWARD_SERVICE_FILE"',
            'oc -n "$PROJECT" replace --save-config=false -f "$FORWARD_SERVICE_FILE"',
            "validate_manifest_topology",
            "validate_manifest_topology rendered-pre-rollout",
            "validate_oauth2_proxy_topology post-rollout",
            "unexpected canonical manifest kinds",
            "additional Service selects live web pod",
            "additional Route targets a Service selecting live pod",
        ):
            self.assertIn(required, script)

    def test_helper_refetches_and_validates_exact_oauth_topology_before_and_after_rollout(self):
        # Given: cluster objects can drift between preflight and the new Pod becoming ready.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the rollout gate is assembled.

        # Then: it re-fetches Deployment, Service collection, and Route topology at both
        # points and rejects backend Service exposure or proxy contract drift.
        self.assertGreaterEqual(script.count("validate_oauth2_proxy_topology"), 3)
        for required in (
            "topology-${phase}-services.json",
            "get services -o json",
            "additional Service selects live web pod",
            "additional Route targets a Service selecting live pod",
            "exact oauth2-proxy args mismatch",
            "oauth2-proxy image is not digest pinned",
            "web loopback topology mismatch",
            "route host topology mismatch",
        ):
            self.assertIn(required, script)

    def test_helper_compares_the_full_api_evidence_map_to_locally_validated_publication(self):
        # Given: the immutable publication and the API evidence response are separate
        # sources that must agree exactly.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: post-rollout review API verification runs.

        # Then: all 36 acquisition keys, five-field identities, and normalized
        # content-addressed URIs are compared to the locally validated publication.
        for required in (
            "API evidence keyset mismatch",
            "API evidence identity/URI mismatch",
            "expected_evidence",
            "set(evidence) != set(expected_evidence)",
            "len(expected_evidence) != 36",
            "PurePosixPath",
        ):
            self.assertIn(required, script)

    def test_helper_probes_exact_schema_and_rejects_attached_object_drift(self):
        # Given: the ETROC schema is additive but must remain exact and non-bypassable.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the post-rollout database gate runs.

        # Then: it independently checks SQL, columns, index details, foreign-key actions,
        # triggers, and rejects any additional ETROC-owned database object.
        for required in (
            "POST_ROLLOUT_ETROC_SCHEMA PASS",
            "PRAGMA table_info(etroc_review_events)",
            "PRAGMA index_list(etroc_review_events)",
            "PRAGMA index_info",
            "PRAGMA foreign_key_list(etroc_review_events)",
            "arbitrary ETROC attached object",
            "etroc_reviews.validate_schema(db)",
            "etroc_review_unapproved_attachment",
        ):
            self.assertIn(required, script)

    def test_helper_proves_spoofed_and_conflicting_identity_headers_cannot_append(self):
        # Given: only oauth2-proxy may establish the trusted identity header.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the external identity boundary is verified.

        # Then: spoofing sends the configured allowlisted identity header, proves it
        # cannot manufacture append capability, and requires an authenticated
        # conflicting-header/session-derived identity probe when available.
        for required in (
            "X-Forwarded-Email: ${ETROC_REVIEWER_TEST_USER}",
            "SPOOF_APPEND_STATUS",
            "external trusted-header spoof manufactured append capability",
            "AUTHENTICATED_CONFLICTING_IDENTITY_GATE PASS",
            "authenticated conflicting-header proof unavailable",
            "--cookie",
        ):
            self.assertIn(required, script)

    def test_helper_preserves_etroc_events_and_identity_chain_across_release_boundaries(self):
        # Given: ETROC reviews and Hybrid comments are durable user data.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: backup, rollout, and rollback coordinates are captured.

        # Then: event count plus the complete ETROC identity chain are compared at every
        # boundary without weakening the existing Hybrid comment preservation gate.
        for required in (
            "ETROC_EVENT_SNAPSHOT_BEFORE",
            "ETROC_EVENT_SNAPSHOT_BACKUP",
            "ETROC_EVENT_SNAPSHOT_POST_ROLLOUT",
            "ETROC_EVENT_SNAPSHOT_ROLLBACK",
            "ETROC event identity chain changed",
            "BEFORE_COMMENTS",
        ):
            self.assertIn(required, script)

    def test_forward_render_uses_pinned_baseline_and_rejects_live_spec_drift(self):
        # Given: the captured Deployment is only an identity/operational-metadata
        # witness, while the separately verified baseline owns the release spec.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the forward Deployment renderer is assembled.

        # Then: it reads the pinned deployment manifest independently, rejects a
        # captured spec mismatch, and only retains the explicitly justified live
        # metadata needed for a resourceVersion-aware replacement.
        forward = script[script.index("render_forward_object() {") : script.index("render_captured_rollback_object() {")]
        for required in (
            "BASELINE_OBJECT_FILE",
            "identity differs from pinned baseline",
            "spec differs from pinned baseline",
            "'resourceVersion': resource_version, 'labels': copy.deepcopy(baseline_metadata.get('labels', {}))",
            "desired={'apiVersion': baseline['apiVersion'], 'kind': kind",
            "'spec': baseline_spec",
        ):
            self.assertIn(required, forward)
        self.assertIn("BASELINE_DEPLOYMENT_FILE", script)
        self.assertNotIn("'spec': source['spec']", forward)

    def test_forward_renderer_preserves_only_baseline_approved_annotations(self):
        # Given: a captured object has exactly the pinned annotations plus generated noise.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os, sys", script.index("render_forward_object() {"))
        renderer = script[start : script.index("\nPY\n", start)]
        baseline_annotations = {"haproxy.router.openshift.io/ip_whitelist": "10.0.0.0/8"}
        with tempfile.TemporaryDirectory() as directory:
            baseline = {
                "apiVersion": "route.openshift.io/v1", "kind": "Route",
                "metadata": {"name": "etl-hybrid-bbqc", "labels": {"app": "etl-hybrid-bbqc"}, "annotations": baseline_annotations},
                "spec": {"host": "etl-hybrid-bbqc.app.cern.ch"},
            }
            captured = {
                **baseline,
                "metadata": {**baseline["metadata"], "namespace": "etroc-solder-inspection", "uid": "route-uid", "resourceVersion": "9", "annotations": {**baseline_annotations, "kubectl.kubernetes.io/last-applied-configuration": "generated"}},
            }
            baseline_file, captured_file = Path(directory) / "baseline.json", Path(directory) / "captured.json"
            baseline_file.write_text(json.dumps(baseline), encoding="utf-8")
            captured_file.write_text(json.dumps(captured), encoding="utf-8")
            environment = os.environ | {
                "RELEASE_KIND": "Route", "BASELINE_OBJECT_FILE": str(baseline_file), "CAPTURED_OBJECT_FILE": str(captured_file),
                "NEW_WEB_IMAGE": "unused", "OLD_WEB_IMAGE": "unused", "OLD_PROXY_IMAGE": "unused", "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context", "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch",
            }
            result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        annotations = json.loads(result.stdout)["metadata"]["annotations"]
        self.assertEqual(annotations["haproxy.router.openshift.io/ip_whitelist"], "10.0.0.0/8")
        self.assertNotIn("kubectl.kubernetes.io/last-applied-configuration", annotations)

    def test_forward_renderer_rejects_annotation_drift_except_known_generated_values(self):
        # Given: generated annotations are tolerated but policy and unknown annotations are not.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os, sys", script.index("render_forward_object() {"))
        renderer = script[start : script.index("\nPY\n", start)]
        cases = (
            ("deployment generated", "Deployment", {"kubectl.kubernetes.io/last-applied-configuration": "generated", "deployment.kubernetes.io/revision": "7"}, 0),
            ("route whitelist value", "Route", {"haproxy.router.openshift.io/ip_whitelist": "192.168.0.0/16"}, 1),
            ("unknown", "Service", {"unreviewed.example/policy": "enabled"}, 1),
        )
        for name, kind, extra_annotations, expected_failure in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                spec = {"selector": {"app": "etl-hybrid-bbqc"}} if kind == "Service" else {"template": {"spec": {"containers": [{"name": "web", "image": "old-web"}, {"name": "oauth2-proxy", "image": "old-proxy"}]}}} if kind == "Deployment" else {"host": "etl-hybrid-bbqc.app.cern.ch"}
                baseline = {"apiVersion": "v1", "kind": kind, "metadata": {"name": "etl-hybrid-bbqc", "labels": {"app": "etl-hybrid-bbqc"}, "annotations": {"reviewed.example/policy": "pinned"}}, "spec": spec}
                captured = {**baseline, "metadata": {**baseline["metadata"], "namespace": "etroc-solder-inspection", "uid": "stable-uid", "resourceVersion": "9", "annotations": {**baseline["metadata"]["annotations"], **extra_annotations}}}
                baseline_file, captured_file = Path(directory) / "baseline.json", Path(directory) / "captured.json"
                baseline_file.write_text(json.dumps(baseline), encoding="utf-8")
                captured_file.write_text(json.dumps(captured), encoding="utf-8")
                environment = os.environ | {"RELEASE_KIND": kind, "BASELINE_OBJECT_FILE": str(baseline_file), "CAPTURED_OBJECT_FILE": str(captured_file), "NEW_WEB_IMAGE": "new-web", "OLD_WEB_IMAGE": "old-web", "OLD_PROXY_IMAGE": "old-proxy", "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context", "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch"}
                result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
                self.assertEqual(result.returncode != 0, bool(expected_failure), result.stderr)
                if expected_failure:
                    self.assertIn("annotations differ from pinned baseline", result.stderr)

    def test_candidate_probe_cleanup_is_uid_guarded_and_owned_before_possible_failures(self):
        # Given: candidate creation succeeded and later wait, copy, or startup can fail.
        script = SCRIPT.read_text(encoding="utf-8")
        candidate_start = script.index('oc -n "$PROJECT" run "$CANDIDATE_PROBE_POD"')
        ownership = script.index("CANDIDATE_PROBE_POD_OWNED=1", candidate_start)
        for later in ('oc -n "$PROJECT" wait', 'oc -n "$PROJECT" cp', 'oc -n "$PROJECT" exec "$CANDIDATE_PROBE_POD" -- sh -c'):
            self.assertLess(ownership, script.index(later, candidate_start))
        cleanup_start = script.index("cleanup_candidate_probe_pod() {")
        cleanup = script[cleanup_start : script.index("\n}\n", cleanup_start) + 3]

        # When: cleanup sees the original UID twice, then sees a recreated UID.
        harness = f'''set -Eeuo pipefail
{cleanup}
PROJECT=project
WORK_DIR="$(mktemp -d)"
CANDIDATE_PROBE_POD=probe
CANDIDATE_PROBE_POD_UID=original
CANDIDATE_PROBE_POD_OWNED=1
mock_uid=original
deletes=0
oc() {{
  if [[ "$*" == *get* ]]; then printf '%s' "$mock_uid"; return 0; fi
  if [[ "$*" == *delete* ]]; then deletes=$((deletes + 1)); return 0; fi
  return 1
}}
cleanup_candidate_probe_pod
cleanup_candidate_probe_pod
CANDIDATE_PROBE_POD_OWNED=1
mock_uid=recreated
if ! cleanup_candidate_probe_pod; then :; fi
printf 'deletes=%s owned=%s\\n' "$deletes" "$CANDIDATE_PROBE_POD_OWNED"
'''
        result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True)

        # Then: only the original object is deleted; retry is idempotent and recreation is refused.
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deletes=1 owned=1", result.stdout)
        self.assertIn("UID changed; refusing deletion", result.stderr)

    def test_rollback_scope_captures_and_restores_service_and_route_fail_closed(self):
        # Given: Service and Route are mutated by the forward release.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: release evidence and rollback are assembled.

        # Then: each object has a captured/forward file plus UID, resourceVersion,
        # checksum, server dry-run, ownership check, exact topology verification, and
        # generated-field-safe restore rendering.
        for kind in ("SERVICE", "ROUTE"):
            for suffix in ("CAPTURED", "FORWARD", "OLD"):
                self.assertIn(f"{suffix}_{kind}_FILE", script)
                self.assertIn(f"{suffix}_{kind}_SHA256", script)
            self.assertIn(f"{kind}_UID", script)
            self.assertIn(f"{kind}_RESOURCE_VERSION", script)
        rollback = script[script.index("prepare_rollback_object() {") : script.index("attempt_rollback() {")]
        for required in (
            "rollback current {kind} is foreign/concurrent drift; refusing rollback overwrite",
            "rollback target UID changed",
            "replace --save-config=false --dry-run=server -f \"$service_rendered\"",
            "replace --save-config=false --dry-run=server -f \"$route_rendered\"",
            "validate_manifest_topology rollback",
            "validate_oauth2_proxy_topology rollback \"$OLD_PROXY_IMAGE\"",
        ):
            self.assertIn(required, rollback)

    def test_rollback_after_authorized_append_accepts_post_append_event_snapshot(self):
        # Given: an authorized append has irreversibly extended the audit chain.
        script = SCRIPT.read_text(encoding="utf-8")
        before = '{"present":true,"count":1,"identity_chain":[[1,"old"]]}'
        after_append = '{"present":true,"count":2,"identity_chain":[[1,"old"],[2,"append"]]}'
        start = script.index("assert_etroc_snapshot() {")
        end = script.index("\n}\n", start) + 3
        assertion = script[start:end]

        # When: rollback sees the legitimate append-only state after a simulated later
        # failure.
        accepted = subprocess.run(
            ["bash", "-c", f"{assertion}\nassert_etroc_snapshot {shlex.quote(after_append)} {shlex.quote(after_append)}"],
            check=False, capture_output=True, text=True,
        )
        rejected = subprocess.run(
            ["bash", "-c", f"{assertion}\nassert_etroc_snapshot {shlex.quote(before)} {shlex.quote(after_append)}"],
            check=False, capture_output=True, text=True,
        )

        # Then: rollback uses the post-append expectation, never the stale pre-append
        # snapshot, and the capture occurs immediately after append/audit verification.
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("ETROC_EVENT_SNAPSHOT_EXPECTED_ROLLBACK", script)
        post = script.index('REVIEW_CREATED_STATUS="$(curl')
        committed = script.index("FORWARD_RELEASE_COMMITTED before irreversible ETROC review verification")
        ownership_released = script.index("ROLLOUT_MUTATED=0", committed)
        self.assertLess(committed, ownership_released)
        self.assertLess(ownership_released, post)
        append = script.index("ETROC_REVIEW_PROXY_FLOW PASS")
        capture = script.index("ETROC_EVENT_SNAPSHOT_EXPECTED_ROLLBACK=", append)
        self.assertLess(append, capture)
        rollback = script[script.index("rollback_deployment() {") : script.index("attempt_rollback() {")]
        self.assertIn('assert_etroc_snapshot "$ETROC_EVENT_SNAPSHOT_EXPECTED_ROLLBACK"', rollback)

    def test_helper_requires_operator_review_inputs_before_rollout(self):
        # Given: a deployment gate must never choose a scientific disposition itself.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the operator has not supplied the exact review target and decision.

        # Then: all three required values are validated before any production Deployment
        # replacement, with no fallback acquisition, state, or note baked into the helper.
        validation = script[script.index("validate_operator_review_inputs() {"):script.index("bootstrap_sso_plugin() {")]
        mutation = script.index('ROLLOUT_MUTATED=1')
        invocation = script.index("validate_operator_review_inputs", script.index("ETROC_REVIEWER_ALLOWLIST PASS"))
        self.assertLess(invocation, mutation)
        for required in (
            "ETROC_REVIEW_ACQUISITION_ID",
            "ETROC_REVIEW_STATE",
            "ETROC_REVIEW_NOTE",
            "operator review acquisition ID is required",
            "operator review state is invalid",
            "operator review note is required",
            "operator review note is invalid",
            "operator review acquisition is not canonical candidate publication evidence",
            "ETROC_OI_2608:",
            "reviewed_no_optical_concern",
            "reviewed_concern_observed",
            "follow_up_required",
        ):
            self.assertIn(required, validation)
        self.assertNotIn("ETROC_REVIEW_ACQUISITION_ID='", validation)
        self.assertNotIn("ETROC_REVIEW_STATE='", validation)
        self.assertNotIn("ETROC_REVIEW_NOTE='", validation)

    def test_operator_review_input_validation_is_deterministic(self):
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("validate_operator_review_inputs() {")
        end = script.index("\n}\n", start) + 3
        validator = script[start:end]

        def run_case(**values):
            environment = os.environ.copy()
            environment.update(values)
            return subprocess.run(
                ["bash", "-c", f"set -Eeuo pipefail\n{validator}\nvalidate_operator_review_inputs"],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

        missing = run_case()
        malformed = run_case(
            ETROC_REVIEW_ACQUISITION_ID="not-a-canonical-id",
            ETROC_REVIEW_STATE="reviewed_concern_observed",
            ETROC_REVIEW_NOTE="operator note",
        )
        invalid_state = run_case(
            ETROC_REVIEW_ACQUISITION_ID="ETROC_OI_2608:W02G4-44:base",
            ETROC_REVIEW_STATE="unsafe_disposition",
            ETROC_REVIEW_NOTE="operator note",
        )
        valid = run_case(
            ETROC_REVIEW_ACQUISITION_ID="ETROC_OI_2608:W02G4-44:base",
            ETROC_REVIEW_STATE="reviewed_concern_observed",
            ETROC_REVIEW_NOTE="operator note",
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("operator review acquisition ID is required", missing.stderr)
        self.assertNotEqual(malformed.returncode, 0)
        self.assertIn("operator review acquisition ID is invalid", malformed.stderr)
        self.assertNotEqual(invalid_state.returncode, 0)
        self.assertIn("operator review state is invalid", invalid_state.stderr)
        self.assertEqual(valid.returncode, 0, valid.stderr)

    def test_helper_exercises_authenticated_proxy_review_append_contract(self):
        # Given: an operator-provided canonical review must be verified through the
        # SSO-protected proxy after the new release is live.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("ETROC_REVIEW_PROXY_FLOW PASS") - 12000
        flow = script[start:script.index("ETROC_PROXY_IDENTITY_GATE PASS", start)]

        # Then: the flow derives the entire canonical key from the authenticated summary,
        # sends identity/content/origin-safe requests, and proves one write, exact
        # readback, lost-response replay, stale conflict, history, and audit without
        # restoring or deleting any database data.
        for required in (
            "ETROC_REVIEW_ACQUISITION_ID",
            "ETROC_REVIEW_STATE",
            "ETROC_REVIEW_NOTE",
            "can_append_review",
            "Content-Type: application/json",
            "Origin: https://etl-hybrid-bbqc.app.cern.ch",
            "cache-control",
            "idempotent_replay",
            "stale_current",
            "/api/etroc-reviews/audit?acquisition_id=",
            "history count changed after idempotent replay",
            "history count changed after stale conflict",
            "ETROC_REVIEW_PROXY_FLOW PASS",
        ):
            self.assertIn(required, flow)
        self.assertNotIn("DELETE FROM etroc_review_events", flow)
        self.assertNotIn("restore", flow.lower())

    def test_topology_inventory_covers_every_service_and_route_selecting_live_pods(self):
        # Given: an additional Service can select the live template with labels other
        # than the historical app label, and a second Route can expose that Service.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the preflight topology inventory is run.

        # Then: it derives the live template labels, inventories all Routes, and rejects
        # both the direct web Service and any additional Route to a selected Service.
        topology = script[
            script.index("validate_oauth2_proxy_topology() {") : script.index(
                "snapshot_etroc_review_events() {"
            )
        ]
        for required in (
            "get routes -o json",
            "template_labels",
            "all(template_labels.get(key) == value",
            "additional Service selects live web pod",
            "additional Route targets a Service selecting live pod",
        ):
            self.assertIn(required, topology)

    def test_topology_pins_oauth_proxy_to_captured_digest_not_merely_a_digest(self):
        # Given: the proxy sidecar is deliberately preserved from the reviewed rollout.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: preflight and post-rollout topology checks are assembled.

        # Then: the image must equal the captured immutable digest at both boundaries.
        topology = script[
            script.index("validate_oauth2_proxy_topology() {") : script.index(
                "snapshot_etroc_review_events() {"
            )
        ]
        self.assertIn("EXPECTED_PROXY_IMAGE", topology)
        self.assertIn("oauth2-proxy image differs from captured reviewed digest", topology)
        self.assertIn('validate_oauth2_proxy_topology captured-pre-rollout "$OLD_PROXY_IMAGE"', script)
        self.assertIn('validate_oauth2_proxy_topology post-rollout "$OLD_PROXY_IMAGE"', script)

    def test_event_snapshot_is_ordered_and_captures_mutable_review_fields(self):
        # Given: an event's state, note, and timestamp are all audit data.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: every release-boundary snapshot is collected.

        # Then: the exact table-column order includes the mutable review fields, so a
        # change in any of them causes the preservation comparison to fail.
        expected = (
            "id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,"
            "state,note,author,author_display,created_at,mutation_id,supersedes_event_id"
        )
        self.assertGreaterEqual(script.count(expected), 4)

    def test_post_migration_compares_the_complete_existing_hybrid_schema(self):
        # Given: ETROC migration is additive and must not alter any existing Hybrid DDL.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the candidate and post-rollout schema gates run.

        # Then: they calculate and compare a non-ETROC sqlite_master digest without an
        # unreachable conditional that skips the comparison after ETROC objects exist.
        for required in (
            "BACKUP_HYBRID_SCHEMA_SHA256",
            "runtime_hybrid_schema_sha256",
            "candidate_hybrid_schema_sha256",
            "existing Hybrid schema changed during ETROC migration",
            "existing Hybrid schema changed after rollout",
        ):
            self.assertIn(required, script)
        self.assertNotIn(
            "if runtime_schema_sha256 != os.environ['BACKUP_SCHEMA_SHA256'] and not review_objects:",
            script,
        )

    def test_candidate_image_entrypoint_and_evidence_loader_run_before_deployment_mutation(self):
        # Given: a local source import cannot prove that the built candidate image starts.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the immutable candidate image is available.

        # Then: a disposable copied legacy DB is installed before the actual entrypoint
        # is started, and its evidence loader plus montage bytes are probed before the
        # production Deployment replacement.
        candidate = script[script.index("CANDIDATE_IMAGE_STARTUP PASS") - 7000 : script.index("CANDIDATE_IMAGE_STARTUP PASS")]
        mutation = script.index('ROLLOUT_MUTATED=1')
        self.assertLess(script.index("CANDIDATE_IMAGE_STARTUP PASS"), mutation)
        for required in (
            "candidate-startup-probe",
            'oc -n "$PROJECT" cp "$LOCAL_BACKUP"',
            "python /app/static/server.py",
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608",
            "candidate evidence loader did not return exact cohort",
            "candidate served montage bytes mismatch",
            "CANDIDATE_LEGACY_COMMENTS_COMPAT PASS",
        ):
            self.assertIn(required, candidate if required != "CANDIDATE_LEGACY_COMMENTS_COMPAT PASS" else script)

    def test_authenticated_spoof_proofs_use_both_real_session_roles(self):
        # Given: proxy header stripping must hold for both reviewer and non-reviewer
        # sessions, not only for an unauthenticated request.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: external spoof resistance is verified.

        # Then: a non-allowlisted real session injects an allowlisted header and an
        # allowlisted real session injects an attacker header.
        for required in (
            "ETROC_NON_ALLOWLISTED_SESSION_COOKIE_JAR",
            "non-allowlisted session spoof manufactured append capability",
            "non-allowlisted session identity was not preserved",
            "allowlisted session identity was not preserved against attacker header",
            "X-Forwarded-Email: ${ETROC_REVIEWER_TEST_USER}",
            "X-Forwarded-Email: attacker@cern.ch",
        ):
            self.assertIn(required, script)

    def test_runtime_http_montage_bytes_equal_the_published_digest(self):
        # Given: JPEG magic bytes do not establish immutable evidence identity.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the served content-addressed montage is fetched through the app.

        # Then: its entire HTTP response byte stream is hashed against montage_sha256.
        probe = script[script.index("RUNTIME_HTTP_ASSETS PASS") - 3500 : script.index("RUNTIME_HTTP_ASSETS PASS")]
        self.assertIn("hashlib.sha256(montage).hexdigest() != record['montage_sha256']", probe)
        self.assertIn("runtime HTTP montage bytes mismatch", probe)

    def test_candidate_creation_captures_uid_from_create_response_and_uses_uid_precondition(self):
        # Given: a same-name pod could be created or recreated between API calls.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the candidate ownership and cleanup paths are assembled.
        candidate = script[script.index('CANDIDATE_PROBE_POD="${DEPLOYMENT}') : script.index("CANDIDATE_IMAGE_STARTUP PASS")]
        cleanup = script[script.index("cleanup_candidate_probe_pod() {") : script.index("\n}\n", script.index("cleanup_candidate_probe_pod() {")) + 3]

        # Then: ownership comes from the create response and delete is UID-preconditioned.
        self.assertIn("--output=json", candidate)
        self.assertIn("CANDIDATE_PROBE_CREATE_RESPONSE", candidate)
        self.assertIn("candidate probe create response", candidate)
        self.assertIn('--raw="/api/v1/namespaces/', cleanup)
        self.assertIn("preconditions", cleanup)
        self.assertIn("uid", cleanup)
        self.assertNotIn('delete pod/"$CANDIDATE_PROBE_POD"', cleanup)

    def test_old_runtime_server_extraction_is_digest_pinned_and_rejects_bad_output(self):
        # Given: a fake `oc image extract` has controlled success and malformed outputs.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("extract_previous_runtime_server() {")
        extraction = script[start : script.index("\n}\n", start) + 3]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_oc = fake_bin / "oc"
            fake_oc.write_text(
                """#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\\n' \"$@\" > \"$FAKE_OC_ARGS\"
test \"$1\" = image
test \"$2\" = extract
test \"$4\" = --path
case \"$FAKE_OC_MODE\" in
  success) cp \"$FAKE_SERVER\" \"${5#*:}/server.py\" ;;
  symlink) ln -s \"$FAKE_SERVER\" \"${5#*:}/server.py\" ;;
  extra) cp \"$FAKE_SERVER\" \"${5#*:}/server.py\"; : > \"${5#*:}/unexpected.py\" ;;
  empty) : > \"${5#*:}/server.py\" ;;
  malformed) printf 'not valid python =\\n' > \"${5#*:}/server.py\" ;;
  failure) exit 42 ;;
esac
""",
                encoding="utf-8",
            )
            fake_oc.chmod(0o755)
            source = root / "server.py"
            source.write_text(
                """import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler

APP_ORIGIN = 'http://127.0.0.1:8080'
IDENTITY_HEADER = 'X-Forwarded-Email'

def init_db():
    with sqlite3.connect(os.environ['COMMENTS_DB']) as db:
        db.execute('CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, target TEXT, body TEXT, status TEXT)')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with sqlite3.connect(os.environ['COMMENTS_DB']) as db:
            cursor = db.execute('INSERT INTO comments(target, body, status) VALUES (?, ?, ?)', (payload['target'], payload['body'], payload['status']))
        response = json.dumps({'id': cursor.lastrowid, 'target': payload['target']}).encode()
        self.send_response(201)
        self.end_headers()
        self.wfile.write(response)
    def do_GET(self):
        target = self.path.split('target=', 1)[1]
        with sqlite3.connect(os.environ['COMMENTS_DB']) as db:
            rows = db.execute('SELECT id, target FROM comments WHERE target = ?', (target,)).fetchall()
        response = json.dumps([{'id': row[0], 'target': row[1]} for row in rows]).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(response)
""",
                encoding="utf-8",
            )
            source.chmod(0o600)
            candidate_db = root / "candidate.sqlite3"
            environment = os.environ | {
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "FAKE_OC_ARGS": str(root / "oc-args"),
                "FAKE_SERVER": str(source),
                "CANDIDATE_DB": str(candidate_db),
            }
            harness = f'''set -Eeuo pipefail
{extraction}
WORK_DIR={shlex.quote(str(root / "work"))}
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
OLD_RUNTIME_DIR="$WORK_DIR/previous-runtime"
OLD_RUNTIME_SERVER="$OLD_RUNTIME_DIR/server.py"
OLD_WEB_IMAGE='registry.example/etroc@sha256:{'a' * 64}'
extract_previous_runtime_server
COMMENTS_DB="$CANDIDATE_DB" OLD_RUNTIME_SERVER="$OLD_RUNTIME_SERVER" python3 -I - <<'PY'
import importlib.util, os
from pathlib import Path
source = Path(os.environ['OLD_RUNTIME_SERVER'])
spec = importlib.util.spec_from_file_location('old_runtime', source)
if spec is None or spec.loader is None:
    raise SystemExit('old runtime is unavailable')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.init_db()
print('LOCAL_OLD_RUNTIME_EXECUTION PASS')
PY
printf 'sha=%s\\n' "$OLD_RUNTIME_SERVER_SHA256"
'''

            # When: a valid old image extraction succeeds.
            environment["FAKE_OC_MODE"] = "success"
            result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True, env=environment)

            # Then: the precise immutable image and path are extracted and evidence is hashed.
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("LOCAL_OLD_RUNTIME_EXECUTION PASS", result.stdout)
            self.assertRegex(result.stdout, r"sha=[0-9a-f]{64}")
            self.assertEqual(
                (root / "oc-args").read_text(encoding="utf-8").splitlines(),
                ["image", "extract", f"registry.example/etroc@sha256:{'a' * 64}", "--path", f"/app/static/server.py:{root / 'work' / 'previous-runtime'}"],
            )

            # Then: image extraction failures and unsafe archive output fail closed.
            for mode in ("failure", "symlink", "extra", "empty", "malformed"):
                environment["FAKE_OC_MODE"] = mode
                failed = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True, env=environment)
                self.assertNotEqual(failed.returncode, 0, mode)

    def test_legacy_compatibility_is_local_and_never_copies_a_candidate_db_to_production(self):
        # Given: the candidate DB has been migrated locally from the copied backup.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the old runtime compatibility gate is assembled.

        # Then: it uses only the extracted absolute source and no production candidate DB path.
        self.assertIn('COMMENTS_DB="$CANDIDATE_DB" OLD_RUNTIME_SERVER="$OLD_RUNTIME_SERVER" python3 -I', script)
        self.assertIn("source = Path(os.environ['OLD_RUNTIME_SERVER'])", script)
        self.assertNotIn("source = Path('/app/static/server.py')", script)
        self.assertNotIn("CANDIDATE_REMOTE_DB", script)
        self.assertNotIn("cleanup_production_candidate_db", script)
        self.assertNotRegex(script, re.compile(r'oc -n "\$PROJECT" cp "\$CANDIDATE_DB" "\$POD:'))
        self.assertNotRegex(script, re.compile(r'oc -n "\$PROJECT" exec(?: -i)? "\$POD" -c web -- env COMMENTS_DB='))

    def test_cookie_jars_are_validated_read_only_inputs(self):
        # Given: authenticated proof jars may contain bearer-equivalent cookies.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the proof requests are constructed.
        cookies = script[script.index("validate_cookie_jar_inputs() {") : script.index("REVIEW_SUMMARY_HEADERS=")]

        # Then: both jars are ownership/mode checked, distinct, and never rewritten.
        for required in ("-f", "-L", "-O", "400", "600", "-ef"):
            self.assertIn(required, cookies)
        self.assertNotIn("--cookie-jar", cookies)

    def test_headroom_counts_wal_and_shm_and_retention_rejects_unknown_artifacts(self):
        # Given: SQLite WAL state and interrupted evidence sets consume real capacity.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: headroom and retention are measured.
        measurement = script[script.index("measure_dashboard_headroom() {") : script.index("verify_context() {")]

        # Then: all SQLite live files and every known artifact set are counted fail-closed.
        self.assertIn("database + '-wal'", measurement)
        self.assertIn("database + '-shm'", measurement)
        self.assertIn("retained_artifact_sets", measurement)
        self.assertIn("unknown dashboard release artifact", measurement)

    def test_rollback_attempts_remaining_objects_after_restore_failure(self):
        # Given: one owned restore can fail after all three objects are classified.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: rollback applies marked objects.
        rollback = script[script.index("rollback_deployment() {") : script.index("attempt_rollback() {")]

        # Then: failures accumulate while later Service and Route replacements still execute.
        self.assertIn("rollback_failures", rollback)
        self.assertIn("rollback restore failures", rollback)
        self.assertLess(rollback.index('replace --save-config=false -f "$deployment_rendered"'), rollback.index('replace --save-config=false -f "$service_rendered"'))
        self.assertLess(rollback.index('replace --save-config=false -f "$service_rendered"'), rollback.index('replace --save-config=false -f "$route_rendered"'))

    def test_rollback_fixture_attempts_later_restores_after_first_or_second_failure(self):
        # Given: all three objects are safely classified as forward-owned before a restore fails.
        script = SCRIPT.read_text(encoding="utf-8")
        helpers = script[script.index("prepare_rollback_object() {") : script.index("rollback_deployment() {")]
        rollback = script[script.index("rollback_deployment() {") : script.index("attempt_rollback() {")]

        # When: either the Deployment or Service replacement fails in an executable oc fixture.
        for failure in ("deployment-rollback.json", "service-rollback.json"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for kind, uid in (("Deployment", "deployment-uid"), ("Service", "service-uid"), ("Route", "route-uid")):
                    metadata = {"name": "etl-hybrid-bbqc", "namespace": "project", "uid": uid, "resourceVersion": "1", "labels": {}, "annotations": {}}
                    old = {"apiVersion": "v1", "kind": kind, "metadata": metadata, "spec": {"release": "old"}}
                    forward = {**old, "metadata": {**metadata, "resourceVersion": "2"}, "spec": {"release": "forward"}}
                    (root / f"old-{kind}.json").write_text(json.dumps(old), encoding="utf-8")
                    (root / f"forward-{kind}.json").write_text(json.dumps(forward), encoding="utf-8")
                harness = f'''set -Eeuo pipefail
{helpers}
{rollback}
WORK_DIR={shlex.quote(str(root))}
PROJECT=project
DEPLOYMENT=etl-hybrid-bbqc
DEPLOYMENT_UID=deployment-uid
SERVICE_UID=service-uid
ROUTE_UID=route-uid
OLD_DEPLOYMENT_FILE="$WORK_DIR/old-Deployment.json"
OLD_SERVICE_FILE="$WORK_DIR/old-Service.json"
OLD_ROUTE_FILE="$WORK_DIR/old-Route.json"
FORWARD_DEPLOYMENT_FILE="$WORK_DIR/forward-Deployment.json"
FORWARD_SERVICE_FILE="$WORK_DIR/forward-Service.json"
FORWARD_ROUTE_FILE="$WORK_DIR/forward-Route.json"
OLD_DEPLOYMENT_SHA256=$(sha256sum "$OLD_DEPLOYMENT_FILE" | cut -d' ' -f1)
OLD_SERVICE_SHA256=$(sha256sum "$OLD_SERVICE_FILE" | cut -d' ' -f1)
OLD_ROUTE_SHA256=$(sha256sum "$OLD_ROUTE_FILE" | cut -d' ' -f1)
FORWARD_DEPLOYMENT_SHA256=$(sha256sum "$FORWARD_DEPLOYMENT_FILE" | cut -d' ' -f1)
FORWARD_SERVICE_SHA256=$(sha256sum "$FORWARD_SERVICE_FILE" | cut -d' ' -f1)
FORWARD_ROUTE_SHA256=$(sha256sum "$FORWARD_ROUTE_FILE" | cut -d' ' -f1)
OLD_PROXY_IMAGE=proxy
verify_context() {{ :; }}
validate_manifest_topology() {{ :; }}
validate_oauth2_proxy_topology() {{ :; }}
oc() {{
  if [[ "$*" == *" get deployment/"* ]]; then cat "$FORWARD_DEPLOYMENT_FILE"; return; fi
  if [[ "$*" == *" get service/"* ]]; then cat "$FORWARD_SERVICE_FILE"; return; fi
  if [[ "$*" == *" get route/"* ]]; then cat "$FORWARD_ROUTE_FILE"; return; fi
  if [[ "$*" == *" replace "* ]]; then
    last="${{@: -1}}"; printf '%s\n' "$(basename "$last")" >> "$WORK_DIR/attempts"
    [[ "$*" == *--dry-run=server* ]] || [[ "$(basename "$last")" != {shlex.quote(failure)} ]]
    return
  fi
  return 1
}}
if rollback_deployment; then exit 91; fi
grep -qx deployment-rollback.json "$WORK_DIR/attempts"
grep -qx service-rollback.json "$WORK_DIR/attempts"
grep -qx route-rollback.json "$WORK_DIR/attempts"
'''
                result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True)

                # Then: each planned replacement ran despite the earlier failure, and rollback failed closed.
                self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == "__main__":
    unittest.main()
