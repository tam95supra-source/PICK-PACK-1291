# HANDOVER CURRENT — PICK PACK 1291

Status: **ACTIVE / cumulative / authoritative**  
Current baseline: **2026-08-19 — Beta25 cache-first + production Web session isolation**  
Current published Beta: **0.4.2-beta.25 / versionCode 31**  
Package: `vn.pickpack1291.app.beta.publicbeta`

Newest immutable checkpoint: `docs/HANDOVER_BETA25_CACHE_FIRST_WEB_SESSION_2026-08-19.md`.

> **CURRENT-BASELINE RULE:** Beta24/Beta23 and earlier release references are historical evidence only. Read current source, this file and current live OTA evidence before citing the latest Beta.

> **RISKY-OPERATION STOP RULE:** Before failback, DR, authority transition, production-data mutation, Stable action, signer action or PR merge, re-fetch PR #38/branch HEAD and revalidate live Service authority, GAS discovery authority, D1 recovery state, Google fallback ledger, replication health and OTA metadata. Never force live state to match a stale handover.

## 1. Owner-approved architecture — OWNER LOCK

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

with:

- D1 normal-mode operational primary;
- Durable Objects/WebSocket invalidation in foreground;
- Google Sheets operational replica / compatibility / fallback / DR;
- GAS discovery / compatibility / fallback / OTA bridge;
- Android SQLite/cache local projection;
- FCM only for Android background/closed wake/invalidation;
- GitHub source/CI/release tooling.

Firebase is not DB/Auth/Storage/business authority.

## 2. Current Beta25 release — OWNER LOCK

- versionName: `0.4.2-beta.25`
- versionCode: `31`
- package: `vn.pickpack1291.app.beta.publicbeta`
- APK: `pick-pack-1291-public-beta-0.4.2-beta.25.apk`
- size: `12810579` bytes
- SHA-256: `5ba70c6ed1c377c41a72f5f1bfe71b8accad6231a147c044614e66a585690aed`
- locked signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- candidate artifact id: `9367409356`
- Beta Drive APK id: `1YvFDNEZpNlCC3EcCm3uMR1WkY7YEzn0q`
- checksum: `SHA256SUMS-beta25.txt`
- checksum Drive id: `18uwHX3A3BwjBWd-j3_v4iNeX4iJeMptL`

Evidence:

- `ops/session2-beta25-build-candidate-result.txt` — config/build/sign PASS.
- `ops/session2-beta25-release-record.txt` — exact signed artifact publication record.
- `ops/session2-beta25-live-verify-result.txt` — GAS Beta25 discovery PASS, full public download/hash PASS, Web live PASS, Stable OTA EMPTY.

The generic GitHub Google OAuth refresh token does not have Drive scope. The first Beta25 publish workflow therefore stopped at SAFETY before upload; it did not create partial release files. The exact signed candidate was then uploaded through the connected Google Drive account, rechecked by live OTA download and recorded explicitly.

Stable remains **EMPTY / UNPUBLISHED / UNTOUCHED**. Signer remains fixed.

## 3. Fresh production authority checkpoint — MUST REVALIDATE BEFORE FAILBACK

Current live evidence `ops/session2-beta25-live-verify-result.txt`:

### Service

- `SERVICE_PRIMARY`
- epoch `6`
- seq `4`
- scope `PRODUCTION`
- generation `m2-prod-20260819-001`

### GAS / Google fallback

- `GOOGLE_FALLBACK`
- epoch `7`
- seq `5`
- generation `m2-prod-20260819-001`

### Read-only D1 safety

Fresh `ops/session2-d1-gate-diagnostic-result.txt` at 2026-08-19T13:40:21Z:

- production D1 resolved;
- Service authority still `SERVICE_PRIMARY|6|4|PRODUCTION|m2-prod-20260819-001`;
- epoch-7 D1 fallback inbox count `0`;
- replication `HEALTHY|0|0|`;
- no active reconciliation metadata row;
- diagnostic complete.

GAS seq advanced to 5 while D1 epoch-7 inbox remains 0. Do not infer that the new fallback event has already been flushed or reconciled. No 7→8 failback was executed by the Beta25 work.

## 4. Beta25 cache-first fixes

### Fallback cache hydration

Legacy GAS intentionally leaves `retention_floor` blank for older SQLite-recovery clients. Beta25 uses `server_retention_floor` as the compatibility fallback so the current client actually hydrates canonical day snapshots while `GOOGLE_FALLBACK` is active.

### Hot operational UI

Employee/session, labor and resource screens read local SQLite/master projection first. Network/revision sync is non-blocking revalidation and cache-miss recovery, not a prerequisite for normal hot rendering.

### ACK gap closure

S27 adds a projection-only view of newly confirmed events so UI does not regress between Service/GAS acknowledgement and arrival of the next canonical snapshot. Confirmed rows are not turned back into send candidates and are not resent.

### Shared History

History renders from the local canonical day snapshot and requests a background revision reconcile. Atomic snapshot updates re-render History/employee screens.

### Cache contract

PDA operational cache remains the exact canonical seven business sessions N..N-6. N/N-1 remain the hot mutation window under existing role rules; older retained dates obey read-only/role semantics.

## 5. Sync screen state

Beta25 Sync now shows the useful project/runtime detail needed for field diagnosis:

