"""Validation rules by source type.

Each module contains validation functions for a specific data source:
- boxscore: NHL JSON API boxscore data
- play_by_play: NHL JSON API play-by-play events
- shift_chart: NHL Stats API shift data
- standings: NHL JSON API standings
- html_reports: NHL HTML report data (ES, GS, FS, SS, TH/TV)
"""

from nhl_api.validation.rules.boxscore import validate_boxscore
from nhl_api.validation.rules.html_reports import (
    validate_event_summary,
    validate_faceoff_summary,
    validate_game_summary,
    validate_shot_summary,
    validate_time_on_ice,
)
from nhl_api.validation.rules.play_by_play import validate_play_by_play
from nhl_api.validation.rules.shift_chart import validate_shift_chart
from nhl_api.validation.rules.standings import validate_standings

__all__ = [
    "validate_boxscore",
    "validate_play_by_play",
    "validate_shift_chart",
    "validate_standings",
    "validate_event_summary",
    "validate_game_summary",
    "validate_faceoff_summary",
    "validate_shot_summary",
    "validate_time_on_ice",
]
