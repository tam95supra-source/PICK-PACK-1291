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

with:

- Cloudflare Worker = production API/runtime;
- Cloudflare D1 = normal-mode operational primary datastore;
- Durable Objects + WebSocket/Hibernation = realtime coordination/fanout;
- Google Sheets = operational replica/compatibility/fallback/DR according to authority state;
- GAS = discovery/compatibility/fallback bridge and Android OTA `update_check` path;
- Android SQLite/cache = local projection/offline state;
- GitHub = source/CI/release infrastructure.

`ARCHITECTURE_GUARDRAILS.md` records the OWNER-approved 2026-08-18 supersession of the previous GAS-only architecture. `AGENTS.md` has now been reconciled to this Service-first model. Do not regress production to GAS-only because an older handover describes that historical state.

No new backend/datastore/queue/auth/sync authority may be added without a new OWNER instruction. Do not introduce Supabase, Firebase, Neon/Postgres, Queue, KV, R2, or another authority by implementation convenience.

## 2. Current Android / OTA baseline — OWNER LOCK

Current Beta source and verified OTA baseline:

- versionName: `0.4.2-beta.22`
- versionCode: `28`
- package: `vn.pickpack1291.app.beta.publicbeta`
- verified OTA APK SHA-256: `da2c1c837102e9e557013971ece9dac961caa6312b579db9c63184acc8daed3b`
- verified OTA APK size: `9790372` bytes
- OTA path: `Android → GAS update_check → Google Drive channel folder`
- Beta/Stable channel isolation remains mandatory.

`.github/workflows/s22-beta21-ota-verify.yml` has a stale filename but current content/title verifies **Beta22**, including the Beta22 OTA roundtrip and Stable-unpublished guard. Do not infer Beta21 from the filename.

Historical Beta18→Beta19 and Beta20 release evidence remains historical. Old Beta19/Beta20 publisher workflows have been retired to historical-only no-op workflows so they cannot accidentally republish an obsolete APK.

Stable remains **UNPUBLISHED / UNTOUCHED** unless the OWNER explicitly commands promotion. Android signing identity remains fixed and must never be replaced.

## 3. Last verified pre-failback authority snapshot — MUST REVALIDATE

The last successful Session1 live postcheck before the Beta19/Beta22 correction recorded:

### Service

- environment: `production`
- generation: `m2-prod-20260819-001`
- mode: `SERVICE_PRIMARY`
- authority epoch: `6`
- authority seq: `3`
- scope: `PRODUCTION`
- replication: `HEALTHY`
- replication pending: `0`
- latest applied migration: `0004_session1_foundation.sql`
- reconciling flag: `0`
- epoch-7 fallback inbox in D1: `0`

Capabilities at that checkpoint included `business_window = 7`, mutation batching, FCM wake, import engine, and realtime protocol `INVALIDATION_V1`.

### GAS / Google fallback

- GAS discovery mode: `GOOGLE_FALLBACK`
- fallback authority epoch: `7`
- authority seq: `3`
- generation matched Service
- production hidden fallback ledger had epoch-7 seq 1–3, exactly **3 PENDING events**
- all three current pending events were produced by **0.4.2-beta.22**

No 7→8 failback/reconciliation had started when the owner paused on the stale-version discrepancy. Epoch 8 is only a planned controlled target after a fresh precondition gate; it is not permission to execute failback.

Never expose tokens/passwords/secrets or raw legacy sensitive fields from fallback rows. Do not rewrite historical fallback rows merely to sanitize them retroactively because event/checksum integrity must be preserved.

## 4. Current recovery / failback safety

Keep the existing recovery/failback implementation and fencing, including:

- `/internal/recovery/failback-resume` authentication fence;
- authority epoch/generation split-brain protection;
- resumable begin/flush/complete/revert flow;
- sanitized new fallback payload persistence;
- checksum compatibility for sanitized recovery payloads;
- constant-time bridge-secret comparison helper.

Before controlled failback, all of these must be true at one fresh checkpoint:

- Service is exactly at the expected pre-failback authority state;
- GAS is exactly at the expected fallback state;
- pending fallback count/sequence/generation are explained and consistent;
- Service replication is healthy;
- no reconcile lock is active;
- D1 fallback inbox is consistent;
- no concurrent mutating deploy/recovery workflow is active;
- Stable remains forbidden;
- PR #38 remains draft/unmerged;
- branch HEAD is freshly re-fetched;
- Beta22 baseline/document/test reconciliation is complete.

If any precondition differs, abort the risky transition and report the difference.

## 5. CI / test contract status

Historical successful Session1 evidence before this correction included:

- Service M2 Precutover — PASS
- Session1 Apply Gate — PASS
- Session1 Live Postcheck — PASS
- Session1 Deploy Observer — PASS
- Session1 Service E2E — PASS
- App Fast Check — PASS
- Release Preflight — PASS at that historical checkpoint

The later legacy Chaos Matrix and Chaos Matrix V2 runs failed at old contract semantics rather than a production outage. Known stale failure: case 17 used an ADMIN `M1_SHADOW_PROBE` and expected `BUSINESS_DATE_NOT_N_N_MINUS_1`; current runtime correctly rejects non-SUPERADMIN shadow probes first with `SHADOW_PROBE_SUPERADMIN_REQUIRED`.

Current runtime rule is preserved:

- ADMIN/USER write window: N/N-1;
- SUPERADMIN PDA/service business window: up to 7 current business dates under current rules;
- `M1_SHADOW_PROBE`: SUPERADMIN-only;
- realtime push protocol: `INVALIDATION_V1` with `DAY_CHANGED`, not the legacy `DELTA` listener.

