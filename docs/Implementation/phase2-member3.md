# Kế hoạch thực hiện Phase2 của member3

Ngày lập: **21/11/2026**. Người thực hiện: **Member 3**.

**Quy ước tài liệu:** kế hoạch, tiến độ, bằng chứng, hướng dẫn chạy và bàn giao
Phase2 của member3 được ghi duy nhất trong file này. Kết quả hiện hành ở mục 14;
hướng dẫn ingress ở mục 15. Các mục ngày 21/11 giữ làm lịch sử triển khai.
Đợt refactor cách viết và thư mục ngày 24/11 được ghi riêng ở mục 16.

Phạm vi là **Phase2 của kế hoạch triển khai giai đoạn 2**: refactor Catalog,
Matching và Discovery trên SQLite, bổ sung kiểm thử kiến trúc và soạn cấu hình
ingress. Mục tiêu là có bản SQLite giữ nguyên hành vi để tích hợp PostgreSQL ở
Phase3 ngày 23–24/11. Trạng thái thực hiện được ghi trong checklist; kết quả
làm mốc trước refactor nằm ở mục 6. **Cập nhật 22/11: phạm vi Phase2 của member3
đã hoàn thành trên SQLite; kết quả hiện hành ở mục 14.**

Nguồn: [kế hoạch chung](../Architecture_Phase2/kehoachtrienkhai-VN.md),
[bàn giao Phase1](phase1.md) và [hợp đồng member3](phase1-member3.md).

## 1. Thứ tự và lịch dự kiến

Mốc Phase2 ban đầu là 18–20/11 và đã qua. Lịch bù đề xuất dành ngày 21–22/11
cho refactor và kiểm chứng SQLite; ngày 23/11 xử lý tích hợp còn vướng trước mốc
PostgreSQL 24/11. Ước lượng phụ thuộc thời gian làm việc và việc member1 bàn giao
port, reader và wiring; không thay đổi lịch chung của nhóm.

1. **21/11:** ghi mốc trước refactor, thống nhất vị trí nối dependency với member1,
   tách Strategy thuần và triển khai Catalog.
2. **22/11:** tách Matching command/repository, chuyển writer, nối reader
   Identity/Catalog, kiểm chứng Discovery và bổ sung kiểm thử kiến trúc.
3. **Cuối 22/11:** hoàn thiện bản cấu hình ingress, chạy hồi quy SQLite, demo và
   ghi commit bàn giao. Có thể soạn ingress trong lúc chờ port của member1.
4. **23/11:** xử lý lỗi tích hợp cùng member1/2 và chuyển sang Phase3. Nếu chưa
   đạt nghiệm thu SQLite thì ghi rõ mục còn thiếu, chưa đánh dấu hoàn tất.

Ưu tiên Strategy → Catalog → Matching command/writer → kiểm thử kiến trúc và
hồi quy. Không cần chờ PostgreSQL để bắt đầu phần thuần Python và SQLite.

## 2. Phần cần phối hợp

Đã kiểm tra hợp đồng và code trong checkout ngày 21/11/2026; kết quả, các điểm
nối hiện tại và phần cần member1 bàn giao được ghi ở mục 7.

**Member1 sở hữu** `PlayerProfile`, `PlayerProfileReader`, `PlayerProfilesReader`
tại `app/features/auth/contracts.py`, composition root và wiring Sessions.
Member3 dùng các hợp đồng đã chốt, không tạo bộ profile port song song. Reader
và wiring thực đã được bổ sung trong lượt tích hợp ngày 22/11 theo đúng hợp đồng,
xem báo cáo tại mục 14.

**Member3 bàn giao** reader Catalog và writer mới cho member1 nối vào tạo
kèo/phê duyệt và detail Sessions. Member3 nối phần Matching của mình và phối hợp
kiểm chứng rollback xuyên module. Chỉ xóa adapter cũ sau khi wiring/test đã chuyển.

**Member2 hỗ trợ** UoW/session provider, SQL và cấu hình triển khai. Reader,
repository và writer dùng transaction bên gọi. Thống nhất vị trí file proxy,
network và certificate trước khi sửa Compose dùng chung. Khóa hàng PostgreSQL
và fixture tranh chấp thực thuộc Phase3; không dùng stub khóa luôn thành công
để tuyên bố đã kiểm chứng khóa.

## 3. Các gói công việc

### 3.1. Ghi mốc trước refactor

- [x] Ghi commit xuất phát và kết quả test tại mục 6.
- [x] Chạy corpus Matching, test Discovery, writer, privacy và kiến trúc hiện có.
- [x] Giữ dữ liệu và kết quả mong đợi của
  `tests/integration/test_phase1_matching_corpus.py`; sau refactor chỉ đổi wiring
  cần thiết để corpus vẫn kiểm cùng hành vi qua HTTP.

Lần rà soát trước trên checkout `90e8fcd` đạt **290 passed, 12 skipped**;
12 ca bỏ qua cần Locust. Đây là mốc trước triển khai, không phải kết quả Phase2.

### 3.2. Tách Strategy chọn nhóm

Vị trí dự kiến: `app/features/matching/domain/strategy.py`. Chuyển `find_group`,
kiểm tra nhóm và tạo gợi ý khỏi `app/features/discovery/service.py`; Matching
sở hữu các kiểu dữ liệu phục vụ việc ghép nhóm.

- [x] Strategy chỉ nhận dữ liệu Python và trả gợi ý hoặc `None`; không query DB,
  đọc đồng hồ hệ thống hoặc commit.
- [x] Giữ order `(created_at, id)` và chọn tổ hợp hợp lệ đầu tiên.
- [x] Giữ đơn/đôi, rank spread tối đa 2, policy của mọi thành viên và ngân sách
  theo mức phí trong request người gọi.
- [x] Viết unit test không/thiếu ứng viên, sai rank/policy/ngân sách, nhiều nhóm
  hợp lệ, đồng hạng và ranh giới rank lệch 2 so với 3.

**Đạt khi:** Strategy kiểm thử được không cần FastAPI/SQLAlchemy; endpoint sau
khi nối Strategy vẫn đạt đủ 8 ca corpus.

### 3.3. Triển khai Catalog

Hợp đồng tại `app/features/catalog/contracts.py`; adapter dự kiến trong
`app/features/catalog/infrastructure/`. Tái sử dụng model sân hiện có.

- [x] Công bố `VenueStatusReader`, `VenueSummary` năm trường và `VenueReader`
  đơn/batch đúng mục 10.1 của bàn giao member3.
- [x] Status reader phân biệt `None`/`False`/`True`; reader hiển thị trả cả sân
  inactive cho lịch sử.
- [x] Nối Matching với reader Catalog và giữ VENUE_NOT_FOUND/VENUE_INACTIVE
  tương ứng khi tích hợp command.
- [x] Batch loại ID trùng, rỗng không query, thiếu ID không có key, tối đa
  500 ID/câu query; không giới hạn tổng số ID nghiệp vụ.
- [x] Adapter SELECT projection đã chốt, trả DTO, dùng session bên gọi,
  không mở transaction hoặc commit riêng.
- [x] Kiểm active/inactive/missing, batch rỗng/trùng và trên 500 ID; ghi cách
  inject reader cho member1 tại mục 11.1.

**Đạt khi:** Matching đọc trạng thái sân qua port Catalog; member1 có reader
thực để tích hợp Sessions; không tạo model venue thứ hai.

### 3.4. Tách Matching command khỏi Discovery

Vị trí dự kiến: `app/features/matching/service.py`, `contracts.py`, `router.py`,
`schemas.py` và `infrastructure/`. Giữ endpoint `POST /matching/requests`.
Discovery giữ use case tìm kiếm sân/kèo.

