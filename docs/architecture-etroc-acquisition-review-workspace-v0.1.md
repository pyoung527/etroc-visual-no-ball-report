# ETROC Acquisition Review Workspace — Architecture v0.1

## Architecture decision

Add a domain-specific ETROC review layer rather than embedding 36 copies of the existing Hybrid comment form or coercing pre-bonding ETROCs into `hybrid_registry`.

The architecture has three independent layers:

1. immutable ETROC publication data and montage assets;
2. append-only live ETROC review events;
3. a same-page review workspace that joins them only after exact provenance validation.

## Surface

```text
#optical tab
├── existing static ETROC scientific analytics
├── live review progress summary
├── review controls
│   ├── Start / Resume review
│   ├── state / wafer / serial / candidate filters
│   └── candidate-priority / wafer-serial ordering
├── montage card pool with live state badges
└── review workspace dialog
    ├── evidence viewport
    │   ├── montage image
    │   ├── fit / zoom / pan / reset
    │   └── exact evidence provenance
    └── decision pane
        ├── current state
        ├── structured state buttons
        ├── note
        ├── history
        └── Previous / Save / Save & Next
```

The review workspace is a focus-managed modal dialog on desktop and a full-screen sheet on narrow mobile. Closing it returns focus to the originating ETROC card.

## Data ownership

| Domain | System of record |
|---|---|
| ETROC component identity | immutable `chips.json` publication contract |
| Acquisition and analysis identity | immutable `chips.json` fields |
| Montage digest and content-addressed path | immutable `chips.json` record plus deployment manifest |
| Bytes actually reviewed | browser-verified Blob displayed through an object URL |
| Human review state/history | new SQLite `etroc_review_events` table |
| CERN user identity | trusted oauth2-proxy identity header |
| ETROC mutation authorization | explicit `ETROC_REVIEWER_USERS` allowlist |
| Hybrid identity/comments | existing registry/comments tables, unchanged |

Human review never mutates `chips.json`, montage files, analysis categories, or canonical Hybrid records.

## End-to-end evidence-byte binding

Each montage is published at a content-addressed path such as:

```text
/data/etroc-optical/ETROC_OI_2608/montages/sha256/<montage_sha256>.jpg
```

The immutable record contains that exact path and digest. Serial-only montage paths may remain as compatibility links for browsing but are never review-save evidence.

The binding chain is:

```text
validated chips.json bytes + publication SHA-256
  -> server returns the full 36-entry canonical evidence map
  -> browser hashes and parses those same chips.json bytes
  -> browser reconciles the exact map keyset/cardinality and each five-field record
  -> content-addressed URL containing the same montage digest
  -> server/deployment gate hashes deployed file bytes
  -> browser fetches URL as Blob
  -> browser computes SHA-256 with crypto.subtle.digest
  -> browser displays that same Blob via object URL
  -> Save enabled only while all publication/evidence/URI/Blob identities match
```

The server also hashes canonical montage bytes when loading/reloading the evidence map. Any missing file, wrong bytes, path/digest disagreement, or JSON/asset deployment skew makes that evidence unavailable for review mutation. The browser revokes old object URLs and re-verifies after navigation/reload; it never records metadata for an independently loaded mutable image.

## Persistence model

### v1 schema

