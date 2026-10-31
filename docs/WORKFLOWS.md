# Luồng nghiệp vụ chi tiết


Với API bảo vệ, JWT thiếu/sai/hết hạn trả `401 UNAUTHORIZED`; cần đăng nhập lại rồi gửi lại yêu cầu. Lỗi nhập liệu không tự sửa hoặc tạo dữ liệu thay người dùng.

<details>
<summary><strong>1. Đăng ký và đăng nhập — FR-01, FR-02</strong></summary>

```mermaid
flowchart TD
    A{"Có tài khoản?"} -->|Không| B["POST /auth/register: email, password, display_name, skill_level, gender"]
    B --> C{"Đúng schema?"}
    C -->|Không| D["422 VALIDATION_ERROR → sửa trường bị báo lỗi"]
    D --> B
    C -->|Có| E{"Email đã tồn tại?"}
    E -->|Có| F["409 EMAIL_ALREADY_EXISTS → đổi email hoặc đăng nhập"]
    E -->|Không| G["Chuẩn hóa email; băm mật khẩu Argon2; lưu user"]
    G --> H["201: hồ sơ tài khoản, chưa cấp token"]
    H --> I["POST /auth/login: email, password"]
    A -->|Có| I
    I --> J{"Đúng schema và thông tin đăng nhập?"}
    J -->|Sai schema| K["422 → sửa dữ liệu"]
    K --> I
    J -->|Sai email hoặc mật khẩu| L["401 INVALID_CREDENTIALS → nhập lại"]
    L --> I
    J -->|Đúng| M["200: access_token, token_type=bearer, expires_in"]
    M --> N["Gửi Authorization: Bearer token cho API bảo vệ"]
```

| Trường đăng ký | Ràng buộc |
|---|---|
| `email` | Email hợp lệ; bỏ khoảng trắng ngoài, chuyển chữ thường |
| `password` | Chuỗi 8–128 ký tự; chỉ lưu bản băm |
| `display_name` | Sau khi trim còn 1–80 ký tự |
| `skill_level` | Một trong 19 mã trình của `SkillLevel` |
| `gender` | `MALE` hoặc `FEMALE` |

Thiếu trường, sai kiểu, giá trị enum sai hoặc thừa trường đều trả 422. Đăng nhập chỉ nhận `email`, `password`; thông báo sai thông tin không tiết lộ email có tồn tại hay không.

- Schema kiểm hình dạng dữ liệu trước sau đó service kiểm email trùng rồi băm mật khẩu. Đăng ký thành công chỉ tạo hồ sơ. Token được cấp sau bước đăng nhập và được middleware kiểm trước API bảo vệ.

</details>

<details>
<summary><strong>2. Chọn tạo kèo — nhập gì, nhập sai thì sao — FR-05</strong></summary>

Không chọn tạo kèo thì đi sang tìm kèo hoặc matching ở mục 3 và 5.

```mermaid
flowchart TD
    A["Chọn tạo kèo; gửi JWT"] --> B["Nhập dữ liệu POST /sessions"]
    B --> C{"Đúng kiểu, trường bắt buộc, enum, timezone?"}
    C -->|Không| D["422 VALIDATION_ERROR → sửa dữ liệu rồi gửi lại"]
    D --> B
    C -->|Có| E["Mở transaction ghi; đọc thời gian sau khi lấy khóa"]
    E --> F{"Lịch tương lai, dài 60–240 phút; min_level ≤ max_level?"}
    F -->|Không| G["422 INVALID_TIME_WINDOW hoặc VALIDATION_ERROR"]
    G --> B
    F -->|Có| H{"Sân tồn tại và hoạt động?"}
    H -->|Không tồn tại| I["404 VENUE_NOT_FOUND → chọn sân khác"]
    H -->|Ngừng hoạt động| J["409 VENUE_INACTIVE → chọn sân khác"]
    H -->|Có| K{"Hồ sơ host phù hợp, không trùng lịch ACCEPTED?"}
    K -->|Không| L["409 PROFILE_INCOMPLETE, ELIGIBILITY_MISMATCH hoặc TIME_CONFLICT"]
    K -->|Có| M["Tạo session OPEN và lượt host ACCEPTED; đóng matching chồng giờ của host"]
    M --> N["Commit một lần → 201 SessionDetail"]
```

