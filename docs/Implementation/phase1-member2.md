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
- [x] Member 1 ghi nhận phản hồi Member 2 ở `a5402b4`; Member 2 đối chiếu lại ở phần 9.
- [x] Đối chiếu Member 3 tại `6ba6c60` và Member 1 tại `7c9a400`; bổ sung phương án
  cho cancellation, projection sân và hồ sơ thiếu ở phần 10.
- [ ] Member 1 công bố port/chốt mã lỗi mới; Member 3 xác nhận phần giao tiếp mình sở hữu.
- [ ] Adapter PostgreSQL, Alembic/import và fixture cạnh tranh: giai đoạn 2–3.
- [ ] Chạy migration/import thật, restore và đo phục hồi: chưa có bằng chứng ở Phase 1.

Không sửa checkbox trong docs của Member 1/3 thay cho xác nhận của họ.
Không gửi thông điệp tới thành viên khác. Member 1 đã sửa link báo cáo về cùng
thư mục implementation ở commit `a5402b4`.

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

Kết quả lần bàn giao đầu: **72 passed, 1 failed**, một cảnh báo deprecation của Starlette/AnyIO.
Test cũ `test_runtime_engine_uses_explicit_test_database` tại
`tests/foundation/test_session.py:58` so sánh nguyên chuỗi URL: SQLAlchemy biểu diễn
đường dẫn Windows bằng percent-encoding, khác chuỗi backslash đầu vào; timeout vẫn
đúng 1200. Assertion đã được sửa trong lượt đối chiếu cập nhật ở phần 9.
Lần chạy thiếu `PYTHONUTF8=1` còn lỗi đọc file tiếng Việt ở test kiến trúc; dùng UTF-8
thì test kiến trúc đạt. Không tuyên bố toàn bộ regression suite đã xanh.

Đã chạy `git diff --check`: đạt. Chưa chạy toàn bộ suite/API, PostgreSQL concurrency,
import/migration hay restore; các kết quả SQLite trên không thay bằng chứng PostgreSQL.

## 9. Đối chiếu cập nhật Member 1 tại `a5402b4`

Đã đọc toàn bộ bản cập nhật `phase1-member1.md` ngày 19/11/2026. Bản cập nhật
**ghi nhận** các đề nghị của Member 2/3; vẫn để mở xác nhận của chủ sở hữu contract.
Phần này cung cấp phương án đủ cụ thể để triển khai, tách việc chọn thiết kế khỏi
việc chứng minh runtime. Không đánh dấu thay xác nhận của Member 1/3.

### 9.1. Các điểm không còn khác biệt từ phía Member 2

Member 2 xác nhận giữ nguyên phần 2: use case sở hữu UoW; locks/reader/writer chung
transaction; port khóa trả bool; session trước user; đọc mới và Clock sau khóa;
read REPEATABLE READ READ ONLY, write READ COMMITTED; timeout/pool như đã nêu;
không tự retry command. Nội dung cập nhật của Member 1 không mâu thuẫn các lựa chọn này.

Member 1 công bố `TransactionLocks` ở `app/domain/ports.py`; Member 2 dự kiến đặt
adapter tại `app/db/transaction_locks.py`, nhận `Callable[[], Session]` giống writer
hiện tại. Đây là vị trí đã chọn từ phía Member 2 để chuẩn bị giai đoạn 2, chưa có file
adapter và chưa có SQL khóa trong service. Các kiểm thử PostgreSQL ở phần 4 vẫn là
điều kiện tích hợp, không phải phần thiếu xác nhận hợp đồng.

### 9.2. Error contract gửi Member 1 để công bố

Giữ envelope `make_error_response()` hiện tại:
`error = {code, message, details, request_id}` và header `X-Request-ID`.
Đề nghị Member 1 công bố hai exception thuần Python trong `app/domain/errors.py`:
`DatabaseTimeoutError` và `DatabaseUnavailableError`; Member 2 nhận diện lỗi driver
ở infrastructure, không đưa SQLSTATE/SQLAlchemy vào domain hoặc service.
Member 1 đăng ký handler trong `app/api/error_handlers.py` với phản hồi chính xác:

