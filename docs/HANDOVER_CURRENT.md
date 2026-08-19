# HANDOVER CURRENT — PICK PACK 1291

Status: **ACTIVE / cumulative / authoritative**  
Last updated: **2026-08-19 11:02 +07:00 (Asia/Bangkok)**  
Closed working session: **S13**  
Next session: **S14**  
Latest published Beta: **0.4.2-beta.19 / versionCode 25**

> **NEW-CHAT STOP RULE:** S14 must first read this file, `docs/handovers/HANDOVER_S13_2026-08-19.md`, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/ADMIN_ACCOUNT_RULES.md`, `docs/BUILD_RELEASE_PLAYBOOK.md`, `docs/SERVICE_MIGRATION_M2.md` and `docs/HANDOVER_POLICY.md`. Then report that state is understood and **WAIT FOR A NEW OWNER COMMAND**. Do not publish Stable, merge PR #38, change authority, edit production data, run acceptance/failover/DR tests, or alter architecture merely because the session opened.

> **S13 DELTA:** S13 was a context-holding session only. No implementation, production mutation, release, test execution, schema change, data edit, architecture decision, Stable publication, or PR merge occurred after S12. The only close actions were state verification plus the required handover update. All valid S12 locks and decisions remain in force.

> **SUPERSEDED ARCHITECTURE NOTICE:** The S11 architecture `Android ↔ GAS ↔ Google Sheets` with Google Sheets as sole operational authority was deliberately superseded in S12 by the owner-approved M2 Service-first migration. Legacy GAS/Google behavior remains only for compatibility, operational replica, fallback and DR under M2 rules.

## 1. Project objective and current production architecture — OWNER LOCK

Current production architecture: `Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`, with Durable Objects/WebSocket realtime; Google Sheets as operational replica/compatibility/fallback/DR; GAS retained as compatibility/discovery/fallback bridge including Beta18 compatibility; GitHub as source/CI/release; Android SQLite/cache as projection/offline only.

Current authority remains environment `production`; scope `PRODUCTION`; mode `SERVICE_PRIMARY`; generation `m2-prod-20260819-001`. Web/PWA remains live on the production Worker. Final known Google replication gate from S12 was `HEALTHY`, pending `0`. Stable promotion requires explicit owner command.

## 2. Owner workstation constraint — OWNER LOCK

Never ask owner to use local CLI/terminal tooling. Build/sign/deploy/release are handled by GitHub Actions or assistant-controlled tooling; owner-facing setup is browser/UI only.

## 3. Production Google data model and M2 role

Workbook `DỮ LIỆU THEO NGÀY` visible tabs: `Danh mục`, `LỊCH SỬ NGHIỆP VỤ`, `DANH SÁCH PDA`, `DANH SÁCH USER PICK`, `DANH SÁCH BÀN PACK`, `DANH SÁCH USER PACK`, `DANH SÁCH NHÂN SỰ`, `RA - VÀO TRONG CA`, `CÔNG NHẬT`, `Danh sách Admin`.

D1 canonical state/events are Service-primary. Google projections remain for legacy clients, fallback and DR. Google failures do not block D1 critical path; outbox retries. Validate headers before writes. Never overwrite/delete production Sheet as DR target. Mandatory pre-Service rollback backup remains untouched. Separate staging workbook exists for replication/DR. Public handovers omit unnecessary Drive IDs/URLs; internal Drive handover contains operational identifiers. Catalog/select values come from project catalogs only.

## 4. Retention and correction — OWNER LOCK

Only N/N-1 may be corrected. Operational retention max 45 days. Older retained days immutable. Backend enforces correction window. Master/catalog/admin records are outside date retention. Android normal sync prioritizes N/N-1 and older dates on demand; Service maintains 45-day floor.

## 5. Business invariants — OWNER LOCK

`MNV` business key; session `MNV + business_date`; `NOT_ENTERED → ACTIVE → ENDED`; ENDED cannot normally re-enter same date; immutable/idempotent `event_id`; immutable canonical events; optimistic version/stale-write rejection; race-safe exclusive resources; failed resource change retains previous; OPEN labor blocks EXIT; EXIT releases current resources; authority epoch/generation fencing prevents split-brain/stale fallback.

PICK requires PDA; User Pick optional; validated last-5 serial search; ambiguous suffix invalid; daily User Pick consumption persists after release/change/EXIT unless authorized reuse.

PACK supports controlled Bàn Pack/User Pack and legitimate one-to-many mapping; daily User Pack consumption persists after release/change/EXIT unless authorized reuse.

ENTER/EXIT timezone Asia/Bangkok; shifts `Ca 1`, `Ca 2`, `HC`/`Ca HC`; work `PICK | PACK | KHÔNG`.

Công nhật: USER/Điều phối cannot operate; ADMIN/SUPERADMIN under correction-age permissions; lifecycle `OPEN / COMPLETED / CANCELLED`; resource policy `GIỮ / TRẢ`; accepted MNV immutable; OPEN blocks EXIT.

## 6. Production-data anomaly fixed in M2

`DANH SÁCH USER PACK` had duplicate `hy1.obpack18`: valid `D18 / Ca 1-18` plus invalid non-existent `D29`. CHỐT: do not rewrite Sheet just to bootstrap; keep valid mapping; report D29 anomaly; preserve legitimate one-to-many mappings including HP multi-user case; migration `0003` implements many-mapping model (verify exact filename before edits).

## 7. Authentication / roles / session — OWNER LOCK

Roles SUPERADMIN/ADMIN/USER with backend enforcement; `Vị trí` values exactly `superadmin`, `admin`, `user`; normal account creation cannot create SUPERADMIN unless owner changes rule. Credential model salted PBKDF2-HMAC-SHA256 + challenge/HMAC proof; never expose password/verifier/token/private key/signing material. Session model `SINGLE_ACTIVE_DEVICE_V1` remains.

## 8. Android local-first / offline — CURRENT M2

Dynamic Service discovery via GAS; Service-primary mutations; durable offline outbox; WorkManager replay; foreground WebSocket reconnect; circuit breaker + GAS fallback; exclusive operations may be `OFFLINE_PROVISIONAL`; local sync recent N/N-1 + older dates on demand. Preserve Beta15/Beta16 SQLite recovery guards. Historical `SQLITE_BUSY` crash loop was fixed in Beta17 with shared SQLite coordination, serialized DB, non-UI reconciliation and failure containment.

## 9. Realtime / fallback / failback — M2

Durable Object realtime; Android/Web converge on one authority; GAS fallback fenced; failover/failback uses epoch/mode transitions + reconciliation; Beta18 compatibility preserved. Production cutover already converged `PRODUCTION / SERVICE_PRIMARY`. Controlled failover/failback acceptance remains pending full closure.

## 10. History/report rules

Shared History is MNV-session operational history; detail includes ENTER/EXIT/resource/labor; admin-account actions excluded; Google history tab is projection after M2. Report manpower order: Trưởng nhóm, Chuyên viên, Tổ trưởng, Điều phối khu pack, Điều phối khu chờ xuất, Kéo hàng, 5S, Picker, Packer, Phúc Long, Tổng. Supplier order `Inhouse, NLV, VW, MP, MGL, HGP, HAD, Tổng`. Tenure Picker/Packer split ≤30/>30 days. `Hỗ trợ bộ phận khác` counts applicable Công nhật with `Khấu trừ nhân sự = Có`, de-duplicated, hidden when zero. Shift scopes `Ca 1 + Ca HC`, `Ca 2`, `Cả ngày`.

## 11. UI/UX

Read `docs/UI_UX_SYSTEM.md`. Bottom tabs exact: `Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`. Header `Chào buổi <...>, <Họ tên>`. Avoid protocol jargon. Preserve compact scanner controls, hardware Enter/OK, Beta18 dual-edge back, parent-tab reset, History Detail back. Sync symbols: `↑` outbound, `↓` download, `↕` concurrent, `✓` idle.

## 12. Logging

MANUAL `BÁO LỖI THỦ CÔNG`; CRASH `BÁO LỖI TỰ ĐỘNG`; DAILY `NHẬT KÝ ANDROID`. Confirm manual report; retry pending logs; delete locally only after ack; never expose secrets.

## 13. Web/PWA — LIVE

Production Web/PWA is live on Worker with M2 auth, IndexedDB state/outbox, offline replay, WebSocket reconnect and operational/admin UI. It is no longer shadow/mock. Real Web + Beta19 concurrent acceptance remains pending final DoD.

## 14. OTA / signing — OWNER LOCK

OTA: `Android → GAS update_check → Google Drive channel folder`; Beta and Stable isolated. Fixed signer SHA-256 `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`; never replace signer. Signing secret names may be documented, values never.

Latest Beta remains `0.4.2-beta.19`, versionCode `25`, package `vn.pickpack1291.app.beta.publicbeta`, signed SHA-256 `6dc47edba684249af0655a30573824911ee4a96482f86acf7f3995d6842c3103`; Beta18→Beta19 update/download/package/version/SHA/signer verification passed in S12. Stable remains UNPUBLISHED/UNTOUCHED.

## 15. S12 completed milestones inherited unchanged

Resolved Google OAuth/API and Cloudflare; created/migrated production D1; stabilized Worker/PWA; resumable chunked Google bootstrap; real 45-day bootstrap PASS; resource anomaly/many-mapping fix; final bootstrap no RUNNING state; D1→Google staging replication PASS (`HEALTHY`, pending 0); retired mutating/redeploying verifier workflows before cutover; Service authority promoted; GAS converged `SERVICE_PRIMARY`; Web observer PASS; Beta19 candidate/signer verified; OTA publisher repaired through V5; final OTA observer PASS; Stable untouched.

## 16. Verified final gates inherited from S12

PASS: Cutover Observer; Runtime Diagnostic; Chaos Matrix; Chaos Matrix V2; Precutover; Release Preflight; App Fast Check; Publisher V5 Observer; OTA Observer. Publisher V1–V4 failures are historical debugging only. Some bootstrap/replication/precutover workflows are intentionally retired/skipped post-cutover to prevent races.

S13 did not rerun these gates; do not reinterpret this handover update as a new test run.

## 17. GitHub state — DO NOT MERGE YET

Repo `tam95supra-source/pick-pack-1291`; branch `agent/service-migration-m2`; PR #38 was re-fetched at S13 close and was **open, draft, unmerged, mergeable**, base `main`. Head SHA immediately before S13 handover commits: `150d58b26b67234b3262ba748dee2ccd93f0e3c0`. The S13 handover commits move branch head again. Always re-fetch PR #38 before any modification or merge. Do not merge until full M2 DoD.

## 18. Process caveats

No owner CLI; no Stable publish without explicit command; no new signer; no production Sheet overwrite/delete; no casual re-enable of retired mutating workflows; do not use original buggy live-release workflow; avoid huge code in workflow YAML; use native GitHub artifact tooling; account for Apps Script propagation with readiness/idempotent retry; no explicit transaction wrapper assumption in remote wrangler verification; no monolithic full-Sheet Worker bootstrap; preserve Beta18 compatibility until deliberately retired; public handovers remain public-safe.

## 19. Remaining work before full M2 DoD

Real PDA Beta19 smoke; real Web+Beta19 concurrent test; controlled Service failover to GAS fallback with split-brain fencing; controlled failback/reconciliation/epoch validation; DR both directions in safe recovery/staging; final replication/integrity verification; final production-complete handover; merge PR #38 only after full DoD.

None of these remaining tasks were executed in S13.

## 20. M2 Definition of Done

Need `ANDROID APP ↔ WEB/PWA ↔ SERVICE/D1 ↔ GOOGLE SHEETS` with realtime PASS, offline PASS, failover PASS, failback PASS, DR both directions PASS, Beta19 OTA PASS (already), real PDA smoke PASS (pending), Google Sheet preserved/reconciled, Stable unpublished unless separately commanded, `HANDOVER_SERVICE_MIGRATION_M2_PRODUCTION_COMPLETE.md`, final `HANDOVER_CURRENT`, then PR #38 merge.

## 21. S14 start order

Read `HANDOVER_CURRENT`, S13 snapshot, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, UI/admin/release/M2/policy docs; re-fetch only time-sensitive state; acknowledge context; then **WAIT FOR OWNER COMMAND**. Do not auto-test, publish Stable, merge, change authority or edit production data.

## 22. Close state

S13 closed with **no project-state delta after S12**. Current inherited state: M2 production cutover DONE; Web/PWA LIVE/READY; Beta19 OTA PUBLISHED/VERIFIED; last known Google replication HEALTHY; Stable UNPUBLISHED/UNTOUCHED; PR #38 DRAFT/UNMERGED; full M2 DoD NOT YET CLOSED because real PDA acceptance, controlled failover/failback and DR remain.
