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

CI chạy ba lệnh này trên Python 3.11. Thư mục `tests/` chia theo module: `auth/`, `discovery/`, `sessions/` (gồm test hai yêu cầu chạy đồng thời), `foundation/` (DB, UnitOfWork, thời gian, xử lý lỗi), `integration/`, `load/`, và `test_architecture.py`. Test tải cần cài thêm `requirements-load.txt`.

## Kiểm thử tải trên Kaggle CPU

Đo ngày 29/10/2026 trên commit `859df1345a6d5034d2202823232f219f34f87ab4`. Môi trường: Kaggle CPU 4 vCPU, RAM 30 GiB, Python 3.13.15, SQLite 3.45.1, một worker Uvicorn, Locust chạy cùng máy qua loopback. Số liệu không phản ánh độ trễ qua Internet.

| Kịch bản | Người dùng | Request | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Lỗi |
|---|---:|---:|---:|---:|---:|---:|---:|
| read | 10 | 393 | 6,59 | 11 | 14 | 34 | 0 |
| read | 50 | 1963 | 32,91 | 13 | 32 | 54 | 0 |
| read | 100 | 3864 | 65,25 | 24 | 100 | 180 | 0 |
| lifecycle | 10 | 1719 | 28,79 | 31 | 120 | 270 | 0 |

`read` chỉ gọi API đọc. Mỗi vòng `lifecycle` tạo kèo, xin tham gia, duyệt, xem chi tiết, rồi rút lượt hoặc hủy kèo.

Hai lượt `lifecycle` còn lại chưa đo được:

- **50 người:** đăng nhập đủ, nhưng giai đoạn warm-up có 27 lỗi 503 (22 ở tạo kèo, 4 ở xin tham gia, 1 ở duyệt). Runner dừng đúng quy tắc. Đây là giới hạn ghi đồng thời của SQLite với một worker.
- **100 người:** mới đăng nhập được 42 cặp thì một request `/auth/login` quá 20 giây và hết thời gian chờ. Runner dừng trước warm-up.

Sau cả sáu lượt, bốn chỉ số kiểm tra DB đều bằng 0: `over_capacity`, `accepted_overlap`, `active_in_cancelled`, `open_without_host`.

Báo cáo đầy đủ, notebook và dữ liệu thô nằm ở [commit `5b9be9f`](https://github.com/datdooo/matchmate-backend/tree/5b9be9fb939de41965eb1f6b290be2b60ea4d28c/docs/load/kaggle-2026-10-29).

Chạy lại (cần Internet):

```bash
python -m pip install -r requirements-load.txt
bash scripts/run_kaggle_load_test.sh --profile full
```

Kết quả từng lượt và `summary.md` được ghi vào `artifacts/` (Git bỏ qua).
