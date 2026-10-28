# Bàn giao phần participation

FR-08/09/10 đi qua router → Service → port → repository trên SQLite. Service thuần Python; UoW mở `BEGIN IMMEDIATE`, sau đó Service mới đọc Clock, kiểm luật và commit một lần. Repository/writer chỉ query, flush hoặc update; lỗi làm rollback cả thao tác.

- Xin tham gia tạo `PENDING`, chưa giữ chỗ. Host đã có `ACCEPTED` khi tạo kèo; capacity đơn/đôi là 2/4, gồm host.
- APPROVE kiểm lại hồ sơ, chỗ và lịch ACCEPTED; đóng matching overlap bằng writer cùng transaction. REJECT bỏ qua capacity/eligibility.
- Rút lượt kiểm tồn tại và owner; host phải hủy kèo. CANCELLED của owner trả bản cũ trước kiểm giờ; không đổi timestamp lần hai.
- `gender_at_join` và `quoted_fee_vnd` giữ nguyên sau duyệt/rút/hủy. Đăng ký lại tạo record mới.
- Overlap dùng hai dấu `<`, hai lịch nối tiếp được phép. DB/API dùng UTC; API trả mã trình qua mapping chung. Tìm sân theo quận, không có GPS.

Các file `participation_*` ở `app/features/sessions/` chứa contract, mapper, repository, Service, schema, dependency và router. DTO host/venue/session và schema response dùng lại phần đã có; không thêm bản sao enum/rank mapping. `app/db/matching_request_writer.py` được dùng cho cả tạo kèo và APPROVE.

Khi nối API hủy kèo của Chiến, cập nhật session và gọi `cancel_active_for_session` trong cùng UoW, gồm cả participation của host. Không tạo Session riêng hoặc commit giữa hai bước. `list_for_session` nhận `actor_user_id` và `now` để tính cờ quyền; nếu không truyền ngữ cảnh thì các cờ là False. Cờ chỉ phục vụ hiển thị, Service vẫn kiểm quyền lúc ghi.

`tests/conftest.py` cấp SQLite file riêng. Fixture client/JWT cho participation ở `tests/participations/conftest.py`; auth và session dependencies cũng trỏ vào cùng DB tạm. Các test concurrency dùng connection riêng, barrier/event có timeout và đọc lại DB sau khi hai actor kết thúc. Ca APPROVE đối đầu hủy kèo kiểm transaction với adapter hủy; cần bổ sung E2E qua DELETE session khi route đó được tích hợp.

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Tải Kaggle chưa có số đo; trạng thái và lệnh chạy nằm trong `docs/LOAD_TEST_RESULTS.md`. Không tự reset DB hoặc seed khi app khởi động. Runtime đọc `DATABASE_URL` và `SQLITE_BUSY_TIMEOUT_MS` từ environment, mặc định vẫn là `sqlite:///./app.db` và 5000 ms.
