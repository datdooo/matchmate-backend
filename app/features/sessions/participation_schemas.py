from dataclasses import asdict
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.domain.enums import Gender, ParticipationStatus, rank_to_skill
from app.features.discovery.schemas import PlayerSummary, SessionSummary
from app.features.sessions.participation_contracts import ParticipationDetail


class JoinSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: int = Field(strict=True, gt=0, le=9223372036854775807)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["APPROVE", "REJECT"]


class ParticipationDetailResponse(BaseModel):
    id: int
    user_id: int
    session_id: int
    player: PlayerSummary
    status: ParticipationStatus
    created_at: AwareDatetime
    decided_at: AwareDatetime | None
    cancelled_at: AwareDatetime | None
    can_cancel: bool
    can_decide: bool
    gender_at_join: Gender
    quoted_fee_vnd: int
    session: SessionSummary

    @classmethod
    def from_detail(cls, detail: ParticipationDetail) -> "ParticipationDetailResponse":
        values = asdict(detail)
        # Domain/DB giữ rank số; API trả mã trình qua mapping chung.
        for player in (values["player"], values["session"]["host"]):
            player["skill_level"] = rank_to_skill(player["skill_level"])
        for field in ("min_level", "max_level"):
            values["session"][field] = rank_to_skill(values["session"][field])
        return cls.model_validate(values)
