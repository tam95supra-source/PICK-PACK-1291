# HANDOVER CURRENT — Pick Pack 1291

Status: BASELINE / cumulative
Last updated: 2026-08-17 (Asia/Bangkok)

## 1. Mục tiêu dự án — CHỐT

- Xây Android APK phục vụ ưu tiên PDA Newland NLS-MT90, Android 10 trở lên.
- Vẫn hỗ trợ điện thoại/PDA Android khác khi phù hợp.
- Google Sheets là database vận hành giai đoạn đầu.
- Google Apps Script dự kiến làm API authoritative giữa APK và Google Sheets.
- GitHub repository public để tận dụng CI/CD miễn phí; toàn bộ source phải public-safe.
- Beta và Stable tách applicationId/channel và cài song song được cho mọi role.
- APK tự kiểm tra OTA, tự thông báo/yêu cầu cập nhật khi có bản mới.

## 2. Drive/database hiện tại — CHỐT THEO HIỆN TRẠNG

Drive có các khối chính:
- `DỮ LIỆU VẬN HÀNH`
- `PHÁT HÀNH APK` với `BẢN THỬ NGHIỆM` và `BẢN ỔN ĐỊNH`
- `NHẬT KÝ HỆ THỐNG` với `NHẬT KÝ ANDROID`, `BÁO LỖI TỰ ĐỘNG`, `NHẬT KÝ WEB`
- Đã bổ sung `BÁO LỖI THỦ CÔNG`
- Đã bổ sung `BÀN GIAO PHIÊN CHAT`

Workbook `DỮ LIỆU THEO NGÀY` hiện có các tab nghiệp vụ/master gồm: Danh mục, nhân sự, PDA, User Pick, bàn Pack, User Pack, Ra/Vào trong ca, Công nhật, tài khoản Admin.

## 3. Logic kế thừa từ dự án cũ — CHỐT Ở MỨC NGUYÊN TẮC

- `MNV` là business key của nhân viên; không dùng họ tên làm key.
- Session theo `MNV + business_date`: CHƯA VÀO -> ACTIVE -> ENDED.
- Mutation phải có immutable `event_id` để idempotent/retry không duplicate.
- PDA, User Pick, User Pack và bàn Pack là tài nguyên exclusive.
- Khi nhiều app tranh cùng tài nguyên: đúng một winner, các app còn lại nhận conflict rõ ràng.
- Đổi tài nguyên phải atomic; đổi PDA thất bại phải giữ PDA cũ.
- Bàn Pack + User Pack mapped được xử lý theo bundle khi nghiệp vụ áp dụng.
- Accepted history không bị silent overwrite; correction phải audited.
- Offline/reconnect dùng local pending queue và replay cùng event ID.
- Không coi resource globally free dựa trên action offline chưa được canonical ACK.
- Conflict UI giữ nguyên form và chỉ yêu cầu xử lý trường xung đột.

## 4. Role — CHỐT

Role đúng ba cấp:
- SUPERADMIN
- ADMIN
- USER

USER: thao tác nghiệp vụ thường và tài nguyên trong phạm vi được cấp.
ADMIN: bao gồm USER + Công nhật/master/user-management/correction trong phạm vi quy định.
SUPERADMIN: toàn quyền hợp lệ, quản lý ADMIN và correction đặc quyền.

## 5. Password/account security — CHỐT TẠM THỜI

- Drive vẫn giữ chế độ share hiện tại để phục vụ công việc; không đổi sang Restricted theo quyết định chủ dự án.
- Plaintext password trong tab tài khoản đã được loại bỏ.
- Cột password đã được thay bằng salted PBKDF2-SHA256 verifier; tab tài khoản đã được hidden.
- Đây là biện pháp tạm thời, không được coi hidden Sheet là security boundary.
- Khi có backend/service hoàn chỉnh, auth sẽ chuyển về server authority; secret không lưu trong Sheet/repo/APK.
- Mọi user phải có chức năng tự đổi mật khẩu trong app.
- Không log password/token/verifier/secret.

## 6. Realtime/sync — CHỐT

