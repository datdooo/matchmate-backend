# Kế hoạch triển khai MatchMate giai đoạn 2

**Nhóm 3 người · Khởi động thứ Hai, ngày 16 tháng 11 năm 2026 · Hạn hoàn thành triển khai: thứ Sáu, ngày 27 tháng 11 năm 2026 lúc 17:00 giờ Việt Nam (UTC+7).**

Nhóm sẽ bàn giao một ứng dụng nguyên khối mô-đun có thể triển khai như một đơn vị duy nhất, quy trình di chuyển sang PostgreSQL đã được kiểm thử và một bản triển khai demo qua HTTPS kèm bằng chứng về tính nhất quán, kiểm soát truy cập và khả năng khôi phục. **Thứ Sáu, ngày 20 tháng 11** là mốc kiểm tra tuần đầu cho việc tái cấu trúc trên SQLite và chạy thử di chuyển sang PostgreSQL. Cả ba thành viên sẽ cùng đo kiểm hiệu năng sau khi tích hợp.

## Phân công phụ trách

| Người phụ trách | Mảng công việc | Kết quả bàn giao |
| --- | --- | --- |
| **Thành viên 1** | **Kiến trúc ứng dụng của Identity và Sessions** | Phụ trách ranh giới Unit of Work, giao diện hồ sơ của Identity, các chính sách vòng đời và cơ chế khóa của Sessions, cùng việc phân quyền ở cấp tuyến API và đối tượng. Gọi thành phần ghi của Matching thông qua một cổng trong cùng giao dịch với thao tác tạo phiên chơi hoặc phê duyệt. |
| **Thành viên 2** | **Lưu trữ dữ liệu, triển khai và khôi phục** | Phụ trách các bộ điều hợp SQLAlchemy, ràng buộc đặc thù theo hệ quản trị cơ sở dữ liệu, các thao tác khóa nền tảng, di chuyển có quản lý phiên bản, nhập dữ liệu lịch sử, CI cho PostgreSQL, cấu trúc triển khai Compose, kiểm tra trạng thái sẵn sàng và sao lưu/khôi phục. |
| **Thành viên 3** | **Kiến trúc Catalog, Matching và Discovery** | Phụ trách quyền sở hữu dữ liệu địa điểm và các hợp đồng đọc, Strategy chọn nhóm hợp lệ đầu tiên, bộ điều hợp ghi của Matching, tách biệt đọc/lệnh và các kiểm thử ranh giới mô-đun. Phụ trách cấu hình cổng vào và dữ liệu quan trắc yêu cầu cho bản demo. |

## Phạm vi kiến trúc và trách nhiệm

