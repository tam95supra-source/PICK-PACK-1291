# HANDOVER CURRENT — PICK PACK 1291

Status: **ACTIVE / cumulative / authoritative**  
Current baseline: **2026-08-20 — Beta33 LIVE / Service telemetry Sync-only / stress dataset 500 staff**  
Current published Beta: **0.4.2-beta.33 / versionCode 39**  
Package: `vn.pickpack1291.app.beta.publicbeta`

> **CURRENT-BASELINE RULE:** Beta32/Beta31/Beta25 and earlier references are historical evidence only. Read current source + live OTA/authority evidence before citing the latest state.

> **RISKY-OPERATION STOP RULE:** Before failback, DR, authority transition, production-data mutation, Stable action, signer action or PR merge, re-fetch PR #38/branch HEAD and revalidate Service authority, GAS discovery authority, replication and OTA state. Never force live state to match stale documentation.

## 1. Owner-approved architecture — OWNER LOCK

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

with Google Sheets operational replica/compatibility/fallback/DR, GAS discovery/compatibility/fallback/OTA, Android SQLite local-first projection/outbox/history, Durable Object/WebSocket invalidation and Firebase only for FCM wake/invalidation.

Service URL: `https://pick-pack-1291-service.pp1291-d79b87776e86.workers.dev`  
GAS URL: `https://script.google.com/macros/s/AKfycbzbEoGfbNg6s2HnP-gUpcBJ7mMIkVBtYuQKMndb9seDV2c55lQwSUO1GZ-LtQ2CxMCauA/exec`  
Production Sheet ID: `1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78`

Firebase is not operational authority/DB/Auth/Storage.

## 2. Current Beta33 release — OWNER LOCK

