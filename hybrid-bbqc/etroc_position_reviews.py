from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Final, Mapping


DATASET_ID: Final = "ETROC_OI_2608"
GEOMETRY_VERSION: Final = "etroc-grid-16x16-v1"
HUMAN_LABELS: Final = frozenset({"GREEN", "BLUE", "YELLOW", "RED"})
POSITION_CATEGORIES: Final = frozenset({"GREEN", "BLUE", "YELLOW", "RED", "NEED_INSPECT"})
POSITION_KEY_FIELDS: Final = (
    "dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id",
    "labelled_montage_sha256", "clean_montage_sha256", "position_publication_sha256", "position",
    "source_image_sha256", "geometry_version",
)
EVENT_FIELDS: Final = (
    "event_id", *POSITION_KEY_FIELDS, "label", "note", "author", "author_display",
    "created_at", "mutation_id", "supersedes_event_id",
)
REQUEST_FIELDS: Final = frozenset((*POSITION_KEY_FIELDS, "label", "note", "expected_current_event_id", "mutation_id"))
CHECKSUM_LINE: Final = re.compile(r"([0-9a-f]{64})  ([^\s]+)")
V1_DDL: Final = (
    "CREATE TABLE position_review_schema (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), version INTEGER NOT NULL CHECK (version = 1), applied_at INTEGER NOT NULL) WITHOUT ROWID",
    "CREATE TABLE position_review_events (id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id TEXT NOT NULL, etroc_serial TEXT NOT NULL, acquisition_id TEXT NOT NULL, analysis_run_id TEXT NOT NULL, labelled_montage_sha256 TEXT NOT NULL, clean_montage_sha256 TEXT NOT NULL, position_publication_sha256 TEXT NOT NULL, position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 255), source_image_sha256 TEXT NOT NULL, geometry_version TEXT NOT NULL CHECK (geometry_version = 'etroc-grid-16x16-v1'), state TEXT NOT NULL CHECK (state IN ('reviewed_no_optical_concern', 'reviewed_concern_observed', 'follow_up_required')), note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 2000 AND (state = 'reviewed_no_optical_concern' OR length(trim(note)) > 0)), author TEXT NOT NULL, author_display TEXT NOT NULL, created_at INTEGER NOT NULL, mutation_id TEXT NOT NULL, supersedes_event_id INTEGER, FOREIGN KEY (supersedes_event_id) REFERENCES position_review_events(id) ON DELETE RESTRICT)",
    "CREATE UNIQUE INDEX idx_position_review_one_root ON position_review_events(dataset_id,etroc_serial,acquisition_id,analysis_run_id,labelled_montage_sha256,clean_montage_sha256,position_publication_sha256,position,source_image_sha256,geometry_version) WHERE supersedes_event_id IS NULL",
    "CREATE UNIQUE INDEX idx_position_review_one_successor ON position_review_events(supersedes_event_id) WHERE supersedes_event_id IS NOT NULL",
    "CREATE UNIQUE INDEX idx_position_review_author_mutation ON position_review_events(author,mutation_id)",
    "CREATE INDEX idx_position_review_current_lookup ON position_review_events(dataset_id,etroc_serial,acquisition_id,analysis_run_id,labelled_montage_sha256,clean_montage_sha256,position_publication_sha256,position,source_image_sha256,geometry_version,id)",
    "CREATE TRIGGER position_review_no_update BEFORE UPDATE ON position_review_events BEGIN SELECT RAISE(ABORT, 'ETROC position review events are append-only'); END",
    "CREATE TRIGGER position_review_no_delete BEFORE DELETE ON position_review_events BEGIN SELECT RAISE(ABORT, 'ETROC position review events are append-only'); END",
    "CREATE TRIGGER position_review_same_evidence_successor BEFORE INSERT ON position_review_events WHEN NEW.supersedes_event_id IS NOT NULL BEGIN SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM position_review_events AS previous WHERE previous.id = NEW.supersedes_event_id AND previous.dataset_id = NEW.dataset_id AND previous.etroc_serial = NEW.etroc_serial AND previous.acquisition_id = NEW.acquisition_id AND previous.analysis_run_id = NEW.analysis_run_id AND previous.labelled_montage_sha256 = NEW.labelled_montage_sha256 AND previous.clean_montage_sha256 = NEW.clean_montage_sha256 AND previous.position_publication_sha256 = NEW.position_publication_sha256 AND previous.position = NEW.position AND previous.source_image_sha256 = NEW.source_image_sha256 AND previous.geometry_version = NEW.geometry_version) THEN RAISE(ABORT, 'invalid ETROC position review supersession') END; END",
)
DDL: Final = (
    "CREATE TABLE position_review_schema (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), version INTEGER NOT NULL CHECK (version = 2), applied_at INTEGER NOT NULL) WITHOUT ROWID",
    "CREATE TABLE position_review_events (id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id TEXT NOT NULL, etroc_serial TEXT NOT NULL, acquisition_id TEXT NOT NULL, analysis_run_id TEXT NOT NULL, labelled_montage_sha256 TEXT NOT NULL, clean_montage_sha256 TEXT NOT NULL, position_publication_sha256 TEXT NOT NULL, position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 255), source_image_sha256 TEXT NOT NULL, geometry_version TEXT NOT NULL CHECK (geometry_version = 'etroc-grid-16x16-v1'), label TEXT NOT NULL CHECK (label IN ('GREEN', 'BLUE', 'YELLOW', 'RED')), note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 2000), author TEXT NOT NULL, author_display TEXT NOT NULL, created_at INTEGER NOT NULL, mutation_id TEXT NOT NULL, supersedes_event_id INTEGER, FOREIGN KEY (supersedes_event_id) REFERENCES position_review_events(id) ON DELETE RESTRICT)",
    *V1_DDL[2:],
)
OBJECT_NAMES: Final = frozenset({
    "position_review_schema", "position_review_events",
    "idx_position_review_one_root", "idx_position_review_one_successor",
    "idx_position_review_author_mutation", "idx_position_review_current_lookup",
    "position_review_no_update", "position_review_no_delete",
    "position_review_same_evidence_successor",
})
LEGACY_OBJECT_NAMES: Final = frozenset({
    "etroc_position_review_schema", "etroc_position_review_events",
    "idx_etroc_position_review_one_root", "idx_etroc_position_review_one_successor",
    "idx_etroc_position_review_author_mutation", "idx_etroc_position_review_current_lookup",
    "etroc_position_review_no_update", "etroc_position_review_no_delete",
    "etroc_position_review_same_evidence_successor",
})