| Nội dung đề xuất | Cách áp dụng dự kiến trong MatchMate | Người phụ trách và mốc kiểm tra |
| --- | --- | --- |
| **§3.1–3.4 · Mô-đun, tầng và quan hệ phụ thuộc** | Identity sở hữu tài khoản, thông tin xác thực, token và DTO tối thiểu của `PlayerProfileReader`. Catalog sở hữu địa điểm và trạng thái hoạt động. Sessions sở hữu lượt đặt chỗ và lượt tham gia. Matching sở hữu yêu cầu ghép nhóm và việc chọn nhóm. Discovery cung cấp tìm kiếm địa điểm/phiên chơi qua một giao diện đọc thống nhất. Mỗi mô-đun tách trách nhiệm API, ứng dụng, miền nghiệp vụ và hạ tầng khi cần. Điểm khởi tạo và kết nối phụ thuộc (composition root) nối các bộ điều hợp vào các cổng. | Thành viên 1 phụ trách Identity, Sessions và kết nối phụ thuộc. Thành viên 3 phụ trách Catalog, Matching, Discovery và kiểm thử các lệnh import. Rà soát ngày **20/11**. |
| **§4.1 · Repository, Unit of Work, Data Mapper, Strategy và Policy** | Các ca sử dụng kiểm soát commit/rollback và tương tác qua các cổng kho dữ liệu hướng nghiệp vụ. SQLAlchemy chỉ nằm trong các bộ điều hợp; các bộ ánh xạ trả về đối tượng miền nghiệp vụ hoặc DTO. Sessions sử dụng giới hạn kỹ năng do chủ phiên đặt và điều kiện đủ tư cách tham gia. Matching sử dụng độ chênh lệch trình độ và ngân sách của nhóm, đồng thời giữ cách chọn nhóm hợp lệ đầu tiên. | Thành viên 1 phụ trách ca sử dụng và chính sách Sessions, Thành viên 2 phụ trách lưu trữ/ánh xạ, Thành viên 3 phụ trách chính sách và Strategy của Matching. Xác minh luồng SQLite ngày **20/11** và PostgreSQL ngày **24/11**. |
| **§4.1 · CQRS ở mức logic** | Tách ca sử dụng ghi khỏi các bộ điều hợp đọc trên cùng cơ sở dữ liệu. Tìm kiếm/chi tiết trả về DTO. Mã truy vấn có thể kết hợp dữ liệu của các mô-đun qua các hợp đồng đọc đã thống nhất. Các luồng đọc cần ảnh chụp dữ liệu nhất quán sử dụng một câu lệnh hoặc một giao dịch ảnh chụp được thiết lập tường minh. | Thành viên 1 và 3 lần lượt phụ trách luồng đọc chi tiết Sessions và Discovery. Xác minh hợp đồng và tính nhất quán của ảnh chụp dữ liệu chậm nhất ngày **24/11**. |
| **§3.3 và §5 · Triển khai, Gatekeeper và vận hành** | Chạy theo mô hình reverse proxy HTTPS → một API → PostgreSQL. Đặt API, cơ sở dữ liệu và hệ thống số liệu giám sát trên các mạng riêng. Chạy di chuyển một lần trước khi triển khai phiên bản. Tách kiểm tra tiến trình còn hoạt động khỏi kiểm tra cơ sở dữ liệu sẵn sàng; trình diễn giới hạn tần suất, quan trắc và khôi phục. | Thành viên 2 phụ trách triển khai, CI và khôi phục. Thành viên 3 phụ trách cổng vào và quan trắc. Thành viên 1 phụ trách chính sách xác thực/phân quyền ở backend. Trình diễn chậm nhất ngày **27/11**. |
| **§4.2–4.4 · Mở rộng dựa trên bằng chứng** | Xem xét lại Redis nếu các lượt đọc lặp lại chiếm ưu thế. Cân nhắc outbox kết hợp tiến trình xử lý nền khi thông báo được đưa vào phạm vi, hoặc tách tiến trình Matching khi phân tích hiệu năng cho thấy áp lực CPU. Các phương án phân tán cần bằng chứng và quyết định riêng. | Cả ba cùng rà soát sau đợt đo kiểm hiệu năng chung. |

## Giai đoạn 1 · Hợp đồng và kiểm thử hồi quy · Ngày 16–17 tháng 11

**Thành viên 1 — Giao dịch ở tầng ứng dụng**

- [ ] Lần theo các vị trí bắt đầu và commit giao dịch hiện tại trong Auth và Sessions. Liệt kê các lệnh vòng đời và các bất biến mà từng lệnh phải bảo toàn.
- [ ] Chạy các kiểm thử vòng đời và Auth hiện có. Ghi nhận phản hồi mong đợi cho dữ liệu đầu vào không hợp lệ, người gọi chưa xác thực, yêu cầu trùng lặp và thao tác rút tham gia/hủy lặp lại. Xác định những chỗ cần kiểm thử hồi quy cho lỗi commit.
- [ ] Thống nhất với Thành viên 2 về Unit of Work và các thao tác khóa phiên chơi, người dùng. Phụ trách hợp đồng dành cho tầng ứng dụng trong `app/domain/ports.py` và các hợp đồng của Sessions.
- [ ] Thống kê các thành phần sử dụng hồ sơ của Identity và các quy tắc truy cập tuyến API hiện có, bao gồm tìm kiếm công khai có chế độ dành cho người đã xác thực. Thống nhất với Thành viên 3 về DTO hồ sơ và hợp đồng trạng thái địa điểm của Catalog mà Sessions cần.

