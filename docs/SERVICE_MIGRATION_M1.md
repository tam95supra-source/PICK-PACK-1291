# PICK PACK 1291 — Service Migration M1 Design / Operations

Status: **M1 STAGING/SHADOW ONLY — no production cutover**

## Scope

This implementation is the backend half of the OWNER-approved Service-first migration. It intentionally stops before Android/Web production cutover, GAS fallback authority changes, Stable publication, OTA migration or signer changes.

Normal M1 shadow flow:

`Test Client → Worker API → D1 transaction → Durable Object realtime`

and asynchronously:

`D1 transaction → sheet_replication_outbox → Sheets API → Google staging copy`

The production workbook is used only as bootstrap/read input in M1.

## Provider boundaries

The implementation keeps business semantics separated from provider mechanics:

- `src/core.ts` — provider-neutral business mutation/state rules expressed through the storage contract;
- `src/realtime.ts` — Durable Object/WebSocket adapter;
- `src/replication.ts` — Google Sheet adapter with OAuth token exchange, schema guard, idempotent append/checkpoint/retry;
- `src/auth.ts` — auth/session adapter compatible with current challenge/HMAC + single-active-device behavior;
- `src/bootstrap.ts` — recovery/bootstrap importer from the existing Google workbook.

A future provider can replace storage/realtime/sheet implementations without changing the canonical mutation semantics.

## Canonical contract

Contract schemas:

- `service/schemas/canonical-event.v1.schema.json`
- `service/schemas/api-result.v1.schema.json`
- `service/schemas/google-sheet-manifest.v1.json`

Canonical event semantics include immutable event/idempotency identity, entity/version identity, business date, authority epoch/sequence, service generation, actor/device provenance, occurred/committed time, payload, schema version and checksum.

## D1 schema

Migration: `service/migrations/0001_m1_foundation.sql`

Key structures:

- `events` — immutable canonical ledger;
- `attendance_sessions`, `labor_sessions` — operational projections;
- `resources`, `resource_pack_map`, `resource_leases`, `resource_daily_consumption` — exclusive resources and daily consumption;
- `employees`, `catalog_values`, `accounts` — master/auth projections;
- `authority_state`, `business_dates`, `sync_checkpoints`, `system_meta` — authority/revision metadata;
- `conflicts` — explicit conflict ledger;
- `sheet_replication_outbox`, `replication_status` — transactional replication and checkpoints;
- `bootstrap_runs`, `source_rows`, `dr_checksums` — source reconciliation/DR metadata;
- auth challenge/session and realtime-ticket tables.

Migration is versioned and reproducible. `schema_migrations` records version `0001_m1_foundation` and a repository migration checksum. Recovery from an empty D1 is `create database → apply migrations → bootstrap current Sheet → finalize checksums/projections`.

M1 does not define a destructive down-migration because the safe rollback is to leave the shadow Service unused and return to the pre-existing production GAS/Sheet path. The mandatory pre-migration Drive/Git backup remains the production rollback point.

## Bootstrap from the real workbook

Source is the existing workbook named exactly `DỮ LIỆU THEO NGÀY`. The importer validates exact tab order and exact headers for:

1. `Danh mục`
2. `LỊCH SỬ NGHIỆP VỤ`
3. `DANH SÁCH PDA`
4. `DANH SÁCH USER PICK`
5. `DANH SÁCH BÀN PACK`
6. `DANH SÁCH USER PACK`
7. `DANH SÁCH NHÂN SỰ`
8. `RA - VÀO TRONG CA`
9. `CÔNG NHẬT`
10. `Danh sách Admin`

Each non-empty source row is normalized only for deterministic transport (fixed header width), hashed with SHA-256, stored with its original row index and reconciled by per-sheet row count + ordered row-hash aggregate checksum. Catalog/select display values are preserved exactly.

Bootstrap never writes to the source workbook. It is safe to run again: imported projections/source rows are rebuilt from the same source and the second reconciliation must match the first.

Password verifier values are imported only into the private D1 auth projection for compatibility and are never returned by public read APIs, committed to Git, or placed in evidence artifacts.

## Business rules enforced in M1

- business-date edit authorization uses the newest two **business session sequence** values, not calendar age;
- USER/ADMIN restricted to `{n,n-1}`; SUPERADMIN bypasses that time window only;
- exact event/idempotency replay returns the original committed result;
- base versions protect stale updates;
- unique resource leases + transaction assertions make exclusive assignment/change race-safe;
- PICK requires an available PDA, User Pick optional;
- PACK validates Bàn Pack → shift/User Pack mapping and availability;
- daily User Pick/User Pack consumption blocks cross-employee reuse;
- OPEN Công nhật blocks attendance EXIT;
- USER cannot operate Công nhật;
- fixed-position Công nhật deduction behavior remains compatible;
- auth challenge/proof uses PBKDF2-derived verifier key and HMAC challenge proof;
- login replacement enforces `SINGLE_ACTIVE_DEVICE_V1`.

