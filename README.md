# Pick Pack 1291

Ứng dụng Android phục vụ vận hành Pick Pack 1291, ưu tiên PDA Newland NLS-MT90 (Android 10+), đồng thời hỗ trợ thiết bị Android tương thích khác.

## Nguyên tắc kiến trúc

- Android native, ưu tiên hiệu năng, pin và thao tác scan trên PDA.
- Google Apps Script là lớp API authoritative giữa app và Google Sheets.
- Google Sheets là kho dữ liệu vận hành giai đoạn đầu.
- Đồng bộ gần realtime chỉ khi app đang foreground/thiết bị đang tương tác.
- Mutation dùng event ID/idempotency, conflict rõ ràng và local pending queue để tránh mất/trùng dữ liệu.
- Beta và Stable là hai applicationId riêng, có thể cài song song.
- Repository public: không chứa credential, dữ liệu nhân sự thật, khóa ký APK, token, secret hay cấu hình Google nhạy cảm.

## Trạng thái

Đang ở giai đoạn khóa data/API contract và bootstrap bảo mật.

Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY
