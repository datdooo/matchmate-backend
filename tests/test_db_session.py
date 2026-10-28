import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.db.session import create_db_engine


@pytest.mark.parametrize("busy_timeout", [None, 1200])
def test_pragmas_on_every_connection(
    tmp_path: Path,
    busy_timeout: int | None,
) -> None:
    """Kiểm PRAGMA trên hai connection tới cùng SQLite file."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"

    if busy_timeout is None:
        # Không truyền timeout để kiểm giá trị mặc định.
        engine = create_db_engine(database_url)
        expected_timeout = 5000
    else:
        engine = create_db_engine(database_url, busy_timeout=busy_timeout)
        expected_timeout = busy_timeout

    try:
        # Giữ connection đầu mở để engine phải cấp connection khác.
        with engine.connect() as first, engine.connect() as second:
            for connection in (first, second):
                foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
                timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()

                assert foreign_keys == 1
                assert timeout == expected_timeout
    finally:
        # Trả tài nguyên để pytest dọn thư mục tạm.
        engine.dispose()


def test_runtime_engine_uses_explicit_test_database(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'environment.db'}"
    command = (
        "import json; from app.db.session import engine; "
        "connection=engine.connect(); "
        "print(json.dumps({'url': str(engine.url), "
        "'timeout': connection.exec_driver_sql('PRAGMA busy_timeout').scalar_one()})); "
        "connection.close(); engine.dispose()"
    )
    result = subprocess.run(
        [sys.executable, "-c", command],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ | {"DATABASE_URL": database_url, "SQLITE_BUSY_TIMEOUT_MS": "1200"},
    )
    assert json.loads(result.stdout) == {"url": database_url, "timeout": 1200}
