# HANDOVER CURRENT — PICK PACK 1291

Status: **ACTIVE / cumulative / authoritative**  
Corrected baseline: **2026-08-19 — Beta22 supersession**  
Current published Beta baseline: **0.4.2-beta.22 / versionCode 28**  
Package: `vn.pickpack1291.app.beta.publicbeta`

> **CURRENT-BASELINE RULE:** Beta19/Beta20 references in older immutable handovers and historical release workflows remain valid historical evidence only. They are not the current release authority. Read current source and OTA evidence before citing the latest Beta.

> **RISKY-OPERATION STOP RULE:** Before any deploy, release, failback, DR, authority transition, production-data mutation, Stable action, or PR merge, re-fetch PR #38/branch HEAD and revalidate live Service authority, GAS discovery authority, D1 recovery state, Google fallback ledger, replication health, and current OTA metadata. If live state differs from this handover, do not force it to match; report and reconcile first.

## 1. Owner-approved production architecture — OWNER LOCK

Current architecture is:

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

with Cloudflare Worker production runtime; D1 normal-mode operational primary; Durable Objects + WebSocket/Hibernation realtime; Google Sheets operational replica/compatibility/fallback/DR; GAS discovery/compatibility/fallback bridge and Android OTA `update_check`; Android SQLite/cache local projection/offline; GitHub source/CI/release.

`ARCHITECTURE_GUARDRAILS.md` records the OWNER-approved 2026-08-18 supersession of the previous GAS-only architecture. `AGENTS.md` is now reconciled to this Service-first model. Do not regress production to GAS-only because an older handover describes that historical state.

No new backend/datastore/queue/auth/sync authority may be added without a new OWNER instruction. Do not introduce Supabase, Firebase, Neon/Postgres, Queue, KV, R2, or another authority by implementation convenience.

## 2. Current Android / OTA baseline — OWNER LOCK

Current Beta source and verified OTA baseline:

- versionName: `0.4.2-beta.22`
- versionCode: `28`
- package: `vn.pickpack1291.app.beta.publicbeta`
- verified OTA APK SHA-256: `da2c1c837102e9e557013971ece9dac961caa6312b579db9c63184acc8daed3b`
- verified OTA APK size: `9790372` bytes
- OTA path: `Android → GAS update_check → Google Drive channel folder`
- Beta/Stable channel isolation mandatory.

`.github/workflows/s22-beta21-ota-verify.yml` has a stale filename but current content/title verifies **Beta22**, including the Beta22 OTA roundtrip and Stable-unpublished guard. Do not infer Beta21 from the filename.

Historical Beta18→Beta19 and Beta20 release evidence remains historical. Active hardcoded Beta19/Beta20 publisher workflows have been retired to historical-only no-op workflows so they cannot accidentally republish obsolete APKs. Historical verification/evidence may remain read-only.

Stable remains **UNPUBLISHED / UNTOUCHED** unless the OWNER explicitly commands promotion. Android signing identity remains fixed and must never be replaced.

## 3. Last verified pre-failback authority snapshot — MUST REVALIDATE

The last successful Session1 live postcheck before the Beta19/Beta22 correction recorded:

### Service

- environment `production`
- generation `m2-prod-20260819-001`
- mode `SERVICE_PRIMARY`
- authority epoch `6`
- authority seq `3`
- scope `PRODUCTION`
- replication `HEALTHY`, pending `0`
- latest migration `0004_session1_foundation.sql`
- reconciling `0`
- epoch-7 fallback inbox in D1 `0`

Capabilities included `business_window = 7`, mutation batching, FCM wake, import engine, and realtime protocol `INVALIDATION_V1`.

### GAS / Google fallback

- GAS discovery mode `GOOGLE_FALLBACK`
- fallback authority epoch `7`
- authority seq `3`
- generation matched Service
- hidden fallback ledger had epoch-7 seq 1–3, exactly **3 PENDING events**
- all three pending events were produced by **0.4.2-beta.22**

No 7→8 failback/reconciliation had started when the OWNER paused on the stale-version discrepancy. Epoch 8 is only a planned controlled target after a fresh precondition gate; it is not permission to execute failback.

Never expose tokens/passwords/secrets or raw legacy sensitive fields from fallback rows. Do not rewrite historical fallback rows merely to sanitize them retroactively because event/checksum integrity must be preserved.

## 4. Recovery / failback safety

Preserve `/internal/recovery/failback-resume`, authentication fencing, authority epoch/generation split-brain protection, resumable begin/flush/complete/revert flow, sanitized new fallback payload persistence, checksum compatibility for sanitized recovery payloads, and the constant-time bridge-secret helper.

Before controlled failback, all of these must be true at one fresh checkpoint:

- Service exactly at expected pre-failback authority state;
- GAS exactly at expected fallback state;
- pending fallback count/sequence/generation explained and consistent;
- Service replication healthy;
- no reconcile lock active;
- D1 fallback inbox consistent;
- no concurrent mutating deploy/recovery workflow;
- Stable forbidden;
- PR #38 draft/unmerged;
- branch HEAD freshly re-fetched;
- Beta22 baseline/document/test reconciliation complete.

If any precondition differs, abort the risky transition and report the difference.

## 5. CI / current test contract

Historical successful Session1 evidence includes Service M2 Precutover, Session1 Apply Gate, Session1 Live Postcheck, Session1 Deploy Observer, Session1 Service E2E, App Fast Check, and Release Preflight at their recorded checkpoints.