```sql
CREATE TABLE etroc_review_schema (
    singleton  INTEGER PRIMARY KEY CHECK (singleton = 1),
    version    INTEGER NOT NULL CHECK (version >= 1),
    applied_at INTEGER NOT NULL
) WITHOUT ROWID;

CREATE TABLE etroc_review_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id          TEXT NOT NULL,
    etroc_serial        TEXT NOT NULL,
    acquisition_id      TEXT NOT NULL,
    analysis_run_id     TEXT NOT NULL,
    montage_sha256      TEXT NOT NULL,
    state               TEXT NOT NULL CHECK (state IN (
                            'reviewed_no_optical_concern',
                            'reviewed_concern_observed',
                            'follow_up_required'
                        )),
    note                TEXT NOT NULL DEFAULT '' CHECK (
                            length(note) <= 2000 AND (
                                state = 'reviewed_no_optical_concern'
                                OR length(trim(note)) > 0
                            )
                        ),
    author              TEXT NOT NULL,
    author_display      TEXT NOT NULL,
    created_at          INTEGER NOT NULL,
    mutation_id         TEXT NOT NULL,
    supersedes_event_id INTEGER,
    FOREIGN KEY (supersedes_event_id)
        REFERENCES etroc_review_events(id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX idx_etroc_review_one_root
    ON etroc_review_events(
        dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256
    ) WHERE supersedes_event_id IS NULL;

CREATE UNIQUE INDEX idx_etroc_review_one_successor
    ON etroc_review_events(supersedes_event_id)
    WHERE supersedes_event_id IS NOT NULL;

CREATE UNIQUE INDEX idx_etroc_review_author_mutation
    ON etroc_review_events(author, mutation_id);

CREATE INDEX idx_etroc_review_current_lookup
    ON etroc_review_events(
        dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,id
    );

CREATE TRIGGER etroc_review_no_update
BEFORE UPDATE ON etroc_review_events
BEGIN SELECT RAISE(ABORT, 'ETROC review events are append-only'); END;

CREATE TRIGGER etroc_review_no_delete
BEFORE DELETE ON etroc_review_events
BEGIN SELECT RAISE(ABORT, 'ETROC review events are append-only'); END;

CREATE TRIGGER etroc_review_same_evidence_successor
BEFORE INSERT ON etroc_review_events
WHEN NEW.supersedes_event_id IS NOT NULL
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM etroc_review_events AS previous
    WHERE previous.id = NEW.supersedes_event_id
      AND previous.dataset_id = NEW.dataset_id
      AND previous.etroc_serial = NEW.etroc_serial
      AND previous.acquisition_id = NEW.acquisition_id
      AND previous.analysis_run_id = NEW.analysis_run_id
      AND previous.montage_sha256 = NEW.montage_sha256
  ) THEN RAISE(ABORT, 'invalid ETROC review supersession') END;
END;
```

`unreviewed` is derived from no root for the canonical five-field evidence key; it is not inserted as a synthetic event. The current review is the sole event in that chain for which no other event references its ID. A successor must reference that immediate current event. The partial unique indexes prevent multiple roots and branches, while the trigger rejects cross-acquisition/evidence supersession. `(author, mutation_id)` uniquely identifies one logical write and supports deterministic retry after a lost response. A new acquisition, serial binding, analysis run, or montage digest therefore starts a separate unreviewed chain without deleting history.

### Schema compatibility and migration protocol

The existing application uses `PRAGMA user_version` for Hybrid registry migrations. Incrementing it would make previous-binary rollback reject the database. ETROC review therefore has an independent metadata table while leaving the existing Hybrid `user_version` unchanged.

Supported states are explicit:

- no `etroc_review_schema` table and no ETROC review objects: subsystem version `0`;
- exactly one metadata row `(singleton=1, version=1, applied_at=...)` plus the exact v1 tables/indexes/triggers above: supported version `1`;
- metadata version greater than `1`, missing/multiple metadata rows, partial objects, extra or altered columns, CHECK clauses, indexes, trigger SQL, or foreign-key actions: unsupported drift; startup fails before serving.

Version `0 → 1` is the only v0.1 transition. Startup executes the following in one `BEGIN IMMEDIATE` transaction with `PRAGMA foreign_keys=ON`:

1. inspect existing ETROC object names and metadata;
2. reject partial pre-existing objects or unsupported/future versions;
3. create all v1 tables, indexes, triggers, and the version row;
4. validate exact `table_info`, normalized `sqlite_master.sql`, `foreign_key_list`, `index_list`/`index_info`, trigger definitions, and the singleton metadata row;
5. run `PRAGMA foreign_key_check` and require no rows;
6. commit only after every check passes.

Any exception, injected fault, or validation mismatch rolls back the whole ETROC migration. Reopening version `1` performs exact validation without mutation. No existing table or column is rewritten. A disposable copy must prove that the actual previous production binary starts and reads/writes a Hybrid comment after the additive v1 objects exist.

## Canonical evidence loader

The server adds a cached loader for:

```text
/app/static/data/etroc-optical/ETROC_OI_2608/chips.json
```

Startup and mutation validation require the same identity/provenance contract enforced by the frontend, including the exact 36-record cohort. The loader hashes the exact `chips.json` bytes as `publication_sha256` before parsing them. Before constructing maps, it rejects duplicate `acquisition_id` values and duplicate canonical five-field keys. The server then builds an immutable 36-entry map keyed by `acquisition_id`, requires a content-addressed montage URI whose path digest equals `montage_sha256`, resolves the file under the static root, and hashes the deployed bytes. Evidence enters the writable map only when file bytes, URI digest, record digest, publication hash, and manifest agree.

For every write, the server derives the complete canonical key:

- `dataset_id`;
- `etroc_serial`;
- `acquisition_id`;
- `analysis_run_id`;
- `montage_sha256`.

