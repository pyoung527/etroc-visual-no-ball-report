import hashlib
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
import urllib.parse
import uuid
from email.message import Message
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "hybrid-bbqc" / "server.py"
STATIC_ROOT = ROOT / "hybrid-bbqc"


def load_server_module():
    spec = importlib.util.spec_from_file_location("etroc_server_under_test", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvidenceTests(unittest.TestCase):
    def test_caches_evidence_until_publication_or_manifest_identity_changes(self):
        # Given: an otherwise valid publication and manifest identity.
        server = load_server_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publication = root / "data/etroc-optical/ETROC_OI_2608/chips.json"
            manifest = publication.with_name("SHA256SUMS")
            publication.parent.mkdir(parents=True)
            publication.write_text("first", encoding="utf-8")
            manifest.write_text("first", encoding="utf-8")
            evidence = mock.sentinel.evidence
            server.reset_etroc_review_evidence_cache()

            # When: the same immutable publication is requested twice, then replaced.
            with mock.patch.object(server.etroc_reviews, "load_evidence", return_value=evidence) as loader:
                self.assertIs(server.load_etroc_review_evidence(root), evidence)
                self.assertIs(server.load_etroc_review_evidence(root), evidence)
                publication.write_text("second-publication", encoding="utf-8")
                self.assertIs(server.load_etroc_review_evidence(root), evidence)

            # Then: the cache is reused once and revalidated after identity change.
            self.assertEqual(loader.call_count, 2)

    def test_loads_exact_raw_publication_and_hashed_montages(self):
        # Given: the Task 1 content-addressed ETROC publication.
        server = load_server_module()

        # When: the dedicated server-side evidence loader reads it.
        evidence = server.load_etroc_review_evidence(STATIC_ROOT)

        # Then: every raw-publication record is present with byte-bound evidence.
        raw = (STATIC_ROOT / "data/etroc-optical/ETROC_OI_2608/chips.json").read_bytes()
        self.assertEqual(evidence.publication_sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(evidence.dataset_id, "ETROC_OI_2608")
        self.assertEqual(len(evidence.by_acquisition), 36)
        self.assertEqual(set(evidence.by_acquisition), {
            record["acquisition_id"] for record in json.loads(raw)["records"]
        })
        for item in evidence.by_acquisition.values():
            self.assertEqual(
                item.montage_uri,
                f"data/etroc-optical/{item.dataset_id}/montages/sha256/"
                f"{item.montage_sha256}.jpg",
            )

    def test_rejects_duplicate_or_deployment_skew(self):
        # Given: a copied publication whose canonical identity is corrupted.
        server = load_server_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = STATIC_ROOT / "data/etroc-optical/ETROC_OI_2608"
            target = root / "data/etroc-optical/ETROC_OI_2608"
            target.mkdir(parents=True)
            payload = json.loads((source / "chips.json").read_text(encoding="utf-8"))
            payload["records"].append(dict(payload["records"][0]))
            (target / "chips.json").write_text(json.dumps(payload), encoding="utf-8")

            # When / Then: duplicate acquisition evidence is rejected before use.
            with self.assertRaisesRegex(ValueError, "duplicate"):
                server.load_etroc_review_evidence(root)

    def test_rejects_checksum_inventory_that_omits_a_canonical_preview(self):
        # Given: a publication copy whose checksum inventory omits a declared preview.
        server = load_server_module()
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = STATIC_ROOT / "data/etroc-optical/ETROC_OI_2608"
            target = root / "data/etroc-optical/ETROC_OI_2608"
            shutil.copytree(source, target, copy_function=os.link)
            checksums = source.joinpath("SHA256SUMS").read_text(encoding="utf-8")
            omitted_preview = json.loads(source.joinpath("chips.json").read_text(encoding="utf-8"))["records"][0]["preview_uri"]
            inventory = target / "SHA256SUMS"
            inventory.unlink()
            inventory.write_text(
                "\n".join(line for line in checksums.splitlines() if not line.endswith(f"  {omitted_preview}")) + "\n",
                encoding="utf-8",
            )

            # When / Then: mutation evidence is rejected before it can be used.
            with self.assertRaisesRegex(ValueError, "checksum inventory"):
                server.load_etroc_review_evidence(root)

    def test_forced_reload_rehashes_assets_after_a_warm_cache(self):
        # Given: a GET-equivalent warm cache backed by a complete publication copy.
        server = load_server_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = STATIC_ROOT / "data/etroc-optical/ETROC_OI_2608"
            target = root / "data/etroc-optical/ETROC_OI_2608"
            shutil.copytree(source, target)
            server.reset_etroc_review_evidence_cache()
            warmed = server.load_etroc_review_evidence(root)
            item = next(iter(warmed.by_acquisition.values()))

            # When: a protected deployed montage drifts without changing the manifest.
            montage = target / item.montage_uri.removeprefix(
                f"data/etroc-optical/{item.dataset_id}/"
            )
            montage.write_bytes(montage.read_bytes() + b"drift")

            # Then: mutation-time validation cannot reuse the warm GET cache.
            with self.assertRaisesRegex(ValueError, "bytes do not match"):
                server.load_etroc_review_evidence(root, force_revalidate=True)


class StartupEvidenceTests(unittest.TestCase):
    def test_initialize_store_requires_complete_present_bundle_before_schema_side_effects(self):
        # Given: copied valid, Hybrid-only, and incomplete ETROC static publications.
        server = load_server_module()
        cases = ("valid", "hybrid_only", "missing_chips", "missing_manifest", "missing_asset")

        # When / Then: valid and Hybrid-only roots initialize, while any present broken
        # ETROC bundle fails before a database or review schema can be created.
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "static"
                shutil.copytree(STATIC_ROOT, root)
                bundle = root / "data/etroc-optical/ETROC_OI_2608"
                database = Path(directory) / "reviews.sqlite3"
                if case == "hybrid_only":
                    shutil.rmtree(bundle)
                elif case == "missing_chips":
                    (bundle / "chips.json").unlink()
                elif case == "missing_manifest":
                    (bundle / "SHA256SUMS").unlink()
                elif case == "missing_asset":
                    first = json.loads((bundle / "chips.json").read_text(encoding="utf-8"))["records"][0]
                    (bundle / first["montage_uri"]).unlink()

                server.reset_etroc_review_evidence_cache()
                if case in {"valid", "hybrid_only"}:
                    with mock.patch.object(
                        server.etroc_reviews,
                        "load_evidence",
                        wraps=server.etroc_reviews.load_evidence,
                    ) as loader:
                        server.initialize_store(database, root)
                        if case == "valid":
                            server.load_etroc_review_evidence(root)
                    with sqlite3.connect(database) as db:
                        review_table = db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='etroc_review_schema'"
                        ).fetchone()
                    self.assertEqual(review_table is not None, case == "valid")
                    self.assertEqual(loader.call_count, 1 if case == "valid" else 0)
                else:
                    with self.assertRaises(ValueError):
                        server.initialize_store(database, root)
                    self.assertFalse(database.exists())


class SchemaTests(unittest.TestCase):
    def test_migrates_only_additive_schema_without_user_version_change(self):
        # Given: a legacy Hybrid database with its version already owned by Hybrid.
        server = load_server_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("PRAGMA user_version=2")
                db.execute("CREATE TABLE comments(id INTEGER PRIMARY KEY, body TEXT)")
                db.commit()

            # When: the ETROC review schema is initialized twice.
            server.init_etroc_review_schema(path)
            server.init_etroc_review_schema(path)

            # Then: exact additive v1 metadata exists and Hybrid's version is untouched.
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
                self.assertEqual(
                    db.execute("SELECT singleton,version FROM etroc_review_schema").fetchall(),
                    [(1, 1)],
                )
                self.assertEqual(
                    db.execute("SELECT count(*) FROM etroc_review_events").fetchone()[0], 0
                )

    def test_rejects_partial_and_future_review_schemas(self):
        # Given: database states that are neither v0 nor exact v1.
        server = load_server_module()
        for sql in (
            "CREATE TABLE etroc_review_events(id INTEGER PRIMARY KEY)",
            "CREATE TABLE etroc_review_schema(singleton INTEGER PRIMARY KEY, version INTEGER, applied_at INTEGER); INSERT INTO etroc_review_schema VALUES(1,2,1)",
        ):
            with self.subTest(sql=sql), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "reviews.sqlite3"
                with sqlite3.connect(path) as db:
                    db.executescript(sql)
                    before = db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()
                with self.assertRaises(ValueError):
                    server.init_etroc_review_schema(path)
                with sqlite3.connect(path) as db:
                    after = db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()
                self.assertEqual(after, before)

    def test_rejects_arbitrary_named_etroc_indexes_and_triggers_only(self):
        # Given: exact ETROC v1 objects plus unrelated Hybrid objects.
        server = load_server_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            server.init_etroc_review_schema(path)
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE comments(id INTEGER PRIMARY KEY, body TEXT)")
                db.execute("CREATE INDEX hybrid_comment_body ON comments(body)")
                db.execute("CREATE TRIGGER hybrid_comment_guard BEFORE INSERT ON comments BEGIN SELECT 1; END")
                db.commit()
            server.init_etroc_review_schema(path)
            for statement in (
                "CREATE INDEX arbitrary_name ON etroc_review_events(note)",
                "CREATE TRIGGER arbitrary_trigger BEFORE INSERT ON etroc_review_events BEGIN SELECT 1; END",
            ):
                with self.subTest(statement=statement), sqlite3.connect(path) as db:
                    db.execute(statement)
                    db.commit()
                with self.assertRaisesRegex(ValueError, "schema"):
                    server.init_etroc_review_schema(path)
                with sqlite3.connect(path) as db:
                    db.execute("DROP INDEX IF EXISTS arbitrary_name")
                    db.execute("DROP TRIGGER IF EXISTS arbitrary_trigger")
                    db.commit()

    def test_rejects_schema_check_literal_case_drift(self):
        # Given: ETROC v1 objects whose state CHECK accepts an unintended uppercase value.
        server = load_server_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            altered = server.etroc_reviews.DDL[1].replace(
                "'reviewed_no_optical_concern'", "'REVIEWED_NO_OPTICAL_CONCERN'"
            )
            with sqlite3.connect(path) as db:
                for statement in (server.etroc_reviews.DDL[0], altered, *server.etroc_reviews.DDL[2:]):
                    db.execute(statement)
                db.execute(
                    "INSERT INTO etroc_review_schema(singleton,version,applied_at) VALUES(1,1,1)"
                )
                db.commit()

            # When / Then: exact schema validation preserves string-literal case.
            with self.assertRaisesRegex(ValueError, "schema definition"):
                server.init_etroc_review_schema(path)

    def test_rejects_every_stray_etroc_prefixed_object(self):
        # Given: a valid ETROC v1 schema plus an unattached ETROC-namespaced table.
        server = load_server_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            server.init_etroc_review_schema(path)
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE ETROC_orphan(id INTEGER PRIMARY KEY)")
                db.commit()

            # When / Then: namespaced drift cannot be ignored because it is unattached.
            with self.assertRaisesRegex(ValueError, "schema objects"):
                server.init_etroc_review_schema(path)


class ReviewServiceTests(unittest.TestCase):
    def test_append_chain_idempotency_and_evidence_validation(self):
        # Given: validated publication evidence and an empty additive review store.
        server = load_server_module()
        evidence = server.load_etroc_review_evidence(STATIC_ROOT)
        item = next(iter(evidence.by_acquisition.values()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            server.init_etroc_review_schema(path)
            request = {
                **{field: getattr(item, field) for field in ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256")},
                "state": "reviewed_concern_observed",
                "note": "Inspect position 17.",
                "expected_current_event_id": None,
                "mutation_id": str(uuid.uuid4()),
            }

            # When: a reviewer appends and retries the same logical write.
            created = server.append_etroc_review(path, evidence, request, "ypark@cern.ch", "ypark")
            replay = server.append_etroc_review(path, evidence, request, "ypark@cern.ch", "ypark")

            # Then: only one root exists and replay is deterministic.
            self.assertEqual(created.status, 201)
            self.assertFalse(created.payload["idempotent_replay"])
            self.assertEqual(replay.status, 200)
            self.assertTrue(replay.payload["idempotent_replay"])
            self.assertEqual(replay.payload["event"], created.payload["event"])
            divergent = dict(request, note="different")
            conflict = server.append_etroc_review(path, evidence, divergent, "ypark@cern.ch", "ypark")
            self.assertEqual(conflict.status, 409)
            self.assertEqual(conflict.payload["error"]["code"], "mutation_id_conflict")
            stale = dict(request, mutation_id=str(uuid.uuid4()), expected_current_event_id=None)
            stale_result = server.append_etroc_review(path, evidence, stale, "ypark@cern.ch", "ypark")
            self.assertEqual(stale_result.payload["error"]["code"], "stale_current")

    def test_idempotent_replay_reads_event_and_current_inside_the_write_transaction(self):
        server = load_server_module()
        evidence = server.load_etroc_review_evidence(STATIC_ROOT)
        item = next(iter(evidence.by_acquisition.values()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.sqlite3"
            server.init_etroc_review_schema(path)
            request = {
                **{field: getattr(item, field) for field in ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256")},
                "state": "reviewed_no_optical_concern",
                "note": "",
                "expected_current_event_id": None,
                "mutation_id": str(uuid.uuid4()),
            }
            created = server.append_etroc_review(path, evidence, request, "ypark@cern.ch", "ypark")
            self.assertEqual(created.status, 201)
            original_current = server.etroc_reviews._current
            transaction_states = []

            def observed_current(db, record):
                transaction_states.append(db.in_transaction)
                return original_current(db, record)

            with mock.patch.object(server.etroc_reviews, "_current", side_effect=observed_current):
                replay = server.append_etroc_review(path, evidence, request, "ypark@cern.ch", "ypark")

            self.assertEqual(replay.status, 200)
            self.assertEqual(transaction_states, [True])


class ReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server_module = load_server_module()
        self.server_module.ROOT = STATIC_ROOT
        self.server_module.DB_PATH = Path(self.tmp.name) / "reviews.sqlite3"
        self.server_module.ETROC_REVIEWER_USERS = {"reviewer@cern.ch"}
        self.server_module.init_etroc_review_schema(self.server_module.DB_PATH)

    def request(self, path, method="GET", payload=None, headers=None):
        request_headers = Message()
        for key, value in (headers or {}).items():
            request_headers[key] = value
        body = b""
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            if "Content-Type" not in request_headers:
                request_headers["Content-Type"] = "application/json"
            request_headers["Content-Length"] = str(len(body))
        handler = object.__new__(self.server_module.Handler)
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

    def test_summary_history_audit_and_strict_mutation_boundary(self):
        # Given: the live Handler has a trusted allowlisted reviewer identity.
        headers = {"X-Forwarded-Email": "Reviewer@CERN.CH"}

        # When: the exact current-dataset summary is requested.
        status, response_headers, summary = self.request(
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608", headers=headers
        )

        # Then: it exposes all evidence and a server-derived capability, never cacheable.
        self.assertEqual(status, 200)
        self.assertEqual(response_headers["Cache-Control"], "no-store")
        self.assertEqual(summary["record_count"], 36)
        self.assertEqual(len(summary["evidence"]), 36)
        self.assertEqual(summary["reviews"], {})
        self.assertTrue(summary["viewer"]["can_append_review"])
        item = next(iter(summary["evidence"].values()))
        request = {
            **{key: item[key] for key in ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256")},
            "state": "reviewed_no_optical_concern",
            "note": "",
            "expected_current_event_id": None,
            "mutation_id": str(uuid.uuid4()),
        }
        status, _, forbidden = self.request("/api/etroc-reviews", "POST", request, headers)
        self.assertEqual(status, 403)
        self.assertEqual(forbidden["error"]["code"], "same_origin_required")
        post_headers = dict(headers, Origin=self.server_module.APP_ORIGIN)
        status, _, created = self.request("/api/etroc-reviews", "POST", request, post_headers)
        self.assertEqual(status, 201)
        self.assertEqual(created["event"]["author"], "reviewer@cern.ch")
        encoded = urllib.parse.quote(item["acquisition_id"], safe="")
        status, _, history = self.request(f"/api/etroc-reviews/history?acquisition_id={encoded}", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(history["current"]["event_id"], created["event"]["event_id"])
        status, _, audit = self.request(f"/api/etroc-reviews/audit?acquisition_id={encoded}", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(audit["chains"][0]["history"][0], created["event"])
        status, _, invalid = self.request("/api/etroc-reviews?dataset_id=ETROC_OI_2608&extra=1", headers=headers)
        self.assertEqual(status, 400)
        self.assertEqual(invalid["error"]["code"], "invalid_query")

    def test_get_routes_require_identity_and_keep_non_reviewers_read_only(self):
        # Given: ETROC review endpoints and an authenticated identity outside the reviewer allowlist.
        acquisition_id = next(iter(self.server_module.load_etroc_review_evidence(STATIC_ROOT).by_acquisition))
        encoded = urllib.parse.quote(acquisition_id, safe="")
        routes = (
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608",
            f"/api/etroc-reviews/history?acquisition_id={encoded}",
            f"/api/etroc-reviews/audit?acquisition_id={encoded}",
        )

        # When / Then: every GET rejects an absent identity with the same structured error.
        for route in routes:
            with self.subTest(route=route):
                status, _, payload = self.request(route)
                self.assertEqual(status, 401)
                self.assertEqual(payload["error"]["code"], "authentication_required")

        # When: an authenticated but unallowlisted user reads the review summary.
        status, _, summary = self.request(
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608",
            headers={"X-Forwarded-Email": "viewer@cern.ch"},
        )

        # Then: the user can read but receives no mutation capability.
        self.assertEqual(status, 200)
        self.assertFalse(summary["viewer"]["can_append_review"])

    def test_history_and_audit_return_structured_store_unavailable(self):
        # Given: a trusted reviewer identity and database reads that fail at the review store boundary.
        headers = {"X-Forwarded-Email": "reviewer@cern.ch"}
        acquisition_id = next(iter(self.server_module.load_etroc_review_evidence(STATIC_ROOT).by_acquisition))
        encoded = urllib.parse.quote(acquisition_id, safe="")

        # When / Then: each read endpoint returns a structured service-unavailable response.
        for route, function in (
            (f"/api/etroc-reviews/history?acquisition_id={encoded}", "history"),
            (f"/api/etroc-reviews/audit?acquisition_id={encoded}", "audit"),
        ):
            with self.subTest(route=route), mock.patch.object(
                self.server_module.etroc_reviews,
                function,
                side_effect=sqlite3.DatabaseError("simulated review store failure"),
            ):
                status, _, payload = self.request(route, headers=headers)
                self.assertEqual(status, 503)
                self.assertEqual(payload["error"]["code"], "review_store_unavailable")

    def test_post_validates_shape_before_loading_evidence_and_replays_during_outage(self):
        # Given: a committed event and a later evidence-loader outage.
        headers = {
            "X-Forwarded-Email": "reviewer@cern.ch",
            "Origin": self.server_module.APP_ORIGIN,
        }
        item = next(iter(self.server_module.load_etroc_review_evidence(STATIC_ROOT).by_acquisition.values()))
        request = {
            **{field: getattr(item, field) for field in ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256")},
            "state": "reviewed_no_optical_concern",
            "note": "",
            "expected_current_event_id": None,
            "mutation_id": str(uuid.uuid4()),
        }
        created_status, _, _ = self.request("/api/etroc-reviews", "POST", request, headers)
        self.assertEqual(created_status, 201)

        # When: malformed, replay, divergent, and fresh writes meet unavailable evidence.
        invalid = dict(request)
        invalid.pop("note")
        fresh = dict(request, mutation_id=str(uuid.uuid4()))
        divergent = dict(request, note="different")
        with mock.patch.object(self.server_module, "load_etroc_review_evidence", side_effect=OSError("asset missing")) as loader:
            invalid_status, _, invalid_payload = self.request("/api/etroc-reviews", "POST", invalid, headers)
            replay_status, _, replay_payload = self.request("/api/etroc-reviews", "POST", request, headers)
            conflict_status, _, conflict_payload = self.request("/api/etroc-reviews", "POST", divergent, headers)
            fresh_status, _, fresh_payload = self.request("/api/etroc-reviews", "POST", fresh, headers)

        # Then: only the non-replay reaches the loader and degradation is structured.
        self.assertEqual(invalid_status, 400)
        self.assertEqual(replay_status, 200)
        self.assertTrue(replay_payload["idempotent_replay"])
        self.assertEqual(conflict_status, 409)
        self.assertEqual(conflict_payload["error"]["code"], "mutation_id_conflict")
        self.assertEqual(fresh_status, 503)
        self.assertEqual(fresh_payload["error"]["code"], "evidence_unavailable")
        self.assertEqual(loader.call_count, 1)

    def test_warmed_get_cache_cannot_permit_a_new_post_after_asset_byte_drift(self):
        # Given: a GET has warmed evidence from a complete independent publication copy.
        source = STATIC_ROOT / "data/etroc-optical/ETROC_OI_2608"
        target = Path(self.tmp.name) / "static" / "data/etroc-optical/ETROC_OI_2608"
        shutil.copytree(source, target)
        self.server_module.ROOT = target.parents[2]
        self.server_module.reset_etroc_review_evidence_cache()
        headers = {
            "X-Forwarded-Email": "reviewer@cern.ch",
            "Origin": self.server_module.APP_ORIGIN,
        }
        status, _, summary = self.request(
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608", headers=headers
        )
        self.assertEqual(status, 200)
        item = next(iter(summary["evidence"].values()))
        request = {
            **{field: item[field] for field in ("dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256")},
            "state": "reviewed_no_optical_concern",
            "note": "",
            "expected_current_event_id": None,
            "mutation_id": str(uuid.uuid4()),
        }

        # When: a protected montage's deployed bytes drift after that GET.
        montage = self.server_module.ROOT / item["montage_uri"]
        montage.write_bytes(montage.read_bytes() + b"drift")
        status, _, payload = self.request("/api/etroc-reviews", "POST", request, headers)

        # Then: the new mutation fails closed and appends no event.
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"]["code"], "evidence_unavailable")
        with sqlite3.connect(self.server_module.DB_PATH) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM etroc_review_events").fetchone()[0], 0)

    def test_cern_principal_validation_is_shared_by_header_and_allowlist(self):
        # Given: canonical CERN identities and malformed printable/header values.
        accepted = ("ypark", "ypark@cern.ch", "YPark@CERN.CH")
        rejected = ("", " ypark", "ypark ", "ypark@other.org", "ypark@cern.ch,other", "ypark\t", "ypark\n", "ypark/../../x")

        # When / Then: the same canonical parser governs both trust boundaries.
        self.assertEqual(
            self.server_module.etroc_reviewer_allowlist(",".join(accepted)),
            {"ypark", "ypark@cern.ch"},
        )
        for value, canonical in (("ypark", "ypark"), ("ypark@cern.ch", "ypark@cern.ch"), ("YPark@CERN.CH", "ypark@cern.ch")):
            with self.subTest(accepted_value=value):
                self.assertEqual(
                    self.server_module.identity({"X-Forwarded-Email": value})["user"],
                    canonical,
                )
        for value in rejected:
            with self.subTest(value=repr(value)):
                self.assertIsNone(self.server_module.identity({"X-Forwarded-Email": value}))
        for value in ("", " ypark", "ypark ", "ypark@other.org", "ypark\t", "ypark\n", "ypark/../../x", "ypark@cern.ch,"):
            with self.subTest(allowlist_value=repr(value)):
                self.assertEqual(self.server_module.etroc_reviewer_allowlist(value), set())

    def test_read_json_rejects_invalid_content_length_before_reading(self):
        # Given: handlers whose request stream records whether it was consumed.
        class ReadProbe(io.BytesIO):
            def __init__(self):
                super().__init__(b'{"unexpected":true}')
                self.read_calls = 0

            def read(self, size=-1):
                self.read_calls += 1
                return super().read(size)

        # When / Then: malformed lengths fail before touching the input stream.
        class HandlerProbe:
            def __init__(self) -> None:
                self.headers = Message()
                self.rfile = ReadProbe()

        for length in (None, "", "-1", "+1", "1.0", " 1", "10001", "١"):
            with self.subTest(length=repr(length)):
                handler = HandlerProbe()
                if length is not None:
                    handler.headers["Content-Length"] = length
                with self.assertRaises(ValueError):
                    self.server_module.read_json(handler)
                self.assertEqual(handler.rfile.read_calls, 0)

    def test_asset_oserror_returns_json_503_for_every_review_read_route(self):
        # Given: an authenticated reviewer and a canonical evidence loader whose asset read fails.
        headers = {"X-Forwarded-Email": "reviewer@cern.ch"}
        acquisition_id = next(iter(self.server_module.load_etroc_review_evidence(STATIC_ROOT).by_acquisition))
        encoded = urllib.parse.quote(acquisition_id, safe="")

        # When / Then: no review endpoint leaks the filesystem error.
        for route in (
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608",
            f"/api/etroc-reviews/history?acquisition_id={encoded}",
            f"/api/etroc-reviews/audit?acquisition_id={encoded}",
        ):
            with self.subTest(route=route), mock.patch.object(
                self.server_module,
                "load_etroc_review_evidence",
                side_effect=OSError("asset missing"),
            ):
                status, _, payload = self.request(route, headers=headers)
                self.assertEqual(status, 503)
                self.assertEqual(payload["error"]["code"], "evidence_unavailable")

    def test_invalid_get_queries_fail_before_evidence_loading_during_outage(self):
        # Given: an evidence loader outage and malformed syntax for every read endpoint.
        headers = {"X-Forwarded-Email": "reviewer@cern.ch"}
        routes = (
            "/api/etroc-reviews?dataset_id=ETROC_OI_2608&extra=1",
            "/api/etroc-reviews/history?acquisition_id=bad&extra=1",
            "/api/etroc-reviews/audit?acquisition_id=bad&extra=1",
        )

        # When / Then: syntax errors remain client errors without touching evidence.
        for route in routes:
            with self.subTest(route=route), mock.patch.object(
                self.server_module,
                "load_etroc_review_evidence",
                side_effect=OSError("asset missing"),
            ) as loader:
                status, _, payload = self.request(route, headers=headers)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "invalid_query")
                loader.assert_not_called()

    def test_missing_evidence_files_return_structured_unavailable(self):
        # Given: static roots missing either chips.json or the checksum manifest.
        headers = {"X-Forwarded-Email": "reviewer@cern.ch"}
        source = STATIC_ROOT / "data/etroc-optical/ETROC_OI_2608"
        for missing in ("chips.json", "SHA256SUMS"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "data/etroc-optical/ETROC_OI_2608"
                shutil.copytree(source, target)
                (target / missing).unlink()
                self.server_module.ROOT = root
                self.server_module.reset_etroc_review_evidence_cache()

                # When: a syntactically valid summary reaches the broken publication root.
                status, _, payload = self.request(
                    "/api/etroc-reviews?dataset_id=ETROC_OI_2608", headers=headers
                )

                # Then: the filesystem outage is caught at the API boundary.
                self.assertEqual(status, 503)
                self.assertEqual(payload["error"]["code"], "evidence_unavailable")
