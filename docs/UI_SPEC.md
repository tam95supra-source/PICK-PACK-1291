# UI SPEC — Pick Pack 1291

Status: CHỐT
Decision date: 2026-08-17 (Asia/Bangkok)
Canonical concept: MẪU 3 — NHẸ NHÀNG / DỄ NHÌN

## 1. Design direction

- Giao diện sáng, nhẹ, chuyên nghiệp, ít chi tiết thừa.
- Ưu tiên PDA Newland NLS-MT90 màn hình khoảng 5 inch và thao tác một tay.
- Scan-first, nút lớn, font rõ, khoảng cách chạm đủ rộng.
- Không dùng animation nặng, glassmorphism hoặc hiệu ứng gây tốn GPU/pin.
- Màu chính: teal/cyan dịu trên nền trắng/light gray.
- Màu trạng thái dùng có kiểm soát: xanh lá = thành công/công nhật, đỏ = RA/lỗi nguy hiểm, cam = tài nguyên/cảnh báo, xanh dương/tím = nhóm chức năng phụ.
- Icon/artwork chính thức lấy từ master artwork do chủ dự án cung cấp; không redesign nội dung.

## 2. Login screen

- Header/logo căn giữa phía trên.
- Tên `PICK PACK 1291` rõ ràng, phần `SUPRA DC HƯNG YÊN` nhỏ hơn.
- Trường `Tài khoản` và `Mật khẩu` dạng input sáng, border nhẹ.
- Có nút hiện/ẩn mật khẩu.
- Nút `ĐĂNG NHẬP` teal/cyan, full width, chiều cao đủ thao tác bằng găng/tay.
- Link `Đổi mật khẩu` và `Cài đặt` ở mức secondary, không cạnh tranh với CTA chính.

## 3. Home/dashboard

- App bar sáng với menu, tiêu đề `Trang chủ`, user/role ở góc phải.
- Grid 2 cột, các module chính dạng card lớn:
  - VÀO CA
  - RA CA
  - CÔNG NHẬT
  - TÀI NGUYÊN
  - DANH SÁCH
  - BÁO CÁO
- Card có icon lớn, label ngắn, màu pastel dễ phân biệt nhưng không chói.
- Phía cuối màn hình có vùng trạng thái đồng bộ nhỏ gọn: kết nối, lần sync gần nhất, server sequence/trạng thái phù hợp.

## 4. Form nghiệp vụ — ví dụ VÀO CA

- Header teal/cyan, nút back rõ ràng.
- Các field xếp một cột theo thứ tự thao tác thực tế.
- MNV ưu tiên scan hoặc nhập nhanh; có icon scan ở bên phải.
- Dropdown Ca làm việc và Vị trí trong ca dùng control lớn, dễ chạm.
- CTA `TIẾP TỤC` full width ở cuối vùng thao tác.
- Khi conflict, giữ nguyên dữ liệu đã nhập/scan; chỉ highlight field/resource xung đột và hiển thị lý do.

## 5. Sync UX

- Foreground: sync tự động; user không phải bấm refresh thường xuyên.
- Trạng thái nên dùng wording ngắn: `Đã đồng bộ`, `Đang đồng bộ`, `Đang chờ gửi`, `Mất kết nối`.
- Không dùng modal cho các sync thành công thông thường.
- Conflict/error mới cần banner/dialog rõ ràng.
- Khi app/screen rời foreground trong lúc đang có transaction, UI/state tuân thủ lifecycle `DRAINING -> SUSPENDED`; không hủy mutation đang in-flight chỉ vì screen off/background.

## 6. Settings

Tối thiểu gồm:
- Đổi mật khẩu.
- Trạng thái kết nối/sync và lần sync gần nhất.
- Dữ liệu đang chờ gửi / thông tin chẩn đoán phù hợp.
- Gửi báo lỗi thủ công.
- Phiên bản, Beta/Stable, OTA.
- Thông tin thiết bị/app.

## 7. Footer / branding

Ở các màn hình phù hợp, căn giữa phía dưới:

`Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY`

Footer phải nhỏ, rõ nhưng không chiếm diện tích thao tác chính.

## 8. Beta vs Stable

- Giữ cùng hệ thiết kế và branding.
- Beta được nhận diện bằng tên app/badge `Beta` nhỏ; không thay đổi toàn bộ palette hoặc artwork.
- Tránh để người dùng nhầm channel nhưng vẫn giữ trải nghiệm nhất quán.

## 9. Performance constraints

- Ưu tiên native Android components/Compose implementation nhẹ.
- Hạn chế blur, shader, video background, parallax và animation liên tục.
- Không giữ UI timer chỉ để trang trí.
- Danh sách lớn phải lazy-render/paginate/filter tại local Room DB khi phù hợp.
- Scanner chỉ active ở màn hình/flow cần scan.

## 10. Canonical status

Mẫu 1, 2, 4, 5 chỉ còn là phương án tham khảo. MẪU 3 là baseline UI chính thức để triển khai Android từ thời điểm quyết định này, trừ khi chủ dự án ra quyết định thay thế sau này.