- [x] Chuyển command/DTO/persistence Matching về module Matching. Router xử lý
  HTTP/ánh xạ; wiring đặt tại vị trí thống nhất với member1.
- [x] Giữ một `uow.write()` và một lần commit cho kiểm tra lịch, đóng request
  cũ, tạo request mới, đọc ứng viên và tính gợi ý.
- [x] Dùng profile reader Identity cho caller và batch reader cho ứng viên;
  không query từng user. Đổi enum sang rank bằng `skill_to_rank()` cho cả hai.
- [x] Loại candidate thiếu profile/UNSPECIFIED, giữ thứ tự request khi ghép
  profile. Caller thiếu vẫn UNAUTHORIZED, UNSPECIFIED vẫn PROFILE_INCOMPLETE.
- [x] Giữ bộ lọc ACTIVE, sân/giờ/loại trận, chưa bắt đầu, loại caller và lịch
  ACCEPTED chồng giờ; không cắt top-K hay biến lỗi query thành gợi ý rỗng.
- [x] Không có nhóm vẫn lưu request và trả `suggestion=null`. Gửi lại thành
  công tạo ID mới, đóng bản cũ bằng REPLACED; lỗi phải rollback toàn bộ.
- [x] Kiểm batch thiếu hồ sơ, mapping rank, corpus và lỗi create/selection/commit
  sau khi đóng request cũ để xác minh request cũ còn nguyên.

**Đạt khi:** Discovery không còn command ghi Matching; Matching không import
contracts nội bộ Discovery; response và ưu tiên xác thực giữ tương thích.

### 3.5. Chuyển writer và kiểm chứng Discovery

- [x] Chuyển adapter duy nhất từ `app/db/matching_request_writer.py` sang
  `app/features/matching/infrastructure/matching_request_writer.py`, giữ lớp
  `SqlAlchemyMatchingRequestWriter` và port trong `app/domain/ports.py`.
- [x] Phối hợp member1 đổi wiring tạo kèo/phê duyệt và cập nhật test rồi mới xóa
  đường dẫn cũ; không giữ hai implementation độc lập.
- [x] Kiểm writer chỉ đóng ACTIVE của đúng user giao giờ thực bằng CONFIRMED;
  giữ lịch nối tiếp/người khác/lịch sử. Writer không commit riêng.
- [x] Kiểm lỗi writer khiến cả thay đổi Sessions và Matching rollback.
- [x] Giữ join projection đọc trong adapter Discovery; filter/count/order trước
  phân trang. Kiểm sân active, quận, limit/offset và các bộ lọc tìm kèo hiện có.
- [x] Giữ `host_me=true` cần JWT; detail chỉ host có `management`, người xem chỉ
  thấy `my_participations` của mình; gợi ý không lộ email/ngân sách người khác.

**Đạt khi:** luồng tạo → tham gia → phê duyệt đóng đúng Matching; các test
writer/privacy và truy vấn Discovery đạt trên SQLite.

### 3.6. Mở rộng kiểm thử kiến trúc

- [x] Mở rộng `tests/test_architecture.py` quét package mới, gồm Strategy/domain
  và application thay vì chỉ tên `*service.py`.
- [x] Giữ domain/application/contracts không import FastAPI/Pydantic/SQLAlchemy
  hoặc `app.db`; SQL và persistence nằm trong infrastructure.
- [x] Phát hiện chu trình import module, kể cả import tương đối; cấm use case
  import adapter/repository nội bộ của module khác.
- [x] Cho phép composition root nối adapter; read adapter chỉ join projection
  đã chốt, không mở ngoại lệ chung cho mọi import xuyên module.
- [x] Kiểm bằng mẫu import vi phạm để chứng minh phát hiện import bị cấm/chu
  trình và chấp nhận các dependency hợp lệ.

**Đạt khi:** bản refactor vượt kiểm tra và có bằng chứng bộ kiểm tra bắt được
vi phạm; wiring/projection hợp lệ không bị chặn nhầm.

### 3.7. Soạn cấu hình ingress

- [x] Soạn cấu hình reverse proxy và hướng dẫn TLS local, body limit, timeout
  và rate limit; ghi đường dẫn cấu hình để member2 tích hợp.
- [x] Giữ HTTPS proxy → API → DB, chỉ ingress công khai; certificate/private
  key truyền qua cấu hình chạy, không commit private key.
- [x] Giữ upstream response timeout khởi điểm 30 giây và tắt retry upstream
  POST; body/rate/burst là cấu hình demo cần đo và hiệu chỉnh sau.
- [x] Lập phương án rate limit theo user/tài khoản chuẩn hóa do backend xác
  minh, ngoài giới hạn theo IP ở ingress; không tin header user ID từ client.
- [x] Ghi quy tắc chỉ tin forwarded header từ proxy. Kiểm cú pháp cấu hình,
  HTTPS local và body vượt giới hạn khi có môi trường proxy chạy được.

**Đạt khi:** có cấu hình và lệnh chạy/kiểm tra tái lập để member2 ghép vào
Compose. Rate limit theo danh tính, telemetry runtime và demo 429 đầy đủ được
nghiệm thu ở Phase3–4 theo kế hoạch chung.

## 4. Kiểm chứng và điều kiện đóng Phase2

