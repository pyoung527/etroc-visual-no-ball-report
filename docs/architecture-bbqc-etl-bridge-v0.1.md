# BBQC–ETL Hybrid Registry Bridge Architecture v0.1

**Date:** 2026-07-29
**Status:** Approved by Young for implementation
**Scope:** BBQC service and its SQLite database; ETL staging schema remains unchanged.

## Problem

ETL staging exposes separate ETROC, LGAD and Subassembly/Hybrid inventories. BBQC is a generated, denormalized ETROC–LGAD QC dashboard whose row, URL and comment identity are based on `ETROC__LGAD`. BBQC currently persists only comments, so it has no stable record that can hold ETL Hybrid identity or survive pair-key changes.

## Decision

Add a stable registry and target-alias layer to the existing BBQC SQLite database. Preserve all current comment API request shapes and static URLs.

## Data model

```sql
CREATE TABLE hybrid_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_key TEXT NOT NULL UNIQUE,
    etroc_serial TEXT NOT NULL,
    lgad_serial TEXT NOT NULL,
    etl_hybrid_id INTEGER UNIQUE,
    etl_hybrid_serial TEXT UNIQUE,
    sync_status TEXT NOT NULL DEFAULT 'unregistered'
      CHECK (sync_status IN ('unregistered','matched','conflict','retired')),
    bbqc_url TEXT NOT NULL,
    source_revision TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX uq_hybrid_registry_active_etroc
  ON hybrid_registry(etroc_serial) WHERE active=1;
CREATE UNIQUE INDEX uq_hybrid_registry_active_lgad
  ON hybrid_registry(lgad_serial) WHERE active=1;

CREATE TABLE hybrid_target_aliases (
    target TEXT PRIMARY KEY,
    hybrid_registry_id INTEGER NOT NULL,
    is_canonical INTEGER NOT NULL DEFAULT 0 CHECK (is_canonical IN (0,1)),
    created_at INTEGER NOT NULL,
    FOREIGN KEY (hybrid_registry_id) REFERENCES hybrid_registry(id)
);

ALTER TABLE comments ADD COLUMN hybrid_registry_id INTEGER
  REFERENCES hybrid_registry(id);
```

`comments.target` remains for backward compatibility. New and migrated hybrid comments also carry `hybrid_registry_id`.

## Startup migration

1. Create registry and alias tables idempotently.
2. Add nullable `comments.hybrid_registry_id` when absent.
3. Parse canonical dashboard links from `/app/static/index.html`; abort before registry mutation if no pairs are found or if any ETROC/LGAD child is duplicated.
4. Preflight each canonical pair against existing rows using exact pair, redirect provenance, then an unambiguous ETROC-or-LGAD child match. Abort before mutation if two existing rows are candidates.
5. Parse redirect detail pages; add old `hybrid:<pair_key>` targets as aliases to the canonical registry row.
6. Add canonical `hybrid:<pair_key>` aliases.
7. Resolve existing hybrid comments through aliases and set `hybrid_registry_id` without rewriting `comments.target`.
8. Leave non-hybrid comment targets unchanged.

## Identity and invariants

- `hybrid_registry.id` is the stable BBQC identity.
- `pair_key = etroc_serial + '__' + lgad_serial`.
- Active ETROC and LGAD serials are individually unique.
- ETL Hybrid ID and serial are nullable until registration, but unique when present.
- Binding requires a positive signed-64-bit JSON integer ETL ID and printable, non-empty ETL serial; partial bind/unbind requests are rejected.
- Binding uses a serialized SQLite transaction. The first identity is immutable; an identical retry is idempotent and a replacement is rejected pending a separately audited correction workflow.
- A pair correction is represented by updating the stable registry row and retaining the former target as an alias; comments remain attached by registry ID.
- If exact pairs, redirects, existing alias ownership, backfilled comment ownership, or child evidence point to more than one registry row, startup fails closed before mutation rather than reassigning provenance.
- Startup globally rejects any non-null comment owner that disagrees with its alias owner, including stale aliases absent from current static pages; backfill updates only unowned comments.

## API

### Existing comments API

Request/response shapes remain compatible. Hybrid reads and summaries aggregate by registry ID while returning canonical targets. Writes retain the submitted target plus registry ID, preserving exact-target visibility for the previous application.

### Registry read API

`GET /api/hybrids?pair_key=<pair>` returns a matching registry row. Without a filter, returns active rows, capped at 200.

### ETL binding API

`POST /api/hybrids/bind`

```json
{
  "pair_key": "W04F2-81__FBK_LF-W14_35",
  "etl_hybrid_id": 12345,
  "etl_hybrid_serial": "<ETL-approved serial>",
  "sync_status": "matched",
  "source_revision": "optional provenance"
}
```

Requires an authenticated administrator, exact application `Origin`, and `Content-Type: application/json`. All identity fields are required; unbinding is not implicit. Uses parameterized SQL. It does not call or modify ETL.

## Security boundary

- The Python backend listens only on `127.0.0.1:8080` inside the Pod.
- The Service exposes a digest-pinned oauth2-proxy only; explicit auth-header stripping is enabled and the backend trusts only `X-Forwarded-Email` passed upstream by `--pass-user-headers`.
- All mutations validate the exact configured `APP_ORIGIN`; JSON mutations reject non-JSON media types.

## Deployment

- Reuses `/data/comments.sqlite3` on the existing PVC.
- Migration runs automatically and idempotently on startup.
- Deployment strategy is `Recreate`, preventing old/new SQLite writers from overlapping.
- The image normalizes `/app` to root-owned read-only static content; only `/data` is owner/root-group writable for the OpenShift runtime UID and PVC.
- `COMMENTS_ADMIN_USERS` must contain Young's accepted CERN identity forms for the bind endpoint.
- Release and rollback procedures pin the web image by digest; mutable `:latest` is not used as a rollback target.
- Pre-rollout capture stores the complete Deployment spec with both runtime images pinned; rollback replaces and compares the full spec, then verifies both runtime digests and one owner-validated Ready pod.
- Operational blocks pin and revalidate API server, CERN account, and namespace; all namespaced commands pass the captured namespace explicitly.
- Build provenance records source revision, deterministic context checksum, Build ID, and output image digest.
- Pre-migration comment targets remain unchanged. A full data rollback validates its off-cluster backup before outage, inventories standard Kubernetes/OpenShift writer controllers (including DeploymentConfig, ReplicationController, exact-UID-owned ReplicaSet, and HPA) plus all pods, requires the current Deployment UID → ReplicaSet UID → Pod owner chain, proves Deployment/ReplicaSet desired replicas and PVC writers are zero, preserves the failed DB with SQLite backup, and restores while scaled to zero.

## Verification

- Unit tests on a temporary SQLite database and synthetic static dashboard.
- Migration test starting from the legacy comments-only schema.
- Alias/backfill test for a corrected pair URL.
- Binding uniqueness and validation tests.
- Full existing test suite.
- Local server HTTP checks for health, registry lookup, legacy comment lookup, authentication and binding.
- Container build and graphify update.
