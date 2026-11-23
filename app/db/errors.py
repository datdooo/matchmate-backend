import sqlite3

from sqlalchemy.exc import DBAPIError, IntegrityError


def is_database_busy(error: DBAPIError) -> bool:
    """Nhận diện khóa bận, deadlock và serialization failure."""
    if sqlstate(error) in {"55P03", "40P01", "40001"}:
        return True

    code = getattr(error.orig, "sqlite_errorcode", None)

    if not isinstance(code, int):
        return False

    # Mã mở rộng giữ mã nhóm ở 8 bit thấp.
    primary_code = code & 0xFF
    return primary_code == sqlite3.SQLITE_BUSY


def sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def is_statement_timeout(error: DBAPIError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    message = getattr(diagnostic, "message_primary", None)
    return sqlstate(error) == "57014" and message == "canceling statement due to statement timeout"


def is_connection_failure(error: DBAPIError) -> bool:
    state = sqlstate(error) or ""
    return (
        error.connection_invalidated
        or state.startswith("08")
        or state
        in {
            "57P01",
            "57P02",
            "57P03",
            "53300",
        }
    )


def is_unique_violation(
    error: IntegrityError, *, postgres_constraint: str, sqlite_columns: str
) -> bool:
    if sqlstate(error) == "23505":
        diagnostic = getattr(error.orig, "diag", None)
        return getattr(diagnostic, "constraint_name", None) == postgres_constraint
    return (
        getattr(error.orig, "sqlite_errorcode", None) == sqlite3.SQLITE_CONSTRAINT_UNIQUE
        and str(error.orig) == f"UNIQUE constraint failed: {sqlite_columns}"
    )
