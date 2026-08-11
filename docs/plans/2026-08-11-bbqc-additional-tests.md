# BBQC Additional Test Memberships — Implementation Plan

**Date:** 2026-08-11
**Status:** Approved scope: SQLite persistence + dashboard display
**Source:** Operator-supplied exact test/hybrid list in CERN work chat

## Goal

Persist two additional test definitions and their hybrid memberships in the BBQC SQLite database, expose them through the existing read API, and display them on the dashboard without changing the canonical 72-hybrid inventory or implying test execution/results.

## Interpretation boundary

- A membership means only **assigned/listed for the named test**.
- It does not mean the test was completed.
- It does not imply pass, fail, acceptance, rejection, or any measured result.
- Exact supplied identifiers beginning with `HYBRID_` are preserved as provenance.
- Each supplied identifier is explicitly cross-walked to an existing canonical `ETROC__LGAD` pair; identifiers are not silently normalized.

## Confirmed input cardinalities

| Test | Memberships |
|---|---:|
| Thermal cycling test | 12 |
| Shear force test | 6 |
| Total membership rows | 18 |
| Unique hybrids | 15 |
| Hybrids in both tests | 3 |
| Canonical inventory matches | 18/18 |

The three hybrids in both tests are:

- `HYBRID_W03F7-87_HPK-W2_1`
- `HYBRID_W04F2-89_HPK-W2_10`
- `HYBRID_W04F2-79_FBK_LF-W14_43`

### Exact golden crosswalk

| Test key | Exact source identifier | Current canonical pair |
|---|---|---|
| `thermal-cycling` | `HYBRID_W03F7-87_HPK-W2_1` | `W03F7-87__HPK-W2_1` |
| `thermal-cycling` | `HYBRID_W03F7-89_HPK-W2_3` | `W03F7-89__HPK-W2_3` |
| `thermal-cycling` | `HYBRID_W03F7-99_HPK-W2_7` | `W03F7-99__HPK-W2_7` |
| `thermal-cycling` | `HYBRID_W03F7-102_HPK-W2_9` | `W03F7-102__HPK-W2_9` |
| `thermal-cycling` | `HYBRID_W04F2-89_HPK-W2_10` | `W04F2-89__HPK-W2_10` |
| `thermal-cycling` | `HYBRID_W04F2-86_HPK-W2_13` | `W04F2-86__HPK-W2_13` |
| `thermal-cycling` | `HYBRID_W04F2-76_HPK-W2_18` | `W04F2-76__HPK-W2_18` |
| `thermal-cycling` | `HYBRID_W04F2-78_HPK-W2_20` | `W04F2-78__HPK-W2_20` |
| `thermal-cycling` | `HYBRID_W04F2-79_FBK_LF-W14_43` | `W04F2-79__FBK_LF-W14_43` |
| `thermal-cycling` | `HYBRID_W04F2-70_FBK_LF-W14_36` | `W04F2-70__FBK_LF-W14_36` |
| `thermal-cycling` | `HYBRID_W04F2-64_FBK_LF-W14_40` | `W04F2-64__FBK_LF-W14_40` |
| `thermal-cycling` | `HYBRID_W04F2-62_FBK_LF-W14_29` | `W04F2-62__FBK_LF-W14_29` |
| `shear-force` | `HYBRID_W03F7-87_HPK-W2_1` | `W03F7-87__HPK-W2_1` |
| `shear-force` | `HYBRID_W03F7-88_HPK-W2_2` | `W03F7-88__HPK-W2_2` |
| `shear-force` | `HYBRID_W04F2-89_HPK-W2_10` | `W04F2-89__HPK-W2_10` |
| `shear-force` | `HYBRID_W04F2-88_HPK-W2_12` | `W04F2-88__HPK-W2_12` |
| `shear-force` | `HYBRID_W04F2-79_FBK_LF-W14_43` | `W04F2-79__FBK_LF-W14_43` |
| `shear-force` | `HYBRID_W04F2-81_FBK_LF-W14_35` | `W04F2-81__FBK_LF-W14_35` |

