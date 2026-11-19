# Phase 1 · Thành viên 2 · Lưu trữ, triển khai và khôi phục

Ngày lập: **19/11/2026**. Phạm vi: giai đoạn 1 trong
[kế hoạch](../Architecture_Phase2/kehoachtrienkhai-VN.md).
Commit khảo sát: `9046444e0a420da3f205c99a39c9641512dcb57b`.

Đã đọc [bàn giao Member 1](phase1-member1.md),
[báo cáo Member 1](member-1-phase-1.vi.md),
[hợp đồng Member 3](phase1-member3.md) và code hiện tại.
Đây là phản hồi và cam kết triển khai **từ phía Member 2**. Không thay mặt Member 1/3
xác nhận đồng thuận, không coi adapter PostgreSQL/migration đã được triển khai.
Các thay đổi runtime thuộc giai đoạn 2–3; giai đoạn này chuẩn bị hợp đồng,
dữ liệu đầu vào và môi trường. Kết quả thực thi được ghi ở cuối tài liệu.

## 1. Khảo sát persistence hiện tại và việc cần chuyển

### `app/db/session.py`

- `create_db_engine()` luôn truyền `check_same_thread=False`, cài listener nhận
  `sqlite3.Connection` và chạy `PRAGMA foreign_keys`, `PRAGMA busy_timeout`.
  Vì vậy chưa dùng được với PostgreSQL chỉ bằng cách đổi URL.
- Tách cấu hình theo dialect. PostgreSQL dự kiến dùng driver psycopg 3,
  URL `postgresql+psycopg://...`, không chạy PRAGMA/check_same_thread.
- Session factory hiện `autoflush=False`, `expire_on_commit=False`.
  Giữ repository flush chủ động; không dựa vào ORM cache để đọc lại sau khóa.
- Chưa có giới hạn pool/statement/lock dành cho PostgreSQL.

### `app/db/types.py`

- `UTCDateTimeText` lưu chuỗi 27 ký tự, định dạng
  `%Y-%m-%dT%H:%M:%S.%fZ`; giá trị trả về là datetime UTC aware.
- PostgreSQL dùng `TIMESTAMP WITH TIME ZONE` qua adapter theo dialect;
  SQLite tiếp tục giữ định dạng cũ. Parse nguồn bằng `from_db_utc()`, giữ microsecond,
  chuẩn hóa UTC khi trả về; từ chối datetime naive theo quy tắc domain hiện có.
- Kiểm round-trip và hai lịch nối tiếp; không dựa vào timezone hiển thị của DB
  để thay đổi ý nghĩa thời gian API.

### `app/db/models.py`

- Có năm bảng: `venues`, `users`, `sessions`, `participations`, `matching_requests`.
- `venues.is_active` là Boolean nhưng CHECK `is_active IN (0, 1)` riêng SQLite.
  PostgreSQL giữ Boolean/NOT NULL, bỏ CHECK số nguyên này theo dialect.
- `uq_participations_active`: unique `(user_id, session_id)` với predicate
  `status IN ('PENDING', 'ACCEPTED')`.
- `uq_matching_requests_active_user`: unique `user_id` với predicate
  `status = 'ACTIVE'` (bao gồm yêu cầu quá giờ chưa đóng).
- Hai index hiện chỉ có `sqlite_where`; phải có `postgresql_where` tương đương.
  Nếu bỏ predicate, lịch sử nhiều lượt/request của cùng user sẽ không nhập được.
- Giữ các CHECK enum, rank 1..19, thời gian, phí và trạng thái đóng/hủy;
  giữ FK và không thêm cascade xóa lịch sử. Dữ liệu gender UNSPECIFIED vẫn hợp lệ ở users.
- ID Integer phải giữ nguyên khi nhập; đồng bộ sequence theo `MAX(id)` rồi thử
  INSERT không truyền ID. Bảng rỗng phải dùng trạng thái sequence chưa được gọi
  (`setval(..., 1, false)`), bảng có dữ liệu dùng max ID với `is_called=true`.
