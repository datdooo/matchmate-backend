# Thiết kế dữ liệu và tính nhất quán Phase 2

> Đề xuất kỹ thuật, chưa thay đổi schema hoặc code. Đọc cùng [kiến trúc tổng thể](de-xuat-kien-truc.md).

## 1. Các invariant không được mất khi refactor

1. `accepted_count <= capacity`; host có lượt `ACCEPTED` khi tạo kèo.
2. Một người không có hai participation `ACCEPTED` thuộc các khoảng thời gian chồng nhau. Hai khoảng nối tiếp được phép: overlap khi `start_a < end_b AND start_b < end_a`.
3. Mỗi `(user_id, session_id)` chỉ có một lượt `PENDING` hoặc `ACCEPTED`; lịch sử `REJECTED`/`CANCELLED` vẫn giữ.
4. Mỗi user có tối đa một matching request `ACTIVE` theo ngữ nghĩa hiện hành, kể cả bản đã quá giờ nhưng chưa được đóng.
5. Tạo kèo/duyệt thành công phải đóng matching request chồng lịch trong cùng commit. Không chuyển bước này sang eventual consistency.
6. Hủy kèo và hủy các lượt hoạt động phải atomic. Phí và giới tính snapshot không bị ghi đè khi duyệt/rút/hủy.
7. `display_status` phụ thuộc thời gian và số lượt được chấp nhận; không thêm cột `FULL`/`STARTED` rồi phụ thuộc job cập nhật để quyết định quyền ghi.

DB giữ FK, CHECK và unique index; use case giữ quyền, state transition và invariant liên bảng. Không kỳ vọng một unique index thông thường tự kiểm được overlap thời gian hoặc giới hạn sức chứa.

## 2. Chuẩn hóa ranh giới transaction

Đề xuất mọi command application service sở hữu một UoW. Dependency chỉ lắp đối tượng, không mở transaction trước body validation. Router chuyển schema sang input DTO rồi gọi use case; repository không commit; không có nested UoW.

Luồng chuẩn: authenticate → validate payload → mở UoW → lấy khóa cần thiết → đọc thời gian hiện tại → đọc lại dữ liệu và kiểm quyền/invariant → ghi/flush → dựng DTO → commit → trả HTTP. Nếu commit thất bại, không trả thành công. External I/O không nằm trong transaction.

Đối với đăng ký, băm mật khẩu trước transaction ghi để không giữ khóa trong phép tính Argon2; vẫn giữ unique email ở DB để phân xử đăng ký đồng thời. Login lấy credential cần thiết trong transaction đọc ngắn rồi verify ngoài transaction.

Đây là thay đổi có chủ ý so với auth/session dependency hiện tại: payload sai có thể trả 422 thay vì chờ khóa rồi 503. Phải cập nhật đặc tả và test tương ứng ở pha triển khai, đồng thời giữ ưu tiên 401 trước 422 cho route yêu cầu đăng nhập.

UoW port mới nên mô tả bảo đảm transaction/rollback, không ghi cứng `BEGIN IMMEDIATE` như contract hiện tại. Adapter SQLite giữ cơ chế đó; adapter PostgreSQL có transaction và thao tác khóa theo repository. Không giả định `read()` ở mọi DB mặc nhiên có cùng snapshot: query nhiều câu cần snapshot nhất quán thì dùng một câu SQL hoặc transaction đọc `REPEATABLE READ`; PostgreSQL `READ COMMITTED` cho snapshot theo từng statement.

## 3. PostgreSQL: giao thức khóa đề xuất

### 3.1. Vì sao cần khóa cả session và user

Khóa row session bảo vệ chỗ cuối trong **cùng kèo**. Nó không ngăn hai transaction duyệt **cùng người vào hai kèo khác nhau**. Đề xuất khóa thêm row user làm điểm đồng bộ hóa lịch của người đó, rồi kiểm lại overlap trên trạng thái đã commit.

Baseline đề xuất: PostgreSQL `READ COMMITTED` với row locks và kiểm lại dữ liệu sau khi lấy khóa. Mọi đường ghi tạo/xóa lịch xác nhận phải tuân thủ cùng giao thức; chỉ một đường ghi bỏ qua khóa cũng làm mất bảo đảm. Chưa coi thiết kế đúng cho đến khi concurrency tests chạy với nhiều connection PostgreSQL thật.