Ưu tiên truyền thông tin giữa các điều phối nhanh nhất có thể khi app đang được sử dụng.

- Khi app foreground và màn hình/thiết bị interactive: sync hoạt động tích cực.
- Vừa vào app: sync ngay, ưu tiên exchange cả upload pending và download delta trong một round-trip.
- User mutation: gửi ngay, không chờ vòng polling.
- Các app khác nhận thay đổi qua `server_seq`/delta sync.
- Có thể dùng adaptive foreground polling: burst nhanh sau activity, chậm dần khi idle; thông số phải server-configurable.
- Không đọc toàn bộ Google Sheet mỗi vòng; dùng head/sequence/delta và cache khi có thể.
- Khi app background hoặc screen off: không bắt đầu vòng sync mới.
- Nếu đang có transaction/sync in-flight tại thời điểm app background/screen off: chuyển sang `DRAINING`, cho request đang chạy hoàn thành rồi mới suspend sync.
- Nếu Android/process bị kill đột ngột trước khi hoàn thành, local transaction + immutable event ID đảm bảo lần mở sau replay an toàn; không được phụ thuộc vào việc process luôn sống tới hết HTTP request.
- Không dùng continuous background polling, permanent socket, GPS hoặc wake lock dài hạn cho mục tiêu realtime này.

## 7. Pin/hiệu suất — CHỐT

- Local Room DB phục vụ UI/cache.
- Coroutines/Flow cho async state.
- Không giữ foreground service liên tục chỉ để sync.
- Scanner chỉ active ở màn hình/flow cần scan.
- Không animation nặng, không query full Sheet lặp lại.
- Offline không retry nóng liên tục; chờ network callback/backoff.

## 8. Logging — CHỐT

Ba luồng chính:

1. Crash tự động -> Drive `BÁO LỖI TỰ ĐỘNG`.
2. User bấm gửi thủ công -> Drive `BÁO LỖI THỦ CÔNG`.
3. Nhật ký Android định kỳ một lần/ngày khi app có cơ hội foreground -> Drive `NHẬT KÝ ANDROID`.

Log phục vụ chẩn đoán phải đủ sâu: timestamp, build/channel/version, model/device ID, Android, account/role dạng phù hợp, screen/flow, network, sync cursor/state, pending queue summary, recent app events, exception/stacktrace, performance/memory metrics và context kỹ thuật cần thiết. Phải redact password, auth header/token, cookie, verifier, signing secret và credential.

Crash flow:
- Ghi crash package xuống local trước.
- Có thể thử upload ngay nếu process còn sống.
- Nếu chưa nhận ACK thì giữ pending.
- Lần app tiếp theo tự upload.

Daily log:
- Không đánh thức thiết bị chỉ để gửi log.
- Nếu ngày đó app không mở, log pending sẽ gửi ở lần foreground tiếp theo.

Xóa local log chỉ sau server ACK xác nhận lưu thành công.

## 9. UI/branding — CHỐT

- UI chuyên nghiệp, nhẹ, ít cầu kỳ nhưng đầy đủ.
- Ưu tiên màn hình PDA ~5 inch, scan-first, nút lớn, font rõ, ít keyboard, thao tác một tay.
- Phong cách màu lấy cảm hứng từ artwork: navy/white/light gray, blue cho info, gold làm accent hạn chế, red error, green success.
- Không dùng hiệu ứng nặng/glassmorphism/animation dài.
- Footer căn giữa phía dưới ở màn hình phù hợp:
  `Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY`
- Artwork do chủ dự án cung cấp là master artwork/icon source của app; khi đóng gói Android chỉ resize/pad kỹ thuật để tạo adaptive/launcher icons, không redesign nội dung.

## 10. Settings — CHỐT

Tối thiểu có:
- Đổi mật khẩu.
- Trạng thái sync/kết nối, lần sync gần nhất, pending data/server seq dạng chẩn đoán phù hợp.
- Gửi báo lỗi/log thủ công.
- Thông tin phiên bản + channel + OTA.
- Thông tin thiết bị/app.

## 11. OTA — CHỐT HƯỚNG

