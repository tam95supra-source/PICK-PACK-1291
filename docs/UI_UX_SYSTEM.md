# UI / UX SYSTEM — PICK PACK 1291

Status: **CHỐT / authoritative**  
Effective from: 2026-08-18  
Latest owner correction recorded: 2026-08-18 17:03 +07:00  
Supersedes: Minimal Teal Corporate / Mẫu 2, fixed-teal assumptions, the S09 three-line identity header, and older report-row ordering where explicitly noted below.

This document records the owner-approved product UI/UX system. Future implementation must preserve these rules unless the owner explicitly changes them.

## 1. Visual system

- Official family: modern enterprise blue / indigo / violet gradient system.
- App supports exactly **7 selectable theme colors** through centralized `ThemeManager` tokens.
- Theme swatches are exactly one horizontal row, equal size, no labels, no wrapping.
- Functional status colors retain normal semantics where useful.
- Real PDA surfaces must not show muddy grey elevation/shadow halos. Routine cards, inputs and navigation use clean white/soft-theme surfaces with subtle theme-tinted outlines.

## 2. Global authenticated shell

One persistent authenticated Activity shell. Bottom tabs are exactly:

`Nghiệp vụ – Nhân sự – Lịch sử – Đồng bộ – Cài đặt`

Rules:

- Root-tab switching changes content in place; do not start/finish another Activity.
- No artificial fade/cross-fade transition delay.
- Bottom navigation remains mounted.
- Selected tab updates immediately.
- Cached/current content renders before asynchronous refresh where possible.

## 3. Top header

The identity area shows only:

`Chào buổi <sáng/trưa/chiều/tối>, <Họ tên>`

- Greeting period comes from the **actual local clock on the PDA**.
- Do not show login/user ID, role, position or avatar placeholder in the top header.
- Long names must fit/ellipsize safely.
- Compact status remains `Mạng / Đồng bộ / Service`.
- Connection state persists across tab changes.
- Do not expose API/revision/protocol/internal implementation text.

## 4. Inner workflow header — latest owner correction

For inner screens such as QR/Vào-Ra, Công nhật, Tài nguyên, Báo cáo and other operational subflows:

- Keep the back-navigation control when needed.
- **Do not render a second text title such as `BÁO CÁO`, `CÔNG NHẬT`, `QUÉT QR NHÂN SỰ` underneath the greeting/status area.**
- The purpose of scan/search workflows is communicated primarily by the input placeholder and subsequent business content.
- Compact header/body padding to maximize the usable PDA viewport.

## 5. Scanner and search inputs

Scanner-oriented fields are the dominant call-to-action and should be noticeably taller than ordinary form fields. Current target implementation uses about **72dp minimum height** for MNV/search fields.

Do not place redundant `Mã nhân viên`, `Hướng dẫn quét...` or similar explanatory text outside the scan field when the placeholder can carry the instruction.

Use contextual placeholders, for example:

- Vào/Ra: `Scan / Nhập mã nhân viên để ghi nhận ra ca / vào ca`
- Công nhật: `Scan / Nhập mã nhân viên để ghi nhận công nhật`
- Tài nguyên: `Scan / Nhập mã nhân viên để quản lý tài nguyên`
- Tìm nhân sự/danh sách: `Scan / Nhập mã nhân viên, họ tên để tìm kiếm`

Hardware/keyboard Enter/OK triggers the operation immediately. Do not add a redundant `Kiểm tra` button.

## 6. Nghiệp vụ cards

Primary cards use one equal component:

- Quét QR nhân sự — `Vào ca / ra ca`
- Công nhật — `Bắt đầu / hoàn thành`
- Báo cáo nhân sự — `Theo ca / theo ngày`
- Tài nguyên — `PDA / Pick / Pack`

Same width/height/radius/padding/icon hierarchy/shadow treatment.

## 7. Required select fields

- Required catalog/select fields do not show a decorative blank/dash (`—`) option.
- A required field must resolve to a real value from its **matching `SHEET_FIELD` namespace** before save.
- Do not invent/borrow catalogs across sheets.
- Preserve explicit business exceptions such as optional User Pick.
- `Danh sách Admin` remains a protected namespace; Admin `Vị trí` is only `superadmin`, `admin`, `user`.

## 8. User-facing copy

Visible copy is for ordinary users only. It should explain what an item is, current status, what to enter/choose, what action is available, or what to do after an error.

