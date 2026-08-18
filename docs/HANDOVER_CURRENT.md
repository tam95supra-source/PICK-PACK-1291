# HANDOVER CURRENT — Pick Pack 1291

Status: **ACTIVE / cumulative / authoritative**  
Last updated: **2026-08-18 09:42 +07:00 (Asia/Bangkok)**  
Latest implementation checkpoint: **S07 — persistent tab shell, global copy rules, CI/release optimization**

> **NEW-CHAT RULE:** Read this file together with `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/BUILD_RELEASE_PLAYBOOK.md` and `docs/HANDOVER_POLICY.md`. Do not infer a new architecture or resurrect superseded UI/release decisions. On a new chat, after reading authoritative state, wait for a new owner command before mutation/release work.

## 1. Project / architecture — CHỐT

Operational architecture:

`Android App ↔ Google Apps Script Web App ↔ Google Sheets`

- Google Sheets is the operational source of truth.
- Apps Script is the transaction/API bridge tied directly to the workbook.
- GitHub is source/CI/release infrastructure only, not business datastore.
- Do **not** add/migrate authority to Supabase, Firebase, Neon/Postgres, Cloudflare backend/storage or another DB/backend/auth/sync/service unless the owner explicitly commands it.
- Beta is full-function and uses real business data/rules for acceptance testing.
- Drive mutation stays inside the official `PICK PACK 1291 - CHÍNH THỨC` tree.

## 2. Owner workstation constraint — CHỐT

The owner's company-managed computer cannot run local CMD/PowerShell/Terminal/CLI.

- Never instruct owner to run git/gh/clasp/adb/Gradle/Node/npm/npx/Java/keytool/OpenSSL or similar local CLI.
- Move command-line work to GitHub Actions/approved automation.
- Owner-facing setup uses browser/UI only where possible.

## 3. Authoritative workbook / main tabs

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

`Danh sách Admin` now has a **Mail** field. Existing accounts were initialized to the owner-approved reset address. Each account may change its own reset-mail address through the app; forgot-password delivery uses the configured email for that account.

Never store plaintext normal passwords in Sheets/repo/handover.

## 4. Business invariants — CHỐT

- `MNV` is the business key.
- Session key is `MNV + business_date`:
  `NOT_ENTERED -> ACTIVE -> ENDED`.
- Once `ENDED`, normal flow cannot re-enter on the same business date.
- Mutations use immutable/idempotent `event_id`.
- Exclusive resources are race-safe; one winner only.
- Resource change is atomic; failure keeps the previous resource assignment.
- Google Sheet/API is authoritative for active session/resource state.
- Master/static data can be cached locally by revision; operational state remains server-authoritative.

### PICK / PACK

- PICK requires PDA.
- **User Pick is optional** and may be blank. This supersedes the old requirement that User Pick was mandatory.
- PDA input uses last 5 serial digits + validated autocomplete/suggestions; ambiguous duplicate last-5 values must not be accepted as a unique selection.
- PACK keeps shift mapping to Bàn Pack + User Pack and exclusivity rules.

## 5. Roles / auth / session — CHỐT

Roles:

- `SUPERADMIN`
- `ADMIN`
- `USER`

Backend enforces permission. `CÔNG NHẬT` is currently ADMIN/SUPERADMIN according to app rules.

Credential/auth rules:

- salted PBKDF2-HMAC-SHA256 verifier
- login challenge/HMAC proof
- plaintext password is not sent directly to GAS
- never commit passwords, verifiers, OAuth credentials, signing secrets or private tokens

### Session model `SINGLE_ACTIVE_DEVICE_V1`

- Android persists session in private storage.
- Closing/killing/reopening app retains login on the same installation.
- No routine 12-hour forced logout.
- Successful login for the same account on another installation/device replaces the old active server session.
- Old device receives 401 on the next sync/API opportunity and must login again.
- Explicit logout/security/account/password-reset actions may invalidate session.

## 6. Forgot password / account mail — LIVE

Public route: `forgot_password`.

- User submits username.
- External response remains generic and does not reveal whether the account exists.
- Rate limit remains 5 minutes per login + device.
- Active account receives a temporary reset credential valid for 2 hours.
- Reset mail goes to the account's configured **Mail** field.
- First successful temp-password login upgrades back to normal PBKDF2 verifier.
- Reset invalidates the previous active session.
- MailApp permission is already authorized.

Settings exposes `ĐỔI MẬT KHẨU` and `ĐỔI MAIL` side by side, equal-width and single-line.

## 7. UI / UX — CURRENT OWNER-APPROVED SYSTEM

**SUPERSEDES** earlier `Minimal Teal Corporate / Mẫu 2`, fixed teal assumptions and the intermediate unequal-hero-card dashboard.

