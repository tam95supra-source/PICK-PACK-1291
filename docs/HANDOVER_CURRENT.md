# HANDOVER CURRENT — Pick Pack 1291

Status: ACTIVE / cumulative / authoritative handover
Session closed: S01
Last updated: 2026-08-17 15:35 +07:00 (Asia/Bangkok)

> File này là bản bàn giao kế thừa. Phiên chat mới phải đọc file này trước khi tiếp tục. Không được coi các quyết định cũ đã biến mất chỉ vì chat mới không còn lịch sử.

## 1. Mục tiêu dự án — CHỐT

- Xây Android APK ưu tiên PDA Newland NLS-MT90, Android 10 trở lên.
- Vẫn hỗ trợ điện thoại/PDA Android khác khi phù hợp.
- Mục tiêu vận hành ban đầu: dữ liệu nghiệp vụ liên kết với Google Sheets, nhiều PDA chia sẻ dữ liệu nhanh nhất có thể khi app đang mở.
- Khi app background/tắt màn hình: không tạo sync mới; nếu có transaction đang chạy thì vào `DRAINING`, chờ transaction hiện tại kết thúc rồi mới `SUSPENDED`.
- Tối ưu pin/hiệu suất, không chạy polling nền liên tục.
- GitHub repository public để tận dụng CI/CD miễn phí; source phải public-safe.
- Beta và Stable tách package/channel và cài song song được cho USER/ADMIN/SUPERADMIN.
- Beta phải có đầy đủ chức năng nghiệp vụ để pilot/test, không phải preview giới hạn.
- App tự phát hiện phiên bản mới và hiện yêu cầu cập nhật; không bắt user vào Cài đặt bấm kiểm tra thủ công.

## 2. Drive/database — CHỐT THEO HIỆN TRẠNG

Drive gốc tiếp tục giữ cơ chế share hiện tại theo quyết định chủ dự án để phục vụ công việc; không tự chuyển Restricted.

Các khối chính:
- `DỮ LIỆU VẬN HÀNH`
- `PHÁT HÀNH APK/BẢN THỬ NGHIỆM`
- `PHÁT HÀNH APK/BẢN ỔN ĐỊNH`
- `NHẬT KÝ HỆ THỐNG/NHẬT KÝ ANDROID`
- `NHẬT KÝ HỆ THỐNG/BÁO LỖI TỰ ĐỘNG`
- `NHẬT KÝ HỆ THỐNG/BÁO LỖI THỦ CÔNG`
- `NHẬT KÝ HỆ THỐNG/NHẬT KÝ WEB`
- `BÀN GIAO PHIÊN CHAT`

Workbook `DỮ LIỆU THEO NGÀY` có các tab nghiệp vụ/master chính:
- Danh mục
- DANH SÁCH NHÂN SỰ
- DANH SÁCH PDA
- DANH SÁCH USER PICK
- DANH SÁCH BÀN PACK
- DANH SÁCH USER PACK
- RA - VÀO TRONG CA
- CÔNG NHẬT
- Danh sách Admin

## 3. Logic nghiệp vụ kế thừa — CHỐT

- `MNV` là business key của nhân viên; không dùng họ tên làm key.
- Session theo `MNV + business_date`: `NOT_ENTERED -> ACTIVE -> ENDED`.
- Một phiên đã `ENDED` không được VÀO lại cùng ngày qua luồng thường.
- Mutation có immutable `event_id` để retry/idempotency không duplicate.
- PDA, User Pick, bàn Pack/User Pack là tài nguyên exclusive.
- Nhiều app tranh cùng tài nguyên: đúng một winner, các app còn lại nhận conflict rõ ràng.
- Đổi tài nguyên phải atomic; nếu đổi thất bại phải giữ tài nguyên cũ.
- Bàn Pack + User Pack xử lý theo bundle mapping.
- Accepted history không silent overwrite; correction phải audited.
- Offline/reconnect phải dựa trên pending queue + replay cùng event ID; không dựa vào việc process Android chắc chắn sống tới hết request.
- Conflict UI phải giữ dữ liệu người dùng đã nhập, chỉ yêu cầu sửa trường xung đột.

## 4. Role — CHỐT

Ba role:
- SUPERADMIN
- ADMIN
- USER

Nguyên tắc:
- USER: nghiệp vụ thường trong phạm vi được cấp.
- ADMIN: USER + Công nhật + quản lý USER/correction theo phạm vi.
- SUPERADMIN: quản lý ADMIN và quyền đặc quyền.
- Backend phải enforce quyền; không chỉ ẩn UI.

