# Phase 1 · Thành viên 1 · Hiện trạng, hợp đồng và bàn giao

Ngày cập nhật: **19/11/2026**.

Tài liệu chỉ theo dõi phạm vi **Phase 1: khảo sát hiện trạng, kiểm thử làm mốc,
thống nhất hợp đồng và chuẩn bị bàn giao**. Các đầu việc xây adapter, refactor,
migration/import, wiring, cấu hình ingress thực tế và kiểm chứng PostgreSQL được
quản lý trong [kế hoạch triển khai](../Architecture_Phase2/kehoachtrienkhai-VN.md).

Nguồn đối chiếu:

- [Báo cáo hiện trạng thành viên 1](member-1-phase-1.vi.md), commit làm mốc
  `696fbb1683eff430012f4db9db0701ec9a98fb01`.
- [Báo cáo thành viên 2](phase1-member2.md), đặc biệt mục 11 và đặc tả telemetry
  tại `7475ef9`.
- [Báo cáo thành viên 3](phase1-member3.md), đặc biệt mục 11–12 và xác nhận
  telemetry tại `43cd47e`.
- [Báo cáo tổng và bằng chứng bàn giao](phase1.md).

`[x]` nghĩa là đã có tài liệu, xác nhận hoặc bằng chứng được dẫn cụ thể.
`[ ]` nghĩa là đầu ra Phase 1 còn thiếu hoặc chưa đủ bằng chứng.
Kết quả kiểm thử bên dưới là kết quả đã ghi nhận, không phải lần chạy lại khi
rút gọn tài liệu này.

## 1. Phạm vi và trạng thái Phase 1

| Thành viên | Đã có | Còn cần để đóng Phase 1 |
| --- | --- | --- |
| **1 — Identity và Sessions** | Truy vết transaction/invariant, kiểm thử, quyền truy cập, xác nhận năm nhóm hợp đồng, đồng bộ tài liệu và checklist | Hoàn thành. |
| **2 — Persistence và vận hành** | Khảo sát SQLite/PostgreSQL, nguồn SQLite tổng hợp, PostgreSQL cục bộ, hợp đồng khóa/snapshot/lỗi, đích backup, đặc tả telemetry | Hoàn thành. |
| **3 — Catalog, Matching và Discovery** | Truy vết Matching, Catalog/profile/writer, phạm vi join đọc, ingress, xác nhận telemetry và bộ ca làm mốc | Hoàn thành. |

### 1.1. Điều kiện đóng Phase 1

- [x] Đã ghi commit khảo sát ban đầu, hành vi API và các invariant cần giữ.
- [x] Đã có bằng chứng kiểm thử Auth/Sessions và nguồn dữ liệu migration thử.
- [x] Đã ghi nhận lựa chọn của thành viên 2/3 và xác nhận của thành viên 1.
- [x] Đủ bộ ca Matching làm mốc theo mục 4.
- [x] Có đích backup ngoài máy ứng dụng cụ thể và người quản lý (mục 3).
- [x] Có danh sách telemetry đã thống nhất giữa thành viên 2/3.
- [x] Đồng bộ checklist/tài liệu và ghi bàn giao chung tại [báo cáo tổng](phase1.md).

### 1.2. Xác nhận chính thức từ thành viên 1

Người xác nhận: **người dùng phụ trách thành viên 1**, ngày **19/11/2026**.
Nguồn: xác nhận trực tiếp “Ok lets confirm them” sau khi rà soát năm nhóm hợp đồng.
Các lựa chọn dưới đây dựa trên phản hồi đã ghi của thành viên 2 và 3.

- [x] **UoW và khóa hàng:** mỗi command sở hữu transaction; repository, reader,
  locks và writer dùng chung UoW. Giữ `write()`, `read()`, `commit()`;
  `TransactionLocks.lock_session()` / `lock_user()` trả bool tồn tại/đã khóa.
  Khóa session trước user, theo ID tăng dần khi có nhiều hàng; đọc lại Clock và
  trạng thái sau khóa. PostgreSQL write dùng READ COMMITTED, read dùng
  REPEATABLE READ, READ ONLY; snapshot đọc bắt đầu ở truy vấn đầu tiên.