**Thành viên 2 — Lưu trữ trên PostgreSQL**

- [ ] Kiểm tra `app/db/session.py`, `models.py`, `types.py` và `unit_of_work.py`. Liệt kê các thiết lập engine riêng cho SQLite, kiểu dấu thời gian, ràng buộc kiểm tra Boolean và chỉ mục có điều kiện cần có bản tương đương trên PostgreSQL.
- [ ] Khởi chạy một PostgreSQL cục bộ. Chuẩn bị bản sao SQLite có các lượt tham gia đã được chấp nhận, dữ liệu tham gia lịch sử và các yêu cầu ghép nhóm đã bị thay thế. Ghi lại số lượng bản ghi dự kiến và các giá trị tiêu biểu để xác minh việc nhập dữ liệu.
- [ ] Thống nhất thao tác nào cần khóa hàng, cách bộ điều hợp biểu diễn lỗi hết thời gian chờ khóa và cách kiểm thử lấy các kết nối cơ sở dữ liệu độc lập.
- [ ] Phác thảo cấu trúc triển khai Compose và tác vụ di chuyển chạy một lần. Chọn nơi lưu bản sao lưu demo nằm ngoài volume/máy chủ ứng dụng và ghi lại các mục tiêu khôi phục mà nhóm sẽ kiểm thử.

**Thành viên 3 — Matching và Discovery**

- [ ] Lần theo lệnh tạo yêu cầu ghép nhóm và các truy vấn đọc địa điểm/phiên chơi trong `app/features/discovery/`. Ghi lại phản hồi endpoint hiện tại, thứ tự ứng viên, cách xử lý khi đồng hạng, hành vi thay thế và quy tắc riêng tư của thông tin chi tiết phiên chơi.
- [ ] Chuẩn bị các trường hợp ghép nhóm: không có ứng viên, quá ít ứng viên, không có nhóm hợp lệ và có nhiều nhóm hợp lệ. Thống nhất với Thành viên 1 về cổng đóng các yêu cầu chồng lấn trong Unit of Work của bên gọi.
- [ ] Xác định dữ liệu địa điểm thuộc Catalog và các phép kết hợp dữ liệu mà Discovery được phép thực hiện khi đọc. Thống nhất với Thành viên 2 về điểm vào hệ thống, các mạng riêng và các trường dữ liệu quan trắc cần cho đo kiểm hiệu năng.

**Bàn giao ngày 17 tháng 11.** Ghi lại commit khởi điểm, hành vi mong đợi và các giao diện Unit of Work, khóa, thành phần ghi của Matching đã thống nhất. Sau đó, Thành viên 1 và 3 có thể tái cấu trúc trên SQLite trong khi Thành viên 2 xây dựng bộ điều hợp cơ sở dữ liệu.

## Giai đoạn 2 · Tái cấu trúc trên SQLite và chạy thử di chuyển sang PostgreSQL · Ngày 18–20 tháng 11

**Thành viên 1 — Giao dịch ở tầng ứng dụng**

