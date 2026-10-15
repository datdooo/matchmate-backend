"""Phase 1 ORM models and database constraints."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTimeText


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("skill_level BETWEEN 1 AND 19", name="ck_users_skill_level"),
        CheckConstraint(
            "gender IN ('MALE','FEMALE','UNSPECIFIED')",
            name="ck_users_gender",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    skill_level: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)


class VenueModel(Base):
    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_venues_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_venues_longitude"),
        CheckConstraint("is_active IN (0,1)", name="ck_venues_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    district_code: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("length(title) BETWEEN 1 AND 120", name="ck_sessions_title"),
        CheckConstraint("length(notes) <= 1000", name="ck_sessions_notes"),
        CheckConstraint("starts_at < ends_at", name="ck_sessions_time_window"),
        CheckConstraint("play_type IN ('SINGLES','DOUBLES')", name="ck_sessions_play_type"),
        CheckConstraint("fee_male_vnd >= 0", name="ck_sessions_fee_male"),
        CheckConstraint("fee_female_vnd >= 0", name="ck_sessions_fee_female"),
        CheckConstraint("min_level BETWEEN 1 AND 19", name="ck_sessions_min_level"),
        CheckConstraint("max_level BETWEEN 1 AND 19", name="ck_sessions_max_level"),
        CheckConstraint("min_level <= max_level", name="ck_sessions_level_window"),
        CheckConstraint(
            "gender_policy IN ('ANY','MALE_ONLY','FEMALE_ONLY')",
            name="ck_sessions_gender_policy",
        ),
        CheckConstraint("status IN ('OPEN','CANCELLED')", name="ck_sessions_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    starts_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    play_type: Mapped[str] = mapped_column(String(16), nullable=False)
    fee_male_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_female_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    min_level: Mapped[int] = mapped_column(Integer, nullable=False)
    max_level: Mapped[int] = mapped_column(Integer, nullable=False)
    gender_policy: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)


class ParticipationModel(Base):
    __tablename__ = "participations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','ACCEPTED','REJECTED','CANCELLED')",
            name="ck_participations_status",
        ),
        CheckConstraint("gender_at_join IN ('MALE','FEMALE')", name="ck_participations_gender"),
        CheckConstraint("quoted_fee_vnd >= 0", name="ck_participations_fee"),
        Index("ix_participations_session_status", "session_id", "status"),
        Index("ix_participations_user_status", "user_id", "status"),
        Index(
            "uq_participations_active_user_session",
            "user_id",
            "session_id",
            unique=True,
            sqlite_where=text("status IN ('PENDING','ACCEPTED')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
    gender_at_join: Mapped[str] = mapped_column(String(16), nullable=False)
    quoted_fee_vnd: Mapped[int] = mapped_column(Integer, nullable=False)


class MatchingRequestModel(Base):
    __tablename__ = "matching_requests"
    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="ck_matching_time_window"),
        CheckConstraint("play_type IN ('SINGLES','DOUBLES')", name="ck_matching_play_type"),
        CheckConstraint("proposed_fee_male_vnd >= 0", name="ck_matching_fee_male"),
        CheckConstraint("proposed_fee_female_vnd >= 0", name="ck_matching_fee_female"),
        CheckConstraint("budget_max_vnd >= 0", name="ck_matching_budget"),
        CheckConstraint(
            "gender_policy IN ('ANY','MALE_ONLY','FEMALE_ONLY')",
            name="ck_matching_gender_policy",
        ),
        CheckConstraint("status IN ('ACTIVE','CLOSED')", name="ck_matching_status"),
        CheckConstraint(
            "closed_reason IS NULL OR closed_reason IN ('REPLACED','CONFIRMED','CANCELLED')",
            name="ck_matching_closed_reason",
        ),
        Index(
            "ix_matching_candidate_window",
            "play_type",
            "venue_id",
            "starts_at",
            "ends_at",
            "status",
        ),
        Index(
            "uq_matching_active_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    play_type: Mapped[str] = mapped_column(String(16), nullable=False)
    proposed_fee_male_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_fee_female_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_max_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    gender_policy: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    closed_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeText(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTimeText(), nullable=True)
