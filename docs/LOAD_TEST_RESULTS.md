# Kết quả tải Kaggle CPU

Chưa chạy tải Kaggle; chưa có số đo RPS hoặc latency để nghiệm thu.

Runner hiện dừng trước khi seed/phát tải nếu app chưa có đủ 11 API nghiệp vụ. Các route còn thiếu ở mốc tích hợp participation: `GET /venues`, `GET /sessions`, `GET /sessions/{session_id}`, `DELETE /sessions/{session_id}`, `POST /matching/requests`.

`POST /sessions` còn cần trả đủ `SessionDetail`. Workload kiểm các field response cần dùng và dừng trước đo nếu warm-up có lỗi; đủ tên route chưa thay thế kiểm thử hành vi.

Sau khi nhóm tích hợp đủ và test hành vi đạt, chạy trên notebook Kaggle CPU từ thư mục repo:

```bash
python -m pip install -r requirements-load.txt
bash scripts/run_kaggle_load_test.sh --profile full
```

Runner dùng một Uvicorn worker và Locust headless qua loopback. Mỗi profile read/lifecycle chạy riêng ở 10/50/100 virtual users, spawn 2/5/10 users mỗi giây. Đợi login tối đa 120 giây, warm-up 15 giây, reset stats rồi đo 60 giây. Read dùng quận theo tỷ lệ 70/20/10; lifecycle có cặp host/player riêng, rút hoặc hủy 50/50, chờ 1–2 giây giữa các vòng.

Mỗi lượt tạo DB tạm mới, tái sử dụng seed của Hải và bổ sung đủ actor. DB local/demo được giữ nguyên. Artifacts gồm HTML, CSV, metadata và log; metadata giữ commit, môi trường, dataset hash, base_time, random seed, số actor, mã lỗi và invariant sau chạy. File actors có thông tin đăng nhập giả lập chỉ nằm trong thư mục tạm.

Chỉ dùng lượt có `measurement_complete=true` làm số đo. Mọi 4xx/503 đều được ghi nhận là lỗi trong hai profile thường; contention đã được kiểm riêng bằng test đồng thời. Nghiệm thu phải đối chiếu invariant, 500 ngoài dự kiến ở 10 users và từng failure CSV; không suy chất lượng từ RPS hoặc số users. p95 tham khảo ở 10 users: GET dưới 1 giây, ghi dưới 2 giây; 50/100 users dùng để ghi nhận giới hạn.
