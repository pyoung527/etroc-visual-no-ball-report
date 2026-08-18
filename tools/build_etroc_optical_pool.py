#!/usr/bin/env python3
"""Build a compact, immutable ETROC optical montage pool for BBQC."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import PIL
from PIL import Image, features

EXPECTED_WAFER_COUNTS = {"W02G4": 18, "W03F7": 9, "W05E5": 9}
APPROVED_ETROC_SERIALS = frozenset(
    {
        "W02G4-44", "W02G4-45", "W02G4-49", "W02G4-50", "W02G4-51", "W02G4-55",
        "W02G4-60", "W02G4-63", "W02G4-64", "W02G4-66", "W02G4-67", "W02G4-68",
        "W02G4-70", "W02G4-78", "W02G4-79", "W02G4-80", "W02G4-81", "W02G4-82",
        "W03F7-75", "W03F7-76", "W03F7-77", "W03F7-78", "W03F7-79", "W03F7-80",
        "W03F7-81", "W03F7-83", "W03F7-85",
        "W05E5-24", "W05E5-30", "W05E5-36", "W05E5-38", "W05E5-39", "W05E5-41",
        "W05E5-64", "W05E5-68", "W05E5-75",
    }
)
DATASET_ID = "ETROC_OI_2608"
WEB_BUDGET_BYTES = 90 * 1024 * 1024
SERIAL_RE = re.compile(r"^(W02G4|W03F7|W05E5)-([0-9]+)$")
COUNT_FIELDS = (
    "green_count", "blue_count", "yellow_count", "red_count", "need_inspect_count",
    "review_candidate_count", "optical_no_ball_count",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def int_field(row: dict[str, str], name: str) -> int:
    value = int(row[name])
    if value < 0:
        raise ValueError(f"negative {name}: {value}")
    return value


def resolve_under(root: Path, relative_path: str) -> Path:
    if not relative_path:
        raise ValueError("empty relative source path")
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError(f"absolute source path is forbidden: {relative_path}")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"source path escapes root: {relative_path}") from exc
    return candidate


def validate_summary_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    if len(rows) != 36:
        raise ValueError(f"expected 36 chip rows, found {len(rows)}")
    serials = {row["etroc_serial"] for row in rows}
    if serials != APPROVED_ETROC_SERIALS:
        raise ValueError(f"ETROC inventory differs from approved 36-serial allowlist: {sorted(serials ^ APPROVED_ETROC_SERIALS)}")
    if Counter(row["wafer"] for row in rows) != Counter(EXPECTED_WAFER_COUNTS):
        raise ValueError("unexpected wafer counts")

    by_serial: dict[str, dict[str, str]] = {}
    montage_paths: set[str] = set()
    for row in rows:
        serial = row["etroc_serial"]
        match = SERIAL_RE.fullmatch(serial)
        if not match or match.group(1) != row["wafer"] or match.group(2) != row["chip"]:
            raise ValueError(f"inconsistent ETROC identity: {serial}, {row['wafer']}, {row['chip']}")
        if row["dataset_id"] != "ETROC_OI_2608_complete" or row["publication_status"] != "exploratory_review_pending":
            raise ValueError(f"unexpected source dataset status: {serial}")
        if any(int_field(row, field) != 256 for field in ("position_count", "image_count", "height_count")):
            raise ValueError(f"incomplete chip: {serial}")
        if row["etl_etroc_id"] or row["hybrid_registry_id"]:
            raise ValueError(f"unexpected bonded identity: {serial}")
        expected_lineage = "supplement-re" if serial in {"W02G4-51", "W05E5-24"} else "base"
        if row["acquisition_id"] != f"ETROC_OI_2608:{expected_lineage}":
            raise ValueError(f"unexpected acquisition lineage: {serial}")
        counts = {field: int_field(row, field) for field in COUNT_FIELDS}
        if sum(counts[field] for field in ("green_count", "blue_count", "yellow_count", "red_count", "need_inspect_count")) != 256:
            raise ValueError(f"category partition does not total 256: {serial}")
        if counts["optical_no_ball_count"] > counts["red_count"]:
            raise ValueError(f"optical no-ball count exceeds red candidates: {serial}")
        montage = row["montage_overlay_relpath"]
        if montage in montage_paths:
            raise ValueError(f"duplicate source montage path: {montage}")
        montage_paths.add(montage)
        by_serial[serial] = row
    return by_serial


def validate_position_results(position_path: Path, summaries: dict[str, dict[str, str]]) -> int:
    positions: dict[str, set[int]] = defaultdict(set)
    source_images: dict[str, set[str]] = defaultdict(set)
    row_count = 0
    with position_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row_count += 1
            serial = row["etroc_serial"]
            if serial not in summaries:
                raise ValueError(f"position row has unapproved ETROC: {serial}")
            summary = summaries[serial]
            if row["wafer"] != summary["wafer"] or row["chip"] != summary["chip"]:
                raise ValueError(f"position identity mismatch: {serial}")
            if row["acquisition_id"] != summary["acquisition_id"]:
                raise ValueError(f"position acquisition mismatch: {serial}")
            if row["publication_status"] != "exploratory_review_pending":
                raise ValueError(f"position publication status mismatch: {serial}")
            position = int(row["position"])
            if position not in range(256) or position in positions[serial]:
                raise ValueError(f"invalid or duplicate position {position}: {serial}")
            source_image = row["source_image_relpath"]
            source_parts = Path(source_image)
            if not source_image or source_parts.is_absolute() or ".." in source_parts.parts or source_image in source_images[serial]:
                raise ValueError(f"missing, unsafe, or duplicate source image: {serial} position {position}")
            try:
                height = float(row["height"])
            except ValueError as exc:
                raise ValueError(f"invalid height: {serial} position {position}") from exc
            if not math.isfinite(height):
                raise ValueError(f"non-finite height: {serial} position {position}")
            positions[serial].add(position)
            source_images[serial].add(source_image)
    if row_count != 9216:
        raise ValueError(f"expected 9216 position rows, found {row_count}")
    for serial in APPROVED_ETROC_SERIALS:
        if positions[serial] != set(range(256)) or len(source_images[serial]) != 256:
            raise ValueError(f"incomplete position/image join: {serial}")
    return row_count


def validate_source_montages(analysis_dir: Path, rows: list[dict[str, str]]) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for row in rows:
        serial = row["etroc_serial"]
        source = resolve_under(analysis_dir, row["montage_overlay_relpath"])
        if not source.is_file():
            raise FileNotFoundError(f"missing source montage: {source}")
        with Image.open(source) as image:
            image.verify()
        with Image.open(source) as image:
            if image.size != (2400, 2176):
                raise ValueError(f"unexpected montage dimensions for {serial}: {image.size}")
        sources[serial] = source
    return sources


def render_jpegs(source: Path, full_path: Path, preview_path: Path) -> dict[str, object]:
    full_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        source_width, source_height = image.size
        image.save(full_path, "JPEG", quality=82, optimize=True, progressive=True)
        preview = image.copy()
        preview.thumbnail((720, 720), Image.Resampling.LANCZOS)
        preview.save(preview_path, "JPEG", quality=82, optimize=True, progressive=True)
    return {
        "source_montage_sha256": sha256(source),
        "source_montage_size_bytes": source.stat().st_size,
        "source_width_px": source_width,
        "source_height_px": source_height,
        "montage_sha256": sha256(full_path),
        "montage_size_bytes": full_path.stat().st_size,
        "preview_sha256": sha256(preview_path),
        "preview_size_bytes": preview_path.stat().st_size,
    }


def verify_bundle(output_dir: Path, records: list[dict[str, object]]) -> None:
    expected_files = {"chips.json"}
    for record in records:
        expected_files.add(str(record["montage_uri"]))
        expected_files.add(str(record["preview_uri"]))
        for role, size in (("montage", (2400, 2176)), ("preview", (720, 653))):
            asset = resolve_under(output_dir, str(record[f"{role}_uri"]))
            if sha256(asset) != record[f"{role}_sha256"] or asset.stat().st_size != record[f"{role}_size_bytes"]:
                raise ValueError(f"generated {role} integrity mismatch: {record['etroc_serial']}")
            with Image.open(asset) as image:
                image.verify()
            with Image.open(asset) as image:
                if image.format != "JPEG" or image.mode != "RGB" or image.size != size:
                    raise ValueError(f"generated {role} contract mismatch: {record['etroc_serial']}")
    actual = {path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.is_file()}
    if actual != expected_files:
        raise ValueError(f"unexpected generated files: {sorted(actual ^ expected_files)}")
    if sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file()) >= WEB_BUDGET_BYTES:
        raise ValueError("generated ETROC web bundle exceeds 90 MiB budget")


def atomic_replace_directory(staged: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.previous")
    if backup.exists():
        shutil.rmtree(backup)
    had_destination = destination.exists()
    if had_destination:
        os.replace(destination, backup)
    try:
        os.replace(staged, destination)
    except BaseException:
        if had_destination and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def build_pool(analysis_dir: Path, app_dir: Path, complete_manifest_path: Path) -> dict[str, object]:
    summary_path = analysis_dir / "bbqc_chip_summary_exploratory.csv"
    position_path = analysis_dir / "bbqc_position_results_exploratory.csv"
    provenance_path = analysis_dir / "provenance.json"
    with summary_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    complete_manifest = json.loads(complete_manifest_path.read_text(encoding="utf-8"))
    if sha256(complete_manifest_path) != provenance["source_complete_manifest_sha256"]:
        raise ValueError("complete source manifest checksum does not match analysis provenance")
    if provenance["status"] != "exploratory_common_baseline_not_publication_ready":
        raise ValueError("unexpected analysis provenance status")
    summaries = validate_summary_rows(rows)
    position_count = validate_position_results(position_path, summaries)
    sources = validate_source_montages(analysis_dir, rows)

    destination = app_dir / "data" / "etroc-optical" / DATASET_ID
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{DATASET_ID}.staged-", dir=destination.parent))
    try:
        records = []
        for row in sorted(rows, key=lambda item: (item["wafer"], int(item["chip"]))):
            serial = row["etroc_serial"]
            montage_uri = f"montages/{serial}.jpg"
            preview_uri = f"previews/{serial}.jpg"
            full_path = resolve_under(staged, montage_uri)
            preview_path = resolve_under(staged, preview_uri)
            assets = render_jpegs(sources[serial], full_path, preview_path)
            source_revision = row["acquisition_id"].rsplit(":", 1)[-1]
            record = {
                "etroc_serial": serial,
                "wafer": row["wafer"],
                "chip": row["chip"],
                "acquisition_id": f"{DATASET_ID}:{serial}:{source_revision}",
                "source_revision": source_revision,
                "analysis_run_id": f"{DATASET_ID}:common-baseline-v0:{row['analysis_batch']}",
                "analysis_batch": row["analysis_batch"],
                "publication_status": "exploratory_review_pending",
                "review_state": "not_reviewed",
                "position_count": int_field(row, "position_count"),
                "image_count": int_field(row, "image_count"),
                "height_count": int_field(row, "height_count"),
                "height_unit": row["height_unit"],
                "green_count": int_field(row, "green_count"),
                "blue_count": int_field(row, "blue_count"),
                "yellow_count": int_field(row, "yellow_count"),
                "red_candidate_count": int_field(row, "red_count"),
                "needs_inspection_count": int_field(row, "need_inspect_count"),
                "review_candidate_count": int_field(row, "review_candidate_count"),
                "optical_no_ball_candidate_count": int_field(row, "optical_no_ball_count"),
                "montage_uri": montage_uri,
                "preview_uri": preview_uri,
                **assets,
            }
            records.append(record)

        payload = {
            "schema_version": "1.0",
            "dataset_id": DATASET_ID,
            "title": "ETROC_OI_2608 pre-bonding optical inspection",
            "publication_status": "exploratory_review_pending",
            "interpretation": "Algorithmic screening candidates; not confirmed QC dispositions.",
            "expected_positions_per_chip": 256,
            "position_record_count": position_count,
            "position_results_sha256": sha256(position_path),
            "record_count": len(records),
            "wafer_counts": EXPECTED_WAFER_COUNTS,
            "analysis_created_at_utc": provenance["created_at_utc"],
            "analysis_config_sha256": provenance["config_sha256"],
            "analysis_config_scope_note": provenance["config_scope_note"],
            "pipeline_files_sha256": provenance["pipeline_files_sha256"],
            "source_complete_manifest_sha256": provenance["source_complete_manifest_sha256"],
            "base_archive_sha256": complete_manifest["base_archive_sha256"],
            "supplement_archive_sha256": complete_manifest["supplement_sha256"],
            "replacement_policy": complete_manifest["replacement_policy"],
            "encoder": {"pillow": PIL.__version__, "libjpeg": features.version_codec("jpg")},
            "records": records,
        }
        (staged / "chips.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        verify_bundle(staged, records)
        checksum_paths = sorted(path for path in staged.rglob("*") if path.is_file())
        (staged / "SHA256SUMS").write_text(
            "".join(f"{sha256(path)}  {path.relative_to(staged).as_posix()}\n" for path in checksum_paths),
            encoding="utf-8",
        )
        if sum(path.stat().st_size for path in staged.rglob("*") if path.is_file()) >= WEB_BUDGET_BYTES:
            raise ValueError("generated ETROC web bundle exceeds 90 MiB budget")
        atomic_replace_directory(staged, destination)
    except BaseException:
        if staged.exists():
            shutil.rmtree(staged)
        raise
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--complete-manifest", type=Path, required=True)
    parser.add_argument("--app-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = build_pool(args.analysis_dir.resolve(), args.app_dir.resolve(), args.complete_manifest.resolve())
    print(json.dumps({"dataset_id": payload["dataset_id"], "records": payload["record_count"]}))


if __name__ == "__main__":
    main()
