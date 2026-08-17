# UI SPEC — Pick Pack 1291

Status: CHỐT
Decision date: 2026-08-17 (Asia/Bangkok)
Canonical concept: MẪU 1 — TỐI GIẢN / HIỆN ĐẠI
Supersedes: MẪU 3 — NHẸ NHÀNG / DỄ NHÌN

## 1. Design direction

- Giao diện nền trắng/light gray, app bar navy, các thẻ chức năng dùng màu đặc với icon/chữ trắng.
- Ưu tiên PDA Newland NLS-MT90 màn hình khoảng 5 inch, scan-first, thao tác một tay.
- Bố cục phải tôn trọng Android system-bar insets; tuyệt đối không để app bar/content lấn status bar/camera cutout.
- Toàn bộ vùng nội dung chính được hạ nhẹ so với bản Beta Preview đầu tiên.
- Không dùng animation nặng, glassmorphism, blur hoặc hiệu ứng gây tốn GPU/pin.
- Màu trạng thái: navy/blue = điều hướng/thao tác chính, green = thành công/công nhật, red = RA/lỗi, orange = tài nguyên/cảnh báo, teal/purple cho nhóm phụ.
- Icon/artwork chính thức lấy từ master artwork do chủ dự án cung cấp; không redesign nội dung.

## 2. Login

- Logo căn giữa, kích thước gọn hơn bản preview đầu.
- Tên `PICK PACK 1291`, subtitle `SUPRA DC HƯNG YÊN`.
- Input `Tài khoản`, `Mật khẩu` sáng, border rõ.
- CTA `ĐĂNG NHẬP` navy, full width.
- Public Beta dùng xác thực server thật; APK không chứa password verifier, Google credential hoặc signing secret.

## 3. Home/dashboard

- App bar navy, icon/menu và text trắng, account/role ở góc phải.
- Thẻ đầu tiên full-width: `QUÉT QR NHÂN SỰ`.
- Không còn hai thẻ `VÀO CA` / `RA CA` độc lập.
- Các module còn lại theo grid 2 cột khi phù hợp:
  - CÔNG NHẬT
  - TÀI NGUYÊN
  - DANH SÁCH
  - BÁO CÁO
- `CÀI ĐẶT` có thể dùng thẻ full-width nhỏ hơn ở cuối nhóm chức năng.
- Trạng thái server/sync hiển thị nhỏ gọn phía dưới vùng thao tác.

## 4. QUÉT QR NHÂN SỰ

Màn đầu tiên chỉ có MNV:
- Ưu tiên dữ liệu từ scanner/QR; vẫn cho nhập tay.
- Enter/IME Done thực hiện kiểm tra ngay.

Sau khi server kiểm tra MNV + business date:

### CHƯA VÀO
- Hiển thị thông tin nhân sự.
- Hiển thị `Ca làm việc`, `Vị trí trong ca` và tài nguyên cần thiết.
- `PICK`: bắt buộc PDA, User Pick tùy chọn.
- `PACK`: chọn bundle Bàn Pack + User Pack mapped.
- `KHÔNG`: không cấp tài nguyên.
- CTA `VÀO CA`.

### ACTIVE
- Hiển thị đầy đủ thông tin phiên hiện tại và tài nguyên đang giữ.
- Chỉ hiện CTA `RA CA` cùng bước xác nhận.

### ENDED
- Báo rõ `ĐÃ HẾT PHIÊN VÀO / RA HÔM NAY`.
- Không cho luồng thường VÀO lại trong ngày.
- Correction là chức năng đặc quyền riêng của ADMIN/SUPERADMIN.

## 5. Conflict / transaction UX

- Mutation chỉ đổi UI sau server ACK.
- Mỗi mutation có immutable `event_id` để retry/idempotency.
- Khi resource conflict, giữ nguyên MNV/form và yêu cầu chọn lại tài nguyên xung đột.
- Không silent overwrite accepted history.

## 6. Footer / branding

Footer cố định sát đáy màn hình, luôn nằm ngoài vùng nội dung cuộn:

`Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY`

- Căn giữa.
- Font nhỏ hơn bản preview đầu tiên.
- Tôn trọng navigation-bar inset.
- Không chiếm diện tích thao tác chính.

## 7. System bars

- Status bar nền trắng, icon tối.
- Navigation bar nền trắng, icon tối khi hệ điều hành hỗ trợ.
- Root view áp dụng status-bar + navigation-bar insets và thêm khoảng hạ nhẹ phía trên.
- Đây là yêu cầu bắt buộc sau kiểm thử trên thiết bị thật cho thấy bản preview đầu lấn status bar.

## 8. Public Beta

- Public Beta là bản thao tác thật, không còn chỉ là UI preview.
- Login, lookup nhân sự/master resource, VÀO và RA đi qua authoritative Beta API.
- Dữ liệu session/resource Beta được ghi transactionally và có server sequence.
- Projection sang Google Sheet phải có queue + ACK; không được coi là đã ghi Sheet nếu chưa nhận ACK.
- Package Beta tách riêng để có thể cài song song trong giai đoạn pilot.

## 9. Performance constraints

- Ưu tiên native Android UI nhẹ.
- Không giữ foreground service liên tục chỉ để sync.
- Scanner chỉ active ở flow cần scan.
- Không query full Sheet liên tục từ Android; master data do backend đọc/cache/filter.
- Không retry nóng khi mất mạng.

## 10. Canonical status

MẪU 1 là baseline UI chính thức kể từ quyết định này. MẪU 3 bị supersede và chỉ còn là tài liệu lịch sử/tham khảo. Mẫu 2, 4, 5 không phải baseline.
