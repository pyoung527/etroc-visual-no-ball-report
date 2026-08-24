import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.parse
import uuid
from email.message import Message
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "hybrid-bbqc" / "etroc_position_reviews.py"
STATIC_ROOT = ROOT / "hybrid-bbqc"


def load_module():
    spec = importlib.util.spec_from_file_location("etroc_position_reviews_under_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PositionEvidenceTests(unittest.TestCase):
    def test_loads_exact_clean_montage_and_9216_position_evidence(self):
        module = load_module()
        self.assertIn("position_publication_sha256", module.POSITION_KEY_FIELDS)
        evidence = module.load_evidence(STATIC_ROOT)
        self.assertEqual(evidence.dataset_id, "ETROC_OI_2608")
        self.assertEqual(len(evidence.by_acquisition), 36)
        self.assertEqual(sum(len(item.positions) for item in evidence.by_acquisition.values()), 9216)
        self.assertEqual(sum(item.target_count for item in evidence.by_acquisition.values()), 82)
        for acquisition in evidence.by_acquisition.values():
            self.assertEqual(acquisition.geometry_version, "etroc-grid-16x16-v1")
            self.assertEqual(len(acquisition.positions), 256)
            self.assertEqual(acquisition.clean_montage_uri, f"data/etroc-optical/ETROC_OI_2608/clean-montages/sha256/{acquisition.clean_montage_sha256}.jpg")
            self.assertEqual(acquisition.position_publication_uri, f"data/etroc-optical/ETROC_OI_2608/positions/sha256/{acquisition.position_publication_sha256}.json")
            for expected_position, position in acquisition.positions.items():
                self.assertEqual(position.position, expected_position)
                self.assertEqual(position.row, expected_position // 16)
                self.assertEqual(position.column, expected_position % 16)
                self.assertEqual(position.review_target, position.algorithm_category == "NEED_INSPECT")

    def test_rejects_position_publication_or_clean_byte_drift(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = STATIC_ROOT / "data/etroc-optical/ETROC_OI_2608"
            target = root / "data/etroc-optical/ETROC_OI_2608"
            __import__("shutil").copytree(source, target)
            publication = __import__("json").loads((target / "chips.json").read_text())
            record = publication["records"][0]
            for field in ("position_publication_uri", "clean_montage_uri"):
                with self.subTest(field=field):
                    asset = target / record[field]
                    original = asset.read_bytes()
                    asset.write_bytes(original + b"drift")
                    with self.assertRaisesRegex(ValueError, "bytes do not match"):
                        module.load_evidence(root)
                    asset.write_bytes(original)


class PositionSchemaAndServiceTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.evidence = self.module.load_evidence(STATIC_ROOT)
        self.acquisition = next(iter(self.evidence.by_acquisition.values()))
        self.position = self.acquisition.positions[0]

    def request(self, **overrides):
        body = {field: getattr(self.position, field) for field in self.module.POSITION_KEY_FIELDS}
        body.update({
            "state": "reviewed_no_optical_concern",
            "note": "",
            "expected_current_event_id": None,
            "mutation_id": str(uuid.uuid4()),
        })
        body.update(overrides)
        return body

    def legacy_ddl(self):
        return tuple(
            statement
            .replace("position_review_", "etroc_position_review_")
            .replace("position_publication_sha256 TEXT NOT NULL, ", "")
            .replace("position_publication_sha256,", "")
            .replace(" AND previous.position_publication_sha256 = NEW.position_publication_sha256", "")
            for statement in self.module.DDL
        )

    def test_empty_legacy_v1_migrates_atomically_and_nonempty_rejects(self):
        for nonempty in (False, True):
            with self.subTest(nonempty=nonempty), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "reviews.sqlite3"
                with sqlite3.connect(path) as db:
                    for statement in self.legacy_ddl():
                        db.execute(statement)
                    db.execute("INSERT INTO etroc_position_review_schema VALUES(1,1,1)")
                    if nonempty:
                        db.execute(
                            "INSERT INTO etroc_position_review_events(dataset_id,etroc_serial,acquisition_id,analysis_run_id,labelled_montage_sha256,clean_montage_sha256,position,source_image_sha256,geometry_version,state,note,author,author_display,created_at,mutation_id,supersedes_event_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
                            ("ETROC_OI_2608", "W02G4-44", "a", "run", "a" * 64, "b" * 64, 0, "c" * 64, "etroc-grid-16x16-v1", "reviewed_no_optical_concern", "", "u", "U", 1, str(uuid.uuid4())),
                        )
                    db.commit()
                if nonempty:
                    with self.assertRaisesRegex(ValueError, "not safely empty"):
                        self.module.init_schema(path)
                    with sqlite3.connect(path) as db:
                        self.assertEqual(db.execute("SELECT count(*) FROM etroc_position_review_events").fetchone()[0], 1)
                else:
                    self.module.init_schema(path)
                    with sqlite3.connect(path) as db:
                        self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='etroc_position_review_events'").fetchone())
                        self.assertEqual(db.execute("SELECT singleton,version FROM position_review_schema").fetchall(), [(1, 1)])

    def test_validate_schema_requires_exact_integrity_check(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            self.module.init_schema(path)
            with sqlite3.connect(path) as db:
                db.execute("PRAGMA ignore_check_constraints=ON")
                db.execute(
                    "INSERT INTO position_review_events(dataset_id,etroc_serial,acquisition_id,analysis_run_id,labelled_montage_sha256,clean_montage_sha256,position_publication_sha256,position,source_image_sha256,geometry_version,state,note,author,author_display,created_at,mutation_id,supersedes_event_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
                    ("ETROC_OI_2608", "W02G4-44", "a", "run", "a" * 64, "b" * 64, "d" * 64, 999, "c" * 64, "etroc-grid-16x16-v1", "reviewed_no_optical_concern", "", "u", "U", 1, str(uuid.uuid4())),
                )
                db.execute("PRAGMA ignore_check_constraints=OFF")
                db.commit()
                with self.assertRaisesRegex(ValueError, "schema integrity"):
                    self.module.validate_schema(db)

    def test_additive_schema_is_exact_idempotent_and_preserves_user_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("PRAGMA user_version=2")
                db.execute("CREATE TABLE comments(id INTEGER PRIMARY KEY, body TEXT)")
            self.module.init_schema(path)
            self.module.init_schema(path)
            acquisition_path = ROOT / "hybrid-bbqc" / "etroc_reviews.py"
            acquisition_spec = importlib.util.spec_from_file_location("etroc_reviews_coexistence", acquisition_path)
            if acquisition_spec is None or acquisition_spec.loader is None:
                raise RuntimeError("cannot load acquisition review module")
            acquisition_module = importlib.util.module_from_spec(acquisition_spec)
            sys.modules[acquisition_spec.name] = acquisition_module
            acquisition_spec.loader.exec_module(acquisition_module)
            acquisition_module.init_schema(path)
            self.module.init_schema(path)
            acquisition_module.init_schema(path)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
                self.assertEqual(db.execute("SELECT singleton,version FROM position_review_schema").fetchall(), [(1, 1)])
                self.assertEqual(db.execute("SELECT count(*) FROM position_review_events").fetchone()[0], 0)
                self.module.validate_schema(db)

    def test_append_replay_stale_and_append_only_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            self.module.init_schema(path)
            request = self.request()
            created = self.module.append(path, self.evidence, request, "ypark", "Young")
            self.assertEqual(created.status, 201)
            self.assertFalse(created.payload["idempotent_replay"])
            event = created.payload["event"]
            self.assertEqual(event["position"], 0)
            replay = self.module.append(path, self.evidence, request, "ypark", "Young")
            self.assertEqual(replay.status, 200)
            self.assertTrue(replay.payload["idempotent_replay"])
            divergent = self.module.append(path, self.evidence, {**request, "note": "different"}, "ypark", "Young")
            self.assertEqual(divergent.status, 409)
            self.assertEqual(divergent.payload["error"]["code"], "mutation_id_conflict")
            stale = self.module.append(path, self.evidence, self.request(), "ypark", "Young")
            self.assertEqual(stale.status, 409)
            self.assertEqual(stale.payload["error"]["code"], "stale_current")
            successor = self.module.append(
                path,
                self.evidence,
                self.request(expected_current_event_id=event["event_id"], state="follow_up_required", note="Reinspect"),
                "ypark",
                "Young",
            )
            self.assertEqual(successor.status, 201)
            with sqlite3.connect(path) as db:
                with self.assertRaises(sqlite3.DatabaseError):
                    db.execute("UPDATE position_review_events SET note='changed'")
                with self.assertRaises(sqlite3.DatabaseError):
                    db.execute("DELETE FROM position_review_events")

    def test_summary_and_history_are_complete_and_position_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            self.module.init_schema(path)
            summary = self.module.summary(path, self.evidence, self.acquisition.acquisition_id, "Young", True)
            self.assertEqual(summary["dataset_id"], "ETROC_OI_2608")
            self.assertEqual(summary["acquisition_id"], self.acquisition.acquisition_id)
            self.assertEqual(summary["position_count"], 256)
            self.assertEqual(len(summary["evidence"]), 256)
            self.assertEqual(summary["reviews"], {})
            self.assertEqual(summary["target_count"], self.acquisition.target_count)
            created = self.module.append(path, self.evidence, self.request(), "ypark", "Young")
            self.assertEqual(created.status, 201)
            refreshed = self.module.summary(path, self.evidence, self.acquisition.acquisition_id, "Young", True)
            self.assertEqual(set(refreshed["reviews"]), {"0"})
            history = self.module.history(path, self.evidence, self.acquisition.acquisition_id, 0)
            self.assertEqual(history.status, 200)
            self.assertEqual(history.payload["current"]["position"], 0)
            self.assertEqual(len(history.payload["history"]), 1)
            audit = self.module.audit(path, self.acquisition.acquisition_id, 0, self.evidence)
            self.assertEqual(audit.status, 200)
            self.assertEqual(audit.payload["position"], 0)
            self.assertEqual(len(audit.payload["chains"]), 1)
            self.assertTrue(audit.payload["chains"][0]["current_publication"])
            self.assertEqual(audit.payload["chains"][0]["history"], history.payload["history"])


class PositionApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        server_path = ROOT / "hybrid-bbqc" / "server.py"
        spec = importlib.util.spec_from_file_location("etroc_position_server_under_test", server_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load server")
        self.server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.server)
        self.server.ROOT = STATIC_ROOT
        self.server.DB_PATH = Path(self.tmp.name) / "reviews.sqlite3"
        self.server.ETROC_REVIEWER_USERS = {"reviewer@cern.ch"}
        self.server.initialize_store(self.server.DB_PATH, STATIC_ROOT)

    def request(self, path, method="GET", payload=None, headers=None):
        request_headers = Message()
        for key, value in (headers or {}).items():
            request_headers[key] = value
        body = b""
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
            request_headers["Content-Length"] = str(len(body))
        handler = object.__new__(self.server.Handler)
        handler.path = path
        handler.headers = request_headers
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        response_headers = {}
        handler.send_response = lambda status: setattr(handler, "status", status)
        handler.send_header = lambda key, value: response_headers.__setitem__(key, value)
        handler.end_headers = lambda: None
        getattr(handler, f"do_{method}")()
        return handler.status, response_headers, json.loads(handler.wfile.getvalue())

    def test_summary_append_history_and_read_only_capability(self):
        evidence = self.server.load_etroc_position_evidence(STATIC_ROOT)
        acquisition_id = next(iter(evidence.by_acquisition))
        encoded = urllib.parse.quote(acquisition_id, safe="")
        route = f"/api/etroc-position-reviews?dataset_id=ETROC_OI_2608&acquisition_id={encoded}"
        status, _, unauthorized = self.request(route)
        self.assertEqual(status, 401)
        self.assertEqual(unauthorized["error"]["code"], "authentication_required")
        status, headers, readonly = self.request(route, headers={"X-Forwarded-Email": "viewer@cern.ch"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertFalse(readonly["viewer"]["can_append_review"])
        self.assertEqual(len(readonly["evidence"]), 256)
        status, _, summary = self.request(route, headers={"X-Forwarded-Email": "Reviewer@CERN.CH"})
        self.assertEqual(status, 200)
        self.assertTrue(summary["viewer"]["can_append_review"])
        item = summary["evidence"]["0"]
        request = {
            **{field: item[field] for field in load_module().POSITION_KEY_FIELDS},
            "state": "reviewed_no_optical_concern",
            "note": "",
            "expected_current_event_id": None,
            "mutation_id": str(uuid.uuid4()),
        }
        status, _, same_origin = self.request("/api/etroc-position-reviews", "POST", request, {"X-Forwarded-Email": "reviewer@cern.ch"})
        self.assertEqual(status, 403)
        self.assertEqual(same_origin["error"]["code"], "same_origin_required")
        post_headers = {"X-Forwarded-Email": "reviewer@cern.ch", "Origin": self.server.APP_ORIGIN}
        status, _, created = self.request("/api/etroc-position-reviews", "POST", request, post_headers)
        self.assertEqual(status, 201)
        self.assertEqual(created["event"]["author"], "reviewer@cern.ch")
        history_route = f"/api/etroc-position-reviews/history?acquisition_id={encoded}&position=0"
        status, _, history = self.request(history_route, headers={"X-Forwarded-Email": "reviewer@cern.ch"})
        self.assertEqual(status, 200)
        self.assertEqual(history["current"]["event_id"], created["event"]["event_id"])
        audit_route = f"/api/etroc-position-reviews/audit?acquisition_id={encoded}&position=0"
        status, _, audit = self.request(audit_route, headers={"X-Forwarded-Email": "reviewer@cern.ch"})
        self.assertEqual(status, 200)
        self.assertEqual(audit["chains"][0]["history"][0], created["event"])
        status, _, invalid = self.request(route + "&extra=1", headers={"X-Forwarded-Email": "reviewer@cern.ch"})
        self.assertEqual(status, 400)
        self.assertEqual(invalid["error"]["code"], "invalid_query")


if __name__ == "__main__":
    unittest.main()
