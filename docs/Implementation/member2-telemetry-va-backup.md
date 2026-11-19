# Member 2 · Bàn giao telemetry và khôi phục Phase 1

Ngày cập nhật: **19/11/2026**. Đối chiếu Member 1 tại `e9c696e` (mục 3–5)
và Member 3 tại `89978d6` (mục 9–10).

Đây là đặc tả bàn giao phía Member 2, chưa phải instrumentation hoặc backup đã
triển khai. Không yêu cầu xác nhận lại các hợp đồng Member 1 đã chốt tại mục 1.2
của [báo cáo mới](phase1-member1.md).

## 1. Danh sách telemetry gửi Member 3

Member 2 chốt phía mình các tên trường, đơn vị và cách đo dưới đây để Member 3
ghép vào request trace. Thời lượng dùng đồng hồ monotonic, đơn vị giây; timestamp
sự kiện dùng UTC. Trường chưa đo được phải bỏ hoặc dùng null, không gán 0.

- `request_id`: lấy từ request state hiện có, giữ cùng giá trị với envelope lỗi
  và `X-Request-ID`. Member 3 truyền context này tới hook DB; Member 2 không sinh
  ID thứ hai. Chỉ dùng trong log/trace, không làm nhãn metrics.
- `route_template`, `method`, `http_status`, `request_duration_seconds`,
  `error_code`: Member 3 cung cấp ở lớp HTTP. Route dùng template đã match,
  không dùng raw URL/query string; route không match dùng giá trị cố định
  `unmatched`. `error_code` lấy mã API thực trả, thành công dùng null.
- `matching_candidate_count`, `matching_selection_duration_seconds`: Member 3
  cung cấp. Đề nghị count là số ứng viên sau bộ lọc request/lịch/profile và trước
  Strategy; duration chỉ bao phần chọn nhóm, không gồm query DB. Phải đo cả khi
  không có gợi ý; route không chạy Matching dùng null. Member 3 còn cần xác nhận
  định nghĩa và vị trí hook trước khi đóng danh sách chung.
- `db_acquire_duration_seconds`: Member 2 cung cấp, tính từ yêu cầu lấy connection
  đến lấy được hoặc thất bại. Có thể gồm tạo connection mới; **không gọi đây là
  pool wait thuần**. Muốn tách `db_pool_wait_seconds` phải có hook đo riêng lúc
  đợi slot; chỉ dùng sự kiện checkout sau khi lấy được connection là chưa đủ.
  Ghi cả lần timeout với outcome, không chỉ các lần lấy thành công.
- `db_lock_acquire_duration_seconds`: Member 2 cung cấp, bao lời gọi primitive
  khóa đến khi trả kết quả hoặc lỗi. Nhãn `lock_target` chỉ `session`/`user`,
  outcome `acquired`/`missing`/`timeout`/`error`. Số đo gồm round trip và execute,
  không chứng minh toàn bộ thời gian là lock wait. Lock wait thực trên PostgreSQL
  có thể lấy mẫu `pg_stat_activity.wait_event_type=Lock` với khoảng lấy mẫu được
  ghi rõ; không suy ra thời lượng chính xác từ một mẫu hoặc thu SQL text.
- `db_transaction_duration_seconds`: Member 2 cung cấp, từ trước bước BEGIN
  đến lúc kết thúc commit/rollback và thu dọn UoW; không bao bước lấy connection
  đã đo riêng. Phân biệt mode `read`/`write` và outcome
  `committed`/`rolled_back`/`failed`/`unknown`. Transaction đọc đóng bình thường
  bằng rollback là `rolled_back`, không tự tính thành lỗi request.
