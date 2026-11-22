# Bàn giao Phase2 member3 ngày 22 tháng 11 năm 2026

Đã hoàn thành tám bước ngày 22/11 cho phạm vi member3 trên SQLite: tách Matching
command, chuyển writer, nối reader thực, hồi quy Discovery/privacy, kiểm tra
kiến trúc, ingress HTTPS local và demo. Khóa/tranh chấp PostgreSQL, telemetry
runtime và rate limit theo danh tính tiếp tục ở Phase3.

## Thay đổi và cách tích hợp

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
- [Ingress và hướng dẫn chạy](ingress-local.md) gồm TLS local, body/time/rate
  limit, proxy trust, log hạn chế dữ liệu và phương án limiter backend Phase3.

## Kết quả kiểm chứng

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
Matching sau commit đều được kiểm chứng; chi tiết tại [ingress local](ingress-local.md).

Bằng chứng cục bộ trong `artifacts/` được Git bỏ qua:
[pytest](../../artifacts/member3-phase2-final-2026-11-22.txt),
[JUnit](../../artifacts/member3-phase2-final-2026-11-22.xml),
[tổng hợp](../../artifacts/member3-phase2-summary-2026-11-22.json),
[demo HTTPS](../../artifacts/member3-phase2-demo-2026-11-22.txt),
[kiểm ingress](../../artifacts/member3-phase2-ingress-2026-11-22.txt).

## Bàn giao tiếp theo

Member1 có thể dùng các profile reader/Catalog reader và wiring đã nối thực;
rà soát cùng các thay đổi Identity/Sessions của mình trước khi tích hợp nhánh
khác. Member2 ghép ingress vào topology PostgreSQL và fixture của nhóm. Bộ
Compose ingress hiện dùng volume SQLite riêng, không thay Compose PostgreSQL.

Phase3 tiếp tục `TransactionLocks`, Clock/state đọc lại sau khóa, tranh chấp
Matching với tạo kèo/phê duyệt trên PostgreSQL, DB snapshot, telemetry và limiter
theo principal. Kết quả ở đây không thay bằng chứng PostgreSQL hoặc benchmark.
