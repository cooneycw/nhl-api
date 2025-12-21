"""Data models for QuantHockey player statistics.

This module provides dataclasses for the 51-field player statistics available
from quanthockey.com. The data includes comprehensive NHL player statistics
covering scoring, time on ice, situational performance, and physical play.

QuantHockey provides:
- Season-by-season player statistics
- All-time career statistics
- Advanced per-60 minute rates
- Situational breakdowns (ES, PP, SH)

Example usage:
    # Parse player stats from QuantHockey data
    stats = QuantHockeyPlayerSeasonStats.from_row_data(
        row_data=["1", "Connor McDavid", "EDM", "28", "C", ...],
        season_id=20242025,
    )

    # Access computed properties
    print(f"{stats.name}: {stats.points} points ({stats.points_per_game:.2f} P/GP)")

Note:
    Field values may be None for players with limited data or for
    fields that don't apply (e.g., faceoff stats for defensemen).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# Validation Utilities
# =============================================================================


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer.

    Args:
        value: Value to convert (str, int, float, or None)
        default: Default value if conversion fails

    Returns:
        Integer value or default
    """
    if value is None:
        return default
    try:
        # Handle string values with commas (e.g., "1,234")
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if value == "" or value == "-":
                return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float.

    Args:
        value: Value to convert (str, int, float, or None)
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
            if value == "" or value == "-":
                return default
        return float(value)
    except (ValueError, TypeError):
        return default


def _validate_percentage(value: float, field_name: str) -> float:
    """Validate that a percentage is within valid range.

    Args:
        value: Percentage value to validate
        field_name: Name of field for error messages

    Returns:
        Validated percentage value

    Raises:
        ValueError: If percentage is out of valid range [0, 100]
    """
    if value < 0 or value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100, got {value}")
    return value


def _validate_non_negative(value: int | float, field_name: str) -> int | float:
    """Validate that a value is non-negative.

    Args:
        value: Value to validate
        field_name: Name of field for error messages

    Returns:
        Validated value

    Raises:
        ValueError: If value is negative
    """
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative, got {value}")
    return value


# =============================================================================
# Player Season Statistics
# =============================================================================


