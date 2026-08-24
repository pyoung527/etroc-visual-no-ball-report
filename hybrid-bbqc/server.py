from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

import etroc_position_reviews
import etroc_reviews

ROOT = Path(os.environ.get("STATIC_ROOT", "/app/static")).resolve()
PRODUCTION_STATIC_ROOT = ROOT
DB_PATH = Path(os.environ.get("COMMENTS_DB", "/data/comments.sqlite3"))
ALLOW_ANON = os.environ.get("COMMENTS_ALLOW_ANON", "false").lower() in {
    "1",
    "true",
    "yes",
}
ADMIN_USERS = {
    x.strip().lower()
    for x in os.environ.get("COMMENTS_ADMIN_USERS", "").split(",")
    if x.strip()
}
CERN_PRINCIPAL_RE = re.compile(
    r"^[a-z](?:[a-z0-9]|[._-](?=[a-z0-9])){0,63}(?:@cern\.ch)?$"
)


def canonical_cern_principal(value: str) -> str | None:
    normalized = value.lower()
    if CERN_PRINCIPAL_RE.fullmatch(normalized) is None:
        return None
    return normalized


def etroc_reviewer_allowlist(raw: str) -> frozenset[str]:
    normalized = [canonical_cern_principal(value) for value in raw.split(",")]
    if not raw or any(value is None for value in normalized):
        return frozenset()
    return frozenset(value for value in normalized if value is not None)


ETROC_REVIEWER_USERS = etroc_reviewer_allowlist(
    os.environ.get("ETROC_REVIEWER_USERS", "")
)
_ETROC_EVIDENCE_CACHE_LOCK = threading.Lock()
_ETROC_EVIDENCE_CACHE: tuple[tuple[str, tuple[int, int, int, int], tuple[int, int, int, int] | None], etroc_reviews.EvidenceSet] | None = None
_ETROC_POSITION_EVIDENCE_CACHE_LOCK = threading.Lock()
_ETROC_POSITION_EVIDENCE_CACHE: tuple[tuple[str, tuple[int, int, int, int], tuple[int, int, int, int] | None], etroc_position_reviews.PositionEvidenceSet] | None = None
MAX_BODY = int(os.environ.get("COMMENTS_MAX_BODY", "2000"))
HOST = os.environ.get("HOST", "127.0.0.1")
APP_ORIGIN = os.environ.get("APP_ORIGIN", "https://etl-hybrid-bbqc.app.cern.ch").rstrip(
    "/"
)
PAIR_PATH_RE = re.compile(r"hybrids/([A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+)\.html")
REDIRECT_RE = re.compile(r"url=([^\"' >;]+)\.html", re.IGNORECASE)
TEST_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_REVISION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
SOURCE_HYBRID_RE = re.compile(
    r"^HYBRID_[A-Za-z0-9.-]+_(?:HPK-[A-Za-z0-9_.-]+|FBK_[A-Za-z0-9_.-]+)$"
)


def split_pair_key(pair_key: str) -> tuple[str, str]:
    pair_key = str(pair_key or "").strip()
    if "__" not in pair_key:
        raise ValueError("invalid pair_key")
    etroc_serial, lgad_serial = pair_key.split("__", 1)
    if not etroc_serial or not lgad_serial:
        raise ValueError("invalid pair_key")
    return etroc_serial, lgad_serial


def discover_canonical_pairs(static_root: Path) -> list[str]:
    index_path = static_root / "index.html"
    if not index_path.is_file():
        return []
    return sorted(
        set(
            PAIR_PATH_RE.findall(
                index_path.read_text(encoding="utf-8", errors="ignore")
            )
        )
    )


