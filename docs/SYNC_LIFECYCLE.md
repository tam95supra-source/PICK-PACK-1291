# Sync Lifecycle Contract

Status: CHỐT nguyên tắc, thông số timeout có thể tune sau pilot.

## State machine

`SUSPENDED -> ACTIVE -> DRAINING -> SUSPENDED`

### ACTIVE
- App foreground và thiết bị interactive.
- Vừa vào ACTIVE phải `sync/exchange` ngay.
- Mutation do user tạo phải gửi ngay, không chờ polling.
- Foreground polling/delta sync chạy adaptive.

### DRAINING
Trigger khi app chuyển background hoặc màn hình không còn interactive.

- Dừng tạo polling cycle mới ngay.
- Không cancel request/mutation đang in-flight chỉ vì lifecycle đổi.
- Chờ request hiện tại kết thúc thành công hoặc kết thúc bằng timeout/network failure đã xác định.
- Sau khi không còn in-flight request thì chuyển `SUSPENDED`.
- Không bắt đầu sync mới chỉ để drain queue khi đã background.

### SUSPENDED
- Không polling.
- Không background periodic sync.
- Không giữ wake lock/foreground service thường trực.
- Pending queue nằm durable trong Room và chờ foreground/network opportunity kế tiếp.

## Crash/OS kill safety

Android không thể bảo đảm process luôn sống đủ lâu sau khi app bị background/force-stop/OS kill. Vì vậy correctness không được phụ thuộc vào `DRAINING` hoàn tất.

Bắt buộc:
- Pending mutation được ghi local transaction trước network send.
- Mỗi mutation có immutable `event_id`.
- ACK server mới cho phép đánh dấu committed/xóa pending.
- Timeout/kill/restart phải replay cùng `event_id`.
- Server idempotency trả kết quả cũ nếu event đã commit trước đó.

## Network policy

- Connect/read/call timeout phải hữu hạn để `DRAINING` không treo vô hạn.
- Retry foreground dùng exponential backoff + jitter.
- Offline không retry nóng; chờ connectivity callback.
- Sync response ưu tiên delta theo `last_server_seq` thay vì full snapshot.

## Foreground cadence ban đầu để pilot

- Foreground entry: ngay lập tức.
- Sau mutation/nhận delta: burst khoảng 1 giây trong cửa sổ ngắn.
- Active bình thường: khoảng 2 giây.
- Idle: khoảng 4 giây hoặc hơn.

Các giá trị trên là config server-side/tunable, không phải hard-coded business invariant.
