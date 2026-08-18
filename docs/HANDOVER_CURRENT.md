# HANDOVER CURRENT — PICK PACK 1291

Status: **ACTIVE / cumulative / authoritative**  
Last updated: **2026-08-18 21:29 +07:00 (Asia/Bangkok)**  
Closed working session: **S11**  
Next session: **S12**  
Latest published Beta: **0.4.2-beta.18 / versionCode 24**

> **NEW-CHAT STOP RULE:** S12 must first read this file, `docs/handovers/HANDOVER_S11_2026-08-18.md`, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/ADMIN_ACCOUNT_RULES.md`, `docs/BUILD_RELEASE_PLAYBOOK.md` and `docs/HANDOVER_POLICY.md`. After reporting that the state is understood, **WAIT FOR A NEW OWNER COMMAND**. Do not build, deploy, edit Sheet, publish OTA, promote Stable or change architecture merely because the session opened.

> Patch labels such as S12/S13/S14/S15/S17/S18 below are **implementation patch labels**, not chat-session numbers. The latest closed chat session is **S11**.

## 1. Project objective and architecture — OWNER LOCK

Android APK for Pick Pack 1291 operational workflows.

Official architecture remains exactly:

`Android App ↔ Google Apps Script Web App ↔ Google Sheets`

- Google Sheets is the operational source of truth.
- Google Apps Script is the transaction/API bridge tied to the workbook.
- GitHub is source/CI/release infrastructure only.
- Android local cache is a read/projection accelerator only; it is **not** a new business authority.
- No Supabase/Firebase/Neon/Postgres/Cloudflare/new backend/storage/auth/sync authority without explicit owner approval.
- Beta is full-function and uses real business rules/data.
- Stable requires explicit owner promotion.

## 2. Owner workstation constraint — OWNER LOCK

Owner's company-managed workstation cannot use local CLI.

Never ask owner to run CMD/PowerShell/Terminal/bash/git/gh/clasp/adb/Gradle/npm/npx/Java/keytool/OpenSSL or similar commands. Build/sign/deploy/release operations are handled by GitHub Actions or assistant-controlled tooling. Owner-facing setup should be browser/UI only.

## 3. Authoritative workbook and tabs

Workbook: **`DỮ LIỆU THEO NGÀY`**.

Main tabs:

- `Danh mục`
- `DANH SÁCH NHÂN SỰ`
- `DANH SÁCH PDA`
- `DANH SÁCH USER PICK`
- `DANH SÁCH BÀN PACK`
- `DANH SÁCH USER PACK`
- `RA - VÀO TRONG CA`
- `CÔNG NHẬT`
- `Danh sách Admin`
- `LỊCH SỬ NGHIỆP VỤ` may be lazily created/used by shared-history logic

Catalog/select values must come from the matching Sheet/catalog namespace. Do not invent values outside the workbook catalog.

## 4. Data-retention and edit window — OWNER LOCK, NEWEST RULE

Owner fixed these rules during S11:

1. **Only business date N and N-1 may be corrected/changed.**
2. Operational data is kept for **maximum 45 days**.
3. When a new day arrives, the oldest day is removed so the retained window remains at most 45 days.
4. N and N-1 are mutable; older retained days are treated as immutable operational history.
5. Backend authorization must enforce the N/N-1 correction window; Android UI alone is not sufficient.

Retention applies to date-scoped operational/history data, not master catalogs/admin account records.

## 5. Local-first 45-day data model — OWNER-APPROVED DIRECTION, IMPLEMENTED IN BETA15+

**SUPERSEDED:** Beta14 screen-result caching (`report_daily`/`history_shared` JSON in SharedPreferences) is no longer the target architecture.

Current model:

`RAM hot state → SQLite 45-day local store → GAS revision/snapshot sync → Google Sheets authority`

### Local operational store

Android contains:

- `OperationalDataStore.kt`
- `OperationalSyncEngine.kt`
- master-data cache remains separate for staff/catalog/resources

The operational store is business-date indexed and keeps the retained date window locally. Report/history screens read local data rather than waiting for a screen-triggered API request.

### Revision-driven synchronization

GAS exposes a lightweight synchronization manifest/status containing business-date/revision information. PDA compares server day revisions with local revisions.

Behavior:

- changed day revision → fetch/replace only that day's snapshot;
- normal steady state should mainly re-fetch N and/or N-1;
- older immutable days are not repeatedly downloaded;
- initial bootstrap prioritizes N and N-1 first, then fills remaining retained days in background;
- replacement is atomic at local-store level so a day is not left half-old/half-new;
- retention floor causes local deletion of expired dates without re-downloading unchanged retained days.

### Foreground multi-PDA convergence

No new push backend was introduced. Foreground revision polling remains the convergence mechanism.

- PDA performing a mutation gets its own operation response immediately.
- Other foreground PDAs observe the changed server revision and fetch the changed date.
- Returning to foreground triggers synchronization promptly.
- Screen-off/background polling is not intended as an always-on service.

### UI rule

Opening Report/History should not require waiting for Sheet/GAS network round trips after local data exists. Network is for synchronization, not for basic screen rendering.

## 6. SQLite crash incident and recovery — CRITICAL

### Incident

Beta15/Beta16 introduced a crash loop on real Newland PDA / Android 11.

Observed exception family:

`SQLiteDatabaseLockedException / SQLITE_BUSY`

Root cause was concurrent local database access/opening around SQLite journal-mode handling during retention cleanup (`OperationalDataStore.dropBefore()` path). The app could crash before the user had enough time to accept OTA.

### Emergency recovery

A server-side compatibility/recovery gate was deployed so vulnerable Beta15/Beta16 clients do not enter the problematic local-sync path during startup. This keeps them alive long enough to receive OTA.

### Beta17 root fix

Beta17 fixed the local database architecture:

- process-wide shared SQLite helper/connection strategy;
- serialized DB access;
- local synchronization runs off the UI thread;
- no unsafe concurrent journal-mode negotiation;
- SQLite/cache failure must not crash the operational app;
- stale revision is left for a later retry when local persistence fails;
- reconciliation self-loop bug fixed so the same manifest does not endlessly re-enqueue itself.

`OperationalSyncEngine` uses a single-thread executor and catches local-cache failures. This safety behavior must be preserved.

### Recovery-gate caveat

Beta17/Beta18 can derive a 45-day local floor from `business_date` when the compatibility response intentionally leaves `retention_floor` blank. Do not casually remove the compatibility behavior until active vulnerable devices are no longer relevant and the replacement behavior is deliberately verified.

## 7. Stress-test dataset status

A synthetic stress dataset was added to the workbook for model/device load testing:

- about 300 synthetic personnel;
- 45 retained days ending 18/08/2026 at generation time;
- random complete Vào/Ra sessions and completed Công nhật records;
- existing operational data was preserved;
- resource fields were intentionally left blank for generated stress records;
- generated catalog/select values came only from existing Sheet catalogs.

Do not regenerate/replace this dataset unless owner asks. The 45-day retention mechanism may progressively remove oldest dates as normal operation advances.

## 8. Business invariants — OWNER LOCK

- `MNV` is the business key.
- Session key: `MNV + business_date`.
- State machine: `NOT_ENTERED → ACTIVE → ENDED`.
- Once ENDED, normal flow cannot re-enter on the same business date.
- Mutations use immutable/idempotent `event_id`.
- Exclusive resources are race-safe; one winner.
- Failed resource change retains the previous resource.
- Google Sheet/server state remains authoritative for mutations/resource exclusivity.

### PICK

- requires PDA;
- User Pick optional;
- PDA entered/searched using validated last 5 serial digits;
- ambiguous duplicate 5-digit suffix cannot be accepted as unique;
- daily User Pick consumption remains used after release/change/EXIT unless authorized reuse exists.

### PACK

- Bàn Pack + mapped User Pack is an exclusive bundle;
- daily User Pack consumption remains used after release/change/EXIT unless authorized reuse exists.

### ENTER / EXIT

- timezone Asia/Bangkok;
- shifts: `Ca 1`, `Ca 2`, `HC`/`Ca HC` according route/UI mapping;
- work choice: `PICK | PACK | KHÔNG`;
- OPEN Công nhật blocks EXIT;
- EXIT releases currently owned resources.

### Công nhật

- USER/Điều phối cannot operate Công nhật;
- ADMIN/SUPERADMIN operate under correction-age permissions;
- lifecycle `OPEN / COMPLETED / CANCELLED`;
- resource policy `GIỮ / TRẢ`;
- accepted MNV immutable;
- OPEN Công nhật blocks EXIT.

## 9. Authentication / admin / session — OWNER LOCK

Roles: SUPERADMIN, ADMIN, USER. Backend enforcement is mandatory.

Admin `Vị trí` values exactly:

- `superadmin`
- `admin`
- `user`

Role mapping exactly:

- SUPERADMIN → `superadmin`
- ADMIN → `admin`
- USER → `user`

Normal account creation cannot create SUPERADMIN unless owner explicitly changes the rule.

Credential model:

- salted PBKDF2-HMAC-SHA256 verifier;
- challenge/HMAC login proof;
- plaintext password is not sent directly;
- no password/verifier/token/private key/private signing material in public repo or handover.

Session model: **`SINGLE_ACTIVE_DEVICE_V1`**.

- persists across normal app/process close on same installation;
- another installation replaces the active server session for that account;
- old device is rejected on next protected request/sync;
- logout/password/security changes may invalidate.

Forgot-password remains generic, rate-limited and uses configured account email.

## 10. Shared operational history — CURRENT RULE

**SUPERSEDED:** device-local app action history is not the authoritative business History screen.

Shared History means operational MNV-session history visible consistently across accounts.

- one outer card per MNV/current business-date session;
- tap MNV for detailed session timeline;
- includes session-related operations such as ENTER, EXIT, resource change and labor start/finish;
- admin-account management actions must not appear in MNV operational history;
- Google Sheet audit projection `LỊCH SỬ NGHIỆP VỤ` is not a separate database authority;
- RA/CÔNG NHẬT remain business-state authority;
- existing current-day history can be synthesized from operational rows when audit projection is absent/incomplete.

Beta15+ reads current shared-history projection from the local operational snapshot rather than performing a screen-specific network load.

## 11. Report rules and local date selector

### Report date

Owner requested Report to allow selection of **every business date actually available in device cache**.

Current behavior:

- date selector is derived from `OperationalDataStore.availableDates()`;
- entering Report prioritizes/selects **N (current business date)** when available;
- report renders from the chosen cached day's local snapshot;
- opening/changing report view is local-first rather than waiting for `report_daily` on each open.

### Canonical manpower row order

1. Trưởng nhóm
2. Chuyên viên
3. Tổ trưởng
4. Điều phối khu pack
5. Điều phối khu chờ xuất
6. Kéo hàng
7. 5S
8. Picker
9. Packer
10. Phúc Long
11. Tổng

Supplier canonical order when present:

`Inhouse, NLV, VW, MP, MGL, HGP, HAD, Tổng`

### Tenure matrices

Separate bordered matrices:

- `Thâm niên Picker`
- `Thâm niên Packer`

Rows:

- Nhân sự mới ≤30 days
- Nhân sự cũ >30 days

### Hỗ trợ bộ phận khác

- only Công nhật with `Khấu trừ nhân sự = Có`;
- same person/support type de-duplicated;
- by supplier + total;
- hide entire support block when zero;
- when support exists show post-deduction Picker/Packer old/new remainder.

Shift scopes:

- `Ca 1 + Ca HC`
- `Ca 2`
- `Cả ngày`

## 12. UI/UX current state

Read `docs/UI_UX_SYSTEM.md` before changing visual system.

Persistent bottom tabs exact order:

`Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`

### Header

Target identity line:

`Chào buổi <sáng/trưa/chiều/tối>, <Họ tên>`

Uses PDA local clock. Do not show login ID/role/position/avatar in the target header design. Keep `Mạng / Đồng bộ / Service` compact and user-facing; avoid API/revision/protocol jargon.

### Scan/search controls

Latest compact target is about **72dp** high after real-PDA feedback. Inputs use stronger border/background/icon treatment so the scan/input zone is visually obvious.

Contextual placeholders remain purpose-specific, including Vào/Ra, Công nhật, Tài nguyên and staff search. Hardware Enter/OK triggers scanner actions.

### Beta18 navigation fixes

1. `EdgeSwipeBackLayout` accepts back gesture from **either edge**:
   - left edge → swipe right;
   - right edge → swipe left.
2. When user is inside a child screen of the active bottom tab, tapping the active **parent tab** resets to that tab's root.
   - Example: `Lịch sử → Chi tiết lịch sử → tap Lịch sử` returns to basic shared-history list.
3. Existing explicit back behavior for `HISTORY_DETAIL → historyScreen()` remains.

## 13. Sync-direction UI — Beta18

Beta18 added a real sync-direction indicator.

Symbols:

- `↑` = outbound/upload mutation currently being sent from PDA;
- `↓` = operational snapshot/revision data currently being downloaded to PDA;
- `↕` = upload and download are active concurrently;
- `✓` = no active transfer / ready.

Implementation:

- `SyncDirectionTracker.kt` is process-local runtime state;
- `BetaApiClient` marks genuine outbound business/account mutations;
- `OperationalSyncEngine` marks `sync_day` / `sync_bootstrap` downloads;
- Sync screen renders live direction state and the header sync chip can reflect active direction.

Do not make arrows decorative or infer direction merely from network connectivity.

## 14. Logging / diagnostics

Categories remain:

- MANUAL → `BÁO LỖI THỦ CÔNG`
- CRASH → `BÁO LỖI TỰ ĐỘNG`
- DAILY → `NHẬT KÝ ANDROID`

Manual report requires confirmation. Pending logs retry after valid session/connectivity. Local logs are deleted only after successful acknowledgement for their upload/event. Never expose secrets/private credentials in logs.

Crash logs were successfully used during S11 to identify the Beta15 SQLite lock incident; preserve remote diagnostic ability.

## 15. OTA / signing / release infrastructure — OWNER LOCK

OTA authority:

`Android → GAS update_check → Google Drive channel folder`

Beta reads Beta channel only. Stable reads Stable channel only.

Fixed signing certificate SHA-256:

`d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`

Never generate a replacement signer.

Four permanent GitHub signing secrets are configured and healthy. Their **names** may be documented, but never their values:

- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

Permanent workflows:

1. `App Fast Check`
2. `Release Preflight - Beta and Stable`
3. `Deploy Current GAS`
4. `Verify Google Apps Script Credentials`
5. `Verify OTA - Beta and Stable`

Release path:

Android-only:

`source → Fast Check → Release Preflight → exact signed Beta artifact → Drive Beta upload → Verify OTA → RELEASED`

GAS changed:

`source → Fast Check → Deploy Current GAS → Release Preflight → exact signed Beta artifact → Drive Beta upload → Verify OTA → RELEASED`

Do not rebuild/re-sign after successful Preflight before publishing that candidate. Signed Stable validation artifacts are validation-only and are **not** permission to publish Stable.

## 16. Latest released Beta — 0.4.2-beta.18

Authoritative current source metadata:

- versionName: **`0.4.2-beta.18`**
- versionCode: **24**
- package: `vn.pickpack1291.app.beta.publicbeta`
- APK name: `pick-pack-1291-public-beta-v0.4.2-beta.18.apk`
- signed APK SHA-256: **`2b0ff097903c7d75cd8f5e9b84c003c07d0fbd5aaf82076d31b07e5aa8803911`**
- fixed signer unchanged
- main source head at release preparation: `660efe5483f1b245876255e1587cf407749c4ff9`

Verification:

- Beta18 App Fast Check run `32147412312`: PASS
- Beta18 Release Preflight run `32147686567`: PASS
- Beta17 → Beta18 OTA verification run `32148119037`: PASS
- live discovery/download PASS
- SHA PASS
- package/version PASS
- fixed signer PASS
- self-update false PASS
- opposite Stable-channel isolation PASS

Stable remains **UNPUBLISHED / UNTOUCHED** by owner promotion.

Temporary observability PRs used for Beta18 CI/OTA verification were closed without merge.

## 17. Release sequence during S11

### Beta12/Beta13/Beta14

- S12 server report aggregation optimized current-day reporting.
- S13 introduced shared MNV-session history and server audit projection.
- S14 added screen-result cache/warming and corrected real-PDA scan/search sizing, but it remained screen-result caching rather than true local-first.

### Beta15/Beta16

- introduced 45-day local-first SQLite/revision model;
- Report date selector from cache;
- compact/restyled scan fields;
- Beta15/Beta16 exposed SQLite lock/reconcile risks on real PDA.

### Beta17

Emergency/root crash recovery release:

- fixed SQLite concurrency/locking architecture;
- moved reconciliation off UI thread;
- prevented local-cache failures from crashing app;
- fixed reconciliation self-loop;
- server compatibility gate allowed vulnerable clients to survive long enough for OTA.

### Beta18

Light navigation/sync-status release:

- real `↑ / ↓ / ↕` sync direction;
- dual-edge swipe back;
- active parent-tab tap resets child screen to parent root.

## 18. Current source-transform chain / technical debt

Android authenticated UI is still produced by assertion-based build-time transforms.

Current chain includes:

- `tools/apply_s10_ui_patch.py`
- `tools/apply_s11_compact_report_patch.py`
- `tools/apply_s12_real_pda_patch.py`
- `tools/apply_s12_compile_hotfix.py`
- `tools/apply_s13_shared_history_ui_patch.py`
- `tools/apply_s14_device_cache_scan_patch.py`
- `tools/apply_s15_local_first_ui_patch.py` + wrapper
- `tools/apply_s17_sqlite_recovery_ui_patch.py`
- `tools/apply_s18_sync_navigation_patch.py`

`app/build.gradle.kts` registers these as generation inputs and current Beta metadata is 0.4.2-beta.18 / 24.

Risks:

- transform anchors can break after base Kotlin edits;
- fix the first/root transform or compiler error, not cascading errors;
- a deliberate future refactor may fold patches into canonical source, but only with identical behavior and full CI/device acceptance.

GAS also uses transform-style deployment patches. Do not casually rewrite canonical GAS without respecting the deployment chain and live health gates.

## 19. Known process caveats / failures not to repeat

- Do not use `./gradlew`; workflow uses setup-gradle + `gradle`.
- Do not ask owner to use local CLI.
- Do not embed giant source patches in workflow YAML.
- Do not generate a new signer.
- Do not rebuild between successful signed Preflight and publish.
- Do not publish Stable because a Stable validation artifact exists.
- Do not make local cache authoritative for resource/mutation decisions.
- Do not return Report/History to screen-by-screen blocking network loads.
- Do not remove SQLite failure guards/retry behavior.
- Do not remove Beta15/Beta16 recovery compatibility without deliberate migration verification.
- Do not create permanent per-release observer workflows; temporary observer PRs are acceptable and must be closed without merge.
- Release Preflight reruns after a live-gate failure can unexpectedly rebuild/re-sign; future hardening may separate live gates from Android signing, but do not change release workflow casually.
- Main `ops/beta-ota-verify-trigger.txt` can remain older because release verification has been performed on temporary observer branches; do not mistake an old main trigger file for the actual published OTA state. The Drive channel + live OTA verification is authoritative for published version.

## 20. Immediate next-session acceptance priorities

S12 should wait for owner command after reading handover. If owner continues Beta18 acceptance, prioritize real PDA checks:

1. Confirm Beta18 installs/launches without any recurrence of SQLite crash loop.
2. Open Report repeatedly after local sync; it should render immediately from local data.
3. Verify Report date selector contains exactly cached dates and defaults to N.
4. Change N or N-1 from another account/PDA and confirm other foreground PDA converges quickly without full 45-day reload.
5. Confirm expired oldest date disappears locally when retention window advances.
6. Observe Sync screen during a mutation: `↑`; during snapshot fetch: `↓`; overlapping: `↕`; idle: `✓`.
7. Verify left-edge and right-edge back gestures on real Newland PDA.
8. `Lịch sử → Chi tiết → tap Lịch sử` must return to shared-history root.
9. Verify explicit top/back gesture from history detail also returns to history root.
10. Continue Vào/Ra, Công nhật, PICK/PACK and resource exclusivity business acceptance.
11. Stable must remain untouched unless owner explicitly commands promotion.

## 21. Open decisions / backlog

No owner decision is currently blocking Beta18 operation.

Possible later work, only on owner command:

- controlled refactor to remove transform-anchor debt;
- release-workflow hardening so a gate-only retry cannot rebuild Android candidates;
- performance measurement of first bootstrap vs steady-state on multiple real PDAs;
- eventual removal of vulnerable-client compatibility gate after migration is confirmed;
- Stable promotion only after explicit owner acceptance.

## 22. Session-close state

No release job is intentionally left half-complete.

**Beta18 is the current published/OTA-verified Beta. Stable is not promoted.**

S12 must read the required files, acknowledge project state, then wait for a new owner command.
