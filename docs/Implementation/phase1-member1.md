# Phase 1 · Thành viên 1 · Yêu cầu bàn giao cho thành viên 2 và 3

Ngày lập và cập nhật đối chiếu: **19/11/2026**.

Tài liệu này chuyển các đề xuất trong
[báo cáo rà soát của thành viên 1](member-1-phase-1.vi.md)
thành đầu việc và tiêu chí bàn giao cho thành viên 2, thành viên 3.
Đã đối chiếu [báo cáo thành viên 2](phase1-member2.md) và
[đề xuất thành viên 3](phase1-member3.md), cùng
[kế hoạch triển khai](../Architecture_Phase2/kehoachtrienkhai-VN.md).
Các xác nhận đơn phương của từng thành viên được ghi rõ bên dưới; chúng chưa
thay cho đồng thuận của cả nhóm hoặc bằng chứng adapter mới đã hoạt động.

Lần đối chiếu mới nhất dựa trên mục 9 của báo cáo thành viên 2 (commit `abfc916`)
và các xác nhận mục 8–9 của thành viên 3 (commit `6ba6c60`). Các lựa chọn đã được
hai bên chấp nhận được cập nhật thành phương án triển khai; phần công bố hợp đồng
của thành viên 1 và bằng chứng runtime tiếp tục được theo dõi riêng.

## 1. Cần chốt gì ở cuối Phase 1?

| Người phụ trách | Nội dung cần thống nhất với thành viên 1 | Kết quả bàn giao |
| --- | --- | --- |
| Thành viên 2 | UoW, API khóa session/user, phạm vi transaction, snapshot đọc, lỗi timeout và fixture PostgreSQL | Chữ ký phương thức, bảo đảm của adapter, cách chạy kiểm thử trên các connection độc lập. |
| Thành viên 3 | Catalog, bộ đọc hồ sơ theo lô, matching writer và cấu hình ingress phối hợp với thành viên 2 | Giao diện trạng thái sân, quy tắc ghép hồ sơ giữ thứ tự ứng viên, đường dẫn writer và các ca kiểm thử tương thích. |

Phase 1 chốt hợp đồng và hành vi làm mốc. Phần xây adapter/refactor trên SQLite
và thử migration thuộc Phase 2; tích hợp khóa PostgreSQL thuộc Phase 3 theo kế hoạch.

### 1.1. Thông tin mới từ hai báo cáo

| Nội dung | Trạng thái được ghi nhận | Việc tiếp theo |
| --- | --- | --- |
| UoW và `TransactionLocks` | Thành viên 2 và 3 chấp nhận dùng chung transaction và thứ tự khóa; adapter dự kiến tại `app/db/transaction_locks.py` | Thành viên 1 công bố port; thành viên 2 xây adapter; thành viên 3 tích hợp `lock_user()` vào Matching. |
| Snapshot PostgreSQL | Thành viên 2 chọn và thành viên 3 chấp nhận `read()` REPEATABLE READ, READ ONLY; `write()` READ COMMITTED | Thành viên 1 công bố hợp đồng chung; thành viên 2 triển khai và kiểm chứng bằng fixture PostgreSQL. |
| PostgreSQL và dữ liệu nguồn | Thành viên 2 báo cáo PostgreSQL cục bộ healthy, có nguồn SQLite tổng hợp và manifest | Còn adapter, migration/import và kiểm thử cạnh tranh; chưa coi là tích hợp ứng dụng thành công. |
| Hồ sơ ứng viên | Thành viên 2 đề nghị và thành viên 3 chấp nhận `PlayerProfilesReader.get_by_ids()` do Identity sở hữu, giữ thứ tự request | Thành viên 1 công bố port/adapter Identity; thành viên 3 thay cách đọc và bổ sung test hồ sơ thiếu, đầu vào rỗng/trùng. |
| Catalog và Matching writer | Thành viên 3 xác nhận status reader tại `app/features/catalog/contracts.py` và writer tại `app/features/matching/infrastructure/matching_request_writer.py` | Thành viên 1 xác nhận/công bố wiring; thành viên 3 chuyển adapter. Projection sân đầy đủ vẫn cần chốt riêng. |
| Error contract và ingress | Thành viên 2 đề nghị exception/response cụ thể; thành viên 3 chấp nhận, gồm commit-unknown và response timeout demo 30 giây, không retry POST | Thành viên 1 công bố exception/handler; thành viên 2 map lỗi driver; thành viên 3 cấu hình/đo proxy thực. |
| Kiểm thử của thành viên 2 | Mục 9.6 ghi đã sửa URL Windows/UTF-8; suite nền tảng + kiến trúc chọn lọc đạt **73 passed**, Ruff đạt | Theo dõi kết quả mới này thay lỗi cũ 72 đạt/1 thất bại; vẫn cần suite tích hợp và bằng chứng PostgreSQL riêng. |

Đây là tổng hợp bằng chứng được ghi trong hai tài liệu. Checklist bên dưới đã
được đối chiếu với mã nguồn và các kiểm thử hiện có ngày 19/11/2026:
`[x]` chỉ phần đã có mã triển khai hoặc đầu ra tài liệu được nêu cụ thể; `[ ]`
chỉ phần chưa làm đủ hoặc chưa có bằng chứng. Những hành vi đã có trên SQLite
được ghi rõ phạm vi, không thay cho hoàn tất refactor hoặc kiểm chứng PostgreSQL.
Các kết quả chạy trước đây được dẫn theo báo cáo, không phải lượt chạy lại trong
lần cập nhật checklist này.

