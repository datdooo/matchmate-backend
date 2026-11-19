# Thành viên 1 · Hiện trạng và bàn giao hợp đồng giao tiếp Phase 1

[Bản tiếng Anh](member-1-phase-1.md)

Rà soát ngày **19/11/2026**, dựa trên commit ban đầu
`696fbb1683eff430012f4db9db0701ec9a98fb01`.
Thư mục làm việc đã có một thay đổi về ký tự xuống dòng trong `pyproject.toml`;
đợt rà soát này giữ nguyên thay đổi đó. Phần bàn giao bổ sung tài liệu và kiểm thử
hồi quy; chưa thay đổi hành vi ứng dụng hoặc cấu trúc cơ sở dữ liệu.

## Trạng thái checklist

| Hạng mục Phase 1 | Trạng thái | Bằng chứng / việc tiếp theo |
| --- | --- | --- |
| Truy vết transaction và liệt kê các điều kiện luôn phải đúng trong vòng đời kèo/lượt tham gia | Hoàn thành | Các phần bên dưới chỉ rõ nơi quản lý transaction và điều kiện của từng lệnh. |
| Chạy kiểm thử Auth/vòng đời, ghi nhận phản hồi và xác định kiểm thử cần có khi commit thất bại | Hoàn thành | Bộ kiểm thử hiện có và các ca mới xác minh rollback cùng phản hồi lỗi khi commit thất bại. Có lệnh chạy lại bên dưới. |
| Thống nhất UoW và thao tác khóa session/user với thành viên 2 | Đã có bản nháp; chờ thống nhất | Bên dưới có chữ ký phương thức đề xuất và yêu cầu đối với adapter. Chưa bổ sung API khóa hàng vào mã ứng dụng. |
| Kiểm kê nơi sử dụng hồ sơ, quyền truy cập route; thống nhất hợp đồng hồ sơ/Catalog với thành viên 3 | Đã kiểm kê; chờ thống nhất | Có bảng nơi sử dụng và bảng route bên dưới. Giao diện hồ sơ và trạng thái sân vẫn là đề xuất, cần các bên phụ trách rà soát. |

## 1. Ranh giới transaction hiện tại

| Thao tác | Nơi mở transaction | Nơi commit | Công việc trong transaction |
| --- | --- | --- | --- |
| Đăng ký | `provide_registration_service()` trong [Auth dependencies](../../app/features/auth/dependencies.py) gọi `uow.write()` trước khi `yield` | Dependency commit sau khi hàm xử lý route trả về, với phạm vi dependency `function` của FastAPI | Kiểm tra email trùng, băm Argon2, insert/flush, dựng phản hồi. Hiện tại transaction ghi vẫn được giữ trong lúc băm mật khẩu. |
| Đăng nhập | `provide_login_service()` gọi `uow.read()` trước khi `yield` | Không commit; rollback/đóng transaction đọc khi thoát phạm vi | Đọc thông tin xác thực, kiểm tra mật khẩu, cấp token. Hiện tại transaction đọc vẫn được giữ trong lúc kiểm tra mật khẩu. |
| Tra cứu user từ JWT | `lookup_authenticated_user()` mở UoW đọc riêng trong middleware | Không commit | Đọc tài khoản hiện tại rồi đóng transaction trước khi chạy endpoint. Kết quả này không thay thế việc kiểm tra lại trạng thái bên trong transaction thay đổi dữ liệu. |
| Tạo kèo | `provide_create_session_service()` trong [session router](../../app/features/sessions/session_router.py) gọi `uow.write()` | Dependency commit sau khi endpoint dựng dữ liệu chi tiết | Kiểm tra thời gian/sân/hồ sơ/trùng lịch, tạo kèo và lượt của host, đóng yêu cầu matching chồng lịch, dựng dữ liệu chi tiết. |
| Hủy kèo | Cùng dependency ghi của thao tác tạo kèo | Cùng dependency đó | Kiểm tra quyền host trước khi xử lý yêu cầu lặp, hủy kèo và các lượt đang hoạt động, dựng dữ liệu chi tiết. |
| Xem chi tiết kèo | `provide_read_session_service()` trong session router gọi `uow.read()` | Không commit | Đọc nhiều lần để lấy kèo, host, sân và các lượt tham gia. SQLite hiện dùng transaction tường minh để giữ cùng ảnh chụp dữ liệu. |
| Xin tham gia / duyệt / từ chối / rút lượt | [ParticipationService](../../app/features/sessions/participation_service.py) tự mở `uow.write()` | `_finish()` dựng dữ liệu chi tiết, gọi `uow.commit()`, rồi trả kết quả | Dependency chỉ lắp các adapter; repository và matching writer dùng chung UoW này. |
| Tìm kiếm qua Discovery | [DiscoveryService](../../app/features/discovery/service.py) mở `uow.read()` | Không commit | Truy vấn trả DTO, gồm cả đếm tổng số và lấy dữ liệu phân trang. |
| Tạo yêu cầu matching | Discovery service mở `uow.write()` | Service commit sau khi thay yêu cầu cũ, thêm yêu cầu mới và chọn nhóm | Hiện là một lệnh nguyên tử, bao gồm cả tính gợi ý. Thành viên 3 phụ trách tách phần này. |

