# Phase 1 · Thành viên 3 · Yêu cầu, xác nhận hợp đồng và bàn giao

Ngày lập: **19/11/2026**.

Người phụ trách: **Member 3 — Catalog, Matching và Discovery**.

**Phạm vi hiện tại: chỉ Phase 1. Member 3 chưa bắt đầu Phase 2.** Tài liệu ghi
yêu cầu, khảo sát, xác nhận thiết kế và đầu ra bàn giao. Chữ ký/đường dẫn/tiêu chí
triển khai không phải bằng chứng đã tạo port, adapter, wiring, instrumentation
hoặc kiểm thử mới. Việc xây các thành phần đó thuộc kế hoạch giai đoạn sau.

**Trạng thái bàn giao:** Member 1 đã chính thức xác nhận
năm nhóm hợp đồng tại mục 1.2 của [báo cáo mới](phase1-member1.md), bản `e9c696e`;
Member 2 đã ghi nhận tại mục 11 của [báo cáo Member 2](phase1-member2.md).
Không còn chờ Member 1 xác nhận thiết kế. Mục 11–12 bên dưới là trạng thái hiện
hành, thay các câu “chờ xác nhận/công bố” trong lịch sử mục 9–10. Công bố code
thuộc giai đoạn sau. [Báo cáo tổng và corpus Matching](phase1.md).

Tài liệu này đề xuất các hợp đồng để ba thành viên triển khai độc lập và tích hợp
đúng trách nhiệm. Tham chiếu [bàn giao của Member 1](phase1-member1.md),
[báo cáo hiện trạng của Member 1](member-1-phase-1.vi.md) và
[kế hoạch triển khai](../Architecture_Phase2/kehoachtrienkhai-VN.md).