Do not expose ACK/protocol/server revision/master revision/cache architecture/design commentary or raw engineering terminology in routine UI.

Routine notices use non-blocking top notifications for about 3 seconds, maximum 3 visible. Confirmation dialogs are reserved for consequential/destructive actions and manual diagnostic-log submission.

## 9. Staff UI and phone data

- Full staff master remains searchable from local cache.
- Staff list renders incrementally/lazily; do not synchronously construct thousands of cards on tab entry.
- Vietnamese phone numbers are displayed/stored with the leading `0`.
- App normalizes legacy 9-digit values and requires saved phone numbers to be 10 digits beginning with `0`.

## 10. Lịch sử

Lịch sử is an operational activity view, not a raw event/debug dump.

- Summary: total / completed / needs attention.
- Simple user filter.
- Recent activity grouped by date/time.
- Semantic action icons/status chips.
- Translate backend error codes into user-facing explanations; raw `PP_*` codes are not the primary visible content.

## 11. Đồng bộ

Đồng bộ is an operational dashboard, not a sparse developer key/value screen.

- Clear network/sync/pending status.
- Useful last-refresh information.
- App channel/version.
- Explicit `LÀM MỚI TRẠNG THÁI` while automatic foreground sync remains active.
- No revision/protocol jargon.

## 12. Báo cáo nhân sự — latest owner layout

Report screens are compact and optimized for the PDA viewport.

### 12.1 Table treatment

- Report matrices **must have visible borders between cells**; do not render floating numbers without grid separation.
- Use compact typography/padding while maintaining legibility.
- Header and total rows may use subtle background emphasis.
- Supplier columns are shown for relevant suppliers; current canonical supplier order is `Inhouse, NLV, VW, MP, MGL, HGP, HAD` when present, followed by `Tổng`.

### 12.2 Main manpower matrix

The position matrix follows the owner reference structure. Canonical row order is:

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

`Phúc Long` is visually highlighted where appropriate.

**SUPERSEDED:** the older rule `Phúc Long before Kéo hàng` is no longer valid. The 2026-08-18 owner reference places **Phúc Long after Packer and immediately before Tổng**.

### 12.3 Tenure matrices

Show separate bordered matrices:

- `Thâm niên Picker`
- `Thâm niên Packer`

Rows:

- `Nhân sự mới` = tenure ≤ 30 days
- `Nhân sự cũ` = tenure > 30 days

Staff marked as deducted support are removed from the effective Picker/Packer tenure counts.

### 12.4 Hỗ trợ bộ phận khác

- Derived only from Công nhật records explicitly marked **Khấu trừ nhân sự = Có** for the selected shift scope.
- De-duplicate the same person within the same support type for the matrix.
- Show by supplier and total in a bordered matrix.
- **Hide the entire support block when deducted support total = 0.**
- When support exists, show the post-deduction team remainder for Picker and Packer, including old/new split.

### 12.5 Shift scopes

Supported report scopes remain:

- `Ca 1 + Ca HC`
- `Ca 2`
- `Cả ngày`

## 13. Settings

Settings must not duplicate a full `Đồng bộ dữ liệu` section because Đồng bộ owns that bottom tab.

Practical settings include account/password/mail/theme/update/log/device/admin/logout. `Đổi mật khẩu` and `Đổi mail` remain side-by-side, equal width and single-line where screen width permits.

## 14. Semantic icons

Use proper Android vector/semantic icons for tabs, work cards, section/action items where useful. Avoid arbitrary Unicode glyphs whose rendering depends on device fonts.

## 15. Review gate

Before a Beta/Stable release candidate is accepted, UI-related source must satisfy at minimum:

- persistent five-tab shell and exact tab order
- no tab transition delay implementation
- one-line local-time greeting header only
- no duplicated inner-screen text title below status chips
- contextual tall scan/search fields without redundant external scan instructions
- no grey elevation haze on routine rounded surfaces
- required selects have no decorative dash placeholder
- 7 theme swatches remain one row
- History/Sync remain useful operational screens
- report matrices have visible cell borders
- separate Picker/Packer tenure matrices
- deducted-support block hidden when total is zero
- new report row order with Phúc Long after Packer and before Tổng

Any deliberate exception requires a new explicit owner decision and must be recorded as `SUPERSEDED` in the cumulative handover.
