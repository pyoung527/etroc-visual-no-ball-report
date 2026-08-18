# Tab-local Scientific Dashboards — Architecture v0.1

## Surface and placement

Primary surface: **Monitor**. Density and auditability take priority over a hero composition.

```text
nav.tabs
├── #bbqc.tab
│   ├── #bbqc-analytics (existing, moved here)
│   └── existing summary / views / filters / table
├── #optical.tab
│   ├── #etroc-optical-analytics (new)
│   ├── ETROC_OI_2608 pool (existing)
│   └── legacy Hybrid-linked montage sections
└── #lgad-optical.tab
    ├── #lgad-optical-analytics (new)
    └── existing summary / search / panorama groups
```

The existing tab controller remains the only visibility mechanism: inactive `.tab` sections are `display:none`; no dashboard-level visibility duplication is introduced.

## Data flows

### BBQC

```text
72 canonical table rows + comments/additional-test APIs
  -> existing dashboard.js
  -> #bbqc-analytics
```

Only DOM placement changes.

### ETROC

```text
/data/etroc-optical/ETROC_OI_2608/chips.json
  -> existing ETROCOpticalContract.validate(payload)
  -> immutable validated records
  -> ETROC pool cards + tab-local statistics/table
```

`etroc-optical.js` remains the single fetch and validation owner. Rendering functions receive the same validated records so cards and statistics cannot diverge. Exported contract helpers allow deterministic Node tests without a browser.

The approved cohort spans five immutable analysis runs and must reconcile exactly before rendering: `pack2=17`, `pack1=9`, `pack1_original=8`, `re_chip24=1`, and `re_chip51=1`. Validation also requires the exact run↔batch relationship, UTC analysis timestamp, the eight approved pipeline filenames and their SHA-256 shapes, top-level/per-record SHA-256 shapes, positive integer asset sizes, source geometry/unit, and exact serial→source lineage (`W02G4-51` and `W05E5-24` are `supplement-re`; all others are `base`). Any mismatch fails the pool and statistics dashboard closed.

Derived values:

- partition = green + blue + yellow + red candidate + needs inspection;
- review candidate = separate overlapping workload field;
- wafer/cohort rates always use positions in the current cohort as denominator;
- filter state derives a new view only and never mutates records.

### LGAD

```text
existing #lgad-optical .lgad-card DOM
  -> group and card counts
  -> tab-local availability dashboard
```

No new manifest/API is introduced. The dashboard uses the canonical rendered card inventory and safely derives only availability/group statistics.

## Components

- `hybrid-bbqc/index.html`
  - move BBQC analytics markup inside `#bbqc`;
  - add ETROC and LGAD dashboard semantic containers;
  - load local assets only.
- `hybrid-bbqc/etroc-optical.js`
  - validated aggregate calculator;
  - filter controller;
  - accessible CSS/SVG/HTML chart and audit-table renderer;
  - existing pool renderer.
- `hybrid-bbqc/etroc-optical.css`
  - shared optical statistics layout and responsive/reduced-motion rules.
- `hybrid-bbqc/lgad-optical-stats.js`
  - DOM-derived availability/group statistics renderer.
- Tests
  - extend `test_etroc_optical_pool.py`;
  - add `test_tab_local_dashboards.py` for placement, LGAD inventory, and invariant Hybrid identity.

## Visual system

Reuse current forest/gold/cream palette. Category colors have text labels and patterns/order so color is not the sole cue:

- green — algorithm category `green`;
- blue — algorithm category `blue`;
- gold — algorithm category `yellow`;
- red — `red candidate` only;
- gray — `needs inspection`.

No chart library. Use semantic list/bar structures and local SVG only where needed. Charts provide a table/audit alternative.

## Failure and degradation

- ETROC fetch/identity/cardinality/partition failure: clear both pool and ETROC dashboard, set `aria-busy=false`, announce `ETROC optical dataset unavailable`; no partial metrics.
- LGAD zero/malformed card inventory: show an availability-unavailable alert; do not render zero as an authoritative inventory.
- BBQC API failures retain existing static/live separation.

## Accessibility

- Tab controls use `tablist`/`tab`/`tabpanel`, roving `tabindex`, `aria-selected`/`aria-controls`, and Arrow/Home/End keyboard navigation.
- One `aria-labelledby` section per dashboard.
- Dynamic result counts and load states use `role=status`/`aria-live=polite`.
- Search/filter controls have explicit labels and ≥44 px targets.
- Audit table has a caption, keyboard-sortable headers with `aria-sort`, and horizontal overflow guidance on narrow screens.
- Visible `n/N` labels accompany bars.
- `prefers-reduced-motion` removes transitions.

## Security and provenance

- Continue safe `textContent` rendering for data-derived strings.
- Asset URIs pass the existing serial-bound allowlist.
- No HTML injection from JSON or DOM data attributes.
- Display dataset ID, full immutable analysis-run distribution, analysis timestamp, full analysis config SHA-256, and `exploratory_review_pending` near ETROC metrics.
