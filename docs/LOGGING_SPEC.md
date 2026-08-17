# Android Logging & Diagnostic Bundle

Status: CHỐT nguyên tắc.

## Destination classes

### AUTO_CRASH
Drive destination: `NHẬT KÝ HỆ THỐNG/BÁO LỖI TỰ ĐỘNG`

Tạo khi app gặp uncaught exception/crash nghiêm trọng. Ghi local trước, upload ngay nếu còn khả năng; nếu chưa ACK thì tự gửi ở lần foreground sau.

### MANUAL_REPORT
Drive destination: `NHẬT KÝ HỆ THỐNG/BÁO LỖI THỦ CÔNG`

User bấm `Gửi báo lỗi / nhật ký chẩn đoán`. Bundle phải đủ dữ liệu để điều tra lỗi liên màn hình, sync, scanner, network, local DB, hiệu suất và OTA mà không cần yêu cầu user tái hiện ngay lập tức.

### ANDROID_DAILY
Drive destination: `NHẬT KÝ HỆ THỐNG/NHẬT KÝ ANDROID`

Tối đa một bundle logic/ngày/installation. Không đánh thức máy để gửi. Khi app foreground, gửi bundle ngày chưa ACK; sau ACK mới xóa local.

## File format

Khuyến nghị: `.jsonl.gz` hoặc bundle `.zip` chứa JSON/JSONL text UTF-8. Không dùng binary format khó điều tra khi cần mở thủ công.

Tên file chứa tối thiểu:
- log type
- business/local date + timestamp
- anonymous/stable installation ID hoặc device identifier phù hợp
- app channel Beta/Stable
- versionName/versionCode

Không đưa password/token/secret vào filename.

## Diagnostic envelope

Mỗi bundle có metadata:
- schema_version
- log_id UUID
- log_type
- created_at / timezone
- app package/channel/version/build
- device manufacturer/model/product
- Android version/API level
- installation_id/device_id theo contract
- current account ID/role nếu đã login (không password/token)
- current screen/feature/flow
- current business date/shift nếu liên quan
- network type/online state
- sync lifecycle state ACTIVE/DRAINING/SUSPENDED
- last_server_seq
- pending event counts + oldest pending age
- local DB schema version
- scanner provider/state
- OTA state/current target version

## Event breadcrumbs

Giữ rolling ring buffer local có giới hạn, gồm event kỹ thuật có timestamp/level/category/correlation ID, ví dụ:
- APP_START/FOREGROUND/BACKGROUND/SCREEN_INTERACTIVE
- LOGIN_SUCCESS/LOGIN_FAILURE_REASON_CODE
- SYNC_START/SYNC_HEAD/SYNC_DELTA/SYNC_ACK/SYNC_CONFLICT/SYNC_TIMEOUT
- EVENT_ENQUEUED/EVENT_ACK/EVENT_REPLAY
- HTTP_START/HTTP_END với endpoint logical name, status, duration, byte counts
- DB_TRANSACTION_START/END/ERROR
- SCANNER_OPEN/CLOSE/SCAN_RESULT_METADATA/ERROR
- SESSION_ENTER/EXIT outcome code
- RESOURCE_ASSIGN/CHANGE/RETURN outcome code
- LABOR operation outcome code
- OTA_CHECK/DOWNLOAD/VERIFY/INSTALL_REQUEST
- lifecycle/memory pressure warnings

Không log raw password, Authorization header, cookie, verifier, secret hoặc full payload chứa dữ liệu nhạy cảm.

## Performance metrics

Thu thập nhẹ, phục vụ tối ưu:
- app cold/warm start duration
- screen render/load duration cho flow chính
- sync request latency p50/p95-style local aggregates
- Sheet/API logical request count
- retry/conflict/error counters
- Room query/transaction duration cho query quan trọng
- process memory snapshot
- GC/memory pressure signal nếu có
- battery level/charging state tại thời điểm report (không polling liên tục)
- network transitions
- scanner latency/error count

## Crash package

Ngoài envelope + breadcrumbs:
- exception class/message
- full stack trace của app
- cause chain/suppressed exceptions khi có
- thread name
- last known screen/operation/correlation ID
- recent sync/network/DB breadcrumbs
- app/device/runtime metadata
- pending queue summary

Không cố thực hiện thao tác nặng sau crash. Ưu tiên fsync/atomic local persistence, upload chỉ best-effort.

## Manual report package

Manual report phải rộng hơn crash:
- envelope hiện tại
- breadcrumbs chi tiết gần đây
- aggregated metrics của phiên/ngày hiện tại
- sanitized recent request/result metadata
- pending queue diagnostics
- conflict history gần đây
- Room table row counts/schema health checks an toàn
- scanner diagnostics
- OTA diagnostics
- crash/restart markers gần đây nếu có
- optional user note do user nhập

Không export toàn database vận hành hoặc toàn bảng nhân sự vào report mặc định. Nếu sau này cần deep support mode, phải có quyền ADMIN/SUPERADMIN và policy riêng.

## Daily package

- session/app uptime foreground
- số lần mở app
- tổng sync/mutation/ACK/conflict/retry/timeout/error
- latency aggregates
- crash count
- scanner counts/error
- OTA events
- memory/performance summaries
- redacted breadcrumbs cần thiết

## Redaction

Redactor chạy trước cả local persistence và upload đối với trường nhạy cảm. Tối thiểu match key/name:
`password`, `pass`, `authorization`, `bearer`, `token`, `refresh_token`, `cookie`, `secret`, `verifier`, `private_key`, `keystore_password`, `key_password`.

Nếu không xác định an toàn, bỏ field thay vì ghi nguyên giá trị.

## Retention local

- File pending chưa ACK: không xóa chỉ vì quá ngày.
- File đã ACK: xóa local ngay/sớm nhất có thể.
- Rolling breadcrumbs phải có size cap để không đầy storage.
- Nếu storage pressure, ưu tiên giữ crash/manual pending chưa ACK và loại bỏ debug breadcrumbs cũ trước.

## ACK contract

Chỉ coi upload thành công khi server trả canonical ACK có `log_id` và storage reference/status thành công. Sau ACK mới xóa file local.