The client submits the acquisition ID and the complete five-field evidence key it displayed; that five-field key is the asserted evidence version in v0.1, and there is no separate client-supplied publication-version field. The server rejects unknown acquisitions, historical-only acquisitions, or any dataset/serial/run/hash mismatch. Read-only audit history is database-derived and remains available even when an acquisition is no longer in the writable current-publication map.

## API contracts

All JSON endpoints use `Cache-Control: no-store`. Unknown request fields are rejected. Timestamps are UTC Unix seconds. A review event has one stable response shape:

```json
{
  "event_id": 124,
  "dataset_id": "ETROC_OI_2608",
  "etroc_serial": "W02G4-44",
  "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
  "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
  "montage_sha256": "<64 lowercase hex>",
  "state": "reviewed_concern_observed",
  "note": "Inspect positions 17 and 46.",
  "author": "ypark@cern.ch",
  "author_display": "ypark",
  "created_at": 1787070000,
  "mutation_id": "4f3f65bf-c37a-4c84-87f5-fb65b6f8f2af",
  "supersedes_event_id": 123
}
```

`supersedes_event_id` is JSON `null` for a root. A current summary uses the same canonical key/state/author/time fields, plus `current_event_id` and `history_count`; it omits neither run nor montage digest.

All errors use:

```json
{
  "error": {
    "code": "stable_machine_code",
    "message": "Human-readable non-sensitive explanation"
  }
}
```

Optional conflict fields described below live inside `error`. Raw exceptions, SQL, paths, allowlists, proxy headers, and authentication material are never returned.

GET query parsing is strict and bounded: batched summary accepts exactly one `dataset_id` equal to the configured current dataset; history and audit accept exactly one non-empty percent-decoded UTF-8 `acquisition_id` within the same identifier length bound used by POST. Duplicate parameters, unknown parameters, malformed encoding/UTF-8, arrays, control characters, oversized values, or missing required parameters return `400 invalid_query`; syntactically valid unknown IDs use the endpoint-specific `404` code.

### Batched current summaries

```http
GET /api/etroc-reviews?dataset_id=ETROC_OI_2608
```

Response:

```json
{
  "dataset_id": "ETROC_OI_2608",
  "record_count": 36,
  "publication_sha256": "<SHA-256 of exact chips.json bytes>",
  "viewer": {
    "identity_display": "ypark",
    "can_append_review": true
  },
  "evidence": {
    "ETROC_OI_2608:W02G4-44:base": {
      "dataset_id": "ETROC_OI_2608",
      "etroc_serial": "W02G4-44",
      "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
      "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
      "montage_sha256": "<64 lowercase hex>",
      "montage_uri": "data/etroc-optical/ETROC_OI_2608/montages/sha256/<same digest>.jpg"
    }
  },
  "reviews": {
    "ETROC_OI_2608:W02G4-44:base": {
      "current_event_id": 123,
      "dataset_id": "ETROC_OI_2608",
      "etroc_serial": "W02G4-44",
      "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
      "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
      "montage_sha256": "<64 lowercase hex>",
      "state": "reviewed_no_optical_concern",
      "note": "No additional optical concern.",
      "author": "ypark@cern.ch",
      "author_display": "ypark",
      "created_at": 1787070000,
      "history_count": 2
    }
  }
}
```

`evidence` is mandatory and contains exactly 36 entries whose keys and embedded acquisition IDs match exactly; it is present even when every acquisition is unreviewed. Its keyset must equal the browser-validated publication keyset, and each entry must match the browser-parsed five-field record and content-addressed URI. The browser also hashes its fetched `chips.json` bytes and requires equality with `publication_sha256`. Any cardinality, duplicate, missing/extra key, field, URI, or publication-hash mismatch disables the entire live review mutation surface rather than only the affected card.

The server returns an empty `reviews` map only when the validated cohort/evidence map exists and no events exist. Dataset/API failure uses an error response, so the UI cannot render an outage as zero reviews. `viewer.can_append_review` is computed server-side from normalized trusted identity and the fail-closed allowlist; the allowlist itself is never sent to the browser. The frontend uses this capability for immediate read-only rendering, while POST independently repeats authorization.

### Current acquisition history

```http
GET /api/etroc-reviews/history?acquisition_id=<encoded exact ID>
```

Requires the acquisition to exist in the validated current publication. `200 OK` returns the canonical evidence record, current event or `null`, and the exact chain newest-first:

