"""Data models for NHL Shift Charts.

This module defines dataclass models for player shift data from the
NHL Stats REST API shift charts endpoint.

Example usage:
    # Parse a shift record from API response
    shift = ShiftRecord(
        shift_id=14765329,
        game_id=2024020500,
        player_id=8470613,
        first_name="Brent",
        last_name="Burns",
        team_id=12,
        team_abbrev="CAR",
        period=1,
        shift_number=1,
        start_time="00:28",
        end_time="01:15",
        duration_seconds=47,
        type_code=517,
        is_goal_event=False,
    )

    # Create a parsed shift chart
    chart = ParsedShiftChart(
        game_id=2024020500,
        season_id=20242025,
        total_shifts=756,
        shifts=[shift, ...],
    )

    # Get player's total TOI
    player_toi = chart.get_player_toi(8470613)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Type codes from NHL Stats API
SHIFT_TYPE_CODE = 517  # Regular shift
GOAL_TYPE_CODE = 505  # Goal event

# Detail codes
DETAIL_SHIFT = 0  # Regular shift
DETAIL_GOAL_EV = 803  # Even-strength goal
DETAIL_GOAL_PP = 808  # Power-play goal


@dataclass(frozen=True, slots=True)
class ShiftRecord:
    """Individual player shift record.

    Represents a single shift from the NHL Stats API shift charts endpoint.
    Frozen and slotted for memory efficiency when storing many shifts.

    Attributes:
        shift_id: Unique shift identifier from API
        game_id: NHL game ID
        player_id: NHL player ID
        first_name: Player's first name
        last_name: Player's last name
        team_id: Team ID
        team_abbrev: Team abbreviation (e.g., "CAR")
        period: Game period (1, 2, 3, 4 for OT)
        shift_number: Sequential shift count for this player in the game
        start_time: Shift start time in "MM:SS" format (game clock)
        end_time: Shift end time in "MM:SS" format (game clock)
        duration_seconds: Shift duration in seconds (computed from MM:SS)
        type_code: Record type (517=shift, 505=goal event)
        is_goal_event: True if this is a goal event (type_code=505)
        event_description: Goal type if goal event ("EVG", "PPG", etc.)
        event_details: Scorer/assist info if goal event
        detail_code: Event detail code (0=shift, 803/808=goal types)
        hex_value: Team color hex code (e.g., "#C8102E")
    """

    shift_id: int
    game_id: int
    player_id: int
    first_name: str
    last_name: str
    team_id: int
    team_abbrev: str
    period: int
    shift_number: int
    start_time: str
    end_time: str
    duration_seconds: int
    type_code: int = SHIFT_TYPE_CODE
    is_goal_event: bool = False
    event_description: str | None = None
    event_details: str | None = None
    detail_code: int = DETAIL_SHIFT
    hex_value: str | None = None

    @property
    def full_name(self) -> str:
        """Player's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def duration_display(self) -> str:
        """Duration in MM:SS format."""
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


