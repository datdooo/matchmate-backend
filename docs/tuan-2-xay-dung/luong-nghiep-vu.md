# Tuần 2: Luồng nghiệp vụ

Tài liệu mô tả từng luồng đã làm, với dữ liệu nhập, các lỗi có thể gặp và kết quả. Quy tắc chung và danh sách API ở [thiết kế tuần 1](../tuan-1-thiet-ke/thiet-ke.md).

Với API cần đăng nhập, JWT thiếu, sai hoặc hết hạn trả `401 UNAUTHORIZED`. Client đăng nhập lại rồi gửi lại yêu cầu. Hệ thống không tự sửa dữ liệu sai và không tạo dữ liệu thay người dùng.

| Mục | Luồng | FR |
|---|---|---|
| 1 | Đăng ký và đăng nhập | 01, 02 |
| 2 | Tạo kèo | 05 |
| 3 | Tìm kèo, xem chi tiết, xin tham gia | 03, 04, 06, 08 |
| 4 | Duyệt, rút lượt, hủy kèo | 07, 09, 10 |
| 5 | Gợi ý ghép nhóm | 11 |
| 6 | Từ HTTP đến DB | mọi API |

## 1. Đăng ký và đăng nhập (FR-01, FR-02)

```mermaid
flowchart TD
    A{"Có tài khoản?"} -->|Không| B["POST /auth/register"]
    B --> C{"Đúng schema?"}
    C -->|Không| D["422 VALIDATION_ERROR"]
    C -->|Có| E{"Email đã tồn tại?"}
    E -->|Có| F["409 EMAIL_ALREADY_EXISTS"]
    E -->|Không| G["Chuẩn hóa email, băm Argon2, lưu user"]
    G --> H["201: hồ sơ tài khoản, chưa có token"]
    H --> I["POST /auth/login"]
    A -->|Có| I
    I --> J{"Đúng schema và thông tin đăng nhập?"}
    J -->|Sai schema| K["422"]
    J -->|Sai email hoặc mật khẩu| L["401 INVALID_CREDENTIALS"]
    J -->|Đúng| M["200: access_token, token_type=bearer, expires_in"]
    M --> N["Gửi header Authorization: Bearer token"]
```

| Trường đăng ký | Ràng buộc |
|---|---|
| `email` | Email hợp lệ. Bỏ khoảng trắng hai đầu, chuyển chữ thường |
| `password` | 8–128 ký tự. Chỉ lưu bản băm |
| `display_name` | Sau khi cắt khoảng trắng còn 1–80 ký tự |
| `skill_level` | Một trong 19 mã của `SkillLevel` |
| `gender` | `MALE` hoặc `FEMALE` |

Thiếu trường, sai kiểu, enum sai hoặc thừa trường đều trả 422. Đăng nhập chỉ nhận `email` và `password`. Khi sai thông tin, phản hồi không cho biết email có tồn tại hay không.

Đăng ký chỉ tạo hồ sơ, token chỉ được cấp ở bước đăng nhập. Middleware kiểm token trước khi request vào API cần đăng nhập.

## 2. Tạo kèo (FR-05)

```mermaid
flowchart TD
    A["POST /sessions với JWT"] --> B{"Đúng kiểu, trường bắt buộc, enum, múi giờ?"}
    B -->|Không| C["422 VALIDATION_ERROR"]
    B -->|Có| D["Mở transaction ghi, đọc giờ sau khi có khóa"]
    D --> E{"Lịch ở tương lai, dài 60–240 phút, min_level ≤ max_level?"}
    E -->|Không| F["422 INVALID_TIME_WINDOW hoặc VALIDATION_ERROR"]
    E -->|Có| G{"Sân tồn tại và đang hoạt động?"}
    G -->|Không tồn tại| H["404 VENUE_NOT_FOUND"]
    G -->|Ngừng hoạt động| I["409 VENUE_INACTIVE"]
    G -->|Có| J{"Hồ sơ host phù hợp và không trùng lịch ACCEPTED?"}
    J -->|Không| K["409 PROFILE_INCOMPLETE, ELIGIBILITY_MISMATCH hoặc TIME_CONFLICT"]
    J -->|Có| L["Tạo kèo OPEN và lượt host ACCEPTED, đóng matching chồng giờ của host"]
    L --> M["Commit một lần, trả 201 với chi tiết kèo"]
```

