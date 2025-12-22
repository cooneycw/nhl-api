"""Pydantic schemas for entity API endpoints.

Defines request/response models for players, teams, and games.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

# =============================================================================
# Pagination
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=100, description="Items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")


# =============================================================================
# Players
# =============================================================================


class PlayerSummary(BaseModel):
    """Player summary for list views."""

    player_id: int
    first_name: str
    last_name: str
    full_name: str
    age: int | None = None
    primary_position: str | None = None
    position_type: Literal["F", "D", "G"] | None = None
    current_team_id: int | None = None
    team_name: str | None = None
    team_abbreviation: str | None = None
    sweater_number: int | None = None
    headshot_url: str | None = None
    active: bool = True


class PlayerDetail(BaseModel):
    """Detailed player information."""

    player_id: int
    first_name: str
    last_name: str
    full_name: str
    birth_date: date | None = None
    age: int | None = None
    birth_country: str | None = None
    nationality: str | None = None
    height_inches: int | None = None
    height_display: str | None = None
    weight_lbs: int | None = None
    shoots_catches: str | None = None
    primary_position: str | None = None
    position_type: Literal["F", "D", "G"] | None = None
    roster_status: str | None = None
    current_team_id: int | None = None
    team_name: str | None = None
    team_abbreviation: str | None = None
    division_name: str | None = None
    conference_name: str | None = None
    captain: bool = False
    alternate_captain: bool = False
    rookie: bool = False
    nhl_experience: int | None = None
    sweater_number: int | None = None
    headshot_url: str | None = None
    active: bool = True
    updated_at: datetime | None = None


class PlayerListResponse(BaseModel):
    """Response for player list endpoint."""

    players: list[PlayerSummary]
    pagination: PaginationMeta


# =============================================================================
# Teams
# =============================================================================


class TeamSummary(BaseModel):
    """Team summary for list views."""

    team_id: int
    name: str
    abbreviation: str
    team_name: str | None = None
    location_name: str | None = None
    division_id: int | None = None
    division_name: str | None = None
    conference_id: int | None = None
    conference_name: str | None = None
    active: bool = True


class TeamDetail(BaseModel):
    """Detailed team information."""

    team_id: int
    franchise_id: int | None = None
    name: str
    abbreviation: str
    team_name: str | None = None
    location_name: str | None = None
    division_id: int | None = None
    division_name: str | None = None
    conference_id: int | None = None
    conference_name: str | None = None
    venue_id: int | None = None
    venue_name: str | None = None
    first_year_of_play: int | None = None
    official_site_url: str | None = None
    active: bool = True
    updated_at: datetime | None = None


class TeamWithRoster(BaseModel):
    """Team with roster players."""

    team: TeamDetail
    roster: list[PlayerSummary]


class DivisionTeams(BaseModel):
    """Teams grouped by division."""

    division_id: int
    division_name: str
    conference_name: str | None = None
    teams: list[TeamSummary]


class TeamListResponse(BaseModel):
    """Response for team list endpoint with division grouping."""

    divisions: list[DivisionTeams]
    total_teams: int


# =============================================================================
# Games
# =============================================================================


class GameSummary(BaseModel):
    """Game summary for list views."""

    game_id: int
    season_id: int
    season_name: str | None = None
    game_type: str
    game_type_name: str | None = None
    game_date: date
    game_time: time | str | None = None
    venue_name: str | None = None
    home_team_id: int
    home_team_name: str
    home_team_abbr: str
    home_score: int | None = None
    away_team_id: int
    away_team_name: str
    away_team_abbr: str
    away_score: int | None = None
    game_state: str | None = None
    is_overtime: bool = False
    is_shootout: bool = False
    winner_abbr: str | None = None

    @field_serializer("game_time")
    def serialize_game_time(self, value: time | str | None) -> str | None:
        """Serialize time objects to HH:MM:SS string format."""
        if value is None:
            return None
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        return value


class GameDetail(BaseModel):
    """Detailed game information."""

    game_id: int
    season_id: int
    season_name: str | None = None
    game_type: str
    game_type_name: str | None = None
    game_date: date
    game_time: time | str | None = None
    venue_id: int | None = None
    venue_name: str | None = None
    venue_city: str | None = None
    home_team_id: int
    home_team_name: str
    home_team_abbr: str
    home_score: int | None = None
    away_team_id: int
    away_team_name: str
    away_team_abbr: str
    away_score: int | None = None
    final_period: int | None = None
    game_state: str | None = None
    is_overtime: bool = False
    is_shootout: bool = False
    game_outcome: str | None = None
    winner_team_id: int | None = None
    winner_abbr: str | None = None
    goal_differential: int | None = None
    attendance: int | None = None
    game_duration_minutes: int | None = None
    updated_at: datetime | None = None

    @field_serializer("game_time")
    def serialize_game_time(self, value: time | str | None) -> str | None:
        """Serialize time objects to HH:MM:SS string format."""
        if value is None:
            return None
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        return value


class GameListResponse(BaseModel):
    """Response for game list endpoint."""

    games: list[GameSummary]
    pagination: PaginationMeta


# =============================================================================
# Game Events (Play-by-Play)
# =============================================================================


class PlayByPlayEvent(BaseModel):
    """Individual play-by-play event."""

    event_idx: int
    event_type: str
    period: int
    period_type: str | None = None
    time_in_period: str | None = None
    time_remaining: str | None = None
    description: str | None = None
    player1_id: int | None = None
    player1_name: str | None = None
    player1_role: str | None = None
    player2_id: int | None = None
    player2_name: str | None = None
    player2_role: str | None = None
    player3_id: int | None = None
    player3_name: str | None = None
    player3_role: str | None = None
    team_id: int | None = None
    team_abbr: str | None = None
    home_score: int = 0
    away_score: int = 0
    shot_type: str | None = None
    zone: str | None = None
    x_coord: float | None = None
    y_coord: float | None = None


class GameEventsResponse(BaseModel):
    """Response for game events endpoint."""

    game_id: int
    events: list[PlayByPlayEvent]
    total_events: int


# =============================================================================
# Game Player Statistics
# =============================================================================


class SkaterGameStats(BaseModel):
    """Individual skater statistics for a game."""

    player_id: int
    player_name: str
    team_id: int
    team_abbr: str
    position: str | None = None
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    pim: int = 0
    shots: int = 0
    hits: int = 0
    blocked_shots: int = 0
    giveaways: int = 0
    takeaways: int = 0
    faceoff_pct: float | None = None
    toi_seconds: int = 0
    toi_formatted: str = "00:00"
    shifts: int = 0
    power_play_goals: int = 0
    shorthanded_goals: int = 0


class GoalieGameStats(BaseModel):
    """Individual goalie statistics for a game."""

    player_id: int
    player_name: str
    team_id: int
    team_abbr: str
    saves: int = 0
    shots_against: int = 0
    goals_against: int = 0
    save_pct: float | None = None
    toi_seconds: int = 0
    toi_formatted: str = "00:00"
    even_strength_saves: int = 0
    even_strength_shots: int = 0
    power_play_saves: int = 0
    power_play_shots: int = 0
    shorthanded_saves: int = 0
    shorthanded_shots: int = 0
    is_starter: bool = False
    decision: str | None = None


class GamePlayerStats(BaseModel):
    """All player statistics for a game."""

    game_id: int
    home_team_id: int
    home_team_abbr: str
    away_team_id: int
    away_team_abbr: str
    home_skaters: list[SkaterGameStats]
    away_skaters: list[SkaterGameStats]
    home_goalies: list[GoalieGameStats]
    away_goalies: list[GoalieGameStats]


# =============================================================================
# Game Shifts (TOI Detail)
# =============================================================================


class ShiftDetail(BaseModel):
    """Individual shift record."""

    shift_number: int
    period: int
    start_time: str
    end_time: str
    duration_seconds: int
    is_goal_event: bool = False
    event_description: str | None = None


class PlayerShiftSummary(BaseModel):
    """Player shift summary with TOI breakdown."""

    player_id: int
    player_name: str
    sweater_number: int | None = None
    position: str | None = None
    team_id: int
    team_abbr: str

    # Total TOI
    total_toi_seconds: int = 0
    total_toi_display: str = "00:00"
    total_shifts: int = 0
    avg_shift_seconds: float = 0.0

    # By period (period number -> seconds)
    period_1_toi: int = 0
    period_2_toi: int = 0
    period_3_toi: int = 0
    ot_toi: int = 0


class GameShiftsResponse(BaseModel):
    """All shift data for a game."""

    game_id: int
    home_team_id: int
    home_team_abbr: str
    away_team_id: int
    away_team_abbr: str
    home_players: list[PlayerShiftSummary]
    away_players: list[PlayerShiftSummary]


# =============================================================================
# Player Game Log
# =============================================================================


class PlayerGameEntry(BaseModel):
    """Single game entry in a player's game log (clickable game)."""

    game_id: int
    game_date: date
    season_id: int
    opponent_team_id: int
    opponent_abbr: str
    opponent_name: str
    is_home: bool
    result: str | None = None  # W, L, OTL

    # Scores
    player_team_score: int | None = None
    opponent_score: int | None = None

    # Stats (for skaters)
    goals: int | None = None
    assists: int | None = None
    points: int | None = None
    plus_minus: int | None = None
    pim: int | None = None
    shots: int | None = None
    toi_display: str | None = None

    # Stats (for goalies)
    saves: int | None = None
    shots_against: int | None = None
    save_pct: float | None = None
    decision: str | None = None


class PlayerGameLogResponse(BaseModel):
    """Player's game log with recent games."""

    player_id: int
    player_name: str
    position_type: str | None = None
    games: list[PlayerGameEntry]
    pagination: PaginationMeta


# =============================================================================
# Team Games (Recent Schedule)
# =============================================================================


class TeamRecentGamesResponse(BaseModel):
    """Team's recent and upcoming games."""

    team_id: int
    team_name: str
    team_abbr: str
    games: list[GameSummary]
    pagination: PaginationMeta