**Cập nhật xác nhận phía Member 3 ngày 19/11/2026**, đối chiếu
[Member 1, mục 5](phase1-member1.md#5-checklist-ghi-nhận-và-xác-nhận-bàn-giao) và
[Member 2, mục 2 và 9](phase1-member2.md), tại checkout commit `abfc916`.
Đối chiếu tiếp Member 1 tại `7c9a400` và Member 2 tại `7ceb404`; xác nhận bổ sung
phía Member 3 ở mục 10. Các kết luận mới thay trạng thái còn mở tương ứng ở mục 9.
Member 3 chấp nhận các lựa chọn ghi ở mục 9–10 bên dưới. Đây là lịch sử đối chiếu;
trạng thái xác nhận hiện hành đã được cập nhật ở đầu tài liệu và mục 11–12.

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
do Identity sở hữu tại đường dẫn đích `app/features/auth/contracts.py`.
Member 1 đã xác nhận thiết kế, công bố code thuộc giai đoạn sau; quy tắc chi tiết
tại mục 9.2 bên dưới. Join trực tiếp xuyên
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
- Projection đọc đầy đủ gồm ID, tên, địa chỉ, quận và trạng thái: Member 3 chấp nhận
  VenueSummary/VenueReader theo mục 10.1; giữ bộ lọc, phân trang và phản hồi hiện có.

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
  Member 1 đã xác nhận thiết kế wiring vào tạo phiên chơi và phê duyệt;
  việc chuyển/lắp adapter thuộc giai đoạn triển khai sau.
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
  Member 1 đã xác nhận hợp đồng lỗi; công bố code thuộc giai đoạn sau.

## 6. Yêu cầu bàn giao cho giai đoạn sau — không phải công việc Phase 1

Các mục dưới đây chỉ mô tả hành vi cần giữ khi triển khai theo kế hoạch chung.
Member 3 chưa thực hiện Phase 2; không dùng các mục này để đánh giá đã xong Phase 1.

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

## 7. Tiêu chí kiểm chứng khi triển khai sau — không phải checklist đóng Phase 1

Đây là tiêu chí nghiệm thu tương lai. Đầu ra còn thiếu để đóng Phase 1 là corpus
Matching có dữ liệu/kết quả cố định tại mục 12, không phải toàn bộ test dưới đây.

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
- [x] Member 1 xác nhận thiết kế profile/batch reader, Catalog và wiring writer
  theo mục 1.2 báo cáo mới; chưa coi code đã được công bố.
- [x] Member 1 xác nhận UoW/khóa và hợp đồng lỗi theo mục 1.2–1.3;
  adapter/fixture thuộc giai đoạn triển khai sau.
- [x] Member 3 chấp nhận VenueSummary/VenueReader, phạm vi join đọc và batch tối đa
  500 ID/câu theo Member 2 mục 10.3; chưa tạo port/adapter trong lượt cập nhật này.
- [x] Đối chiếu query cũ và chấp nhận loại candidate thiếu profile/UNSPECIFIED,
  giữ thứ tự và bộ lọc theo Member 2 mục 10.4.
- [x] Member 3 chấp nhận generic 500 cho 57014 chưa rõ nguồn hủy và quy tắc
  telemetry tại mục 10.3; Member 1 đã xác nhận response contract trong tài liệu.
- [x] Ghi quyết định, nguồn xác nhận, ngày và đầu ra tại [báo cáo tổng](phase1.md).

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

Port batch thiếu profile không được gây KeyError hay tạo hồ sơ giả. Đã đối chiếu
query hiện tại và chốt phía Member 3 cách loại candidate thiếu profile/UNSPECIFIED
tại mục 10.2; caller thiếu vẫn UNAUTHORIZED. Test tương thích còn mở.
Member 1 cần xác nhận/công bố port trước khi sửa file Identity dùng chung.

### 9.3. Catalog và writer

Member 3 xác nhận VenueStatusReader tại `app/features/catalog/contracts.py`,
giữ None/False/True và cùng transaction như mục 3. Projection sân đầy đủ đã được
Member 3 chấp nhận chữ ký ở mục 10.1; không coi status reader thay toàn bộ DTO sân.

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
bao gồm projection sân ở mục 10 và bổ sung test mục 7. Các checkbox kiểm thử vẫn để trống
cho đến khi có kết quả thực tế. Không sửa xác nhận thay người khác trong tài liệu của họ.

## 10. Xác nhận bổ sung theo Member 1 `7c9a400` và Member 2 `7ceb404`

Ngày đối chiếu: **19/11/2026**. Nguồn: Member 1 mục 2–5, Member 2 mục 10.
Member 1 đã ghi nhận xác nhận trước của Member 3; Member 2 xác nhận không cần
thảo luận lại UoW/locks/batch/writer/timeout đã cùng chấp nhận. Các mục dưới đây
chốt thêm lựa chọn phía Member 3, không xác nhận thay Member 1 hoặc công bố code runtime.

### 10.1. Chốt phía Member 3: projection sân đầy đủ

Chấp nhận đề nghị Member 2 mục 10.3; hợp đồng đích tại
`app/features/catalog/contracts.py`, do Member 3 triển khai:

```python
from dataclasses import dataclass
from typing import Protocol


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

- SELECT đúng năm cột, trả DTO trong transaction bên gọi, không commit/mở UoW riêng.
- Rỗng trả `{}` không query, loại ID trùng; ID thiếu không có key. Batch tối đa
  500 ID/câu là giới hạn kỹ thuật, không phải giới hạn tổng kết quả nghiệp vụ.
- Reader trả cả sân inactive để phục vụ lịch sử. Command tiếp tục dùng
  VenueStatusReader với quy tắc None/False/True, không thay bằng reader hiển thị.
- Discovery/detail ánh xạ sang DTO API hiện có, không đổi trường hoặc wrapper.
  Catalog không import contracts nội bộ Discovery/Sessions, không tạo model lưu
  trữ venue thứ hai.
- Discovery read adapter được đọc/join projection năm cột Catalog với dữ liệu
  Sessions theo hợp đồng đọc; SQL/ORM ở infrastructure, không import repository
  nội bộ Catalog hoặc ghi venue từ Discovery. Shared storage metadata hiện có
  chỉ dùng trong adapter.
- Bộ lọc/count/order phải áp trước limit/offset. Không lấy trang session rồi lọc
  sân bằng Python. Có thể batch enrich sau khi các điều kiện đã áp đúng tại DB.
- Giữ danh sách sân công khai chỉ active, lọc quận, order ID và count/page như
  `SqlAlchemyDiscoveryRepository.find_venues()` hiện tại đã đối chiếu.
- Sân inactive vẫn đọc được trong detail khi endpoint cho xem phiên chơi đó.
  Session tồn tại nhưng mất venue tham chiếu là lỗi kỹ thuật, không đổi thành
  SESSION_NOT_FOUND, không dựng sân giả hoặc âm thầm bỏ dữ liệu.

Member 1 còn xác nhận dùng projection cho detail/wiring. Port, adapter và test
active/inactive/missing, batch rỗng/trùng, pagination/snapshot chưa được tạo trong
lượt sửa tài liệu này.

### 10.2. Chốt phía Member 3: ứng viên thiếu profile

Đã đọc trực tiếp `SqlAlchemyMatchingRepository.candidates()` tại
`app/features/discovery/repository.py`: INNER JOIN UserModel, chỉ MALE/FEMALE,
lọc ACTIVE, sân/loại/giờ khớp, chưa bắt đầu, loại caller và lịch ACCEPTED chồng
giờ, order `(created_at, id)`. Chấp nhận kết luận Member 2 mục 10.4:

- Candidate thiếu profile: bỏ khỏi tập ứng viên như INNER JOIN cũ, không KeyError,
  hồ sơ giả, đóng hoặc xóa request vì thiếu hồ sơ.
- Candidate UNSPECIFIED: loại trước Strategy. Caller thiếu vẫn UNAUTHORIZED;
  caller UNSPECIFIED vẫn PROFILE_INCOMPLETE.
- Giữ các bộ lọc request/overlap và thứ tự tương đối còn lại; không cắt top-K để
  vừa batch và không biến lỗi truy vấn thành `suggestion = None`.
- Test trường hợp thiếu bằng fake reader hoặc dữ liệu legacy kiểm soát được;
  không tắt FK trong app.
- Batch trong command READ COMMITTED không có cam kết snapshot chung như
  `read()` REPEATABLE READ. Khóa caller bảo vệ lịch caller, không khóa toàn bộ
  hồ sơ ứng viên; gợi ý không giữ chỗ.

Đây là đối chiếu code và quyết định thiết kế; test first-valid, rank, thứ tự,
profile thiếu/UNSPECIFIED và rollback với batch reader mới vẫn cần triển khai.

### 10.3. Ghi nhận và chấp nhận nhánh 57014 chưa rõ nguồn hủy

Member 3 chấp nhận đề nghị Member 2 mục 10.2 để giữ telemetry và API nhất quán:

- SQLSTATE 57014 riêng lẻ, kể cả khi đã cấu hình statement_timeout, không đủ
  chứng minh nguyên nhân timeout. Chỉ dùng DatabaseTimeoutError khi có ngữ cảnh tin cậy.
- Chưa rõ nguyên nhân: chuyển generic handler, HTTP 500 INTERNAL_ERROR, message
  `Không thể xử lý yêu cầu`, details `{}`, giữ request_id/X-Request-ID,
  không Retry-After hoặc nội dung SQL/driver. Đã đối chiếu generic handler hiện tại
  tại `app/api/error_handlers.py`; phần adapter phân loại mới chưa triển khai.
- Telemetry dùng loại `query_cancelled_unknown`, ghi SQLSTATE và phase execute/commit,
  không ghi SQL/params/URL/password; không ghi nhận thành statement_timeout hay
  lock_timeout, không thêm user/session ID làm nhãn metrics.
- Rollback khi kết quả thất bại xác định. Mất kết nối trong commit vẫn thuộc
  DATABASE_UNAVAILABLE với outcome unknown; không gộp với cancellation hoặc tự replay.
- Không thêm DatabaseCancelledError vào domain. Member 1 còn ghi nhận/công bố
  contract; Member 2 triển khai nhận diện, Member 3 tích hợp log/metrics tương ứng.

### 10.4. Yêu cầu triển khai tương lai đã ghi trong lịch sử

Danh sách này thuộc giai đoạn 2–3, không phải phần Member 3 đã bắt đầu hoặc điều
kiện đóng Phase 1. Các quyết định thiết kế đã được Member 1 xác nhận; checkbox
bên dưới chỉ thể hiện chưa triển khai code/cấu hình, không còn chờ đồng thuận.

- [ ] Member 1 công bố port UoW/locks, profile/batch, error contract và wiring,
  bao gồm projection sân và generic cancellation.
- [ ] Member 3 hiện thực Catalog reader/projection, chuyển writer, tách Matching
  command/Strategy và test tương thích batch theo mục 7, 10.1–10.2.
- [ ] Member 2 bàn giao adapter/migration/import/fixture và bằng chứng PostgreSQL.
- [ ] Member 2/3 bàn giao cấu hình ingress/backend, đo timeout và connection budget.

Lượt cập nhật này chỉ sửa tài liệu Member 3; không chạy lại test runtime, không
đánh dấu các đầu việc triển khai đã xong, không thay kết quả 73 test đã được Member 2 báo cáo.

## 11. Xác nhận hiện hành sau cập nhật Member 1/2

Ngày đối chiếu: **19/11/2026**, Member 1 `e9c696e`, Member 2 `7475ef9`.
Member 3 ghi nhận xác nhận chính thức của Member 1 tại mục 1.2–1.3 và chấp nhận
đặc tả [telemetry Member 2](member2-telemetry-va-backup.md). Không sửa xác nhận
thay người khác hoặc yêu cầu xác nhận lại năm nhóm hợp đồng đã chốt.

### 11.1. Năm nhóm hợp đồng đã chốt ở Phase 1

- UoW/locks/snapshot: use case sở hữu transaction, reader/repository/locks/writer
  chung UoW, khóa session trước user, Clock và trạng thái đọc lại sau khóa;
  PostgreSQL write READ COMMITTED, read REPEATABLE READ READ ONLY.
- Identity: DTO bốn trường, reader đơn/batch, giữ enum và skill_to_rank(), thứ tự
  ứng viên, loại candidate thiếu/UNSPECIFIED; giữ lỗi caller hiện hành.
- Catalog: status reader, VenueSummary/VenueReader tại đường dẫn đã đề xuất,
  batch tối đa 500 ID/câu, đọc inactive cho lịch sử, filter/count/order trước
  pagination và phạm vi projection/join đọc đã chốt.
- Matching writer: giữ port/chữ ký, cùng transaction tạo kèo/duyệt, tách
  CONFIRMED/REPLACED; chấp nhận vị trí đích và composition root Member 1 phụ trách.
- Error contract: giữ envelope/request_id/X-Request-ID. BUSY có Retry-After: 1;
  timeout/unavailable không có Retry-After mặc định. Commit-unknown không tự
  replay; 57014 chưa rõ nguồn hủy dùng generic 500, không thêm exception domain.

Các message/details/status chính xác lấy theo bảng Member 1 mục 1.3 và đề nghị
Member 2 mục 9.2/10.2 đã được chấp nhận. Đây là hợp đồng tài liệu, không khẳng
định exception/handler/adapter mới đã được viết. Các câu còn ghi chờ xác nhận
trong mục lịch sử 9–10 không còn phản ánh trạng thái hiện tại.

### 11.2. Telemetry HTTP và Matching — xác nhận phía Member 3

Chấp nhận tên trường và đơn vị tại mục 1 đặc tả Member 2. Timestamp UTC;
duration dùng đồng hồ monotonic, đơn vị giây. Chưa đo được phải null/bỏ trường,
không giả số 0. Member 3 cung cấp:

- `request_id`: từ request state hiện có, trùng error envelope/X-Request-ID,
  không sinh ID thứ hai ở DB; chỉ log/trace, không làm nhãn metrics.
- `route_template`, `method`, `http_status`, `request_duration_seconds`,
  `error_code`: lớp HTTP đo từ lúc bắt đầu xử lý request đến hoàn tất response
  hoặc lỗi; bao query/Strategy/commit nếu có. Route dùng template đã match,
  chưa match là `unmatched`, không raw URL/query string. Error code đúng mã API
  thực, thành công null; ghi cả 401/422/503 và request chưa match.
- `matching_candidate_count`: số ứng viên sau lọc request/lịch/profile và ngay
  trước Strategy, không tính caller, không phải số tổ hợp hay kích thước nhóm.
- `matching_selection_duration_seconds`: bao đúng lời gọi Strategy đến khi trả
  về hoặc lỗi, không gồm query/profile batch/commit. Đo cả ca không có gợi ý;
  không chạy Matching hoặc lỗi trước điểm đo thì null/bỏ trường.

### 11.3. Telemetry DB — ghi nhận trách nhiệm Member 2

- `db_acquire_duration_seconds`: yêu cầu connection đến thành công/thất bại,
  có thể gồm tạo connection; không gọi là pool wait thuần. Chỉ thêm
  `db_pool_wait_seconds` nếu có hook đo đợi slot riêng, checkout event không đủ.
- `db_lock_acquire_duration_seconds`: bao primitive khóa tới kết quả/lỗi,
  lock_target session/user, outcome acquired/missing/timeout/error; có execute
  và round trip, không coi toàn bộ là lock wait thuần. Lấy mẫu PostgreSQL phải
  ghi khoảng lấy mẫu, không suy thời gian chính xác từ một mẫu hoặc thu SQL text.
- `db_transaction_duration_seconds`: trước BEGIN tới kết thúc commit/rollback
  và cleanup, không gồm acquire đã đo riêng. Mode read/write; outcome
  committed/rolled_back/failed/unknown. Read đóng bình thường bằng rollback
  không phải lỗi request; một UoW phát đúng một kết quả cuối.
- `db_error_kind`, `db_sqlstate`, `db_phase`: dùng tập hữu hạn và phase
  acquire/begin/execute/commit/rollback theo đặc tả Member 2; SQLSTATE thiếu null.
  57014 chưa rõ nguồn dùng query_cancelled_unknown. Cleanup không ghi đè nguyên
  nhân/kết quả commit-unknown. SQLSTATE chỉ log/trace đã lọc, không là nhãn metrics.

### 11.4. Context, nơi export và giới hạn dữ liệu

Member 3 xác nhận nguyên tắc bàn giao context/export sau để Member 2 nối hook
khi triển khai; đây là thiết kế Phase 1, chưa tạo instrumentation:

- HTTP đưa request_id/route/method vào context riêng mỗi request; dự kiến dùng
  ContextVar và bảo toàn khi sang sync/threadpool. Hook DB dùng cùng context,
  không global dùng chung hoặc sinh ID khác; reset khi kết thúc request.
- Structured request/error logs xuất stdout ứng dụng; hook DB và Matching gửi
  số đo tới collector metrics nội bộ dùng chung, exporter đặt mạng private theo
  topology Member 2. Không yêu cầu public endpoint export để hoàn thành Phase 1.
  Thư viện, bucket, địa chỉ scrape và cấu hình thực chọn ở giai đoạn triển khai.
- Histogram dùng tên/đơn vị tương ứng, công bố bucket khi triển khai. Nhãn chỉ
  thuộc tập hữu hạn route template/method/status/dialect/mode/outcome/lock target/
  error kind. Không dùng request/user/session/venue ID, PID, SQLSTATE tùy ý,
  URL, SQL/params, email, token hoặc credential làm nhãn.
- Không log hồ sơ, ngân sách người khác, password, URL kết nối hoặc dump.
  Telemetry lỗi không thay kết quả command, không phát query trên transaction
  đã lỗi hoặc giữ transaction chờ exporter I/O mạng.

Phía Member 2 đã chốt đặc tả gốc tại `7475ef9`, phía Member 3 xác nhận danh sách,
đơn vị và ranh giới đo trong mục 11 này. Tech Lead đã chốt phương án context và
export vào [đặc tả dùng chung](member2-telemetry-va-backup.md). Context xuyên HTTP/DB, ca lỗi, số đo acquisition,
nhãn hữu hạn và redaction là tiêu chí nghiệm thu tương lai, không phải test đã chạy.

## 12. Checklist hoàn thiện Phase 1 phía Member 3

- [x] Ghi nhận luồng Matching, response, thứ tự/tie-break, thay thế request,
  quyền riêng tư và phạm vi Catalog/Discovery.
- [x] Thống nhất profile/rank/batch, Catalog/projection, writer/UoW/khóa và lỗi;
  Member 1 đã xác nhận chính thức, không còn chờ code để chốt thiết kế.
- [x] Ghi nhận topology private, ingress timeout 30s để đo demo, không retry POST.
- [x] Xác nhận danh sách telemetry chung, bên cung cấp, đơn vị và ranh giới đo
  theo đặc tả Member 2; bổ sung nguyên tắc context/export phía Member 3.
- [x] Chuẩn bị đủ corpus Matching cố định với caller/request/candidate ID,
  created_at, rank, giới tính, policy, phí/ngân sách, sân/giờ/loại trận; ghi thứ
  tự đầu vào và nhóm/ID mong đợi hoặc null cho từng ca.
- [x] Corpus đủ ca: không ứng viên; thiếu người đơn/đôi; đủ người nhưng không
  nhóm hợp lệ (chỉ rõ rank/giới tính/ngân sách làm loại); nhiều nhóm hợp lệ;
  cùng created_at phân xử bằng ID. Đính kèm đường dẫn bằng chứng/test hiện có,
  tách kết quả mong đợi khỏi kết quả đã chạy.
- [x] Tech Lead ghi nhận context/export và đồng bộ đặc tả telemetry chung.
- [x] Ghi [bàn giao Phase 1](phase1.md).

[Corpus tích hợp](../../tests/integration/test_phase1_matching_corpus.py) bổ sung
tám ca qua API và SQLite tạm. [Báo cáo tổng](phase1.md) ghi dữ liệu, thứ tự, kết
quả kiểm thử và đích backup đã chọn. Refactor và kiểm chứng vận hành thuộc các
giai đoạn sau.