@dataclass(frozen=True, slots=True)
class PositionEvidenceRecord:
    dataset_id: str
    etroc_serial: str
    acquisition_id: str
    analysis_run_id: str
    labelled_montage_sha256: str
    clean_montage_sha256: str
    position_publication_sha256: str
    position: int
    source_image_sha256: str
    geometry_version: str
    row: int
    column: int
    algorithm_category: str
    algorithm_reason: str
    review_target: bool
    cell: Mapping[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            **{field: getattr(self, field) for field in POSITION_KEY_FIELDS},
            "row": self.row,
            "column": self.column,
            "algorithm_category": self.algorithm_category,
            "algorithm_reason": self.algorithm_reason,
            "review_target": self.review_target,
            "cell": dict(self.cell),
        }


@dataclass(frozen=True, slots=True)
class PositionAcquisitionEvidence:
    dataset_id: str
    etroc_serial: str
    acquisition_id: str
    analysis_run_id: str
    labelled_montage_sha256: str
    clean_montage_sha256: str
    clean_montage_uri: str
    position_publication_sha256: str
    position_publication_uri: str
    height_publication_sha256: str
    height_publication_uri: str
    height_contract: Mapping[str, object]
    height_measurements: Mapping[int, Mapping[str, object]]
    geometry_version: str
    target_count: int
    positions: Mapping[int, PositionEvidenceRecord]


@dataclass(frozen=True, slots=True)
class PositionEvidenceSet:
    dataset_id: str
    publication_sha256: str
    by_acquisition: Mapping[str, PositionAcquisitionEvidence]


@dataclass(frozen=True, slots=True)
class ServiceResult:
    status: int
    payload: dict[str, object]


def _normalized_sql(sql: str) -> str:
    parts = re.split(r"('(?:''|[^'])*')", sql.replace(";", ""))
    return "".join(part if index % 2 else " ".join(part.replace('"', "").split()).lower() for index, part in enumerate(parts))


def _digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _checksum_inventory(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("ETROC position checksum inventory is unavailable") from exc
    inventory: dict[str, str] = {}
    for line in lines:
        match = CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise ValueError("invalid ETROC position checksum inventory")
        digest, relative = match.groups()
        candidate = Path(relative)
        if candidate.is_absolute() or candidate.as_posix() != relative or any(part in {"", ".", ".."} for part in candidate.parts) or relative in inventory:
            raise ValueError("invalid ETROC position checksum inventory")
        inventory[relative] = digest
    if not inventory:
        raise ValueError("invalid ETROC position checksum inventory")
    return inventory


def _asset_bytes(bundle: Path, relative: str, digest: str, size: int | None, role: str) -> bytes:
    path = (bundle / relative).resolve()
    if bundle.resolve() not in path.parents or not path.is_file():
        raise ValueError(f"ETROC position {role} is unavailable")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"ETROC position {role} is unavailable") from exc
    if (size is not None and len(raw) != size) or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"ETROC position {role} bytes do not match publication")
    return raw