- `DatabaseBusyError`: HTTP 503, `DATABASE_BUSY`, message hiện tại
  `Hệ thống đang bận, vui lòng thử lại`, `details={}`, `Retry-After: 1`.
- `DatabaseTimeoutError`: HTTP 503, `DATABASE_TIMEOUT`, message
  `Thao tác dữ liệu vượt quá thời gian cho phép`, `details={}`;
  không thêm Retry-After mặc định để tránh khuyến khích retry command chưa có idempotency.
- `DatabaseUnavailableError`: HTTP 503, `DATABASE_UNAVAILABLE`, message
  `Không thể kết nối cơ sở dữ liệu`, `details={}` khi lỗi xảy ra trước commit.
  Trường hợp mất kết nối **trong commit**, exception nhận `outcome_unknown=True`;
  handler trả `details={"outcome": "unknown"}` và message
  `Chưa xác định được kết quả thao tác dữ liệu`.
  Không thêm Retry-After và không tự replay trong cả hai trường hợp unavailable.

Không thêm trường outcome vào response thành công hoặc các lỗi khác. Client gặp
outcome unknown phải đối chiếu trạng thái tài nguyên; chưa có API idempotency thì
không tự gửi lại lệnh tạo. Busy có Retry-After giữ tương thích hiện hành, không có
nghĩa adapter sẽ retry tự động.

Tiêu chí test chung trước tích hợp: status/code/message/header đúng; cùng envelope
và request_id; không lộ SQL, connection URL/password; timeout/flush lỗi xác minh
rollback bằng connection khác. Commit-unknown phải được test riêng và không khẳng
định mutation chưa xảy ra. `57014` là query cancellation: chỉ gán nguyên nhân
statement timeout khi có ngữ cảnh xác định; không so text driver, không đổi thành
DATABASE_BUSY. Nếu không phân biệt được nguồn hủy, chỉ công bố lỗi thực thi bị hủy,
không ghi log/metrics như đã chứng minh lock timeout.

Đây là bản đề nghị cuối từ Member 2; các mã mới vẫn chưa được Member 1 xác nhận
hay triển khai. Các mã HTTP/nghiệp vụ hiện có không đổi trong lượt sửa tài liệu này.

### 9.3. Projection hồ sơ ứng viên: phương án tránh N+1

Member 2 đề nghị Member 1/3 dùng bước đọc theo lô trước khi cần tối ưu join:
Identity công bố thêm port ở `app/features/auth/contracts.py`:

```python
class PlayerProfilesReader(Protocol):
    def get_by_ids(self, user_ids: list[int]) -> dict[int, PlayerProfile]: ...
```

- `PlayerProfile` dùng đúng bốn trường và enum Member 3 đề xuất. Thiếu ID thì
  không có key trong kết quả; danh sách rỗng trả `{}` không truy vấn. Loại ID trùng.
- Query Matching lấy request/candidate ID theo thứ tự `(created_at, id)`, rồi đọc
  profile theo lô trong **cùng UoW**, dựng DTO theo thứ tự candidate ban đầu.
  Không lấy thứ tự của dict/SQL IN làm thứ tự xếp ứng viên.
- Identity chỉ SELECT id/display_name/skill_level/gender, không SELECT nguyên
  UserModel rồi truyền ra ngoài; trả DTO, giữ UNSPECIFIED, dùng skill_to_rank khi
  chuyển sang PlayerSummary. Matching xử lý hồ sơ thiếu bằng luật hiện hành,
  không tự thay đổi ý nghĩa suggestion.
- Adapter do Identity sở hữu; composition root inject qua port, Matching không
  import adapter nội bộ Auth. Với tập ID lớn được chia batch có giới hạn tham số;
  số query theo số batch, không gọi get_by_id cho từng người.
