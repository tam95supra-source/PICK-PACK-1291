# HANDOVER CURRENT — Pick Pack 1291

Status: ACTIVE / cumulative / authoritative handover  
Last updated: 2026-08-18 06:05 +07:00 (Asia/Bangkok)  
Current closed session: S03  
Next session: S04

> **STOP RULE CHO S04:** Đầu phiên mới chỉ đọc kỹ file này, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md`, `docs/HANDOVER_POLICY.md` và snapshot `docs/handovers/HANDOVER_S03_2026-08-18.md`, xác nhận đã nắm trạng thái rồi **chờ lệnh chủ dự án**. Không tự build, deploy, sửa Sheet, chạy/rerun workflow, tạo release, upload/unlock APK hoặc mutation nào trước khi có lệnh mới.

## 1. Kiến trúc CHỐT

`Android App ↔ Google Apps Script Web App ↔ Google Sheets`

- Google Sheets là operational source of truth.
- Apps Script là API/transaction bridge gắn trực tiếp workbook.
- GitHub dùng source/CI/release infrastructure; không phải datastore nghiệp vụ.
- Không tự thêm Supabase/Firebase/Neon/Cloudflare/database/backend/service authority khác nếu owner chưa yêu cầu rõ.
- Beta phải full-function để test thật.
- Drive mutation chỉ trong cây `PICK PACK 1291 - CHÍNH THỨC`.

## 2. Ràng buộc workstation owner

Máy công ty của owner không chạy CMD/PowerShell/Terminal/CLI cục bộ.

- Không hướng dẫn owner chạy `git`, `gh`, `clasp`, `adb`, Gradle, Node/npm/npx, Java/keytool, OpenSSL…
- Command-line phải đưa lên GitHub Actions/CI/automation.
- Owner-facing setup dùng browser/UI: GitHub web, Apps Script UI, Google Drive/Workspace UI.

## 3. Workbook / schema

Workbook authoritative: `DỮ LIỆU THEO NGÀY`.

Tabs chính:
- `Danh mục`
- `DANH SÁCH NHÂN SỰ`
- `DANH SÁCH PDA`
- `DANH SÁCH USER PICK`
- `DANH SÁCH BÀN PACK`
- `DANH SÁCH USER PACK`
- `RA - VÀO TRONG CA`
- `CÔNG NHẬT`
- `Danh sách Admin`

Password không lưu plaintext; `Danh sách Admin` dùng verifier. Event/revision fields phải giữ cho idempotency/sync.

## 4. Business invariants

- `MNV` là business key.
- Session theo `MNV + business_date`: `NOT_ENTERED -> ACTIVE -> ENDED`.
- `ENDED` không vào lại cùng ngày qua flow thường.
- Mutation dùng immutable/idempotent `event_id`.
- Resource độc quyền phải chống race; đổi resource atomic; fail giữ resource cũ.
- State session/resource authoritative phải lấy từ Sheet API.
- Master/static data cache local theo revision; operational state vẫn kiểm động server.

### PICK/PACK hiện tại

- PICK bắt buộc PDA.
- **User Pick là tùy chọn**, được bỏ trống. Quyết định này supersede yêu cầu cũ “PICK bắt buộc User Pick”.
- PDA UI nhập 5 số cuối serial + autocomplete/gợi ý; chỉ nhận kết quả hợp lệ/duy nhất.
- PACK giữ mapping bàn Pack + User Pack theo ca và exclusivity.

## 5. Role / auth / session

Role: `SUPERADMIN`, `ADMIN`, `USER`; backend enforce quyền. `CÔNG NHẬT` hiện dành cho ADMIN/SUPERADMIN theo phân quyền app.

Auth:
- credential bình thường dùng salted PBKDF2-HMAC-SHA256;
- login challenge/HMAC proof;
- plaintext password không gửi trực tiếp tới Apps Script;
- không commit password/verifier thật/token/signing key/credential vào repo public.

### Session `SINGLE_ACTIVE_DEVICE_V1`

- Android lưu session bền trong private app storage.
- Tắt app/process kill rồi mở lại vẫn giữ đăng nhập.
- Không còn timeout bình thường 12 giờ.
- Cùng account login thành công ở installation/device khác sẽ thay active server session cũ.
- Thiết bị cũ nhận 401 ở request/sync kế tiếp và phải login lại.
- Explicit logout, account/security change hoặc reset password có thể kết thúc phiên.

### Quên mật khẩu — LIVE

- Public action `forgot_password`.
- App gửi username; response generic không lộ account tồn tại hay không.
- Rate limit 5 phút theo login + device.
- Account active nhận reset credential tạm, hết hạn sau 2 giờ.
- Mail mật khẩu tạm chỉ gửi về email quản trị owner đã chốt.
- Login đầu bằng mật khẩu tạm nâng lại về PBKDF2 verifier.
- Reset làm session cũ không còn hợp lệ.
- Apps Script MailApp đã được owner authorize bằng browser helper `ppAuthorizeMail()`.

Superadmin hiện dùng login `admin`. Reset thật đã PASS và mail đã tới Gmail. Có 2 mail reset liên tiếp; **chỉ dùng mail mới nhất**. Không ghi mật khẩu vào handover/chat/repo. One-time reset workflow đã được xóa sau khi hoàn tất.

## 6. UI / branding CHỐT — supersede Mẫu 1

Từ `0.4.2-beta.4+`, visual system chính thức là **Mẫu 2 — Minimal Teal Corporate**.

- White/light surface, teal primary, charcoal text, enterprise tối giản, compact PDA-friendly.
- Footer nhỏ sát đáy: `Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY`.
- Launcher icon dùng đúng artwork owner cung cấp, không redesign/inset/đổi ảnh.
- Routine success toast/noti phải hạn chế; intrusive notification chỉ cho lỗi, session replacement, security, OTA/sự kiện quan trọng.

Login:
- bỏ dòng Beta/version marketing;
- logo + fields + actions cân giữa màn hình;
- có `QUÊN MẬT KHẨU?`.

QR/performance:
- preview/search ưu tiên master cache local;
- `employee_context` không kéo master options/active labor nếu màn không cần;
- session state vẫn server-authoritative.

Báo cáo:
- bỏ các dòng tiêu đề thừa `NGUỒN LỰC` / `THÂM NIÊN`;
- khối hỗ trợ chỉ hiện khi tổng khấu trừ > 0;
- `Phúc Long` đứng trước `Kéo hàng`;
- giảm padding/margin để bảng sát màn hình hơn;
- ô 0/cột toàn 0 tiếp tục tối ưu hiển thị theo logic hiện có.

## 7. Google Apps Script — LIVE

Repo source và live Web App đã xác nhận:
- `api_version: 0.4.2`
- `mode: APP_GSHEET`
- `sheet_read: true`
- `auth_session_model: SINGLE_ACTIVE_DEVICE_V1`
- `update_check` BETA/STABLE đọc Google Drive đúng channel;
- `forgot_password` live;
- MailApp permission đã authorize;
- actual superadmin reset + mail delivery PASS.

Deploy GAS đã chuyển khỏi yêu cầu local `clasp`. Browser-only Google OAuth + Apps Script REST API dùng 5 GitHub Secrets đã cấu hình và hoạt động:
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GAS_SCRIPT_ID`
- `GAS_DEPLOYMENT_ID`

