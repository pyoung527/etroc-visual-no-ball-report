# Hybrid X-ray / reviewed-montage comparison

## User correction and acceptance
Young requires X-ray and the same ETROC's current reviewed montage visible together, not separate modal/tab workflows. Translate all Korean supplied notes into English. This is a usability correction to production build59/source90fd001; preserve scientific evidence and review state.

## Design contract (existing cream/green tokens retained)
- A single large comparison dialog/workspace, launched by clicking the supplied thumbnail or a primary `Compare X-ray and montage` button. Left: `X-ray`; right: `Current reviewed pre-bonding montage`. Both visible simultaneously on desktop and phone; no nested modal, tab switch, or original-algorithm fallback.
- Common fixed/always reachable identity header with exact ETROC and supplied LGAD, English notes, Close; clear loading/error state per pane.
- Fit overview plus practical per-pane zoom (+/-/Reset or fit/detail controls), independently scrollable panes. Never claim coordinate correspondence or automatically synchronize differing modality grids. Preserve orientation/aspect ratio; do not flip/crop/relabel X-ray.
- Reviewed montage uses existing verified clean image + current effective overlays, positions0–255 always present. Existing optical viewer and its readable-number contract unchanged. Comparison detail zoom must give location glyphs >=16px and scrolling to last position; overview may scale the entire montage, clearly labeled overview/detail. No labels placed on X-ray.
- Desktop both images fit the comparison workspace; mobile both panes persist side by side, bounded within viewport, independently scrollable detail areas, Close reachable and keyboard Escape/focus restoration correct. Avoid oversized surrounding prose.
- All new-section rendered prose, card notes, comparison notes/status and source disclosure must be English. Preserve exact identifiers. Source downloads remain original/corrected CSV with original Korean provenance; do not mutate immutable manifest, CSVs or source PNGs.

## English note semantics
Source grammar has exactly five variants (35rows):
`solder bump missing: N개 (optical inspection 기준)` -> `Missing solder bumps: N (based on optical inspection).`
`; shear force test에 사용됨` -> `Used for shear force testing.`
Keep counts, optical basis and usage (not assignment/planned/not pass/fail) intact. Display a provenance label such as `Supplied pre-bonding optical note`. Source disclaimer can say `Source directory indicates left-right-mirrored images; no additional flip is applied.` without displaying Korean folder text. Unknown source grammar must not leak untranslated or silently drop meaning; strict parser/fail-closed.

## Architecture and immutable boundaries
- Scope frontend only: new-hybrids.js/css, narrow current-results bridge in etroc-results.js, index cache versions, executable tests. No server/schema/registry/evidence-bundle changes.
- Obtain only current fully reconciled models from results controller via narrow validated read-only request/response or mount boundary. Never scrape prior rendered card labels, original montage_uri, or cache a stale model across refresh/publication invalidation. Avoid exposing mutable internal models (clone response if model returned).
- Current-results loading, refresh, review update, publication failure invalidate visible/inflight comparison optical evidence synchronously; correct latest model can be shown after reconciliation. No duplicate modal layering.
- Verify X-ray image bytes against pinned manifest and optical clean bytes against reconciled expected digest; decode and render the very same Blob. Check exact dimensions. Generation cancellation, abort and URL revocation on close/switch/failure; async errors cannot revive old chip or image.
- Failure of one modality must be explicit while preserving the independently verified other modality; never call partial comparison complete. Source manifest failure means cohort unavailable as before.
- 35 supplied pairs/images, all36optical, 72legacy identities and their denominators stay unchanged. Existing review/comment DB untouched.

## Verification
- TDD executable regression tests for English grammar/all35notes, same-ID paired render, 256effective overlays, refresh invalidation, no model mutation, image SHA/decode failures, stale async close/reopen, keyboard and zoom controls. Adapt obsolete separate-button tests to new workflow; do not silently weaken scientific assertions.
- Parent real browser QA all35pairs, both panes concurrently visible, each image hashes to correct source, all256 overlays match current results; desktop1440x1000 and phone390x844, zoom/scroll/Close/focus, no Korean in visible new-section or dialog prose, notes count/usage parity.
- Full suite: PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml --with Pillow==12.2.0 python -m pytest -q -p no:cacheprovider --tb=short
- Independent reviewer after source freeze, then pinned helper asset updates, release and actual-pod read-only QA if authentication available. Authentication is a separate gate, never report deployed from local tests.
