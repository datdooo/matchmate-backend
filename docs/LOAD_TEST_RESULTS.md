# Kết quả tải Kaggle CPU

Chạy ngày **29/10/2026 (giờ Việt Nam)** trên source `859df1345a6d5034d2202823232f219f34f87ab4`. Bản main `ca406f8` chỉ cập nhật README sau source này; mã chạy không đổi.

**Đạt baseline 10 users ở cả read và lifecycle.** Read 50/100 users cũng đo đủ, không lỗi. Lifecycle 50/100 users dừng trước cửa sổ đo do quá tải; chưa nghiệm thu hai mức ghi này. Không có lượt nào vi phạm bốn invariant khi đọc lại DB.

## Môi trường và cách đo

Kaggle CPU, 4 vCPU (cgroup `400000 100000`), RAM giới hạn 30 GiB, Python 3.13.15, SQLite 3.45.1. Một Uvicorn worker và Locust dùng chung máy, gọi loopback; không phải số đo qua Internet hoặc cam kết tải production. Internet OFF, accelerator None; source git bundle và wheel được gắn bằng private input, kiểm SHA-256 trước cài. Phiên bản dependency thực tế có trong metadata từng lượt.

Lint/format đạt và **235 test chức năng pass ngay trên Kaggle** trước khi chạy `python -m scripts.run_kaggle_load_test --profile full`. Mỗi lượt dùng DB tạm mới, 10 sân/30 kèo seed; random seed 42, spawn 2/5/10 users mỗi giây. Đợi login đủ (tối đa 120 giây), warm-up 15 giây rồi reset stats và đo 60 giây. Lifecycle dùng cặp host/player riêng mỗi virtual user, rút hoặc hủy 50/50 và chờ 1–2 giây giữa vòng.

## Số đo hợp lệ

Latency tính bằng ms; RPS làm tròn hai chữ số từ metadata `aggregate`/stats CSV. CSV có thể ghi trước phần log tổng kết cuối cùng vài request; bảng dùng cùng snapshot trong metadata, không trộn hai thời điểm.

| Profile | Users | Đủ 60s | Requests | RPS | p50 | p95 | p99 | Lỗi request |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| read | 10 | Có | 393 | 6.59 | 11 | 14 | 34 | 0 |
| read | 50 | Có | 1963 | 32.91 | 13 | 32 | 54 | 0 |
| read | 100 | Có | 3864 | 65.25 | 24 | 100 | 180 | 0 |
| lifecycle | 10 | Có | 1719 | 28.79 | 31 | 120 | 270 | 0 |
| lifecycle | 50 | Không | n/a | n/a | n/a | n/a | n/a | n/a |
| lifecycle | 100 | Không | n/a | n/a | n/a | n/a | n/a | n/a |

Bốn lượt đo đủ có `exit_code=0`, không 4xx/5xx/409/DATABASE_BUSY hoặc lỗi kiểm contract trong cửa sổ đo. Read đạt p95 tham khảo < 1 giây; các request ghi ở mức 10 users đạt p95 < 2 giây (chi tiết từng API trong stats CSV/HTML).

## Giới hạn ở mức ghi cao

- **Lifecycle 50 users:** login đủ 50 cặp, nhưng warm-up có **27 HTTP 503**: tạo kèo 22, xin tham gia 4, duyệt 1. Runner dừng đúng quy tắc trước đo (`measurement_complete=false`, exit 1). CSV/log warm-up có latency nhưng không dùng làm kết quả 60 giây. Đây là giới hạn ghi đồng thời của cấu hình hiện tại; không bỏ lỗi hoặc thêm retry để báo đạt.
- **Lifecycle 100 users:** mới login đủ 42 cặp thì một request `/auth/login` timeout sau khoảng 20 giây (`HTTP_0` trong log). Runner dừng trước warm-up/đo, exit 1. Log còn có lỗi Locust CSV writer lúc thoát (`I/O operation on closed file`); failures CSV trống không có nghĩa là không lỗi, phải đọc log và metadata.
- Cả sáu DB sau dừng đều có `over_capacity=0`, `accepted_overlap=0`, `active_in_cancelled=0`, `open_without_host=0`. Với lượt chưa đo, kết quả này chỉ mô tả DB đã kiểm tra, không thay thế kiểm tải đầy đủ.

Không sửa ứng dụng hoặc mở rộng kiến trúc để ép đạt 50/100 users. Phase 2 có thể dùng baseline này để đánh giá phần đăng nhập và giới hạn SQLite một writer. Docker toàn luồng vẫn cần kiểm chứng riêng.

## Bằng chứng và chạy lại

[Notebook đã chạy, giữ cả output lỗi](load/kaggle-2026-10-29/matchmate-phase-1-load-test.ipynb), [metadata tổng hợp](load/kaggle-2026-10-29/run-summary.json), [môi trường](load/kaggle-2026-10-29/kaggle-environment.json) và CSV/log từng lượt nằm trong [thư mục kết quả](load/kaggle-2026-10-29). [Gói đầy đủ](load/kaggle-2026-10-29/matchmate-kaggle-results.zip) giữ nguyên HTML, CSV, log, metadata và báo cáo runner (bao gồm lượt không đạt).

SHA-256 gói đầy đủ: `7c1e26d90b1fd23ea913ad24a06f1ee3119ffca1af22ed6a033fb1be594e1ac4`.

Notebook: https://www.kaggle.com/code/datdooo/matchmate-phase-1-load-test/edit (private, tài khoản sở hữu mới xem được). Để chạy online từ repo:

```bash
python -m pip install -r requirements-load.txt
python -m pytest -q
bash scripts/run_kaggle_load_test.sh --profile full
```

Lượt local trước đây dừng do `psutil.NoSuchProcess` trước đo, không dùng làm số đo Kaggle. Gói hiện tại là kết quả từ Kaggle thật, giữ nguyên monitor và quy tắc dừng.