| Dữ liệu | Ràng buộc |
|---|---|
| `venue_id` | Số nguyên dương, sân tồn tại và đang hoạt động |
| `title`, `notes` | Tiêu đề 1–120 ký tự sau khi cắt khoảng trắng. Ghi chú không bắt buộc, tối đa 1000 ký tự |
| `starts_at`, `ends_at` | ISO 8601 có múi giờ. Bắt đầu ở tương lai, thời lượng 60–240 phút |
| `play_type` | `SINGLES` là 2 người, `DOUBLES` là 4 người, đều tính host |
| `fee_male_vnd`, `fee_female_vnd` | Số nguyên VND không âm |
| `min_level`, `max_level` | Mã trình hợp lệ, min không cao hơn max, host phải nằm trong khoảng |
| `gender_policy` | `ANY` (mặc định), `MALE_ONLY` hoặc `FEMALE_ONLY`. Host cũng phải phù hợp |

ID và phí không vượt giới hạn INTEGER 64 bit của SQLite. Host lấy từ JWT. Sức chứa và trạng thái do hệ thống đặt, client không gửi.

Kèo và lượt của host được ghi trên cùng connection. Nếu lỗi giữa chừng, transaction rollback nên không có kèo nào thiếu lượt host. Lỗi 409 nghĩa là chưa tạo kèo.

## 3. Tìm kèo, xem chi tiết, xin tham gia (FR-03, 04, 06, 08)

```mermaid
flowchart TD
    A["GET /venues hoặc GET /sessions"] --> B{"Bộ lọc hợp lệ?"}
    B -->|Không| C["422"]
    B -->|Có| D{"Có kết quả?"}
    D -->|Không| E["200 với items rỗng"]
    D -->|Có| F["GET /sessions/{session_id} với JWT"]
    F --> G{"Kèo tồn tại?"}
    G -->|Không| H["404 SESSION_NOT_FOUND"]
    G -->|Có| I["200: lịch, phí, số chỗ, trạng thái"]
    I --> J["POST /participations với session_id và JWT"]
    J --> K{"Kèo còn mở, chưa bắt đầu, còn chỗ?"}
    K -->|Không| L["409 SESSION_CANCELLED, SESSION_ALREADY_STARTED hoặc SESSION_FULL"]
    K -->|Có| M{"Đủ điều kiện, chưa có lượt hoạt động, không trùng lịch?"}
    M -->|Không| N["409 PROFILE_INCOMPLETE, ELIGIBILITY_MISMATCH, PARTICIPATION_ALREADY_EXISTS hoặc TIME_CONFLICT"]
    M -->|Có| O["Lưu PENDING cùng giới tính và phí lúc xin, commit, trả 201"]
    O --> P["Chờ host duyệt. PENDING chưa giữ chỗ"]
```

**Bộ lọc của `GET /sessions`:** `district_code`, `venue_id`, `play_type`, `skill_level`, `gender`, `max_fee_vnd`, `available_from`, `available_to`, `only_available`, `host_me`, `limit`, `offset`.

- `available_from` và `available_to` phải cùng có hoặc cùng vắng, mốc đầu nhỏ hơn mốc cuối, cả hai có múi giờ.
- Phí không âm. `limit` từ 1 đến 100, `offset` không âm.
- `host_me=true` cần JWT và chỉ trả kèo của tài khoản đang đăng nhập.
- `GET /venues` chỉ lọc theo quận và phân trang.

