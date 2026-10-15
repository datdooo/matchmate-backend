"""FastAPI/Pydantic schemas for participation endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class JoinSessionRequest(StrictRequestModel):
    session_id: int = Field(gt=0)


class DecisionRequest(StrictRequestModel):
    decision: Literal["APPROVE", "REJECT"]


class PlayerSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    skill_level: str
    gender: str


class VenueViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    district_code: str
    latitude: float
    longitude: float
    distance_km: float | None


class SessionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    host: PlayerSummaryResponse
    venue: VenueViewResponse
    starts_at: datetime
    ends_at: datetime
    play_type: str
    capacity: int
    fee_male_vnd: int
    fee_female_vnd: int
    min_level: str
    max_level: str
    gender_policy: str
    status: str
    display_status: str
    accepted_count: int
    remaining_capacity: int


class ParticipationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    session_id: int
    player: PlayerSummaryResponse
    status: str
    created_at: datetime
    decided_at: datetime | None
    cancelled_at: datetime | None
    can_cancel: bool
    can_decide: bool
    gender_at_join: str
    quoted_fee_vnd: int
    session: SessionSummaryResponse