### 3.2. Quy tắc thứ tự và từng use case

Thứ tự chung cho các tài nguyên đã tồn tại: **session theo ID tăng dần → user theo ID tăng dần → participation → matching request**. Không có luồng giữ user rồi quay lại lấy khóa session đã tồn tại. Các thao tác tương lai đụng nhiều session phải biết tập ID trước hoặc retry toàn transaction khi phát hiện tập thay đổi.

- **Approve/reject:** đọc participation ban đầu để biết session/user (chưa coi là căn cứ quyết định), khóa session, khóa user đích, đọc lại participation và trạng thái kèo, kiểm quyền và thời gian. Approve đếm lại chỗ, kiểm overlap, cập nhật trạng thái, đóng matching, rồi commit. Reject có thể dùng cùng giao thức đơn giản dù không cần kiểm capacity/overlap.
- **Join:** khóa session rồi user, kiểm open/capacity/profile/overlap, ghi `PENDING`. Dù không giữ chỗ, cách này vẫn giữ ngữ nghĩa hiện tại là không nhận đơn khi kèo đã đầy.
- **Withdraw:** khóa session rồi user của participation; đọc lại quyền/trạng thái, cập nhật nếu hợp lệ. DELETE lặp giữ tính idempotent như đặc tả.
- **Cancel session:** khóa session trước để chặn join/approve/withdraw; đọc danh sách user của các lượt hoạt động, khóa các user theo ID tăng dần; kiểm lại quyền/thời gian, hủy kèo và các lượt. Không mở lại matching đã đóng.
- **Create session:** khóa user host, kiểm overlap, tạo session mới và lượt host. Ngoại lệ hợp lệ với thứ tự trên: session mới chưa được transaction khác nhìn thấy, không lấy khóa một session đã tồn tại sau khi giữ user.
- **Create matching request:** khóa user người gọi, kiểm lịch, đóng request cũ và tạo request mới; không lấy khóa session. Thao tác tạo/duyệt lịch của cùng user cũng giữ khóa user nên không bỏ sót việc đóng matching do race.

Row user có thể trở thành điểm contention cho một tài khoản hoạt động dồn dập, nhưng phạm vi nhỏ hơn khóa toàn DB. Nếu sau này tách Identity thành service riêng, không thể tiếp tục khóa bảng user xuyên service: cần thiết kế chủ sở hữu lịch riêng hoặc cơ chế nhất quán khác trước khi tách.

Thiết lập lock/statement timeout có giới hạn và ánh xạ lỗi hạ tầng rõ ràng. Deadlock hoặc serialization failure nếu có được rollback toàn transaction; retry giới hạn, ví dụ tối đa hai lần với jitter và tổng deadline. Mỗi lần retry đọc lại clock và dữ liệu. Không retry lỗi nghiệp vụ 409; không retry mù khi mất kết nối khiến kết quả commit không rõ.

### 3.3. Sequence duyệt lượt

```mermaid
sequenceDiagram
    participant C as Client host
    participant A as API
    participant S as Approve use case
    participant D as PostgreSQL
    C->>A: POST decision APPROVE
    A->>A: JWT và schema validation
    A->>S: actor ID, participation ID
    S->>D: BEGIN; lấy session/user ID
    S->>D: khóa session rồi user; đọc lại participation
    S->>S: đọc clock, kiểm quyền và state
    S->>D: đếm ACCEPTED và kiểm overlap
    alt hợp lệ
        S->>D: ACCEPTED + đóng matching chồng giờ
        S->>D: COMMIT
        S-->>A: DTO thành công
        A-->>C: 200
    else xung đột nghiệp vụ
        S->>D: ROLLBACK
        S-->>A: DomainError
        A-->>C: 409 hoặc 403 tùy lỗi
    end
```

Khi approve đua cancel/withdraw, giao thức tạo thứ tự xử lý hợp lệ theo khóa/commit, không bảo đảm request đến mạng trước sẽ thắng. Khi chờ khóa qua giờ bắt đầu kèo, phải kiểm clock sau khi có khóa và từ chối thao tác không còn hợp lệ.

