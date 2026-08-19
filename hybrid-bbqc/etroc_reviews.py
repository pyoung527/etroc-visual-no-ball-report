from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Final, Mapping


DATASET_ID: Final = "ETROC_OI_2608"
REVIEW_STATES: Final = frozenset({"reviewed_no_optical_concern", "reviewed_concern_observed", "follow_up_required"})
EVENT_FIELDS: Final = ("event_id", "dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256", "state", "note", "author", "author_display", "created_at", "mutation_id", "supersedes_event_id")
KEY_FIELDS: Final = ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256")
REQUEST_FIELDS: Final = frozenset((*KEY_FIELDS, "state", "note", "expected_current_event_id", "mutation_id"))
CHECKSUM_LINE: Final = re.compile(r"([0-9a-f]{64})  ([^\s]+)")
DDL: Final = (
    "CREATE TABLE etroc_review_schema (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), version INTEGER NOT NULL CHECK (version >= 1), applied_at INTEGER NOT NULL) WITHOUT ROWID",
    "CREATE TABLE etroc_review_events (id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id TEXT NOT NULL, etroc_serial TEXT NOT NULL, acquisition_id TEXT NOT NULL, analysis_run_id TEXT NOT NULL, montage_sha256 TEXT NOT NULL, state TEXT NOT NULL CHECK (state IN ('reviewed_no_optical_concern', 'reviewed_concern_observed', 'follow_up_required')), note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 2000 AND (state = 'reviewed_no_optical_concern' OR length(trim(note)) > 0)), author TEXT NOT NULL, author_display TEXT NOT NULL, created_at INTEGER NOT NULL, mutation_id TEXT NOT NULL, supersedes_event_id INTEGER, FOREIGN KEY (supersedes_event_id) REFERENCES etroc_review_events(id) ON DELETE RESTRICT)",
    "CREATE UNIQUE INDEX idx_etroc_review_one_root ON etroc_review_events(dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256) WHERE supersedes_event_id IS NULL",
    "CREATE UNIQUE INDEX idx_etroc_review_one_successor ON etroc_review_events(supersedes_event_id) WHERE supersedes_event_id IS NOT NULL",
    "CREATE UNIQUE INDEX idx_etroc_review_author_mutation ON etroc_review_events(author,mutation_id)",
    "CREATE INDEX idx_etroc_review_current_lookup ON etroc_review_events(dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,id)",
    "CREATE TRIGGER etroc_review_no_update BEFORE UPDATE ON etroc_review_events BEGIN SELECT RAISE(ABORT, 'ETROC review events are append-only'); END",
    "CREATE TRIGGER etroc_review_no_delete BEFORE DELETE ON etroc_review_events BEGIN SELECT RAISE(ABORT, 'ETROC review events are append-only'); END",
    "CREATE TRIGGER etroc_review_same_evidence_successor BEFORE INSERT ON etroc_review_events WHEN NEW.supersedes_event_id IS NOT NULL BEGIN SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM etroc_review_events AS previous WHERE previous.id = NEW.supersedes_event_id AND previous.dataset_id = NEW.dataset_id AND previous.etroc_serial = NEW.etroc_serial AND previous.acquisition_id = NEW.acquisition_id AND previous.analysis_run_id = NEW.analysis_run_id AND previous.montage_sha256 = NEW.montage_sha256) THEN RAISE(ABORT, 'invalid ETROC review supersession') END; END",
)
OBJECT_NAMES: Final = frozenset({"etroc_review_schema", "etroc_review_events", "idx_etroc_review_one_root", "idx_etroc_review_one_successor", "idx_etroc_review_author_mutation", "idx_etroc_review_current_lookup", "etroc_review_no_update", "etroc_review_no_delete", "etroc_review_same_evidence_successor"})


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    dataset_id: str
    etroc_serial: str
    acquisition_id: str
    analysis_run_id: str
    montage_sha256: str
    montage_uri: str

    def as_dict(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in (*KEY_FIELDS, "montage_uri")}