def discover_redirect_aliases(
    static_root: Path, canonical_pairs: set[str]
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    detail_dir = static_root / "hybrids"
    if not detail_dir.is_dir():
        return aliases
    for path in detail_dir.glob("*.html"):
        old_pair = path.stem
        if "__" not in old_pair or old_pair in canonical_pairs:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not re.search(r"http-equiv=[\"']refresh[\"']", text, re.IGNORECASE):
            continue
        match = REDIRECT_RE.search(text)
        if not match:
            continue
        canonical_pair = Path(match.group(1)).name
        if canonical_pair in canonical_pairs:
            aliases[old_pair] = canonical_pair
    return aliases


def source_identifier_pair(source_hybrid_identifier: str) -> str:
    if not SOURCE_HYBRID_RE.fullmatch(source_hybrid_identifier):
        raise ValueError(f"invalid source hybrid identifier: {source_hybrid_identifier}")
    body = source_hybrid_identifier.removeprefix("HYBRID_")
    for marker in ("_HPK-", "_FBK_"):
        if marker in body:
            return body.replace(marker, f"__{marker[1:]}", 1)
    raise ValueError(f"invalid source hybrid identifier: {source_hybrid_identifier}")


def load_additional_tests_manifest(
    path: Path, canonical_pairs: set[str]
) -> dict | None:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid additional test manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("invalid additional test manifest schema")
    source_revision = manifest.get("source_revision")
    tests = manifest.get("tests")
    if not isinstance(source_revision, str) or not SOURCE_REVISION_RE.fullmatch(source_revision):
        raise ValueError("invalid additional test source revision")
    if not isinstance(tests, list) or not tests:
        raise ValueError("additional test manifest has no tests")
    seen_test_keys: set[str] = set()
    seen_display_names: set[str] = set()
    seen_memberships: set[tuple[str, str]] = set()
    raw_pair_map: dict[str, str] = {}
    normalized_tests: list[dict] = []
    for item in tests:
        if not isinstance(item, dict):
            raise ValueError("invalid additional test entry")
        test_key = item.get("test_key")
        display_name = item.get("display_name")
        hybrids = item.get("hybrids")
        if not isinstance(test_key, str) or not TEST_KEY_RE.fullmatch(test_key):
            raise ValueError("invalid additional test key")
        if (
            not isinstance(display_name, str)
            or not display_name.strip()
            or len(display_name) > 100
        ):
            raise ValueError("invalid additional test display name")
        if test_key in seen_test_keys or display_name in seen_display_names:
            raise ValueError("duplicate additional test")
        if not isinstance(hybrids, list) or not hybrids:
            raise ValueError(f"additional test has no hybrids: {test_key}")
        seen_test_keys.add(test_key)
        seen_display_names.add(display_name)
        normalized_members: list[dict] = []
        seen_test_raw: set[str] = set()
        for member in hybrids:
            if not isinstance(member, dict):
                raise ValueError("invalid additional test membership")
            raw = member.get("source_hybrid_identifier")
            pair_key = member.get("pair_key")
            if not isinstance(raw, str):
                raise ValueError("invalid source hybrid identifier")
            if not isinstance(pair_key, str):
                raise ValueError("invalid additional test pair key")
            split_pair_key(pair_key)
            source_identifier_pair(raw)
            if raw in seen_test_raw:
                raise ValueError(f"duplicate source hybrid identifier: {test_key}/{raw}")
            seen_test_raw.add(raw)
            if pair_key not in canonical_pairs:
                raise ValueError(f"additional test hybrid is not canonical: {pair_key}")
            membership = (test_key, pair_key)
            if membership in seen_memberships:
                raise ValueError(f"duplicate additional test membership: {test_key}/{pair_key}")
            previous_pair = raw_pair_map.setdefault(raw, pair_key)
            if previous_pair != pair_key:
                raise ValueError(f"source hybrid identifier maps to multiple pairs: {raw}")
            seen_memberships.add(membership)
            normalized_members.append(
                {"source_hybrid_identifier": raw, "pair_key": pair_key}
            )
        normalized_tests.append(
            {
                "test_key": test_key,
                "display_name": display_name,
                "hybrids": normalized_members,
            }
        )
    return {
        "source_revision": source_revision,
        "tests": normalized_tests,
    }


def validate_additional_test_schema(db: sqlite3.Connection) -> None:
    expected_columns = {
        "additional_tests": [
            ("id", "INTEGER", 0, 1),
            ("test_key", "TEXT", 1, 0),
            ("display_name", "TEXT", 1, 0),
            ("source_revision", "TEXT", 1, 0),
            ("active", "INTEGER", 1, 0),
            ("created_at", "INTEGER", 1, 0),
            ("updated_at", "INTEGER", 1, 0),
        ],
        "hybrid_additional_tests": [
            ("additional_test_id", "INTEGER", 1, 1),
            ("hybrid_registry_id", "INTEGER", 1, 2),
            ("source_hybrid_identifier", "TEXT", 1, 0),
            ("source_revision", "TEXT", 1, 0),
            ("active", "INTEGER", 1, 0),
            ("created_at", "INTEGER", 1, 0),
            ("updated_at", "INTEGER", 1, 0),
        ],
    }
    for table, expected in expected_columns.items():
        actual = [
            (row[1], row[2].upper(), row[3], row[5])
            for row in db.execute(f"PRAGMA table_info({table})")
        ]
        if actual != expected:
            raise ValueError(f"incompatible {table} columns: {actual}")
        sql_row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        normalized_sql = re.sub(r"\s+", "", (sql_row[0] if sql_row else "").lower())
        if "check(activein(0,1))" not in normalized_sql:
            raise ValueError(f"incompatible {table} active constraint")

    unique_indexes: dict[str, list[tuple[tuple[str, ...], str, int]]] = {}
    for table in expected_columns:
        actual_indexes: list[tuple[tuple[str, ...], str, int]] = []
        for index in db.execute(f"PRAGMA index_list({table})"):
            if index[2] != 1:
                continue
            columns = tuple(
                row[2]
                for row in db.execute(f"PRAGMA index_info({index[1]})")
            )
            origin = str(index[3]) if len(index) > 3 else ""
            partial = int(index[4]) if len(index) > 4 else 1
            actual_indexes.append((columns, origin, partial))
        unique_indexes[table] = actual_indexes
    expected_additional_indexes = [
        (("test_key",), "u", 0),
        (("display_name",), "u", 0),
    ]
    if sorted(unique_indexes["additional_tests"]) != sorted(expected_additional_indexes):
        raise ValueError(
            f"incompatible additional_tests unique constraints: {unique_indexes['additional_tests']}"
        )
    expected_membership_indexes = [
        (("additional_test_id", "hybrid_registry_id"), "pk", 0),
        (("additional_test_id", "source_hybrid_identifier"), "u", 0),
    ]
    if sorted(unique_indexes["hybrid_additional_tests"]) != sorted(expected_membership_indexes):
        raise ValueError(
            "incompatible hybrid_additional_tests unique constraints: "
            f"{unique_indexes['hybrid_additional_tests']}"
        )

    foreign_keys = {
        (row[2], row[3], row[4], row[6].upper())
        for row in db.execute("PRAGMA foreign_key_list(hybrid_additional_tests)")
    }
    expected_foreign_keys = {
        ("additional_tests", "additional_test_id", "id", "RESTRICT"),
        ("hybrid_registry", "hybrid_registry_id", "id", "RESTRICT"),
    }
    if foreign_keys != expected_foreign_keys:
        raise ValueError(f"incompatible hybrid_additional_tests foreign keys: {foreign_keys}")


IDENTITY_HEADER = "X-Forwarded-Email"


def init_db(
    db_path: Path = DB_PATH,
    static_root: Path = ROOT,
    *,
    require_additional_tests: bool | None = None,
) -> None:
    db_path = Path(db_path)
    static_root = Path(static_root)
    canonical_pairs = discover_canonical_pairs(static_root)
    if not canonical_pairs:
        raise ValueError("no canonical hybrid pairs found in static dashboard")
    canonical_pair_set = set(canonical_pairs)
    additional_tests_manifest = load_additional_tests_manifest(
        static_root / "additional-tests.json", canonical_pair_set
    )
    redirect_aliases = discover_redirect_aliases(static_root, canonical_pair_set)
    if require_additional_tests is None:
        require_additional_tests = static_root.resolve() == PRODUCTION_STATIC_ROOT.resolve()
    if require_additional_tests and additional_tests_manifest is None:
        raise ValueError("additional test manifest is required for production static root")
    seen_etroc: set[str] = set()
    seen_lgad: set[str] = set()
    for pair_key in canonical_pairs:
        etroc_serial, lgad_serial = split_pair_key(pair_key)
        if etroc_serial in seen_etroc:
            raise ValueError(f"duplicate active ETROC: {etroc_serial}")
        if lgad_serial in seen_lgad:
            raise ValueError(f"duplicate active LGAD: {lgad_serial}")
        seen_etroc.add(etroc_serial)
        seen_lgad.add(lgad_serial)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path, isolation_level=None) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        schema_version = db.execute("PRAGMA user_version").fetchone()[0]
        if schema_version not in (0, 2):
            raise ValueError(f"unsupported database schema version: {schema_version}")
        if schema_version == 2:
            existing_managed_tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('additional_tests','hybrid_additional_tests')"
                )
            }
            if existing_managed_tables != {"additional_tests", "hybrid_additional_tests"}:
                raise ValueError("database schema version 2 is missing managed tables")
        db.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'review',
            author TEXT NOT NULL,
            author_display TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0
        )
        """)
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_comments_target ON comments(target, deleted, created_at)"
        )
        db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_key TEXT NOT NULL UNIQUE,
            etroc_serial TEXT NOT NULL,
            lgad_serial TEXT NOT NULL,
            etl_hybrid_id INTEGER UNIQUE,
            etl_hybrid_serial TEXT UNIQUE,
            sync_status TEXT NOT NULL DEFAULT 'unregistered'
              CHECK (sync_status IN ('unregistered','matched','conflict','retired')),
            bbqc_url TEXT NOT NULL,
            source_revision TEXT,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """)
        db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_target_aliases (
            target TEXT PRIMARY KEY,
            hybrid_registry_id INTEGER NOT NULL,
            is_canonical INTEGER NOT NULL DEFAULT 0 CHECK (is_canonical IN (0,1)),
            created_at INTEGER NOT NULL,
            FOREIGN KEY (hybrid_registry_id) REFERENCES hybrid_registry(id)
        )
        """)
        db.execute("""
        CREATE TABLE IF NOT EXISTS additional_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_key TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL UNIQUE,
            source_revision TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """)
        db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_additional_tests (
            additional_test_id INTEGER NOT NULL,
            hybrid_registry_id INTEGER NOT NULL,
            source_hybrid_identifier TEXT NOT NULL,
            source_revision TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (additional_test_id, hybrid_registry_id),
            UNIQUE (additional_test_id, source_hybrid_identifier),
            FOREIGN KEY (additional_test_id) REFERENCES additional_tests(id) ON DELETE RESTRICT,
            FOREIGN KEY (hybrid_registry_id) REFERENCES hybrid_registry(id) ON DELETE RESTRICT
        )
        """)
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_hybrid_additional_tests_registry ON hybrid_additional_tests(hybrid_registry_id,active,additional_test_id)"
        )
        validate_additional_test_schema(db)
        comment_columns = {row[1] for row in db.execute("PRAGMA table_info(comments)")}
        if "hybrid_registry_id" not in comment_columns:
            db.execute(
                "ALTER TABLE comments ADD COLUMN hybrid_registry_id INTEGER REFERENCES hybrid_registry(id)"
            )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_comments_hybrid_registry ON comments(hybrid_registry_id,deleted,created_at)"
        )

        now = int(time.time())

        existing_rows = db.execute(
            "SELECT id,pair_key,etroc_serial,lgad_serial FROM hybrid_registry"
        ).fetchall()
        by_pair = {row[1]: row[0] for row in existing_rows}
        by_etroc: dict[str, set[int]] = {}
        by_lgad: dict[str, set[int]] = {}
        for registry_id, _pair_key, etroc_serial, lgad_serial in existing_rows:
            by_etroc.setdefault(etroc_serial, set()).add(registry_id)
            by_lgad.setdefault(lgad_serial, set()).add(registry_id)
        ownership_conflict = db.execute(
            """
            SELECT comment.id,comment.target,comment.hybrid_registry_id,
                   alias.hybrid_registry_id
            FROM comments AS comment
            JOIN hybrid_target_aliases AS alias ON alias.target=comment.target
            WHERE comment.hybrid_registry_id IS NOT NULL
              AND comment.hybrid_registry_id != alias.hybrid_registry_id
            LIMIT 1
            """
        ).fetchone()
        if ownership_conflict is not None:
            raise ValueError(
                "comment/alias ownership conflict for "
                f"comment {ownership_conflict[0]} target {ownership_conflict[1]}"
            )
        existing_target_owners: dict[str, set[int]] = {}
        for target, registry_id in db.execute(
            "SELECT target,hybrid_registry_id FROM hybrid_target_aliases"
        ):
            existing_target_owners.setdefault(target, set()).add(registry_id)
        for target, registry_id in db.execute(
            """
            SELECT DISTINCT target,hybrid_registry_id FROM comments
            WHERE hybrid_registry_id IS NOT NULL
            """
        ):
            existing_target_owners.setdefault(target, set()).add(registry_id)

        planned_registry_ids: dict[str, int | None] = {}
        used_registry_ids: dict[int, str] = {}
        for pair_key in canonical_pairs:
            etroc_serial, lgad_serial = split_pair_key(pair_key)
            exact_id = by_pair.get(pair_key)
            direct_candidates = set(
                existing_target_owners.get(f"hybrid:{pair_key}", set())
            )
            if exact_id is not None:
                direct_candidates.add(exact_id)
            for old_pair, canonical_pair in redirect_aliases.items():
                if canonical_pair != pair_key:
                    continue
                if old_pair in by_pair:
                    direct_candidates.add(by_pair[old_pair])
                direct_candidates.update(
                    existing_target_owners.get(f"hybrid:{old_pair}", set())
                )
            if exact_id is not None:
                candidates = direct_candidates
            else:
                candidates = direct_candidates or (
                    by_etroc.get(etroc_serial, set()) | by_lgad.get(lgad_serial, set())
                )
            if len(candidates) > 1:
                raise ValueError(f"ambiguous registry identity for {pair_key}")
            registry_id = next(iter(candidates), None)
            if registry_id is not None and registry_id in used_registry_ids:
                raise ValueError(
                    f"registry identity reused by {used_registry_ids[registry_id]} and {pair_key}"
                )
            if registry_id is not None:
                used_registry_ids[registry_id] = pair_key
            planned_registry_ids[pair_key] = registry_id

        desired_registry_ids = [
            registry_id for registry_id in planned_registry_ids.values() if registry_id is not None
        ]
        if desired_registry_ids:
            placeholders = ",".join("?" for _ in desired_registry_ids)
            db.execute(
                f"UPDATE hybrid_registry SET active=0 WHERE active=1 AND id NOT IN ({placeholders})",
                desired_registry_ids,
            )
        else:
            db.execute("UPDATE hybrid_registry SET active=0 WHERE active=1")
        registry_ids: dict[str, int] = {}
        for pair_key in canonical_pairs:
            etroc_serial, lgad_serial = split_pair_key(pair_key)
            registry_id = planned_registry_ids[pair_key]
            if registry_id is not None:
                db.execute(
                    """
                    UPDATE hybrid_registry
                    SET pair_key=?,etroc_serial=?,lgad_serial=?,bbqc_url=?,active=1,updated_at=?
                    WHERE id=? AND (
                        pair_key IS NOT ? OR etroc_serial IS NOT ? OR lgad_serial IS NOT ?
                        OR bbqc_url IS NOT ? OR active<>1
                    )
                    """,
                    (
                        pair_key,
                        etroc_serial,
                        lgad_serial,
                        f"/hybrids/{pair_key}.html",
                        now,
                        registry_id,
                        pair_key,
                        etroc_serial,
                        lgad_serial,
                        f"/hybrids/{pair_key}.html",
                    ),
                )
            else:
                cursor = db.execute(
                    """
                    INSERT INTO hybrid_registry(
                        pair_key,etroc_serial,lgad_serial,sync_status,bbqc_url,
                        active,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        pair_key,
                        etroc_serial,
                        lgad_serial,
                        "unregistered",
                        f"/hybrids/{pair_key}.html",
                        1,
                        now,
                        now,
                    ),
                )
                registry_id = cursor.lastrowid
                if registry_id is None:
                    raise RuntimeError("failed to create hybrid registry row")
            registry_ids[pair_key] = registry_id

        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_hybrid_registry_active_etroc ON hybrid_registry(etroc_serial) WHERE active=1"
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_hybrid_registry_active_lgad ON hybrid_registry(lgad_serial) WHERE active=1"
        )

        for pair_key, registry_id in registry_ids.items():
            db.execute(
                "UPDATE hybrid_target_aliases SET is_canonical=0 WHERE hybrid_registry_id=?",
                (registry_id,),
            )
            db.execute(
                """
                INSERT INTO hybrid_target_aliases(target,hybrid_registry_id,is_canonical,created_at)
                VALUES(?,?,1,?)
                ON CONFLICT(target) DO UPDATE SET
                    hybrid_registry_id=excluded.hybrid_registry_id,
                    is_canonical=1
                """,
                (f"hybrid:{pair_key}", registry_id, now),
            )
        for old_pair, canonical_pair in redirect_aliases.items():
            registry_id = registry_ids[canonical_pair]
            db.execute(
                """
                INSERT INTO hybrid_target_aliases(target,hybrid_registry_id,is_canonical,created_at)
                VALUES(?,?,0,?)
                ON CONFLICT(target) DO UPDATE SET
                    hybrid_registry_id=excluded.hybrid_registry_id,
                    is_canonical=0
                """,
                (f"hybrid:{old_pair}", registry_id, now),
            )

        db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_hybrid_target_aliases_canonical
            ON hybrid_target_aliases(hybrid_registry_id) WHERE is_canonical=1
            """
        )
        if additional_tests_manifest is not None:
            source_revision = additional_tests_manifest["source_revision"]
            desired_test_keys = {
                test["test_key"] for test in additional_tests_manifest["tests"]
            }
            for test_id, test_key, active in db.execute(
                "SELECT id,test_key,active FROM additional_tests"
            ):
                if active == 1 and test_key not in desired_test_keys:
                    db.execute(
                        "UPDATE additional_tests SET active=0,updated_at=? WHERE id=?",
                        (now, test_id),
                    )
            test_ids: dict[str, int] = {}
            for test in additional_tests_manifest["tests"]:
                db.execute(
                    """
                    INSERT INTO additional_tests(
                        test_key,display_name,source_revision,active,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(test_key) DO UPDATE SET
                        updated_at=CASE
                            WHEN additional_tests.display_name IS NOT excluded.display_name
                              OR additional_tests.source_revision IS NOT excluded.source_revision
                              OR additional_tests.active != 1
                            THEN excluded.updated_at ELSE additional_tests.updated_at END,
                        display_name=excluded.display_name,
                        source_revision=excluded.source_revision,
                        active=1
                    """,
                    (
                        test["test_key"],
                        test["display_name"],
                        source_revision,
                        1,
                        now,
                        now,
                    ),
                )
                test_row = db.execute(
                    "SELECT id FROM additional_tests WHERE test_key=?",
                    (test["test_key"],),
                ).fetchone()
                if test_row is None:
                    raise RuntimeError("failed to reconcile additional test")
                test_ids[test["test_key"]] = test_row[0]

            desired_memberships: set[tuple[int, int]] = set()
            for test in additional_tests_manifest["tests"]:
                test_id = test_ids[test["test_key"]]
                for member in test["hybrids"]:
                    desired_memberships.add((test_id, registry_ids[member["pair_key"]]))
            for test_id, registry_id, active in db.execute(
                "SELECT additional_test_id,hybrid_registry_id,active FROM hybrid_additional_tests"
            ):
                if active == 1 and (test_id, registry_id) not in desired_memberships:
                    db.execute(
                        """
                        UPDATE hybrid_additional_tests
                        SET active=0,updated_at=?
                        WHERE additional_test_id=? AND hybrid_registry_id=?
                        """,
                        (now, test_id, registry_id),
                    )
            for test in additional_tests_manifest["tests"]:
                test_id = test_ids[test["test_key"]]
                for member in test["hybrids"]:
                    registry_id = registry_ids[member["pair_key"]]
                    db.execute(
                        """
                        INSERT INTO hybrid_additional_tests(
                            additional_test_id,hybrid_registry_id,
                            source_hybrid_identifier,source_revision,active,
                            created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?)
                        ON CONFLICT(additional_test_id,hybrid_registry_id) DO UPDATE SET
                            updated_at=CASE
                                WHEN hybrid_additional_tests.source_hybrid_identifier IS NOT excluded.source_hybrid_identifier
                                  OR hybrid_additional_tests.source_revision IS NOT excluded.source_revision
                                  OR hybrid_additional_tests.active != 1
                                THEN excluded.updated_at ELSE hybrid_additional_tests.updated_at END,
                            source_hybrid_identifier=excluded.source_hybrid_identifier,
                            source_revision=excluded.source_revision,
                            active=1
                        """,
                        (
                            test_id,
                            registry_id,
                            member["source_hybrid_identifier"],
                            source_revision,
                            1,
                            now,
                            now,
                        ),
                    )
        db.execute(
            """
            UPDATE comments
            SET hybrid_registry_id = (
                    SELECT alias.hybrid_registry_id
                    FROM hybrid_target_aliases AS alias
                    WHERE alias.target = comments.target
                )
            WHERE hybrid_registry_id IS NULL
              AND target IN (SELECT target FROM hybrid_target_aliases)
            """
        )
        foreign_key_errors = db.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise ValueError(f"database foreign key errors: {foreign_key_errors}")
        integrity_rows = db.execute("PRAGMA integrity_check").fetchall()
        if integrity_rows != [("ok",)]:
            raise ValueError(f"database integrity check failed: {integrity_rows}")
        db.execute("PRAGMA user_version=2")
        db.commit()
    review_publication = static_root / "data/etroc-optical/ETROC_OI_2608/chips.json"
    if review_publication.is_file():
        init_etroc_review_schema(db_path)


