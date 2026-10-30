# Xin, duyệt và rút lượt tham gia

Tài liệu này mô tả FR-08, FR-09 và FR-10 cùng phần dữ liệu dùng chung với tạo/hủy kèo. Xem [luồng và nhánh lỗi](WORKFLOWS.md) hoặc [đặc tả API](openapi.json) khi tích hợp giao diện.

## Các file liên quan

Trong `app/features/sessions/`, các file bắt đầu bằng `participation_` phụ trách lượt tham gia:

| File | Nhiệm vụ |
|---|---|
| [participation_router.py](../app/features/sessions/participation_router.py) | Nhận ba API xin, quyết định và rút lượt |
| [participation_schemas.py](../app/features/sessions/participation_schemas.py) | Kiểm dữ liệu HTTP và định dạng response |
| [participation_service.py](../app/features/sessions/participation_service.py) | Kiểm quyền, trạng thái, điều kiện tuyển, chỗ và lịch |
| [participation_contracts.py](../app/features/sessions/participation_contracts.py) | Giao diện repository và dữ liệu trao đổi với service |
| [participation_repository.py](../app/features/sessions/participation_repository.py) | Đọc/ghi SQLite qua session của UnitOfWork |
| [participation_mapper.py](../app/features/sessions/participation_mapper.py) | Chuyển dữ liệu DB sang dữ liệu trả về |
| [participation_dependencies.py](../app/features/sessions/participation_dependencies.py) | Ghép service, repository, clock và UnitOfWork |

[UnitOfWork](../app/db/unit_of_work.py) quản lý transaction. [MatchingRequestWriter](../app/db/matching_request_writer.py) đóng yêu cầu matching chồng giờ khi người chơi có lịch được xác nhận. Các file `session_*` cùng thư mục phụ trách tạo, xem và hủy kèo.

## Quy tắc cần giữ

- Host có lượt `ACCEPTED` ngay khi tạo kèo. Kèo đơn/đôi có sức chứa 2/4 người, gồm host. Xin tham gia tạo `PENDING`, chưa giữ chỗ.
- `APPROVE` kiểm lại hồ sơ hiện tại, số chỗ và lịch `ACCEPTED`, rồi đóng matching chồng giờ. `REJECT` không cần kiểm số chỗ hoặc điều kiện tuyển.
- Chỉ người sở hữu được rút lượt; host phải hủy cả kèo. Gọi rút lại lượt đã `CANCELLED` trả kết quả cũ và giữ timestamp. Lượt `REJECTED` không rút được.
- `gender_at_join` và `quoted_fee_vnd` giữ nguyên sau duyệt, rút hoặc hủy. Xin lại tạo bản ghi mới.
- Hai lịch trùng khi `start_a < end_b` và `start_b < end_a`; lịch nối tiếp được phép. Thời gian dùng UTC.

## Transaction và hủy kèo

Service mở `uow.write()` bằng `BEGIN IMMEDIATE`, lấy được khóa rồi mới đọc thời gian và kiểm nghiệp vụ. Repository chỉ truy vấn hoặc cập nhật trên connection đó; service commit một lần sau khi chuẩn bị dữ liệu trả về. Lỗi làm rollback cả thao tác.

API hủy kèo đã được tích hợp. [SessionService.cancel](../app/features/sessions/session_service.py) gọi [repository](../app/features/sessions/session_repository.py) để đổi trạng thái kèo và hủy mọi lượt `PENDING`/`ACCEPTED`, gồm lượt host, trong cùng UnitOfWork. Khi thay tầng dữ liệu, cần giữ hai bước này trong một transaction.

Các cờ `can_cancel`, `can_decide` giúp giao diện hiển thị nút. Service vẫn kiểm quyền và điều kiện khi nhận yêu cầu ghi, vì dữ liệu có thể đã đổi sau lúc xem chi tiết.

## Kiểm thử và giới hạn

[tests/conftest.py](../tests/conftest.py) cấp DB SQLite tạm và client chung. `auth_headers(user_id)` tạo JWT cho tài khoản fixture; request vẫn qua middleware. Fixture của participation bổ sung clock cố định và factory service.

[Các test đồng thời](../tests/participations/test_concurrency.py) dùng connection riêng, đồng bộ bằng barrier/event và đọc lại DB sau khi hai thao tác kết thúc. Có ca tranh chỗ cuối, duyệt một người vào hai lịch trùng, duyệt cùng lúc rút/hủy và chờ khóa qua giờ bắt đầu. Ca duyệt đối đầu hủy kèo hiện kiểm ở tầng transaction/adapter, chưa phải hai request HTTP chạy đồng thời.

Chạy kiểm tra từ thư mục repo:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Kết quả tải Kaggle đã có trong [LOAD_TEST_RESULTS.md](LOAD_TEST_RESULTS.md), kèm các lượt chưa hoàn tất ở tải ghi cao. Runtime đọc `DATABASE_URL` và `SQLITE_BUSY_TIMEOUT_MS`, mặc định là `sqlite:///./app.db` và 5000 ms. Ứng dụng không tự reset hoặc seed DB khi khởi động.