@dataclass(frozen=True, slots=True)
class EvidenceSet:
    dataset_id: str
    publication_sha256: str
    by_acquisition: Mapping[str, EvidenceRecord]


@dataclass(frozen=True, slots=True)
class ServiceResult:
    status: int
    payload: dict[str, object]


def _normalized_sql(sql: str) -> str:
    parts = re.split(r"('(?:''|[^'])*')", sql.replace(";", ""))
    return "".join(
        part if index % 2 else " ".join(part.replace('"', "").split()).lower()
        for index, part in enumerate(parts)
    )


def _error(code: str, message: str, **extra: object) -> ServiceResult:
    return ServiceResult(400, {"error": {"code": code, "message": message, **extra}})


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _checksum_inventory(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("ETROC review checksum inventory is unavailable") from exc
    inventory: dict[str, str] = {}
    for line in lines:
        match = CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise ValueError("invalid ETROC review checksum inventory")
        digest, relative = match.groups()
        relative_path = Path(relative)
        if relative_path.is_absolute() or relative_path.as_posix() != relative or any(part in {"", ".", ".."} for part in relative_path.parts) or relative in inventory:
            raise ValueError("invalid ETROC review checksum inventory")
        inventory[relative] = digest
    if not inventory:
        raise ValueError("invalid ETROC review checksum inventory")
    return inventory


def load_evidence(static_root: Path) -> EvidenceSet:
    root = Path(static_root).resolve()
    publication_path = root / "data/etroc-optical" / DATASET_ID / "chips.json"
    try:
        raw = publication_path.read_bytes()
        publication = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("ETROC review evidence is unavailable") from exc
    if not isinstance(publication, dict) or publication.get("dataset_id") != DATASET_ID:
        raise ValueError("invalid ETROC review publication")
    records = publication.get("records")
    if not isinstance(records, list) or publication.get("record_count") != 36:
        raise ValueError("ETROC review publication must contain exactly 36 records")
    evidence: dict[str, EvidenceRecord] = {}
    keys: set[tuple[str, str, str, str, str]] = set()
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise ValueError("invalid ETROC review record")
        values = (DATASET_ID, raw_record.get("etroc_serial"), raw_record.get("acquisition_id"), raw_record.get("analysis_run_id"), raw_record.get("montage_sha256"))
        if any(not isinstance(value, str) or not value or len(value) > 500 or not value.isprintable() for value in values):
            raise ValueError("invalid ETROC review identity")
        dataset_id, etroc_serial, acquisition_id, analysis_run_id, montage_sha256 = values
        key = (dataset_id, etroc_serial, acquisition_id, analysis_run_id, montage_sha256)
        if acquisition_id in evidence or key in keys:
            raise ValueError("duplicate ETROC review evidence")
        keys.add(key)
        evidence[acquisition_id] = EvidenceRecord(*key, "")
    if len(evidence) != 36:
        raise ValueError("ETROC review publication must contain exactly 36 records")
    canonical_assets = {"chips.json": hashlib.sha256(raw).hexdigest()}
    for raw_record in records:
        dataset_id = DATASET_ID
        etroc_serial = raw_record["etroc_serial"]
        acquisition_id = raw_record["acquisition_id"]
        analysis_run_id = raw_record["analysis_run_id"]
        montage_sha256 = raw_record["montage_sha256"]
        key = (dataset_id, etroc_serial, acquisition_id, analysis_run_id, montage_sha256)
        montage_uri = raw_record.get("montage_uri")
        montage_size = raw_record.get("montage_size_bytes")
        if not _digest(montage_sha256) or not isinstance(montage_uri, str) or type(montage_size) is not int or montage_size < 1:
            raise ValueError("invalid ETROC review montage digest")
        expected_relative = Path("montages/sha256") / f"{montage_sha256}.jpg"
        if Path(montage_uri) != expected_relative:
            raise ValueError("invalid ETROC review montage URI")
        preview_sha256 = raw_record.get("preview_sha256")
        preview_uri = raw_record.get("preview_uri")
        preview_size = raw_record.get("preview_size_bytes")
        expected_preview = Path("previews") / f"{etroc_serial}.jpg"
        if not _digest(preview_sha256) or not isinstance(preview_uri, str) or type(preview_size) is not int or preview_size < 1 or Path(preview_uri) != expected_preview:
            raise ValueError("invalid ETROC review preview digest")
        for relative, digest, size, asset_name in (
            (montage_uri, montage_sha256, montage_size, "montage"),
            (preview_uri, preview_sha256, preview_size, "preview"),
        ):
            if relative in canonical_assets:
                raise ValueError("duplicate ETROC review canonical asset")
            asset_path = (publication_path.parent / relative).resolve()
            if publication_path.parent.resolve() not in asset_path.parents or not asset_path.is_file():
                raise ValueError(f"ETROC review {asset_name} is unavailable")
            try:
                asset_bytes = asset_path.read_bytes()
            except OSError as exc:
                raise ValueError(f"ETROC review {asset_name} is unavailable") from exc
            if len(asset_bytes) != size or hashlib.sha256(asset_bytes).hexdigest() != digest:
                raise ValueError(f"ETROC review {asset_name} bytes do not match publication")
            canonical_assets[relative] = digest
        evidence[acquisition_id] = EvidenceRecord(*key, f"data/etroc-optical/{DATASET_ID}/{montage_uri}")
    if _checksum_inventory(publication_path.parent / "SHA256SUMS") != canonical_assets:
        raise ValueError("ETROC review checksum inventory does not match canonical assets")
    return EvidenceSet(DATASET_ID, hashlib.sha256(raw).hexdigest(), MappingProxyType(evidence))


def _managed_objects(db: sqlite3.Connection) -> dict[str, str]:
    rows = db.execute(
        "SELECT name,sql FROM sqlite_master WHERE "
        "lower(name) GLOB 'etroc_*' "
        "OR (tbl_name IN ('etroc_review_schema','etroc_review_events') "
        "AND type IN ('index','trigger') AND name NOT LIKE 'sqlite_autoindex%') "
        "ORDER BY name"
    )
    return {row[0]: row[1] or "" for row in rows}


def _index_details(db: sqlite3.Connection) -> dict[str, tuple[int, str, int, tuple[str, ...]]]:
    details: dict[str, tuple[int, str, int, tuple[str, ...]]] = {}
    for row in db.execute("PRAGMA index_list(etroc_review_events)"):
        name = row[1]
        details[name] = (
            row[2],
            row[3],
            row[4],
            tuple(index_row[2] for index_row in db.execute(f'PRAGMA index_info("{name.replace(chr(34), chr(34) * 2)}")')),
        )
    return details


def validate_schema(db: sqlite3.Connection) -> None:
    objects = _managed_objects(db)
    if set(objects) != OBJECT_NAMES:
        raise ValueError("unsupported ETROC review schema objects")
    expected = {
        "etroc_review_schema": _normalized_sql(DDL[0]),
        "etroc_review_events": _normalized_sql(DDL[1]),
        "idx_etroc_review_one_root": _normalized_sql(DDL[2]),
        "idx_etroc_review_one_successor": _normalized_sql(DDL[3]),
        "idx_etroc_review_author_mutation": _normalized_sql(DDL[4]),
        "idx_etroc_review_current_lookup": _normalized_sql(DDL[5]),
        "etroc_review_no_update": _normalized_sql(DDL[6]),
        "etroc_review_no_delete": _normalized_sql(DDL[7]),
        "etroc_review_same_evidence_successor": _normalized_sql(DDL[8]),
    }
    if any(_normalized_sql(objects[name]) != sql for name, sql in expected.items()):
        raise ValueError("unsupported ETROC review schema definition")
    metadata = db.execute("SELECT singleton,version,applied_at FROM etroc_review_schema").fetchall()
    if len(metadata) != 1 or metadata[0][0] != 1 or metadata[0][1] != 1 or type(metadata[0][2]) is not int:
        raise ValueError("unsupported ETROC review schema metadata")
    expected_columns = [("id", "INTEGER", 0), ("dataset_id", "TEXT", 1), ("etroc_serial", "TEXT", 1), ("acquisition_id", "TEXT", 1), ("analysis_run_id", "TEXT", 1), ("montage_sha256", "TEXT", 1), ("state", "TEXT", 1), ("note", "TEXT", 1), ("author", "TEXT", 1), ("author_display", "TEXT", 1), ("created_at", "INTEGER", 1), ("mutation_id", "TEXT", 1), ("supersedes_event_id", "INTEGER", 0)]
    columns = [(row[1], row[2].upper(), row[3]) for row in db.execute("PRAGMA table_info(etroc_review_events)")]
    expected_indexes = {
        "idx_etroc_review_one_root": (1, "c", 1, ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256")),
        "idx_etroc_review_one_successor": (1, "c", 1, ("supersedes_event_id",)),
        "idx_etroc_review_author_mutation": (1, "c", 0, ("author", "mutation_id")),
        "idx_etroc_review_current_lookup": (0, "c", 0, ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256", "id")),
    }
    foreign_keys = [tuple(row) for row in db.execute("PRAGMA foreign_key_list(etroc_review_events)")]
    expected_foreign_keys = [(0, 0, "etroc_review_events", "supersedes_event_id", "id", "NO ACTION", "RESTRICT", "NONE")]
    schema_indexes = [row[1] for row in db.execute("PRAGMA index_list(etroc_review_schema)") if not row[1].startswith("sqlite_autoindex")]
    if columns != expected_columns or schema_indexes or _index_details(db) != expected_indexes or foreign_keys != expected_foreign_keys or list(db.execute("PRAGMA foreign_key_check")):
        raise ValueError("unsupported ETROC review schema integrity")


def init_schema(db_path: Path) -> None:
    with sqlite3.connect(Path(db_path), isolation_level=None) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            objects = _managed_objects(db)
            if not objects:
                for statement in DDL:
                    db.execute(statement)
                db.execute("INSERT INTO etroc_review_schema(singleton,version,applied_at) VALUES(1,1,?)", (int(time.time()),))
            else:
                validate_schema(db)
            validate_schema(db)
        except (sqlite3.DatabaseError, ValueError):
            db.rollback()
            raise
        db.commit()


def _event(row: sqlite3.Row) -> dict[str, object]:
    return {"event_id": row["id"], **{field: row[field] for field in EVENT_FIELDS[1:]}}


def _current(db: sqlite3.Connection, evidence: EvidenceRecord) -> dict[str, object] | None:
    row = db.execute("SELECT event.*, (SELECT count(*) FROM etroc_review_events AS chain WHERE chain.dataset_id=event.dataset_id AND chain.etroc_serial=event.etroc_serial AND chain.acquisition_id=event.acquisition_id AND chain.analysis_run_id=event.analysis_run_id AND chain.montage_sha256=event.montage_sha256) AS history_count FROM etroc_review_events AS event WHERE event.dataset_id=? AND event.etroc_serial=? AND event.acquisition_id=? AND event.analysis_run_id=? AND event.montage_sha256=? AND NOT EXISTS (SELECT 1 FROM etroc_review_events AS later WHERE later.supersedes_event_id=event.id)", tuple(getattr(evidence, field) for field in KEY_FIELDS)).fetchone()
    if row is None:
        return None
    return {"current_event_id": row["id"], **{field: row[field] for field in KEY_FIELDS[0:5]}, "state": row["state"], "note": row["note"], "author": row["author"], "author_display": row["author_display"], "created_at": row["created_at"], "history_count": row["history_count"]}


def _history(db: sqlite3.Connection, evidence: EvidenceRecord) -> list[dict[str, object]]:
    rows = db.execute("SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,state,note,author,author_display,created_at,mutation_id,supersedes_event_id FROM etroc_review_events WHERE dataset_id=? AND etroc_serial=? AND acquisition_id=? AND analysis_run_id=? AND montage_sha256=? ORDER BY id DESC", tuple(getattr(evidence, field) for field in KEY_FIELDS)).fetchall()
    return [_event(row) for row in rows]


def summary(db_path: Path, evidence: EvidenceSet, viewer_display: str, can_append_review: bool) -> dict[str, object]:
    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        reviews = {acquisition_id: current for acquisition_id, record in evidence.by_acquisition.items() if (current := _current(db, record)) is not None}
    return {"dataset_id": evidence.dataset_id, "record_count": len(evidence.by_acquisition), "publication_sha256": evidence.publication_sha256, "viewer": {"identity_display": viewer_display, "can_append_review": can_append_review}, "evidence": {key: record.as_dict() for key, record in evidence.by_acquisition.items()}, "reviews": reviews}


def history(db_path: Path, evidence: EvidenceSet, acquisition_id: str) -> ServiceResult:
    record = evidence.by_acquisition.get(acquisition_id)
    if record is None:
        return _error("acquisition_not_found", "The acquisition is not in the current publication.").__class__(404, {"error": {"code": "acquisition_not_found", "message": "The acquisition is not in the current publication."}})
    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        chain = _history(db, record)
        return ServiceResult(200, {"evidence": record.as_dict(), "current": chain[0] if chain else None, "history": chain})


def audit(db_path: Path, acquisition_id: str, evidence: EvidenceSet | None) -> ServiceResult:
    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256 FROM etroc_review_events WHERE acquisition_id=? GROUP BY dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256 ORDER BY MIN(id)", (acquisition_id,)).fetchall()
        chains = []
        for row in rows:
            record = EvidenceRecord(
                row["dataset_id"], row["etroc_serial"], row["acquisition_id"],
                row["analysis_run_id"], row["montage_sha256"], "",
            )
            published = evidence.by_acquisition.get(acquisition_id) if evidence is not None else None
            current_publication = published is not None and all(
                getattr(published, field) == getattr(record, field) for field in KEY_FIELDS
            )
            chain = _history(db, record)
            chains.append({"evidence": {field: getattr(record, field) for field in KEY_FIELDS}, "current_publication": current_publication, "current_event": chain[0] if chain else None, "history": chain})
    if not chains:
        return ServiceResult(404, {"error": {"code": "audit_not_found", "message": "No review history exists for this acquisition."}})
    return ServiceResult(200, {"acquisition_id": acquisition_id, "chains": chains})


def validate_request(request: dict[str, object]) -> ServiceResult | None:
    request_keys = set(request)
    if request_keys - REQUEST_FIELDS:
        return ServiceResult(400, {"error": {"code": "unknown_field", "message": "The request contains an unknown field."}})
    if request_keys != REQUEST_FIELDS:
        return _error("invalid_request_shape", "The request fields do not match the review contract.")
    state, note, mutation_id, expected = request["state"], request["note"], request["mutation_id"], request["expected_current_event_id"]
    if not isinstance(state, str) or state not in REVIEW_STATES:
        return ServiceResult(422, {"error": {"code": "invalid_state", "message": "The review state is invalid."}})
    if not isinstance(note, str) or len(note) > 2000 or (state != "reviewed_no_optical_concern" and not note.strip()):
        return ServiceResult(422, {"error": {"code": "invalid_note", "message": "The review note is invalid."}})
    if (type(expected) is not int and expected is not None) or (type(expected) is int and expected <= 0):
        return ServiceResult(422, {"error": {"code": "invalid_event_id", "message": "The expected current event ID is invalid."}})
    if not isinstance(mutation_id, str):
        return ServiceResult(422, {"error": {"code": "invalid_mutation_id", "message": "The mutation ID is invalid."}})
    try:
        valid_uuid = str(uuid.UUID(mutation_id)) == mutation_id
    except ValueError:
        valid_uuid = False
    if not valid_uuid:
        return ServiceResult(422, {"error": {"code": "invalid_mutation_id", "message": "The mutation ID is invalid."}})
    if not _digest(request["montage_sha256"]):
        return ServiceResult(422, {"error": {"code": "invalid_digest", "message": "The montage digest is invalid."}})
    for field in KEY_FIELDS[:-1]:
        value = request[field]
        if not isinstance(value, str) or not value or len(value) > 500 or not value.isprintable():
            return ServiceResult(400, {"error": {"code": "invalid_request_shape", "message": "The evidence identity is invalid."}})
    return None


def append(db_path: Path, evidence: EvidenceSet | Callable[[], EvidenceSet], request: dict[str, object], author: str, author_display: str) -> ServiceResult:
    request_error = validate_request(request)
    if request_error is not None:
        return request_error
    state, note, mutation_id, expected = request["state"], request["note"], request["mutation_id"], request["expected_current_event_id"]
    assert isinstance(state, str)
    assert isinstance(note, str)
    assert isinstance(mutation_id, str)
    assert expected is None or type(expected) is int
    acquisition_id = request["acquisition_id"]
    assert isinstance(acquisition_id, str)
    with sqlite3.connect(Path(db_path), isolation_level=None) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,state,note,supersedes_event_id FROM etroc_review_events WHERE author=? AND mutation_id=?", (author, mutation_id)).fetchone()
        if existing is not None:
            identical = all(existing[field] == request[field] for field in (*KEY_FIELDS, "state", "note")) and existing["supersedes_event_id"] == expected
            if not identical:
                db.commit()
                return ServiceResult(409, {"error": {"code": "mutation_id_conflict", "message": "This mutation ID was already used for a different review.", "existing_event_id": existing["id"]}})
            replay_record = EvidenceRecord(
                existing["dataset_id"], existing["etroc_serial"], existing["acquisition_id"],
                existing["analysis_run_id"], existing["montage_sha256"], "",
            )
            event = _event(db.execute("SELECT * FROM etroc_review_events WHERE id=?", (existing["id"],)).fetchone())
            current = _current(db, replay_record)
            db.commit()
            return ServiceResult(200, {"ok": True, "idempotent_replay": True, "event": event, "current": current})
        if isinstance(evidence, EvidenceSet):
            current_evidence = evidence
        else:
            current_evidence = evidence()
        record = current_evidence.by_acquisition.get(acquisition_id)
        canonical = record is not None and all(request[field] == getattr(record, field) for field in KEY_FIELDS)
        if record is None or not canonical:
            db.commit()
            return ServiceResult(409, {"error": {"code": "evidence_changed", "message": "The reviewed evidence no longer matches the current publication.", "canonical_evidence": record.as_dict() if record else None}})
        current = _current(db, record)
        current_id = current["current_event_id"] if current else None
        if expected != current_id:
            db.commit()
            return ServiceResult(409, {"error": {"code": "stale_current", "message": "The review changed after it was loaded.", "submitted_expected_current_event_id": expected, "current": current}})
        cursor = db.execute("INSERT INTO etroc_review_events(dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,state,note,author,author_display,created_at,mutation_id,supersedes_event_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (*[getattr(record, field) for field in KEY_FIELDS], state, note, author, author_display, int(time.time()), mutation_id, expected))
        inserted = _event(db.execute("SELECT * FROM etroc_review_events WHERE id=?", (cursor.lastrowid,)).fetchone())
        current = _current(db, record)
        db.commit()
    return ServiceResult(201, {"ok": True, "idempotent_replay": False, "event": inserted, "current": current})