- Đây là phương án batch thay thế join xuyên module cho hồ sơ. Nếu đo cho thấy
  cần join trực tiếp, Identity phải công bố projection đọc với bốn cột trên trước;
  không tự cấp quyền SELECT credential hoặc thay pagination/total của Discovery.

Member 1/3 sở hữu quyết định công bố port này. Member 2 xác nhận hỗ trợ adapter,
kiểu dữ liệu và transaction; không tự tạo port Identity thay Member 1 trong Phase 1.

### 9.4. Catalog, vị trí writer và wiring

Member 2 không có yêu cầu thay `VenueStatusReader.is_active() -> bool | None` tại
`app/features/catalog/contracts.py`. Reader được inject với session provider
của UoW bên gọi; False/None giữ ý nghĩa Member 1/3 đã ghi.

Đề nghị vị trí đích cụ thể của writer là
`app/features/matching/infrastructure/matching_request_writer.py`, lớp
`SqlAlchemyMatchingRequestWriter`, giữ port ở `app/domain/ports.py`.
Member 3 tạo package và chuyển adapter; composition root của Member 1 import/lắp
implementation, Sessions service chỉ import port. Member 2 hỗ trợ SQL/dialect,
không tạo bản writer thứ hai ở `app/db` hoặc sửa hành vi CONFIRMED/REPLACED.
Adapter cũ chỉ xóa sau khi mọi wiring/test chuyển sang đường dẫn mới. Vị trí này
là đề nghị để Member 1/3 chốt, chưa phải file đã tồn tại.

### 9.5. Timeout với ingress: đề nghị cho giai đoạn 3

Các timeout 5/15 giây giới hạn từng thao tác DB, không giới hạn tổng request.
Không lấy phép cộng chúng làm bằng chứng request luôn kết thúc đúng hạn.
Member 2 đề nghị proxy upstream response timeout ban đầu 30 giây cho demo đồng bộ;
Member 3 công bố cấu hình thực, đo riêng Matching và xác nhận phù hợp workload.
Nếu proxy trả 504/ngắt kết nối, command trong backend có thể vẫn commit; không tự
retry, không suy luận timeout HTTP đồng nghĩa rollback. Chỉ áp deadline toàn command
khi đã thiết kế cancellation/kiểm kết quả rõ ràng. Chưa bật retry upstream cho POST.

### 9.6. Đã xử lý điều kiện kiểm thử trên Windows

- `test_runtime_engine_uses_explicit_test_database`: subprocess trả
  `engine.url.database`, so với đường dẫn file dự kiến và vẫn kiểm timeout=1200.
  Kiểm đúng DB đích, không phụ thuộc percent-encoding của chuỗi URL.
- Test kiến trúc đọc source bằng UTF-8 tường minh, không phụ thuộc codepage Windows.
  Không thay luật import hoặc bỏ qua test.
- Ruff check hai file test sửa: đạt.
- Chạy lại `.venv/Scripts/python.exe -m pytest tests/foundation tests/test_architecture.py -q`
  **không cần đặt PYTHONUTF8**: **73 passed**, 1 cảnh báo deprecation Starlette/AnyIO.
  Đây là suite chọn lọc, chưa phải toàn bộ test của dự án.

### 9.7. Phần còn phải được chủ sở hữu xác nhận tại thời điểm `abfc916`

Phía Member 2 đã có chữ ký, bảo đảm, đường dẫn dự kiến và tiêu chí kiểm chứng cho
các phụ thuộc đang mở. Còn Member 1 công bố port/error handler; Member 1/3 chọn
projection/vị trí writer; Member 3 xác nhận timeout ingress. Đây là quyết định
thuộc chủ sở hữu tương ứng, không tự chuyển thành đồng thuận toàn nhóm bằng việc
sửa checkbox. Adapter/migration/concurrency vẫn triển khai theo giai đoạn 2–3;
không cần đợi phần 9 được coi là bằng chứng runtime mới bắt đầu phần adapter độc lập.

