# Comparison comments and clearly visible RED locations

## User request
Add persistent comments at the bottom of the paired X-ray / current-reviewed-montage comparison, and make RED-labelled locations immediately identifiable. Production baseline build60/source16e529a, helperb6b5358. Keep existing scientific evidence, identities, reviews and comments intact.

## Scope / design
Frontend only in new-hybrids.js/css and index asset cache versions, with executable tests. No server.py, schema, existing comments.js, optical viewer, source manifest/CSV/image, registry or canonical-ID changes. Reuse current cream/green tokens with high-contrast RED accents. Keep both image panes side by side and the Close header always reachable. Put a full-width Comments section below BOTH panes, not a third column. Use a scrollable dialog body so comments do not collapse image viewports; preserve Fit/Detail/independent zoom and scrolling on desktop1440x1000 and phone390x844. Scoped section/form styles, no inherited page hero styles.

## Comment identity and existing server contract
- Deterministic target: `hybrid-comparison:NEW_HYBRIDS_20260911:<exact ETROC serial>` for the validated manifest record. This names a unique supplied-pair thread even for the five repeated generic LGAD labels. Never use LGAD-only, a fake registry ID, or pre-bonding-only review threads. Current aliases resolve unknown targets to themselves with hybrid_registry_id NULL; do not create registry records.
- Existing GET /api/me returns authenticated/user identity. POST /api/comments accepts JSON {target,body,status}; use status explicitly `note`, not pass/fail. Server owns author/auth; browser credentials same-origin and native Origin header, no client-forged identities.
- Existing target allowlist is alphanumeric `-_.:/`, max180chars; comment max2000 chars. GET /api/comments?target=... returns latest100 rows, each id,target,body,status,author_display,created_at,updated_at,can_edit. POST201 returns same receipt except can_edit. Validate response identity/shape, render textContent, newest-first; truthful `Latest comments (up to 100)` not an invented total.
- Auth unavailable/unauthenticated disables writing, clear English status; list-read failure is unknown/unavailable, not `No comments yet`.
- Save only on user action; synchronously lock duplicate submissions per target. Capture target/body before await so switching chips cannot retarget a save. POST has NO idempotency support: never automatically retry POST. Handle transport/5xx ambiguity explicitly as `Save status unknown; refresh/check comments before resubmitting`, retain draft and block blind repeat. GET retry is safe.
- Report Saved and clear the submitted draft ONLY after exact POST receipt + GET read-back verifies that id/target/body/status (and receipt metadata) appear in that thread. If POST succeeded but GET failed, retain receipt/draft and offer Refresh comments; do not POST again. Refresh must finish read-back for a pending receipt.
- Keep per-target in-memory drafts/ack/pending state through close/reopen and chip switching (no cross-chip body or status leak); state clearly that unsaved drafts remain only while page stays open. Closing may cancel GET but cannot pretend a POST was cancelled. An in-flight save finishing after switching updates only its own target state, not active UI.
- UI English; preserve user-authored comment body verbatim (do not auto-translate new human comments). No edit/delete feature required.

## RED visibility / navigation
- Derive the RED list strictly from the currently reconciled effective model's `positions.filter(p=>p.label==='RED')`, after optical image verification. Not CSV missing counts or original algorithm labels, not only human labels.
- Show readable `RED locations (n)` and individual location-number buttons (zero-based0–255); exact none is `No RED-labelled locations` only when current verified model available. Unavailable/refreshing removes old lists/counts and highlights synchronously.
- Strong non-scaling high-contrast RED outline + white halo on each current RED tile. Keep evidence center clear (no opaque fill), geometry and all256 existing location numbers unchanged. Do not overlay guessed locations on X-ray.
- Clicking a RED location selects Detail scale>=0.5 (location glyph>=16px), scrolls that exact optical tile into view/center, and visibly marks selected location. All actions keyboard accessible. Stale buttons/model cannot move a different chip. RED is a label, never formal QC failure.
- Keep full current overlay for other labels; RED emphasis supplements, not changes, human/algorithm values. Both modalities remain simultaneously visible during focus.

## Acceptance / verification
1. TDD executable tests for stable35unique targets incl genericLGAD5, authenticated/unauthenticated, real server POST/read-back/reopen and chip separation on disposable SQLite, XSS body, double-submit, pending readback retry without secondPOST, ambiguous transport, close/switch delayed response isolation, draft retention.
2. Exact RED list/outline parity for all35pairs with current effective labels, zeroRED case, human/algorithm RED, refresh removal/change, keyboard selection and focus-scroll to correct0–255 cell; at fit red outlines >=3screenpx and button labels legible without hover.
3. Parent real browser test on local isolated real server exercises an actual comment save, reload, reopen, separate chip, and existing data tables unchanged except local test comments. Production QA READ-ONLY: do not seed/delete test comments in production.
4. Existing317tests/275subtests baseline, old paired-viewer/error-path regressions intact; 225immutable source files unchanged. Full command: PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml --with Pillow==12.2.0 python -m pytest -q -p no:cacheprovider --tb=short
5. Source freeze, independent review, pinned release then actual-pod read-only QA and before/after DB chain preservation. Server stays byte-identical; production POST behavior exercised on disposable server with exact same backend implementation, never a fabricated response.
