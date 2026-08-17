# Pick Pack 1291

Ứng dụng Android phục vụ vận hành Pick Pack 1291, ưu tiên PDA Newland NLS-MT90 (Android 10+), đồng thời hỗ trợ thiết bị Android tương thích khác.

## Kiến trúc chính thức

`Android App ↔ Google Apps Script ↔ Google Sheets`

- Android native, ưu tiên hiệu năng, pin và thao tác scan trên PDA.
- Google Apps Script là lớp API/transaction bridge authoritative giữa app và Google Sheets.
- Google Sheets là **source of truth dữ liệu vận hành** giai đoạn hiện tại.
- Không dùng Supabase/Firebase/Neon/Cloudflare/database-server khác làm datastore, auth backend hoặc authority trung gian nếu chủ dự án chưa chỉ thị rõ ràng.
- Đồng bộ gần realtime chỉ khi app đang foreground/thiết bị đang tương tác.
- Mutation dùng event ID/idempotency, conflict rõ ràng và local pending/retry để tránh mất/trùng dữ liệu.
- Beta và Stable là hai applicationId riêng, có thể cài song song.
- Repository public: không chứa credential, dữ liệu nhân sự thật, khóa ký APK, token, secret hay cấu hình Google nhạy cảm.

Chi tiết quy tắc bắt buộc: [`ARCHITECTURE_GUARDRAILS.md`](ARCHITECTURE_GUARDRAILS.md).

## Trạng thái

Đang chuyển toàn bộ runtime Beta về Google Apps Script + Google Sheets và loại bỏ implementation Supabase không đúng mô hình.

Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY
