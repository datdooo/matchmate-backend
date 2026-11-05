# MatchMate Backend

Backend REST API cho người chơi cầu lông. Người chơi tìm sân và kèo theo quận, xin vào kèo và chờ host duyệt. Ai chưa chọn được kèo gửi nhu cầu để nhận gợi ý nhóm 2 hoặc 4 người.

Đây là Pha 1 của bài tập lớn môn Kiến trúc phần mềm (UET): backend cơ bản, không có frontend. Công nghệ: Python 3.11+, FastAPI, Pydantic, SQLAlchemy 2, SQLite, Docker.

## Đặc tả nghiệp vụ

- Người dùng đăng ký, đăng nhập (JWT). Host là người tạo kèo, không phải vai trò riêng.
- Kèo đơn có 2 người, kèo đôi có 4 người, tính cả host. Lịch ở tương lai, dài 60-240 phút. Tạo kèo ghi luôn lượt của host với trạng thái `ACCEPTED`.
- Người chơi xin tham gia, tạo lượt `PENDING`. Lượt này chưa giữ chỗ. Host duyệt (`ACCEPTED`) hoặc từ chối (`REJECTED`). Khi duyệt, hệ thống kiểm lại quyền, điều kiện tuyển, số chỗ và lịch.
- Người chơi rút lượt trước giờ bắt đầu. Host không rút lượt mà hủy cả kèo, khi đó mọi lượt `PENDING` và `ACCEPTED` bị hủy theo.
- Matching chỉ gợi ý nhóm cùng sân, cùng giờ, cùng loại kèo, hợp giới tính và ngân sách, chênh trình tối đa 2 bậc. Gợi ý không tạo kèo hay giữ chỗ. Không đủ người thì trả `suggestion=null`.

Luồng chi tiết từng chức năng, kèm lỗi có thể gặp, ở [docs/](docs/README.md).

## API

Đặc tả đầy đủ: [docs/openapi.json](docs/openapi.json), hoặc `/docs` (Swagger) và `/redoc` khi chạy ứng dụng.

| Method và đường dẫn | Chức năng | Quyền |
|---|---|---|
| `POST /auth/register` | Đăng ký | Công khai |
| `POST /auth/login` | Đăng nhập, nhận JWT | Công khai |
| `GET /venues` | Tìm sân | Công khai |
| `GET /sessions` | Tìm kèo (`host_me=true` cần JWT) | Công khai |
| `POST /sessions` | Tạo kèo | JWT |
| `GET /sessions/{session_id}` | Xem chi tiết kèo | JWT |
| `DELETE /sessions/{session_id}` | Hủy kèo | Host |
| `POST /participations` | Xin tham gia | JWT |
| `POST /participations/{participation_id}/decision` | Duyệt hoặc từ chối | Host |
| `DELETE /participations/{participation_id}` | Rút lượt của mình | Chủ lượt |
| `POST /matching/requests` | Gợi ý ghép nhóm | JWT |
| `GET /health` | Kiểm tra tiến trình | Công khai |

Lỗi trả về dạng `{"error": {"code", "message", "details", "request_id"}}`.

## Kiến trúc

Ba tầng: API, nghiệp vụ, truy cập dữ liệu. Một request đi từ router đến service rồi repository.

```text
app/
├── main.py        ghép router, middleware, xử lý lỗi
├── api/           xử lý lỗi HTTP dùng chung
├── domain/        enum, entity, luật thời gian, Protocol (Python thuần)
├── db/            model SQLAlchemy, session, UnitOfWork
└── features/
    ├── auth/        đăng ký, đăng nhập, JWT middleware
    ├── discovery/   tìm sân, tìm kèo, matching
    └── sessions/    kèo và lượt tham gia
```

- Service, domain và contracts không import FastAPI, Pydantic, SQLAlchemy hay `app.db`. `tests/test_architecture.py` kiểm điều này.
- Repository dùng SQLAlchemy ORM và trả dữ liệu thuần cho service.
- JWT được kiểm một lần ở middleware, endpoint không tự giải mã lại.
- Thao tác ghi dùng `BEGIN IMMEDIATE` và commit một lần. Nếu chờ khóa quá 5 giây, API trả `503 DATABASE_BUSY`.
- Thời gian nhận vào có múi giờ, lưu UTC.

Chi tiết (sơ đồ dữ liệu, luật phụ thuộc, transaction) ở [docs/tuan-1-nen-tang/thiet-ke.md](docs/tuan-1-nen-tang/thiet-ke.md).

## Chạy

Cần Docker, Docker Compose và Python 3 (để tạo file cấu hình). Tại thư mục gốc:

```bash
python3 -m scripts.init_env
docker compose build
docker compose run --rm api python -m scripts.seed
docker compose up -d
```

Mở [Swagger UI](http://localhost:8000/docs). Seed tạo bảng và 10 sân mẫu. Dừng bằng `docker compose down`, dữ liệu nằm trong volume. Cách chạy không dùng Docker ở [hướng dẫn cài đặt](docs/tuan-3-kiem-thu-va-ban-giao/cai-dat-va-kiem-thu.md).

Demo toàn bộ luồng bằng HTTP thật (tự mở server và DB tạm):

```bash
python -m scripts.demo --step
```

Kiểm thử:

```bash
python -m ruff check .
python -m pytest -q
```

## Kiểm thử tải

Lần đo ngày 29/10/2026 trên Kaggle CPU, một worker. Tải đọc với 10, 50, 100 người và tải ghi với 10 người đo đủ 60 giây, không lỗi request. Tải ghi với 50 và 100 người dừng trước khi đo do lỗi 503 và đăng nhập quá thời gian chờ, chưa có kết quả. Số liệu và giới hạn ở [báo cáo tải](docs/tuan-3-kiem-thu-va-ban-giao/bao-cao-tai.md).