## 2. Thành viên 2 cần triển khai

### 2.1. Adapter Unit of Work cho SQLite và PostgreSQL

Giữ giao diện ứng dụng `write()`, `read()`, `commit()` trong
[app/domain/ports.py](../../app/domain/ports.py), đồng thời triển khai các bảo đảm:

Thành viên 2 đã chấp nhận hợp đồng này trong mục 2 của báo cáo. Cách lắp adapter
được đề nghị là nhận session provider `lambda: uow.session`, dùng chung cho
repository, profile/Catalog reader, locks và Matching writer.

- [x] Participation repository và matching writer hiện dùng chung session provider
  của UoW; xem [participation dependencies](../../app/features/sessions/participation_dependencies.py).
- [ ] Lắp đủ profile reader, Catalog reader và bộ khóa mới vào cùng transaction;
  các hợp đồng/adapter này chưa được triển khai.
- [x] Participation commands và tạo Matching hiện tự mở/commit UoW một lần;
  UoW không auto-commit khi thoát, repository/writer không commit riêng. Xem
  [ParticipationService](../../app/features/sessions/participation_service.py) và
  [DiscoveryService](../../app/features/discovery/service.py).
- [ ] Chuyển Auth và tạo/hủy kèo sang use case sở hữu transaction; hiện vẫn
  mở/commit ở dependency.
- [x] UoW SQLite rollback khi có ngoại lệ hoặc thoát mà chưa commit; lỗi commit
  truyền ra trước phản hồi thành công. Có [test UoW](../../tests/foundation/test_unit_of_work.py)
  và [test lỗi commit qua API](../../tests/integration/test_member1_baseline.py).
- [x] UoW chặn lồng phạm vi transaction, truy cập session ngoài phạm vi/sau commit
  và commit lần hai; có guard trong [adapter](../../app/db/unit_of_work.py).
- [x] Ghi SQLite hiện dùng `BEGIN IMMEDIATE` trong adapter UoW.
- [ ] Triển khai PostgreSQL `write()` READ COMMITTED; hiện adapter vẫn phát
  `BEGIN IMMEDIATE` và engine chỉ cấu hình cho SQLite.

**Quan hệ giữa worker và UoW:** hiện chỉ có một lớp triển khai
`SqlAlchemyUnitOfWork`, nhưng mỗi lệnh tạo một instance UoW riêng. Bộ khóa được
gắn với UoW của lệnh, không phải một instance dùng chung cho toàn bộ worker.
PostgreSQL điều phối khóa giữa các transaction/worker tại DB.

```text
Lệnh A → UoW A → connection + transaction A → repositories / locks / writer
Lệnh B → UoW B → connection + transaction B → repositories / locks / writer
```

Thành viên 1 phụ trách chuyển quyền mở/commit transaction từ dependency sang use
case ở Auth và tạo/hủy kèo. Thành viên 2 cung cấp adapter đáp ứng hợp đồng đó.

### 2.2. Adapter khóa session và user

Thành viên 2 đã chấp nhận port dưới đây; thành viên 3 đã đề xuất sử dụng
`lock_user()` với cùng ý nghĩa trả về. Thành viên 1 còn phải công bố port trong
`app/domain/ports.py` trước khi các bên tích hợp:

```python
class TransactionLocks(Protocol):
    def lock_session(self, session_id: int) -> bool: ...
    def lock_user(self, user_id: int) -> bool: ...
```

Thành viên 2 chọn vị trí adapter `app/db/transaction_locks.py`, nhận
`Callable[[], Session]`; thành viên 3 đã ghi nhận lựa chọn này. Đây là đầu ra cần
triển khai, chưa phải file đã tồn tại. Các phương thức thực hiện khóa hàng bi quan
trong transaction của UoW, không khóa một đối tượng UoW trong bộ nhớ.

- [ ] `True` nghĩa là hàng tồn tại và đã được khóa đến khi transaction kết thúc;
  `False` nghĩa là không có hàng. Use case chọn mã lỗi nghiệp vụ/xác thực phù hợp.
- [ ] PostgreSQL khóa hàng trên chính connection/transaction của UoW đang hoạt
  động bằng `SELECT id ... FOR UPDATE`. Chỉ gọi trong UoW ghi; không mở UoW mới,
  commit hoặc đọc Clock trong phương thức khóa.
- [ ] SQLite dùng khóa ghi đã lấy ở đầu UoW và kiểm tra hàng tồn tại; vẫn bảo toàn
  khả năng chạy đường SQLite để làm mốc so sánh.
- [ ] Cung cấp cách đọc lại dữ liệu sau khóa mà không bị bộ nhớ đệm ORM trả trạng
  thái đã đọc trước khi khóa: truy vấn mới với `populate_existing=True` hoặc
  refresh tường minh nếu dùng ORM entity. Chỉ SELECT ID để khóa không làm mới
  entity đã cache.
- [ ] Giải phóng khóa khi commit/rollback; có giới hạn thời gian chờ khóa.