Chạy test tương ứng sau mỗi gói, rồi toàn bộ suite trước bàn giao. Cài
`requirements-load.txt` nếu cần chạy cả ca Locust; ghi riêng skipped và lý do.

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m pytest -q -rs
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m ruff format --check app tests scripts
git diff --check
```

- [x] Đạt 8 ca corpus với cùng dữ liệu và kết quả mong đợi.
- [x] Đạt test Strategy, Catalog, batch profile, rollback, writer, Discovery,
  privacy và kiến trúc; toàn bộ suite không có lỗi hồi quy SQLite.
- [x] Demo Matching không nhóm, thay request, first-valid và luồng tạo kèo →
  tham gia → phê duyệt đóng request chồng giờ.
- [x] Reader/writer thực đã được nối cho Sessions/Matching tại composition root;
  phần hỗ trợ Identity/member1 được ghi rõ trong báo cáo 22/11.
- [x] Có cấu hình ingress, hướng dẫn chạy và kết quả kiểm tra HTTPS/413/429 tương ứng.
- [x] Ghi commit SQLite sau refactor làm mốc cho benchmark sau tích hợp.

## 5. Bàn giao sang Phase3

Bàn giao đường dẫn port/adapter, cách inject Strategy/reader/writer, commit
refactor, kết quả test và lỗi tích hợp còn mở cho member1/2.

Phase3 tiếp tục lấy khóa user chung khi tạo Matching, đọc lại Clock/hồ sơ/lịch
sau khóa, kiểm tranh chấp Matching với tạo kèo/phê duyệt trên PostgreSQL và
triển khai telemetry HTTP/Matching theo [đặc tả chung](member2-telemetry-va-backup.md).
Snapshot đọc PostgreSQL, hook DB, migration/import và fixture do member2 phối hợp
triển khai. Kết quả SQLite không thay thế bằng chứng PostgreSQL.

Khi đóng Phase2, bổ sung tại đây: commit bàn giao; lệnh/kết quả test; ca skipped;
kết quả demo/proxy; trạng thái wiring member1; phần chuyển tiếp Phase3.

## 6. Kết quả làm mốc trước refactor ngày 21/11/2026

**Commit xuất phát:** `90e8fcd8acf60720f361b4c04404ae9e1b9624d5`, nhánh `main`.
Working tree có thay đổi staged/unstaged trong `.dockerignore`, `.gitignore`
và file kế hoạch này chưa được Git theo dõi. Không có thay đổi so với HEAD ở
`app/`, `tests/`, `scripts/` hoặc các file cấu hình Python/dependency đã kiểm tra.
Hash SHA-256 của các file Python và cấu hình được lưu trong manifest và giữ
nguyên sau lần chạy. Bước 1 đã hoàn tất; chưa bắt đầu refactor.

**Môi trường:** Windows, Python 3.14.2, pytest 9.1.1, dependency trong `.venv`
theo `requirements-dev.txt`. Locust chưa cài. Chạy ngoài sandbox vì TestClient
đã treo khi chạy trong sandbox ở lần rà soát trước; các fixture dùng SQLite tạm.

Lệnh thực tế, với `PYTHONUTF8=1`:

```powershell
.venv/Scripts/python.exe -u -m pytest -q -rs --junitxml=artifacts/member3-phase2-baseline-2026-11-21/pytest.xml
```

- **290 passed, 12 skipped, 0 failed, 0 errors**, thời lượng pytest **36,58 giây**,
  exit code **0**. Có đủ **8/8 ca corpus Matching đạt**.
- Skipped: 1 ca trong `tests/load/test_runner.py` và 11 ca trong
  `tests/load/test_workloads.py`; đều cần dependency trong `requirements-load.txt`.
  Kết quả này không xác nhận các ca workload đã đạt.
- Có 2 warning hiện có: AnyIO BlockingPortal deprecated và khóa HS512 ngắn
  trong ca kiểm tra từ chối thuật toán JWT khác.
- `ruff check app tests scripts`: đạt. `ruff format --check app tests scripts`:
  99 file đúng định dạng. `git diff --check`: đạt.

Bằng chứng cục bộ:
[log pytest](../../artifacts/member3-phase2-baseline-2026-11-21/pytest.txt),
[JUnit XML](../../artifacts/member3-phase2-baseline-2026-11-21/pytest.xml),
[manifest commit và môi trường](../../artifacts/member3-phase2-baseline-2026-11-21/manifest.json),
[tổng hợp kết quả](../../artifacts/member3-phase2-baseline-2026-11-21/summary.json).
Thư mục `artifacts/` được Git bỏ qua; các file bằng chứng hiện nằm trên máy này.

Khi kiểm chứng sau refactor, dùng cùng corpus, ghi lại môi trường/dependency và
so sánh kết quả với mốc này. Nếu cài thêm Locust, phân biệt các ca mới chạy được
với 290 ca đã đạt để tránh coi thay đổi phạm vi chạy là thay đổi hành vi ứng dụng.

## 7. Kết quả kiểm tra phụ thuộc member1 ngày 21/11/2026

**Bước 2 trong danh sách công việc ngày 21/11 đã hoàn thành phần kiểm tra.**
Đối chiếu checkout `90e8fcd8acf60720f361b4c04404ae9e1b9624d5` với xác nhận
[member1 mục 1.2](phase1-member1.md#12-xác-nhận-chính-thức-từ-thành-viên-1) và
[member3 mục 11](phase1-member3.md#11-xác-nhận-hiện-hành-sau-cập-nhật-member-12).
Thiết kế đã chốt ngày 19/11; code reader và wiring mới chưa có trong checkout
này. Kết quả không phản ánh các nhánh hoặc máy khác của thành viên trong nhóm.

### 7.1. Hợp đồng Identity cần sử dụng

- [x] Xác nhận nguồn và quyền sở hữu: Identity/member1 công bố hợp đồng tại
  `app/features/auth/contracts.py`; member3 sử dụng qua dependency injection.
- [x] Ghi đúng DTO `PlayerProfile`: `id`, `display_name`,
  `skill_level: SkillLevel`, `gender: Gender`; không có email/password hash.
- [x] Ghi đúng reader đơn `get_by_id(user_id: int) -> PlayerProfile | None` và
  reader batch `get_by_ids(user_ids: list[int]) -> dict[int, PlayerProfile]`.
- [x] Giữ batch loại ID trùng, rỗng trả `{}` không query, thiếu ID không có key;
  dùng cùng session/transaction bên gọi, không tự mở UoW hoặc commit.
- [x] Giữ `skill_to_rank()` cho caller và candidate, loại candidate thiếu
  profile/UNSPECIFIED, giữ thứ tự request và lỗi caller hiện hành.

Trong [contracts Auth hiện tại](../../app/features/auth/contracts.py), chỉ có
DTO `User`, repository và các hợp đồng xác thực; chưa có ba khai báo
`PlayerProfile`, `PlayerProfileReader`, `PlayerProfilesReader`. Tìm toàn bộ
`app/` chưa thấy implementation tương ứng hoặc reader profile theo batch.
`UserRepository.get_by_id()` trả `User` có email, nên không coi nó là reader
profile tối thiểu đã được bàn giao.

### 7.2. Các điểm nối hiện tại cần chuyển khi tích hợp

- [Discovery dependencies](../../app/features/discovery/dependencies.py) tạo
  một UoW dùng chung cho repository đọc và Matching. Command còn ở Discovery;
  [Matching repository](../../app/features/discovery/repository.py) đọc trực
  tiếp `UserModel` cho caller và join user khi lấy ứng viên. Chưa inject reader
  Identity hoặc Catalog vào command.
- [Auth dependencies](../../app/features/auth/dependencies.py) có hàm
  `lookup_authenticated_user()` mở UoW đọc riêng để xác thực. Không dùng hàm này
  thay reader trong command Matching vì sẽ tách transaction của bên gọi.
- [Entry point](../../app/main.py) đăng ký router và provider, nhưng chưa có
  wiring Matching/Catalog/profile mới. Vị trí composition root chính thức khi
  refactor do member1 bàn giao; không coi một file/provider mới đã tồn tại.
- [Sessions router](../../app/features/sessions/session_router.py) còn tạo UoW
  và repository trong provider. Luồng tạo kèo gọi writer gián tiếp từ
  [Sessions repository](../../app/features/sessions/session_repository.py).
- [Participation dependencies](../../app/features/sessions/participation_dependencies.py)
  đã inject writer vào service bằng `lambda: uow.session`, cùng transaction với
  repository. Adapter vẫn ở `app/db/matching_request_writer.py`; phải chuyển
  wiring và test khi member3 chuyển adapter về Matching.
- [Domain ports](../../app/domain/ports.py) đã có `Clock`, `UnitOfWork` và
  `MatchingRequestWriter`; chưa có `TransactionLocks`. Port/adapter khóa và kiểm
  chứng PostgreSQL được nối theo kế hoạch tích hợp Phase3 với member1/2.

### 7.3. Phần cần member1 bàn giao trước nghiệm thu tích hợp

- [ ] Công bố DTO/port reader đơn và batch đúng hợp đồng ở mục 7.1.
- [ ] Bàn giao implementation reader, đường dẫn import và cách nhận session
  provider của UoW bên gọi; kèm bằng chứng batch không query từng user, chỉ đọc
  bốn trường công khai và không tự commit.
- [ ] Bàn giao provider/composition root thực để nối reader Identity, Catalog,
  Strategy và writer. Member3 cung cấp các adapter thuộc phạm vi của mình.
- [ ] Chuyển cả wiring tạo kèo và phê duyệt sang writer tại đường dẫn mới, nối
  Catalog reader vào Sessions/detail và xác minh rollback chung khi tích hợp.

Đây là danh sách bàn giao dựa trên hợp đồng đã được xác nhận, không phải yêu
cầu xác nhận lại thiết kế hay thông báo đã gửi tới member1. Chỉ đánh dấu các mục
trên sau khi code thực đã có và được kiểm chứng trong bản tích hợp.

### 7.4. Công việc member3 có thể làm ngay

Sau lần kiểm tra phụ thuộc, **bước 3: tách Strategy thuần** đã hoàn thành và có
unit test tại mục 8. Có thể triển khai Catalog theo hợp đồng đã chốt; phần này
không cần reader Identity mới.
Khi tách command, chỉ inject reader thực sau khi member1 bàn giao; không tạo
profile port trùng hoặc gọi adapter Auth trực tiếp từ use case để vượt phụ thuộc.

Lần kiểm tra phụ thuộc member1 trước bước 3 chỉ cập nhật tài liệu phối hợp;
code và kiểm thử lúc đó giữ nguyên so với bước 1. Kết quả refactor và lần chạy
suite sau bước 3 được ghi riêng bên dưới.

## 8. Kết quả tách Strategy ngày 21/11/2026

**Bước 3 trong danh sách công việc ngày 21/11 đã hoàn thành.**

- Tạo [Strategy thuần](../../app/features/matching/domain/strategy.py), chuyển
  nguyên 5 hàm `policy_allows`, `fee_for`, `group_is_valid`, `find_group` và
  `build_suggestion` từ Discovery. Đối chiếu AST với commit baseline xác nhận
  logic các hàm giữ nguyên.
- Chuyển 5 DTO phục vụ Strategy sang
  [Matching contracts](../../app/features/matching/contracts.py). Giữ nguyên
  các trường, kiểu và tính bất biến; Discovery re-export cùng lớp để các nơi
  đang dùng tiếp tục hoạt động. Matching không import module Discovery.
- [Discovery service](../../app/features/discovery/service.py) gọi Strategy mới;
  command, repository, router và transaction vẫn ở vị trí hiện tại để tiếp tục
  tách theo các gói sau.
- Bổ sung [28 unit test](../../tests/matching/test_strategy.py) về số ứng viên,
  rank toàn nhóm, policy, ngân sách theo giới tính và phí caller, thứ tự request,
  first-valid, dữ liệu gợi ý và việc không thay đổi danh sách đầu vào.
- Mở rộng [kiểm tra tầng nghiệp vụ](../../tests/test_architecture.py) để quét
  package domain Matching mới. Kiểm tra chu trình/import xuyên module đầy đủ
  tại gói 3.6 vẫn còn trong kế hoạch.

Kiểm chứng trên cùng môi trường Python 3.14.2 và dependency như baseline:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -u -m pytest -q -rs --junitxml=artifacts/member3-phase2-step3-2026-11-21.xml
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m ruff format --check app tests scripts
git diff --check
```

