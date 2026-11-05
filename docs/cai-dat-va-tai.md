# Cài đặt, kiểm thử và kiểm thử tải

## Docker

Cần Docker, Docker Compose và Python 3 (chỉ để tạo file cấu hình). Tại thư mục gốc:

```bash
python3 -m scripts.init_env
docker compose build
docker compose run --rm api python -m scripts.seed
docker compose up -d
```

`init_env` tạo `.env` với JWT secret ngẫu nhiên và không ghi đè file có sẵn. Compose chạy một worker, lưu DB trong volume `matchmate_data`. Swagger ở http://localhost:8000/docs.

| Việc | Lệnh |
|---|---|
| Xem log | `docker compose logs -f api` |
| Build lại sau khi sửa code | `docker compose up --build -d` |
| Dừng, giữ dữ liệu | `docker compose down` |
| Dừng và xóa dữ liệu | `docker compose down -v` |

Seed tạo bảng và 10 sân mẫu, không reset DB và không cập nhật cấu trúc bảng đã có.

## Python

Cần Python 3.11 trở lên:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m scripts.init_env
python -m scripts.seed
python -m uvicorn app.main:app --reload --no-access-log
```

| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./app.db` | Đường dẫn DB. Seed và app phải dùng cùng giá trị, đặt qua biến môi trường |
| `JWT_SECRET_KEY` | không có | Bắt buộc, ít nhất 32 byte |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | Thời hạn token |
| `SQLITE_BUSY_TIMEOUT_MS` | 5000 | Thời gian chờ khóa ghi |

## Demo

```bash
python -m scripts.demo --step
```

Script tự mở server với DB tạm rồi đi qua 9 bước: đăng ký, đăng nhập hai tài khoản, tạo kèo, xin tham gia, duyệt, rút lượt, hủy kèo. Nhấn Enter để sang bước tiếp theo, bỏ `--step` để chạy một mạch. Hai bước nhập lịch sai (422) và xin vào kèo đã đầy (409) là cố ý.

## Kiểm thử

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

CI chạy ba lệnh này trên Python 3.11, đã cài cả `requirements-load.txt` nên test tải cũng chạy. Một job riêng build Docker image, seed và chạy thử API bằng Compose. Thư mục `tests/` chia theo module: `auth/`, `discovery/`, `sessions/` (gồm test hai yêu cầu chạy đồng thời), `foundation/` (DB, UnitOfWork, thời gian, xử lý lỗi), `integration/`, `load/`, và `test_architecture.py`. Muốn chạy test tải ở máy mình, cài thêm `requirements-load.txt`.

## Kiểm thử tải trên Kaggle CPU

Kết quả đo (Locust, 10/50/100 người, notebook đã chạy và dữ liệu thô) nằm ở [commit `5b9be9f`](https://github.com/datdooo/matchmate-backend/tree/5b9be9fb939de41965eb1f6b290be2b60ea4d28c/docs/load/kaggle-2026-10-29). Tải ghi (`lifecycle`) với 50 và 100 người chưa đo được, lý do ghi trong báo cáo ở commit đó.

Chạy lại (cần Internet):

```bash
python -m pip install -r requirements-load.txt
bash scripts/run_kaggle_load_test.sh --profile full
```

Kết quả từng lượt và `summary.md` được ghi vào `artifacts/` (Git bỏ qua).
