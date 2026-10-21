import sqlite3

from sqlalchemy.exc import DBAPIError


def is_database_busy(error: DBAPIError) -> bool:
    """Nhận diện nhóm SQLITE_BUSY từ lỗi driver gốc."""
    code = getattr(error.orig, "sqlite_errorcode", None)

    if not isinstance(code, int):
        return False

    # Mã mở rộng giữ mã nhóm ở 8 bit thấp.
    primary_code = code & 0xFF
    return primary_code == sqlite3.SQLITE_BUSY