**Chi tiết kèo** trả số chỗ (đếm từ lượt `ACCEPTED`), lượt của người đang xem và hai cờ `can_cancel`, `can_decide`. Host còn nhận danh sách lượt để quản lý. Trạng thái `AVAILABLE`, `FULL`, `STARTED`, `ENDED`, `CANCELLED` là trạng thái hiển thị tính từ lịch và số người (bảng ở tuần 1), không phải cột trong DB.

Số chỗ người dùng thấy ở trang trước chỉ để tham khảo. Khi xin tham gia và khi duyệt, hệ thống kiểm lại từ đầu trong transaction.

## 4. Duyệt, rút lượt, hủy kèo (FR-07, 09, 10)

```mermaid
flowchart TD
    A{"Thao tác nào?"}
    A -->|Duyệt hoặc từ chối| B["POST /participations/id/decision: APPROVE hoặc REJECT"]
    B --> C{"Lượt tồn tại, người gọi là host, lượt PENDING, kèo mở và chưa bắt đầu?"}
    C -->|Không| D["404 không tồn tại, 403 sai quyền, 409 sai trạng thái hoặc kèo đã bắt đầu/hủy"]
    C -->|Có| E{"Quyết định?"}
    E -->|REJECT| F["Ghi REJECTED, trả 200. Không kiểm chỗ hay điều kiện tuyển"]
    E -->|APPROVE| G{"Hồ sơ hiện tại hợp lệ, còn chỗ, không trùng lịch ACCEPTED?"}
    G -->|Không| H["409, lượt giữ PENDING, rollback"]
    G -->|Có| I["Ghi ACCEPTED, đóng matching chồng giờ, commit, trả 200"]

    A -->|Rút lượt| J["DELETE /participations/id, không có body"]
    J --> K{"Đúng chủ lượt và không phải lượt host?"}
    K -->|Không| L["403 FORBIDDEN hoặc 409 HOST_PARTICIPATION_REQUIRED"]
    K -->|Có| M{"Trạng thái lượt?"}
    M -->|CANCELLED| N["200 bản cũ, không đổi timestamp"]
    M -->|REJECTED| O["409 INVALID_STATE"]
    M -->|PENDING hoặc ACCEPTED| P{"Kèo mở và chưa bắt đầu?"}
    P -->|Không| Q["409"]
    P -->|Có| R["Ghi CANCELLED, trả 200. Không mở lại matching đã đóng"]

    A -->|Hủy kèo| S["DELETE /sessions/id bởi host, không có body"]
    S --> T{"Kèo tồn tại và đúng host?"}
    T -->|Không| U["404 SESSION_NOT_FOUND hoặc 403 FORBIDDEN"]
    T -->|Có| V{"Trạng thái kèo?"}
    V -->|Đã hủy| W["200 chi tiết hiện tại, không hủy lần hai"]
    V -->|Đã bắt đầu| X["409 SESSION_ALREADY_STARTED"]
    V -->|Chưa bắt đầu| Y["Một transaction: kèo và mọi lượt PENDING/ACCEPTED thành CANCELLED, trả 200"]
```

ID sai định dạng, hoặc body quyết định thiếu, sai, thừa trường, trả 422. Mỗi nhánh thành công trả chi tiết hiện tại, và chỉ trả sau khi commit.

Vài điểm cần nhớ:

- Duyệt không chỉ đổi trạng thái. Nó xác nhận một lịch chơi, nên phải đóng các nhu cầu matching chồng giờ trong cùng transaction.
- `REJECT` không chiếm chỗ, nên không cần kiểm sức chứa.
- Rút lượt và hủy kèo gọi lặp vẫn an toàn.
- Xin lại sau khi rút hoặc bị từ chối tạo lượt mới. Lượt cũ giữ nguyên làm lịch sử.

## 5. Gợi ý ghép nhóm (FR-11)

