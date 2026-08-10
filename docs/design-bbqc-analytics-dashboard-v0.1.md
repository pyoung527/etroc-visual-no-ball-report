# BBQC Analytics Dashboard — Design v0.1

## Placement

Insert the analytics section as the first content inside `<main>`, before the existing six summary metrics and navigation tabs.

## Visual system

Reuse the application palette:

- forest `#104b3a` — primary/readiness
- gold `#d9c56f` — evidence/attention accent
- red `#d7301f` — screening candidate only
- cream `#fbfaf4` / `#fffdf8` — page and card surfaces
- muted `#6d756f` — secondary labels

## Components

1. **Analytics header** — title, short provenance statement, live/static state badge.
2. **Four KPI cards** — animated counters with explicit labels.
3. **Screening donut** — no optical no-ball candidate vs screening candidate.
4. **Evidence coverage** — animated horizontal bars for optical, X-ray, NW.
5. **Concordance** — animated bars for Match, Mismatch, Incomplete, Pending.
6. **Wafer distribution** — per-wafer totals with candidate overlay.
7. **Reviewer status donut** — latest comment status per hybrid, loaded from the existing summary API.
8. **Interpretation note** — candidate and NW caveats.

## Motion

- Run once when the dashboard enters the viewport.
- Counters interpolate from 0 to their final values.
- SVG donut strokes reveal using `stroke-dashoffset`.
- Bars scale on the X axis.
- Use one `requestAnimationFrame` loop for counters and CSS transitions for charts.
- Reduced-motion mode renders final values immediately and removes transitions.

## Data flow

```text
#hybrid-table tbody tr
  -> static row model
  -> totals / evidence / concordance / wafer distributions

row canonical hybrid target
  -> GET /api/comments/summary?target=...
  -> latest status per hybrid
  -> live reviewer-status distribution
```

No derived value is written back to SQLite or the static page.

## Failure states

- Missing table rows: dashboard displays `Data unavailable` and does not invent values.
- Comment API unavailable: static charts remain; live review card shows `Live review status unavailable`.
- Unknown comment status: count under `Other`, never coerce to pass/fail.

## Accessibility

- Semantic section/headings.
- SVG charts have `role="img"` and dynamic `aria-label` summaries.
- Color is never the only status cue; labels and values are always visible.
- Keyboard/navigation behavior of the existing page is unchanged.
- Motion is non-essential and disabled by reduced-motion preference.
