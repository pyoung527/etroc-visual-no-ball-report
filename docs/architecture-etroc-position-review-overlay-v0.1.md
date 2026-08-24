# ETROC Position Review Overlay — Architecture v0.1

## Decision

Extend the existing evidence-bound ETROC workspace with a separate position publication and append-only position event subsystem. Never mutate the labelled montage, algorithm position results, acquisition-level review events, or Hybrid data.

## Layers

```text
immutable analysis evidence
├── labelled montage (existing)
├── clean montage (new deterministic derivative)
└── position publication JSON (new)

live review state
├── acquisition events (existing)
└── position events (new append-only chain)

browser workspace
├── verified clean/labelled Blob switcher
├── SVG 16×16 overlay
└── NEED_INSPECT queue/crop/four-label panel
```

## Deterministic clean montage

Input is `bbqc_position_results_exploratory.csv` plus the exact `image_path` bytes already validated by the analysis publication builder.

Geometry `etroc-grid-16x16-v1`:

- canvas `2400×2176` RGB white;
- 16 columns, tile width 150;
- 16 rows, tile height 136;
- neutral header rectangle `(x, y, 150, 16)`;
- source image converted to RGB, Pillow thumbnail bounded by `150×120`, pasted at `(x, y+16)` with the same top-left placement as the analysis pipeline;
- no category text/colour and no centroid marker.

JPEG encoder remains the existing pinned Pillow/libjpeg contract. Clean bytes are published at a SHA-256 path. Labelled bytes remain at the existing SHA-256 path.

## Position publication

The normative layout is exactly 36 content-addressed position JSON documents, one per ETROC acquisition, each containing exactly 256 positions. Every `chips.json` record references its own document. Dataset-wide validation occurs in the builder and server evidence loader: they require the exact 36-record acquisition keyset, 36 unique position-document URIs/digests, 256 positions per document, 9,216 unique `(acquisition_id, position)` keys, and 82 total review targets.

```json
{
  "schema_version": "1.0",
  "geometry_version": "etroc-grid-16x16-v1",
  "dataset_id": "ETROC_OI_2608",
  "etroc_serial": "W02G4-44",
  "acquisition_id": "...",
  "analysis_run_id": "...",
  "labelled_montage_sha256": "...",
  "clean_montage_sha256": "...",
  "positions": [
    {
      "position": 0,
      "row": 0,
      "column": 0,
      "algorithm_category": "GREEN",
      "algorithm_reason": "height_in_spec",
      "source_image_sha256": "...",
      "cell": {"x": 0, "y": 0, "width": 150, "height": 136, "image_y": 16, "image_height": 120},
      "review_target": false
    }
  ]
}
```

`chips.json` adds `clean_montage_uri`, `clean_montage_sha256`, `position_publication_uri`, `position_publication_sha256`, `position_geometry_version`, and `position_review_target_count`. Existing fields and labelled montage semantics remain unchanged.

## Browser evidence binding

1. Hash/parse `chips.json` bytes as today.
2. Reconcile acquisition evidence with the server.
3. Fetch/hash/parse the selected ETROC position publication.
4. Require exact 256 positions, key range, row/column formula, geometry, category counts, target count, and acquisition/run/montage identities.
5. Fetch clean montage as Blob, hash it, decode it, and display an object URL from that same Blob.
6. Overlay SVG uses position metadata cell coordinates in the same transformed viewport.
7. Save remains disabled unless clean Blob, labelled evidence, position JSON, and server position evidence all agree.

## Persistence

Use new objects rather than changing the v1 acquisition event table:

