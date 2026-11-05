# Kết quả tải Kaggle CPU

Chạy ngày **29/10/2026** trên mã nguồn `859df1345a6d5034d2202823232f219f34f87ab4`. Các số liệu dưới đây thuộc lần chạy này.

## Môi trường và cách đo

Kaggle CPU, 4 vCPU (cgroup `400000 100000`), RAM giới hạn 30 GiB, Python 3.13.15, SQLite 3.45.1. Một Uvicorn worker và Locust dùng chung máy, gọi loopback; không phải số đo qua Internet hoặc cam kết tải production. Internet OFF, accelerator None; source git bundle và wheel được gắn bằng private input, kiểm SHA-256 trước cài. Phiên bản dependency thực tế có trong metadata từng lượt.


## Số đo hợp lệ

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

- **Lifecycle 50 users:** login đủ 50 cặp, nhưng warm-up có **27 HTTP 503**: tạo kèo 22, xin tham gia 4, duyệt 1. Runner dừng đúng quy tắc trước đo (`measurement_complete=false`, exit 1). CSV/log warm-up có latency nhưng không dùng làm kết quả 60 giây. Đây là giới hạn ghi đồng thời của cấu hình hiện tại.
- **Lifecycle 100 users:** mới login đủ 42 cặp thì một request `/auth/login` timeout sau khoảng 20 giây (`HTTP_0` trong log). Runner dừng trước warm-up/đo, exit 1. Log còn có lỗi Locust CSV writer lúc thoát (`I/O operation on closed file`); failures CSV trống không có nghĩa là không lỗi, phải đọc log và metadata.
- Cả sáu DB sau dừng đều có `over_capacity=0`, `accepted_overlap=0`, `active_in_cancelled=0`, `open_without_host=0`. Với lượt chưa đo, kết quả này chỉ mô tả DB đã kiểm tra, không thay thế kiểm tải đầy đủ.

Hai mức ghi 50/100 người chưa có kết quả đo đầy đủ. Phase 2 có thể đối chiếu các lỗi trên khi đánh giá phần đăng nhập và giới hạn ghi của SQLite. Các số đo trong báo cáo lấy từ Uvicorn chạy trực tiếp trên Kaggle.

## Chạy lại

Để chạy lại từ repo trong môi trường có Internet:

```bash
python -m pip install -r requirements-load.txt
python -m pytest -q
bash scripts/run_kaggle_load_test.sh --profile full
```