Kết quả **318 passed, 12 skipped, 2 warnings**, thời lượng pytest **36,98 giây**,
exit code 0. Bao gồm **28/28 unit test Strategy**, **8/8 corpus API** và kiểm
thử kiến trúc đạt. Số passed tăng đúng 28 ca so với baseline; các ca skipped và
warning giống baseline. Corpus Phase1 không đổi dữ liệu hay kết quả mong đợi.
Ruff đạt, 105 file đúng định dạng và diff không có lỗi whitespace.

Module Strategy còn được import bằng Python với `-S` để bỏ site-packages;
không cần FastAPI, Pydantic hoặc SQLAlchemy. Bằng chứng test cục bộ nằm tại
[JUnit XML bước 3](../../artifacts/member3-phase2-step3-2026-11-21.xml).

## 9. Kết quả kiểm thử Strategy ngày 21/11/2026

**Bước 4 trong danh sách công việc ngày 21/11 đã hoàn thành.**
Rà soát 28 ca của bước 3 và bổ sung 7 ca còn thiếu trong
[unit test Strategy](../../tests/matching/test_strategy.py):

- Bỏ qua ứng viên cũ hơn nhưng không hợp lệ rồi chọn người tiếp theo, kiểm
  riêng ba nguyên nhân rank, policy và ngân sách; giữ nguyên danh sách đầu vào.
- Chấp nhận nhóm nữ với caller nữ và policy FEMALE_ONLY, ngân sách bằng đúng
  phí nữ; kiểm kết quả gợi ý và mức phí từng thành viên.
- Với nhóm đôi, policy của một candidate phải chấp nhận cả các candidate khác,
  kể cả khi đã chấp nhận caller và chính người đó; kiểm cả MALE_ONLY/FEMALE_ONLY.
- Với nhóm đôi, tổng ngân sách đủ vẫn không hợp lệ nếu một người thiếu ngân
  sách của chính mình; không bù ngân sách giữa các thành viên.

Checklist kiểm thử của ngày:

- [x] Không/thiếu ứng viên, không có nhóm hợp lệ do rank/policy/ngân sách.
- [x] Nhiều nhóm hợp lệ, first-valid và đồng hạng phân xử bằng request ID.
- [x] Ranh giới rank lệch 2 được nhận, lệch 3 bị loại; kiểm độ chênh toàn nhóm.
- [x] Chạy lại 8 ca corpus API với dữ liệu và kết quả mong đợi giữ nguyên.

Lệnh chạy với `PYTHONUTF8=1`:

```powershell
.venv/Scripts/python.exe -u -m pytest -q -rs tests/matching/test_strategy.py tests/integration/test_phase1_matching_corpus.py tests/test_architecture.py --junitxml=artifacts/member3-phase2-step4-2026-11-21.xml
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m ruff format --check app tests scripts
git diff --check
```

Kết quả **44 passed, 0 skipped, 0 failed**, thời lượng pytest **1,63 giây**,
exit code 0: **35 unit test Strategy + 8 corpus API + 1 kiểm thử kiến trúc**.
Có 1 warning AnyIO BlockingPortal deprecated. Ruff, định dạng 105 file và
kiểm tra whitespace đều đạt. Xem [JUnit XML bước 4](../../artifacts/member3-phase2-step4-2026-11-21.xml).

Bước này chỉ bổ sung test và tài liệu, không sửa thuật toán hoặc code ứng dụng.
Lần chạy 44 ca tập trung vào Strategy/corpus/kiến trúc; kết quả toàn bộ suite
gần nhất vẫn là lần chạy ở bước 3, không cộng gộp thành một lần chạy mới.
Tiếp theo là **bước 5: tạo hợp đồng Catalog**.

## 10. Kết quả tạo hợp đồng Catalog ngày 21/11/2026

**Bước 5 trong danh sách công việc ngày 21/11 đã hoàn thành.**
Tạo package Catalog và công bố tại
[app/features/catalog/contracts.py](../../app/features/catalog/contracts.py):

- `VenueSummary` là frozen dataclass gồm đúng `id`, `name`, `address`,
  `district_code`, `is_active` theo hợp đồng Phase1.
- `VenueStatusReader.is_active(venue_id: int) -> bool | None`: None nghĩa là
  không có sân, False nghĩa là inactive, True nghĩa là active. Use case giữ
  trách nhiệm ánh xạ VENUE_NOT_FOUND/VENUE_INACTIVE.
- `VenueReader.get_by_id(venue_id: int) -> VenueSummary | None` và
  `get_by_ids(venue_ids: list[int]) -> dict[int, VenueSummary]` phục vụ projection
  đọc, gồm cả sân inactive cho lịch sử.

Docstring ghi nghĩa vụ adapter: cùng transaction bên gọi, không tự mở UoW/commit;
batch loại ID trùng, rỗng không query, bỏ ID thiếu, tối đa 500 ID mỗi câu query
và không giới hạn tổng đầu vào. Các hành vi DB này được triển khai ở bước 6 và
kiểm thử ở bước 7; khai báo Protocol chưa phải implementation.

Kiểm chứng đã đạt:

- Import với Python `-S`, không cần FastAPI/Pydantic/SQLAlchemy; kiểm tra đủ năm
  trường, kiểu, frozen dataclass và chữ ký ba phương thức bằng `get_type_hints`.
- `pytest -q tests/test_architecture.py`: **1 passed**, thời lượng **0,14 giây**,
  exit code 0; có 1 warning AnyIO hiện có. Test đã tự quét contracts Catalog mới.
