# HANDOVER CURRENT — PICK PACK 1291

Status: **ACTIVE / cumulative / authoritative**  
Current baseline: **2026-08-19 — Beta23 + production Web + FCM sender binding**  
Current published Beta: **0.4.2-beta.23 / versionCode 29**  
Package: `vn.pickpack1291.app.beta.publicbeta`

Newest immutable release checkpoint: `docs/HANDOVER_BETA23_WEB_FCM_2026-08-19.md`.

> **CURRENT-BASELINE RULE:** Beta22 and earlier release references remain historical evidence only. They are not the current release authority. Read current source, this file and live OTA evidence before citing the latest Beta.

> **RISKY-OPERATION STOP RULE:** Before any failback, DR, authority transition, production-data mutation, Stable action, signer action or PR merge, re-fetch PR #38/branch HEAD and revalidate live Service authority, GAS discovery authority, D1 recovery state, Google fallback ledger, replication health and OTA metadata. If live state differs, do not force it to match this handover.

## 1. Owner-approved production architecture — OWNER LOCK

Current architecture remains:

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

with:

- Cloudflare Worker production runtime;
- D1 normal-mode operational primary;
- Durable Objects + WebSocket/Hibernation realtime invalidation;
- Google Sheets operational replica / compatibility / fallback / DR;
- GAS discovery / compatibility / fallback bridge and Android OTA `update_check`;
- Android SQLite/cache local projection/offline state;
- GitHub source/CI/release tooling;
- Firebase used only for Android FCM wake/invalidation.

Firebase is **not** an auth/database/storage/business-data authority. No new backend/datastore/queue/auth/sync authority may be introduced without explicit OWNER instruction.

## 2. Current Android / OTA baseline — OWNER LOCK

Current published Beta:

- versionName: `0.4.2-beta.23`
- versionCode: `29`
- package: `vn.pickpack1291.app.beta.publicbeta`
- APK: `pick-pack-1291-public-beta-0.4.2-beta.23.apk`
- verified SHA-256: `ea561b034a78147cc3df35f6bc2ddef3f8850b812c3c872b58bf65153b4ca5c4`
- verified size: `12810579` bytes
- locked signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- Beta Drive file id: `1C3Odx5NbnBiyvIplFpDZq6r5O-ealtzV`
- checksum file: `SHA256SUMS-beta23.txt`
- checksum Drive file id: `1QW08lHELDz4AoCdBVnIXR7IDxStcXJWB`
- OTA path: `Android → GAS update_check → Google Drive Beta folder`.

Release evidence:

- `ops/session2-beta23-build-candidate-result.txt`: config/build/sign all PASS; package/version/signer verified; artifact id `9364146648`.
- uploaded APK was downloaded back from Google Drive and re-hashed byte-for-byte; SHA and size matched the signed candidate.
- `ops/session2-beta23-ota-live-verify-result.txt`: Beta23 discovery PASS, public download HTTP `206`, Stable discovery `EMPTY`.
- GAS `update_check` sets selected APK to `ANYONE_WITH_LINK / VIEW` when needed; Beta23 Drive metadata now has `anyone / reader` permission.

Stable remains **UNPUBLISHED / EMPTY / UNTOUCHED** unless OWNER explicitly commands promotion. Android signing identity remains fixed and must never be replaced.

## 3. Current production authority checkpoint — MUST REVALIDATE BEFORE FAILBACK

Fresh sanitized checkpoint recorded in `ops/session2-final-state-diagnostic-result.txt`:

### Service

- mode: `SERVICE_PRIMARY`
- authority epoch: `6`
- authority seq: `4`
- scope: `PRODUCTION`
- generation: `m2-prod-20260819-001`

### GAS / Google fallback

- mode: `GOOGLE_FALLBACK`
- authority epoch: `7`
- authority seq: `4`
- generation: `m2-prod-20260819-001`

### OTA / FCM

- Beta OTA: `0.4.2-beta.23`
- Beta OTA size/SHA matched the values in section 2.
- Stable OTA: `EMPTY`.
- Cloudflare `FCM_SERVICE_ACCOUNT_JSON` binding: `READY`.