- [ ] Đưa việc khởi tạo bộ điều hợp ra khỏi router của Sessions. Để ca sử dụng ở tầng ứng dụng mở và commit Unit of Work của chính nó; các thành phần cung cấp phụ thuộc chịu trách nhiệm kết nối. Bảo đảm lỗi commit được truyền lên dưới dạng lỗi và các thay đổi được rollback.
- [ ] Đưa việc băm và xác minh mật khẩu ra ngoài các giao dịch cơ sở dữ liệu tương ứng. Giữ nguyên thứ tự ưu tiên xác thực và ghi lại mọi thay đổi đã thống nhất về thứ tự ưu tiên 422/503 sau khi chuyển việc kiểm tra đầu vào lên trước giao dịch ghi.
- [ ] Xác minh việc tạo phiên chơi vẫn tạo lượt tham gia đã được chấp nhận cho chủ phiên, phê duyệt vẫn giữ các giá trị phí và giới tính đã chụp tại thời điểm liên quan, và thao tác hủy/rút tham gia lặp lại vẫn giữ hành vi hiện tại. Kết nối thao tác tạo và phê duyệt với thành phần ghi của Matching qua cổng đã thống nhất.
- [ ] Cung cấp `PlayerProfileReader` tối thiểu từ Identity để Sessions và Matching sử dụng DTO hồ sơ không chứa trường thông tin xác thực. Kết nối thành phần này, `Clock` và các bộ điều hợp kho dữ liệu tại composition root. Tách các quy tắc đủ tư cách tham gia và chuyển trạng thái của Sessions, đồng thời kiểm thử đơn vị bằng các đối tượng giả khi hữu ích.
- [ ] Tách luồng đọc chi tiết Sessions khỏi các lệnh vòng đời. Giữ nguyên `management` chỉ dành cho chủ phiên và `my_participations` riêng cho từng người xem. Khai báo chính sách truy cập công khai/được bảo vệ cho các tuyến API và kiểm thử hành vi xác thực có điều kiện.

**Thành viên 2 — Lưu trữ trên PostgreSQL**

- [ ] Bổ sung cấu hình kết nối PostgreSQL và các bản di chuyển lược đồ có quản lý phiên bản. Chuyển đổi cách xử lý dấu thời gian, Boolean, khóa ngoại và các điều kiện bảo đảm tính duy nhất cho lượt tham gia và yêu cầu ghép nhóm đang hoạt động.
- [ ] Nhập một bản sao SQLite theo thứ tự phụ thuộc khóa ngoại, giữ nguyên ID và lịch sử, đồng thời điều chỉnh các sequence vượt quá giá trị đã nhập. So sánh số lượng bản ghi và kiểm tra mẫu dấu thời gian, trạng thái, bản ghi lịch sử.
- [ ] Chuẩn bị bộ thiết lập dữ liệu và môi trường kiểm thử PostgreSQL thực, triển khai các thao tác khóa nền tảng theo hợp đồng đã thống nhất. Cung cấp lệnh khởi động và di chuyển cho các thành viên khác.
- [ ] Giữ truy vấn và khóa hàng trong các bộ điều hợp lưu trữ. Tái sử dụng bộ ánh xạ để trả về giá trị miền nghiệp vụ và DTO; cấu hình giới hạn nhóm kết nối cùng thời gian chờ lấy kết nối, khóa và câu lệnh, với cách xử lý lỗi phù hợp cho từng hệ quản trị.

**Thành viên 3 — Matching và Discovery**

- [ ] Tách Strategy chọn nhóm hợp lệ đầu tiên thành hàm hoặc lớp thuần túy với thứ tự ứng viên xác định. Dùng các trường hợp ở Giai đoạn 1 để xác minh nhóm được chọn và các phản hồi không tìm được nhóm vẫn như cũ.
- [ ] Tách mã thay đổi dữ liệu ghép nhóm khỏi luồng đọc của Discovery. Cung cấp bản triển khai thành phần ghi của Matching sử dụng giao dịch của bên gọi. Xác minh DTO và hành vi riêng tư của Discovery.
- [ ] Mở rộng `tests/test_architecture.py` để kiểm tra hướng phụ thuộc, chu trình giữa các mô-đun và việc import trực tiếp bộ điều hợp nội bộ của mô-đun khác.
- [ ] Đưa quyền sở hữu địa điểm và việc truy cập trạng thái hoạt động ra sau hợp đồng của Catalog. Giữ các phép kết hợp dữ liệu tìm kiếm và ánh xạ DTO của Discovery trong bộ điều hợp đọc; xác minh bộ lọc, phân trang và tính tương thích của phản hồi. Giữ kiểm thử độ chênh lệch trình độ và ngân sách nhóm tách biệt với kiểm thử điều kiện tham gia của Sessions.
- [ ] Soạn cấu hình reverse proxy cho TLS cục bộ, giới hạn kích thước nội dung yêu cầu, thời gian chờ yêu cầu và giới hạn tần suất. Lập phương án thực thi các giới hạn theo người dùng đã xác thực hoặc định danh tài khoản đã chuẩn hóa bằng dữ liệu được backend xác minh.

