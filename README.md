# MatchMate Backend

Backend tìm kèo và ghép người chơi cầu lông cho học phần Kiến trúc phần mềm. Pha 1 dùng FastAPI, SQLAlchemy và SQLite; phạm vi là 11 API nghiệp vụ, 5 bảng và 19 mức trình. Đã bỏ GPS, tìm sân/kèo theo `district_code`.

Hiện đã tích hợp auth/JWT, tạo/xem kèo và ba API participation. Discovery có repository/service/schema, còn cần nối route; API hủy kèo chưa được tích hợp. Chưa có số đo tải Kaggle hoặc nghiệm thu Docker toàn luồng.

Tạo/xem kèo trả `SessionDetail`. Ba API participation trả `ParticipationDetail`.

## Chạy local

Python 3.11 trở lên. Docker/CI dùng Python 3.11.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m scripts.init_env
python -m scripts.seed
python -m uvicorn app.main:app --reload --no-access-log
```

`init_env` tạo JWT secret ngẫu nhiên trong `.env`, giữ nguyên file nếu đã có. Seed được chạy chủ động để tạo schema và 10 sân demo; app không tự seed hoặc reset DB lúc khởi động.

Mở `http://127.0.0.1:8000/docs` để thao tác bằng Swagger. `/health` chỉ kiểm liveness và không query DB. Runtime đọc `DATABASE_URL` từ environment, mặc định `sqlite:///./app.db`; `SQLITE_BUSY_TIMEOUT_MS` mặc định 5000. Khi đổi URL, seed và app phải dùng cùng environment. Git chỉ đồng bộ code/seed, không đồng bộ dữ liệu SQLite giữa các máy.

## API đã tích hợp

| Method | Route | Quyền |
|---|---|---|
| POST | `/auth/register` | Public |
| POST | `/auth/login` | Public |
| POST | `/sessions` | JWT |
| GET | `/sessions/{session_id}` | JWT |
| POST | `/participations` | JWT |
| POST | `/participations/{participation_id}/decision` | Host |
| DELETE | `/participations/{participation_id}` | Owner, không rút riêng lượt host |
| GET | `/health` | Public |

Các endpoint không có prefix `/api/v1`. Tạo participation trả `ParticipationDetail` gồm player và session đầy đủ, không trả ORM. `PENDING` chưa giữ chỗ; capacity đơn/đôi là 2/4 và tính cả host. Snapshot phí/giới tính được giữ sau duyệt/rút/hủy.

## Code và kiểm thử

API → Service → Protocol → Repository → SQLite. Service/domain/contracts thuần Python; repository map ORM sang dữ liệu thuần. UoW dùng `BEGIN IMMEDIATE` trước kiểm dữ liệu, đọc Clock sau khi lấy quyền ghi, commit một lần và rollback khi lỗi. Không có counter/capacity lưu riêng, cache hoặc queue.

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Test có SQLite file tạm, JWT/API thật, unique/rollback, snapshot, idempotency và sáu ca concurrency nghiệp vụ. Một warning deprecation từ Starlette vẫn còn. Hướng dẫn bàn giao participation nằm ở [docs/PARTICIPATIONS.md](docs/PARTICIPATIONS.md).

## Tải và Docker

[docs/LOAD_TEST_RESULTS.md](docs/LOAD_TEST_RESULTS.md) ghi trạng thái tải và lệnh chạy Kaggle CPU. Runner dùng DB tạm mới cho mỗi lượt và dừng trước phát tải khi thiếu API. Không dùng kết quả `/health` để thay tải nghiệp vụ.

Dockerfile/Compose đã có; sau khi tích hợp đủ endpoint cần kiểm lại build, seed, volume DB và toàn luồng. Không tự coi Docker đã được nghiệm thu vì CI lint/test xanh.

Chiến còn cần nối environment/JWT và URL DB vào volume `/app/data`, đồng thời đưa thư mục `scripts` vào image để chạy seed trong container. Đây là phần vận hành chưa được nghiệm thu.

## Phân công và Git

- Chiến: auth, tạo/xem/hủy kèo, JWT/config, composition root, Docker/CI/README.
- Hải: discovery/matching, seed/dataset, query và read scenario.
- Đạt: DB/UoW/UTC, `participation_*`, matching writer, concurrency và tích hợp tải.

Mỗi người làm trên feature branch, đồng bộ main và tích hợp qua PR nhỏ. Không gọi chéo Service/router. Trong sessions, `session_*` thuộc Chiến, `participation_*` thuộc Đạt; thay phần dùng chung cần nêu module bị ảnh hưởng và kiểm regression.

Nguồn nghiệp vụ: [đặc tả MatchMate](https://docs.google.com/document/d/1uKPAGgImttE029ZZ9ZAqeioh0bX514sAla_Jq38PPj4/edit?usp=drivesdk). Các đoạn GPS trong bản cũ đã được thay bằng quyết định tìm theo quận.