- versionName `0.4.2-beta.33`
- versionCode `39`
- package `vn.pickpack1291.app.beta.publicbeta`
- APK size `12880379`
- APK SHA-256 `dde653a4e146874df88f90d758156d5393cc6e4b79bf57c4a8614b7ccda09397`
- signer SHA-256 `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- artifact ID `9404068037`
- Beta Drive APK ID `1-sZ-P0J4G4zAb-4_ytTzc4vbj3qxdkdy`
- checksum Drive ID `1QSLmWYWi9b4c7OlvrSUuFU6ybCS5kehU`

Evidence:
- `ops/session11-beta33-build-candidate-result.txt`
- `ops/session11-beta33-final-acceptance-result.txt`

Final acceptance PASS: authority, `HEALTHY_0`, OTA discovery, exact public download/hash, self-update and Stable isolation.

## 3. Fresh live authority checkpoint

Evidence `ops/session6-authority-gas-readonly-result.txt`, checked 2026-08-20T12:11:45.356Z:

- Service `SERVICE_PRIMARY`
- epoch `8`
- seq `18505`
- scope `PRODUCTION`
- replication `HEALTHY / pending 0`
- GAS `SERVICE_PRIMARY / epoch 8`
- Service HTTP 200
- GAS HTTP 200
- verdict PASS

## 4. Beta33 correction — OWNER LOCK

Service/backend telemetry belongs to **tab Đồng bộ**, not tab Lịch sử.

Beta33 S37:
- removed Service telemetry block and `sync_status` telemetry call from History;
- preserved Beta32/S36 History performance;
- Sync shows RTT/route/authority/replication plus realtime connections, online-recent devices, realtime business date and endpoint readiness.

Build contract:
- `history_telemetry_removed=PASS`
- `sync_telemetry_contract=PASS`
- `beta32_perf_preserved=PASS`

## 5. History/local-first contract — OWNER LOCK

History is durable local history + canonical snapshots. A mutation must be recorded locally immediately and remain visible even if pending/retry/rejected/conflict/failed. Do not wait for Service ACK before History exists. Do not delete history because Service/Google rejects a mutation.

Normal hot path remains local-first SQLite/outbox then network flush/ACK/canonical catch-up. Confirmed events are not resent.

## 6. Stress dataset current backend state

Main seed evidence: `ops/session9-stress500-n13n-result.txt`.

Seeded into D1 + Google target tabs:
- exactly 500 employees, MNV `30001..30500`
- dates `2026-08-07..2026-08-20` = 14 days
- 360 complete attendance sessions/day = 5,040 sessions = 10,080 attendance events/rows
- 300 labor sessions/day = 4,200 sessions = 8,400 labor events
- total canonical stress events 18,480
- non-target D1 unchanged
- non-target Google unchanged
- Stable untouched

Pre-stress Google backup:
`DỮ LIỆU THEO NGÀY__PRE_STRESS_500_N13_N_BACKUP__2026-08-20_1657`
ID `1oB6FyiODQ1nuzCRvvA8yPDM_uH0ONLBfrHb1EZMMONk`

Android retention remains canonical `N..N-6` = 7 business sessions even though backend stress source has 14 days.

## 7. Production Sheet safety

Stress target tabs only:
- `DANH SÁCH NHÂN SỰ`
- `RA - VÀO TRONG CA`
- `CÔNG NHẬT`

Do not mutate user Pick/PDA/bàn Pack/user Pack/catalog as a shortcut. Use only values from `Danh mục`. Do not reset/rename/delete production Sheet tabs.

## 8. Web/session inherited state

Production Web v10 remains inherited from previous work:
- hidden login/app overlays fixed;
- migration `0005_web_session_isolation.sql` applied;
- one PDA slot + one Web slot per login are independent;
- PDA + Web can remain active concurrently;
- second Web replaces only first Web;
- logout only affects own client class.

Beta33 did not redeploy Web.

## 9. OTA/release locks

Beta folder ID `1WMXI-8-Z1mbY2v11noYFHe_eoMNiNZXg`.  
Stable folder ID `1kxTd2rFfWutc2KWDwqgK8WYWDmSygIN4`.

Stable is currently **EMPTY / UNPUBLISHED / UNTOUCHED**.

Normal release gate requires Service-primary/production, Service-GAS epoch match, replication `HEALTHY_0`, exact signed candidate, full public-byte/hash verification, self-update false, Stable isolation and PR38 unchanged.

Beta29 had a one-time replication waiver. Never reuse it silently. Never fake ACK/delete canonical events to satisfy a gate.

## 10. GitHub/PR locks

Repo `tam95supra-source/pick-pack-1291`  
Branch `agent/service-migration-m2`  
PR `#38`

Fresh handover check: PR open, draft, not merged.

- no merge without explicit OWNER approval;
- no Stable publish without explicit OWNER command;
- no signer/package change;
- no destructive production Sheet shortcut;
- preserve backups;
- no secrets in repo/chat/docs.

PR body may contain stale Beta25 baseline and is not current-state authority.

## 11. Still NOT PROVEN by CI alone

Do not mark these PASS without genuine field evidence:
- Beta33 History perceived performance on real PDA with stress data;
- Sync telemetry layout/visibility on real PDA;
- 2-PDA realtime convergence/shared History;
- physical FCM background/closed wake delivery;
- full PDA + Web concurrency/replacement acceptance;
- final DR/integrity closure.

PR merge and Stable publish are intentionally not done.

## 12. Continuation order

1. Treat Beta33 as current baseline.
2. If owner reports a defect, diagnose Beta33 and fix-forward Beta34+ if needed.
3. Before backend/data/release changes, fresh-check authority/replication/OTA/PR.
4. Keep History local-first and Service telemetry Sync-only.
5. Do not change N..N-6 retention merely because the backend stress source contains 14 days.
6. Do not merge PR38 or publish Stable without explicit OWNER command.

Full transfer artifact for this checkpoint: `PICK_PACK_1291_HANDOVER_MASTER_BETA33_2026-08-20.md`.