Immutable manifest SHA-256 for this requirement: `90c8e9854c2dbdad9a5393ab4dd0e11314bad173c22048c7f3a637fe009619a5`.
The acceptance test contains the same 18 tuples independently; it does not derive expected values from the manifest.

## Versioned source manifest

Add `hybrid-bbqc/additional-tests.json` with:

- schema version;
- source revision/provenance label;
- stable test key and exact display name;
- exact `source_hybrid_identifier` from the supplied list;
- explicit canonical `pair_key` crosswalk.

The manifest is authoritative for current active memberships. Startup must parse and validate the complete manifest before mutating SQLite.

## SQLite model

### `additional_tests`

- `id` — stable local surrogate key;
- `test_key` — `NOT NULL`, unique stable machine key;
- `display_name` — `NOT NULL`, globally unique exact user-facing name;
- `source_revision` — `NOT NULL` current manifest provenance;
- `active` — `NOT NULL CHECK(active IN (0,1))` lifecycle;
- `created_at`, `updated_at` — `NOT NULL`.

### `hybrid_additional_tests`

- `additional_test_id` → `additional_tests.id`, `NOT NULL ON DELETE RESTRICT`;
- `hybrid_registry_id` → `hybrid_registry.id`, `NOT NULL ON DELETE RESTRICT`;
- `source_hybrid_identifier` — `NOT NULL`, exact supplied `HYBRID_...` value;
- `source_revision` — `NOT NULL` current manifest revision;
- `active` — `NOT NULL CHECK(active IN (0,1))`;
- `created_at`, `updated_at` — `NOT NULL`;
- primary key `(additional_test_id, hybrid_registry_id)`;
- unique `(additional_test_id, source_hybrid_identifier)`.

This is a many-to-many relationship, allowing one hybrid to appear in both tests. The database stores **current-state provenance**: an approved raw identifier or source-revision change updates the stable membership row only when values actually differ; prior revisions remain recoverable from Git/release evidence rather than as DB history. Inactive rows preserve the latest known provenance.

`source_hybrid_identifier` and canonical `pair_key` are independent, explicitly approved crosswalk values. For a future pair correction, the manifest changes only `pair_key` in the same reviewed release, retains the byte-exact raw identifier, and reconciliation resolves the corrected pair to the existing stable `hybrid_registry.id`.

## Migration rules

1. Parse and validate the canonical inventory, redirect evidence, unique ETROC/LGAD ownership, and complete manifest before opening a write transaction.
2. Reject missing/empty production manifests, unsupported schema versions, invalid JSON/types/revisions, duplicate test keys/names/raw IDs/canonical memberships, malformed raw identifiers, conflicting crosswalks, and unknown canonical pairs.
3. Enable foreign keys, then acquire `BEGIN IMMEDIATE`; DDL, schema introspection, reconciliation, checks, schema-version update, and commit occur in that one transaction.
4. Use `PRAGMA user_version=2` plus exact semantic introspection of columns, PKs, unique indexes, checks and foreign-key delete actions; a partial/incompatible pre-existing table fails closed.
5. Upsert active tests and memberships while preserving IDs and `created_at`. `updated_at` changes only when display name, source revision, raw identifier, canonical relationship, or active state changes.
6. Mark previously managed but no-longer-listed records inactive with an updated timestamp; do not erase historical rows. A later re-addition reactivates the same stable row.
7. Preserve existing comments, aliases, registry identities, ETL bindings, and source provenance.
8. Consume every row from `PRAGMA foreign_key_check` and require the complete `PRAGMA integrity_check` result to be exactly one `ok` row before commit.
9. A second startup with the same inventory/manifest is a data no-op: IDs and both timestamps remain unchanged.

## API contract

Extend `GET /api/hybrids` records with:

```json
{
  "additional_tests": [
    {
      "test_key": "thermal-cycling",
      "display_name": "Thermal cycling test",
      "source_hybrid_identifier": "HYBRID_W03F7-87_HPK-W2_1"
    }
  ]
}
```

