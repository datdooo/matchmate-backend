# Kết quả tải Kaggle CPU

**Chưa có lượt đo Kaggle hợp lệ.** App đã có đủ 11 API nghiệp vụ; preflight không còn báo thiếu route. Sau sửa tích hợp, 235 test local đã qua, gồm matching đủ 2/4 người, tạo/xin/duyệt/xem/rút/hủy qua SQLite thật và sáu ca concurrency.

## Lượt thử local 10 users

Đã gọi `python -m scripts.run_kaggle_load_test --profile full --users 10`. Cả hai lượt dừng trước warm-up/đo vì monitor CPU của Locust gọi `psutil.Process()` và gặp `psutil.NoSuchProcess` trong môi trường kiểm tra. Đây là lỗi đọc process của môi trường, không phải kết quả HTTP của API.

| Profile | Môi trường | Virtual users | Đã login đủ | Đủ 60 giây đo | Exit code |
|---|---|---:|---|---|---:|
| read | local | 10 | 8/10 | Không | 2 |
| lifecycle | local | 10 | 8/10 cặp host/player | Không | 2 |

`measurement_complete=false` ở cả hai metadata. **Không có RPS hoặc p50/p95/p99 hợp lệ**, và không dùng số lỗi mặc định 0 của một cửa sổ chưa đo để kết luận thành công. Invariant đọc lại DB sau dừng đều bằng 0 vi phạm; điều này không thay thế kiểm tải hoàn chỉnh.

Artifacts local gồm `artifacts/locust-{profile}-10u.log`, HTML, CSV và metadata. Thư mục artifacts được Git bỏ qua; thông tin đăng nhập giả lập chỉ nằm trong DB/manifest tạm. Không sửa Locust hoặc bỏ monitor để biến lượt dừng thành lượt đạt.

## Chạy nghiệm thu Kaggle CPU

Từ thư mục repo trong notebook Kaggle CPU:

```bash
python -m pip install -r requirements-load.txt
python -m pytest -q
bash scripts/run_kaggle_load_test.sh --profile full
```

Hai profile read/lifecycle chạy riêng ở 10/50/100 virtual users, spawn 2/5/10 users mỗi giây. Một Uvicorn worker và Locust dùng chung máy, gọi loopback. Đợi mọi user login tối đa 120 giây, warm-up 15 giây, reset stats và đo 60 giây. Lifecycle có hai actor riêng mỗi virtual user, rút hoặc hủy 50/50, chờ 1–2 giây giữa các vòng.

Mỗi lượt dùng DB tạm mới, 10 sân/30 kèo seed và đủ actor; giữ nguyên DB demo. Metadata ghi môi trường, dependency/SQLite, CPU/RAM/cgroup, commit, dataset hash, base_time, random seed, mã lỗi và invariant. Workload kiểm trạng thái, ID/session, snapshot và số ACCEPTED; invariant kiểm quá chỗ, ACCEPTED chồng lịch, lượt hoạt động trong kèo đã hủy và kèo OPEN thiếu host ACCEPTED.

Chỉ công nhận số đo khi `environment=kaggle` và `measurement_complete=true`; đối chiếu HTML, stats/failures CSV, log và metadata từng lượt. Mọi 4xx/503 trong profile thường đều là lỗi. Nghiệm thu yêu cầu invariant đúng ở mọi mức, không 500 ngoài dự kiến ở 10 users; p95 tham khảo GET < 1 giây, ghi < 2 giây. Mức 50/100 dùng để ghi nhận giới hạn, báo đủ DATABASE_BUSY/503 và không che lỗi bằng retry.
