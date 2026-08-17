# Pick Pack 1291 — Deploy Google Sheet API

Đây là bước triển khai duy nhất cần thực hiện trong Google Workspace cho mô hình đã duyệt:

`Android App ↔ Google Apps Script ↔ Google Sheets`

Không dùng Supabase/Firebase/database/backend ngoài mô hình này.

## Workbook đích

- Spreadsheet: `DỮ LIỆU THEO NGÀY`
- ID: `1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78`

## Tạo Web App gắn với Sheet

1. Mở workbook trên.
2. Chọn **Extensions → Apps Script**.
3. Trong project Apps Script vừa mở, thay nội dung code bằng file [`google-apps-script/PICK_PACK_API.gs`](google-apps-script/PICK_PACK_API.gs).
4. Bật hiển thị manifest nếu cần và đặt `appsscript.json` theo file [`google-apps-script/appsscript.json`](google-apps-script/appsscript.json).
5. Chọn **Deploy → New deployment → Web app**.
6. Execute as: **Me** (chủ workbook).
7. Who has access: **Anyone**. Web app vẫn có lớp đăng nhập/challenge-proof riêng dựa trên `Danh sách Admin`; quyền Anyone chỉ cho phép APK gọi endpoint Web App.
8. Authorize quyền Spreadsheet/Drive khi Google yêu cầu.
9. Copy URL kết thúc bằng `/exec`.

## Kiểm tra trước khi phát hành APK

POST JSON sau vào `/exec`:

```json
{"action":"health"}
```

Chỉ được phát hành nếu response có:

```json
{"ok":true,"mode":"APP_GSHEET","sheet_read":true}
```

## Quy tắc release

- URL `/exec` là cấu hình public endpoint, không phải password/secret.
- APK Beta/Stable không chứa credential Google.
- Password người dùng không gửi plaintext; app dùng PBKDF2 + challenge/HMAC proof.
- CI phải fail nếu source runtime quay lại endpoint/SDK backend ngoài mô hình đã duyệt.