Thứ tự gọi do use case của thành viên 1 điều khiển; adapter cung cấp thao tác khóa:

| Lệnh | Thứ tự khóa |
| --- | --- |
| Xin tham gia | Session → user xin tham gia. |
| Duyệt / từ chối | Tra cứu ban đầu để lấy ID → session → user của lượt → đọc lại trạng thái. |
| Rút lượt | Session → user của lượt → đọc lại trạng thái. |
| Hủy kèo | Session → lấy các user có lượt hoạt động → loại trùng, khóa user theo ID tăng dần. |
| Tạo kèo | User host → kiểm tra trùng lịch → thêm session mới. |
| Tạo yêu cầu matching, do thành viên 3 tích hợp | User gọi lệnh → kiểm tra lịch → thay yêu cầu matching. |

Quy tắc tổng quát: session đã tồn tại theo ID tăng dần → user theo ID tăng dần →
participation → matching. Không lấy khóa session đã tồn tại sau khi giữ khóa user.
Use case đọc đồng hồ và kiểm tra lại trạng thái sau khi lấy đủ khóa cần thiết.

### 2.3. Snapshot đọc và xử lý lỗi hạ tầng

Triển khai theo lựa chọn của thành viên 2 đã được thành viên 3 chấp nhận ở mục 9.1
và 9.4 trong báo cáo của mình:

- [ ] `read()` PostgreSQL dùng **REPEATABLE READ, READ ONLY**, thiết lập trước
  SELECT đầu tiên; SQLite giữ BEGIN tường minh. Count/page và các phần chi tiết
  trong cùng phạm vi phải nhìn cùng snapshot.
- [x] Đã ghi rõ trong hợp đồng tài liệu: snapshot PostgreSQL bắt đầu từ truy vấn đầu tiên, không bảo đảm dữ
  liệu mới nhất tại thời điểm trả response. Không dùng `read()` cho command hoặc
  `FOR UPDATE`; `write()` vẫn READ COMMITTED để đọc thấy trạng thái mới sau chờ khóa.
- [ ] Cấu hình khởi điểm: `pool_size=5`, `max_overflow=0`, `pool_timeout=5s`,
  `connect_timeout=5s`, `lock_timeout=5s`, `statement_timeout=15s`. Với N worker,
  ngân sách API là tối đa N×5 connection; tính thêm migration/monitor/test.
- [ ] Nhận SQLSTATE từ psycopg 3, không so chuỗi lỗi và không dùng cách nhận diện
  mã lỗi SQLite cho PostgreSQL. Bắt riêng `sqlalchemy.exc.TimeoutError` khi chờ pool.
- [ ] Giai đoạn đầu không tự retry command; rollback toàn lệnh khi lỗi cho phép
  xác định thất bại. Khi mất kết nối lúc commit, không tự replay hoặc khẳng định
  server chắc chắn đã rollback nếu kết quả commit chưa rõ.

| Loại lỗi | Phương án do thành viên 2 đề xuất | Trạng thái / việc cần làm |
| --- | --- | --- |
| SQLite BUSY; PostgreSQL `55P03`; pool timeout | `503 DATABASE_BUSY`, `Retry-After: 1` | Giữ mã lỗi hiện có; cần triển khai nhận diện PostgreSQL/pool và kiểm thử rollback. |
| Deadlock `40P01`; serialization failure `40001` | `503 DATABASE_BUSY`, `Retry-After: 1`; không tự retry | Cần kiểm thử rollback toàn command và phản hồi lỗi. |
| `57014` do statement timeout | `503 DATABASE_TIMEOUT`, không thêm `Retry-After` mặc định | Thành viên 3 chấp nhận đề nghị; thành viên 1 còn công bố contract. Chỉ kết luận statement timeout khi có đủ ngữ cảnh, không coi mọi `57014` là lock timeout. |
| Lỗi kết nối class 08 / lỗi driver do mất kết nối | `503 DATABASE_UNAVAILABLE`, không thêm `Retry-After` | Thành viên 3 chấp nhận đề nghị; thành viên 1 còn công bố contract, gồm trường hợp mất kết nối trong commit có kết quả chưa rõ. |
| Unique/FK/CHECK | Chỉ unique constraint đã biết được map sang lỗi nghiệp vụ | Không đổi mọi lỗi toàn vẹn thành DATABASE_BUSY; giữ lỗi kỹ thuật ngoài dự kiến được che thông tin nhạy cảm. |

**Đầu việc error contract của thành viên 1, theo mục 9.2 của thành viên 2 và 9.4
của thành viên 3:** công bố `DatabaseTimeoutError`, `DatabaseUnavailableError`
thuần Python trong `app/domain/errors.py`, đăng ký handler trong
`app/api/error_handlers.py`. Exception unavailable hỗ trợ `outcome_unknown=True`
khi mất kết nối trong commit; phần nhận diện SQLSTATE/SQLAlchemy ở infrastructure.