[SqlAlchemyUnitOfWork](../../app/db/unit_of_work.py) mở `BEGIN IMMEDIATE` khi ghi
và `BEGIN` khi đọc. Khối `finally` rollback và giải phóng DB session, kể cả khi
commit phát sinh lỗi. Repository gọi flush nhưng không commit. Lỗi SQLite bận
được chuyển thành `DatabaseBusyError`. Chưa có khóa hàng PostgreSQL.

### Các lệnh vòng đời và điều kiện phải giữ nguyên

| Lệnh | Quy tắc cần bảo toàn |
| --- | --- |
| Đăng ký | Chuẩn hóa email; DB bảo đảm email duy nhất; lưu mật khẩu đã băm; không để lộ thông tin xác thực. Commit thất bại không được để lại tài khoản. |
| Tạo kèo | Thời gian ở tương lai, kéo dài 60–240 phút; sân tồn tại và hoạt động; hồ sơ host đầy đủ và đủ điều kiện; không trùng lịch đã được chấp nhận. Trong cùng transaction, thêm kèo OPEN, lượt ACCEPTED của host kèm phí/giới tính tại thời điểm tạo, và đóng các yêu cầu matching ACTIVE chồng lịch. |
| Xin tham gia | Kèo tồn tại, OPEN và chưa bắt đầu; còn chỗ; hồ sơ hiện tại đủ điều kiện; chưa có lượt đang hoạt động của cùng user/kèo; không trùng lịch đã được chấp nhận. Thêm lượt PENDING kèm phí/giới tính tại thời điểm xin. PENDING không giữ chỗ và có thể chồng lịch với một yêu cầu PENDING khác. |
| Duyệt | Chỉ host; lượt đang PENDING; kèo OPEN và chưa bắt đầu. Kiểm tra lại hồ sơ hiện tại, số chỗ và lịch đã được chấp nhận. Chuyển sang ACCEPTED và đóng matching chồng lịch trong cùng commit. Giữ nguyên phí/giới tính đã ghi nhận lúc xin tham gia. |
| Từ chối | Chỉ host; lượt đang PENDING; kèo OPEN và chưa bắt đầu. Chuyển sang REJECTED mà không yêu cầu người chơi còn đủ điều kiện, kèo còn chỗ hoặc người chơi không trùng lịch. Giữ nguyên phí/giới tính đã ghi nhận. |
| Rút lượt | Chỉ chủ lượt; host phải hủy kèo thay vì rút lượt của mình. PENDING/ACCEPTED chuyển thành CANCELLED trước giờ bắt đầu. Nếu lượt đã CANCELLED, trả lại trạng thái hiện có kể cả sau giờ bắt đầu; không đổi thời điểm hủy và không mở lại matching. Không thể rút lượt REJECTED. |
| Hủy kèo | Chỉ host, kể cả khi gọi lặp. Hủy trước giờ bắt đầu; cập nhật kèo và mọi lượt PENDING/ACCEPTED một cách nguyên tử, giữ lịch sử REJECTED/CANCELLED và phí/giới tính đã ghi nhận. Kèo đã CANCELLED trả lại kết quả hiện có kể cả sau giờ bắt đầu. Không mở lại matching. |