- Unique email hiện có phải tiếp tục phân xử đăng ký đồng thời.
  Sức chứa và lịch chồng là invariant liên bảng, không được tuyên bố các unique
  index trên tự bảo vệ được chúng.

### `app/db/unit_of_work.py` và `errors.py`

- UoW hiện bắt đầu bằng `BEGIN IMMEDIATE`/`BEGIN`, rollback khi thoát,
  chặn lồng UoW, truy cập ngoài phạm vi và truy cập sau commit.
- `is_database_busy()` chỉ nhận `sqlite_errorcode`; chưa nhận SQLSTATE PostgreSQL.
- `SqlAlchemyMatchingRequestWriter` nhận session provider và không commit riêng;
  giữ bảo đảm này khi Member 3 chuyển adapter về module Matching.
- Chưa có migration versioned. `scripts/seed.py` dùng `create_all()` cho demo,
  không thay thế migration. Giai đoạn 2 bổ sung Alembic; không chạy seed để nâng schema.

## 2. Xác nhận phía Member 2 về hợp đồng dùng chung

### UoW và quyền sở hữu transaction

Chấp nhận giữ `write()`, `read()`, `commit()` theo đề nghị Member 1/3:

- Mỗi command có UoW riêng; use case mở và commit đúng một lần.
- Repository, profile reader, Catalog reader, locks và Matching writer nhận
  `lambda: uow.session`; dùng cùng Session/connection/transaction của lệnh.
- Không auto-commit khi thoát, không commit trong repository/locks/writer,
  không mở UoW lồng. Ngoại lệ hoặc thiếu commit rollback toàn bộ.
- Lỗi commit phải truyền ra, không trả DTO thành công; không truy cập session sau commit.
- SQLite tiếp tục `BEGIN IMMEDIATE` cho ghi. PostgreSQL `write()` dùng
  READ COMMITTED và khóa hàng; không phát `BEGIN IMMEDIATE`.
- Member 1 sở hữu định nghĩa port và sửa docstring đang ghi cứng SQLite;
  Member 2 triển khai adapter ở giai đoạn 2. Không sửa port chung trong bàn giao này.

### Port khóa

Member 2 chấp nhận chữ ký Member 1 đề xuất trong `app/domain/ports.py`:

```python
class TransactionLocks(Protocol):
    def lock_session(self, session_id: int) -> bool: ...
    def lock_user(self, user_id: int) -> bool: ...
```

- Chỉ gọi trong UoW ghi đang hoạt động. True: hàng tồn tại, giữ khóa đến cuối
  transaction. False: không tìm thấy hàng; use case quyết định lỗi HTTP/nghiệp vụ.
- Adapter PostgreSQL dùng SELECT ID ... FOR UPDATE trên connection hiện tại.
  SQLite kiểm tồn tại sau khi UoW lấy khóa ghi. Không commit/đọc đồng hồ trong adapter khóa.
- Quy tắc: session tồn tại theo ID tăng dần → user theo ID tăng dần → participation
  → matching. Tạo kèo khóa host trước khi thêm session mới; tạo Matching chỉ khóa user.
  Không lấy khóa session đã tồn tại sau khi giữ khóa user.
- Member 1 điều khiển thứ tự khóa Sessions; Member 3 dùng cùng khóa user khi tạo
  Matching. Member 2 cung cấp primitive, không chuyển luật nghiệp vụ vào SQL adapter.
- Đọc lại bằng truy vấn mới sau khóa; nếu lấy ORM entity dùng `populate_existing=True`
  hoặc refresh tường minh. SELECT ID để lấy khóa không tự làm mới entity đã cache.
  Sau khóa use case đọc lại Clock, trạng thái, số chỗ và lịch trước khi quyết định.

### Snapshot đọc