## Realtime

`RealtimeHub` is a Durable Object using WebSocket Hibernation. Clients receive small `DELTA` notifications after durable D1 commit. Reconnect correctness is provided by `/v1/delta?since_seq=...`; the socket is not the source of correctness.

## Google staging replication

The D1 mutation transaction writes an outbox row before ACK. Replication is outside the mutation critical path.

The Sheet adapter:

1. exchanges the existing Google OAuth refresh credential for a short-lived access token;
2. targets only the configured staging workbook ID;
3. creates a hidden technical tab `__M1_SERVICE_REPLICA` if absent;
4. verifies its exact 20-column canonical header before writing;
5. deduplicates by `event_id`;
6. appends a micro-batch;
7. advances the D1 replication checkpoint;
8. marks outbox rows `SYNCED` only after the Google call succeeds;
9. moves temporary failures to `RETRY` with backoff;
10. moves schema drift to `PAUSED_SCHEMA` rather than guessing column positions.

Google failure therefore never reverses an already durable Service mutation.

## API surface

Public/unprotected:

- `GET /health`
- `GET /v1/capabilities`
- `GET /v1/discovery`
- `POST /v1/auth/challenge`
- `POST /v1/auth/session`
- `GET /v1/realtime?ticket=...` (WebSocket upgrade with short-lived one-use ticket)

Authenticated:

- `POST /v1/auth/logout`
- `POST /v1/realtime/ticket`
- `GET /v1/employees`
- `GET /v1/catalog`
- `GET /v1/resources`
- `GET /v1/operational?business_date=YYYY-MM-DD`
- `GET /v1/delta?since_seq=N`
- `GET /v1/bootstrap`
- `GET /v1/sync/manifest`
- `GET /v1/conflicts`
- `GET /v1/diagnostics` (SUPERADMIN)
- `GET /v1/recovery/status` (SUPERADMIN)
- `POST /v1/mutations`

CI-only M1 internal endpoints under `/internal/*` require the `M1_ADMIN_TOKEN` secret. They exist only to perform bootstrap, deterministic failure injection and acceptance evidence; they are not an end-user API.

## Error / conflict semantics

All errors use an explicit `error_class` such as `VALIDATION`, `AUTH`, `PERMISSION`, `CONFLICT`, `RESOURCE`, `TRANSIENT`, `INTEGRITY`, `SCHEMA`, `INTERNAL`, plus a `retryable` flag. Version/resource conflicts are not silently last-write-wins.

## Dynamic discovery

`GET /v1/discovery` returns service URL, generation, authority epoch, schema version and capabilities location. M1 marks the environment `staging-shadow` and explicitly states `production_authority_unchanged=true`. Android/Web integration of this discovery contract belongs to M2.

## CI deployment and acceptance

Workflow: `.github/workflows/service-m1-staging.yml`

It performs, without OWNER local CLI:

- credential-name preflight;
- Google source read-access/schema preflight;
- Wrangler type generation + TypeScript check;
- staging D1 resolve/create and migration;
- empty local D1-state migration proof plus remote staging migration;
- first Worker deploy with runtime-only encrypted secrets;
- real workbook bootstrap pass A;
- real workbook re-bootstrap pass B and reconciliation comparison;
- auth/session, duplicate event, idempotency-key replay, stale version, race, simultaneous mutation, Công nhật/EXIT, realtime two-client, reconnect/delta, Google normal replication, temporary failure/retry, retention and n/n-1 tests;
- staging Sheet canonical technical-tab verification;
- safe evidence artifact upload.

The workflow never runs on `main`; it is scoped to the M1 working branch and does not publish APK/Stable or deploy GAS.

## Required secret names

Values must never be documented or committed. M1 CI/deployment expects these existing GitHub/Cloudflare secret names:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`

Worker runtime secret names:

- `SERVICE_TOKEN_SECRET`
- `M1_ADMIN_TOKEN`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GOOGLE_STAGING_SHEET_ID`

## Explicit M1 non-goals

M1 does not:

- redirect Android production/Beta18 to Service;
- change production authority epoch/path;
- disable/replace production GAS;
- implement Android Room/outbox/circuit breaker integration;
- publish or cut over Web/PWA production;
- implement production failover/failback/GAS authority transitions;
- publish Stable;
- change Android signer;
- overwrite the production workbook.

Those are M2 tasks after M1 is proven PASS.
