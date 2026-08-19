# ETROC Acquisition Review Workspace — PRD v0.1

## Problem

The `ETROC_OI_2608` montage pool currently renders each ETROC as a link that opens a JPEG in a new browser tab. A reviewer must repeatedly open an image, inspect it, return to the pool, find the card again, and use a separate mechanism to record a decision. This makes a 36-ETROC review slow, error-prone, and difficult to resume.

## Goal

Provide an in-app, sequential review workflow for each exact ETROC optical acquisition while preserving scientific interpretation boundaries and immutable evidence provenance.

A reviewer should be able to inspect a montage, record a structured review plus an optional/required note, save it, and advance to the next prioritized unreviewed acquisition without leaving the ETROC tab.

## Users

- ETL/KNU optical QC reviewers
- Engineers triaging algorithmic optical-screening candidates
- Production coordinators tracking review completion and follow-up workload

## Confirmed product decisions

1. Each exact ETROC acquisition has one current review state.
2. Every state change is preserved as an append-only history event.
3. The structured state model is:
   - `unreviewed` — derived from the absence of an event;
   - `reviewed_no_optical_concern`;
   - `reviewed_concern_observed`;
   - `follow_up_required`.
4. The default `Save & Next` queue is candidate-priority ordered by one canonical comparator:
   - unreviewed acquisitions before reviewed acquisitions;
   - acquisitions with optical no-ball candidates;
   - acquisitions with red candidates;
   - descending `needs_inspection_count`;
   - descending `review_candidate_count`;
   - exact ETROC serial as deterministic tie-breaker.
5. Candidate priority determines review order only; it does not determine a human review outcome or production QC disposition.
6. Only users in the explicit `ETROC_REVIEWER_USERS` allowlist may append review events. Other authenticated CERN route users have read-only access.

## MVP user journey

1. The reviewer opens the ETROC optical tab.
2. The page loads immutable `ETROC_OI_2608` records and batched live review summaries.
3. Cards show current review state, reviewer, timestamp, and review-history count without hiding the existing algorithmic candidate counts.
4. The reviewer enters the workspace in one of three ways:
   - `Start/Resume review` builds an unreviewed queue from the current wafer/serial/candidate filters and chosen ordering; the card-view state filter is intentionally ignored;
   - opening an unreviewed card builds that same queue, anchors it at the clicked card, and continues forward without wrapping;
   - opening a reviewed card enters correction mode for that acquisition only.
5. The same-page review workspace displays:
   - large montage with fit, zoom, and pan;
   - exact ETROC serial and acquisition identity;
   - algorithmic counts and scientific disclaimer;
   - current review state and prior history;
   - structured state controls and note field;
   - previous, next, and `Save & Next` actions.
6. Saving appends a new review event and advances to the next item in the active candidate-priority queue.
7. The reviewer can stop and later select `Resume next unreviewed`.

## Review workspace requirements

### Evidence panel

- Render the full montage inside the application rather than opening a new tab by default.
- Fetch `chips.json` as bytes, compute its publication SHA-256 in the browser, and parse those same verified bytes.
- Require the authenticated batched GET to advertise a server-derived full evidence record for all 36 writable acquisitions: the five-field key, content-addressed montage URI, and publication SHA-256.
- Fetch the montage from that content-addressed path, receive it as a `Blob`, compute SHA-256 in the browser, and display that same verified Blob through an object URL.
- Keep Save disabled until the browser publication hash and record, server-advertised evidence record, montage URL digest, fetched Blob hash, and displayed Blob all match exactly.
- Revoke the object URL when leaving the item; an explicit `Open verified original` action opens the same content-addressed asset, not a mutable serial-only path.
- Provide fit-to-view, zoom, pan, reset, and explicit open-original fallback.
- Preload and verify only the immediately adjacent queue images.
- Display the exact acquisition ID, analysis run ID, montage SHA-256, and byte-verification state associated with the viewed artifact.
- Keep the warning that algorithmic screening is not a confirmed QC disposition.

### Decision panel

- Present the three completed states with human-readable labels:
  - `Reviewed — no optical concern`;
  - `Reviewed — concern observed`;
  - `Follow-up required`.
- Require a non-empty note for concern and follow-up states.
- Allow an optional note for no-concern reviews.
- Disable duplicate submissions while a save is in flight.
- Announce save success, validation errors, and concurrency conflicts accessibly.

### Queue and navigation

- Show progress as `reviewed / 36` and position within the active queue.
- Provide previous/next controls and keyboard navigation outside editable fields.
- `Start/Resume review` snapshots wafer, serial, candidate filters, and ordering, then includes only currently unreviewed acquisitions. The current-state filter is a card-view control and is intentionally not part of queue construction.
- Directly opening an unreviewed card constructs the same filtered unreviewed queue, starts at the clicked acquisition, and advances forward without wrapping; directly opening a reviewed card is correction-only.
- `Save & Next` uses that filter/order snapshot and never silently jumps to another wafer/filter; at end-of-queue it shows a completion summary and returns only on explicit action.
- Opening an already reviewed card enters correction mode: append a superseding event with `Save`; do not offer queue-advancing `Save & Next` from correction mode.
- A `409 Conflict` preserves the local draft, displays the intervening event, and does not advance.
- Changing item, pressing Escape, or closing with a selected state or modified note requires an accessible discard confirmation.
- Default ordering uses the single canonical comparator above; reviewers may switch to wafer/serial order before opening the workspace.
- Filters include current state, wafer, exact/partial serial, and candidate type.

### Pool and summary

- Preserve the existing static scientific analytics and denominators.
- Add a separate live-review summary: unreviewed, no concern, concern observed, and follow-up.
- Review-state filters affect card visibility only and never relabel or mutate algorithmic category totals or queue membership.
- Wafer, serial, and candidate filters affect both card visibility and queue membership; their values are snapshotted when a queue opens.
- If the review API is unavailable, montage inspection remains available and the live review surface shows a degraded/unavailable state rather than zero reviews.

