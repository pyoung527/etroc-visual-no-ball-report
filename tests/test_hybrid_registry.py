import importlib.util
import json
import re
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "hybrid-bbqc" / "server.py"


def load_server_module() -> Any:
    spec = importlib.util.spec_from_file_location("bbqc_server_under_test", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_legacy_comments_db(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute(
            """
            CREATE TABLE comments (
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
            """
        )
        db.execute(
            """
            INSERT INTO comments(target,body,status,author,author_display,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                "hybrid:ET-OLD__LG-OLD",
                "legacy comment",
                "review",
                "ypark",
                "ypark",
                1,
                1,
            ),
        )
        db.commit()


def create_static_site(root: Path) -> None:
    (root / "hybrids").mkdir(parents=True)
    (root / "index.html").write_text(
        """
        <a href="hybrids/ET-1__LG-1.html">first</a>
        <tr onclick="location.href='hybrids/ET-2__LG-2.html'"></tr>
        """,
        encoding="utf-8",
    )
    (root / "hybrids" / "ET-1__LG-1.html").write_text("canonical", encoding="utf-8")
    (root / "hybrids" / "ET-2__LG-2.html").write_text("canonical", encoding="utf-8")
    (root / "hybrids" / "ET-OLD__LG-OLD.html").write_text(
        """
        <meta http-equiv="refresh" content="0; url=ET-1__LG-1.html">
        <link rel="canonical" href="ET-1__LG-1.html">
        """,
        encoding="utf-8",
    )


class HybridRegistryMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.db_path = base / "comments.sqlite3"
        self.static_root = base / "static"
        create_legacy_comments_db(self.db_path)
        create_static_site(self.static_root)
        self.server = load_server_module()

    def test_init_db_seeds_registry_aliases_and_backfills_legacy_comments(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            registry = db.execute(
                "SELECT id,pair_key,etroc_serial,lgad_serial,sync_status,bbqc_url FROM hybrid_registry ORDER BY pair_key"
            ).fetchall()
            aliases = db.execute(
                "SELECT target,hybrid_registry_id,is_canonical FROM hybrid_target_aliases ORDER BY target"
            ).fetchall()
            comment = db.execute(
                "SELECT target,hybrid_registry_id FROM comments WHERE body='legacy comment'"
            ).fetchone()
            comment_columns = {
                row[1] for row in db.execute("PRAGMA table_info(comments)").fetchall()
            }

        self.assertEqual(
            [row["pair_key"] for row in registry], ["ET-1__LG-1", "ET-2__LG-2"]
        )
        self.assertEqual(registry[0]["etroc_serial"], "ET-1")
        self.assertEqual(registry[0]["lgad_serial"], "LG-1")
        self.assertEqual(registry[0]["sync_status"], "unregistered")
        self.assertEqual(registry[0]["bbqc_url"], "/hybrids/ET-1__LG-1.html")

        alias_map = {row["target"]: row for row in aliases}
        self.assertEqual(alias_map["hybrid:ET-1__LG-1"]["is_canonical"], 1)
        self.assertEqual(alias_map["hybrid:ET-2__LG-2"]["is_canonical"], 1)
        self.assertEqual(alias_map["hybrid:ET-OLD__LG-OLD"]["is_canonical"], 0)
        self.assertEqual(
            alias_map["hybrid:ET-OLD__LG-OLD"]["hybrid_registry_id"],
            alias_map["hybrid:ET-1__LG-1"]["hybrid_registry_id"],
        )

        self.assertIn("hybrid_registry_id", comment_columns)
        self.assertEqual(comment["target"], "hybrid:ET-OLD__LG-OLD")
        self.assertEqual(
            comment["hybrid_registry_id"],
            alias_map["hybrid:ET-1__LG-1"]["hybrid_registry_id"],
        )

    def test_init_db_is_idempotent(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            registry_count = db.execute(
                "SELECT COUNT(*) FROM hybrid_registry"
            ).fetchone()[0]
            alias_count = db.execute(
                "SELECT COUNT(*) FROM hybrid_target_aliases"
            ).fetchone()[0]
            comment_count = db.execute("SELECT COUNT(*) FROM comments").fetchone()[0]

        self.assertEqual(registry_count, 2)
        self.assertEqual(alias_count, 3)
        self.assertEqual(comment_count, 1)

    def test_init_db_rejects_duplicate_active_child_assignments(self):
        duplicate_cases = {
            "ETROC": ["ET-1__LG-1", "ET-1__LG-9"],
            "LGAD": ["ET-1__LG-1", "ET-9__LG-1"],
        }
        for child, pairs in duplicate_cases.items():
            with self.subTest(child=child):
                (self.static_root / "index.html").write_text(
                    "\n".join(
                        f'<a href="hybrids/{pair}.html">pair</a>' for pair in pairs
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, f"duplicate active {child}"):
                    self.server.init_db(
                        db_path=self.db_path, static_root=self.static_root
                    )

    def test_init_db_rejects_missing_or_empty_dashboard(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        (self.static_root / "index.html").write_text("no pair links", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "no canonical hybrid pairs"):
            self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            active_count = db.execute(
                "SELECT COUNT(*) FROM hybrid_registry WHERE active=1"
            ).fetchone()[0]
        self.assertEqual(active_count, 2)

    def test_pair_correction_preserves_registry_id_etl_binding_and_comments(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        bound = self.server.bind_hybrid(
            self.db_path,
            pair_key="ET-1__LG-1",
            etl_hybrid_id=12345,
            etl_hybrid_serial="ETL-STABLE-1",
            sync_status="matched",
            source_revision="before-correction",
        )
        stable_id = bound["id"]

        (self.static_root / "index.html").write_text(
            """
            <a href="hybrids/ET-1__LG-9.html">corrected</a>
            <a href="hybrids/ET-2__LG-2.html">second</a>
            """,
            encoding="utf-8",
        )
        (self.static_root / "hybrids" / "ET-1__LG-1.html").write_text(
            '<meta http-equiv="refresh" content="0; url=ET-1__LG-9.html">',
            encoding="utf-8",
        )
        (self.static_root / "hybrids" / "ET-1__LG-9.html").write_text(
            "canonical corrected", encoding="utf-8"
        )

        self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            corrected = db.execute(
                "SELECT * FROM hybrid_registry WHERE pair_key='ET-1__LG-9'"
            ).fetchone()
            aliases = {
                row["target"]: row
                for row in db.execute(
                    "SELECT target,hybrid_registry_id,is_canonical FROM hybrid_target_aliases"
                ).fetchall()
            }
            comment = db.execute(
                "SELECT target,hybrid_registry_id FROM comments WHERE body='legacy comment'"
            ).fetchone()
            active_count = db.execute(
                "SELECT COUNT(*) FROM hybrid_registry WHERE active=1"
            ).fetchone()[0]

        self.assertEqual(corrected["id"], stable_id)
        self.assertEqual(corrected["etl_hybrid_id"], 12345)
        self.assertEqual(corrected["etl_hybrid_serial"], "ETL-STABLE-1")
        self.assertEqual(corrected["sync_status"], "matched")
        self.assertEqual(active_count, 2)
        self.assertEqual(aliases["hybrid:ET-1__LG-1"]["hybrid_registry_id"], stable_id)
        self.assertEqual(aliases["hybrid:ET-1__LG-1"]["is_canonical"], 0)
        self.assertEqual(aliases["hybrid:ET-1__LG-9"]["is_canonical"], 1)
        self.assertEqual(comment["target"], "hybrid:ET-OLD__LG-OLD")
        self.assertEqual(comment["hybrid_registry_id"], stable_id)

    def test_etroc_side_pair_correction_preserves_stable_identity(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        bound = self.server.bind_hybrid(
            self.db_path,
            pair_key="ET-1__LG-1",
            etl_hybrid_id=12345,
            etl_hybrid_serial="ETL-STABLE-1",
            sync_status="matched",
        )

        (self.static_root / "index.html").write_text(
            """
            <a href="hybrids/ET-9__LG-1.html">corrected</a>
            <a href="hybrids/ET-2__LG-2.html">second</a>
            """,
            encoding="utf-8",
        )
        (self.static_root / "hybrids" / "ET-1__LG-1.html").write_text(
            '<meta http-equiv="refresh" content="0; url=ET-9__LG-1.html">',
            encoding="utf-8",
        )
        (self.static_root / "hybrids" / "ET-9__LG-1.html").write_text(
            "canonical corrected", encoding="utf-8"
        )

        self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            corrected = db.execute(
                "SELECT * FROM hybrid_registry WHERE pair_key='ET-9__LG-1'"
            ).fetchone()
            old_alias = db.execute(
                "SELECT hybrid_registry_id,is_canonical FROM hybrid_target_aliases WHERE target='hybrid:ET-1__LG-1'"
            ).fetchone()

        self.assertEqual(corrected["id"], bound["id"])
        self.assertEqual(corrected["etl_hybrid_id"], 12345)
        self.assertEqual(corrected["etl_hybrid_serial"], "ETL-STABLE-1")
        self.assertEqual(old_alias["hybrid_registry_id"], bound["id"])
        self.assertEqual(old_alias["is_canonical"], 0)

    def test_pair_correction_rejects_exact_vs_redirect_identity_conflict(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        (self.static_root / "index.html").write_text(
            '<a href="hybrids/ET-1__LG-1.html">current</a>', encoding="utf-8"
        )
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        (self.static_root / "index.html").write_text(
            '<a href="hybrids/ET-2__LG-2.html">reintroduced</a>', encoding="utf-8"
        )
        (self.static_root / "hybrids" / "ET-1__LG-1.html").write_text(
            '<meta http-equiv="refresh" content="0; url=ET-2__LG-2.html">',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "ambiguous registry identity"):
            self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            active_pairs = db.execute(
                "SELECT pair_key FROM hybrid_registry WHERE active=1"
            ).fetchall()
        self.assertEqual(active_pairs, [("ET-1__LG-1",)])

    def test_redirect_retarget_rejects_existing_alias_and_comment_owner_conflict(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        with sqlite3.connect(self.db_path) as db:
            before_alias = db.execute(
                """
                SELECT hybrid_registry_id FROM hybrid_target_aliases
                WHERE target='hybrid:ET-OLD__LG-OLD'
                """
            ).fetchone()[0]
            before_comment = db.execute(
                """
                SELECT hybrid_registry_id FROM comments
                WHERE target='hybrid:ET-OLD__LG-OLD'
                """
            ).fetchone()[0]

        (self.static_root / "hybrids" / "ET-OLD__LG-OLD.html").write_text(
            '<meta http-equiv="refresh" content="0; url=ET-2__LG-2.html">',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "ambiguous registry identity"):
            self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            after_alias = db.execute(
                """
                SELECT hybrid_registry_id FROM hybrid_target_aliases
                WHERE target='hybrid:ET-OLD__LG-OLD'
                """
            ).fetchone()[0]
            after_comment = db.execute(
                """
                SELECT hybrid_registry_id FROM comments
                WHERE target='hybrid:ET-OLD__LG-OLD'
                """
            ).fetchone()[0]
        self.assertEqual((after_alias, after_comment), (before_alias, before_comment))

    def test_stale_alias_comment_owner_conflict_fails_without_mutation(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        with sqlite3.connect(self.db_path) as db:
            first_id = db.execute(
                "SELECT id FROM hybrid_registry WHERE pair_key='ET-1__LG-1'"
            ).fetchone()[0]
            second_id = db.execute(
                "SELECT id FROM hybrid_registry WHERE pair_key='ET-2__LG-2'"
            ).fetchone()[0]
            db.execute(
                """
                INSERT INTO hybrid_target_aliases(
                    target,hybrid_registry_id,is_canonical,created_at
                ) VALUES(?,?,0,?)
                """,
                ("hybrid:STALE__PAIR", first_id, "2026-07-29T00:00:00Z"),
            )
            db.execute(
                """
                INSERT INTO comments(
                    target,body,status,author,author_display,
                    hybrid_registry_id,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    "hybrid:STALE__PAIR",
                    "stale provenance",
                    "review",
                    "reviewer@cern.ch",
                    "Reviewer",
                    second_id,
                    "2026-07-29T00:00:00Z",
                    "2026-07-29T00:00:00Z",
                ),
            )
            db.commit()
            before = db.execute(
                """
                SELECT alias.hybrid_registry_id,comment.hybrid_registry_id
                FROM hybrid_target_aliases AS alias
                JOIN comments AS comment ON comment.target=alias.target
                WHERE alias.target='hybrid:STALE__PAIR'
                """
            ).fetchone()

        with self.assertRaisesRegex(ValueError, "comment/alias ownership conflict"):
            self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            after = db.execute(
                """
                SELECT alias.hybrid_registry_id,comment.hybrid_registry_id
                FROM hybrid_target_aliases AS alias
                JOIN comments AS comment ON comment.target=alias.target
                WHERE alias.target='hybrid:STALE__PAIR'
                """
            ).fetchone()
        self.assertEqual(after, before)

    def test_pair_correction_rejects_ambiguous_existing_children(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        (self.static_root / "index.html").write_text(
            '<a href="hybrids/ET-1__LG-2.html">ambiguous</a>', encoding="utf-8"
        )
        (self.static_root / "hybrids" / "ET-1__LG-2.html").write_text(
            "canonical", encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "ambiguous registry identity"):
            self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with sqlite3.connect(self.db_path) as db:
            original_pairs = db.execute(
                "SELECT pair_key FROM hybrid_registry WHERE active=1 ORDER BY pair_key"
            ).fetchall()
        self.assertEqual(original_pairs, [("ET-1__LG-1",), ("ET-2__LG-2",)])

    def test_legacy_and_canonical_targets_resolve_to_one_stable_registry(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        canonical = self.server.resolve_hybrid_target(self.db_path, "hybrid:ET-1__LG-1")
        legacy = self.server.resolve_hybrid_target(
            self.db_path, "hybrid:ET-OLD__LG-OLD"
        )

        self.assertEqual(canonical["hybrid_registry_id"], legacy["hybrid_registry_id"])
        self.assertEqual(canonical["canonical_target"], "hybrid:ET-1__LG-1")
        self.assertEqual(legacy["canonical_target"], "hybrid:ET-1__LG-1")

    def test_bind_hybrid_persists_etl_identity_and_provenance(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        row = self.server.bind_hybrid(
            self.db_path,
            pair_key="ET-1__LG-1",
            etl_hybrid_id=12345,
            etl_hybrid_serial="ET2.01-KNU-NH0001",
            sync_status="matched",
            source_revision="staging-import-1",
        )

        self.assertEqual(row["pair_key"], "ET-1__LG-1")
        self.assertEqual(row["etl_hybrid_id"], 12345)
        self.assertEqual(row["etl_hybrid_serial"], "ET2.01-KNU-NH0001")
        self.assertEqual(row["sync_status"], "matched")
        self.assertEqual(row["source_revision"], "staging-import-1")

        rebound = self.server.bind_hybrid(
            self.db_path,
            pair_key="ET-1__LG-1",
            etl_hybrid_id=12345,
            etl_hybrid_serial="ET2.01-KNU-NH0001",
            sync_status="matched",
        )
        self.assertEqual(rebound["source_revision"], "staging-import-1")

        with self.assertRaisesRegex(ValueError, "hybrid already bound"):
            self.server.bind_hybrid(
                self.db_path,
                pair_key="ET-1__LG-1",
                etl_hybrid_id=54321,
                etl_hybrid_serial="ETL-REPLACEMENT",
                sync_status="matched",
                source_revision="replacement-attempt",
            )

        with self.assertRaisesRegex(ValueError, "complete ETL binding required"):
            self.server.bind_hybrid(
                self.db_path,
                pair_key="ET-1__LG-1",
                etl_hybrid_id=None,
                etl_hybrid_serial=None,
                sync_status="unregistered",
            )
        with self.assertRaisesRegex(ValueError, "invalid binding sync_status"):
            self.server.bind_hybrid(
                self.db_path,
                pair_key="ET-1__LG-1",
                etl_hybrid_id=888,
                etl_hybrid_serial="ETL-SHOULD-NOT-BIND",
                sync_status="unregistered",
            )
        preserved = self.server.list_hybrids(self.db_path, pair_key="ET-1__LG-1")[0]
        self.assertEqual(preserved["etl_hybrid_id"], 12345)
        self.assertEqual(preserved["etl_hybrid_serial"], "ET2.01-KNU-NH0001")
        self.assertEqual(preserved["sync_status"], "matched")

    def test_bind_hybrid_rejects_invalid_or_conflicting_identity(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)

        with self.assertRaisesRegex(ValueError, "matched requires etl_hybrid_serial"):
            self.server.bind_hybrid(
                self.db_path,
                pair_key="ET-1__LG-1",
                etl_hybrid_id=12345,
                etl_hybrid_serial=None,
                sync_status="matched",
            )
        for invalid_id in (12.9, "12", True, 2**63):
            with (
                self.subTest(invalid_id=invalid_id),
                self.assertRaisesRegex(ValueError, "invalid etl_hybrid_id"),
            ):
                self.server.bind_hybrid(
                    self.db_path,
                    pair_key="ET-1__LG-1",
                    etl_hybrid_id=invalid_id,
                    etl_hybrid_serial="ETL-INVALID-ID",
                    sync_status="matched",
                )
        for invalid_serial in ("\x00", "ETL\nSERIAL"):
            with self.subTest(invalid_serial=invalid_serial), self.assertRaisesRegex(
                ValueError, "invalid etl_hybrid_serial"
            ):
                self.server.bind_hybrid(
                    self.db_path,
                    pair_key="ET-1__LG-1",
                    etl_hybrid_id=12345,
                    etl_hybrid_serial=invalid_serial,
                    sync_status="matched",
                )
        with self.assertRaisesRegex(ValueError, "invalid source_revision"):
            self.server.bind_hybrid(
                self.db_path,
                pair_key="ET-1__LG-1",
                etl_hybrid_id=12345,
                etl_hybrid_serial="ETL-VALID",
                sync_status="matched",
                source_revision={"bad": "type"},
            )
        with self.assertRaisesRegex(LookupError, "unknown pair_key"):
            self.server.bind_hybrid(
                self.db_path,
                pair_key="MISSING__PAIR",
                etl_hybrid_id=999,
                etl_hybrid_serial="ETL-MISSING-1",
                sync_status="matched",
            )

        self.server.bind_hybrid(
            self.db_path,
            pair_key="ET-1__LG-1",
            etl_hybrid_id=12345,
            etl_hybrid_serial="ETL-UNIQUE-1",
            sync_status="matched",
        )
        with self.assertRaisesRegex(ValueError, "ETL identity already bound"):
            self.server.bind_hybrid(
                self.db_path,
                pair_key="ET-2__LG-2",
                etl_hybrid_id=12345,
                etl_hybrid_serial="ETL-UNIQUE-2",
                sync_status="matched",
            )
        with self.assertRaisesRegex(ValueError, "ETL identity already bound"):
            self.server.bind_hybrid(
                self.db_path,
                pair_key="ET-2__LG-2",
                etl_hybrid_id=54321,
                etl_hybrid_serial="ETL-UNIQUE-1",
                sync_status="matched",
            )


    def test_concurrent_binding_is_first_writer_wins(self):
        self.server.init_db(db_path=self.db_path, static_root=self.static_root)
        barrier = threading.Barrier(2)

        def attempt(identity):
            barrier.wait()
            try:
                return self.server.bind_hybrid(
                    self.db_path,
                    pair_key="ET-1__LG-1",
                    etl_hybrid_id=identity,
                    etl_hybrid_serial=f"ETL-{identity}",
                    sync_status="matched",
                    source_revision=f"concurrent-{identity}",
                )
            except ValueError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, (1001, 1002)))

        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)
        self.assertEqual(
            sum(
                isinstance(item, ValueError) and "hybrid already bound" in str(item)
                for item in outcomes
            ),
            1,
        )


class HybridRegistryHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.db_path = base / "comments.sqlite3"
        self.static_root = base / "static"
        create_legacy_comments_db(self.db_path)
        create_static_site(self.static_root)
        self.server_module = load_server_module()
        self.server_module.DB_PATH = self.db_path
        self.server_module.ROOT = self.static_root
        self.server_module.ALLOW_ANON = False
        self.server_module.ADMIN_USERS = {"ypark", "ypark@cern.ch"}
        self.server_module.init_db(db_path=self.db_path, static_root=self.static_root)
        self.httpd = self.server_module.ThreadingHTTPServer(
            ("127.0.0.1", 0), self.server_module.Handler
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        host, port = self.httpd.server_address
        self.base_url = f"http://{host}:{port}"
        self.server_module.APP_ORIGIN = self.base_url

    def _stop_server(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def request(
        self,
        path,
        *,
        method="GET",
        payload=None,
        user=None,
        origin=None,
        content_type="application/json",
        extra_headers=None,
    ):
        data = None
        headers = dict(extra_headers or {})
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = content_type
        if user:
            headers["X-Forwarded-Email"] = user
        if method != "GET":
            headers["Origin"] = self.base_url if origin is None else origin
        req = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_registry_read_and_admin_bind_api(self):
        query = urllib.parse.urlencode({"pair_key": "ET-1__LG-1"})
        status, payload = self.request(f"/api/hybrids?{query}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["records"][0]["pair_key"], "ET-1__LG-1")

        bind_payload = {
            "pair_key": "ET-1__LG-1",
            "etl_hybrid_id": 12345,
            "etl_hybrid_serial": "ETL-KNU-HYBRID-1",
            "sync_status": "matched",
            "source_revision": "http-test",
        }
        status, _ = self.request(
            "/api/hybrids/bind", method="POST", payload=bind_payload
        )
        self.assertEqual(status, 401)
        status, _ = self.request(
            "/api/hybrids/bind", method="POST", payload=bind_payload, user="alice"
        )
        self.assertEqual(status, 403)
        status, bound = self.request(
            "/api/hybrids/bind", method="POST", payload=bind_payload, user="ypark"
        )
        self.assertEqual(status, 200)
        self.assertEqual(bound["sync_status"], "matched")
        self.assertEqual(bound["etl_hybrid_serial"], "ETL-KNU-HYBRID-1")

    def test_bind_api_rejects_spoofed_identity_csrf_and_partial_payloads(self):
        bind_payload = {
            "pair_key": "ET-1__LG-1",
            "etl_hybrid_id": 12345,
            "etl_hybrid_serial": "ETL-KNU-HYBRID-1",
            "sync_status": "matched",
        }
        status, _ = self.request(
            "/api/hybrids/bind",
            method="POST",
            payload=bind_payload,
            extra_headers={
                "X-Remote-User": "ypark",
                "X-Auth-Request-Email": "ypark@cern.ch",
            },
        )
        self.assertEqual(status, 401)

        status, _ = self.request(
            "/api/hybrids/bind",
            method="POST",
            payload=bind_payload,
            user="ypark",
            origin="https://evil.cern.ch",
        )
        self.assertEqual(status, 403)

        status, _ = self.request(
            "/api/hybrids/bind",
            method="POST",
            payload=bind_payload,
            user="ypark",
            origin=self.base_url + "/",
        )
        self.assertEqual(status, 403)

        status, _ = self.request(
            "/api/hybrids/bind",
            method="POST",
            payload=bind_payload,
            user="ypark",
            origin="",
        )
        self.assertEqual(status, 403)

        status, _ = self.request(
            "/api/hybrids/bind",
            method="POST",
            payload=bind_payload,
            user="ypark",
            content_type="text/plain",
        )
        self.assertEqual(status, 415)

        status, _ = self.request(
            "/api/hybrids/bind",
            method="POST",
            payload={"pair_key": "ET-2__LG-2"},
            user="ypark",
        )
        self.assertEqual(status, 400)

    def test_legacy_comment_target_reads_and_writes_canonical_registry(self):
        legacy = urllib.parse.quote("hybrid:ET-OLD__LG-OLD", safe="")
        status, comments = self.request(f"/api/comments?target={legacy}")
        self.assertEqual(status, 200)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["target"], "hybrid:ET-1__LG-1")

        summary_query = urllib.parse.urlencode(
            [
                ("target", "hybrid:ET-OLD__LG-OLD"),
                ("target", "hybrid:ET-1__LG-1"),
            ]
        )
        status, summary = self.request(f"/api/comments/summary?{summary_query}")
        self.assertEqual(status, 200)
        self.assertEqual(summary["hybrid:ET-OLD__LG-OLD"]["count"], 1)
        self.assertEqual(summary["hybrid:ET-1__LG-1"]["count"], 1)
        self.assertEqual(
            summary["hybrid:ET-OLD__LG-OLD"]["latest"]["target"],
            "hybrid:ET-1__LG-1",
        )

        status, created = self.request(
            "/api/comments",
            method="POST",
            user="ypark",
            payload={
                "target": "hybrid:ET-OLD__LG-OLD",
                "body": "new via legacy alias",
                "status": "review",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(created["target"], "hybrid:ET-1__LG-1")

        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT target,hybrid_registry_id FROM comments WHERE body=?",
                ("new via legacy alias",),
            ).fetchone()
        self.assertEqual(row[0], "hybrid:ET-OLD__LG-OLD")
        self.assertIsNotNone(row[1])

    def test_summary_targets_parameter_preserves_non_hybrid_behavior(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO comments(
                    target,body,status,author,author_display,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                ("module:plain", "plain comment", "note", "ypark", "ypark", 2, 2),
            )
            db.executemany(
                """
                INSERT INTO comments(
                    target,body,status,author,author_display,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                [
                    (
                        "module:plain",
                        f"bulk comment {index}",
                        "note",
                        "ypark",
                        "ypark",
                        10 + index,
                        10 + index,
                    )
                    for index in range(250)
                ],
            )
            db.commit()
        query = urllib.parse.urlencode(
            {"targets": "hybrid:ET-OLD__LG-OLD,module:plain"}
        )
        status, summary = self.request(f"/api/comments/summary?{query}")

        self.assertEqual(status, 200)
        self.assertEqual(summary["hybrid:ET-OLD__LG-OLD"]["count"], 1)
        self.assertEqual(summary["module:plain"]["count"], 251)
        self.assertEqual(summary["module:plain"]["latest"]["target"], "module:plain")
        self.assertEqual(summary["module:plain"]["latest"]["body"], "bulk comment 249")


class HybridRegistryRealStaticTests(unittest.TestCase):
    def test_real_dashboard_seeds_exact_unique_72_pair_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "comments.sqlite3"
            server = load_server_module()
            static_root = ROOT / "hybrid-bbqc"
            server.init_db(db_path=db_path, static_root=static_root)
            server.init_db(db_path=db_path, static_root=static_root)
            with sqlite3.connect(db_path) as db:
                active, etrocs, lgads = db.execute(
                    """
                    SELECT COUNT(*),COUNT(DISTINCT etroc_serial),
                           COUNT(DISTINCT lgad_serial)
                    FROM hybrid_registry WHERE active=1
                    """
                ).fetchone()
                canonical = db.execute(
                    "SELECT COUNT(*) FROM hybrid_target_aliases WHERE is_canonical=1"
                ).fetchone()[0]
                aliases = db.execute(
                    "SELECT COUNT(*) FROM hybrid_target_aliases"
                ).fetchone()[0]
                foreign_key_errors = db.execute("PRAGMA foreign_key_check").fetchall()
                integrity = db.execute("PRAGMA integrity_check").fetchone()[0]

        self.assertEqual((active, etrocs, lgads, canonical), (72, 72, 72, 72))
        self.assertGreaterEqual(aliases, 72)
        self.assertEqual(foreign_key_errors, [])
        self.assertEqual(integrity, "ok")


class HybridRegistryDeploymentTests(unittest.TestCase):
    def test_manifest_isolates_backend_and_prevents_overlapping_sqlite_writers(self):
        manifest = (ROOT / "hybrid-bbqc" / "openshift" / "deployment.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("strategy:\n    type: Recreate", manifest)
        self.assertIn('- name: HOST\n              value: "127.0.0.1"', manifest)
        self.assertIn(
            "- name: APP_ORIGIN\n              value: https://etl-hybrid-bbqc.app.cern.ch",
            manifest,
        )
        self.assertIn("urlopen('http://127.0.0.1:8080/api/health'", manifest)
        self.assertIn("--upstream=http://127.0.0.1:8080", manifest)
        self.assertIn(
            "quay.io/oauth2-proxy/oauth2-proxy@sha256:10a1165743a192e1940b4708fb9647027185ce11a681a1c5519b442ff7f1f561",
            manifest,
        )
        self.assertIn("--skip-auth-strip-headers=true", manifest)
        containerfile = (ROOT / "hybrid-bbqc" / "Containerfile").read_text(
            encoding="utf-8"
        )
        self.assertIn("chown -R root:root /app", containerfile)
        self.assertIn("chown app:0 /data", containerfile)
        self.assertIn("chmod -R u=rwX,go=rX /app", containerfile)
        self.assertIn("chmod g=u /data", containerfile)

    def test_single_app_pod_selector_is_owner_ready_pvc_and_cardinality_aware(self):
        selector_path = (
            ROOT / "hybrid-bbqc" / "openshift" / "select_single_app_pod.py"
        )
        spec = importlib.util.spec_from_file_location("bbqc_pod_selector", selector_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pvc_volume = {
            "name": "data",
            "persistentVolumeClaim": {"claimName": "etl-hybrid-bbqc-comments"},
        }
        replica_sets = [
            {
                "metadata": {
                    "name": "etl-hybrid-bbqc-abc",
                    "uid": "rs-current-uid",
                    "ownerReferences": [
                        {
                            "controller": True,
                            "kind": "Deployment",
                            "name": "etl-hybrid-bbqc",
                            "uid": "deployment-current-uid",
                        }
                    ],
                }
            }
        ]

        def pod(
            name, *, owner_name="etl-hybrid-bbqc-abc", owner_uid="rs-current-uid"
        ):
            return {
                "metadata": {
                    "name": name,
                    "labels": {"app": "etl-hybrid-bbqc"},
                    "ownerReferences": [
                        {
                            "controller": True,
                            "kind": "ReplicaSet",
                            "name": owner_name,
                            "uid": owner_uid,
                        }
                    ],
                },
                "spec": {
                    "volumes": [pvc_volume],
                    "containers": [
                        {
                            "name": "web",
                            "volumeMounts": [{"name": "data", "mountPath": "/data"}],
                        },
                        {"name": "oauth2-proxy"},
                    ],
                },
                "status": {
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerStatuses": [
                        {"name": "web", "ready": True},
                        {"name": "oauth2-proxy", "ready": True},
                    ],
                },
            }

        selected = module.select_single_app_pod(
            [pod("app-one")],
            replica_sets,
            deployment="etl-hybrid-bbqc",
            deployment_uid="deployment-current-uid",
            pvc="etl-hybrid-bbqc-comments",
            containers={"web", "oauth2-proxy"},
            pvc_container="web",
            pvc_mount_path="/data",
        )
        self.assertEqual(selected, "app-one")
        with self.assertRaisesRegex(ValueError, "expected exactly one ready pod"):
            module.select_single_app_pod(
                [pod("app-one"), pod("app-two")],
                replica_sets,
                deployment="etl-hybrid-bbqc",
                deployment_uid="deployment-current-uid",
                pvc="etl-hybrid-bbqc-comments",
                containers={"web", "oauth2-proxy"},
                pvc_container="web",
                pvc_mount_path="/data",
            )

        stale_replica_set = {
            "metadata": {
                "name": "etl-hybrid-bbqc-stale",
                "uid": "rs-stale-uid",
                "ownerReferences": [
                    {
                        "controller": True,
                        "kind": "Deployment",
                        "name": "etl-hybrid-bbqc",
                        "uid": "deployment-old-uid",
                    }
                ],
            }
        }
        standalone = pod("standalone")
        standalone["metadata"]["ownerReferences"] = []
        stale_cases = [
            (
                [
                    pod("app-one"),
                    pod(
                        "stale",
                        owner_name="etl-hybrid-bbqc-stale",
                        owner_uid="rs-stale-uid",
                    ),
                ],
                [*replica_sets, stale_replica_set],
            ),
            (
                [pod("app-one"), pod("old-rs-uid", owner_uid="rs-old-uid")],
                replica_sets,
            ),
            ([pod("app-one"), standalone], replica_sets),
        ]
        for pods, replica_set_fixture in stale_cases:
            with self.subTest(pods=[item["metadata"]["name"] for item in pods]):
                with self.assertRaisesRegex(
                    ValueError, "outside exact Deployment UID chain"
                ):
                    module.select_single_app_pod(
                        pods,
                        replica_set_fixture,
                        deployment="etl-hybrid-bbqc",
                        deployment_uid="deployment-current-uid",
                        pvc="etl-hybrid-bbqc-comments",
                        containers={"web", "oauth2-proxy"},
                        pvc_container="web",
                        pvc_mount_path="/data",
                    )

    def test_pvc_controller_inventory_is_uid_and_scale_aware(self):
        validator_path = (
            ROOT / "hybrid-bbqc" / "openshift" / "validate_pvc_controllers.py"
        )
        spec = importlib.util.spec_from_file_location(
            "bbqc_pvc_controller_validator", validator_path
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        volume = {
            "name": "data",
            "persistentVolumeClaim": {"claimName": "etl-hybrid-bbqc-comments"},
        }

        def controller(kind, name, uid, *, owner_uid=None):
            metadata = {"name": name, "uid": uid}
            if owner_uid:
                metadata["ownerReferences"] = [
                    {
                        "controller": True,
                        "kind": "Deployment",
                        "name": "etl-hybrid-bbqc",
                        "uid": owner_uid,
                    }
                ]
            return {
                "kind": kind,
                "metadata": metadata,
                "spec": {
                    "replicas": 1,
                    "template": {"spec": {"volumes": [volume]}},
                },
            }

        deployment = controller(
            "Deployment", "etl-hybrid-bbqc", "deployment-current-uid"
        )
        replica_set = controller(
            "ReplicaSet",
            "etl-hybrid-bbqc-abc",
            "rs-current-uid",
            owner_uid="deployment-current-uid",
        )
        kwargs = {
            "pvc": "etl-hybrid-bbqc-comments",
            "deployment": "etl-hybrid-bbqc",
            "deployment_uid": "deployment-current-uid",
        }
        self.assertEqual(
            len(module.validate_pvc_controllers([deployment, replica_set], **kwargs)),
            2,
        )
        stale_deployment = controller(
            "Deployment", "etl-hybrid-bbqc", "deployment-old-uid"
        )
        stale_replica_set = controller(
            "ReplicaSet",
            "etl-hybrid-bbqc-stale",
            "rs-stale-uid",
            owner_uid="deployment-old-uid",
        )
        deployment_config = controller(
            "DeploymentConfig", "legacy-writer", "dc-uid"
        )
        hpa = {
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": "app-hpa", "uid": "hpa-uid"},
            "spec": {
                "scaleTargetRef": {
                    "kind": "Deployment",
                    "name": "etl-hybrid-bbqc",
                }
            },
        }
        for fixtures in (
            [stale_deployment, replica_set],
            [deployment, replica_set, stale_replica_set],
            [deployment, replica_set, deployment_config],
            [deployment, replica_set, hpa],
        ):
            with self.subTest(fixtures=[item["kind"] for item in fixtures]):
                with self.assertRaises(ValueError):
                    module.validate_pvc_controllers(fixtures, **kwargs)
        with self.assertRaisesRegex(ValueError, "not scaled to zero"):
            module.validate_pvc_controllers(
                [deployment, replica_set], **kwargs, require_scaled_zero=True
            )
        scaled_deployment = json.loads(json.dumps(deployment))
        scaled_deployment["spec"]["replicas"] = 0
        no_pvc_replica_set = controller(
            "ReplicaSet",
            "etl-hybrid-bbqc-no-pvc",
            "rs-no-pvc-uid",
            owner_uid="deployment-current-uid",
        )
        no_pvc_replica_set["spec"]["template"]["spec"]["volumes"] = []
        with self.assertRaisesRegex(ValueError, "not scaled to zero"):
            module.validate_pvc_controllers(
                [scaled_deployment, no_pvc_replica_set],
                **kwargs,
                require_scaled_zero=True,
            )
        no_pvc_replica_set["spec"]["replicas"] = 0
        module.validate_pvc_controllers(
            [scaled_deployment, no_pvc_replica_set],
            **kwargs,
            require_scaled_zero=True,
        )
        scaled = json.loads(json.dumps([deployment, replica_set]))
        for item in scaled:
            item["spec"]["replicas"] = 0
        module.validate_pvc_controllers(
            scaled, **kwargs, require_scaled_zero=True
        )

    def test_runbook_release_and_restore_steps_fail_closed(self):
        runbook = (ROOT / "README_CERN_DEPLOY.md").read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", runbook, flags=re.DOTALL)
        self.assertGreaterEqual(len(bash_blocks), 10)
        self.assertTrue(
            all(block.startswith("set -Eeuo pipefail\n") for block in bash_blocks)
        )
        for required in (
            'oc -n "$PROJECT" start-build etl-hybrid-bbqc',
            '--from-dir="$BUILD_CONTEXT" -o name',
            'cp -a hybrid-bbqc assets "$BUILD_CONTEXT/"',
            "BUILD_CONTEXT_SHA256=",
            "SOURCE_REVISION=",
            "bbqc.cern.ch/build-name=$BUILD_NAME",
            "rm -f /tmp/etl-hybrid-bbqc-deployment-pinned.yaml",
            "test -s /tmp/etl-hybrid-bbqc-deployment-pinned.yaml",
            'source "${HOME}/bbqc-backups/current-release.env"',
            "verify_context",
            'oc -n "$PROJECT" wait --for=delete pod -l app=etl-hybrid-bbqc',
            "select_single_app_pod.py",
            "validate_pvc_controllers.py",
            "DEPLOYMENT_UID=",
            '--deployment-uid "$DEPLOYMENT_UID"',
            "deploymentconfigs.apps.openshift.io",
            "replicationcontrollers,replicasets.apps",
            "horizontalpodautoscalers.autoscaling",
            "--require-scaled-zero",
            'assert not consumers, consumers',
            'assert consumers == ["etl-hybrid-bbqc-db-restore"], consumers',
            "OLD_DEPLOYMENT_FILE=",
            "OLD_DEPLOYMENT_SHA256=",
            'oc -n "$PROJECT" replace --dry-run=server -f "$ROLLBACK_DEPLOYMENT"',
            'oc -n "$PROJECT" replace -f "$ROLLBACK_DEPLOYMENT"',
            "ROLLBACK_SPEC_PASS",
            'test "$ROLLBACK_PROXY_IMAGE" = "$OLD_PROXY_IMAGE"',
            'test "$REMOTE_BACKUP_SHA256" = "$BACKUP_SHA256"',
            "failed_source.backup(failed_target)",
            "assert comments == int(os.environ['BEFORE_COMMENTS'])",
            "SSO_PROXY_GATE PASS",
        ):
            self.assertIn(required, runbook)
        self.assertLess(
            runbook.index('test -r "$LOCAL_BACKUP"'),
            runbook.index('oc -n "$PROJECT" scale deployment/etl-hybrid-bbqc'),
        )


if __name__ == "__main__":
    unittest.main()