| Exception / tình huống | Mã HTTP và code | Message | Details / header |
| --- | --- | --- | --- |
| `DatabaseBusyError` | `503 DATABASE_BUSY` | `Hệ thống đang bận, vui lòng thử lại` | `details={}`, `Retry-After: 1`; không có nghĩa tự retry command. |
| `DatabaseTimeoutError` | `503 DATABASE_TIMEOUT` | `Thao tác dữ liệu vượt quá thời gian cho phép` | `details={}`, không thêm `Retry-After` mặc định. |
| `DatabaseUnavailableError`, mất kết nối trước commit | `503 DATABASE_UNAVAILABLE` | `Không thể kết nối cơ sở dữ liệu` | `details={}`, không thêm `Retry-After`. |
| `DatabaseUnavailableError(outcome_unknown=True)`, mất kết nối trong commit | `503 DATABASE_UNAVAILABLE` | `Chưa xác định được kết quả thao tác dữ liệu` | `details={"outcome": "unknown"}`, không thêm `Retry-After`; không tự replay hoặc khẳng định mutation chưa xảy ra. |

Đây là response contract do thành viên 2 đề nghị và thành viên 3 chấp nhận, chưa
phải các exception/handler mới đã được thành viên 1 công bố trong runtime.

- [ ] Kiểm thử đúng status/code/message/header, envelope hiện có
  `error={code, message, details, request_id}` và `X-Request-ID`; không lộ SQL,
  URL kết nối hoặc mật khẩu. Không thêm `outcome` vào response thành công/lỗi khác.
- [ ] Kiểm lỗi flush/timeout bằng connection khác để xác minh rollback; kiểm
  commit-unknown riêng, không dùng assertion dữ liệu chắc chắn chưa thay đổi.
- [ ] Không gán mọi query cancellation `57014` thành statement timeout. Khi chưa
  phân biệt được nguồn hủy, chỉ mô tả lỗi thực thi bị hủy và không ghi log/metrics
  như đã chứng minh nguyên nhân timeout. Cách phản hồi cuối cho trường hợp chưa rõ
  nguyên nhân cần được ghi rõ khi thành viên 1 công bố error contract.

Các giá trị timeout DB là cấu hình ban đầu để kiểm thử, chưa phải kết quả tối ưu
hoặc deadline HTTP tổng. Thành viên 3 đã chấp nhận response timeout upstream
**30 giây** làm mốc demo để đo Matching đồng bộ; chưa có bằng chứng cấu hình thực
hoặc bảo đảm mọi request kết thúc trong 30 giây. Không bật retry upstream cho POST.
Proxy trả 504/ngắt kết nối không chứng minh backend đã rollback; backend có thể
vẫn commit. Thành viên 2/3 cần đo cấu hình thực trước khi chốt thông số vận hành.

### 2.4. Môi trường đã chuẩn bị và bằng chứng còn cần bàn giao

Theo mục 3, 4 và 8 của báo cáo thành viên 2:

- [x] Đã có [script tạo nguồn SQLite](../../scripts/prepare_member2_phase1.py),
  manifest và [Compose PostgreSQL riêng](../../compose.phase1-member2.yaml).
  Dữ liệu là tổng hợp; không phải bản sao dữ liệu người dùng thật.
- [x] Script/kiểm thử fixture đã mô tả và kiểm bộ nguồn venues=1, users=3, sessions=1, participations=4,
  matching_requests=3; max ID tương ứng 10/40/50/90/120. Dùng để kiểm lịch sử,
  partial uniqueness, sequence và timestamp UTC có microsecond; xem
  [test fixture](../../tests/foundation/test_member2_phase1_fixture.py).
- [x] Đã có bằng chứng do thành viên 2 báo cáo: PostgreSQL 17.11 cục bộ healthy, timezone UTC, cổng loopback 55432,
  lock timeout 5s, statement timeout 15s trên môi trường Windows của thành viên 2.
  Chưa có schema nghiệp vụ/migration trong DB này. Dùng cấu hình cục bộ theo báo
  cáo; không trỏ API hiện tại vào đó trước khi adapter hỗ trợ PostgreSQL.

Các phần còn phải triển khai/kiểm chứng:

- [ ] Cung cấp cấu hình kết nối PostgreSQL, lệnh khởi động/migration và fixture
  trên DB test riêng đã migrate. A/B phải là connection vật lý khác nhau, kiểm
  bằng `pg_backend_pid()`; mỗi tác vụ có UoW riêng, không bọc cả test cạnh tranh
  trong một outer transaction.
- [ ] Chứng minh transaction B phải chờ khi A giữ cùng hàng session/user; sau khi
  A commit/rollback, B lấy khóa và đọc được trạng thái mới. Điều phối bằng
  Event/Barrier thay vì chỉ sleep; kiểm trạng thái cuối bằng connection C.
- [ ] Kiểm tra hàng không tồn tại, timeout, giải phóng khóa, rollback khi ghi lỗi
  và khi commit lỗi; xác minh dữ liệu bằng connection khác sau khi lệnh kết thúc.
- [ ] Cùng thành viên 1 kiểm tra chỗ cuối, cùng user ở hai kèo chồng lịch, duyệt
  đối đầu hủy/rút lượt và chờ khóa qua giờ bắt đầu.
- [ ] Cùng thành viên 3 xác minh matching writer dùng chính transaction của lệnh
  tạo kèo/duyệt, không có commit độc lập.
