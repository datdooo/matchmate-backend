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

## 1. Cần chốt gì ở cuối Phase 1?

| Người phụ trách | Nội dung cần thống nhất với thành viên 1 | Kết quả bàn giao |
| --- | --- | --- |
| Thành viên 2 | UoW, API khóa session/user, phạm vi transaction, snapshot đọc, lỗi timeout và fixture PostgreSQL | Chữ ký phương thức, bảo đảm của adapter, cách chạy kiểm thử trên các connection độc lập. |
| Thành viên 3 | Catalog, dữ liệu hồ sơ dùng cho Matching/Discovery, matching writer và các phép join đọc được phép | Giao diện trạng thái sân, quy tắc ánh xạ hồ sơ, vị trí adapter writer và các ca kiểm thử tương thích. |

Phase 1 chốt hợp đồng và hành vi làm mốc. Phần xây adapter/refactor trên SQLite
và thử migration thuộc Phase 2; tích hợp khóa PostgreSQL thuộc Phase 3 theo kế hoạch.

### 1.1. Thông tin mới từ hai báo cáo

| Nội dung | Trạng thái được ghi nhận | Việc tiếp theo |
| --- | --- | --- |
| UoW và `TransactionLocks` | Thành viên 2 chấp nhận giao diện, cách dùng chung transaction và thứ tự khóa; thành viên 3 đề xuất dùng cùng `lock_user()` | Thành viên 1 công bố port; thành viên 2 xây adapter; thành viên 3 tích hợp khóa vào Matching. |
| Snapshot PostgreSQL | Thành viên 2 chọn `read()` là REPEATABLE READ, READ ONLY; `write()` là READ COMMITTED | Ghi lựa chọn này vào hợp đồng chung và kiểm chứng bằng fixture PostgreSQL. |
| PostgreSQL và dữ liệu nguồn | Thành viên 2 báo cáo PostgreSQL cục bộ healthy, có nguồn SQLite tổng hợp và manifest | Còn adapter, migration/import và kiểm thử cạnh tranh; chưa coi là tích hợp ứng dụng thành công. |
| Catalog, hồ sơ và Matching writer | Thành viên 3 đã nêu chữ ký, vị trí Catalog dự kiến và quy tắc chuyển rank | Còn xác nhận từ thành viên 1, hợp đồng projection ứng viên và vị trí adapter writer cụ thể. |
| Kiểm thử của thành viên 2 | Báo cáo ghi 2 ca fixture đạt; lượt kiểm nền tảng + kiến trúc có 72 đạt, 1 thất bại trên Windows | Xử lý chênh lệch biểu diễn URL trong test, chạy lại và ghi kết quả trước khi dùng làm điều kiện tích hợp. |

Đây là tổng hợp bằng chứng được ghi trong hai tài liệu, không phải kết quả chạy
lại trên môi trường hiện tại. Checklist triển khai bên dưới vẫn để mở cho các
phần runtime chưa có bằng chứng hoàn thành.

## 2. Thành viên 2 cần triển khai

### 2.1. Adapter Unit of Work cho SQLite và PostgreSQL

Giữ giao diện ứng dụng `write()`, `read()`, `commit()` trong
[app/domain/ports.py](../../app/domain/ports.py), đồng thời triển khai các bảo đảm:

Thành viên 2 đã chấp nhận hợp đồng này trong mục 2 của báo cáo. Cách lắp adapter
được đề nghị là nhận session provider `lambda: uow.session`, dùng chung cho
repository, profile/Catalog reader, locks và Matching writer.

- [ ] Repository, bộ đọc hồ sơ, bộ khóa và matching writer của cùng một lệnh dùng
  chung DB session, connection và transaction.
- [ ] Use case chủ động commit đúng một lần. Adapter không tự commit khi thoát
  phạm vi và repository không commit riêng.
- [ ] Ngoại lệ hoặc thoát phạm vi mà chưa commit phải rollback toàn bộ thay đổi;
  lỗi commit phải được truyền ra để endpoint trả lỗi thay vì thành công.
- [ ] Không cho lồng UoW hoặc dùng DB session ngoài phạm vi transaction/sau commit.
- [ ] Giữ `BEGIN IMMEDIATE` cho ghi SQLite; triển khai cơ chế transaction phù hợp
  cho PostgreSQL: `write()` dùng READ COMMITTED, không gửi câu lệnh riêng của
  SQLite sang PostgreSQL.

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

Triển khai theo lựa chọn đã được thành viên 2 ghi nhận:

- [ ] `read()` PostgreSQL dùng **REPEATABLE READ, READ ONLY**, thiết lập trước
  SELECT đầu tiên; SQLite giữ BEGIN tường minh. Count/page và các phần chi tiết
  trong cùng phạm vi phải nhìn cùng snapshot.
