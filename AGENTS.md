# AGENTS.md — Pick Pack 1291 mandatory project rules

These rules are authoritative for any agent, coding assistant, CI automation, or future handover working in this repository.

## 1. Owner requirements override inherited implementation

- Do not infer a new architecture from existing code, handovers, migrations, or deployed infrastructure.
- Do not treat an inherited implementation as permission to change the project purpose.
- If existing code conflicts with an explicit owner requirement, correct the code toward the explicit requirement.
- Never silently reinterpret or expand the requested purpose.

## 2. Approved operational architecture

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

with:

- Cloudflare Worker as the production API/runtime;
- Cloudflare D1 as the normal-mode operational primary datastore;
- Durable Objects + WebSocket/Hibernation for realtime coordination/fanout;
- Google Sheets as operational replica/compatibility/fallback/DR according to authority state;
- Google Apps Script as discovery/compatibility/fallback bridge and OTA `update_check` authority;
- Android SQLite/cache as local projection/offline state;
- GitHub as source/CI/release infrastructure only.

`ARCHITECTURE_GUARDRAILS.md` records the OWNER-approved 2026-08-18 supersession of the earlier GAS-only architecture. Older handovers may describe `Android ↔ GAS ↔ Google Sheets` as a historical state; they must not be used to roll production authority back implicitly.

## 3. No unauthorized service/backend changes

The Service-first stack above is already OWNER-approved. Do not add, replace, or migrate authority to a different backend, datastore, queue, auth authority, or synchronization authority without a new explicit owner instruction.

In particular, do not introduce or migrate to:

- Supabase;
- Firebase;
- Neon/Postgres;
- another Cloudflare datastore/service beyond the approved Worker/D1/Durable Objects design;
- Queue, KV, R2, or another new infrastructure component;
- another database/server/backend/service;
- another auth authority;
- another synchronization authority.

If a technical limitation appears to require such a change, keep the approved Service-first architecture unchanged, document the blocker precisely, and require explicit owner authorization before changing architecture.

## 4. Do not act contrary to the stated goal

Before a material implementation change, verify that it directly serves the latest explicit owner requirements. Do not add infrastructure merely because it is convenient, familiar, already present elsewhere, or inherited from a previous session.

## 5. Data and release safety

- Reconcile existing business data before deleting/replacing an implementation.
- Do not commit secrets, plaintext passwords, Google credentials, Android signing keys, or private tokens to the public repository.
- Beta must exercise the real business functions needed for testing.
- Preserve Android signing identity for in-place updates.
- Starting with the OTA-enabled Android 0.4.2 build (`0.4.2-beta.2` for Beta), runtime update discovery must call the approved Google Apps Script `update_check` route.
- `BETA` must read release APKs only from Google Drive folder `BẢN THỬ NGHIỆM`.
- `STABLE` must read release APKs only from Google Drive folder `BẢN ỔN ĐỊNH`.
- Do not restore GitHub Releases as the steady-state OTA authority for 0.4.2+ unless the owner explicitly changes this requirement.
- GitHub prerelease `v0.4.2-beta.2-publicbeta` is only a one-time compatibility bridge so legacy Beta clients that still check GitHub can migrate to the Drive-OTA build.
- OTA APK downloads must be SHA-256 verified before the Android installer is launched.
- OTA checks remain foreground-oriented: check on app open/foreground opportunities; do not introduce background/screen-off polling.
- Launcher icon artwork must use the exact owner-provided artwork without redesign, replacement, decorative inset, or alternate artwork.
- Login session must survive app/process closure on the same installation. The active account session remains valid until explicit logout, account/security change, or a successful login for that same account from a different app installation/device replaces the active server session.

## 6. Architecture enforcement

Read and obey `ARCHITECTURE_GUARDRAILS.md`, `docs/UI_UX_SYSTEM.md`, `docs/BUILD_RELEASE_PLAYBOOK.md`, `docs/ADMIN_ACCOUNT_RULES.md` and `README.md` before material runtime/release changes. CI architecture/UX/release gates are intentional and must not be bypassed to make a build pass.

## 7. Owner workstation constraint — no local command line

- The owner's company-managed computer cannot run CMD, PowerShell, Terminal, shell scripts, or other local command-line workflows.
- Do not instruct the owner to execute `cmd`, PowerShell, `bash`, `clasp`, `git`, `gh`, `adb`, Gradle, Node/npm/npx, Java/keytool, OpenSSL, or similar local CLI commands.
- Owner-facing setup and administration must preferentially use browser/UI workflows such as GitHub web UI, Google Workspace/Apps Script UI, Drive UI, or repository-hosted CI/automation.
- If a required task normally needs a local CLI, redesign it so CI/automation performs the command-line portion and the owner only performs browser-based authorization, secret entry, or explicit approval.
- If a browser-only path is genuinely impossible, state the blocker explicitly instead of giving unusable local terminal instructions.