- [ ] Bổ sung bằng chứng REPEATABLE READ giữ snapshot giữa count/page, đọc mới
  sau khóa không stale, và deadline test đủ lớn so với lock timeout.
- [x] Đã ghi nhận thành viên 2 xử lý lỗi URL Windows bằng so đường dẫn DB đích
  (`engine.url.database`) và giữ kiểm timeout; test kiến trúc đọc UTF-8 tường minh.
  Mục 9.6 báo cáo **73 passed** cho foundation/architecture, không cần đặt
  `PYTHONUTF8`, cùng Ruff đạt. Đây là kết quả do thành viên 2 báo cáo, không phải
  lần chạy lại ở tài liệu này hoặc toàn bộ suite/API/PostgreSQL.

Adapter dùng driver psycopg 3, URL `postgresql+psycopg://...`; migration dùng
Alembic. Tách PRAGMA/`check_same_thread` theo dialect, chuyển timestamp PostgreSQL
sang TIMESTAMPTZ, xử lý Boolean phù hợp và thêm `postgresql_where` cho hai partial
unique index. Import theo thứ tự venues + users → sessions → participations +
matching_requests, đối chiếu manifest và đồng bộ sequence; thử insert không ID,
kể cả bảng rỗng (`setval(..., 1, false)`). Không dùng seed thay migration.

Migration phải giữ FK, lịch sử, ID/sequence, UTC timestamp và các unique predicate
cho participation/matching đang hoạt động để các invariant trong báo cáo vẫn đúng.
Chi tiết migration, Compose, CI và phục hồi nằm trong phần việc của thành viên 2
ở kế hoạch triển khai; tài liệu này tập trung vào các phụ thuộc của thành viên 1.

## 3. Thành viên 3 cần triển khai

### 3.1. Catalog và giao diện trạng thái sân

Thành viên 3 đã xác nhận phía mình giao diện dưới đây tại
`app/features/catalog/contracts.py` (mục 9.3); thành viên 2 không yêu cầu đổi
hợp đồng. Đường dẫn chưa phải file đã triển khai; thành viên 1 còn phải xác nhận
cách dùng trong Sessions trước khi tích hợp:

```python
class VenueStatusReader(Protocol):
    def is_active(self, venue_id: int) -> bool | None: ...
```

- [ ] `None`: không tìm thấy sân, để use case trả `404 VENUE_NOT_FOUND`.
- [ ] `False`: sân ngừng hoạt động, để use case trả `409 VENUE_INACTIVE`.
- [ ] `True`: được tiếp tục kiểm tra nghiệp vụ, không có nghĩa toàn yêu cầu đã hợp lệ.
- [ ] Adapter dùng transaction của bên gọi, không tự mở transaction hoặc commit.
- [ ] Đưa quyền sở hữu dữ liệu sân/trạng thái hoạt động về Catalog; cung cấp phép
  chiếu đọc gồm ID, tên, địa chỉ, quận và trạng thái cho Discovery/chi tiết kèo.
  Chữ ký projection sân đầy đủ còn mở; status reader không thay toàn bộ DTO sân.
- [ ] Giữ kiểm tra trạng thái tối thiểu và DTO hiển thị sân thành các hợp đồng rõ
  ràng; giữ tương thích bộ lọc, phân trang và phản hồi hiện có.

Thành viên 1 thay chỗ gọi `SessionRepository.venue_is_active()` bằng port được
inject. Thành viên 3 cung cấp hợp đồng/adapter Catalog và tích hợp phía Matching.

### 3.2. Matching writer dùng chung transaction

Giữ chữ ký port đã có trong `app/domain/ports.py`:

```python
class MatchingRequestWriter(Protocol):
    def close_overlapping(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> None: ...
```

- [ ] Cung cấp adapter do module Matching sở hữu, được lắp bằng UoW của bên gọi.
  Thành viên 2 đề nghị và thành viên 3 chấp nhận đường dẫn
  `app/features/matching/infrastructure/matching_request_writer.py`, giữ tên lớp
  `SqlAlchemyMatchingRequestWriter`; hiện adapter nằm tại
  `app/db/matching_request_writer.py`. Thành viên 1 còn phải xác nhận wiring.
- [ ] Thành viên 3 tạo package và chuyển adapter; composition root của thành
  viên 1 import/lắp implementation, Sessions service chỉ import port. Chỉ xóa
  adapter cũ sau khi mọi wiring/test đã chuyển; không duy trì hai implementation
  độc lập. Thành viên 2 hỗ trợ SQL/dialect.
- [x] Adapter hiện tại chỉ đóng yêu cầu `ACTIVE` của đúng user có khoảng thời gian chồng nhau theo
  `request.starts_at < ends_at and request.ends_at > starts_at`.
- [x] Adapter hiện tại ghi `CLOSED`, lý do `CONFIRMED` và thời điểm `now` được truyền vào.
- [x] Adapter hiện tại giữ nguyên yêu cầu không chồng lịch và lịch sử đã đóng; hai lịch nối tiếp
  không được coi là chồng nhau.
- [x] Adapter hiện tại không tự commit hoặc mở UoW mới; phát sinh lỗi truyền về use case.
- [x] Luồng rút lượt/hủy kèo hiện không mở lại matching đã đóng.