- [ ] Ghi rõ snapshot PostgreSQL bắt đầu từ truy vấn đầu tiên, không bảo đảm dữ
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
| `57014` do statement timeout | `503 DATABASE_TIMEOUT` | Mã mới, chờ thành viên 1 xác nhận error contract; không coi mọi `57014` là lock timeout. |
| Lỗi kết nối class 08 / lỗi driver do mất kết nối | `503 DATABASE_UNAVAILABLE` | Mã mới, chờ thành viên 1 xác nhận; phân biệt trường hợp kết quả commit chưa rõ. |
| Unique/FK/CHECK | Chỉ unique constraint đã biết được map sang lỗi nghiệp vụ | Không đổi mọi lỗi toàn vẹn thành DATABASE_BUSY; giữ lỗi kỹ thuật ngoài dự kiến được che thông tin nhạy cảm. |

Các giá trị trên là cấu hình ban đầu để kiểm thử, chưa phải kết quả tối ưu hoặc
deadline HTTP tổng. Thành viên 2 và 3 còn phải phối hợp timeout backend/proxy khi
tích hợp ingress ở Phase 3.

### 2.4. Môi trường đã chuẩn bị và bằng chứng còn cần bàn giao

Theo mục 3, 4 và 8 của báo cáo thành viên 2:

- Đã có [script tạo nguồn SQLite](../../scripts/prepare_member2_phase1.py),
  manifest và [Compose PostgreSQL riêng](../../compose.phase1-member2.yaml).
  Dữ liệu là tổng hợp; không phải bản sao dữ liệu người dùng thật.
- Bộ nguồn có venues=1, users=3, sessions=1, participations=4,
  matching_requests=3; max ID tương ứng 10/40/50/90/120. Dùng để kiểm lịch sử,
  partial uniqueness, sequence và timestamp UTC có microsecond.
- Báo cáo ghi PostgreSQL 17.11 cục bộ healthy, timezone UTC, cổng loopback 55432,
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
- [ ] Xử lý lỗi test nền tảng `test_runtime_engine_uses_explicit_test_database`
  liên quan percent-encoding/backslash URL Windows, rồi chạy lại với UTF-8 và
  ghi rõ kết quả. Báo cáo hiện có 72 đạt, 1 thất bại; không coi toàn suite đã xanh.

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

Thành viên 3 đã đề xuất giao diện dưới đây tại
`app/features/catalog/contracts.py`; đường dẫn này chưa phải file đã triển khai.
Thành viên 1 còn phải ghi nhận xác nhận trước khi sửa các chỗ gọi chung:

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
  Vị trí đích cụ thể còn chờ chốt cấu trúc module; hiện adapter nằm tại
  `app/db/matching_request_writer.py`.
- [ ] Chỉ đóng yêu cầu `ACTIVE` của đúng user có khoảng thời gian chồng nhau theo
  `request.starts_at < ends_at and request.ends_at > starts_at`.
- [ ] Ghi `CLOSED`, lý do `CONFIRMED` và thời điểm `now` được truyền vào.
- [ ] Giữ nguyên yêu cầu không chồng lịch và lịch sử đã đóng; hai lịch nối tiếp
  không được coi là chồng nhau.
- [ ] Không tự commit hoặc mở UoW mới; phát sinh lỗi phải truyền về use case.
- [ ] Không mở lại matching khi người chơi rút lượt hoặc host hủy kèo.

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
  yêu cầu cũ. Gọi lặp thành công vẫn trả `201` với ID mới và đóng bản cũ bằng REPLACED.
- [ ] Tách Strategy first-valid thành hàm/lớp thuần; giữ thứ tự ứng viên
  `(created_at, id)` và chọn nhóm hợp lệ đầu tiên. Chuẩn bị ca không có ứng viên,
  thiếu ứng viên, không có nhóm hợp lệ, có nhiều nhóm hợp lệ và trường hợp đồng hạng.
- [ ] Giữ quy tắc chênh lệch trình độ/ngân sách nhóm riêng với điều kiện trình độ
  do host đặt của Sessions.
- [ ] Giữ ý nghĩa `suggestion=null`; không tự đổi sang tính ngoài transaction,
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
- [ ] Giữ xử lý `UNSPECIFIED` cho dữ liệu cũ để lỗi PROFILE_INCOMPLETE còn hiệu lực.
- [ ] Thay phụ thuộc nội bộ vào Auth bằng reader/phép chiếu công khai được thống
  nhất. Với danh sách ứng viên, chốt phép join đọc được phép để tránh tra từng
  hồ sơ riêng lẻ và tránh kéo thông tin xác thực sang module khác. Projection do
  Identity sở hữu; chữ ký, vị trí triển khai và cách đọc theo lô/join vẫn còn mở.
- [ ] Trả DTO từ read adapter; không để ORM object, email, hash hoặc ngân sách của
  người khác lọt vào kết quả hiển thị/gợi ý.
- [ ] Giữ tìm kiếm công khai; chế độ `host_me=true` yêu cầu JWT và lấy ID từ principal.
- [ ] Phối hợp với thành viên 1 bảo toàn chi tiết kèo: chỉ host có `management`,
  mỗi người chỉ có lượt của mình trong `my_participations`.
