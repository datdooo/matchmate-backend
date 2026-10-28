# Kết quả tải Kaggle CPU

Chưa chạy tải Kaggle; chưa có số đo RPS hoặc latency để nghiệm thu.

Runner hiện dừng trước khi seed/phát tải nếu app chưa có đủ 11 API nghiệp vụ. Các route còn thiếu: `GET /venues`, `GET /sessions`, `DELETE /sessions/{session_id}`, `POST /matching/requests`.

Tạo/xem kèo đã trả `SessionDetail`. Workload kiểm các field response cần dùng và dừng trước đo nếu warm-up có lỗi; đủ tên route chưa thay thế kiểm thử hành vi.

Các điểm cần nối trước lượt đo:

| Phần | Việc còn lại |
|---|---|
| Hải | Nối route tìm sân, tìm kèo, matching; sửa `provide_current_user_id` đang gọi đệ quy chính nó. Kiểm lại mapper matching đang có `record \| None` lúc runtime và mapper session đang trả ID thay vì đủ host/venue. |
| Chiến | Nối hủy kèo và hủy các lượt hoạt động trong cùng transaction; kiểm Docker/wiring. |
| Đạt | Sau tích hợp: chạy lại test toàn luồng, chạy hai profile trên Kaggle CPU và thay trạng thái này bằng số đo cùng artifacts. |

Sau khi nhóm tích hợp đủ và test hành vi đạt, chạy trên notebook Kaggle CPU từ thư mục repo:

```bash
python -m pip install -r requirements-load.txt
python -m pytest tests/load/test_workloads.py -q
bash scripts/run_kaggle_load_test.sh --profile full
```

Runner dùng một Uvicorn worker và Locust headless qua loopback. Mỗi profile read/lifecycle chạy riêng ở 10/50/100 virtual users, spawn 2/5/10 users mỗi giây. Đợi login tối đa 120 giây, warm-up 15 giây, reset stats rồi đo 60 giây. Read dùng quận theo tỷ lệ 70/20/10; lifecycle có cặp host/player riêng, rút hoặc hủy 50/50, chờ 1–2 giây giữa các vòng.

Mỗi lượt tạo DB tạm mới, tái sử dụng seed của Hải và bổ sung đủ actor. DB local/demo được giữ nguyên. Artifacts gồm HTML, CSV, metadata và log; metadata giữ commit, môi trường, dataset hash, base_time, random seed, số actor, mã lỗi và invariant sau chạy. File actors có thông tin đăng nhập giả lập chỉ nằm trong thư mục tạm.

Workload lifecycle kiểm trạng thái, đúng session/id, quote và giới tính snapshot sau xin/duyệt/rút; kiểm số ACCEPTED sau tạo/xem/hủy. Invariant đọc lại DB gồm quá chỗ, lịch ACCEPTED chồng nhau, lượt hoạt động trong kèo đã hủy và kèo OPEN thiếu host ACCEPTED. Test workload dùng response giả để kiểm cả hai nhánh rút/hủy và phát hiện response sai; đây không phải kết quả tải.

Chỉ dùng lượt có `measurement_complete=true` làm số đo. Mọi 4xx/503 đều được ghi nhận là lỗi trong hai profile thường; contention đã được kiểm riêng bằng test đồng thời. Nghiệm thu phải đối chiếu invariant, 500 ngoài dự kiến ở 10 users và từng failure CSV; không suy chất lượng từ RPS hoặc số users. p95 tham khảo ở 10 users: GET dưới 1 giây, ghi dưới 2 giây; 50/100 users dùng để ghi nhận giới hạn.
