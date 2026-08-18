# HANDOVER CURRENT — Pick Pack 1291

Status: **ACTIVE / cumulative / authoritative**  
Last updated: **2026-08-18 16:27 +07:00 (Asia/Bangkok)**  
Last closed snapshot: **S09**  
Current working session: **S10**  
Latest release: **Beta 0.4.2-beta.10 / versionCode 16**

> **NEW-CHAT STOP RULE:** first read this file, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/ADMIN_ACCOUNT_RULES.md`, `docs/BUILD_RELEASE_PLAYBOOK.md` and `docs/HANDOVER_POLICY.md`. After reporting that the state is understood, **WAIT FOR A NEW OWNER COMMAND**. Do not build, deploy, edit Sheet, publish OTA, promote Stable or change architecture merely because this handover was opened.

## 1. Architecture — OWNER LOCK

Official operational architecture:

`Android App ↔ Google Apps Script Web App ↔ Google Sheets`

- Google Sheets is the operational source of truth.
- Google Apps Script is the transaction/API bridge tied directly to the workbook.
- GitHub is source/CI/release infrastructure only.
- Do not add/migrate authority to Supabase, Firebase, Neon/Postgres, Cloudflare backend/storage, another DB/backend/auth/sync/service without an explicit owner command.
- Beta is full-function and uses real business rules/data paths for acceptance testing.
- Drive mutation stays inside the official `PICK PACK 1291 - CHÍNH THỨC` tree.

## 2. Owner workstation constraint — OWNER LOCK

The owner's company-managed computer cannot run CMD/PowerShell/Terminal/CLI.

- Never instruct owner to run git/gh/clasp/adb/Gradle/Node/npm/npx/Java/keytool/OpenSSL or similar local CLI.
- Move CLI work to GitHub Actions or assistant-controlled tooling.
- Owner-facing setup uses browser/UI only where possible.

## 3. Authoritative workbook and catalogs

Workbook: `DỮ LIỆU THEO NGÀY`.

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

### `Danh mục` namespace rule

Headers follow `SHEET_FIELD` semantics and are used as catalogs only for the **matching sheet + matching editable field**.

- Do not borrow values across sheets because names look similar.
- System-owned/status values are not offered in operational contexts where users cannot edit them.
- Example: `DANH SÁCH PDA_Tình trạng` is a PDA-management state and is **not selectable when assigning a PDA to PICK**.
- If a catalog does not exist for a field, do not invent or borrow one unless owner explicitly defines a fallback.
- Required select fields do not expose a decorative blank/dash option; they must resolve to a valid matching catalog value before save.
- Preserve explicit business-rule exceptions such as optional User Pick.

## 4. Admin account namespace — OWNER LOCK

`Danh sách Admin` is specialized and **not** an employee-position catalog.

`Vị trí` is fixed system-wide to exactly:

- `superadmin`
- `admin`
- `user`

Rules:

- Never read Admin `Vị trí` from `Danh mục`.
- Never fall back to `DANH SÁCH NHÂN SỰ_Vị trí chính` or any other catalog.
- Backend derives/validates Admin position from role rather than trusting arbitrary client values.
- Existing mapping: SUPERADMIN -> `superadmin`, ADMIN -> `admin`, USER -> `user`.
- Normal account creation through the app cannot create another `SUPERADMIN` unless owner explicitly changes this rule.
- The allowed set may change only after an explicit owner decision.

`Danh sách Admin` also has a `Mail` field for reset-password delivery.

## 5. Business invariants

- `MNV` is the business key.
- Session key: `MNV + business_date`.
- State machine: `NOT_ENTERED -> ACTIVE -> ENDED`.
- Once `ENDED`, normal flow cannot re-enter on the same business date.
- Mutations use immutable/idempotent `event_id`.
- Exclusive resources are race-safe; one winner only.
- Resource changes are atomic; failure retains the previous resource.
- Google Sheet/API remains authoritative for active session/resource state.
- Master/static data may be cached by revision; operational state remains server-authoritative.

### PICK / PACK

- PICK requires PDA.
- User Pick is **optional** and may be blank.
- PDA entry uses last 5 serial digits + validated suggestions; ambiguous duplicate suffixes are not accepted as unique.
- PACK keeps shift mapping to Bàn Pack + User Pack and exclusivity rules.
- New PDA assignment requires master state `HOẠT_ĐỘNG`; an already assigned PDA may continue if later set BẢO_TRÌ/KHÓA, but cannot be newly assigned.
- Used User Pick/User Pack stays consumed for the business day after release/change/EXIT unless authorized reuse applies.

### ENTER / EXIT

- Business timezone: Asia/Bangkok.
- Shifts: `Ca 1`, `Ca 2`, `HC`.
- ENTER work choice: `PICK | PACK | KHÔNG`.
- PICK requires PDA; User Pick optional.
- PACK requires valid Bàn Pack + mapped User Pack bundle.
- KHÔNG uses no operational resource.
- OPEN Công nhật blocks EXIT.
- EXIT releases resources still owned; prior PDA return must not make EXIT fail.

### Công nhật

- USER/Điều phối cannot operate Công nhật.
- ADMIN/SUPERADMIN can operate according to correction-age permissions.
- States: OPEN / COMPLETED / CANCELLED.
- Create requires ACTIVE work session, valid category and no overlap.
- Resource policy on create supports `GIỮ` / `TRẢ`.
- OPEN Công nhật blocks EXIT.
- MNV of accepted record is immutable.
- Google projection remains the locked 12-column schema documented in `05_BUSINESS_CONG_NHAT.md`.

## 6. Auth / role / session

Roles:

- `SUPERADMIN`
- `ADMIN`
- `USER`

Backend enforces permissions; hiding UI alone is never sufficient.

Credential model:

- salted PBKDF2-HMAC-SHA256 verifier
- challenge/HMAC login proof
- plaintext password is not sent directly to GAS
- do not store passwords, verifiers, OAuth credentials, signing material or private tokens in public repo/handover

Session model: `SINGLE_ACTIVE_DEVICE_V1`.

- Session survives normal app/process closure on the same installation.
- No routine 12-hour forced logout.
- Successful login on another installation/device replaces the same account's active server session.
- Old device is rejected on next protected API/sync opportunity.
- Logout/password-reset/security changes may invalidate session.

### Forgot password / Mail

- Public action: `forgot_password`.
- External response remains generic; no account-existence leak.
- Rate limit remains 5 minutes per login + device.
- Temporary reset credential remains valid for 2 hours.
- Reset email goes to that account's configured `Mail`.
- Successful temp-password login upgrades back to normal PBKDF2 verifier.
- Reset invalidates previous active session.

## 7. UI / UX — authoritative S10 state

Authoritative details: `docs/UI_UX_SYSTEM.md`.

Current family remains the owner-approved modern enterprise blue/indigo/violet system with centralized 7-color theming.

### Global shell

Bottom tabs, exact order:

`Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`

- One persistent authenticated Activity shell.
- Tab changes swap content in place.
- No Activity start/finish per root tab.
- No artificial fade/cross-fade transition delay.
- Bottom navigation remains mounted.

### Header — S10 supersedes S09 three-line identity rule

Top identity now shows **only**:

`Chào buổi <sáng/trưa/chiều/tối>, <Họ tên>`

- Greeting is based on the actual local clock on the PDA.
- Do not show user/login ID in the top header.
- Do not show position/role in the top header.
- No avatar placeholder without a real photo.
- No duplicate root-tab title in the gradient header.
- Right-side status remains compact Mạng / Đồng bộ / Service.
- Connection state persists across tab changes.

### Real-PDA surface correction

- Routine rounded cards/inputs/navigation use clean white/soft theme surfaces and subtle theme-tinted outlines.
- Avoid grey elevation/shadow haze around rounded surfaces.

### Nghiệp vụ cards

Equal component for:

- Quét QR nhân sự — Vào ca / ra ca
- Công nhật — Bắt đầu / hoàn thành
- Báo cáo nhân sự — Theo ca / theo ngày
- Tài nguyên — PDA / Pick / Pack

### Lịch sử — S10 redesign

- Summary counters: total / completed / needs attention.
- Filter: all / completed / needs attention.
- Recent activity grouped by date/time.
- Semantic action icons and status chips.
- Raw `PP_*` backend errors are translated into ordinary-user explanations instead of being the primary visible detail.

### Đồng bộ — S10 redesign

- Operational connectivity/sync dashboard rather than sparse raw key/value output.
- Shows network/sync/pending state, useful refresh information, channel/version and Service state.
- Explicit `LÀM MỚI TRẠNG THÁI` action while automatic foreground sync remains active.
- No internal protocol/revision jargon.

### Staff / phone correction — S10

- Full staff master remains searchable from local cache and lazily rendered.
- Existing `DANH SÁCH NHÂN SỰ` phone data was normalized on 2026-08-18: **100/100 existing 9-digit values received the leading `0`**.
- Phone column is formatted as text to preserve leading zero.
- App normalizes legacy 9-digit numbers and requires 10 digits beginning with `0` on save.

### User-facing copy

Only ordinary-user useful text. Do not expose ACK/protocol/cache/revision/design/developer commentary in routine UI.

## 8. Notifications / input

- Routine top notifications auto-hide after about 3 seconds.
- Maximum 3 notifications; new items evict oldest over the limit.
- Routine not-found/success/status states do not use blocking OK dialogs.
- Yes/No confirmations are reserved for consequential actions and manual diagnostic log send.
- MNV/PDA scanner Enter/OK executes immediately; no redundant `Kiểm tra` button.

## 9. Logging

Categories:

- MANUAL -> `BÁO LỖI THỦ CÔNG`
- CRASH -> `BÁO LỖI TỰ ĐỘNG`
- DAILY -> `NHẬT KÝ ANDROID`

Rules:

- Secrets/private data are redacted as applicable.
- Manual send requires confirmation.
- MANUAL/CRASH/DAILY local file is deleted only after successful server acknowledgement for that upload/event.
- Pending crash/daily logs are attempted after restored session, not only fresh login.
- User-facing copy does not expose ACK jargon.

## 10. Reports

Keep active rules:

- no redundant `NGUỒN LỰC` / `THÂM NIÊN` title rows
- support block hidden when deducted support total is 0
- `Phúc Long` before `Kéo hàng`
- compact PDA-friendly spacing
- zero/all-zero display optimizations remain
- tables form one coherent block; avoid heavy rounded borders around every subtable

## 11. GAS live state

Live architecture remains `0.4.2 / APP_GSHEET` with:

- Sheet-read health
- `SINGLE_ACTIVE_DEVICE_V1`
- Drive-based `update_check`
- account-email forgot-password routing
- MailApp authorization
- strict catalog fields exposed to Android master snapshot
- Admin position backend lock

No GAS source change was required for Beta10; the existing live GAS remained authoritative. GAS source changes still require explicit `Deploy Current GAS` and post-deploy gates.

## 12. OTA release state

### Published Beta — `0.4.2-beta.10`

- Package: `vn.pickpack1291.app.beta.publicbeta`
- VersionCode: `16`
- APK: `pick-pack-1291-public-beta-v0.4.2-beta.10.apk`
- Drive file ID: `1x7DhEohCDuF2R7rUFDT5y1OI9KwtkD6n`
- Signed APK SHA-256: `690771122d7b597a19aaa3399bcc3ed6d84626e97db33c02ce58739f7353165f`
- Fixed signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- Authority/source: GAS `update_check` -> Google Drive Beta folder.

Beta10 scope delivered:

1. remove grey rounded-surface/elevation haze on real PDA
2. header now `Chào buổi ..., Họ tên` based on PDA local time; no user/position lines
3. required staff catalog selects no longer show decorative dash/blank option
4. staff phone leading zero fixed in existing Sheet data and app input/save flow
5. Lịch sử redesigned into useful summary/filter/grouped activity UI with friendly errors
6. Đồng bộ redesigned into useful operational dashboard

Beta10 release gates passed:

- live GAS/Drive Beta+Stable channel isolation
- Beta Release + Stable Release compile/package/version validation
- all four GitHub signing secrets detected
- automated signing of exact validated Beta + Stable artifacts
- fixed signer validation on both signed artifacts
- Beta9 -> Beta10 live discovery from GAS/Drive
- live downloaded Beta10 APK SHA match
- package/version match
- fixed signer match
- Beta10 self-update false
- Stable channel isolation

The permanent OTA verifier was corrected during S10 to accept the live GAS response contract `available / version_name / apk_url` while remaining backward-compatible with legacy field names.

### Stable

**Not promoted.** Stable release artifact may be built/signed for technical validation, but Stable publish requires owner-approved Beta soak/business acceptance and an explicit owner command.

## 13. Build / release — S10 automated signing state

Authoritative playbook: `docs/BUILD_RELEASE_PLAYBOOK.md`.

Permanent workflows:

1. `App Fast Check`
2. `Release Preflight - Beta and Stable`
3. `Deploy Current GAS`
4. `Verify Google Apps Script Credentials`
5. `Verify OTA - Beta and Stable`

### Four signing secrets — confirmed working

- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

They were proven in successful Beta10 Preflight. Normal releases no longer need the old manual recovery-signing flow.

Normal Android-only Beta path:

`source -> Fast Check -> Release Preflight(build + fixed signing) -> exact signed Beta artifact -> Drive Beta upload -> Verify OTA -> RELEASED`

Android + GAS path:

`source -> Fast Check -> Deploy Current GAS -> Release Preflight(build + fixed signing) -> exact signed Beta artifact -> Drive Beta upload -> Verify OTA -> RELEASED`

Rules:

- no rebuild/re-sign between Preflight and publish
- never generate a replacement signer
- Stable signed artifact is not permission to publish Stable
- emergency encrypted Drive signing recovery remains fallback only if GitHub secrets are lost/corrupted
- no temporary Apps Script signing bridge, external signing service, observer/status workflow or per-release signing workflow

## 14. Known failures already learned — DO NOT REPEAT

- Do not assume `./gradlew`; use setup-gradle + `gradle`.
- Do not embed giant multiline source patches in workflow YAML.
- Standalone source transforms/direct edits must use unique asserted anchors; fix the first/root error, not cascades.
- Do not dispatch a workflow in the same commit that first creates it.
- Do not create observer/status workflows writing `main`.
- Do not let CI self-edit workflow files.
- Do not hardcode old Beta versions.
- Do not run full release/live probes for tiny normal edits.
- Do not repeatedly bootstrap SDK when exact hosted tools exist.
- Do not assume GAS OAuth has Drive upload scope.
- Do not explore unapproved external backends during release troubleshooting.
- Do not put handover/docs finalization on OTA critical path.
- If OTA verifier fails, inspect the actual live GAS response contract before rebuilding/re-signing; Beta10 proved a verifier schema mismatch can occur while the published APK itself is correct.

## 15. Current acceptance priorities

After installing/testing Beta10 on the real PDA, owner-driven checks should focus on:

- confirm grey haze is gone across cards/inputs/nav on-device
- confirm greeting period changes correctly with PDA local clock and only name is shown
- confirm required staff selects have real values and no dash placeholder
- confirm leading `0` remains visible/editable/saved for phone numbers
- review redesigned Lịch sử readability and friendly failure text
- review redesigned Đồng bộ usefulness and refresh behavior
- continue QR/Công nhật/PICK/PACK/report business acceptance

Do not promote Stable without explicit owner approval.

## 16. Authoritative references

Read together:

- `AGENTS.md`
- `ARCHITECTURE_GUARDRAILS.md`
- `docs/UI_UX_SYSTEM.md`
- `docs/ADMIN_ACCOUNT_RULES.md`
- `docs/BUILD_RELEASE_PLAYBOOK.md`
- `docs/HANDOVER_POLICY.md`
- latest immutable session snapshot under `docs/handovers/`
