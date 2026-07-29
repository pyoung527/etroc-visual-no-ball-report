# BBQC Hybrid Registry Bridge Implementation Plan

> **For Hermes:** Use strict RED–GREEN–REFACTOR and independent review for this plan.

**Goal:** Add a stable BBQC hybrid registry that bridges pair-based QC records to ETL Hybrid identities without changing ETL or breaking existing comment APIs.

**Architecture:** Extend the existing comments SQLite database with `hybrid_registry`, `hybrid_target_aliases`, and nullable `comments.hybrid_registry_id`. Seed canonical pairs and redirect aliases from the deployed static site at startup, then expose read and admin binding endpoints.

**Tech Stack:** Python 3.12 standard library, SQLite, `http.server`, `unittest`, OpenShift.

---

## Design Gate

- Chosen: BBQC-local bridge table; ETL unchanged.
- Approved by Young: 2026-07-29.
- Compatibility: legacy `comments.target` and existing `/api/comments*` routes remain supported.
- Physical ETL writes: out of scope.

### Task 1: Add failing migration and seed tests

**Files:**
- Create: `tests/test_hybrid_registry.py`
- Modify later: `hybrid-bbqc/server.py`

1. Build a temporary static root containing two canonical dashboard links and one redirect page.
2. Build a legacy comments-only SQLite database.
3. Assert `init_db(db_path, static_root)` creates/seeds registry and aliases.
4. Assert a legacy target is preserved and receives `hybrid_registry_id`.
5. Run `python -m unittest tests.test_hybrid_registry -v`.
6. Expected RED: missing parameterized `init_db`/registry behavior.

### Task 2: Implement idempotent schema and startup migration

**Files:**
- Modify: `hybrid-bbqc/server.py`

1. Add database connection, pair parsing, static discovery and schema helpers.
2. Create tables/indexes and migrate the comments column.
3. Seed canonical and redirect aliases.
4. Backfill existing hybrid comments by registry ID without rewriting legacy targets.
5. Re-run the focused test; expected GREEN.
6. Add a second-init assertion; expected no duplicate rows or errors.

### Task 3: Add failing resolver and ETL binding tests

**Files:**
- Modify: `tests/test_hybrid_registry.py`

1. Assert canonical and legacy targets resolve to the same stable registry ID.
2. Assert valid ETL binding persists IDs, serial, status and provenance.
3. Assert `matched` without ETL serial is rejected.
4. Assert duplicate ETL serial/ID and unknown pair are rejected.
5. Run focused tests; expected RED before implementation.

### Task 4: Implement resolver and binding service functions

**Files:**
- Modify: `hybrid-bbqc/server.py`

1. Add normalized pair/status validation.
2. Add target resolution and parameterized registry lookup.
3. Add atomic ETL binding update with explicit error responses.
4. Run focused and full tests; expected GREEN.

### Task 5: Add HTTP API integration tests and routes

**Files:**
- Modify: `tests/test_hybrid_registry.py`
- Modify: `hybrid-bbqc/server.py`

1. Start `ThreadingHTTPServer` against a temporary DB/root.
2. Assert `GET /api/hybrids?pair_key=...` returns the seeded row.
3. Assert unauthenticated bind returns 401 and non-admin returns 403.
4. Assert admin bind returns 200 and readback shows `matched`.
5. Assert legacy comments target resolves to canonical comments.
6. Implement minimal routes; rerun tests to GREEN.

### Task 6: Update deployment and operations documentation

**Files:**
- Modify: `hybrid-bbqc/openshift/deployment.yaml`
- Modify: `README_CERN_DEPLOY.md`

1. Add `COMMENTS_ADMIN_USERS` with Young's CERN username/email forms.
2. Document automatic migration, registry APIs, backup, verification and rollback.
3. Validate YAML and inspect the rendered diff.

### Task 7: Final verification and review

1. Run `python -m unittest discover -s tests -v`.
2. Start the real service locally with a temporary DB; request health, registry and comments endpoints.
3. Exercise bind auth and successful admin binding.
4. Inspect the SQLite schema, counts, aliases and foreign-key links.
5. Build the container image if the local engine is available.
6. Run security scans and independent code review.
7. Run `graphify update .` and verify the graph report includes the new registry functions.
8. Report any deployment step not performed; do not modify production without a separate deployment decision.

### Independent-review hardening amendment

The first independent review found deployment blockers. They are incorporated
as mandatory completion criteria:

1. Reject partial binding and non-integer/out-of-range ETL IDs; serialize the
   first immutable binding and reject identity replacement.
2. Preserve stored comment targets; aggregate hybrid reads by registry ID.
3. Preserve identity for ETROC-side and LGAD-side corrections using redirect or
   unambiguous child evidence; include existing alias/comment ownership and fail
   closed on ambiguous or retargeted provenance. Globally reject stale
   alias/comment owner mismatches and backfill only null owners.
4. Bind the backend to loopback and trust only oauth2-proxy's
   `X-Forwarded-Email` header passed upstream by `--pass-user-headers`.
5. Require exact Origin on mutations and JSON content type for request bodies.
6. Use `Recreate` to prevent overlapping SQLite writers.
7. Pin releases/rollbacks to image digests and verify backups, exact 72-row
   coverage, unresolved comments, foreign keys, integrity, logs and external SSO.
