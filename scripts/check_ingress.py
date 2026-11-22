"""Verify local HTTPS, proxy identity boundaries, body limit and a rate-limit burst."""

import argparse
import json
import ssl
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://localhost:8443")
    parser.add_argument("--ca", type=Path, default=Path("artifacts/ingress-tls/fullchain.pem"))
    args = parser.parse_args()
    client = build_opener(
        ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile=args.ca))
    )

    def request(path, data=None, headers=None):
        req = Request(args.url + path, data=data, headers=headers or {})
        try:
            response = client.open(req, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers

    assert request("/health")[0] == 200
    status, body, headers = request(
        "/sessions?host_me=true",
        headers={"X-User-ID": "1", "X-Account-ID": "1", "X-Forwarded-For": "203.0.113.1"},
    )
    assert status == 401 and body["error"]["code"] == "UNAUTHORIZED"
    assert headers["X-Request-ID"] == body["error"]["request_id"]
    assert headers.get_all("X-Request-ID") == [body["error"]["request_id"]]
    status, body, headers = request("/auth/login", data=b"x" * 65_537)
    assert status == 413 and body["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert headers["X-Request-ID"] == body["error"]["request_id"]
    statuses = Counter()
    for _ in range(15):
        status, body, headers = request(
            "/auth/login", data=b"{}", headers={"Content-Type": "application/json"}
        )
        statuses[status] += 1
        if status == 429:
            assert headers.get("Retry-After") == "6"
            assert headers["X-Request-ID"] == body["error"]["request_id"]
    assert statuses[429] > 0, statuses
    print(
        json.dumps(
            {
                "https": "passed",
                "spoofed_identity": "rejected",
                "body_limit": 413,
                "login_burst": dict(statuses),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
