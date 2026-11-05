# Tài liệu MatchMate Backend

Tài liệu chia theo ba tuần của Pha 1. Mỗi thư mục là tài liệu của tuần đó.

| Tuần | Tài liệu | Nội dung |
|---|---|---|
| 1. Thiết kế | [thiet-ke.md](tuan-1-thiet-ke/thiet-ke.md) | Phạm vi, cấu trúc code, luật phụ thuộc, transaction, sơ đồ dữ liệu, quy tắc nghiệp vụ, danh sách API |
| 2. Xây dựng | [luong-nghiep-vu.md](tuan-2-xay-dung/luong-nghiep-vu.md) | Sáu luồng: đăng ký/đăng nhập, tạo kèo, tìm và xin tham gia, duyệt/rút/hủy, matching, đường đi từ HTTP đến DB |
| 3. Hoàn thiện | [cai-dat-va-kiem-thu.md](tuan-3-hoan-thien/cai-dat-va-kiem-thu.md) | Chạy bằng Docker và Python, demo, lệnh kiểm thử, cách chia thư mục test |
| 3. Hoàn thiện | [bao-cao-tai.md](tuan-3-hoan-thien/bao-cao-tai.md) | Số đo tải Kaggle CPU ngày 29/10/2026 và giới hạn |

Đặc tả API sinh từ code nằm ở [openapi.json](openapi.json). Nếu đổi API, sinh lại file này từ `app.openapi()`.