- [x] **Identity:** chấp nhận `PlayerProfile` bốn trường `id`, `display_name`,
  `skill_level: SkillLevel`, `gender: Gender`; reader đơn và batch do Identity
  sở hữu. `get_by_id()` trả DTO hoặc None; `get_by_ids()` trả dict, bỏ ID thiếu,
  loại ID trùng, đầu vào rỗng trả `{}`. Giữ `skill_to_rank()` và thứ tự ứng viên;
  loại candidate thiếu profile/UNSPECIFIED, giữ lỗi caller hiện hành.
- [x] **Catalog:** chấp nhận `VenueStatusReader.is_active() -> bool | None`,
  `VenueSummary` năm trường và `VenueReader` đơn/batch tại
  `app/features/catalog/contracts.py`. Đọc cả sân inactive cho lịch sử; batch
  tối đa 500 ID/câu, không giới hạn tổng kết quả. Giữ filter/count/order trước
  phân trang; chỉ cho phép join projection đọc đã thống nhất.
- [x] **Matching writer:** giữ
  `MatchingRequestWriter.close_overlapping(user_id, starts_at, ends_at, now)`;
  cùng transaction với tạo kèo/duyệt, không tự commit. CONFIRMED chỉ đóng ACTIVE
  chồng lịch; REPLACED dùng khi thay yêu cầu cũ. Chấp nhận đường dẫn đích
  `app/features/matching/infrastructure/matching_request_writer.py`, giữ tên lớp
  `SqlAlchemyMatchingRequestWriter` và composition root do thành viên 1 phụ trách.
- [x] **Error contract:** chấp nhận bảng phản hồi ở mục 1.3, gồm generic 500 cho
  cancellation chưa rõ nguồn hủy, `outcome=unknown` khi mất kết nối trong commit
  và không tự replay command. Trong các lỗi DB nêu dưới đây, chỉ BUSY có
  `Retry-After` mặc định.

Đây là xác nhận hợp đồng ở Phase 1; trạng thái xây các thành phần mới được theo
dõi ở kế hoạch triển khai riêng.

### 1.3. Hành vi lỗi đã thống nhất để bàn giao

Giữ envelope `error={code, message, details, request_id}` và header `X-Request-ID`.

| Tình huống | Phản hồi đã thống nhất | Details / header |
| --- | --- | --- |
| SQLite BUSY; PostgreSQL 55P03; pool timeout; 40P01/40001 | `503 DATABASE_BUSY` — `Hệ thống đang bận, vui lòng thử lại` | `{}`, `Retry-After: 1`; không tự retry command. |
| Statement timeout có ngữ cảnh tin cậy | `503 DATABASE_TIMEOUT` — `Thao tác dữ liệu vượt quá thời gian cho phép` | `{}`, không `Retry-After` mặc định. |
| Mất kết nối trước commit | `503 DATABASE_UNAVAILABLE` — `Không thể kết nối cơ sở dữ liệu` | `{}`, không `Retry-After`. |
| Mất kết nối trong commit, chưa rõ kết quả | `503 DATABASE_UNAVAILABLE` — `Chưa xác định được kết quả thao tác dữ liệu` | `{"outcome": "unknown"}`, không `Retry-After`; không khẳng định mutation chưa xảy ra. |
| SQLSTATE 57014 chưa rõ nguồn hủy | `500 INTERNAL_ERROR` — `Không thể xử lý yêu cầu` | `{}`, không `Retry-After` hoặc nội dung SQL/driver. |

Chỉ SQLSTATE 57014 hoặc việc đã cấu hình statement_timeout chưa đủ chứng minh
nguyên nhân timeout. Nhánh chưa rõ dùng generic handler; telemetry nội bộ phân
loại `query_cancelled_unknown`, không thêm exception domain cho cancellation.
Unique/FK/CHECK không tự đổi thành DATABASE_BUSY. Chi tiết thiết kế lỗi ở mục 9.2
và 10.2 của báo cáo thành viên 2.

## 2. Thành viên 1 · Checklist Phase 1

- [x] Truy vết nơi bắt đầu/commit transaction trong Auth và Sessions; liệt kê
  create, join, approve/reject, withdraw/cancel và các invariant.
