"""Validation constants and tolerances.

Defines thresholds, ranges, and other constants used by validation rules.
"""

# Time constants (in seconds)
PERIOD_TIME_MAX_REG = 20 * 60  # 20:00 regulation period
PERIOD_TIME_MAX_OT_REG = 5 * 60  # 5:00 regular season OT
PERIOD_TIME_MAX_OT_PLAYOFF = 20 * 60  # 20:00 playoff OT

# Tolerances for floating-point comparisons
TOI_TOLERANCE_SECONDS = 5  # Allow 5 second difference in TOI comparisons
PERCENTAGE_TOLERANCE = 0.01  # 1% tolerance for percentage calculations

# Coordinate ranges for rink positions
COORD_X_MIN = -100.0
COORD_X_MAX = 100.0
COORD_Y_MIN = -42.5
COORD_Y_MAX = 42.5

# Period constraints
PERIOD_MIN = 1
PERIOD_MAX_REG = 3  # Regulation periods
PERIOD_OT = 4  # Overtime period (regular season)
PERIOD_SO = 5  # Shootout "period"
PERIOD_MAX_PLAYOFF = 10  # Theoretically unlimited but cap at 10 OT

# Game type codes
GAME_TYPE_REGULAR = 2
GAME_TYPE_PLAYOFF = 3

# Player constraints
MAX_ASSISTS_PER_GOAL = 2
MAX_PLAYERS_ON_ICE = 6  # Excluding goalie pull situations

# Percentage ranges
PCT_MIN = 0.0
PCT_MAX_100 = 100.0  # For percentages stored as 0-100
PCT_MAX_1 = 1.0  # For percentages stored as 0-1 (save_pct)

# Source type identifiers
SOURCE_BOXSCORE = "boxscore"
SOURCE_PBP = "play_by_play"
SOURCE_SHIFTS = "shift_chart"
SOURCE_STANDINGS = "standings"
SOURCE_HTML_ES = "html_event_summary"
SOURCE_HTML_GS = "html_game_summary"
SOURCE_HTML_FS = "html_faceoff_summary"
SOURCE_HTML_SS = "html_shot_summary"
SOURCE_HTML_TOI = "html_time_on_ice"
