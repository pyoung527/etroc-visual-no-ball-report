from __future__ import annotations

import json
import os
import re
import shlex
import shutil
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
    def test_backup_dir_override_defaults_exactly_and_rejects_unsafe_paths(self):
        # Given: production may select a private durable directory, never a traversal or symlink.
        script = SCRIPT.read_text(encoding="utf-8")
        helpers = script[
            script.index("validate_backup_directory() {") : script.index(
                "validate_dashboard_headroom() {"
            )
        ]

        # When: an override and unsafe values are supplied to the boundary parser.
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            override = parent / "eos-backups"
            symlink = parent / "symlink"
            symlink.symlink_to(override)
            unsafe_parent = parent / "unsafe"
            unsafe_parent.mkdir(mode=0o700)
            unsafe_parent.chmod(0o777)
            temporary_root = subprocess.run(
                ["bash", "-c", f"{helpers}\nvalidate_backup_directory {shlex.quote(str(override))}"],
                check=False, capture_output=True, text=True,
            )
            traversal = subprocess.run(
                ["bash", "-c", f"{helpers}\nvalidate_backup_directory {shlex.quote(str(parent / '..' / 'escape'))}"],
                check=False, capture_output=True, text=True,
            )
            symlinked = subprocess.run(
                ["bash", "-c", f"{helpers}\nvalidate_backup_directory {shlex.quote(str(symlink))}"],
                check=False, capture_output=True, text=True,
            )
            unsafe = subprocess.run(
                ["bash", "-c", f"{helpers}\nvalidate_backup_directory {shlex.quote(str(unsafe_parent / 'backups'))}"],
                check=False, capture_output=True, text=True,
            )

            # Then: temporary, traversal, symlink, and writable-parent paths are refused.
            self.assertNotEqual(temporary_root.returncode, 0)
            self.assertNotEqual(traversal.returncode, 0)
            self.assertNotEqual(symlinked.returncode, 0)
            self.assertNotEqual(unsafe.returncode, 0)
        self.assertIn('BACKUP_DIR="${BBQC_BACKUP_DIR:-${HOME}/bbqc-backups}"', script)
        assignment = next(line for line in script.splitlines() if line.startswith("BACKUP_DIR="))
        selected = subprocess.run(
            ["bash", "-c", f"{assignment}; printf '%s' \"$BACKUP_DIR\""],
            check=False, capture_output=True, text=True,
            env={"HOME": "/home/default", "BBQC_BACKUP_DIR": "/eos/home-y/ypark/bbqc-production-backups"},
        )
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertEqual(selected.stdout, "/eos/home-y/ypark/bbqc-production-backups")

    def test_backup_dir_is_strictly_below_only_the_current_users_home_or_eos_root(self):
        # Given: durable backup evidence must stay under the current user's canonical roots.
        script = SCRIPT.read_text(encoding="utf-8")
        validator = script[
            script.index("validate_backup_directory() {") : script.index(
                "measure_durable_storage() {"
            )
        ]

        # When: the boundary policy is inspected for accepted and rejected roots.

        # Then: only descendants of canonical HOME or the exact current-user EOS root
        # qualify; roots themselves, other users, transient filesystems, traversal, and
        # symlinks do not.
        self.assertIn("pwd.getpwnam(username).pw_dir", validator)
        self.assertIn("PurePath('/eos', f'home-{username[0]}', username)", validator)
        self.assertIn("path != root and root in path.parents", validator)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            eos_root = root / "eos" / "home-y" / "young-park"
            home.mkdir()
            eos_root.mkdir(parents=True)
            home.chmod(0o700)
            eos_root.chmod(0o700)
            symlink = root / "home-link"
            symlink.symlink_to(home)
            exercised = validator.replace(
                "home = PurePath(pwd.getpwnam(username).pw_dir)",
                "home = PurePath(os.environ['TEST_HOME'])",
            ).replace(
                "eos_root = PurePath('/eos', f'home-{username[0]}', username)",
                "eos_root = PurePath(os.environ['TEST_EOS_ROOT'])",
            ).replace(
                "for index in range(1, len(path.parts) - 1):\n    directory_status(PurePath(*path.parts[:index + 1]))",
                "for index in ():\n    pass",
            ).replace(
                "parent_status = directory_status(parent)",
                "parent_status = os.stat(parent)",
            ).replace(
                "if parent_status.st_uid != os.geteuid() or parent_status.st_mode & 0o022 or not os.access(parent, os.W_OK | os.X_OK):",
                "if False:",
            )

            def validate(path: Path | str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    ["bash", "-c", f"umask 077\n{exercised}\nvalidate_backup_directory {shlex.quote(str(path))}"],
                    check=False,
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        "HOME": str(home),
                        "TEST_HOME": str(home),
                        "TEST_EOS_ROOT": str(eos_root),
                        "WORK_DIR": str(root / "work"),
                    },
                )

            accepted_home = validate(home / "bbqc-backups")
            accepted_eos = validate(eos_root / "bbqc-production-backups")
            rejected = (
                validate(home),
                validate(eos_root),
                validate(root / "eos" / "home-y" / "another-user" / "backups"),
                validate(root / "run" / "user" / "1000" / "backups"),
                validate(root / "data" / "backups"),
                validate(home / ".." / "escape"),
                validate(symlink / "backups"),
            )

        self.assertEqual(accepted_home.returncode, 0, accepted_home.stderr)
        self.assertEqual(accepted_eos.returncode, 0, accepted_eos.stderr)
        for result in rejected:
            self.assertNotEqual(result.returncode, 0)

    def test_retention_treats_checksum_sidecar_as_one_release_set(self):
        # Given: a completed helper release includes a checksum beside its backup.
        script = SCRIPT.read_text(encoding="utf-8")
        measurement = script[
            script.index("measure_dashboard_headroom() {") : script.index("verify_context() {")
        ]

        # When: retention groups recognized release artifacts by timestamp.

        # Then: the checksum is allowlisted and shares the backup's timestamp instead of
        # becoming an unknown artifact or a second retained release.
        checksum_pattern = r"comments\.sqlite3\.before-dashboard-(?P<stamp>\d{8}T\d{6}Z)\.bak\.sha256"
        self.assertIn(checksum_pattern, measurement)
        self.assertIn("stamps.add(match['stamp'])", measurement)
        self.assertIn("unknown dashboard release artifact", measurement)
        retention_start = measurement.index("import os, re\nfrom pathlib import Path")
        retention_end = measurement.index("\nPY\n)", retention_start)
        retention = measurement[retention_start:retention_end]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            complete_stamp = "20260819T120000Z"
            incomplete_stamp = "20260820T120000Z"
            for name in (
                f"dashboard-release-{complete_stamp}.env",
                f"comments.sqlite3.before-dashboard-{complete_stamp}.bak",
                f"comments.sqlite3.before-dashboard-{complete_stamp}.bak.sha256",
                f"deployment-before-dashboard-{complete_stamp}.json",
                f"service-before-dashboard-{complete_stamp}.json",
                f"route-before-dashboard-{complete_stamp}.json",
                f"buildconfig-captured-dashboard-{complete_stamp}.json",
                f"comments.sqlite3.before-dashboard-{incomplete_stamp}.bak",
                f"deploy-dashboard-{'a' * 40}.sh",
                f"bbqc-etroc-{complete_stamp}.log",
            ):
                (root / name).touch()
            counted = subprocess.run(
                ["python3", "-I", "-c", retention],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "BACKUP_DIR": str(root)},
            )
            (root / "deploy-dashboard-short-sha.sh").touch()
            unknown = subprocess.run(
                ["python3", "-I", "-c", retention],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "BACKUP_DIR": str(root)},
            )

        self.assertEqual(counted.returncode, 0, counted.stderr)
        self.assertEqual(counted.stdout, "2\n")
        self.assertNotEqual(unknown.returncode, 0)

    def test_candidate_create_failure_never_adopts_or_operates_on_a_same_name_pod(self):
        # Given: a failed create can race with an unrelated same-name pod.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index('CANDIDATE_PROBE_POD="${DEPLOYMENT}')
        end = script.index('oc -n "$PROJECT" wait', start)
        candidate_create = script[start:end]

        # When: oc run fails in a shell that records every oc invocation.
        with tempfile.TemporaryDirectory() as directory:
            commands = Path(directory) / "oc-commands"
            harness = f"""set -Eeuo pipefail
WORK_DIR={shlex.quote(directory)}
DEPLOYMENT=dashboard
PROJECT=project
NEW_WEB_IMAGE=registry.example/dashboard@sha256:{'a' * 64}
ETROC_REVIEWER_USERS_NORMALIZED=reviewer@example.invalid
CANDIDATE_PROBE_CREATE_RESPONSE="$WORK_DIR/candidate-probe-create.json"
oc() {{ printf '%s\\n' "$*" >> {shlex.quote(str(commands))}; return 1; }}
{candidate_create}
printf 'ROLLOUT_REACHED\\n' >> {shlex.quote(str(commands))}
"""
            result = subprocess.run(
                ["bash", "-c", harness], check=False, capture_output=True, text=True
            )
            recorded = commands.read_text(encoding="utf-8")

        # Then: failure is release-blocking and there is no get/adoption, copy, exec,
        # delete, or rollout continuation after the failed create.
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(recorded.count("run "), 1)
        for forbidden in (" get ", " cp ", " exec ", " delete ", "ROLLOUT_REACHED"):
            self.assertNotIn(forbidden, recorded)

    def test_storage_measurement_uses_afs_then_df_and_rejects_malformed_output(self):
        # Given: both AFS and EOS storage report formats are untrusted command output.
        script = SCRIPT.read_text(encoding="utf-8")
        helpers = script[
            script.index("measure_durable_storage() {") : script.index(
                "measure_dashboard_headroom() {"
            )
        ]

        # When: AFS uses fs lq, non-AFS uses df, and each output is malformed.
        afs = subprocess.run(
            ["bash", "-c", f"{helpers}\nBACKUP_DIR=/afs/cern.ch/user/y/ypark/bbqc-backups; fs() {{ printf 'Volume Name Quota Used %%Used Partition\\nuser 5000000 1000000 20%% disk\\n'; }}; df() {{ false; }}; measure_durable_storage"],
            check=False, capture_output=True, text=True,
        )
        eos = subprocess.run(
            ["bash", "-c", f"{helpers}\nBACKUP_DIR=/eos/home-y/ypark/bbqc-production-backups; df() {{ printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\neos 6000000 1000000 4900000 17%% /eos\\n'; }}; measure_durable_storage"],
            check=False, capture_output=True, text=True,
        )
        malformed_fs = subprocess.run(
            ["bash", "-c", f"{helpers}\nBACKUP_DIR=/afs/cern.ch/user/y/ypark/bbqc-backups; fs() {{ printf 'bad\\n'; }}; measure_durable_storage"],
            check=False, capture_output=True, text=True,
        )
        failed_afs_quota = subprocess.run(
            ["bash", "-c", f"{helpers}\nBACKUP_DIR=/afs/cern.ch/user/y/ypark/bbqc-backups; fs() {{ return 1; }}; df() {{ printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\nafs 999999999 1 999999998 1%% /afs\\n'; }}; measure_durable_storage"],
            check=False, capture_output=True, text=True,
        )
        malformed_df = subprocess.run(
            ["bash", "-c", f"{helpers}\nBACKUP_DIR=/safe; df() {{ printf 'Filesystem 1K-blocks Used Available Use%% Mounted on\\na 1 2 3 4%% /x\\nb 1 2 3 4%% /y\\n'; }}; measure_durable_storage"],
            check=False, capture_output=True, text=True,
        )

        # Then: AFS and EOS expose exact numeric evidence; malformed output fails closed.
        self.assertEqual(afs.returncode, 0, afs.stderr)
        self.assertEqual(afs.stdout.strip(), "afs 5000000 1000000 4000000")
        self.assertEqual(eos.returncode, 0, eos.stderr)
        self.assertEqual(eos.stdout.strip(), "df 6000000 1000000 4900000")
        self.assertNotEqual(malformed_fs.returncode, 0)
        self.assertNotEqual(failed_afs_quota.returncode, 0)
        self.assertNotEqual(malformed_df.returncode, 0)

    def test_dashboard_headroom_gate_accepts_sufficient_numeric_space(self):
        # Given: a database, PVC, and durable storage capacity with room beyond every explicit margin.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index(
                "measure_dashboard_headroom() {"
            )
        ]

        # When: the gate receives strict numeric KiB measurements.
        result = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1048576 1049600 afs 5000000 1000000 4000000 0"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: it permits the release and emits only numeric headroom evidence.
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"DASHBOARD_HEADROOM PASS db_bytes=1048576 .*storage_type=afs .*storage_free_kib=4000000")

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
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1048576 1000 afs 5000000 1000000 4000000 0"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: the gate fails closed before the backup can start.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PVC backup headroom is insufficient", result.stderr)

    def test_dashboard_headroom_gate_rejects_low_afs_space(self):
        # Given: durable storage has less free KiB than the copied DB, evidence allowance, and margin.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index(
                "measure_dashboard_headroom() {"
            )
        ]

        # When: the exact quota/used values leave inadequate free space.
        result = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1048576 1049600 afs 1000 999 1 0"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Then: no release artifacts are permitted.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("durable storage release-evidence headroom is insufficient", result.stderr)

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
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1KiB 1000 afs 5000000 1 4999999 0"],
            check=False,
            capture_output=True,
            text=True,
        )
        negative = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1024 -1 afs 5000000 1 4999999 0"],
            check=False,
            capture_output=True,
            text=True,
        )
        overflow = subprocess.run(
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 999999999999999999999999 1000 afs 5000000 1 4999999 0"],
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

    def test_dashboard_headroom_probe_forwards_heredoc_stdin_to_the_container(self):
        # Given: a fake oc client that returns measurements only when stdin forwarding is enabled.
        script = SCRIPT.read_text(encoding="utf-8")
        gate = script[
            script.index("PVC_BACKUP_SAFETY_KIB=") : script.index("verify_context() {")
        ]
        with tempfile.TemporaryDirectory() as backup_dir:
            command = f"""
set -Eeuo pipefail
{gate}
PROJECT=fixture
POD=fixture
BACKUP_DIR={shlex.quote(backup_dir)}
oc() {{
  case " $* " in
    *" exec -i fixture -c web -- python - "*) printf '1024 999999\\n' ;;
    *) return 64 ;;
  esac
}}
measure_durable_storage() {{ printf 'df 5000000 1 4999999\\n'; }}
validate_dashboard_headroom() {{ printf 'HEADROOM_ARGS=%s\\n' "$*"; }}
measure_dashboard_headroom
"""

            # When: the real headroom probe executes its remote Python heredoc.
            result = subprocess.run(
                ["bash", "-c", command],
                check=False,
                capture_output=True,
                text=True,
            )

        # Then: oc receives -i and the strict numeric measurements reach the gate.
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HEADROOM_ARGS=1024 999999 df 5000000 1 4999999 0", result.stdout)

    def test_every_oc_exec_heredoc_forwards_stdin_without_a_tty(self):
        # Given: every remote Python/shell heredoc in the production helper, including multiline commands.
        script = SCRIPT.read_text(encoding="utf-8")
        call_blocks = re.findall(
            r'oc -n "\$PROJECT" exec'
            r'(?:(?!oc -n "\$PROJECT" exec).)*?'
            r'(?:python -|sh -s) <<\'(?:PY|SH)\'',
            script,
            flags=re.DOTALL,
        )

        # Then: the exact closed set forwards stdin and none allocates a TTY.
        self.assertEqual(len(call_blocks), 15, f"unexpected heredoc oc exec call set: {call_blocks}")
        missing_stdin = [block for block in call_blocks if re.search(r"\bexec\s+-i(?:\s|$)", block) is None]
        tty_calls = [
            block
            for block in call_blocks
            if re.search(r"(?<!\S)-(?:t|it|ti)(?!\S)", block) is not None
        ]
        self.assertEqual(missing_stdin, [], f"heredoc oc exec calls missing -i: {missing_stdin}")
        self.assertEqual(tty_calls, [], f"machine-readable oc exec calls must not allocate a TTY: {tty_calls}")

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
            ["bash", "-c", f"{gate}\nvalidate_dashboard_headroom 1048576 1049600 afs 5000000 1000000 4000000 20"],
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
        gate = script.index("validate_backup_directory \"$BACKUP_DIR\"\nmeasure_dashboard_headroom")
        backup = script.index('oc -n "$PROJECT" exec -i "$POD" -c web -- env BACKUP=')
        artifact_write = script.index('oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$CAPTURED_DEPLOYMENT_FILE"')
        self.assertLess(gate, backup)
        self.assertLess(gate, artifact_write)
        self.assertLess(script.index('validate_backup_directory "$BACKUP_DIR"'), gate + len('validate_backup_directory "$BACKUP_DIR"'))
        self.assertNotIn("rm -f \"$BACKUP_DIR", script)

    def test_candidate_host_rehearsal_uses_the_pod_compatible_python_before_backup(self):
        # Given: LXPLUS python3 is 3.9 while the immutable production runtime is Python 3.12.
        script = SCRIPT.read_text(encoding="utf-8")

        # Then: the helper pins and validates Python 3.12 before auth/backup, and only the
        # host-side candidate-module rehearsal uses that interpreter.
        self.assertIn("CANDIDATE_HOST_PYTHON='/usr/bin/python3.12'", script)
        gate = script.index("verify_candidate_host_python\n")
        self.assertLess(gate, script.index("ensure_authenticated\n"))
        self.assertLess(gate, script.index('BACKUP="/data/comments.sqlite3.before-dashboard-'))
        self.assertIn('candidate_python_version="$("$CANDIDATE_HOST_PYTHON" -I -c', script)
        self.assertIn('test "$candidate_python_version" = 3.12.13', script)
        self.assertIn('"$CANDIDATE_HOST_PYTHON" -I -c \'from dataclasses import make_dataclass;', script)
        candidate_rehearsal = script.index('CANDIDATE_RUNTIME="${BUILD_CONTEXT}/runtime"')
        candidate_command = script[candidate_rehearsal : script.index("<<'PY'", candidate_rehearsal)]
        self.assertIn('"$CANDIDATE_HOST_PYTHON" -I -', candidate_command)
        self.assertNotIn('python3 -I -', candidate_command)
        candidate_version_gate = script.index(
            'test "$(oc -n "$PROJECT" exec "$CANDIDATE_PROBE_POD" -- env EXPECTED_POD_UID="$CANDIDATE_PROBE_POD_UID" sh -ec \'test "$POD_UID" = "$EXPECTED_POD_UID"; exec python --version\' 2>&1)" = "Python 3.12.13"'
        )
        self.assertGreater(candidate_version_gate, script.index('wait --for=condition=Ready pod/"$CANDIDATE_PROBE_POD"'))
        self.assertLess(candidate_version_gate, script.index('cat > /data/comments.sqlite3'))
        self.assertLess(candidate_version_gate, script.index("python /app/static/server.py"))

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
            "SOURCE_REVISION='50517e9e36e09f766972443700999674b2ab3395'",
            script,
        )
        expected = {
            "index.html": "37c7702345089150823340e242de698510a72c99dc83bb07f902a2465fa1e4b1",
            "dashboard.css": "5f9d7e3bab4ac732d6e7800f2c2a70fe75184db6f00a6e41da2d677e1d1a5b8f",
            "dashboard.js": "317e358631a8cea15ea4dabe6369ab1f5480454baf6e7ddcfae66d9c1b3d1644",
            "etroc-optical.css": "b5fa95983a9b85ad72b9c8c4c93573aa4d7e7961bf6356fd11e7ddc8a43d8c3c",
            "etroc-optical.js": "c565469f4b750018548db7a439018109414c7a107b1d3194a485208498652b5d",
            "etroc-review.js": "c616b8887e68044e747415ca9c088ce65a296bac107924600c3415cbbfb0bce9",
            "lgad-optical-stats.js": "e3cfb2eff6b8391cdae80b19cf75740bb5680c12434402594eb894ce36796a02",
            "ETROC_MANIFEST_SHA256": "e3c74d49cf8aea3e7dc960c92937298a653cefa7ec72a3a5a3f4177183fa9471",
            "SERVER_PY_SHA256": "b5bb6c91d7eb46eabdeedacc43abb76696cd24ff724eb0023366c313df26e55d",
            "ETROC_REVIEWS_PY_SHA256": "65819646c5dde06f62efbfbe73bad224e27e9b8b6ae9c1c6808e162801dbc454",
            "ETROC_POSITION_REVIEWS_PY_SHA256": "16d7c1b90fc34984b454167c50bd57e18638c201a2eb400b489f02a55498ae32",
            "DEPLOYMENT_MANIFEST_SHA256": "45a3a2266bcb4d18dcdb9949e5b55a00ed85f4f1e7494cebb87500b84bdbae30",
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
            "if len(lines) != 145:",
            "unsafe ETROC dataset manifest entry",
            "sum(path.startswith('montages/') for path in seen) != 36",
            "sum(path.startswith('clean-montages/sha256/') for path in seen) != 36",
            "sum(path.startswith('positions/sha256/') for path in seen) != 36",
            "sum(path.startswith('previews/') for path in seen) != 36",
            "cd '/app/static/${ETROC_DATASET_REL}' && sha256sum -c SHA256SUMS",
            "payload.get('position_record_count') != 9216",
            "len(set(assets)) != 144",
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
            "ETROC_POSITION_REVIEWS_PY_SHA256=",
            '"${RAW_ROOT}/hybrid-bbqc/${file}"',
            '"${RAW_ROOT}/hybrid-bbqc/server.py"',
            '"${RAW_ROOT}/hybrid-bbqc/etroc_reviews.py"',
            '"${RAW_ROOT}/hybrid-bbqc/etroc_position_reviews.py"',
            '"$ETROC_REVIEW_JS_SHA256"',
            '"$SERVER_PY_SHA256"',
            '"$ETROC_REVIEWS_PY_SHA256"',
            '"$ETROC_POSITION_REVIEWS_PY_SHA256"',
            "runtime/server.py",
            "runtime/etroc_reviews.py",
            "runtime/etroc_position_reviews.py",
            "COPY runtime/ /app/static/",
            "/app/static/etroc-review.js",
            "/app/static/server.py",
            "/app/static/etroc_reviews.py",
            "/app/static/etroc_position_reviews.py",
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
            "etroc_position_reviews.validate_schema(db)",
            "value_field = 'label' if 'label' in columns else 'state' if 'state' in columns else None",
            "position_version != [(1, 2)]",
            "position_review_version[0][:2] != (1, 2)",
            "PRAGMA foreign_key_check",
            "PRAGMA integrity_check",
            "OLD_RUNTIME_SERVER",
            '"$CANDIDATE_HOST_PYTHON" -I - <<\'PY\'',
            "--path \"/app/static/server.py:${OLD_RUNTIME_DIR}\"",
            "--path \"/app/static/etroc_reviews.py:${OLD_RUNTIME_DIR}\"",
            "--path \"/app/static/etroc_position_reviews.py:${OLD_RUNTIME_DIR}\"",
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
            "dataset_id=payload.get('dataset_id')",
            "key=(dataset_id,) + tuple(record.get(field) for field in ('etroc_serial','acquisition_id','analysis_run_id','montage_sha256'))",
        ):
            self.assertIn(required, script)
        self.assertNotIn("tuple(record.get(field) for field in ('dataset_id','etroc_serial'", script)

    def test_helper_gates_exact_review_runtime_contract_and_identity_boundary(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "ETROC_REVIEW_RUNTIME_CONTRACT PASS",
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608",
            "record_count') != 36",
            "len(evidence) != 36",
            "publication_sha256') != os.environ['CHIPS_PUBLICATION_SHA256']",
            "publication_dataset_id=publication.get('dataset_id')",
            "'dataset_id': publication_dataset_id",
            "etroc_review_schema",
            "etroc_review_events",
            "external trusted-header spoof was accepted",
            "internal proxy-derived allowlisted identity was not accepted",
            "X-Forwarded-Email: ${ETROC_REVIEWER_TEST_USER}",
            "ETROC review history/audit read-only schema mismatch",
            "INTERNAL_STATUS=\"$(oc -n \"$PROJECT\" exec -i \"$POD\" -c web -- env ETROC_REVIEWER_TEST_USER=\"$ETROC_REVIEWER_TEST_USER\" python - <<'PY'",
        ):
            self.assertIn(required, script)
        self.assertNotIn('exec "$POD" -c web -- sh -c \\\n  "curl --silent', script)
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

    def test_helper_proves_unauthenticated_spoofed_identity_headers_cannot_bypass_sso(self):
        # Given: only oauth2-proxy may establish the trusted identity header.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the external identity boundary is verified.

        # Then: spoofing sends the configured allowlisted identity header but is
        # redirected through CERN SSO without needing an exported browser session.
        for required in (
            "X-Forwarded-Email: ${ETROC_REVIEWER_TEST_USER}",
            "external trusted-header spoof was accepted",
            "AUTHENTICATED_BROWSER_QA PENDING",
        ):
            self.assertIn(required, script)
        self.assertNotIn("SPOOF_APPEND_STATUS", script)
        self.assertNotIn('curl --cookie ', script)

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

    def test_forward_renderer_normalizes_only_the_exact_reviewed_legacy_deltas(self):
        # Given: the captured legacy object differs from the pinned target only in the
        # reviewed target env/proxy topology, immutable images, exact Kubernetes defaults,
        # and the single operational restart annotation.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os, re, sys", script.index("render_forward_object() {"))
        renderer = script[start : script.index("\nPY\n", start)]
        target_origin = "https://etl-hybrid-bbqc.app.cern.ch"
        common_args = ["--provider=oidc", "--http-address=0.0.0.0:4180", "--upstream=http://127.0.0.1:8080", "--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback", "--email-domain=*", "--reverse-proxy=true", "--pass-host-header=true", "--pass-user-headers=true"]
        legacy_args = common_args + ["--set-xauthrequest=true", "--skip-provider-button=true", "--cookie-secure=true", "--cookie-samesite=lax"]
        target_args = common_args + ["--skip-auth-strip-headers=false", "--skip-provider-button=true", "--cookie-secure=true", "--cookie-samesite=lax"]
        baseline_deployment = {
            "apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {"name": "etl-hybrid-bbqc", "labels": {"app": "etl-hybrid-bbqc"}, "annotations": {}},
            "spec": {"template": {"metadata": {"labels": {"app": "etl-hybrid-bbqc"}}, "spec": {"containers": [
                {"name": "web", "image": "baseline-web", "env": [
                    {"name": "HOST", "value": "127.0.0.1"},
                    {"name": "COMMENTS_ADMIN_USERS", "value": "user@cern.ch"},
                    {"name": "ETROC_REVIEWER_USERS", "value": "user@cern.ch"},
                    {"name": "APP_ORIGIN", "value": target_origin},
                ], "readinessProbe": {"exec": {"command": ["probe"]}, "periodSeconds": 10, "timeoutSeconds": 3}, "livenessProbe": {"exec": {"command": ["probe"]}, "periodSeconds": 20, "timeoutSeconds": 3}},
                {"name": "oauth2-proxy", "image": "baseline-proxy", "args": target_args},
            ]}}},
        }
        baseline_service = {
            "apiVersion": "v1", "kind": "Service",
            "metadata": {"name": "etl-hybrid-bbqc", "labels": {"app": "etl-hybrid-bbqc"}, "annotations": {}},
            "spec": {"selector": {"app": "etl-hybrid-bbqc"}, "ports": [{"name": "oauth", "protocol": "TCP", "port": 4180, "targetPort": "oauth"}]},
        }

        # When: each exact legacy capture is rendered against the target baseline.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            captured_deployment = json.loads(json.dumps(baseline_deployment))
            captured_deployment["metadata"] |= {"namespace": "etroc-solder-inspection", "uid": "deployment-uid", "resourceVersion": "1"}
            captured_deployment["spec"]["template"]["spec"]["containers"][0]["image"] = "old-web"
            captured_deployment["spec"]["template"]["spec"]["containers"][0]["env"] = [{"name": "HOST", "value": "127.0.0.1"}]
            captured_deployment["spec"]["template"]["spec"]["containers"][1]["image"] = "old-proxy"
            captured_deployment["spec"]["template"]["spec"]["containers"][1]["args"] = legacy_args
            for probe_name in ("readinessProbe", "livenessProbe"):
                captured_deployment["spec"]["template"]["spec"]["containers"][0][probe_name] |= {
                    "failureThreshold": 3, "successThreshold": 1, "timeoutSeconds": 3,
                }
            captured_deployment["spec"] |= {"progressDeadlineSeconds": 600, "revisionHistoryLimit": 10}
            captured_deployment["spec"]["template"]["metadata"]["annotations"] = {"kubectl.kubernetes.io/restartedAt": "2026-07-29T09:00:57+02:00"}
            captured_deployment["spec"]["template"]["spec"] |= {
                "dnsPolicy": "ClusterFirst", "restartPolicy": "Always", "schedulerName": "default-scheduler",
                "securityContext": {}, "terminationGracePeriodSeconds": 30,
            }
            captured_service = json.loads(json.dumps(baseline_service))
            captured_service["metadata"] |= {"namespace": "etroc-solder-inspection", "uid": "service-uid", "resourceVersion": "1"}
            captured_service["spec"]["ports"] = [{"name": "oauth", "protocol": "TCP", "port": 8080, "targetPort": "oauth"}]
            captured_service["spec"] |= {
                "clusterIP": "172.30.14.70", "clusterIPs": ["172.30.14.70"],
                "ipFamilies": ["IPv4"], "ipFamilyPolicy": "SingleStack",
                "internalTrafficPolicy": "Cluster", "sessionAffinity": "None", "type": "ClusterIP",
            }
            for kind, baseline, captured in (("Deployment", baseline_deployment, captured_deployment), ("Service", baseline_service, captured_service)):
                baseline_file, captured_file = root / f"{kind}-baseline.json", root / f"{kind}-captured.json"
                baseline_file.write_text(json.dumps(baseline), encoding="utf-8")
                captured_file.write_text(json.dumps(captured), encoding="utf-8")
                environment = os.environ | {"RELEASE_KIND": kind, "BASELINE_OBJECT_FILE": str(baseline_file), "CAPTURED_OBJECT_FILE": str(captured_file), "NEW_WEB_IMAGE": "new-web", "OLD_WEB_IMAGE": "old-web", "OLD_PROXY_IMAGE": "old-proxy", "OLD_TOPOLOGY_MODE": "legacy", "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context", "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch"}
                result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
                self.assertEqual(result.returncode, 0, result.stderr)
                rendered = json.loads(result.stdout)
                if kind == "Deployment":
                    rendered_web = next(item for item in rendered["spec"]["template"]["spec"]["containers"] if item["name"] == "web")
                    rendered_proxy = next(item for item in rendered["spec"]["template"]["spec"]["containers"] if item["name"] == "oauth2-proxy")
                    rendered_env = {item["name"]: item["value"] for item in rendered_web["env"]}
                    self.assertEqual(rendered_env["APP_ORIGIN"], target_origin)
                    self.assertEqual(rendered_env["COMMENTS_ADMIN_USERS"], "user@cern.ch")
                    self.assertEqual(rendered_env["ETROC_REVIEWER_USERS"], "user@cern.ch")
                    self.assertEqual(rendered_proxy["image"], "old-proxy")
                    self.assertEqual(rendered_web["readinessProbe"]["timeoutSeconds"], 3)
                    self.assertEqual(rendered_web["livenessProbe"]["timeoutSeconds"], 3)
                    self.assertEqual(rendered["spec"]["progressDeadlineSeconds"], 600)
                else:
                    self.assertEqual(rendered["spec"]["ports"], baseline_service["spec"]["ports"])

            target_capture = json.loads(json.dumps(baseline_deployment))
            target_capture["metadata"] |= {"namespace": "etroc-solder-inspection", "uid": "deployment-uid", "resourceVersion": "2"}
            target_capture["spec"]["template"]["spec"]["containers"][0]["image"] = "old-web"
            target_capture["spec"]["template"]["spec"]["containers"][1]["image"] = "old-proxy"
            target_capture["spec"]["template"]["spec"]["containers"][0]["env"].reverse()
            target_capture_file = root / "Deployment-captured-target-permuted.json"
            target_capture_file.write_text(json.dumps(target_capture), encoding="utf-8")
            target_environment = os.environ | {"RELEASE_KIND": "Deployment", "BASELINE_OBJECT_FILE": str(root / "Deployment-baseline.json"), "CAPTURED_OBJECT_FILE": str(target_capture_file), "NEW_WEB_IMAGE": "new-web", "OLD_WEB_IMAGE": "old-web", "OLD_PROXY_IMAGE": "old-proxy", "OLD_TOPOLOGY_MODE": "target", "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context", "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch"}
            target_result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=target_environment)
            self.assertEqual(target_result.returncode, 0, target_result.stderr)
            target_capture["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"] = "drift"
            target_capture_file.write_text(json.dumps(target_capture), encoding="utf-8")
            target_drift = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=target_environment)
            self.assertNotEqual(target_drift.returncode, 0)
            self.assertIn("environment differs from pinned baseline", target_drift.stderr)

            invalid_service = json.loads(json.dumps(captured_service))
            invalid_service["spec"]["type"] = "NodePort"
            invalid_service_file = root / "Service-captured-invalid-default.json"
            invalid_service_file.write_text(json.dumps(invalid_service), encoding="utf-8")
            environment["RELEASE_KIND"] = "Service"
            environment["BASELINE_OBJECT_FILE"] = str(root / "Service-baseline.json")
            environment["CAPTURED_OBJECT_FILE"] = str(invalid_service_file)
            invalid_service_result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
            self.assertNotEqual(invalid_service_result.returncode, 0)
            self.assertIn("Service server default is not the reviewed value", invalid_service_result.stderr)

            # Then: an invalid calendar/timezone value and unrelated legacy drift remain blocking.
            for invalid_value in ("2026-99-99T99:99:99+99:99", "2026-07-29T09:00:57+00:60"):
                invalid_time = json.loads(json.dumps(captured_deployment))
                invalid_time["spec"]["template"]["metadata"]["annotations"]["kubectl.kubernetes.io/restartedAt"] = invalid_value
                invalid_time_file = root / "Deployment-captured-invalid-time.json"
                invalid_time_file.write_text(json.dumps(invalid_time), encoding="utf-8")
                environment["RELEASE_KIND"] = "Deployment"
                environment["BASELINE_OBJECT_FILE"] = str(root / "Deployment-baseline.json")
                environment["CAPTURED_OBJECT_FILE"] = str(invalid_time_file)
                invalid_time_result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
                self.assertNotEqual(invalid_time_result.returncode, 0)
                self.assertIn("restart annotation is invalid", invalid_time_result.stderr)

            subset_baseline = json.loads(json.dumps(baseline_deployment))
            subset_env = subset_baseline["spec"]["template"]["spec"]["containers"][0]["env"]
            subset_baseline["spec"]["template"]["spec"]["containers"][0]["env"] = [item for item in subset_env if item["name"] != "ETROC_REVIEWER_USERS"]
            subset_baseline_file = root / "Deployment-baseline-subset.json"
            subset_baseline_file.write_text(json.dumps(subset_baseline), encoding="utf-8")
            environment["BASELINE_OBJECT_FILE"] = str(subset_baseline_file)
            environment["CAPTURED_OBJECT_FILE"] = str(root / "Deployment-captured.json")
            subset_result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
            self.assertNotEqual(subset_result.returncode, 0)
            self.assertIn("target environment is incomplete or duplicated", subset_result.stderr)

            captured_deployment["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"] = "0.0.0.0"
            captured_file = root / "Deployment-captured-drift.json"
            captured_file.write_text(json.dumps(captured_deployment), encoding="utf-8")
            environment["RELEASE_KIND"] = "Deployment"
            environment["BASELINE_OBJECT_FILE"] = str(root / "Deployment-baseline.json")
            environment["CAPTURED_OBJECT_FILE"] = str(captured_file)
            drift = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("spec differs from pinned baseline", drift.stderr)

    def test_forward_renderer_preserves_only_baseline_approved_annotations(self):
        # Given: a captured object has exactly the pinned annotations plus generated noise.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os, re, sys", script.index("render_forward_object() {"))
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
                "NEW_WEB_IMAGE": "unused", "OLD_WEB_IMAGE": "unused", "OLD_PROXY_IMAGE": "unused", "OLD_TOPOLOGY_MODE": "target", "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context", "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch",
            }
            result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        annotations = json.loads(result.stdout)["metadata"]["annotations"]
        self.assertEqual(annotations["haproxy.router.openshift.io/ip_whitelist"], "10.0.0.0/8")
        self.assertNotIn("kubectl.kubernetes.io/last-applied-configuration", annotations)

    def test_forward_renderer_normalizes_only_reviewed_route_server_defaults(self):
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os, re, sys", script.index("render_forward_object() {"))
        renderer = script[start : script.index("\nPY\n", start)]
        baseline = {
            "apiVersion": "route.openshift.io/v1", "kind": "Route",
            "metadata": {"name": "etl-hybrid-bbqc", "labels": {"app": "etl-hybrid-bbqc"}, "annotations": {}},
            "spec": {"host": "etl-hybrid-bbqc.app.cern.ch", "to": {"kind": "Service", "name": "etl-hybrid-bbqc"}, "port": {"targetPort": "oauth"}, "tls": {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"}},
        }
        captures = (
            ("weight and wildcard server defaults", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100}, None, {"wildcardPolicy": "None"}, {}, False),
            ("pinned wildcard policy remains", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100}, None, {"wildcardPolicy": "None"}, {"wildcardPolicy": "None"}, False),
            ("captured omission differs from pinned wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {}, {"wildcardPolicy": "None"}, True),
            ("null weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": None}, None, {}, {}, True),
            ("zero weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 0}, None, {}, {}, True),
            ("other weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 99}, None, {}, {}, True),
            ("string weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": "100"}, None, {}, {}, True),
            ("extra to key", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100, "unexpected": True}, None, {}, {}, True),
            ("empty wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": ""}, {}, True),
            ("subdomain wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": "Subdomain"}, {}, True),
            ("null wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": None}, {}, True),
            ("other wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": "Wildcard"}, {}, True),
            ("extra route key", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"unexpected": True}, {}, True),
            ("explicit empty alternate backends", {"kind": "Service", "name": "etl-hybrid-bbqc"}, [], {}, {}, True),
            ("alternate backend", {"kind": "Service", "name": "etl-hybrid-bbqc"}, [{"kind": "Service", "name": "other", "weight": 1}], {}, {}, True),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (case, route_to, alternate_backends, captured_fields, baseline_fields, rejected) in enumerate(captures):
                pinned = json.loads(json.dumps(baseline))
                pinned["spec"].update(baseline_fields)
                baseline_file = root / f"baseline-{index}.json"
                baseline_file.write_text(json.dumps(pinned), encoding="utf-8")
                captured = json.loads(json.dumps(baseline))
                captured["metadata"] |= {"namespace": "etroc-solder-inspection", "uid": "route-uid", "resourceVersion": "9"}
                captured["spec"]["to"] = route_to
                captured["spec"].update(captured_fields)
                if alternate_backends is not None:
                    captured["spec"]["alternateBackends"] = alternate_backends
                captured_file = root / f"captured-{index}.json"
                captured_file.write_text(json.dumps(captured), encoding="utf-8")
                environment = os.environ | {"RELEASE_KIND": "Route", "BASELINE_OBJECT_FILE": str(baseline_file), "CAPTURED_OBJECT_FILE": str(captured_file), "NEW_WEB_IMAGE": "unused", "OLD_WEB_IMAGE": "unused", "OLD_PROXY_IMAGE": "unused", "OLD_TOPOLOGY_MODE": "target", "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context", "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch"}
                result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
                self.assertEqual(result.returncode != 0, rejected, f"{case}: {result.stderr}")
                if not rejected:
                    self.assertEqual(json.loads(result.stdout)["spec"], pinned["spec"])

    def test_forward_renderer_preserves_only_attested_cern_route_annotations(self):
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os, re, sys", script.index("render_forward_object() {"))
        renderer = script[start : script.index("\nPY\n", start)]
        baseline = {
            "apiVersion": "route.openshift.io/v1", "kind": "Route",
            "metadata": {"name": "etl-hybrid-bbqc", "labels": {"app": "etl-hybrid-bbqc"}, "annotations": {}},
            "spec": {"host": "etl-hybrid-bbqc.app.cern.ch", "to": {"kind": "Service", "name": "etl-hybrid-bbqc"}, "port": {"targetPort": "oauth"}, "tls": {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"}},
        }
        whitelist = "0.0.0.0/0 ::/0"
        last_applied = json.dumps({"metadata": {"annotations": {"haproxy.router.openshift.io/ip_whitelist": whitelist}}})
        captured = json.loads(json.dumps(baseline))
        captured["metadata"] |= {
            "namespace": "etroc-solder-inspection", "uid": "route-uid", "resourceVersion": "9",
            "annotations": {
                "haproxy.router.openshift.io/ip_whitelist": whitelist,
                "external-dns.alpha.kubernetes.io/target": "paas-apps-shard-4.cern.ch",
                "kubectl.kubernetes.io/last-applied-configuration": last_applied,
            },
        }
        captured["spec"]["to"]["weight"] = 100
        captured["spec"]["wildcardPolicy"] = "None"
        captured["status"] = {"ingress": [{
            "host": "etl-hybrid-bbqc.app.cern.ch", "routerName": "apps-shard-4",
            "routerCanonicalHostname": "router-apps-shard-4.paas-apps-shard-4.cern.ch",
            "wildcardPolicy": "None", "conditions": [{"type": "Admitted", "status": "True"}],
        }]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline_file = root / "baseline.json"
            captured_file = root / "captured.json"
            baseline_file.write_text(json.dumps(baseline), encoding="utf-8")
            environment = os.environ | {
                "RELEASE_KIND": "Route", "BASELINE_OBJECT_FILE": str(baseline_file), "CAPTURED_OBJECT_FILE": str(captured_file),
                "NEW_WEB_IMAGE": "unused", "OLD_WEB_IMAGE": "unused", "OLD_PROXY_IMAGE": "unused", "OLD_TOPOLOGY_MODE": "legacy",
                "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context", "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch",
            }
            captured_file.write_text(json.dumps(captured), encoding="utf-8")
            valid = subprocess.run([sys.executable, "-I", "-c", renderer], capture_output=True, text=True, env=environment)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            annotations = json.loads(valid.stdout)["metadata"]["annotations"]
            self.assertEqual(annotations["haproxy.router.openshift.io/ip_whitelist"], whitelist)
            self.assertEqual(annotations["external-dns.alpha.kubernetes.io/target"], "paas-apps-shard-4.cern.ch")
            self.assertNotIn("kubectl.kubernetes.io/last-applied-configuration", annotations)
            target_capture = json.loads(json.dumps(captured))
            target_capture["metadata"]["annotations"].pop("kubectl.kubernetes.io/last-applied-configuration")
            captured_file.write_text(json.dumps(target_capture), encoding="utf-8")
            environment["OLD_TOPOLOGY_MODE"] = "target"
            target = subprocess.run([sys.executable, "-I", "-c", renderer], capture_output=True, text=True, env=environment)
            self.assertEqual(target.returncode, 0, target.stderr)
            mismatched = json.loads(json.dumps(target_capture))
            mismatched["metadata"]["annotations"]["external-dns.alpha.kubernetes.io/target"] = "paas-apps-shard-5.cern.ch"
            captured_file.write_text(json.dumps(mismatched), encoding="utf-8")
            mismatch = subprocess.run([sys.executable, "-I", "-c", renderer], capture_output=True, text=True, env=environment)
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn("external DNS target differs from admitted router shard", mismatch.stderr)
            unknown = json.loads(json.dumps(target_capture))
            unknown["metadata"]["annotations"]["unreviewed.example/policy"] = "enabled"
            captured_file.write_text(json.dumps(unknown), encoding="utf-8")
            unknown_result = subprocess.run([sys.executable, "-I", "-c", renderer], capture_output=True, text=True, env=environment)
            self.assertNotEqual(unknown_result.returncode, 0)
            self.assertIn("annotations differ from pinned baseline", unknown_result.stderr)

    def test_captured_rollback_renderer_preserves_route_wildcard_policy(self):
        # Given: the captured Route has OpenShift's explicit server-default policy.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os", script.index("render_captured_rollback_object() {"))
        renderer = script[start : script.index("\nPY\n", start)]
        captured = {
            "apiVersion": "route.openshift.io/v1", "kind": "Route",
            "metadata": {"name": "etl-hybrid-bbqc", "namespace": "etroc-solder-inspection", "uid": "route-uid"},
            "spec": {"host": "etl-hybrid-bbqc.app.cern.ch", "to": {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100}, "port": {"targetPort": "oauth"}, "tls": {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"}, "wildcardPolicy": "None"},
        }

        # When: rollback is rendered from the captured Route.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            captured_file, rollback_file = root / "captured.json", root / "rollback.json"
            captured_file.write_text(json.dumps(captured), encoding="utf-8")
            result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=os.environ | {"CAPTURED_OBJECT_FILE": str(captured_file), "ROLLBACK_OBJECT_FILE": str(rollback_file)})

            # Then: the rollback artifact accepts and retains the captured server default.
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(rollback_file.read_text(encoding="utf-8"))["spec"]["wildcardPolicy"], "None")

    def test_forward_renderer_rejects_annotation_drift_except_known_generated_values(self):
        # Given: generated annotations are tolerated but policy and unknown annotations are not.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os, re, sys", script.index("render_forward_object() {"))
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
                environment = os.environ | {"RELEASE_KIND": kind, "BASELINE_OBJECT_FILE": str(baseline_file), "CAPTURED_OBJECT_FILE": str(captured_file), "NEW_WEB_IMAGE": "new-web", "OLD_WEB_IMAGE": "old-web", "OLD_PROXY_IMAGE": "old-proxy", "OLD_TOPOLOGY_MODE": "target", "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context", "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch"}
                result = subprocess.run([sys.executable, "-I", "-c", renderer], check=False, capture_output=True, text=True, env=environment)
                self.assertEqual(result.returncode != 0, bool(expected_failure), result.stderr)
                if expected_failure:
                    if name == "route whitelist value":
                        self.assertIn("Route reviewed annotations are incomplete or invalid", result.stderr)
                    else:
                        self.assertIn("annotations differ from pinned baseline", result.stderr)

    def test_forward_renderer_accepts_exact_validated_release_annotations_on_all_objects(self):
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("import copy, json, os, re, sys", script.index("render_forward_object() {"))
        renderer = script[start : script.index("\nPY\n", start)]
        release = {
            "bbqc.cern.ch/source-revision": "a" * 40,
            "bbqc.cern.ch/build-context-sha256": "b" * 64,
            "bbqc.cern.ch/build-name": "build.build.openshift.io/etl-hybrid-bbqc-47",
            "bbqc.cern.ch/release-mode": "immutable-overlay",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind, spec in (
                ("Service", {"selector": {"app": "etl-hybrid-bbqc"}}),
                ("Route", {"host": "etl-hybrid-bbqc.app.cern.ch"}),
            ):
                baseline = {"apiVersion": "v1", "kind": kind, "metadata": {"name": "etl-hybrid-bbqc", "labels": {"app": "etl-hybrid-bbqc"}, "annotations": {}}, "spec": spec}
                captured = {**baseline, "metadata": {**baseline["metadata"], "namespace": "etroc-solder-inspection", "uid": f"{kind.lower()}-uid", "resourceVersion": "9", "annotations": release}}
                baseline_file, captured_file = root / f"{kind}-baseline.json", root / f"{kind}-captured.json"
                baseline_file.write_text(json.dumps(baseline), encoding="utf-8")
                captured_file.write_text(json.dumps(captured), encoding="utf-8")
                environment = os.environ | {
                    "RELEASE_KIND": kind, "BASELINE_OBJECT_FILE": str(baseline_file), "CAPTURED_OBJECT_FILE": str(captured_file),
                    "NEW_WEB_IMAGE": "unused", "OLD_WEB_IMAGE": "unused", "OLD_PROXY_IMAGE": "unused", "OLD_TOPOLOGY_MODE": "target",
                    "OLD_RELEASE_ANNOTATIONS_JSON": json.dumps(release), "SOURCE_REVISION": "source", "BUILD_CONTEXT_SHA256": "context",
                    "BUILD_NAME": "build", "ETROC_REVIEWER_USERS_NORMALIZED": "user@cern.ch",
                }
                valid = subprocess.run([sys.executable, "-I", "-c", renderer], capture_output=True, text=True, env=environment)
                self.assertEqual(valid.returncode, 0, f"{kind}: {valid.stderr}")
                drifted = json.loads(json.dumps(captured))
                drifted["metadata"]["annotations"]["bbqc.cern.ch/source-revision"] = "c" * 40
                captured_file.write_text(json.dumps(drifted), encoding="utf-8")
                invalid = subprocess.run([sys.executable, "-I", "-c", renderer], capture_output=True, text=True, env=environment)
                self.assertNotEqual(invalid.returncode, 0)
                self.assertIn("previous release annotation changed after validation", invalid.stderr)

    def test_deployment_pins_web_probe_timeout_above_internal_http_timeout(self):
        manifest = yaml.safe_load((ROOT / "hybrid-bbqc" / "openshift" / "deployment.yaml").read_text(encoding="utf-8"))
        web = next(item for item in manifest["spec"]["template"]["spec"]["containers"] if item["name"] == "web")
        for probe_name in ("readinessProbe", "livenessProbe"):
            probe = web[probe_name]
            self.assertEqual(probe.get("timeoutSeconds"), 3, probe_name)
            self.assertIn("timeout=2", probe["exec"]["command"][-1])

    def test_buildconfig_manifest_pins_build_history_retention(self):
        manifest = yaml.safe_load((ROOT / "hybrid-bbqc" / "openshift" / "buildconfig.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["spec"]["successfulBuildsHistoryLimit"], 5)
        self.assertEqual(manifest["spec"]["failedBuildsHistoryLimit"], 5)

    def test_previous_release_annotations_are_bound_to_completed_build_digest(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("validate_previous_release_annotations() {", script)
        validator = script[
            script.index("validate_previous_release_annotations() {") : script.index(
                "render_forward_object() {", script.index("validate_previous_release_annotations() {")
            )
        ]
        for required in (
            "bbqc.cern.ch/source-revision",
            "bbqc.cern.ch/build-context-sha256",
            "bbqc.cern.ch/build-name",
            "bbqc.cern.ch/release-mode",
            "status.output.to.imageDigest",
            "successfulBuildsHistoryLimit",
            "get', 'builds', '-l', 'buildconfig=' + buildconfig",
            "retained successful Build identity or owner is invalid",
            "missing previous release Build is not explained by successful-Build retention",
            "imagestreamimage/",
            "openshift.io/image.managed",
            "image.openshift.io/manifestBlobStored",
            "io.openshift.build.name",
            "previous release image is absent or duplicated in ImageStream history",
            "BUILDCONFIG_UID",
            "ownerReferences",
            "previous release Build controller ownerReference is invalid",
            "previous release Build is not complete",
            "previous release Build digest differs from deployed old image",
        ):
            self.assertIn(required, validator)
        forward = script[script.index("render_forward_object() {") : script.index("render_captured_rollback_object() {")]
        self.assertIn("OLD_RELEASE_ANNOTATIONS_JSON", forward)
        self.assertIn("validated_previous_release_annotations", forward)

    def test_previous_release_build_owner_reference_rejection_is_executable(self):
        script = SCRIPT.read_text(encoding="utf-8")
        function_start = script.index("validate_previous_release_annotations() {")
        python_start = script.index("import json, os, re, subprocess", function_start)
        validator = script[python_start : script.index("\nPY\n}\n\nrender_forward_object()", python_start)]
        annotations = {
            "bbqc.cern.ch/source-revision": "a" * 40,
            "bbqc.cern.ch/build-context-sha256": "b" * 64,
            "bbqc.cern.ch/build-name": "build.build.openshift.io/etl-hybrid-bbqc-39",
            "bbqc.cern.ch/release-mode": "immutable-overlay",
        }
        buildconfig_uid = "c79ed76a-20fe-4798-9194-b30a617a3590"
        digest = "sha256:" + "c" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            captured = root / "deployment.json"
            captured.write_text(json.dumps({"metadata": {"uid": "deployment-uid", "annotations": annotations}, "spec": {"template": {"spec": {"containers": [{"name": "web", "image": "registry.example/etl-hybrid-bbqc@" + digest}]}}}}), encoding="utf-8")
            fake_build = root / "build.json"
            fake_oc = root / "oc"
            fake_oc.write_text("#!/bin/sh\ncat \"$FAKE_BUILD_JSON\"\n", encoding="utf-8")
            fake_oc.chmod(0o700)
            base_build = {
                "metadata": {
                    "name": "etl-hybrid-bbqc-39",
                    "namespace": "etroc-solder-inspection",
                    "labels": {"buildconfig": "etl-hybrid-bbqc"},
                    "annotations": {
                        "openshift.io/build-config.name": "etl-hybrid-bbqc",
                        "openshift.io/build.number": "39",
                    },
                },
                "status": {"phase": "Complete", "output": {"to": {"imageDigest": digest}}},
            }
            environment = os.environ | {
                "PATH": str(root) + os.pathsep + os.environ["PATH"],
                "FAKE_BUILD_JSON": str(fake_build),
                "CAPTURED_DEPLOYMENT_FILE": str(captured),
                "OLD_WEB_IMAGE": "registry.example/etl-hybrid-bbqc@" + digest,
                "PROJECT": "etroc-solder-inspection",
                "BUILDCONFIG": "etl-hybrid-bbqc",
                "BUILDCONFIG_UID": buildconfig_uid,
                "DEPLOYMENT_UID": "deployment-uid",
            }
            cases = (
                ("valid", [{"apiVersion": "build.openshift.io/v1", "controller": True, "kind": "BuildConfig", "name": "etl-hybrid-bbqc", "uid": buildconfig_uid}], 0),
                ("missing", [], 1),
                ("wrong", [{"apiVersion": "build.openshift.io/v1", "controller": True, "kind": "BuildConfig", "name": "etl-hybrid-bbqc", "uid": "wrong-uid"}], 1),
            )
            for label, owners, expected_failure in cases:
                with self.subTest(label=label):
                    payload = json.loads(json.dumps(base_build))
                    payload["metadata"]["ownerReferences"] = owners
                    fake_build.write_text(json.dumps(payload), encoding="utf-8")
                    result = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
                    self.assertEqual(result.returncode != 0, bool(expected_failure), result.stderr)
                    if expected_failure:
                        self.assertIn("controller ownerReference is invalid", result.stderr)

    def test_previous_release_pruned_build_fallback_is_executable(self):
        script = SCRIPT.read_text(encoding="utf-8")
        function_start = script.index("validate_previous_release_annotations() {")
        python_start = script.index("import json, os, re, subprocess", function_start)
        validator = script[python_start : script.index("\nPY\n}\n\nrender_forward_object()", python_start)]
        annotations = {
            "bbqc.cern.ch/source-revision": "a" * 40,
            "bbqc.cern.ch/build-context-sha256": "b" * 64,
            "bbqc.cern.ch/build-name": "build.build.openshift.io/etl-hybrid-bbqc-39",
            "bbqc.cern.ch/release-mode": "immutable-overlay",
        }
        uid = "c79ed76a-20fe-4798-9194-b30a617a3590"
        digest = "sha256:" + "c" * 64
        old_image = "registry.example/etroc-solder-inspection/etl-hybrid-bbqc@" + digest
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deployment = root / "deployment.json"
            buildconfig = root / "buildconfig.json"
            isi_file = root / "isi.json"
            stream_file = root / "stream.json"
            builds_file = root / "builds.json"
            deployment.write_text(json.dumps({"metadata": {"uid": "deployment-uid", "annotations": annotations}, "spec": {"template": {"spec": {"containers": [{"name": "web", "image": old_image}]}}}}), encoding="utf-8")
            buildconfig.write_text(json.dumps({
                "metadata": {"name": "etl-hybrid-bbqc", "namespace": "etroc-solder-inspection", "uid": uid, "creationTimestamp": "2026-07-03T06:36:44Z"},
                "spec": {"successfulBuildsHistoryLimit": 5}, "status": {"lastVersion": 45},
            }), encoding="utf-8")
            isi_file.write_text(json.dumps({
                "metadata": {"name": "etl-hybrid-bbqc@" + digest, "namespace": "etroc-solder-inspection"},
                "image": {
                    "metadata": {"name": digest, "creationTimestamp": "2026-08-18T12:38:58Z", "annotations": {"openshift.io/image.managed": "true", "image.openshift.io/manifestBlobStored": "true"}},
                    "dockerImageReference": old_image,
                    "dockerImageMetadata": {"Config": {"Labels": {"io.openshift.build.name": "etl-hybrid-bbqc-39", "io.openshift.build.namespace": "etroc-solder-inspection"}}},
                },
            }), encoding="utf-8")
            valid_stream = {
                "metadata": {"name": "etl-hybrid-bbqc", "namespace": "etroc-solder-inspection"},
                "status": {"tags": [{"tag": "latest", "items": [{"image": digest, "dockerImageReference": old_image, "created": "2026-08-18T12:38:58Z"}]}]},
            }
            stream_file.write_text(json.dumps(valid_stream), encoding="utf-8")
            retained_owner = [{"apiVersion": "build.openshift.io/v1", "controller": True, "kind": "BuildConfig", "name": "etl-hybrid-bbqc", "uid": uid}]
            builds_file.write_text(json.dumps({"items": [
                {
                    "metadata": {
                        "name": f"etl-hybrid-bbqc-{number}", "namespace": "etroc-solder-inspection", "creationTimestamp": f"2026-08-19T12:{number}:00Z",
                        "ownerReferences": retained_owner, "labels": {"buildconfig": "etl-hybrid-bbqc"},
                        "annotations": {"openshift.io/build.number": str(number), "openshift.io/build-config.name": "etl-hybrid-bbqc"},
                    },
                    "status": {"phase": "Complete", "completionTimestamp": f"2026-08-19T13:{number}:00Z"},
                }
                for number in range(40, 45)
            ]}), encoding="utf-8")
            fake_oc = root / "oc"
            fake_oc.write_text(
                "#!/bin/sh\ncase \"$*\" in\n"
                "  *\"get build/\"*) exit 0 ;;\n"
                "  *\"get builds \"*) cat \"$FAKE_BUILDS_JSON\" ;;\n"
                "  *\"get imagestreamimage/\"*) cat \"$FAKE_ISI_JSON\" ;;\n"
                "  *\"get imagestream/\"*) cat \"$FAKE_STREAM_JSON\" ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_oc.chmod(0o700)
            environment = os.environ | {
                "PATH": str(root) + os.pathsep + os.environ["PATH"],
                "FAKE_ISI_JSON": str(isi_file), "FAKE_STREAM_JSON": str(stream_file), "FAKE_BUILDS_JSON": str(builds_file),
                "CAPTURED_DEPLOYMENT_FILE": str(deployment), "CAPTURED_BUILDCONFIG_FILE": str(buildconfig),
                "OLD_WEB_IMAGE": old_image, "PROJECT": "etroc-solder-inspection",
                "BUILDCONFIG": "etl-hybrid-bbqc", "BUILDCONFIG_UID": uid, "DEPLOYMENT_UID": "deployment-uid",
            }
            valid = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            valid_buildconfig = json.loads(buildconfig.read_text(encoding="utf-8"))
            missing_history = json.loads(json.dumps(valid_buildconfig))
            missing_history["spec"].pop("successfulBuildsHistoryLimit")
            buildconfig.write_text(json.dumps(missing_history), encoding="utf-8")
            missing_history_result = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertNotEqual(missing_history_result.returncode, 0)
            self.assertIn("retention is not explicit", missing_history_result.stderr)
            recreated_buildconfig = json.loads(json.dumps(valid_buildconfig))
            recreated_buildconfig["metadata"]["creationTimestamp"] = "2026-08-18T13:00:00Z"
            buildconfig.write_text(json.dumps(recreated_buildconfig), encoding="utf-8")
            recreated_result = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertNotEqual(recreated_result.returncode, 0)
            self.assertIn("image predates current BuildConfig UID", recreated_result.stderr)
            buildconfig.write_text(json.dumps(valid_buildconfig), encoding="utf-8")
            valid_builds = json.loads(builds_file.read_text(encoding="utf-8"))
            older_retained = json.loads(json.dumps(valid_builds))
            older_item = json.loads(json.dumps(older_retained["items"][0]))
            older_item["metadata"]["name"] = "etl-hybrid-bbqc-38"
            older_item["metadata"]["annotations"]["openshift.io/build.number"] = "38"
            older_item["status"]["completionTimestamp"] = "2026-08-19T15:38:00Z"
            older_retained["items"].append(older_item)
            builds_file.write_text(json.dumps(older_retained), encoding="utf-8")
            older_result = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertNotEqual(older_result.returncode, 0)
            self.assertIn("not newer than historical release", older_result.stderr)
            out_of_order = json.loads(json.dumps(valid_builds))
            out_of_order["items"][1]["status"]["completionTimestamp"] = "2026-08-18T12:00:00Z"
            builds_file.write_text(json.dumps(out_of_order), encoding="utf-8")
            chronology_result = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertNotEqual(chronology_result.returncode, 0)
            self.assertIn("completion sequence", chronology_result.stderr)
            builds_file.write_text(json.dumps(valid_builds), encoding="utf-8")
            insufficient_builds = json.loads(json.dumps(valid_builds))
            insufficient_builds["items"] = insufficient_builds["items"][:4]
            builds_file.write_text(json.dumps(insufficient_builds), encoding="utf-8")
            insufficient = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertNotEqual(insufficient.returncode, 0)
            self.assertIn("not explained by successful-Build retention", insufficient.stderr)
            gapped_builds = json.loads(json.dumps(valid_builds))
            last = gapped_builds["items"][-1]
            last["metadata"]["name"] = "etl-hybrid-bbqc-45"
            last["metadata"]["annotations"]["openshift.io/build.number"] = "45"
            last["status"]["completionTimestamp"] = "2026-08-19T13:45:00Z"
            builds_file.write_text(json.dumps(gapped_builds), encoding="utf-8")
            gapped = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertNotEqual(gapped.returncode, 0)
            self.assertIn("not explained by successful-Build retention", gapped.stderr)
            shifted_builds = json.loads(json.dumps(valid_builds))
            for item in shifted_builds["items"]:
                old_number = int(item["metadata"]["annotations"]["openshift.io/build.number"])
                new_number = old_number + 1
                item["metadata"]["name"] = f"etl-hybrid-bbqc-{new_number}"
                item["metadata"]["annotations"]["openshift.io/build.number"] = str(new_number)
                item["status"]["completionTimestamp"] = f"2026-08-19T14:{new_number}:00Z"
            builds_file.write_text(json.dumps(shifted_builds), encoding="utf-8")
            shifted = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertEqual(shifted.returncode, 0, shifted.stderr)
            builds_file.write_text(json.dumps(valid_builds), encoding="utf-8")
            invalid_stream = json.loads(json.dumps(valid_stream))
            invalid_stream["status"]["tags"][0]["items"] = []
            stream_file.write_text(json.dumps(invalid_stream), encoding="utf-8")
            invalid = subprocess.run([sys.executable, "-I", "-c", validator], capture_output=True, text=True, env=environment)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("absent or duplicated in ImageStream history", invalid.stderr)

    def test_candidate_probe_cleanup_is_uid_guarded_and_owned_before_possible_failures(self):
        # Given: candidate creation succeeded and later wait, copy, or startup can fail.
        script = SCRIPT.read_text(encoding="utf-8")
        candidate_start = script.index('oc -n "$PROJECT" run "$CANDIDATE_PROBE_POD"')
        ownership = script.index("CANDIDATE_PROBE_POD_OWNED=1", candidate_start)
        self.assertIn("verify_candidate_probe_identity() {", script)
        identity_start = script.index("verify_candidate_probe_identity() {")
        identity = script[identity_start : script.index("\n}\n", identity_start) + 3]
        for later in (
            'oc -n "$PROJECT" wait',
            'cat > /data/comments.sqlite3',
            'cat > /tmp/candidate-http-acquisition-id',
            'python /app/static/server.py',
        ):
            later_position = script.index(later, candidate_start)
            self.assertGreater(script.rfind("verify_candidate_probe_identity", candidate_start, later_position), candidate_start)
            self.assertLess(ownership, later_position)
        cleanup_start = script.index("cleanup_candidate_probe_pod() {")
        cleanup = script[cleanup_start : script.index("\n}\n", cleanup_start) + 3]

        # When: cleanup sees the original UID twice, then sees a recreated UID.
        harness = f'''set -Eeuo pipefail
{cleanup}
{identity}
PROJECT=project
WORK_DIR="$(mktemp -d)"
CANDIDATE_PROBE_POD=probe
CANDIDATE_PROBE_POD_UID=original
CANDIDATE_PROBE_POD_OWNED=0
cleanup_candidate_probe_pod
CANDIDATE_PROBE_POD_OWNED=1
mock_uid=original
deletes=0
oc() {{
  if [[ "$*" == *get* ]]; then printf '%s' "$mock_uid"; return 0; fi
  if [[ "$*" == *delete* ]]; then deletes=$((deletes + 1)); return 0; fi
  return 1
}}
verify_candidate_probe_identity
mock_uid=recreated
if verify_candidate_probe_identity; then exit 1; fi
mock_uid=original
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
            "validate_manifest_topology rollback \"$deployment_topology\" \"$service_topology\" \"$route_topology\" \"$OLD_TOPOLOGY_MODE\"",
            "validate_oauth2_proxy_topology rollback \"$OLD_PROXY_IMAGE\" \"$OLD_TOPOLOGY_MODE\"",
        ):
            self.assertIn(required, rollback)

    def test_rollback_keeps_pre_rollout_etroc_snapshot_as_the_invariant(self):
        # Given: production verification never appends a review event.
        script = SCRIPT.read_text(encoding="utf-8")
        before = '{"present":true,"count":1,"identity_chain":[[1,"old"]]}'
        after_append = '{"present":true,"count":2,"identity_chain":[[1,"old"],[2,"append"]]}'
        start = script.index("assert_etroc_snapshot() {")
        end = script.index("\n}\n", start) + 3
        assertion = script[start:end]

        # When: rollback compares the restored database with the pre-rollout snapshot.
        accepted = subprocess.run(
            ["bash", "-c", f"{assertion}\nassert_etroc_snapshot {shlex.quote(after_append)} {shlex.quote(after_append)}"],
            check=False, capture_output=True, text=True,
        )
        rejected = subprocess.run(
            ["bash", "-c", f"{assertion}\nassert_etroc_snapshot {shlex.quote(before)} {shlex.quote(after_append)}"],
            check=False, capture_output=True, text=True,
        )

        # Then: an appended production event is rejected, and rollback remains owned
        # until every mandatory read-only production gate has passed.
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertNotIn("ETROC_EVENT_SNAPSHOT_EXPECTED_ROLLBACK", script)
        committed = script.index("FORWARD_RELEASE_COMMITTED after mandatory read-only post-rollout gates")
        ownership_released = script.index("ROLLOUT_MUTATED=0", committed)
        self.assertLess(script.index("AUTHENTICATED_BROWSER_QA PENDING"), committed)
        self.assertLess(committed, ownership_released)
        rollback = script[script.index("rollback_deployment() {") : script.index("attempt_rollback() {")]
        self.assertIn('assert_etroc_snapshot "$ETROC_EVENT_SNAPSHOT_BEFORE"', rollback)

    def test_helper_never_accepts_operator_scientific_review_inputs(self):
        # Given: deployment verification is operational, not a scientific review.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the helper is inspected for operator-provided dispositions.

        # Then: no acquisition, state, note, validator, or production proxy flow can
        # choose or synthesize a scientific disposition.
        for forbidden in (
            "ETROC_REVIEW_ACQUISITION_ID",
            "ETROC_REVIEW_STATE",
            "ETROC_REVIEW_NOTE",
            "validate_operator_review_inputs",
            "ETROC_REVIEW_PROXY_FLOW PASS",
        ):
            self.assertNotIn(forbidden, script)

    def test_helper_exercises_review_mutation_only_on_disposable_candidate_copies(self):
        # Given: append semantics need end-to-end coverage without changing production.
        script = SCRIPT.read_text(encoding="utf-8")
        candidate = script[script.index('CANDIDATE_PROBE_POD="${DEPLOYMENT}') : script.index("CANDIDATE_IMAGE_STARTUP PASS")]

        # When: the new image is started with a copied local backup on emptyDir.

        # Then: it performs one authorized append with exact readback/history/audit,
        # idempotent replay and stale conflict, while retaining append-only and legacy
        # Hybrid-comments invariants entirely before the production mutation.
        for required in (
            "emptyDir",
            'cat > /data/comments.sqlite3',
            "candidate HTTP existing-history supersession response is invalid",
            "idempotent_replay",
            "stale_current",
            "candidate history/audit exactness mismatch",
            "candidate HTTP replay/stale conflict changed event count",
            "candidate Hybrid comments changed during review mutation verification",
            "CANDIDATE_REVIEW_MUTATION PASS",
        ):
            self.assertIn(required, candidate)
        self.assertLess(script.index("CANDIDATE_REVIEW_MUTATION PASS"), script.index('ROLLOUT_MUTATED=1'))
        self.assertNotRegex(candidate, re.compile(r'oc -n "\$PROJECT" (?:cp|exec).*"\$POD"'))

    def test_helper_makes_disposable_empty_and_existing_review_history_gates_deterministic(self):
        # Given: the production backup may contain either no ETROC history or arbitrary
        # pre-existing history for the canonical publication acquisition.
        script = SCRIPT.read_text(encoding="utf-8")
        local_gate = script[script.index('cp "$LOCAL_BACKUP" "$CANDIDATE_DB"') : script.index("CANDIDATE_ETROC_SCHEMA PASS")]
        candidate = script[script.index('CANDIDATE_PROBE_POD="${DEPLOYMENT}') : script.index("CANDIDATE_IMAGE_STARTUP PASS")]

        # When: the disposable local and new-image candidate gates are assembled.

        # Then: the local gate clears one deterministic chain, proves empty-history
        # append then supersession with +2 events, and seeds the emptyDir copy with a
        # deterministic one-event chain for an HTTP-only existing-history +1 proof.
        for required in (
            "CANDIDATE_HTTP_ACQUISITION_FILE",
            "DELETE FROM etroc_review_events WHERE acquisition_id=?",
            "expected_current_event_id': None",
            "local empty-history append response is invalid",
            "local existing-history supersession response is invalid",
            "local empty-history replay/stale conflict changed event count",
            "local existing-history replay/stale conflict changed event count",
            "local deterministic mutation count is not +2",
            "supersedes_event_id') is not None",
            "supersedes_event_id') != event1['event_id']",
            "candidate HTTP seed event is invalid",
        ):
            self.assertIn(required, local_gate)
        resets = local_gate.split("db.execute('DROP TRIGGER etroc_review_no_delete')")[1:]
        self.assertEqual(len(resets), 2)
        for reset in resets:
            delete = reset.index("DELETE FROM etroc_review_events WHERE acquisition_id=?")
            restore = reset.index("db.execute(etroc_reviews.DDL[7])")
            validate = reset.index("etroc_reviews.init_schema(candidate)")
            self.assertLess(delete, restore)
            self.assertLess(restore, validate)
        self.assertEqual(
            local_gate.count("audit_record_key={field: getattr(record, field) for field in etroc_reviews.KEY_FIELDS}"),
            1,
        )
        self.assertEqual(local_gate.count("chain.get('evidence') == audit_record_key"), 2)
        self.assertNotIn("chain.get('evidence') == record.as_dict()", local_gate)
        for diagnostic in (
            "existing_history_checks={",
            "history_status",
            "audit_status",
            "history_evidence",
            "history_current",
            "history_chain",
            "audit_chain_count",
            "audit_current",
            "audit_history",
            "failed=",
        ):
            self.assertIn(diagnostic, local_gate)
        for required in (
            'cat > /data/comments.sqlite3',
            'CANDIDATE_HTTP_ACQUISITION_FILE',
            "candidate HTTP existing-history supersession response is invalid",
            "candidate HTTP replay/stale conflict changed event count",
            "candidate HTTP mutation count is not +1",
            "supersedes_event_id') != prior_event_id",
        ):
            self.assertIn(required, candidate)
        self.assertNotIn('oc -n "$PROJECT" cp "$LOCAL_BACKUP"', candidate)
        self.assertLess(script.index("CANDIDATE_REVIEW_MUTATION PASS"), script.index('ROLLOUT_MUTATED=1'))

    def test_topology_inventory_covers_every_service_and_route_selecting_live_pods(self):
        # Given: an additional Service can select the live template with labels other
        # than the historical app label, and a second Route can expose that Service.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the preflight topology inventory is run.

        # Then: it derives the live template labels, inventories all Routes, and rejects
        # both the direct web Service and any additional Route to a selected Service.
        topology = script[
            script.index("validate_oauth2_proxy_topology_files() {") : script.index(
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
            script.index("validate_oauth2_proxy_topology_files() {") : script.index(
                "snapshot_etroc_review_events() {"
            )
        ]
        self.assertIn("EXPECTED_PROXY_IMAGE", topology)
        self.assertIn("oauth2-proxy image differs from captured reviewed digest", topology)
        self.assertIn('validate_oauth2_proxy_topology preflight \'\' either', script)
        self.assertIn('validate_captured_oauth2_proxy_topology "$CAPTURED_DEPLOYMENT_FILE" "$CAPTURED_SERVICE_FILE" "$CAPTURED_ROUTE_FILE" "$OLD_PROXY_IMAGE" either "$OLD_WEB_IMAGE"', script)
        self.assertIn('validate_oauth2_proxy_topology captured-bind "$OLD_PROXY_IMAGE" "$OLD_TOPOLOGY_MODE" "$OLD_WEB_IMAGE"', script)
        self.assertIn('validate_oauth2_proxy_topology pre-mutation "$OLD_PROXY_IMAGE" "$OLD_TOPOLOGY_MODE" "$OLD_WEB_IMAGE"', script)
        self.assertIn('validate_oauth2_proxy_topology post-rollout "$OLD_PROXY_IMAGE"', script)

    def test_preflight_accepts_exact_legacy_target_and_rejects_hybrids(self):
        # Given: the live release can be either the exact legacy or target contract.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("validate_oauth2_proxy_topology_files() {")
        topology_end = script.index("\n}\n", script.index("validate_oauth2_proxy_topology() {")) + 3
        topology = script[start:topology_end]
        digest = "registry.example/proxy@sha256:" + "a" * 64
        common = ["--provider=oidc", "--http-address=0.0.0.0:4180", "--upstream=http://127.0.0.1:8080", "--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback", "--email-domain=*", "--reverse-proxy=true", "--pass-host-header=true", "--pass-user-headers=true"]
        legacy_args = common + ["--set-xauthrequest=true", "--skip-provider-button=true", "--cookie-secure=true", "--cookie-samesite=lax"]
        target_args = common + ["--skip-auth-strip-headers=false", "--skip-provider-button=true", "--cookie-secure=true", "--cookie-samesite=lax"]

        def deployment(origin: bool, args: list[str]):
            env = [{"name": "HOST", "value": "127.0.0.1"}]
            if origin:
                env.append({"name": "APP_ORIGIN", "value": "https://etl-hybrid-bbqc.app.cern.ch"})
            return {"kind": "Deployment", "spec": {"template": {"metadata": {"labels": {"app": "etl-hybrid-bbqc"}}, "spec": {"containers": [{"name": "web", "image": "registry.example/web@sha256:" + "b" * 64, "env": env}, {"name": "oauth2-proxy", "image": digest, "ports": [{"name": "oauth", "containerPort": 4180, "protocol": "TCP"}], "args": args}]}}}}

        cases = (("legacy", deployment(False, legacy_args), 8080, "legacy", False), ("target", deployment(True, target_args), 4180, "target", False), ("origin legacy args", deployment(True, legacy_args), 8080, "", True), ("legacy service target deployment", deployment(True, target_args), 8080, "", True), ("xauth and no strip", deployment(True, common + ["--set-xauthrequest=true", "--skip-auth-strip-headers=false", "--skip-provider-button=true", "--cookie-secure=true", "--cookie-samesite=lax"]), 4180, "", True))
        invalid_origins = (
            ("valueFrom", {"name": "APP_ORIGIN", "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}}}),
            ("null", {"name": "APP_ORIGIN", "value": None}),
            ("duplicate", {"name": "APP_ORIGIN", "value": "https://etl-hybrid-bbqc.app.cern.ch"}),
        )
        for name, extra_origin in invalid_origins:
            invalid = deployment(True, target_args)
            if name == "duplicate":
                invalid["spec"]["template"]["spec"]["containers"][0]["env"].append(extra_origin)
            else:
                invalid["spec"]["template"]["spec"]["containers"][0]["env"][-1] = extra_origin
            cases += ((f"target APP_ORIGIN {name}", invalid, 4180, "", True),)
        legacy_value_from = deployment(False, legacy_args)
        legacy_value_from["spec"]["template"]["spec"]["containers"][0]["env"].append(invalid_origins[0][1])
        cases += (("legacy APP_ORIGIN valueFrom", legacy_value_from, 8080, "", True),)
        route_forms = (
            ("source omission", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {}, False),
            ("weight and wildcard server defaults", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100}, None, {"wildcardPolicy": "None"}, False),
            ("null weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": None}, None, {}, True),
            ("zero weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 0}, None, {}, True),
            ("other weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 99}, None, {}, True),
            ("string weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": "100"}, None, {}, True),
            ("extra to key", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100, "unexpected": True}, None, {}, True),
            ("empty wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": ""}, True),
            ("subdomain wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": "Subdomain"}, True),
            ("null wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": None}, True),
            ("other wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": "Wildcard"}, True),
            ("extra route key", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"unexpected": True}, True),
            ("explicit empty alternate backends", {"kind": "Service", "name": "etl-hybrid-bbqc"}, [], {}, True),
            ("alternate backend", {"kind": "Service", "name": "etl-hybrid-bbqc"}, [{"kind": "Service", "name": "other", "weight": 1}], {}, True),
            ("malformed alternate backends", {"kind": "Service", "name": "etl-hybrid-bbqc"}, {"name": "other"}, {}, True),
        )
        for name, deployment_object, service_port, mode, rejected in cases:
            for route_name, route_to, alternate_backends, route_fields, route_rejected in route_forms:
                with self.subTest(name=name, route=route_name), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / "bin").mkdir()
                    service = {"items": [{"metadata": {"name": "etl-hybrid-bbqc"}, "spec": {"selector": {"app": "etl-hybrid-bbqc"}, "ports": [{"name": "oauth", "protocol": "TCP", "port": service_port, "targetPort": "oauth"}]}}]}
                    route_spec = {"host": "etl-hybrid-bbqc.app.cern.ch", "to": route_to, "port": {"targetPort": "oauth"}, "tls": {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"}, **route_fields, **({"alternateBackends": alternate_backends} if alternate_backends is not None else {})}
                    route = {"items": [{"metadata": {"name": "etl-hybrid-bbqc"}, "spec": route_spec}]}
                    for filename, value in (("deployment.json", deployment_object), ("services.json", service), ("routes.json", route)):
                        (root / filename).write_text(json.dumps(value), encoding="utf-8")
                    fake_oc = root / "bin" / "oc"
                    fake_oc.write_text("#!/usr/bin/env bash\ncase \"$*\" in\n  *'get deployment/'*) cat \"$FAKE_TOPOLOGY_DIR/deployment.json\" ;;\n  *'get services '*) cat \"$FAKE_TOPOLOGY_DIR/services.json\" ;;\n  *'get routes '*) cat \"$FAKE_TOPOLOGY_DIR/routes.json\" ;;\n  *) exit 64 ;;\nesac\n", encoding="utf-8")
                    fake_oc.chmod(0o755)
                    harness = f'''set -Eeuo pipefail
{topology}
WORK_DIR={shlex.quote(str(root / "work"))}
PROJECT=project
DEPLOYMENT=etl-hybrid-bbqc
mkdir -p "$WORK_DIR"
OLD_TOPOLOGY_MODE="$(validate_oauth2_proxy_topology captured-pre-rollout {shlex.quote(digest)} either)"
printf 'OLD_TOPOLOGY_MODE=%s\\n' "$OLD_TOPOLOGY_MODE"
'''
                    result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True, env=os.environ | {"PATH": f"{root / 'bin'}:{os.environ['PATH']}", "FAKE_TOPOLOGY_DIR": str(root)})
                    self.assertEqual(result.returncode != 0, rejected or route_rejected, result.stderr)
                    if not rejected and not route_rejected:
                        self.assertEqual(result.stdout, f"OLD_TOPOLOGY_MODE={mode}\n")

    def test_captured_topology_classification_binds_legacy_rollback_before_live_refetch(self):
        # Given: an earlier preflight could observe target while the durable capture is legacy.
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("validate_captured_oauth2_proxy_topology", script)
        capture_start = script.index('oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$CAPTURED_DEPLOYMENT_FILE"')
        mode_assignment = script.index('OLD_TOPOLOGY_MODE="$(validate_captured_oauth2_proxy_topology')
        self.assertLess(capture_start, mode_assignment)
        self.assertNotIn('OLD_TOPOLOGY_MODE="$(validate_oauth2_proxy_topology captured-pre-rollout', script)

        # When: the capture-bound classifier is used for the durable rollback objects.
        start = script.index("validate_captured_oauth2_proxy_topology() {")
        classifier = script[start : script.index("\n}\n", start) + 3]
        harness = f'''set -Eeuo pipefail
{classifier}
validate_oauth2_proxy_topology_files() {{ printf '%s' legacy; }}
mode="$(validate_captured_oauth2_proxy_topology deployment service route proxy legacy web)"
test "$mode" = legacy
'''
        result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True)

        # Then: rollback mode comes from the captured files, not a live preflight value.
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rendered_manifest_rejects_nonliteral_or_duplicate_app_origin(self):
        # Given: rendered target manifests must carry exactly one literal APP_ORIGIN.
        script = SCRIPT.read_text(encoding="utf-8")
        start = script.index("validate_manifest_topology() {")
        validator = script[start : script.index("\n}\n", start) + 3]
        origin = "https://etl-hybrid-bbqc.app.cern.ch"
        args = ["--provider=oidc", "--http-address=0.0.0.0:4180", "--upstream=http://127.0.0.1:8080", "--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback", "--email-domain=*", "--reverse-proxy=true", "--pass-host-header=true", "--pass-user-headers=true", "--skip-auth-strip-headers=false", "--skip-provider-button=true", "--cookie-secure=true", "--cookie-samesite=lax"]
        deployment = {"kind": "Deployment", "metadata": {"name": "etl-hybrid-bbqc"}, "spec": {"template": {"spec": {"containers": [{"name": "web", "env": [{"name": "HOST", "value": "127.0.0.1"}, {"name": "APP_ORIGIN", "value": origin}]}, {"name": "oauth2-proxy", "ports": [{"name": "oauth", "containerPort": 4180, "protocol": "TCP"}], "args": args}]}}}}
        service = {"kind": "Service", "metadata": {"name": "etl-hybrid-bbqc"}, "spec": {"selector": {"app": "etl-hybrid-bbqc"}, "ports": [{"name": "oauth", "protocol": "TCP", "port": 4180, "targetPort": "oauth"}]}}
        route = {"kind": "Route", "metadata": {"name": "etl-hybrid-bbqc"}, "spec": {"host": "etl-hybrid-bbqc.app.cern.ch", "to": {"kind": "Service", "name": "etl-hybrid-bbqc"}, "port": {"targetPort": "oauth"}, "tls": {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"}}}
        invalid_origins = (
            {"name": "APP_ORIGIN", "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}}},
            {"name": "APP_ORIGIN", "value": None},
            {"name": "APP_ORIGIN", "value": origin},
        )

        # When: a literal entry is replaced or duplicated in otherwise exact manifests.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, invalid_origin in enumerate(invalid_origins):
                invalid = json.loads(json.dumps(deployment))
                environment = invalid["spec"]["template"]["spec"]["containers"][0]["env"]
                if index == 2:
                    environment.append(invalid_origin)
                else:
                    environment[-1] = invalid_origin
                deployment_file, service_file, route_file = root / f"deployment-{index}.json", root / "service.json", root / "route.json"
                deployment_file.write_text(json.dumps(invalid), encoding="utf-8")
                service_file.write_text(json.dumps(service), encoding="utf-8")
                route_file.write_text(json.dumps(route), encoding="utf-8")
                harness = f'''set -Eeuo pipefail
{validator}
WORK_DIR={shlex.quote(str(root / f"work-{index}"))}
mkdir -p "$WORK_DIR"
oc() {{ local argument; for argument in "$@"; do :; done; cat "$argument"; }}
validate_manifest_topology target {shlex.quote(str(deployment_file))} {shlex.quote(str(service_file))} {shlex.quote(str(route_file))}
'''
                result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True)

                # Then: every non-exact APP_ORIGIN form is release-blocking.
                self.assertNotEqual(result.returncode, 0, result.stderr)

            route_forms = (
                ("source omission", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {}, "target", False),
                ("legacy weight and wildcard server defaults", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100}, None, {"wildcardPolicy": "None"}, "legacy", False),
                ("target weight and wildcard server defaults", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100}, None, {"wildcardPolicy": "None"}, "target", False),
                ("null weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": None}, None, {}, "target", True),
                ("zero weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 0}, None, {}, "target", True),
                ("other weight", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 99}, None, {}, "target", True),
                ("extra to key", {"kind": "Service", "name": "etl-hybrid-bbqc", "weight": 100, "unexpected": True}, None, {}, "target", True),
                ("empty wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": ""}, "target", True),
                ("subdomain wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": "Subdomain"}, "target", True),
                ("null wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": None}, "target", True),
                ("other wildcard policy", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"wildcardPolicy": "Wildcard"}, "target", True),
                ("extra route key", {"kind": "Service", "name": "etl-hybrid-bbqc"}, None, {"unexpected": True}, "target", True),
                ("explicit empty alternate backends", {"kind": "Service", "name": "etl-hybrid-bbqc"}, [], {}, "target", True),
                ("alternate backend", {"kind": "Service", "name": "etl-hybrid-bbqc"}, [{"kind": "Service", "name": "other", "weight": 1}], {}, "target", True),
            )
            for index, (case, route_to, alternate_backends, route_fields, mode, rejected) in enumerate(route_forms):
                route_spec = {"host": "etl-hybrid-bbqc.app.cern.ch", "to": route_to, "port": {"targetPort": "oauth"}, "tls": {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"}, **route_fields, **({"alternateBackends": alternate_backends} if alternate_backends is not None else {})}
                route_file = root / f"route-weight-{index}.json"
                route_file.write_text(json.dumps({"kind": "Route", "metadata": {"name": "etl-hybrid-bbqc"}, "spec": route_spec}), encoding="utf-8")
                deployment_file = root / f"deployment-weight-{index}.json"
                deployment_file.write_text(json.dumps(deployment), encoding="utf-8")
                harness = f'''set -Eeuo pipefail
{validator}
WORK_DIR={shlex.quote(str(root / f"weight-work-{index}"))}
mkdir -p "$WORK_DIR"
oc() {{ local argument; for argument in "$@"; do :; done; cat "$argument"; }}
validate_manifest_topology {mode} {shlex.quote(str(deployment_file))} {shlex.quote(str(service_file))} {shlex.quote(str(route_file))}
'''
                result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True)
                self.assertEqual(result.returncode != 0, rejected, f"{case}: {result.stderr}")

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
        candidate = script[script.index('CANDIDATE_PROBE_POD="${DEPLOYMENT}') : script.index("CANDIDATE_IMAGE_STARTUP PASS")]
        mutation = script.index('ROLLOUT_MUTATED=1')
        self.assertLess(script.index("CANDIDATE_IMAGE_STARTUP PASS"), mutation)
        for required in (
            "candidate-startup-probe",
            'cat > /data/comments.sqlite3',
            "python /app/static/server.py",
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608",
            "candidate evidence loader did not return exact cohort",
            "candidate served montage bytes mismatch",
            "CANDIDATE_LEGACY_COMMENTS_COMPAT PASS",
        ):
            self.assertIn(required, candidate if required != "CANDIDATE_LEGACY_COMMENTS_COMPAT PASS" else script)

    def test_helper_has_no_cookie_export_or_production_review_post_workflow(self):
        # Given: post-rollout gates must be read-only and session-independent.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the complete helper and post-rollout section are inspected.

        # Then: no cookie jars or second-user session inputs remain, and no production
        # request can invoke the ETROC review POST endpoint after rollout.
        for forbidden in (
            "ETROC_AUTHENTICATED_SESSION_COOKIE_JAR",
            "ETROC_NON_ALLOWLISTED_SESSION_COOKIE_JAR",
            "validate_cookie_jar_inputs",
            'curl --cookie ',
        ):
            self.assertNotIn(forbidden, script)
        post_rollout = script[script.index('ROLLOUT_MUTATED=1') :]
        self.assertNotIn("--request POST", post_rollout)
        self.assertNotIn("method='POST'", post_rollout)

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

        # Then: ownership comes from the create response, the replacement-prone override
        # retains the exact immutable image, and delete is UID-preconditioned.
        self.assertIn("--output=json", candidate)
        self.assertIn("CANDIDATE_PROBE_CREATE_RESPONSE", candidate)
        self.assertIn("candidate probe create response", candidate)
        self.assertIn("\"image\":\"'\"$NEW_WEB_IMAGE\"'\"", candidate)
        self.assertIn('"command":["sleep","300"]', candidate)
        self.assertIn('"fieldPath":"metadata.uid"', candidate)
        self.assertNotIn('oc -n "$PROJECT" cp ', candidate)
        self.assertGreaterEqual(candidate.count('EXPECTED_POD_UID="$CANDIDATE_PROBE_POD_UID"'), 4)
        self.assertIn("cat /tmp/candidate-entrypoint.log", candidate)
        self.assertNotIn('logs "$CANDIDATE_PROBE_POD"', candidate)
        self.assertLess(
            candidate.index("CANDIDATE_PROBE_POD_OWNED=1"),
            candidate.index("candidate probe create response spec mismatch"),
        )
        self.assertIn('--raw="/api/v1/namespaces/', cleanup)
        self.assertIn("preconditions", cleanup)
        self.assertIn("uid", cleanup)
        self.assertNotIn('delete pod/"$CANDIDATE_PROBE_POD"', cleanup)

    def test_invalid_created_candidate_spec_triggers_uid_preconditioned_cleanup(self):
        script = SCRIPT.read_text(encoding="utf-8")
        cleanup_start = script.index("cleanup_candidate_probe_pod() {")
        cleanup = script[cleanup_start : script.index("\n}\n", cleanup_start) + 3]
        candidate_start = script.index('oc -n "$PROJECT" run "$CANDIDATE_PROBE_POD"')
        validation_start = script.index('CANDIDATE_PROBE_POD_UID="$(CANDIDATE_PROBE_CREATE_RESPONSE=', candidate_start)
        validation_end = script.index("\nverify_candidate_probe_identity\n", validation_start)
        capture_and_validate = script[validation_start:validation_end]

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            response = work / "candidate-probe-create.json"
            marker = work / "deleted"
            response.write_text(
                json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "Pod",
                        "metadata": {"name": "probe", "namespace": "project", "uid": "original"},
                        "spec": {
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "probe",
                                    "image": "immutable-image",
                                    "command": ["wrong-command"],
                                    "volumeMounts": [{"name": "data", "mountPath": "/data"}],
                                    "env": [
                                        {"name": "HOST", "value": "127.0.0.1"},
                                        {"name": "ETROC_REVIEWER_USERS", "value": "ypark"},
                                        {
                                            "name": "POD_UID",
                                            "valueFrom": {
                                                "fieldRef": {"apiVersion": "v1", "fieldPath": "metadata.uid"}
                                            },
                                        },
                                    ],
                                }
                            ],
                            "volumes": [{"name": "data", "emptyDir": {}}],
                        },
                    }
                ),
                encoding="utf-8",
            )
            harness = f'''set -Eeuo pipefail
{cleanup}
PROJECT=project
WORK_DIR={shlex.quote(str(work))}
CANDIDATE_PROBE_POD=probe
CANDIDATE_PROBE_POD_UID=''
CANDIDATE_PROBE_POD_OWNED=0
CANDIDATE_PROBE_CREATE_RESPONSE={shlex.quote(str(response))}
NEW_WEB_IMAGE=immutable-image
ETROC_REVIEWER_USERS_NORMALIZED=ypark
DELETE_MARKER={shlex.quote(str(marker))}
oc() {{
  if [[ "$*" == *get* ]]; then printf original; return 0; fi
  if [[ "$*" == *"delete --raw="* ]]; then printf deleted > "$DELETE_MARKER"; return 0; fi
  return 1
}}
trap cleanup_candidate_probe_pod EXIT
{capture_and_validate}
'''
            result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True)
            delete_options = json.loads((work / "candidate-probe-delete-options.json").read_text(encoding="utf-8"))
            marker_value = marker.read_text(encoding="utf-8")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("candidate probe create response spec mismatch", result.stderr)
        self.assertEqual(marker_value, "deleted")
        self.assertEqual(delete_options["preconditions"], {"uid": "original"})

    def test_old_runtime_server_extraction_is_digest_pinned_and_rejects_bad_output(self):
        # Given: a fake `oc` records authenticated public-registry extraction calls.
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
printf '%s\\n' \"$@\" >> \"$FAKE_OC_ARGS\"
case \"$1 $2\" in
  'registry login')
    test \"$3\" = --to=\"$FAKE_AUTH_PATH\"
    case \"$FAKE_AUTH_MODE\" in
      success) printf '%s' \"$FAKE_AUTH_CONTENT\" > \"$FAKE_AUTH_PATH\"; chmod 600 \"$FAKE_AUTH_PATH\" ;;
      symlink) ln -s \"$FAKE_SERVER\" \"$FAKE_AUTH_PATH\" ;;
      world_readable) printf '%s' \"$FAKE_AUTH_CONTENT\" > \"$FAKE_AUTH_PATH\"; chmod 644 \"$FAKE_AUTH_PATH\" ;;
      empty) : > \"$FAKE_AUTH_PATH\" ;;
      hardlink) printf '%s' \"$FAKE_AUTH_CONTENT\" > \"$FAKE_AUTH_PATH\"; ln \"$FAKE_AUTH_PATH\" \"$FAKE_AUTH_PATH.link\" ;;
    esac ;;
  'image extract')
    test \"$3\" = --registry-config=\"$FAKE_AUTH_PATH\"
    test \"$4\" = \"$FAKE_PUBLIC_IMAGE\"
    test \"$5\" = --path
    test \"$7\" = --path
    test \"$9\" = --path
    test \"$(stat -c '%a' \"$FAKE_AUTH_PATH\")\" = 600
    test \"$(stat -c '%h' \"$FAKE_AUTH_PATH\")\" = 1
    test -s \"$FAKE_AUTH_PATH\"
    case \"$FAKE_OC_MODE\" in
      success) cp \"$FAKE_SERVER\" \"${6#*:}/server.py\"; cp \"$FAKE_ETROC_REVIEWS\" \"${8#*:}/etroc_reviews.py\"; cp \"$FAKE_ETROC_POSITION_REVIEWS\" \"${10#*:}/etroc_position_reviews.py\" ;;
      symlink) cp \"$FAKE_ETROC_REVIEWS\" \"${8#*:}/etroc_reviews.py\"; cp \"$FAKE_ETROC_POSITION_REVIEWS\" \"${10#*:}/etroc_position_reviews.py\"; ln -s \"$FAKE_SERVER\" \"${6#*:}/server.py\" ;;
      extra) cp \"$FAKE_SERVER\" \"${6#*:}/server.py\"; cp \"$FAKE_ETROC_REVIEWS\" \"${8#*:}/etroc_reviews.py\"; cp \"$FAKE_ETROC_POSITION_REVIEWS\" \"${10#*:}/etroc_position_reviews.py\"; : > \"${6#*:}/unexpected.py\" ;;
      empty) cp \"$FAKE_ETROC_REVIEWS\" \"${8#*:}/etroc_reviews.py\"; cp \"$FAKE_ETROC_POSITION_REVIEWS\" \"${10#*:}/etroc_position_reviews.py\"; : > \"${6#*:}/server.py\" ;;
      malformed) cp \"$FAKE_ETROC_REVIEWS\" \"${8#*:}/etroc_reviews.py\"; cp \"$FAKE_ETROC_POSITION_REVIEWS\" \"${10#*:}/etroc_position_reviews.py\"; printf 'not valid python =\\n' > \"${6#*:}/server.py\" ;;
      failure) exit 42 ;;
    esac ;;
  *) exit 99 ;;
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
import etroc_reviews
import etroc_position_reviews
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
            dependency = root / "etroc_reviews.py"
            dependency.write_text("# previous runtime dependency\n", encoding="utf-8")
            dependency.chmod(0o600)
            position_dependency = root / "etroc_position_reviews.py"
            position_dependency.write_text("# previous position runtime dependency\n", encoding="utf-8")
            position_dependency.chmod(0o600)
            candidate_db = root / "candidate.sqlite3"
            environment = os.environ | {
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "FAKE_OC_ARGS": str(root / "oc-args"),
                "FAKE_SERVER": str(source),
                "FAKE_ETROC_REVIEWS": str(dependency),
                "FAKE_ETROC_POSITION_REVIEWS": str(position_dependency),
                "CANDIDATE_DB": str(candidate_db),
                "FAKE_AUTH_CONTENT": "registry-token-must-not-escape",
            }
            harness = f'''set -Eeuo pipefail
{extraction}
WORK_DIR={shlex.quote(str(root / "work"))}
mkdir -p "$WORK_DIR"
OLD_RUNTIME_DIR="$WORK_DIR/previous-runtime"
OLD_RUNTIME_SERVER="$OLD_RUNTIME_DIR/server.py"
OLD_RUNTIME_ETROC_REVIEWS="$OLD_RUNTIME_DIR/etroc_reviews.py"
OLD_RUNTIME_ETROC_POSITION_REVIEWS="$OLD_RUNTIME_DIR/etroc_position_reviews.py"
OLD_WEB_IMAGE="${{TEST_OLD_WEB_IMAGE:-image-registry.openshift-image-registry.svc:5000/etroc-solder-inspection/etl-hybrid-bbqc@sha256:{'a' * 64}}}"
FAKE_AUTH_PATH="$WORK_DIR/registry-auth.json"
FAKE_PUBLIC_IMAGE="registry.paas.cern.ch/etroc-solder-inspection/etl-hybrid-bbqc@sha256:{'a' * 64}"
export FAKE_AUTH_PATH FAKE_PUBLIC_IMAGE
: > "$FAKE_OC_ARGS"
if test "${{FAKE_EXPECT_FAILURE:-0}}" = 1; then
  set +e
  extract_previous_runtime_server
  status=$?
  set -e
  test "$status" -ne 0
  test ! -e "$FAKE_AUTH_PATH"
  printf 'EXPECTED_FAILURE_CLEANUP PASS\\n'
  exit 0
fi
extract_previous_runtime_server
test ! -e "$FAKE_AUTH_PATH"
COMMENTS_DB="$CANDIDATE_DB" OLD_RUNTIME_SERVER="$OLD_RUNTIME_SERVER" python3 -I - <<'PY'
import importlib.util, os, sys
from pathlib import Path
source = Path(os.environ['OLD_RUNTIME_SERVER'])
sys.path.insert(0, str(source.parent))
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
            environment["FAKE_AUTH_MODE"] = "success"
            result = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True, env=environment)

            # Then: only the host changes; login is private and extraction is digest pinned.
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("LOCAL_OLD_RUNTIME_EXECUTION PASS", result.stdout)
            self.assertRegex(result.stdout, r"sha=[0-9a-f]{64}")
            self.assertNotIn(environment["FAKE_AUTH_CONTENT"], result.stdout + result.stderr)
            self.assertNotIn(
                environment["FAKE_AUTH_CONTENT"],
                (root / "oc-args").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (root / "oc-args").read_text(encoding="utf-8").splitlines(),
                [
                    "registry", "login", f"--to={root / 'work' / 'registry-auth.json'}",
                    "image", "extract", f"--registry-config={root / 'work' / 'registry-auth.json'}",
                    f"registry.paas.cern.ch/etroc-solder-inspection/etl-hybrid-bbqc@sha256:{'a' * 64}",
                    "--path", f"/app/static/server.py:{root / 'work' / 'previous-runtime'}",
                    "--path", f"/app/static/etroc_reviews.py:{root / 'work' / 'previous-runtime'}",
                    "--path", f"/app/static/etroc_position_reviews.py:{root / 'work' / 'previous-runtime'}",
                ],
            )
            self.assertFalse((root / "work" / "registry-auth.json").exists())
            release_state = script[
                script.index("{\n  declare -p SOURCE_REVISION") : script.index("} > \"$RELEASE_STATE\"")
            ]
            self.assertNotIn("registry-auth.json", release_state)

            # Then: unsafe auth files and image extraction failures clean up at the boundary.
            environment["FAKE_EXPECT_FAILURE"] = "1"
            for auth_mode in ("symlink", "world_readable", "empty", "hardlink"):
                shutil.rmtree(root / "work")
                environment["FAKE_AUTH_MODE"] = auth_mode
                environment["FAKE_OC_MODE"] = "success"
                failed = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True, env=environment)
                self.assertEqual(failed.returncode, 0, failed.stderr)
                self.assertIn("EXPECTED_FAILURE_CLEANUP PASS", failed.stdout)

            for mode in ("failure", "symlink", "extra", "empty", "malformed"):
                shutil.rmtree(root / "work")
                environment["FAKE_AUTH_MODE"] = "success"
                environment["FAKE_OC_MODE"] = mode
                failed = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True, env=environment)
                self.assertEqual(failed.returncode, 0, failed.stderr)
                self.assertIn("EXPECTED_FAILURE_CLEANUP PASS", failed.stdout)

            # Then: an untrusted internal reference cannot initiate login or extraction.
            for image in (
                f"image-registry.openshift-image-registry.svc:5000/other/etl-hybrid-bbqc@sha256:{'a' * 64}",
                f"image-registry.openshift-image-registry.svc:5000/etroc-solder-inspection/other@sha256:{'a' * 64}",
                "image-registry.openshift-image-registry.svc:5000/etroc-solder-inspection/etl-hybrid-bbqc:latest",
                f"image-registry.openshift-image-registry.svc:5000/etroc-solder-inspection/etl-hybrid-bbqc@sha256:{'A' * 64}",
                f"image-registry.openshift-image-registry.svc:5000/etroc-solder-inspection/etl-hybrid-bbqc@sha256:{'a' * 63}",
                "registry.example/etroc-solder-inspection/etl-hybrid-bbqc@sha256:" + "a" * 64,
            ):
                shutil.rmtree(root / "work")
                environment["TEST_OLD_WEB_IMAGE"] = image
                environment["FAKE_AUTH_MODE"] = "success"
                environment["FAKE_OC_MODE"] = "success"
                failed = subprocess.run(["bash", "-c", harness], check=False, capture_output=True, text=True, env=environment)
                self.assertEqual(failed.returncode, 0, failed.stderr)
                self.assertEqual((root / "oc-args").read_text(encoding="utf-8"), "")

    def test_legacy_compatibility_is_local_and_never_copies_a_candidate_db_to_production(self):
        # Given: the candidate DB has been migrated locally from the copied backup.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: the old runtime compatibility gate is assembled.

        # Then: it uses only the extracted absolute source and the immutable candidate overlay,
        # never a production candidate DB path.
        self.assertIn(
            'COMMENTS_DB="$CANDIDATE_DB" OLD_RUNTIME_SERVER="$OLD_RUNTIME_SERVER" CANDIDATE_STATIC_ROOT="${BUILD_CONTEXT}/overlay" "$CANDIDATE_HOST_PYTHON" -I',
            script,
        )
        self.assertIn("source = Path(os.environ['OLD_RUNTIME_SERVER'])", script)
        self.assertIn("candidate_static_root = Path(os.environ['CANDIDATE_STATIC_ROOT'])", script)
        compatibility = script[
            script.index('COMMENTS_DB="$CANDIDATE_DB" OLD_RUNTIME_SERVER="$OLD_RUNTIME_SERVER"') :
            script.index("CANDIDATE_LEGACY_COMMENTS_COMPAT PASS")
        ]
        self.assertIn("server.ROOT = candidate_static_root", compatibility)
        self.assertIn("server.init_db(static_root=candidate_static_root)", compatibility)
        self.assertNotIn("server.init_db()", compatibility)
        self.assertLess(
            compatibility.index("server.ROOT = candidate_static_root"),
            compatibility.index("server.init_db(static_root=candidate_static_root)"),
        )
        self.assertNotIn("source = Path('/app/static/server.py')", script)
        self.assertNotIn("CANDIDATE_REMOTE_DB", script)
        self.assertNotIn("cleanup_production_candidate_db", script)
        self.assertNotRegex(script, re.compile(r'oc -n "\$PROJECT" cp "\$CANDIDATE_DB" "\$POD:'))
        self.assertNotRegex(script, re.compile(r'oc -n "\$PROJECT" exec(?: -i)? "\$POD" -c web -- env COMMENTS_DB='))

    def test_authenticated_browser_qa_is_explicitly_deferred(self):
        # Given: helper completion must not require a human browser session.
        script = SCRIPT.read_text(encoding="utf-8")

        # When: post-rollout external SSO handling is reached.

        # Then: the marker precedes the commit boundary instead of blocking it.
        marker = script.index("AUTHENTICATED_BROWSER_QA PENDING")
        committed = script.index("FORWARD_RELEASE_COMMITTED after mandatory read-only post-rollout gates")
        self.assertLess(marker, committed)

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
        topology_mode = "legacy"
        for failure in ("deployment-rollback.json", "service-rollback.json"):
            with self.subTest(topology_mode=topology_mode, failure=failure), tempfile.TemporaryDirectory() as directory:
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
OLD_WEB_IMAGE=web
    OLD_TOPOLOGY_MODE={topology_mode}
    verify_context() {{ :; }}
    validate_manifest_topology() {{ test "$5" = "$OLD_TOPOLOGY_MODE"; }}
    validate_oauth2_proxy_topology() {{ test "$3" = "$OLD_TOPOLOGY_MODE"; }}
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
