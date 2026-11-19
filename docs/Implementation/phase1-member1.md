# Phase 1 · Thành viên 1 · Yêu cầu bàn giao cho thành viên 2 và 3

Ngày lập: **19/11/2026**.

Tài liệu này chuyển các đề xuất trong
[báo cáo rà soát của thành viên 1](../Architecture_Phase2/member-1-phase-1.vi.md)
thành đầu việc và tiêu chí bàn giao cho thành viên 2, thành viên 3.
Phân công bám theo [kế hoạch triển khai](../Architecture_Phase2/ke-hoach-trien-khai.md).
Các chữ ký mới dưới đây vẫn là **đề xuất chờ thống nhất**, chưa phải chức năng đã
triển khai hoặc quyết định đã được cả nhóm chấp thuận.

## 1. Cần chốt gì ở cuối Phase 1?

| Người phụ trách | Nội dung cần thống nhất với thành viên 1 | Kết quả bàn giao |
| --- | --- | --- |
| Thành viên 2 | UoW, API khóa session/user, phạm vi transaction, snapshot đọc, lỗi timeout và fixture PostgreSQL | Chữ ký phương thức, bảo đảm của adapter, cách chạy kiểm thử trên các connection độc lập. |
| Thành viên 3 | Catalog, dữ liệu hồ sơ dùng cho Matching/Discovery, matching writer và các phép join đọc được phép | Giao diện trạng thái sân, quy tắc ánh xạ hồ sơ, vị trí adapter writer và các ca kiểm thử tương thích. |

Phase 1 chốt hợp đồng và hành vi làm mốc. Phần xây adapter/refactor trên SQLite
và thử migration thuộc Phase 2; tích hợp khóa PostgreSQL thuộc Phase 3 theo kế hoạch.

## 2. Thành viên 2 cần triển khai

### 2.1. Adapter Unit of Work cho SQLite và PostgreSQL

Giữ giao diện ứng dụng `write()`, `read()`, `commit()` trong
[app/domain/ports.py](../../app/domain/ports.py), đồng thời triển khai các bảo đảm:

- [ ] Repository, bộ đọc hồ sơ, bộ khóa và matching writer của cùng một lệnh dùng
  chung DB session, connection và transaction.
- [ ] Use case chủ động commit đúng một lần. Adapter không tự commit khi thoát
  phạm vi và repository không commit riêng.
- [ ] Ngoại lệ hoặc thoát phạm vi mà chưa commit phải rollback toàn bộ thay đổi;
  lỗi commit phải được truyền ra để endpoint trả lỗi thay vì thành công.
- [ ] Không cho lồng UoW hoặc dùng DB session ngoài phạm vi transaction/sau commit.
- [ ] Giữ `BEGIN IMMEDIATE` cho ghi SQLite; triển khai cơ chế transaction phù hợp
  cho PostgreSQL, không gửi câu lệnh riêng của SQLite sang PostgreSQL.

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

Thống nhất với thành viên 1 port dự kiến trong `app/domain/ports.py`:

```python
class TransactionLocks(Protocol):
    def lock_session(self, session_id: int) -> bool: ...
    def lock_user(self, user_id: int) -> bool: ...
```

- [ ] `True` nghĩa là hàng tồn tại và đã được khóa đến khi transaction kết thúc;
  `False` nghĩa là không có hàng. Use case chọn mã lỗi nghiệp vụ/xác thực phù hợp.
- [ ] PostgreSQL khóa hàng trên chính connection/transaction của UoW đang hoạt
  động. Không mở UoW mới hoặc commit trong phương thức khóa.
- [ ] SQLite dùng khóa ghi đã lấy ở đầu UoW và kiểm tra hàng tồn tại; vẫn bảo toàn
  khả năng chạy đường SQLite để làm mốc so sánh.
- [ ] Cung cấp cách đọc lại dữ liệu sau khóa mà không bị bộ nhớ đệm ORM trả trạng
  thái đã đọc trước khi khóa.
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

- [ ] Chốt cơ chế giữ ảnh chụp dữ liệu nhất quán cho chi tiết kèo và các truy vấn
  đếm/phân trang gồm nhiều câu SQL: REPEATABLE READ cho phạm vi đọc cần thiết,
  phạm vi đọc snapshot riêng, hoặc một câu SQL tương đương.
- [ ] Ghi rõ bảo đảm của `read()`. READ COMMITTED trên PostgreSQL chỉ bảo đảm
  snapshot theo từng câu lệnh, không tự bảo đảm cùng snapshot cho toàn transaction.
- [ ] Giới hạn pool, thời gian chờ connection, khóa và câu lệnh; ánh xạ lỗi
  PostgreSQL theo loại lỗi tương ứng, không dùng mã lỗi SQLite để nhận diện.
- [ ] Kiểm chứng rollback và phản hồi lỗi khi hết thời gian chờ khóa. Hành vi
  SQLite làm mốc là `503 DATABASE_BUSY` kèm `Retry-After: 1`; cách ánh xạ PostgreSQL
  cần được chốt rõ trước tích hợp.
- [ ] Không tự động thử lại khi kết quả commit không xác định do mất kết nối.

### 2.4. Môi trường và bằng chứng bàn giao

- [ ] Cung cấp cấu hình kết nối PostgreSQL, lệnh khởi động/migration và fixture
  cho phép hai tác vụ dùng connection độc lập tới cùng DB kiểm thử.
- [ ] Chứng minh transaction B phải chờ khi A giữ cùng hàng session/user; sau khi
  A commit/rollback, B lấy khóa và đọc được trạng thái mới.
