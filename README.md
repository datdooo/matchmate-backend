# MatchMate Backend

## TL;DR

MatchMate hỗ trợ người chơi cầu lông tìm kèo phù hợp và chủ kèo tuyển thêm người. Người chơi tra cứu sân/kèo theo quận, gửi yêu cầu tham gia và chờ host duyệt; cũng có thể tạo kèo hoặc tìm nhóm qua matching. Pha 1 cung cấp backend REST API, chưa có frontend hoàn chỉnh và không dùng GPS.

Backend sử dụng **FastAPI, Pydantic, SQLAlchemy, SQLite và Docker**.

## Chức năng chính

- **Tài khoản:** đăng ký hồ sơ và đăng nhập bằng JWT. Host là người tạo kèo, không phải vai trò quản trị riêng.
- **Tìm sân và kèo:** tra cứu theo quận, trình độ, giới tính, lịch và mức phí; xem số chỗ và điều kiện tham gia.
- **Quản lý kèo:** tạo kèo đơn/đôi, xem chi tiết và hủy trước giờ bắt đầu. Kèo có 2/4 người tính cả host, thời lượng 60–240 phút.
- **Tham gia:** xin vào kèo, host duyệt/từ chối và người chơi rút lượt. Yêu cầu đang chờ chưa giữ chỗ; khi duyệt phải kiểm lại điều kiện, số chỗ và lịch.
- **Matching:** gợi ý nhóm cùng sân, giờ và loại kèo, phù hợp giới tính, ngân sách và chênh trình tối đa 2 bậc. Gợi ý chưa tự tạo kèo hoặc giữ chỗ.

## Luồng sử dụng

1. **Đăng ký và đăng nhập:** tạo hồ sơ gồm email, mật khẩu, tên hiển thị, trình độ và giới tính; đăng nhập để lấy JWT.
2. **Tìm sân và kèo:** lọc kèo phù hợp rồi xem lịch, phí và số chỗ. Tra cứu công khai không cần đăng nhập; xem chi tiết cần JWT.
3. **Tạo kèo hoặc xin tham gia:** host nhập sân, lịch, loại kèo, phí và điều kiện tuyển. Người chơi khác xin tham gia để tạo lượt `PENDING`.
4. **Host duyệt hoặc từ chối:** duyệt chuyển lượt sang `ACCEPTED` khi còn chỗ và không trùng lịch đã xác nhận; từ chối chuyển sang `REJECTED`.
5. **Rút lượt hoặc hủy kèo:** người chơi rút lượt của mình trước giờ bắt đầu; host hủy cả kèo và các lượt đang hoạt động.
6. **Tìm nhóm qua matching:** nếu chưa chọn được kèo, gửi nhu cầu để nhận gợi ý đủ 2/4 người. Chưa đủ nhóm thì trả `suggestion=null`.

## Chạy nhanh

Cần Docker, Docker Compose và Python 3 để tạo cấu hình. Chạy tại thư mục gốc:

```bash
python3 -m scripts.init_env
docker compose build
docker compose run --rm api python -m scripts.seed
docker compose up -d
```

Mở [Swagger UI](http://localhost:8000/docs) để thử API. Seed tạo bảng và 10 sân mẫu. Dừng bằng `docker compose down`; dữ liệu được giữ trong volume. Cách chạy không dùng Docker nằm trong [hướng dẫn cài đặt](docs/INSTALLATION.md).

## Demo đơn giản test API

Sau khi cài môi trường Python theo hướng dẫn cài đặt, chạy:

```bash
python -m scripts.demo --step
```

Script tự mở server và DB tạm, đăng ký/đăng nhập hai tài khoản rồi lần lượt tạo kèo, xin tham gia, duyệt, rút và hủy. Nhấn Enter để đi tiếp. Các bước nhập lịch sai hoặc xin khi kèo đầy dùng để kiểm tra phản hồi lỗi; mỗi bước đều gọi HTTP thật và kiểm kết quả.

## Tài liệu

- [Cài đặt, chạy project và kiểm thử](docs/INSTALLATION.md)
- [Kiến trúc, nghiệp vụ và API](docs/ARCHITECTURE.md)
- [Đặc tả API — OpenAPI JSON](docs/openapi.json)
- [Luồng chi tiết: dữ liệu nhập, nhánh lỗi và mã nguồn](docs/WORKFLOWS.md)
- [Xin, duyệt và rút lượt tham gia](docs/PARTICIPATIONS.md)
- [Kiểm thử tải Kaggle CPU](docs/LOAD_TEST_RESULTS.md)

## Kiểm thử tải trên Kaggle CPU

[Báo cáo tải](docs/LOAD_TEST_RESULTS.md) ghi môi trường, số đo và các giới hạn. 235 test đạt; tải đọc 10/50/100 người dùng mô phỏng và luồng ghi 10 người đo đủ 60 giây, không lỗi request. Luồng ghi 50/100 người dừng trước khi đo do 503 hoặc đăng nhập quá thời gian chờ, chưa có kết quả đầy đủ.

[Notebook đã chạy](docs/load/kaggle-2026-10-29/matchmate-phase-1-load-test.ipynb) và [CSV/log](docs/load/kaggle-2026-10-29) được lưu để đối chiếu. Kết quả đo trên một máy là số liệu tham khảo cho cấu hình hiện tại.