## 5. Password/account security — CHỐT TẠM THỜI

- Plaintext password trong Sheet đã bị loại bỏ.
- Tab `Danh sách Admin` đã được hidden.
- Password lưu dạng salted `PBKDF2-HMAC-SHA256` verifier; không lưu plaintext.
- Hidden Sheet không được coi là security boundary.
- Không commit password/verifier/token/service key/signing key/log thật vào GitHub public.
- App có chức năng user tự đổi mật khẩu.
- Log phải redact password, auth header/token, cookie, verifier, private key và signing secret.

### Sự cố login đã xử lý cuối S01

- Full Beta ban đầu báo sai mật khẩu cho mọi tài khoản dù user nhập đúng.
- Root cause: bảng backend `pp_accounts` có 7 tài khoản nhưng 7/7 chưa có `password_verifier`; backend Full Beta lại chuyển sang verify ở bảng này.
- Đã đồng bộ verifier server-side từ nguồn Sheet vào `pp_accounts` mà không đưa verifier vào repo/APK.
- Kết quả cuối: 7/7 account có verifier hợp lệ, 0 account đang bị lock; failed-attempt state do lỗi này đã reset.
- Không đổi mật khẩu thực tế của user.
- Fix này là backend-side, không cần cài APK mới.

## 6. Kiến trúc backend hiện tại — THỰC TẾ S01 / PROVISIONAL

### Quyết định ban đầu

Ban đầu dự kiến `APK -> Google Apps Script -> Google Sheets` để giữ mô hình 0đ và Sheet làm authoritative database.

### Thực tế Beta hiện tại

Trong S01, để có Public Beta thao tác thật nhanh, implementation đã chuyển tạm sang:

`Android APK -> Supabase Edge Function (pick-pack-beta-api) -> Supabase Postgres`

và:
- master data nhân sự/PDA/User Pick/Bàn Pack/User Pack/Danh mục đang đọc từ Google Sheet;
- transaction VÀO/RA, tài nguyên, Công nhật, auth/session, audit, diagnostic hiện lưu ở backend Beta;
- mutation tạo `server_seq`/event và xếp `pp_sheet_projection_queue` để dự kiến projection về Google Sheet.

### Quan trọng

- Đây là **implementation Beta tạm thời**, không được tự coi là quyết định cuối cho Stable.
- Mục tiêu ban đầu Google Sheets + chi phí 0đ vẫn còn hiệu lực về mặt yêu cầu sản phẩm.
- Trước Stable phải quyết định rõ: tiếp tục Supabase free-tier làm authority, hay chuyển/hoàn thiện Apps Script/Sheet authority theo yêu cầu ban đầu.
- Không dùng backend/service của dự án BÁO HÀNG cũ để tránh ghi nhầm database.

## 7. Google Sheet projection — CHƯA HOÀN THIỆN

- Public Beta hiện có durable transaction backend và projection queue.
- **Writer tự động ACK transaction xuống tab Google Sheet vận hành chưa hoàn thiện.**
- App có thể hiển thị số `chờ Sheet ACK`.
- Không được nói với user rằng transaction đã ghi Google Sheet nếu projection chưa ACK.
- Đây là hạng mục ưu tiên cao ở phiên tiếp theo vì yêu cầu cốt lõi là APK <-> Google Sheets và chia sẻ dữ liệu giữa các điều phối.

## 8. Realtime/sync — REQUIREMENT CHỐT, IMPLEMENTATION CẦN HOÀN THIỆN/ĐO

Requirement:
- App foreground + thiết bị interactive: sync nhanh nhất hợp lý.
- Mở app/return foreground: sync ngay.
- User mutation gửi ngay, không chờ polling.
- App khác nhận thay đổi qua server sequence/delta.
- Có thể adaptive polling/burst nhanh khi active, chậm khi idle.
- Background/screen off: không tạo polling mới.
- Nếu có request in-flight khi thoát/tắt màn hình: `DRAINING -> hoàn tất request -> SUSPENDED`.
- Không permanent socket/foreground service/wakelock dài hạn chỉ để sync.

Tình trạng code Beta:
- Mutation server-side hoạt động trực tiếp.
- Có `server_seq`, `sync_status` và backend state.
- Adaptive foreground delta-sync/polling nhiều PDA cần tiếp tục kiểm tra và hoàn thiện trên thiết bị thật; không được giả định đã đạt SLA 1-3 giây cho mọi máy.