- `db_error_kind`, `db_sqlstate`, `db_phase`: Member 2 cung cấp khi có lỗi.
  Phase dùng `acquire`/`begin`/`execute`/`commit`/`rollback`; SQLSTATE không có
  thì null. Error kind dùng tập hữu hạn `busy`, `pool_timeout`, `lock_timeout`,
  `deadlock`, `serialization_failure`, `statement_timeout`,
  `query_cancelled_unknown`, `unavailable`, `integrity`, `other`.
  Chỉ gán `statement_timeout` khi có ngữ cảnh tin cậy; 57014 riêng lẻ dùng
  `query_cancelled_unknown`. Mất kết nối trong commit giữ outcome `unknown`;
  lỗi cleanup sau đó không được ghi đè nguyên nhân/kết quả chưa biết.

Histogram metrics dùng tên và đơn vị tương ứng, công bố bucket khi triển khai.
Chỉ dùng nhãn hữu hạn: route template, method, status, dialect, mode, outcome,
lock target, error kind. Không dùng request/user/session/venue ID, backend PID,
SQLSTATE tùy ý, URL, SQL/params, email, token hoặc credential làm nhãn. SQLSTATE
chỉ thuộc log/trace đã lọc. Không log password, URL kết nối hoặc nội dung dump.
Telemetry lỗi không được làm command thất bại hoặc tự phát query trên transaction
đã lỗi; exporter không giữ transaction chờ I/O mạng.

### Tiêu chí kiểm chứng khi triển khai giai đoạn 2–3

1. Member 3 chứng minh cùng request ID từ HTTP qua DB đến error envelope; route
   chưa match/401/422/503 vẫn được ghi, không chỉ request thành công.
2. Member 2 dùng connection độc lập tạo pool contention/row-lock contention,
   đo thành công và timeout; không gán execute latency thành thời gian chờ thuần.
3. Kiểm outcome commit, rollback do thiếu commit/lỗi và commit-unknown. Một UoW
   phát đúng một kết quả cuối; exporter hỏng không đổi kết quả nghiệp vụ.
4. Member 3 kiểm candidate count ở tập đầu vào Strategy, duration first-valid
   gồm cả ca không có nhóm; không log profile hoặc ngân sách người khác.
5. Cả hai kiểm nhãn hữu hạn và soát log không chứa dữ liệu nhạy cảm. Những ca này
   là tiêu chí nghiệm thu tương lai, chưa phải test đã chạy trong Phase 1.

## 2. Hồ sơ đích backup cần điền

Chưa có địa chỉ kho/máy ngoài máy ứng dụng trong repository. Không dùng
`artifacts/`, volume PostgreSQL hay thư mục khác trên cùng máy làm bằng chứng
off-host. Hồ sơ sau phải được người quản lý hạ tầng cung cấp trước diễn tập:

- Máy/kho đích và bằng chứng độc lập với máy chạy API/DB: **chưa được cung cấp**.
- Bucket/share/thư mục gốc thực tế: **chưa được cung cấp**.
- Người quản lý và người có quyền restore: **chưa được cung cấp**.
- Kênh truyền, tài khoản dịch vụ và cách cấp secret ngoài Git:
  **chưa được cung cấp**; không gửi mật khẩu/private key vào báo cáo/chat.
- Chính sách lưu giữ, dung lượng, mã hóa và lịch chạy backup:
  **chưa được xác nhận**. Đề nghị hằng ngày để kiểm mục tiêu RPO 24 giờ.
- DB/host restore riêng và người cấp quyền tạo DB: **chưa được cung cấp**.

Sau khi có thư mục gốc, cấu trúc tương đối thống nhất phía Member 2:
`matchmate-backups/<release-commit>/<UTC timestamp>/`, gồm dump custom,
checksum SHA-256 và manifest. Đây là quy ước đặt tên, chưa phải đích đã cấu hình.
Manifest ghi release commit/image digest, migration revision, PostgreSQL/pg_dump
version, UTC bắt đầu/kết thúc dump, checksum, kích thước, thời điểm off-host
upload/verify hoàn tất và người vận hành; không chứa secret. Nếu cần đối chiếu
counts trong lúc nguồn còn ghi, phải lấy cùng snapshot với dump hoặc đóng ghi;
không so counts từ một lần query khác rồi tuyên bố bản dump sai/đúng.

