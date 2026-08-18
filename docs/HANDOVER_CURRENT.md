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

Current production architecture is `Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`, with Durable Objects + WebSocket/Hibernation for realtime; Google Sheets as operational replica/compatibility/fallback/DR under M2; Google Apps Script retained as compatibility/discovery/fallback bridge including Beta18 compatibility; GitHub as source/CI/release; Android local SQLite/cache as projection/offline only.

Current authority state after cutover: environment `production`; authority scope `PRODUCTION`; authority mode `SERVICE_PRIMARY`; generation `m2-prod-20260819-001`; Web/PWA `https://pick-pack-1291-service.pp1291-d79b87776e86.workers.dev`; final Google replication gate `HEALTHY`, pending `0`.

Stable promotion still requires explicit owner command.

## 2. Owner workstation constraint — OWNER LOCK

Owner's company-managed workstation cannot use local CLI. Never ask owner to run CMD/PowerShell/Terminal/bash/git/gh/clasp/adb/Gradle/npm/npx/Java/keytool/OpenSSL or similar commands. Build/sign/deploy/release operations are handled by GitHub Actions or assistant-controlled tooling. Owner-facing setup should be browser/UI only.

## 3. Production Google data model and role after M2

Production workbook remains `DỮ LIỆU THEO NGÀY` with exactly these visible tabs: `Danh mục`, `LỊCH SỬ NGHIỆP VỤ`, `DANH SÁCH PDA`, `DANH SÁCH USER PICK`, `DANH SÁCH BÀN PACK`, `DANH SÁCH USER PACK`, `DANH SÁCH NHÂN SỰ`, `RA - VÀO TRONG CA`, `CÔNG NHẬT`, `Danh sách Admin`.

M2 rules: D1 canonical events/state are Service-primary; Google operational projections remain required for legacy Beta18/GAS clients; Google failures do not block D1 critical mutation path because outbox retries; header/schema validation before writes; production Sheet must not be overwritten/deleted as DR target; mandatory pre-Service rollback backup remains untouched; separate staging workbook is used for technical replication/DR; public repo handovers must omit unnecessary Drive IDs/URLs while internal Drive handover holds those details. Catalog/select values still come from project catalogs only.

## 4. Data retention and correction window — OWNER LOCK

Only business date N and N-1 may be corrected/changed. Operational data retention maximum 45 days. N/N-1 mutable; older retained days immutable. Service/backend must enforce correction window. Master/catalog/admin records are outside date-retention deletion. Android/PDA normal sync prioritizes N/N-1 and fetches older retained dates on demand while Service maintains the full 45-day floor.

## 5. Business invariants — OWNER LOCK

`MNV` is business key; session key `MNV + business_date`; state `NOT_ENTERED → ACTIVE → ENDED`; ENDED cannot normally re-enter same date; immutable/idempotent `event_id`; immutable canonical events; optimistic version/stale-write rejection; race-safe exclusive resources; failed resource change retains previous resource; OPEN labor blocks EXIT; EXIT releases current resources; authority epoch/generation fencing prevents split-brain/stale fallback.

PICK: requires PDA; User Pick optional; PDA search uses validated last 5 serial digits; ambiguous duplicate suffix is invalid; daily User Pick remains used after release/change/EXIT unless authorized reuse.

PACK: Bàn Pack + mapped User Pack controlled resources; legitimate one-to-many user-pack mappings supported; daily User Pack remains used after release/change/EXIT unless authorized reuse.

ENTER/EXIT: timezone Asia/Bangkok; shifts `Ca 1`, `Ca 2`, `HC`/`Ca HC`; work `PICK | PACK | KHÔNG`; OPEN labor blocks EXIT.

Công nhật: USER/Điều phối cannot operate; ADMIN/SUPERADMIN under correction-age permissions; lifecycle `OPEN / COMPLETED / CANCELLED`; resource policy `GIỮ / TRẢ`; accepted MNV immutable; OPEN Công nhật blocks EXIT.

## 6. Production-data anomaly discovered during M2 bootstrap

`DANH SÁCH USER PACK` contained duplicate `hy1.obpack18`: one valid `D18 / Ca 1-18` mapping and one row referencing non-existent `D29`. CHỐT: do not rewrite production Sheet just to make bootstrap pass; keep valid mappings; report invalid D29 as anomaly; resource-pack schema supports legitimate one-to-many mappings including HP multi-user case; migration `0003` implements many-mapping model (verify exact filename before code changes).

## 7. Authentication / roles / session — OWNER LOCK