Chọn `read()` PostgreSQL là **REPEATABLE READ, READ ONLY** cho toàn phạm vi,
thiết lập trước SELECT đầu tiên; SQLite giữ BEGIN tường minh hiện tại.
Như vậy count + page và các phần chi tiết dùng cùng snapshot. Snapshot PostgreSQL
được thiết lập ở truy vấn đầu tiên, không phải cam kết dữ liệu mới nhất lúc trả response.
`write()` vẫn READ COMMITTED để truy vấn sau khi chờ khóa thấy dữ liệu vừa commit.
Không dùng `read()` cho command; không khóa FOR UPDATE trong transaction read-only.

### Timeout, lỗi và retry (quyết định triển khai từ phía Member 2)

Thông số khởi điểm để kiểm thử, chưa phải cấu hình đã đo tối ưu:
pool_size=5, max_overflow=0, pool_timeout=5 giây; connect_timeout=5 giây;
lock_timeout=5 giây; statement_timeout=15 giây. Với N worker, tổng pool API tối đa
là N×5, phải tính thêm migration/monitor/test và giới hạn kết nối DB.

- SQLite BUSY và PostgreSQL SQLSTATE `55P03` (lock timeout/unavailable): rollback,
  `503 DATABASE_BUSY`, `Retry-After: 1` như contract hiện tại.
- Pool checkout timeout: `503 DATABASE_BUSY`, `Retry-After: 1`; bắt riêng
  `sqlalchemy.exc.TimeoutError`, không chỉ DBAPIError.
- `40P01` (deadlock), `40001` (serialization failure): rollback toàn lệnh,
  trả `503 DATABASE_BUSY`, `Retry-After: 1`; giai đoạn đầu không tự retry command.
- `57014` do statement timeout: rollback, dự kiến `503 DATABASE_TIMEOUT`.
  Không gán mọi `57014` thành lock timeout; driver có thể báo cùng mã khi query bị hủy.
- Lỗi kết nối (class 08/driver OperationalError do mất kết nối): dự kiến
  `503 DATABASE_UNAVAILABLE`. Mất kết nối lúc commit có thể chưa biết commit thành
  công hay chưa: không tự replay, không tuyên bố chắc chắn đã rollback trên server.
- Unique/FK/CHECK không đổi thành DATABASE_BUSY. Chỉ map unique constraint đã biết
  sang lỗi nghiệp vụ; lỗi toàn vẹn bất ngờ giữ ở error handler, không lộ SQL/credentials.
- `DATABASE_TIMEOUT`/`DATABASE_UNAVAILABLE` là mã **đề xuất bổ sung**, Member 1 cần
  xác nhận error contract trước tích hợp; chưa tồn tại trong runtime hiện tại.

Nhận diện SQLSTATE từ driver (`sqlstate` của psycopg 3), không so text thông báo.
Các giá trị timeout trên không cộng thành cam kết deadline HTTP; proxy/backend
phải phối hợp deadline với Member 3 ở giai đoạn 3.

## 3. Dữ liệu SQLite để chuyển thử

Script [prepare_member2_phase1.py](../../scripts/prepare_member2_phase1.py) tạo
DB **tổng hợp**, không đọc/sao chép dữ liệu người dùng thật và không thay `app.db`.
Vì workspace không có bản DB nghiệp vụ được cung cấp, đây là bộ dữ liệu kiểm tra
đặc trưng lịch sử, không phải bằng chứng đã nhập dữ liệu production.

```powershell
.venv/Scripts/python.exe -m scripts.prepare_member2_phase1
```

Đầu ra nằm trong `artifacts/member2-phase1/` (đã gitignore):
`migration-source.db` và `migration-source.manifest.json`. Script từ chối ghi đè;
chạy lại với `--output artifacts/member2-phase1-run2` để giữ bằng chứng cũ.

Số lượng dự kiến: venues=1, users=3, sessions=1, participations=4,
matching_requests=3. ID cố định, không liên tiếp để phát hiện lỗi reset sequence:
max ID lần lượt 10/40/50/90/120. Các điểm kiểm tra:

