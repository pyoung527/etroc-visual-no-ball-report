# ETROC Acquisition Review Workspace Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Implement a same-page, evidence-bound, append-only ETROC acquisition review workflow for the exact 36-record `ETROC_OI_2608` publication without changing bonded Hybrid identities or existing comments.

**Architecture:** Publish montage bytes at content-addressed paths; load and validate an immutable 36-record evidence map in the Python server; persist review events in a dedicated exact-schema SQLite subsystem; expose protected summary/history/audit/append APIs; and join live review state into a verified-Blob accessible browser workspace. Preserve the existing SSO proxy, Hybrid registry/comments, tab-local scientific dashboard, immutable analysis payload, and previous-binary compatibility.

**Tech Stack:** Python 3.11 stdlib HTTP/SQLite, pytest/unittest, browser JavaScript with Web Crypto and safe DOM APIs, HTML/CSS, OpenShift YAML/bash deployment helper, graphify.

---

## Design Gate

- PRD: `docs/prd-etroc-acquisition-review-workspace-v0.1.md`
- Architecture: `docs/architecture-etroc-acquisition-review-workspace-v0.1.md`
- Independent design verdict: PASS on 2026-08-19.
- User approval: explicit implementation approval on 2026-08-19.
- Production deployment is not part of implementation completion and requires a separate quota/auth/release preflight.

## Task 1: Content-addressed ETROC montage publication

**Objective:** Make every canonical montage URI immutable and digest-addressed.

**Files:**
- Modify: `tests/test_etroc_optical_pool.py`
- Modify: `tools/build_etroc_optical_pool.py`
- Modify/regenerate: `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/chips.json`
- Create/regenerate: `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/montages/sha256/*.jpg`
- Modify/regenerate: `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/SHA256SUMS`

**TDD cycle:**
1. Add tests requiring `montages/sha256/<montage_sha256>.jpg`, exact file-byte hash, one canonical URI per record, and no serial-addressed montage dependency.
2. Run the focused tests and confirm expected failure on current `montages/<serial>.jpg` output.
3. Render to a temporary file, calculate the digest, atomically publish to the digest path, and preserve stable serial previews only.
4. Regenerate the checked-in publication from the existing validated bytes without changing scientific counts/provenance/identities.
5. Run: `PYTHONPATH=. python3 -m pytest tests/test_etroc_optical_pool.py -q -p no:cacheprovider`.

## Task 2: Evidence loader and exact ETROC review schema

**Objective:** Add a dedicated server-side evidence loader and exact additive review schema without changing `PRAGMA user_version` semantics for the existing Hybrid subsystem.

**Files:**
- Create: `hybrid-bbqc/etroc_reviews.py`
- Create: `tests/test_etroc_reviews.py`
- Modify: `hybrid-bbqc/server.py`

**TDD cycle:**
1. Add failing tests for raw `chips.json` SHA-256, exact 36-entry map, duplicate acquisition/key rejection, digest-path/file verification, and deployment skew failure.
2. Add failing migration tests for true legacy DB, exact version `0→1`, second-run idempotency, drift/future/partial-schema rejection, injected rollback, unchanged `PRAGMA user_version`, and previous-binary comment compatibility.
3. Implement immutable evidence records plus exact DDL/index/trigger validation from the approved architecture.
4. Verify second-root, fork, cross-key successor, direct UPDATE/DELETE, state/note, FK, and integrity invariants.
5. Run focused backend tests.

## Task 3: Review service and HTTP API contracts

**Objective:** Implement summary/capability/history/audit/append behavior with authorization, optimistic concurrency, and idempotent retry.

**Files:**
- Modify: `hybrid-bbqc/etroc_reviews.py`
- Modify: `hybrid-bbqc/server.py`
- Modify: `tests/test_etroc_reviews.py`

**TDD cycle:**
1. Add failing service/API tests for exact 36-entry summary evidence map, empty valid reviews, server-derived `viewer.can_append_review`, strict GET query parsing, current history, historical audit, and no-store responses.
2. Add failing POST tests for allowlist fail-closed behavior, same-origin/JSON checks, full five-field evidence match, state/note validation, root/successor append, stale `409`, committed-response-lost replay, divergent mutation-ID reuse, and evidence changes.
3. Implement transaction-first idempotency lookup and `BEGIN IMMEDIATE` append/readback.
4. Wire `/api/etroc-reviews`, `/history`, `/audit`, and POST into `Handler` without routing ETROCs through `hybrid_registry` or comments.
5. Run focused API tests and the existing Hybrid registry/comment suites.

## Task 4: Frontend contract and verified evidence controller

