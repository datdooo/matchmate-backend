# MatchMate Backend

![MatchMate: cầu lông và ghép kèo](docs/assets/matchmate-cover.png)

MatchMate là backend REST API giúp người chơi cầu lông tìm kèo phù hợp và giúp chủ kèo tuyển thêm người. Người chơi tra cứu sân và kèo theo quận, gửi yêu cầu tham gia rồi chờ host duyệt. Ai chưa chọn được kèo có thể gửi nhu cầu để hệ thống gợi ý nhóm.

Đây là Pha 1 của bài tập lớn môn Kiến trúc phần mềm (UET). Pha 1 chỉ có backend: chưa có frontend hoàn chỉnh và không dùng GPS. Công nghệ: FastAPI, Pydantic, SQLAlchemy 2, SQLite, Docker.

## Chức năng

- **Tài khoản:** đăng ký, đăng nhập bằng JWT. Host là người tạo kèo, không phải vai trò quản trị riêng.
- **Tìm sân và kèo:** lọc theo quận, trình độ, giới tính, lịch và mức phí. Tra cứu công khai, không cần đăng nhập.
- **Quản lý kèo:** tạo kèo đơn (2 người) hoặc đôi (4 người), tính cả host. Xem chi tiết và hủy trước giờ bắt đầu. Mỗi kèo dài 60–240 phút.
- **Tham gia:** xin vào kèo, host duyệt hoặc từ chối, người chơi rút lượt. Lượt đang chờ chưa giữ chỗ. Khi duyệt, hệ thống kiểm lại điều kiện, số chỗ và lịch.
- **Matching:** gợi ý nhóm đủ 2 hoặc 4 người cùng sân, cùng giờ, cùng loại kèo, hợp giới tính và ngân sách, chênh trình tối đa 2 bậc. Gợi ý không tự tạo kèo hay giữ chỗ. Chưa đủ người thì trả `suggestion=null`.

## Cách dùng

1. Đăng ký rồi đăng nhập để lấy JWT.
2. Tìm sân và kèo. Muốn xem chi tiết thì cần JWT.
3. Host tạo kèo. Người chơi khác xin tham gia và tạo lượt `PENDING`.
4. Host duyệt (`ACCEPTED`) hoặc từ chối (`REJECTED`). Duyệt chỉ thành công khi còn chỗ và không trùng lịch đã xác nhận.
5. Người chơi rút lượt trước giờ bắt đầu. Host hủy kèo thì mọi lượt đang hoạt động bị hủy theo.
6. Chưa chọn được kèo thì gửi yêu cầu matching.

## Chạy nhanh

Cần Docker, Docker Compose và Python 3 (để tạo file cấu hình). Tại thư mục gốc:

```bash
python3 -m scripts.init_env
docker compose build
docker compose run --rm api python -m scripts.seed
docker compose up -d
```

Mở [Swagger UI](http://localhost:8000/docs) để thử API. Seed tạo bảng và 10 sân mẫu. Dừng bằng `docker compose down`, dữ liệu vẫn nằm trong volume. Cách chạy không dùng Docker ở [hướng dẫn cài đặt](docs/tuan-3-kiem-thu-va-ban-giao/cai-dat-va-kiem-thu.md).

## Demo

Sau khi cài môi trường Python theo hướng dẫn cài đặt:

```bash
python -m scripts.demo --step
```

Script tự mở server với DB tạm, đăng ký và đăng nhập hai tài khoản, rồi lần lượt tạo kèo, xin tham gia, duyệt, rút và hủy. Nhấn Enter để sang bước tiếp theo. Mỗi bước gọi HTTP thật và kiểm dữ liệu trả về. Hai bước nhập lịch sai (422) và xin vào kèo đã đầy (409) là tình huống cố ý.

## Tài liệu

Tài liệu chia theo ba tuần của kế hoạch Pha 1, mục lục ở [docs/README.md](docs/README.md).

- Tuần 1, nền tảng: [thiết kế, dữ liệu và danh sách API](docs/tuan-1-nen-tang/thiet-ke.md), [luồng tài khoản, tạo kèo, xin và duyệt](docs/tuan-1-nen-tang/luong-nghiep-vu.md)
- Tuần 2, hoàn thiện API: [luồng tìm kiếm, rút, hủy và matching](docs/tuan-2-hoan-thien-api/luong-nghiep-vu.md)
- Tuần 3, kiểm thử và bàn giao: [từ HTTP đến DB](docs/tuan-3-kiem-thu-va-ban-giao/tu-http-den-db.md), [cài đặt và kiểm thử](docs/tuan-3-kiem-thu-va-ban-giao/cai-dat-va-kiem-thu.md), [báo cáo tải](docs/tuan-3-kiem-thu-va-ban-giao/bao-cao-tai.md)
- [Đặc tả API (OpenAPI JSON)](docs/openapi.json)

## Kiểm thử tải

Lần đo ngày 29/10/2026 trên Kaggle CPU (một worker, 235 test đạt ở thời điểm đó):

- Tải đọc với 10, 50 và 100 người, và tải ghi (lifecycle) với 10 người: đo đủ 60 giây, không lỗi request.
- Tải ghi với 50 và 100 người: dừng trước khi đo, do lỗi 503 hoặc đăng nhập quá thời gian chờ. Chưa có kết quả.

Chi tiết và giới hạn ở [báo cáo tải](docs/tuan-3-kiem-thu-va-ban-giao/bao-cao-tai.md). Notebook đã chạy và dữ liệu thô nằm ở [mốc Pha 1](https://github.com/datdooo/matchmate-backend/tree/5b9be9f939de41965eb1f6b290be2b60ea4d28c/docs/load/kaggle-2026-10-29).
