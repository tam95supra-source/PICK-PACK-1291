# HANDOVER CURRENT — Pick Pack 1291

Status: ACTIVE / cumulative / authoritative handover  
Last updated: 2026-08-17 19:37 +07:00 (Asia/Bangkok)  
Current closed session: S02  
Next session: S03

> **STOP RULE CHO S03:** Phiên mới chỉ đọc kỹ file này, `AGENTS.md`, `ARCHITECTURE_GUARDRAILS.md` và snapshot `docs/handovers/HANDOVER_S02_2026-08-17.md`, xác nhận đã nắm trạng thái rồi **chờ lệnh chủ dự án**. Không tự build, deploy, sửa Sheet, push GitHub, tạo release, chạy/rerun workflow, unlock APK, thêm service hoặc thực hiện mutation nào trước khi có lệnh mới.

## 1. Kiến trúc CHỐT

Mô hình vận hành chính thức:

`Android App <-> Google Apps Script Web App <-> Google Sheets`

- Google Sheets là operational source of truth.
- Apps Script là lớp API gắn trực tiếp workbook.
- Không tự thêm Supabase/Firebase/Neon/Cloudflare/database/backend authority khác.
- GitHub chỉ dùng source/CI/release/OTA.
- Beta phải full-function để test.
- Drive chỉ thao tác trong root chính thức của dự án; chi tiết nội bộ nằm trong bản handover Drive, không public trong repo.

## 2. Workbook / schema

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

Cột kỹ thuật đã có cho event/revision ở RA-VÀO và CÔNG NHẬT. Password không lưu plaintext; `Danh sách Admin` dùng PBKDF2 verifier.

Master-data hiện biết:
- Ca: `Ca 1`, `Ca 2`, `Ca HC`.
- PICK cần PDA + User Pick.
- PACK cần Pack table + User Pack map theo Ca.
- Có anomaly master Pack đã biết; API phải cảnh báo/loại mapping invalid, không tự sửa Sheet.

## 3. Business invariants

- `MNV` là business key.
- Session theo `MNV + business_date`: `NOT_ENTERED -> ACTIVE -> ENDED`.
- `ENDED` không VÀO lại cùng ngày qua flow thường.
- Mutation dùng immutable/idempotent event ID.
- PDA/User Pick/Bàn Pack/User Pack là exclusive resource.
- Tranh tài nguyên phải conflict rõ; đổi resource atomic và fail phải giữ resource cũ.
- Không silent overwrite accepted history.
- State operational authoritative phải lấy từ Sheet API.

## 4. Role / security

Role: `SUPERADMIN`, `ADMIN`, `USER`; backend phải enforce quyền.

Auth:
- salted PBKDF2-HMAC-SHA256 verifier;
- APK tính PBKDF2 + challenge/HMAC proof;
- plaintext password không gửi tới Apps Script;
- không commit password, verifier thật, token, signing key, recovery secret hoặc log/dữ liệu nhạy cảm vào public repo.

Fixed Android signing identity phải được bảo toàn giữa các bản update; private signing material nằm ngoài public repo.

## 5. UI / branding CHỐT

Baseline: **Mẫu 1**.
- nền sáng, appbar navy, card màu đặc, chữ/icon trắng;
- không lấn statusbar/cutout;
- footer nhỏ sát đáy: `Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY`;
- icon phải dùng đúng artwork chủ dự án cung cấp, không redesign.

Trang chủ hiện định hướng:
- `QUÉT QR NHÂN SỰ`
- `DANH SÁCH NHÂN SỰ`
- `CÔNG NHẬT` cho ADMIN/SUPERADMIN
- `THEO DÕI CA`
- `BÁO CÁO`
- `CÀI ĐẶT`

`QUÉT QR NHÂN SỰ` phải là card cùng kiểu các card khác. Bỏ text giải thích dài; chỉ giữ text thật cần như `Scan để bắt đầu hoặc kết thúc công nhật.`

## 6. Cache / search v0.4.2

Yêu cầu: tìm/scan MNV phải phản hồi gần như ngay, không round-trip Sheet cho master lookup.

Source v0.4.2 đã refactor:
- local master snapshot cache;
- index nhân sự theo MNV;
- local search MNV/họ tên/nhà thầu/vị trí;
- màn `DANH SÁCH NHÂN SỰ`;
- scan có thể render preview local trước khi server xác nhận session live.

Chỉ master/static data được cache. Session/resource operational state vẫn server/Sheet-authoritative.

## 7. Báo cáo v0.4.2

Phạm vi:
- `Ca 1 + Ca HC`
- `Ca 2`
- `Cả ngày`

Nhà thầu viết tắt:
- NLV = Nguồn Lực Việt
- HAD = Hoa Anh Đào
- VW = Việt Work
- MP = Man Power
- MGL = Mega Link
- HGP = Hà Gia Phát
- IH = Inhouse

UI report:
- ô = 0 để trống;
- cột nhà thầu toàn 0 thì ẩn;
- bảng tự co, không tràn form;
- text có thể wrap.

