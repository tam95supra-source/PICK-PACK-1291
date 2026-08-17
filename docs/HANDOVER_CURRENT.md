# HANDOVER CURRENT — Pick Pack 1291

Status: ACTIVE / cumulative / authoritative handover
Last updated: 2026-08-17 16:53 +07:00 (Asia/Bangkok)

> Mọi phiên/agent phải đọc `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md` và file này trước khi thay đổi implementation. Yêu cầu trực tiếp của chủ dự án là authority cao nhất. Không tự suy diễn, không tự thêm backend/service/datastore, không đổi mục đích hoặc kiến trúc nếu chưa được yêu cầu rõ.

## 1. Kiến trúc CHỐT

Mô hình vận hành chính thức hiện tại:

`Android APP <-> Google Apps Script Web App <-> Google Sheets`

- Google Sheets là nguồn dữ liệu vận hành authoritative.
- Apps Script chỉ là lớp API gắn trực tiếp với workbook để app đọc/ghi Sheet an toàn và atomic hơn; không có database vận hành thứ hai.
- Không Supabase, Firebase, Neon, Cloudflare database hay backend ngoài nào được phép tự thêm.
- Endpoint Apps Script đã được chủ dự án cung cấp và CI health-check PASS:
  `https://script.google.com/macros/s/AKfycbzbEoGfbNg6s2HnP-gUpcBJ7mMIkVBtYuQKMndb9seDV2c55lQwSUO1GZ-LtQ2CxMCauA/exec`
- Workbook authoritative: `DỮ LIỆU THEO NGÀY`, ID `1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78`.

## 2. Quy tắc chống tự suy diễn — CHỐT

- Không tự đổi kiến trúc, data authority, auth authority, distribution channel hoặc mục tiêu nghiệp vụ.
- Không lấy implementation tạm/legacy/handover cũ làm quyền thay thế yêu cầu trực tiếp của chủ dự án.
- Khi gặp mâu thuẫn: dừng phần mâu thuẫn, giữ dữ liệu, đối soát yêu cầu gốc rồi sửa về đúng yêu cầu.
- Không thêm service chỉ vì thuận tiện kỹ thuật.
- CI có architecture gate chặn reference/runtime Supabase quay trở lại.

## 3. Supabase — ĐÃ LOẠI KHỎI PICK PACK

- Toàn bộ bảng `pp_*`, function `pp_*`, sequence Pick Pack và Vault secret ký APK liên quan đã được xóa khỏi project Supabase cũ.
- Dữ liệu VÀO/RA đã phát sinh trước đó được đối soát với Sheet trước khi xóa; các dòng nghiệp vụ trong Sheet được giữ lại.
- Các Edge Function cũ `pick-pack-beta-api`, `pick-pack-sheet-worker`, `pick-pack-ci-signing` đã bị vô hiệu hóa và trả `410 DECOMMISSIONED`. Connector không có thao tác xóa Edge Function vật lý; chúng không còn đọc/ghi/giữ dữ liệu Pick Pack.
- Repo đã xóa thư mục/runtime/workflow Supabase liên quan.

## 4. Workbook / schema chính

Các tab chính:
- `Danh mục`
- `DANH SÁCH NHÂN SỰ`
- `DANH SÁCH PDA`
- `DANH SÁCH USER PICK`
- `DANH SÁCH BÀN PACK`
- `DANH SÁCH USER PACK`
- `RA - VÀO TRONG CA`
- `CÔNG NHẬT`
- `Danh sách Admin`

Đã bổ sung cột kỹ thuật phục vụ idempotency/revision trong chính Sheet, không dùng database ngoài.

## 5. Auth / role

- Role: `SUPERADMIN`, `ADMIN`, `USER`.
- Password plaintext không lưu trong Sheet và không gửi tới Apps Script.
- `Danh sách Admin` giữ salted `PBKDF2-HMAC-SHA256` verifier.
- APK thực hiện PBKDF2 và gửi challenge/HMAC proof; Apps Script xác thực proof.
- Tạo tài khoản/đổi mật khẩu tạo verifier phía APK trước khi ghi.
- Không commit verifier, password, token, signing key hoặc dữ liệu nhạy cảm vào repo public.

## 6. Business invariants

