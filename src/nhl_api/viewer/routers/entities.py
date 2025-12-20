"""Entity exploration endpoints for players, teams, and games.

Provides paginated, searchable, and filterable access to NHL entity data
using materialized views for optimal query performance.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db
from nhl_api.viewer.schemas.entities import (
    DivisionTeams,
    GameDetail,
    GameListResponse,
    GameSummary,
    PaginationMeta,
    PlayerDetail,
    PlayerListResponse,
    PlayerSummary,
    TeamDetail,
    TeamListResponse,
    TeamSummary,
    TeamWithRoster,
)

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(tags=["entities"])


# =============================================================================
# Players
# =============================================================================


@router.get(
    "/players",
    response_model=PlayerListResponse,
    summary="List Players",
    description="Get paginated list of players with search and position filter",
)
async def list_players(
    db: DbDep,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 25,
    search: Annotated[str | None, Query(description="Search by player name")] = None,
    position: Annotated[
        Literal["C", "LW", "RW", "D", "G"] | None,
        Query(description="Filter by primary position"),
    ] = None,
    team_id: Annotated[int | None, Query(description="Filter by team ID")] = None,
    active_only: Annotated[bool, Query(description="Only show active players")] = True,
) -> PlayerListResponse:
    """Get a paginated list of players.

    Supports full-text search on player names and filtering by position/team.
    """
    # Build WHERE clauses
    conditions: list[str] = []
    params: list[object] = []
    param_idx = 1

    if active_only:
        conditions.append("active = TRUE")

    if search:
        conditions.append(
            f"(full_name ILIKE ${param_idx} OR "
            f"to_tsvector('english', full_name) @@ plainto_tsquery('english', ${param_idx + 1}))"
        )
        params.extend([f"%{search}%", search])
        param_idx += 2

    if position:
        conditions.append(f"primary_position = ${param_idx}")
        params.append(position)
        param_idx += 1

    if team_id:
        conditions.append(f"current_team_id = ${param_idx}")
        params.append(team_id)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    # Get total count
    count_query = f"SELECT COUNT(*) FROM mv_player_summary WHERE {where_clause}"
    total_items = await db.fetchval(count_query, *params)

    # Calculate pagination
    total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 0
    offset = (page - 1) * per_page

    # Get players
    query = f"""
        SELECT
            player_id, first_name, last_name, full_name, age,
            primary_position, position_type, current_team_id,
            team_name, team_abbreviation, sweater_number,
            headshot_url, active
        FROM mv_player_summary
        WHERE {where_clause}
        ORDER BY last_name, first_name
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([per_page, offset])

    rows = await db.fetch(query, *params)

    players = [PlayerSummary(**dict(row)) for row in rows]

    return PlayerListResponse(
        players=players,
        pagination=PaginationMeta(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/players/{player_id}",
    response_model=PlayerDetail,
    summary="Get Player",
    description="Get detailed player information by ID",
)
async def get_player(
    db: DbDep,
    player_id: int,
) -> PlayerDetail:
    """Get detailed information for a specific player."""
    query = """
        SELECT
            player_id, first_name, last_name, full_name,
            birth_date, age, birth_country, nationality,
            height_inches, height_display, weight_lbs,
            shoots_catches, primary_position, position_type,
            roster_status, current_team_id, team_name,
            team_abbreviation, division_name, conference_name,
            captain, alternate_captain, rookie, nhl_experience,
            sweater_number, headshot_url, active, updated_at
        FROM mv_player_summary
        WHERE player_id = $1
    """
    row = await db.fetchrow(query, player_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player with ID {player_id} not found",
        )

    return PlayerDetail(**dict(row))


# =============================================================================
# Teams
# =============================================================================


@router.get(
    "/teams",
    response_model=TeamListResponse,
    summary="List Teams",
    description="Get all teams grouped by division",
)
async def list_teams(
    db: DbDep,
    active_only: Annotated[bool, Query(description="Only show active teams")] = True,
) -> TeamListResponse:
    """Get all teams grouped by division and conference."""
    where_clause = "t.active = TRUE" if active_only else "TRUE"

    query = f"""
        SELECT
            t.team_id, t.name, t.abbreviation, t.team_name,
            t.location_name, t.division_id, d.name AS division_name,
            t.conference_id, c.name AS conference_name, t.active
        FROM teams t
        LEFT JOIN divisions d ON t.division_id = d.division_id
        LEFT JOIN conferences c ON t.conference_id = c.conference_id
        WHERE {where_clause}
        ORDER BY c.name, d.name, t.name
    """
    rows = await db.fetch(query)

    # Group by division
    divisions_map: dict[int, DivisionTeams] = {}
    for row in rows:
        div_id = row["division_id"]
        if div_id is None:
            continue

        if div_id not in divisions_map:
            divisions_map[div_id] = DivisionTeams(
                division_id=div_id,
                division_name=row["division_name"] or "Unknown",
                conference_name=row["conference_name"],
                teams=[],
            )
        divisions_map[div_id].teams.append(TeamSummary(**dict(row)))

    return TeamListResponse(
        divisions=list(divisions_map.values()),
        total_teams=len(rows),
    )


@router.get(
    "/teams/{team_id}",
    response_model=TeamWithRoster,
    summary="Get Team",
    description="Get team details with current roster",
)
async def get_team(
    db: DbDep,
    team_id: int,
) -> TeamWithRoster:
    """Get detailed team information with current roster."""
    # Get team details
    team_query = """
        SELECT
            t.team_id, t.franchise_id, t.name, t.abbreviation,
            t.team_name, t.location_name, t.division_id,
            d.name AS division_name, t.conference_id,
            c.name AS conference_name, t.venue_id,
            v.name AS venue_name, t.first_year_of_play,
            t.official_site_url, t.active, t.updated_at
        FROM teams t
        LEFT JOIN divisions d ON t.division_id = d.division_id
        LEFT JOIN conferences c ON t.conference_id = c.conference_id
        LEFT JOIN venues v ON t.venue_id = v.venue_id
        WHERE t.team_id = $1
    """
    team_row = await db.fetchrow(team_query, team_id)

    if not team_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with ID {team_id} not found",
        )

    team = TeamDetail(**dict(team_row))

    # Get roster
    roster_query = """
        SELECT
            player_id, first_name, last_name, full_name, age,
            primary_position, position_type, current_team_id,
            team_name, team_abbreviation, sweater_number,
            headshot_url, active
        FROM mv_player_summary
        WHERE current_team_id = $1 AND active = TRUE
        ORDER BY
            CASE position_type
                WHEN 'G' THEN 1
                WHEN 'D' THEN 2
                WHEN 'F' THEN 3
                ELSE 4
            END,
            last_name, first_name
    """
    roster_rows = await db.fetch(roster_query, team_id)
    roster = [PlayerSummary(**dict(row)) for row in roster_rows]

    return TeamWithRoster(team=team, roster=roster)


