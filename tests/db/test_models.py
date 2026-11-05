import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, select
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.models import (
    MatchingRequestModel,
    ParticipationModel,
    SessionModel,
    UserModel,
    VenueModel,
)
from app.db.session import create_db_engine, create_session_factory


@pytest.fixture
def db_engine(tmp_path: Path) -> Iterator[Engine]:
    """Tạo DB riêng cho mỗi test, không dùng DB local."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'models.db'}")
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()


def test_creates_five_tables(db_engine: Engine) -> None:
    """Các model phải tạo được đủ năm bảng trên SQLite."""
    tables = inspect(db_engine).get_table_names()

    assert set(tables) == {
        "users",
        "venues",
        "sessions",
        "participations",
        "matching_requests",
    }


def test_venue_round_trip(db_engine: Engine) -> None:
    """Ghi sân rồi đọc bằng DB Session mới để kiểm dữ liệu đã commit."""
    factory = create_session_factory(db_engine)

    with factory() as session:
        venue = VenueModel(
            name="Sân demo 01",
            address="Địa điểm giả lập",
            district_code="CAU_GIAY",
        )
        session.add(venue)
        session.commit()
        venue_id = venue.id

    with factory() as session:
        saved = session.scalar(select(VenueModel).where(VenueModel.id == venue_id))

        assert saved is not None
        assert saved.name == "Sân demo 01"
        assert saved.district_code == "CAU_GIAY"
        assert saved.is_active is True

    # Schema mới chỉ tìm theo quận, không giữ các cột tọa độ.
    columns = {column["name"] for column in inspect(db_engine).get_columns("venues")}
    assert columns == {
        "id",
        "name",
        "address",
        "district_code",
        "is_active",
    }


@pytest.mark.parametrize(
    ("skill_level", "gender"),
    [
        (0, "MALE"),
        (20, "FEMALE"),
        (9, "INVALID"),
    ],
)
def test_rejects_invalid_profile(
    db_engine: Engine,
    skill_level: int,
    gender: str,
) -> None:
    """DB phải chặn rank hoặc giới tính ngoài tập giá trị cho phép."""
    factory = create_session_factory(db_engine)
    now = datetime.now(timezone.utc)

    with factory() as session:
        user = UserModel(
            email="test@example.com",
            password_hash="test-hash",
            display_name="Người chơi demo",
            skill_level=skill_level,
            gender=gender,
            created_at=now,
            updated_at=now,
        )
        session.add(user)

        with pytest.raises(IntegrityError) as caught:
            session.flush()

        # Kiểm đúng lỗi CHECK, tránh test pass vì một lỗi dữ liệu khác.
        assert caught.value.orig.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_CHECK
        session.rollback()


def test_rejects_participation_with_missing_references(
    db_engine: Engine,
) -> None:
    """Không tạo được lượt tham gia khi user và kèo chưa tồn tại."""
    factory = create_session_factory(db_engine)

    with factory() as session:
        participation = ParticipationModel(
            user_id=999,
            session_id=999,
            status="PENDING",
            gender_at_join="MALE",
            quoted_fee_vnd=60000,
            created_at=datetime.now(timezone.utc),
        )
        session.add(participation)

        with pytest.raises(IntegrityError) as caught:
            session.flush()

        assert caught.value.orig.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY
        session.rollback()


@pytest.fixture
def session_data(db_engine: Engine) -> tuple[int, int]:
    """Tạo kèo có host ACCEPTED và một player chưa tham gia."""
    factory = create_session_factory(db_engine)
    now = datetime.now(timezone.utc)

    with factory() as session:
        host = UserModel(
            email="host@example.com",
            password_hash="test-hash",
            display_name="Host demo",
            skill_level=9,
            gender="MALE",
            created_at=now,
            updated_at=now,
        )
        player = UserModel(
            email="player@example.com",
            password_hash="test-hash",
            display_name="Player demo",
            skill_level=9,
            gender="FEMALE",
            created_at=now,
            updated_at=now,
        )
        venue = VenueModel(
            name="Sân demo",
            address="Địa điểm giả lập",
            district_code="CAU_GIAY",
        )
        session.add_all([host, player, venue])
        # Lấy ID để tạo các bản ghi có khóa ngoại.
        session.flush()

        game = SessionModel(
            host_user_id=host.id,
            venue_id=venue.id,
            title="Kèo demo",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=2),
            play_type="DOUBLES",
            fee_male_vnd=70000,
            fee_female_vnd=60000,
            min_level=8,
            max_level=10,
            created_at=now,
        )
        session.add(game)
        session.flush()

        session.add(
            ParticipationModel(
                user_id=host.id,
                session_id=game.id,
                status="ACCEPTED",
                gender_at_join="MALE",
                quoted_fee_vnd=70000,
                created_at=now,
                decided_at=now,
            )
        )
        session.commit()
        return player.id, game.id


@pytest.mark.parametrize("existing_status", ["PENDING", "ACCEPTED"])
def test_rejects_duplicate_active_participation(
    db_engine: Engine,
    session_data: tuple[int, int],
    existing_status: str,
) -> None:
    """PENDING và ACCEPTED đều chặn một lượt hoạt động mới."""
    player_id, game_id = session_data
    factory = create_session_factory(db_engine)
    now = datetime.now(timezone.utc)

    with factory() as session:
        session.add(
            ParticipationModel(
                user_id=player_id,
                session_id=game_id,
                status=existing_status,
                gender_at_join="FEMALE",
                quoted_fee_vnd=60000,
                created_at=now,
                decided_at=now if existing_status == "ACCEPTED" else None,
            )
        )
        session.commit()

        session.add(
            ParticipationModel(
                user_id=player_id,
                session_id=game_id,
                status="PENDING",
                gender_at_join="FEMALE",
                quoted_fee_vnd=60000,
                created_at=now,
            )
        )

        with pytest.raises(IntegrityError) as caught:
            session.flush()

        assert caught.value.orig.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE
        session.rollback()


@pytest.mark.parametrize("existing_status", ["ACTIVE", "CLOSED"])
def test_matching_request_active_uniqueness(
    db_engine: Engine,
    session_data: tuple[int, int],
    existing_status: str,
) -> None:
    """Chỉ nhu cầu ACTIVE chặn user tạo thêm nhu cầu ACTIVE khác."""
    player_id, game_id = session_data
    factory = create_session_factory(db_engine)
    now = datetime.now(timezone.utc)

    with factory() as session:
        game = session.get(SessionModel, game_id)
        assert game is not None

        # Hai nhu cầu dùng chung dữ liệu; khác trạng thái và thời điểm đóng.
        request_data = {
            "user_id": player_id,
            "venue_id": game.venue_id,
            "starts_at": game.starts_at,
            "ends_at": game.ends_at,
            "play_type": "DOUBLES",
            "proposed_fee_male_vnd": 70000,
            "proposed_fee_female_vnd": 60000,
            "budget_max_vnd": 80000,
            "gender_policy": "ANY",
            "created_at": now,
        }

        session.add(
            MatchingRequestModel(
                **request_data,
                status=existing_status,
                closed_reason="REPLACED" if existing_status == "CLOSED" else None,
                closed_at=now if existing_status == "CLOSED" else None,
            )
        )
        session.commit()

        session.add(MatchingRequestModel(**request_data, status="ACTIVE"))

        if existing_status == "ACTIVE":
            with pytest.raises(IntegrityError) as caught:
                session.flush()

            assert caught.value.orig.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE
            session.rollback()
        else:
            session.commit()

        # Đọc bằng Session mới để kiểm kết quả thực sự đã lưu.
    with factory() as session:
        requests = session.scalars(
            select(MatchingRequestModel).where(MatchingRequestModel.user_id == player_id)
        ).all()

        assert len(requests) == (1 if existing_status == "ACTIVE" else 2)
        assert sum(item.status == "ACTIVE" for item in requests) == 1


@pytest.mark.parametrize("old_status", ["REJECTED", "CANCELLED"])
def test_allows_rejoin_after_closed_participation(
    db_engine: Engine,
    session_data: tuple[int, int],
    old_status: str,
) -> None:
    """Lượt đã kết thúc không chặn đăng ký lại vào cùng kèo."""
    player_id, game_id = session_data
    factory = create_session_factory(db_engine)
    now = datetime.now(timezone.utc)

    with factory() as session:
        old = ParticipationModel(
            user_id=player_id,
            session_id=game_id,
            status=old_status,
            gender_at_join="FEMALE",
            quoted_fee_vnd=60000,
            created_at=now,
            decided_at=now if old_status == "REJECTED" else None,
            cancelled_at=now if old_status == "CANCELLED" else None,
        )
        session.add(old)
        session.commit()

        session.add(
            ParticipationModel(
                user_id=player_id,
                session_id=game_id,
                status="PENDING",
                gender_at_join="FEMALE",
                quoted_fee_vnd=60000,
                created_at=now,
            )
        )
        session.commit()

    with factory() as session:
        records = session.scalars(
            select(ParticipationModel).where(
                ParticipationModel.user_id == player_id,
                ParticipationModel.session_id == game_id,
            )
        ).all()

        assert len(records) == 2
        assert {record.status for record in records} == {old_status, "PENDING"}