Với mọi lệnh vòng đời: số lượt được chấp nhận không vượt sức chứa, tính cả host
(2 người khi đánh đơn, 4 người khi đánh đôi). Hai khoảng thời gian được coi là
chồng nhau khi `start_a < end_b and start_b < end_a`; vì vậy hai lịch nối tiếp
được phép, còn một người không được có hai lượt ACCEPTED chồng lịch.
Mỗi user/kèo chỉ có một lượt đang hoạt động, đồng thời vẫn giữ các bản ghi lịch sử.
Trạng thái hiển thị tiếp tục được tính từ thời gian/số người, không lưu trạng thái
FULL/STARTED để làm căn cứ quyết định.

## 2. Hành vi HTTP làm mốc và bằng chứng kiểm thử hồi quy

Lỗi dùng cấu trúc `{"error": {"code", "message", "details", "request_id"}}`,
với header phản hồi `X-Request-ID` trùng `request_id`. Không cố định các ID và
thời điểm được sinh động trong dữ liệu kiểm thử.
[Bộ xử lý lỗi](../../app/api/error_handlers.py) quy định ánh xạ mã lỗi.

| Tình huống | Phản hồi hiện tại |
| --- | --- |
| Body/query/path không hợp lệ, đã đáp ứng yêu cầu xác thực và không phải chờ khóa | `422 VALIDATION_ERROR`; khoảng thời gian sai quy tắc nghiệp vụ dùng `422 INVALID_TIME_WINDOW`. Chi tiết lỗi kiểm tra đầu vào không chứa dữ liệu nhạy cảm gốc. |
| Thiếu/sai JWT trên route yêu cầu đăng nhập, kể cả khi body/path sai | `401 UNAUTHORIZED`, `WWW-Authenticate: Bearer`, trước bước kiểm tra đầu vào của endpoint. |
| Email đăng nhập không tồn tại hoặc sai mật khẩu | `401 INVALID_CREDENTIALS`, `WWW-Authenticate: Bearer`; hai trường hợp dùng cùng thông báo. |
| Đăng ký bằng email đã tồn tại sau chuẩn hóa | `409 EMAIL_ALREADY_EXISTS`. |
| Xin tham gia lặp khi lượt trước vẫn hoạt động và đã qua các bước kiểm tra điều kiện/sức chứa | `409 PARTICIPATION_ALREADY_EXISTS`. Thứ tự kiểm tra có ý nghĩa: nếu kèo đầy, có thể trả `SESSION_FULL` trước. |
| Tạo lại kèo cho cùng host và khoảng thời gian | Logic hiện tại từ chối vì trùng lịch đã được chấp nhận, trả `409 TIME_CONFLICT`; chưa có cơ chế phát lại kết quả theo khóa yêu cầu. |
| Quyết định lại một lượt không còn PENDING | `409 INVALID_STATE`. |
| Tạo yêu cầu matching lặp | `201` với ID mới; yêu cầu ACTIVE cũ chuyển thành CLOSED với lý do REPLACED. Thành viên 3 phụ trách kiểm thử giữ nguyên kết quả matching. |
| Chủ thể có quyền gọi rút lượt / hủy kèo lặp | `200`, cùng bản ghi/trạng thái/thời điểm, kể cả sau giờ bắt đầu. Vẫn kiểm tra quyền sở hữu. |
| Người không có quyền duyệt/hủy/rút đối tượng của người khác | `403 FORBIDDEN`; không thay đổi dữ liệu. Host tự rút lượt của mình nhận `409 HOST_PARTICIPATION_REQUIRED`. |
| Hết thời gian chờ khóa ghi SQLite | `503 DATABASE_BUSY`, `Retry-After: 1`; không để lại dữ liệu ghi dở dang. |
| Commit gặp lỗi ngoài dự kiến | `500 INTERNAL_ERROR`, thông tin kỹ thuật được ẩn; không trả thành công và không để lại dữ liệu ghi dở dang. |

