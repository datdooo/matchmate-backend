from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ParticipationModel
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository

START = datetime(2030, 11, 1, 12, tzinfo=timezone.utc)


def test_count_includes_host_and_ignores_pending(db_session_factory, game_data):
    with db_session_factory() as session:
        session.add_all(
            [
                ParticipationModel(
                    user_id=game_data["player"],
                    session_id=game_data["first"],
                    status="ACCEPTED",
                    gender_at_join="FEMALE",
                    quoted_fee_vnd=40000,
                    created_at=START,
                    decided_at=START,
                ),
                ParticipationModel(
                    user_id=game_data["player"],
                    session_id=game_data["second"],
                    status="PENDING",
                    gender_at_join="FEMALE",
                    quoted_fee_vnd=40000,
                    created_at=START,
                ),
            ]
        )
        session.flush()
        repo = SqlAlchemyParticipationRepository(lambda: session)
        assert [repo.count_accepted(game_data[key]) for key in ("first", "second")] == [2, 1]
        assert repo.count_accepted(9999) == 0


@pytest.mark.parametrize(
    "status, expected",
    [
        ("PENDING", True),
        ("ACCEPTED", True),
        ("REJECTED", False),
        ("CANCELLED", False),
    ],
)
def test_active_only_blocks_pending_or_accepted(db_session_factory, game_data, status, expected):
    with db_session_factory() as session:
        session.add(
            ParticipationModel(
                user_id=game_data["player"],
                session_id=game_data["first"],
                status=status,
                gender_at_join="FEMALE",
                quoted_fee_vnd=40000,
                created_at=START,
            )
        )
        session.flush()
        repo = SqlAlchemyParticipationRepository(lambda: session)
        assert repo.has_active(game_data["player"], game_data["first"]) is expected
        assert repo.has_active(game_data["player"], game_data["second"]) is False
        assert repo.has_active(game_data["other"], game_data["first"]) is False


@pytest.mark.parametrize(
    "start, end, expected",
    [
        (-1, 0, False),
        (0, 1, True),
        (1, 3, True),
        (2, 4, False),
    ],
)
def test_overlap_ignores_pending_and_allows_adjacent(
    db_session_factory: sessionmaker[Session],
    game_data,
    start,
    end,
    expected,
):
    with db_session_factory() as session:
        for key, status in [("first", "ACCEPTED"), ("second", "PENDING")]:
            session.add(
                ParticipationModel(
                    user_id=game_data["player"],
                    session_id=game_data[key],
                    status=status,
                    gender_at_join="FEMALE",
                    quoted_fee_vnd=40000,
                    created_at=START,
                )
            )
        session.flush()
        repo = SqlAlchemyParticipationRepository(lambda: session)
        assert (
            repo.has_overlap(
                game_data["player"], START + timedelta(hours=start), START + timedelta(hours=end)
            )
            is expected
        )
        assert repo.has_overlap(game_data["other"], START, START + timedelta(hours=2)) is False