```json
{
  "evidence": {
    "dataset_id": "ETROC_OI_2608",
    "etroc_serial": "W02G4-44",
    "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
    "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
    "montage_sha256": "<64 lowercase hex>",
    "montage_uri": "data/etroc-optical/ETROC_OI_2608/montages/sha256/<same digest>.jpg"
  },
  "current": null,
  "history": []
}
```

A reviewed response substitutes the shared event object for `current` and returns every event in `history`. `404 acquisition_not_found` means the acquisition is not in the current publication; `503 evidence_unavailable` means canonical evidence could not be validated.

### Historical audit

```http
GET /api/etroc-reviews/audit?acquisition_id=<encoded exact ID>
```

Reads persisted events without requiring current-publication membership. `200 OK` returns all evidence chains for that exact acquisition:

```json
{
  "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
  "chains": [
    {
      "evidence": {
        "dataset_id": "ETROC_OI_2608",
        "etroc_serial": "W02G4-44",
        "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
        "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
        "montage_sha256": "<64 lowercase hex>"
      },
      "current_publication": false,
      "current_event": {
        "event_id": 124,
        "dataset_id": "ETROC_OI_2608",
        "etroc_serial": "W02G4-44",
        "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
        "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
        "montage_sha256": "<64 lowercase hex>",
        "state": "reviewed_concern_observed",
        "note": "Inspect positions 17 and 46.",
        "author": "ypark@cern.ch",
        "author_display": "ypark",
        "created_at": 1787070000,
        "mutation_id": "4f3f65bf-c37a-4c84-87f5-fb65b6f8f2af",
        "supersedes_event_id": 123
      },
      "history": [
        {
          "event_id": 124,
          "dataset_id": "ETROC_OI_2608",
          "etroc_serial": "W02G4-44",
          "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
          "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
          "montage_sha256": "<64 lowercase hex>",
          "state": "reviewed_concern_observed",
          "note": "Inspect positions 17 and 46.",
          "author": "ypark@cern.ch",
          "author_display": "ypark",
          "created_at": 1787070000,
          "mutation_id": "4f3f65bf-c37a-4c84-87f5-fb65b6f8f2af",
          "supersedes_event_id": 123
        }
      ]
    }
  ]
}
```

`current_event` is the terminal event in each persisted chain and `history` is newest-first. `404 audit_not_found` means no persisted chain exists. This endpoint is read-only; historical-only evidence can never be mutated through POST.

### Append state change

```http
POST /api/etroc-reviews
Content-Type: application/json
Origin: https://etl-hybrid-bbqc.app.cern.ch
```

Request:

```json
{
  "dataset_id": "ETROC_OI_2608",
  "etroc_serial": "W02G4-44",
  "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
  "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
  "montage_sha256": "<64 lowercase hex>",
  "state": "reviewed_concern_observed",
  "note": "Inspect positions 17 and 46.",
  "expected_current_event_id": 123,
  "mutation_id": "4f3f65bf-c37a-4c84-87f5-fb65b6f8f2af"
}
```

Rules:

- CERN SSO identity is required and the normalized user must be in `ETROC_REVIEWER_USERS`; authenticated non-reviewers receive `403` and no transaction begins;
- the complete five-field evidence key and content-addressed deployed bytes must exactly match the writable canonical record;
- browser Save is enabled only after hashing and displaying the matching Blob, while the server independently revalidates current evidence;
- `mutation_id` must be a canonical UUID string generated once per logical draft; `(author, mutation_id)` is unique;
- after authorization and syntax checks, the transaction first looks up `(author, mutation_id)`: an existing event whose canonical key, state, note, and `supersedes_event_id` exactly match the request returns `200` with that original event/readback and appends nothing, while any mismatch returns `409 Idempotency Conflict`;
- only when no matching mutation exists does normal current-publication/evidence validation and insertion continue;
- `expected_current_event_id` must be JSON `null` or a non-boolean positive integer;
- `expected_current_event_id=null` is valid only if no root exists for the exact key;
- a non-null expected ID must equal the sole immediate current event for that key and becomes `supersedes_event_id`;
- stale expected ID returns `409 Conflict` with the new current summary and performs no insert;
- the root/successor unique indexes and same-evidence trigger provide database-level no-root/no-fork/no-cross-key enforcement;
- concern/follow-up require a non-empty note;
- no-concern permits an empty note;
- author fields come only from the trusted proxy-exclusive CERN SSO identity header;
- insertion, current-version comparison, and refreshed readback occur in one `BEGIN IMMEDIATE` transaction;
- success returns the inserted event and refreshed current summary.

A newly inserted event returns `201 Created`:

