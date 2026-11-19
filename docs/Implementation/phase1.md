# MatchMate · Báo cáo tổng kết Phase 1

Ngày bàn giao **19/11/2026**. Tech Lead tổng hợp các quyết định và bằng chứng
từ [Member 1](phase1-member1.md), [Member 2](phase1-member2.md) và
[Member 3](phase1-member3.md).

**Phase 1 đã hoàn thành.** Báo cáo này ghi các hợp đồng đã chốt, dữ liệu làm
mốc, kết quả kiểm thử và phân công triển khai Phase 2.

## 1. Phạm vi và đầu ra bàn giao

- **Member 1 · Identity và Sessions.** Đã truy vết ranh giới transaction,
  từng lệnh vòng đời, nơi dùng hồ sơ và quyền truy cập; ghi hành vi HTTP làm mốc
  và kiểm thử rollback khi commit thất bại. Xác nhận năm nhóm hợp đồng tại
  `40f0ee3`, được giữ trong `e9c696e`. Bản khảo sát bắt đầu từ
  `696fbb1683eff430012f4db9db0701ec9a98fb01`.
  [Hiện trạng và cách chạy kiểm thử](member-1-phase-1.vi.md).
- **Member 2 · Persistence và vận hành.** Đã khảo sát khác biệt SQLite/PostgreSQL,
  chuẩn bị dữ liệu chuyển thử, PostgreSQL cục bộ, thiết kế khóa/snapshot và quy
  trình khôi phục. Đặc tả telemetry gốc tại `7475ef9`.
  [Báo cáo Member 2](phase1-member2.md).
- **Member 3 · Catalog, Matching và Discovery.** Đã ghi luồng tạo Matching,
  truy vấn đọc, thứ tự ứng viên, quyền riêng tư, hợp đồng Catalog/writer và cấu
  hình ingress dự kiến. Xác nhận telemetry và đề xuất cách truyền context/export
  tại `43cd47e`. Bộ ca làm mốc nằm ở mục 3.
  [Báo cáo Member 3](phase1-member3.md).

Phase 1 giao các hợp đồng, dữ liệu làm mốc và phương án triển khai. Phần triển
khai và nghiệm thu PostgreSQL, telemetry và khôi phục được theo dõi ở mục 5.

## 2. Hành vi và hợp đồng đã chốt

1. **Transaction, khóa và snapshot.** Tầng ứng dụng sở hữu `write()`, `read()` và
   một lần `commit()` cho lệnh ghi. Repository, reader, locks và writer dùng cùng
   UoW. Thiếu commit hoặc lỗi đã biết dẫn đến rollback. Hai thao tác
   `lock_session(id)` và `lock_user(id)` trả `bool` cho biết hàng tồn tại và đã
   được khóa. Khóa session trước user và khóa theo ID tăng dần trong từng nhóm.
   Tạo kèo mới khóa host trước insert, tạo Matching chỉ khóa người gọi. Đọc lại
   Clock và dữ liệu liên quan sau khóa. SQLite dùng `BEGIN IMMEDIATE` khi ghi.
   PostgreSQL dùng READ COMMITTED khi ghi và REPEATABLE READ, READ ONLY khi đọc,
   với snapshot hình thành từ truy vấn đầu tiên.
2. **Identity.** `PlayerProfile` có `id`, `display_name`, `skill_level: SkillLevel`
   và `gender: Gender`. Identity sở hữu `get_by_id()` và `get_by_ids()`. Đầu vào
   batch rỗng trả `{}` không query, loại ID trùng và bỏ ID thiếu khỏi kết quả.
   Matching giữ `skill_to_rank()` và thứ tự ứng viên, loại hồ sơ thiếu hoặc
   `UNSPECIFIED`. Caller thiếu vẫn `UNAUTHORIZED`, caller `UNSPECIFIED` vẫn
   `PROFILE_INCOMPLETE`.
3. **Catalog và Discovery.** Catalog sở hữu `VenueStatusReader.is_active()`
   trả `True`/`False`/`None` và `VenueSummary` gồm `id`, `name`, `address`,
   `district_code`, `is_active`. `VenueReader` đọc đơn/batch trong transaction
   bên gọi, trả cả sân inactive cho lịch sử, tối đa 500 ID mỗi câu query.
   Discovery được join projection đọc năm cột với dữ liệu Sessions. Giữ filter,
   count và order trước phân trang, cùng hình dạng DTO và quy tắc quyền riêng tư.
4. **Matching writer.** Giữ `close_overlapping(user_id, starts_at, ends_at, now)`
   trong UoW của lệnh tạo kèo/duyệt. Writer chỉ đóng `ACTIVE` của đúng user và
   có giao giờ thực bằng `CONFIRMED`. Hai lịch nối tiếp được giữ nguyên. Tạo
   Matching lần nữa dùng `REPLACED` và tạo ID mới. Member 3 chuyển adapter sang
   `app/features/matching/infrastructure/matching_request_writer.py`. Member 1
   lắp tại composition root. Lỗi writer phải làm lệnh gọi thất bại và rollback.