## 10. Đối chiếu `7c9a400` của Member 1 và `6ba6c60` của Member 3

Ngày đối chiếu: **19/11/2026**. Phần này cập nhật trạng thái phần 9, không thay
các bằng chứng chạy test trước đó bằng kết quả chạy mới. Hai commit trên chỉ sửa
tài liệu, chưa công bố port/exception/adapter trong mã nguồn.

### 10.1. Những lựa chọn Member 2 và 3 đã cùng chấp nhận

Đã đọc xác nhận mục 9 của Member 3 và phần tổng hợp/checklist mới của Member 1:

- UoW/khóa: session provider dùng chung, bool tồn tại/đã khóa, thứ tự khóa và
  vị trí adapter `app/db/transaction_locks.py`.
- Snapshot: read REPEATABLE READ READ ONLY, write READ COMMITTED; không dùng
  read-only để khóa/ghi và không coi snapshot là dữ liệu mới nhất lúc trả response.
- Identity: `PlayerProfilesReader.get_by_ids()` đọc theo lô, giữ enum/rank,
  không lộ credential, không dùng thứ tự SQL IN/dict để chọn nhóm.
- Catalog status reader và Matching writer ở vị trí phần 9.4; chỉ một implementation
  writer, chuyển wiring/test trước khi bỏ đường cũ.
- Error envelope/commit-unknown và cấu hình timeout/pool khởi điểm như phần 9.2/9.5;
  ingress 30 giây để đo demo, không retry upstream POST.

Như vậy không còn chờ Member 3 xác nhận lại các lựa chọn trên. Member 1 đã ghi nhận
chúng nhưng trong checklist của mình vẫn để mở xác nhận/công bố contract và wiring.
Member 2 giữ nguyên cam kết triển khai, không tự ghi rằng Member 1 đã công bố.

### 10.2. Bổ sung dứt điểm phương án cho `57014` chưa rõ nguồn hủy

Member 1 mục 2.3 yêu cầu nêu phản hồi cuối khi chưa phân biệt được query cancellation.
Member 2 chọn đề nghị sau để không nhận diện sai nguyên nhân hoặc phát sinh thêm mã
API chưa cần thiết:

- Chỉ tạo `DatabaseTimeoutError` khi có ngữ cảnh tin cậy xác định statement timeout,
  ví dụ nhánh deadline do adapter quản lý; **SQLSTATE `57014` riêng lẻ chưa đủ**.
  Có cấu hình statement_timeout không chứng minh mọi cancellation đều do timeout.
- `57014` không xác định được nguồn hủy: rollback transaction nếu thất bại đã rõ,
  truyền lỗi kỹ thuật tới generic error handler hiện tại. Client nhận **HTTP 500,
  `INTERNAL_ERROR`, message `Không thể xử lý yêu cầu`, details `{}`**, giữ request_id
  và `X-Request-ID`; không `Retry-After`, không SQL/driver message trong response.
- Telemetry nội bộ phân loại `query_cancelled_unknown`, có SQLSTATE và phase
  (`execute`/`commit`) nhưng không ghi SQL/params/URL/password; không gán nó thành
  metric statement_timeout hay lock_timeout. Đây là tên loại lỗi trong telemetry,
  không phải nhãn request/user có cardinality cao hoặc mã API mới.
- Giai đoạn đầu chỉ có SQLSTATE mà chưa xác định được nguyên nhân thì dùng nhánh
  unknown này; không cần trì hoãn adapter để cố phân loại bằng chuỗi thông báo.
- Lỗi mất kết nối **trong commit** vẫn áp dụng `DATABASE_UNAVAILABLE` với
  `outcome=unknown`; không gộp nó với query cancellation chỉ vì cùng là lỗi DB.
  SQLSTATE deadlock/serialization/lock và lỗi toàn vẹn giữ mapping phần 2/9.2.