- Every returned hybrid has `additional_tests`; non-members receive `[]`.
- Nested rows require an active registry row, active test, and active membership.
- Ordering is deterministic by test key.
- Existing fields, top-level `count`, and filtering by exact `pair_key` remain backward compatible.
- The dashboard always fetches the complete unfiltered `/api/hybrids` payload, joins cards/rows by exact `pair_key`, and computes 12/6 as active **membership-row** counts; filtered responses are never used for global totals.
- No mutation endpoint is added in this scope; the versioned manifest is the source of truth.

## Dashboard contract

- Add an “Additional tests” summary showing `Thermal cycling test — 12` and `Shear force test — 6` active membership rows.
- Add accessible membership badges to corresponding hybrid cards and table rows.
- A hybrid in both tests shows both badges.
- Add visible text explaining that badges denote assignment only, not execution or result.
- Dynamic labels and identifiers are rendered only with DOM `textContent`, never API-derived `innerHTML`.
- Additional-test availability has its own `role=status`/live region; hybrid-API failure cannot overwrite or misrepresent the independent live-comment status.
- If the live hybrid API fails, the canonical static inventory and current evidence dashboard remain usable; additional-test display alone shows a degraded/unavailable state without inventing data.
- Preserve all existing scientific labels, counts, identifiers, comment behavior, responsive layout, and reduced-motion behavior.

## TDD acceptance matrix

1. Legacy comments-only DB + real/synthetic static inventory + manifest creates registry/test/membership tables.
2. Exact counts: 2 active tests, 18 active memberships, 15 distinct hybrids, 3 dual-test hybrids.
3. All 18 raw identifiers round-trip byte-for-byte from manifest → DB → API.
4. Every explicit pair key exists in the canonical inventory and resolves to one stable registry ID.
5. Duplicate/malformed/unknown membership fails before mutation.
6. Missing/empty manifest fails without deactivating prior records.
7. Second migration is idempotent and retains IDs/timestamps.
8. Removed membership becomes inactive rather than deleted.
9. Pair correction preserves membership through stable registry ID.
10. `/api/hybrids` remains backward compatible and returns deterministic nested tests.
11. Dashboard summary counts are 12 and 6; dual members show both badges.
12. Dashboard labels membership as assignment only, not result.
13. Existing 72-hybrid canonical inventory and full test suite remain unchanged/passing.

## Deployment boundary

Production currently runs the legacy comments-only backend with a static dashboard overlay. This feature requires a full application image containing the registry migration, manifest, API change, and UI assets—not another static-only overlay.

Before production mutation:

1. finish the outstanding BuildConfig provenance hardening and independent review;
2. capture account/server/project/deployment/PVC/immutable images;
3. create and verify an online SQLite backup and schema/comment counts;
4. server-dry-run the full Deployment replacement with `Recreate` and one replica;
5. deploy one immutable image;
6. verify 72 registry rows, 2 tests, 18 memberships, 15 distinct members, 3 dual members, 74-or-more comments, zero FK errors, DB integrity, API payload, badges, logs, readiness, and CERN SSO;
7. retain the old immutable image and pre-migration database backup for rollback.

Database restore is permitted only with every SQLite writer stopped and only as exceptional recovery, because restoring the pre-rollout backup discards comments created after backup. Normal rollback is **image-only**: pin the exact previous immutable web/proxy images while leaving the additive migrated DB in place.

Before production, executable rollback validation must:

1. clone the verified pre-rollout DB into a disposable file and migrate it with the candidate server/static manifest;
2. start the exact previous immutable web image against that migrated copy;
3. verify startup, health, pre-existing comment read, new comment write/read, unchanged pre-existing comments, and preserved 2/18/15/3 additive rows;
4. stop the old image, re-upgrade the same DB with the candidate image, and verify 2/18/15/3 and comment continuity again.

The release evidence records both immutable image digests, backup path/hash, old/new schema hashes, exact commands and assertions.