- network/validated Internet and measured latency;
- actual authority/route/provider;
- upload/download direction/rate state;
- pending and review/rejected local rows;
- local date count, hot N/N-1 and full N..N-6 window/revisions;
- master revision/staff count;
- generation/epoch/seq and Service URL presence;
- realtime mode;
- FCM registration state;
- last runtime error.

No normal constant foreground polling was introduced.

## 6. Web fixes / session model

Production Web v10 is live.

Fixed login overlay:

- production CSS forces `.login-wrap[hidden]`, `.admin-app[hidden]` and `.notice[hidden]` to `display:none!important`;
- live diagnostic verifies the current CSS and application source.

Session isolation:

- migration `0005_web_session_isolation.sql` is applied;
- PDA session slot remains `auth_sessions`;
- Web session slot is `auth_web_sessions`;
- Web sends `client_source='WEB'`;
- one PDA and one Web may remain active concurrently for the same login;
- a second Web replaces only the previous Web session;
- PDA/Web logout affects only its own session class.

This supersedes old wording that one session/login covered all client types.

Evidence:

- `ops/session2-product-deploy-v10-web-session-result.txt`
- `ops/session2-web-v10-live-diagnostic-result.txt`
- `ops/session2-post-v10-safety-diagnostic-result.txt`
- `ops/session2-beta25-live-verify-result.txt`

## 7. Realtime / fallback boundary — OWNER LOCK

Normal `SERVICE_PRIMARY`:

- foreground: `INVALIDATION_V1` WebSocket (`DAY_CHANGED`, `MASTER_CHANGED`) then authoritative delta/revision pull;
- background/closed Android: FCM invalidation then WorkManager catch-up;
- other PDAs converge through Service/D1.

Current GAS discovery is still `GOOGLE_FALLBACK`. Beta25 keeps the UI fast and cache-hydrated under fallback, but it does not bypass authority fencing or pretend fallback has Service-primary WebSocket realtime. Under fallback, cross-PDA freshness occurs on revision-sync triggers such as start/login/reconnect/manual/background work.

Do not enable Service-primary realtime by cheating the fence. A safe controlled return to Service authority requires real-client acceptance plus a fresh failback precondition checkpoint.

## 8. Role / business invariants — OWNER LOCK

- roles: `SUPERADMIN / ADMIN / USER`;
- MNV is business key; attendance session is `MNV + business_date`;
- attendance lifecycle `NOT_ENTERED → ACTIVE → ENDED`;
- ADMIN/USER current business write window N/N-1;
- USER/ADMIN N-2..N-6 read-only;
- SUPERADMIN PDA may mutate N..N-6 under existing rules;
- Web SUPERADMIN may perform older historical corrections with audit semantics;
- immutable/idempotent events; no last-write-wins;
- stale-version conflicts rejected;
- exclusive resources race-safe;
- PICK requires PDA where defined; User Pick optional where allowed;
- PACK mapping follows project catalog/mapping rules;
- OPEN Công nhật blocks EXIT;
- normal account creation cannot create another SUPERADMIN without explicit owner approval;
- PBKDF2-HMAC-SHA256 challenge/proof compatibility preserved;
- one-active-PDA-slot and one-active-Web-slot are independent.

Production Google data must not be renamed/reset/regenerated/overwritten/deleted as a shortcut. Catalog/select values come only from project catalogs.

## 9. Firebase / FCM boundary

Approved Firebase client project remains `pick-pack-1291-fcm-20260819` for the Beta package. Production Worker has the `FCM_SERVICE_ACCOUNT_JSON` secret binding and FCM remains invalidation-only.

Physical Beta25 FCM wake delivery is **not proven by CI** and must not be fabricated.

## 10. Current physical acceptance still required

Still requires genuine PDA/Web field evidence on Beta25:

- employee + session context appears immediately from hydrated cache;
- enter/exit remains visually coherent through pending → confirmed → canonical snapshot;
- labor start/finish is immediate from local projection;
- shared History appears on both PDAs after sync;
- resource flow remains correct;
- same account can keep PDA + Web logged in concurrently;
- second Web login invalidates only the first Web;
- physical FCM background/closed wake delivery;
- after any later authorized failback, Service-primary cross-PDA WebSocket realtime.

Do not mark these PASS from CI alone.

## 11. GitHub / safety locks

Repository: `tam95supra-source/pick-pack-1291`  
Branch: `agent/service-migration-m2`  
PR: `#38`

- PR remains draft/open/unmerged.
- No merge without explicit OWNER approval.
- No Stable publish without explicit OWNER command.
- No Android signer change.
- No destructive production Sheet overwrite/delete/reset.
- Preserve rollback backup and fallback/checksum integrity.
- No secrets in repo/chat/docs.
- Never ask OWNER to run local CLI.
- No 7→8 failback until physical acceptance and fresh failback gates both pass.

## 12. Continuation order

1. Treat Beta25 as the current Beta baseline.
2. Owner performs real-PDA/Web acceptance against the defects that motivated Beta25.
3. Collect fresh logs only for remaining defects; fix forward in another Beta if necessary.
4. If physical acceptance passes, re-read Service/GAS/D1/Google fallback ledger/replication.
5. Only then consider controlled reconciliation/failback under existing OWNER rules.
6. Complete DR/final integrity closure.
7. Merge PR only after explicit OWNER approval.
