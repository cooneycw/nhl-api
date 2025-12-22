"""Validation rules by source type.

Each module contains validation functions for a specific data source:
- boxscore: NHL JSON API boxscore data
- play_by_play: NHL JSON API play-by-play events
- shift_chart: NHL Stats API shift data
- standings: NHL JSON API standings
- html_reports: NHL HTML report data (ES, GS, FS, SS, TH/TV)
- cross_source: Cross-source validation (PBP vs Boxscore, Shifts vs Boxscore, etc.)
"""

from nhl_api.validation.rules.boxscore import validate_boxscore
from nhl_api.validation.rules.cross_source import (
    validate_final_score_schedule_vs_boxscore,
    validate_goals_pbp_vs_boxscore,
    validate_shift_count_shifts_vs_boxscore,
    validate_shots_pbp_vs_boxscore,
    validate_toi_shifts_vs_boxscore,
)
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
    # Internal consistency rules
    "validate_boxscore",
    "validate_play_by_play",
    "validate_shift_chart",
    "validate_standings",
    "validate_event_summary",
    "validate_game_summary",
    "validate_faceoff_summary",
    "validate_shot_summary",
    "validate_time_on_ice",
    # Cross-source rules
    "validate_goals_pbp_vs_boxscore",
    "validate_shots_pbp_vs_boxscore",
    "validate_toi_shifts_vs_boxscore",
    "validate_shift_count_shifts_vs_boxscore",
    "validate_final_score_schedule_vs_boxscore",
]