# =============================================================================
# Games
# =============================================================================


@router.get(
    "/games",
    response_model=GameListResponse,
    summary="List Games",
    description="Get paginated list of games with date and team filters",
)
async def list_games(
    db: DbDep,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 25,
    season: Annotated[
        str | None, Query(description="Filter by season (e.g., '20242025')")
    ] = None,
    team_id: Annotated[
        int | None, Query(description="Filter by team (home or away)")
    ] = None,
    start_date: Annotated[
        date | None, Query(description="Start date (inclusive)")
    ] = None,
    end_date: Annotated[date | None, Query(description="End date (inclusive)")] = None,
    game_type: Annotated[
        Literal["PR", "R", "P", "A"] | None,
        Query(description="Game type: PR=Preseason, R=Regular, P=Playoffs, A=All-Star"),
    ] = None,
) -> GameListResponse:
    """Get a paginated list of games.

    Supports filtering by season, team, date range, and game type.
    """
    # Build WHERE clauses
    conditions: list[str] = []
    params: list[object] = []
    param_idx = 1

    if season:
        conditions.append(f"season_name = ${param_idx}")
        params.append(season)
        param_idx += 1

    if team_id:
        conditions.append(
            f"(home_team_id = ${param_idx} OR away_team_id = ${param_idx})"
        )
        params.append(team_id)
        param_idx += 1

    if start_date:
        conditions.append(f"game_date >= ${param_idx}")
        params.append(start_date)
        param_idx += 1

    if end_date:
        conditions.append(f"game_date <= ${param_idx}")
        params.append(end_date)
        param_idx += 1

    if game_type:
        conditions.append(f"game_type = ${param_idx}")
        params.append(game_type)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    # Get total count
    count_query = f"SELECT COUNT(*) FROM mv_game_summary WHERE {where_clause}"
    total_items = await db.fetchval(count_query, *params)

    # Calculate pagination
    total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 0
    offset = (page - 1) * per_page

    # Get games
    query = f"""
        SELECT
            game_id, season_id, season_name, game_type, game_type_name,
            game_date, game_time, venue_name, home_team_id,
            home_team_name, home_team_abbr, home_score,
            away_team_id, away_team_name, away_team_abbr, away_score,
            game_state, is_overtime, is_shootout, winner_abbr
        FROM mv_game_summary
        WHERE {where_clause}
        ORDER BY game_date DESC, game_time DESC NULLS LAST
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([per_page, offset])

    rows = await db.fetch(query, *params)

    games = [GameSummary(**dict(row)) for row in rows]

    return GameListResponse(
        games=games,
        pagination=PaginationMeta(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/games/{game_id}",
    response_model=GameDetail,
    summary="Get Game",
    description="Get detailed game information by ID",
)
async def get_game(
    db: DbDep,
    game_id: int,
) -> GameDetail:
    """Get detailed information for a specific game."""
    query = """
        SELECT
            game_id, season_id, season_name, game_type, game_type_name,
            game_date, game_time, venue_id, venue_name, venue_city,
            home_team_id, home_team_name, home_team_abbr, home_score,
            away_team_id, away_team_name, away_team_abbr, away_score,
            final_period, game_state, is_overtime, is_shootout,
            game_outcome, winner_team_id, winner_abbr,
            goal_differential, attendance, game_duration_minutes,
            updated_at
        FROM mv_game_summary
        WHERE game_id = $1
    """
    row = await db.fetchrow(query, game_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game with ID {game_id} not found",
        )

    return GameDetail(**dict(row))
