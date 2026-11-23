from datetime import datetime

from app.domain.entities import Participation, Session
from app.domain.enums import Gender, GenderPolicy, ParticipationStatus, SessionStatus, skill_to_rank
from app.domain.errors import DomainError
from app.domain.ports import Clock
from app.features.auth.contracts import PlayerProfile
from app.features.sessions.session_contracts import CreateSessionInput, SessionError


def require_host_eligibility(host: PlayerProfile, data: CreateSessionInput) -> None:
    if host.gender not in (Gender.MALE, Gender.FEMALE):
        raise SessionError("PROFILE_INCOMPLETE", "Hồ sơ chưa đầy đủ")

    minimum = skill_to_rank(data.min_level)
    maximum = skill_to_rank(data.max_level)
    if minimum > maximum:
        raise SessionError("VALIDATION_ERROR", "Khoảng trình độ không hợp lệ")

    if not _matches_requirements(host, minimum, maximum, data.gender_policy):
        raise SessionError("ELIGIBILITY_MISMATCH", "Host không đáp ứng điều kiện của kèo")


def require_player_eligibility(player: PlayerProfile, game: Session) -> None:
    if player.gender not in (Gender.MALE, Gender.FEMALE):
        raise DomainError("PROFILE_INCOMPLETE", "Cần khai giới tính để xác định phí")
    if not _matches_requirements(player, game.min_level, game.max_level, game.gender_policy):
        raise DomainError("ELIGIBILITY_MISMATCH", "Hồ sơ không đáp ứng điều kiện của kèo")


def _matches_requirements(
    profile: PlayerProfile, minimum: int, maximum: int, gender_policy: str
) -> bool:
    return gender_policy in (GenderPolicy.ANY, f"{profile.gender.value}_ONLY") and (
        minimum <= skill_to_rank(profile.skill_level) <= maximum
    )


def require_open_session(game: Session, now: datetime) -> None:
    if game.status == SessionStatus.CANCELLED:
        raise DomainError("SESSION_CANCELLED", "Kèo đã hủy")
    if now >= game.starts_at:
        raise DomainError("SESSION_ALREADY_STARTED", "Kèo đã bắt đầu")


def require_decision_allowed(
    game: Session, participation: Participation, actor_id: int, now: datetime
) -> None:
    if actor_id != game.host_user_id:
        raise DomainError("FORBIDDEN", "Chỉ chủ kèo được quyết định yêu cầu")
    if participation.status != ParticipationStatus.PENDING:
        raise DomainError("INVALID_STATE", "Chỉ quyết định yêu cầu đang PENDING")
    require_open_session(game, now)


def should_withdraw(
    game: Session, participation: Participation, actor_id: int, now: datetime
) -> bool:
    if actor_id != participation.user_id:
        raise DomainError("FORBIDDEN", "Chỉ được rút lượt của mình")
    if actor_id == game.host_user_id:
        raise DomainError("HOST_PARTICIPATION_REQUIRED", "Chủ kèo phải hủy kèo để rút")
    if participation.status == ParticipationStatus.CANCELLED:
        return False
    if participation.status not in (ParticipationStatus.PENDING, ParticipationStatus.ACCEPTED):
        raise DomainError("INVALID_STATE", "Lượt này không thể rút")
    require_open_session(game, now)
    return True


def session_cancellation_time(
    *, host_id: int, actor_id: int, status: str, starts_at: datetime, clock: Clock
) -> datetime | None:
    if host_id != actor_id:
        raise SessionError("FORBIDDEN", "Chỉ host được hủy kèo")
    if status == SessionStatus.CANCELLED:
        return None
    now = clock.now()
    if now >= starts_at:
        raise SessionError("SESSION_ALREADY_STARTED", "Kèo đã bắt đầu")
    return now
