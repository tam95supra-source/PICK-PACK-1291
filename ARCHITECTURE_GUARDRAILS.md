# PICK PACK 1291 — Architecture Guardrails

## Mô hình được phép

Mô hình dữ liệu/vận hành của dự án là:

`Android App ↔ Google Apps Script ↔ Google Sheets`

- Google Sheets là nguồn dữ liệu vận hành (source of truth) của giai đoạn hiện tại.
- Google Apps Script chỉ là lớp API/transaction bridge gắn với Google Sheets; không được biến thành một database riêng.
- GitHub chỉ dùng cho source/CI/phát hành APK; không phải backend dữ liệu vận hành.

## Phạm vi Google Drive được phép

- Mọi file dữ liệu, log, bản phát hành, bàn giao hoặc gói deploy của Pick Pack 1291 chỉ được thao tác bên trong cây Drive `PICK PACK 1291 - CHÍNH THỨC`.
- Không tự tạo, chuyển, sao chép hoặc dùng thư mục Pick Pack khác ngoài cây `PICK PACK 1291 - CHÍNH THỨC`.
- Nếu một giới hạn kỹ thuật thực sự buộc phải phát sinh file/thư mục ngoài cây chính thức, phải dừng phần đó và xin xác nhận chủ dự án trước.
- Không được tái sử dụng service, thư mục, Apps Script hay tài nguyên của dự án khác cho Pick Pack 1291 chỉ vì chúng đang tồn tại.

## Quy tắc bắt buộc

1. **Không tự suy diễn kiến trúc.** Không được tự thêm, thay hoặc chuyển authority sang Supabase, Firebase, Neon, Cloudflare, database/server trung gian hay dịch vụ backend khác nếu chủ dự án chưa yêu cầu rõ ràng.
2. **Không làm trái mục đích/yêu cầu đã chốt.** Khi có nhiều cách triển khai, phải ưu tiên cách nằm trong mô hình và mục đích đã được chủ dự án xác định.
3. **Không coi trạng thái bàn giao/code cũ là quyền thay đổi yêu cầu.** Nếu code hiện tại lệch với yêu cầu đã chốt, phải sửa code về đúng yêu cầu; không được lấy implementation lệch làm kiến trúc mặc định.
4. **Mọi thay đổi authority, datastore, auth backend, service trung gian hoặc mô hình đồng bộ đều cần chỉ thị rõ ràng của chủ dự án trước khi triển khai.** Không có chỉ thị thì không được thêm.
5. **Nếu gặp giới hạn kỹ thuật cần thay đổi kiến trúc**, dừng phần thay đổi kiến trúc đó, nêu đúng giới hạn và các lựa chọn tối thiểu; không tự chọn một dịch vụ mới.
6. **Không làm mất dữ liệu đã ghi nhận.** Trước khi loại bỏ implementation cũ phải đối soát dữ liệu nghiệp vụ đã phát sinh với Google Sheets.
7. **Beta phải full-function theo cùng business rules** để test thật; không dùng backend tạm khác mô hình chỉ để làm nhanh.
8. **Foreground sync:** mở/quay lại app sync ngay; khi app ở background/screen off không khởi tạo polling mới. Request đang chạy được phép drain rồi suspend.
9. **Mutation phải idempotent** bằng `event_id`; tranh tài nguyên phải fail rõ ràng; đổi tài nguyên phải atomic trong phạm vi transaction/lock của Google Apps Script + Google Sheets.
10. **Security:** không commit password plaintext, verifier, token, signing key hoặc credential vào repo public. Hidden Sheet không được coi là security boundary.
11. **Master data phải cache:** danh sách nhân sự/PDA/User Pick/Bàn Pack/User Pack/Danh mục được cache trên thiết bị và có revision riêng. Chỉ refresh khi master revision thay đổi; trạng thái phiên/tài nguyên đang sử dụng vẫn phải kiểm tra động để chống cấp trùng.
12. **Log phải route đúng loại:** MANUAL → `BÁO LỖI THỦ CÔNG`; CRASH → `BÁO LỖI TỰ ĐỘNG`; DAILY → `NHẬT KÝ ANDROID`, đều nằm dưới `PICK PACK 1291 - CHÍNH THỨC/NHẬT KÝ HỆ THỐNG`.

## Quy tắc kiểm tra trước khi phát hành

Một bản Beta/Stable không được tuyên bố đúng mô hình nếu APK còn tham chiếu runtime tới Supabase hoặc backend ngoài mô hình được duyệt. CI phải quét source/workflow để chặn các endpoint/SDK Supabase trong app runtime.