Thâm niên:
- mới `<= 30 ngày`;
- cũ `> 30 ngày`;
- chia cột nhà thầu như bảng nguồn lực.

Nhân sự đi hỗ trợ:
- lấy từ `CÔNG NHẬT`;
- có `Khấu trừ nhân sự`;
- Có/tích thì tính khấu trừ;
- Không thì không tính;
- vị trí cố định như Kéo hàng/Tổ trưởng công nhật không tính trừ người.

Android/GAS source 0.4.2 đã được chỉnh cho report/deduction. **Không coi production-active cho tới khi GAS 0.4.2 live và test Sheet thật.** Live Sheet cũng phải được kiểm tra schema `Khấu trừ nhân sự` sau deploy, không tự giả định đã có.

## 8. Google Apps Script — điểm dừng

Repo source hiện có API version `0.4.2`.

Live Web App lần cuối được xác nhận qua CI khoảng 19:18 +07 ngày 2026-08-17 vẫn trả:
- `api_version: 0.4.1`
- `sheet_read: true`
- revision 2
- master revision 1

=> GAS 0.4.2 **chưa được xác nhận live**. Không release/unlock APK 0.4.2 trước khi deploy 0.4.2 và health gate PASS.

Deploy bundle 0.4.2 đã được đóng gói; chi tiết file nội bộ nằm trong Drive handover.

## 9. Android Beta 0.4.2

Metadata:
- package `vn.pickpack1291.app.beta.publicbeta`
- versionCode `7`
- versionName `0.4.2-beta.1`

CI build `32029460958`:
- architecture gate PASS;
- API probe PASS;
- Beta/Stable assemble PASS;
- package metadata PASS;
- unsigned signing toolkit upload PASS;
- automated sign/release SKIPPED vì Actions signing secrets chưa có.

Một APK 0.4.2 đã được staged trong Drive chờ deploy GAS, nhưng **chưa được unlock/release**.

### P0 checksum mismatch phát hiện khi bàn giao

Read-only verification ngay trước handover cho thấy:
- checksum companion staged ghi `61367187168593269143ac6ba0840e361c1a6fd95a1a452186f3d997e8184f0f`;
- hash thực tế của APK staged tải từ Drive là `056acdfd3ab9a9b8e03395e4ac3ee076f17bbdc9f4ccc1950fed1dd4d7cdf96c`.

=> Không publish OTA/unlock 0.4.2 với checksum hiện tại. Khi owner ra lệnh phải re-verify APK signer/SHA, regenerate checksum, rồi mới đi tiếp sau GAS 0.4.2 health PASS.

## 10. Beta 0.4.1

- Beta package giữ `vn.pickpack1291.app.beta.publicbeta`.
- `0.4.1-beta.1`, versionCode 6.
- 0.4.1 đã được mở trên Drive sau khi GAS 0.4.1 live được xác nhận.
- Có thể cài đè 0.4.0 nếu cùng fixed signer.

Không tuyên bố protected business flows đã E2E PASS nếu chưa test thiết bị thật.

## 11. OTA — trạng thái thật

OTA client hiện:
- đọc GitHub Releases;
- Beta lấy prerelease, Stable lấy release;
- tự check khi app mở/quay foreground;
- interval guard khoảng 10 phút;
- DownloadManager tải APK;
- verify SHA-256;
- mở Android package installer.

GitHub Releases tại cuối S02 vẫn dừng ở Beta `0.3.0-beta.2-publicbeta`; chưa có GitHub Release 0.4.1/0.4.2. Vì vậy file APK chỉ nằm trên Drive **không làm app OTA nhìn thấy**.

Android có thể vẫn yêu cầu user xác nhận unknown-source/install; OTA hiện không phải silent Device Owner install.

### Push-triggered OTA

Đã thảo luận phương án publish GitHub Release -> push signal -> foreground app hiện update / background notification -> app xác minh GitHub Release + SHA.

FCM chỉ được đề xuất làm kênh push, không làm data authority. **Trạng thái: ĐỀ XUẤT, CHƯA ĐƯỢC OWNER PHÊ DUYỆT.** Do guardrail cấm tự thêm Firebase/service ngoài, S03 không được thêm FCM nếu chưa có lệnh rõ. Foreground release check nên giữ làm fallback nếu sau này push được duyệt.

## 12. Tự deploy GAS / tự publish OTA — quyền còn thiếu

Owner đã hỏi cách cấp quyền. Phương án được hướng dẫn: Apps Script API + `clasp` + GitHub Actions secrets.

Các secret dự kiến:
- `CLASPRC_JSON`
- `CLASP_JSON`
- `GAS_DEPLOYMENT_ID`
- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

**Chưa có xác nhận owner đã cấu hình các secret này.** Không tự kiểm tra/đổi secrets hay dựng pipeline mới ở đầu S03.

Mục tiêu pipeline khi owner cấp quyền và ra lệnh:
`push source -> deploy GAS -> health gate -> build -> sign -> verify signer -> GitHub Release -> OTA visible`.

## 13. Sync / scanner / logging

