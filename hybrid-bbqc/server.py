from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("STATIC_ROOT", "/app/static")).resolve()
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
MAX_BODY = int(os.environ.get("COMMENTS_MAX_BODY", "2000"))
HOST = os.environ.get("HOST", "127.0.0.1")
APP_ORIGIN = os.environ.get("APP_ORIGIN", "https://etl-hybrid-bbqc.app.cern.ch").rstrip(
    "/"
)
PAIR_PATH_RE = re.compile(r"hybrids/([A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+)\.html")
REDIRECT_RE = re.compile(r"url=([^\"' >;]+)\.html", re.IGNORECASE)


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


IDENTITY_HEADER = "X-Forwarded-Email"


def init_db(db_path: Path = DB_PATH, static_root: Path = ROOT) -> None:
    db_path = Path(db_path)
    static_root = Path(static_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
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
        comment_columns = {row[1] for row in db.execute("PRAGMA table_info(comments)")}
        if "hybrid_registry_id" not in comment_columns:
            db.execute(
                "ALTER TABLE comments ADD COLUMN hybrid_registry_id INTEGER REFERENCES hybrid_registry(id)"
            )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_comments_hybrid_registry ON comments(hybrid_registry_id,deleted,created_at)"
        )

        now = int(time.time())
        canonical_pairs = discover_canonical_pairs(static_root)
        if not canonical_pairs:
            raise ValueError("no canonical hybrid pairs found in static dashboard")
        canonical_pair_set = set(canonical_pairs)
        redirect_aliases = discover_redirect_aliases(static_root, canonical_pair_set)
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
                    WHERE id=?
                    """,
                    (
                        pair_key,
                        etroc_serial,
                        lgad_serial,
                        f"/hybrids/{pair_key}.html",
                        now,
                        registry_id,
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
        db.commit()


def identity(headers) -> dict | None:
    value = headers.get(IDENTITY_HEADER)
    if value and "," not in value:
        raw = value.strip()
        if raw:
            user = raw.lower()
            display = raw.split("@")[0]
            return {
                "user": user,
                "display": display,
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
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length > 10000:
        raise ValueError("request too large")
    raw = handler.rfile.read(length) if length else b"{}"
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise TypeError("JSON object required")
    return data


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
    return [dict(row) for row in rows]


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
                registry_summary = {
                    registry_id: {"count": 0, "latest": None}
                    for registry_id in registry_ids
                }
                plain_summary = {
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
                latest = dict(source["latest"]) if source["latest"] else None
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
    init_db()
    port = int(os.environ.get("PORT", "8080"))
    print(
        f"BBQC_STARTUP_OK root={ROOT} host={HOST} port={port} "
        f"db={DB_PATH} allow_anon={ALLOW_ANON}",
        flush=True,
    )
    ThreadingHTTPServer((HOST, port), Handler).serve_forever()