Test cần có khi triển khai: giả lập `57014` không có ngữ cảnh → generic 500;
nguồn timeout xác định → 503 DATABASE_TIMEOUT; hai nhánh không có Retry-After;
rollback khi kết quả thất bại xác định; commit-unknown không tự replay và không
assert mutation chắc chắn chưa xảy ra. Member 1 cần ghi nhận nhánh generic này khi
công bố handler; không cần thêm `DatabaseCancelledError` ở domain.

### 10.3. Projection sân đầy đủ để Member 1/3 chốt

Code hiện tại đã có DTO `VenueRecord` trong Discovery gồm năm trường
`id`, `name`, `address`, `district_code`, `is_active`; detail Sessions trả đúng
năm trường này. Member 2 đề nghị Catalog công bố kiểu tương ứng và reader tại
`app/features/catalog/contracts.py` do Member 3 sở hữu:

```python
@dataclass(frozen=True)
class VenueSummary:
    id: int
    name: str
    address: str
    district_code: str
    is_active: bool


class VenueReader(Protocol):
    def get_by_id(self, venue_id: int) -> VenueSummary | None: ...
    def get_by_ids(self, venue_ids: list[int]) -> dict[int, VenueSummary]: ...
```

Quy tắc dữ liệu và persistence Member 2 hỗ trợ:

- SELECT đúng năm cột; trả DTO thuần và cùng transaction bên gọi; không commit,
  mở UoW riêng hoặc trả ORM. Danh sách rỗng không query; loại ID trùng; thiếu ID
  không có key; batch tối đa đề nghị 500 ID/câu để dùng được cả SQLite/PostgreSQL.
  Đây là kích thước batch, **không phải giới hạn số kết quả nghiệp vụ**.
- `get_by_id/get_by_ids` trả cả sân inactive để xem lịch sử. Không lọc inactive
  ở reader chung. Danh sách sân công khai hiện chỉ lấy sân active, lọc quận,
  order ID, count/page: Discovery phải giữ riêng hành vi này.
- Không dùng VenueReader thay VenueStatusReader cho command: status reader vẫn
  None → VENUE_NOT_FOUND, False → VENUE_INACTIVE, True → tiếp tục kiểm nghiệp vụ.
- Discovery/detail ánh xạ VenueSummary sang DTO API hiện hành, không đổi tên
  trường hoặc thêm wrapper. Catalog không import contracts nội bộ Discovery/Sessions.
  Khi chuyển quyền sở hữu DTO, có thể giữ mapper tương thích trong read adapter,
  không duy trì hai model lưu trữ venue độc lập.

Phạm vi query/join để giữ bộ lọc và pagination:

- Discovery read adapter được đọc/join **projection năm cột Catalog trên** với
  Sessions theo hợp đồng đọc; chỉ đọc, không ghi venue hoặc import repository
  nội bộ Catalog. SQL/ORM vẫn ở infrastructure; shared storage metadata có thể
  dùng trong adapter trong cấu trúc repo hiện tại.
- Không thay join lọc sân bằng lấy một trang session trước rồi lọc sân bằng
  Python: làm sai total, limit/offset và số kết quả. Nếu dùng reader batch để enrich,
  bộ lọc/count/order phải đã được áp đúng trước phân trang.
- Detail đã có session nhưng mất venue FK: giữ lỗi kỹ thuật hiện hành, không
  biến thành SESSION_NOT_FOUND, không trả venue giả hoặc âm thầm bỏ trường.
  Sân inactive vẫn đọc được trong detail nếu endpoint hiện tại cho xem session đó.
- Member 3 công bố DTO/reader và phạm vi read adapter; Member 1 xác nhận dùng
  cho detail/wiring. Member 2 xác nhận khả năng SELECT/batch/FK/snapshot trên cả DB.

