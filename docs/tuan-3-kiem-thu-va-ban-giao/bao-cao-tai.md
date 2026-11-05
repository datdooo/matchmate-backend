# Tuần 3: Báo cáo tải trên Kaggle CPU

Lần đo chạy ngày **29/10/2026** trên mã nguồn `859df1345a6d5034d2202823232f219f34f87ab4`. Mọi số liệu dưới đây thuộc lần chạy đó, không phải kết quả của mã hiện tại.

## Môi trường

- Kaggle CPU, 4 vCPU, RAM giới hạn 30 GiB, Python 3.13.15, SQLite 3.45.1.
- Một worker Uvicorn. Locust chạy cùng máy và gọi qua loopback. Vì vậy số liệu không phản ánh độ trễ qua Internet và không phải cam kết cho production.
- Internet tắt, không dùng accelerator. Mã nguồn (git bundle) và wheel được gắn bằng private input, kiểm SHA-256 trước khi cài. Phiên bản dependency thực tế nằm trong metadata từng lượt.

## Kết quả đo đủ 60 giây

| Kịch bản | Người dùng | Request | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Lỗi request |
|---|---:|---:|---:|---:|---:|---:|---:|
| read | 10 | 393 | 6,59 | 11 | 14 | 34 | 0 |
| read | 50 | 1963 | 32,91 | 13 | 32 | 54 | 0 |
| read | 100 | 3864 | 65,25 | 24 | 100 | 180 | 0 |
| lifecycle | 10 | 1719 | 28,79 | 31 | 120 | 270 | 0 |

`read` chỉ gọi các API đọc. Mỗi vòng `lifecycle` tạo kèo, xin tham gia, duyệt, xem chi tiết, rồi rút lượt hoặc hủy kèo (chọn ngẫu nhiên). Tài khoản được tạo sẵn bằng script seed và đăng nhập trước khi đo.

Bốn lượt này có `exit_code=0` và không có lỗi 4xx, 5xx, 409, `DATABASE_BUSY` hay lỗi kiểm contract trong cửa sổ đo. Lượt `read` đạt p95 dưới 1 giây. Các request ghi ở mức 10 người đạt p95 dưới 2 giây. Số liệu từng API nằm trong file stats CSV.

## Lượt không đo được

| Kịch bản | Người dùng | Kết quả |
|---|---:|---|
| lifecycle | 50 | Dừng trước khi đo |
| lifecycle | 100 | Dừng trước khi đo |

- **50 người:** đăng nhập đủ 50 cặp, nhưng giai đoạn warm-up có 27 lỗi HTTP 503 (22 ở tạo kèo, 4 ở xin tham gia, 1 ở duyệt). Runner dừng đúng quy tắc, `measurement_complete=false`, exit 1. Số liệu warm-up không dùng làm kết quả. Đây là giới hạn ghi đồng thời của cấu hình hiện tại: SQLite một writer, một worker.
- **100 người:** mới đăng nhập được 42 cặp thì một request `/auth/login` quá 20 giây và hết thời gian chờ (`HTTP_0` trong log). Runner dừng trước warm-up, exit 1. Log còn có lỗi ghi CSV của Locust lúc thoát (`I/O operation on closed file`). File failures CSV trống không có nghĩa là không có lỗi, phải đọc cả log và metadata.

Sau cả sáu lượt, bốn chỉ số kiểm tra DB đều bằng 0: `over_capacity`, `accepted_overlap`, `active_in_cancelled`, `open_without_host`. Với hai lượt không đo được, kết quả này chỉ cho biết DB sau khi dừng còn đúng. Nó không thay cho một lượt đo đầy đủ.

Mức ghi 50 và 100 người chưa có số đo. Khi làm Pha 2, hai lỗi trên là chỗ cần xem lại đầu tiên: đăng nhập và giới hạn ghi của SQLite.

## Dữ liệu gốc

Báo cáo đầy đủ, notebook đã chạy, CSV, log và metadata nằm ở commit `5b9be9f`, đã gỡ khỏi nhánh chính để repo gọn:

- [Báo cáo tại mốc `5b9be9f`](https://github.com/datdooo/matchmate-backend/blob/5b9be9fb939de41965eb1f6b290be2b60ea4d28c/docs/LOAD_TEST_RESULTS.md)
- [Dữ liệu đo gốc](https://github.com/datdooo/matchmate-backend/tree/5b9be9fb939de41965eb1f6b290be2b60ea4d28c/docs/load/kaggle-2026-10-29)

## Chạy lại

Cần môi trường có Internet:

```bash
python -m pip install -r requirements-load.txt
python -m pytest -q
bash scripts/run_kaggle_load_test.sh --profile full
```

Số liệu từng lượt và bảng tóm tắt `summary.md` được ghi vào thư mục `artifacts/` (Git bỏ qua). Báo cáo này không bị ghi đè. Muốn đưa số đo mới vào repo, hãy chép kết quả sang đây và ghi rõ commit đã đo.
