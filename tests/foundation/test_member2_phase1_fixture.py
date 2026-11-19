import sqlite3

import pytest

from scripts.prepare_member2_phase1 import prepare


def test_migration_source_preserves_history_and_active_uniqueness(tmp_path):
    manifest = prepare(tmp_path)
    assert manifest["counts"] == {
        "venues": 1,
        "users": 3,
        "sessions": 1,
        "participations": 4,
        "matching_requests": 3,
    }
    with sqlite3.connect(tmp_path / "migration-source.db") as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute(
            "SELECT status FROM participations WHERE user_id = 30 ORDER BY id"
        ).fetchall() == [("REJECTED",), ("CANCELLED",), ("ACCEPTED",)]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO participations SELECT 999, user_id, session_id, status, "
                "gender_at_join, quoted_fee_vnd, created_at, decided_at, cancelled_at "
                "FROM participations WHERE id = 90"
            )
        db.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO matching_requests SELECT 999, user_id, venue_id, starts_at, "
                "ends_at, play_type, proposed_fee_male_vnd, proposed_fee_female_vnd, "
                "budget_max_vnd, gender_policy, status, closed_reason, created_at, closed_at "
                "FROM matching_requests WHERE id = 120"
            )


def test_existing_evidence_is_not_overwritten(tmp_path):
    prepare(tmp_path)
    before = (tmp_path / "migration-source.db").read_bytes()
    with pytest.raises(FileExistsError):
        prepare(tmp_path)
    assert (tmp_path / "migration-source.db").read_bytes() == before
