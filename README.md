# MatchMate Backend

Backend REST API cho người chơi cầu lông. Người chơi tìm sân và kèo theo quận, xin vào kèo và chờ host duyệt. Ai chưa chọn được kèo gửi nhu cầu để nhận gợi ý nhóm 2 hoặc 4 người.

Pha 1 của bài tập lớn môn Kiến trúc phần mềm (UET): backend cơ bản, không có frontend. Python 3.11+, FastAPI, Pydantic, SQLAlchemy 2, SQLite, Docker.

## API

Đặc tả đầy đủ ở [docs/openapi.json](docs/openapi.json), hoặc `/docs` (Swagger) khi chạy ứng dụng. Quy tắc nghiệp vụ và lỗi từng endpoint ở [docs/dac-ta.md](docs/dac-ta.md).

| Endpoint | Chức năng | Quyền |
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

## Kiến trúc

Ba tầng: router (API), service (nghiệp vụ), repository (truy cập dữ liệu), chia thành ba module `auth`, `discovery`, `sessions` trong `app/features/`.

- Service, domain và contracts không import FastAPI, Pydantic hay SQLAlchemy (`tests/test_architecture.py` kiểm).
- Repository dùng SQLAlchemy ORM. JWT được kiểm một lần ở middleware.
- Thao tác ghi dùng `BEGIN IMMEDIATE` và commit một lần. Chờ khóa quá 5 giây thì trả `503 DATABASE_BUSY`.

Chi tiết ở [docs/kien-truc.md](docs/kien-truc.md).

## Chạy

Cần Docker, Docker Compose và Python 3 (để tạo file cấu hình):

```bash
python3 -m scripts.init_env
docker compose build
docker compose run --rm api python -m scripts.seed
docker compose up -d
```

Swagger ở http://localhost:8000/docs. Chạy không dùng Docker, demo và kiểm thử tải ở [docs/cai-dat-va-tai.md](docs/cai-dat-va-tai.md).

```bash
python -m scripts.demo --step   # demo toàn luồng bằng HTTP thật
python -m pytest -q             # kiểm thử
```