Later legacy Chaos Matrix / Chaos V2 failures were stale-contract failures, not evidence that production Service was down. The old case 17 sent an ADMIN `M1_SHADOW_PROBE` and expected `BUSINESS_DATE_NOT_N_N_MINUS_1`; current runtime correctly rejects non-SUPERADMIN shadow probes first with `SHADOW_PROBE_SUPERADMIN_REQUIRED`.

Current runtime/test contract is preserved:

- ADMIN/USER business write window N/N-1;
- SUPERADMIN current PDA/service business window up to 7 current business dates;
- `M1_SHADOW_PROBE` SUPERADMIN-only;
- realtime protocol `INVALIDATION_V1` with `DAY_CHANGED`, not legacy `DELTA`.

Both Chaos workflows now apply a deterministic exact-marker current-contract patch before executing the isolated local matrix. Date-window assertions use legitimate business mutations and realtime assertions use `DAY_CHANGED / INVALIDATION_V1`; production runtime permissions were not weakened. Fresh CI evidence is required before calling corrected Chaos suites PASS.

## 6. Release Preflight — RECONCILED

Release Preflight is now Service-first aware:

- production authority health gate checks Worker `/health`, production environment, `SERVICE_PRIMARY`, `PRODUCTION`, and non-empty generation;
- GAS health is explicitly compatibility-only and checks Sheet read/auth/report/history compatibility markers;
- Beta/Stable Drive OTA channel isolation remains checked;
- Stable OTA is required to remain unpublished in the live gate;
- Android versionCode/versionName remain derived from `app/build.gradle.kts`;
- fixed signer validation remains;
- the workflow still does **not** publish to Google Drive.

A Release Preflight PASS must be interpreted as Service-first production health + GAS compatibility/OTA isolation + Android release validation, not as GAS/Sheets operational authority.

## 7. PWA / realtime / import

Production PWA is live on the Worker. Current realtime contract is `INVALIDATION_V1` with `DAY_CHANGED`; no reliance on the legacy realtime `DELTA` listener. Recovery route exists and is authentication-fenced.

Web import backend endpoints/engine exist, but end-user Web import UI has not been proven complete and must not be claimed complete without evidence.

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

- five persistent tabs exactly `Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`;
- preserve current owner-approved visual system;
- scanner flows trigger on hardware Enter/OK;
- no redundant `Kiểm tra` button for the same scan action;
- no protocol jargon in user UI;
- sync indicators remain semantically correct;
- Beta remains full-function for real acceptance;
- OTA remains GAS `update_check` → Drive channel folder;
- Beta/Stable channel isolation remains.

## 10. Owner workstation / security locks

- Never ask OWNER to run CMD, PowerShell, Terminal, adb, git, gh, Gradle, clasp, or another local CLI.
- Use CI/assistant-controlled tooling and browser/UI owner interactions.
- Never expose or commit plaintext passwords, verifier values, OAuth credentials, private tokens, signing material, bridge secrets, or sensitive historical auth payloads.
- Preserve mandatory rollback backup from the Service migration.

## 11. Beta22 formal acceptance status

Production fallback evidence proves real Beta22 device operations occurred, but this does **not** automatically prove every formal acceptance row.

Old current-baseline rows `real PDA Beta19 smoke` and `Web + Beta19 concurrent` are superseded. Reconstruct evidence for Beta22 and only mark PASS when evidence supports it. Run only genuinely missing acceptance tests.

Formal evidence/closure still needed:

- fresh corrected Chaos suites PASS;
- exact Beta22 PDA acceptance reconstruction;
- exact Web + Beta22 concurrent/realtime acceptance reconstruction;
- controlled failback/reconciliation after fresh precondition gate;
- DR both directions in safe recovery/staging;
- final replication/integrity verification;
- final production-complete handover.

## 12. GitHub / PR state

Repository `tam95supra-source/pick-pack-1291`; working branch `agent/service-migration-m2`; PR `#38`.

PR #38 title/body are corrected to the Beta22 Service-first baseline and must remain **draft / unmerged** until full Definition of Done and explicit OWNER approval. Always re-fetch current head before a material/risky operation.

## 13. Immutable history policy

Do not mass-replace or rewrite Beta19 from immutable historical snapshots. Keep old S12/S13 handovers as historical evidence of what was true at their closure. Newer current/supersession documents explicitly state that their old “latest Beta19” language is no longer current.

## 14. Current execution order

1. Let fresh CI validate the corrected Chaos / App / Service / Release Preflight contracts; inspect failures rather than weakening runtime rules.
2. Reconstruct formal Beta22 PDA/Web acceptance evidence and execute only genuinely missing tests.
3. Re-read live Service/GAS/D1/Google fallback state.
4. Only if every failback precondition matches, execute the controlled failback sequence.
5. Complete DR, final integrity verification, production-complete handover, and only then consider PR merge under explicit OWNER approval.

## 15. Current safety state

- Beta22 current; Beta19/Beta20 historical only.
- Service-first architecture authoritative.
- Version-neutral Service/D1/PWA/recovery work preserved.
- Active obsolete Beta19/Beta20 publisher paths retired.
- Release Preflight Service-first semantics reconciled.
- Corrected Chaos contracts submitted for fresh CI evidence.
- Stable unpublished/untouched.
- signer unchanged.
- production Sheet overwrite/delete forbidden.
- PR #38 unmerged.
- no failback authorized merely by this document.