## 8. UI / UX lock — current owner-approved system

This section **SUPERSEDES** the old fixed `Minimal Teal Corporate / Mẫu 2` lock.

Authoritative detail is in `docs/UI_UX_SYSTEM.md`.

Mandatory rules:

- Official design family is the owner-approved modern enterprise blue/indigo/violet system with centralized 7-color theming.
- The 7 theme choices stay on one row, equal-width, without color-name labels.
- Work cards use one equal component; do not mix hero-card and unrelated card geometries.
- The authenticated app uses one persistent five-tab shell in this order: `Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`.
- Switching those five tabs must not start/finish another Activity and must not add an artificial fade/cross-fade delay.
- The top authenticated header shows user name, position and account on separate constrained lines; do not use `PICK PACK 1291` as the normal tab title.
- Reserve the compact header status area for user-facing Mạng / Đồng bộ / Service status.
- Use semantic icons appropriate to each tab/card/title/action; production UI should prefer stable Android vector/icon resources over arbitrary font glyphs.
- Settings must not duplicate a `Đồng bộ dữ liệu` section because synchronization has its own tab.
- UI copy is for ordinary users only. Do not expose implementation commentary such as server/API revision, ACK, request/cache architecture, AI/designer notes or instructions explaining implementation decisions.
- Routine notices use the project top-notification queue: about 3 seconds, maximum 3 visible/queued items; avoid blocking OK dialogs for routine state/not-found/success messages.
- Manual diagnostic-log sending and consequential/destructive actions may use explicit confirmation dialogs according to project rules.
- MNV/PDA scanner flows trigger on hardware/keyboard Enter/OK; do not add redundant `Kiểm tra` buttons merely to trigger the same operation.
- The approved visual language applies to inner workflows (QR, Công nhật, Tài nguyên, Báo cáo, Nhân sự, Lịch sử, Đồng bộ, Settings/admin), not only the dashboard.
- Login remains centered, without beta/version marketing text, and includes `QUÊN MẬT KHẨU?`.
- PICK requires PDA; User Pick is optional. PDA selection uses the last 5 serial digits with validated suggestions.
- Reports keep operational matrices but suppress redundant section-title rows; support table is hidden when deducted support count is zero; Phúc Long precedes Kéo hàng; avoid heavy rounded borders around every table.

## 9. Build / release operating rules

Authoritative detail is in `docs/BUILD_RELEASE_PLAYBOOK.md`.

Mandatory rules:

- Ordinary app/source changes use a fast Beta+Stable debug validation pipeline with static guards; do not run live GAS/Drive release probes for every small edit.
- Full Beta+Stable release assemble, live API/Drive probes, package metadata and signing validation run only in an explicit Release Preflight before OTA/release work.
- VersionCode/versionName are read from source; do not hardcode an old Beta version in CI.
- Use the exact preinstalled Android SDK when it contains the required platform/build-tools; use the pinned verified SDK bootstrap only as fallback.
- Permanent CI validates but does not commit source/status/observer receipt files back to `main`.
- Do not create observer workflows that write run status into `main`.
- Do not make CI self-edit `.github/workflows`.
- Complex source transformations belong in standalone scripts with exact unique markers; do not embed large multiline Kotlin/Python transformations directly in workflow YAML.
- Preserve the fixed Android signer. Never generate a replacement signing identity to make a release pass.
- Release Preflight does not itself publish to Google Drive. OTA publish is a separate deliberate step with signer, SHA-256, channel isolation and E2E update checks.
- Stable requires owner-approved Beta soak/business acceptance; successful compilation alone is not permission to promote Stable.

## 10. Admin account namespace — OWNER LOCK

Authoritative detail is in `docs/ADMIN_ACCOUNT_RULES.md`.

- `Danh sách Admin` is a specialized account namespace, not an employee-position catalog.
- The `Vị trí` field in `Danh sách Admin` is fixed system-wide to exactly: `superadmin`, `admin`, `user`.
- Do **not** populate or infer Admin `Vị trí` from `Danh mục`, `DANH SÁCH NHÂN SỰ_Vị trí chính`, or any other sheet/catalog.
- Similar field names across sheets do not authorize cross-sheet fallback.
- Android and GAS must derive/validate Admin position from the Admin role; arbitrary client-supplied values are invalid.
- Normal app account creation must not create a new `SUPERADMIN` unless the owner explicitly authorizes that capability later.
- This allowed set and its role-position mapping may change **only after an explicit owner instruction**. No developer, agent, migration, UI redesign, or implementation convenience may alter it autonomously.