```json
{
  "ok": true,
  "idempotent_replay": false,
  "event": {
    "event_id": 124,
    "dataset_id": "ETROC_OI_2608",
    "etroc_serial": "W02G4-44",
    "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
    "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
    "montage_sha256": "<64 lowercase hex>",
    "state": "reviewed_concern_observed",
    "note": "Inspect positions 17 and 46.",
    "author": "ypark@cern.ch",
    "author_display": "ypark",
    "created_at": 1787070000,
    "mutation_id": "4f3f65bf-c37a-4c84-87f5-fb65b6f8f2af",
    "supersedes_event_id": 123
  },
  "current": {
    "current_event_id": 124,
    "dataset_id": "ETROC_OI_2608",
    "etroc_serial": "W02G4-44",
    "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
    "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
    "montage_sha256": "<64 lowercase hex>",
    "state": "reviewed_concern_observed",
    "note": "Inspect positions 17 and 46.",
    "author": "ypark@cern.ch",
    "author_display": "ypark",
    "created_at": 1787070000,
    "history_count": 2
  }
}
```

An exact retry of an already committed mutation returns `200 OK` with the same shape, same `event`, current chain summary at readback time, and `idempotent_replay: true`; it never appends or advances twice.

A stale current version returns `409 Conflict`:

```json
{
  "error": {
    "code": "stale_current",
    "message": "The review changed after it was loaded.",
    "submitted_expected_current_event_id": 123,
    "current": {
      "current_event_id": 125,
      "dataset_id": "ETROC_OI_2608",
      "etroc_serial": "W02G4-44",
      "acquisition_id": "ETROC_OI_2608:W02G4-44:base",
      "analysis_run_id": "ETROC_OI_2608:common-baseline-v0:pack2",
      "montage_sha256": "<64 lowercase hex>",
      "state": "follow_up_required",
      "note": "Independent reinspection requested.",
      "author": "reviewer@cern.ch",
      "author_display": "reviewer",
      "created_at": 1787070100,
      "history_count": 3
    }
  }
}
```

The frontend uses this exact `error.current` object for the conflict UI and retains the unsaved draft. Mutation-ID reuse with any non-identical request returns `409 Conflict` with `{error: {code: "mutation_id_conflict", message: "...", existing_event_id: 124}}`; it does not expose another author's event. Current-publication/evidence mismatch returns `409 Conflict` with `code: "evidence_changed"` and `canonical_evidence` containing the server's full current evidence record, or `null` when the acquisition is no longer writable.

Other statuses are fixed:

| Status | `error.code` | Condition |
|---|---|---|
| `400` | `invalid_json` / `invalid_request_shape` / `unknown_field` / `invalid_query` | malformed JSON/body, missing/extra fields, or invalid/duplicate/unknown/oversized GET parameters |
| `401` | `authentication_required` | no trusted proxy identity reaches the app |
| `403` | `review_not_authorized` / `same_origin_required` | non-allowlisted identity or wrong Origin |
| `404` | `dataset_not_found` / `acquisition_not_found` / `audit_not_found` | requested read target does not exist |
| `409` | `stale_current` / `mutation_id_conflict` / `evidence_changed` | concurrency, idempotency, or current-evidence conflict |
| `415` | `json_required` | mutation media type is not `application/json` |
| `422` | `invalid_state` / `invalid_note` / `invalid_event_id` / `invalid_mutation_id` / `invalid_digest` | syntactically valid request violates field rules |
| `503` | `evidence_unavailable` / `review_store_unavailable` | canonical publication/assets or SQLite cannot be safely read |

Batched GET, history, and audit use the same error envelope and applicable read statuses. No error is represented as an empty evidence/review/history success body.

There is no PATCH or DELETE for ETROC review events in v0.1. Corrections append a superseding event, and database triggers reject direct event UPDATE/DELETE.

## Queue derivation

The frontend joins validated static records to live summaries by the exact canonical five-field evidence key; acquisition-only matches are insufficient.

One shared comparator, used by cards, `Start/Resume`, tests, and `Save & Next`, is:

```text
unreviewed first
  -> optical_no_ball_candidate_count > 0 first
  -> red_candidate_count > 0 first
  -> needs_inspection_count descending
  -> review_candidate_count descending
  -> etroc_serial natural ascending
```

`Start/Resume` snapshots wafer, serial, candidate filters, and comparator choice; it intentionally ignores the card-view current-state filter and includes only acquisitions that are unreviewed when the queue opens. Before every advance, the client refreshes summaries for remaining acquisitions and skips items completed remotely. The snapshot never expands to a different wafer/serial/candidate filter. If no still-unreviewed item remains, the dialog shows an end-of-queue summary and waits for explicit close/return.