- Beta và Stable tách package/applicationId để cài song song.
- Mỗi channel có manifest/version riêng.
- App tự check update khi khởi động/foreground theo policy.
- Verify hash APK trước khi cài.
- Signing key/keystore/password tuyệt đối không nằm trong public repo.

## 12. GitHub public security — CHỐT

Repository: `tam95supra-source/pick-pack-1291`, public.

Đã tạo:
- `README.md`
- `.gitignore` chặn Android build outputs, keystore/cert/private key, env/secret, credentials, logs/db và APK/AAB.
- `SECURITY.md` quy định public-by-design và secret rotation nếu lỡ commit.
- `docs/HANDOVER_POLICY.md`
- file này: `docs/HANDOVER_CURRENT.md`

Các giá trị sau không được hard-code/public:
- password/verifier thật
- Google owner/service credentials
- Apps Script server secret
- signing keystore/private key/password
- operational logs thật
- export database/nhân sự thật
- Spreadsheet/Drive sensitive configuration không cần public

Android không được chứa credential có thể truy cập thẳng Sheet/Drive. Spreadsheet ID và Drive runtime IDs nên ở backend config, không phải client source.

## 13. Quy trình bàn giao phiên — CHỐT

Khi chủ dự án báo `chuyển phiên chat`:
- đối chiếu trạng thái thực tế nếu tool còn dùng được;
- cập nhật file cumulative này;
- tạo snapshot `docs/handovers/HANDOVER_SXX_YYYY-MM-DD.md`;
- bản mới phải kế thừa mọi quyết định còn hiệu lực từ phiên 1 trở đi;
- không chỉ ghi riêng thay đổi của phiên vừa kết thúc;
- ghi rõ done / doing / todo / blockers / open decisions / superseded decisions;
- không ghi secret/dữ liệu nhạy cảm vào public repo;
- đồng thời duy trì bản bàn giao trên Drive khi workflow được hoàn thiện.

## 14. Đã làm

- Đọc Drive/database hiện tại và 4 tài liệu nghiệp vụ cũ được cung cấp.
- Chắt lọc business invariants phù hợp cho mô hình APK <-> Google Sheets.
- Kiểm tra quyền Drive và GitHub.
- Xác nhận repo mới public và có quyền admin/push.
- Loại bỏ plaintext passwords khỏi Sheet bằng verifier salted PBKDF2-SHA256 và hide tab tài khoản.
- Tạo folder Drive `BÁO LỖI THỦ CÔNG`.
- Tạo folder Drive `BÀN GIAO PHIÊN CHAT`.
- Bootstrap tài liệu bảo mật/bàn giao trên GitHub.

## 15. Đang làm / bước tiếp theo

- Khóa canonical data contract và `_SYS_*` schema tối thiểu.
- Khóa API contract cho auth, bootstrap, sync/exchange, session/resource/labor, logging và OTA.
- Thiết kế Android project skeleton và scanner abstraction cho Newland + generic fallback.
- Thiết kế Apps Script bootstrap/deploy flow với minimum manual steps.

## 16. Chưa làm

- Chưa tạo source Android.
- Chưa tạo Apps Script project/deployment.
- Chưa tạo `_SYS_*` Sheets.
- Chưa build APK Beta.
- Chưa triển khai GitHub Actions build/sign/release.
- Chưa upload OTA APK/manifest.
- Chưa test concurrency/resource conflicts/offline replay trên thiết bị thật.
- Chưa tạo bản snapshot bàn giao phiên vì chủ dự án chưa báo chuyển phiên.

## 17. Rủi ro/technical debt đã biết

- Google Sheets/Apps Script không phải realtime database; mục tiêu là near-realtime foreground, phải đo bằng pilot thực tế.
- Hidden Sheet không phải lớp bảo mật; verifier hiện tại chỉ là phương án tạm trước backend auth hoàn chỉnh.
- Nếu process Android bị OS/force-stop kill trong lúc `DRAINING`, không thể bảo đảm HTTP hoàn tất; integrity phải dựa trên durable local queue + idempotent server events.
- Public GitHub yêu cầu kiểm soát secret trước commit; một secret đã commit phải coi là compromised và rotate.