@dataclass(frozen=True, slots=True)
class QuantHockeyPlayerSeasonStats:
    """51-field player statistics from QuantHockey for a single season.

    This dataclass represents the comprehensive statistics available from
    QuantHockey's season player pages. All counting stats are integers,
    rates are floats, and percentages are stored as 0-100 values.

    Attributes are grouped by category:
    - Core: Identity and basic stats (11 fields)
    - TOI: Time on ice breakdowns (4 fields)
    - Goals: Situational goal breakdowns (5 fields)
    - Assists: Situational assist breakdowns (5 fields)
    - Points: Situational point breakdowns (6 fields)
    - Per60: Per-60-minute rates (9 fields)
    - PerGame: Per-game rates (3 fields)
    - Shooting: Shot statistics (2 fields)
    - Physical: Physical play stats (2 fields)
    - Faceoffs: Faceoff statistics (3 fields)
    - Metadata: Additional fields (1 field)
    """

    # =========================================================================
    # Metadata
    # =========================================================================
    season_id: int  # NHL season ID (e.g., 20242025)

    # =========================================================================
    # Core Identity (11 fields)
    # =========================================================================
    rank: int  # Ranking in scoring leaders
    name: str  # Player full name
    team: str  # Team abbreviation (e.g., "EDM")
    age: int  # Player age during season
    position: str  # Position code (C, LW, RW, D, G)
    games_played: int  # GP
    goals: int  # G
    assists: int  # A
    points: int  # P
    pim: int  # Penalty minutes
    plus_minus: int  # +/-

    # =========================================================================
    # Time on Ice (4 fields) - in minutes per game
    # =========================================================================
    toi_avg: float  # Average TOI per game
    toi_es: float  # Even-strength TOI per game
    toi_pp: float  # Power-play TOI per game
    toi_sh: float  # Short-handed TOI per game

    # =========================================================================
    # Goal Breakdowns (5 fields)
    # =========================================================================
    es_goals: int  # Even-strength goals
    pp_goals: int  # Power-play goals
    sh_goals: int  # Short-handed goals
    gw_goals: int  # Game-winning goals
    ot_goals: int  # Overtime goals

    # =========================================================================
    # Assist Breakdowns (5 fields)
    # =========================================================================
    es_assists: int  # Even-strength assists
    pp_assists: int  # Power-play assists
    sh_assists: int  # Short-handed assists
    gw_assists: int  # Game-winning assists
    ot_assists: int  # Overtime assists

    # =========================================================================
    # Point Breakdowns (6 fields)
    # =========================================================================
    es_points: int  # Even-strength points
    pp_points: int  # Power-play points
    sh_points: int  # Short-handed points
    gw_points: int  # Game-winning points
    ot_points: int  # Overtime points
    ppp_pct: float  # Power-play points percentage (0-100)

    # =========================================================================
    # Per-60 Rates - All Situations (3 fields)
    # =========================================================================
    goals_per_60: float  # Goals per 60 minutes
    assists_per_60: float  # Assists per 60 minutes
    points_per_60: float  # Points per 60 minutes

    # =========================================================================
    # Per-60 Rates - Even-Strength (3 fields)
    # =========================================================================
    es_goals_per_60: float  # ES goals per 60 minutes
    es_assists_per_60: float  # ES assists per 60 minutes
    es_points_per_60: float  # ES points per 60 minutes

    # =========================================================================
    # Per-60 Rates - Power-Play (3 fields)
    # =========================================================================
    pp_goals_per_60: float  # PP goals per 60 minutes
    pp_assists_per_60: float  # PP assists per 60 minutes
    pp_points_per_60: float  # PP points per 60 minutes

    # =========================================================================
    # Per-Game Rates (3 fields)
    # =========================================================================
    goals_per_game: float  # Goals per game
    assists_per_game: float  # Assists per game
    points_per_game: float  # Points per game

    # =========================================================================
    # Shooting Statistics (2 fields)
    # =========================================================================
    shots_on_goal: int  # Total shots on goal
    shooting_pct: float  # Shooting percentage (0-100)

    # =========================================================================
    # Physical Play (2 fields)
    # =========================================================================
    hits: int  # Total hits
    blocked_shots: int  # Total blocked shots

    # =========================================================================
    # Faceoff Statistics (3 fields)
    # =========================================================================
    faceoffs_won: int  # Total faceoffs won
    faceoffs_lost: int  # Total faceoffs lost
    faceoff_pct: float  # Faceoff win percentage (0-100)

    # =========================================================================
    # Additional Metadata (1 field)
    # =========================================================================
    nationality: str = ""  # Country code (optional)

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def from_row_data(
        cls,
        row_data: list[str],
        season_id: int,
        *,
        validate: bool = True,
    ) -> QuantHockeyPlayerSeasonStats:
        """Create instance from QuantHockey HTML table row data.

        Args:
            row_data: List of string values from HTML table row (51 elements)
            season_id: NHL season ID (e.g., 20242025)
            validate: Whether to validate field values

        Returns:
            QuantHockeyPlayerSeasonStats instance

        Raises:
            ValueError: If row_data has wrong length or validation fails
        """
        if len(row_data) < 50:  # Allow flexibility for optional nationality
            raise ValueError(f"Expected at least 50 fields, got {len(row_data)}")

        # Parse all fields with safe conversions
        stats = cls(
            season_id=season_id,
            # Core (11)
            rank=_safe_int(row_data[0]),
            name=row_data[1].strip(),
            team=row_data[2].strip().upper(),
            age=_safe_int(row_data[3]),
            position=row_data[4].strip().upper(),
            games_played=_safe_int(row_data[5]),
            goals=_safe_int(row_data[6]),
            assists=_safe_int(row_data[7]),
            points=_safe_int(row_data[8]),
            pim=_safe_int(row_data[9]),
            plus_minus=_safe_int(row_data[10]),
            # TOI (4)
            toi_avg=_safe_float(row_data[11]),
            toi_es=_safe_float(row_data[12]),
            toi_pp=_safe_float(row_data[13]),
            toi_sh=_safe_float(row_data[14]),
            # Goals breakdown (5)
            es_goals=_safe_int(row_data[15]),
            pp_goals=_safe_int(row_data[16]),
            sh_goals=_safe_int(row_data[17]),
            gw_goals=_safe_int(row_data[18]),
            ot_goals=_safe_int(row_data[19]),
            # Assists breakdown (5)
            es_assists=_safe_int(row_data[20]),
            pp_assists=_safe_int(row_data[21]),
            sh_assists=_safe_int(row_data[22]),
            gw_assists=_safe_int(row_data[23]),
            ot_assists=_safe_int(row_data[24]),
            # Points breakdown (6)
            es_points=_safe_int(row_data[25]),
            pp_points=_safe_int(row_data[26]),
            sh_points=_safe_int(row_data[27]),
            gw_points=_safe_int(row_data[28]),
            ot_points=_safe_int(row_data[29]),
            ppp_pct=_safe_float(row_data[30]),
            # Per-60 all situations (3)
            goals_per_60=_safe_float(row_data[31]),
            assists_per_60=_safe_float(row_data[32]),
            points_per_60=_safe_float(row_data[33]),
            # Per-60 even-strength (3)
            es_goals_per_60=_safe_float(row_data[34]),
            es_assists_per_60=_safe_float(row_data[35]),
            es_points_per_60=_safe_float(row_data[36]),
            # Per-60 power-play (3)
            pp_goals_per_60=_safe_float(row_data[37]),
            pp_assists_per_60=_safe_float(row_data[38]),
            pp_points_per_60=_safe_float(row_data[39]),
            # Per-game (3)
            goals_per_game=_safe_float(row_data[40]),
            assists_per_game=_safe_float(row_data[41]),
            points_per_game=_safe_float(row_data[42]),
            # Shooting (2)
            shots_on_goal=_safe_int(row_data[43]),
            shooting_pct=_safe_float(row_data[44]),
            # Physical (2)
            hits=_safe_int(row_data[45]),
            blocked_shots=_safe_int(row_data[46]),
            # Faceoffs (3)
            faceoffs_won=_safe_int(row_data[47]),
            faceoffs_lost=_safe_int(row_data[48]),
            faceoff_pct=_safe_float(row_data[49]),
            # Nationality (optional)
            nationality=row_data[50].strip() if len(row_data) > 50 else "",
        )

        if validate:
            stats.validate()

        return stats

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        validate: bool = True,
    ) -> QuantHockeyPlayerSeasonStats:
        """Create instance from dictionary.

        Args:
            data: Dictionary with field names as keys
            validate: Whether to validate field values

        Returns:
            QuantHockeyPlayerSeasonStats instance
        """
        stats = cls(
            season_id=_safe_int(data.get("season_id", 0)),
            rank=_safe_int(data.get("rank", 0)),
            name=str(data.get("name", "")),
            team=str(data.get("team", "")),
            age=_safe_int(data.get("age", 0)),
            position=str(data.get("position", "")),
            games_played=_safe_int(data.get("games_played", 0)),
            goals=_safe_int(data.get("goals", 0)),
            assists=_safe_int(data.get("assists", 0)),
            points=_safe_int(data.get("points", 0)),
            pim=_safe_int(data.get("pim", 0)),
            plus_minus=_safe_int(data.get("plus_minus", 0)),
            toi_avg=_safe_float(data.get("toi_avg", 0.0)),
            toi_es=_safe_float(data.get("toi_es", 0.0)),
            toi_pp=_safe_float(data.get("toi_pp", 0.0)),
            toi_sh=_safe_float(data.get("toi_sh", 0.0)),
            es_goals=_safe_int(data.get("es_goals", 0)),
            pp_goals=_safe_int(data.get("pp_goals", 0)),
            sh_goals=_safe_int(data.get("sh_goals", 0)),
            gw_goals=_safe_int(data.get("gw_goals", 0)),
            ot_goals=_safe_int(data.get("ot_goals", 0)),
            es_assists=_safe_int(data.get("es_assists", 0)),
            pp_assists=_safe_int(data.get("pp_assists", 0)),
            sh_assists=_safe_int(data.get("sh_assists", 0)),
            gw_assists=_safe_int(data.get("gw_assists", 0)),
            ot_assists=_safe_int(data.get("ot_assists", 0)),
            es_points=_safe_int(data.get("es_points", 0)),
            pp_points=_safe_int(data.get("pp_points", 0)),
            sh_points=_safe_int(data.get("sh_points", 0)),
            gw_points=_safe_int(data.get("gw_points", 0)),
            ot_points=_safe_int(data.get("ot_points", 0)),
            ppp_pct=_safe_float(data.get("ppp_pct", 0.0)),
            goals_per_60=_safe_float(data.get("goals_per_60", 0.0)),
            assists_per_60=_safe_float(data.get("assists_per_60", 0.0)),
            points_per_60=_safe_float(data.get("points_per_60", 0.0)),
            es_goals_per_60=_safe_float(data.get("es_goals_per_60", 0.0)),
            es_assists_per_60=_safe_float(data.get("es_assists_per_60", 0.0)),
            es_points_per_60=_safe_float(data.get("es_points_per_60", 0.0)),
            pp_goals_per_60=_safe_float(data.get("pp_goals_per_60", 0.0)),
            pp_assists_per_60=_safe_float(data.get("pp_assists_per_60", 0.0)),
            pp_points_per_60=_safe_float(data.get("pp_points_per_60", 0.0)),
            goals_per_game=_safe_float(data.get("goals_per_game", 0.0)),
            assists_per_game=_safe_float(data.get("assists_per_game", 0.0)),
            points_per_game=_safe_float(data.get("points_per_game", 0.0)),
            shots_on_goal=_safe_int(data.get("shots_on_goal", 0)),
            shooting_pct=_safe_float(data.get("shooting_pct", 0.0)),
            hits=_safe_int(data.get("hits", 0)),
            blocked_shots=_safe_int(data.get("blocked_shots", 0)),
            faceoffs_won=_safe_int(data.get("faceoffs_won", 0)),
            faceoffs_lost=_safe_int(data.get("faceoffs_lost", 0)),
            faceoff_pct=_safe_float(data.get("faceoff_pct", 0.0)),
            nationality=str(data.get("nationality", "")),
        )

        if validate:
            stats.validate()

        return stats

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """Validate all field values.

        Raises:
            ValueError: If any field has an invalid value
        """
        # Validate non-negative counting stats
        for field_name in [
            "rank",
            "age",
            "games_played",
            "goals",
            "assists",
            "points",
            "pim",
            "es_goals",
            "pp_goals",
            "sh_goals",
            "gw_goals",
            "ot_goals",
            "es_assists",
            "pp_assists",
            "sh_assists",
            "gw_assists",
            "ot_assists",
            "es_points",
            "pp_points",
            "sh_points",
            "gw_points",
            "ot_points",
            "shots_on_goal",
            "hits",
            "blocked_shots",
            "faceoffs_won",
            "faceoffs_lost",
        ]:
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative, got {value}")

        # Validate percentages (0-100)
        for field_name in ["ppp_pct", "shooting_pct", "faceoff_pct"]:
            value = getattr(self, field_name)
            if value < 0 or value > 100:
                raise ValueError(f"{field_name} must be between 0 and 100, got {value}")

        # Validate non-negative rates
        for field_name in [
            "toi_avg",
            "toi_es",
            "toi_pp",
            "toi_sh",
            "goals_per_60",
            "assists_per_60",
            "points_per_60",
            "es_goals_per_60",
            "es_assists_per_60",
            "es_points_per_60",
            "pp_goals_per_60",
            "pp_assists_per_60",
            "pp_points_per_60",
            "goals_per_game",
            "assists_per_game",
            "points_per_game",
        ]:
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative, got {value}")

        # Validate required strings
        if not self.name:
            raise ValueError("name cannot be empty")

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def total_faceoffs(self) -> int:
        """Total faceoffs taken."""
        return self.faceoffs_won + self.faceoffs_lost

    @property
    def is_forward(self) -> bool:
        """True if player is a forward (C, LW, RW)."""
        return self.position in ("C", "LW", "RW", "F")

    @property
    def is_defenseman(self) -> bool:
        """True if player is a defenseman."""
        return self.position == "D"

    @property
    def is_goalie(self) -> bool:
        """True if player is a goalie."""
        return self.position == "G"

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary with all fields
        """
        return {
            "season_id": self.season_id,
            "rank": self.rank,
            "name": self.name,
            "team": self.team,
            "age": self.age,
            "position": self.position,
            "games_played": self.games_played,
            "goals": self.goals,
            "assists": self.assists,
            "points": self.points,
            "pim": self.pim,
            "plus_minus": self.plus_minus,
            "toi_avg": self.toi_avg,
            "toi_es": self.toi_es,
            "toi_pp": self.toi_pp,
            "toi_sh": self.toi_sh,
            "es_goals": self.es_goals,
            "pp_goals": self.pp_goals,
            "sh_goals": self.sh_goals,
            "gw_goals": self.gw_goals,
            "ot_goals": self.ot_goals,
            "es_assists": self.es_assists,
            "pp_assists": self.pp_assists,
            "sh_assists": self.sh_assists,
            "gw_assists": self.gw_assists,
            "ot_assists": self.ot_assists,
            "es_points": self.es_points,
            "pp_points": self.pp_points,
            "sh_points": self.sh_points,
            "gw_points": self.gw_points,
            "ot_points": self.ot_points,
            "ppp_pct": self.ppp_pct,
            "goals_per_60": self.goals_per_60,
            "assists_per_60": self.assists_per_60,
            "points_per_60": self.points_per_60,
            "es_goals_per_60": self.es_goals_per_60,
            "es_assists_per_60": self.es_assists_per_60,
            "es_points_per_60": self.es_points_per_60,
            "pp_goals_per_60": self.pp_goals_per_60,
            "pp_assists_per_60": self.pp_assists_per_60,
            "pp_points_per_60": self.pp_points_per_60,
            "goals_per_game": self.goals_per_game,
            "assists_per_game": self.assists_per_game,
            "points_per_game": self.points_per_game,
            "shots_on_goal": self.shots_on_goal,
            "shooting_pct": self.shooting_pct,
            "hits": self.hits,
            "blocked_shots": self.blocked_shots,
            "faceoffs_won": self.faceoffs_won,
            "faceoffs_lost": self.faceoffs_lost,
            "faceoff_pct": self.faceoff_pct,
            "nationality": self.nationality,
        }


# =============================================================================
# Player Career Statistics
# =============================================================================


@dataclass(frozen=True, slots=True)
class QuantHockeyPlayerCareerStats:
    """Career (all-time) statistics from QuantHockey.

    Similar to QuantHockeyPlayerSeasonStats but represents accumulated
    statistics across a player's entire NHL career. Career stats don't
    include per-60 or per-game rates (these would be calculated from totals).

    This is used for the all-time leaders pages.
    """

    # =========================================================================
    # Identity
    # =========================================================================
    name: str  # Player full name
    position: str  # Primary position
    nationality: str  # Country code

    # =========================================================================
    # Career Span
    # =========================================================================
    first_season: int  # First NHL season (e.g., 2005)
    last_season: int  # Last NHL season (e.g., 2024)
    seasons_played: int  # Total seasons

    # =========================================================================
    # Core Career Stats
    # =========================================================================
    games_played: int  # Career GP
    goals: int  # Career G
    assists: int  # Career A
    points: int  # Career P
    pim: int  # Career PIM
    plus_minus: int  # Career +/-

    # =========================================================================
    # Situational Goals
    # =========================================================================
    es_goals: int = 0
    pp_goals: int = 0
    sh_goals: int = 0
    gw_goals: int = 0
    ot_goals: int = 0

    # =========================================================================
    # Situational Assists
    # =========================================================================
    es_assists: int = 0
    pp_assists: int = 0
    sh_assists: int = 0
    gw_assists: int = 0
    ot_assists: int = 0

    # =========================================================================
    # Other Stats
    # =========================================================================
    shots_on_goal: int = 0
    shooting_pct: float = 0.0
    hits: int = 0
    blocked_shots: int = 0
    faceoffs_won: int = 0
    faceoffs_lost: int = 0
    faceoff_pct: float = 0.0

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def from_row_data(
        cls,
        row_data: list[str],
        *,
        validate: bool = True,
    ) -> QuantHockeyPlayerCareerStats:
        """Create instance from QuantHockey all-time leaders table row.

        Args:
            row_data: List of string values from HTML table row
            validate: Whether to validate field values

        Returns:
            QuantHockeyPlayerCareerStats instance
        """
        # Career tables have different column layout than season tables
        # Adapt parsing based on actual QuantHockey career table structure
        stats = cls(
            name=row_data[1].strip() if len(row_data) > 1 else "",
            position=row_data[2].strip().upper() if len(row_data) > 2 else "",
            nationality=row_data[3].strip() if len(row_data) > 3 else "",
            first_season=_safe_int(row_data[4]) if len(row_data) > 4 else 0,
            last_season=_safe_int(row_data[5]) if len(row_data) > 5 else 0,
            seasons_played=_safe_int(row_data[6]) if len(row_data) > 6 else 0,
            games_played=_safe_int(row_data[7]) if len(row_data) > 7 else 0,
            goals=_safe_int(row_data[8]) if len(row_data) > 8 else 0,
            assists=_safe_int(row_data[9]) if len(row_data) > 9 else 0,
            points=_safe_int(row_data[10]) if len(row_data) > 10 else 0,
            pim=_safe_int(row_data[11]) if len(row_data) > 11 else 0,
            plus_minus=_safe_int(row_data[12]) if len(row_data) > 12 else 0,
        )

        if validate:
            stats.validate()

        return stats

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        validate: bool = True,
    ) -> QuantHockeyPlayerCareerStats:
        """Create instance from dictionary.

        Args:
            data: Dictionary with field names as keys
            validate: Whether to validate field values

        Returns:
            QuantHockeyPlayerCareerStats instance
        """
        stats = cls(
            name=str(data.get("name", "")),
            position=str(data.get("position", "")),
            nationality=str(data.get("nationality", "")),
            first_season=_safe_int(data.get("first_season", 0)),
            last_season=_safe_int(data.get("last_season", 0)),
            seasons_played=_safe_int(data.get("seasons_played", 0)),
            games_played=_safe_int(data.get("games_played", 0)),
            goals=_safe_int(data.get("goals", 0)),
            assists=_safe_int(data.get("assists", 0)),
            points=_safe_int(data.get("points", 0)),
            pim=_safe_int(data.get("pim", 0)),
            plus_minus=_safe_int(data.get("plus_minus", 0)),
            es_goals=_safe_int(data.get("es_goals", 0)),
            pp_goals=_safe_int(data.get("pp_goals", 0)),
            sh_goals=_safe_int(data.get("sh_goals", 0)),
            gw_goals=_safe_int(data.get("gw_goals", 0)),
            ot_goals=_safe_int(data.get("ot_goals", 0)),
            es_assists=_safe_int(data.get("es_assists", 0)),
            pp_assists=_safe_int(data.get("pp_assists", 0)),
            sh_assists=_safe_int(data.get("sh_assists", 0)),
            gw_assists=_safe_int(data.get("gw_assists", 0)),
            ot_assists=_safe_int(data.get("ot_assists", 0)),
            shots_on_goal=_safe_int(data.get("shots_on_goal", 0)),
            shooting_pct=_safe_float(data.get("shooting_pct", 0.0)),
            hits=_safe_int(data.get("hits", 0)),
            blocked_shots=_safe_int(data.get("blocked_shots", 0)),
            faceoffs_won=_safe_int(data.get("faceoffs_won", 0)),
            faceoffs_lost=_safe_int(data.get("faceoffs_lost", 0)),
            faceoff_pct=_safe_float(data.get("faceoff_pct", 0.0)),
        )

        if validate:
            stats.validate()

        return stats

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """Validate all field values.

        Raises:
            ValueError: If any field has an invalid value
        """
        if not self.name:
            raise ValueError("name cannot be empty")

        # Validate non-negative counting stats
        for field_name in [
            "games_played",
            "goals",
            "assists",
            "points",
            "pim",
            "seasons_played",
            "es_goals",
            "pp_goals",
            "sh_goals",
            "gw_goals",
            "ot_goals",
            "es_assists",
            "pp_assists",
            "sh_assists",
            "gw_assists",
            "ot_assists",
            "shots_on_goal",
            "hits",
            "blocked_shots",
            "faceoffs_won",
            "faceoffs_lost",
        ]:
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative, got {value}")

        # Validate percentages
        for field_name in ["shooting_pct", "faceoff_pct"]:
            value = getattr(self, field_name)
            if value < 0 or value > 100:
                raise ValueError(f"{field_name} must be between 0 and 100, got {value}")

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def career_span(self) -> str:
        """Career span as string (e.g., '2005-2024')."""
        if self.first_season and self.last_season:
            return f"{self.first_season}-{self.last_season}"
        return ""

    @property
    def goals_per_game(self) -> float:
        """Career goals per game."""
        if self.games_played > 0:
            return self.goals / self.games_played
        return 0.0

    @property
    def assists_per_game(self) -> float:
        """Career assists per game."""
        if self.games_played > 0:
            return self.assists / self.games_played
        return 0.0

    @property
    def points_per_game(self) -> float:
        """Career points per game."""
        if self.games_played > 0:
            return self.points / self.games_played
        return 0.0

    @property
    def total_faceoffs(self) -> int:
        """Total career faceoffs taken."""
        return self.faceoffs_won + self.faceoffs_lost

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary with all fields
        """
        return {
            "name": self.name,
            "position": self.position,
            "nationality": self.nationality,
            "first_season": self.first_season,
            "last_season": self.last_season,
            "seasons_played": self.seasons_played,
            "games_played": self.games_played,
            "goals": self.goals,
            "assists": self.assists,
            "points": self.points,
            "pim": self.pim,
            "plus_minus": self.plus_minus,
            "es_goals": self.es_goals,
            "pp_goals": self.pp_goals,
            "sh_goals": self.sh_goals,
            "gw_goals": self.gw_goals,
            "ot_goals": self.ot_goals,
            "es_assists": self.es_assists,
            "pp_assists": self.pp_assists,
            "sh_assists": self.sh_assists,
            "gw_assists": self.gw_assists,
            "ot_assists": self.ot_assists,
            "shots_on_goal": self.shots_on_goal,
            "shooting_pct": self.shooting_pct,
            "hits": self.hits,
            "blocked_shots": self.blocked_shots,
            "faceoffs_won": self.faceoffs_won,
            "faceoffs_lost": self.faceoffs_lost,
            "faceoff_pct": self.faceoff_pct,
        }