5. **Lỗi DB.** Giữ `error={code, message, details, request_id}` và `X-Request-ID`.
   SQLite BUSY, PostgreSQL 55P03, pool timeout, 40P01 và 40001 trả `503 DATABASE_BUSY`
   với `Retry-After: 1`. Statement timeout đã xác định trả `503 DATABASE_TIMEOUT`.
   Mất kết nối trả `503 DATABASE_UNAVAILABLE`, thêm `{"outcome":"unknown"}` khi
   xảy ra trong commit và chưa rõ kết quả. `57014` chưa xác định nguồn hủy trả
   `500 INTERNAL_ERROR` và ghi loại `query_cancelled_unknown` nội bộ. Timeout,
   unavailable và generic 500 không có `Retry-After` mặc định. Không tự phát lại
   lệnh. Giữ unique/FK/CHECK ngoài nhóm BUSY.
   [Bảng phản hồi chính xác](phase1-member1.md#13-hành-vi-lỗi-đã-thống-nhất-để-bàn-giao).

Hành vi Auth/Sessions làm mốc gồm `401` trước lỗi đầu vào trên route được bảo vệ,
chỉ host thấy `management`, mỗi người chỉ thấy `my_participations` của mình,
giữ snapshot phí/giới tính và tính lặp của thao tác rút/hủy. `host_me=true` yêu
cầu đăng nhập. Khi DB bị khóa, dữ liệu sai có thể trả `503` ở đăng ký/tạo kèo
và `422` ở xin tham gia. Trong Phase 2, Tech Lead chốt chuyển hai route đầu sang
`422` đối với dữ liệu không hợp lệ, giữ ưu tiên `401`.
[Kiểm thử hồi quy Member 1](../../tests/integration/test_member1_baseline.py).

## 3. Bộ ca Matching làm mốc

Bộ ca chạy `POST /matching/requests` với JWT và SQLite tạm. Mỗi ca dùng một DB
riêng, sân active ID `10`, đồng hồ cố định `2030-11-02T10:00:00Z`, lịch từ
`12:00:00Z` đến `14:00:00Z` cùng ngày. Caller user `100` có rank `9`, `MALE`,
policy `ANY`, phí đề xuất nam/nữ `60.000/40.000` VND và ngân sách `60.000` VND.
Request cũ `900` của caller tạo lúc `09:54:00Z`. Các request ứng viên đều
`ACTIVE`, cùng sân, khung giờ, loại trận và phí trên, không có lịch ACCEPTED chồng
giờ. Ứng viên mặc định tạo lúc `09:59:00Z`, rank `9`, `MALE`, policy `ANY` và
ngân sách `60.000` VND. Định danh `request/user` bên dưới dùng ID của hai bản ghi.

| Ca | Dữ liệu thay đổi và thứ tự ứng viên vào bước chọn nhóm | Kết quả mong đợi |
| --- | --- | --- |
| Không có ứng viên · đơn | Không có request của người khác | `null` |
| Thiếu người · đơn | `200/201` có hồ sơ `UNSPECIFIED`, bị lọc, còn `[]` | `null` |
| Thiếu người · đôi | `200/201`, `210/211` cùng giờ tạo. Cần ba ứng viên | `null` |
| Đủ người, lệch rank · đơn | `200/201` rank `12`, lệch `3` so với caller | `null` |
| Đủ người, sai policy giới tính · đơn | `200/201` là `FEMALE`, policy `FEMALE_ONLY` loại caller `MALE` | `null` |
| Đủ người, quá ngân sách · đơn | `200/201` có ngân sách `59.999`, phí áp dụng `60.000` | `null` |
| Nhiều nhóm hợp lệ · đôi | `240/241` (rank 12), `230/231` (rank 10), `220/221` (FEMALE, ngân sách 40.000), `210/211` (rank 11), `200/201` lần lượt tạo từ `09:55` đến `09:59` UTC. Các tổ hợp có `240` đều lệch rank 3. Sau đó `230/220/210` là tổ hợp hợp lệ đầu tiên, trước `230/220/200` | `[100, 231, 221, 211]` |
| Đồng hạng thời gian · đơn | `210/201` và `200/211` cùng `09:59`; thứ tự sau phân xử là `200/211`, `210/201` | `[100, 211]` |

Mọi ca phải trả `201`, ghi request mới `901` ở trạng thái `ACTIVE` và đóng `900`
bằng `REPLACED`. Khi có gợi ý, kiểm thứ tự ID thành viên, phí ước tính, cờ yêu
cầu xác nhận và việc không lộ email/ngân sách trong danh sách thành viên.
[Corpus có thể chạy lại](../../tests/integration/test_phase1_matching_corpus.py).

## 4. Dữ liệu, telemetry và vận hành

- **Dữ liệu chuyển thử và PostgreSQL.** SQLite tổng hợp gồm `venues=1`, `users=3`,
  `sessions=1`, `participations=4`, `matching_requests=3`. Fixture giữ ID và lịch
  sử participation/matching, UTC có microsecond và hồ sơ `UNSPECIFIED`. Dùng
  `python -m scripts.prepare_member2_phase1 --output artifacts/member2-phase1-repro`
  để tạo DB và manifest. Chọn tên output mới nếu thư mục đã có bằng chứng.
  Member 2 đã xác minh PostgreSQL `17.11`, UTC, `lock_timeout=5s`,
  `statement_timeout=15s` qua Compose cục bộ.
  [Script dữ liệu](../../scripts/prepare_member2_phase1.py) ·
  [Kiểm thử fixture](../../tests/foundation/test_member2_phase1_fixture.py) ·
  [Compose](../../compose.phase1-member2.yaml) ·
  [Bằng chứng Member 2](phase1-member2.md#8-kết-quả-thực-thi-ngày-19112026).
- **Telemetry Member 3.** Ghi `request_id`, `route_template`, `method`,
  `http_status`, `request_duration_seconds`, `error_code`. Ghi thêm
  `matching_candidate_count` sau lọc và trước bước chọn, cùng
  `matching_selection_duration_seconds` cho đúng bước chọn nhóm.
- **Telemetry Member 2.** Ghi `db_acquire_duration_seconds`,
  `db_lock_acquire_duration_seconds`, `db_transaction_duration_seconds`,
  `db_error_kind`, `db_sqlstate`, `db_phase`. Thời lượng lấy connection/khóa
  bao gồm công việc ngoài thời gian chờ. Đo thời gian chờ thuần cần hook riêng.
- **Context và export.** Tech Lead chốt thiết kế theo xác nhận Member 3. Hook DB
  của Member 2 dùng context riêng của request do HTTP truyền qua `ContextVar`.
  Giữ context khi sang threadpool và dọn sau request. Log có cấu trúc xuất stdout.
  Metrics HTTP/Matching/DB gửi tới collector trên mạng riêng. Timestamp UTC,
  thời lượng tính giây bằng đồng hồ monotonic, trường chưa đo dùng null hoặc bỏ.
  Request ID và SQLSTATE chỉ dùng trong log/trace đã lọc. Metrics dùng nhãn hữu
  hạn. Không ghi thông tin xác thực, thông tin hồ sơ hoặc nội dung SQL/params.
  [Đặc tả và tiêu chí kiểm chứng](member2-telemetry-va-backup.md#1-danh-sách-telemetry-đã-chốt).
- **Ingress và backup.** Demo theo HTTPS proxy → API → PostgreSQL, chỉ ingress
  công khai. Mốc upstream response timeout `30s` và tắt retry upstream cho POST.
  Migration chạy một lần trước API, `/health` dùng cho liveness, readiness kiểm
  DB. App/DB chạy trên **máy Member 1**. Member 2 quản lý backup trên **máy
  Member 2** tại `artifacts/backups/` tính từ gốc dự án. Diễn tập dùng dump custom,
  SHA-256 và restore vào DB riêng. Mục tiêu phát hiện DB lỗi ≤30 giây, API sẵn
  sàng ≤60 giây từ khi DB khỏe, RTO ≤30 phút, RPO ≤24 giờ với backup hằng ngày.
  [Đích lưu và quy trình](member2-telemetry-va-backup.md#2-đích-backup-đã-chốt).

## 5. Kiểm thử và bàn giao sang Phase 2

Mốc lịch sử **160 ca Auth/Sessions** do Member 1 ghi nhận và **73 ca nền tảng/
kiến trúc** do Member 2 ghi nhận. Hai nhóm có phạm vi giao nhau.

Lần kiểm chứng bàn giao trên Windows với Python 3.14.3 đạt **302 ca**, gồm cả
tám ca Matching mới. Hai cảnh báo hiện có liên quan đến AnyIO portal và khóa
HS512 cố ý dùng trong ca kiểm tra từ chối thuật toán. Ruff và `git diff --check`
đều đạt. Lệnh dưới đây dùng UTF-8 để các script ghi tiếng Việt trên Windows.

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check app tests scripts
```

Commit bàn giao là commit tạo tệp này. Có thể tra bằng
`git log --diff-filter=A -- docs/Implementation/phase1.md`.

- **Member 1** triển khai port, composition root, handler lỗi và refactor
  Identity/Sessions. Giữ thứ tự ưu tiên xác thực và các bất biến ở mục 2.
- **Member 2** triển khai adapter, migration/import, fixture PostgreSQL độc lập,
  instrumentation DB và cấu hình chuyển/kiểm/khôi phục backup. Chốt hostname/IP,
  quyền truy cập, lịch chạy và môi trường restore với Member 1 khi triển khai.
- **Member 3** tách Matching Strategy/command, chuyển writer, triển khai Catalog
  reader và giữ tương thích Discovery. Dùng corpus mục 3 để kiểm trên bản refactor.
  Cấu hình ingress và instrumentation HTTP/Matching, phối hợp với Member 2.

Kế hoạch và các mốc nghiệm thu được theo dõi tại
[kế hoạch triển khai](../Architecture_Phase2/kehoachtrienkhai-VN.md).
