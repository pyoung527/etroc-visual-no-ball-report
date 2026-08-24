# ETROC Position Review Overlay — PRD v0.1

## Problem

The deployed ETROC review workspace binds one human disposition to an immutable labelled montage. The montage pixels already contain algorithm category text, category colour, and a centroid marker. A reviewer can inspect a `NEED_INSPECT` location but cannot correct or record that position independently, and editing the montage would destroy the analysis evidence.

## Goal

Add an evidence-bound position review layer over a clean, immutable montage while preserving the original labelled analysis montage unchanged.

## Users

- ETL/KNU optical QC reviewers
- Engineers resolving exploratory `NEED_INSPECT` candidates

## Confirmed decisions

1. The labelled analysis montage remains immutable and available as analysis evidence.
2. A clean montage is deterministically generated from the same 256 source PNGs with the same 16×16 geometry but no algorithm label, category colour, or centroid mark.
3. Position metadata is published for all 9,216 positions; the default review-target cohort is the 82 positions whose immutable algorithm category is `NEED_INSPECT`.
4. A reviewer may directly select another position for ad-hoc review, but the default progress denominator remains the snapshotted review-target cohort, not all 9,216 positions.
5. Algorithm category and human disposition are separate fields. Human review never rewrites algorithm output or image bytes.
6. Position events are append-only and bound to an exact acquisition/run/artifact/position identity.
7. ETROC-level disposition remains a separate explicit decision and is never inferred automatically from position events.

## Position states

- `unreviewed` — derived from no event;
- `reviewed_no_optical_concern`;
- `reviewed_concern_observed`;
- `follow_up_required`.

A non-empty note is required for concern and follow-up. A note is optional for no-concern.

## MVP user journey

1. Reviewer opens an ETROC in the existing same-page workspace.
2. Evidence panel defaults to the browser-verified clean montage with human overlay enabled.
3. Reviewer may toggle:
   - Clean montage;
   - Labelled analysis montage;
   - Algorithm candidate overlay;
   - Human review overlay.
4. `Start position review` snapshots the current ETROC's `NEED_INSPECT` positions in ascending position order.
5. The active position is highlighted and its clean crop is shown enlarged with position, row, column, immutable algorithm category/reason, and source digest.
6. Reviewer selects a human state, adds a note when required, and uses `Save & Next`.
7. Saving appends an event, verifies readback, and advances only after success. Conflict or timeout preserves the draft and does not advance.
8. Reviewer may click any grid cell for direct single-position review.
9. ETROC view reports target progress such as `8 / 12 NEED_INSPECT positions reviewed` and a descriptive state breakdown.
10. ETROC-level review remains available separately after position inspection.

## Evidence contract

Acquisition evidence remains:

```text
(dataset_id, etroc_serial, acquisition_id, analysis_run_id, labelled_montage_sha256)
```

Position evidence is:

```text
(dataset_id, etroc_serial, acquisition_id, analysis_run_id,
 labelled_montage_sha256, clean_montage_sha256, position_publication_sha256,
 position, source_image_sha256, geometry_version)
```

`position` is an integer `0..255`; `row = position // 16`; `column = position % 16`. `geometry_version` is `etroc-grid-16x16-v1`. `position_publication_sha256` binds algorithm category/reason, target membership, and cell geometry; any new position-publication digest starts a new unreviewed chain even when image bytes are unchanged.

The browser must hash and display the same clean montage Blob it reconciles with the server evidence map. Save is disabled on any publication, keyset, URI, digest, geometry, or Blob mismatch.

## Publication requirements

- Preserve the existing labelled montage URI and digest.
- Publish each clean montage at `clean-montages/sha256/<digest>.jpg`.
- Publish a content-addressed `positions/sha256/<digest>.json` containing exactly 256 position records per ETROC and 9,216 total.
- Each position record includes position/row/column, immutable algorithm category/reason, source image SHA-256, clean cell geometry, and canonical acquisition/run identity.
- The clean montage is exactly `2400×2176`: 16 columns × 150 px and 16 rows × 136 px. Each tile has a 16 px neutral header and a 150×120 image region matching the original pipeline placement.
- Clean generation is deterministic and validates source path safety, unique positions, source image bytes, dimensions, and complete identity joins.

## Review queue and UX

- Default target: immutable category `NEED_INSPECT`.
- `Start position review` snapshots only positions that are both review targets and currently unreviewed. The snapshot order and denominator are fixed for that session.
- Direct selection of an unreviewed target anchors that same target queue at the selected position and continues forward without wrapping.
- Direct selection of a non-target position is single-item ad-hoc mode. Direct selection of an already reviewed position is single-item correction mode. Both omit `Save & Next`.
- Before every queue advance, refresh live current summaries, skip positions completed remotely, and preserve local draft/conflict state. Never add newly appearing targets or otherwise expand the snapshot.
- Target progress keeps the original snapshotted target denominator; remotely completed positions count as reviewed rather than shrinking the denominator.
- Deterministic order: ETROC serial natural order, then numeric position.
- Within one ETROC dialog, position order is ascending numeric position.
- Algorithm overlay is visually distinct from human state and includes text/icon semantics, not colour alone.
- The active cell is keyboard reachable; arrow keys move among cells outside editable controls; Enter opens the active position.
- Fit/zoom/pan apply to the image and overlays together.
- Switching montage modes never changes the canonical position or draft.
- Dirty navigation/close requires confirmation.

## Semantics

- `NEED_INSPECT` is an exploratory algorithm category, not a defect or failed QC result.
- `Reviewed — no optical concern` means the reviewer did not observe an optical concern at that exact position/image evidence.
- `Concern observed` is not automatically a detector defect or ETROC-level failure.
- `Follow-up required` requests reinspection, remeasurement, reanalysis, or expert adjudication.
- Position counts are descriptive workflow counts and do not modify static algorithm denominators.

## Security and concurrency

- Reuse the existing CERN SSO and fail-closed `ETROC_REVIEWER_USERS` capability.
- Author and timestamp are server-derived.
- POST requires same-origin JSON, bounded body, unknown-field rejection, exact position evidence, `expected_current_event_id`, and stable UUID `mutation_id`.
- Exact retry returns the original event; divergent mutation reuse and stale current state return `409`.
- Direct `UPDATE` and `DELETE` are rejected.

## Non-goals

- Reclassifying or regenerating the algorithm categories.
- Editing labelled or clean montage pixels in the browser.
- Requiring adjudication of all 9,216 positions for MVP completion.
- Automatically deriving ETROC-level or production PASS/FAIL.
- Multi-reviewer consensus or offline synchronization.

## Success criteria

- The 82 current `NEED_INSPECT` positions are reviewable sequentially without editing an image.
- Reviewers can compare clean and labelled evidence without losing position/draft context.
- Every saved position review is bound to exact displayed bytes and immutable position provenance.
- Progress uses an explicit target denominator and cannot present an outage as zero reviews.
- Existing ETROC-level history, Hybrid comments, and immutable montage evidence remain unchanged.

## Definition of done

- Deterministic clean publication and 9,216-position metadata tests pass.
- Position schema/API chain, authorization, idempotency, concurrency, and drift tests pass.
- Browser tests cover Blob verification, overlay geometry, toggles, target queue, ad-hoc position selection, Save & Next, conflict, dirty draft, and read-only mode.
- Desktop and narrow-mobile browser QA pass.
- Existing ETROC/Hybrid/OpenShift tests remain green.
- Independent scientific-semantics, data-integrity/security, and accessibility reviews have no HIGH/MEDIUM findings.