The guarded V9 production deploy also revalidated D1/fallback safety and confirmed the fallback set remained unchanged after deployment.

Last explicit fallback data inspection before this checkpoint showed:

- Google hidden fallback ledger epoch 7 seq `1..4`, contiguous, all `PENDING`;
- D1 epoch-7 fallback inbox `0` rows;
- replication `HEALTHY`, pending `0`;
- no active reconcile lock.

No `7→8` failback has been executed or authorized by this document.

## 4. Firebase / FCM state

Approved Beta23 Firebase client project:

- project id: `pick-pack-1291-fcm-20260819`
- package: `vn.pickpack1291.app.beta.publicbeta`
- client configuration is stored in `app/google-services.json`.

Production Worker sender credential:

- Cloudflare secret name: `FCM_SERVICE_ACCOUNT_JSON`;
- value is not in GitHub/chat/docs and must remain secret;
- sanitized Cloudflare API diagnostic confirmed exactly one `secret_text` binding with that name;
- evidence: `ops/session2-fcm-secret-diagnostic-result.txt`.

Service implementation:

- `service/src/push.ts` reads the one-secret service-account JSON in memory;
- FCM is invalidation-only;
- canonical business events are deterministically staged into `push_outbox` as `DAY_CHANGED` from the durable event log;
- master imports enqueue `MASTER_CHANGED`;
- Android always pulls authoritative Service/D1 state after wake.

**Acceptance boundary:** secret presence, source support and production deployment are proven. A real Beta23 physical PDA obtaining an FCM token and receiving an actual FCM wake is **not yet proven** by CI/release evidence and must not be fabricated.

## 5. Production Web / Service state

Production Web/Admin is deployed on the Worker and has fresh guarded evidence.

`ops/session2-product-deploy-v9-result.txt` records:

- source/credentials PASS;
- D1 resolution PASS;
- Service authority gate PASS;
- Google fallback gate PASS;
- D1 safety gate PASS;
- Cloudflare deploy PASS;
- live Web/API verification PASS;
- fallback ledger recheck PASS;
- final verdict PASS.

Current Web target is the full admin/dashboard presentation with sidebar/topbar/KPIs/tables, role gates, import UI/backend integration and SUPERADMIN historical route. Realtime uses `INVALIDATION_V1`, `DAY_CHANGED` and `MASTER_CHANGED`.

Protected History/API behavior is authentication-fenced. A `307` to the protected history page when unauthenticated is not evidence that the page is missing; protected APIs correctly return `401` without auth.

## 6. Important corrected release/deploy defects

The following were tooling/gate defects corrected without weakening production safety:

1. `system_meta` uses `key/value`; old diagnostics queried nonexistent `meta_key/meta_value`.
2. D1 migrations `0001`–`0004` were already applied; an old gate queried later schema incorrectly.
3. Google fallback sheet uses `ingest_status`; an old gate expected `status`.
4. Wrangler runtime config under `/tmp` broke relative `src/entry_product.ts` resolution; runtime config is now generated inside `service/`.
5. GitHub Google OAuth refresh token has no Drive scope; OTA publication therefore uses the connected Google Drive path instead of pretending that token can upload.
6. Release candidate build uses Gradle `9.4.1` with Android SDK 36/build-tools 36.0.0; no Gradle wrapper is assumed.

These fixes do not authorize production-data rewrite, failback, Stable publication or signer changes.

## 7. Runtime / sync contract — OWNER LOCK

- ADMIN/USER business write window: N/N-1.
- SUPERADMIN current PDA/Service business window: exact seven Service business dates N..N-6; never calendar approximation.
- Web SUPERADMIN may query older history.
- realtime protocol: `INVALIDATION_V1` with `DAY_CHANGED` / `MASTER_CHANGED`; no legacy `DELTA`.
- WebSocket/FCM carry invalidation only; clients pull authoritative state.
- foreground has no interval polling; background periodic work is only a safety net.
- local-first Android writes must be durable local pending before network send and reconcile idempotently.
- fallback only when discovery says `GOOGLE_FALLBACK`; ordinary Service timeout is not automatic permission to fallback.
- PDA import remains SUPERADMIN-only with template/version/checksum validation, chunk <=500, preview + explicit commit, audit/revision/invalidation and correction-style rollback semantics.

