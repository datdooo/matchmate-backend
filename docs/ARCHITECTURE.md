# Kiến trúc, nghiệp vụ và API

## Công nghệ và mã nguồn


Ứng dụng dùng Python 3.11+, FastAPI/Pydantic, SQLAlchemy 2 và SQLite. Đăng nhập dùng JWT HS256; mật khẩu được băm bằng Argon2.

Một request đi từ router vào service để kiểm nghiệp vụ, sau đó repository đọc hoặc ghi DB. Các `Protocol` định nghĩa giao diện Python giữa service và phần truy cập dữ liệu. Dependency ghép các thành phần này khi tạo ứng dụng. Với thao tác ghi, các bước kiểm tra và cập nhật liên quan dùng chung một transaction; lỗi thì rollback.

| Vị trí | Nội dung |
|---|---|
| `app/main.py`, `app/api` | Ghép router, middleware và xử lý lỗi chung |
| `app/features/auth` | Đăng ký, đăng nhập, băm mật khẩu và kiểm JWT |
| `app/features/discovery` | Tra cứu sân/kèo và gợi ý matching |
| `app/features/sessions` | Tạo, xem, hủy kèo; xin, duyệt và rút lượt tham gia |
| `app/domain` | Entity, enum, giao diện và luật thời gian dùng chung |
| `app/db` | Model, kết nối SQLite, UTC, UnitOfWork và adapter ghi |
| `tests`, `scripts` | Kiểm thử; tạo dữ liệu mẫu, demo và chạy kiểm thử tải |

DB có 5 bảng: `users`, `venues`, `sessions`, `participations`, `matching_requests`. Số chỗ được tính từ các lượt `ACCEPTED`. Thời gian đầu vào phải có múi giờ, được chuẩn hóa về UTC và trả qua API với hậu tố `Z`.

## Ví dụ luồng duyệt người chơi

Router nhận `POST /participations/{participation_id}/decision`; JWT xác định người đang thao tác. Schema kiểm quyết định `APPROVE` hoặc `REJECT`, rồi chuyển cho service.

Service mở transaction ghi, kiểm người thao tác là host, lượt đang `PENDING` và kèo chưa bắt đầu. Với `APPROVE`, service kiểm lại hồ sơ, số chỗ và lịch đã xác nhận. Repository đổi trạng thái lượt; writer đóng matching chồng giờ trên cùng connection. Hoàn tất thì commit, lỗi thì rollback.

`Protocol` là giao diện Python, không phải bước gọi mạng. Chi tiết các file nằm trong [tài liệu lượt tham gia](PARTICIPATIONS.md).

## Quy tắc dữ liệu và tích hợp Phase 2

- Kèo đơn/đôi có 2/4 người, gồm host; chỉ lượt `ACCEPTED` tính vào số chỗ.
- Xin tham gia tạo `PENDING`. Khi duyệt vẫn phải kiểm lại sức chứa vì dữ liệu có thể thay đổi sau lúc người chơi xem kèo.
- Lịch ở tương lai, dài 60–240 phút và không chồng lịch `ACCEPTED`. Hai lịch nối tiếp được phép.
- Phí và giới tính tại thời điểm xin được giữ nguyên. Hủy kèo hủy cả các lượt đang hoạt động trong cùng transaction.
- Dữ liệu đầu vào phải có múi giờ. DB lưu UTC dưới dạng TEXT cố định, API trả thời gian có `Z`.
- SQLite chỉ có một writer. Hết thời gian chờ khóa trả `503 DATABASE_BUSY`; ứng dụng không bỏ qua các bước kiểm dữ liệu.
- Các cờ quyền trong response phục vụ giao diện. Service vẫn kiểm lại quyền khi nhận thao tác ghi.

DB có khóa ngoại, CHECK và unique lượt tham gia đang hoạt động. Khi thay DB hoặc thêm frontend, cần giữ các ràng buộc, quyền host và transaction của những thao tác liên quan.

Pha 1 chưa triển khai frontend hoàn chỉnh, chat/thông báo đẩy, đặt sân thực tế, thanh toán/hoàn tiền, xác minh trình độ, Elo/AI hoặc danh sách chờ.

## API

Đặc tả lưu ở [openapi.json](openapi.json). Có thể mở file bằng [Swagger Editor](https://editor.swagger.io/); khi chạy ứng dụng, dùng `/docs` để thử API, `/redoc` để đọc và `/openapi.json` để lấy đặc tả.

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

Ngoài 11 API nghiệp vụ, `GET /health` kiểm tra tiến trình đang chạy, không kiểm tra toàn bộ DB.

JWT được gửi qua `Authorization: Bearer <token>`. Thiếu, sai hoặc hết hạn token trả 401 trên API bảo vệ. Mã lỗi và dữ liệu đầu vào/đầu ra nằm trong đặc tả; [luồng chi tiết bằng tiếng Việt](WORKFLOWS.md) giải thích các trường nhập, nhánh lỗi và kết quả.

## Kiểm thử và giới hạn

CI chạy Ruff và pytest. Các test dùng SQLite file tạm riêng, kiểm JWT/API, rollback, dữ liệu tại lúc xin, gọi rút/hủy lặp lại và sáu tình huống đồng thời. Ca duyệt đối đầu hủy kèo kiểm ở tầng transaction/adapter; chưa phải hai request HTTP chạy đồng thời.

[Báo cáo Kaggle](LOAD_TEST_RESULTS.md) giữ kết quả tải và dữ liệu gốc, gồm các lượt ghi 50/100 người chưa đo đầy đủ. Phép đo dùng Uvicorn và Locust trên cùng máy, gọi loopback; chỉ là số liệu tham khảo của cấu hình đó.
