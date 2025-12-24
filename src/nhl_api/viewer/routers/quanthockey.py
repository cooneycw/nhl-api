"""QuantHockey player statistics endpoints.

Provides access to QuantHockey 51-field player statistics including:
- Season leaders (points, goals, assists)
- Team player stats
- Individual player stats
- Historical snapshot data
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(prefix="/quanthockey", tags=["quanthockey"])


# =============================================================================
# Schemas
# =============================================================================


class PlayerStatsEntry(BaseModel):
    """Comprehensive 51-field player statistics."""

    # Core Identity
    rank: int
    player_name: str
    team_abbrev: str
    age: int | None
    position: str
    games_played: int
    goals: int
    assists: int
    points: int
    pim: int
    plus_minus: int

    # Time on Ice
    toi_avg: float | None
    toi_es: float | None
    toi_pp: float | None
    toi_sh: float | None

    # Goal Breakdowns
    es_goals: int | None
    pp_goals: int | None
    sh_goals: int | None
    gw_goals: int | None
    ot_goals: int | None

    # Assist Breakdowns
    es_assists: int | None
    pp_assists: int | None
    sh_assists: int | None
    gw_assists: int | None
    ot_assists: int | None

    # Point Breakdowns
    es_points: int | None
    pp_points: int | None
    sh_points: int | None
    gw_points: int | None
    ot_points: int | None
    ppp_pct: float | None

    # Per-60 Rates
    goals_per_60: float | None
    assists_per_60: float | None
    points_per_60: float | None
    es_goals_per_60: float | None
    es_assists_per_60: float | None
    es_points_per_60: float | None
    pp_goals_per_60: float | None
    pp_assists_per_60: float | None
    pp_points_per_60: float | None

    # Per-Game Rates
    goals_per_game: float | None
    assists_per_game: float | None
    points_per_game: float | None

    # Shooting
    shots_on_goal: int | None
    shooting_pct: float | None

    # Physical
    hits: int | None
    blocked_shots: int | None

    # Faceoffs
    faceoffs_won: int | None
    faceoffs_lost: int | None
    faceoff_pct: float | None

    # Metadata
    nationality: str | None
    player_id: int | None  # NHL player_id if linked


class ScoringLeadersResponse(BaseModel):
    """Scoring leaders for a season."""

    season_id: int
    snapshot_date: date
    leaders: list[PlayerStatsEntry]
    total_players: int


class TeamStatsResponse(BaseModel):
    """Player stats for a specific team."""

    team_abbrev: str
    season_id: int
    snapshot_date: date
    players: list[PlayerStatsEntry]
    player_count: int


class PlayerHistoryEntry(BaseModel):
    """A single snapshot of player stats."""

    snapshot_date: date
    rank: int
    games_played: int
    goals: int
    assists: int
    points: int
    plus_minus: int
    points_per_game: float | None


class PlayerHistoryResponse(BaseModel):
    """Historical snapshots for a player."""

    player_name: str
    season_id: int
    snapshots: list[PlayerHistoryEntry]
    snapshot_count: int


class AvailableSeasonsResponse(BaseModel):
    """Available seasons with QuantHockey data."""

    seasons: list[int]
    latest_season: int | None


# =============================================================================
# Helper Functions
# =============================================================================


def _row_to_player_stats(row: dict[str, Any]) -> PlayerStatsEntry:
    """Convert a database row to PlayerStatsEntry."""
    return PlayerStatsEntry(
        rank=row["rank"],
        player_name=row["player_name"],
        team_abbrev=row["team_abbrev"],
        age=row["age"],
        position=row["position"],
        games_played=row["games_played"],
        goals=row["goals"],
        assists=row["assists"],
        points=row["points"],
        pim=row["pim"],
        plus_minus=row["plus_minus"],
        toi_avg=float(row["toi_avg"]) if row["toi_avg"] else None,
        toi_es=float(row["toi_es"]) if row["toi_es"] else None,
        toi_pp=float(row["toi_pp"]) if row["toi_pp"] else None,
        toi_sh=float(row["toi_sh"]) if row["toi_sh"] else None,
        es_goals=row["es_goals"],
        pp_goals=row["pp_goals"],
        sh_goals=row["sh_goals"],
        gw_goals=row["gw_goals"],
        ot_goals=row["ot_goals"],
        es_assists=row["es_assists"],
        pp_assists=row["pp_assists"],
        sh_assists=row["sh_assists"],
        gw_assists=row["gw_assists"],
        ot_assists=row["ot_assists"],
        es_points=row["es_points"],
        pp_points=row["pp_points"],
        sh_points=row["sh_points"],
        gw_points=row["gw_points"],
        ot_points=row["ot_points"],
        ppp_pct=float(row["ppp_pct"]) if row["ppp_pct"] else None,
        goals_per_60=float(row["goals_per_60"]) if row["goals_per_60"] else None,
        assists_per_60=float(row["assists_per_60"]) if row["assists_per_60"] else None,
        points_per_60=float(row["points_per_60"]) if row["points_per_60"] else None,
        es_goals_per_60=float(row["es_goals_per_60"])
        if row["es_goals_per_60"]
        else None,
        es_assists_per_60=float(row["es_assists_per_60"])
        if row["es_assists_per_60"]
        else None,
        es_points_per_60=float(row["es_points_per_60"])
        if row["es_points_per_60"]
        else None,
        pp_goals_per_60=float(row["pp_goals_per_60"])
        if row["pp_goals_per_60"]
        else None,
        pp_assists_per_60=float(row["pp_assists_per_60"])
        if row["pp_assists_per_60"]
        else None,
        pp_points_per_60=float(row["pp_points_per_60"])
        if row["pp_points_per_60"]
        else None,
        goals_per_game=float(row["goals_per_game"]) if row["goals_per_game"] else None,
        assists_per_game=float(row["assists_per_game"])
        if row["assists_per_game"]
        else None,
        points_per_game=float(row["points_per_game"])
        if row["points_per_game"]
        else None,
        shots_on_goal=row["shots_on_goal"],
        shooting_pct=float(row["shooting_pct"]) if row["shooting_pct"] else None,
        hits=row["hits"],
        blocked_shots=row["blocked_shots"],
        faceoffs_won=row["faceoffs_won"],
        faceoffs_lost=row["faceoffs_lost"],
        faceoff_pct=float(row["faceoff_pct"]) if row["faceoff_pct"] else None,
        nationality=row["nationality"],
        player_id=row["player_id"],
    )


# =============================================================================
# Scoring Leaders
# =============================================================================


@router.get(
    "/leaders",
    response_model=ScoringLeadersResponse,
    summary="Get Scoring Leaders",
    description="Get top scoring players for a season",
)
async def get_scoring_leaders(
    db: DbDep,
    season_id: Annotated[
        int | None, Query(description="Season ID (defaults to current)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Max players")] = 50,
    position: Annotated[
        str | None, Query(description="Filter by position (C, LW, RW, D)")
    ] = None,
    sort_by: Annotated[
        str,
        Query(description="Sort field: points, goals, assists, plus_minus"),
    ] = "points",
) -> ScoringLeadersResponse:
    """Get top scoring players for a season."""
    # Get latest season if not specified
    if season_id is None:
        season_row = await db.fetchrow(
            """
            SELECT MAX(season_id) as latest_season
            FROM qh_player_season_stats
            """
        )
        if not season_row or not season_row["latest_season"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No QuantHockey data available",
            )
        season_id = season_row["latest_season"]

    # Get latest snapshot date for this season
    snapshot_row = await db.fetchrow(
        """
        SELECT MAX(snapshot_date) as latest_date
        FROM qh_player_season_stats
        WHERE season_id = $1
        """,
        season_id,
    )
    if not snapshot_row or not snapshot_row["latest_date"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No QuantHockey data found for season {season_id}",
        )
    snapshot_date = snapshot_row["latest_date"]

    # Validate sort_by
    valid_sorts = {"points", "goals", "assists", "plus_minus"}
    if sort_by not in valid_sorts:
        sort_by = "points"

    # Build query
    query = """
        SELECT *
        FROM qh_player_season_stats
        WHERE season_id = $1 AND snapshot_date = $2
    """
    params: list[Any] = [season_id, snapshot_date]

    if position:
        query += " AND position = $3"
        params.append(position.upper())

    query += f" ORDER BY {sort_by} DESC LIMIT ${len(params) + 1}"
    params.append(limit)

    rows = await db.fetch(query, *params)

    leaders = [_row_to_player_stats(row) for row in rows]

    # Get total count
    count_query = """
        SELECT COUNT(*) as total
        FROM qh_player_season_stats
        WHERE season_id = $1 AND snapshot_date = $2
    """
    count_params: list[Any] = [season_id, snapshot_date]
    if position:
        count_query += " AND position = $3"
        count_params.append(position.upper())

    count_row = await db.fetchrow(count_query, *count_params)
    total = count_row["total"] if count_row else 0

    return ScoringLeadersResponse(
        season_id=season_id,
        snapshot_date=snapshot_date,
        leaders=leaders,
        total_players=total,
    )


# =============================================================================
# Team Stats
# =============================================================================


@router.get(
    "/teams/{team_abbrev}",
    response_model=TeamStatsResponse,
    summary="Get Team Player Stats",
    description="Get all player stats for a specific team",
)
async def get_team_stats(
    team_abbrev: str,
    db: DbDep,
    season_id: Annotated[
        int | None, Query(description="Season ID (defaults to current)")
    ] = None,
) -> TeamStatsResponse:
    """Get player stats for a specific team."""
    team_abbrev = team_abbrev.upper()

    # Get latest season if not specified
    if season_id is None:
        season_row = await db.fetchrow(
            """
            SELECT MAX(season_id) as latest_season
            FROM qh_player_season_stats
            WHERE team_abbrev = $1
            """,
            team_abbrev,
        )
        if not season_row or not season_row["latest_season"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No QuantHockey data found for team {team_abbrev}",
            )
        season_id = season_row["latest_season"]

    # Get latest snapshot date
    snapshot_row = await db.fetchrow(
        """
        SELECT MAX(snapshot_date) as latest_date
        FROM qh_player_season_stats
        WHERE season_id = $1 AND team_abbrev = $2
        """,
        season_id,
        team_abbrev,
    )
    if not snapshot_row or not snapshot_row["latest_date"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No QuantHockey data found for team {team_abbrev} in season {season_id}",
        )
    snapshot_date = snapshot_row["latest_date"]

    rows = await db.fetch(
        """
        SELECT *
        FROM qh_player_season_stats
        WHERE season_id = $1 AND team_abbrev = $2 AND snapshot_date = $3
        ORDER BY points DESC
        """,
        season_id,
        team_abbrev,
        snapshot_date,
    )

    players = [_row_to_player_stats(row) for row in rows]

    return TeamStatsResponse(
        team_abbrev=team_abbrev,
        season_id=season_id,
        snapshot_date=snapshot_date,
        players=players,
        player_count=len(players),
    )


# =============================================================================
# Player History
# =============================================================================


@router.get(
    "/players/{player_name}/history",
    response_model=PlayerHistoryResponse,
    summary="Get Player History",
    description="Get historical snapshots for a player's season",
)
async def get_player_history(
    player_name: str,
    db: DbDep,
    season_id: Annotated[
        int | None, Query(description="Season ID (defaults to current)")
    ] = None,
) -> PlayerHistoryResponse:
    """Get historical stat snapshots for a player."""
    # Get latest season if not specified
    if season_id is None:
        season_row = await db.fetchrow(
            """
            SELECT MAX(season_id) as latest_season
            FROM qh_player_season_stats
            WHERE player_name ILIKE $1
            """,
            f"%{player_name}%",
        )
        if not season_row or not season_row["latest_season"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for player matching '{player_name}'",
            )
        season_id = season_row["latest_season"]

    rows = await db.fetch(
        """
        SELECT snapshot_date, rank, games_played, goals, assists, points,
               plus_minus, points_per_game
        FROM qh_player_season_stats
        WHERE season_id = $1 AND player_name ILIKE $2
        ORDER BY snapshot_date DESC
        """,
        season_id,
        f"%{player_name}%",
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for player matching '{player_name}' in season {season_id}",
        )

    # Get exact name from first row
    exact_name_row = await db.fetchrow(
        """
        SELECT player_name
        FROM qh_player_season_stats
        WHERE season_id = $1 AND player_name ILIKE $2
        LIMIT 1
        """,
        season_id,
        f"%{player_name}%",
    )
    exact_name = exact_name_row["player_name"] if exact_name_row else player_name

    snapshots = [
        PlayerHistoryEntry(
            snapshot_date=row["snapshot_date"],
            rank=row["rank"],
            games_played=row["games_played"],
            goals=row["goals"],
            assists=row["assists"],
            points=row["points"],
            plus_minus=row["plus_minus"],
            points_per_game=float(row["points_per_game"])
            if row["points_per_game"]
            else None,
        )
        for row in rows
    ]

    return PlayerHistoryResponse(
        player_name=exact_name,
        season_id=season_id,
        snapshots=snapshots,
        snapshot_count=len(snapshots),
    )


# =============================================================================
# Available Seasons
# =============================================================================


@router.get(
    "/seasons",
    response_model=AvailableSeasonsResponse,
    summary="Get Available Seasons",
    description="Get list of seasons with QuantHockey data",
)
async def get_available_seasons(db: DbDep) -> AvailableSeasonsResponse:
    """Get list of seasons that have QuantHockey data."""
    rows = await db.fetch(
        """
        SELECT DISTINCT season_id
        FROM qh_player_season_stats
        ORDER BY season_id DESC
        """
    )

    seasons = [row["season_id"] for row in rows]

    return AvailableSeasonsResponse(
        seasons=seasons,
        latest_season=seasons[0] if seasons else None,
    )
