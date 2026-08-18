# HANDOVER CURRENT — PICK PACK 1291

Status: **ACTIVE / cumulative / authoritative**  
Last updated: **2026-08-19 06:40 +07:00 (Asia/Bangkok)**  
Closed working session: **S12**  
Next session: **S13**  
Latest published Beta: **0.4.2-beta.19 / versionCode 25**

> **NEW-CHAT STOP RULE:** S13 must first read this file, `docs/handovers/HANDOVER_S12_2026-08-19.md`, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/ADMIN_ACCOUNT_RULES.md`, `docs/BUILD_RELEASE_PLAYBOOK.md`, `docs/SERVICE_MIGRATION_M2.md` and `docs/HANDOVER_POLICY.md`. Then report that state is understood and **WAIT FOR A NEW OWNER COMMAND**. Do not publish Stable, merge PR #38, change authority, edit production data, or alter architecture merely because the session opened.

> **SUPERSEDED ARCHITECTURE NOTICE:** The S11 architecture `Android ↔ GAS ↔ Google Sheets` with Google Sheets as sole operational authority was deliberately superseded in S12 by the owner-approved M2 Service-first migration described below. Legacy GAS/Google behavior remains only for compatibility, operational replica, fallback and DR under M2 rules.

## 1. Project objective and current production architecture — OWNER LOCK

Pick Pack 1291 provides Android/PDA and Web/PWA operational workflows for personnel attendance, PICK/PACK resources, labor/Công nhật, reporting/history, admin and synchronization.

Current production architecture is:

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

with:

- Durable Objects + WebSocket/Hibernation for realtime coordination;
- Google Sheets as operational replica, compatibility layer, fallback and DR source/target under controlled M2 rules;
- Google Apps Script retained as legacy compatibility/discovery/fallback bridge, including Beta18 compatibility;
- GitHub as source/CI/release infrastructure;
- Android local SQLite/cache remains a projection/offline mechanism and is not an independent business authority.

Current authority state after cutover:

- environment: `production`
- authority scope: `PRODUCTION`
- authority mode: `SERVICE_PRIMARY`
- Service generation: `m2-prod-20260819-001`
- production Web/PWA: `https://pick-pack-1291-service.pp1291-d79b87776e86.workers.dev`
- Google replication final gate: `HEALTHY`, pending `0`

Stable promotion still requires explicit owner command.

## 2. Owner workstation constraint — OWNER LOCK

Owner's company-managed workstation cannot use local CLI.

Never ask owner to run CMD/PowerShell/Terminal/bash/git/gh/clasp/adb/Gradle/npm/npx/Java/keytool/OpenSSL or similar commands. Build/sign/deploy/release operations are handled by GitHub Actions or assistant-controlled tooling. Owner-facing setup should be browser/UI only.

## 3. Production Google data model and role after M2

Production workbook remains `DỮ LIỆU THEO NGÀY` with exactly these visible tabs:

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

M2 rules:

- D1 canonical events/state are Service-primary after cutover.
- Google operational projections remain required so legacy Beta18/GAS clients continue to function.
- Replication failures must not block the D1 critical mutation path; outbox retries are used.
- Google schema/header validation is mandatory before writes.
- Production Sheet must not be deleted/overwritten as a DR target.
- A mandatory pre-Service-migration rollback backup exists in Drive and must remain untouched.
- A separate Service shadow/staging workbook exists for technical replication/DR exercises.
- Public repo handovers must not expose unnecessary Drive IDs/URLs; internal Drive handover holds those details.

Catalog/select values must still come from the matching catalog namespace. Do not invent values outside project catalogs.

## 4. Data retention and correction window — OWNER LOCK

1. Only business date **N and N-1** may be corrected/changed.
2. Operational data is retained for a maximum of **45 days**.
3. N and N-1 remain mutable; older retained days are immutable operational history.
4. Service/backend authorization must enforce the correction window; Android/Web UI alone is insufficient.
5. Master catalogs/admin records are not subject to the same date-retention deletion rule.
6. Android/PDA must not eagerly cache all 45 days by default after M2: normal synchronization prioritizes N/N-1 and fetches older retained dates on demand while the Service itself maintains the full 45-day retention floor.

## 5. Business invariants — OWNER LOCK

- `MNV` is the business key.
- Session key: `MNV + business_date`.
- State machine: `NOT_ENTERED → ACTIVE → ENDED`.
- Once ENDED, normal flow cannot re-enter on the same business date.
- Mutations use immutable/idempotent `event_id`.
- Canonical events are immutable.
- Optimistic versions/stale-write rejection are enforced by Service.
- Exclusive resources are race-safe; one winner.
- Failed resource change retains the previous resource.
- OPEN Công nhật/labor blocks EXIT.
- EXIT releases currently owned resources.
- Authority epoch/generation fencing prevents split-brain and stale fallback ingestion.