## 4. Matching: giảm thời gian giữ khóa mà giữ ngữ nghĩa

### 4.1. Bước an toàn đầu tiên

Tách hàm hiện có thành Strategy thuần; giữ cách sắp candidates và first-valid. Lọc sớm các ứng viên chắc chắn không thể hợp với người gọi bằng các điều kiện cần, sau đó vẫn kiểm toàn bộ group. Đo candidate count, số tổ hợp và thời gian strategy riêng khỏi thời gian DB.

Không tự thêm `LIMIT 100` vào candidate query: có thể bỏ mất nhóm hợp lệ ở phía sau và biến `suggestion=null` thành kết quả sai theo đặc tả hiện tại. Nếu muốn budget/top-K, phải công bố kết quả chưa tìm hết hoặc version contract, không coi đó chỉ là tối ưu nội bộ.

### 4.2. Phương án giảm transaction dài

Đề xuất sau khi có baseline:

1. Transaction ghi ngắn: khóa user, validate, thay request cũ, tạo request mới, commit.
2. Transaction đọc snapshot ngắn: đọc request cùng candidates/profile cần thiết, trả DTO snapshot rồi đóng transaction.
3. Chạy strategy ngoài transaction. Kết quả chỉ là gợi ý tại snapshot, có thể đã cũ ngay khi phản hồi; mọi xác nhận sau đó vẫn kiểm lại.

Trade-off: request đã được lưu nếu tính suggestion thất bại sau commit. Vì vậy **không triển khai cách này như refactor trong suốt**. Cần quyết định contract trước: giữ endpoint cũ với hành vi hiện tại và thêm phiên bản/job API mới, hoặc công bố lỗi có request ID để client lấy lại kết quả. Không trả `suggestion=null` khi timeout vì `null` hiện nghĩa là chưa đủ nhóm hợp lệ. Request bị thay thế/đóng trong lúc tính không được quảng bá như gợi ý còn hiệu lực; kiểm lại trước phản hồi hoặc trả trạng thái stale được đặc tả.

Nếu cần matching bất đồng bộ: API mới trả 202 + job ID, có endpoint đọc trạng thái `PENDING/RUNNING/SUCCEEDED/FAILED/EXPIRED`, deadline, retry và ownership. Đây là phạm vi sau, không mặc định đổi API `201` hiện hành.

## 5. Chuyển SQLite sang PostgreSQL

Không chỉ sửa `DATABASE_URL`. Các điểm phải xử lý ở pha triển khai:

- Engine/connection: bỏ PRAGMA và `check_same_thread` khỏi adapter PostgreSQL; cấu hình driver, pool, timeout, isolation và ánh xạ lỗi tương ứng. Không tái sử dụng nhận diện SQLite busy cho lỗi PostgreSQL.
- Partial unique index: giữ predicate cho active participation và active matching bằng cấu hình PostgreSQL tương ứng. `sqlite_where` không khai báo predicate cho PostgreSQL; index unique vô điều kiện sẽ làm mất khả năng giữ lịch sử nhiều lượt/request của cùng user.
- Boolean: CHECK `is_active IN (0, 1)` hiện tại gắn biểu diễn SQLite; PostgreSQL Boolean cần constraint phù hợp.
- Thời gian: chuyển `UTCDateTimeText` sang timestamp có timezone hoặc adapter theo dialect; parse dữ liệu UTC cũ, kiểm round-trip và biên nối tiếp. Không thay ý nghĩa timezone API.
- ID/sequence: sau import ID cũ phải đồng bộ sequence; kiểm foreign key và số bản ghi trước khi mở ghi.
- Migration: đưa schema vào migration versioned, ví dụ Alembic; seed chỉ thêm dữ liệu mẫu, không là công cụ nâng cấp schema.

Quy trình cutover đề xuất cho quy mô đồ án: backup nhất quán SQLite → tạm ngừng ghi → migrate schema mới → import theo thứ tự FK → kiểm row count, enum, index và invariant → smoke test → đổi cấu hình → mở ghi. Ghi lại thời gian downtime. Nếu đã có write mới ở PostgreSQL, quay lại bản SQLite cũ sẽ mất dữ liệu; rollback lúc đó phải có kế hoạch chuyển dữ liệu ngược hoặc sửa tiến, không chỉ đổi URL.