**Điểm khác biệt về thứ tự ưu tiên lỗi cần xử lý trong Phase 2:** khi một bên ghi
khác đang giữ `BEGIN IMMEDIATE`, body `{}` không hợp lệ hiện trả `503` ở đăng ký
và tạo kèo, vì dependency mở transaction ghi trước khi kiểm tra body. Cùng body
đó ở thao tác xin tham gia lại trả `422`, vì use case mở transaction sau bước
kiểm tra đầu vào. Đợt refactor đề xuất chủ động đổi hai trường hợp đầu thành
`422`; phải giữ ưu tiên `401` trên route yêu cầu đăng nhập và cập nhật kiểm thử
mốc này khi triển khai thay đổi.

Bằng chứng hiện có gồm:

- [Kiểm thử Auth](../../tests/auth/): đăng ký, chuẩn hóa, tính duy nhất, claims/chữ
  ký JWT và Authorization không hợp lệ trên route công khai.
- [Kiểm thử Sessions](../../tests/sessions/): chuyển trạng thái, phí/giới tính đã
  ghi nhận, trùng lịch/sức chứa, quyền truy cập, rút lượt lặp không đổi kết quả,
  các tình huống tranh chấp đồng thời trên SQLite và hết thời gian chờ khóa.
- [Kiểm thử các route tích hợp](../../tests/integration/test_main.py): giữ lịch sử
  khi hủy và gọi hủy lặp, đóng matching, tìm kiếm công khai và thống nhất trạng
  thái hiển thị.
- [Kiểm thử UoW](../../tests/foundation/test_unit_of_work.py): commit, rollback khi
  chưa commit, rollback khi có ngoại lệ, transaction đọc và hết thời gian chờ khóa.
- [Các kiểm thử mốc mới của thành viên 1](../../tests/integration/test_member1_baseline.py):
  chủ động gây lỗi tại `Session.commit()` sau khi flush thật cho đăng ký, tạo kèo,
  hủy kèo, xin tham gia, duyệt, từ chối và rút lượt. Mỗi lệnh được kiểm tra với cả
  lỗi SQLite bận lẫn lỗi ngoài dự kiến; một DB session mới xác minh cả năm bảng
  khớp ảnh chụp trước lệnh, gồm trạng thái matching và các mốc thời gian. Các ca
  này còn kiểm tra ưu tiên 401 trước kiểm tra đầu vào, khác biệt 422/503, đăng nhập
  không hợp lệ và quyền xem dữ liệu chi tiết.

Các lỗi commit được chủ động gây ra chứng minh khả năng rollback khi commit
**chưa thành công**. Chúng chưa chứng minh khả năng phục hồi khi mất kết nối làm
cho kết quả commit không xác định. Kiểm thử tranh chấp SQLite chưa chứng minh
tính đúng đắn khi xử lý đồng thời trên PostgreSQL.

### Cách kiểm chứng

Dùng Python 3.11+ và cài `requirements-dev.txt` trong môi trường riêng.
Đợt rà soát dùng Python 3.12.3 cùng các phiên bản thư viện bị ràng buộc trong repo.

```bash
python -m pytest tests/auth tests/sessions tests/foundation/test_unit_of_work.py tests/integration/test_main.py tests/integration/test_member1_baseline.py -q
ruff check tests/integration/test_member1_baseline.py
```

Kết quả ngày 19/11/2026: **160 ca đạt trong 6,39 giây**, gồm 29 ca kiểm thử mốc
mới của thành viên 1; Ruff đạt. Còn hai cảnh báo từ thư viện/kiểm thử: Starlette
dùng bí danh AnyIO portal đã bị đánh dấu ngừng khuyến nghị, và khóa kiểm thử ngắn
được cố ý dùng trong ca từ chối token HS512. Không có ca thất bại hoặc bị bỏ qua.

## 3. Hợp đồng giao tiếp đề xuất để thành viên 2 rà soát

