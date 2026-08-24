# ETROC Position Review Overlay Implementation Plan

> **For Hermes:** Use TDD and single-writer implementation; independently review final scientific semantics, data integrity/security, and accessibility.

**Goal:** Add deterministic clean montages, exact position publications, append-only position review APIs, and an accessible SVG overlay/queue to the existing ETROC acquisition workspace.

**Architecture:** Preserve labelled montage evidence; generate digest-addressed clean derivatives and 256-position documents; add an independent append-only position event subsystem; reconcile exact position evidence in the browser before enabling review.

**Tech Stack:** Python/Pillow build tooling, Python stdlib HTTP/SQLite, browser JavaScript/Web Crypto/SVG, HTML/CSS, pytest, OpenShift release helper.

---

## Design gate

- PRD: `docs/prd-etroc-position-review-overlay-v0.1.md`
- Architecture: `docs/architecture-etroc-position-review-overlay-v0.1.md`
- User approval: explicit `구현 시작해` in the current session.
- AFK defaults: review-target cohort is immutable `NEED_INSPECT`; all positions are directly selectable; clean montage is default; no automatic acquisition disposition.

## Task 1: Deterministic clean montage and position publication

**Files**
- Modify: `tools/build_etroc_optical_pool.py`
- Modify: `tests/test_etroc_optical_pool.py`
- Regenerate: `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/chips.json`
- Create: `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/clean-montages/sha256/*.jpg`
- Create: `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/positions/sha256/*.json`
- Regenerate: `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/SHA256SUMS`

**TDD**
1. Add failing tests for exact 36 clean assets, 36 position documents, 9,216 unique position rows, 82 `NEED_INSPECT` targets, fixed geometry, exact digests, and unchanged labelled bytes.
2. Run focused tests and confirm RED.
3. Extend validation to retain canonical position rows and hash source images.
4. Implement deterministic clean rendering with pinned geometry/encoder.
5. Publish content-addressed JSON/assets and add exact record fields.
6. Regenerate from `/home/young-park/projects/optical_inspection/outputs/etroc_oi_2608_common_baseline_v0` and verify reproducibility with a second disposable build.
7. Run `uv run --with pytest --with pyyaml --with 'Pillow==12.2.0' python -m pytest tests/test_etroc_optical_pool.py -q -p no:cacheprovider`.

## Task 2: Position evidence loader and exact schema

**Files**
- Create/Modify: `hybrid-bbqc/etroc_position_reviews.py`
- Modify: `hybrid-bbqc/etroc_reviews.py` only for additive namespace coexistence
- Modify: `hybrid-bbqc/server.py`
- Create/Modify: `tests/test_etroc_position_reviews.py`

**TDD**
1. Add RED tests for exact 36×256 evidence, position-publication/clean/source hashes, geometry/category/target reconciliation, deployment skew, and a new unreviewed chain when `position_publication_sha256` changes.
2. Add RED migration tests for legacy DB, complete normative DDL/managed-object inventory, exact additive v1 schema, idempotency, drift/future/partial rejection, rollback, and unchanged existing schemas/events/comments.
3. Implement immutable position evidence records and exact DDL/index/trigger validation.
4. Test one root, one successor, no fork/cross-position supersession, no update/delete, note/state constraints, FK and integrity.
5. Run focused backend tests.

## Task 3: Position summary/history/append API

**Files**
- Create/Modify: `hybrid-bbqc/etroc_position_reviews.py`
- Modify: `hybrid-bbqc/etroc_reviews.py` only for additive namespace coexistence
- Modify: `hybrid-bbqc/server.py`
- Create/Modify: `tests/test_etroc_position_reviews.py`

**TDD**
1. Add RED tests for strict query parsing, exact no-store response shapes, complete 256-entry summary evidence, history, and DB-derived historical audit.
2. Add RED tests for capability, read-only access, same-origin JSON POST, unknown fields, complete key including `position_publication_sha256`, root/successor, stale `409`, exact replay, divergent mutation reuse, error precedence, and historical-only mutation rejection.
3. Implement service transactions and HTTP routes.
4. Verify acquisition API and Hybrid tests remain unchanged.

## Task 4: Verified position controller and SVG overlay

**Files**
- Modify: `hybrid-bbqc/etroc-review.js`
- Modify: `tests/test_etroc_review_frontend.py`

**TDD**
1. Add RED pure-contract tests for exact position JSON/hash/keyset/geometry validation and server reconciliation.
2. Add RED queue tests: Start snapshots only currently unreviewed targets; direct unreviewed target anchors that queue; reviewed/non-target direct selection is single-item correction/ad-hoc without Save & Next; live refresh skips remote completion without expanding the snapshot or changing its denominator; conflict never advances; mutation retry is stable.
3. Add RED Blob-generation tests proving the same clean Blob is hashed, decoded, displayed, cropped, and revoked.
4. Implement controller state, verified mode switching, and SVG cell model.

## Task 5: Position review UI

**Files**
- Modify: `hybrid-bbqc/index.html`
- Modify: `hybrid-bbqc/etroc-review.js`
- Modify: `hybrid-bbqc/etroc-optical.css`
- Modify: `tests/test_etroc_review_frontend.py`
- Modify: `tests/test_tab_local_dashboards.py`

**TDD**
1. Add RED structure/accessibility tests for montage toggles, algorithm/human overlay controls, target progress, position grid, crop panel, state controls, note, history, Save/Save & Next.
2. Implement clean-default viewport with analysis toggle and synchronized SVG overlay.
3. Implement keyboard grid navigation, focus restoration, dirty confirmation, responsive crop/decision pane, read-only capability, accessible announcements, reduced motion.
4. Preserve acquisition-level controls as a clearly separate section.

## Task 6: Release packaging and deployment gates

**Files**
- Modify: `hybrid-bbqc/openshift/deploy_dashboard_overlay_lxplus.sh`
- Modify: `tests/test_lxplus_dashboard_deploy.py`

**TDD**
1. Add RED tests for clean/position inventory, checksums, exact runtime evidence map, additive DB schema, zero-event smoke, source/asset pins, and rollback compatibility.
2. Update immutable build context and post-rollout read-only gates.
3. Run focused helper tests and `bash -n`.
4. Do not deploy until local/browser/review gates pass and an explicit release action is taken.

## Task 7: Integration and review

1. Run full pytest with bytecode/cache disabled.
2. Start a disposable local server and exercise summary/history/append/replay/conflict.
3. Run desktop and narrow-mobile browser QA for clean/analysis modes, overlay alignment, target queue, ad-hoc position, Save & Next, correction, conflict, dirty close, read-only and keyboard flow.
4. Verify 36 labelled + 36 clean montages, 36 position documents, 9,216 positions, 82 targets, exact hashes, 74 existing Hybrid comments in production backup fixtures, and no fabricated Hybrid identities.
5. Run `graphify update .`, `git diff --check`, and inspect final status.
6. Obtain independent spec, scientific/data-integrity/security, and frontend/accessibility reviews; fix HIGH/MEDIUM findings and rerun.
7. Commit and push immutable implementation. Production deployment is a separate verified release step.

## Final commands

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml --with 'Pillow==12.2.0' \
  python -m pytest -q -p no:cacheprovider
bash -n hybrid-bbqc/openshift/deploy_dashboard_overlay_lxplus.sh
graphify update .
git diff --check
git status --short
```
