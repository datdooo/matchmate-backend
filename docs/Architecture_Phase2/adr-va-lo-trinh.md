# ADR đề xuất và lộ trình nghiệm thu

> Tất cả ADR bên dưới ở trạng thái **Proposed**. Chưa có quyết định triển khai nào được thực hiện trong lần cập nhật tài liệu này. Mã QA tham chiếu [đề xuất kiến trúc](de-xuat-kien-truc.md).

## ADR-01 - Modular monolith, phân lớp với dependency inversion

**Bối cảnh:** backend nhỏ, các nghiệp vụ kèo/lượt/matching có invariant cần cùng transaction; repo đã chia feature và có ports.

**Quyết định đề xuất:** giữ một deployable, xác lập Identity/Catalog/Sessions/Matching/Discovery; tách API, application, domain, adapter theo nhu cầu. Thực hiện bằng các bước nhỏ trên cấu trúc hiện tại trước khi đổi tên thư mục.

**Phương án khác:** giữ nguyên ba tầng hiện tại là ít công nhất nhưng chưa giải quyết coupling; service-based/microservices cho triển khai độc lập nhưng thêm giao tiếp mạng và consistency phân tán.

**Hệ quả:** dễ test/refactor, giữ ACID; vẫn triển khai toàn backend cùng nhau và chung failure domain. Ranh giới module cần test cưỡng chế vì DB dùng chung.

**Đánh giá lại khi:** module có nhu cầu scale độc lập được đo, nhóm sở hữu độc lập, hoặc release toàn backend trở thành trở ngại thực tế. QA-01, QA-03.

## ADR-02 - PostgreSQL cho tải ghi đồng thời, một DB chính

**Bối cảnh:** SQLite dùng `BEGIN IMMEDIATE` bảo vệ nhiều invariant bằng khóa writer toàn cục. ORM hiện tại vẫn chứa nhiều chi tiết SQLite.

**Quyết định đề xuất:** thử nghiệm PostgreSQL với khóa session/user như [thiết kế dữ liệu](du-lieu-va-nhat-quan.md); giữ SQLite làm baseline trước khi quyết định cutover.

**Phương án khác:** tiếp tục SQLite thích hợp demo ít write; WAL có thể cải thiện tương tác đọc/ghi nhưng không tạo nhiều writer đồng thời. Sharding/NoSQL làm các invariant liên bảng khó hơn, chưa có căn cứ chọn.

**Hệ quả:** thêm vận hành DB, migration, backup và concurrency tests; khả năng tăng throughput không tự động được bảo đảm. Chi phí khóa theo user và pool phải đo.

**Cổng chấp nhận:** QA-01 không vi phạm; migration bảo toàn dữ liệu; QA-02 cải thiện hoặc đạt mục tiêu với tài nguyên ghi rõ; restore drill đạt QA-05. Nếu chưa đạt, giữ baseline và sửa spike, không tuyên bố chuyển DB thành công.

## ADR-03 - Application use case sở hữu transaction

**Bối cảnh:** dependency và service hiện chia nhau quyền mở/commit UoW, router session biết adapter.

**Quyết định đề xuất:** dependencies chỉ lắp đối tượng; application service mở/commit/rollback; repository không commit. Password hash và external I/O ngoài transaction.

**Phương án khác:** decorator hoặc transaction middleware chung ít code lặp nhưng dễ tạo scope quá rộng, khó phân biệt query/command và che giấu ranh giới use case.

**Hệ quả:** entry point HTTP/CLI dùng cùng hành vi; cần cập nhật lỗi ưu tiên 422/503 đã mô tả, kiểm commit failure và thời điểm clock. QA-01, QA-03.

## ADR-04 - CQRS mức logic và matching Strategy

**Bối cảnh:** search đọc DTO, lifecycle bảo vệ invariant, matching thay đổi thuật toán có nhu cầu riêng.

**Quyết định đề xuất:** query/command khác code path nhưng chung PostgreSQL; Strategy mặc định giữ first-valid. Tối ưu matching trong transaction trước, chỉ chuyển tính toán ra ngoài sau khi chốt contract partial failure.

**Phương án khác:** read replica/materialized projection/event sourcing có thể scale đọc nhưng thêm lag, replay và vận hành. Thay bằng top-K ngay sẽ thay ngữ nghĩa kết quả.

**Hệ quả:** query adapter được tối ưu riêng; không tự có eventual consistency từ việc tách class. Có thêm interface strategy nhưng không cần plugin framework. QA-02, QA-03.

## ADR-05 - Ingress đơn giản, backend giữ kiểm quyền

**Bối cảnh:** JWT và object authorization đã có; rate limit/TLS ingress chưa được cấu hình trong repo khảo sát; danh sách protected route viết tay có nguy cơ bị bỏ sót khi mở rộng.

**Quyết định đề xuất:** reverse proxy cho TLS/limits, policy route rõ ràng và test coverage; backend kiểm token và quyền trên dữ liệu. Thêm telemetry có redaction.

