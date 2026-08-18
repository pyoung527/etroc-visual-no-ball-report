# ETROC_OI_2608 Montage Pool Implementation Plan

> **For Hermes:** Implement task-by-task with strict TDD and independent review before commit/deploy.

**Goal:** Add the 36-chip ETROC_OI_2608 pre-bonding optical montage dataset to BBQC’s existing Pre-bonding ETROC optical inspection tab without changing the canonical 72-Hybrid inventory or presenting exploratory screening as confirmed QC.

**Architecture:** Publish an immutable static dataset bundle under `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/`, with one validated JSON chip pool and optimized montage/preview JPEG assets generated from the exploratory analysis output. `hybrid-bbqc/etroc-optical.js` renders a new dataset block safely with DOM APIs before the legacy Hybrid-linked optical pool. No database migration or `/api/hybrids` change is required.

**Tech Stack:** Python 3/Pillow build tool, static JSON/JPEG assets, vanilla JavaScript/CSS, `unittest`, existing CERN OKD Binary Build/overlay deployment workflow.

---

## Design Gate

Options considered:

1. Append 36 fake Hybrid cards — rejected because none of the ETROCs is mapped to the current Hybrid registry and this would corrupt the 72-Hybrid KPI/identity model.
2. Embed 422 MB of source montage PNGs — rejected because equivalent web JPEG assets preserve the montage visualization with substantially smaller build/deployment footprint.
3. Add an independent ETROC optical dataset block inside the existing optical tab — selected.

Chosen behavior:

- Display the exact 36 ETROC serials grouped by W02G4/W03F7/W05E5.
- Show `Exploratory · review pending`, 256/256 coverage, and algorithmic candidate counts without PASS/FAIL language.
- Open an optimized full montage from each card; use a separate preview asset in the grid.
- Keep the current 72 Hybrid rows/cards and their URLs unchanged.
- Fail visibly with `ETROC optical dataset unavailable` if JSON loading or validation fails.

Approval needed before implementation: no — Young explicitly requested that this pool be updated and displayed.

---

### Task 1: Lock the static data-pool contract

**Files:**
- Create: `tests/test_etroc_optical_pool.py`
- Create: `tools/build_etroc_optical_pool.py`
- Create: `hybrid-bbqc/data/etroc-optical/ETROC_OI_2608/chips.json`

**Steps:**
1. Write tests requiring exactly 36 unique ETROC records, exact wafer counts 18/9/9, 256 image and height rows per chip, review-pending status, no Hybrid/LGAD IDs, relative asset URIs, and no local absolute paths.
2. Run the focused test and verify RED because the pool does not exist.
3. Implement the builder to read the validated exploratory chip summary, generate immutable records, convert montage PNGs to full/preview JPEGs, and record source/published SHA-256 and byte size.
4. Generate the bundle from `outputs/etroc_oi_2608_common_baseline_v0`.
5. Re-run the focused tests and verify GREEN.

### Task 2: Render the new pool in the existing optical tab

**Files:**
- Modify: `hybrid-bbqc/index.html`
- Create: `hybrid-bbqc/etroc-optical.js`
- Create: `hybrid-bbqc/etroc-optical.css`
- Test: `tests/test_etroc_optical_pool.py`

**Steps:**
1. Add failing tests for the dataset root, stylesheet/script references, loading/unavailable live region, safe DOM rendering (`textContent`, no data-driven `innerHTML`), and preservation of 72 canonical Hybrid detail links.
2. Verify RED.
3. Add a dataset container at the start of `#optical`, load the JSON, validate the expected dataset/cardinality in the browser, and render wafer-grouped cards using DOM creation.
4. Add responsive/reduced-motion-aware card styling and explicit exploratory semantics.
5. Verify focused tests GREEN.

### Task 3: Verify data, UI, and regression boundaries

**Files:**
- Test: existing test suite plus `tests/test_etroc_optical_pool.py`

**Steps:**
1. Run all Python tests with bytecode disabled.
2. Parse all JSON and validate every montage/preview checksum, MIME type, dimensions, and relative URI.
3. Start the app locally and verify the DOM contains 36 new cards, wafer counts 18/9/9, visible exploratory caveat, working asset links, and unchanged 72-Hybrid inventory.
4. Run browser console checks for fetch/JavaScript errors and test the failed-data state.
5. Run `graphify update .` and re-run the focused/full tests.

### Task 4: Independent review and commit

**Steps:**
1. Inspect `git diff --stat`, split the large binary-asset diff from code review, and scan added source lines for secrets/injection hazards.
2. Dispatch an independent reviewer for contract, XSS, identity-boundary, accessibility, and regression review.
3. Fix blockers and repeat verification.
4. Commit only after review passes.

### Task 5: Safe CERN OKD rollout

**Target:** production application `etl-hybrid-bbqc`; exact API/project/deployment must be re-established by authenticated preflight before mutation.

**Steps:**
1. Verify CERN account, API server, project, deployment/route, active source revision/image digest, rollout permissions, and current live 72-Hybrid state.
2. Use the existing reviewed binary-build/overlay helper only after updating and re-running its static allowlist/provenance tests for the new JSON/JS/CSS/JPEG assets.
3. Capture backup/release/rollback coordinates and server-side dry-run the forward state.
4. Build and roll out from an allowlisted clean context; verify runtime asset checksums and internal health.
5. Verify external CERN SSO redirect, then authenticated live DOM: 36 new ETROC cards, exact wafer counts, working montage links, unchanged Hybrid 72.
6. Roll back on any failed gate; production remains unchanged if authentication or preflight is unavailable.