- `MNV` là business key.
- Session theo `MNV + business_date`: `NOT_ENTERED -> ACTIVE -> ENDED`.
- `ENDED` không VÀO lại trong ngày qua flow thường.
- VÀO/RA dùng immutable `event_id` để chống duplicate/retry.
- PDA/User Pick/Bàn Pack/User Pack là exclusive resource.
- Tranh tài nguyên phải conflict rõ; đổi tài nguyên phải atomic.
- Sheet mutation dùng Apps Script `LockService` cho các flow cần khóa.

## 7. UI / flow — CHỐT

- Baseline giao diện: **Mẫu 1**.
- Không lấn status bar/cutout.
- Footer nhỏ sát đáy: `Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY`.
- Trang chủ dùng một thẻ `QUÉT QR NHÂN SỰ`:
  - `NOT_ENTERED` -> thông tin + Ca/Vị trí/tài nguyên + `VÀO CA`.
  - `ACTIVE` -> thông tin phiên + tài nguyên + `RA CA`/đổi tài nguyên.
  - `ENDED` -> báo hết phiên hôm nay.
- Beta phải full-function để test toàn bộ chức năng.

## 8. Sync

- App foreground: sync ngay khi mở/quay lại và polling revision thích ứng.
- Background/screen off: không mở polling mới.
- Request đang chạy được phép hoàn tất trước khi suspend.
- Apps Script `PP_REVISION` dùng làm change detector; state authoritative vẫn reload từ Sheet API.
- Không tuyên bố SLA realtime cụ thể cho nhiều PDA cho tới khi test thiết bị thật.

## 9. Beta 0.4 — BUILD/KÝ ĐÃ PASS

Bản sửa đúng kiến trúc:
- Package: `vn.pickpack1291.app.beta.publicbeta`
- VersionCode: `5`
- VersionName: `0.4.0-beta.1`
- Apps Script health: PASS (`APP_GSHEET`, `sheet_read=true`).
- Android compile/package metadata: PASS.
- APK được ký bằng fixed certificate cũ để bảo toàn update identity.
- Certificate SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`.
- APK signature verification: v3 PASS.
- APK SHA-256: `47ba72713c2501be2cc49ccde2f8c07d42225cb9b4096d3f7a11abf7a89f1c0b`.
- APK đã upload Drive `BẢN THỬ NGHIỆM`: file ID `14340Jw__49AK8ye81o4N9Ij903YiNqZt`.

## 10. OTA

Client 0.4:
- tự check khi app mở/quay foreground;
- đọc Beta prerelease / Stable release từ GitHub Releases;
- DownloadManager tải APK;
- kiểm SHA-256;
- mở Android package installer.

Android vẫn có thể yêu cầu user cho phép unknown-source installer và xác nhận cài.

Bản 0.3.x cũ phụ thuộc API Supabase đã bị decommission nên chuyển 0.3.x -> 0.4 cần cài APK 0.4 thủ công một lần. Từ 0.4 trở đi OTA client không phụ thuộc Supabase.

### CI signing/publish

Fixed signing bundle đã được sao lưu mã hóa trong Google Drive riêng của chủ sở hữu; private recovery key chỉ owner có quyền.

CI chuẩn đã được chuẩn bị để tự ký + publish khi GitHub Actions có 4 secret:
- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

Connector GitHub hiện không có API quản lý Actions Secrets, vì vậy không được đưa secret vào repo để lách giới hạn này.

## 11. Scanner / test thực tế còn phải làm

- Test login bằng tài khoản thật trên PDA.
- Test VÀO/RA ghi trực tiếp Sheet.
- Test tranh tài nguyên trên >=2 PDA.
- Test Công nhật start/finish.
- Test hardware scanner Newland NLS-MT90; manual input/generic scanner là fallback.
- Test foreground sync nhiều máy.
- Test OTA sau khi CI signing secrets được cấu hình và có release mới hơn 0.4.

## 12. Repo guardrails

- `AGENTS.md`: bắt buộc tuân yêu cầu chủ dự án, cấm tự đổi mục đích/kiến trúc.
- `ARCHITECTURE_GUARDRAILS.md`: mô hình App <-> Apps Script <-> Google Sheets là authority hiện tại.
- `.github/workflows/beta-preview.yml`: health-check endpoint GSheet + architecture gate + build/package verification.

Không được quay lại nội dung Supabase/provisional của snapshot S01 làm kiến trúc hiện hành.