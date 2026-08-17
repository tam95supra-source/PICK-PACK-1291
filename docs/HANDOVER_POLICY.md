# Quy trình bàn giao phiên chat

## Mục tiêu

Không để mất context dự án khi phiên chat lag, lỗi, bị xóa hoặc chuyển sang phiên mới.

## Trigger

Khi chủ dự án báo **chuyển phiên chat** (hoặc diễn đạt tương đương), phải thực hiện bàn giao trước khi kết thúc phiên nếu công cụ còn khả dụng.

## Hai lớp hồ sơ

1. `docs/HANDOVER_CURRENT.md`: hồ sơ **cộng dồn**, luôn phản ánh toàn bộ trạng thái dự án từ phiên đầu đến hiện tại.
2. `docs/handovers/HANDOVER_SXX_YYYY-MM-DD.md`: snapshot bất biến của từng lần bàn giao.

Bản bàn giao mới không chỉ ghi thay đổi của phiên vừa xong; nó phải kế thừa các quyết định còn hiệu lực từ mọi phiên trước.

## Nội dung bắt buộc

- Mục tiêu và phạm vi dự án.
- Kiến trúc đã chốt.
- Nghiệp vụ/invariant đã chốt.
- Schema/data contract đã chốt.
- Quyền USER/ADMIN/SUPERADMIN.
- Realtime/offline/sync behavior.
- OTA Beta/Stable.
- Security và secret handling.
- Logging/crash/manual/daily log.
- UI/branding/footer/icon.
- GitHub/Drive cấu trúc liên quan, không ghi secret hoặc dữ liệu nhạy cảm.
- Việc đã hoàn thành.
- Việc đang làm.
- Việc chưa làm/backlog.
- Mâu thuẫn/open decisions cần chủ dự án quyết định.
- Known risks/technical debt.
- Cách tiếp tục ở phiên sau.

## Quy tắc public-safe

Repository là public. File bàn giao trên GitHub tuyệt đối không chứa password, verifier thực tế, token, key, dữ liệu nhân sự thật, log thật, Drive URL/ID không cần công khai hoặc secret khác.

Nếu cần lưu chi tiết nội bộ hơn, dùng bản bàn giao trong thư mục Drive `BÀN GIAO PHIÊN CHAT`; nhưng vẫn không ghi plaintext password/secret.

## Quy tắc kế thừa

- Quyết định mới thay thế quyết định cũ phải ghi rõ `SUPERSEDED` và lý do.
- Không tự xóa requirement cũ chỉ vì phiên hiện tại không nhắc lại.
- Phân biệt `CHỐT`, `ĐỀ XUẤT`, `ĐANG THỬ NGHIỆM`, `CHƯA QUYẾT ĐỊNH`.
- Trước khi bàn giao phải đối chiếu repo, Drive/schema và trạng thái thực tế nếu có quyền truy cập.