Chạy thử migration và restore trên bản sao trước. Không đòi zero downtime hoặc dual-write ở Phase 2. PostgreSQL là DB nghiệm thu chính sau cutover; SQLite có thể giữ cho demo cũ, nhưng test SQLite không thay test integration trên PostgreSQL.

## 6. Truy vấn và index

Giữ các index participation/session-status, participation/user-status và matching candidates đang có. Xem xét thêm index phục vụ `venues(district_code, is_active, id)`, `sessions(venue_id, starts_at, id)` và `sessions(host_user_id, starts_at, id)` theo query plan thực tế, thay vì tạo mọi tổ hợp bộ lọc.

Đo bằng kế hoạch truy vấn và dữ liệu có phân bố thực tế: số kèo/sân, tỷ lệ OPEN, số lượt lịch sử. Index làm tăng chi phí write và storage. `EXPLAIN ANALYZE` thực thi query nên chỉ dùng với query phù hợp trên môi trường thử nghiệm.

Giữ offset pagination để tương thích trước mắt. Khi offset sâu thành bottleneck, bổ sung cursor `(starts_at, id)` cho session và `id` cho venue qua contract rõ ràng. Không giả định cursor tự bảo đảm snapshot bất biến nếu dữ liệu nền thay đổi. `total` có thể là truy vấn đắt; chỉ đổi/bỏ trường này khi đã version API.

## 7. Retry và idempotency

Hiện DELETE cancel/withdraw có tính idempotent theo nghiệp vụ; create matching cố ý tạo bản mới khi gọi lặp. Không tự thay đổi các hành vi đó.

Đề xuất mở rộng `Idempotency-Key` cho create session và create matching để xử lý mất response sau commit. Key là tùy chọn hoặc thuộc phiên bản API mới; request không có key giữ hành vi cũ.

- Unique theo `(actor_id, operation, key)`; lưu fingerprint payload, resource ID, status và response cần replay trong cùng transaction mutation.
- Cùng key + cùng payload trả kết quả trước đó; khác payload trả conflict. Cạnh tranh cùng key phải được phân xử ở DB, không chỉ bằng bộ nhớ một process.
- Chỉ replay sau khi xác thực đúng actor; lưu response tối thiểu, không chứa token. Chính sách TTL đề xuất 24 giờ, công bố rõ replay sau TTL có thể tạo thao tác mới.
- Thiết kế rõ commit-unknown: client retry cùng key để tra kết quả. Không thêm retry tự động cho command chưa có cơ chế xác định kết quả.

## 8. Outbox cho notification, chỉ khi mở rộng chức năng

Transaction nghiệp vụ ghi thêm event `ParticipationApproved` hoặc `SessionCancelled` trong bảng outbox. Trường tối thiểu: event ID, type/version, aggregate ID, occurred_at, payload tối thiểu, attempts, next_attempt_at và trạng thái/lease xử lý.

Worker claim theo batch bằng cơ chế khóa/lease, commit việc claim rồi gọi provider ngoài transaction DB; thành công đánh dấu đã gửi, thất bại backoff có jitter và số lần tối đa. Lease hết hạn cho phép xử lý lại sau crash. Có danh sách failed để operator kiểm tra và replay có kiểm soát.

Delivery là **at-least-once**. Worker có thể crash sau khi provider đã gửi nhưng trước khi đánh dấu, nên event ID cần làm idempotency key phía provider nếu được hỗ trợ. Consumer nội bộ dùng inbox/unique event ID trong cùng transaction effect. Nếu provider không hỗ trợ deduplication, vẫn có nguy cơ thông báo trùng; không tuyên bố exactly-once.

Nếu approval và cancellation xảy ra nhanh, không gửi một thông báo “đã duyệt” lỗi thời sau thông báo hủy: giữ thứ tự theo aggregate hoặc kiểm version/trạng thái trước gửi và bỏ event đã bị thay thế. Theo dõi tuổi event cũ nhất, số retry và failed. Notification outage không rollback quyết định đã commit; lỗi insert outbox trong transaction thì rollback cả mutation để giữ tính atomic đã chọn.