# =============================================================================
# Season Container
# =============================================================================


@dataclass
class QuantHockeySeasonData:
    """Container for all player statistics from a single season.

    This class holds the complete dataset from a QuantHockey season page,
    including metadata and the list of all player statistics.

    Attributes:
        season_id: NHL season ID (e.g., 20242025)
        season_name: Human-readable season name (e.g., "2024-25")
        players: List of player statistics
        download_timestamp: When the data was fetched
    """

    season_id: int
    season_name: str
    players: list[QuantHockeyPlayerSeasonStats] = field(default_factory=list)
    download_timestamp: str = ""

    @property
    def player_count(self) -> int:
        """Number of players in the dataset."""
        return len(self.players)

    def get_player(self, name: str) -> QuantHockeyPlayerSeasonStats | None:
        """Find a player by name (case-insensitive partial match).

        Args:
            name: Player name to search for

        Returns:
            First matching player or None
        """
        name_lower = name.lower()
        for player in self.players:
            if name_lower in player.name.lower():
                return player
        return None

    def get_team_players(self, team: str) -> list[QuantHockeyPlayerSeasonStats]:
        """Get all players for a specific team.

        Args:
            team: Team abbreviation (e.g., "EDM")

        Returns:
            List of players on the team
        """
        team_upper = team.upper()
        return [p for p in self.players if p.team == team_upper]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "season_id": self.season_id,
            "season_name": self.season_name,
            "player_count": self.player_count,
            "download_timestamp": self.download_timestamp,
            "players": [p.to_dict() for p in self.players],
        }