**Phương án khác:** gateway platform/service mesh làm tăng thành phần vận hành, chưa cần cho một backend.

**Hệ quả:** thêm một hop và cấu hình tin cậy proxy; một ingress vẫn là SPOF. QA-04, QA-05.

## ADR-06 - Outbox có điều kiện; trì hoãn event sourcing/microservices

**Bối cảnh:** notification chưa thuộc Phase 1; commit DB rồi gửi bên ngoài có khoảng hở mất sự kiện.

**Quyết định đề xuất:** khi notification được đưa vào scope, thêm outbox và worker cùng codebase, DB-backed polling trước. Không chuyển invariant sức chứa/overlap/đóng matching sang xử lý event.

**Phương án khác:** callback sau commit đơn giản nhưng có thể mất việc; broker trực tiếp vẫn có dual-write gap; event sourcing đổi mô hình lưu trữ quá sâu.

**Hệ quả:** delivery at-least-once, cần dedup/lease/retry và giám sát backlog; chưa cần broker riêng. Không làm bước này nếu chỉ có thời gian cho phần cốt lõi.

## 1. Lộ trình triển khai sau khi chốt tài liệu

Các bước dưới đây là backlog tương lai, không phải các thay đổi đã thực hiện.

### M0 - Baseline và hợp đồng

- Chốt API/invariant hiện hành; đọc và chạy bộ test sẵn có khi bắt đầu triển khai.
- Chạy baseline SQLite theo workload đã định nghĩa, gồm matching no-solution; lưu commit, seed, môi trường, raw results và nhận xét.
- Bổ sung characterization tests cho priority lỗi, DELETE lặp, commit failure, request matching lặp và tính riêng tư của session detail trước refactor.
- Đầu ra: báo cáo baseline; không lấy số đo đọc-only làm bằng chứng chịu được write load.

### M1 - Chuẩn hóa ranh giới, chưa đổi DB

- Dời wiring khỏi router; chuẩn hóa UoW ownership; định nghĩa port profile và matching writer theo module.
- Tách matching use case/strategy khỏi discovery service; giữ API và thuật toán mặc định.
- Bổ sung test dependency graph/cycle và cross-module adapter imports. Giữ unit tests domain chạy với fake.
- Cổng nghiệm thu: regression suite qua; khác biệt 422/503 được ghi rõ; không đổi trạng thái/response ngoài các thay đổi đã đặc tả. Đây là mốc có thể demo độc lập.

### M2 - Spike PostgreSQL và migration

- Implement adapter, constraints theo dialect, migration versioned và import dữ liệu trên bản sao.
- Implement giao thức khóa; chạy concurrency suite với connection thật, thêm case tạo kèo đối đầu approve và create matching đối đầu approve.
- Kiểm thử migration từ DB có lịch sử rejected/cancelled/replaced, không chỉ DB rỗng.
- Cổng nghiệm thu: invariant giữ qua stress/race; tất cả row count và index predicate đúng; restore thành công. Không mở rộng API replicas trước mốc này.

### M3 - Đo và tối ưu hiệu năng

- So sánh baseline SQLite/PostgreSQL trên cùng dataset/ngân sách tài nguyên; không đổi DB, worker và thuật toán cùng lúc rồi gán toàn bộ cải thiện cho một yếu tố.
- Đo query plan, lock wait, transaction duration và candidate combinations; thêm index có căn cứ.
- Thử 1 và 2 API replicas, đặt tổng connection pool trong ngân sách DB; nếu không cải thiện thì tìm nút thắt thay vì tiếp tục tăng replicas.
- Chỉ đưa matching compute ra ngoài transaction nếu đã có quyết định contract ở M0/M1 hoặc một ADR bổ sung. Cắt candidate tùy tiện không được coi là tối ưu tương thích.
- Cổng nghiệm thu: QA-02, report cả số đo không đạt và giới hạn thử nghiệm.

### M4 - Bảo vệ biên và vận hành

- Thêm ingress, rate limit, route auth policy coverage, readiness và structured logs/metrics.
- CI chạy unit + integration PostgreSQL + kiến trúc + lint; build image và smoke test migration/startup. Dùng image cùng digest cho staging/release.
- Thiết kế migration chạy một job trước rollout, không để mỗi API replica tự migrate khi boot. Thay đổi schema ưu tiên mở rộng tương thích rồi dọn bỏ ở release sau.
- Diễn tập mất DB, restart API, restore backup và rollback ứng dụng tương thích schema. Cổng: QA-04/QA-05.

### M5 - Mở rộng theo bằng chứng sau transaction và PostgreSQL

