"""Demo API thật với DB tạm; chạy `python -m scripts.demo --step` để thuyết trình."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


class DemoError(Exception):
    pass


def run_demo(base_url: str, step: bool) -> None:
    # Chỉ gọi server loopback do script mở, không gửi token qua proxy của máy.
    client = build_opener(ProxyHandler({}))

    def api(method, path, data=None, token=None, expected=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            base_url + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers,
            method=method,
        )
        try:
            response = client.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            body = json.load(response)
            if response.status != expected:
                code = body.get("error", {}).get("code", "UNEXPECTED_RESPONSE")
                raise DemoError(f"{method} {path}: HTTP {response.status}, {code}")
        print(f"  {method} {path} → HTTP {expected}", flush=True)
        return body

    def show(title):
        if step:
            input("\nNhấn Enter để chạy bước tiếp theo...")
        print(f"\n{title}", flush=True)

    def check(condition, message):
        if not condition:
            raise DemoError(message)

    show("1. Đăng ký và đăng nhập hai tài khoản demo")
    tokens = []
    for name, gender in (("Host demo", "MALE"), ("Người chơi demo", "FEMALE")):
        account = {
            "email": f"demo-{secrets.token_hex(5)}@example.com",
            "password": secrets.token_urlsafe(16),
        }
        api(
            "POST",
            "/auth/register",
            {**account, "display_name": name, "skill_level": "TB", "gender": gender},
            expected=201,
        )
        tokens.append(api("POST", "/auth/login", account)["access_token"])
    host, player = tokens
    print("  Hai tài khoản đã có JWT; không cần copy token.")

    show("2. Tìm sân và chuẩn bị kèo đơn")
    venue = api("GET", "/venues")["items"][0]
    start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    game = {
        "venue_id": venue["id"],
        "title": "Kèo demo Phase 1",
        "play_type": "SINGLES",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=2)).isoformat(),
        "fee_male_vnd": 60000,
        "fee_female_vnd": 40000,
        "min_level": "TB_MINUS",
        "max_level": "TB_PLUS",
        "gender_policy": "ANY",
    }
    print(f"  Sân: {venue['name']}; 2 người tính cả host, thời lượng 120 phút.")

    show("3. Thử nhập sai: thời lượng chỉ 30 phút")
    bad = api(
        "POST",
        "/sessions",
        {**game, "ends_at": (start + timedelta(minutes=30)).isoformat()},
        host,
        expected=422,
    )
    check(bad["error"]["code"] == "INVALID_TIME_WINDOW", "Sai mã lỗi thời gian")
    check(api("GET", "/sessions?host_me=true", token=host)["total"] == 0, "Kèo lỗi bị lưu")
    print("  INVALID_TIME_WINDOW: từ chối dữ liệu sai, không tạo kèo dở dang.")

    show("4. Host tạo kèo hợp lệ")
    created = api("POST", "/sessions", game, host, expected=201)
    session_id = created["id"]
    check(created["status"] == "OPEN" and created["accepted_count"] == 1, "Sai trạng thái host")
    print(f"  Kèo #{session_id}: OPEN; host ACCEPTED, còn 1 chỗ.")

    show("5. Người chơi xin tham gia")
    joined = api("POST", "/participations", {"session_id": session_id}, player, expected=201)
    part_id = joined["id"]
    check(joined["status"] == "PENDING", "Xin tham gia không tạo PENDING")
    check(joined["quoted_fee_vnd"] == 40000, "Phí snapshot không đúng")
    print(f"  Lượt #{part_id}: PENDING, chưa giữ chỗ; phí được lưu là 40.000 VND.")

    show("6. Host duyệt và kiểm tra kèo đã đủ người")
    approved = api("POST", f"/participations/{part_id}/decision", {"decision": "APPROVE"}, host)
    check(approved["status"] == "ACCEPTED", "Duyệt chưa chuyển ACCEPTED")
    detail = api("GET", f"/sessions/{session_id}", token=host)
    check(detail["accepted_count"] == 2 and detail["remaining_capacity"] == 0, "Sai sức chứa")
    print("  ACCEPTED; kèo đủ 2/2 người, không còn chỗ.")

    show("7. Thử xin khi kèo đã đầy")
    full = api("POST", "/participations", {"session_id": session_id}, player, expected=409)
    check(full["error"]["code"] == "SESSION_FULL", "Sai mã lỗi khi kèo đầy")
    print("  SESSION_FULL: từ chối, không tăng số người.")

    show("8. Người chơi rút lượt")
    withdrawn = api("DELETE", f"/participations/{part_id}", token=player)
    check(withdrawn["status"] == "CANCELLED", "Rút chưa chuyển CANCELLED")
    detail = api("GET", f"/sessions/{session_id}", token=host)
    check(detail["accepted_count"] == 1 and detail["remaining_capacity"] == 1, "Không trả lại chỗ")
    print("  Lượt CANCELLED; kèo còn host, mở lại 1 chỗ.")

    show("9. Host hủy kèo")
    cancelled = api("DELETE", f"/sessions/{session_id}", token=host)
    check(
        cancelled["status"] == "CANCELLED" and cancelled["accepted_count"] == 0, "Hủy chưa đầy đủ"
    )
    print("  Kèo CANCELLED; không còn lượt ACCEPTED.")
    print("\nHOÀN TẤT: các bước đều gọi HTTP thật và kiểm tra dữ liệu trả về.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", action="store_true", help="Nhấn Enter trước mỗi bước demo")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    try:
        # DB và secret riêng: không cần .env và không chạm app.db của người dùng.
        with tempfile.TemporaryDirectory(prefix="matchmate-demo-") as directory:
            env = {
                **os.environ,
                "DATABASE_URL": f"sqlite:///{directory}/demo.db",
                "JWT_SECRET_KEY": secrets.token_urlsafe(48),
                "JWT_ALGORITHM": "HS256",
                "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
                "PYTHONPATH": str(repo),
            }
            with (Path(directory) / "server.log").open("w+") as log:
                subprocess.run(
                    [sys.executable, "-m", "scripts.seed"],
                    cwd=repo,
                    env=env,
                    stdout=log,
                    stderr=log,
                    check=True,
                )
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                server = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                        "--no-access-log",
                    ],
                    cwd=repo,
                    env=env,
                    stdout=log,
                    stderr=log,
                )
                try:
                    url = f"http://127.0.0.1:{port}"
                    opener = build_opener(ProxyHandler({}))
                    deadline = time.monotonic() + 20
                    while True:
                        try:
                            with opener.open(url + "/health", timeout=1) as response:
                                if response.status == 200:
                                    break
                        except (URLError, TimeoutError):
                            pass
                        if server.poll() is not None or time.monotonic() >= deadline:
                            raise DemoError(
                                "Backend không khởi động; kiểm tra dependency trong .venv"
                            )
                        time.sleep(0.1)
                    print(
                        "MATCHMATE — DEMO API THẬT\n"
                        "DB tạm mới; tự dừng server và xóa DB khi kết thúc."
                    )
                    run_demo(url, args.step)
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait()
    except (DemoError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(
            f"\nDEMO DỪNG: {error}\nCài dependency: python -m pip install -r requirements-dev.txt"
        )
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nĐã dừng demo và dọn DB tạm.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
