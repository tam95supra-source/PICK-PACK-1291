# HANDOVER CURRENT — PICK PACK 1291

Status: **ACTIVE / cumulative / authoritative**  
Last updated: **2026-08-18 17:03 +07:00 (Asia/Bangkok)**  
Closed working session: **S10**  
Next session: **S11**  
Latest published Beta: **0.4.2-beta.11 / versionCode 17**

> **NEW-CHAT STOP RULE:** S11 must first read this file, `docs/handovers/HANDOVER_S10_2026-08-18.md`, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/ADMIN_ACCOUNT_RULES.md`, `docs/BUILD_RELEASE_PLAYBOOK.md` and `docs/HANDOVER_POLICY.md`. After reporting that the state is understood, **WAIT FOR A NEW OWNER COMMAND**. Do not build, deploy, edit Sheet, publish OTA, promote Stable or change architecture merely because the session opened.

## 1. Project objective and architecture — OWNER LOCK

Android APK for Pick Pack 1291 operational workflows.

Official architecture:

`Android App ↔ Google Apps Script Web App ↔ Google Sheets`

- Google Sheets is operational source of truth.
- Google Apps Script is the transaction/API bridge tied to the workbook.
- GitHub is source/CI/release infrastructure only.
- No Supabase/Firebase/Neon/Postgres/Cloudflare backend/storage/another DB/auth/sync authority without explicit owner approval.
- Beta is full-function and uses real business rules/data.
- Drive mutations remain inside the official Pick Pack 1291 project tree.

## 2. Owner workstation constraint — OWNER LOCK

Owner's company-managed workstation cannot run local CLI.

Never ask owner to run CMD/PowerShell/Terminal/bash/git/gh/clasp/adb/Gradle/npm/npx/Java/keytool/OpenSSL or similar commands. CLI/build/sign/deploy work is handled by GitHub Actions or assistant-controlled tooling. Browser/UI-only owner setup is preferred.

## 3. Authoritative workbook and catalogs

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

### `Danh mục` namespace rule

Headers follow **`SHEET_FIELD` semantics**.

- Use only the matching sheet + editable-field catalog.
- Never borrow across sheets because labels look similar.
- System-owned statuses are not selectable in contexts where the user cannot edit them.
- Required selects do not expose a decorative blank/dash option.
- Required selects must resolve to a valid matching catalog before save.
- Preserve explicit business exceptions such as optional User Pick.

## 4. Admin account namespace — OWNER LOCK

`Danh sách Admin` is specialized and not a staff-position catalog.

Allowed Admin `Vị trí` values exactly:

- `superadmin`
- `admin`
- `user`

Mapping:

- SUPERADMIN → `superadmin`
- ADMIN → `admin`
- USER → `user`

Never populate Admin position from `Danh mục` or staff catalogs. Backend derives/validates position from role. Normal account creation cannot create another SUPERADMIN unless owner explicitly changes the rule. Account reset Mail remains supported.

## 5. Business invariants

- `MNV` is the business key.
- Session key: `MNV + business_date`.
- State machine: `NOT_ENTERED → ACTIVE → ENDED`.
- Once ENDED, normal flow cannot re-enter on the same business date.
- Mutations use immutable/idempotent `event_id`.
- Exclusive resources are race-safe; exactly one winner.
- Resource changes are atomic; failure retains the previous resource.
- Operational state remains server/Sheet authoritative.

### PICK / PACK

- PICK requires PDA.
- User Pick is optional.
- PDA uses last 5 serial digits + validated suggestions; ambiguous duplicate suffixes cannot be accepted as unique.
- New PDA assignment obeys master availability/active state rules.
- PACK preserves Bàn Pack + mapped User Pack bundle/exclusivity.
- Daily User Pick/User Pack consumption remains used after release/change/EXIT unless authorized reuse applies.

### ENTER / EXIT

- Business timezone Asia/Bangkok.
- Shift choices remain `Ca 1`, `Ca 2`, `HC`/`Ca HC` according to route/UI mapping.
- Work choice `PICK | PACK | KHÔNG`.
- PICK requires PDA; User Pick optional.
- PACK requires valid Bàn Pack + mapped User Pack.
- KHÔNG uses no operational resource.
- OPEN Công nhật blocks EXIT.
- EXIT releases resources still owned; previously returned PDA does not block EXIT.

### Công nhật

- USER/Điều phối cannot operate Công nhật.
- ADMIN/SUPERADMIN operate under correction-age permissions.
- Create requires ACTIVE session, valid category and no overlap.
- Resource policy supports `GIỮ` / `TRẢ`.
- OPEN Công nhật blocks EXIT.
- Accepted MNV is immutable.
- Locked projection/schema remains in `05_BUSINESS_CONG_NHAT.md`.

## 6. Authentication / role / session

Roles: SUPERADMIN, ADMIN, USER. Backend enforcement is mandatory.

Credential model:

- salted PBKDF2-HMAC-SHA256 verifier
- challenge/HMAC login proof
- plaintext password is not sent directly to GAS
- no actual passwords/verifiers/private tokens/signing private material in public repo/handover

Session model: **`SINGLE_ACTIVE_DEVICE_V1`**.

- Session survives normal app/process closure on the same installation.
- No routine 12-hour forced logout.
- Login on another installation replaces the same account's active server session.
- Old device is rejected at next protected API/sync opportunity.
- Logout/password reset/security changes may invalidate session.

Forgot-password remains generic externally, rate-limited and routed to configured account Mail.

## 7. UI / UX — latest authoritative state

Read `docs/UI_UX_SYSTEM.md`.

### Visual family

- Modern enterprise blue / indigo / violet gradient system.
- Exactly 7 theme swatches through centralized `ThemeManager`.
- No grey elevation/shadow haze on routine rounded surfaces; use clean white/soft theme surfaces and subtle outlines.

### Persistent shell

Bottom tabs exact order:

`Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`

One persistent authenticated Activity. Root-tab switches update in place with no artificial transition delay.

### Header

Current identity shows only:

`Chào buổi <sáng/trưa/chiều/tối>, <Họ tên>`

Greeting is based on the PDA's actual local clock. Do not show login ID, role, position or avatar placeholder. `Mạng / Đồng bộ / Service` stays compact and persistent.

### Inner screens — latest owner correction

- Keep back navigation where needed.
- Do not show a second text title (`BÁO CÁO`, `CÔNG NHẬT`, `QUÉT QR NHÂN SỰ`, etc.) beneath the greeting/status area.
- Compact header/body spacing to increase usable PDA viewport.
- Scanner/search fields carry contextual instructions and are deliberately taller; current target ~72dp minimum height.
- Remove redundant `Mã nhân viên` / scan instruction labels outside the scan input when placeholder already explains the purpose.

Current contextual placeholders include:

- `Scan / Nhập mã nhân viên để ghi nhận ra ca / vào ca`
- `Scan / Nhập mã nhân viên để ghi nhận công nhật`
- `Scan / Nhập mã nhân viên để quản lý tài nguyên`
- `Scan / Nhập mã nhân viên, họ tên để tìm kiếm`

Hardware Enter/OK executes scanner flows; no redundant `Kiểm tra` button.

### Staff / phone

S10 normalized existing staff phone values so known legacy 9-digit values regained leading `0`; Sheet column is kept as text. App normalizes legacy values and validates 10 digits beginning with `0` on save.

### History

Operational History view with total/completed/needs-attention summary, filter, grouped activity, semantic status/icons and friendly errors instead of raw `PP_*` codes.

### Sync

Operational Sync dashboard with network/sync/pending status, useful refresh info, channel/version and `LÀM MỚI TRẠNG THÁI`; no protocol/revision jargon.

## 8. Report layout — Beta11 owner correction

### Bordered tables

Report matrices must have visible borders between cells. No floating unseparated numbers.

### Main manpower matrix row order

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

Supplier columns are dynamic by relevant data, canonical order when present:

`Inhouse, NLV, VW, MP, MGL, HGP, HAD, Tổng`

**SUPERSEDED:** older rule `Phúc Long before Kéo hàng` is no longer valid. Latest owner reference places **Phúc Long after Packer and immediately before Tổng**.

### Tenure

Separate bordered matrices:

- `Thâm niên Picker`
- `Thâm niên Packer`

`Nhân sự mới` = tenure ≤ 30 days. `Nhân sự cũ` = tenure > 30 days.

### Hỗ trợ bộ phận khác

- Only Công nhật explicitly marked **Khấu trừ nhân sự = Có** in selected shift scope.
- Same person/support type de-duplicated in matrix.
- Deducted staff removed from effective Picker/Packer tenure counts.
- Entire support block hidden when deducted total = 0.
- When support exists, show post-deduction Picker/Packer remainder with old/new split.

Shift scopes:

- `Ca 1 + Ca HC`
- `Ca 2`
- `Cả ngày`

Beta11 implementation composes `report_daily` + `list_sessions`; ADMIN/SUPERADMIN also loads permission-restricted `list_labor` for deducted-support details. No GAS change/deploy was required for Beta11.

## 9. Logging

Categories:

- MANUAL → `BÁO LỖI THỦ CÔNG`
- CRASH → `BÁO LỖI TỰ ĐỘNG`
- DAILY → `NHẬT KÝ ANDROID`

Manual send requires confirmation. Local logs delete only after successful acknowledgement for their upload/event. Pending crash/daily logs retry after restored session. Redact secrets/private data where applicable.

## 10. OTA / signing / release infrastructure

OTA authority:

`Android → GAS update_check → Google Drive channel folder`

Beta only reads Beta channel; Stable only reads Stable channel. GitHub Releases are not steady-state OTA authority.

### Fixed signer

SHA-256:

`d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`

Never generate a replacement signer.

### Four GitHub signing secrets — confirmed permanent setup

- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

Confirmed working during S10. Do not recreate/rotate per release. Emergency encrypted Drive recovery is fallback only if secrets are lost/corrupted.

Release Preflight builds/signs Beta + Stable technical candidates using the fixed signer; a signed Stable validation artifact is **not permission to publish Stable**.

### Permanent workflows

1. `App Fast Check`
2. `Release Preflight - Beta and Stable`
3. `Deploy Current GAS`
4. `Verify Google Apps Script Credentials`
5. `Verify OTA - Beta and Stable`

Android-only Beta path:

`source → Fast Check → Release Preflight(build + signing) → exact signed Beta artifact → Drive Beta upload → Verify OTA → RELEASED`

Android + GAS path:

`source → Fast Check → Deploy Current GAS → Release Preflight → exact signed Beta artifact → Drive Beta upload → Verify OTA → RELEASED`

No rebuild/re-sign between successful Preflight and publish.

## 11. Latest published Beta — 0.4.2-beta.11

- VersionCode: **17**
- Package: `vn.pickpack1291.app.beta.publicbeta`
- APK: `pick-pack-1291-public-beta-v0.4.2-beta.11.apk`
- Signed SHA-256: `95385b7929dcbdded8e09ad7f402b93e6a2b780a97449698ade17f538243d4f1`
- Fixed signer verified
- Source release-preparation commit: `a76267a72f5e24bf2c9f621d3ec2737fb274c0cf`
- OTA trigger commit: `759bfa10b0f0eb155f8a87870128c5c249937bcd`

Beta11 gates passed:

- live GAS health + Beta/Stable isolation
- Beta Release + Stable Release compile
- package/version validation
- four signing secrets detected
- automated signing of exact validated candidates
- fixed signer validation
- Beta10 → Beta11 live discovery
- live downloaded APK SHA match
- package/version match
- fixed signer match
- Beta11 self-update false
- Stable isolation

### Stable

**NOT PROMOTED.** Stable publish requires owner-approved Beta soak/business acceptance and an explicit Stable-publish command.

## 12. S10 completed work

### Beta10

- removed grey rounded-surface haze
- one-line local-time greeting header
- removed user/position from header
- required staff selects without decorative dash
- fixed phone leading zero in Sheet/app
- redesigned History
- redesigned Sync
- completed one-time GitHub signing-secret setup

### Beta11

- removed redundant inner-screen title text
- enlarged contextual scan/search fields
- removed redundant external scan labels/instructions
- tightened spacing for PDA viewport
- report cell borders
- report layout based on owner reference
- separate Picker/Packer tenure matrices
- deducted-support matrix/summary with hide-on-zero
- new report row order with Phúc Long after Packer before Tổng

Temporary observability PRs used to retrieve CI runs were closed without merge after successful verification; no per-release observer workflow was added.

## 13. Current state / next-session priorities

No release task is half-complete. Beta11 is published and OTA-verified; Stable remains unpublished.

Next owner-driven real-PDA acceptance should check:

- inner titles gone while back control remains usable
- scan/search placeholder readability and field height
- compact spacing without clipping
- report borders legible on PDA
- report row/column order
- Picker/Packer new/old counts
- deducted support includes only `Khấu trừ nhân sự = Có`
- support block disappears completely at zero
- post-deduction Picker/Packer summary is correct
- continue QR/Công nhật/PICK/PACK/report business acceptance

## 14. Known risks / technical debt

- S10/S11 UI changes are applied through assertion-based build-time transforms: `tools/apply_s10_ui_patch.py` then `tools/apply_s11_compact_report_patch.py`. They currently pass CI but anchors can be fragile if base Kotlin changes. Future edits must preserve unique anchors or deliberately fold patches into source through a controlled change.
- Report composition now combines multiple API calls; test slow/unstable PDA networks for confusing mixed freshness.
- Detailed deducted-support composition uses permission-restricted `list_labor`; do not weaken backend authorization merely to expose it to unauthorized roles.
- Beta11 passed CI/OTA but still awaits owner real-device visual/business acceptance.

## 15. Known failures not to repeat

- Do not assume `./gradlew`; use setup-gradle + `gradle`.
- Do not embed giant source patches in workflow YAML.
- Use coherent standalone transform scripts/direct edits with unique asserted anchors.
- Fix first/root compile error, not cascades.
- Do not create per-release observer/status/finalizer workflows.
- Do not let CI self-edit workflow definitions.
- Do not hardcode stale Beta versions.
- Do not run full release/live gates for ordinary small non-release edits.
- Do not regenerate signing identity.
- Do not return to manual recovery signing while the four GitHub secrets are healthy.
- Do not assume GAS OAuth has Drive upload scope.
- Do not explore unapproved external backends.
- Handover/docs housekeeping remains after OTA PASS, not on release critical path.

## 16. Authoritative references for S11

Read together:

- `docs/HANDOVER_CURRENT.md`
- `docs/handovers/HANDOVER_S10_2026-08-18.md`
- `AGENTS.md`
- `ARCHITECTURE_GUARDRAILS.md`
- `docs/UI_UX_SYSTEM.md`
- `docs/ADMIN_ACCOUNT_RULES.md`
- `docs/BUILD_RELEASE_PLAYBOOK.md`
- `docs/HANDOVER_POLICY.md`
- business docs for Vào/Ra, resources, Công nhật and roles/accounts