Authoritative specification: `docs/UI_UX_SYSTEM.md`.

Owner approved a unified modern enterprise design family:

- blue / indigo / violet visual language with centralized theme tokens
- 7 selectable theme colors remain supported
- all 7 swatches always on one horizontal row, no names, no wrap
- work cards are equal components
- semantic icons throughout tabs/cards/titles/actions
- the approved visual language applies to inner workflows as well as outer screens

### Authenticated header

Do not use `PICK PACK 1291` as the routine top tab title.

Header identity area uses separate constrained lines:

1. Họ tên
2. Vị trí
3. `Tài khoản: <login>`

Compact right-side status area is reserved for user-facing:

- Mạng
- Đồng bộ
- Service

No revision/server-sequence/API jargon in routine UI.

### Fixed five-tab navigation

Exact order:

`Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`

S07 functional refactor changed authenticated navigation to **one persistent `OperationsActivity` shell**:

- Business and the other four tabs no longer cross Activities.
- Tab switch no longer uses `TransitionManager/Fade`.
- Content swaps in-place immediately.
- Bottom nav remains mounted; selected state updates in-place.
- Authenticated login/restore enters the BUSINESS shell and closes the login Activity.

S07 Beta+Stable **release compilation passed** for this refactor.

### User-facing copy rule — global

Visible text is only information useful to ordinary users.

Do not insert AI/developer/system-design commentary into screens, including:

- ACK/request protocol explanations
- server/master revision numbers
- cache/Sheet architecture explanations
- `Không cần nút kiểm tra`
- `Màu giao diện được đổi trong tab Cài đặt`
- explanations of implementation decisions

Technical details belong in diagnostics/docs/logs, not routine UI.

Settings no longer duplicates a `Đồng bộ / dữ liệu` section because `Đồng bộ` has its own tab.

### Current visual implementation caveat

The owner-approved multi-screen mockup family is the **visual target/spec**. S07 implemented the global shell/navigation/copy behavior and equal work-card structure, but future visual work must continue to align every inner screen pixel/layout component with `docs/UI_UX_SYSTEM.md`; do not falsely assume every mockup detail is already implemented just because the behavioral shell is complete.

## 8. Notifications / interaction — CHỐT

- Routine notifications appear at top of screen for about 3 seconds.
- Maximum 3 notifications; newer items evict the oldest when over limit.
- Routine not-found/success/status messages should not require an OK dialog.
- Yes/No confirmations are reserved for consequential actions or owner-approved cases.
- Manual diagnostic-log submission requires Yes/No confirmation.
- Scanner-oriented MNV input triggers on PDA/keyboard Enter/OK; no redundant `Kiểm tra` button is required.

## 9. Staff / history / sync / settings

### Nhân sự

- full staff list available from local master data
- search MNV/name
- ADMIN/SUPERADMIN can add/edit/delete
- delete requires confirmation
- backend prevents deletion when business constraints disallow it, e.g. active session

### Lịch sử

- shows user-facing action history and synchronized/not-synchronized state
- does not explain ACK/protocol internals

### Đồng bộ

User-facing summary uses understandable concepts such as:

- Mạng
- Đồng bộ
- Dữ liệu chờ gửi
- Phiên bản
- Service

Developer fields such as server/master revisions may remain internally available but are not routine user copy.

### Cài đặt

Contains practical configuration only, including account/mail, 7-color theme, updates, logs, device/admin items and logout. Duplicate sync-details section is removed.

## 10. Logging — CHỐT

Categories:

- MANUAL -> `BÁO LỖI THỦ CÔNG`
- CRASH -> `BÁO LỖI TỰ ĐỘNG`
- DAILY -> `NHẬT KÝ ANDROID`

Rules:

- redact secrets/private data where applicable
- manual send uses Yes/No confirmation
- Manual/Crash/Daily local file is deleted **only after successful server ACK for that upload/event**
- pending Crash/Daily logs are also attempted after restored session, not only after a fresh login
- user-facing success text does not expose ACK implementation jargon

## 11. Reports — active business/UI rules

- no redundant `NGUỒN LỰC` / `THÂM NIÊN` title rows
- support block only shown when deducted support total > 0
- `Phúc Long` before `Kéo hàng`
- compact PDA-friendly spacing
- zero-cell/all-zero-column display optimizations remain according to existing logic
- table sections should read as one coherent block; avoid heavy rounded outline around each table

## 12. GAS live state

Live API remains `0.4.2` / `APP_GSHEET` architecture with:

- Sheet read health
- `SINGLE_ACTIVE_DEVICE_V1`
- Drive-based `update_check` channel routing
- account-email forgot-password route
- MailApp authorization