- Session 50 có host 20 ACCEPTED và player 30 ACCEPTED; chưa vượt sức chứa đôi.
- Cùng player/session còn lượt REJECTED 70, CANCELLED 80 và ACCEPTED 90:
  nhập thành công chỉ khi unique index giữ đúng predicate.
- User 40 có Matching 100 CLOSED/REPLACED, 110 CLOSED/CONFIRMED,
  120 ACTIVE; vẫn giữ hồ sơ UNSPECIFIED để kiểm tương thích dữ liệu cũ.
- Timestamp chuẩn `2030-11-01T10:00:00.123456Z`, giữ microsecond và UTC.
- Giữ snapshot phí 60000/40000, giới tính MALE/FEMALE; không tạo hash đăng nhập thật.
- Script kiểm `PRAGMA foreign_key_check`, `PRAGMA integrity_check` trước ghi manifest.

Giai đoạn 2 nhập venues + users → sessions → participations + matching_requests;
so counts/ID/trạng thái/timestamp với manifest, kiểm predicate thực trong catalog
PostgreSQL, điều chỉnh sequence rồi thử INSERT trên DB thử nghiệm.

## 4. PostgreSQL cục bộ và cách cấp fixture

[compose.phase1-member2.yaml](../../compose.phase1-member2.yaml) là stack DB
độc lập với Compose SQLite hiện tại. PostgreSQL 17, cổng loopback 55432,
volume riêng; mật khẩu lấy từ môi trường và không ghi vào Git.

```powershell
$env:MEMBER2_POSTGRES_PASSWORD = [guid]::NewGuid().ToString('N')
docker compose -f compose.phase1-member2.yaml config --quiet
docker compose -f compose.phase1-member2.yaml up -d --wait postgres
docker compose -f compose.phase1-member2.yaml exec -T postgres psql -U matchmate -d matchmate_phase1 -c 'SELECT version(), current_database(), current_setting(''TimeZone'');'
```

Giữ mật khẩu cục bộ cho lần chạy sau: thay env không đổi mật khẩu role trong
volume đã khởi tạo. Không cấu hình API hiện tại trỏ DB này khi adapter chưa hỗ trợ.
Image `postgres:17` là lựa chọn dev; giai đoạn phát hành phải ghi lại digest thực.

Fixture PostgreSQL giai đoạn 2–3 sẽ dùng DB test riêng, migrate schema trước test;
không dùng một outer transaction bao cả test cạnh tranh. A/B mở connection vật lý
khác nhau tới cùng DB (kiểm `pg_backend_pid()` khác nhau), mỗi tác vụ UoW riêng.
Dùng Event/Barrier để A giữ khóa trước khi B thử; timeout test phải lớn hơn lock
timeout; kiểm kết quả cuối bằng connection C sau khi A/B kết thúc. Không suy luận
tính đúng từ sleep hoặc test trên SQLite.

Các ca bàn giao: tồn tại/không tồn tại; B chờ A rồi thấy trạng thái commit mới;
timeout; nhả khóa sau commit/rollback; lỗi flush/commit; đọc lại không stale;
REPEATABLE READ giữ count/page; writer và participation rollback cùng nhau.
Các race nghiệp vụ do Member 1/3 chủ trì, Member 2 hỗ trợ fixture/adapter.

## 5. Phác thảo triển khai và khôi phục

Topology đích: Internet → reverse proxy HTTPS → API → PostgreSQL.
Chỉ proxy publish cổng. Proxy/API chia sẻ mạng ingress nội bộ; API/migrate/DB
chia sẻ mạng DB private; metrics không publish ra Internet.

- Member 3 cung cấp proxy/TLS/rate limit và request metrics; Member 2 cung cấp
  Compose, DB, readiness, DB telemetry. Backend Member 1 giữ JWT/object authorization.
