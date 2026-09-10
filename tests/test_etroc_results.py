"""Post-review aggregate: real immutable evidence and temporary review stores only."""
import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

from test_etroc_position_reviews import load_module, STATIC_ROOT, PositionApiTests


def seed_reviews(module, path, evidence, label="GREEN"):
    """Explicitly test-only fixture; append legitimate events, never edit production DB."""
    events = []
    for acquisition in evidence.by_acquisition.values():
        for position in acquisition.positions.values():
            if not position.review_target:
                continue
            request = {field: getattr(position, field) for field in module.POSITION_KEY_FIELDS}
            request.update(label=label, note="TEST FIXTURE — not a production review", expected_current_event_id=None, mutation_id=str(uuid.uuid4()))
            result = module.append(path, evidence, request, "test.reviewer@cern.ch", "Test reviewer")
            assert result.status == 201, result
            events.append((request, result.payload["event"]["event_id"]))
    return events


class ResultServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.evidence = cls.module.load_evidence(STATIC_ROOT)

    def test_pending_complete_correction_and_bounded_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test-only.sqlite3"
            self.module.init_schema(path)
            pending = self.module.results_summary(path, self.evidence)
            self.assertEqual(pending["record_count"], 36)
            self.assertEqual(pending["position_count"], 9216)
            self.assertEqual(pending["target_count"], 82)
            self.assertEqual(pending["reviewed_target_count"], 0)
            self.assertEqual(sum(item["target_count"] == 0 for item in pending["results"].values()), 14)
            for key, item in pending["results"].items():
                acquisition = self.evidence.by_acquisition[key]
                self.assertEqual(item["algorithm_labels"], [p.algorithm_category for p in acquisition.positions.values()])
                self.assertEqual(item["human_labels"], {})
                self.assertEqual(item["position_publication_sha256"], acquisition.position_publication_sha256)
            events = seed_reviews(self.module, path, self.evidence)
            complete = self.module.results_summary(path, self.evidence)
            self.assertEqual(complete["reviewed_target_count"], 82)
            self.assertLess(len(json.dumps(complete)), 150_000)
            request, event_id = events[0]
            correction = dict(request, label="RED", expected_current_event_id=event_id, mutation_id=str(uuid.uuid4()))
            saved = self.module.append(path, self.evidence, correction, "test.reviewer@cern.ch", "Test reviewer")
            self.assertEqual(saved.status, 201)
            refreshed = self.module.results_summary(path, self.evidence)
            current = refreshed["results"][request["acquisition_id"]]["human_labels"][str(request["position"])]
            self.assertEqual(current, {"label": "RED", "current_event_id": saved.payload["event"]["event_id"]})
            self.assertEqual(refreshed["reviewed_target_count"], 82)
            history = self.module.history(path, self.evidence, request["acquisition_id"], request["position"])
            self.assertEqual(len(history.payload["history"]), 2)

    def test_missing_or_malformed_store_never_returns_zero_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test-only.sqlite3"
            with self.assertRaises((ValueError, sqlite3.DatabaseError)):
                self.module.results_summary(path, self.evidence)
            self.module.init_schema(path)
            with sqlite3.connect(path) as db:
                db.execute("DROP TRIGGER position_review_no_update")
            with self.assertRaises(ValueError):
                self.module.results_summary(path, self.evidence)


class ResultApiTests(PositionApiTests):
    def test_results_route_auth_cache_query_and_unavailable(self):
        route = "/api/etroc-position-reviews/results?dataset_id=ETROC_OI_2608"
        self.assertEqual(self.request(route)[0], 401)
        headers = {"X-Forwarded-Email": "viewer@cern.ch"}
        status, response_headers, result = self.request(route, headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(response_headers["Cache-Control"], "no-store")
        self.assertEqual(result["position_count"], 9216)
        self.assertEqual(self.request(route + "&extra=1", headers=headers)[0], 400)
        with sqlite3.connect(self.server.DB_PATH) as db:
            db.execute("DROP TRIGGER position_review_no_update")
        self.assertEqual(self.request(route, headers=headers)[0], 503)