- `ruff check app tests scripts`: đạt; `ruff format --check app tests scripts`:
  107 file đúng định dạng; `git diff --check`: đạt.

Xem [JUnit XML bước 5](../../artifacts/member3-phase2-step5-2026-11-21.xml).
Các file ứng dụng có sẵn giữ nguyên trong bước này; chưa nối reader vào endpoint
hay thay `VenueRecord` của Discovery. Tiếp theo là **bước 6: adapter Catalog trên SQLite**.

## 11. Kết quả triển khai adapter Catalog ngày 21/11/2026

**Bước 6 trong danh sách công việc ngày 21/11 đã hoàn thành.**
Tạo hai adapter tại
[infrastructure/venue_reader.py](../../app/features/catalog/infrastructure/venue_reader.py):

- `SqlAlchemyVenueStatusReader.is_active()` SELECT cột trạng thái, trả đúng
  True/False/None cho sân active/inactive/không tồn tại.
- `SqlAlchemyVenueReader.get_by_id()` SELECT đúng năm cột đã chốt và trả
  `VenueSummary` hoặc None; không loại sân inactive.
- `get_by_ids()` loại ID trùng trước khi chia batch, rỗng không lấy session,
  mỗi câu query tối đa 500 ID, bỏ ID thiếu và trả dict DTO. Không giới hạn tổng
  số ID hoặc phụ thuộc thứ tự trả về của SQL IN.

Adapter tái sử dụng `VenueModel`; không tạo model, engine, session hay transaction
mới và không tự commit. Chỉ infrastructure import SQLAlchemy và model lưu trữ.

### 11.1. Cách inject cho bên sử dụng

Khởi tạo adapter bằng callback lấy session từ **chính UoW của command/query**.
Callback giúp có thể nối dependency trước khi use case mở UoW:

```python
from app.features.catalog.infrastructure.venue_reader import (
    SqlAlchemyVenueReader,
    SqlAlchemyVenueStatusReader,
)

venue_reader = SqlAlchemyVenueReader(lambda: uow.session)
venue_status_reader = SqlAlchemyVenueStatusReader(lambda: uow.session)
```

Composition root inject các đối tượng này qua port `VenueReader` và
`VenueStatusReader`. Use case gọi reader trong `uow.read()` hoặc `uow.write()`;
command sở hữu commit. Chưa đổi wiring Sessions/Matching trong bước này.
`get_by_id()` có thể trả sân inactive cho detail/lịch sử; status reader phục vụ
kiểm tra lệnh, với None → VENUE_NOT_FOUND và False → VENUE_INACTIVE ở use case.

### 11.2. Kiểm chứng adapter trên SQLite

Thêm [test adapter Catalog](../../tests/catalog/test_venue_reader.py) dùng DB tạm:

- Ba ca status active/inactive/missing và DTO sân inactive dùng được sau khi
  transaction đóng.
- Batch rỗng không gọi session provider; batch lớn có 1.001 sân và một ID thiếu,
  kèm ID trùng, trả đủ 1.001 DTO bằng đúng ba SELECT. Tổng 1.002 tham số sau
  deduplicate, không query nào quá 500; mỗi SELECT projection có đúng năm cột.
- Trong UoW ghi, cả hai reader nhìn thấy thay đổi chưa commit của bên gọi.
  Sau khi thoát không commit, cập nhật và bản ghi mới đều rollback, xác minh
  reader không mở transaction riêng hoặc commit hộ caller.

Lệnh chạy với `PYTHONUTF8=1`:

```powershell
.venv/Scripts/python.exe -u -m pytest -q tests/catalog tests/test_architecture.py --junitxml=artifacts/member3-phase2-step6-2026-11-21.xml
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m ruff format --check app tests scripts
git diff --check
```

Kết quả **8 passed** gồm **7 ca adapter và 1 kiểm thử kiến trúc**, không skipped
hoặc thất bại; pytest **0,79 giây**, exit code 0. Có 1 warning AnyIO hiện có.
Ruff đạt, 111 file đúng định dạng và diff không có lỗi whitespace.
Xem [JUnit XML bước 6](../../artifacts/member3-phase2-step6-2026-11-21.xml).

Đây là kiểm chứng adapter độc lập trên SQLite; chưa xác nhận wiring endpoint
hoặc PostgreSQL. Tiếp theo là **bước 7: rà soát và hoàn thiện kiểm thử Catalog**.

## 12. Kết quả hoàn thiện kiểm thử Catalog ngày 21/11/2026

**Bước 7 trong danh sách công việc ngày 21/11 đã hoàn thành.**
Mở rộng [test reader Catalog](../../tests/catalog/test_venue_reader.py) từ 7 lên
**17 ca**; không sửa implementation adapter trong bước này.

- Kiểm DTO đọc đơn cho cả active/inactive/missing; kết quả vẫn dùng được sau
  khi UoW đóng, không trả ORM object hoặc dựng sân giả.
- Kiểm batch trộn ID tồn tại, thiếu và trùng; batch toàn ID thiếu trả `{}`;
  ánh xạ đầy đủ các trường và giữ nguyên danh sách ID đầu vào.
- Giữ các ca batch rỗng không lấy session và batch lớn hơn 500 ID đã có ở bước 6.
- Kiểm cả ba phương thức chỉ query được trong UoW bên gọi, từ chối gọi trước
  khi mở hoặc sau khi đóng UoW.
- Gây lỗi SQL cho status, đọc đơn và truy vấn thứ hai của batch. Lỗi gốc phải
  truyền lên, không đổi thành None/False/dict dở dang; thay đổi trước đó trong
  UoW bên gọi phải rollback. Các ca dùng SQLite tạm và gỡ hook sau khi chạy.

Lệnh chạy với `PYTHONUTF8=1`:

```powershell
.venv/Scripts/python.exe -u -m pytest -q tests/catalog tests/test_architecture.py --junitxml=artifacts/member3-phase2-step7-catalog-2026-11-21.xml
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m ruff format --check app tests scripts
git diff --check
```

Kết quả **18 passed, 0 skipped, 0 failed**, gồm **17 ca adapter + 1 kiểm thử
kiến trúc**, thời lượng pytest **2,73 giây**, exit code 0. Có 1 warning AnyIO
BlockingPortal deprecated hiện có. Ruff đạt, 111 file đúng định dạng và diff
không có lỗi whitespace. Xem
[JUnit XML bước 7](../../artifacts/member3-phase2-step7-catalog-2026-11-21.xml).

Các tiêu chí kiểm thử Catalog của ngày đã đạt. Việc nối adapter vào
Sessions/Matching và nghiệm thu trên PostgreSQL vẫn theo các gói tích hợp,
không được đánh dấu hoàn tất bằng kết quả test adapter độc lập này.
Tiếp theo là **bước 8: kiểm tra hồi quy và ghi nhận kết quả cuối ngày**.

## 13. Chốt kết quả công việc ngày 21/11/2026

**Bước 8 đã hoàn thành. Tám bước công việc ngày 21/11 đã xong.**
Phần việc hoàn thành gồm baseline, kiểm tra phụ thuộc member1, Strategy thuần
đã nối vào service hiện tại, unit test Strategy, hợp đồng Catalog, adapter
SQLite và kiểm thử Catalog. Phase2 tổng thể còn các gói tích hợp ở mục 13.3.

### 13.1. Kiểm tra hồi quy cuối ngày

Môi trường Windows, Python 3.14.2, pytest 9.1.1 và dependency như baseline.
Chạy với `PYTHONUTF8=1`, TestClient ngoài sandbox và SQLite tạm:

```powershell
.venv/Scripts/python.exe -u -m pytest -q -rs --junitxml=artifacts/member3-phase2-step8-2026-11-21.xml
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
git diff --check
git diff --cached --check
```