### PICK

- requires PDA;
- User Pick optional;
- PDA search/entry uses validated last 5 serial digits;
- ambiguous duplicate 5-digit suffix cannot be accepted as unique;
- daily User Pick consumption remains used after release/change/EXIT unless authorized reuse exists.

### PACK

- Bàn Pack + mapped User Pack are controlled resources;
- multi-user pack mapping is supported where catalog data legitimately contains multiple user-pack mappings for one table/shift;
- daily User Pack consumption remains used after release/change/EXIT unless authorized reuse exists.

### ENTER / EXIT

- timezone: Asia/Bangkok;
- shifts: `Ca 1`, `Ca 2`, `HC`/`Ca HC` according route/UI mapping;
- work choice: `PICK | PACK | KHÔNG`;
- OPEN labor blocks EXIT.

### Công nhật

- USER/Điều phối cannot operate Công nhật;
- ADMIN/SUPERADMIN operate under correction-age permissions;
- lifecycle: `OPEN / COMPLETED / CANCELLED`;
- resource policy: `GIỮ / TRẢ`;
- accepted MNV immutable;
- OPEN Công nhật blocks EXIT.

## 6. Production-data anomaly discovered during M2 bootstrap

During real production bootstrap, `DANH SÁCH USER PACK` contained a duplicate `hy1.obpack18`: one valid mapping to `D18 / Ca 1-18` and another row referencing non-existent `D29`.

Resolution — **CHỐT**:

- do not rewrite production Sheet merely to make bootstrap pass;
- bootstrap/reconciliation keeps valid mapping(s);
- invalid `D29` row is reported as an anomaly instead of crashing import;
- resource-pack schema was expanded to preserve legitimate one-to-many mappings, including the HP case with multiple valid user-pack mappings in the same shift;
- migration `0003` implements the many-mapping model; verify exact filename on branch before code edits.

## 7. Authentication / roles / session — OWNER LOCK

Roles: SUPERADMIN, ADMIN, USER. Backend enforcement is mandatory.

Admin `Vị trí` values exactly: `superadmin`, `admin`, `user`.

Role mapping: SUPERADMIN → `superadmin`; ADMIN → `admin`; USER → `user`.

Normal account creation cannot create SUPERADMIN unless owner explicitly changes the rule.

Credential model:

- salted PBKDF2-HMAC-SHA256 verifier;
- challenge/HMAC login proof;
- plaintext password is not sent directly;
- never place passwords, verifiers, tokens, private keys or signing material in public repo or handover.

Session model remains **`SINGLE_ACTIVE_DEVICE_V1`**:

- persists across normal app/process close on same installation;
- another installation replaces the active server session for that account;
- old device is rejected on next protected request/sync;
- logout/password/security changes may invalidate.

## 8. Android local-first / offline model — CURRENT M2 RULE

Legacy S11 local-first SQLite behavior remains important, but transport authority changed to Service-primary.

Current M2 Android behavior:

- dynamic Service discovery through the stable GAS endpoint;
- Service-primary mutations while authority is Service-primary;
- durable offline outbox;
- WorkManager replay;
- foreground WebSocket realtime with reconnect;
- circuit breaker and GAS fallback when Service is unavailable/not authority;
- exclusive operations may be represented as `OFFLINE_PROVISIONAL` until authoritative replay;
- normal local sync keeps recent N/N-1 projections and fetches older retained dates on demand;
- vulnerable Beta15/Beta16 SQLite recovery guards must not be casually removed.

Historical incident preserved: Beta15/Beta16 had `SQLiteDatabaseLockedException / SQLITE_BUSY` crash loops on real Android 11 PDA. Beta17 fixed process-wide SQLite coordination, serialized DB access, non-UI-thread reconciliation and failure containment. Preserve those guards.

## 9. Realtime, fallback and failback — M2

- Service uses Durable Object realtime coordination and WebSocket reconnect behavior.
- Android and Web/PWA are expected to converge against the same authority state.
- GAS fallback is fenced; it must not become an uncontrolled competing authority.
- Failover/failback requires authority epoch/mode transitions and reconciliation, not merely URL switching.
- Beta18 compatibility must remain functional after Service cutover.

Production cutover already converged successfully: Service and GAS agree on `PRODUCTION / SERVICE_PRIMARY` and the same authority epoch at the final observer gate.

Controlled production failover/failback acceptance is still pending final project closure.

## 10. Shared history and reporting rules

Shared History remains operational MNV-session history, not device-local app history.

- one outer card per MNV/current business-date session;
- detailed session timeline includes ENTER/EXIT/resource/labor events;
- admin-account actions must not appear in MNV operational history;
- Google `LỊCH SỬ NGHIỆP VỤ` is an operational projection, not an independent canonical event authority after M2.

