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
WEB_BUDGET_BYTES = 180 * 1024 * 1024
POSITION_GEOMETRY_VERSION = "etroc-grid-16x16-v1"
POSITION_CATEGORIES = frozenset({"GREEN", "BLUE", "YELLOW", "RED", "NEED_INSPECT"})
GRID_ROWS = 16
GRID_COLUMNS = 16
TILE_WIDTH = 150
IMAGE_HEIGHT = 120
LABEL_HEIGHT = 16
TILE_HEIGHT = IMAGE_HEIGHT + LABEL_HEIGHT
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


def validate_position_results(
    position_path: Path,
    summaries: dict[str, dict[str, str]],
    source_root: Path,
) -> tuple[int, dict[str, list[dict[str, object]]]]:
    positions: dict[str, set[int]] = defaultdict(set)
    source_images: dict[str, set[str]] = defaultdict(set)
    category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    rows_by_serial: dict[str, list[dict[str, object]]] = defaultdict(list)
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
            grid_row, grid_column = divmod(position, GRID_COLUMNS)
            if int(row["row"]) != grid_row or int(row["col"]) != grid_column:
                raise ValueError(f"position grid mismatch: {serial} position {position}")
            category = row["category"]
            if category not in POSITION_CATEGORIES:
                raise ValueError(f"invalid position category: {serial} position {position}")
            if not row["reason"]:
                raise ValueError(f"missing position reason: {serial} position {position}")
            source_image = row["source_image_relpath"]
            source_parts = Path(source_image)
            if not source_image or source_parts.is_absolute() or ".." in source_parts.parts or source_image in source_images[serial]:
                raise ValueError(f"missing, unsafe, or duplicate source image: {serial} position {position}")
            source_path = resolve_under(source_root, source_image)
            if not source_path.is_file() or Path(row["image_path"]).resolve() != source_path:
                raise ValueError(f"position source image identity mismatch: {serial} position {position}")
            with Image.open(source_path) as image:
                image.verify()
            with Image.open(source_path) as image:
                if image.width <= 0 or image.height <= 0:
                    raise ValueError(f"invalid source image dimensions: {serial} position {position}")
            try:
                height = float(row["height"])
            except ValueError as exc:
                raise ValueError(f"invalid height: {serial} position {position}") from exc
            if not math.isfinite(height):
                raise ValueError(f"non-finite height: {serial} position {position}")
            positions[serial].add(position)
            source_images[serial].add(source_image)
            category_counts[serial][category] += 1
            rows_by_serial[serial].append({
                "position": position,
                "row": grid_row,
                "column": grid_column,
                "algorithm_category": category,
                "algorithm_reason": row["reason"],
                "source_image_sha256": sha256(source_path),
                "source_path": source_path,
                "review_target": category == "NEED_INSPECT",
            })
    if row_count != 9216:
        raise ValueError(f"expected 9216 position rows, found {row_count}")
    for serial in APPROVED_ETROC_SERIALS:
        if positions[serial] != set(range(256)) or len(source_images[serial]) != 256:
            raise ValueError(f"incomplete position/image join: {serial}")
        summary = summaries[serial]
        expected_counts = {
            "GREEN": int_field(summary, "green_count"),
            "BLUE": int_field(summary, "blue_count"),
            "YELLOW": int_field(summary, "yellow_count"),
            "RED": int_field(summary, "red_count"),
            "NEED_INSPECT": int_field(summary, "need_inspect_count"),
        }
        if category_counts[serial] != Counter(expected_counts):
            raise ValueError(f"position category counts differ from summary: {serial}")
        rows_by_serial[serial].sort(key=lambda item: int(str(item["position"])))
    return row_count, dict(rows_by_serial)


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


def render_clean_montage(position_rows: list[dict[str, object]], destination: Path) -> dict[str, object]:
    if [row["position"] for row in position_rows] != list(range(GRID_ROWS * GRID_COLUMNS)):
        raise ValueError("clean montage position inventory is incomplete")
    canvas = Image.new("RGB", (GRID_COLUMNS * TILE_WIDTH, GRID_ROWS * TILE_HEIGHT), "white")
    for row in position_rows:
        position = int(str(row["position"]))
        grid_row, grid_column = divmod(position, GRID_COLUMNS)
        x = grid_column * TILE_WIDTH
        y = grid_row * TILE_HEIGHT
        with Image.open(Path(str(row["source_path"]))) as opened:
            image = opened.convert("RGB")
            image.thumbnail((TILE_WIDTH, IMAGE_HEIGHT), Image.Resampling.LANCZOS)
            canvas.paste(image, (x, y + LABEL_HEIGHT))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "JPEG", quality=82, optimize=True, progressive=True)
    return {
        "clean_montage_sha256": sha256(destination),
        "clean_montage_size_bytes": destination.stat().st_size,
    }


