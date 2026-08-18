# Tab-local Scientific Dashboards — PRD v0.1

## Problem

The BBQC statistical dashboard is currently outside the three-tab content model, so it remains visible while users inspect unrelated pre-bonding ETROC and LGAD evidence. The ETROC and LGAD tabs have inventories but no tab-specific statistical overview.

## Goal

Place one scientifically scoped dashboard inside each matching tab:

1. **Bump-bonding analysis result** — the existing 72-Hybrid BBQC dashboard.
2. **Pre-bonding ETROC optical inspection montage** — a new dashboard for the exact 36 unbonded ETROCs in `ETROC_OI_2608`.
3. **LGAD optical inspection panoramas** — an availability/inventory dashboard for the exact 35 panorama cards.

Only the active tab's dashboard is visible.

## Users

- ETL/KNU QC reviewers
- Engineers triaging optical screening candidates
- Production coordinators checking evidence coverage

## MVP scope

### BBQC tab

- Move the existing dashboard unchanged into `#bbqc` before the tab's controls and legacy six-metric summary.
- Preserve its 72-Hybrid DOM/API data sources and live-review degraded state.

### ETROC optical tab

- Compute all metrics at runtime from the validated `chips.json` payload.
- KPIs: `36` ETROCs, `9,216` positions, red candidates `17/9,216`, needs-inspection `82/9,216`, optical no-ball candidates `3/9,216`.
- Charts: five-category position composition; wafer-normalized category composition; per-ETROC review-candidate workload.
- Audit table: exact serial, wafer, five category counts, review candidates, optical no-ball candidates, and montage link.
- Wafer/search controls filter charts/table as one visible cohort; every rate shows `n/N`.

### LGAD optical tab

- Derive from the 35 existing `.lgad-card` elements.
- KPIs: 35 sensors, 8,960 tiles (`35 × 256`), 35 panoramas, four source groups.
- Group distribution: HPK1 `8/35`, HPK3 `9/35`, LF1 `9/35`, LF2 `9/35`.
- Explicitly label this as evidence availability/inventory, not algorithm screening or confirmed QC.

## Scientific constraints

- ETROC counts are **algorithmic screening categories**, not PASS/FAIL dispositions.
- `review_candidate_count` is a review workload indicator and is not an additional disjoint category in the 256-position partition.
- LGAD panorama existence proves evidence availability only.
- Pre-bonding ETROCs remain outside the canonical 72-Hybrid inventory and APIs.
- Height distribution/mean/RMS are out of scope because the 9,216 individual height values are not in the published web bundle; only their cardinality, unit declaration, and checksum are available.
- Exact component, acquisition, wafer, source, and analysis-run identifiers remain unchanged; the approved cohort is visibly reported as five immutable runs (`pack2=17`, `pack1=9`, `pack1_original=8`, `re_chip24=1`, `re_chip51=1`).

## Non-goals

- Reclassification, threshold tuning, or human adjudication.
- Database/API/schema changes.
- Adding unbonded components to the Hybrid registry.
- External chart libraries or CDN dependencies.
- Inventing LGAD quality outcomes.

## Success criteria

- Each dashboard is a descendant of its matching `.tab` section.
- Switching tabs exposes only the matching dashboard.
- ETROC totals exactly reconcile to 36 records and 9,216 positions; the five partition counts total 9,216.
- Wafer subsets reconcile to 18/9/9 ETROCs and 4,608/2,304/2,304 positions.
- LGAD group totals reconcile to 35 cards and 8/9/9/9.
- Malformed ETROC data fails closed with an announced unavailable state.
- Existing canonical Hybrid digest and count remain unchanged.
- Keyboard, screen-reader, reduced-motion, desktop, and narrow-mobile behavior are verified.

## Definition of done

- TDD tests cover placement, calculations, malformed data, filter/table semantics, and invariant inventories.
- Full regression suite passes.
- Local production server serves all assets.
- Real-browser QA verifies all three tabs, chart/table values, responsive behavior, and console/network cleanliness.
- Independent spec/quality review passes before commit.
