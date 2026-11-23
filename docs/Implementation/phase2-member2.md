# Giai đoạn 2 · Bàn giao của Member 2

Phạm vi là nền PostgreSQL, migration, nhập dữ liệu SQLite và kiểm thử trên cơ sở
dữ liệu thật. Phần SQLite tiếp tục dùng cho kiểm thử hồi quy.

## Những gì đã triển khai

- [Cấu hình kết nối](../../app/db/session.py) nhận `DATABASE_URL` cho SQLite
  hoặc PostgreSQL qua Psycopg 3. PostgreSQL dùng UTC, tối đa 5 kết nối mỗi tiến
  trình, không mở thêm kết nối vượt pool, chờ kết nối 5 giây. Mặc định chờ khóa
  5 giây và giới hạn câu lệnh 15 giây. Có thể đặt
  `POSTGRES_LOCK_TIMEOUT_MS` và `POSTGRES_STATEMENT_TIMEOUT_MS` để kiểm thử.
- [Alembic](../../alembic.ini) quản lý lược đồ PostgreSQL. Revision
  [`0001_postgres_schema`](../../migrations/versions/0001_postgres_schema.py)
  tạo năm bảng, khóa ngoại, các ràng buộc và hai chỉ mục unique có điều kiện cho
  lượt tham gia và Matching đang hoạt động. PostgreSQL dùng `TIMESTAMPTZ` và
  Boolean gốc. ID và số tiền dùng `BIGINT` để giữ phạm vi dữ liệu hiện có.
- [Công cụ nhập](../../scripts/import_sqlite_to_postgres.py) đọc bản sao SQLite
  ở chế độ chỉ đọc, kiểm tra toàn vẹn và khóa ngoại, rồi nhập vào các bảng
  PostgreSQL trống theo thứ tự phụ thuộc. Công cụ đối chiếu lại các trường theo
  từng lô, giữ ID và lịch sử, rồi đặt số bắt đầu tiếp theo của từng cột ID.
  Nhập và đặt lại ID nằm trong cùng transaction. Lỗi giữa chừng rollback cả
  đợt nhập. Kết quả CLI chỉ in số bản ghi từng bảng.
- [Unit of Work](../../app/db/unit_of_work.py) mở PostgreSQL ở `READ COMMITTED`
  khi ghi và `REPEATABLE READ, READ ONLY` khi đọc. `lock_session(id)` và
  `lock_user(id)` dùng `SELECT ... FOR UPDATE` trên cùng kết nối với các thao
  tác ghi. Chúng trả `False` nếu bản ghi không tồn tại và chỉ gọi được trong
  transaction ghi. SQLite vẫn dùng `BEGIN IMMEDIATE`.
- Lỗi DB giữ [hợp đồng bàn giao Phase 1](phase1.md#2-hành-vi-và-hợp-đồng-đã-chốt).
  Hết thời gian chờ pool/khóa, deadlock và serialization failure trả
  `503 DATABASE_BUSY`. Statement timeout nhận diện từ mã và chẩn đoán cụ thể
  của server trả `503 DATABASE_TIMEOUT`. Cancellation không rõ nguồn dùng
  phản hồi 500 chung. Mất kết nối trong commit có thể báo `outcome: unknown`.

## Chạy thử trên máy phát triển

Dùng PowerShell 7 từ thư mục gốc repo. Dùng lại cùng mật khẩu khi khởi động lại
volume đã tạo. Lệnh dưới đây dùng project, database và cổng riêng cho Giai đoạn 2.

```powershell
python -m pip install -r requirements-dev.txt
$env:PYTHONUTF8 = '1'
$env:MEMBER2_POSTGRES_PASSWORD = Read-Host 'Mật khẩu PostgreSQL local' -MaskInput
$env:MEMBER2_POSTGRES_DB = 'matchmate_phase2'
$env:MEMBER2_POSTGRES_PORT = '55433'

docker compose -p matchmate-member2-phase2 -f compose.phase1-member2.yaml up -d --wait postgres
$pgPassword = [uri]::EscapeDataString($env:MEMBER2_POSTGRES_PASSWORD)
$env:DATABASE_URL = "postgresql+psycopg://matchmate:${pgPassword}@127.0.0.1:55433/matchmate_phase2"

python -m alembic upgrade head
python -m alembic current
$sourceDir = 'artifacts/member2-phase2/source-' + [guid]::NewGuid().ToString('N')
python -m scripts.prepare_member2_phase1 --output $sourceDir
python -m scripts.import_sqlite_to_postgres --source "$sourceDir/migration-source.db"
```

Lần nhập mẫu có kết quả mong đợi `venues=1`, `users=3`, `sessions=1`,
`participations=4`, `matching_requests=3`. Nếu cần chạy lại lần nhập, tạo một
database đích sạch, trỏ `DATABASE_URL` sang đó và chạy lại migration.

Để chạy API với dữ liệu vừa nhập, khởi tạo JWT secret bằng
`python -m scripts.init_env` nếu chưa có, rồi chạy
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` trong cùng shell.

## Kiểm thử và bàn giao bước tích hợp

Fixture PostgreSQL cần tài khoản có quyền `CREATEDB` trên máy phát triển. Mỗi
ca tạo một DB tên ngẫu nhiên, chạy Alembic và dọn đúng DB đó khi hoàn tất.

```powershell
$env:MATCHMATE_TEST_POSTGRES_URL = $env:DATABASE_URL
Remove-Item Env:DATABASE_URL
python -m pytest tests/integration/test_member2_postgres.py -q
python -m pytest -q -rs
python -m ruff check .
python -m ruff format --check .
```

[Bộ test PostgreSQL](../../tests/integration/test_member2_postgres.py) kiểm
schema khớp metadata, lịch sử và thứ tự cấp ID sau nhập, rollback khi nhập lỗi,
hai chỉ mục unique, timeout khóa trên hai kết nối riêng, snapshot đọc và
statement timeout. Ca API đi qua tạo kèo, tạo yêu cầu Matching, xin tham gia,
duyệt và xác nhận yêu cầu Matching trùng lịch đã được đóng.

Ngày 23/11/2026, đã chạy Alembic và nhập bộ SQLite Phase 1 vào database sạch
trên PostgreSQL Docker **17.11**. Số bản ghi khớp cả năm bảng. Khi bật fixture
PostgreSQL, toàn bộ suite đạt **417 ca**, gồm 6 ca PostgreSQL mới. Ruff lint,
Ruff format và `git diff --check` đều đạt.

Giai đoạn 3 dùng các thao tác khóa này để tích hợp vào Sessions và Matching.
Member 1 và Member 3 phụ trách thời điểm gọi khóa và đọc lại dữ liệu sau khóa
trong use case. CI PostgreSQL, Compose demo có ingress, readiness và đo DB
thuộc mốc tích hợp. Diễn tập backup/restore thuộc mốc bàn giao sau đó.
