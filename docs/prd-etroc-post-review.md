# ETROC post-review results — implementation contract

## Goal / scope (scale-adaptive BMAD)
The pre-bonding ETROC tab opens on all 36 acquisitions, not an empty pending queue. Display current position classifications over clean optical evidence; preserve immutable source publications, position/height evidence, original labelled montages, and append-only review history. No DB migration, auth change, scientific reclassification, or deployment is in scope.

## Scientific and design contract
- A single validated result model drives cards, category counts, pending-review counts and filters.
- Every acquisition contributes 256 positions. Non-target GREEN/BLUE/YELLOW/RED comes from the algorithm. NEED_INSPECT is replaced by its current human label, or explicitly PENDING if no current event exists. PENDING is not a colour or a QC outcome.
- Show effective categories, human/algorithm provenance counts, reviewed/target progress and acquisitions without review targets. Completion is workflow coverage, never a quality/pass guarantee. RED is a classification, not a missing-ball claim.
- Default cards use clean montage plus all-256 effective overlays with non-colour label/provenance tooltips. Original labelled montage, static algorithm counts and run/config provenance live under collapsed “Original evidence”. No fixed Pending/Exploratory badges or redundant candidate banners.
- Keep existing cream/dark-green dashboard palette and typography; use five directly named categories, focus-visible controls, aria-live load/filter status, responsive grids, and no animation. Zero-target acquisitions retain meaningful algorithm categories.
- Corrections/history/height inspection remain a secondary action opening the existing evidence-verified workspace. Workspace current overlay uses effective labels by default. Original algorithm overlay is opt-in.
- Missing, malformed or failed live result responses clear all result metrics/cards and report unavailable, never zero or a fallback original montage as final.

## Architecture / API
Add authenticated GET `/api/etroc-position-reviews/results?dataset_id=ETROC_OI_2608` alongside the unchanged completion endpoint. Reuse authoritative `load_evidence`, full-evidence-key `_current`, schema validation and one SQLite read snapshot. Return bounded per-acquisition algorithm arrays (256), sparse current human labels (target positions only, event ID), evidence digests and completion. No history, notes or giant 256-position detail responses in the aggregate endpoint. Existing write/read/history APIs and concurrency protections remain unchanged.

The existing immutable optical contract validates/hashes chips.json. A separate `etroc-results.js` reconciles the aggregate against its exact publication identity and algorithm partitions, derives one effective model, renders the result section and manages filters. Existing workspace receives the publication independently. A successful position correction readback invalidates/reloads the aggregate so cards and metrics cannot retain the superseded result. Fail closed while refreshing. Original algorithm analytics may remain only inside Original evidence.

## Implementation and acceptance
1. Add backend service/HTTP tests for complete, pending, zero-target, correction, unavailable and malformed store.
2. Implement backend bounded endpoint and frontend pure contract/DOM renderer; integrate result-first tab and workspace defaults without modifying static assets.
3. Add executable Node contract/DOM tests (driven by pytest) for malformed payloads, effective overlays, filters and correction refresh. Run full `uv run --with pytest --with pyyaml --with Pillow==12.2.0 pytest` plus JS syntax checks.
4. Verify dynamic totals 36 acquisitions / 9,216 positions / 82 targets, including 14 zero-target acquisitions from authoritative evidence. Update graphify and inspect changed files. Parent owns independent browser/review/deployment. No commit/push/deploy by builder.