```mermaid
flowchart TD
    A["POST /matching/requests với JWT"] --> B{"Schema và thời gian hợp lệ?"}
    B -->|Không| C["422, không tạo yêu cầu"]
    B -->|Có| D{"Sân tồn tại và hoạt động, hồ sơ phù hợp, phí của mình trong ngân sách, không trùng lịch?"}
    D -->|Không| E["404 sân không tồn tại, 409 điều kiện hoặc lịch, 422 vượt ngân sách"]
    D -->|Có| F["Đóng yêu cầu ACTIVE cũ của người gửi (REPLACED), tạo yêu cầu mới ACTIVE"]
    F --> G["Lấy ứng viên ACTIVE chưa hết hạn, cùng sân, giờ chính xác, loại kèo. Bỏ người có lịch ACCEPTED chồng giờ"]
    G --> H{"Đủ 2/4 người, chênh trình tối đa 2 bậc, mọi policy và ngân sách phù hợp?"}
    H -->|Không| I["201: yêu cầu mới, suggestion=null"]
    H -->|Có| J["201: yêu cầu và suggestion, requires_confirmation=true"]
```

Trường gửi lên: `venue_id`, `starts_at`, `ends_at`, `play_type`, `proposed_fee_male_vnd`, `proposed_fee_female_vnd`, `budget_max_vnd`, `gender_policy` (mặc định `ANY`). ID, phí, thời lượng và múi giờ theo cùng giới hạn như tạo kèo.

Mức phí của nhóm gợi ý lấy theo đề xuất của người gọi, và phải nằm trong ngân sách của từng thành viên.

Matching chỉ gợi ý. Nó không tạo kèo hay lượt tham gia nào. Không đủ người là kết quả bình thường (`suggestion=null`), không phải lỗi. Mỗi người chỉ giữ một yêu cầu `ACTIVE`: yêu cầu mới thay yêu cầu cũ. Yêu cầu cũng bị đóng khi người đó xác nhận một lịch chồng giờ ở luồng 2 hoặc luồng 4.

## 6. Từ HTTP đến DB

```mermaid
flowchart TD
    A["HTTP request"] --> B{"API cần JWT và JWT hợp lệ?"}
    B -->|Không| C["401 UNAUTHORIZED"]
    B -->|Có hoặc API công khai| D{"Schema đúng?"}
    D -->|Không| E["422 VALIDATION_ERROR, không ghi DB"]
    D -->|Có| F{"Đọc hay ghi?"}
    F -->|Đọc| G["BEGIN, đọc theo một snapshot"]
    F -->|Ghi| H["BEGIN IMMEDIATE, chờ khóa tối đa SQLITE_BUSY_TIMEOUT_MS"]
    H --> I{"Lấy được khóa?"}
    I -->|Không| J["503 DATABASE_BUSY, Retry-After: 1"]
    I -->|Có| K["Đọc Clock, kiểm quyền, trạng thái, sức chứa, lịch"]
    K --> L{"Nghiệp vụ hợp lệ?"}
    L -->|Không| M["Rollback, trả 403, 404, 409 hoặc 422 theo mã lỗi"]
    L -->|Có| N["Ghi và đọc dữ liệu trả về trên cùng connection"]
    N --> O["Commit một lần, trả response"]
    N -->|Lỗi kỹ thuật| P["Rollback, 500 INTERNAL_ERROR, không lộ SQL hay exception"]
```

JWT middleware chạy trước router. Nếu một request vừa sai JWT vừa sai schema thì 401 đến trước. Với các lỗi nghiệp vụ, mã lỗi trả về phụ thuộc thứ tự các bước kiểm trong service.

Hai yêu cầu duyệt cùng nhắm vào chỗ cuối không thể cùng thành công. Yêu cầu lấy được khóa sau phải đếm lại các lượt `ACCEPTED`. Nếu chờ khóa quá hạn, client nhận 503 và tự thử lại.