Directly opening an unreviewed card constructs the same filtered/sorted unreviewed queue, anchors the cursor at the clicked acquisition, and advances only through later entries without wrapping. Directly opening an already reviewed card is correction mode: Save appends a successor, while `Save & Next` is unavailable. A conflict preserves the local draft and does not advance. Previous/Next, Escape, overlay click, and close are blocked by an accessible discard confirmation whenever state/note differs from the loaded draft.

## Frontend components

### `hybrid-bbqc/etroc-optical.js`

Retains sole ownership of fetching immutable publication bytes, hashing those exact bytes, parsing/validating the same bytes, and exposing `{records, publicationSha256}` to the review controller. It does not overwrite `record.review_state`.

### `hybrid-bbqc/etroc-review.js`

New controller responsibilities:

- batched summary/capability/full-evidence/current-history/historical-audit API calls;
- exact 36-entry keyset, publication SHA-256, five-field provenance, and content-addressed URI reconciliation before any mutation control is enabled;
- content-addressed Blob fetch, Web Crypto SHA-256 verification, object-URL lifecycle, and Save gating;
- the single candidate-priority comparator and live-state-refreshing queue advancement;
- dialog lifecycle, dirty-draft confirmation, and focus restoration;
- zoom/pan/reset controls over the verified Blob;
- state/note validation plus server-derived capability-based read-only presentation;
- stable mutation-ID lifecycle, idempotent timeout reconciliation, optimistic-concurrency save, preserved-draft conflict presentation, and correction mode;
- `Save & Next`, end-of-queue, and resume behavior;
- degraded live-API/evidence-integrity state.

Use safe DOM construction and `textContent`; do not render reviewer text through `innerHTML`.

### `hybrid-bbqc/etroc-review.css`

New scoped styles reuse the existing forest/gold/cream visual language. State is not encoded by color alone. Controls have at least 44 px targets, visible focus, reduced-motion behavior, and mobile full-screen layout.

### `hybrid-bbqc/index.html`

Add semantic review summary/filter containers and one dialog shell inside the ETROC tab. Do not pre-render 36 comment forms.

## Accessibility and keyboard behavior

- Dialog uses `role=dialog`, `aria-modal=true`, labelled title, focus trap, and originating-card focus restoration.
- Escape/close/navigation closes immediately only for a clean draft; a dirty draft opens a labelled confirmation dialog with explicit `Keep editing` and `Discard draft` actions.
- Previous/next keyboard shortcuts are disabled while focus is in inputs, textarea, select, or content-editable elements.
- Zoom controls are buttons with announced current zoom; pan is not the only way to inspect the verified image.
- State radio group has a legend explaining that states are optical reviews, not production QC dispositions.
- Byte-verification, Save results, and conflict errors use an `aria-live` status region.
- History is a semantic ordered list with author/time/state and current-versus-historical-evidence text.

## Failure and degradation

- Static ETROC payload invalid or JSON/asset deployment skew: fail the entire ETROC pool/statistics/review surface closed as today.
- Review API unavailable: keep non-authoritative static montage browsing available; label live review unavailable; disable mutation controls.
- Review response canonical-key mismatch: do not display the returned state; show an integrity error.
- Missing content-addressed image, URL/hash mismatch, server byte mismatch, stale cached bytes, browser digest mismatch, or Blob decode failure: keep metadata/history visible, revoke the object URL, disable Save, and offer verified retry only.
- Authenticated user outside `ETROC_REVIEWER_USERS`: show read-only review/history and explain that mutation is not authorized.
- Save network timeout: preserve the draft and its mutation ID, do not advance, then retry the exact logical mutation; committed requests return the original event and uncommitted requests insert once.
- `409 Conflict`: preserve the draft, display the intervening current event, and require the reviewer to explicitly reapply or cancel.
- End-of-queue: show reviewed/remaining counts and wait for explicit return; never wrap silently.

## Security

- CERN SSO is required; reads remain within the SSO-protected application route.
- Normalize `ETROC_REVIEWER_USERS` with the same identity canonicalization as the trusted proxy header. Missing/empty/malformed allowlist fails closed for mutation.
- Only allowlisted users may POST; authenticated non-reviewers receive `403`, and unauthenticated requests receive `401`.
- Preserve the proxy-exclusive trusted-header boundary; ordinary clients cannot manufacture identity/authorization with a forwarded header.
- Acceptance requires both directions: an external route request supplying the configured identity header as an allowlisted user must still be redirected/rejected or retain the real non-allowlisted identity, while an internal proxy-to-app request carrying the proxy-derived allowlisted identity must succeed.
- Reuse strict `Origin == APP_ORIGIN` and `application/json` checks.
- Parameterized SQL only.
- Bound request size, note length, enums, exact key fields, integer event IDs, and SHA-256 format.
- Reject booleans/fractional values for event IDs.
- Client fields are assertions to validate, not authority: the server derives author, timestamps, dataset, serial, acquisition lineage, run, URI, and digest from trusted sources.

