# UI / UX SYSTEM — PICK PACK 1291

Status: **CHỐT / authoritative**  
Effective from: 2026-08-18  
Supersedes: Minimal Teal Corporate / Mẫu 2 and fixed-teal assumptions.

This document records the owner-approved product UI/UX system. Future implementation must preserve these rules unless the owner explicitly changes them.

## 1. Visual system

- Official design family: the owner-approved modern enterprise layout with a **blue / indigo / violet gradient visual system**, rounded surfaces, clean spacing and clear semantic icons.
- The app continues to support **7 selectable theme colors**. Theme color is a system token, not a one-off button color: header, selected state, icon emphasis, buttons, chips, highlights and related surfaces must remain visually coherent after a theme change.
- Theme choice is centralized through `ThemeManager`; do not scatter hardcoded primary-theme colors across screens.
- The 7 color selectors have **no color-name text** and must always fit on **one horizontal row**, with equal sizing and no wrap/overflow.
- Functional status colors may retain conventional semantics where necessary: success/active = green, warning/pending = amber/orange, destructive/error = red. They must not become unrelated decorative palettes.

## 2. Global app shell

Authenticated operation uses one persistent application shell.

Bottom navigation is always one row, in this exact order:

1. Nghiệp vụ
2. Nhân sự
3. Lịch sử
4. Đồng bộ
5. Cài đặt

Rules:

- Switching these five tabs must **not start/finish another Activity** and must not recreate the whole authenticated screen.
- Switching tabs must not add an artificial fade/cross-fade delay. Content changes in-place and the existing bottom navigation remains mounted.
- The selected tab changes visual state immediately on touch.
- Network/API work initiated by the destination screen must not block rendering of the destination shell. Show cached/current information first when available, then update asynchronously.
- Inner workflow screens under Nghiệp vụ may change content within the same authenticated Activity; returning to the tab root must not require launching a second Activity.

## 3. Top header

On authenticated tabs, do not use `PICK PACK 1291` as the main top-bar title.

The compact identity area contains three user-facing lines:

- Họ tên
- Vị trí
- `Tài khoản: <login>`

Each item stays on its own line. Text must be constrained/ellipsized so long values never break the header or overlap the status area.

The right side reserves a compact status area for:

- Mạng
- Đồng bộ
- Service

Status wording must be short and understandable to normal users, e.g. `Tốt`, `Mất kết nối`, `Đã xong`, `Đang chờ`, `Hoạt động`, `Chưa cấu hình`.

Do not expose internal revision numbers, server sequence numbers, API implementation labels or protocol terms in this header.

## 4. Nghiệp vụ cards

The primary work cards use one component and are visually equal:

- same width/height
- same radius
- same padding
- same icon area
- same title/subtitle hierarchy
- same shadow/border treatment

Primary cards:

- Quét QR nhân sự — `Vào ca / ra ca`
- Công nhật — `Bắt đầu / hoàn thành`
- Báo cáo nhân sự — `Theo ca / theo ngày`
- Tài nguyên — `PDA / Pick / Pack`

Do not make one work card a large hero while the others use a different component unless the owner explicitly changes this rule.

## 5. Semantic icons

Every tab, section title, work card and action that benefits from an icon uses an icon matching its meaning.

Examples:

- Quét QR nhân sự: scan/QR frame
- Công nhật: clipboard/task/check
- Báo cáo: chart/report
- Tài nguyên: box/device/resource
- Nhân sự: people/users
- Lịch sử: clock/history
- Đồng bộ: sync/cloud arrows
- Cài đặt: gear
- Đổi mật khẩu: lock/key
- Mail: envelope
- Thiết bị: phone/device
- Cập nhật: download/update

Prefer proper Android vector/icon resources for production UI. Do not rely on arbitrary Unicode glyphs where device fonts can render inconsistently.

## 6. User-facing copy rule — mandatory

All visible copy is written for ordinary app users, not for developers, AI agents, system designers or backend operators.

Allowed copy should answer one of these questions:

- What is this item?
- What is its current status?
- What should the user enter or choose?
- What action can the user take?
- What went wrong and what can the user do next?

Do **not** insert implementation/developer commentary such as:

- server/API revision or sequence explanations
- `ACK`, protocol or cache implementation explanations
- statements explaining that data comes from a cache/Sheet/service architecture
- notes like `Không cần nút kiểm tra`
- notes like `Màu giao diện được đổi trong tab Cài đặt`
- AI/designer commentary explaining why a screen behaves a certain way
- internal roadmap/service notes that do not help the current user action

Technical details may exist in logs, developer docs and diagnostics, but not routine user UI.

Use concise Vietnamese consistently. Avoid mixing `server`, `request`, `ACK`, `revision`, `master cache` and similar engineering terms into normal screens.

## 7. Notifications and confirmations

- Routine notices use top-of-screen notifications.
- Each notification auto-hides after about **3 seconds**.
- Show at most **3 notifications** at once; newer notifications evict the oldest when the queue exceeds 3.
- Do not use `OK` dialogs for routine not-found/success/status messages.
- Confirmation dialogs are reserved for genuinely consequential or explicitly owner-approved actions, including destructive actions and manual diagnostic-log submission.
- Manual log submission uses Yes/No confirmation.

## 8. Input / scanner interaction

For MNV/PDA scanner-oriented flows:

- Enter/OK from hardware PDA or keyboard triggers the operation immediately.
- Do not reserve screen space for redundant `Kiểm tra` buttons when Enter/OK is the accepted trigger.
- Error/not-found state should appear inline or through the standard top notification, not a blocking OK dialog.

## 9. Settings ownership

`Đồng bộ` has its own bottom tab. Therefore Settings must **not** duplicate a `Đồng bộ dữ liệu` / sync-details section.

Settings contains practical configuration such as:

- Tài khoản
- Đổi mật khẩu
- Đổi địa chỉ mail
- Mail nhận reset mật khẩu
- Giao diện / 7 theme swatches
- Cập nhật
- Nhật ký / gửi báo lỗi
- Thiết bị
- Quản trị items when role permits
- Đăng xuất

`Đổi mật khẩu` and `Đổi mail` remain side by side, equal-width and single-line.

## 10. Inner workflow quality

The approved design system applies to **every screen**, not only the outer dashboard.

QR, Công nhật, Tài nguyên, Báo cáo, Nhân sự, Lịch sử, Đồng bộ, Settings and admin screens must reuse the same spacing, typography, card hierarchy, icons, colors, input styling and status chips.

Do not leave inner screens as raw controls or sparse developer forms while the home screen is polished.

## 11. Report layout

Reports should look like one coherent information block, with sections separated by spacing, headers and subtle background hierarchy rather than heavy rounded outlines around every table.

Existing business display rules remain active:

- no redundant `NGUỒN LỰC` / `THÂM NIÊN` title rows
- support block hidden when deducted support total is zero
- `Phúc Long` before `Kéo hàng`
- compact PDA-friendly spacing
- zero-value display/collapsing behavior remains according to existing report rules

## 12. Review gate

Before a Beta/Stable release candidate is accepted, UI-related source must satisfy at minimum:

- one persistent five-tab shell
- no tab transition delay implementation
- no duplicate sync section in Settings
- no banned developer-facing copy
- correct tab order
- 7 theme swatches remain one row
- visual tokens remain centralized

Any deliberate exception requires a new explicit owner decision and must be recorded as `SUPERSEDED` in the cumulative handover.