Tiêu chí kiểm chứng: active/inactive/missing; batch rỗng/trùng; chỉ năm cột;
filter quận và count/page giữ nguyên; detail không có N+1 theo từng sân khi đọc
danh sách; dữ liệu venue và session cùng snapshot. Đây là đề nghị cụ thể thay cho
mục projection sân còn mở, chưa phải Member 3 đã công bố port mới.

### 10.4. Hồ sơ ứng viên thiếu: kết luận từ query cũ

Đã đối chiếu `SqlAlchemyMatchingRepository.candidates()` trong
`app/features/discovery/repository.py`: dùng **INNER JOIN UserModel**,
lọc gender MALE/FEMALE, ACTIVE, sân/loại/lịch khớp, chưa bắt đầu, loại caller và
lịch ACCEPTED chồng nhau, order `(created_at, id)`.

Do đó Member 2 đề nghị contract tương thích khi Member 3 chuyển sang batch:

- Candidate không có profile: bỏ khỏi tập ứng viên, tương ứng INNER JOIN cũ;
  không KeyError/hồ sơ giả và không đóng/xóa matching request vì thiếu profile.
- Candidate UNSPECIFIED: loại trước Strategy, tương ứng bộ lọc gender cũ.
  Caller thiếu vẫn UNAUTHORIZED; caller UNSPECIFIED vẫn PROFILE_INCOMPLETE.
- Giữ mọi bộ lọc request/overlap và thứ tự tương đối của ứng viên còn hợp lệ.
  Không giới hạn top-K để vừa batch, không tự biến lỗi truy vấn thành suggestion=null.
- Thiếu hồ sơ ở DB đã bật FK thường không xảy ra: kiểm tương thích bằng fake
  reader hoặc dữ liệu legacy được kiểm soát; không tắt FK trong app để tạo test.
- Các truy vấn batch trong command ở READ COMMITTED vẫn theo isolation đã chọn;
  không tuyên bố chúng có snapshot chung như read REPEATABLE READ. Khóa caller
  bảo vệ lịch của caller, không phải khóa toàn bộ hồ sơ ứng viên. Gợi ý không giữ chỗ.

Điều này cung cấp kết quả đối chiếu mà Member 1 mục 3.5 và Member 3 mục 9.2 yêu cầu;
Member 3 thêm test first-valid/thứ tự/profile thiếu khi hiện thực batch reader.

### 10.5. Bàn giao để chuyển sang giai đoạn 2

- [x] Member 2 ghi nhận xác nhận thực tế của Member 3, không yêu cầu xác nhận lại
  UoW/locks/batch/writer/timeout đã có ở `6ba6c60`.
- [x] Member 2 bổ sung nhánh phản hồi cancellation chưa rõ nguyên nhân.
- [x] Member 2 đề nghị chữ ký/semantics projection sân đầy đủ và phạm vi join đọc.
- [x] Member 2 đối chiếu query cũ và nêu quy tắc candidate thiếu/UNSPECIFIED.
- [ ] Member 1 công bố port khóa/UoW, profile/batch reader, error handler và wiring;
  ghi nhận nhánh cancellation unknown ở mục 10.2.
- [ ] Member 1/3 xác nhận projection sân cụ thể ở mục 10.3 và đưa vào contract Catalog.
- [ ] Member 3 hiện thực/test batch và Matching theo quy tắc tương thích mục 10.4.
- [ ] Member 2 hiện thực adapter/migration/import/fixture theo giai đoạn 2–3;
  phối hợp proxy/backend và đo connection budget trước demo.

Phần 10 chỉ thay đổi tài liệu Member 2; không sửa mã runtime, docs/checklist của
Member 1/3 hay coi port chưa tạo là đã hoàn thành. Chưa chạy lại test vì không đổi
code; bằng chứng gần nhất vẫn là **73 passed** ở mục 9.6. Những mục runtime chưa
đánh dấu là việc triển khai/nghiệm thu, không phải lý do phải thảo luận lại các
lựa chọn Member 2/3 đã cùng chấp nhận.
