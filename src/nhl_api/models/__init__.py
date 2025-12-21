"""Data models for NHL entities."""

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
    "DETAIL_GOAL_EV",
    "DETAIL_GOAL_PP",
    "DETAIL_SHIFT",
    "GOAL_TYPE_CODE",
    "ParsedShiftChart",
    "SHIFT_TYPE_CODE",
    "ShiftRecord",
    "parse_duration",
]