def identity(headers) -> dict | None:
    value = headers.get(IDENTITY_HEADER)
    if isinstance(value, str):
        user = canonical_cern_principal(value)
        if user is not None:
            return {
                "user": user,
                "display": value.split("@", 1)[0],
                "is_admin": user in ADMIN_USERS,
            }
    if ALLOW_ANON:
        return {
            "user": "anonymous-local",
            "display": "anonymous-local",
            "is_admin": True,
        }
    return None


def json_response(handler, status: int, payload: dict | list) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def mutation_request_error(
    handler, *, require_json: bool = True
) -> tuple[int, str] | None:
    origin = handler.headers.get("Origin") or ""
    if origin != APP_ORIGIN:
        return 403, "same-origin request required"
    if require_json:
        media_type = (handler.headers.get("Content-Type") or "").split(";", 1)[0]
        if media_type.strip().lower() != "application/json":
            return 415, "application/json required"
    return None


def read_json(handler) -> dict:
    content_length = handler.headers.get("Content-Length")
    if not isinstance(content_length, str) or re.fullmatch(r"[0-9]+", content_length) is None:
        raise ValueError("invalid Content-Length")
    length = int(content_length)
    if length > 10000:
        raise ValueError("request too large")
    raw = handler.rfile.read(length) if length else b"{}"
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise TypeError("JSON object required")
    return data