## Required production authentication topology

The ETROC review feature is deployable only with the BBQC-specific manifests and hardened overlay path; root-level `openshift/deployment.yaml` and `openshift/service.yaml` are not valid release inputs for this application.

Mandatory baseline artifacts:

- `hybrid-bbqc/openshift/deployment.yaml`;
- `hybrid-bbqc/openshift/service.yaml`;
- `hybrid-bbqc/openshift/route.yaml`;
- `hybrid-bbqc/openshift/deploy_dashboard_overlay_lxplus.sh` plus its provenance/selector helpers.

The candidate and live OpenShift objects must preserve all of these invariants:

1. The `web` container sets `HOST=127.0.0.1`, listens only on pod loopback port 8080, has `COMMENTS_ALLOW_ANON=false`, exact `APP_ORIGIN=https://etl-hybrid-bbqc.app.cern.ch`, and receives the non-empty `ETROC_REVIEWER_USERS` configuration.
2. A digest-pinned `oauth2-proxy` sidecar is the only externally reachable container, listens on 4180, and uses `--upstream=http://127.0.0.1:8080`.
3. `--pass-user-headers=true` supplies the CERN identity. For the pinned proxy version, `--skip-auth-strip-headers=true` must be regression-tested to drop an incoming request's authentication-style header value before injecting the session-derived `X-Forwarded-Email`; a proxy version or flag change blocks rollout until the behavior is re-proven.
4. The Service exposes only `targetPort: oauth`; no Service or Route targets the `web` port.
5. The Route targets that Service's `oauth` port, uses host `etl-hybrid-bbqc.app.cern.ch`, TLS edge termination, and HTTP-to-HTTPS redirect.
6. Deployment strategy remains `Recreate`, so old and new SQLite writers do not overlap.
7. The immutable overlay preserves the captured proxy image digest/topology while replacing only the validated web image and approved review configuration.

The deployment helper must inspect the rendered and live Deployment/Service/Route before rollout and again after rollout. Any direct web Service, non-loopback web bind, missing proxy sidecar, non-digest proxy image, non-loopback upstream, identity-header behavior mismatch, origin/host mismatch, or route-to-web path is a hard failure. External authenticated browser verification must send a conflicting client `X-Forwarded-Email` value and still observe the actual CERN session identity/capability; unauthenticated injection must still redirect to CERN SSO. A normal authenticated request through the proxy must produce the expected allowlisted capability.

## Test strategy

### Database and API

- True legacy database fixture executes exact version `0→1` migration without altering Hybrid rows/comments or existing `PRAGMA user_version`.
- Second startup at v1 is read-only/idempotent; future version, missing metadata row, extra row, partial table, altered column/CHECK/FK/index/trigger, and stray ETROC object all fail before serving.
- Injected failures after each DDL/metadata/validation step roll back every ETROC object and row.
- Previous production binary accepts the additive database and can read/write a Hybrid comment.
- Valid first review and immediate-current successor preserve one linear history chain.
- Multiple roots, branch/fork, cross-acquisition/run/hash/serial supersession, missing predecessor, duplicate `(author, mutation_id)`, direct UPDATE, and direct DELETE fail at database/application boundaries.
- Current lookup uses the full five-field key; historical acquisition audit remains readable after removal from the current publication, while POST is rejected.
- Unknown acquisition, wrong dataset/serial/run/hash, malformed state, missing required note, oversized note, and forged author fail.
- Stale/missing/boolean/fractional expected event ID returns the specified error without insert.
- Concurrent first writers produce exactly one success and one conflict.
- A committed-but-response-lost retry with the same author/mutation ID and exact payload returns the original event with no duplicate; an uncommitted retry inserts once; mutation-ID payload reuse returns idempotency conflict.
- Unauthenticated, authenticated-but-not-allowlisted, missing/empty/malformed allowlist, wrong-origin, and wrong-content-type writes fail; an allowlisted reviewer succeeds.
- Batched GET capability is `true` only for an allowlisted trusted identity and `false` for non-allowlisted or fail-closed allowlist states without exposing the allowlist.
- External route injection of the configured identity header cannot gain allowlisted capability/POST success; an internal proxy-derived allowlisted identity integration fixture succeeds.
- Batched summaries always return an exact 36-entry server-authoritative evidence map and publication hash, including the all-unreviewed/empty-reviews case; missing/extra/duplicate keys, wrong fields/URI/hash, and API/evidence-loader failures are distinguishable and fail closed.
- Contract tests assert exact no-store response schemas and status/error codes for batched GET, current history, historical audit, strict GET query validation, `201` insert, `200` idempotent replay, stale-current/intervening-event conflict, mutation-ID conflict, evidence change/removal, validation/auth/origin/content-type failures, and `503` evidence/store degradation.

