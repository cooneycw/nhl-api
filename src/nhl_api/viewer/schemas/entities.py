"""Pydantic schemas for entity API endpoints.

Defines request/response models for players, teams, and games.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

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
    game_time: str | None = None
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


class GameDetail(BaseModel):
    """Detailed game information."""

    game_id: int
    season_id: int
    season_name: str | None = None
    game_type: str
    game_type_name: str | None = None
    game_date: date
    game_time: str | None = None
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


class GameListResponse(BaseModel):
    """Response for game list endpoint."""

    games: list[GameSummary]
    pagination: PaginationMeta
