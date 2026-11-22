# Chạy ingress HTTPS local cho Phase2

Bản demo SQLite dùng `compose.ingress.yaml` độc lập với `compose.yaml` và
Compose PostgreSQL của member2. Chỉ ingress mở cổng trên loopback: HTTP 8080,
HTTPS 8443. API ở mạng backend internal, không publish cổng 8000; dữ liệu nằm
trong volume `matchmate-phase2-ingress_ingress_data` riêng.

## Khởi tạo và chạy

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

## Giới hạn và danh tính

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

## Log và kết quả kiểm chứng ngày 22 tháng 11

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