## 9. Pin/hiệu suất — CHỐT

- Không continuous background polling.
- Không GPS nếu nghiệp vụ không cần.
- Không wake lock dài hạn.
- Scanner chỉ active trong flow cần scan.
- UI nhẹ, tránh animation nặng.
- Offline/retry phải có backoff/network callback.
- Mục tiêu dài hạn vẫn là local durable queue/Room; cần đối chiếu implementation hiện tại trước khi tuyên bố offline đầy đủ.

## 10. UI/branding — MẪU 1 LÀ CHỐT HIỆN TẠI

### Quyết định bị thay thế

- Mẫu 3 từng được chốt ban đầu nhưng **đã SUPERSEDED** sau khi test trên thiết bị thật.

### Baseline hiện tại

- Dùng **Mẫu 1 — tối giản/hiện đại**, nền sáng, app bar navy, card màu đặc, icon/chữ trắng.
- Layout phải nằm dưới status bar/cutout; không lấn thanh trạng thái của thiết bị.
- Footer luôn ở giữa sát đáy, nhỏ hơn nội dung chính:
  `Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY`
- Artwork do chủ dự án cung cấp là master icon/artwork; không redesign nội dung, chỉ resize/pad kỹ thuật cho Android.
- Ưu tiên PDA ~5 inch, nút lớn, thao tác một tay, scan-first, ít keyboard.

## 11. Flow VÀO/RA — CHỐT

Trang chủ không còn hai thẻ VÀO CA và RA CA riêng.

Dùng một thẻ:
- `QUÉT QR NHÂN SỰ`

Flow:
1. User quét/nhập MNV.
2. Backend lấy trạng thái session hôm nay.
3. Nếu `NOT_ENTERED`: hiện thông tin nhân sự + form Ca/Vị trí/tài nguyên + nút `VÀO CA`.
4. Nếu `ACTIVE`: hiện thông tin phiên/tài nguyên + nút `RA CA` và thao tác đổi tài nguyên/vị trí.
5. Nếu `ENDED`: báo đã hết phiên VÀO/RA hôm nay; không hiện VÀO lại luồng thường.

## 12. Full Public Beta — ĐÃ PHÁT HÀNH

Release hiện tại:
- Version: `0.3.0-beta.1`
- GitHub tag: `v0.3.0-beta.1-publicbeta`
- Package: `vn.pickpack1291.app.beta.publicbeta`
- Min Android: 10 / API 29
- APK đã build và verify bằng GitHub Actions.
- APK đã upload GitHub prerelease và Drive `PHÁT HÀNH APK/BẢN THỬ NGHIỆM`.
- SHA-256 của release 0.3.0-beta.1: `8781c6d96f645bddd385d0ddebb331a1cb9357b2be3504f8d2b38ffaf48e6a12`.

Các module đã mở trong Full Beta:
- Login thật.
- QUÉT QR NHÂN SỰ / VÀO / RA.
- Công nhật start/finish.
- Đổi tài nguyên/vị trí atomic.
- Danh sách phiên/công nhật/tìm nhân sự.
- Báo cáo ngày cơ bản.
- Cài đặt / đổi mật khẩu / diagnostic ACK.
- ADMIN/SUPERADMIN account management theo role.

Lưu ý: `QUÉT QR` hiện phải tiếp tục kiểm tra tích hợp scanner phần cứng Newland; tên flow có nhưng không được mặc định rằng Newland scanner SDK/provider đã hoàn thiện.

## 13. Stable channel — ĐÃ CÓ BUILD CHANNEL, CHƯA PHÁT HÀNH PRODUCTION

- Stable package: `vn.pickpack1291.app.stable`.
- Stable channel build đã compile/package verify trong CI.
- Chưa phát hành production Stable.
- Beta/Stable share functional source và update client nhưng package/version channel tách riêng.

## 14. OTA — ĐÃ CÓ CLIENT/CHECKER, CÒN BLOCKER SIGNING

Đã implement:
- App gọi update check khi mở/quay foreground.
- Backend phân Beta prerelease và Stable release riêng.
- Khi có version mới, app tự hiển thị prompt; user không phải vào Settings bấm check thủ công.
- Download qua Android DownloadManager.
- Verify SHA-256 trước khi mở package installer.
- Áp dụng cùng cơ chế cho Beta và Stable.

Giới hạn Android:
- Android có thể yêu cầu user cấp quyền cài app không rõ nguồn và xác nhận installer; không được bypass bảo mật hệ điều hành.