## Identity and provenance contract

The visible unit is an ETROC, but each review is bound to one canonical evidence key:

```text
(dataset_id, etroc_serial, acquisition_id, analysis_run_id, montage_sha256)
```

All five fields are required consistently in persistence, current-state lookup, supersession validation, API evidence/review responses, and audit history. The server derives them from the deployed canonical `chips.json`, hashes those exact publication bytes, and hashes each deployed content-addressed montage. The batched API returns a complete 36-entry evidence map plus `publication_sha256`, even when `reviews` is empty. The browser hashes and parses the same fetched publication bytes, reconciles every server evidence entry, then independently hashes and displays the same montage Blob. Save is unavailable unless the complete evidence map cardinality/keyset and all publication/record/URI/Blob identities agree.

A later acquisition, analysis run, montage digest, or deployment-skewed JSON/asset pair must not inherit a prior current state automatically. Persisted history for evidence no longer present in the current 36-record publication remains available through a read-only audit endpoint and cannot accept new mutations.

Unbonded ETROCs remain outside `hybrid_registry`. ETROC review records must not use a fabricated `hybrid:` target or partner identity.

## Review semantics

- `Reviewed — no optical concern` is not a production QC PASS.
- `Reviewed — concern observed` means a reviewer saw an optical concern; it is not automatically a confirmed detector defect.
- `Follow-up required` requests reinspection, remeasurement, reanalysis, or expert adjudication.
- The immutable publication field `review_state=not_reviewed` describes the static analysis bundle and remains unchanged; live human review is a separate layer.

## Concurrency and audit requirements

- Saving requires the event ID/version last read by the client and a browser-generated UUID mutation ID.
- The mutation ID remains stable across timeout/retry for an unchanged draft. The server uniquely constrains `(author, mutation_id)` and returns the original event for an exact retry without appending a duplicate.
- Reusing a mutation ID with different evidence, state, note, or expected event ID is a conflict; a new mutation ID is generated only after success, explicit discard, or explicit conflict reapply.
- If another reviewer changed the acquisition first, return `409 Conflict`; do not silently overwrite or advance the queue.
- Every successor must reference the immediate current event for the same canonical five-field evidence key; roots and successors cannot fork or cross acquisition/evidence boundaries.
- Corrections append a new event that supersedes the previous current event.
- Database triggers reject direct `UPDATE` and `DELETE`, and uniqueness/insert validation reject multiple roots, forks, and cross-key supersession.
- History records author, timestamp, state, note, and exact evidence provenance, including persisted acquisitions absent from the current publication.
- MVP does not physically delete or rewrite historical events.

## Security and privacy

- CERN SSO is required for all review reads and mutations through the protected application route.
- Only normalized identities in `ETROC_REVIEWER_USERS` may append review events; authenticated non-reviewers receive `403` and retain read-only access. Empty/missing allowlist fails closed for mutation.
- The authenticated batched GET response includes server-derived `viewer.identity_display` and `viewer.can_append_review`; it never exposes the allowlist. The UI renders mutation controls from this capability and the POST endpoint independently re-authorizes.
- Trust identity only from the proxy-exclusive configured header; direct client injection is not accepted by the deployment boundary and must be tested externally.
- Continue same-origin and JSON content-type enforcement.
- Use server-derived user identity; never accept author identity from the browser payload.
- Escape notes and render with safe DOM APIs.
- Enforce bounded note length and structured enum validation.

## Non-goals

- Position-by-position adjudication of all 9,216 positions.
- Automatic conversion of reviews into ETL production PASS/FAIL.
- Modifying analysis classifications, thresholds, or immutable montage assets.
- Adding pre-bonding ETROCs to the Hybrid registry.
- Multi-reviewer consensus scoring in v0.1.
- Offline review synchronization.

## Success metrics

- A reviewer can complete multiple ETROCs without returning to the card grid or opening image tabs.
- Every successful save reads back the exact current state and append-only history entry.
- Save is impossible until the exact displayed montage Blob hashes to the canonical digest; stale cache, wrong bytes, or JSON/asset deployment skew fail closed.
- Candidate-priority `Save & Next` order is deterministic, refreshes remote state, and never discards a dirty draft.
- Review progress can be resumed from the next still-unreviewed acquisition in the snapshotted filter/order.
- No review is silently attached to a changed acquisition/run/montage or to a historical acquisition absent from the current publication.
- Concurrent edits fail with `409` and preserve the local draft plus intervening event until explicit resolution.

## Definition of done

- PRD, architecture, and implementation plan are approved before coding.
- TDD covers exact atomic schema creation and drift rejection, second-run idempotency, injected migration rollback, previous-binary rollback, append-only triggers/chain invariants, 36-entry server evidence/publication reconciliation, provenance and deployed-byte validation, state/note rules, reviewer authorization, concurrency, queue ordering/state refresh, dirty-draft protection, and degraded API behavior.
- Stale-cache, wrong-byte, content-address mismatch, and JSON/asset deployment-skew browser fixtures must disable Save.
- Existing Hybrid registry/comment tests and canonical 72-Hybrid digest remain unchanged.
- Real-browser desktop and narrow-mobile QA exercises open, byte verification, zoom, save, save-and-next, resume, correction, conflict, dirty-close confirmation, filtering, and keyboard/screen-reader behavior.
- Production rollout includes online SQLite backup, rollback coordinates, exact migration verification, previous-binary probe, deployed-asset/publication hashing, mandatory BBQC oauth2-proxy topology validation, external header-spoof probe, runtime API evidence-map probes, and live browser verification.
