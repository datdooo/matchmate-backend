from enum import Enum


class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    UNSPECIFIED = "UNSPECIFIED"


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
