# HANDOVER CURRENT — Pick Pack 1291

Status: **ACTIVE / cumulative / authoritative**  
Last updated: **2026-08-18 12:42 +07:00 (Asia/Bangkok)**  
Closed working session: **S09**  
Next session: **S10**  
Latest release: **Beta 0.4.2-beta.9 / versionCode 15**

> **NEW-CHAT STOP RULE:** S10 must first read this file, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/ADMIN_ACCOUNT_RULES.md`, `docs/BUILD_RELEASE_PLAYBOOK.md` and `docs/HANDOVER_POLICY.md`. After reporting that the state is understood, **WAIT FOR A NEW OWNER COMMAND**. Do not build, deploy, edit Sheet, publish OTA, promote Stable or change architecture merely because this handover was opened.

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

## 3. Authoritative workbook and tabs

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
- If a catalog does not exist for a field, do not invent or borrow one unless the owner explicitly defines a fallback.

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
- Normal account creation through the app cannot create another `SUPERADMIN` unless owner explicitly changes this rule.
- The allowed set may change **only after an explicit owner decision**.

`Danh sách Admin` also has a `Mail` field for reset-password delivery. Existing accounts were initialized to the approved reset address; accounts can change their configured reset mail through the app subject to permissions.

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

## 7. UI / UX — current approved system

Authoritative details: `docs/UI_UX_SYSTEM.md`.

Current family is the owner-approved modern enterprise blue/indigo/violet system with centralized 7-color theming. It supersedes old fixed teal/Mẫu 2 implementations.

### Global shell

Bottom tabs, exact order:

`Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`

- One persistent authenticated Activity shell.
- Tab changes swap content in place.
- No Activity start/finish per root tab.
- No artificial fade/cross-fade transition delay.
- Bottom navigation remains mounted.

### Header after real-device S09 correction

Do not display duplicate tab titles such as `NGHIỆP VỤ`, `NHÂN SỰ`, `LỊCH SỬ`, `ĐỒNG BỘ`, `CÀI ĐẶT` in the gradient header.

Identity header shows exactly three constrained, left-aligned lines:

1. Họ tên
2. Vị trí
3. Login/user ID directly

- No avatar placeholder if no real user photo exists.
- No `Tài khoản:` prefix.
- Long values must ellipsize/fit without breaking the header.
- Right-side status is compact Mạng / Đồng bộ / Service information only.
- Connection status is persistent Activity state; changing tabs must not reset it to `Mạng: Đang kết nối`.

### Nghiệp vụ / inner screens

- Work cards use equal size/radius/padding/icon hierarchy.
- Semantic Android vector icons are required for tabs/cards/titles/actions.
- Design system applies inside QR, Công nhật, Tài nguyên, Báo cáo, Nhân sự, Lịch sử, Đồng bộ, Settings/admin — not dashboard only.
- Settings has no duplicate `Đồng bộ dữ liệu` section because Đồng bộ has its own tab.
- 7 theme swatches remain exactly one horizontal row, no names/no wrapping.

### Staff performance

- Full staff master remains searchable from local cache.
- Staff UI renders incrementally/lazily instead of constructing thousands of cards synchronously on tab click.
- Search still covers the full local master cache.

### User-facing copy rule

Visible text is only information useful to ordinary users.

Do not expose AI/developer/system-design commentary such as:

- ACK/protocol explanations
- server/master revision text
- cache/Sheet architecture explanations
- implementation notes like `Không cần nút kiểm tra`
- design notes like `Màu giao diện được đổi...`

Technical details belong in logs/docs/diagnostics, not routine screens.

## 8. Notification / input rules

- Routine top notifications auto-hide after about 3 seconds.
- Maximum 3 notifications; new items evict the oldest when over limit.
- Routine not-found/success/status states do not use blocking OK dialogs.
- Yes/No confirmations are reserved for consequential actions and owner-approved cases.
- Manual diagnostic log submission requires Yes/No confirmation.
- MNV/PDA scanner flows execute on hardware/keyboard Enter/OK; no redundant `Kiểm tra` button.

## 9. Logging

Categories:

- MANUAL -> `BÁO LỖI THỦ CÔNG`
- CRASH -> `BÁO LỖI TỰ ĐỘNG`
- DAILY -> `NHẬT KÝ ANDROID`

Rules:

- Secrets/private data are redacted as applicable.
- Manual send requires confirmation.
- MANUAL/CRASH/DAILY local file is deleted **only after successful server acknowledgement for that upload/event**.
- Pending crash/daily logs are also attempted after restored session, not only a fresh login.
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
- catalog fields exposed to Android master snapshot according to strict namespace rules
- Admin position backend lock

GAS source changes do **not** auto-deploy. Live mutation uses explicit permanent `Deploy Current GAS` workflow and must pass post-deploy health/reset/OTA-isolation gates.

## 12. OTA release state

### Published Beta — `0.4.2-beta.9`

- Package: `vn.pickpack1291.app.beta.publicbeta`
- VersionCode: `15`
- APK: `pick-pack-1291-public-beta-v0.4.2-beta.9.apk`
- SHA-256: `6c96a9415299bd11f73ed21e314fb354c530c093f30ae1e23bfa7332d0ff3b6b`
- Fixed signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- Authority/source: GAS `update_check` -> Google Drive Beta folder.

Beta9 gates passed before publication:

- Beta Debug + Stable Debug
- explicit GAS deploy and live validation for S09 backend/catalog changes
- Release Preflight: architecture/UX, live GAS/Drive channel isolation, Beta Release + Stable Release, metadata
- fixed signing identity verification
- Beta8 -> Beta9 update discovery
- live downloaded APK SHA match
- Beta9 self-update false
- Stable isolation

### Stable

Not promoted. Stable requires owner-approved Beta soak/business acceptance and explicit owner command.

## 13. Build / release optimization — FINAL S09 SETUP

Authoritative playbook: `docs/BUILD_RELEASE_PLAYBOOK.md`.

Permanent workflows are now exactly:

1. `App Fast Check`
2. `Release Preflight - Beta and Stable`
3. `Deploy Current GAS`
4. `Verify Google Apps Script Credentials`
5. `Verify Beta OTA`

### Fast Check optimization

- Detects change scope first.
- App/Gradle change: static guards + Beta Debug + Stable Debug.
- GAS-only change: static/GAS syntax only; skips Android SDK/Gradle.
- Documentation/handover-only changes no longer trigger Android builds.
- Stale older Fast Check is cancelled when a newer source commit arrives.

### Release Preflight optimization

- Live GAS/Drive gates and Android Release build run in parallel.
- Beta Release + Stable Release are built once with cache/parallel enabled.
- Exact unsigned Beta candidate + release metadata are uploaded as artifact.
- Signing/publish must reuse that artifact; **do not rebuild before OTA**.

### Permanent Beta OTA gate

`Verify Beta OTA` replaces per-release one-shot verifiers/status probes. After Drive upload, update permanent `ops/beta-ota-verify-trigger.txt` with previous version, target version and expected SHA.

It verifies live discovery, downloaded SHA, package/version, fixed signer, self-update false and Stable isolation without committing status files to `main`.

### Critical path

Android-only Beta:

`source -> Fast Check -> Release Preflight -> reuse artifact -> sign -> Drive upload -> Verify Beta OTA -> RELEASED`

Android + GAS:

`source -> Fast Check -> Deploy Current GAS -> Release Preflight -> reuse artifact -> sign -> Drive upload -> Verify Beta OTA -> RELEASED`

Handover/docs/history cleanup happen **after OTA PASS**, not before release completion.

## 14. Signing automation status / remaining release bottleneck

Four GitHub signing secrets are still not confirmed complete:

- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

Until owner later chooses to configure them browser-only, use only the existing official encrypted signing recovery material inside the approved project Drive tree.

Current fastest safe fallback:

- reuse Preflight artifact
- decrypt/sign temporarily in assistant-controlled runtime
- verify fixed signer
- delete plaintext signing material immediately
- upload via approved Drive connector
- run permanent Beta OTA gate

Do not create a temporary Apps Script signing bridge, temporary signing workflow, observer/status workflow or replacement signing identity.

Configuring the four signing secrets is the only major remaining step toward true one-click CI signing; it is a backlog item, not permission to change signer.

## 15. Known build failures already learned — DO NOT REPEAT

- Do not assume `./gradlew`; repo uses `gradle/actions/setup-gradle` + `gradle`.
- Do not embed giant multiline Kotlin/Python patches inside workflow YAML.
- Do not dispatch a workflow in the same commit that first creates it.
- Do not create observer/status jobs that write to `main`.
- Do not let CI self-edit `.github/workflows`.
- Do not hardcode old Beta versions in workflow logic.
- Do not run full release/live probes for every small edit.
- Do not repeatedly bootstrap Android SDK if exact preinstalled tools exist.
- Do not assume GAS OAuth token has Drive upload scope.
- Do not explore historical/unapproved external backends during signing/release troubleshooting.
- Do not put handover/docs finalization on the OTA critical path.

## 16. Next-session priorities / acceptance

S10 starts by reading authoritative files and waiting for the owner's next command.

Likely owner-driven next work after installing/testing Beta9:

- review real-device screenshots/spacing of corrected UI
- verify tab switching no longer resets network status
- verify Staff tab load responsiveness with large master data
- verify strict catalog selections in employee/resource/admin forms
- verify Admin roles/positions remain only superadmin/admin/user
- continue business-flow PDA testing for QR, Công nhật, PICK/PACK and reports

Do not promote Stable without explicit owner approval.

## 17. Authoritative references

Read together:

- `AGENTS.md`
- `ARCHITECTURE_GUARDRAILS.md`
- `docs/UI_UX_SYSTEM.md`
- `docs/ADMIN_ACCOUNT_RULES.md`
- `docs/BUILD_RELEASE_PLAYBOOK.md`
- `docs/HANDOVER_POLICY.md`
- latest immutable session snapshot under `docs/handovers/`