Report canonical manpower row order remains: Trưởng nhóm; Chuyên viên; Tổ trưởng; Điều phối khu pack; Điều phối khu chờ xuất; Kéo hàng; 5S; Picker; Packer; Phúc Long; Tổng.

Supplier order when present: `Inhouse, NLV, VW, MP, MGL, HGP, HAD, Tổng`.

Tenure matrices remain `Thâm niên Picker` and `Thâm niên Packer`, split ≤30 days / >30 days.

`Hỗ trợ bộ phận khác` only counts applicable Công nhật with `Khấu trừ nhân sự = Có`, de-duplicated per person/support type; hide block when zero.

Shift scopes remain `Ca 1 + Ca HC`, `Ca 2`, `Cả ngày`.

## 11. UI/UX current rules

Read `docs/UI_UX_SYSTEM.md` before visual changes.

Persistent bottom tabs exact order: `Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`.

Header target identity: `Chào buổi <sáng/trưa/chiều/tối>, <Họ tên>` using PDA local clock. Avoid API/revision/protocol jargon in user-facing chips.

Scan/search controls remain compact and hardware Enter/OK must trigger scanner actions.

Navigation fixes from Beta18 remain required: dual-edge swipe-back; tapping active parent bottom-tab resets child screen to tab root; explicit History Detail back returns to History root.

Sync direction semantics remain real runtime state, not decoration: `↑` outbound; `↓` download; `↕` concurrent; `✓` idle/ready.

## 12. Logging / diagnostics

Categories remain MANUAL → `BÁO LỖI THỦ CÔNG`; CRASH → `BÁO LỖI TỰ ĐỘNG`; DAILY → `NHẬT KÝ ANDROID`.

Manual report requires confirmation. Pending logs retry after valid session/connectivity. Local logs are deleted only after successful acknowledgement. Never expose secrets/private credentials in logs.

## 13. Web/PWA — PRODUCTION READY

Web/PWA is already live on the production Worker URL listed in section 1.

Implemented behavior includes same-origin Worker hosting, M2 authentication, IndexedDB local state/outbox, offline replay, realtime WebSocket reconnect and operational/admin UI.

Do not treat Web as merely mock/shadow. It is on the production Service path, but real owner/device acceptance of Web + Beta19 concurrent workflows remains pending final DoD.

## 14. OTA / signing / release — OWNER LOCK

OTA authority remains `Android → GAS update_check → Google Drive channel folder`.

Beta reads Beta channel only. Stable reads Stable channel only.