- [x] Chạy các kiểm thử làm mốc, ghi phản hồi payload sai, thiếu xác thực,
  yêu cầu trùng và DELETE lặp; bổ sung ca commit thất bại.
- [x] Kiểm kê nơi sử dụng hồ sơ Identity và quyền truy cập route, gồm tìm kiếm
  công khai có chế độ `host_me=true` yêu cầu đăng nhập.
- [x] Thống nhất hợp đồng UoW/khóa với thành viên 2 và profile/Catalog/writer
  với thành viên 3; xác nhận được ghi ở mục 1.2.
- [x] Đồng bộ xác nhận trong hai bản báo cáo hiện trạng và checklist Phase 1
  của kế hoạch tổng.
- [x] Ghi bàn giao chung tại [báo cáo tổng](phase1.md).

Bằng chứng: [báo cáo thành viên 1](member-1-phase-1.vi.md) ghi **160 ca đạt**,
gồm 29 ca mới; Ruff đạt. Các ca mới kiểm lỗi commit của bảy lệnh, ưu tiên 401,
khác biệt 422/503 và quyền riêng tư của chi tiết kèo. Mốc hiện tại: payload sai
khi DB đang bị khóa có thể trả 503 ở đăng ký/tạo kèo, nhưng trả 422 ở xin tham gia;
401 vẫn được ưu tiên trên route yêu cầu đăng nhập.

## 3. Thành viên 2 · Checklist Phase 1

- [x] Khảo sát `session.py`, `models.py`, `types.py`, `unit_of_work.py` và lỗi DB;
  ghi PRAGMA, timestamp, Boolean, partial index và sequence cần xử lý theo dialect.
- [x] Chuẩn bị [script nguồn SQLite tổng hợp](../../scripts/prepare_member2_phase1.py),
  manifest và [kiểm thử fixture](../../tests/foundation/test_member2_phase1_fixture.py).
  Bộ dữ liệu có lịch sử participation và matching đã thay thế; counts
  venues=1, users=3, sessions=1, participations=4, matching_requests=3.
- [x] Báo cáo đã chạy PostgreSQL cục bộ bằng
  [Compose riêng](../../compose.phase1-member2.yaml): PostgreSQL 17.11, UTC,
  cổng loopback 55432, lock timeout 5s và statement timeout 15s.
- [x] Thống nhất thao tác khóa, lỗi timeout và thiết kế kiểm thử bằng connection
  độc lập: A/B có UoW riêng, kiểm `pg_backend_pid()`, điều phối Event/Barrier,
  đọc trạng thái cuối bằng connection C.
- [x] Phác thảo HTTPS proxy → API → PostgreSQL, mạng ingress/DB private, migration
  một lần trước API startup, liveness/readiness và quy trình backup/restore.
- [x] Ghi mục tiêu diễn tập: phát hiện DB mất kết nối 30 giây, API phục hồi 60 giây
  sau khi DB khỏe, RTO 30 phút, RPO 24 giờ nếu backup hằng ngày thành công.
