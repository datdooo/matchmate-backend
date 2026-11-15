# Architecture Phase 2 - MatchMate

Tài liệu đề xuất ngày 15/11/2026, dựa trên code hiện tại và chín PDF bài giảng trong thư mục này. **Chỉ là thiết kế đề xuất; chưa triển khai thay đổi code, schema hay hạ tầng.**

## Thứ tự đọc

0. [Đánh giá hiệu năng và yêu cầu Kaggle](danh-gia-hieu-nang-baseline.md): bằng chứng từ báo cáo cũ, giới hạn số liệu và điều chỉnh kế hoạch đo theo yêu cầu Phase 2. Quy định môi trường đo ở đây thay giả định phần cứng ban đầu trong đề xuất.

1. [Đề xuất kiến trúc](de-xuat-kien-truc.md): hiện trạng, mục tiêu chất lượng, ranh giới module, các view kiến trúc và lựa chọn design pattern.
2. [Thiết kế dữ liệu và tính nhất quán](du-lieu-va-nhat-quan.md): transaction, concurrency, matching, migration và cơ chế xử lý lỗi.
3. [ADR và lộ trình nghiệm thu](adr-va-lo-trinh.md): quyết định đề xuất, thứ tự triển khai, tiêu chí kiểm chứng và nội dung demo.

## Kết luận định hướng

Tiến hóa kiến trúc hiện tại thành **modular monolith với các lớp API / application / domain / infrastructure và dependency inversion**. Giữ một đơn vị triển khai nghiệp vụ, chuẩn hóa Repository + Unit of Work, tách query khỏi command ở mức code, và dùng Strategy cho thuật toán matching. PostgreSQL là đích đề xuất cho thử nghiệm tải ghi đồng thời; SQLite tiếp tục là baseline Phase 1.

Repo đã có phân lớp, Protocol, Repository, Unit of Work, mapper và dependency injection. Vì vậy Phase 2 là hoàn thiện và kiểm chứng kiến trúc, không phải bắt đầu từ một hệ thống hoàn toàn chưa có pattern.

Thông báo bất đồng bộ với transactional outbox là phần mở rộng có điều kiện. Microservices, Kafka, Kubernetes, sharding và event sourcing chưa nằm trong phạm vi cốt lõi.

[Lộ trình mở rộng đã thống nhất](de-xuat-kien-truc.md#44-lộ-trình-mở-rộng-sau-transaction-và-postgresql): sau transaction/PostgreSQL, đo lại → thử Redis nếu đọc lặp là nút thắt → thêm outbox/worker khi có công việc bất đồng bộ → cô lập matching nếu CPU ảnh hưởng API → chỉ xét kiến trúc phân tán khi có bằng chứng và nhu cầu phù hợp. Đây là các nhánh có điều kiện, không phải yêu cầu thêm toàn bộ công nghệ.

Các mục tiêu hiệu năng trong bộ tài liệu là **ngưỡng đề xuất để đo**, không phải kết quả benchmark. Các đường dẫn code là bằng chứng đọc tĩnh, không hàm ý đã chạy test trong lần soạn tài liệu này.
