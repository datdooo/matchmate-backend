# Bàn giao phần participation

FR-08/09/10 đi qua router → Service → port → repository trên SQLite. Service thuần Python; UoW mở `BEGIN IMMEDIATE`, sau đó Service mới đọc Clock, kiểm luật và commit một lần. Repository/writer chỉ query, flush hoặc update; lỗi làm rollback cả thao tác.

- Xin tham gia tạo `PENDING`, chưa giữ chỗ. Host đã có `ACCEPTED` khi tạo kèo; capacity đơn/đôi là 2/4, gồm host.
- APPROVE kiểm lại hồ sơ, chỗ và lịch ACCEPTED; đóng matching overlap bằng writer cùng transaction. REJECT bỏ qua capacity/eligibility.
- Rút lượt kiểm tồn tại và owner; host phải hủy kèo. CANCELLED của owner trả bản cũ trước kiểm giờ; không đổi timestamp lần hai.
- `gender_at_join` và `quoted_fee_vnd` giữ nguyên sau duyệt/rút/hủy. Đăng ký lại tạo record mới.
- Overlap dùng hai dấu `<`, hai lịch nối tiếp được phép. DB/API dùng UTC; API trả mã trình qua mapping chung. Tìm sân theo quận, không có GPS.

Các file `participation_*` ở `app/features/sessions/` chứa contract, mapper, repository, Service, schema, dependency và router. DTO host/venue/session và schema response dùng lại phần đã có; không thêm bản sao enum/rank mapping. Adapter participation dùng chung hàm thuần `compute_display_status` với discovery, còn query/mapping vẫn thuộc participation; không gọi chéo Service. `app/db/matching_request_writer.py` được dùng cho cả tạo kèo và APPROVE.

Khi nối API hủy kèo của Chiến, cập nhật session và gọi `cancel_active_for_session` trong cùng UoW, gồm cả participation của host. Không tạo Session riêng hoặc commit giữa hai bước. `list_for_session` nhận `actor_user_id` và `now` để tính cờ quyền; nếu không truyền ngữ cảnh thì các cờ là False. Cờ chỉ phục vụ hiển thị, Service vẫn kiểm quyền lúc ghi.

`tests/conftest.py` cấp SQLite file riêng, `client` và `auth_headers` dùng chung cho cả nhóm. Auth, discovery, session và participation dependencies đều trỏ vào DB tạm đó. `auth_headers(user_id)` tạo JWT cho user đã có trong fixture và vẫn đi qua middleware thật. `tests/participations/conftest.py` chỉ bổ sung Clock cố định và factory Service. Test khác có thể mở rộng client chung để override dependency của feature; teardown sẽ trả wiring về như cũ.

Các test concurrency dùng connection riêng, barrier/event có timeout và đọc lại DB sau khi hai actor kết thúc. Ca APPROVE đối đầu hủy kèo kiểm transaction với adapter hủy; cần bổ sung E2E qua DELETE session khi route đó được tích hợp.

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Tải Kaggle chưa có số đo; trạng thái và lệnh chạy nằm trong `docs/LOAD_TEST_RESULTS.md`. Không tự reset DB hoặc seed khi app khởi động. Runtime đọc `DATABASE_URL` và `SQLITE_BUSY_TIMEOUT_MS` từ environment, mặc định vẫn là `sqlite:///./app.db` và 5000 ms.