[UoW port](../../app/domain/ports.py) dự kiến giữ `write()`, `read()` và `commit()`.
Sửa tài liệu của port để mô tả bảo đảm transaction, thay vì câu SQL riêng cho
SQLite. Lệnh ở tầng ứng dụng mở phạm vi ghi và chủ động commit đúng một lần sau
khi dựng kết quả. Không tự động commit, không lồng UoW, không mở transaction riêng
trong repository. Mọi ngoại lệ hoặc thoát phạm vi mà chưa commit đều rollback;
lỗi commit phải được truyền ra trước khi trả phản hồi thành công. DB session của
adapter chỉ dùng được trong phạm vi UoW và trước commit. Dependency chỉ lắp adapter.

`read()` phải công bố rõ bảo đảm về ảnh chụp dữ liệu cho các thao tác đọc chi tiết,
đếm tổng và phân trang gồm nhiều truy vấn. SQLite đã cung cấp bảo đảm này. Thành
viên 2 cần cấu hình PostgreSQL REPEATABLE READ cho các phạm vi đọc đó, hoặc thống
nhất phạm vi đọc snapshot riêng / cách triển khai bằng một câu SQL. Chỉ dùng
PostgreSQL READ COMMITTED không tạo cùng ảnh chụp dữ liệu cho toàn transaction.
Phạm vi ghi dùng READ COMMITTED kết hợp khóa hàng.

Port dự kiến được inject, đặt tại `app/domain/ports.py` (chưa triển khai):

```python
class TransactionLocks(Protocol):
    def lock_session(self, session_id: int) -> bool: ...
    def lock_user(self, user_id: int) -> bool: ...
```

- `True`: hàng tồn tại và được khóa đến khi UoW kết thúc. `False`: hàng không tồn
  tại, để tầng ứng dụng chọn lỗi không tìm thấy/xác thực theo hành vi hiện có.
- Adapter dùng connection và transaction của bên gọi; không commit, không mở UoW
  mới. Với SQLite, khóa ghi toàn DB hiện có kết hợp kiểm tra tồn tại có thể đáp ứng
  yêu cầu đồng bộ. PostgreSQL dùng khóa hàng trong adapter của mình.
- Đọc lại trạng thái sau khi lấy khóa. Tra cứu participation trước khóa chỉ để
  xác định session/user ID; không dùng kết quả đó để quyết định quyền hoặc chuyển
  trạng thái. Bảo đảm bộ nhớ đệm ORM không trả trạng thái cũ trước khi khóa.
- Khóa các session đã tồn tại theo ID tăng dần, rồi user theo ID tăng dần, tiếp
  đến participation và matching. Không lấy khóa session đã tồn tại sau khi đã giữ
  khóa user. Đọc đồng hồ sau khi lấy đủ các khóa cần thiết.