def _etroc_evidence_identity(static_root: Path) -> tuple[str, tuple[int, int, int, int], tuple[int, int, int, int] | None]:
    root = Path(static_root).resolve()
    publication = root / "data/etroc-optical" / etroc_reviews.DATASET_ID / "chips.json"
    manifest = publication.with_name("SHA256SUMS")
    try:
        publication_stat = publication.stat()
    except FileNotFoundError as exc:
        raise ValueError("ETROC review evidence is unavailable") from exc
    try:
        manifest_stat = manifest.stat()
    except FileNotFoundError:
        manifest_stat = None
    except OSError as exc:
        raise ValueError("ETROC review evidence is unavailable") from exc
    return (
        str(root),
        (publication_stat.st_dev, publication_stat.st_ino, publication_stat.st_size, publication_stat.st_mtime_ns),
        None if manifest_stat is None else (manifest_stat.st_dev, manifest_stat.st_ino, manifest_stat.st_size, manifest_stat.st_mtime_ns),
    )


def reset_etroc_review_evidence_cache() -> None:
    global _ETROC_EVIDENCE_CACHE
    with _ETROC_EVIDENCE_CACHE_LOCK:
        _ETROC_EVIDENCE_CACHE = None


def load_etroc_review_evidence(
    static_root: Path, *, force_revalidate: bool = False
) -> etroc_reviews.EvidenceSet:
    global _ETROC_EVIDENCE_CACHE
    identity = _etroc_evidence_identity(static_root)
    with _ETROC_EVIDENCE_CACHE_LOCK:
        if (
            not force_revalidate
            and _ETROC_EVIDENCE_CACHE is not None
            and _ETROC_EVIDENCE_CACHE[0] == identity
        ):
            return _ETROC_EVIDENCE_CACHE[1]
        _ETROC_EVIDENCE_CACHE = None
        evidence = etroc_reviews.load_evidence(static_root)
        if _etroc_evidence_identity(static_root) != identity:
            _ETROC_EVIDENCE_CACHE = None
            raise ValueError("ETROC review evidence changed while loading")
        _ETROC_EVIDENCE_CACHE = (identity, evidence)
        return evidence


def reset_etroc_position_evidence_cache() -> None:
    global _ETROC_POSITION_EVIDENCE_CACHE
    with _ETROC_POSITION_EVIDENCE_CACHE_LOCK:
        _ETROC_POSITION_EVIDENCE_CACHE = None


def load_etroc_position_evidence(
    static_root: Path, *, force_revalidate: bool = False
) -> etroc_position_reviews.PositionEvidenceSet:
    global _ETROC_POSITION_EVIDENCE_CACHE
    identity = _etroc_evidence_identity(static_root)
    with _ETROC_POSITION_EVIDENCE_CACHE_LOCK:
        if (
            not force_revalidate
            and _ETROC_POSITION_EVIDENCE_CACHE is not None
            and _ETROC_POSITION_EVIDENCE_CACHE[0] == identity
        ):
            return _ETROC_POSITION_EVIDENCE_CACHE[1]
        _ETROC_POSITION_EVIDENCE_CACHE = None
        evidence = etroc_position_reviews.load_evidence(static_root)
        if _etroc_evidence_identity(static_root) != identity:
            raise ValueError("ETROC position evidence changed while loading")
        _ETROC_POSITION_EVIDENCE_CACHE = (identity, evidence)
        return evidence


