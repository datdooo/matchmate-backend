# Đối chiếu hiệu năng Phase 1 với yêu cầu Phase 2

## 1. Kết luận và phạm vi bằng chứng

Modular monolith và dependency inversion chủ yếu cải thiện khả năng thay đổi/kiểm thử, không tự tăng throughput. Các cải tiến có giả thuyết hiệu năng cụ thể là transaction ngắn, giảm tranh chấp writer, persistence PostgreSQL với khóa theo tài nguyên, tối ưu query và matching. Mỗi thay đổi phải đo riêng trên cùng phần cứng Kaggle CPU.

Đã đọc dữ liệu trong Git local tại commit lưu báo cáo `5b9be9fb939de41965eb1f6b290be2b60ea4d28c`, thư mục `docs/load/kaggle-2026-10-29`: run-summary, environment, CSV read-100/lifecycle-10, metadata và log lifecycle-50/100. Có thể xem lại bằng `git show <commit>:<path>` mà không checkout hoặc sửa code.

**Commit thực sự được benchmark là `859df1345a6d5034d2202823232f219f34f87ab4`, không phải HEAD hiện tại `fe71760`.** Có thay đổi application và runner sau commit đó. Vì vậy đây là bằng chứng lịch sử để định hướng, chưa phải baseline đo lại của code hiện tại.

