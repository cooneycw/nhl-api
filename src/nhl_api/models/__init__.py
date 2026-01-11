"""Data models for NHL entities."""

from nhl_api.models.quanthockey import (
    QuantHockeyPlayerCareerStats,
    QuantHockeyPlayerSeasonStats,
    QuantHockeySeasonData,
)
from nhl_api.models.second_snapshots import (
    SITUATION_3V3,
    SITUATION_3V4,
    SITUATION_3V5,
    SITUATION_4V3,
    SITUATION_4V4,
    SITUATION_4V5,
    SITUATION_5V3,
    SITUATION_5V4,
    SITUATION_5V5,
    SecondSnapshot,
    calculate_situation_code,
    is_power_play_situation,
)
from nhl_api.models.shifts import (
    DETAIL_GOAL_EV,
    DETAIL_GOAL_PP,
    DETAIL_SHIFT,
    GOAL_TYPE_CODE,
    SHIFT_TYPE_CODE,
    ParsedShiftChart,
    ShiftRecord,
    parse_duration,
)

__all__ = [
    # QuantHockey Models
    "QuantHockeyPlayerCareerStats",
    "QuantHockeyPlayerSeasonStats",
    "QuantHockeySeasonData",
    # Second Snapshots Models
    "SITUATION_3V3",
    "SITUATION_3V4",
    "SITUATION_3V5",
    "SITUATION_4V3",
    "SITUATION_4V4",
    "SITUATION_4V5",
    "SITUATION_5V3",
    "SITUATION_5V4",
    "SITUATION_5V5",
    "SecondSnapshot",
    "calculate_situation_code",
    "is_power_play_situation",
    # Shifts Models
    "DETAIL_GOAL_EV",
    "DETAIL_GOAL_PP",
    "DETAIL_SHIFT",
    "GOAL_TYPE_CODE",
    "ParsedShiftChart",
    "SHIFT_TYPE_CODE",
    "ShiftRecord",
    "parse_duration",
]
