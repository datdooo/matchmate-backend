from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTimeText


class VenueModel(Base):
    """Địa điểm chơi cầu lông, tra cứu theo quận."""

    __tablename__ = "venues"

    __table_args__ = (
        CheckConstraint(
            "is_active IN (0, 1)",
            name="ck_venues_is_active",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)

    # Dùng mã quận thống nhất giữa seed và bộ lọc tìm kiếm.
    district_code: Mapped[str] = mapped_column(String, nullable=False)

    # SQLite lưu Boolean bằng 0/1.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UserModel(Base):
    """Tài khoản và hồ sơ dùng để kiểm điều kiện tham gia."""

    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "skill_level BETWEEN 1 AND 19",
            name="ck_users_skill_level",
        ),
        CheckConstraint(
            "gender IN ('MALE', 'FEMALE', 'UNSPECIFIED')",
            name="ck_users_gender",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)

    # DB lưu rank 1..19; mapper chuyển qua enum chung của domain.
    skill_level: Mapped[int] = mapped_column(Integer, nullable=False)

    # UNSPECIFIED nhận diện hồ sơ thiếu; API đăng ký chỉ nhận MALE/FEMALE.
    gender: Mapped[str] = mapped_column(String, nullable=False)

    # Service truyền thời gian vào để toàn bộ thao tác dùng cùng mốc now.
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)


class SessionModel(Base):
    """Kèo có một sân và lịch cố định; host cũng là người chơi."""

    __tablename__ = "sessions"

    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) BETWEEN 1 AND 120",
            name="ck_sessions_title",
        ),
        CheckConstraint(
            "length(notes) <= 1000",
            name="ck_sessions_notes",
        ),
        CheckConstraint(
            "starts_at < ends_at",
            name="ck_sessions_time",
        ),
        CheckConstraint(
            "play_type IN ('SINGLES', 'DOUBLES')",
            name="ck_sessions_play_type",
        ),
        CheckConstraint(
            "fee_male_vnd >= 0 AND fee_female_vnd >= 0",
            name="ck_sessions_fees",
        ),
        CheckConstraint(
            "min_level BETWEEN 1 AND 19 AND max_level BETWEEN 1 AND 19 AND min_level <= max_level",
            name="ck_sessions_levels",
        ),
        CheckConstraint(
            "gender_policy IN ('ANY', 'MALE_ONLY', 'FEMALE_ONLY')",
            name="ck_sessions_gender_policy",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'CANCELLED')",
            name="ck_sessions_status",
        ),
        CheckConstraint(
            "(status = 'OPEN' AND cancelled_at IS NULL) "
            "OR (status = 'CANCELLED' AND cancelled_at IS NOT NULL)",
            name="ck_sessions_cancelled_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Không xóa cascade để giữ lịch sử kèo và lượt tham gia.
    host_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str] = mapped_column(String, nullable=False, default="")

    starts_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)

    # Sức chứa suy từ play_type: đơn 2, đôi 4; không lưu cột capacity.
    play_type: Mapped[str] = mapped_column(String, nullable=False)
    fee_male_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_female_vnd: Mapped[int] = mapped_column(Integer, nullable=False)

    min_level: Mapped[int] = mapped_column(Integer, nullable=False)
    max_level: Mapped[int] = mapped_column(Integer, nullable=False)
    gender_policy: Mapped[str] = mapped_column(String, nullable=False, default="ANY")

    status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)


class ParticipationModel(Base):
    """Lượt tham gia toàn bộ lịch kèo, giữ lại cả các lượt đã kết thúc."""

    __tablename__ = "participations"

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
            name="ck_participations_status",
        ),
        CheckConstraint(
            "gender_at_join IN ('MALE', 'FEMALE')",
            name="ck_participations_gender",
        ),
        CheckConstraint(
            "quoted_fee_vnd >= 0",
            name="ck_participations_fee",
        ),
        # Chỉ cấm trùng lượt đang hoạt động; lượt cũ vẫn được giữ lịch sử.
        Index(
            "uq_participations_active",
            "user_id",
            "session_id",
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'ACCEPTED')"),
        ),
        Index(
            "ix_participations_session_status",
            "session_id",
            "status",
        ),
        Index(
            "ix_participations_user_status",
            "user_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False)

    # Snapshot lúc đăng ký; duyệt, rút hoặc hủy đều giữ nguyên.
    gender_at_join: Mapped[str] = mapped_column(String, nullable=False)
    quoted_fee_vnd: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)


class MatchingRequestModel(Base):
    """Nhu cầu tìm nhóm tại một sân và lịch cố định."""

    __tablename__ = "matching_requests"

    __table_args__ = (
        CheckConstraint(
            "starts_at < ends_at",
            name="ck_matching_requests_time",
        ),
        CheckConstraint(
            "play_type IN ('SINGLES', 'DOUBLES')",
            name="ck_matching_requests_play_type",
        ),
        CheckConstraint(
            "proposed_fee_male_vnd >= 0 AND proposed_fee_female_vnd >= 0 AND budget_max_vnd >= 0",
            name="ck_matching_requests_fees",
        ),
        CheckConstraint(
            "gender_policy IN ('ANY', 'MALE_ONLY', 'FEMALE_ONLY')",
            name="ck_matching_requests_gender_policy",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'CLOSED')",
            name="ck_matching_requests_status",
        ),
        CheckConstraint(
            "(status = 'ACTIVE' "
            "AND closed_at IS NULL AND closed_reason IS NULL) "
            "OR (status = 'CLOSED' AND closed_at IS NOT NULL "
            "AND closed_reason IS NOT NULL "
            "AND closed_reason IN ('REPLACED', 'CONFIRMED', 'CANCELLED'))",
            name="ck_matching_requests_closure",
        ),
        # Mỗi user có tối đa một nhu cầu ACTIVE, kể cả bản đã quá giờ.
        Index(
            "uq_matching_requests_active_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "ix_matching_requests_candidates",
            "play_type",
            "venue_id",
            "starts_at",
            "ends_at",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)

    starts_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    play_type: Mapped[str] = mapped_column(String, nullable=False)

    proposed_fee_male_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_fee_female_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_max_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    gender_policy: Mapped[str] = mapped_column(String, nullable=False, default="ANY")

    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    closed_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