Nguồn xem trên GitHub: [run-summary](https://github.com/datdooo/matchmate-backend/blob/5b9be9fb939de41965eb1f6b290be2b60ea4d28c/docs/load/kaggle-2026-10-29/run-summary.json), [log 50 user](https://github.com/datdooo/matchmate-backend/blob/5b9be9fb939de41965eb1f6b290be2b60ea4d28c/docs/load/kaggle-2026-10-29/locust-lifecycle-50u.log), [log 100 user](https://github.com/datdooo/matchmate-backend/blob/5b9be9fb939de41965eb1f6b290be2b60ea4d28c/docs/load/kaggle-2026-10-29/locust-lifecycle-100u.log). Các file được đọc từ Git local, không chạy benchmark mới trong lần cập nhật này.

## 2. Số liệu đã đo thành công

- Read 10 virtual users: 393 request, 6,59 request/s, p95 14 ms, p99 34 ms, 0 failure.
- Read 50 virtual users: 1.963 request, 32,91 request/s, p95 32 ms, p99 54 ms, 0 failure.
- Read 100 virtual users: 3.864 request, 65,25 request/s, p95 100 ms, p99 180 ms, 0 failure.
- Lifecycle 10 virtual users: 1.719 request, 28,79 request/s, p95 120 ms, p99 270 ms, 0 failure. Đây là workload gồm nhiều bước ghi và GET detail, không phải toàn bộ request đều là ghi.

Các invariant được kiểm sau lượt chạy đều có số vi phạm bằng 0. Điều này không chứng minh đúng cho mọi race hoặc chứng minh hệ thống chịu được 100 user ghi.

Runner dùng warm-up 15 giây, đo 60 giây, Locust wait time 1–2 giây giữa task. Read throughput tăng theo số virtual users; 65,25 request/s là throughput đạt được ở workload đó, **không phải throughput tối đa đã tìm ra**. Login bị loại khỏi cửa sổ đo thành công. Các profile này không cung cấp benchmark tải matching riêng.

## 3. Hai lượt lifecycle không hoàn tất

### 50 virtual users

Metadata ghi 50 user sẵn sàng, 100 actor accounts, `measurement_complete=false`, `measurement_seconds=0`. Log warm-up có 217 request, gồm 100 login, với 27 failure: 22 POST sessions, 4 POST participations và 1 decision, đều HTTP 503. POST sessions trong phần log này có độ trễ trung bình khoảng 5,9 giây.

Runner dừng nếu warm-up có failure nên không bước vào cửa sổ đo. `errors={}` chỉ phản ánh bộ đếm ngoài cửa sổ đo, không có nghĩa toàn lượt chạy không lỗi. Đây là bằng chứng suy giảm nghiêm trọng khi tải lifecycle tăng, nhưng không được lấy throughput/p95 warm-up làm kết quả đo ổn định để so với lượt thành công.

SQLite writer contention là giả thuyết mạnh vì code dùng `BEGIN IMMEDIATE`, busy timeout 5 giây và trả 503 cho DB busy. Log chỉ ghi HTTP status, chưa có lock-wait tracing/error body để quy toàn bộ nguyên nhân về DB. Cần đo thêm thời gian chờ khóa, pool/thread wait và CPU để phân biệt nguyên nhân.

### 100 virtual users

Metadata ghi chỉ 42 lifecycle users hoàn tất chuẩn bị (mỗi user cần hai tài khoản), không có cửa sổ đo. Log cuối có 102 login request, một `HTTP_0` khoảng 20 giây; không phải lỗi HTTP 0 do server trả, mà là failure ở client/transport. Có lỗi Locust/greenlet khi shutdown và ghi CSV đã đóng.

Chưa có số liệu lifecycle 100 user để kết luận SQLite thất bại ở workload này. Argon2, tải khởi tạo đăng nhập và tài nguyên runner/API là các giả thuyết cần kiểm chứng, không phải root cause đã xác nhận. Không giảm độ an toàn password hashing chỉ để đạt benchmark.

## 4. Điều chỉnh ưu tiên kiến trúc

1. **Chuẩn hóa transaction ngắn và profiling:** giữ tính đúng, đưa hashing/external I/O ra khỏi write transaction; đo thời gian khóa. Refactor phân lớp riêng có thể không tăng tốc.
2. **Thử PostgreSQL với giao thức khóa session/user:** nhắm vào suy giảm lifecycle-50 và writer toàn DB. Đổi DB có thể thêm overhead trên dữ liệu nhỏ; chỉ chọn vì hiệu năng khi kết quả thực nghiệm ủng hộ và invariant vẫn đúng.
3. **Tối ưu truy vấn/index sau query plan:** read hiện chưa có lỗi tới 100 user; chưa có căn cứ thêm Redis/read replicas ngay. Cần dataset lớn hơn trước khi kết luận query đã tối ưu.
4. **Strategy và tối ưu matching:** cần vì code xét tổ hợp trong transaction, nhưng báo cáo cũ chưa đo endpoint này; tạo baseline matching trước khi nhận công cải thiện.
5. **Tách bootstrap login khỏi bài đo lifecycle:** cấp token tuần tự hoặc concurrency có giới hạn ngoài thời gian đo, giống nhau cho baseline và bản cải tiến; có bài đo login riêng để không che giấu vấn đề xác thực.
6. **Rate limiting là bảo vệ quá tải:** báo 429 riêng, không tính request bị chặn thành throughput nghiệp vụ thành công. Thêm proxy/outbox không tự làm API nhanh hơn.

## 5. Thiết kế so sánh đúng yêu cầu pha 2

Yêu cầu được người dùng cung cấp: đánh giá trước/sau, giải thích cải tiến và đo trên một cấu hình phần cứng cố định, ưu tiên Kaggle CPU. **Điều này thay giả định trước đó về máy phát tải riêng và cấu hình 4 vCPU/8 GiB trong tài liệu đề xuất.**

Môi trường cũ báo 4 CPU, RAM hệ thống khoảng 31,35 GiB, cgroup CPU quota tương đương 4 CPU và memory limit 30 GiB, một Uvicorn worker; Python 3.13.15. Lần đo mới phải ghi CPU model/quota, RAM limit, storage và dependency versions thực tế, không giả định mọi Kaggle session giống hệt nhau. Chạy A/B trong cùng Kaggle session là ưu tiên; API, DB và Locust cùng chia sẻ ngân sách máy, đo CPU/RAM từng process để phát hiện load generator trở thành bottleneck.

Các biến thể đề xuất:

- A: HEAD hiện tại với SQLite, giữ nguyên hành vi.
- B: chỉ chuẩn hóa module/transaction, SQLite; tách lợi ích maintainability khỏi hiệu năng.
- C: cùng workload, PostgreSQL và khóa đúng invariant; giữ số API worker như B.
- D: tối ưu query/matching đã được chọn từ profiling; thay từng yếu tố để đo ảnh hưởng.
- Nếu thử tăng worker, làm thêm biến thể riêng trên cùng CPU/RAM tổng, không cấp thêm máy/tài nguyên cho bản cải tiến.

Giữ cùng seed, số record, phân bố dữ liệu, user/spawn rate, think time, thời gian tương đối tới lịch chơi, phiên bản thư viện và cửa sổ đo giữa các biến thể. Tạo DB mới trước mỗi lượt; không để lifecycle tích lũy lịch sử làm lượt sau nặng hơn. Giữ 10/50/100 user để đối chiếu; bổ sung dataset lớn và matching 10/50/100/200 candidates như bài đo riêng.

Chạy warm-up và measurement giống nhau cho mọi biến thể, đề xuất 2 phút + 10 phút và ít nhất 3 lần, đổi thứ tự A/B giữa các lần để giảm ảnh hưởng môi trường. Nếu baseline không qua warm-up, ghi rõ failed case; có thể thiết kế thêm bài stress thu số liệu lỗi xuyên suốt, nhưng phải áp dụng runner mới cho cả A và B, không trộn với báo cáo cũ.

Đầu ra bắt buộc: completion status, successful throughput, p50/p95/p99, 5xx/429/timeout, CPU/RAM, lock wait/transaction duration, query count và invariant violations. Chỉ tính phần trăm cải thiện cho cùng workload và lượt đo hợp lệ. Với baseline không hoàn tất, kết luận phù hợp là “bản cải tiến hoàn tất workload mà baseline chưa hoàn tất”, không suy ra nhanh hơn một hệ số từ aggregate rỗng.

Mục tiêu quan trọng nhất cho đồ án: lifecycle 50/100 user hoàn tất ổn định, lỗi hạ tầng giảm, không mất invariant; sau đó mới tối ưu latency. Các mục tiêu p95 định lượng trước đó vẫn là ngưỡng thử nghiệm, cần hiệu chỉnh theo baseline Kaggle mới.