Sync:
- foreground sync ngay khi mở/quay lại;
- adaptive polling khi foreground;
- background/screen off không mở polling mới;
- request đang chạy được phép hoàn tất trước khi suspend;
- không tuyên bố SLA realtime nhiều PDA nếu chưa test thật.

Scanner:
- numeric MNV;
- IME action;
- hardware Enter suffix support;
- Newland NLS-MT90 cần test thiết bị thật.

Logging:
- MANUAL -> thư mục báo lỗi thủ công;
- CRASH -> thư mục báo lỗi tự động;
- DAILY -> nhật ký Android;
- local chỉ xóa sau ACK thành công;
- redact secrets.

## 14. GitHub / guardrails

Repo public: `tam95supra-source/pick-pack-1291`, branch `main`.

Implementation head trước các commit handover S02:
`de1777859004d2b1060b5bfee62363d825b2b061` (`chore: remove forbidden legacy OTA workflow`).

Bắt buộc đọc:
- `AGENTS.md`
- `ARCHITECTURE_GUARDRAILS.md`
- `docs/HANDOVER_POLICY.md`
- `docs/HANDOVER_CURRENT.md`

Legacy OTA workflow còn tham chiếu Supabase đã được xóa. Không quay lại Supabase/provisional S01.

## 15. DONE S02

- Chốt và vận hành lại kiến trúc App <-> Apps Script <-> Google Sheets.
- GAS 0.4.1 owner deploy + health PASS.
- Beta 0.4.1 build/ký/Drive đã mở.
- Cải thiện cache/master revision, scanner Enter, swipe-back, logging route, UI Mẫu 1.
- Nhận và implement yêu cầu 0.4.2 về icon chính xác, cache search nhanh, danh sách nhân sự, card QR, dọn text, report nguồn lực/thâm niên/hỗ trợ/khấu trừ.
- Android/GAS source 0.4.2 implement xong; CI compile/package PASS.
- GAS deploy bundle 0.4.2 đã đóng gói.
- APK 0.4.2 đã staged nhưng chưa release.
- Phát hiện checksum mismatch P0 trước handover.
- Xác định OTA hiện phụ thuộc GitHub Release, không phụ thuộc file Drive.
- Thảo luận push OTA qua FCM nhưng chưa approve.
- Hướng dẫn owner cấp quyền `clasp`/Actions secrets; chưa xác nhận hoàn tất.

## 16. TODO / backlog

### P0
1. **Đầu S03: chỉ đọc handover rồi chờ lệnh.**
2. Khi owner ra lệnh: re-verify staged APK 0.4.2 signer + SHA và sửa checksum mismatch.
3. Deploy/verify GAS 0.4.2 live.
4. Verify Sheet schema `Khấu trừ nhân sự`.
5. Sau backend PASS mới unlock APK 0.4.2.
6. Publish GitHub prerelease 0.4.2 đúng Beta channel.
7. Test update in-place 0.4.1 -> 0.4.2.

### Test nghiệp vụ
- login thật;
- hardware scanner/Newland;
- cache/search latency;
- NOT_ENTERED/ACTIVE/ENDED;
- PICK PDA + User Pick;
- PACK theo Ca;
- resource conflict >=2 PDA;
- VÀO/RA/resource change;
- Công nhật + Khấu trừ;
- báo cáo Ca 1+HC / Ca 2 / Cả ngày;
- tenure <=30/>30;
- hỗ trợ/khấu trừ;
- manual/crash/daily logs;
- revision/master cache refresh.

### CI/OTA
- Nếu owner đã cấu hình secrets và ra lệnh: nối auto deploy GAS + sign/publish release.
- Push-triggered OTA/FCM chỉ làm sau khi owner phê duyệt rõ.

## 17. SUPERSEDED

- Supabase/Edge Function/Postgres Pick Pack -> **SUPERSEDED**.
- Mẫu 3 -> Mẫu 1.
- VÀO/RA tách card -> `QUÉT QR NHÂN SỰ` context-aware.
- Beta giới hạn -> full-function Beta.
- Tài nguyên card độc lập -> resource change trong flow phiên nhân sự.
- OTA metadata qua backend cũ -> GitHub Releases.
- APK nằm trên Drive != OTA release.

## 18. Điểm bắt đầu S03

S03 phải:
1. đọc file này;
2. đọc `AGENTS.md`;
3. đọc `ARCHITECTURE_GUARDRAILS.md`;
4. đọc snapshot S02;
5. ghi nhận: live GAS lần cuối vẫn 0.4.1; source GAS 0.4.2; build 0.4.2 PASS nhưng staged checksum mismatch; 0.4.2 chưa GitHub Release; FCM chưa duyệt; deploy/signing secrets chưa được xác nhận;
6. trả lời ngắn rằng đã kiểm tra và **CHỜ LỆNH**;
7. **không tự chạy bất kỳ build/deploy/workflow/release/write/mutation nào**.

Đây là yêu cầu trực tiếp cuối S02 của chủ dự án và có priority cao nhất cho hành vi mở đầu S03.