def init_etroc_position_review_schema(db_path: Path) -> None:
    etroc_position_reviews.init_schema(db_path)


def init_etroc_review_schema(db_path: Path) -> None:
    etroc_reviews.init_schema(db_path)


def initialize_store(
    db_path: Path = DB_PATH,
    static_root: Path = ROOT,
    *,
    require_additional_tests: bool | None = None,
) -> None:
    static_root = Path(static_root)
    bundle = static_root / "data" / "etroc-optical" / etroc_reviews.DATASET_ID
    if bundle.exists():
        if not bundle.is_dir():
            raise ValueError("ETROC review evidence bundle is invalid")
        load_etroc_review_evidence(static_root, force_revalidate=True)
        load_etroc_position_evidence(static_root, force_revalidate=True)
    init_db(
        db_path=db_path,
        static_root=static_root,
        require_additional_tests=require_additional_tests,
    )
    if bundle.exists():
        init_etroc_position_review_schema(db_path)


def append_etroc_review(
    db_path: Path, evidence, request: dict, author: str, author_display: str
):
    return etroc_reviews.append(db_path, evidence, request, author, author_display)


def etroc_error(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


def etroc_query(query: str, allowed: set[str]) -> dict[str, str]:
    if re.search(r"%(?![0-9A-Fa-f]{2})", query):
        raise ValueError("invalid query encoding")
    pairs = urllib.parse.parse_qsl(query, keep_blank_values=True, strict_parsing=True, encoding="utf-8", errors="strict")
    if len(pairs) != len(allowed) or {key for key, _value in pairs} != allowed:
        raise ValueError("invalid query fields")
    result = dict(pairs)
    if any(not value or len(value) > 500 or not value.isprintable() for value in result.values()):
        raise ValueError("invalid query value")
    return result


def etroc_viewer(headers) -> tuple[str, bool, str | None]:
    if not headers.get(IDENTITY_HEADER):
        return "", False, None
    user = identity(headers)
    if not user:
        return "", False, None
    normalized = user["user"].strip().lower()
    return user["display"], normalized in ETROC_REVIEWER_USERS, normalized


def normalize_target(value: str) -> str:
    value = str(value or "").strip()
    if not value or len(value) > 180:
        raise ValueError("invalid target")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:/")
    if any(ch not in allowed for ch in value):
        raise ValueError("invalid target")
    return value


def normalize_status(value: str) -> str:
    value = str(value or "review").strip().lower()
    allowed = {"review", "pass", "fail", "follow-up", "note"}
    if value not in allowed:
        raise ValueError("invalid status")
    return value


def resolve_hybrid_targets(
    db: sqlite3.Connection, targets: list[str]
) -> dict[str, dict]:
    normalized = list(dict.fromkeys(normalize_target(target) for target in targets))
    resolved = {
        target: {"hybrid_registry_id": None, "canonical_target": target}
        for target in normalized
    }
    if not normalized:
        return resolved
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """
        SELECT alias.target AS requested_target, alias.hybrid_registry_id,
               canonical.target AS canonical_target
        FROM hybrid_target_aliases AS alias
        JOIN hybrid_target_aliases AS canonical
          ON canonical.hybrid_registry_id = alias.hybrid_registry_id
         AND canonical.is_canonical = 1
        WHERE alias.target IN (SELECT value FROM json_each(?))
        """,
        (json.dumps(normalized),),
    ).fetchall()
    for row in rows:
        resolved[row["requested_target"]] = {
            "hybrid_registry_id": row["hybrid_registry_id"],
            "canonical_target": row["canonical_target"],
        }
    return resolved


def resolve_hybrid_target(db_path: Path, target: str) -> dict:
    target = normalize_target(target)
    with sqlite3.connect(Path(db_path)) as db:
        return resolve_hybrid_targets(db, [target])[target]


