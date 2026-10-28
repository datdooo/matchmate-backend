from enum import Enum


class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    UNSPECIFIED = "UNSPECIFIED"


class GenderPolicy(str, Enum):
    ANY = "ANY"
    MALE_ONLY = "MALE_ONLY"
    FEMALE_ONLY = "FEMALE_ONLY"


class SkillLevel(str, Enum):
    NEWBIE = "NEWBIE"
    Y_MINUS = "Y_MINUS"
    Y = "Y"
    Y_PLUS = "Y_PLUS"
    TBY_MINUS = "TBY_MINUS"
    TBY = "TBY"
    TBY_PLUS = "TBY_PLUS"
    TB_MINUS = "TB_MINUS"
    TB = "TB"
    TB_PLUS = "TB_PLUS"
    TBK_MINUS = "TBK_MINUS"
    TBK = "TBK"
    TBK_PLUS = "TBK_PLUS"
    K_MINUS = "K_MINUS"
    K = "K"
    K_PLUS = "K_PLUS"
    T_MINUS = "T_MINUS"
    T = "T"
    T_PLUS = "T_PLUS"


SKILL_TO_RANK = {level: rank for rank, level in enumerate(SkillLevel, start=1)}

RANK_TO_SKILL = {rank: level for level, rank in SKILL_TO_RANK.items()}


def skill_to_rank(level: SkillLevel) -> int:
    return SKILL_TO_RANK[level]


def rank_to_skill(rank: int) -> SkillLevel:
    return RANK_TO_SKILL[rank]


class PlayType(str, Enum):
    SINGLES = "SINGLES"
    DOUBLES = "DOUBLES"


class MatchingStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class SessionStatus(str, Enum):
    OPEN = "OPEN"
    CANCELLED = "CANCELLED"


class DisplayStatus(str, Enum):
    CANCELLED = "CANCELLED"
    ENDED = "ENDED"
    STARTED = "STARTED"
    FULL = "FULL"
    AVAILABLE = "AVAILABLE"


class EffectiveStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"


class CloseReason(str, Enum):
    REPLACED = "REPLACED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