**Mốc kiểm tra ngày 20 tháng 11.** Demo luồng tạo → tham gia → phê duyệt và ghép nhóm trên bản SQLite đã tái cấu trúc. Trình bày các kiểm thử Strategy của Matching và kết quả kiểm tra nhập thử dữ liệu vào PostgreSQL. Ghi lại commit SQLite đã tái cấu trúc này để đo kiểm hiệu năng sau đó.

## Giai đoạn 3 · Tích hợp PostgreSQL · Ngày 23–24 tháng 11

**Thành viên 1 — Giao dịch ở tầng ứng dụng**

- [ ] Tích hợp khóa vào thao tác tham gia, phê duyệt/từ chối và rút tham gia theo thứ tự phiên chơi trước, người dùng sau. Khi hủy, lấy khóa phiên chơi trước, rồi khóa các người dùng bị ảnh hưởng theo ID tăng dần. Khi tạo, khóa người dùng là chủ phiên trước khi kiểm tra trùng lịch và thêm phiên chơi mới.
- [ ] Đọc lại thời gian và trạng thái cơ sở dữ liệu liên quan sau khi lấy khóa. Kiểm tra quyền, trạng thái, số chỗ còn trống và trùng lịch trước khi ghi. Đưa việc đóng yêu cầu ghép nhóm vào cùng giao dịch tạo/phê duyệt.
- [ ] Chạy các kiểm tra tranh chấp đồng thời đầu tiên cho vòng đời trên PostgreSQL bằng bộ thiết lập kiểm thử của Thành viên 2 và rà soát trạng thái đã commit sau khi cả hai yêu cầu hoàn tất.
- [ ] Xác minh phản hồi chi tiết Sessions trên PostgreSQL đọc ảnh chụp dữ liệu nhất quán khi kết hợp nhiều truy vấn. Bổ sung kiểm thử chính sách tuyến API để phát hiện lỗi khi endpoint mới thiếu khai báo quyền truy cập. Xác minh kiểm tra JWT và quyền chủ phiên/chủ sở hữu tại backend bảo vệ các thao tác thay đổi dữ liệu phía sau cổng vào.

**Thành viên 2 — Lưu trữ trên PostgreSQL**

- [ ] Kết nối ứng dụng với PostgreSQL qua cấu hình môi trường. Xác minh lời gọi khóa sử dụng cùng giao dịch cơ sở dữ liệu với thao tác thay đổi dữ liệu; xác nhận hành vi hết thời gian chờ khóa và rollback bằng các kết nối độc lập.
- [ ] Bổ sung kiểm thử nhanh cho di chuyển và khởi động có thể tái lập vào cấu hình Compose/CI hiện có. Chạy nhập dữ liệu trên cơ sở dữ liệu mới và xác nhận thao tác thêm bản ghi mới nhận được ID hợp lệ sau khi nhập.
- [ ] Chạy di chuyển như một tác vụ duy nhất trước khi API khởi động. Build và kiểm thử nhanh đúng image có mã digest dự kiến phát hành. Giữ `/health` để kiểm tra tiến trình còn hoạt động và bổ sung phép kiểm tra cơ sở dữ liệu sẵn sàng có giới hạn thời gian. Chỉ công khai cổng vào trong cấu trúc triển khai demo.
- [ ] Bổ sung phép đo thời gian chờ nhóm kết nối DB, thời gian chờ khóa và thời lượng giao dịch cho đợt đo kiểm hiệu năng chung. Đưa lint, kiểm thử kiến trúc, hồi quy SQLite và tích hợp PostgreSQL vào CI.

