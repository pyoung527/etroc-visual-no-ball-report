from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "hybrid-bbqc" / "openshift" / "validate_build_provenance.py"


def buildconfig(*, generation: int = 7, last_version: int = 30) -> dict:
    return {
        "apiVersion": "build.openshift.io/v1",
        "kind": "BuildConfig",
        "metadata": {
            "name": "etl-hybrid-bbqc",
            "namespace": "etroc-solder-inspection",
            "uid": "bc-uid-1",
            "resourceVersion": "100",
            "generation": generation,
            "labels": {"app": "etl-hybrid-bbqc"},
            "annotations": {"owner": "bbqc"},
            "finalizers": [],
            "ownerReferences": [],
        },
        "spec": {
            "runPolicy": "Serial",
            "source": {"type": "Binary"},
            "strategy": {
                "type": "Docker",
                "dockerStrategy": {"dockerfilePath": "hybrid-bbqc/Containerfile"},
            },
            "output": {
                "to": {"kind": "ImageStreamTag", "name": "etl-hybrid-bbqc:latest"}
            },
        },
        "status": {"lastVersion": last_version},
    }


def completed_build(captured: dict, *, build_number: int = 31) -> dict:
    return {
        "apiVersion": "build.openshift.io/v1",
        "kind": "Build",
        "metadata": {
            "name": f"etl-hybrid-bbqc-{build_number}",
            "namespace": "etroc-solder-inspection",
            "uid": "build-uid-31",
            "annotations": {
                "openshift.io/build-config.name": "etl-hybrid-bbqc",
                "openshift.io/build.number": str(build_number),
            },
            "ownerReferences": [
                {
                    "apiVersion": "build.openshift.io/v1",
                    "kind": "BuildConfig",
                    "name": "etl-hybrid-bbqc",
                    "uid": "bc-uid-1",
                    "controller": True,
                }
            ],
        },
        "spec": {
            "source": deepcopy(captured["spec"]["source"]),
            "strategy": deepcopy(captured["spec"]["strategy"]),
            "output": {
                **deepcopy(captured["spec"]["output"]),
                "pushSecret": {"name": "builder-dockercfg-example"},
            },
        },
        "status": {
            "phase": "Complete",
            "output": {"to": {"imageDigest": "sha256:" + "a" * 64}},
        },
    }


class BuildProvenanceValidatorTests(unittest.TestCase):
    def run_validator(self, captured: dict, current: dict, build: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = {}
            for name, payload in (("captured", captured), ("current", current), ("build", build)):
                path = tmp_path / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths[name] = path
            return subprocess.run(
                [
                    "python3",
                    "-I",
                    str(VALIDATOR),
                    "--captured",
                    str(paths["captured"]),
                    "--current",
                    str(paths["current"]),
                    "--build",
                    str(paths["build"]),
                    "--name",
                    "etl-hybrid-bbqc",
                    "--namespace",
                    "etroc-solder-inspection",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

    def valid_documents(self) -> tuple[dict, dict, dict]:
        captured = buildconfig()
        current = buildconfig(generation=8, last_version=31)
        current["metadata"]["resourceVersion"] = "120"
        return captured, current, completed_build(captured)

    def test_accepts_exact_single_build_continuity(self):
        captured, current, build = self.valid_documents()
        result = self.run_validator(captured, current, build)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BUILD_PROVENANCE PASS", result.stdout)

    def test_rejects_transient_spec_change_restored_after_build(self):
        captured, current, build = self.valid_documents()
        current["metadata"]["generation"] = 9
        result = self.run_validator(captured, current, build)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("generation continuity", result.stderr)

    def test_rejects_concurrent_extra_build(self):
        captured, current, build = self.valid_documents()
        current["status"]["lastVersion"] = 32
        result = self.run_validator(captured, current, build)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lastVersion continuity", result.stderr)

    def test_rejects_build_number_or_spec_drift(self):
        for mutation, message in (
            (lambda _c, b: b["metadata"]["annotations"].__setitem__("openshift.io/build.number", "32"), "build number"),
            (lambda _c, b: b["spec"]["source"].__setitem__("type", "Git"), "Build source"),
            (lambda _c, b: b["spec"]["output"]["to"].__setitem__("name", "other:latest"), "Build output"),
            (lambda _c, b: b["spec"]["output"].__setitem__("other", {}), "unexpected fields"),
        ):
            with self.subTest(message=message):
                captured, current, build = self.valid_documents()
                mutation(current, build)
                result = self.run_validator(captured, current, build)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message.lower(), result.stderr.lower())

    def test_rejects_identity_metadata_owner_and_deletion_drift(self):
        mutations = (
            (lambda c, _b: c["metadata"]["labels"].__setitem__("owner", "other"), "metadata changed"),
            (lambda c, _b: c["metadata"].__setitem__("uid", "bc-uid-2"), "UID changed"),
            (lambda _c, b: b["metadata"]["ownerReferences"][0].__setitem__("uid", "bc-uid-2"), "owner"),
            (lambda c, _b: c["metadata"].__setitem__("deletionTimestamp", "2026-08-11T00:00:00Z"), "being deleted"),
            (lambda _c, b: b["metadata"].__setitem__("deletionTimestamp", "2026-08-11T00:00:00Z"), "being deleted"),
        )
        for mutation, message in mutations:
            with self.subTest(message=message):
                captured, current, build = self.valid_documents()
                mutation(current, build)
                result = self.run_validator(captured, current, build)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message.lower(), result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
