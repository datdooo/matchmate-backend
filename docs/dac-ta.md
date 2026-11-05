# Đặc tả nghiệp vụ và API

Đặc tả máy đọc được ở [openapi.json](openapi.json). Khi chạy ứng dụng, mở `/docs` để thử API.

## Quy tắc chung

- API cần đăng nhập nhận `Authorization: Bearer <token>`. Token thiếu, sai hoặc hết hạn trả `401 UNAUTHORIZED`. Middleware kiểm JWT trước khi request vào router, nên 401 đến trước 422.
- Lỗi luôn có dạng `{"error": {"code", "message", "details", "request_id"}}`. Lỗi không chứa mật khẩu, token hay câu SQL.
- Thời gian gửi lên phải có múi giờ (ISO 8601) và được lưu theo UTC. API trả thời gian có hậu tố `Z`.
- Kèo đơn (`SINGLES`) có 2 người, kèo đôi (`DOUBLES`) có 4 người, tính cả host. Lịch ở tương lai, dài 60-240 phút.
- Tạo kèo ghi luôn lượt của host với trạng thái `ACCEPTED`. Số chỗ đếm từ các lượt `ACCEPTED`.
- Xin tham gia tạo lượt `PENDING`, chưa giữ chỗ. Phí và giới tính lúc xin được lưu (`quoted_fee_vnd`, `gender_at_join`) và không tính lại sau đó.
- Host không rút lượt riêng. Host phải hủy cả kèo.
- Thao tác ghi dùng chung một transaction. Nếu chờ khóa ghi quá 5 giây, API trả `503 DATABASE_BUSY` kèm `Retry-After: 1`.
- Xin lại sau khi rút hoặc bị từ chối tạo lượt mới. Lượt cũ giữ làm lịch sử.

Trạng thái lượt: `PENDING`, `ACCEPTED`, `REJECTED`, `CANCELLED`. Trạng thái kèo trong DB: `OPEN`, `CANCELLED`.

Khi trả về, kèo có thêm `display_status`, tính theo thứ tự sau:

| Điều kiện | `display_status` |
|---|---|
| Kèo đã hủy | `CANCELLED` |
| Đã qua giờ kết thúc | `ENDED` |
| Đã qua giờ bắt đầu | `STARTED` |
| Số lượt `ACCEPTED` bằng sức chứa | `FULL` |
| Còn lại | `AVAILABLE` |

## Tài khoản

### POST /auth/register

- **Gửi:** `email`, `password` (8-128 ký tự), `display_name` (1-80 ký tự), `skill_level` (một trong 19 mã), `gender` (`MALE` hoặc `FEMALE`). Thiếu, thừa hay sai kiểu trường đều trả 422
- **Lỗi:** `422 VALIDATION_ERROR`, `409 EMAIL_ALREADY_EXISTS`
- **Kết quả:** `201`, hồ sơ tài khoản, chưa có token. Email được cắt khoảng trắng, chuyển chữ thường. Mật khẩu băm Argon2

### POST /auth/login

- **Gửi:** `email`, `password`
- **Lỗi:** `422`, `401 INVALID_CREDENTIALS` (không cho biết email có tồn tại hay không)
- **Kết quả:** `200`, `access_token`, `token_type=bearer`, `expires_in` (mặc định 60 phút)

## Tìm kiếm

### GET /venues (công khai)

- **Gửi:** `district_code`, `limit` (1-100), `offset`
- **Lỗi:** `422` nếu tham số sai hoặc có tham số lạ
- **Kết quả:** `200`, `items` và `total`. Chỉ sân đang hoạt động, sắp theo `id`. Không có kết quả vẫn là `200` với `items` rỗng

### GET /sessions (công khai, trừ `host_me=true`)

- **Gửi:** `district_code`, `venue_id`, `play_type`, `skill_level`, `gender`, `max_fee_vnd`, `available_from`, `available_to`, `only_available`, `host_me`, `limit`, `offset`
- **Quy tắc:** `available_from` và `available_to` phải cùng có hoặc cùng vắng, có múi giờ, mốc đầu nhỏ hơn mốc cuối. Phí không âm. `host_me=true` chỉ trả kèo của người đang đăng nhập
- **Lỗi:** `401` nếu `host_me=true` thiếu token, `422` nếu bộ lọc sai hoặc có tham số lạ
- **Kết quả:** `200`, `items` và `total`, sắp theo `starts_at` rồi `id`

## Kèo

### POST /sessions (JWT)

- **Gửi:** `venue_id`, `title` (1-120 ký tự), `notes` (không bắt buộc, tối đa 1000), `starts_at`, `ends_at`, `play_type`, `fee_male_vnd`, `fee_female_vnd` (số nguyên VND không âm), `min_level`, `max_level` (min không cao hơn max), `gender_policy` (`ANY` mặc định, `MALE_ONLY`, `FEMALE_ONLY`)
- **Quy tắc:** Host lấy từ JWT, phải nằm trong khoảng trình và hợp `gender_policy`. Host không được có lịch `ACCEPTED` chồng giờ
- **Lỗi:** `422 VALIDATION_ERROR` hoặc `INVALID_TIME_WINDOW`, `404 VENUE_NOT_FOUND`, `409 VENUE_INACTIVE`, `PROFILE_INCOMPLETE`, `ELIGIBILITY_MISMATCH`, `TIME_CONFLICT`
- **Kết quả:** `201`, chi tiết kèo. Kèo và lượt host được ghi cùng transaction. Các nhu cầu matching chồng giờ của host bị đóng

