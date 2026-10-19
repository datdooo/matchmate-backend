from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import VenueModel
from app.db.session import create_db_engine, create_session_factory


@pytest.fixture
def db_engine(tmp_path: Path) -> Iterator[Engine]:
    """Mỗi test dùng một SQLite file riêng, có đủ năm bảng."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")

    try:
        # Import models đã đăng ký đủ năm bảng vào cùng metadata.
        VenueModel.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session_factory(db_engine: Engine) -> sessionmaker[Session]:
    """Cấp các DB Session cùng trỏ vào DB tạm của test."""
    return create_session_factory(db_engine)


@pytest.fixture
def db_session(
    db_session_factory: sessionmaker[Session],
) -> Iterator[Session]:
    """DB Session để chuẩn bị dữ liệu và kiểm kết quả."""
    with db_session_factory() as session:
        try:
            yield session
        finally:
            session.rollback()