**Objective:** Implement raw-publication hashing, full evidence reconciliation, verified montage Blob display, capability/read-only state, and deterministic queue logic.

**Files:**
- Create: `hybrid-bbqc/etroc-review.js`
- Create: `tests/test_etroc_review_frontend.py`
- Modify: `hybrid-bbqc/etroc-optical.js`

**TDD cycle:**
1. Add Node/browser-contract tests for raw-byte SHA-256 parsing, exact 36-key reconciliation, full five-field joins, content-addressed URI checks, capability rendering, and fail-closed degradation.
2. Add deterministic comparator/queue tests: card-only state filter, Start/Resume snapshot, direct-unreviewed anchor/no-wrap, reviewed correction mode, live remote skip, conflict/no-advance.
3. Implement pure exported contract functions first, then browser controller state.
4. Fetch `chips.json` as bytes, hash and parse the same bytes, fetch summary, reconcile all evidence, then hash/display the exact montage Blob.
5. Preserve one `mutation_id` per unchanged logical draft and reconcile timeout retries.

## Task 5: Accessible review workspace UI

**Objective:** Replace new-tab montage review with an accessible same-page full-screen dialog.

**Files:**
- Modify: `hybrid-bbqc/index.html`
- Modify: `hybrid-bbqc/etroc-optical.js`
- Modify: `hybrid-bbqc/etroc-review.js`
- Modify: `hybrid-bbqc/etroc-optical.css`
- Modify: `tests/test_etroc_review_frontend.py`
- Modify: `tests/test_tab_local_dashboards.py`

**TDD cycle:**
1. Add failing structure/contract tests for `role=dialog`, `aria-modal`, labelled title, status region, state radios, note, Save, Save & Next, navigation, close, and local script ordering.
2. Implement card/table review buttons using safe DOM APIs; retain an explicitly labelled static fallback link only when live review is unavailable.
3. Implement focus trap/restoration, Escape/overlay/dirty-draft behavior, keyboard suppression in editable controls, zoom/pan/reset, text+color states, and narrow-mobile layout.
4. Update cards/progress/filter controls from the live exact-key review map without changing scientific denominators.
5. Run focused frontend/dashboard tests.

## Task 6: OpenShift and deployment gates

**Objective:** Package and validate the review subsystem while preserving the existing proxy boundary and rollback behavior.

**Files:**
- Modify: `hybrid-bbqc/openshift/deployment.yaml`
- Modify: `hybrid-bbqc/openshift/deploy_dashboard_overlay_lxplus.sh`
- Modify: `tests/test_lxplus_dashboard_deploy.py`

**TDD cycle:**
1. Add failing helper tests for `ETROC_REVIEWER_USERS`, content-addressed montage inventory, `chips.json` publication hash, exact 36-entry API evidence map, review schema/startup probe, and required oauth2-proxy topology.
2. Add external header-spoof and proxy-derived identity acceptance commands without client-selected author headers.
3. Update immutable asset lists/checksums/runtime gates and preserve previous Deployment rollback coordinates.
4. Validate with `bash -n` and focused helper tests. Do not authenticate or deploy in this task.

## Task 7: Integration, browser QA, graph refresh, and independent review

**Objective:** Prove the feature works end-to-end locally and is merge-ready.

**Files:**
- All changed files above.
- Update: `graphify-out/graph.json`, `graphify-out/graph.html`, `graphify-out/GRAPH_REPORT.md`.

**Steps:**
1. Run the complete suite with the required import path and caches disabled.
2. Start the real server on an available local port with a disposable SQLite DB, test static assets and all review API paths, and inspect logs.
3. Exercise desktop and narrow-mobile flows in a real browser: load, open, verified image, create review, Save & Next, correction, conflict, timeout replay, dirty close, read-only capability, and keyboard/focus behavior.
4. Run `graphify update .` after code changes.
5. Run `git diff --check`, inspect final diff/status, and ensure no ETROC rows entered `hybrid_registry`.
6. Obtain independent spec, security/data-integrity, and frontend/accessibility review against the final diff; fix all HIGH/MEDIUM findings and rerun affected tests.
7. Commit implementation on `feat/etroc-oi-2608`; do not push or deploy without an explicit release decision.

## Final Verification Commands

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:/tmp/etroc-visual-no-ball-report-plan \
  python3 -m pytest -q -p no:cacheprovider
bash -n hybrid-bbqc/openshift/deploy_dashboard_overlay_lxplus.sh
graphify update .
git diff --check
git status --short
```

Expected: all tests pass, shell syntax passes, graph refresh succeeds, diff check passes, and only approved implementation/docs/assets are changed.