- [ ] Bổ sung kiểm thử kiến trúc cho chiều phụ thuộc, chu trình module và import
  trực tiếp adapter nội bộ của module khác.

## 4. Phần thành viên 1 sẽ thực hiện để tích hợp

| Phần việc | Phối hợp cần có |
| --- | --- |
| Định nghĩa port UoW/khóa ở tầng ứng dụng và gọi khóa đúng thứ tự | Thành viên 2 triển khai adapter; thành viên 3 dùng cùng khóa user cho matching. |
| Refactor Auth và tạo/hủy kèo để use case quản lý transaction | Thành viên 2 bảo đảm commit/rollback; dependency chỉ lắp các đối tượng. |
| Đưa băm/kiểm tra mật khẩu ra ngoài transaction tương ứng | Thành viên 2 giữ unique email và cung cấp adapter cho transaction ngắn. |
| Công bố bộ đọc hồ sơ Identity | Thành viên 2 hỗ trợ persistence; thành viên 3 tiêu thụ hợp đồng/ánh xạ rank. |
| Inject Catalog reader và Matching writer vào Sessions | Thành viên 3 cung cấp adapter theo hợp đồng; thành viên 2 kiểm chứng dùng chung transaction. |
| Kiểm tra quyền, điều kiện tham gia, trạng thái và dữ liệu sau khóa | Thành viên 2 cung cấp đọc mới sau khóa; thành viên 3 bảo toàn hợp đồng đọc. |
| Xác nhận mã lỗi hạ tầng mới và khai báo lỗi API | Thành viên 2 đề xuất DATABASE_TIMEOUT/DATABASE_UNAVAILABLE; thành viên 1 cần chốt trước khi adapter và error handler tích hợp. |
| Chốt projection hồ sơ ứng viên và vị trí hợp đồng dùng chung | Thành viên 3 đưa yêu cầu đọc theo lô/join; thành viên 1 giữ quyền sở hữu dữ liệu Identity. |

Đã có bằng chứng mốc trong báo cáo: **160 ca kiểm thử đạt**, gồm 29 ca mới của
thành viên 1. Khi chuyển kiểm tra payload lên trước transaction, cập nhật các ca
đăng ký/tạo kèo từ ưu tiên `503` sang `422`; vẫn giữ ưu tiên `401` trên route yêu
cầu đăng nhập. Đây là kết quả đã ghi trong báo cáo, chưa phải bằng chứng cho các
adapter PostgreSQL hoặc chức năng mới liệt kê trong tài liệu này.

## 5. Checklist ghi nhận và xác nhận bàn giao

Các mục đã đánh dấu chỉ xác nhận đã nhận được nội dung trong báo cáo của từng
thành viên, không xác nhận runtime đã triển khai hoặc đồng thuận của cả nhóm.

- [x] Đã ghi nhận thành viên 2 chấp nhận UoW, chữ ký/ý nghĩa `TransactionLocks`
  và dùng cùng connection/transaction theo mục 2 của `phase1-member2.md`.
- [x] Đã ghi nhận lựa chọn snapshot đọc, cấu hình timeout, ánh xạ lỗi và thiết kế
  fixture connection độc lập từ thành viên 2.
- [x] Đã ghi nhận đề xuất Catalog, Identity DTO/rank, writer và phạm vi triển khai
  Matching/Discovery từ thành viên 3.
- [ ] Thành viên 1 xác nhận/công bố port UoW/khóa, bộ đọc hồ sơ và lựa chọn snapshot
  chung trước khi refactor file dùng chung.
- [ ] Thành viên 1 xác nhận error contract cho `DATABASE_TIMEOUT` và
  `DATABASE_UNAVAILABLE`; thành viên 2 triển khai nhận diện lỗi và kiểm thử.
- [ ] Thành viên 1 và 3 chốt `VenueStatusReader` tại đường dẫn Catalog dự kiến,
  vị trí adapter writer và cách inject vào Sessions.
- [ ] Thành viên 1 và 3 xác nhận `skill_to_rank()` và chốt chữ ký/vị trí projection
  hồ sơ ứng viên; thành viên 2 hỗ trợ adapter trên cùng transaction.
- [ ] Thành viên 3 ghi nhận lựa chọn REPEATABLE READ, READ ONLY cùng timeout và
  fixture do thành viên 2 đề xuất; phối hợp deadline ingress/backend khi tích hợp.
- [ ] Thành viên 2 bàn giao adapter/migration/fixture và kết quả kiểm thử sau khi
  xử lý lỗi kiểm thử nền tảng đã báo cáo; thành viên 3 bổ sung bằng chứng mục 7
  trong báo cáo của mình. Chưa có bằng chứng hai phần runtime này đã hoàn thành.
- [ ] Cả ba ghi lại quyết định cuối, đường dẫn triển khai, lệnh kiểm thử và commit
  bàn giao trước khi đánh dấu hoàn thành các mục hợp đồng còn mở ở Phase 1.