### Blocker signing

- CI hiện vẫn đang dùng debug signing identity cho pilot.
- OTA in-place lâu dài yêu cầu **fixed signing key** được lưu ngoài public repo, ví dụ GitHub Actions Secrets hoặc secure external secret store.
- Không được commit keystore/private key/password lên GitHub public.
- Trước khi phát hành chuỗi OTA chính thức phải khóa signing baseline cho cả Beta và Stable.
- Bản 0.2 cũ không có updater; từ 0.3 trở đi updater đã có, nhưng nếu signing identity thay đổi thì Android vẫn không cho update đè tại chỗ.

## 15. Logging — REQUIREMENT CHỐT / STORAGE DRIVE CÒN PHẦN KẾT NỐI

Ba luồng Drive yêu cầu:
1. Crash tự động -> `BÁO LỖI TỰ ĐỘNG`.
2. User gửi thủ công -> `BÁO LỖI THỦ CÔNG`.
3. Daily Android log, một lần/ngày khi app có cơ hội foreground -> `NHẬT KÝ ANDROID`.

Diagnostic bundle phải đủ để điều tra: build/channel/version, device/model/Android, role/account ID phù hợp, screen/flow, network, sync state/cursor, pending summary, breadcrumbs, exception/stacktrace, DB/performance/memory, scanner, OTA, business event result; redact toàn bộ secret.

Crash logic:
- ghi local trước;
- thử upload nếu có thể;
- chưa ACK thì giữ pending;
- lần mở sau gửi lại;
- chỉ xóa local sau ACK.

Tình trạng hiện tại:
- Backend Full Beta có endpoint/action `diagnostic_log` và ACK vào backend diagnostic table.
- Luồng lưu file thực tế vào các thư mục Drive nêu trên cần tiếp tục hoàn thiện/verify; không được coi diagnostic ACK backend là đã lưu Drive.

## 16. GitHub public security — CHỐT

Repository: `tam95supra-source/pick-pack-1291` — Public.

Đã có:
- `README.md`
- `.gitignore`
- `SECURITY.md`
- `docs/HANDOVER_POLICY.md`
- `docs/HANDOVER_CURRENT.md`
- `docs/UI_SPEC.md`
- sync/logging specs và source Android/CI.

Không commit:
- plaintext password/verifier thật
- Google service/owner credentials
- Supabase service role key
- signing keystore/private key/password
- operational logs thật
- database/nhân sự export thật
- token/session secret

Public repo phải coi mọi commit history là công khai vĩnh viễn; secret lỡ commit phải rotate.

## 17. CI/CD — ĐÃ HOẠT ĐỘNG

- GitHub Actions build Android trên public repo.
- Workflow Full Beta/Stable đã build PASS sau khi sửa lỗi Kotlin lexical whitespace.
- Source Kotlin đã được normalize và one-shot normalization workflow đã bị xóa sau khi persist fix.
- Main head cuối phiên S01 khi kiểm tra: `f27af4c5b1291b1a15c7ddfed9cc7b6475b88829` (`chore: remove one-shot normalization workflow`).
- Release Beta 0.3.0-beta.1 được build/verify/publish thành công từ workflow channel build.

## 18. Những quyết định SUPERSEDED / KHÔNG ĐƯỢC ÁP LẠI MÁY MÓC

- `UI Mẫu 3` -> SUPERSEDED bởi `UI Mẫu 1`.
- `VÀO CA` và `RA CA` là hai thẻ riêng -> SUPERSEDED bởi `QUÉT QR NHÂN SỰ` context-aware.
- Beta chỉ là UI Preview/giới hạn -> SUPERSEDED; Beta phải full-function test build.
- `background -> cancel request ngay` -> SUPERSEDED; phải `DRAINING` transaction hiện tại rồi suspend.
- Apps Script authoritative là kế hoạch ban đầu -> hiện **không phải backend Beta đang chạy**; backend Beta đang dùng Supabase provisional. Quyết định kiến trúc Stable còn mở.

## 19. DONE — CUỐI S01

