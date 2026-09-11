# New supplied Hybrid batch — implementation contract

## Goal and authority
Publish Young's 35 bonded specimens and their 35 supplied PNG images into the existing BBQC main tab, with corrected LGAD association and source notes, without corrupting legacy identity, scientific evidence, reviewer state or statistical denominators. User explicitly authorized implementation through production deployment on 2026-09-11.

Input: `/home/young-park/.hermes/profiles/schuman/downloads/onedrive-new-hybrids/new_hybrids.zip`; SHA256 `5a428fa82513ec707c7801eb7eb7202cf596113cae6f03b823bef6249b5d59ee`, 35022225 bytes. Archive contains original `lgad_etroc_pairs.csv` (36 rows) and 35 PNG files under `좌우반전/`, all decoded at 1142×1142. Preserve original archive/CSV/image bytes.

Authoritative user corrections (keep separately from original input):
- W05E5-30 LGAD ID = HPK-W7-4.
- W03F7-85 was not bump-bonded: exclude from new bonded batch; retain all existing pre-bonding records and reviews. Its original CSV row is retained in source evidence with corrected explanatory note. Properly quote embedded comma when serializing corrected CSV.
- Missing image was precisely excluded W03F7-85. Remaining 35 ETROCs have 35 exact file counterparts under explicitly enumerated crosswalk (W02G4→2, W03F7→3, W05E5→5 plus literal suffix). Never guess extra files or identities.

## Identity / persistence decision
The old main index has 72 canonical `hybrids/<pair_key>.html` identities. server.py discovers them from index links, reconciles persisted aliases and comments, and requires unique active LGAD and ETROC serials. The incoming string `LF-LC2-K-UBM` repeats for W02G4-68/50/64/66/79 and does not establish five unique LGAD serials. Do not suffix, normalize, fabricate or merge these identities; preserve exact supplied labels and explicitly mark individual LGAD serial not supplied for these five.

Use a separately named static supplied-batch publication keyed by exact ETROC within dataset, displayed prominently INSIDE existing `#bbqc` tab before legacy analytics. All 35 are published and usable; this is not 35 new Construction DB registrations. Do NOT insert this set into existing canonical `hybrids/*.html` links, registry, active uniqueness indexes, old 72-card selectors or old statistical denominators. No server.py/DB/schema/auth changes. Preserve old 72 and new35 as explicitly separate cohorts; never relabel old72 screening as107 measured objects. No master-system registration in this scope.

## UI/design contract (reuse existing cream/dark-green tokens)
- New section title `New hybrids · supplied batch`, summary35 bonded specimens /35 supplied images; clear distinct scope from existing registered cohort.
- All35 cards with ETROC, exact supplied LGAD label, supplied-image thumbnail, source notes and missing-count wording explicitly `Pre-bonding optical: ... (supplied CSV)` (not X-ray pass/fail or new adjudication).
- Blank connection channel stays `Not supplied`; no guessed channels or zeros. Two shear notes retained as supplied usage notes, NOT automatic writes to existing assignment registry.
- Search ETROC/LGAD; counts reflect displayed subset out of35. Compact, results-first, no redundant workflow controls or ornamental charts. Accessible native buttons/input labels, mobile fit and keyboard focus.
- Click image opens enlarged read-only supplied-image dialog (close/Escape/backdrop/focus restore). Verify expected image SHA256; decode and display SAME Blob; fail closed and revoke URLs on all paths, including stale async close/reopen. Do not add artificial0–255 location labels over these images: supplied orientation-to-coordinate mapping is not established.
- Keep images exactly as supplied: source directory named `좌우반전` is provenance, not a command to flip them again. Measurement date/modality not fabricated. Prefer `Supplied image` until source modality metadata is established.
- A secondary button opens current effective pre-bonding reviewed montage for matching ETROC through existing reconciled verified viewer, preserving its location0–255 numbering and current labels. If results unavailable, show unavailable rather than original algorithm fallback. A narrowly validated event bridge in etroc-results.js is acceptable; no API writes.
- Original supplied CSV and corrected source CSV downloadable, with corrections/exclusion provenance accessible but not dominating cards. Never rewrite user notes as operator-authored comments.

## Publication architecture
- Deterministic builder `tools/build_new_hybrids.py` reads ZIP, validates all members/rows, applies explicitly versioned approved corrections, verifies excluded row and exact35 image mapping, preserves payloads and emits bounded manifest plus content-addressed images and SHA256SUMS under `hybrid-bbqc/data/new-hybrids/NEW_HYBRIDS_20260911/`.
- Strict top-level/record validation. Key dataset plus ETROC, original CSV fields, source-member path, image bytes/width/height/SHA256, nullable channel, source notes, archive digest, corrected CSV digest, explicit exclusions/corrections. Expose no invented acquisition timestamp, Construction ID, LGAD physical serial or pixel alignment.
- Shared validated manifest drives visible count/cards/filter. Manifest corruption/missing/duplicate/mismapped record fails entire new section closed without affecting original dashboard. Content-addressing alone is not verification; browser hash manifest against fixed code pin and image against authenticated manifest.
- `hybrid-bbqc/new-hybrids.js`, `new-hybrids.css`, index hook plus cache pins. No untrusted HTML insertion. Thumbnail/source assets bounded and full popup hash/decode verified.
- Release helper must download/pin full new bundle, JS/CSS and manifest; verify exact asset closure in build context and actual runtime HTTP. Source revision and later helper revision are distinct. Preserve existing mandatory security/backup/rollback gates.

## TDD / verification / release order
1. Add deterministic archive/CSV/correction/mapping tests (RED then implementation then GREEN). Include traversal, symlink/encrypted members, duplicate rows/members, invalid IDs, missing/extra/corrupt PNG, wrong dimensions, repeated generic LGAD allowed only exact approved rows, preservation of raw CSV and images, unbonded exclusion, idempotent build, stale outputs rejection.
2. Add executable frontend success/error/viewer/lifecycle/search/secondary-reviewed-link tests; original72 registry/key digest and36 pre-bonding corpus remain unchanged. Main tab contains new section; other tabs do not.
3. Full suite: `PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml --with Pillow==12.2.0 python -m pytest -q -p no:cacheprovider --tb=short`; node --check, bash -n release helper, git diff --check; graphify update after source changes.
4. Parent independent browser QA: all35 cards/images/popups decoded with exact mapping, source notes and corrected W05E5-30, W03F7-85 absent ONLY from new batch, current reviewed montage opens and updates, original72 stats/registry intact, all36 pre-bonding/82reviews preserved, mobile/keyboard/error/corrupt bytes, zero production writes.
5. Independent spec/security review on frozen final diff; resolve blockers and rerun focused/full tests. Commit/push immutable source, pin helper, verify remote asset hashes before human auth.
6. Current task access discovery found expired LXPLUS master (SSH255) and local API path unusable. Re-establish trusted human authentication only at actual boundary; never request OTP/password in chat. Verify live ypark/host/cluster/project and baseline counts/digests before launch.
7. Checksum-pinned helper in remote tmux. Verify helper exit0 + actual Build/image/generation readiness; runtime full bundle; DB/comment/review/alias/registry invariants before/after; externalSSO protection; remove QA forwards. Do not claim deployed from a Git push or build alone.

## Definition of done
35 confirmed bonded records/35 original images published and browsable on production, corrected mapping exact, excluded unbonded ETROC preserved in old optical cohort, separate cohort semantics/identity truthful, reviews/comments/evidence unmodified, no invented LGAD uniqueness or measurement data, all tests and independent review pass, actual operating page verified. Authentication blocker must be reported honestly rather than bypassed.