Browser-only GAS deployment uses configured GitHub Secrets. Never expose their values.

## 13. OTA — CHỐT

Steady-state:

`Android -> GAS update_check -> Google Drive channel folder`

- BETA only `BẢN THỬ NGHIỆM`
- STABLE only `BẢN ỔN ĐỊNH`
- GitHub Releases are not steady-state OTA authority
- check on open/foreground; no screen-off/background polling
- verify downloaded APK SHA-256 before installer
- normal Android may still require user install confirmation / unknown-source permission

## 14. Current release state

### Published Beta — `0.4.2-beta.6`

- Package: `vn.pickpack1291.app.beta.publicbeta`
- VersionCode: `12`
- SHA-256: `ac6c537d3d0e6a85574233ad9031544befd3a282349e47c605e5cd05b0701860`
- Fixed signer SHA-256:
  `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`

beta.6 OTA E2E passed:

- beta.5 -> beta.6 update found
- actual OTA download SHA matched
- beta.6 does not update to itself
- Stable does not see Beta build

### Source candidate — `0.4.2-beta.7`

- VersionCode: `13`
- Source contains S07 persistent-shell/copy-rule refactor.
- Beta Release + Stable Release compilation passed before source commit.
- **NOT published to Google Drive OTA.**
- Do not tell owner beta.7 is released unless a later OTA publish and E2E verification actually completes.

### Stable

Not promoted. Stable release still requires Beta soak/business acceptance and an explicit owner decision.

## 15. Build / CI / release optimization — CHỐT

Authoritative procedure: `docs/BUILD_RELEASE_PLAYBOOK.md`.

### Permanent two-tier model

**Tier A — `App Fast Check`**

Normal source changes:

- static architecture/UX guards
- launcher hash
- Beta Debug assemble
- Stable Debug assemble
- no live GAS/Drive release probe
- no signing/publish
- concurrency cancels stale older fast checks

**Tier B — `Release Preflight - Beta and Stable`**

Explicit pre-release only:

- live GAS health
- live BETA/STABLE Drive channel checks
- dynamic source version metadata
- Beta Release + Stable Release assemble
- package/version validation
- candidate artifact
- fixed-signer validation if four signing secrets are ready
- validation only; no automatic Drive OTA publish

Both pipelines first use an exact preinstalled Android SDK when available and only fall back to the pinned verified SDK bootstrap when required.

### Recurring failures now recorded/prevented

The build playbook records these known failure classes:

- brittle one-line Kotlin patch anchors / parser cascades
- multiline source embedded in workflow YAML
- dispatching newly-created workflows before registration
- observers writing receipts to `main` causing rebase races
- CI trying to self-edit `.github/workflows`
- `ops/*` source/status conflicts
- stale hardcoded release versions
- full release/live probes on every tiny edit
- repeated Android SDK bootstrap
- wrong/historical external-service assumptions
- OAuth scope mismatch for Drive upload

Permanent CI must validate, not write observer/status/source commits back to `main`.

## 16. Android signing automation

Four GitHub signing secrets remain the preferred full-auto signing path when confirmed configured:

- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

Do not expose values.

Until confirmed, use only the official existing signing recovery path and verify the fixed signer. Never create a replacement signing identity.

## 17. Scanner / performance

- MNV numeric input supports hardware/IME Enter suffix.
- master lookup/search prefers local cache where appropriate.
- operational session/resource state remains server-authoritative.
- actual Newland/PDA hardware behavior still needs real-device acceptance after relevant Beta updates.

## 18. P0 acceptance / backlog

On real PDA after next OTA candidate:

- verify five-tab switching is perceptually immediate with no Activity flash/delay
- verify approved header/layout on actual screen dimensions
- verify QR MNV Enter/OK flow and NOT_ENTERED/ACTIVE/ENDED states
- verify PDA last-5 suggestions and duplicate handling
- verify PICK without User Pick
- verify Công nhật flows and report readability
- verify theme switching across all inner screens
- verify notifications queue/3-second behavior
- verify forgot password for a normal user using configured account email
- verify force-close/reopen session persistence
- verify same-account replacement from a second installation/device

Visual implementation should continue from the approved design spec; do not redesign it again without owner request.

## 19. Handover policy

Two layers:

1. `docs/HANDOVER_CURRENT.md` — cumulative authoritative state.
2. `docs/handovers/HANDOVER_SXX_YYYY-MM-DD.md` — immutable snapshot when a chat handover is requested.

When a later decision replaces an old one, mark the old decision `SUPERSEDED` rather than silently dropping it.

Public repo handovers must not include plaintext passwords, tokens, private signing material, real personnel data or unnecessary private identifiers.