## 8. Business invariants — OWNER LOCK

- MNV business key; session `MNV + business_date`.
- Attendance `NOT_ENTERED → ACTIVE → ENDED`.
- Immutable/idempotent event IDs and immutable canonical event history.
- Stale-version conflicts rejected; no last-write-wins.
- Exclusive resource ownership race-safe.
- PICK requires PDA; User Pick optional where allowed.
- PACK mapping controlled and supports legitimate one-to-many mapping.
- OPEN Công nhật blocks EXIT.
- Roles `SUPERADMIN / ADMIN / USER`; backend enforced.
- Normal account creation cannot create another SUPERADMIN without explicit OWNER approval.
- PBKDF2-HMAC-SHA256 challenge/proof compatibility preserved.
- `SINGLE_ACTIVE_DEVICE_V1` preserved.

Production Google data must not be renamed/reset/regenerated/overwritten/deleted as a shortcut. Catalog/select values come only from project catalogs.

## 9. UI / client locks — OWNER LOCK

Android keeps five persistent tabs exactly:

`Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`

Additional locks:

- preserve owner-approved visual system;
- scanner flows trigger on hardware Enter/OK;
- no redundant scan-check button;
- no protocol jargon in end-user UI;
- sync indicators remain semantically correct;
- Beta stays full-function for real acceptance;
- Beta/Stable OTA channel isolation remains mandatory.

## 10. Security / owner workstation locks

- Never ask OWNER to run CMD, PowerShell, Terminal, adb, git, gh, Gradle, clasp or another local CLI.
- Use CI/assistant-controlled tooling and browser/UI owner interactions.
- Never expose/commit passwords, verifier values, OAuth credentials, private tokens, Firebase service-account JSON, signing material, bridge secrets or sensitive historical auth payloads.
- Preserve the mandatory rollback backup from the Service migration.

## 11. Current acceptance status / remaining Definition of Done

Proven complete:

- Beta23 source version/package configuration;
- Beta23 build/sign/signer verification;
- Beta23 Drive roundtrip integrity;
- Beta23 GAS OTA discovery/public download;
- Stable-empty guard;
- production Web guarded deploy/live verification;
- FCM client configuration;
- production FCM secret binding presence;
- production Service support for one-secret Firebase sender credential;
- durable `DAY_CHANGED` staging and existing `MASTER_CHANGED` invalidation path.

Still **not proven** and must not be inferred:

- real physical Beta23 PDA FCM wake delivery;
- full real-PDA Beta23 business acceptance across genuinely required enter/exit/labor/resource rows;
- exact Web + Beta23 concurrent/realtime acceptance on real clients;
- controlled failback/reconciliation;
- DR both directions and final production integrity closure.

Therefore failback remains blocked until the missing real-client acceptance evidence exists and a new fresh precondition checkpoint matches.

## 12. GitHub / PR state

Repository: `tam95supra-source/pick-pack-1291`  
Branch: `agent/service-migration-m2`  
PR: `#38`

PR #38 must remain **draft / open / unmerged** until full Definition of Done and explicit OWNER approval. Always re-fetch current head before any material/risky operation.

## 13. Current continuation order

1. Treat Beta23 as the current release baseline; Beta22 and earlier are historical.
2. Obtain real physical Beta23 PDA acceptance, including actual FCM wake evidence and only genuinely missing business cases.
3. Run exact Web + Beta23 concurrent/realtime acceptance.
4. Re-fetch a fresh numbered Service/GAS/D1/Google fallback checkpoint.
5. Only if every failback precondition matches, execute controlled failback under existing OWNER rules.
6. Complete DR/final integrity closure.
7. Merge PR only after explicit OWNER approval.

## 14. Current safety state

- Beta23 current.
- production Web complete under guarded live verification.
- FCM sender binding present and deployed; physical wake acceptance still pending.
- Service-first architecture authoritative.
- Stable empty/unpublished/untouched.
- signer unchanged.
- production Sheet overwrite/delete forbidden.
- PR #38 draft/open/unmerged.
- no failback authorized merely by this handover.
