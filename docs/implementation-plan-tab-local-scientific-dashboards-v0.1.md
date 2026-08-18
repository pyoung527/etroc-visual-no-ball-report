# Tab-local Scientific Dashboards — Implementation Plan v0.1

> Implement with strict RED–GREEN–REFACTOR and independent review before commit.

## Task 1 — Lock placement and inventory contracts

**Tests:** create `tests/test_tab_local_dashboards.py`; extend `tests/test_etroc_optical_pool.py`.

1. Add failing tests requiring each dashboard to be a descendant of the matching tab.
2. Require the first tab to preserve the exact 72-Hybrid digest.
3. Require ETROC 36 and LGAD 35 exact inventories and local assets only.
4. Run focused tests and confirm RED.

## Task 2 — Move BBQC dashboard into its tab

**File:** `hybrid-bbqc/index.html`.

1. Move the unchanged `#bbqc-analytics` markup to the beginning of `#bbqc`.
2. Move the legacy six-metric BBQC summary with it so unrelated tabs no longer display Hybrid metrics.
3. Keep `dashboard.js` behavior and canonical table/card DOM unchanged.
4. Run placement and analytics regression tests GREEN.

## Task 3 — Add ETROC statistics dashboard

**Files:** `hybrid-bbqc/index.html`, `hybrid-bbqc/etroc-optical.js`, `hybrid-bbqc/etroc-optical.css`, tests.

1. Write failing calculation tests for exact totals, wafer totals, partition reconciliation, and filtered cohorts.
2. Export a pure aggregate helper through `ETROCOpticalContract` and verify malformed/overlapping semantics fail closed.
3. Add semantic KPI, composition, wafer, workload, filters, and audit-table containers.
4. Render all values from the already validated payload; preserve full montage links.
5. Verify the exact 17/82/3 counts and 6,512/2,035/570/17/82 partition.

## Task 4 — Add LGAD availability dashboard

**Files:** `hybrid-bbqc/index.html`, create `hybrid-bbqc/lgad-optical-stats.js`, extend CSS/tests.

1. Write failing tests for 35 cards, 8/9/9/9 groups, 8,960 tiles, and evidence-only wording.
2. Compute from existing card/group DOM without adding scientific outcome fields.
3. Render four KPIs and direct-labeled group bars inside `#lgad-optical`.
4. Keep existing search/card behavior unchanged.

## Task 5 — Browser and regression verification

1. Run focused and full Python test suites with bytecode disabled.
2. Run JS contract tests against real `chips.json`, including malformed payloads.
3. Start the production server on a verified free port.
4. In a real browser verify:
   - only the active tab's dashboard is visible;
   - exact ETROC/LGAD totals and filters;
   - full montage links;
   - malformed-data fail-closed state;
   - desktop and narrow-mobile layouts;
   - no console/network errors.
5. Run `graphify update .`, `git diff --check`, and the full suite again.

## Task 6 — Independent review and commit

1. Review exact final diff for scientific semantics, identity boundaries, XSS, calculation denominators, accessibility, and regression safety.
2. Fix blockers and repeat all gates.
3. Commit/push only after PASS.
4. Production deployment is a separate explicitly authenticated operation; this implementation request does not imply deployment.