### GET /sessions/{session_id} (JWT)

- **Lỗi:** `404 SESSION_NOT_FOUND`, `422` nếu ID sai
- **Kết quả:** `200`: lịch, phí, số chỗ, `display_status`, các lượt của người xem (`my_participations`), cờ `can_cancel` và `can_decide`. Host nhận thêm danh sách lượt để quản lý (`management`). Hai cờ chỉ để hiển thị, service kiểm quyền lại khi ghi

### DELETE /sessions/{session_id} (chỉ host)

- **Lỗi:** `404 SESSION_NOT_FOUND`, `403 FORBIDDEN`, `409 SESSION_ALREADY_STARTED`
- **Kết quả:** `200`, chi tiết kèo. Kèo và mọi lượt `PENDING`, `ACCEPTED` (cả của host) chuyển `CANCELLED` trong một transaction. Gọi lại khi kèo đã hủy vẫn `200`, không đổi gì

## Lượt tham gia

### POST /participations (JWT)

- **Gửi:** `session_id`
- **Lỗi:** `404 SESSION_NOT_FOUND`, `409 SESSION_CANCELLED`, `SESSION_ALREADY_STARTED`, `SESSION_FULL`, `PROFILE_INCOMPLETE`, `ELIGIBILITY_MISMATCH` (trình hoặc giới tính không hợp), `PARTICIPATION_ALREADY_EXISTS`, `TIME_CONFLICT`
- **Kết quả:** `201`, lượt `PENDING` kèm phí và giới tính tại lúc xin

### POST /participations/{participation_id}/decision (chỉ host)

- **Gửi:** `decision`: `APPROVE` hoặc `REJECT`
- **Lỗi:** `404 PARTICIPATION_NOT_FOUND`, `403 FORBIDDEN`, `409 INVALID_STATE` (lượt không còn `PENDING`), `SESSION_CANCELLED`, `SESSION_ALREADY_STARTED`. Riêng `APPROVE` còn có `409 SESSION_FULL`, `ELIGIBILITY_MISMATCH`, `TIME_CONFLICT` và lượt giữ nguyên `PENDING`
- **Kết quả:** `200`. `REJECT` ghi `REJECTED`, không kiểm chỗ. `APPROVE` kiểm lại hồ sơ hiện tại, số chỗ và lịch, ghi `ACCEPTED` và đóng các nhu cầu matching chồng giờ trong cùng transaction

Hai yêu cầu `APPROVE` cùng nhắm vào chỗ cuối không thể cùng thành công. Yêu cầu lấy được khóa sau phải đếm lại các lượt `ACCEPTED`.

### DELETE /participations/{participation_id} (chủ lượt)

- **Lỗi:** `404 PARTICIPATION_NOT_FOUND`, `403 FORBIDDEN`, `409 HOST_PARTICIPATION_REQUIRED` (host phải hủy kèo), `INVALID_STATE` (lượt đã `REJECTED`), `SESSION_CANCELLED`, `SESSION_ALREADY_STARTED`
- **Kết quả:** `200`, ghi `CANCELLED`. Gọi lại trên lượt đã `CANCELLED` vẫn `200`, trả bản cũ. Matching đã đóng không mở lại

Nếu duyệt và hủy chạy gần nhau, kết quả theo thứ tự commit. Hủy kèo trước thì duyệt bị từ chối. Duyệt trước thì lượt vừa `ACCEPTED` bị hủy theo kèo. Rút lượt trước thì duyệt bị từ chối. Duyệt trước thì rút giải phóng đúng một chỗ.

## Matching

### POST /matching/requests (JWT)

- **Gửi:** `venue_id`, `starts_at`, `ends_at`, `play_type`, `proposed_fee_male_vnd`, `proposed_fee_female_vnd`, `budget_max_vnd`, `gender_policy` (mặc định `ANY`). Trình và giới tính lấy từ hồ sơ, không gửi
- **Lỗi:** `422` (kể cả phí của chính mình vượt ngân sách), `404 VENUE_NOT_FOUND`, `409 PROFILE_INCOMPLETE`, `ELIGIBILITY_MISMATCH`, `TIME_CONFLICT`
- **Kết quả:** `201`: yêu cầu mới và `suggestion`. Mỗi người chỉ giữ một yêu cầu `ACTIVE`, yêu cầu mới thay yêu cầu cũ nên gọi lặp tạo bản mới

Cách chọn nhóm: ứng viên phải cùng sân, giờ chính xác, loại kèo, còn hiệu lực và không có lịch `ACCEPTED` chồng giờ. Xét theo `created_at` rồi `id`. Kèo đơn cần 1 ứng viên, kèo đôi xét tổ hợp 3 ứng viên. Nhóm đầu tiên thỏa mọi điều kiện được chọn: chênh trình không quá 2 bậc, `gender_policy` của mọi người phù hợp, ngân sách từng người đủ. Phí của nhóm theo hai mức người gọi đề xuất (nam theo phí nam, nữ theo phí nữ), mỗi mức không vượt ngân sách của đúng người đó.

Không đủ người thì `suggestion=null`, đó là kết quả bình thường. Khi có nhóm, `requires_confirmation=true`. Matching chỉ gợi ý: không tạo kèo, không giữ chỗ. Yêu cầu cũng bị đóng khi người đó xác nhận một lịch chồng giờ (tạo kèo hoặc được duyệt).

## Khác

`GET /health` trả `{"status": "ok"}`, chỉ cho biết tiến trình chạy, không kiểm tra DB.