def bind_hybrid(
    db_path: Path,
    *,
    pair_key: str,
    etl_hybrid_id: int | None,
    etl_hybrid_serial: str | None,
    sync_status: str,
    source_revision: str | None = None,
) -> dict:
    pair_key = str(pair_key or "").strip()
    split_pair_key(pair_key)
    sync_status = str(sync_status or "").strip().lower()
    if sync_status not in {"unregistered", "matched", "conflict", "retired"}:
        raise ValueError("invalid sync_status")
    if etl_hybrid_id is not None and (
        type(etl_hybrid_id) is not int or not (1 <= etl_hybrid_id <= 2**63 - 1)
    ):
        raise ValueError("invalid etl_hybrid_id")
    if etl_hybrid_serial is not None and not isinstance(etl_hybrid_serial, str):
        raise ValueError("invalid etl_hybrid_serial")
    etl_hybrid_serial = (etl_hybrid_serial or "").strip() or None
    if etl_hybrid_serial and (
        len(etl_hybrid_serial) > 180 or not etl_hybrid_serial.isprintable()
    ):
        raise ValueError("invalid etl_hybrid_serial")
    if sync_status == "matched" and not etl_hybrid_serial:
        raise ValueError("matched requires etl_hybrid_serial")
    if etl_hybrid_id is None or etl_hybrid_serial is None:
        raise ValueError("complete ETL binding required")
    if sync_status == "unregistered":
        raise ValueError("invalid binding sync_status")
    if source_revision is not None and not isinstance(source_revision, str):
        raise ValueError("invalid source_revision")
    source_revision = (source_revision or "").strip() or None
    if source_revision and (
        len(source_revision) > 500 or not source_revision.isprintable()
    ):
        raise ValueError("invalid source_revision")

    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            """
            SELECT id,etl_hybrid_id,etl_hybrid_serial
            FROM hybrid_registry WHERE pair_key=? AND active=1
            """,
            (pair_key,),
        ).fetchone()
        if not row:
            raise LookupError("unknown pair_key")
        registry_id = row["id"]
        current_id = row["etl_hybrid_id"]
        current_serial = row["etl_hybrid_serial"]
        if (current_id is not None or current_serial is not None) and (
            current_id != etl_hybrid_id or current_serial != etl_hybrid_serial
        ):
            raise ValueError("hybrid already bound")
        conflict = db.execute(
            "SELECT id FROM hybrid_registry WHERE id<>? AND etl_hybrid_id=? LIMIT 1",
            (registry_id, etl_hybrid_id),
        ).fetchone()
        if not conflict:
            conflict = db.execute(
                "SELECT id FROM hybrid_registry WHERE id<>? AND etl_hybrid_serial=? LIMIT 1",
                (registry_id, etl_hybrid_serial),
            ).fetchone()
        if conflict:
            raise ValueError("ETL identity already bound")
        now = int(time.time())
        try:
            db.execute(
                """
                UPDATE hybrid_registry
                SET etl_hybrid_id=?, etl_hybrid_serial=?, sync_status=?,
                    source_revision=COALESCE(?,source_revision), updated_at=?
                WHERE id=?
                """,
                (
                    etl_hybrid_id,
                    etl_hybrid_serial,
                    sync_status,
                    source_revision,
                    now,
                    registry_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("ETL identity already bound") from exc
        updated = db.execute(
            """
            SELECT id,pair_key,etroc_serial,lgad_serial,etl_hybrid_id,
                   etl_hybrid_serial,sync_status,bbqc_url,source_revision,
                   active,created_at,updated_at
            FROM hybrid_registry WHERE id=?
            """,
            (registry_id,),
        ).fetchone()
        db.commit()
    return dict(updated)


def list_hybrids(db_path: Path, pair_key: str | None = None) -> list[dict]:
    if pair_key is not None:
        pair_key = str(pair_key or "").strip()
        split_pair_key(pair_key)
    with sqlite3.connect(Path(db_path)) as db:
        db.row_factory = sqlite3.Row
        if pair_key is None:
            rows = db.execute(
                """
                SELECT id,pair_key,etroc_serial,lgad_serial,etl_hybrid_id,
                       etl_hybrid_serial,sync_status,bbqc_url,source_revision,
                       active,created_at,updated_at
                FROM hybrid_registry WHERE active=1
                ORDER BY pair_key LIMIT 200
                """
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT id,pair_key,etroc_serial,lgad_serial,etl_hybrid_id,
                       etl_hybrid_serial,sync_status,bbqc_url,source_revision,
                       active,created_at,updated_at
                FROM hybrid_registry WHERE active=1 AND pair_key=?
                ORDER BY pair_key LIMIT 200
                """,
                (pair_key,),
            ).fetchall()
        records = [dict(row) for row in rows]
        tests_by_registry: dict[int, list[dict]] = {
            record["id"]: [] for record in records
        }
        if records:
            placeholders = ",".join("?" for _record in records)
            membership_rows = db.execute(
                f"""
                SELECT membership.hybrid_registry_id,test.test_key,
                       test.display_name,membership.source_hybrid_identifier
                FROM hybrid_additional_tests AS membership
                JOIN additional_tests AS test
                  ON test.id=membership.additional_test_id
                WHERE membership.active=1 AND test.active=1
                  AND membership.hybrid_registry_id IN ({placeholders})
                ORDER BY membership.hybrid_registry_id,test.test_key
                """,
                tuple(record["id"] for record in records),
            ).fetchall()
            for membership in membership_rows:
                tests_by_registry[membership["hybrid_registry_id"]].append(
                    {
                        "test_key": membership["test_key"],
                        "display_name": membership["display_name"],
                        "source_hybrid_identifier": membership[
                            "source_hybrid_identifier"
                        ],
                    }
                )
    for record in records:
        record["additional_tests"] = tests_by_registry[record["id"]]
    return records


class Handler(SimpleHTTPRequestHandler):
    server_version = "ETLHybridBBQC/0.2"

    def translate_path(self, path: str) -> str:
        parsed = urllib.parse.urlparse(path)
        clean = parsed.path.lstrip("/") or "index.html"
        full = (ROOT / clean).resolve()
        if ROOT not in full.parents and full != ROOT:
            return str(ROOT / "index.html")
        if full.is_dir():
            full = full / "index.html"
        return str(full)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}", flush=True)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/etroc-position-reviews"):
            display, allowed, user = etroc_viewer(self.headers)
            if user is None:
                return json_response(self, 401, etroc_error("authentication_required", "CERN SSO login is required."))
            if parsed.path == "/api/etroc-position-reviews":
                try:
                    query = etroc_query(parsed.query, {"dataset_id", "acquisition_id"})
                except ValueError:
                    return json_response(self, 400, etroc_error("invalid_query", "The query is invalid."))
                try:
                    evidence = load_etroc_position_evidence(ROOT)
                except (OSError, ValueError):
                    return json_response(self, 503, etroc_error("evidence_unavailable", "Current ETROC position evidence is unavailable."))
                if query["dataset_id"] != evidence.dataset_id:
                    return json_response(self, 404, etroc_error("dataset_not_found", "The dataset is not available."))
                try:
                    payload = etroc_position_reviews.summary(DB_PATH, evidence, query["acquisition_id"], display, allowed)
                except KeyError:
                    return json_response(self, 404, etroc_error("acquisition_not_found", "The acquisition is not in the current publication."))
                except sqlite3.DatabaseError:
                    return json_response(self, 503, etroc_error("review_store_unavailable", "The position review store is unavailable."))
                return json_response(self, 200, payload)
            if parsed.path == "/api/etroc-position-reviews/audit":
                try:
                    query = etroc_query(parsed.query, {"acquisition_id", "position"})
                    if re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", query["position"]) is None:
                        raise ValueError("invalid position")
                    position = int(query["position"])
                    if position > 255:
                        raise ValueError("invalid position")
                except ValueError:
                    return json_response(self, 400, etroc_error("invalid_query", "The query is invalid."))
                try:
                    evidence = load_etroc_position_evidence(ROOT)
                except (OSError, ValueError):
                    evidence = None
                try:
                    result = etroc_position_reviews.audit(DB_PATH, query["acquisition_id"], position, evidence)
                except sqlite3.DatabaseError:
                    return json_response(self, 503, etroc_error("review_store_unavailable", "The position review store is unavailable."))
                return json_response(self, result.status, result.payload)
            if parsed.path == "/api/etroc-position-reviews/history":
                try:
                    query = etroc_query(parsed.query, {"acquisition_id", "position"})
                    if re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", query["position"]) is None:
                        raise ValueError("invalid position")
                    position = int(query["position"])
                    if position > 255:
                        raise ValueError("invalid position")
                except ValueError:
                    return json_response(self, 400, etroc_error("invalid_query", "The query is invalid."))
                try:
                    evidence = load_etroc_position_evidence(ROOT)
                    result = etroc_position_reviews.history(DB_PATH, evidence, query["acquisition_id"], position)
                except (OSError, ValueError):
                    return json_response(self, 503, etroc_error("evidence_unavailable", "Current ETROC position evidence is unavailable."))
                except sqlite3.DatabaseError:
                    return json_response(self, 503, etroc_error("review_store_unavailable", "The position review store is unavailable."))
                return json_response(self, result.status, result.payload)
            return json_response(self, 404, etroc_error("position_not_found", "The ETROC position review endpoint is not available."))
        if parsed.path.startswith("/api/etroc-reviews"):
            display, allowed, user = etroc_viewer(self.headers)
            if user is None:
                return json_response(self, 401, etroc_error("authentication_required", "CERN SSO login is required."))
            if parsed.path == "/api/etroc-reviews/audit":
                try:
                    acquisition_id = etroc_query(parsed.query, {"acquisition_id"})["acquisition_id"]
                except ValueError:
                    return json_response(self, 400, etroc_error("invalid_query", "The query is invalid."))
                try:
                    evidence = load_etroc_review_evidence(ROOT)
                except (OSError, ValueError):
                    return json_response(self, 503, etroc_error("evidence_unavailable", "Current ETROC review evidence is unavailable."))
                try:
                    result = etroc_reviews.audit(DB_PATH, acquisition_id, evidence)
                except sqlite3.DatabaseError:
                    return json_response(self, 503, etroc_error("review_store_unavailable", "The review store is unavailable."))
                return json_response(self, result.status, result.payload)
            if parsed.path == "/api/etroc-reviews":
                try:
                    dataset_id = etroc_query(parsed.query, {"dataset_id"})["dataset_id"]
                except ValueError:
                    return json_response(self, 400, etroc_error("invalid_query", "The query is invalid."))
                try:
                    evidence = load_etroc_review_evidence(ROOT)
                except (OSError, ValueError):
                    return json_response(self, 503, etroc_error("evidence_unavailable", "Current ETROC review evidence is unavailable."))
                if dataset_id != evidence.dataset_id:
                    return json_response(self, 404, etroc_error("dataset_not_found", "The dataset is not available."))
                try:
                    return json_response(self, 200, etroc_reviews.summary(DB_PATH, evidence, display, allowed))
                except sqlite3.DatabaseError:
                    return json_response(self, 503, etroc_error("review_store_unavailable", "The review store is unavailable."))
            if parsed.path == "/api/etroc-reviews/history":
                try:
                    acquisition_id = etroc_query(parsed.query, {"acquisition_id"})["acquisition_id"]
                except ValueError:
                    return json_response(self, 400, etroc_error("invalid_query", "The query is invalid."))
                try:
                    evidence = load_etroc_review_evidence(ROOT)
                except (OSError, ValueError):
                    return json_response(self, 503, etroc_error("evidence_unavailable", "Current ETROC review evidence is unavailable."))
                try:
                    result = etroc_reviews.history(DB_PATH, evidence, acquisition_id)
                except sqlite3.DatabaseError:
                    return json_response(self, 503, etroc_error("review_store_unavailable", "The review store is unavailable."))
                return json_response(self, result.status, result.payload)
            return json_response(self, 404, etroc_error("acquisition_not_found", "The ETROC review endpoint is not available."))
        if parsed.path == "/api/health":
            return json_response(self, 200, {"ok": True})
        if parsed.path == "/api/me":
            user = identity(self.headers)
            return json_response(self, 200, {"authenticated": bool(user), "user": user})
        if parsed.path == "/api/hybrids":
            qs = urllib.parse.parse_qs(parsed.query)
            pair_key = qs.get("pair_key", [None])[0]
            try:
                records = list_hybrids(DB_PATH, pair_key=pair_key)
            except ValueError as e:
                return json_response(self, 400, {"error": str(e)})
            return json_response(self, 200, {"count": len(records), "records": records})
        if parsed.path == "/api/comments/summary":
            qs = urllib.parse.parse_qs(parsed.query)
            raw_targets = qs.get("target", [])
            if not raw_targets and qs.get("targets"):
                raw_targets = ",".join(qs.get("targets", [])).split(",")
            try:
                targets = [normalize_target(x) for x in raw_targets if str(x).strip()]
            except ValueError as e:
                return json_response(self, 400, {"error": str(e)})
            targets = list(dict.fromkeys(targets))[:200]
            if not targets:
                return json_response(self, 200, {})
            with sqlite3.connect(DB_PATH) as db:
                db.row_factory = sqlite3.Row
                resolved = resolve_hybrid_targets(db, targets)
                registry_ids = sorted(
                    {
                        item["hybrid_registry_id"]
                        for item in resolved.values()
                        if item["hybrid_registry_id"] is not None
                    }
                )
                plain_targets = [
                    target
                    for target, item in resolved.items()
                    if item["hybrid_registry_id"] is None
                ]
                registry_summary: dict = {
                    registry_id: {"count": 0, "latest": None}
                    for registry_id in registry_ids
                }
                plain_summary: dict = {
                    target: {"count": 0, "latest": None} for target in plain_targets
                }
                if registry_ids:
                    registry_json = json.dumps(registry_ids)
                    latest_rows = db.execute(
                        """
                        WITH ranked AS (
                            SELECT id,target,body,status,author_display,
                                   created_at,updated_at,hybrid_registry_id,
                                   COUNT(*) OVER (
                                       PARTITION BY hybrid_registry_id
                                   ) AS comment_count,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY hybrid_registry_id
                                       ORDER BY created_at DESC,id DESC
                                   ) AS row_number
                            FROM comments
                            WHERE deleted=0 AND hybrid_registry_id IN (
                                SELECT value FROM json_each(?)
                            )
                        )
                        SELECT id,target,body,status,author_display,created_at,
                               updated_at,hybrid_registry_id,comment_count
                        FROM ranked WHERE row_number=1
                        """,
                        (registry_json,),
                    ).fetchall()
                    for row in latest_rows:
                        item = dict(row)
                        registry_id = item.pop("hybrid_registry_id")
                        count = item.pop("comment_count")
                        registry_summary[registry_id] = {
                            "count": count,
                            "latest": item,
                        }
                if plain_targets:
                    plain_json = json.dumps(plain_targets)
                    latest_rows = db.execute(
                        """
                        WITH ranked AS (
                            SELECT id,target,body,status,author_display,
                                   created_at,updated_at,
                                   COUNT(*) OVER (
                                       PARTITION BY target
                                   ) AS comment_count,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY target
                                       ORDER BY created_at DESC,id DESC
                                   ) AS row_number
                            FROM comments
                            WHERE deleted=0 AND hybrid_registry_id IS NULL
                              AND target IN (SELECT value FROM json_each(?))
                        )
                        SELECT id,target,body,status,author_display,created_at,
                               updated_at,comment_count
                        FROM ranked WHERE row_number=1
                        """,
                        (plain_json,),
                    ).fetchall()
                    for row in latest_rows:
                        item = dict(row)
                        target = item["target"]
                        count = item.pop("comment_count")
                        plain_summary[target] = {"count": count, "latest": item}
            summary = {}
            for requested, resolution in resolved.items():
                registry_id = resolution["hybrid_registry_id"]
                source = (
                    registry_summary[registry_id]
                    if registry_id is not None
                    else plain_summary[requested]
                )
                latest_value = source["latest"]
                latest = latest_value.copy() if isinstance(latest_value, dict) else None
                if latest is not None and registry_id is not None:
                    latest["target"] = resolution["canonical_target"]
                summary[requested] = {"count": source["count"], "latest": latest}
            return json_response(self, 200, summary)
        if parsed.path == "/api/comments":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                target = normalize_target(qs.get("target", [""])[0])
            except ValueError as e:
                return json_response(self, 400, {"error": str(e)})
            requested_target = target
            user = identity(self.headers)
            with sqlite3.connect(DB_PATH) as db:
                db.row_factory = sqlite3.Row
                resolution = resolve_hybrid_targets(db, [requested_target])[
                    requested_target
                ]
                registry_id = resolution["hybrid_registry_id"]
                canonical_target = resolution["canonical_target"]
                if registry_id is None:
                    rows = db.execute(
                        """
                        SELECT id,target,body,status,author,author_display,created_at,updated_at
                        FROM comments
                        WHERE target=? AND hybrid_registry_id IS NULL AND deleted=0
                        ORDER BY created_at DESC LIMIT 100
                        """,
                        (requested_target,),
                    ).fetchall()
                else:
                    rows = db.execute(
                        """
                        SELECT id,target,body,status,author,author_display,created_at,updated_at
                        FROM comments
                        WHERE deleted=0 AND (
                            hybrid_registry_id=? OR (
                                hybrid_registry_id IS NULL AND target IN (
                                    SELECT target FROM hybrid_target_aliases
                                    WHERE hybrid_registry_id=?
                                )
                            )
                        )
                        ORDER BY created_at DESC LIMIT 100
                        """,
                        (registry_id, registry_id),
                    ).fetchall()
            payload = []
            for row in rows:
                item = dict(row)
                if registry_id is not None:
                    item["target"] = canonical_target
                item["can_edit"] = bool(
                    user
                    and (item.get("author") == user["user"] or user.get("is_admin"))
                )
                item.pop("author", None)
                payload.append(item)
            return json_response(self, 200, payload)
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/etroc-position-reviews":
            display, allowed, user = etroc_viewer(self.headers)
            if user is None:
                return json_response(self, 401, etroc_error("authentication_required", "CERN SSO login is required."))
            if not allowed:
                return json_response(self, 403, etroc_error("review_not_authorized", "This identity cannot append ETROC position reviews."))
            if (self.headers.get("Origin") or "") != APP_ORIGIN:
                return json_response(self, 403, etroc_error("same_origin_required", "A same-origin request is required."))
            content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return json_response(self, 415, etroc_error("json_required", "An application/json request is required."))
            try:
                request = read_json(self)
            except (TypeError, ValueError, json.JSONDecodeError):
                return json_response(self, 400, etroc_error("invalid_json", "The request body must be a JSON object."))
            request_error = etroc_position_reviews.validate_request(request)
            if request_error is not None:
                return json_response(self, request_error.status, request_error.payload)
            try:
                result = etroc_position_reviews.append(
                    DB_PATH,
                    lambda: load_etroc_position_evidence(ROOT, force_revalidate=True),
                    request,
                    user,
                    display,
                )
            except (OSError, ValueError):
                return json_response(self, 503, etroc_error("evidence_unavailable", "Current ETROC position evidence is unavailable."))
            except sqlite3.DatabaseError:
                return json_response(self, 503, etroc_error("review_store_unavailable", "The position review store is unavailable."))
            return json_response(self, result.status, result.payload)
        if parsed.path == "/api/etroc-reviews":
            display, allowed, user = etroc_viewer(self.headers)
            if user is None:
                return json_response(self, 401, etroc_error("authentication_required", "CERN SSO login is required."))
            if not allowed:
                return json_response(self, 403, etroc_error("review_not_authorized", "This identity cannot append ETROC reviews."))
            origin = self.headers.get("Origin") or ""
            if origin != APP_ORIGIN:
                return json_response(self, 403, etroc_error("same_origin_required", "A same-origin request is required."))
            content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return json_response(self, 415, etroc_error("json_required", "An application/json request is required."))
            try:
                request = read_json(self)
            except (TypeError, ValueError, json.JSONDecodeError):
                return json_response(self, 400, etroc_error("invalid_json", "The request body must be a JSON object."))
            request_error = etroc_reviews.validate_request(request)
            if request_error is not None:
                return json_response(self, request_error.status, request_error.payload)
            try:
                result = etroc_reviews.append(DB_PATH, lambda: load_etroc_review_evidence(ROOT, force_revalidate=True), request, user, display)
            except (OSError, ValueError):
                return json_response(self, 503, etroc_error("evidence_unavailable", "Current ETROC review evidence is unavailable."))
            except sqlite3.DatabaseError:
                return json_response(self, 503, etroc_error("review_store_unavailable", "The review store is unavailable."))
            return json_response(self, result.status, result.payload)
        if parsed.path == "/api/hybrids/bind":
            user = identity(self.headers)
            if not user:
                return json_response(self, 401, {"error": "CERN SSO login required"})
            if not user["is_admin"]:
                return json_response(self, 403, {"error": "admin required"})
            request_error = mutation_request_error(self)
            if request_error:
                status, message = request_error
                return json_response(self, status, {"error": message})
            try:
                data = read_json(self)
                required_fields = {
                    "pair_key",
                    "etl_hybrid_id",
                    "etl_hybrid_serial",
                    "sync_status",
                }
                missing_fields = sorted(required_fields - data.keys())
                if missing_fields:
                    raise ValueError(
                        f"missing required fields: {','.join(missing_fields)}"
                    )
                row = bind_hybrid(
                    DB_PATH,
                    pair_key=data["pair_key"],
                    etl_hybrid_id=data["etl_hybrid_id"],
                    etl_hybrid_serial=data["etl_hybrid_serial"],
                    sync_status=data["sync_status"],
                    source_revision=data.get("source_revision"),
                )
            except LookupError as e:
                return json_response(self, 404, {"error": str(e)})
            except (TypeError, ValueError, json.JSONDecodeError) as e:
                return json_response(self, 400, {"error": str(e)})
            return json_response(self, 200, row)
        if parsed.path != "/api/comments":
            return json_response(self, 404, {"error": "not found"})
        user = identity(self.headers)
        if not user:
            return json_response(self, 401, {"error": "CERN SSO login required"})
        request_error = mutation_request_error(self)
        if request_error:
            status, message = request_error
            return json_response(self, status, {"error": message})
        try:
            data = read_json(self)
            target = normalize_target(data.get("target", ""))
            requested_target = target
            resolved_target = resolve_hybrid_target(DB_PATH, target)
            canonical_target = resolved_target["canonical_target"]
            hybrid_registry_id = resolved_target["hybrid_registry_id"]
            body = str(data.get("body", "")).strip()
            status = normalize_status(data.get("status", "review"))
            if not body:
                raise ValueError("empty comment")
            if len(body) > MAX_BODY:
                raise ValueError(f"comment too long; max {MAX_BODY} chars")
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            return json_response(self, 400, {"error": str(e)})
        now = int(time.time())
        with sqlite3.connect(DB_PATH) as db:
            db.execute("PRAGMA foreign_keys=ON")
            cur = db.execute(
                """
                INSERT INTO comments(
                    target,body,status,author,author_display,created_at,updated_at,hybrid_registry_id
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    requested_target,
                    body,
                    status,
                    user["user"],
                    user["display"],
                    now,
                    now,
                    hybrid_registry_id,
                ),
            )
            cid = cur.lastrowid
            db.commit()
        return json_response(
            self,
            201,
            {
                "id": cid,
                "target": canonical_target,
                "body": body,
                "status": status,
                "author_display": user["display"],
                "created_at": now,
                "updated_at": now,
            },
        )

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/comments/"):
            return json_response(self, 404, {"error": "not found"})
        user = identity(self.headers)
        if not user:
            return json_response(self, 401, {"error": "CERN SSO login required"})
        request_error = mutation_request_error(self)
        if request_error:
            status, message = request_error
            return json_response(self, status, {"error": message})
        try:
            cid = int(parsed.path.rsplit("/", 1)[-1])
            data = read_json(self)
            body = str(data.get("body", "")).strip()
            status = normalize_status(data.get("status", "review"))
            if not body:
                raise ValueError("empty comment")
            if len(body) > MAX_BODY:
                raise ValueError(f"comment too long; max {MAX_BODY} chars")
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            return json_response(self, 400, {"error": str(e)})
        now = int(time.time())
        with sqlite3.connect(DB_PATH) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT id,target,author,author_display,created_at FROM comments WHERE id=? AND deleted=0",
                (cid,),
            ).fetchone()
            if not row:
                return json_response(self, 404, {"error": "not found"})
            if row["author"] != user["user"] and not user["is_admin"]:
                return json_response(self, 403, {"error": "not allowed"})
            db.execute(
                "UPDATE comments SET body=?, status=?, updated_at=? WHERE id=?",
                (body, status, now, cid),
            )
            db.commit()
            item = dict(row)
        return json_response(
            self,
            200,
            {
                "id": cid,
                "target": item["target"],
                "body": body,
                "status": status,
                "author_display": item["author_display"],
                "created_at": item["created_at"],
                "updated_at": now,
                "can_edit": True,
            },
        )

    def do_PUT(self):
        return self.do_PATCH()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/comments/"):
            return json_response(self, 404, {"error": "not found"})
        user = identity(self.headers)
        if not user:
            return json_response(self, 401, {"error": "CERN SSO login required"})
        request_error = mutation_request_error(self, require_json=False)
        if request_error:
            status, message = request_error
            return json_response(self, status, {"error": message})
        try:
            cid = int(parsed.path.rsplit("/", 1)[-1])
        except ValueError:
            return json_response(self, 400, {"error": "invalid comment id"})
        with sqlite3.connect(DB_PATH) as db:
            row = db.execute(
                "SELECT author FROM comments WHERE id=? AND deleted=0", (cid,)
            ).fetchone()
            if not row:
                return json_response(self, 404, {"error": "not found"})
            if row[0] != user["user"] and not user["is_admin"]:
                return json_response(self, 403, {"error": "not allowed"})
            db.execute(
                "UPDATE comments SET deleted=1, updated_at=? WHERE id=?",
                (int(time.time()), cid),
            )
            db.commit()
        return json_response(self, 200, {"ok": True})


if __name__ == "__main__":
    initialize_store()
    port = int(os.environ.get("PORT", "8080"))
    print(
        f"BBQC_STARTUP_OK root={ROOT} host={HOST} port={port} "
        f"db={DB_PATH} allow_anon={ALLOW_ANON}",
        flush=True,
    )
    ThreadingHTTPServer((HOST, port), Handler).serve_forever()
