# BBQC Analytics Dashboard — PRD v0.1

## Problem

The current main page exposes 72 hybrid records and evidence, but users must scan cards/table rows to understand overall QC coverage and review state.

## Goal

Add a statistics-first section at the top of the existing BBQC main page that summarizes screening, evidence coverage, QC concordance, wafer distribution, and live reviewer status without changing any underlying scientific classification.

## Users

- ETL/KNU hybrid QC reviewers
- Production and database coordinators
- Engineers checking evidence completeness

## MVP scope

1. Animated headline counters for total hybrids, screening candidates, evidence-complete hybrids, and currently reviewed hybrids.
2. Motion charts:
   - screening candidate vs no optical no-ball candidate donut;
   - optical/X-ray/NW evidence coverage bars;
   - concordance distribution bars;
   - wafer-level hybrid and candidate distribution;
   - live latest-review-status donut driven by `/api/comments/summary`.
3. Charts derive static values from the existing 72 table rows and dynamic review values from the current comment API.
4. Graceful fallback when the comment API is unavailable.
5. Responsive layout and reduced-motion mode.

## Scientific labeling constraints

- `FAIL candidate` must be displayed as **screening candidate**, not confirmed failure.
- NW anomalies must not be described as direct evidence of bump failure.
- Static evidence/concordance and dynamic reviewer status must be visually and textually separated.
- Missing comments mean **not reviewed in the comment workflow**, not pass or fail.
- Exact ETROC/LGAD identifiers remain unchanged.

## Non-goals

- Reclassifying any hybrid.
- Modifying comments, evidence, mappings, or ETL production bindings.
- Introducing a third-party charting/CDN dependency.
- Persisting dashboard-derived values.

## Success criteria

- All 72 table rows are represented in the computed totals.
- Chart totals match the DOM source data.
- Comment API failure leaves the static dashboard usable.
- No horizontal overflow at desktop or narrow-mobile widths.
- No console errors or missing local assets.
- `prefers-reduced-motion: reduce` disables non-essential animation.

## Definition of done

- Automated structural and semantic tests pass.
- Existing test suite passes.
- Production server serves the page and assets.
- Browser QA verifies animation end state, responsive layout, reduced-motion rule, and no console errors.
- External CERN route is verified after deployment, or the exact authentication/deployment blocker is reported.