Không ghi giá trị secrets vào repo/handover.

## 8. OTA CHỐT từ 0.4.2+

Steady-state authority:

`Android -> GAS update_check -> Google Drive channel folder`

- BETA chỉ đọc `BẢN THỬ NGHIỆM`.
- STABLE chỉ đọc `BẢN ỔN ĐỊNH`.
- Không restore GitHub Releases làm steady-state OTA authority nếu owner chưa đổi yêu cầu.
- GitHub prerelease beta.2 chỉ là compatibility bridge cho legacy updater.
- App check ở open/foreground; không thêm polling background/screen-off.
- APK phải SHA-256 verify trước Android package installer.
- Android bình thường vẫn có thể yêu cầu user xác nhận cài/unknown-source; không phải silent Device Owner install.

Migration:
- `0.4.1-beta.1` cần cài OTA-enabled build thủ công một lần.
- `0.4.2-beta.2+` dùng GAS/Drive OTA.

## 9. Current Beta — `0.4.2-beta.4`

- Package: `vn.pickpack1291.app.beta.publicbeta`
- VersionCode: `10`
- VersionName: `0.4.2-beta.4`
- APK name: `pick-pack-1291-public-beta-v0.4.2-beta.4.apk`
- SHA-256: `e6bff0cc81f82cb6e8365f9fff3abd3e4c76dcfcfa65d85fe54789d131485084`
- Fixed signer SHA-256 phải giữ nguyên: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`

Gates PASS:
- Beta + Stable compile;
- package/version metadata;
- owner launcher resource;
- fixed signer;
- Drive upload;
- OTA E2E beta.3 -> beta.4;
- download Drive thật + SHA match;
- beta.4 không update lại chính nó;
- Stable isolation khỏi Beta.

## 10. GitHub state / CI risk

Repo: `tam95supra-source/pick-pack-1291`, branch `main`.

Implementation head trước các commit handover S03:
`625037d8911b2051a1fd001e00ef8a7366b538b9` — remove one-time superadmin reset workflow.

Commit quan trọng S03:
- `38b13dcdf52daa4050eb209e8b27cf39e3eb3d10` — Minimal Teal + reset flow + performance/PDA/report changes.
- `bbe7c64f29ea24731120dabeab852a23123b9158` — public Apps Script MailApp authorization helper.
- `625037d8911b2051a1fd001e00ef8a7366b538b9` — delete one-time reset workflow.

### P0 CI technical debt

`.github/workflows/beta-preview.yml` **vẫn hardcode beta.3/versionCode 9** ở metadata/sign/release trong khi source hiện là beta.4/versionCode 10.

=> Không coi workflow này là pipeline release chuẩn cho bản kế tiếp cho tới khi sửa/consolidate. Trước release mới phải làm version metadata dynamic hoặc đồng bộ target hiện tại, tránh phát nhầm beta.3.

Beta4 được build bằng workflow riêng `build-beta4-final.yml`, deploy GAS bằng `beta4-deploy-gas.yml`, verify OTA bằng `verify-ota-beta4-final.yml`.

Repo còn nhiều workflow migration/repair/verify one-shot. Chỉ cleanup sau khi owner ra lệnh và đã rà soát gate cần giữ.

### Android signing automation

4 Actions signing secrets chưa được xác nhận cấu hình đầy đủ:
- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

Beta4 đã được ký bằng recovery material chính thức và fixed signer đúng. Full-auto sign/release vẫn là backlog nếu owner muốn hands-off release. Không expose signing material.

## 11. Sync / scanner / logging

Sync:
- foreground sync open/resume;
- background/screen-off không khởi tạo polling mới;
- request đang chạy được phép drain.

Scanner:
- MNV numeric;
- IME/hardware Enter suffix support;
- Newland/PDA hardware cần test thiết bị thật sau Beta4.

Logging:
- MANUAL -> `BÁO LỖI THỦ CÔNG`;
- CRASH -> `BÁO LỖI TỰ ĐỘNG`;
- DAILY -> `NHẬT KÝ ANDROID`;
- redact secrets; local chỉ xóa sau ACK thành công.

## 12. DONE S03

- Ghi rule no-local-CLI toàn dự án.
- Browser-only OAuth/REST deploy GAS hoạt động.
- OTA chuyển sang GAS + Drive Beta/Stable.
- GAS 0.4.2 + WEB_APP + health gates PASS.
- Icon owner artwork đúng và session persistent/single-active-device từ beta3.
- Chốt Minimal Teal Corporate beta4.
- Center login, bỏ Beta/version text.
- Tối ưu login và QR latency.
- PDA last-5 autocomplete; User Pick optional.
- Giảm routine notifications.
- Report layout/order/conditional support theo owner.
- Forgot password -> admin email + MailApp authorization.
- Reset thật superadmin và mail delivery PASS.
- Build/sign/upload beta4 + OTA E2E PASS.
- One-time reset workflow đã xóa.

## 13. TODO / device acceptance

### P0 trên PDA thật
- Cài/OTA beta4.
- Login superadmin bằng **mail reset mới nhất**.
- Đo loading login.
- Force close/mở lại -> session phải còn.
- Login account đó trên máy 2 -> máy 1 bị thay session ở request/sync kế.
- QR nhân sự: latency + NOT_ENTERED/ACTIVE/ENDED.
- PDA 5 số cuối -> gợi ý đúng; duplicate last5 không được chọn mơ hồ.
- PICK không User Pick -> lưu được.
- Báo cáo Minimal Teal trên kích thước PDA thật.
- Forgot password cho một user thường -> mail admin, generic response, mật khẩu tạm login trong 2 giờ.

### P0 trước release kế tiếp
- Sửa/consolidate `beta-preview.yml` hardcode beta3/versionCode9.
- Rà soát và cleanup one-shot workflows nếu owner yêu cầu.
- Nếu cần full-auto release: cấu hình/test 4 Android signing secrets bằng browser-only flow.
- Không thay OTA authority về GitHub Releases.

### Stable
- Chưa promote Stable chỉ vì Beta build PASS.
- Stable cần soak/test Beta thật trước khi release.
- Stable dùng cùng OTA code nhưng chỉ đọc `BẢN ỔN ĐỊNH`.

## 14. Known risks / technical debt

- `beta-preview.yml` stale hardcodes là rủi ro phát nhầm version.
- Nhiều workflow one-shot cần consolidate có kiểm soát.
- GAS còn constant GitHub Releases legacy dù runtime OTA authority đã là Drive; có thể cleanup sau.
- Actual latency/UX trên PDA thật chưa đo end-to-end sau beta4.
- Android installer vẫn cần user interaction trên thiết bị bình thường.
- Forgot-password public route hiện có generic response + 5-minute rate limit; cần theo dõi abuse/mail quota nếu rollout rộng.

## 15. Cách tiếp tục S04

1. Đọc handover/guardrails, xác nhận trạng thái, chờ owner.
2. Nếu owner báo lỗi Beta4: inspect logs/reproduce trước, không đổi kiến trúc.
3. Nếu release tiếp: **sửa CI hardcode trước**, tăng version/versionCode, deploy GAS nếu source GAS đổi, build, signer gate, Drive upload, OTA E2E.
4. Nếu Stable: soak Beta trước, giữ fixed signer, upload duy nhất vào Stable folder.
5. Không hướng dẫn owner dùng CMD/PowerShell/terminal.
