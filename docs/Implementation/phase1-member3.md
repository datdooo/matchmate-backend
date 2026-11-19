# Phase 1 · Thành viên 3 · Đề xuất hợp đồng giao tiếp với thành viên 1 và 2

Ngày lập: **19/11/2026**.

Người phụ trách: **Member 3 — Catalog, Matching và Discovery**.

Tài liệu này đề xuất các hợp đồng để ba thành viên triển khai độc lập và tích hợp
đúng trách nhiệm. Tham chiếu [bàn giao của Member 1](phase1-member1.md),
[báo cáo hiện trạng của Member 1](member-1-phase-1.vi.md) và
[kế hoạch triển khai](../Architecture_Phase2/kehoachtrienkhai-VN.md).

**Trạng thái: đề xuất chờ xác nhận.** Chưa có xác nhận của Member 1/2 được ghi nhận
trong tài liệu này. Việc tạo tài liệu không có nghĩa các interface mới đã được
triển khai hoặc các kiểm thử bên dưới đã chạy đạt.

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

Đề nghị Member 1 và 3 chốt một phép chiếu đọc công khai do Identity sở hữu để
adapter Matching/Discovery lấy ID, tên hiển thị, trình độ và giới tính theo lô
hoặc bằng phép join đã được cho phép. Chữ ký và vị trí triển khai còn mở.

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
- Member 3 sở hữu hành vi và adapter writer thuộc Matching; vị trí đích cụ thể
  chốt cùng cấu trúc module. Member 1 inject vào tạo phiên chơi và phê duyệt.
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
- Xác nhận snapshot cho `read()` khi Discovery đếm tổng và lấy trang bằng nhiều
  truy vấn: REPEATABLE READ, phạm vi snapshot riêng hoặc một câu SQL tương đương.
- Xác nhận giới hạn thời gian chờ, ánh xạ lỗi PostgreSQL và fixture dùng các
  connection độc lập để kiểm thử tạo Matching đối đầu phê duyệt/tạo phiên chơi.

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

- [ ] Member 1 xác nhận PlayerProfile/PlayerProfileReader và đường dẫn triển khai.
- [ ] Member 1 và 3 xác nhận dùng skill_to_rank() và projection hồ sơ ứng viên.
- [ ] Member 1 và 3 xác nhận VenueStatusReader và nơi đặt hợp đồng Catalog.
- [ ] Member 1 và 3 xác nhận writer, vị trí adapter và cách inject vào Sessions.
- [ ] Member 2 xác nhận UoW dùng chung, port khóa, snapshot, timeout và fixture.
- [ ] Ghi lại quyết định cuối, người xác nhận, ngày xác nhận và commit bàn giao.

Chỉ đánh dấu sau khi có phản hồi thực tế. Các điểm chưa chốt cần được ghi rõ
trước khi refactor file dùng chung.