Fixed signing certificate SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`.

Never generate or substitute a signer.

Permanent signing secret names may be documented, never values: `ANDROID_SIGNING_KEY_B64`, `ANDROID_SIGNING_STORE_PASSWORD`, `ANDROID_SIGNING_KEY_PASSWORD`, `ANDROID_SIGNING_ALIAS`.

Latest published Beta:

- versionName: `0.4.2-beta.19`
- versionCode: `25`
- package: `vn.pickpack1291.app.beta.publicbeta`
- exact signed candidate SHA-256: `6dc47edba684249af0655a30573824911ee4a96482f86acf7f3995d6842c3103`
- fixed signer unchanged
- Beta18 → Beta19 OTA update check/download/package/version/SHA/signer verification: **PASS**

Stable remains **UNPUBLISHED / UNTOUCHED**. A Stable validation artifact is not permission to publish Stable.

## 15. S12 Service migration implementation — completed milestones

S12 completed:

1. Google OAuth scope issue resolved and required Google APIs enabled.
2. Cloudflare authentication verified.
3. Production D1 created and migrations applied.
4. Worker/PWA deployed and runtime health stabilized.
5. Google production bootstrap converted to resumable/chunked idempotent phases.
6. Production bootstrap completed against real 45-day dataset.
7. Resource mapping anomaly and one-to-many mapping issue fixed with migration/schema update.
8. Final bootstrap completed with no `RUNNING` state.
9. D1 → Google staging outbox replication live test passed; replication `HEALTHY`, pending `0`.
10. Mutating/redeploying verifier workflows retired/skipped before authority cutover to eliminate CI races.
11. Production Service authority promoted and GAS converged to `SERVICE_PRIMARY`.
12. Web/PWA production observer passed.
13. Beta19 signed candidate verified with fixed signer.
14. OTA publisher path repaired through failed iterations; final V5 publisher succeeded.
15. Final OTA observer passed complete Beta18 → Beta19 verification.
16. Stable channel remained untouched.

## 16. Verified CI/live gates at S12 close

Final relevant successful gates:

- `Service M2 Cutover Observer`
- `Service M2 Runtime Diagnostic`
- `Service M2 Chaos Matrix`
- `Service M2 Chaos Matrix V2`
- `Service M2 Precutover`
- `Release Preflight - Beta and Stable`
- `App Fast Check`
- `Service M2 Publisher V5 Run Observer`
- `Service M2 OTA Observer`

Historical publisher V1–V4 failures are debugging history only; V5 and final OTA observer are authoritative current release evidence.

Some bootstrap/replication/precutover workflows are intentionally retired/skipped after cutover to avoid unintended mutation/redeployment races. Intentional skips are not production failures.

## 17. GitHub state — DO NOT MERGE YET

Repository: `tam95supra-source/pick-pack-1291`.

M2 branch: `agent/service-migration-m2`.

PR #38 remains open, draft, unmerged, base `main`.

Implementation head immediately before S12 handover-document commits was `6b23b69d5ed5e3c4dc1fca2bbc2193426a015418`. S12 handover-document commits then moved branch head. Always re-fetch PR #38 before any modification or merge.

Do not merge PR #38 until full M2 Definition of Done passes.

## 18. Known process caveats / failures not to repeat

- Do not ask owner to use CLI.
- Do not publish Stable without explicit owner command.
- Do not generate a new signer.
- Do not overwrite/delete production Google Sheet.
- Do not re-enable retired mutating bootstrap/deploy workflows casually after cutover.
- Do not use the original buggy `Service M2 Live Web and Beta OTA` workflow for cutover.
- Do not embed huge code/publisher payloads directly inside workflow YAML; use source scripts.
- GitHub artifact downloads should use native GitHub tooling rather than brittle direct redirect handling.
- Google Apps Script deployments can propagate gradually; secured temporary publisher operations require readiness stabilization and idempotent chunk retry.
- `wrangler d1 execute` remote mode should not be assumed to accept explicit `BEGIN TRANSACTION` wrappers in verification scripts.
- Do not run monolithic full-Sheet bootstrap through one Worker HTTP request; use resumable/chunked bootstrap.
- Preserve Beta18 compatibility until explicitly retired after owner acceptance.
- Public repo handovers must remain public-safe: no plaintext secrets and no unnecessary private Drive identifiers.

## 19. Remaining work before full M2 Definition of Done

Web and OTA Beta19 are already live. Remaining work is acceptance/closure:

1. Real PDA smoke of Beta19: update, launch/login, Vào/Ra, Công nhật, PICK/PACK/resource change, no SQLite crash recurrence, offline→reconnect replay.
2. Real Web + Beta19 concurrent test against production Service/realtime.
3. Controlled Service-down/flapping failover to GAS fallback with split-brain fencing.
4. Controlled failback with reconciliation and authority epoch validation.
5. DR both directions in safe recovery/staging flow: Google → fresh Service; D1 → Google staging; exact tab/schema checks.
6. Final Google replication/integrity verification after failover/failback/DR.
7. Produce final production-complete handover after all DoD items pass.
8. Merge PR #38 only after full DoD.

## 20. M2 Definition of Done — mandatory closure bar

Only call M2 complete when `ANDROID APP ↔ WEB/PWA ↔ SERVICE/D1 ↔ GOOGLE SHEETS` is demonstrated and all are true:

- realtime PASS;
- offline PASS;
- failover PASS;
- failback PASS;
- DR both directions PASS;
- Beta19 Service-first OTA production verification PASS — already done;
- real PDA smoke PASS — pending owner/device validation;
- Google Sheet preserved/reconciled;
- Stable unpublished unless separately commanded;
- `HANDOVER_SERVICE_MIGRATION_M2_PRODUCTION_COMPLETE.md` produced;
- `docs/HANDOVER_CURRENT.md` updated to completion state;
- PR #38 merged only after closure.

## 21. S13 required start order

1. Read `docs/HANDOVER_CURRENT.md`.
2. Read `docs/handovers/HANDOVER_S12_2026-08-19.md`.
3. Read `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/ADMIN_ACCOUNT_RULES.md`, `docs/BUILD_RELEASE_PLAYBOOK.md`, `docs/SERVICE_MIGRATION_M2.md`, `docs/HANDOVER_POLICY.md`.
4. Re-fetch PR #38 and current Service/OTA state only where temporal verification is needed.
5. State that project context is understood.
6. **WAIT FOR OWNER COMMAND.** Do not automatically start tests, publish Stable, merge PR, change authority, or edit production data.

## 22. Session-close state

S12 closes with:

- M2 production cutover: **DONE**
- Web/PWA production: **LIVE / READY**
- Beta19 OTA: **PUBLISHED / VERIFIED**
- Google replication final gate: **HEALTHY**
- Stable: **UNPUBLISHED / UNTOUCHED**
- PR #38: **DRAFT / UNMERGED**
- Full M2 DoD: **NOT YET CLOSED** because real PDA acceptance, controlled failover/failback and DR exercises remain.

S13 must read the required files, acknowledge state, then wait for a new owner command.
