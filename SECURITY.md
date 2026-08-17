# Security Policy

## Public repository rule

Mọi nội dung trong repository này phải được xem là công khai vĩnh viễn, kể cả lịch sử Git đã xóa ở commit sau.

### Tuyệt đối không commit

- Mật khẩu hoặc password verifier lấy từ dữ liệu thật.
- Access token, refresh token, API key, webhook secret, cookie/session secret.
- Google service-account JSON, Apps Script secret, Spreadsheet/Drive cấu hình nhạy cảm không cần công khai.
- APK signing keystore, private key, certificate private material hoặc mật khẩu signing.
- File `.env`, `local.properties`, `secrets.properties` có giá trị thật.
- Log thực tế có thông tin tài khoản, thiết bị hoặc dữ liệu vận hành.
- Export Google Sheets/database thật hoặc dữ liệu nhân sự thật.

### Secret storage

- GitHub Actions secrets/variables: chỉ dùng cho CI/CD cần thiết.
- Server-side secret: lưu ngoài source code (ví dụ Apps Script Properties khi backend được triển khai).
- Android APK không được chứa secret có thể dùng để truy cập trực tiếp Google Sheets/Drive.

### Architecture boundary

Android client không truy cập Google Sheets bằng owner credential. Client chỉ gọi API backend và phải được xác thực/authorize ở server.

### Logging

Log phải tự động redact các trường nhạy cảm như `password`, `authorization`, `token`, `cookie`, `secret`, verifier và payload chứa credential trước khi ghi local hoặc upload.

### Incident rule

Nếu secret bị commit lên GitHub, coi secret đó đã bị lộ: revoke/rotate trước, sau đó mới xóa khỏi repository/history. Không coi việc xóa commit là đủ.