def position_publication(
    record: dict[str, object],
    position_rows: list[dict[str, object]],
) -> dict[str, object]:
    positions = []
    for row in position_rows:
        position = int(str(row["position"]))
        positions.append({
            "position": position,
            "row": int(str(row["row"])),
            "column": int(str(row["column"])),
            "algorithm_category": row["algorithm_category"],
            "algorithm_reason": row["algorithm_reason"],
            "source_image_sha256": row["source_image_sha256"],
            "review_target": bool(row["review_target"]),
            "cell": {
                "x": (position % GRID_COLUMNS) * TILE_WIDTH,
                "y": (position // GRID_COLUMNS) * TILE_HEIGHT,
                "width": TILE_WIDTH,
                "height": TILE_HEIGHT,
                "image_y": LABEL_HEIGHT,
                "image_height": IMAGE_HEIGHT,
            },
        })
    return {
        "schema_version": "1.0",
        "geometry_version": POSITION_GEOMETRY_VERSION,
        "dataset_id": DATASET_ID,
        "etroc_serial": record["etroc_serial"],
        "acquisition_id": record["acquisition_id"],
        "analysis_run_id": record["analysis_run_id"],
        "labelled_montage_sha256": record["montage_sha256"],
        "clean_montage_sha256": record["clean_montage_sha256"],
        "review_target_count": sum(bool(row["review_target"]) for row in position_rows),
        "positions": positions,
    }


def verify_bundle(output_dir: Path, records: list[dict[str, object]]) -> None:
    expected_files = {"chips.json"}
    total_positions = 0
    total_targets = 0
    for record in records:
        expected_files.add(str(record["montage_uri"]))
        expected_files.add(str(record["preview_uri"]))
        expected_files.add(str(record["clean_montage_uri"]))
        expected_files.add(str(record["position_publication_uri"]))
        for role, size in (("montage", (2400, 2176)), ("preview", (720, 653)), ("clean_montage", (2400, 2176))):
            asset = resolve_under(output_dir, str(record[f"{role}_uri"]))
            if sha256(asset) != record[f"{role}_sha256"] or asset.stat().st_size != record[f"{role}_size_bytes"]:
                raise ValueError(f"generated {role} integrity mismatch: {record['etroc_serial']}")
            with Image.open(asset) as image:
                image.verify()
            with Image.open(asset) as image:
                if image.format != "JPEG" or image.mode != "RGB" or image.size != size or image.info.get("progressive") != 1:
                    raise ValueError(f"generated {role} contract mismatch: {record['etroc_serial']}")
        position_path = resolve_under(output_dir, str(record["position_publication_uri"]))
        if sha256(position_path) != record["position_publication_sha256"]:
            raise ValueError(f"position publication integrity mismatch: {record['etroc_serial']}")
        position_document = json.loads(position_path.read_text(encoding="utf-8"))
        positions = position_document.get("positions")
        if (
            position_document.get("schema_version") != "1.0"
            or position_document.get("geometry_version") != POSITION_GEOMETRY_VERSION
            or position_document.get("dataset_id") != DATASET_ID
            or position_document.get("etroc_serial") != record["etroc_serial"]
            or position_document.get("acquisition_id") != record["acquisition_id"]
            or position_document.get("analysis_run_id") != record["analysis_run_id"]
            or position_document.get("labelled_montage_sha256") != record["montage_sha256"]
            or position_document.get("clean_montage_sha256") != record["clean_montage_sha256"]
            or not isinstance(positions, list)
            or len(positions) != 256
        ):
            raise ValueError(f"position publication contract mismatch: {record['etroc_serial']}")
        target_count = 0
        for expected_position, position in enumerate(positions):
            if (
                position.get("position") != expected_position
                or position.get("row") != expected_position // GRID_COLUMNS
                or position.get("column") != expected_position % GRID_COLUMNS
                or position.get("algorithm_category") not in POSITION_CATEGORIES
                or not isinstance(position.get("algorithm_reason"), str)
                or not position["algorithm_reason"]
                or re.fullmatch(r"[0-9a-f]{64}", str(position.get("source_image_sha256"))) is None
                or position.get("review_target") != (position.get("algorithm_category") == "NEED_INSPECT")
            ):
                raise ValueError(f"position record contract mismatch: {record['etroc_serial']} position {expected_position}")
            target_count += int(position["review_target"])
        if target_count != record["position_review_target_count"] or target_count != position_document.get("review_target_count"):
            raise ValueError(f"position review target count mismatch: {record['etroc_serial']}")
        total_positions += len(positions)
        total_targets += target_count
    if total_positions != 9216 or total_targets != 82:
        raise ValueError("generated position publication aggregate mismatch")
    actual = {path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.is_file()}
    if actual != expected_files:
        raise ValueError(f"unexpected generated files: {sorted(actual ^ expected_files)}")
    if sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file()) >= WEB_BUDGET_BYTES:
        raise ValueError("generated ETROC web bundle exceeds 180 MiB budget")


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
    source_root = (complete_manifest_path.parent.parent / "analysis_ready").resolve()
    if (
        complete_manifest.get("source_complete_png_count") != 9216
        or complete_manifest.get("analysis_ready", {}).get("image_count") != 9216
        or not source_root.is_dir()
    ):
        raise ValueError("complete manifest does not identify the exact analysis-ready source image root")
    position_count, positions_by_serial = validate_position_results(position_path, summaries, source_root)
    sources = validate_source_montages(analysis_dir, rows)

    destination = app_dir / "data" / "etroc-optical" / DATASET_ID
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{DATASET_ID}.staged-", dir=destination.parent))
    try:
        records = []
        for row in sorted(rows, key=lambda item: (item["wafer"], int(item["chip"]))):
            serial = row["etroc_serial"]
            source_revision = row["acquisition_id"].rsplit(":", 1)[-1]
            staged_montage_path = resolve_under(staged, f"montages/{serial}.jpg")
            preview_uri = f"previews/{serial}.jpg"
            staged_montage_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path = resolve_under(staged, preview_uri)
            assets = render_jpegs(sources[serial], staged_montage_path, preview_path)
            montage_uri = f"montages/sha256/{assets['montage_sha256']}.jpg"
            full_path = resolve_under(staged, montage_uri)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged_montage_path, full_path)
            staged_montage_path.unlink()
            position_rows = positions_by_serial[serial]
            staged_clean_path = resolve_under(staged, f"clean-montages/{serial}.jpg")
            clean_assets = render_clean_montage(position_rows, staged_clean_path)
            clean_montage_uri = f"clean-montages/sha256/{clean_assets['clean_montage_sha256']}.jpg"
            clean_path = resolve_under(staged, clean_montage_uri)
            clean_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged_clean_path, clean_path)
            staged_clean_path.unlink()
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
                "clean_montage_uri": clean_montage_uri,
                "position_geometry_version": POSITION_GEOMETRY_VERSION,
                "position_review_target_count": sum(bool(item["review_target"]) for item in position_rows),
                **assets,
                **clean_assets,
            }
            position_document = position_publication(record, position_rows)
            position_bytes = (json.dumps(position_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
            position_sha256 = hashlib.sha256(position_bytes).hexdigest()
            position_uri = f"positions/sha256/{position_sha256}.json"
            position_path_output = resolve_under(staged, position_uri)
            position_path_output.parent.mkdir(parents=True, exist_ok=True)
            position_path_output.write_bytes(position_bytes)
            record["position_publication_uri"] = position_uri
            record["position_publication_sha256"] = position_sha256
            records.append(record)

        payload = {
            "schema_version": "1.0",
            "dataset_id": DATASET_ID,
            "title": "ETROC_OI_2608 pre-bonding optical inspection",
            "publication_status": "exploratory_review_pending",
            "interpretation": "Algorithmic screening candidates; not confirmed QC dispositions.",
            "expected_positions_per_chip": 256,
            "position_geometry_version": POSITION_GEOMETRY_VERSION,
            "position_record_count": position_count,
            "position_review_target_count": sum(int(record["position_review_target_count"]) for record in records),
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