- [ ] Kiểm tra hàng không tồn tại, timeout, giải phóng khóa, rollback khi ghi lỗi
  và khi commit lỗi; xác minh dữ liệu bằng connection khác sau khi lệnh kết thúc.
- [ ] Cùng thành viên 1 kiểm tra chỗ cuối, cùng user ở hai kèo chồng lịch, duyệt
  đối đầu hủy/rút lượt và chờ khóa qua giờ bắt đầu.
- [ ] Cùng thành viên 3 xác minh matching writer dùng chính transaction của lệnh
  tạo kèo/duyệt, không có commit độc lập.

Migration phải giữ FK, lịch sử, ID/sequence, UTC timestamp và các unique predicate
cho participation/matching đang hoạt động để các invariant trong báo cáo vẫn đúng.
Chi tiết migration, Compose, CI và phục hồi nằm trong phần việc của thành viên 2
ở kế hoạch triển khai; tài liệu này tập trung vào các phụ thuộc của thành viên 1.

## 3. Thành viên 3 cần triển khai

### 3.1. Catalog và giao diện trạng thái sân

Thành viên 3 sở hữu Catalog và cung cấp giao diện dự kiến:

```python
class VenueStatusReader(Protocol):
    def is_active(self, venue_id: int) -> bool | None: ...
```

- [ ] `None`: không tìm thấy sân, để use case trả `404 VENUE_NOT_FOUND`.
- [ ] `False`: sân ngừng hoạt động, để use case trả `409 VENUE_INACTIVE`.
- [ ] `True`: được tiếp tục kiểm tra và tạo kèo.
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

### 3.3. Tạo matching và Strategy

- [ ] Tách lệnh thay đổi matching khỏi đường đọc Discovery; use case sở hữu UoW.
- [ ] Dùng cùng cơ chế khóa user với tạo kèo/duyệt trước khi kiểm tra lịch ACCEPTED
  và thay yêu cầu ACTIVE. Không lấy khóa session sau khi giữ khóa user.
- [ ] Thay yêu cầu cũ và tạo yêu cầu mới trong một transaction; thất bại giữ nguyên
  yêu cầu cũ. Gọi lặp thành công vẫn trả `201` với ID mới và đóng bản cũ bằng REPLACED.
- [ ] Tách Strategy first-valid thành hàm/lớp thuần; giữ thứ tự ứng viên và cách
  chọn nhóm như mốc hiện tại. Chuẩn bị ca không có ứng viên, thiếu ứng viên, không
  có nhóm hợp lệ và có nhiều nhóm hợp lệ.
- [ ] Giữ quy tắc chênh lệch trình độ/ngân sách nhóm riêng với điều kiện trình độ
  do host đặt của Sessions.
- [ ] Giữ ý nghĩa `suggestion=null`; không tự đổi sang tính ngoài transaction,
  bất đồng bộ hoặc cắt bớt ứng viên làm thay đổi kết quả khi chưa có quyết định mới.
- [ ] Cùng thành viên 1/2 chạy tình huống tạo matching đối đầu duyệt/tạo kèo;
  trạng thái cuối không có yêu cầu ACTIVE xung đột với lịch ACCEPTED.

### 3.4. Dùng hồ sơ Identity và bảo toàn dữ liệu đọc

**Thành viên 1 định nghĩa và công bố** `PlayerProfile` / `PlayerProfileReader`
trong Identity. Thành viên 3 thống nhất và sử dụng hợp đồng đó trong Matching và
các hợp đồng đọc liên quan; không phụ trách xây chức năng xác thực Identity.

DTO đề xuất có `id`, `display_name`, `skill_level: SkillLevel`, `gender: Gender`;
`get_by_id(user_id)` trả DTO hoặc `None`, không công bố email/password hash.

- [ ] Thống nhất cách đổi `SkillLevel` sang rank số cho `PlayerSummary` và Strategy,
  giữ thứ tự và quy tắc chênh lệch trình độ hiện tại.
- [ ] Giữ xử lý `UNSPECIFIED` cho dữ liệu cũ để lỗi PROFILE_INCOMPLETE còn hiệu lực.
- [ ] Thay phụ thuộc nội bộ vào Auth bằng reader/phép chiếu công khai được thống
  nhất. Với danh sách ứng viên, chốt phép join đọc được phép để tránh tra từng
  hồ sơ riêng lẻ và tránh kéo thông tin xác thực sang module khác.
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

Đã có bằng chứng mốc trong báo cáo: **160 ca kiểm thử đạt**, gồm 29 ca mới của
thành viên 1. Khi chuyển kiểm tra payload lên trước transaction, cập nhật các ca
đăng ký/tạo kèo từ ưu tiên `503` sang `422`; vẫn giữ ưu tiên `401` trên route yêu
cầu đăng nhập. Đây là kết quả đã ghi trong báo cáo, chưa phải bằng chứng cho các
adapter PostgreSQL hoặc chức năng mới liệt kê trong tài liệu này.

## 5. Checklist xác nhận bàn giao

- [ ] Thành viên 2 xác nhận chữ ký và ý nghĩa `TransactionLocks`, cách gắn với UoW.
- [ ] Thành viên 2 xác nhận cơ chế snapshot đọc, timeout và fixture connection độc lập.
- [ ] Thành viên 3 xác nhận `VenueStatusReader`, Matching writer và nơi đặt adapter.
- [ ] Thành viên 1 và 3 xác nhận DTO hồ sơ, chuyển đổi trình độ và phép join đọc được phép.
- [ ] Cả ba ghi lại quyết định cuối, đường dẫn triển khai, lệnh kiểm thử và commit
  bàn giao trước khi đánh dấu hoàn thành các mục hợp đồng còn mở ở Phase 1.
