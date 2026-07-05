#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("STATIC_ROOT", "/app/static")).resolve()
DB_PATH = Path(os.environ.get("COMMENTS_DB", "/data/comments.sqlite3"))
ALLOW_ANON = os.environ.get("COMMENTS_ALLOW_ANON", "false").lower() in {"1", "true", "yes"}
ADMIN_USERS = {x.strip().lower() for x in os.environ.get("COMMENTS_ADMIN_USERS", "").split(",") if x.strip()}
MAX_BODY = int(os.environ.get("COMMENTS_MAX_BODY", "2000"))

IDENTITY_HEADERS = [
    "X-Forwarded-Email", "X-Auth-Request-Email", "X-Remote-User",
    "X-Forwarded-User", "X-Forwarded-Preferred-Username", "OIDC_CLAIM_email",
]


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
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
        db.execute("CREATE INDEX IF NOT EXISTS idx_comments_target ON comments(target, deleted, created_at)")


def identity(headers) -> dict | None:
    for name in IDENTITY_HEADERS:
        value = headers.get(name)
        if value:
            raw = value.split(",")[0].strip()
            if raw:
                user = raw.lower()
                display = raw.split("@")[0]
                return {"user": user, "display": display, "is_admin": user in ADMIN_USERS}
    if ALLOW_ANON:
        return {"user": "anonymous-local", "display": "anonymous-local", "is_admin": True}
    return None


def json_response(handler, status: int, payload: dict | list) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length > 10000:
        raise ValueError("request too large")
    data = handler.rfile.read(length) if length else b"{}"
    return json.loads(data.decode("utf-8"))


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


class Handler(SimpleHTTPRequestHandler):
    server_version = "ETLHybridBBQC/0.1"

    def translate_path(self, path: str) -> str:
        parsed = urllib.parse.urlparse(path)
        clean = parsed.path.lstrip("/") or "index.html"
        full = (ROOT / clean).resolve()
        if ROOT not in full.parents and full != ROOT:
            return str(ROOT / "index.html")
        if full.is_dir():
            full = full / "index.html"
        return str(full)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            return json_response(self, 200, {"ok": True})
        if parsed.path == "/api/me":
            user = identity(self.headers)
            return json_response(self, 200, {"authenticated": bool(user), "user": user})
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
            placeholders = ",".join("?" for _ in targets)
            summary = {target: {"count": 0, "latest": None} for target in targets}
            with sqlite3.connect(DB_PATH) as db:
                db.row_factory = sqlite3.Row
                counts = db.execute(
                    f"SELECT target,COUNT(*) AS count FROM comments WHERE deleted=0 AND target IN ({placeholders}) GROUP BY target",
                    targets,
                ).fetchall()
                latest = db.execute(
                    f"""
                    SELECT id,target,body,status,author_display,created_at,updated_at
                    FROM comments
                    WHERE deleted=0 AND target IN ({placeholders})
                    ORDER BY target, created_at DESC, id DESC
                    """,
                    targets,
                ).fetchall()
            for row in counts:
                summary[row["target"]]["count"] = row["count"]
            seen = set()
            for row in latest:
                target = row["target"]
                if target in seen:
                    continue
                seen.add(target)
                summary[target]["latest"] = dict(row)
            return json_response(self, 200, summary)
        if parsed.path == "/api/comments":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                target = normalize_target(qs.get("target", [""])[0])
            except ValueError as e:
                return json_response(self, 400, {"error": str(e)})
            user = identity(self.headers)
            with sqlite3.connect(DB_PATH) as db:
                db.row_factory = sqlite3.Row
                rows = db.execute(
                    "SELECT id,target,body,status,author,author_display,created_at,updated_at FROM comments WHERE target=? AND deleted=0 ORDER BY created_at DESC LIMIT 100",
                    (target,),
                ).fetchall()
            payload = []
            for row in rows:
                item = dict(row)
                item["can_edit"] = bool(user and (item.get("author") == user["user"] or user.get("is_admin")))
                item.pop("author", None)
                payload.append(item)
            return json_response(self, 200, payload)
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/comments":
            return json_response(self, 404, {"error": "not found"})
        user = identity(self.headers)
        if not user:
            return json_response(self, 401, {"error": "CERN SSO login required"})
        try:
            data = read_json(self)
            target = normalize_target(data.get("target", ""))
            body = str(data.get("body", "")).strip()
            status = normalize_status(data.get("status", "review"))
            if not body:
                raise ValueError("empty comment")
            if len(body) > MAX_BODY:
                raise ValueError(f"comment too long; max {MAX_BODY} chars")
        except (ValueError, json.JSONDecodeError) as e:
            return json_response(self, 400, {"error": str(e)})
        now = int(time.time())
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute(
                "INSERT INTO comments(target, body, status, author, author_display, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
                (target, body, status, user["user"], user["display"], now, now),
            )
            cid = cur.lastrowid
            db.commit()
        return json_response(self, 201, {"id": cid, "target": target, "body": body, "status": status, "author_display": user["display"], "created_at": now, "updated_at": now})

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/comments/"):
            return json_response(self, 404, {"error": "not found"})
        user = identity(self.headers)
        if not user:
            return json_response(self, 401, {"error": "CERN SSO login required"})
        try:
            cid = int(parsed.path.rsplit("/", 1)[-1])
            data = read_json(self)
            body = str(data.get("body", "")).strip()
            status = normalize_status(data.get("status", "review"))
            if not body:
                raise ValueError("empty comment")
            if len(body) > MAX_BODY:
                raise ValueError(f"comment too long; max {MAX_BODY} chars")
        except (ValueError, json.JSONDecodeError) as e:
            return json_response(self, 400, {"error": str(e)})
        now = int(time.time())
        with sqlite3.connect(DB_PATH) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT id,target,author,author_display,created_at FROM comments WHERE id=? AND deleted=0", (cid,)).fetchone()
            if not row:
                return json_response(self, 404, {"error": "not found"})
            if row["author"] != user["user"] and not user["is_admin"]:
                return json_response(self, 403, {"error": "not allowed"})
            db.execute("UPDATE comments SET body=?, status=?, updated_at=? WHERE id=?", (body, status, now, cid))
            db.commit()
            item = dict(row)
        return json_response(self, 200, {
            "id": cid, "target": item["target"], "body": body, "status": status,
            "author_display": item["author_display"], "created_at": item["created_at"],
            "updated_at": now, "can_edit": True,
        })

    def do_PUT(self):
        return self.do_PATCH()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/comments/"):
            return json_response(self, 404, {"error": "not found"})
        user = identity(self.headers)
        if not user:
            return json_response(self, 401, {"error": "CERN SSO login required"})
        try:
            cid = int(parsed.path.rsplit("/", 1)[-1])
        except ValueError:
            return json_response(self, 400, {"error": "invalid comment id"})
        with sqlite3.connect(DB_PATH) as db:
            row = db.execute("SELECT author FROM comments WHERE id=? AND deleted=0", (cid,)).fetchone()
            if not row:
                return json_response(self, 404, {"error": "not found"})
            if row[0] != user["user"] and not user["is_admin"]:
                return json_response(self, 403, {"error": "not allowed"})
            db.execute("UPDATE comments SET deleted=1, updated_at=? WHERE id=?", (int(time.time()), cid))
            db.commit()
        return json_response(self, 200, {"ok": True})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "8080"))
    print(f"Serving {ROOT} with comments API on :{port}; db={DB_PATH}; allow_anon={ALLOW_ANON}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