## 3. Quy trình backup/restore bàn giao

1. Kiểm DB nguồn, phiên bản công cụ phù hợp server, release/schema và quyền
   dump. Secret lấy từ cấu hình cục bộ, không đặt trong lệnh/báo cáo. Ghi mốc UTC;
   tạo tên output mới, không ghi đè bằng chứng cũ.
2. Dùng `pg_dump -Fc` ra staging có quyền truy cập hạn chế; kiểm exit code,
   kích thước và đọc TOC bằng `pg_restore --list`. Tính SHA-256, ghi manifest.
   Đọc được TOC chưa chứng minh restore thành công.
3. Chuyển dump/checksum/manifest qua kênh đã cấp đến kho ngoài máy; tính lại
   checksum tại đích và so sánh. Chỉ ghi backup thành công khi đích xác nhận đủ
   tệp và checksum trùng. Staging cục bộ chưa đáp ứng RPO off-host.
4. Lấy chính bản off-host về môi trường restore; kiểm checksum. Người vận hành
   xác minh host/DB đích khác nguồn. Tạo DB trống riêng và restore bằng
   `pg_restore --exit-on-error --no-owner --no-privileges`; không dùng `--clean`
   trên DB nghiệp vụ. Dump schema/data này không sao lưu role cấp cluster;
   chuẩn bị role và cấp lại quyền ứng dụng theo cấu hình triển khai.
5. Kiểm migration revision, FK/CHECK/partial index, ID/lịch sử/timestamp UTC,
   sequence bằng insert trong DB restore, rồi chạy smoke test Auth/Sessions/
   Matching phù hợp dữ liệu thử. Với fixture tổng hợp, so manifest ở
   `prepare_member2_phase1.py`; dữ liệu đó không có hash đăng nhập thật.
6. Ghi thời điểm phát hiện sự cố, DB khỏe, API sẵn sàng và smoke test đạt.
   Đối chiếu phát hiện ≤30 giây, phục hồi API ≤60 giây sau DB khỏe và RTO ≤30
   phút từ sự cố đến smoke test đạt. RPO tính từ điểm dữ liệu phục hồi được;
   nếu không có snapshot timestamp chính xác, dùng mốc bắt đầu dump làm cận
   bảo thủ. Một bản backup mới chưa chứng minh lịch hằng ngày/RPO luôn đạt.
7. Giữ log diễn tập đã lọc secret, checksum, manifest và kết quả smoke test làm
   bằng chứng. Chỉ xóa DB restore/staging theo chính sách đã thống nhất sau đó;
   quy trình này chưa thực hiện xóa hay thay đổi DB nào.

## 4. Xác nhận còn cần

- **Member 1:** cập nhật trạng thái xác nhận ở báo cáo cũ và checklist tổng theo
  mục 1.2 tài liệu mới; cung cấp commit công bố port/error handler/composition
  root khi triển khai giai đoạn 2. Xác nhận thiết kế đã có, không cần hỏi lại.
- **Member 3:** xác nhận tên/đơn vị/định nghĩa trường HTTP và Matching, cách truyền
  request context, nơi export; thống nhất cùng Member 2 giới hạn đo pool/lock
  wait nêu ở mục 1. Cung cấp corpus Matching và sau đó cấu hình ingress thực,
  số worker để tính connection budget (không cần cấu hình thật để đóng Phase 1).
- **Nhóm/người quản lý hạ tầng:** điền hồ sơ mục 2. Đây là thông tin môi trường
  thực, không thể thay bằng tên máy, tài khoản hoặc địa chỉ kho tự đặt.

Chỉ đánh dấu telemetry đã thống nhất chung sau phản hồi Member 3; chỉ đánh dấu
backup off-host/restore đạt sau khi có đích thực và bằng chứng chạy.
