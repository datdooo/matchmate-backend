import secrets
from pathlib import Path


def main() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"

    content = (
        f"JWT_SECRET_KEY={secrets.token_urlsafe(32)}\n"
        "JWT_ALGORITHM=HS256\n"
        "ACCESS_TOKEN_EXPIRE_MINUTES=60\n"
    )

    try:
        with env_path.open("x", encoding="utf-8") as file:
            file.write(content)
    except FileExistsError:
        print(".env already exists; kept unchanged.")
        return

    print("Created .env with a random JWT secret.")


if __name__ == "__main__":
    main()