- Tác vụ `migrate` chạy một lần từ cùng image phát hành, `alembic upgrade head`,
  đợi DB healthy; API phụ thuộc migrate hoàn tất thành công. Không để mỗi worker
  tự migrate. Migration lỗi chặn release. Đây là phác thảo, chưa có service migrate.
- `/health` giữ liveness; readiness dùng SELECT 1 với timeout ngắn, lỗi DB làm
  ngừng nhận traffic, không liên tục restart API chỉ vì DB đang mất kết nối.
- Không cần Redis/Kafka/Kubernetes cho giai đoạn này.

Backup demo chọn **kho ngoài máy ứng dụng**, ví dụ thư mục trên máy người vận hành
riêng `matchmate-backups/<release>/<UTC timestamp>/`, nhận dump bằng kênh bảo mật.
Local `artifacts/` chỉ là staging/bằng chứng, không tính là backup off-host.
Cần nhóm cung cấp máy/kho thật trước nghiệm thu; chưa có đích ngoài máy được cấu hình.
Dump PostgreSQL dạng custom bằng `pg_dump -Fc`, checksum, lưu quyền truy cập hạn chế;
khôi phục bằng `pg_restore` vào DB thứ hai, không ghi đè DB nguồn/backup.
SQLite đang ghi phải dùng SQLite backup API hoặc dừng ghi khi chụp, không copy
mỗi file `.db` và bỏ qua WAL. Fixture tổng hợp đã đóng connection khi bàn giao.

Mục tiêu diễn tập: phát hiện DB mất kết nối ≤30 giây; API phục hồi ≤60 giây sau
khi DB khỏe; RTO ≤30 phút; RPO ≤24 giờ khi backup thành công hằng ngày. Đo từ mốc
sự cố đến khi smoke test dữ liệu/nghiệp vụ đạt, không chỉ thời gian chạy restore.
Quay lui image chỉ khi schema tương thích; sau khi PostgreSQL nhận ghi mới,
không quay về SQLite cũ bằng cách đổi URL vì sẽ mất các ghi mới.

## 6. Tình trạng bàn giao và việc còn phụ thuộc

- [x] Khảo sát bốn file persistence, lỗi DB và writer; ghi khác biệt theo dialect.
- [x] Phản hồi phía Member 2 cho UoW/locks/snapshot, thứ tự khóa và cách test connection.
- [x] Chuẩn bị script nguồn SQLite tổng hợp, manifest và Compose PostgreSQL riêng.
- [x] Tạo dữ liệu SQLite và xác minh PostgreSQL cục bộ healthy (bằng chứng ở phần 8).
- [x] Phác thảo migration một lần, mạng private, backup off-host và mục tiêu khôi phục.
- [ ] Member 1/3 ghi nhận đồng thuận; Member 1 bổ sung port và chốt mã lỗi mới.
- [ ] Adapter PostgreSQL, Alembic/import và fixture cạnh tranh: giai đoạn 2–3.
- [ ] Chạy migration/import thật, restore và đo phục hồi: chưa có bằng chứng ở Phase 1.

Không sửa checkbox trong docs của Member 1/3 thay cho xác nhận của họ.
Không gửi thông điệp tới thành viên khác. Link báo cáo trong `phase1-member1.md`
đang trỏ nhầm thư mục Architecture_Phase2; báo cáo thực tế ở cùng thư mục implementation.

## 7. Liên hệ học liệu

- Persistence Layer trang 2–4, 6–9: boundary, Repository/UoW, Data Mapper, migration
  → phần 1–3 và hợp đồng transaction của Member 2.
- Kiểu kiến trúc trang 3–7; Designing Architecture trang 27–29: hướng phụ thuộc,
  giao diện giữa lớp → SQL/khóa nằm ở adapter, use case gọi port.
- Docker trang 2–8: container/Dockerfile/CI → môi trường DB và release có thể tái lập.
- Quality Attributes trang 7–19, 24: phát hiện/phục hồi, deployability, performance
  → readiness, backup/restore, rollout và số đo pool/lock/transaction.
