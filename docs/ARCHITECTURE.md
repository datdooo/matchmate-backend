# Kiến trúc, nghiệp vụ và API

## Công nghệ và mã nguồn

Ứng dụng dùng Python 3.11+, FastAPI/Pydantic, SQLAlchemy 2 và SQLite. Đăng nhập dùng JWT HS256; mật khẩu được băm bằng Argon2.

Một request đi từ router vào service để kiểm nghiệp vụ, sau đó repository đọc hoặc ghi DB. Các `Protocol` định nghĩa giao diện Python giữa service và phần truy cập dữ liệu. Dependency ghép các thành phần này khi tạo ứng dụng. Với thao tác ghi, các bước kiểm tra và cập nhật liên quan dùng chung một transaction; lỗi thì rollback.

DB có 5 bảng: `users`, `venues`, `sessions`, `participations`, `matching_requests`. Số chỗ được tính từ các lượt `ACCEPTED`.

## Ví dụ luồng duyệt người chơi

Router nhận `POST /participations/{participation_id}/decision`; JWT sẽ xác định người đang thao tác. Schema kiểm quyết định `APPROVE` hoặc `REJECT`, rồi chuyển cho service.

Service mở transaction ghi, kiểm người thao tác là host, lượt đang `PENDING` và kèo chưa bắt đầu. Với `APPROVE`, service kiểm tra lại hồ sơ, số chỗ và lịch đã xác nhận. Repository sẽ đổi trạng thái lượt và writer đóng matching chồng giờ trên cùng connection. Nếu hoàn tất thì commit còn lỗi thì rollback.

## Quy tắc dữ liệu và tích hợp Phase 2

- Kèo đơn/đôi có 2/4 người, tính cả host; chỉ lượt `ACCEPTED` mới tính vào số chỗ.
- Khi có người xin tham gia tạo `PENDING`. Khi duyệt phải kiểm lại sức chứa.
- Lịch ở tương lai, dài 60–240 phút và không chồng lịch `ACCEPTED`; hai lịch nối tiếp được phép.
- Phí và giới tính được lưu tại thời điểm xin, giữ nguyên sau duyệt/rút/hủy. Hủy kèo thì phải hủy cả các lượt đang hoạt động trong cùng transaction.
- Dữ liệu đầu vào phải có múi giờ được DB lưu UTC dưới dạng TEXT cố định và API phải trả thời gian có `Z`.
- SQLite chỉ có một writer. Khi hết thời gian chờ khóa phải trả `503 DATABASE_BUSY`.
- Các cờ quyền trong response dùng để phục vụ giao diện. Khi nhận thao tác ghi Service phải kiểm tra lại quyền.

DB có khóa ngoại, CHECK và unique lượt tham gia đang hoạt động. Khi thay DB hoặc thêm frontend, phải giữ các ràng buộc, quyền host và transaction của những thao tác liên quan.

Pha 1 chưa triển khai frontend hoàn chỉnh, chat/thông báo, đặt sân thực tế, thanh toán/hoàn tiền, xác minh trình độ, Elo/AI hoặc danh sách chờ.

## API

Đặc tả: [openapi.json](openapi.json). Khi chạy ứng dụng, mở `/docs` để thử API hoặc `/redoc` để đọc.

| FR | API | Chức năng và quyền |
|---|---|---|
| 01 | `POST /auth/register` | Đăng ký, công khai |
| 02 | `POST /auth/login` | Đăng nhập, công khai |
| 03 | `GET /venues` | Tìm sân, công khai |
| 04 | `GET /sessions` | Tìm kèo; lọc `host_me=true` cần JWT |
| 05 | `POST /sessions` | Tạo kèo, cần JWT |
| 06 | `GET /sessions/{session_id}` | Xem chi tiết, cần JWT |
| 07 | `DELETE /sessions/{session_id}` | Hủy kèo, chỉ host |
| 08 | `POST /participations` | Xin tham gia, cần JWT |
| 09 | `POST /participations/{participation_id}/decision` | Duyệt/từ chối, chỉ host |
| 10 | `DELETE /participations/{participation_id}` | Rút lượt của mình; host phải hủy kèo |
| 11 | `POST /matching/requests` | Gợi ý ghép nhóm, cần JWT |

`GET /health` kiểm tra tiến trình đang chạy, không kiểm tra DB.