Both Chaos workflows now apply a deterministic current-contract patch before executing the local isolated test matrix. The patch changes date-window tests to use legitimate business mutations and changes realtime assertions to `DAY_CHANGED / INVALIDATION_V1`; it does **not** weaken production runtime permissions to make an old test pass. Fresh CI evidence is required before calling the corrected Chaos suites PASS.

## 6. Release Preflight interpretation

Release Preflight correctly derives Android versionCode/versionName from `app/build.gradle.kts`, preserves the fixed signer checks, and does not itself publish to Drive.

Its GAS live-gate wording/assertions still carry historical compatibility markers such as `APP_GSHEET`, S12 report-engine and S13 history-engine labels. Treat those as compatibility-layer checks, **not** as architecture authority. The live gate must be reconciled to explicitly validate Service-first production plus GAS compatibility/OTA isolation before final release acceptance.

## 7. PWA / realtime

Production PWA is live on the Worker. Current realtime contract is:

- protocol `INVALIDATION_V1`;
- invalidation event `DAY_CHANGED`;
- no reliance on legacy realtime `DELTA` listener.

The recovery route exists and is authentication-fenced. Web import backend endpoints/engine exist, but end-user Web import UI has not been proven complete and must not be claimed complete without evidence.

## 8. Business invariants — OWNER LOCK

- MNV remains the business key.
- Attendance session remains `MNV + business_date`.
- Attendance state remains `NOT_ENTERED → ACTIVE → ENDED`.
- Canonical event IDs are immutable/idempotent.
- Stale-version conflicts are rejected; do not use last-write-wins.
- Exclusive resource ownership is race-safe.
- PICK requires PDA; User Pick optional where currently allowed.
- PACK mapping remains controlled and supports legitimate one-to-many mapping.
- OPEN Công nhật blocks EXIT.
- Roles remain `SUPERADMIN / ADMIN / USER` with backend enforcement.
- Normal account creation cannot create another SUPERADMIN without explicit OWNER approval.
- Authentication remains PBKDF2-HMAC-SHA256 challenge/proof compatible.
- Session model remains `SINGLE_ACTIVE_DEVICE_V1`.

Production Google data must not be renamed/reset/regenerated/overwritten/deleted as a migration shortcut. Catalog/select values come from project catalogs only.

## 9. UI / client locks — OWNER LOCK

- persistent five tabs exactly: `Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`;
- preserve current owner-approved visual system;
- scanner flows trigger on hardware Enter/OK;
- do not add redundant `Kiểm tra` button for the same scan action;
- no protocol jargon in user-facing UI;
- sync indicators remain semantically correct;
- Beta remains full-function for real acceptance testing;
- OTA remains GAS `update_check` → Drive channel folder;
- Beta/Stable channel isolation remains.

## 10. Owner workstation / security locks

- Never ask the OWNER to run CMD, PowerShell, Terminal, adb, git, gh, Gradle, clasp, or another local CLI.
- Use CI/assistant-controlled tooling and browser/UI owner interactions.
- Never commit or expose plaintext passwords, verifier values, OAuth credentials, private tokens, signing material, bridge secrets, or sensitive historical auth payloads.
- Preserve mandatory rollback backup from the Service migration.

## 11. Beta22 formal acceptance status

Production fallback evidence proves real Beta22 device operations occurred, but this does **not** automatically prove every formal acceptance row.

The old current-baseline rows `real PDA Beta19 smoke` and `Web + Beta19 concurrent` are superseded. Reconstruct evidence for Beta22 and only mark a row PASS when evidence supports it. Run only genuinely missing acceptance tests; do not repeat tests blindly.

Formal work still requiring evidence/closure includes:

- corrected Chaos suites fresh PASS;
- exact Beta22 PDA acceptance matrix reconstruction;
- exact Web + Beta22 concurrent/realtime acceptance reconstruction;
- controlled failback/reconciliation only after fresh precondition gate;
- DR both directions in safe recovery/staging paths;
- final replication/integrity verification;
- final production-complete handover.

## 12. GitHub / PR state

Repository: `tam95supra-source/pick-pack-1291`  
Working branch: `agent/service-migration-m2`  
PR: `#38`

PR #38 must remain **draft / unmerged** until full Definition of Done and explicit OWNER approval. Re-fetch its head before every material/risky operation because documentation and CI cleanup commits move the branch head.

The stale PR title/body that described Beta19 as current must be corrected to Beta22; historical Beta19 milestones may remain explicitly labeled historical.

## 13. Immutable history policy

Do not mass-replace or rewrite Beta19 from immutable historical snapshots. Keep old S12/S13 handovers as historical evidence of what was true at their closure. Newer current/supersession documents must clearly state that their “latest Beta19” language is no longer current.

## 14. Next execution order

1. Finish current documentation/PR/version reconciliation.
2. Finish old publisher retirement and Release Preflight architecture wording/gate reconciliation.
3. Obtain fresh CI evidence for the corrected test contract.
4. Reconstruct formal Beta22 device/Web acceptance evidence.
5. Re-read live Service/GAS/D1/Google fallback state.
6. Only if every failback precondition matches, execute the controlled failback sequence.
7. Complete DR, final integrity verification, production-complete handover, and only then consider PR merge under explicit OWNER approval.

## 15. Current close guard

At this corrected baseline:

- Beta22 is current; Beta19/Beta20 are historical only;
- Service-first architecture is authoritative;
- version-neutral Service/D1/PWA/recovery work is preserved;
- Stable remains unpublished/untouched;
- signer remains unchanged;
- production Sheet overwrite/delete remains forbidden;
- PR #38 remains unmerged;
- no failback is authorized merely by this document.