- **342 passed, 12 skipped, 0 failed, 0 errors**, pytest **39,85 giây**, exit
  code 0. Số passed tăng 52 ca so với baseline: 35 Strategy + 17 Catalog.
- **8/8 corpus Matching** và kiểm thử kiến trúc đạt; file corpus giữ nguyên
  hash so với baseline, không sửa dữ liệu/kết quả mong đợi.
- 12 ca skipped vẫn là workload cần Locust: 1 ca `tests/load/test_runner.py`
  và 11 ca `tests/load/test_workloads.py`. Chưa kết luận các ca này đã đạt.
- Hai warning hiện có vẫn là AnyIO BlockingPortal deprecated và khóa HS512
  ngắn trong ca kiểm từ chối thuật toán JWT khác.
- Ruff toàn repo đạt, **130 file đúng định dạng**; kiểm tra whitespace cả
  working tree và staged diff đạt.

Kiểm tra định dạng toàn repo như CI ban đầu phát hiện thiếu dòng trống giữa
hai lớp trong code mẫu của `member-1-phase-1.md` và `member-1-phase-1.vi.md`.
Đã thêm đúng một dòng trống mỗi file, giữ nguyên nội dung thiết kế và chạy lại
kiểm tra định dạng đạt. Không sửa thêm code ứng dụng sau lần chạy hồi quy.

Bằng chứng cục bộ:
[log pytest](../../artifacts/member3-phase2-step8-2026-11-21.txt),
[JUnit XML](../../artifacts/member3-phase2-step8-2026-11-21.xml),
[manifest môi trường và hash](../../artifacts/member3-phase2-step8-manifest-2026-11-21.json),
[tổng hợp kết quả](../../artifacts/member3-phase2-step8-summary-2026-11-21.json),
[log Ruff](../../artifacts/member3-phase2-step8-ruff-check-2026-11-21.txt) và
[log định dạng](../../artifacts/member3-phase2-step8-ruff-format-2026-11-21.txt).

### 13.2. Thay đổi và đầu ra để member1 tích hợp

- [Matching Strategy](../../app/features/matching/domain/strategy.py) và
  [DTO Matching](../../app/features/matching/contracts.py). Discovery gọi
  Strategy mới và re-export DTO cũ để giữ tương thích các nơi đang dùng.
- [Catalog contracts](../../app/features/catalog/contracts.py) công bố
  `VenueStatusReader`, `VenueReader`, `VenueSummary`.
- [Catalog adapter](../../app/features/catalog/infrastructure/venue_reader.py)
  công bố `SqlAlchemyVenueStatusReader` và `SqlAlchemyVenueReader`. Cách inject
  callback `lambda: uow.session` nằm ở mục 11.1; DTO đọc gồm cả sân inactive,
  status reader phân biệt True/False/None, không tự commit.
- [Test Strategy](../../tests/matching/test_strategy.py),
  [test Catalog](../../tests/catalog/test_venue_reader.py) và phần quét domain
  Matching trong [test kiến trúc](../../tests/test_architecture.py).

Đã chuẩn bị đường dẫn, chữ ký và hướng dẫn tích hợp trong repo để member1 sử
dụng. Code writer vẫn ở đường dẫn cũ, chưa có writer mới để bàn giao trong ngày.
Lần kiểm chứng cuối ngày chạy trên working tree dựa trên HEAD
`90e8fcd8acf60720f361b4c04404ae9e1b9624d5`. Manifest ghi hash của cả file mới
và file sửa để xác định đúng trạng thái đã chạy test. Có thể tra commit lưu
phần Strategy/Catalog bằng `git log -1 -- app/features/matching/domain/strategy.py
app/features/catalog/infrastructure/venue_reader.py`. Hai thay đổi có sẵn ở
`.gitignore` và `.dockerignore` được giữ nguyên.

### 13.3. Phần tiếp tục sau ngày 21/11

1. Nhận code DTO/reader Identity đơn và batch cùng wiring thực từ member1;
   checkout hiện tại chưa có các thành phần đó. Thiết kế đã được xác nhận ở Phase1.
2. Tách Matching command/repository khỏi Discovery và nối reader Identity/Catalog.
3. Chuyển Matching writer, phối hợp member1 đổi wiring tạo kèo/phê duyệt và
   kiểm chứng rollback chung; giữ một implementation duy nhất.
4. Hoàn thiện kiểm tra chu trình/import xuyên module, hồi quy Discovery/privacy,
   cấu hình ingress và ghi commit SQLite refactor trước benchmark.
5. Tiếp tục khóa/tranh chấp, telemetry và nghiệm thu PostgreSQL ở Phase3 theo
   kế hoạch chung; phối hợp session provider, fixture và triển khai với member2.

Các phụ thuộc member1 không cản phần Strategy/Catalog đã hoàn thành, nhưng
phải được bàn giao trước khi nghiệm thu command và wiring tích hợp. Kết quả
cuối ngày chưa phải bằng chứng đã đóng toàn bộ Phase2.


## 14. Bàn giao Phase2 SQLite ngày 22/11/2026