**Thành viên 3 — Matching và Discovery**

- [ ] Lấy cùng loại khóa người dùng khi tạo yêu cầu ghép nhóm, kiểm tra lịch đã được chấp nhận của người dùng và thay thế yêu cầu đang hoạt động trong một giao dịch. Giữ việc đóng yêu cầu chồng lấn trong Unit of Work của bên gọi.
- [ ] Xác minh API vẫn trả về gợi ý có cùng cấu trúc và ý nghĩa; cùng Thành viên 1 kiểm thử tranh chấp giữa tạo yêu cầu ghép nhóm và phê duyệt. Kiểm tra trạng thái cuối cùng đã commit không còn yêu cầu ghép nhóm đang hoạt động gây xung đột.
- [ ] Hoàn thiện chính sách giới hạn tần suất cho đăng nhập, thao tác ghi đã xác thực và tìm kiếm công khai. Chỉ tin cậy các header chuyển tiếp từ cổng vào. Bổ sung log yêu cầu có cấu trúc gồm mã tương quan, mẫu tuyến API, trạng thái, thời lượng và mã lỗi. Bổ sung số liệu giám sát yêu cầu và ghép nhóm, tránh đưa ID người dùng/phiên chơi vào nhãn số liệu.

**Mốc kiểm tra ngày 24 tháng 11.** Bản tích hợp chạy được luồng tạo → tham gia → phê duyệt và ghép nhóm trên PostgreSQL. Các kiểm thử vòng đời và ghép nhóm đều sử dụng cùng quy trình khóa đã được tài liệu hóa và môi trường kiểm thử có thể tái lập.

## Giai đoạn 4 · Xác minh và bàn giao · Ngày 25–27 tháng 11

**Thành viên 1 — Giao dịch ở tầng ứng dụng**

- [ ] Hoàn tất các lần lặp kiểm thử tranh chấp chỗ cuối cùng và trùng lịch của cùng người dùng. Đồng thời kiểm thử phê duyệt tranh chấp với hủy/rút tham gia, tạo phiên chơi tranh chấp với phê duyệt và trường hợp thời gian chờ khóa kéo dài qua thời điểm bắt đầu phiên chơi.
- [ ] Chủ động gây lỗi giữa bước cập nhật lượt tham gia và đóng yêu cầu ghép nhóm, rồi xác minh rollback. Bàn giao kết quả kiểm thử vòng đời và phần giải thích ngắn về các ranh giới giao dịch.
- [ ] Thử các yêu cầu từ người ngoài đối với chi tiết phiên chơi, phê duyệt, rút tham gia và hủy. Xác minh yêu cầu bị từ chối không làm thay đổi dữ liệu. Xác minh thông tin xác thực không nằm trong image/log; cùng Thành viên 2 và 3 tài liệu hóa chính sách luân chuyển khóa và ghi nhận kiểm toán các thao tác thay đổi dữ liệu.

**Thành viên 2 — Lưu trữ trên PostgreSQL**

- [ ] Chạy lại di chuyển và kiểm tra toàn vẹn từ cơ sở dữ liệu sạch với dữ liệu lịch sử tiêu biểu. Kiểm tra khóa ngoại, điều kiện của chỉ mục có điều kiện, tính bảo toàn dấu thời gian qua ghi/đọc và các sequence. Lưu bản sao lưu, khôi phục vào cơ sở dữ liệu thứ hai và kiểm thử nhanh dữ liệu đã khôi phục.
- [ ] Bàn giao các lệnh di chuyển/thiết lập và sao lưu/khôi phục, kết quả xác minh và thời gian khôi phục đã đo.
- [ ] Trên hệ thống demo, làm gián đoạn DB, quan sát trạng thái sẵn sàng và rollback, khởi động lại API sau khi DB phục hồi, đồng thời diễn tập quay lui ứng dụng trên lược đồ tương thích. Ghi lại thời gian phát hiện, khởi động lại và phục hồi. Giữ đích khôi phục tách biệt với nguồn sao lưu.