- CQRS là phần phối hợp: hỗ trợ snapshot đọc nhất quán cho query của Member 1/3,
  không xây read replica hay database đọc riêng.

Khóa PostgreSQL, SQLSTATE, sequence và TIMESTAMPTZ là chi tiết cần tài liệu bổ sung:
[Transaction isolation](https://www.postgresql.org/docs/17/transaction-iso.html),
[Explicit locking](https://www.postgresql.org/docs/17/explicit-locking.html),
[Error codes](https://www.postgresql.org/docs/17/errcodes-appendix.html).
Không coi các kỹ thuật này là nội dung đã được slide hướng dẫn đầy đủ.

## 8. Kết quả thực thi ngày 19/11/2026

Môi trường: Windows, Python 3.14, SQLAlchemy 2.1.4 theo constraints của repo;
Docker Engine 29.8.0. Đã cài `requirements-dev.txt` vào `.venv`.

### PostgreSQL cục bộ

- `docker compose ... config --quiet`: thành công.
- `docker compose ... up -d --wait postgres`: container healthy.
- Server thực tế: PostgreSQL **17.11**, database `matchmate_phase1`, timezone UTC;
  `SHOW lock_timeout` = 5s, `SHOW statement_timeout` = 15s.
- Image đã chạy:
  `postgres@sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe`.
- Container `matchmate-member2-phase1-postgres-1` được giữ chạy để tiếp tục giai đoạn 2;
  chỉ bind `127.0.0.1:55432`. Chưa có schema nghiệp vụ/migration trong DB này.
- Mật khẩu demo ngẫu nhiên lưu cục bộ ở
  `artifacts/member2-phase1/postgres.env` (gitignored), không chép vào tài liệu.
  Dùng lại đúng file này cho stack đã khởi tạo:

```powershell
docker compose --env-file artifacts/member2-phase1/postgres.env -f compose.phase1-member2.yaml ps
docker compose --env-file artifacts/member2-phase1/postgres.env -f compose.phase1-member2.yaml exec -T postgres psql -U matchmate -d matchmate_phase1
# Dừng khi không dùng; giữ volume và dữ liệu:
docker compose --env-file artifacts/member2-phase1/postgres.env -f compose.phase1-member2.yaml stop
```

### SQLite và kiểm thử

- Đã chạy script tạo DB nguồn: counts users=3, venues=1, sessions=1,
  participations=4, matching_requests=3; max ID và timestamp đúng phần 3.
- `foreign_key_check` và `integrity_check`: đạt.
- Hai test mới tại
  [test_member2_phase1_fixture.py](../../tests/foundation/test_member2_phase1_fixture.py):
  **2 passed**. Kiểm lịch sử cùng user/session vẫn tồn tại, active trùng bị từ chối
  ở cả hai partial unique index, và không ghi đè bằng chứng cũ.
- Ruff check hai file Python mới: đạt; đã format bằng Ruff.
- Kiểm nền tảng + kiến trúc:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m pytest tests/foundation tests/test_architecture.py -q
```

Kết quả cuối: **72 passed, 1 failed**, một cảnh báo deprecation của Starlette/AnyIO.
Test cũ `test_runtime_engine_uses_explicit_test_database` tại
`tests/foundation/test_session.py:58` so sánh nguyên chuỗi URL: SQLAlchemy biểu diễn
đường dẫn Windows bằng percent-encoding, khác chuỗi backslash đầu vào; timeout vẫn
đúng 1200. Không đổi assertion này hoặc runtime trong bàn giao Phase 1.
Lần chạy thiếu `PYTHONUTF8=1` còn lỗi đọc file tiếng Việt ở test kiến trúc; dùng UTF-8
thì test kiến trúc đạt. Không tuyên bố toàn bộ regression suite đã xanh.

Đã chạy `git diff --check`: đạt. Chưa chạy toàn bộ suite/API, PostgreSQL concurrency,
import/migration hay restore; các kết quả SQLite trên không thay bằng chứng PostgreSQL.