```sql
CREATE TABLE position_review_schema (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  version INTEGER NOT NULL CHECK (version = 2),
  applied_at INTEGER NOT NULL
) WITHOUT ROWID;

CREATE TABLE position_review_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_id TEXT NOT NULL,
  etroc_serial TEXT NOT NULL,
  acquisition_id TEXT NOT NULL,
  analysis_run_id TEXT NOT NULL,
  labelled_montage_sha256 TEXT NOT NULL,
  clean_montage_sha256 TEXT NOT NULL,
  position_publication_sha256 TEXT NOT NULL,
  position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 255),
  source_image_sha256 TEXT NOT NULL,
  geometry_version TEXT NOT NULL CHECK (geometry_version = 'etroc-grid-16x16-v1'),
  label TEXT NOT NULL CHECK (label IN ('GREEN','BLUE','YELLOW','RED')),
  note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 2000),
  author TEXT NOT NULL,
  author_display TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  mutation_id TEXT NOT NULL,
  supersedes_event_id INTEGER REFERENCES position_review_events(id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX idx_position_review_one_root
ON position_review_events(
  dataset_id,etroc_serial,acquisition_id,analysis_run_id,
  labelled_montage_sha256,clean_montage_sha256,position_publication_sha256,
  position,source_image_sha256,geometry_version
) WHERE supersedes_event_id IS NULL;

CREATE UNIQUE INDEX idx_position_review_one_successor
ON position_review_events(supersedes_event_id)
WHERE supersedes_event_id IS NOT NULL;

CREATE UNIQUE INDEX idx_position_review_author_mutation
ON position_review_events(author,mutation_id);

CREATE INDEX idx_position_review_current_lookup
ON position_review_events(
  dataset_id,etroc_serial,acquisition_id,analysis_run_id,
  labelled_montage_sha256,clean_montage_sha256,position_publication_sha256,
  position,source_image_sha256,geometry_version,id
);

CREATE TRIGGER position_review_no_update
BEFORE UPDATE ON position_review_events
BEGIN SELECT RAISE(ABORT, 'ETROC position review events are append-only'); END;

CREATE TRIGGER position_review_no_delete
BEFORE DELETE ON position_review_events
BEGIN SELECT RAISE(ABORT, 'ETROC position review events are append-only'); END;

CREATE TRIGGER position_review_same_evidence_successor
BEFORE INSERT ON position_review_events
WHEN NEW.supersedes_event_id IS NOT NULL
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM position_review_events AS previous
    WHERE previous.id = NEW.supersedes_event_id
      AND previous.dataset_id = NEW.dataset_id
      AND previous.etroc_serial = NEW.etroc_serial
      AND previous.acquisition_id = NEW.acquisition_id
      AND previous.analysis_run_id = NEW.analysis_run_id
      AND previous.labelled_montage_sha256 = NEW.labelled_montage_sha256
      AND previous.clean_montage_sha256 = NEW.clean_montage_sha256
      AND previous.position_publication_sha256 = NEW.position_publication_sha256
      AND previous.position = NEW.position
      AND previous.source_image_sha256 = NEW.source_image_sha256
      AND previous.geometry_version = NEW.geometry_version
  ) THEN RAISE(ABORT, 'invalid ETROC position review supersession') END;
END;
```

The exact managed-object inventory is the two tables, four indexes, and three triggers named above. Startup accepts only no position-review objects (v0), the exact deployed v1 inventory, or that exact v2 inventory and SQL. Exact v1 may migrate to v2 only when `position_review_events` is empty; non-empty v1 fails closed because its old concern/follow-up states cannot be scientifically mapped to colour labels. The v1→v2 migration rebuilds the event table and dependent indexes/triggers in one `BEGIN IMMEDIATE` transaction. Startup validates metadata, `table_info`, `index_list/index_info`, foreign-key action `ON DELETE RESTRICT`, trigger SQL, `foreign_key_check`, and `integrity_check`. Any create/validation/injected failure rolls back the complete position subsystem while preserving acquisition review objects, Hybrid objects, rows, and `PRAGMA user_version`. Reopening exact v2 is read-only/idempotent; partial, future, extra attached, or definition-drifted objects fail closed.

## API

Every JSON response sets `Cache-Control: no-store`. GET query parsing rejects missing, duplicate, unknown, blank, malformed UTF-8/percent encoding, oversized values, and positions outside canonical decimal `0..255`. Errors use exactly `{"error":{"code":"stable_code","message":"non-sensitive text",...optionalConflictFields}}`.

### Summary

```http
GET /api/etroc-position-reviews?dataset_id=ETROC_OI_2608&acquisition_id=<encoded exact id>
```

`200` contains exactly:

```json
{
  "dataset_id":"ETROC_OI_2608",
  "publication_sha256":"<chips.json digest>",
  "acquisition_id":"...",
  "etroc_serial":"W02G4-44",
  "analysis_run_id":"...",
  "labelled_montage_sha256":"<digest>",
  "clean_montage_sha256":"<digest>",
  "clean_montage_uri":"data/etroc-optical/ETROC_OI_2608/clean-montages/sha256/<digest>.jpg",
  "position_publication_sha256":"<digest>",
  "position_publication_uri":"data/etroc-optical/ETROC_OI_2608/positions/sha256/<digest>.json",
  "geometry_version":"etroc-grid-16x16-v1",
  "position_count":256,
  "target_count":1,
  "viewer":{"identity_display":"Young","can_append_review":true},
  "evidence":{"0":{"dataset_id":"ETROC_OI_2608","etroc_serial":"W02G4-44","acquisition_id":"...","analysis_run_id":"...","labelled_montage_sha256":"<digest>","clean_montage_sha256":"<digest>","position_publication_sha256":"<digest>","position":0,"source_image_sha256":"<digest>","geometry_version":"etroc-grid-16x16-v1","row":0,"column":0,"algorithm_category":"GREEN","algorithm_reason":"height_in_spec","review_target":false,"cell":{"x":0,"y":0,"width":150,"height":136,"image_y":16,"image_height":120}}},
  "reviews":{"0":{"current_event_id":1,"dataset_id":"ETROC_OI_2608","etroc_serial":"W02G4-44","acquisition_id":"...","analysis_run_id":"...","labelled_montage_sha256":"<digest>","clean_montage_sha256":"<digest>","position_publication_sha256":"<digest>","position":0,"source_image_sha256":"<digest>","geometry_version":"etroc-grid-16x16-v1","label":"GREEN","note":"","author":"young.park@cern.ch","author_display":"young.park","created_at":1787000000,"history_count":1}}
}
```

