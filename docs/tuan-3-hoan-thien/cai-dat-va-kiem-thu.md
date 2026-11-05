# Cài đặt và chạy

## Docker

Cần Docker, Docker Compose và Python 3 để tạo file cấu hình. Chạy tại thư mục gốc:

```bash
python3 -m scripts.init_env
docker compose build
docker compose run --rm api python -m scripts.seed
docker compose up -d
```

`init_env` dùng thư viện chuẩn Python, tạo `.env` với JWT secret ngẫu nhiên và không ghi đè file có sẵn. Python của ứng dụng và các dependency chạy trong container.

| Việc | Lệnh |
|---|---|
| Xem log | `docker compose logs -f api` |
| Chạy lại | `docker compose up -d` |
| Build lại sau khi sửa code hoặc dependency | `docker compose up --build -d` |
| Dừng, giữ dữ liệu | `docker compose down` |

Container không tự reload code. Seed tạo bảng và 10 sân mẫu, không reset DB. Seed không cập nhật cấu trúc bảng đã tồn tại; thay schema cần xử lý dữ liệu cũ trước. `docker compose down -v` xóa volume dữ liệu.

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

Trên PowerShell dùng `.venv\Scripts\Activate.ps1`.

Ứng dụng dùng `sqlite:///./app.db`. Khi đổi `DATABASE_URL`, seed và app phải nhận cùng giá trị từ environment. `SQLITE_BUSY_TIMEOUT_MS` mặc định là 5000 ms. App không tự seed hay reset DB lúc khởi động.

Mở [Swagger UI](http://127.0.0.1:8000/docs) để thử API. Compose lưu DB trong volume `matchmate_data`.

## Demo và kiểm thử

Sau khi cài `requirements-dev.txt`:

```bash
python -m scripts.demo --step
```

Script tự chạy server với DB tạm riêng và secret ngẫu nhiên. Mỗi bước gọi HTTP thật và kiểm tra dữ liệu trả về. Các phản hồi 422 khi tạo lịch sai và 409 khi kèo đầy là tình huống để thử. Script sẽ dừng server và dọn DB khi kết thúc.

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Muốn chạy đủ các test workload, cài `requirements-load.txt`. Cách đo và kết quả nằm trong [báo cáo tải](LOAD_TEST_RESULTS.md).
