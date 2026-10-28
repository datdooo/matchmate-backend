# MatchMate Backend

MatchMate hỗ trợ người chơi cầu lông tìm kèo phù hợp và chủ kèo tuyển thêm người. Pha 1 là backend REST JSON, demo qua Swagger, dùng một ứng dụng và một SQLite DB. Tìm sân/kèo theo `district_code`; nhóm đã bỏ GPS.

Phạm vi gồm **11 API nghiệp vụ, 5 bảng và 19 mức trình**. Đã nối đủ **11 API và `/health`**, có test tích hợp qua SQLite thật. Docker toàn luồng và tải Kaggle chưa được nghiệm thu.

## Bài toán và nghiệp vụ

Người chơi là tài khoản đã đăng ký; host là người chơi tạo một kèo và quản lý yêu cầu của kèo đó, không phải vai trò quản trị riêng.

- Người chơi đăng ký hồ sơ, đăng nhập, tra cứu sân/kèo theo quận, trình độ, giới tính, lịch và phí.
- Host tạo kèo đơn/đôi với một sân, lịch tương lai cố định dài 60–240 phút và tự có một lượt `ACCEPTED`. Sức chứa là 2/4 người, tính cả host. Người chơi xin tham gia tạo `PENDING`, chưa giữ chỗ; host duyệt hoặc từ chối trước giờ bắt đầu.
- Khi duyệt phải kiểm lại điều kiện, chỗ và lịch `ACCEPTED`. Hai lịch nối tiếp được phép. Mức phí và giới tính lúc xin được giữ nguyên; đăng ký lại tạo lượt mới. Người chơi rút lượt của mình; host phải hủy cả kèo.
- Matching gợi ý đủ 2/4 người cùng sân, giờ chính xác và loại kèo; kiểm policy giới tính, ngân sách và chênh trình tối đa 2 bậc. Chưa đủ nhóm thì trả `suggestion=null`; gợi ý không tự giữ chỗ hoặc tạo participation.

Ngoài phạm vi Pha 1: frontend hoàn chỉnh, chat/thông báo đẩy, đặt sân thực tế, thanh toán/hoàn tiền, xác minh trình độ, Elo/AI và danh sách chờ. Mức phí công bố không phải bằng chứng thanh toán.

## Framework và tổ chức code

Python 3.11+, FastAPI/Pydantic cho HTTP và schema, SQLAlchemy 2 cho ORM, SQLite cho dữ liệu; PyJWT HS256 và Argon2 cho đăng nhập. CI và Docker dùng Python 3.11.

Request đi qua API → Service → Protocol → Repository → SQLite. Service/domain/contracts thuần Python; repository trả dữ liệu thuần, không đưa ORM ra response. Protocol/port mô tả giao diện Service cần; dependency ghép các adapter tại biên ứng dụng.

| Thư mục | Vai trò |
|---|---|
| `app/features/auth` | Đăng ký, đăng nhập, JWT middleware |
| `app/features/discovery` | Tìm sân/kèo, matching |
| `app/features/sessions` | `session_*` quản lý kèo; `participation_*` xin/duyệt/rút |
| `app/domain`, `app/db` | Entity, enum, port, luật giờ; model, UTC, UoW và adapter ghi |
| `app/api`, `app/main.py` | Envelope lỗi, ghép router và dependency |
| `tests`, `scripts` | Test/fixture/Locust; seed và runner tải |

Năm bảng là `users`, `venues`, `sessions`, `participations`, `matching_requests`. DB có FK, CHECK và unique lượt hoạt động; không lưu counter sức chứa riêng. UTC được chuẩn hóa khi vào hệ thống, DB lưu TEXT cố định và API trả thời gian có `Z`.

Mỗi thao tác ghi dùng `BEGIN IMMEDIATE` trước khi kiểm dữ liệu, đọc Clock sau khi lấy khóa, dùng chung connection, commit một lần và rollback khi lỗi. APPROVE đóng matching chồng giờ trong cùng transaction. SQLite chờ khóa tối đa 5000 ms mặc định; hết thời gian trả `503 DATABASE_BUSY`, `Retry-After: 1`.

## Chạy local và kiểm thử

Từ thư mục repo:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m scripts.init_env
python -m scripts.seed
python -m uvicorn app.main:app --reload --no-access-log
```

`init_env` tạo `.env` với JWT secret ngẫu nhiên, giữ file nếu đã có; không commit file này. Seed tạo schema và 10 sân demo, không tạo tài khoản/kèo thật. App không tự seed hoặc reset DB khi khởi động.

Runtime đọc `DATABASE_URL` từ environment, mặc định `sqlite:///./app.db`; `SQLITE_BUSY_TIMEOUT_MS` mặc định 5000. Khi đổi DB, seed và app phải nhận cùng environment. Git đồng bộ code/seed, không đồng bộ dữ liệu DB giữa các máy.

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Test dùng SQLite file tạm riêng, có JWT/API thật, rollback, snapshot, idempotency và sáu ca concurrency. CI chạy lint/format/test. Test workload cần thêm `requirements-load.txt`; [bàn giao participation](docs/PARTICIPATIONS.md) ghi cách dùng fixture và nối transaction hủy kèo.