- Xin tham gia/duyệt hoặc từ chối/rút lượt: khóa session rồi user đích. Hủy kèo:
  khóa session, lấy các user có lượt đang hoạt động, loại trùng và khóa theo ID
  tăng dần. Tạo kèo: chỉ khóa host trước khi thêm session mới. Tạo matching: chỉ
  khóa user gọi lệnh. Tuân theo
  [thiết kế nhất quán](du-lieu-va-nhat-quan.md#32-quy-tắc-thứ-tự-và-từng-use-case).
- Thời gian chờ khóa, chờ connection từ pool và thực thi câu lệnh phải có giới hạn.
  Thành viên 2 cần ánh xạ rõ lỗi timeout PostgreSQL; không dùng lại cách nhận diện
  mã lỗi SQLite. Rollback toàn bộ thao tác khi thất bại. Không tự động thử lại khi
  chưa biết commit đã thành công hay chưa.
- Thành viên 1 phụ trách hợp đồng tầng ứng dụng và thứ tự gọi; thành viên 2 phụ
  trách SQL, xử lý từng hệ quản trị DB và fixture tích hợp dùng các connection độc lập.

Đề xuất giữ nguyên chữ ký hợp đồng writer hiện có của Matching:
`MatchingRequestWriter.close_overlapping(user_id, starts_at, ends_at, now)`.
Writer phải dùng cùng transaction, không tự commit, xét chồng lịch theo bất đẳng
thức nghiêm ngặt, chỉ đóng ACTIVE thành CLOSED với lý do CONFIRMED và dùng thời
điểm được truyền vào. Inject writer trực tiếp vào thao tác tạo kèo và duyệt, thay
vì để `SessionRepository` kế thừa writer. Thành viên 3 cung cấp adapter thuộc
module Matching; thành viên 2 xác minh adapter dùng chung transaction lưu trữ.

## 4. Nơi sử dụng Identity và hợp đồng đề xuất với thành viên 3

| Nơi sử dụng hiện tại | Phụ thuộc / thông tin hiện dùng | Đích refactor |
| --- | --- | --- |
| Tạo kèo | `SessionService.users: UserRepository`, được lắp bằng `SqlAlchemyUserRepository`; cần ID, giới tính, trình độ | Inject bộ đọc hồ sơ của Identity, không dùng repository có cả chức năng truy cập thông tin xác thực. |
| Xin tham gia/duyệt | `ParticipationRepository.get_user()` gọi repository SQLAlchemy nội bộ của Auth; cần giới tính và trình độ | Inject cùng bộ đọc hồ sơ Identity vào application service. |
| Người gọi matching | Matching repository đọc `UserModel` và trả `PlayerSummary` | Dùng hợp đồng hồ sơ đã thống nhất; giữ cách hiểu trình độ dạng số hiện tại khi chọn nhóm. |
| Ứng viên matching | Matching repository join các yêu cầu với `UserModel` | Thống nhất hợp đồng đọc/phép chiếu công khai do Identity sở hữu để join ứng viên; tránh tra cứu từng hồ sơ riêng lẻ. |
| Chi tiết kèo/lượt và tìm kiếm Discovery | Read adapter join `UserModel` để lấy ID, tên hiển thị, trình độ, giới tính của host/người chơi | Dùng phép chiếu công khai đã thống nhất và trả DTO; không để email, hash hoặc đối tượng ORM thoát ra ngoài. |
| JWT middleware và đăng ký/đăng nhập Auth | Auth repository / thông tin xác thực | Giữ trong Identity; use case thay đổi dữ liệu đọc lại hồ sơ liên quan sau khi khóa. |

Giao diện công khai đề xuất của Identity trong `app/features/auth/contracts.py`:

```python
@dataclass(frozen=True)
class PlayerProfile:
    id: int
    display_name: str
    skill_level: SkillLevel
    gender: Gender

class PlayerProfileReader(Protocol):
    def get_by_id(self, user_id: int) -> PlayerProfile | None: ...
```

Không có email, password hash hoặc phương thức tra cứu thông tin xác thực. Trả
`None` khi không có tài khoản; chấp nhận giá trị giới tính `UNSPECIFIED` trong dữ
liệu cũ để kiểm tra PROFILE_INCOMPLETE hiện có vẫn hoạt động. Sessions dùng
`skill_to_rank()` để kiểm tra khoảng trình độ do host đặt; Matching hiện dùng
trình độ số nguyên trong `PlayerSummary`, nên adapter phải chuyển đổi rõ ràng,
không làm đổi thứ tự hoặc quy tắc chênh lệch trình độ nhóm. Gắn reader với UoW của
bên gọi để kiểm tra trạng thái có hiệu lực khi thay đổi dữ liệu. Các phép join chỉ
phục vụ hiển thị có thể dùng phép chiếu đọc đã thống nhất trong cùng snapshot.

Giao diện Catalog tối thiểu đề xuất, do thành viên 3 sở hữu:

```python
class VenueStatusReader(Protocol):
    def is_active(self, venue_id: int) -> bool | None: ...
```

`None` tương ứng VENUE_NOT_FOUND (404); `False` tương ứng VENUE_INACTIVE (409);
`True` cho phép tiếp tục tạo kèo. Dùng cùng transaction. Hiện Sessions thực hiện
qua `SessionRepository.venue_is_active()`, còn Matching đọc `VenueRecord` của
Discovery. Catalog cũng sở hữu phép chiếu dữ liệu sân đầy đủ hơn (ID, tên, địa chỉ,
quận, trạng thái hoạt động) cho Discovery và đọc chi tiết. Tách phép chiếu đó khỏi
kiểm tra trạng thái tối thiểu; không cần thêm API quản trị sân mới.

## 5. Quy tắc truy cập route và đối tượng hiện tại

| Phương thức / đường dẫn | Xác thực | Quy tắc đối tượng/dữ liệu |
| --- | --- | --- |
| POST `/auth/register`, POST `/auth/login` | Công khai | Nếu có gửi Authorization nhưng không hợp lệ, middleware vẫn từ chối. |
| GET `/venues` | Công khai | Trả DTO sân công khai. |
| GET `/sessions` | Mặc định công khai | `host_me=true` yêu cầu JWT; lấy ID người xem từ principal đã xác thực và chỉ trả kèo do người đó làm host. Tìm kiếm thông thường không lộ dữ liệu quản lý lượt riêng tư. |
| POST `/sessions` | JWT | Người dùng đã xác thực trở thành host; payload không được chọn host khác. |
| GET `/sessions/{id}` | JWT | Mọi người dùng đã xác thực đều có thể xem; chỉ host nhận `management`; mỗi người chỉ thấy các lượt của mình trong `my_participations`, gồm cả lịch sử. |
| DELETE `/sessions/{id}` | JWT | Chỉ host, kể cả khi hủy lặp. |
| POST `/participations` | JWT | Người dùng đã xác thực là người xin tham gia. |
| POST `/participations/{id}/decision` | JWT | Chỉ host của kèo. |
| DELETE `/participations/{id}` | JWT | Chỉ chủ lượt; host không được rút lượt host của mình. |
| POST `/matching/requests` | JWT | Người dùng đã xác thực sở hữu yêu cầu/yêu cầu thay thế; gợi ý không chứa email hoặc ngân sách của người khác. |
| GET `/health` | Công khai | Kiểm tra tiến trình còn hoạt động. |
| `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` | Tài liệu tự sinh công khai | Các route hiện có do framework tạo; cần tính đến khi kiểm tra khai báo chính sách truy cập. |

[JWT middleware](../../app/features/auth/middleware.py) hiện suy ra route yêu cầu
đăng nhập từ phương thức HTTP và biểu thức chính quy của đường dẫn. Khi tìm kèo,
nó nhận các giá trị đúng của `host_me` là `true`, `1`, `yes`, `on`, `t`, `y`, không
phân biệt hoa thường. Authorization được gửi nhưng sai bị từ chối ngay cả trên
route công khai; OPTIONS bỏ qua xác thực. Phase 2 cần khai báo chính sách truy cập
tường minh và có kiểm thử thất bại nếu route mới chưa được khai báo, đồng thời
giữ các quy tắc xác thực có điều kiện này.

## Các quyết định bàn giao còn chờ thống nhất

1. **Thành viên 2:** xác nhận tên port khóa, ý nghĩa giá trị trả về, cách lắp adapter
   dùng chung transaction, cơ chế snapshot đọc, ánh xạ lỗi timeout và cách thiết
   lập kiểm thử PostgreSQL.
2. **Thành viên 3:** xác nhận cách biểu diễn trình độ trong DTO hồ sơ, bên sở hữu
   phép chiếu ứng viên/dữ liệu đọc, hợp đồng trạng thái sân của Catalog và vị trí
   adapter matching writer.
3. **Thành viên 1 và 2:** đưa thay đổi ưu tiên lỗi `503 → 422` của đăng ký/tạo kèo
   đã ghi nhận vào refactor và kiểm thử Phase 2. Vẫn phải giữ ưu tiên `401` trên
   route yêu cầu đăng nhập.

Chưa gửi thông điệp cho các thành viên khác và chưa coi các đề xuất là đã được
thống nhất. Có thể hoàn tất các checkbox còn lại sau khi ghi nhận các quyết định trên.