**Thành viên 3 — Matching và Discovery**

- [ ] Chạy lại các kiểm thử tương đương kết quả Strategy, yêu cầu lặp lại, quyền riêng tư và kiến trúc trên bản tích hợp. Kiểm tra việc thay thế yêu cầu ghép nhóm thất bại vẫn giữ yêu cầu trước đó, và việc đặt chỗ thành công chỉ đóng yêu cầu đang hoạt động bị chồng lấn.
- [ ] Bàn giao bằng chứng kiểm thử ghép nhóm và demo cách tách luồng truy vấn Discovery khỏi luồng lệnh Matching.
- [ ] Trình diễn TLS, phản hồi `429` kèm thông tin để thử lại khi có đợt yêu cầu dồn dập theo cấu hình và log yêu cầu/lỗi đã che thông tin nhạy cảm. Theo dõi một yêu cầu bằng mã tương quan. Trình bày một lệnh import bị cấm được kiểm thử kiến trúc phát hiện và thay Strategy qua cấu hình kết nối phụ thuộc mà vẫn giữ cùng router.

**Nộp bài ngày 27 tháng 11 lúc 17:00 giờ Việt Nam.** Cả ba cùng rà soát bản tích hợp, ghi lại commit và bàn giao chung hướng dẫn chạy cùng bằng chứng xác minh.

## Tiêu chí nghiệm thu và bằng chứng demo

| Hạng mục | Bằng chứng |
| --- | --- |
| **QA-01 · Tính nhất quán** | Với các kết nối PostgreSQL độc lập, ghi nhận không có lượt đặt chỗ vượt sức chứa hoặc lượt đặt chỗ `ACCEPTED` trùng lịch qua ít nhất 1.000 lần lặp cho mỗi loại tranh chấp: chỗ cuối cùng và trùng lịch của cùng người dùng. Ghi nhận riêng các trường hợp hết thời gian chờ do hạ tầng. Trình diễn rollback khi có lỗi, tính nguyên tử của việc hủy phiên chơi và đóng yêu cầu ghép nhóm. Kiểm chứng dữ liệu nhập theo khóa ngoại, số lượng bản ghi, dấu thời gian UTC, tính duy nhất có điều kiện và các sequence. |
| **QA-02 · Hiệu năng** | Đo kiểm hiệu năng chung sau tích hợp. So sánh cùng tải công việc và giới hạn tài nguyên trên ba bản dựng; công bố thông lượng thành công, độ trễ, lỗi và kết quả kiểm tra bất biến. Xem các mục tiêu độ trễ/tỷ lệ lỗi trong đề xuất là giả thuyết cần rà soát sau khi có số đo cơ sở trên Kaggle. |
| **QA-03 · Khả năng sửa đổi** | Trình bày ranh giới của năm mô-đun, kiểm thử kiến trúc phát hiện import bị cấm, thay Strategy qua kết nối tại composition root và hành vi kiểm tra điều kiện tham gia/sức chứa hiện có chạy qua cả hai bộ điều hợp DB. Xác minh các luồng đọc chỉ trả về DTO và kết quả ghép nhóm tương thích trên tập dữ liệu kiểm thử cố định. |
| **QA-04 · Bảo mật** | Giữ thứ tự ưu tiên 401 trên các tuyến được bảo vệ và ghi lại mọi thay đổi đã thống nhất về ưu tiên 422/503. Trình bày kiểm thử bao phủ tuyến công khai/được bảo vệ, từ chối cấp quyền trước khi thay đổi dữ liệu, log/lỗi đã che thông tin nhạy cảm và đợt yêu cầu dồn dập theo cấu hình nhận `429` kèm thông tin để thử lại qua HTTPS. |
| **QA-05 · Khôi phục và khả năng quan sát** | Trình bày yêu cầu/lỗi được liên kết bằng mã tương quan, mất kết nối DB làm kiểm tra trạng thái sẵn sàng thất bại và khôi phục vào DB mới. Ghi lại thời gian thực tế so với các mục tiêu ban đầu của đề xuất: 30 giây để phát hiện mất DB, 60 giây để API phục hồi sau khi DB hoạt động bình thường, RTO (thời gian khôi phục mục tiêu) 30 phút và RPO (mức mất dữ liệu tối đa theo thời gian) 24 giờ nếu cấu hình sao lưu hằng ngày. |