def load_evidence(static_root: Path) -> PositionEvidenceSet:
    root = Path(static_root).resolve()
    bundle = root / "data/etroc-optical" / DATASET_ID
    publication_path = bundle / "chips.json"
    try:
        publication_raw = publication_path.read_bytes()
        publication = json.loads(publication_raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("ETROC position evidence is unavailable") from exc
    records = publication.get("records") if isinstance(publication, dict) else None
    if (
        not isinstance(publication, dict)
        or publication.get("dataset_id") != DATASET_ID
        or publication.get("record_count") != 36
        or publication.get("position_record_count") != 9216
        or publication.get("position_review_target_count") != 82
        or publication.get("position_geometry_version") != GEOMETRY_VERSION
        or not isinstance(records, list)
        or len(records) != 36
    ):
        raise ValueError("invalid ETROC position publication")
    canonical_assets = {"chips.json": hashlib.sha256(publication_raw).hexdigest()}
    acquisitions: dict[str, PositionAcquisitionEvidence] = {}
    total_positions = 0
    total_targets = 0
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise ValueError("invalid ETROC position acquisition record")
        identity = (DATASET_ID, raw_record.get("etroc_serial"), raw_record.get("acquisition_id"), raw_record.get("analysis_run_id"))
        if any(not isinstance(value, str) or not value or len(value) > 500 or not value.isprintable() for value in identity):
            raise ValueError("invalid ETROC position acquisition identity")
        dataset_id, etroc_serial, acquisition_id, analysis_run_id = identity
        labelled_digest = raw_record.get("montage_sha256")
        clean_digest = raw_record.get("clean_montage_sha256")
        position_digest = raw_record.get("position_publication_sha256")
        height_digest = raw_record.get("height_publication_sha256")
        clean_uri = raw_record.get("clean_montage_uri")
        position_uri = raw_record.get("position_publication_uri")
        height_uri = raw_record.get("height_publication_uri")
        geometry = raw_record.get("position_geometry_version")
        target_count = raw_record.get("position_review_target_count")
        if (
            acquisition_id in acquisitions
            or not all(_digest(value) for value in (labelled_digest, clean_digest, position_digest, height_digest))
            or clean_uri != f"clean-montages/sha256/{clean_digest}.jpg"
            or position_uri != f"positions/sha256/{position_digest}.json"
            or height_uri != f"heights/sha256/{height_digest}.json"
            or geometry != GEOMETRY_VERSION
            or type(target_count) is not int
            or target_count < 0
            or target_count > 256
        ):
            raise ValueError("invalid ETROC position acquisition evidence")
        asset_specs = (
            (raw_record.get("montage_uri"), labelled_digest, raw_record.get("montage_size_bytes"), "labelled montage"),
            (raw_record.get("preview_uri"), raw_record.get("preview_sha256"), raw_record.get("preview_size_bytes"), "preview"),
            (clean_uri, clean_digest, raw_record.get("clean_montage_size_bytes"), "clean montage"),
            (position_uri, position_digest, None, "position publication"),
            (height_uri, height_digest, raw_record.get("height_publication_size_bytes"), "height publication"),
        )
        position_raw = b""
        height_raw = b""
        for relative, digest, size, role in asset_specs:
            if not isinstance(relative, str) or not _digest(digest) or (size is not None and (type(size) is not int or size < 1)) or relative in canonical_assets:
                raise ValueError("invalid ETROC position canonical asset")
            raw = _asset_bytes(bundle, relative, digest, size, role)
            canonical_assets[relative] = digest
            if role == "position publication":
                position_raw = raw
            elif role == "height publication":
                height_raw = raw
        try:
            document = json.loads(position_raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid ETROC position publication document") from exc
        raw_positions = document.get("positions") if isinstance(document, dict) else None
        if (
            document.get("schema_version") != "1.0"
            or document.get("geometry_version") != GEOMETRY_VERSION
            or document.get("dataset_id") != dataset_id
            or document.get("etroc_serial") != etroc_serial
            or document.get("acquisition_id") != acquisition_id
            or document.get("analysis_run_id") != analysis_run_id
            or document.get("labelled_montage_sha256") != labelled_digest
            or document.get("clean_montage_sha256") != clean_digest
            or document.get("review_target_count") != target_count
            or not isinstance(raw_positions, list)
            or len(raw_positions) != 256
        ):
            raise ValueError("ETROC position document identity mismatch")
        try:
            height_document = json.loads(height_raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid ETROC height publication document") from exc
        height_contract = height_document.get("height_contract") if isinstance(height_document, dict) else None
        raw_measurements = height_document.get("measurements") if isinstance(height_document, dict) else None
        expected_height_contract = {
            "unit": "mm", "no_ball_lte": 0.01, "in_spec_min": 0.035,
            "in_spec_max_exclusive": 0.065, "algorithm_config_sha256": publication.get("analysis_config_sha256"),
        }
        if (set(height_document) != {"schema_version", "dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "height_contract", "measurements"}
                or height_document.get("schema_version") != "1.0" or height_document.get("dataset_id") != dataset_id
                or height_document.get("etroc_serial") != etroc_serial or height_document.get("acquisition_id") != acquisition_id
                or height_document.get("analysis_run_id") != analysis_run_id or height_contract != expected_height_contract
                or not isinstance(raw_measurements, list) or len(raw_measurements) != 256):
            raise ValueError("ETROC height document identity mismatch")
        height_measurements: dict[int, Mapping[str, object]] = {}
        for expected_position, measurement in enumerate(raw_measurements):
            if (not isinstance(measurement, dict) or set(measurement) != {"position", "status", "value"}
                    or measurement.get("position") != expected_position or measurement.get("status") not in {"HEIGHT_NO_BALL", "IN_SPEC", "OUT_OF_SPEC"}
                    or isinstance(measurement.get("value"), bool) or not isinstance(measurement.get("value"), (int, float))
                    or not math.isfinite(float(measurement["value"]))):
                raise ValueError("invalid ETROC height measurement")
            height_measurements[expected_position] = MappingProxyType(dict(measurement))
        positions: dict[int, PositionEvidenceRecord] = {}
        observed_targets = 0
        expected_cell_keys = {"x", "y", "width", "height", "image_y", "image_height"}
        for expected_position, raw_position in enumerate(raw_positions):
            if not isinstance(raw_position, dict) or set(raw_position) != {"position", "row", "column", "algorithm_category", "algorithm_reason", "source_image_sha256", "review_target", "cell"}:
                raise ValueError("invalid ETROC position record shape")
            row, column = divmod(expected_position, 16)
            category = raw_position["algorithm_category"]
            cell = raw_position["cell"]
            expected_cell = {"x": column * 150, "y": row * 136, "width": 150, "height": 136, "image_y": 16, "image_height": 120}
            if (
                raw_position["position"] != expected_position
                or raw_position["row"] != row
                or raw_position["column"] != column
                or category not in POSITION_CATEGORIES
                or not isinstance(raw_position["algorithm_reason"], str)
                or not raw_position["algorithm_reason"]
                or not _digest(raw_position["source_image_sha256"])
                or type(raw_position["review_target"]) is not bool
                or raw_position["review_target"] != (category == "NEED_INSPECT")
                or not isinstance(cell, dict)
                or set(cell) != expected_cell_keys
                or cell != expected_cell
            ):
                raise ValueError("invalid ETROC position record")
            evidence = PositionEvidenceRecord(
                dataset_id, etroc_serial, acquisition_id, analysis_run_id,
                labelled_digest, clean_digest, position_digest, expected_position,
                raw_position["source_image_sha256"], GEOMETRY_VERSION,
                row, column, category, raw_position["algorithm_reason"],
                raw_position["review_target"], MappingProxyType(dict(cell)),
            )
            positions[expected_position] = evidence
            observed_targets += int(evidence.review_target)
        if observed_targets != target_count:
            raise ValueError("ETROC position target count mismatch")
        acquisitions[acquisition_id] = PositionAcquisitionEvidence(
            dataset_id, etroc_serial, acquisition_id, analysis_run_id,
            labelled_digest, clean_digest,
            f"data/etroc-optical/{DATASET_ID}/{clean_uri}",
            position_digest, f"data/etroc-optical/{DATASET_ID}/{position_uri}",
            height_digest, f"data/etroc-optical/{DATASET_ID}/{height_uri}",
            MappingProxyType(dict(expected_height_contract)), MappingProxyType(height_measurements),
            GEOMETRY_VERSION, target_count, MappingProxyType(positions),
        )
        total_positions += len(positions)
        total_targets += target_count
    if len(acquisitions) != 36 or total_positions != 9216 or total_targets != 82:
        raise ValueError("ETROC position evidence aggregate mismatch")
    if _checksum_inventory(bundle / "SHA256SUMS") != canonical_assets:
        raise ValueError("ETROC position checksum inventory does not match canonical assets")
    return PositionEvidenceSet(DATASET_ID, hashlib.sha256(publication_raw).hexdigest(), MappingProxyType(acquisitions))


def _legacy_objects(db: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE name GLOB 'etroc_position_review_*' "
            "OR name GLOB 'idx_etroc_position_review_*' "
            "OR (tbl_name IN ('etroc_position_review_schema','etroc_position_review_events') "
            "AND type IN ('index','trigger') AND name NOT LIKE 'sqlite_autoindex%')"
        )
    }


def _drop_empty_legacy_schema(db: sqlite3.Connection) -> None:
    legacy = _legacy_objects(db)
    if not legacy:
        return
    if legacy != LEGACY_OBJECT_NAMES:
        raise ValueError("unsupported legacy ETROC position review schema objects")
    metadata = db.execute("SELECT singleton,version FROM etroc_position_review_schema").fetchall()
    event_count = db.execute("SELECT count(*) FROM etroc_position_review_events").fetchone()[0]
    if metadata != [(1, 1)] or event_count != 0:
        raise ValueError("legacy ETROC position review schema is not safely empty")
    for kind, name in (
        ("TRIGGER", "etroc_position_review_same_evidence_successor"),
        ("TRIGGER", "etroc_position_review_no_delete"),
        ("TRIGGER", "etroc_position_review_no_update"),
        ("INDEX", "idx_etroc_position_review_current_lookup"),
        ("INDEX", "idx_etroc_position_review_author_mutation"),
        ("INDEX", "idx_etroc_position_review_one_successor"),
        ("INDEX", "idx_etroc_position_review_one_root"),
        ("TABLE", "etroc_position_review_events"),
        ("TABLE", "etroc_position_review_schema"),
    ):
        db.execute(f"DROP {kind} {name}")


def _managed_objects(db: sqlite3.Connection) -> dict[str, str]:
    rows = db.execute(
        "SELECT name,tbl_name,sql FROM sqlite_master WHERE "
        "name GLOB 'position_review_*' OR name GLOB 'idx_position_review_*' "
        "OR (tbl_name IN ('position_review_schema','position_review_events') "
        "AND type IN ('index','trigger') AND name NOT LIKE 'sqlite_autoindex%') ORDER BY name"
    )
    return {row[0]: row[2] or "" for row in rows}


def _index_details(db: sqlite3.Connection) -> dict[str, tuple[int, str, int, tuple[str, ...]]]:
    details = {}
    for row in db.execute("PRAGMA index_list(position_review_events)"):
        name = row[1]
        details[name] = (row[2], row[3], row[4], tuple(item[2] for item in db.execute(f'PRAGMA index_info("{name.replace(chr(34), chr(34) * 2)}")')))
    return details


def _validate_schema_contract(
    db: sqlite3.Connection,
    ddl: tuple[str, ...],
    version: int,
    value_field: str,
) -> None:
    objects = _managed_objects(db)
    if set(objects) != OBJECT_NAMES:
        raise ValueError("unsupported ETROC position review schema objects")
    expected = {name: _normalized_sql(statement) for name, statement in zip((
        "position_review_schema", "position_review_events",
        "idx_position_review_one_root", "idx_position_review_one_successor",
        "idx_position_review_author_mutation", "idx_position_review_current_lookup",
        "position_review_no_update", "position_review_no_delete",
        "position_review_same_evidence_successor",
    ), ddl)}
    if any(_normalized_sql(objects[name]) != sql for name, sql in expected.items()):
        raise ValueError("unsupported ETROC position review schema definition")
    metadata = db.execute("SELECT singleton,version,applied_at FROM position_review_schema").fetchall()
    if len(metadata) != 1 or metadata[0][0] != 1 or metadata[0][1] != version or type(metadata[0][2]) is not int:
        raise ValueError("unsupported ETROC position review schema metadata")
    columns = [(row[1], row[2].upper(), row[3]) for row in db.execute("PRAGMA table_info(position_review_events)")]
    expected_columns = [
        ("id", "INTEGER", 0), ("dataset_id", "TEXT", 1), ("etroc_serial", "TEXT", 1),
        ("acquisition_id", "TEXT", 1), ("analysis_run_id", "TEXT", 1),
        ("labelled_montage_sha256", "TEXT", 1), ("clean_montage_sha256", "TEXT", 1),
        ("position_publication_sha256", "TEXT", 1), ("position", "INTEGER", 1), ("source_image_sha256", "TEXT", 1),
        ("geometry_version", "TEXT", 1), (value_field, "TEXT", 1), ("note", "TEXT", 1),
        ("author", "TEXT", 1), ("author_display", "TEXT", 1), ("created_at", "INTEGER", 1),
        ("mutation_id", "TEXT", 1), ("supersedes_event_id", "INTEGER", 0),
    ]
    expected_indexes = {
        "idx_position_review_one_root": (1, "c", 1, POSITION_KEY_FIELDS),
        "idx_position_review_one_successor": (1, "c", 1, ("supersedes_event_id",)),
        "idx_position_review_author_mutation": (1, "c", 0, ("author", "mutation_id")),
        "idx_position_review_current_lookup": (0, "c", 0, (*POSITION_KEY_FIELDS, "id")),
    }
    foreign_keys = [tuple(row) for row in db.execute("PRAGMA foreign_key_list(position_review_events)")]
    if (
        columns != expected_columns
        or _index_details(db) != expected_indexes
        or foreign_keys != [(0, 0, "position_review_events", "supersedes_event_id", "id", "NO ACTION", "RESTRICT", "NONE")]
        or [row[1] for row in db.execute("PRAGMA index_list(position_review_schema)") if not row[1].startswith("sqlite_autoindex")]
        or list(db.execute("PRAGMA foreign_key_check"))
        or list(db.execute("PRAGMA integrity_check")) != [("ok",)]
    ):
        raise ValueError("unsupported ETROC position review schema integrity")


def validate_schema(db: sqlite3.Connection) -> None:
    _validate_schema_contract(db, DDL, 2, "label")


def _drop_position_schema(db: sqlite3.Connection) -> None:
    for kind, name in (
        ("TRIGGER", "position_review_same_evidence_successor"),
        ("TRIGGER", "position_review_no_delete"),
        ("TRIGGER", "position_review_no_update"),
        ("INDEX", "idx_position_review_current_lookup"),
        ("INDEX", "idx_position_review_author_mutation"),
        ("INDEX", "idx_position_review_one_successor"),
        ("INDEX", "idx_position_review_one_root"),
        ("TABLE", "position_review_events"),
        ("TABLE", "position_review_schema"),
    ):
        db.execute(f"DROP {kind} {name}")


def _migrate_empty_v1(db: sqlite3.Connection) -> None:
    _validate_schema_contract(db, V1_DDL, 1, "state")
    if db.execute("SELECT count(*) FROM position_review_events").fetchone()[0] != 0:
        raise ValueError("deployed v1 ETROC position review events cannot be mapped to colour labels")
    _drop_position_schema(db)
    for statement in DDL:
        db.execute(statement)
    db.execute("INSERT INTO position_review_schema(singleton,version,applied_at) VALUES(1,2,?)", (int(time.time()),))


def init_schema(db_path: Path) -> None:
    with sqlite3.connect(Path(db_path), isolation_level=None) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            _drop_empty_legacy_schema(db)
            objects = _managed_objects(db)
            if not objects:
                for statement in DDL:
                    db.execute(statement)
                db.execute("INSERT INTO position_review_schema(singleton,version,applied_at) VALUES(1,2,?)", (int(time.time()),))
            else:
                try:
                    validate_schema(db)
                except ValueError:
                    _migrate_empty_v1(db)
            validate_schema(db)
        except (sqlite3.DatabaseError, ValueError):
            db.rollback()
            raise
        db.commit()


def _event(row: sqlite3.Row) -> dict[str, object]:
    return {"event_id": row["id"], **{field: row[field] for field in EVENT_FIELDS[1:]}}


def _current(db: sqlite3.Connection, evidence: PositionEvidenceRecord) -> dict[str, object] | None:
    where = " AND ".join(f"event.{field}=?" for field in POSITION_KEY_FIELDS)
    row = db.execute(
        f"SELECT event.*, (SELECT count(*) FROM position_review_events AS chain WHERE "
        + " AND ".join(f"chain.{field}=event.{field}" for field in POSITION_KEY_FIELDS)
        + f") AS history_count FROM position_review_events AS event WHERE {where} "
        "AND NOT EXISTS (SELECT 1 FROM position_review_events AS later WHERE later.supersedes_event_id=event.id)",
        tuple(getattr(evidence, field) for field in POSITION_KEY_FIELDS),
    ).fetchone()
    if row is None:
        return None
    return {
        "current_event_id": row["id"],
        **{field: row[field] for field in POSITION_KEY_FIELDS},
        "label": row["label"], "note": row["note"], "author": row["author"],
        "author_display": row["author_display"], "created_at": row["created_at"],
        "history_count": row["history_count"],
    }


def _history(db: sqlite3.Connection, evidence: PositionEvidenceRecord) -> list[dict[str, object]]:
    where = " AND ".join(f"{field}=?" for field in POSITION_KEY_FIELDS)
    rows = db.execute(
        f"SELECT * FROM position_review_events WHERE {where} ORDER BY id DESC",
        tuple(getattr(evidence, field) for field in POSITION_KEY_FIELDS),
    ).fetchall()
    return [_event(row) for row in rows]


def _completion(acquisition: PositionAcquisitionEvidence, reviews: Mapping[str, object]) -> dict[str, object]:
    reviewed_target_count = sum(
        1 for position, record in acquisition.positions.items()
        if record.review_target and str(position) in reviews
    )
    if acquisition.target_count == 0:
        status = "not_applicable"
    elif reviewed_target_count == acquisition.target_count:
        status = "review_complete"
    else:
        status = "review_pending"
    return {
        "acquisition_id": acquisition.acquisition_id,
        "etroc_serial": acquisition.etroc_serial,
        "target_count": acquisition.target_count,
        "reviewed_target_count": reviewed_target_count,
        "status": status,
    }


def summary(db_path: Path, evidence: PositionEvidenceSet, acquisition_id: str, viewer_display: str, can_append_review: bool) -> dict[str, object]:
    acquisition = evidence.by_acquisition.get(acquisition_id)
    if acquisition is None:
        raise KeyError(acquisition_id)
    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        reviews = {str(position): current for position, record in acquisition.positions.items() if (current := _current(db, record)) is not None}
    completion = _completion(acquisition, reviews)
    return {
        "dataset_id": evidence.dataset_id,
        "publication_sha256": evidence.publication_sha256,
        "acquisition_id": acquisition.acquisition_id,
        "etroc_serial": acquisition.etroc_serial,
        "analysis_run_id": acquisition.analysis_run_id,
        "labelled_montage_sha256": acquisition.labelled_montage_sha256,
        "clean_montage_sha256": acquisition.clean_montage_sha256,
        "clean_montage_uri": acquisition.clean_montage_uri,
        "position_publication_sha256": acquisition.position_publication_sha256,
        "position_publication_uri": acquisition.position_publication_uri,
        "height_publication_sha256": acquisition.height_publication_sha256,
        "height_publication_uri": acquisition.height_publication_uri,
        "height_contract": dict(acquisition.height_contract),
        "height_evidence": {str(position): dict(measurement) for position, measurement in acquisition.height_measurements.items()},
        "geometry_version": acquisition.geometry_version,
        "position_count": len(acquisition.positions),
        "target_count": acquisition.target_count,
        "reviewed_target_count": completion["reviewed_target_count"],
        "completion_status": completion["status"],
        "viewer": {"identity_display": viewer_display, "can_append_review": can_append_review},
        "evidence": {str(position): record.as_dict() for position, record in acquisition.positions.items()},
        "reviews": reviews,
    }


def completion_summary(db_path: Path, evidence: PositionEvidenceSet) -> dict[str, object]:
    completion: dict[str, dict[str, object]] = {}
    reviewed_total = 0
    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        for acquisition_id, acquisition in evidence.by_acquisition.items():
            reviews = {
                str(position): current
                for position, record in acquisition.positions.items()
                if record.review_target and (current := _current(db, record)) is not None
            }
            reviewed_total += len(reviews)
            completion[acquisition_id] = _completion(acquisition, reviews)
    return {
        "dataset_id": evidence.dataset_id,
        "publication_sha256": evidence.publication_sha256,
        "record_count": len(evidence.by_acquisition),
        "target_count": sum(item.target_count for item in evidence.by_acquisition.values()),
        "reviewed_target_count": reviewed_total,
        "completion": completion,
    }


def results_summary(db_path: Path, evidence: PositionEvidenceSet) -> dict[str, object]:
    """Bounded current labels from one read snapshot, never history or review notes.

    Algorithm/geometry evidence was validated by load_evidence. Current human
    labels use the exact immutable position key, just like the detail API.
    """
    results: dict[str, dict[str, object]] = {}
    with sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        validate_schema(db)
        db.row_factory = sqlite3.Row
        for acquisition_id, acquisition in evidence.by_acquisition.items():
            reviews = {}
            for position, record in acquisition.positions.items():
                if not record.review_target:
                    continue
                current = _current(db, record)
                if current is not None:
                    if current["label"] not in HUMAN_LABELS or type(current["current_event_id"]) is not int or current["current_event_id"] <= 0:
                        raise ValueError("invalid current position review")
                    reviews[str(position)] = {
                        "label": current["label"], "current_event_id": current["current_event_id"],
                    }
            results[acquisition_id] = {
                **_completion(acquisition, reviews),
                "analysis_run_id": acquisition.analysis_run_id,
                "labelled_montage_sha256": acquisition.labelled_montage_sha256,
                "clean_montage_sha256": acquisition.clean_montage_sha256,
                "position_publication_sha256": acquisition.position_publication_sha256,
                "geometry_version": acquisition.geometry_version,
                "algorithm_labels": [acquisition.positions[position].algorithm_category for position in range(256)],
                "human_labels": reviews,
            }
    return {
        "dataset_id": evidence.dataset_id,
        "publication_sha256": evidence.publication_sha256,
        "record_count": len(results),
        "position_count": sum(len(item.positions) for item in evidence.by_acquisition.values()),
        "target_count": sum(item["target_count"] for item in results.values()),
        "reviewed_target_count": sum(item["reviewed_target_count"] for item in results.values()),
        "results": results,
    }


def history(db_path: Path, evidence: PositionEvidenceSet, acquisition_id: str, position: int) -> ServiceResult:
    acquisition = evidence.by_acquisition.get(acquisition_id)
    record = acquisition.positions.get(position) if acquisition is not None else None
    if record is None:
        return ServiceResult(404, {"error": {"code": "position_not_found", "message": "The position is not in the current publication."}})
    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        chain = _history(db, record)
    return ServiceResult(200, {"evidence": record.as_dict(), "current": chain[0] if chain else None, "history": chain})


def audit(
    db_path: Path,
    acquisition_id: str,
    position: int,
    evidence: PositionEvidenceSet | None,
) -> ServiceResult:
    fields = ",".join(POSITION_KEY_FIELDS)
    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            f"SELECT {fields} FROM position_review_events WHERE acquisition_id=? AND position=? "
            f"GROUP BY {fields} ORDER BY MIN(id)",
            (acquisition_id, position),
        ).fetchall()
        chains = []
        for row in rows:
            record = PositionEvidenceRecord(
                *[row[field] for field in POSITION_KEY_FIELDS],
                position // 16, position % 16, "GREEN", "historical", False,
                MappingProxyType({}),
            )
            acquisition = evidence.by_acquisition.get(acquisition_id) if evidence is not None else None
            published = acquisition.positions.get(position) if acquisition is not None else None
            current_publication = published is not None and all(
                getattr(published, field) == getattr(record, field) for field in POSITION_KEY_FIELDS
            )
            chain = _history(db, record)
            chains.append({
                "evidence": {field: getattr(record, field) for field in POSITION_KEY_FIELDS},
                "current_publication": current_publication,
                "current_event": chain[0] if chain else None,
                "history": chain,
            })
    if not chains:
        return ServiceResult(404, {"error": {"code": "audit_not_found", "message": "No review history exists for this position."}})
    return ServiceResult(200, {"acquisition_id": acquisition_id, "position": position, "chains": chains})


def validate_request(request: dict[str, object]) -> ServiceResult | None:
    keys = set(request)
    if keys - REQUEST_FIELDS:
        return ServiceResult(400, {"error": {"code": "unknown_field", "message": "The request contains an unknown field."}})
    if keys != REQUEST_FIELDS:
        return ServiceResult(400, {"error": {"code": "invalid_request_shape", "message": "The request fields do not match the position review contract."}})
    label, note, expected, mutation_id = request["label"], request["note"], request["expected_current_event_id"], request["mutation_id"]
    if not isinstance(label, str) or label not in HUMAN_LABELS:
        return ServiceResult(422, {"error": {"code": "invalid_label", "message": "The human position label is invalid."}})
    if not isinstance(note, str) or len(note) > 2000:
        return ServiceResult(422, {"error": {"code": "invalid_note", "message": "The review note is invalid."}})
    if (type(expected) is not int and expected is not None) or (type(expected) is int and expected <= 0):
        return ServiceResult(422, {"error": {"code": "invalid_event_id", "message": "The expected current event ID is invalid."}})
    try:
        valid_uuid = isinstance(mutation_id, str) and str(uuid.UUID(mutation_id)) == mutation_id
    except ValueError:
        valid_uuid = False
    if not valid_uuid:
        return ServiceResult(422, {"error": {"code": "invalid_mutation_id", "message": "The mutation ID is invalid."}})
    for field in ("labelled_montage_sha256", "clean_montage_sha256", "position_publication_sha256", "source_image_sha256"):
        if not _digest(request[field]):
            return ServiceResult(422, {"error": {"code": "invalid_digest", "message": "An evidence digest is invalid."}})
    if type(request["position"]) is not int or request["position"] not in range(256) or request["geometry_version"] != GEOMETRY_VERSION:
        return ServiceResult(422, {"error": {"code": "invalid_position", "message": "The position evidence is invalid."}})
    for field in ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "geometry_version"):
        value = request[field]
        if not isinstance(value, str) or not value or len(value) > 500 or not value.isprintable():
            return ServiceResult(400, {"error": {"code": "invalid_request_shape", "message": "The position evidence identity is invalid."}})
    return None


def append(
    db_path: Path,
    evidence: PositionEvidenceSet | Callable[[], PositionEvidenceSet],
    request: dict[str, object],
    author: str,
    author_display: str,
) -> ServiceResult:
    error = validate_request(request)
    if error is not None:
        return error
    acquisition_id = str(request["acquisition_id"])
    position = int(request["position"])
    label = str(request["label"])
    note = str(request["note"])
    mutation_id = str(request["mutation_id"])
    expected = request["expected_current_event_id"]
    with sqlite3.connect(Path(db_path), isolation_level=None) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT * FROM position_review_events WHERE author=? AND mutation_id=?", (author, mutation_id)).fetchone()
        if existing is not None:
            identical = all(existing[field] == request[field] for field in (*POSITION_KEY_FIELDS, "label", "note")) and existing["supersedes_event_id"] == expected
            if not identical:
                db.commit()
                return ServiceResult(409, {"error": {"code": "mutation_id_conflict", "message": "This mutation ID was already used for a different position review.", "existing_event_id": existing["id"]}})
            replay = PositionEvidenceRecord(
                *[existing[field] for field in POSITION_KEY_FIELDS],
                position // 16, position % 16, "GREEN", "historical", False, MappingProxyType({}),
            )
            event = _event(existing)
            current = _current(db, replay)
            db.commit()
            return ServiceResult(200, {"ok": True, "idempotent_replay": True, "event": event, "current": current})
        current_evidence = evidence if isinstance(evidence, PositionEvidenceSet) else evidence()
        acquisition = current_evidence.by_acquisition.get(acquisition_id)
        record = acquisition.positions.get(position) if acquisition is not None else None
        if record is None or not all(request[field] == getattr(record, field) for field in POSITION_KEY_FIELDS):
            db.commit()
            return ServiceResult(409, {"error": {"code": "evidence_changed", "message": "The reviewed position no longer matches the current publication.", "canonical_evidence": record.as_dict() if record else None}})
        if not record.review_target:
            db.commit()
            return ServiceResult(422, {"error": {"code": "position_not_review_target", "message": "Only NEED_INSPECT target positions can receive a human label."}})
        current = _current(db, record)
        current_id = current["current_event_id"] if current else None
        if expected != current_id:
            db.commit()
            return ServiceResult(409, {"error": {"code": "stale_current", "message": "The position review changed after it was loaded.", "submitted_expected_current_event_id": expected, "current": current}})
        columns = ",".join((*POSITION_KEY_FIELDS, "label", "note", "author", "author_display", "created_at", "mutation_id", "supersedes_event_id"))
        placeholders = ",".join("?" for _ in range(len(POSITION_KEY_FIELDS) + 7))
        cursor = db.execute(
            f"INSERT INTO position_review_events({columns}) VALUES({placeholders})",
            (*[getattr(record, field) for field in POSITION_KEY_FIELDS], label, note, author, author_display, int(time.time()), mutation_id, expected),
        )
        inserted = _event(db.execute("SELECT * FROM position_review_events WHERE id=?", (cursor.lastrowid,)).fetchone())
        current = _current(db, record)
        db.commit()
    return ServiceResult(201, {"ok": True, "idempotent_replay": False, "event": inserted, "current": current})