| Dữ liệu tạo kèo | Ràng buộc |
|---|---|
| `venue_id` | ID sân là số nguyên dương, sân tồn tại và đang hoạt động |
| `title`, `notes` | Tiêu đề sau trim 1–120 ký tự; ghi chú tùy chọn, tối đa 1000 ký tự |
| `starts_at`, `ends_at` | ISO 8601 có múi giờ; bắt đầu ở tương lai; thời lượng 60–240 phút |
| `play_type` | `SINGLES` → 2 người; `DOUBLES` → 4 người, đều tính host |
| `fee_male_vnd`, `fee_female_vnd` | Số nguyên VND không âm |
| `min_level`, `max_level` | Mã trình hợp lệ, min không cao hơn max; host nằm trong khoảng |
| `gender_policy` | `ANY` mặc định, hoặc `MALE_ONLY`/`FEMALE_ONLY`; host cũng phải phù hợp |

 `host_user_id`, capacity và trạng thái do hệ thống xác định. Khi lỗi, transaction rollback; không để lại session thiếu lượt host.

- Host là tài khoản lấy từ JWT. Sau khi các kiểm tra đạt, repository ghi cả kèo và lượt host trên cùng connection; router trả chi tiết kèo. Client không được coi một lỗi 409 là tạo kèo thành công.

</details>

<details>
<summary><strong>3. Không tạo kèo — tìm, xem và xin tham gia — FR-03, FR-04, FR-06, FR-08</strong></summary>

```mermaid
flowchart TD
    A["Không tạo kèo"] --> B["GET /venues hoặc GET /sessions"]
    B --> C{"Bộ lọc hợp lệ?"}
    C -->|Không| D["422 → sửa bộ lọc"]
    D --> B
    C -->|Có| E{"Có kết quả phù hợp?"}
    E -->|Không| F["200: items rỗng → đổi bộ lọc hoặc dùng matching"]
    E -->|Có| G["Đăng nhập nếu cần; GET /sessions/session_id"]
    G --> H{"Kèo tồn tại?"}
    H -->|Không| I["404 SESSION_NOT_FOUND → chọn lại kèo"]
    H -->|Có| J["200: xem lịch, phí, số chỗ và trạng thái"]
    J --> K{"Muốn tham gia?"}
    K -->|Không| B
    K -->|Có| L["POST /participations: session_id; gửi JWT"]
    L --> M{"Kèo còn mở, chưa bắt đầu, còn chỗ?"}
    M -->|Không| N["409 SESSION_CANCELLED, SESSION_ALREADY_STARTED hoặc SESSION_FULL"]
    M -->|Có| O{"Đủ điều kiện, chưa có lượt hoạt động và không trùng lịch?"}
    O -->|Không| P["409 PROFILE_INCOMPLETE, ELIGIBILITY_MISMATCH, PARTICIPATION_ALREADY_EXISTS hoặc TIME_CONFLICT"]
    O -->|Có| Q["Lưu PENDING, giới tính và phí tại lúc xin; commit → 201"]
    Q --> R["Chờ host duyệt; PENDING chưa giữ chỗ"]
```

**Bộ lọc:** `district_code`, `venue_id`, `play_type`, `skill_level`, `gender`, `max_fee_vnd`, `available_from/available_to`, `only_available`, `host_me`, `limit/offset`. Hai mốc available phải cùng có hoặc cùng vắng, mốc đầu nhỏ hơn mốc cuối; thời gian có múi giờ, phí không âm, limit 1–100 và offset không âm. Tìm sân chỉ dùng quận và phân trang. `host_me=true` cần JWT và lấy kèo của tài khoản hiện tại.

