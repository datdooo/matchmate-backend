# Tuần 3: Cài đặt, chạy và kiểm thử

## Chạy bằng Docker

Cần Docker, Docker Compose và Python 3 (chỉ để tạo file cấu hình). Chạy tại thư mục gốc của repo:

```bash
python3 -m scripts.init_env
docker compose build
docker compose run --rm api python -m scripts.seed
docker compose up -d
```

`init_env` chỉ dùng thư viện chuẩn của Python. Nó tạo `.env` với JWT secret ngẫu nhiên và không ghi đè file có sẵn. Ứng dụng và dependency chạy trong container.

Mở [Swagger UI](http://127.0.0.1:8000/docs) để thử API. Compose chạy một worker và lưu DB trong volume `matchmate_data`.

| Việc | Lệnh |
|---|---|
| Xem log | `docker compose logs -f api` |
| Chạy lại | `docker compose up -d` |
| Build lại sau khi sửa code hoặc dependency | `docker compose up --build -d` |
| Dừng, giữ dữ liệu | `docker compose down` |
| Dừng và xóa dữ liệu | `docker compose down -v` |

Container không tự nạp lại code, nên sửa code xong phải build lại. Seed tạo bảng và 10 sân mẫu, không reset DB, và không cập nhật cấu trúc bảng đã có. Nếu đổi schema, phải xử lý dữ liệu cũ trước.

## Chạy bằng Python

Cần Python 3.11 trở lên:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m scripts.init_env
python -m scripts.seed
python -m uvicorn app.main:app --reload --no-access-log
```

Trên PowerShell, kích hoạt môi trường bằng `.venv\Scripts\Activate.ps1`.

Mặc định app dùng `sqlite:///./app.db`. Muốn đổi, đặt `DATABASE_URL` và dùng cùng giá trị khi seed và khi chạy app. App không tự seed hay reset DB lúc khởi động.

| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./app.db` | Đường dẫn DB |
| `JWT_SECRET_KEY` | không có | Bắt buộc, ít nhất 32 byte. `init_env` tạo giúp |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | Thời hạn token |
| `SQLITE_BUSY_TIMEOUT_MS` | 5000 | Thời gian chờ khóa ghi |

## Demo

```bash
python -m scripts.demo --step
```

Script tự mở server với DB tạm và secret ngẫu nhiên, rồi đi qua 9 bước: đăng ký, đăng nhập hai tài khoản, tạo kèo, xin tham gia, duyệt, rút lượt và hủy kèo. Bỏ `--step` để chạy một mạch. Nhấn Enter để sang bước tiếp theo. Mỗi bước gọi HTTP thật và kiểm dữ liệu trả về. Hai bước nhập lịch sai (422) và xin vào kèo đã đầy (409) là tình huống cố ý để xem phản hồi lỗi. Cuối cùng script tắt server và xóa DB tạm.

## Kiểm thử

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

CI chạy đúng ba lệnh này trên Python 3.11 (`.github/workflows/`).

Thư mục `tests/` theo cùng cách chia với `app/`:

| Thư mục | Nội dung |
|---|---|
| `tests/auth/` | Đăng ký, đăng nhập, JWT |
| `tests/db/` | Model, ràng buộc, session, UnitOfWork, ghi đóng matching |
| `tests/domain/` | Luật thời gian |
| `tests/discovery/` | Tìm sân, tìm kèo, matching |
| `tests/participations/` | Xin, duyệt, rút lượt, kể cả hai yêu cầu chạy đồng thời |
| `tests/load/` | Kịch bản Locust và test kiểm kịch bản |
| `tests/` (gốc) | Kiểm luật kiến trúc, xử lý lỗi, tích hợp qua `app.main`, seed |

Muốn chạy cả test workload, cài thêm `requirements-load.txt`. Cách đo tải và kết quả ở [báo cáo tải](bao-cao-tai.md).