## API và file đặc tả

**[docs/openapi.json](docs/openapi.json)** được xuất từ app, mô tả các API đã tích hợp. Mở file bằng [Swagger Editor](https://editor.swagger.io/) để preview. Khi chạy local, dùng [Swagger UI](http://127.0.0.1:8000/docs), [ReDoc](http://127.0.0.1:8000/redoc) hoặc [OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

| FR | Method | Route | Quyền |
|---|---|---|---|
| FR-01 | POST | `/auth/register` | Public |
| FR-02 | POST | `/auth/login` | Public |
| FR-03 | GET | `/venues` | Public |
| FR-04 | GET | `/sessions` | Public; `host_me=true` cần JWT |
| FR-05 | POST | `/sessions` | JWT |
| FR-06 | GET | `/sessions/{session_id}` | JWT |
| FR-07 | DELETE | `/sessions/{session_id}` | Host |
| FR-08 | POST | `/participations` | JWT |
| FR-09 | POST | `/participations/{participation_id}/decision` | Host |
| FR-10 | DELETE | `/participations/{participation_id}` | Chủ lượt, không rút riêng lượt host |
| FR-11 | POST | `/matching/requests` | JWT |
| Kỹ thuật | GET | `/health` | Public, chỉ liveness |

Tạo/xem/hủy kèo trả `SessionDetail`, mở rộng schema `SessionSummary` dùng chung. Ba API participation trả `ParticipationDetail` đầy đủ. Datetime nhận ISO 8601 có timezone; từ chối Unix timestamp và số nguyên vượt miền INTEGER của SQLite bằng 422.

Khi thêm hoặc sửa route/schema, xuất lại JSON từ thư mục repo để tránh lệch với app:

```bash
python -c 'import json; from pathlib import Path; from app.main import app; Path("docs/openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")'
```

## Deploy, giới hạn và bàn giao Phase 2

Dockerfile dùng `python:3.11-slim`, chạy non-root, Uvicorn một worker trên `0.0.0.0:8000`. Compose publish port 8000, healthcheck `/health` và volume `matchmate_data` tại `/app/data`. DB trong container dự kiến dùng `sqlite:////app/data/matchmate.db`; giữ volume để giữ dữ liệu.

Compose đã nối JWT/environment và URL DB vào volume; image đã có `scripts`. Sau khi tạo `.env`, các lệnh dự kiến là:

```bash
docker compose build
docker compose run --rm api python -m scripts.seed
docker compose up -d
```

**Docker chưa được nghiệm thu trong lượt rà này:** môi trường kiểm tra không có Docker CLI. Nhóm cần kiểm build, seed lặp, restart giữ dữ liệu và luồng nghiệp vụ trên máy có Docker trước khi bàn giao.

SQLite chỉ có một writer nên tải ghi đồng thời có thể phải chờ hoặc gặp 503. Cần giữ đúng transaction, kiểm lại capacity/lịch khi ghi và đọc invariant sau test. [Trạng thái tải](docs/LOAD_TEST_RESULTS.md) ghi bằng chứng chạy và giới hạn môi trường.

Runner Kaggle có hai profile read/lifecycle riêng ở 10/50/100 users, một worker, DB mới mỗi lượt và HTML/CSV/metadata. **Chưa có số đo Kaggle**; lượt local 10 users dừng trước đo vì monitor Locust không đọc được process (`psutil.NoSuchProcess`). Nhóm cần chạy Kaggle Pha 1 trước khi chốt baseline; Phase 2 dựa trên số đo thật để đánh giá giới hạn. Bản hiện tại không dùng cache, queue hoặc nhiều worker.

## Phân công và trình bày

| Thành viên | Phần phụ trách |
|---|---|
| Chiến | Auth, tạo/xem/hủy kèo; config, wiring, Docker, CI, README |
| Hải | Tìm sân/kèo, matching; query, seed/dataset, read scenario |
| Đạt | FR-08/09/10 xin/duyệt/rút; DB/constraint/UTC, UoW, adapter participation/đóng matching, concurrency và tổng hợp tải Kaggle |

Mỗi người làm trên feature branch, đồng bộ `main` và tích hợp qua PR nhỏ. [Commit](https://github.com/datdooo/matchmate-backend/commits/main/) và [PR](https://github.com/datdooo/matchmate-backend/pulls?q=is%3Apr) lưu thay đổi thực tế để đối chiếu phân công; thay phần dùng chung cần kiểm regression.

Trình bày khoảng 6 phút ngay trên README/Swagger: 1 phút bài toán và tác nhân; 2 phút luồng tạo → xin → duyệt → xem → rút; 1 phút tổ chức code/framework; 1 phút transaction và các vấn đề dễ thấy; 1 phút deploy, việc còn thiếu và bàn giao. Không cần slide.

Nguồn nghiệp vụ: [đặc tả MatchMate](https://docs.google.com/document/d/1uKPAGgImttE029ZZ9ZAqeioh0bX514sAla_Jq38PPj4/edit?usp=drivesdk); quyết định mới tìm theo quận thay các đoạn GPS trong bản cũ.