- [x] Người dùng chốt ngày **19/11/2026**: app/DB trên máy thành viên 1;
  backup trên máy thành viên 2, tại `artifacts/backups/` tính từ gốc dự án
  `matchmate-backend/`, do thành viên 2 quản lý, không ghi ký tự ổ đĩa.
  Chi tiết tại [hồ sơ backup](member2-telemetry-va-backup.md#2-đích-backup-đã-chốt).
  Đây là xác nhận đích lưu Phase 1; chưa phải bằng chứng truyền tệp/restore đạt.
- [x] Chốt danh sách trường telemetry theo mục 4.1.

Bằng chứng do thành viên 2 báo cáo: hai ca fixture đạt; kết quả mới nhất của suite
foundation/architecture chọn lọc là **73 passed**, Ruff đạt, sau khi sửa khả năng
chạy trên Windows. Nguồn SQLite là dữ liệu tổng hợp; kết quả này chưa phải bằng
chứng import hoặc concurrency PostgreSQL.

## 4. Thành viên 3 · Checklist Phase 1

- [x] Truy vết tạo Matching, query sân/kèo và các phản hồi hiện tại: tạo thành công
  trả 201, gửi lại tạo ID mới và đóng bản cũ bằng REPLACED; không có nhóm hợp lệ
  trả `suggestion=null` nhưng vẫn lưu yêu cầu.
- [x] Ghi thứ tự ứng viên `(created_at, id)`, chọn first-valid, rank spread tối đa
  2, bộ lọc request/lịch và quy tắc hồ sơ thiếu/UNSPECIFIED theo query hiện hành.
- [x] Ghi quy tắc privacy: chỉ host có `management`, mỗi người chỉ thấy lượt của
  mình trong `my_participations`, gợi ý không lộ email hoặc ngân sách người khác.
- [x] Thống nhất port đóng matching chồng lịch trong UoW bên gọi, quyền sở hữu
  Catalog và projection đọc/join Discovery được phép; thành viên 1 đã xác nhận.
- [x] Ghi nhận topology private của thành viên 2 và mốc response timeout ingress
  demo 30 giây, không retry upstream POST; đây là lựa chọn thiết kế đã được chấp nhận.
- [x] Hoàn thiện bộ ca Matching với dữ liệu cố định, thứ tự ứng viên và kết quả
  tại [báo cáo tổng, mục 3](phase1.md#3-bộ-ca-matching-làm-mốc).
- [x] Cùng thành viên 2 chốt danh sách telemetry ở mục 4.1.

| Ca cần chuẩn bị | Kết quả mong đợi |
| --- | --- |
| Không có ứng viên | Lưu yêu cầu; không có gợi ý. |
| Thiếu ứng viên để đủ nhóm đơn/đôi | Lưu yêu cầu; không có gợi ý. |
| Đủ ứng viên nhưng không có nhóm hợp lệ | Lưu yêu cầu; không có gợi ý; ghi rõ điều kiện trình độ/giới tính/ngân sách làm nhóm bị loại. |
| Có nhiều nhóm hợp lệ | Chọn đúng nhóm hợp lệ đầu tiên theo thứ tự hiện hành. |
| Ứng viên cùng `created_at` | Dùng ID để phân xử thứ tự và chọn nhóm nhất quán. |

[Corpus tích hợp](../../tests/integration/test_phase1_matching_corpus.py) kiểm
các ca trên qua API và SQLite tạm.

### 4.1. Telemetry đã chốt

Ghi một danh sách chung cho benchmark và truy vết, phân công rõ bên cung cấp:

| Nhóm | Trường/số đo cần chốt |
| --- | --- |
| Request, thành viên 3 phụ trách | Correlation/request ID, route template, HTTP status, duration, error code. |
| Matching, thành viên 3 phụ trách | Candidate count và thời gian chọn nhóm. |
| DB, thành viên 2 phụ trách | Thời lượng lấy connection, lấy khóa và transaction. Chỉ đo thời gian chờ thuần nếu có hook phù hợp. |

Member 2 đặc tả tại `7475ef9`, Member 3 xác nhận tại `43cd47e` và Tech Lead chốt
context/export theo [đặc tả telemetry](member2-telemetry-va-backup.md).
Instrumentation nằm trong kế hoạch triển khai.

## 5. Checklist ghi nhận và xác nhận bàn giao

- [x] Đã có commit khảo sát, báo cáo hành vi và bằng chứng Auth/Sessions của thành viên 1.
- [x] Đã có dữ liệu nguồn, môi trường PostgreSQL cục bộ và khảo sát persistence của thành viên 2.
- [x] Đã ghi nhận năm nhóm hợp đồng được thành viên 1 xác nhận, cùng các phản hồi thành viên 2/3.
- [x] Corpus Matching làm mốc có ca nhiều nhóm hợp lệ và đồng hạng.
- [x] Thành viên 2 ghi đích backup trên máy thành viên 2, thư mục
  `artifacts/backups/` từ gốc dự án, do thành viên 2 quản lý (nguồn ở máy thành viên 1).
- [x] Chốt danh sách telemetry và bên cung cấp từng trường/số đo.
- [x] Đồng bộ trạng thái hợp đồng trong tài liệu cũ và checklist tổng.
- [x] Bàn giao chung tại [phase1.md](phase1.md), liên kết corpus, dữ liệu mẫu,
  kết quả kiểm thử và hợp đồng đã chốt.

Các mục trên hoàn thành phạm vi Phase 1 theo kế hoạch.