**Trạng thái: Phase2 của member3 hoàn thành trên SQLite.** Commit triển khai:
[`cf989fa`](https://github.com/ncmanh-uet/matchmate-backend/commit/cf989fa5bc508aca78f7ba82181c76a918a0deaf).

Đã hoàn thành tám bước ngày 22/11 cho phạm vi member3 trên SQLite: tách Matching
command, chuyển writer, nối reader thực, hồi quy Discovery/privacy, kiểm tra
kiến trúc, ingress HTTPS local và demo. Khóa/tranh chấp PostgreSQL, telemetry
runtime và rate limit theo danh tính tiếp tục ở Phase3.

### 14.1. Thay đổi và cách tích hợp

- Matching sở hữu [service](../../app/features/matching/service.py),
  [contracts](../../app/features/matching/contracts.py),
  [router](../../app/features/matching/router.py), schemas và repository trong
  infrastructure. Discovery chỉ còn tìm kiếm. Giữ URL, request/response và
  thứ tự xác thực hiện tại; không đổi thuật toán first-valid.
- Identity công bố `PlayerProfile`, reader đơn/batch tại `auth/contracts.py`.
  Bổ sung [adapter Identity](../../app/features/auth/infrastructure/player_profile_reader.py)
  đúng hợp đồng Phase1 để tích hợp bằng code thực vì GitHub chưa có reader mới.
  Đây là phần hỗ trợ tích hợp member1, không phải bộ port riêng của Matching.
- [Composition root](../../app/composition.py) nối Clock, UoW, Strategy, reader
  Identity/Catalog và writer. Matching, tạo kèo và phê duyệt dùng cùng UoW của
  thao tác tương ứng; adapter không commit riêng.
- Writer duy nhất ở
  [matching/infrastructure/matching_request_writer.py](../../app/features/matching/infrastructure/matching_request_writer.py).
  Đã xóa adapter cũ và chuyển wiring/test. Lỗi writer rollback cả Sessions/Matching.
- Sessions dùng Catalog status reader khi tạo kèo và Catalog reader trong
  detail, giữ sân inactive cho lịch sử. Các DTO dùng chung nằm trong domain/API
  chung; Discovery không còn phụ thuộc Matching chỉ để biểu diễn hồ sơ.
- Reader Identity SELECT bốn trường công khai, batch tối đa 500 ID/câu, giữ
  UNSPECIFIED và bỏ ID thiếu. Matching giữ order request khi ghép profile và
  dùng `skill_to_rank()` cho caller/candidate. Không query từng ứng viên.
- [Kiểm tra kiến trúc](../../scripts/check_architecture.py) phân giải import
  tuyệt đối/tương đối, cấm framework/DB trong nghiệp vụ, cấm adapter xuyên module
  và phát hiện chu trình feature. Có mẫu vi phạm và mẫu hợp lệ trong test.
- [Ingress và hướng dẫn chạy](#15-hướng-dẫn-ingress-https-local) gồm TLS local, body/time/rate
  limit, proxy trust, log hạn chế dữ liệu và phương án limiter backend Phase3.

### 14.2. Kết quả kiểm chứng

Mốc đầu ngày `382468e`: **342 passed, 12 skipped, 2 warnings** trong **40,38s**.
GitHub không có commit mới khi fetch. Sau tích hợp và cài `requirements-load.txt`:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -u -m pytest -q -rs --junitxml=artifacts/member3-phase2-final-2026-11-22.xml
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m scripts.check_architecture
git diff --check
```

**382 passed, 0 skipped, 0 failed**, pytest **48,76s** trên Windows/Python 3.14.2.
Hai warning có sẵn là AnyIO portal deprecated và khóa HS512 ngắn trong ca kiểm
từ chối thuật toán. Cả 12 ca workload trước đây skipped nay đã chạy đạt.

Nhóm trọng tâm: **50 Matching**, **17 Catalog**, **3 reader Identity**,
**9 kiến trúc**, **8 corpus Matching qua API**. Corpus chỉ đổi Clock dependency
sang composition root; dữ liệu và assertions giữ nguyên, đã đối chiếu AST.

Test mới kiểm rollback tại create/candidates/profile batch/Strategy/commit,
candidate thiếu/UNSPECIFIED, thứ tự dict khác request, rank enum, lỗi Catalog,
thay Strategy qua wiring, lỗi writer trong tạo kèo, bộ lọc/count/page và việc
Discovery không SELECT email/password hash. Các ca privacy và writer phê duyệt
hiện có đều đạt trong toàn bộ suite.

Docker API Python 3.11 và Nginx được chạy thật. Demo HTTPS, cấu hình `nginx -t`,
413/429, chống header giả danh, request ID, network private và trạng thái
Matching sau commit đều được kiểm chứng; chi tiết tại [ingress local](#15-hướng-dẫn-ingress-https-local).

Bằng chứng cục bộ trong `artifacts/` được Git bỏ qua:
[pytest](../../artifacts/member3-phase2-final-2026-11-22.txt),
[JUnit](../../artifacts/member3-phase2-final-2026-11-22.xml),
[tổng hợp](../../artifacts/member3-phase2-summary-2026-11-22.json),
[demo HTTPS](../../artifacts/member3-phase2-demo-2026-11-22.txt),
[kiểm ingress](../../artifacts/member3-phase2-ingress-2026-11-22.txt).

### 14.3. Bàn giao tiếp theo

Member1 có thể dùng các profile reader/Catalog reader và wiring đã nối thực;
rà soát cùng các thay đổi Identity/Sessions của mình trước khi tích hợp nhánh
khác. Member2 ghép ingress vào topology PostgreSQL và fixture của nhóm. Bộ
Compose ingress hiện dùng volume SQLite riêng, không thay Compose PostgreSQL.

Phase3 tiếp tục `TransactionLocks`, Clock/state đọc lại sau khóa, tranh chấp
Matching với tạo kèo/phê duyệt trên PostgreSQL, DB snapshot, telemetry và limiter
theo principal. Kết quả ở đây không thay bằng chứng PostgreSQL hoặc benchmark.

## 15. Hướng dẫn ingress HTTPS local

Bản demo SQLite dùng `compose.ingress.yaml` độc lập với `compose.yaml` và
Compose PostgreSQL của member2. Chỉ ingress mở cổng trên loopback: HTTP 8080,
HTTPS 8443. API ở mạng backend internal, không publish cổng 8000; dữ liệu nằm
trong volume `matchmate-phase2-ingress_ingress_data` riêng.

### 15.1. Khởi tạo và chạy

Cần Docker Desktop đang chạy, Python với `requirements-dev.txt` và OpenSSL.
Script tìm OpenSSL trên PATH hoặc trong Git for Windows; có thể chỉ định
`--openssl PATH`. Các lệnh dưới đây chạy tại gốc repo bằng PowerShell.

```powershell
python -m scripts.init_env
python -m scripts.prepare_ingress_tls
docker compose -f compose.ingress.yaml config --quiet
docker compose -f compose.ingress.yaml build api
docker compose -f compose.ingress.yaml run --rm --no-deps api python -m scripts.seed
docker compose -f compose.ingress.yaml up -d --wait
docker compose -f compose.ingress.yaml exec -T ingress nginx -t
python -m scripts.demo --base-url https://localhost:8443 --ca artifacts/ingress-tls/fullchain.pem
python -m scripts.check_ingress
```

Tạo TLS ở lần đầu; nếu thư mục đã có certificate/key thì bỏ qua lệnh tạo TLS.
Certificate tự ký có SAN localhost/127.0.0.1, thời hạn 7 ngày. Script kiểm chứng
dùng CA được chỉ định để xác minh TLS; không tắt kiểm tra certificate. Private
key và `.env` nằm ngoài Git và Docker build context.

Xem API tại `https://localhost:8443/docs`. Dừng bằng
`docker compose -f compose.ingress.yaml down`; lệnh này giữ volume dữ liệu demo.
Không dùng volume demo làm nguồn dữ liệu sản xuất hoặc bằng chứng migration PostgreSQL.

### 15.2. Giới hạn và danh tính

`deploy/nginx/nginx.conf` áp body limit **64 KiB**, timeout header/body **10s**,
connect upstream **5s**, send/read upstream **30s** và `proxy_next_upstream off`
để không phát lại POST. `proxy_read_timeout` đo khoảng cách giữa hai lần đọc
upstream, không phải tổng deadline của request.
[Hành vi timeout và retry của Nginx](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).

Ba bucket theo IP dùng cho demo: đăng ký/đăng nhập **10 request/phút, burst 5**;
ghi Sessions/Participations/Matching **10 request/giây, burst 20**; tìm kiếm công
khai **20 request/giây, burst 40**. Request vượt giới hạn trả **429** với
`Retry-After: 6`, error envelope và request ID. Các ngưỡng này là cấu hình demo,
chưa là kết quả tối ưu tải. Nginx dùng leaky bucket; `burst` không phải quota
trong một cửa sổ thời gian cố định.
[Cấu hình rate limit Nginx](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html).

Proxy ghi đè X-Forwarded-For/Proto theo connection thật và xóa X-User-ID,
X-Account-ID từ client. Uvicorn chỉ tin proxy tại `172.29.22.2`; API backend
mặc định `172.29.22.3`, subnet `172.29.22.0/24`. Nếu subnet trùng môi trường,
đặt đồng thời `MATCHMATE_PROXY_IP`, `MATCHMATE_API_IP`, `MATCHMATE_BACKEND_SUBNET`
trước khi tạo network. Backend vẫn kiểm JWT và quyền đối tượng trên từng lệnh.

Rate limit theo **user/tài khoản đã chuẩn hóa** được nối ở Phase3: backend lấy
user ID từ principal đã xác minh, hoặc khóa đăng nhập từ định danh đã được
Identity chuẩn hóa sau kiểm tra payload. Không lấy danh tính từ header client.
Limiter không ghi email/token vào log hoặc nhãn metrics, trả cùng envelope 429.
Khi có nhiều process/instance phải dùng bộ đếm dùng chung; bucket theo IP tại
ingress tiếp tục bảo vệ trước bước xác thực. Bản Phase2 hiện thực bucket IP và
bàn giao điểm nối backend, chưa tuyên bố có limiter theo tài khoản.

### 15.3. Log và kết quả kiểm chứng ngày 22 tháng 11

Access log chỉ có request ID, method, status, duration; không ghi body, query
string, Authorization hoặc email. ID phản hồi backend được giữ ở ingress;
413/429 do ingress sinh có ID riêng khớp body và header.

- Docker build API Python 3.11 thành công; Nginx **1.30.7**, `nginx -t` đạt.
- API không publish cổng; network backend có `Internal=true`.
- Demo HTTPS tạo/thay request Matching, nhận gợi ý, tạo kèo, xin/duyệt, rút/hủy đạt.
- Sau demo: Matching **1 REPLACED, 2 CONFIRMED, 0 ACTIVE**; rút/hủy không mở lại request.
- TLS được xác minh bằng CA local; header giả danh bị từ chối 401; body quá lớn
  trả 413; burst 15 lần login nhận **10 phản hồi 422 và 5 phản hồi 429**.
- Request ID khớp error body/header, không có header X-Request-ID trùng lặp.

Chạy lại trên dữ liệu/bucket đã tồn tại có thể cho số phản hồi 429 khác; điều
kiện kiểm chứng là có 429 cùng Retry-After và request ID đúng, không cố định tỷ lệ.


## 16. Refactor cách viết và thư mục member3 ngày 24/11/2026

### 16.1. Ngữ cảnh và phạm vi được người dùng xác nhận

Người dùng là **member3**, đã hoàn thành **Phase1 và Phase2 của giai đoạn 2**.
Đợt này chỉ refactor phần đã làm để gần mẫu trong `docs/style_code_of_mine`:
Catalog, Matching, Discovery và kiểm tra kiến trúc tương ứng. Không triển khai
Phase3 hoặc thay đổi nghiệp vụ của member1/member2.

Ưu tiên cách viết tuần tự, tên biến rõ, biến trung gian `query`/`result`,
khởi tạo đối tượng bằng tham số có tên và router chia theo tài nguyên.
Giữ service sở hữu transaction, reader/writer không commit riêng, Strategy thuần,
response/error contract, first-valid và quyền riêng tư hiện có. Giữ nguyên code
Identity, Sessions, DB/UoW, model, migration, cấu hình triển khai và các test
Auth/Sessions/foundation/integration/load.

### 16.2. Đường dẫn code chính sau refactor

```text
app/features/
├── catalog/
│   ├── contracts.py
│   └── venue_reader.py
├── matching/
│   ├── routers/requests.py
│   ├── schemas.py
│   ├── contracts.py
│   ├── service.py
│   ├── strategy.py
│   ├── repository.py
│   └── matching_request_writer.py
└── discovery/
    ├── routers/venues.py
    ├── routers/sessions.py
    ├── schemas.py
    ├── contracts.py
    ├── service.py
    └── repository.py
```

Lược `__init__.py` và các file chuyển tiếp khỏi cây để thể hiện vị trí code chính.
Không tạo thêm model, engine, transaction hoặc router Catalog không cần thiết.

Các file cũ trong `catalog/infrastructure/`, `matching/infrastructure/`,
`matching/domain/strategy.py`, `matching/router.py` và `discovery/router.py`
được giữ làm đường dẫn tương thích. Chúng chỉ import lại đúng class/hàm mới;
không có SQL hoặc thuật toán thứ hai. Nhờ đó không phải sửa import trong
`app/main.py`, code hoặc test của member1/member2. Code/test của member3 sử dụng
đường dẫn mới. Hai provider Matching/Discovery trong `app/composition.py` dùng
tham số có tên; các provider Sessions/Participation/detail giữ nguyên logic.

### 16.3. Những thay đổi về cách viết

- Matching ghép request với hồ sơ bằng vòng lặp và `continue`, bỏ biểu thức `:=`.
  Thứ tự request và cách loại hồ sơ thiếu/UNSPECIFIED giữ nguyên.
- Tách biến phí người gửi; truyền tên trường khi tạo `PlayerSummary` và nối
  dependency; giữ thứ tự kiểm tra lỗi và một lần commit cuối command.
- Strategy dùng tên `required_candidates`, `ordered_candidates`,
  `candidate_group`; vẫn sắp `(created_at, id)` và chọn tổ hợp hợp lệ đầu tiên.
- Catalog tách `session`, `query`, `result`; batch vẫn tối đa 500 ID/câu, đầu vào
  rỗng không lấy session, chỉ đọc projection đã chốt.
- Discovery đổi tên viết tắt trong mapper/truy vấn, tách bước tạo hồ sơ host và
  record; giữ điều kiện lọc/count/order trước phân trang.
- Router tách tìm sân/tìm kèo/tạo Matching theo tài nguyên; bổ sung kiểu đầu vào
  cho hàm ánh xạ response, dùng `payload` cho body tạo Matching.
- Bộ kiểm tra kiến trúc tiếp tục kiểm Strategy sau khi bỏ thư mục `domain/`;
  cấm service import trực tiếp reader/writer và package routers, có bốn ca
  kiểm tra vi phạm mới.

### 16.4. Kiểm chứng trước và sau

Bằng chứng cục bộ lưu trong `artifacts/member3-style-refactor/` (Git bỏ qua).
Trước sửa: **411 passed**, hai warning có sẵn, pytest **50,06 giây**.
Lần chạy toàn bộ ban đầu không collect được test PostgreSQL vì môi trường thiếu
`alembic`; baseline SQLite dùng cùng lệnh bỏ riêng module đó. Không sửa dependency
hoặc test PostgreSQL của member2 để xử lý vấn đề môi trường.

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m pytest -q -rs --ignore=tests/integration/test_member2_postgres.py --junitxml=artifacts/member3-style-refactor/after-sqlite.xml
.venv/Scripts/python.exe -m ruff check app tests scripts
.venv/Scripts/python.exe -m ruff format --check app tests scripts
.venv/Scripts/python.exe -m scripts.check_architecture
git diff --check
```

Sau refactor: **415 passed, 0 skipped, 0 failed**, hai warning có sẵn, pytest
**47,12 giây**. Tăng đúng bốn ca kiểm tra kiến trúc; 411 ca cũ vẫn đạt, gồm các
test Auth/Sessions, tám ca corpus Matching, rollback, quyền riêng tư và workload.
Ruff check đạt; Ruff format kiểm tra 143 file đạt; architecture checker và
`git diff --check` đạt.

Đối chiếu tính tương thích:

- OpenAPI sinh từ ứng dụng trước/sau giống nhau hoàn toàn, gồm URL, schema,
  operation ID, mã phản hồi và khai báo bảo mật.
- SHA-256 của 95 file trong phạm vi bảo vệ không đổi, gồm code/test của
  Auth/Sessions/DB/domain/API, migration, CI, entry point và các cấu hình chạy.
- AST của bốn hàm `provide_participation_service`, `provide_session_service`,
  `provide_session_detail_service`, `_session_detail_reader` không đổi. Trong
  composition root chỉ đổi đường dẫn import adapter member3 và cách truyền
  tham số của hai provider Matching/Discovery.
- Các đường dẫn import cũ trả đúng cùng đối tượng class/hàm với đường dẫn mới;
  patch writer từ test Sessions vẫn tác động đúng implementation đang chạy.
- File corpus Phase1 giữ nguyên trong nhóm 95 file đã đối chiếu hash.
- Các thay đổi có sẵn trong `.gitignore`, `.dockerignore` và mẫu
  `docs/style_code_of_mine/` không được sửa trong đợt này.

Bằng chứng: `baseline-sqlite.xml`, `after-sqlite.xml`, `protected-before.json`,
`openapi-before.json`, `openapi-after.json`, `compatibility.json` trong thư mục
artifacts nêu trên. Kết quả SQLite không thay bằng chứng PostgreSQL hoặc demo
TLS/benchmark mới; cấu hình ingress không thay đổi trong đợt refactor này.