@dataclass
class ParsedShiftChart:
    """All shifts for a single game.

    Container for all shift records from a game, with helper methods
    for filtering and aggregating shift data.

    Attributes:
        game_id: NHL game ID
        season_id: Season ID in YYYYYYYY format (e.g., 20242025)
        total_shifts: Total number of shift records returned by API
        home_team_id: Home team ID (extracted from shifts)
        away_team_id: Away team ID (extracted from shifts)
        shifts: List of all ShiftRecord objects
    """

    game_id: int
    season_id: int
    total_shifts: int
    home_team_id: int | None = None
    away_team_id: int | None = None
    shifts: list[ShiftRecord] = field(default_factory=list)

    def get_player_shifts(self, player_id: int) -> list[ShiftRecord]:
        """Get all shifts for a specific player.

        Args:
            player_id: NHL player ID

        Returns:
            List of shifts for the player
        """
        return [s for s in self.shifts if s.player_id == player_id]

    def get_period_shifts(self, period: int) -> list[ShiftRecord]:
        """Get all shifts for a specific period.

        Args:
            period: Game period (1, 2, 3, 4 for OT)

        Returns:
            List of shifts in the period
        """
        return [s for s in self.shifts if s.period == period]

    def get_team_shifts(self, team_id: int) -> list[ShiftRecord]:
        """Get all shifts for a specific team.

        Args:
            team_id: NHL team ID

        Returns:
            List of shifts for the team
        """
        return [s for s in self.shifts if s.team_id == team_id]

    def get_player_toi(self, player_id: int) -> int:
        """Calculate total time on ice for a player.

        Args:
            player_id: NHL player ID

        Returns:
            Total TOI in seconds
        """
        return sum(
            s.duration_seconds
            for s in self.shifts
            if s.player_id == player_id and not s.is_goal_event
        )

    def get_player_toi_by_period(self, player_id: int) -> dict[int, int]:
        """Calculate TOI by period for a player.

        Args:
            player_id: NHL player ID

        Returns:
            Dict mapping period number to TOI in seconds
        """
        toi_by_period: dict[int, int] = {}
        for shift in self.shifts:
            if shift.player_id == player_id and not shift.is_goal_event:
                toi_by_period[shift.period] = (
                    toi_by_period.get(shift.period, 0) + shift.duration_seconds
                )
        return toi_by_period

    def get_player_shift_count(self, player_id: int) -> int:
        """Get number of shifts for a player.

        Args:
            player_id: NHL player ID

        Returns:
            Number of shifts (excluding goal events)
        """
        return sum(
            1 for s in self.shifts if s.player_id == player_id and not s.is_goal_event
        )

    def get_all_player_ids(self) -> set[int]:
        """Get all unique player IDs in the shift chart.

        Returns:
            Set of player IDs
        """
        return {s.player_id for s in self.shifts}

    def get_team_player_ids(self, team_id: int) -> set[int]:
        """Get all player IDs for a team.

        Args:
            team_id: NHL team ID

        Returns:
            Set of player IDs for the team
        """
        return {s.player_id for s in self.shifts if s.team_id == team_id}

    def get_goal_events(self) -> list[ShiftRecord]:
        """Get all goal event records.

        Returns:
            List of goal event ShiftRecords
        """
        return [s for s in self.shifts if s.is_goal_event]

    @property
    def shift_count(self) -> int:
        """Total number of shifts (excluding goal events)."""
        return sum(1 for s in self.shifts if not s.is_goal_event)

    @property
    def goal_count(self) -> int:
        """Total number of goal events."""
        return sum(1 for s in self.shifts if s.is_goal_event)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "game_id": self.game_id,
            "season_id": self.season_id,
            "total_shifts": self.total_shifts,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "shifts": [_shift_to_dict(s) for s in self.shifts],
        }


def _shift_to_dict(shift: ShiftRecord) -> dict[str, Any]:
    """Convert a ShiftRecord to dictionary.

    Args:
        shift: ShiftRecord to convert

    Returns:
        Dictionary representation
    """
    return {
        "shift_id": shift.shift_id,
        "game_id": shift.game_id,
        "player_id": shift.player_id,
        "first_name": shift.first_name,
        "last_name": shift.last_name,
        "team_id": shift.team_id,
        "team_abbrev": shift.team_abbrev,
        "period": shift.period,
        "shift_number": shift.shift_number,
        "start_time": shift.start_time,
        "end_time": shift.end_time,
        "duration_seconds": shift.duration_seconds,
        "type_code": shift.type_code,
        "is_goal_event": shift.is_goal_event,
        "event_description": shift.event_description,
        "event_details": shift.event_details,
        "detail_code": shift.detail_code,
        "hex_value": shift.hex_value,
    }


def parse_duration(duration_str: str | None) -> int:
    """Parse duration string to seconds.

    Args:
        duration_str: Duration in "MM:SS" format, or None

    Returns:
        Duration in seconds, or 0 if None/invalid

    Example:
        >>> parse_duration("00:47")
        47
        >>> parse_duration("01:15")
        75
        >>> parse_duration(None)
        0
    """
    if not duration_str:
        return 0

    try:
        parts = duration_str.split(":")
        if len(parts) != 2:
            return 0
        minutes = int(parts[0])
        seconds = int(parts[1])
        return minutes * 60 + seconds
    except (ValueError, AttributeError):
        return 0
