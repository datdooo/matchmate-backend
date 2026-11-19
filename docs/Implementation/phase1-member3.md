# Phase 1 · Thành viên 3 · Đề xuất hợp đồng giao tiếp với thành viên 1 và 2

Ngày lập: **19/11/2026**.

Người phụ trách: **Member 3 — Catalog, Matching và Discovery**.

Tài liệu này đề xuất các hợp đồng để ba thành viên triển khai độc lập và tích hợp
đúng trách nhiệm. Tham chiếu [bàn giao của Member 1](phase1-member1.md),
[báo cáo hiện trạng của Member 1](member-1-phase-1.vi.md) và
[kế hoạch triển khai](../Architecture_Phase2/kehoachtrienkhai-VN.md).

**Cập nhật xác nhận phía Member 3 ngày 19/11/2026**, đối chiếu
[Member 1, mục 5](phase1-member1.md#5-checklist-ghi-nhận-và-xác-nhận-bàn-giao) và
[Member 2, mục 2 và 9](phase1-member2.md), tại checkout commit `abfc916`.
Member 3 chấp nhận các lựa chọn ghi ở mục 9 bên dưới. Member 1 hiện mới ghi nhận
đề nghị của các bên, chưa công bố toàn bộ port/error contract; không coi đây là
đồng thuận đầy đủ hoặc bằng chứng adapter/kiểm thử đã hoàn thành.

## 1. Hiện trạng đã đọc

- `app/domain/ports.py` có `Clock`, `UnitOfWork` và `MatchingRequestWriter`.
- `app/features/discovery/contracts.py` có `PlayerSummary` với
  `skill_level: int`, `VenueRecord`, các DTO tìm kiếm và `MatchingRepository`.
- `create_matching_request()` hiện nằm trong Discovery service: mở UoW ghi,
  kiểm tra hồ sơ/sân/thời gian/ngân sách/lịch ACCEPTED, đóng yêu cầu cũ bằng
  REPLACED, tạo yêu cầu mới, chọn nhóm và commit.
- `find_group()` sắp ứng viên theo `(created_at, id)` và chọn nhóm hợp lệ đầu tiên.
- `app/domain/enums.py` đã có `SkillLevel`, `skill_to_rank()` và
  `rank_to_skill()`. Rank chạy từ 1 đến 19 theo thứ tự khai báo enum.
- Adapter writer hiện có tại `app/db/matching_request_writer.py`; vị trí đích
  thuộc module Matching cần được thống nhất khi refactor.

## 2. Đề xuất với Member 1: hợp đồng hồ sơ Identity

### 2.1. Dữ liệu và interface

Đề nghị Member 1 định nghĩa, công bố hợp đồng tại
`app/features/auth/contracts.py` và cung cấp triển khai reader của Identity:

```python
from dataclasses import dataclass
from typing import Protocol

from app.domain.enums import Gender, SkillLevel


@dataclass(frozen=True)
class PlayerProfile:
    id: int
    display_name: str
    skill_level: SkillLevel
    gender: Gender


class PlayerProfileReader(Protocol):
    def get_by_id(self, user_id: int) -> PlayerProfile | None: ...
```

- Trả `None` khi tài khoản không tồn tại; use case Matching giữ lỗi UNAUTHORIZED.
- Không công bố email, password hash hoặc phương thức truy cập thông tin xác thực.
- Giữ khả năng trả giới tính UNSPECIFIED của dữ liệu cũ để Matching tiếp tục
  kiểm tra và trả PROFILE_INCOMPLETE.
- Reader dùng DB session/transaction của UoW bên gọi; không mở UoW hay commit riêng.
- Member 1 sở hữu hợp đồng và triển khai Identity; Member 3 sử dụng hợp đồng,
  ánh xạ dữ liệu và thay chỗ Matching gọi `get_user()`.

### 2.2. Chuyển trình độ sang rank

Member 3 đề xuất giữ `PlayerSummary.skill_level: int` trong luồng Matching và
chuyển từ `PlayerProfile.skill_level` bằng hàm hiện có:

```python
from app.domain.enums import skill_to_rank

rank = skill_to_rank(profile.skill_level)
```

Ví dụ: NEWBIE → 1, Y_MINUS → 2, Y → 3, Y_PLUS → 4, T_PLUS → 19.
Không tạo bảng chuyển đổi khác, không thay thứ tự enum trong phạm vi refactor.
Áp dụng cùng quy tắc cho người gửi yêu cầu và tất cả ứng viên. Giữ điều kiện
`max(ranks) - min(ranks) <= 2` và các quy tắc giới tính/ngân sách hiện tại.

### 2.3. Hồ sơ ứng viên và dữ liệu hiển thị

Member 3 chấp nhận phương án đọc theo lô ở mục 9.3 của Member 2:
`PlayerProfilesReader.get_by_ids(user_ids: list[int]) -> dict[int, PlayerProfile]`,
do Identity công bố tại `app/features/auth/contracts.py`. Member 1 còn cần xác
nhận/công bố port; quy tắc chi tiết tại mục 9.2 bên dưới. Join trực tiếp xuyên
module chỉ xem xét sau đo kiểm và khi Identity công bố projection tương ứng.

- Không gọi `get_by_id()` riêng cho từng ứng viên gây thêm một truy vấn mỗi người.
- Không import adapter nội bộ Auth từ module khác.
- Kết quả đọc trả DTO; không để ORM object hoặc thông tin xác thực thoát ra.
- Gợi ý không công bố ngân sách của người khác.

## 3. Member 3 đề xuất cung cấp: hợp đồng Catalog

```python
from typing import Protocol


class VenueStatusReader(Protocol):
    def is_active(self, venue_id: int) -> bool | None: ...
```

- `None`: use case trả VENUE_NOT_FOUND (404).
- `False`: use case trả VENUE_INACTIVE (409).
- `True`: tiếp tục kiểm tra nghiệp vụ; không có nghĩa toàn bộ yêu cầu đã hợp lệ.
- Adapter dùng cùng transaction của bên gọi, không tự commit.
- Catalog sở hữu dữ liệu sân và trạng thái hoạt động. Hợp đồng dự kiến đặt tại
  `app/features/catalog/contracts.py`; đây là đường dẫn đề xuất, chưa phải file
  đã được tạo.
- Member 1 inject reader vào Sessions thay cho kiểm tra sân qua repository nội bộ.
  Member 3 cung cấp reader và tích hợp phía Matching.
- Projection đọc đầy đủ gồm ID, tên, địa chỉ, quận và trạng thái được chốt riêng
  cho Discovery/chi tiết phiên chơi; giữ bộ lọc, phân trang và phản hồi hiện có.

## 4. Member 3 cung cấp: Matching writer

Giữ chữ ký đã có tại `app/domain/ports.py`:

```python
from datetime import datetime
from typing import Protocol


class MatchingRequestWriter(Protocol):
    def close_overlapping(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> None: ...
```

- Chỉ đóng yêu cầu ACTIVE của đúng user thỏa
  `request.starts_at < ends_at and request.ends_at > starts_at`.
- Chuyển thành CLOSED, lý do CONFIRMED, dùng `now` bên gọi truyền vào.
- Giữ yêu cầu không chồng giờ và các bản ghi lịch sử; hai lịch nối tiếp không trùng.
- Không tự mở transaction hoặc commit; lỗi truyền về use case để rollback.
- Không tự mở lại Matching khi hủy phiên chơi hoặc rút tham gia.
- Member 3 chấp nhận vị trí đích
  `app/features/matching/infrastructure/matching_request_writer.py`, lớp
  `SqlAlchemyMatchingRequestWriter`, theo mục 9.4 của Member 2.
  Member 1 còn cần xác nhận wiring vào tạo phiên chơi và phê duyệt.
  Member 2 hỗ trợ persistence và xác minh dùng chung transaction.

Phân biệt: `close_active_for_user(..., REPLACED, ...)` khi tạo lại Matching đóng
yêu cầu cũ đang hoạt động. `close_overlapping(..., CONFIRMED, ...)` khi xác nhận
lịch chỉ đóng yêu cầu chồng giờ. Không gộp hai hành vi này.

## 5. Đề nghị Member 2 xác nhận UoW, khóa và snapshot đọc

- Giữ `write()`, `read()`, `commit()`; use case mở giao dịch và commit một lần.
  Repository/reader/writer/locks dùng chung session, connection và transaction.
- Lỗi hoặc thoát mà chưa commit phải rollback. Lỗi commit không được trả thành công.
- Xác nhận port `TransactionLocks.lock_user(user_id) -> bool` theo đề xuất của
  Member 1: True khi tồn tại và đã khóa đến cuối transaction, False khi không tồn tại.
- Tạo Matching lấy khóa user gọi lệnh, sau đó đọc Clock, đọc lại hồ sơ/lịch và
  thay yêu cầu. Không lấy khóa session đã tồn tại sau khi giữ khóa user.
- SQLite giữ cơ chế ghi hiện tại; PostgreSQL dùng khóa hàng trong adapter.
  Member 3 gọi port, không đặt SQL khóa trong service.
- Member 3 chấp nhận `read()` PostgreSQL REPEATABLE READ, READ ONLY cho cả phạm vi,
  thiết lập trước SELECT đầu tiên; `write()` dùng READ COMMITTED và khóa hàng.
- Member 3 ghi nhận/chấp nhận timeout và thiết kế fixture connection độc lập của
  Member 2 để chuẩn bị tích hợp; chưa coi fixture/adapter đã được bàn giao chạy đạt.
  Các mã lỗi mới còn chờ Member 1 công bố, chi tiết tại mục 9.4.

## 6. Phạm vi Member 3 triển khai sau khi chốt

- Tách Matching command khỏi Discovery query, giữ việc tạo yêu cầu và tính gợi ý
  trong giao dịch hiện tại; không tự chuyển sang xử lý bất đồng bộ.
- Tách Strategy thuần, giữ thứ tự `(created_at, id)` và cách chọn first-valid.
- Không tìm được nhóm vẫn lưu yêu cầu, trả `suggestion = None`.
- Gửi lại thành công tạo ID mới và đóng yêu cầu cũ bằng REPLACED; lỗi phải giữ
  nguyên yêu cầu cũ.
- Giữ tìm kiếm công khai; `host_me=true` yêu cầu JWT và lấy user ID từ principal.
- Phối hợp bảo toàn quyền riêng tư: chỉ host có `management`, mỗi người chỉ thấy
  dữ liệu `my_participations` của mình.
- Bổ sung kiểm thử ranh giới module, vòng phụ thuộc và import adapter nội bộ.

## 7. Bằng chứng cần bổ sung

- [ ] Ánh xạ SkillLevel → rank giống nhau cho người gọi và ứng viên.
- [ ] Không có/thiếu ứng viên, không có nhóm hợp lệ, nhiều nhóm hợp lệ, đồng hạng.
- [ ] Tạo lại Matching thành công và rollback khi thay thế thất bại.
- [ ] Writer chỉ đóng ACTIVE chồng giờ; giữ lịch nối tiếp và lịch sử.
- [ ] Lỗi giữa xác nhận tham gia và đóng Matching khiến cả hai cùng rollback.
- [ ] Tạo Matching đối đầu phê duyệt/tạo phiên chơi dùng khóa user chung.
- [ ] Bộ lọc/phân trang, DTO, quyền riêng tư và ranh giới module giữ tương thích.

Các mục trên là tiêu chí cần kiểm chứng, chưa phải kết quả đã đạt. Kết quả 160 test
trong báo cáo Member 1 là bằng chứng do Member 1 ghi nhận; tài liệu này không
tuyên bố đã chạy lại hoặc đã kiểm chứng PostgreSQL.

## 8. Checklist xác nhận của các bên

- [x] Member 3 chấp nhận PlayerProfile/PlayerProfileReader, dùng skill_to_rank()
  và phương án PlayerProfilesReader đọc theo lô do Identity sở hữu.
- [x] Member 3 chốt phía mình VenueStatusReader tại app/features/catalog/contracts.py.
- [x] Member 3 chấp nhận đường dẫn writer mới và quy tắc chuyển adapter ở mục 9.3.
- [x] Ghi nhận Member 2 chấp nhận UoW/locks chung transaction và chọn snapshot,
  timeout, thiết kế fixture; Member 3 chấp nhận để tích hợp theo mục 9.
- [x] Member 3 chấp nhận response timeout ingress khởi điểm 30 giây để đo thử,
  không bật retry upstream POST; chưa xác nhận cấu hình thực hoặc hiệu năng.
- [ ] Member 1 xác nhận/công bố profile reader, batch reader, Catalog và wiring writer.
- [ ] Member 1 công bố port khóa và chốt mã lỗi mới; Member 2 triển khai adapter/fixture.
- [ ] Ghi lại quyết định cuối, người xác nhận, ngày xác nhận và commit bàn giao.

Chỉ đánh dấu sau khi có phản hồi thực tế. Các điểm chưa chốt cần được ghi rõ
trước khi refactor file dùng chung.

## 9. Xác nhận chi tiết phía Member 3 sau cập nhật của Member 1/2

### 9.1. UoW, khóa và snapshot

Chấp nhận các bảo đảm ở mục 2 và 9.1 của Member 2: mỗi command có UoW riêng;
reader/repository/locks/writer nhận session provider của cùng UoW; use case commit
một lần, không auto-commit hoặc UoW lồng, không dùng session sau commit.

Port khóa do Member 1 công bố tại `app/domain/ports.py`; adapter Member 2 dự kiến
đặt tại `app/db/transaction_locks.py`. Matching chỉ gọi `lock_user(actor_user_id)`
trong UoW ghi. True nghĩa là hàng tồn tại và được khóa, False nghĩa là không tồn
tại để use case giữ lỗi xác thực hiện hành. Sau khóa mới đọc Clock và truy vấn
lại hồ sơ/lịch, tránh dữ liệu ORM cache trước khóa. Không lấy khóa session đã
tồn tại sau khóa user. Việc kiểm tra lịch ACCEPTED, đóng yêu cầu cũ, tạo yêu cầu
mới và chọn nhóm vẫn trong cùng transaction.

Discovery chấp nhận REPEATABLE READ, READ ONLY cho `read()` để count/page dùng cùng
snapshot. Snapshot được thiết lập ở truy vấn đầu tiên, không bảo đảm mới nhất lúc
trả response. Không gọi FOR UPDATE trong read-only; command dùng `write()`
READ COMMITTED. Member 1 còn công bố hợp đồng chung, Member 2 triển khai/kiểm chứng.

### 9.2. Profile và đọc theo lô

Chấp nhận DTO bốn trường tại mục 2, giữ enum SkillLevel/Gender và UNSPECIFIED;
chuyển sang rank bằng skill_to_rank() cho cả caller và ứng viên.

```python
class PlayerProfilesReader(Protocol):
    def get_by_ids(self, user_ids: list[int]) -> dict[int, PlayerProfile]: ...
```

Identity sở hữu port/adapter. Loại ID trùng, đầu vào rỗng trả `{}` không truy vấn;
ID không tồn tại không có key. Chỉ SELECT bốn trường công khai, trả DTO trong
cùng UoW; chia batch khi cần để giới hạn tham số, không query từng user.
Matching giữ thứ tự request `(created_at, id)` khi ghép profile; không dùng thứ tự
dict hoặc SQL IN để chọn nhóm. Không thay total/pagination của Discovery.

Port batch thiếu profile không được gây KeyError hay tạo hồ sơ giả. Trước khi
thay query hiện tại cần đối chiếu cách query cũ xử lý user không tồn tại để giữ
hành vi tương thích; caller thiếu vẫn UNAUTHORIZED. Test tương thích còn mở.
Member 1 cần xác nhận/công bố port trước khi sửa file Identity dùng chung.

### 9.3. Catalog và writer

Member 3 xác nhận VenueStatusReader tại `app/features/catalog/contracts.py`,
giữ None/False/True và cùng transaction như mục 3. Projection sân đầy đủ còn cần
chốt chữ ký cụ thể cho Discovery/detail; không coi status reader thay toàn bộ DTO sân.

Chấp nhận chuyển writer về
`app/features/matching/infrastructure/matching_request_writer.py`. Giữ tên lớp,
port ở `app/domain/ports.py` và hành vi CONFIRMED/REPLACED riêng biệt. Member 3
tạo package/chuyển adapter; Member 1 lắp implementation ở composition root,
Sessions service chỉ import port. Member 2 hỗ trợ SQL/dialect. Chỉ xóa adapter cũ
sau khi mọi wiring/test đã chuyển; không duy trì hai implementation độc lập.

### 9.4. Timeout, lỗi và ingress

Chấp nhận thông số khởi điểm Member 2 để kiểm thử: pool_size=5, max_overflow=0,
pool_timeout=5s, connect_timeout=5s, lock_timeout=5s, statement_timeout=15s.
Đây chưa phải thông số tối ưu đã đo; tổng connection budget phải tính theo worker.

Ghi nhận ánh xạ BUSY/55P03, pool timeout, 40P01/40001 về 503 DATABASE_BUSY với
Retry-After: 1, rollback khi kết quả thất bại đã rõ, không tự retry command.
Member 3 chấp nhận đề nghị mục 9.2 của Member 2 về DATABASE_TIMEOUT và
DATABASE_UNAVAILABLE để tích hợp; **Member 1 vẫn phải công bố exception/handler**.
Không coi mọi 57014 là lock timeout; chỉ nhận diện statement timeout khi đủ ngữ cảnh.
Giữ envelope error và X-Request-ID, không lộ SQL hoặc thông tin kết nối.

Mất kết nối trong commit có thể không rõ kết quả: đề nghị trả
`details={"outcome": "unknown"}` theo Member 2, không tuyên bố chắc chắn rollback,
không thêm Retry-After cho timeout/unavailable và không tự replay command.

Member 3 chấp nhận upstream response timeout **30 giây** làm mốc cấu hình demo
để đo thử Matching đồng bộ, chưa xác nhận mọi request sẽ hoàn tất trong 30 giây.
Không bật retry upstream cho POST. Timeout DB giới hạn từng thao tác, không phải
deadline toàn request; proxy trả 504/ngắt kết nối không chứng minh backend rollback.
Cần công bố cấu hình proxy thực và đo Matching trước khi chốt thông số vận hành.

### 9.5. Trạng thái kiểm chứng và việc còn mở

Member 2 báo cáo suite foundation/architecture chọn lọc đạt 73 test và Ruff đạt
sau sửa khả năng chạy Windows (mục 9.6); đây là kết quả do Member 2 ghi nhận,
không phải lần chạy lại của Member 3 hoặc bằng chứng PostgreSQL hoàn thành.

Tiếp theo: Member 1 xác nhận/công bố port/error handler và wiring; Member 2 bàn
giao adapter/migration/fixture; Member 3 triển khai các hợp đồng đã chấp nhận,
chốt projection sân và bổ sung test mục 7. Các checkbox kiểm thử vẫn để trống
cho đến khi có kết quả thực tế. Không sửa xác nhận thay người khác trong tài liệu của họ.
