"""Create a short-lived localhost certificate under ignored artifacts, using OpenSSL."""

import argparse
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openssl", default=shutil.which("openssl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/ingress-tls"))
    args = parser.parse_args()
    executable = args.openssl
    if executable is None and (git := shutil.which("git")):
        candidate = Path(git).resolve().parents[1] / "mingw64/bin/openssl.exe"
        if candidate.exists():
            executable = str(candidate)
    if executable is None:
        parser.error("Install OpenSSL or pass --openssl PATH")
    args.output.mkdir(parents=True, exist_ok=True)
    key = args.output / "privkey.pem"
    cert = args.output / "fullchain.pem"
    if key.exists() or cert.exists():
        parser.error("Output already contains a certificate/key; choose another directory")
    subprocess.run(
        [
            executable,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "7",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    try:
        key.chmod(0o600)
    except OSError:
        pass
    print(f"Local TLS files created in {args.output}; validity 7 days.")


if __name__ == "__main__":
    main()