Roles SUPERADMIN, ADMIN, USER with backend enforcement. Admin `Vị trí` values exactly `superadmin`, `admin`, `user`; role mapping exact. Normal account creation cannot create SUPERADMIN unless owner changes rule.

Credential model: salted PBKDF2-HMAC-SHA256 verifier; challenge/HMAC proof; plaintext password not sent directly; no passwords/verifiers/tokens/private keys/signing material in public repo or handover.

Session model `SINGLE_ACTIVE_DEVICE_V1`: persists across normal app close on same installation; another installation replaces active server session; old device rejected on next protected request/sync; logout/password/security changes may invalidate.

## 8. Android local-first / offline model — CURRENT M2 RULE

Dynamic Service discovery via stable GAS endpoint; Service-primary mutations; durable offline outbox; WorkManager replay; foreground WebSocket reconnect; circuit breaker + GAS fallback when Service unavailable/not authority; exclusive operations may be `OFFLINE_PROVISIONAL`; normal local sync recent N/N-1 and older dates on demand; preserve Beta15/Beta16 SQLite recovery guards.

Historical incident: Beta15/Beta16 `SQLiteDatabaseLockedException / SQLITE_BUSY` crash loops on Android 11 PDA. Beta17 fixed shared SQLite coordination, serialized DB access, non-UI reconciliation and failure containment. Preserve those safeguards.

## 9. Realtime, fallback and failback — M2

Service uses Durable Object realtime. Android/Web converge on one authority. GAS fallback is fenced and must not become competing authority. Failover/failback requires authority epoch/mode transitions + reconciliation, not URL switching. Beta18 compatibility must remain. Production cutover already converged with Service/GAS agreeing `PRODUCTION / SERVICE_PRIMARY` and same epoch. Controlled failover/failback acceptance remains pending closure.

## 10. Shared history and reporting rules

Shared History is operational MNV-session history, not device-local app history; detail includes ENTER/EXIT/resource/labor; admin-account actions excluded; Google `LỊCH SỬ NGHIỆP VỤ` is projection, not independent canonical authority after M2.

Report manpower order: Trưởng nhóm, Chuyên viên, Tổ trưởng, Điều phối khu pack, Điều phối khu chờ xuất, Kéo hàng, 5S, Picker, Packer, Phúc Long, Tổng. Supplier order: `Inhouse, NLV, VW, MP, MGL, HGP, HAD, Tổng`. Tenure matrices Picker/Packer split ≤30 days / >30 days. `Hỗ trợ bộ phận khác` counts applicable Công nhật with `Khấu trừ nhân sự = Có`, de-duplicated; hide when zero. Shift scopes `Ca 1 + Ca HC`, `Ca 2`, `Cả ngày`.

## 11. UI/UX current rules

Read `docs/UI_UX_SYSTEM.md` before visual changes. Bottom tabs exact order `Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`. Header target `Chào buổi <sáng/trưa/chiều/tối>, <Họ tên>`. Avoid API/revision jargon. Scan/search remains compact; hardware Enter/OK triggers scanning. Preserve Beta18 dual-edge swipe-back, active parent-tab reset, History Detail back. Sync direction semantics: `↑` outbound, `↓` download, `↕` concurrent, `✓` idle.

## 12. Logging / diagnostics

MANUAL → `BÁO LỖI THỦ CÔNG`; CRASH → `BÁO LỖI TỰ ĐỘNG`; DAILY → `NHẬT KÝ ANDROID`. Manual report requires confirmation. Pending logs retry. Delete local logs only after acknowledgement. Never expose secrets/private credentials in logs.

## 13. Web/PWA — PRODUCTION READY

Web/PWA is live on production Worker. It uses same-origin Worker hosting, M2 authentication, IndexedDB state/outbox, offline replay, WebSocket reconnect and operational/admin UI. It is not a shadow/mock site. Real owner/device Web + Beta19 concurrent acceptance remains pending final DoD.

## 14. OTA / signing / release — OWNER LOCK

OTA authority remains `Android → GAS update_check → Google Drive channel folder`. Beta reads Beta only; Stable reads Stable only.

