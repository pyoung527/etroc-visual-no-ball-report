#!/usr/bin/env python3
"""Fail-closed BuildConfig-to-Build provenance validator for BBQC releases."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, NoReturn


DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PROTECTED_METADATA = (
    "name",
    "namespace",
    "labels",
    "annotations",
    "finalizers",
    "ownerReferences",
)


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def load_object(path: Path, expected_kind: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read {expected_kind} JSON {path}: {exc}")
    if not isinstance(value, dict) or value.get("kind") != expected_kind:
        fail(f"expected {expected_kind} object in {path}")
    return value


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    return value


def require_int(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        fail(f"{label} must be an integer >= {minimum}")
    return value


def compact(value: Any) -> Any:
    """Normalize API-defaulted empty containers without hiding non-empty drift."""
    if isinstance(value, dict):
        result = {key: compact(item) for key, item in value.items()}
        return {key: item for key, item in result.items() if item not in ({}, [], None)}
    if isinstance(value, list):
        return [compact(item) for item in value]
    return value


def validate(
    captured: dict[str, Any],
    current: dict[str, Any],
    build: dict[str, Any],
    *,
    expected_name: str,
    expected_namespace: str,
) -> tuple[int, int, str]:
    captured_metadata = require_mapping(captured.get("metadata"), "captured BuildConfig metadata")
    current_metadata = require_mapping(current.get("metadata"), "current BuildConfig metadata")
    build_metadata = require_mapping(build.get("metadata"), "Build metadata")

    for label, metadata in (
        ("captured BuildConfig", captured_metadata),
        ("current BuildConfig", current_metadata),
        ("Build", build_metadata),
    ):
        if metadata.get("name") is None or metadata.get("namespace") is None:
            fail(f"{label} identity is incomplete")
        if metadata.get("deletionTimestamp") is not None:
            fail(f"{label} is being deleted")

    if (
        captured_metadata.get("name") != expected_name
        or captured_metadata.get("namespace") != expected_namespace
    ):
        fail("captured BuildConfig target identity changed")
    if (
        current_metadata.get("name") != expected_name
        or current_metadata.get("namespace") != expected_namespace
    ):
        fail("current BuildConfig target identity changed")
    if build_metadata.get("namespace") != expected_namespace:
        fail("Build namespace changed")

    captured_uid = captured_metadata.get("uid")
    if not isinstance(captured_uid, str) or not captured_uid:
        fail("captured BuildConfig UID is missing")
    if current_metadata.get("uid") != captured_uid:
        fail("captured BuildConfig UID changed")

    captured_spec = require_mapping(captured.get("spec"), "captured BuildConfig spec")
    current_spec = require_mapping(current.get("spec"), "current BuildConfig spec")
    if current_spec != captured_spec:
        fail("captured BuildConfig spec changed")
    if any(
        current_metadata.get(key) != captured_metadata.get(key)
        for key in PROTECTED_METADATA
    ):
        fail("captured BuildConfig protected metadata changed")

    captured_generation = require_int(
        captured_metadata.get("generation"), "captured BuildConfig generation", 1
    )
    current_generation = require_int(
        current_metadata.get("generation"), "current BuildConfig generation", 1
    )
    if current_generation != captured_generation + 1:
        fail(
            "BuildConfig generation continuity failed: "
            f"captured={captured_generation} current={current_generation}"
        )

    captured_status = require_mapping(captured.get("status", {}), "captured BuildConfig status")
    current_status = require_mapping(current.get("status", {}), "current BuildConfig status")
    captured_last_version = require_int(
        captured_status.get("lastVersion", 0), "captured BuildConfig lastVersion"
    )
    current_last_version = require_int(
        current_status.get("lastVersion"), "current BuildConfig lastVersion"
    )
    if current_last_version != captured_last_version + 1:
        fail(
            "BuildConfig lastVersion continuity failed: "
            f"captured={captured_last_version} current={current_last_version}"
        )

    annotations = require_mapping(build_metadata.get("annotations", {}), "Build annotations")
    if annotations.get("openshift.io/build-config.name") != expected_name:
        fail("Build config-name annotation changed")
    raw_build_number = annotations.get("openshift.io/build.number")
    if not isinstance(raw_build_number, str) or not raw_build_number.isdecimal():
        fail("Build number annotation is invalid")
    build_number = int(raw_build_number)
    if build_number != current_last_version:
        fail(
            f"Build number continuity failed: build={build_number} "
            f"current_lastVersion={current_last_version}"
        )
    if build_metadata.get("name") != f"{expected_name}-{build_number}":
        fail("Build name does not match its build number")

    owner_references = build_metadata.get("ownerReferences", [])
    if not isinstance(owner_references, list):
        fail("Build ownerReferences must be an array")
    buildconfig_owners = [
        owner
        for owner in owner_references
        if isinstance(owner, dict) and owner.get("kind") == "BuildConfig"
    ]
    if len(buildconfig_owners) != 1:
        fail("Build must have exactly one BuildConfig owner")
    owner = buildconfig_owners[0]
    if (
        owner.get("name") != expected_name
        or owner.get("uid") != captured_uid
        or owner.get("controller") is not True
    ):
        fail("Build owner does not match captured BuildConfig")

    build_spec = require_mapping(build.get("spec"), "Build spec")
    for key, label in (
        ("source", "Build source"),
        ("strategy", "Build strategy"),
        ("output", "Build output"),
    ):
        if compact(build_spec.get(key)) != compact(captured_spec.get(key)):
            fail(f"{label} differs from captured BuildConfig")

    build_status = require_mapping(build.get("status"), "Build status")
    if build_status.get("phase") != "Complete":
        fail(f"Build phase is not Complete: {build_status.get('phase')!r}")
    status_output = require_mapping(build_status.get("output"), "Build status output")
    status_to = require_mapping(status_output.get("to"), "Build status output.to")
    digest = status_to.get("imageDigest")
    if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        fail("Build output image digest is invalid")

    return current_generation, build_number, digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captured", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--namespace", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    captured = load_object(args.captured, "BuildConfig")
    current = load_object(args.current, "BuildConfig")
    build = load_object(args.build, "Build")
    generation, build_number, digest = validate(
        captured,
        current,
        build,
        expected_name=args.name,
        expected_namespace=args.namespace,
    )
    print(
        "BUILD_PROVENANCE PASS "
        f"generation={generation} build_number={build_number} digest={digest}"
    )


if __name__ == "__main__":
    main()