**Detail:** trả số chỗ tính từ `ACCEPTED`, lượt của người xem và cờ `can_cancel/can_decide`; host nhận thêm danh sách quản lý. `AVAILABLE/FULL/STARTED/ENDED` là trạng thái hiển thị được tính từ lịch và số người, không phải bốn trạng thái session được ghi vào DB.

- Hệ thống kiểm lại dữ liệu khi nhận yêu cầu, không tin số chỗ đã xem trước đó. Xin tham gia chỉ tạo PENDING. Khi nhiều người cùng xin một chỗ, quyết định duyệt vẫn phải kiểm capacity lần nữa.

</details>

<details>
<summary><strong>4. Host duyệt/từ chối, người chơi rút hoặc host hủy — FR-07, FR-09, FR-10</strong></summary>

```mermaid
flowchart TD
    A["Xem chi tiết kèo và lượt tham gia"] --> B{"Thao tác nào?"}
    B -->|Duyệt hoặc từ chối| C["POST /participations/id/decision: APPROVE hoặc REJECT"]
    C --> D{"Lượt tồn tại, actor là host, trạng thái PENDING; kèo mở và chưa bắt đầu?"}
    D -->|Không| E["404 không tồn tại; 403 sai quyền; 409 sai trạng thái hoặc đã bắt đầu/hủy"]
    D -->|Có| F{"Quyết định?"}
    F -->|REJECT| G["Ghi REJECTED → 200; không cần kiểm số chỗ hay điều kiện tuyển"]
    F -->|APPROVE| H{"Hồ sơ hiện tại hợp lệ, còn chỗ, không trùng lịch ACCEPTED?"}
    H -->|Không| I["409 → giữ nguyên PENDING, rollback"]
    H -->|Có| J["Ghi ACCEPTED; đóng matching chồng giờ; commit → 200"]
    B -->|Rút lượt| K["DELETE /participations/id; không có body"]
    K --> L{"Đúng chủ lượt và không phải lượt host?"}
    L -->|Không| M["403 FORBIDDEN hoặc 409 HOST_PARTICIPATION_REQUIRED"]
    L -->|Có| N{"Trạng thái lượt?"}
    N -->|Đã CANCELLED| O["200 bản cũ; không đổi timestamp"]
    N -->|REJECTED| P["409 INVALID_STATE"]
    N -->|PENDING hoặc ACCEPTED| Q{"Kèo mở và chưa bắt đầu?"}
    Q -->|Không| R["409; không rút được"]
    Q -->|Có| S["Ghi CANCELLED → 200; không mở lại matching đã đóng"]
    B -->|Hủy kèo| T["Host: DELETE /sessions/id; không có body"]
    T --> U{"Kèo tồn tại và đúng host?"}
    U -->|Không| V["404 SESSION_NOT_FOUND hoặc 403 FORBIDDEN"]
    U -->|Có| W{"Đã hủy hoặc đã bắt đầu?"}
    W -->|Đã hủy| X["200 chi tiết hiện tại; không hủy lần hai"]
    W -->|Đã bắt đầu| Y["409 SESSION_ALREADY_STARTED"]
    W -->|Chưa bắt đầu| Z["Một transaction: session và mọi PENDING/ACCEPTED → CANCELLED; trả 200"]
```

ID không hợp lệ, body quyết định thiếu/sai/thừa trường trả 422. Luồng rút/duyệt cũng trả 404 nếu không tìm thấy lượt hoặc kèo. Mỗi nhánh thành công trả chi tiết hiện tại, không trả lời thành công trước commit.

- Duyệt không chỉ đổi trạng thái; nó xác nhận lịch nên phải đóng matching chồng giờ trong cùng transaction. REJECT không chiếm chỗ. Rút và hủy có thể gọi lặp an toàn; đăng ký lại sau rút/từ chối tạo lượt mới, không sửa lịch sử cũ.

</details>

<details>
<summary><strong>5. Không chọn kèo có sẵn — gửi yêu cầu matching — FR-11</strong></summary>