`evidence` has exactly the string keys `"0".."255"`; `reviews` is a subset. Empty reviews is valid only beside the complete validated map.

### History and historical audit

```http
GET /api/etroc-position-reviews/history?acquisition_id=<id>&position=<0..255>
GET /api/etroc-position-reviews/audit?acquisition_id=<id>&position=<0..255>
```

History requires current publication evidence and returns `{"evidence":<complete evidence>,"current":<event|null>,"history":[<newest-first events>]}`. Audit is DB-derived and returns `{"acquisition_id":"...","position":0,"chains":[{"evidence":<complete persisted key>,"current_publication":true,"current_event":<event>,"history":[...]}]}` for every persisted digest chain. Historical chains are readable but never writable when they differ from the current position-publication evidence.

An event has exactly `event_id`, the ten canonical position-key fields (including `position_publication_sha256`), `label`, `note`, server-derived `author`, `author_display`, `created_at`, `mutation_id`, and `supersedes_event_id`. A current summary replaces `event_id/mutation_id/supersedes_event_id` with `current_event_id/history_count`.

### Append

```http
POST /api/etroc-position-reviews
Content-Type: application/json
Origin: https://etl-hybrid-bbqc.app.cern.ch
```

The body has exactly the ten canonical key fields plus `label`, `note`, `expected_current_event_id`, and canonical UUID `mutation_id`. The target evidence must have `review_target=true`; non-target mutation is rejected with `422 position_not_review_target`. `201` insert and `200` exact replay return `{"ok":true,"idempotent_replay":false|true,"event":<event>,"current":<current>}`.

Validation/error precedence is: authentication `401`; POST capability `403`; same-origin `403`; media type `415`; bounded JSON/object/unknown/missing field `400`; enum/note/digest/position/UUID `422`; transaction-first exact replay or divergent mutation-ID `200/409`; forced current evidence revalidation `409 evidence_changed` or `503 evidence_unavailable`; optimistic concurrency `409 stale_current`; insert/readback/store failure `503 review_store_unavailable`. Conflict payloads include only the submitted expected ID, current summary, canonical evidence, or existing event ID needed for explicit recovery. No raw SQL, path, allowlist, secret, or exception is returned.

Known valid IDs absent from current publication return `404 acquisition_not_found`/`position_not_found`; audit with no persisted chain returns `404 audit_not_found`.

## Frontend state

- `activeAcquisition`: existing queue item.
- `positionPublication`: verified 256-position document.
- `positionEvidence`: server-reconciled map.
- `positionReviews`: current summaries.
- `positionQueue`: immutable snapshot of positions that were both targets and unreviewed when Start opened; target denominator and order never expand or shrink.
- `positionMode`: `queue`, `inspection`, or `correction`. Direct unreviewed target selection anchors the target queue; non-target positions are read-only inspection; reviewed targets are single-item correction and omit `Save & Next`.
- `activePosition`: numeric position. Queue advancement refreshes live state, skips remotely completed positions, never adds positions, and preserves the fixed denominator.
- `positionDraft`: label, optional note, mutation ID, dirty flag, expected current event ID.
- `montageMode`: `clean` or `analysis`.
- `showAlgorithmOverlay`, `showHumanOverlay`: independent booleans.

SVG cells are real focusable buttons/controls with accessible names, not click-only rectangles. The crop panel uses CSS object positioning or a canvas draw from the already verified Blob; it never refetches unverified bytes.

## Migration and compatibility

- Existing production DB migrates additively in one `BEGIN IMMEDIATE` transaction.
- Acquisition events and Hybrid comments remain byte/row/schema preserved.
- Previous runtime compatibility is tested against the additive position objects.
- Any partial/future/drifted position schema fails closed before serving mutation APIs.

## Security

Reuse the loopback backend and oauth2-proxy-exclusive boundary. The server derives identity and capability, validates same-origin JSON and bounded fields, uses parameterized SQL, rejects unknown fields, and never exposes allowlists or raw errors.

## Testing

- Builder: source path/digest, 9,216 unique positions, deterministic geometry/bytes, category/target reconciliation, malformed source failure, no labelled asset mutation.
- Backend: exact evidence loader, migration rollback/drift, roots/forks/cross-position supersession, idempotency/concurrency, auth/origin/content-type, audit.
- Frontend: publication/Blob mismatch, SVG geometry and keyboard semantics, mode toggles, target queue, ad-hoc direct position, dirty/conflict/retry/read-only.
- Integration: exact dataset counts, zero scientific event creation by smoke, Hybrid preservation, desktop/mobile browser flow, OpenShift asset/proxy/DB gates.

## Risks and mitigations

- **Anchoring to machine labels:** clean mode defaults on; algorithm context is a separate toggle/panel.
- **Overwhelming 9,216 denominator:** progress is explicitly target-cohort based; all positions remain selectable without becoming mandatory.
- **Image/overlay drift:** fixed geometry version and exact 256-cell reconciliation fail closed.
- **Publication size:** publish 36 clean JPEGs and compact position JSON, not 9,216 raw PNGs.
- **False scientific promotion:** algorithm category and human position label remain separate; acquisition disposition is not exposed in this workflow.
