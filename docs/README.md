# Tài liệu MatchMate Backend

Đặc tả đầy đủ (BRD, FRD, NFR, thiết kế hệ thống, kiểm chứng) và kế hoạch dự án nằm ở tài liệu Google Docs của nhóm. Thư mục này là tài liệu đi cùng code, chia theo ba tuần của Pha 1 như kế hoạch trong đặc tả.

| Tuần | Mốc theo đặc tả | Tài liệu |
|---|---|---|
| 1. Nền tảng | Docker, `/health`, Swagger chạy. Đăng nhập và API có bảo vệ hoạt động. Tạo kèo → xin → duyệt chạy trên SQLite thật | [thiết kế](tuan-1-nen-tang/thiet-ke.md), [luồng tài khoản, tạo kèo, xin, duyệt](tuan-1-nen-tang/luong-nghiep-vu.md) |
| 2. Hoàn thiện API | Đủ 11 API theo contract. Toàn luồng và matching hoạt động | [luồng tìm kiếm, rút, hủy, matching](tuan-2-hoan-thien-api/luong-nghiep-vu.md) |
| 3. Kiểm thử và bàn giao | Test toàn luồng và đồng thời, Docker, báo cáo tải Kaggle, README, demo | [từ HTTP đến DB](tuan-3-kiem-thu-va-ban-giao/tu-http-den-db.md), [cài đặt và kiểm thử](tuan-3-kiem-thu-va-ban-giao/cai-dat-va-kiem-thu.md), [báo cáo tải](tuan-3-kiem-thu-va-ban-giao/bao-cao-tai.md) |

Đặc tả API sinh từ code nằm ở [openapi.json](openapi.json). Nếu đổi API, sinh lại file này từ `app.openapi()`.

## Phân công

| Thành viên | Phụ trách |
|---|---|
| Chiến | FR-01, 02, 05, 06, 07: đăng ký, đăng nhập, tạo, xem, hủy kèo. JWT middleware, Docker, CI, tích hợp, README |
| Hải | FR-03, 04, 11: tìm sân, tìm kèo, matching. Bộ lọc, seed và fixture |
| Đạt | FR-08, 09, 10: xin, duyệt, rút lượt. DB, UnitOfWork, UTC, test đồng thời, báo cáo tải |

## Khác biệt giữa đặc tả và code hiện tại

GPS đã bị nhóm bỏ khỏi Pha 1 và đặc tả đã được sửa theo (05/11/2026): tra cứu chỉ theo quận (`district_code`), không có tọa độ, bán kính hay `distance_km`. Phần còn lại:


- **Cấu trúc thư mục:** đặc tả liệt kê `app/core/` và `app/api/authentication_middleware.py`. Code đặt cấu hình ở `app/config.py` và middleware ở `app/features/auth/middleware.py`.

Cấu trúc thư mục cần nhóm chọn: sửa đặc tả cho khớp code, hoặc chuyển code cho khớp đặc tả.
