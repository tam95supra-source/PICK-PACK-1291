# SERVICE MIGRATION M2 — PRECUTOVER ARCHITECTURE

## Status semantics

This document describes the M2 implementation on `agent/service-migration-m2`.
It is **not** a production-cutover completion certificate. Production authority, Stable release, Android signer, and the mandatory pre-migration rollback point remain owner-locked.

## Target topology

```text
Android Beta/Stable ----\
                        +--> Service Worker --> D1 canonical event ledger + projections
Web/PWA ----------------/          |
                                   +--> Durable Object / WebSocket realtime
                                   |
                                   +--> transactional sheet_replication_outbox
                                              |
                                              v
                                      Google staging replica

GAS production API --> discovery + legacy bridge + controlled GOOGLE_FALLBACK
```

Service/D1 is the intended canonical authority after cutover. Google Sheets remains operational replica, controlled fallback and DR surface; it is not a concurrent writer while Service is primary.

## M2 source components

### Service

- `service/src/entry.ts` — M2 boundary, S15 compatibility sync, recovery/write fencing and DR routes.
- `service/src/index.ts` — auth, canonical mutation, delta, realtime, bootstrap, replication and authority APIs.
- `service/src/core.ts` — canonical event commit, idempotency, optimistic versioning, resource leases and business-date authorization.
- `service/src/integrity.ts` — resource availability and PACK table/shift/user mapping validation.
- `service/src/legacy.ts` — Android/GAS legacy action to canonical event adapter.
- `service/src/compat.ts` — D1 projections rendered in the existing Android S15 `sync_status/sync_day/sync_bootstrap` shape.
- `service/src/recovery.ts` — fallback-ledger verification and fenced failback replay.
- `service/src/dr.ts` — D1 to Google **staging** full workbook rebuild with a hard production-target fence.
- `service/src/replication.ts` — transactional-outbox Google staging replication.
- `service/src/realtime.ts` — Durable Object WebSocket Hibernation hub.

### D1

`0002_m2_authority_recovery.sql` adds authority transition audit, fallback inbox, recovery runs, client devices, DR manifests and health samples. M1 tables and the immutable canonical event ledger remain the base schema.

### Android

- The Worker URL is **not compiled into the APK**.
- GAS `service_discovery` supplies dynamic authority and Service URL.
- `M2ServiceTransport` uses Service when discovery says `SERVICE_PRIMARY`; otherwise the proven GAS path remains available.
- PBKDF2/HMAC Service login runs in parallel with legacy login during migration.
- `OperationalDataStore` database upgrade is additive; Beta18 45-day day snapshots are not dropped.
- Canonical mutation outbox survives process death.
- WorkManager replays when the network returns.
- Exclusive-resource offline operations are marked `OFFLINE_PROVISIONAL` until server confirmation.
- Foreground realtime uses WebSocket; polling remains reconnect/fallback protection.
- Existing S15 renderer/cache consumes D1 through the compatibility sync contract.

### Web/PWA

The Service Worker-hosted PWA uses the same Service/D1 authority as Android. It implements PBKDF2/HMAC login, IndexedDB cache/outbox, offline replay, conflict surfacing, realtime reconnect, five operational navigation tabs, attendance/labor operations and staff search. PWA shell caching never becomes business-data authority.

### GAS fallback

`SERVICE_MIGRATION_M2.gs` and the M2 routing patch implement:

- public Service discovery;
- `SERVICE_PRIMARY`, `GOOGLE_FALLBACK`, `RECONCILING`, `OFFLINE_LOCAL` modes;
- Service bridge for legacy Android mutations while Service is primary;
- automatic failover claim after bounded Service failures;
- hidden `__PP_M2_FALLBACK_EVENTS` ledger with `(authority_epoch, authority_seq)` and SHA-256 checksum;
- no mutation acceptance while `RECONCILING`;
- SUPERADMIN-confirmed reconcile/failback control routes.

## Authority and fencing protocol

Every canonical Service event carries `authority_epoch`, monotonic `authority_seq` within the epoch, and `service_generation`.

### Service primary

Only the current Service epoch/generation accepts Service writes. Stale epoch or generation is rejected.

### Failover

When GAS owns fallback, it increments the authority epoch and starts fallback sequence from 1. Fallback events are appended to the hidden fallback ledger. The Service may stage only the **immediately next** fallback epoch while its old D1 authority is still present; event-id and sequence collisions are rejected.

### Failback

1. SUPERADMIN + owner confirmation changes GAS from `GOOGLE_FALLBACK` to `RECONCILING`.
2. GAS stops accepting operational writes.
3. All fallback ledger rows are staged into D1 fallback inbox.
4. Service recovery verifies contiguous sequence and checksum.
5. A D1 reconciliation lock blocks public Service mutations.
6. Fallback events replay through the legacy-to-canonical adapter and canonical Business Core.
7. Service verifies epoch/sequence/event counts.
8. Service advances to a fresh epoch/generation and clears the D1 reconciliation lock.
9. GAS may switch back to `SERVICE_PRIMARY` only after no fallback row is pending and it receives the fresh Service epoch/generation.

This prevents both authorities from being legitimate writers at the same time.

## DR paths

### Google production source -> D1

M1/M2 bootstrap reads the existing production workbook as the bootstrap source. Source title, 10 tabs and headers are verified. Shadow bootstrap is read-only against the production workbook.

### D1 -> Google staging

`/internal/dr/rebuild-google-staging` reconstructs the 10 visible workbook tabs from D1 projections/event history. The code aborts if `GOOGLE_STAGING_SHEET_ID == GOOGLE_SOURCE_SHEET_ID`, so this path cannot be used to overwrite the production bootstrap source during precutover.

Each recovery run records status and validation metadata.

## Local/CI gates

- `Service M2 Precutover`: PWA syntax, strict Worker typecheck, empty-D1 migrations, architecture guards.
- `App Fast Check`: static safety guards plus BetaDebug and StableDebug build.
- `Service M2 Chaos Matrix V2`: isolated Wrangler Worker + local D1, seeded test data, auth/session, n/n-1, idempotency, optimistic versioning, resource race, labor constraints, delta, two-client realtime, authority fencing, fallback ingest, failback, DR fence and Google-failure/off-critical-path behavior.
- `GAS M2 Source Sync`: non-deploying source materialization and syntax validation. It does **not** deploy production GAS.

## Production locks before live cutover

Until live M2 gates pass:

- do not merge PR #38 into `main`;
- do not change production authority;
- do not deploy M2 GAS to production merely because source CI is green;
- do not publish Stable;
- do not change the Android signer;
- do not reset or overwrite the production workbook;
- do not remove `PICK_PACK_1291_PRE_SERVICE_MIGRATION_BACKUP_2026-08-18_2318`.

## Live gates still required

A source-precutover result is insufficient for completion. M2 completion additionally requires authenticated Cloudflare deployment, remote D1 migration, real production-Sheet read-only bootstrap/reconciliation, live Worker/DO/WebSocket tests, real Google staging replication/retry, controlled authority cutover, failover/failback proof, signed Beta OTA verification and the full owner-specified acceptance matrix. Stable remains unpublished unless separately owner-authorized.