### Frontend

- The one canonical candidate-priority comparator is deterministic on all tie levels.
- State filters do not alter static analytics denominators.
- Review summary joins only after raw `chips.json` byte hashing and an exact 36-entry server evidence-map/publication-hash reconciliation; the all-unreviewed empty-review map still enables only evidence-verified authorized mutation.
- Real-browser fixtures cover correct content-addressed Blob, stale cached bytes, wrong bytes, URL/hash mismatch, JSON/asset deployment skew, and decode failure; only exact verified displayed bytes enable Save.
- Object URLs are revoked and adjacent-image preloading remains bounded.
- Start/Resume ignores the card-only state filter, snapshots wafer/serial/candidate filters plus ordering, refreshes live states, skips remotely completed items, handles end-of-queue, and never expands filters.
- Direct unreviewed-card open builds the same queue anchored at that card and does not wrap; reviewed-card correction mode disables Save & Next.
- Conflict preserves draft; navigation/Escape/close protects dirty drafts.
- Capability `false` renders read-only controls without probing POST; capability `true` permits controls but does not bypass POST reauthorization.
- Timeout retry retains one mutation ID and reconciles committed/uncommitted outcomes without duplicate advance or duplicate event.
- API failure preserves non-authoritative montage browsing but disables review mutation.
- Notes are rendered as text, not HTML.

### Production

- Online SQLite backup, integrity, exact Hybrid/ETROC schema, and comment/review counts before mutation.
- Candidate image/startup probe against a disposable legacy database copy, including actual previous-binary Hybrid comment read/write.
- Rendered/live BBQC Deployment, Service, and Route satisfy the exact loopback-web, digest-pinned oauth2-proxy, oauth-only Service/Route, header-strip/inject, `APP_ORIGIN`, TLS, and `Recreate` invariants; root-level OpenShift manifests are rejected as release inputs.
- Build/runtime gates hash `chips.json`, require the same `publication_sha256` from the API, validate the exact 36-entry evidence map, and hash the manifest plus every content-addressed montage/URI correspondence before rollout success.
- Immutable Build provenance and digest-bound rollout.
- Post-rollout exact review schema/triggers, existing comments, authorized capability/POST/readback, unauthorized `403`, external trusted-header spoof resistance, internal proxy-derived identity success, idempotent lost-response retry, conflict, historical audit, pod readiness, logs, route SSO, and desktop/mobile verified-Blob interaction.

## Rollout and rollback

1. Back up `/data/comments.sqlite3` online and copy/verify it off-cluster.
2. Build content-addressed montage paths and verify every file byte against `chips.json` and the release manifest; record exact `publication_sha256`.
3. Probe the candidate image against a copied true-legacy database; require atomic v1 migration, exact schema/trigger validation, evidence-byte loader success, and actual previous-production-binary Hybrid comment read/write before production mutation.
4. Confirm `ETROC_REVIEWER_USERS` is non-empty, normalized, and contains only the explicitly approved identities; record its non-secret digest/count, not raw authentication material.
5. Render and validate the BBQC Deployment/Service/Route topology against all mandatory proxy, loopback, oauth-port, origin, TLS, digest, and `Recreate` invariants; reject root-level OpenShift manifests.
6. Deploy the immutable web image digest while preserving the captured digest-pinned proxy and validated topology.
7. Verify existing Hybrid comments plus exact API publication/evidence map, allowlisted capability/append/readback, read-only capability, unauthorized `403`, external header-spoof resistance, internal proxy-derived identity success, idempotent retry, conflict, historical audit, and browser-displayed Blob hash.
8. If rollout or verification fails, restore the exact previous Deployment object/image. Because v1 is additive and previous-binary compatible by an exercised probe, database rollback should not normally be required; retain the verified DB backup for emergency recovery and never delete review events to force rollback.