Fixed signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`. Never replace signer. Permanent signing secret names: `ANDROID_SIGNING_KEY_B64`, `ANDROID_SIGNING_STORE_PASSWORD`, `ANDROID_SIGNING_KEY_PASSWORD`, `ANDROID_SIGNING_ALIAS`; never expose values.

Latest Beta: `0.4.2-beta.19`, versionCode `25`, package `vn.pickpack1291.app.beta.publicbeta`, signed candidate SHA-256 `6dc47edba684249af0655a30573824911ee4a96482f86acf7f3995d6842c3103`, fixed signer unchanged. Beta18→Beta19 update check/download/package/version/SHA/signer verification PASS. Stable remains UNPUBLISHED/UNTOUCHED.

## 15. S12 Service migration implementation — completed milestones

S12 resolved Google OAuth/API and Cloudflare credentials; created/migrated production D1; stabilized Worker/PWA; converted full Google bootstrap to resumable/chunked idempotent phases; completed real 45-day bootstrap; fixed resource anomaly/one-to-many mapping; completed final bootstrap with no RUNNING state; passed D1→Google staging replication (`HEALTHY`, pending 0); retired mutating/redeploying verifier workflows before cutover; promoted Service authority; converged GAS `SERVICE_PRIMARY`; passed Web/PWA observer; verified Beta19 signer/candidate; repaired OTA publisher path through V5; passed final Beta18→Beta19 OTA observer; left Stable untouched.

## 16. Verified CI/live gates at S12 close

PASS: `Service M2 Cutover Observer`, `Service M2 Runtime Diagnostic`, `Service M2 Chaos Matrix`, `Service M2 Chaos Matrix V2`, `Service M2 Precutover`, `Release Preflight - Beta and Stable`, `App Fast Check`, `Service M2 Publisher V5 Run Observer`, `Service M2 OTA Observer`.

Historical publisher V1–V4 failures are debugging history only. Some bootstrap/replication/precutover workflows are intentionally retired/skipped post-cutover to prevent mutation/redeploy races; intentional skips are not failures.

## 17. GitHub state — DO NOT MERGE YET

Repository `tam95supra-source/pick-pack-1291`; M2 branch `agent/service-migration-m2`; PR #38 open/draft/unmerged, base `main`. Implementation head immediately before S12 handover-doc commits was `6b23b69d5ed5e3c4dc1fca2bbc2193426a015418`; handover docs then moved branch head. Always re-fetch PR #38 before modification/merge. Do not merge until full M2 DoD.

## 18. Known process caveats / failures not to repeat

Do not ask owner to use CLI; do not publish Stable without explicit command; do not generate new signer; do not overwrite/delete production Sheet; do not casually re-enable retired mutating workflows; do not use original buggy live-release workflow; do not embed huge code payloads in workflow YAML; use native GitHub tooling for artifact download; account for Apps Script deployment propagation with readiness stabilization/idempotent retry; do not assume `wrangler d1 execute` remote supports explicit transaction wrappers; do not use monolithic full-Sheet Worker bootstrap; preserve Beta18 compatibility until deliberately retired; keep public handovers public-safe.

## 19. Remaining work before full M2 Definition of Done

Web and Beta19 OTA are already live. Remaining acceptance/closure: real PDA Beta19 smoke; real Web+Beta19 concurrent test; controlled Service failover to GAS fallback with split-brain fencing; controlled failback/reconciliation/epoch validation; DR both directions in safe recovery/staging; final replication/integrity verification; final production-complete handover; merge PR #38 only after full DoD.

## 20. M2 Definition of Done — mandatory closure bar

Only call M2 complete when `ANDROID APP ↔ WEB/PWA ↔ SERVICE/D1 ↔ GOOGLE SHEETS` is demonstrated with realtime PASS, offline PASS, failover PASS, failback PASS, DR both directions PASS, Beta19 production OTA PASS (already), real PDA smoke PASS (pending), Google Sheet preserved/reconciled, Stable unpublished unless separately commanded, `HANDOVER_SERVICE_MIGRATION_M2_PRODUCTION_COMPLETE.md` produced, `docs/HANDOVER_CURRENT.md` updated to completion and PR #38 merged only after closure.

## 21. S13 required start order

Read `docs/HANDOVER_CURRENT.md`; read `docs/handovers/HANDOVER_S12_2026-08-19.md`; read `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/ADMIN_ACCOUNT_RULES.md`, `docs/BUILD_RELEASE_PLAYBOOK.md`, `docs/SERVICE_MIGRATION_M2.md`, `docs/HANDOVER_POLICY.md`; re-fetch only time-sensitive PR/Service/OTA state; acknowledge context; then **WAIT FOR OWNER COMMAND**. Do not automatically test, publish Stable, merge PR, change authority or edit production data.

## 22. Session-close state

S12 closes: M2 production cutover DONE; Web/PWA LIVE/READY; Beta19 OTA PUBLISHED/VERIFIED; Google replication final gate HEALTHY; Stable UNPUBLISHED/UNTOUCHED; PR #38 DRAFT/UNMERGED; full M2 DoD NOT YET CLOSED because real PDA acceptance, controlled failover/failback and DR exercises remain.