Nếu tích hợp PostgreSQL chậm quá ngày 24 tháng 11, ưu tiên di chuyển và các kiểm thử chỗ cuối cùng, trùng lịch, đóng yêu cầu ghép nhóm. Khi nộp bài, trình bày bản SQLite tại mốc kiểm tra đã được xác minh cùng mọi bằng chứng PostgreSQL đã hoàn thành, đồng thời chỉ rõ các kiểm tra còn tồn đọng. Xem bản PostgreSQL tích hợp là bản triển khai thử nghiệm cho đến khi đáp ứng các tiêu chí chuyển đổi chính thức trong ADR.

## Đo kiểm hiệu năng chung sau triển khai

Đây là mốc **M3** trong ADR. Cả ba thành viên sẽ cùng chạy và rà soát sau khi triển khai. M0 ghi lại commit cơ sở và hành vi hiện tại để có thể đo hiệu năng của bản gốc trong cùng buổi đo chung với các biến thể khác.

- So sánh **A** (commit SQLite gốc), **B** (tái cấu trúc mô-đun và giao dịch trên SQLite) và **C** (PostgreSQL có khóa hàng). Giữ cố định số worker và các giới hạn. Dùng cùng giá trị khởi tạo ngẫu nhiên, tập dữ liệu, cấu hình tải và khoảng thời gian đo; dùng DB mới cho mỗi lần chạy. Ghi lại giới hạn CPU và bộ nhớ thực tế trên Kaggle. Giữ cấu hình cổng vào tương đương giữa các lần chạy được so sánh; đo riêng cấu hình có giới hạn tần suất nếu cấu hình đó làm thay đổi tải công việc.
- Ưu tiên luồng vòng đời với 50/100 người dùng ảo. Bao gồm các lượt chạy vòng đời và đọc Discovery với 10/50/100 người dùng, đo riêng đăng nhập/đăng ký và ghép nhóm với 10/50/100/200 ứng viên, có cả trường hợp không có lời giải. Cấp sẵn token cho các lượt chạy vòng đời và đọc. Tuân theo tài liệu đo cơ sở về khởi động làm nóng, số lần lặp, số liệu và cách báo cáo các lần chạy không đạt tới khoảng thời gian đo.
- Rà soát kế hoạch truy vấn, thời gian chờ khóa, thời lượng giao dịch và số ứng viên ghép nhóm trước khi chọn thay đổi tối ưu. Đo một chỉ mục hoặc phương án tối ưu Strategy như một biến thể riêng và xác nhận kết quả API vẫn như cũ. Kiểm thử riêng mọi biến thể hai bản sao ứng dụng sau khi kiểm tra tính đúng đắn, với cùng tổng ngân sách tài nguyên và kết nối DB. Thay đổi ngữ nghĩa hoàn tất hoặc thất bại của việc ghép nhóm cần có ADR trước khi đưa tính toán ra ngoài giao dịch của nó.

Nguồn tham khảo và phạm vi công việc tiếp theo được trình bày trong [tổng quan kiến trúc](README.md), [đề xuất kiến trúc](de-xuat-kien-truc.md), [thiết kế dữ liệu và tính nhất quán](du-lieu-va-nhat-quan.md), [ADR và các mốc triển khai](adr-va-lo-trinh.md) và [kế hoạch đo kiểm hiệu năng CPU trên Kaggle](danh-gia-hieu-nang-baseline.md).