Các mục đã đánh dấu ở phần này là hành vi của
[writer hiện có trong app/db](../../app/db/matching_request_writer.py), được bao
phủ bởi [test writer](../../tests/foundation/test_matching_request_writer.py),
[test tích hợp](../../tests/integration/test_main.py) và test lỗi commit.
Việc chuyển writer sang module Matching và wiring theo đường dẫn mới vẫn chưa xong.

Thành viên 1 inject writer trực tiếp vào tạo kèo và duyệt. Tạo session/lượt host
hoặc chuyển lượt thành ACCEPTED và đóng matching phải cùng commit. Thành viên 2
hỗ trợ adapter DB; thành viên 3 chịu trách nhiệm hành vi và ranh giới module Matching.

**Bằng chứng cần có:** tạo kèo/duyệt thành công đóng đúng yêu cầu; lỗi giữa cập nhật
participation và đóng matching hoặc lỗi commit khiến cả hai thay đổi rollback.

Theo báo cáo thành viên 3, phải giữ riêng hai hành vi:
`close_active_for_user(..., REPLACED, ...)` đóng yêu cầu cũ khi gửi lại Matching;
`close_overlapping(..., CONFIRMED, ...)` chỉ đóng yêu cầu chồng lịch khi lịch chơi
được xác nhận. Không gộp thành một thao tác đóng mọi yêu cầu.

### 3.3. Tạo matching và Strategy

- [ ] Tách lệnh thay đổi matching khỏi đường đọc Discovery; use case sở hữu UoW.
- [ ] Dùng cùng cơ chế khóa user với tạo kèo/duyệt trước khi kiểm tra lịch ACCEPTED
  và thay yêu cầu ACTIVE: gọi `TransactionLocks.lock_user()`, sau đó đọc Clock,
  đọc lại hồ sơ/lịch rồi mới thay yêu cầu. Không đặt SQL khóa trong service và
  không lấy khóa session sau khi giữ khóa user.
- [ ] Thay yêu cầu cũ và tạo yêu cầu mới trong một transaction; thất bại giữ nguyên
  yêu cầu cũ: cần bổ sung bằng chứng kiểm thử lỗi thay thế Matching.
- [x] Tạo Matching hiện đóng bản cũ bằng REPLACED, thêm bản mới và chọn nhóm trong
  một UoW; gọi lặp thành công trả `201` với ID mới. Có test
  `test_matching_replace_group_create_approve_cancel` trong bộ tích hợp.
- [x] Đã có hàm thuần `find_group()` trong Discovery service, sắp `(created_at, id)`
  và chọn nhóm hợp lệ đầu tiên; `group_is_valid()` giữ chênh lệch rank tối đa 2.
- [ ] Tách Strategy first-valid thành hàm/lớp thuần; giữ thứ tự ứng viên
  `(created_at, id)` và chọn nhóm hợp lệ đầu tiên. Chuẩn bị ca không có ứng viên,
  thiếu ứng viên, không có nhóm hợp lệ, có nhiều nhóm hợp lệ và trường hợp đồng hạng.
  Phần còn thiếu là tách Strategy khỏi Discovery, lắp qua wiring và đủ bộ test
  tương thích; hàm hiện có chưa hoàn thành toàn bộ đầu việc này.
- [ ] Giữ quy tắc chênh lệch trình độ/ngân sách nhóm riêng với điều kiện trình độ
  do host đặt của Sessions.
- [x] Luồng hiện tại giữ ý nghĩa `suggestion=null`; không tự đổi sang tính ngoài transaction,
  bất đồng bộ hoặc cắt bớt ứng viên làm thay đổi kết quả khi chưa có quyết định mới.
  Không tìm được nhóm vẫn lưu yêu cầu; tạo yêu cầu và tính gợi ý vẫn cùng transaction.
- [ ] Cùng thành viên 1/2 chạy tình huống tạo matching đối đầu duyệt/tạo kèo;
  trạng thái cuối không có yêu cầu ACTIVE xung đột với lịch ACCEPTED.

### 3.4. Dùng hồ sơ Identity và bảo toàn dữ liệu đọc

**Thành viên 1 định nghĩa và công bố** `PlayerProfile` / `PlayerProfileReader`
trong `app/features/auth/contracts.py` và cung cấp triển khai reader Identity,
đúng đề nghị của thành viên 3. Thành viên 3 sử dụng hợp đồng, ánh xạ DTO và thay
chỗ Matching gọi `get_user()`; không phụ trách xây chức năng xác thực Identity.

DTO đề xuất có `id`, `display_name`, `skill_level: SkillLevel`, `gender: Gender`;
`get_by_id(user_id)` trả DTO hoặc `None`, không công bố email/password hash.

- [ ] Giữ `PlayerSummary.skill_level: int`; đổi `PlayerProfile.skill_level` bằng
  `skill_to_rank()` hiện có cho cả người gọi và ứng viên. Không tạo bảng chuyển
  đổi mới hoặc đổi thứ tự enum. Rank từ 1 đến 19 (NEWBIE=1, T_PLUS=19); giữ
  `max(ranks) - min(ranks) <= 2` cùng quy tắc giới tính/ngân sách hiện tại.
- [x] Sessions và Matching hiện kiểm giới tính chưa đầy đủ và trả
  PROFILE_INCOMPLETE; Sessions có test với UNSPECIFIED trong
  [test service](../../tests/sessions/test_service.py).