- Đọc Drive/database và tài liệu `.md` dự án cũ, chắt lọc invariant phù hợp.
- Kiểm tra quyền Drive/GitHub; repo public hoạt động.
- Loại plaintext password khỏi Sheet, chuyển verifier, hide tab Admin.
- Tạo `BÁO LỖI THỦ CÔNG` và `BÀN GIAO PHIÊN CHAT` trên Drive.
- Xây source Android baseline Android 10+.
- Chuyển UI sang Mẫu 1 theo test thiết bị thật.
- Sửa status bar inset/footer theo feedback PDA.
- Xây flow context-aware QUÉT QR NHÂN SỰ.
- Xây Full Beta backend/API và các module nghiệp vụ cơ bản.
- Xây Beta/Stable flavor/package riêng.
- Xây OTA checker/download/hash verification shared cho hai channel.
- GitHub Actions build + verify + GitHub prerelease.
- Upload Public Beta 0.3.0-beta.1 lên Drive Beta.
- Fix backend login verifier migration 7/7 account, reset lock state.

## 20. TODO ƯU TIÊN — PHIÊN TIẾP THEO

### P0 — cần làm trước khi gọi Beta đạt mô hình mục tiêu

1. Test lại login trên PDA sau hotfix verifier; xác nhận account thật đăng nhập PASS.
2. Hoàn thiện/verify writer projection transaction về Google Sheet (`RA - VÀO TRONG CA`, Công nhật và state cần thiết) với ACK rõ ràng.
3. Hoàn thiện near-realtime multi-device sync: foreground immediate exchange/delta, server_seq polling hợp lý, DRAINING đúng lifecycle; đo thực tế trên >=2 PDA.
4. Test concurrency thực: hai PDA tranh PDA/User Pick/Pack, đúng một winner; change thất bại giữ resource cũ.
5. Thiết lập fixed signing key ngoài repo public và GitHub Actions secret để OTA in-place bền vững.
6. Tích hợp/verify scanner Newland MT90 thực tế; fallback manual/generic scanner cho thiết bị khác.

### P1

7. Hoàn thiện crash/manual/daily log upload đúng thư mục Drive và chỉ xóa local sau Drive ACK.
8. Verify đổi mật khẩu end-to-end và policy session revoke.
9. Verify ADMIN/SUPERADMIN account-management permissions và audit.
10. Test app foreground/background/screen-off trong lúc request đang chạy để xác nhận DRAINING không làm mất transaction.
11. Test OTA Beta -> Beta bằng fixed signing key; sau đó chuẩn hóa Stable release workflow.
12. Quyết định kiến trúc authority trước Stable: Supabase free-tier hay quay về/hoàn thiện Apps Script + Google Sheets theo mục tiêu ban đầu.

## 21. Rủi ro / technical debt

- Google Sheets/Apps Script không phải realtime database; nếu quay lại mô hình đó phải đo quota/concurrency.
- Supabase Beta hiện là một thay đổi so với kiến trúc ban đầu và cần quyết định chính thức trước Stable.
- Sheet đang share theo link theo yêu cầu công việc; verifier tốt hơn plaintext nhưng hidden Sheet không phải security boundary.
- Sheet projection chưa hoàn thiện nghĩa là dữ liệu transaction Beta hiện không nên được mô tả là đã realtime hai chiều với Google Sheet.
- Debug signing hiện tại làm OTA lâu dài chưa đáng tin cậy cho tới khi fixed key được khóa.
- Hardware scanner Newland cần test thật, không chỉ test nhập MNV.
- Offline durable queue/Room và adaptive realtime phải được kiểm chứng trong source hiện tại trước khi tuyên bố hoàn chỉnh.

## 22. Quy trình bàn giao phiên — CHỐT

Mỗi lần chủ dự án nói `chuyển phiên chat`:
1. Đọc/đối chiếu trạng thái thực tế GitHub/Drive/backend nếu tool khả dụng.
2. Cập nhật file cumulative `docs/HANDOVER_CURRENT.md`.
3. Tạo immutable snapshot `docs/handovers/HANDOVER_SXX_YYYY-MM-DD.md` kế thừa toàn bộ lịch sử còn hiệu lực.
4. Upload snapshot tương ứng vào Drive `BÀN GIAO PHIÊN CHAT`.
5. Ghi rõ `DONE / TODO / blockers / open decisions / superseded`.
6. Không đưa secret/dữ liệu nhạy cảm vào public repo hoặc handover.

## 23. Điểm bắt đầu cho S02

Phiên S02 phải bắt đầu bằng:
- đọc file này;
- kiểm tra login thật sau migration verifier;
- kiểm tra projection queue/Sheet writer;
- kiểm tra signing-key capability/secret setup;
- không quay lại Mẫu 3 hoặc UI VÀO/RA tách riêng;
- không tuyên bố Google Sheet realtime hai chiều cho tới khi writer + multi-device delta đã test PASS.