```mermaid
flowchart TD
    A["POST /matching/requests; gửi JWT"] --> B["Nhập sân, giờ, loại kèo, phí nam/nữ đề xuất, ngân sách và policy giới tính"]
    B --> C{"Schema và thời gian hợp lệ?"}
    C -->|Không| D["422 → sửa dữ liệu; không tạo yêu cầu"]
    C -->|Có| E{"Sân tồn tại/hoạt động; hồ sơ phù hợp; phí bản thân không vượt ngân sách; không trùng lịch?"}
    E -->|Không| F["404 sân không tồn tại; 409 điều kiện/lịch; 422 vượt ngân sách"]
    E -->|Có| G["Đóng yêu cầu ACTIVE cũ của người gửi với REPLACED; tạo yêu cầu mới ACTIVE"]
    G --> H["Lấy ứng viên ACTIVE chưa hết hạn, cùng sân, giờ chính xác và loại kèo; loại lịch ACCEPTED chồng giờ"]
    H --> I{"Đủ 2/4 người, chênh trình ≤ 2 bậc, mọi policy và ngân sách phù hợp?"}
    I -->|Không| J["201: request mới và suggestion=null"]
    I -->|Có| K["201: request và suggestion đủ nhóm; requires_confirmation=true"]
    J --> L["Không tự tạo session hoặc participation"]
    K --> L
```

Tên trường: `venue_id`, `starts_at`, `ends_at`, `play_type`, `proposed_fee_male_vnd`, `proposed_fee_female_vnd`, `budget_max_vnd`, `gender_policy` (mặc định `ANY`). ID/phí, thời lượng và múi giờ tuân theo giới hạn tương tự tạo kèo. Mức phí của nhóm gợi ý lấy theo đề xuất của người gọi và phải nằm trong ngân sách từng thành viên.

- Matching là gợi ý, không phải một lượt đặt chỗ. Không đủ nhóm là kết quả bình thường `suggestion=null`. Yêu cầu mới thay yêu cầu ACTIVE cũ; được xác nhận lịch ở tạo/duyệt kèo sẽ đóng matching liên quan.

</details>

<details>
<summary><strong>6. Từ HTTP đến DB — lỗi chung, commit và rollback</strong></summary>

```mermaid
flowchart TD
    A["HTTP request"] --> B{"JWT cần thiết và hợp lệ?"}
    B -->|Không| C["401 UNAUTHORIZED"]
    B -->|Có hoặc route công khai| D{"Schema đúng?"}
    D -->|Không| E["422 VALIDATION_ERROR; không ghi DB"]
    D -->|Có| F{"Đọc hay ghi?"}
    F -->|Đọc| G["BEGIN; đọc snapshot; không commit ghi"]
    F -->|Ghi| H["BEGIN IMMEDIATE; chờ khóa tối đa cấu hình"]
    H --> I{"Lấy được khóa?"}
    I -->|Không| J["503 DATABASE_BUSY; Retry-After: 1"]
    I -->|Có| K["Đọc Clock; kiểm quyền, trạng thái, capacity và lịch"]
    K --> L{"Nghiệp vụ hợp lệ?"}
    L -->|Không| M["Rollback → 403, 404, 409 hoặc 422 theo mã lỗi"]
    L -->|Có| N["Ghi và đọc dữ liệu trả về trên cùng connection"]
    N --> O["Commit một lần → trả response thành công"]
    G --> P["Trả kết quả tra cứu"]
    N -->|Lỗi kỹ thuật| Q["Rollback; 500 INTERNAL_ERROR; không gửi SQL hoặc exception ra client"]
```

- JWT middleware chạy trước router; thứ tự trả lỗi cụ thể còn phụ thuộc thứ tự kiểm tra trong service. Error envelope có `code`, `message`, `details`, `request_id` trong `error`; không đưa password/token hoặc câu SQL vào lỗi trả cho client.

- Hai yêu cầu duyệt không thể cùng xác nhận chỗ cuối dựa trên một dữ liệu cũ. Thao tác sau lấy được khóa phải kiểm lại số người đã ACCEPTED. Nếu hết thời gian chờ, client nhận 503 rõ ràng; hệ thống không bỏ kiểm tra hoặc tự coi yêu cầu thành công.

</details>