- [ ] Bộ đọc hồ sơ mới phải tiếp tục trả được UNSPECIFIED; chưa có
  `PlayerProfileReader`/`PlayerProfilesReader` để xác minh phần tích hợp mới.
- [ ] Thay phụ thuộc nội bộ vào Auth bằng reader/phép chiếu công khai được thống
  nhất. Với danh sách ứng viên, dùng phương án đọc theo lô do thành viên 2 đề nghị
  và thành viên 3 chấp nhận bên dưới; thành viên 1 còn công bố port/adapter Identity.
- [x] Read adapter hiện trả DTO/dữ liệu thuần; phản hồi hiển thị/gợi ý không chứa
  ORM object, email, hash hoặc ngân sách của người khác. Có test DTO/privacy trong
  [bộ tích hợp](../../tests/integration/test_main.py).
- [x] Tìm kiếm hiện công khai; chế độ `host_me=true` yêu cầu JWT và lấy ID từ
  principal, được kiểm trong bộ tích hợp và test ưu tiên xác thực.
- [x] Chi tiết kèo hiện chỉ trả `management` cho host, mỗi người chỉ có lượt của
  mình trong `my_participations`; có test
  `test_detail_exposes_only_the_viewers_participations_to_non_hosts`.
- [ ] Kiểm chứng lại DTO, tìm kiếm và privacy sau refactor sang Catalog/Matching,
  bộ đọc hồ sơ mới và PostgreSQL; kết quả SQLite hiện tại chưa thay thế bước này.
- [ ] Bổ sung kiểm thử kiến trúc cho chiều phụ thuộc, chu trình module và import
  trực tiếp adapter nội bộ của module khác.

### 3.5. Đọc hồ sơ ứng viên theo lô, thay cho lựa chọn projection còn mở trước đây

Thành viên 2 (mục 9.3) và thành viên 3 (mục 9.2) đã chọn phương án để thành viên 1
công bố tại `app/features/auth/contracts.py`:

```python
class PlayerProfilesReader(Protocol):
    def get_by_ids(self, user_ids: list[int]) -> dict[int, PlayerProfile]: ...
```

Identity sở hữu port/adapter và chỉ SELECT `id`, `display_name`, `skill_level`,
`gender`, trả `PlayerProfile` với enum hiện có. Thành viên 2 hỗ trợ persistence;
thành viên 3 tiêu thụ qua port, không import adapter nội bộ Auth.

- [ ] Đầu vào rỗng trả `{}` mà không query; loại ID trùng; ID thiếu không có key
  trong kết quả. Chia batch khi cần theo giới hạn tham số, không gọi từng user.
- [ ] Matching lấy request/candidate ID theo `(created_at, id)`, đọc profile theo
  lô trong cùng UoW rồi ghép theo thứ tự request ban đầu. Không dùng thứ tự dict
  hoặc SQL IN làm thứ tự chọn nhóm; cùng quy tắc `skill_to_rank()` cho caller và
  ứng viên, giữ `UNSPECIFIED`.
- [ ] Giữ caller thiếu trả UNAUTHORIZED. Với ứng viên thiếu hồ sơ, đối chiếu hành
  vi query cũ trước khi thay: không gây KeyError, không tạo hồ sơ giả hoặc thay
  ý nghĩa `suggestion`; bổ sung kiểm thử tương thích.
- [ ] Giữ total/pagination của Discovery và snapshot chung. Nếu đo kiểm cho thấy
  cần join trực tiếp xuyên module, Identity phải công bố projection bốn trường
  trước; đây là lựa chọn có điều kiện sau đo, không còn là điều kiện chặn ban đầu.

Thành viên 1 còn xác nhận/công bố hợp đồng batch. Các tiêu chí đầu vào rỗng/trùng,
ID thiếu, chia batch, rank và thứ tự ứng viên phải có bằng chứng khi triển khai;
hai báo cáo chưa tuyên bố các test này đã chạy đạt.

### 3.6. Ingress phối hợp với thành viên 2

- [ ] Thành viên 3 công bố cấu hình proxy thực với upstream response timeout demo
  ban đầu 30 giây, không retry upstream POST; đo Matching đồng bộ trước khi chốt.
- [ ] Phối hợp timeout/pool của thành viên 2 theo mục 2.3; không coi tổng timeout
  DB là deadline request hoặc suy luận 504 đồng nghĩa rollback.
- [ ] Giữ error envelope, `X-Request-ID`, chính sách không tự replay và phân biệt
  timeout/unavailable/commit-unknown theo contract thành viên 1 công bố; bảo toàn
  request telemetry không lộ SQL/thông tin kết nối.

## 4. Phần thành viên 1 sẽ thực hiện để tích hợp