- Lộ trình thiết kế đã được người dùng đồng ý; chưa triển khai. Điều kiện và cách đánh giá chi tiết ở [mục 4.4 của đề xuất kiến trúc](de-xuat-kien-truc.md#44-lộ-trình-mở-rộng-sau-transaction-và-postgresql).
- Đo lại trên cùng Kaggle CPU sau cải tiến transaction/PostgreSQL để xác định nút thắt mới.
- Thử Redis khi đọc lặp là nút thắt; kiểm cache lạnh/nóng, invalidation và fallback.
- Thêm outbox + worker khi có notification hoặc công việc phù hợp bất đồng bộ; thử crash trước/sau gửi, duplicate và replay event. Bổ sung idempotency key cho command cần retry qua mạng.
- Cô lập matching thành worker/process riêng khi CPU matching ảnh hưởng API; chốt contract trước nếu đổi sang job bất đồng bộ, đo cả thời gian có kết quả.
- Chỉ xét microservices, Kafka, Kubernetes hoặc sharding khi có nhu cầu và bằng chứng tương ứng; viết ADR riêng trước khi triển khai.
- Cổng nghiệm thu từng nhánh: có baseline và kết quả trước/sau trên cùng ngân sách tài nguyên, đạt mục tiêu cụ thể, không vi phạm invariant, ghi rõ chi phí vận hành và phương án bỏ thay đổi nếu không có lợi. Không yêu cầu thực hiện mọi nhánh.

**Phạm vi tối thiểu nên hoàn thành cho Phase 2:** M0–M4; M5 là tùy chọn. Nếu thời gian hạn chế, giảm chức năng mới, giữ việc chứng minh transaction, module boundary và đo trước/sau.

## 2. Bộ tình huống nghiệm thu cần có

- Hai approvals tranh một chỗ; một user vào hai kèo chồng; approve đối đầu withdraw/cancel; create session đối đầu approve của cùng user; create matching đối đầu lịch được xác nhận.
- Khóa chờ qua giờ bắt đầu; lock timeout; commit lỗi; exception sau ghi participation nhưng trước đóng matching; mỗi trường hợp không để trạng thái nửa chừng.
- Cancel lặp, withdraw lặp, matching tạo lặp không key; request có cùng key/different payload nếu đã triển khai idempotency.
- Hồ sơ hiện tại thay đổi so với snapshot: approval dùng hồ sơ hiện tại để eligibility nhưng giữ quoted fee/gender snapshot. Nếu bổ sung API cập nhật hồ sơ, nó phải tham gia giao thức khóa user.
- Người ngoài không xem `management`, không duyệt/hủy kèo của người khác; log/error không chứa secret; route mới thiếu auth policy phải bị phát hiện trong CI.
- Read DTO không có ORM object hoặc lazy load sau transaction; multi-query response không trộn snapshot nếu yêu cầu nhất quán.
- Migration với nhiều lượt lịch sử cùng user/session; nhiều matching đã CLOSED; Boolean/timezone/sequence và partial index đúng trên DB đích.
- Matching: không candidates, thiếu người, không có tổ hợp hợp lệ, nhiều nhóm hợp lệ và tie-break deterministic. Strategy tối ưu phải cho cùng kết quả strategy baseline trên corpus cố định.
- Nếu có outbox: provider timeout, worker crash sau gửi, lease hết hạn, duplicate event, cancellation sau approval, backlog phục hồi và failed-event replay.

## 3. Demo kiến trúc có bằng chứng

1. Trình bày sơ đồ module, dependency direction và một violation bị architecture test bắt.
2. Chạy luồng tạo kèo → xin → duyệt; chạy race tranh chỗ và race lịch chồng, kiểm dữ liệu sau commit.
3. Thay strategy trong test/composition root để chứng minh router không phụ thuộc thuật toán; giữ strategy mặc định khi demo API hiện hành.
4. So sánh đồ thị/đầu ra benchmark trước và sau, có cùng workload, config và lỗi; chỉ kết luận trong phạm vi đo.
5. Làm DB unavailable để thấy readiness và lỗi có kiểm soát, rồi restore bản backup vào DB thử nghiệm.
6. Chỉ demo worker/outbox nếu đã triển khai; không vẽ thành phần tùy chọn như hệ thống đang chạy.

## 4. Các điểm cần chốt trước triển khai

- Ngân sách máy, tải mục tiêu, dữ liệu benchmark và thời gian dành cho Phase 2; hiện dùng giả định ghi trong QA.
- PostgreSQL là đích triển khai chính hay chỉ spike so sánh; có cần duy trì hỗ trợ hai DB dài hạn hay không.
- Có chấp nhận đổi ưu tiên 422/503 khi chuẩn hóa UoW và version API nếu matching tách computation khỏi commit không.
- Notification/idempotency có thuộc phạm vi nộp bài hay để pha sau; chưa có yêu cầu nên không đưa vào phần bắt buộc.
- Chọn RPO/RTO và nơi lưu backup theo ngân sách; một máy Compose không đạt mục tiêu chịu lỗi mất host nếu không có nơi phục hồi.

Các câu hỏi này không cản việc hoàn thành tài liệu đề xuất. Chúng là đầu vào cần xác nhận khi bắt đầu thay đổi hệ thống.