| Phần việc | Phối hợp cần có |
| --- | --- |
| Định nghĩa port UoW/khóa ở tầng ứng dụng và gọi khóa đúng thứ tự | Thành viên 2 triển khai adapter; thành viên 3 dùng cùng khóa user cho matching. |
| Refactor Auth và tạo/hủy kèo để use case quản lý transaction | Thành viên 2 bảo đảm commit/rollback; dependency chỉ lắp các đối tượng. |
| Đưa băm/kiểm tra mật khẩu ra ngoài transaction tương ứng | Thành viên 2 giữ unique email và cung cấp adapter cho transaction ngắn. |
| Công bố `PlayerProfileReader` và `PlayerProfilesReader` tại `app/features/auth/contracts.py`, cung cấp adapter Identity | Thành viên 2 hỗ trợ persistence; thành viên 3 dùng reader theo lô và giữ thứ tự/rank. |
| Inject Catalog reader và Matching writer vào Sessions | Thành viên 3 cung cấp adapter theo hợp đồng; thành viên 2 kiểm chứng dùng chung transaction. |
| Kiểm tra quyền, điều kiện tham gia, trạng thái và dữ liệu sau khóa | Thành viên 2 cung cấp đọc mới sau khóa; thành viên 3 bảo toàn hợp đồng đọc. |
| Công bố `DatabaseTimeoutError`, `DatabaseUnavailableError(outcome_unknown=...)` và handler tại các file domain/API hiện có | Thành viên 2 map driver/SQLSTATE; thành viên 3 chấp nhận response contract mục 2.3 và không retry POST. |
| Xác nhận batch reader, Catalog và wiring writer ở đường dẫn mới | Thành viên 2/3 đã chọn batch reader/vị trí writer; thành viên 1 còn công bố hợp đồng và lắp implementation, projection sân đầy đủ vẫn cần chốt. |

Đã có bằng chứng mốc trong báo cáo: **160 ca kiểm thử đạt**, gồm 29 ca mới của
thành viên 1. Khi chuyển kiểm tra payload lên trước transaction, cập nhật các ca
đăng ký/tạo kèo từ ưu tiên `503` sang `422`; vẫn giữ ưu tiên `401` trên route yêu
cầu đăng nhập. Đây là kết quả đã ghi trong báo cáo, chưa phải bằng chứng cho các
adapter PostgreSQL hoặc chức năng mới liệt kê trong tài liệu này.

## 5. Checklist ghi nhận và xác nhận bàn giao

Các mục đã đánh dấu chỉ xác nhận đã nhận được nội dung trong báo cáo của từng
thành viên, không xác nhận runtime mới đã triển khai hoặc đồng thuận của cả nhóm.
Trạng thái triển khai thực tế nằm ở từng checklist mục 2–3; các mục SQLite đã có
được đánh dấu riêng và kèm nguồn đối chiếu.

- [x] Đã ghi nhận thành viên 2 chấp nhận UoW, chữ ký/ý nghĩa `TransactionLocks`
  và dùng cùng connection/transaction theo mục 2 của `phase1-member2.md`.
- [x] Đã ghi nhận lựa chọn snapshot đọc, cấu hình timeout, ánh xạ lỗi và thiết kế
  fixture connection độc lập từ thành viên 2.
- [x] Đã ghi nhận đề xuất Catalog, Identity DTO/rank, writer và phạm vi triển khai
  Matching/Discovery từ thành viên 3.
- [x] Đã ghi nhận xác nhận mới của thành viên 3 cho batch reader, đường dẫn Catalog,
  đường dẫn writer, UoW/khóa/snapshot/timeout và fixture ở mục 8–9 báo cáo của mình.
- [x] Đã ghi nhận response timeout ingress khởi điểm 30 giây và không retry POST
  được thành viên 3 chấp nhận; cấu hình thực và đo kiểm vẫn chưa hoàn thành.
- [x] Đã cập nhật bằng chứng kiểm thử thành viên 2 từ lỗi Windows trước đây sang
  **73 passed** cho suite chọn lọc tại mục 9.6; không coi là toàn suite đã đạt.
- [ ] Thành viên 1 xác nhận/công bố port UoW/khóa, bộ đọc hồ sơ và lựa chọn snapshot
  chung trước khi refactor file dùng chung.
- [ ] Thành viên 1 công bố error contract mục 2.3, gồm message/details/header và
  commit-unknown; thành viên 2 triển khai nhận diện lỗi và kiểm thử riêng từng trường hợp.
- [ ] Thành viên 1 xác nhận Catalog và wiring writer theo đường dẫn đã được thành
  viên 2/3 chọn; thành viên 3 chốt projection sân đầy đủ và chuyển adapter an toàn.
- [ ] Thành viên 1 công bố `PlayerProfilesReader.get_by_ids()` và adapter Identity;
  thành viên 3 kiểm chứng batch/ID thiếu/rank/thứ tự ứng viên theo mục 3.5.
- [ ] Thành viên 2 triển khai adapter khóa tại `app/db/transaction_locks.py`,
  migration/fixture và bằng chứng PostgreSQL; thành viên 3 triển khai Matching,
  Catalog, Discovery và bổ sung test mục 7 trong báo cáo của mình.
- [ ] Thành viên 2/3 bàn giao cấu hình ingress/backend thực, số đo timeout và ngân
  sách connection theo worker. Không coi lựa chọn timeout 30 giây là kết quả hiệu năng.
- [ ] Cả ba ghi lại quyết định cuối, đường dẫn triển khai, lệnh kiểm thử và commit
  bàn giao trước khi đánh dấu hoàn thành các mục hợp đồng còn mở ở Phase 1.
