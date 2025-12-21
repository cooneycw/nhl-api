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
    GameEventsResponse,
    GameListResponse,
    GamePlayerStats,
    GameShiftsResponse,
    GameSummary,
    GoalieGameStats,
    PaginationMeta,
    PlayByPlayEvent,
    PlayerDetail,
    PlayerGameEntry,
    PlayerGameLogResponse,
    PlayerListResponse,
    PlayerShiftSummary,
    PlayerSummary,
    SkaterGameStats,
    TeamDetail,
    TeamListResponse,
    TeamRecentGamesResponse,
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


@router.get(
    "/games/{game_id}/events",
    response_model=GameEventsResponse,
    summary="Get Game Events",
    description="Get play-by-play events for a game",
)
async def get_game_events(
    db: DbDep,
    game_id: int,
    period: Annotated[int | None, Query(description="Filter by period")] = None,
    event_type: Annotated[
        str | None, Query(description="Filter by event type (e.g., 'goal', 'penalty')")
    ] = None,
) -> GameEventsResponse:
    """Get play-by-play events for a specific game.

    Supports filtering by period and event type.
    """
    # Build WHERE clauses
    conditions: list[str] = ["e.game_id = $1"]
    params: list[object] = [game_id]
    param_idx = 2

    if period is not None:
        conditions.append(f"e.period = ${param_idx}")
        params.append(period)
        param_idx += 1

    if event_type:
        conditions.append(f"e.event_type ILIKE ${param_idx}")
        params.append(f"%{event_type}%")
        param_idx += 1

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            e.event_idx,
            e.event_type,
            e.period,
            e.period_type,
            e.time_in_period,
            e.time_remaining,
            e.description,
            e.player1_id,
            COALESCE(p1.first_name || ' ' || p1.last_name, '') as player1_name,
            e.player1_role,
            e.player2_id,
            COALESCE(p2.first_name || ' ' || p2.last_name, '') as player2_name,
            e.player2_role,
            e.player3_id,
            COALESCE(p3.first_name || ' ' || p3.last_name, '') as player3_name,
            e.player3_role,
            e.event_owner_team_id as team_id,
            t.abbreviation as team_abbr,
            e.home_score,
            e.away_score,
            e.shot_type,
            e.zone,
            e.x_coord,
            e.y_coord
        FROM game_events e
        LEFT JOIN players p1 ON e.player1_id = p1.player_id
        LEFT JOIN players p2 ON e.player2_id = p2.player_id
        LEFT JOIN players p3 ON e.player3_id = p3.player_id
        LEFT JOIN teams t ON e.event_owner_team_id = t.team_id
        WHERE {where_clause}
        ORDER BY e.period, e.event_idx
    """
    rows = await db.fetch(query, *params)

    events = [PlayByPlayEvent(**dict(row)) for row in rows]

    return GameEventsResponse(
        game_id=game_id,
        events=events,
        total_events=len(events),
    )


def _format_toi(seconds: int | None) -> str:
    """Format time on ice from seconds to MM:SS."""
    if seconds is None or seconds == 0:
        return "00:00"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


@router.get(
    "/games/{game_id}/stats",
    response_model=GamePlayerStats,
    summary="Get Game Player Stats",
    description="Get player statistics for a game",
)
async def get_game_stats(
    db: DbDep,
    game_id: int,
) -> GamePlayerStats:
    """Get player statistics for a specific game.

    Returns skater and goalie stats for both home and away teams.
    """
    # First get game info to determine home/away teams
    game_query = """
        SELECT home_team_id, away_team_id, home_team_abbr, away_team_abbr
        FROM mv_game_summary
        WHERE game_id = $1
    """
    game_row = await db.fetchrow(game_query, game_id)

    if not game_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game with ID {game_id} not found",
        )

    home_team_id = game_row["home_team_id"]
    away_team_id = game_row["away_team_id"]
    home_team_abbr = game_row["home_team_abbr"]
    away_team_abbr = game_row["away_team_abbr"]

    # Get skater stats
    skater_query = """
        SELECT
            s.player_id,
            p.first_name || ' ' || p.last_name as player_name,
            s.team_id,
            t.abbreviation as team_abbr,
            s.position,
            COALESCE(s.goals, 0) as goals,
            COALESCE(s.assists, 0) as assists,
            COALESCE(s.points, 0) as points,
            COALESCE(s.plus_minus, 0) as plus_minus,
            COALESCE(s.pim, 0) as pim,
            COALESCE(s.shots, 0) as shots,
            COALESCE(s.hits, 0) as hits,
            COALESCE(s.blocked_shots, 0) as blocked_shots,
            COALESCE(s.giveaways, 0) as giveaways,
            COALESCE(s.takeaways, 0) as takeaways,
            s.faceoff_pct,
            COALESCE(s.toi_seconds, 0) as toi_seconds,
            COALESCE(s.shifts, 0) as shifts,
            COALESCE(s.power_play_goals, 0) as power_play_goals,
            COALESCE(s.shorthanded_goals, 0) as shorthanded_goals
        FROM game_skater_stats s
        JOIN players p ON s.player_id = p.player_id
        JOIN teams t ON s.team_id = t.team_id
        WHERE s.game_id = $1
        ORDER BY s.team_id, s.points DESC, s.goals DESC, s.toi_seconds DESC
    """
    skater_rows = await db.fetch(skater_query, game_id)

    home_skaters: list[SkaterGameStats] = []
    away_skaters: list[SkaterGameStats] = []

    for row in skater_rows:
        row_dict = dict(row)
        row_dict["toi_formatted"] = _format_toi(row_dict.get("toi_seconds", 0))
        skater = SkaterGameStats(**row_dict)

        if row["team_id"] == home_team_id:
            home_skaters.append(skater)
        else:
            away_skaters.append(skater)

    # Get goalie stats
    goalie_query = """
        SELECT
            g.player_id,
            p.first_name || ' ' || p.last_name as player_name,
            g.team_id,
            t.abbreviation as team_abbr,
            COALESCE(g.saves, 0) as saves,
            COALESCE(g.shots_against, 0) as shots_against,
            COALESCE(g.goals_against, 0) as goals_against,
            g.save_pct,
            COALESCE(g.toi_seconds, 0) as toi_seconds,
            COALESCE(g.even_strength_saves, 0) as even_strength_saves,
            COALESCE(g.even_strength_shots, 0) as even_strength_shots,
            COALESCE(g.power_play_saves, 0) as power_play_saves,
            COALESCE(g.power_play_shots, 0) as power_play_shots,
            COALESCE(g.shorthanded_saves, 0) as shorthanded_saves,
            COALESCE(g.shorthanded_shots, 0) as shorthanded_shots,
            COALESCE(g.is_starter, FALSE) as is_starter,
            g.decision
        FROM game_goalie_stats g
        JOIN players p ON g.player_id = p.player_id
        JOIN teams t ON g.team_id = t.team_id
        WHERE g.game_id = $1
        ORDER BY g.team_id, g.toi_seconds DESC
    """
    goalie_rows = await db.fetch(goalie_query, game_id)

    home_goalies: list[GoalieGameStats] = []
    away_goalies: list[GoalieGameStats] = []

    for row in goalie_rows:
        row_dict = dict(row)
        row_dict["toi_formatted"] = _format_toi(row_dict.get("toi_seconds", 0))
        goalie = GoalieGameStats(**row_dict)

        if row["team_id"] == home_team_id:
            home_goalies.append(goalie)
        else:
            away_goalies.append(goalie)

    return GamePlayerStats(
        game_id=game_id,
        home_team_id=home_team_id,
        home_team_abbr=home_team_abbr,
        away_team_id=away_team_id,
        away_team_abbr=away_team_abbr,
        home_skaters=home_skaters,
        away_skaters=away_skaters,
        home_goalies=home_goalies,
        away_goalies=away_goalies,
    )


@router.get(
    "/games/{game_id}/shifts",
    response_model=GameShiftsResponse,
    summary="Get Game Shifts",
    description="Get shift chart data for a game",
)
async def get_game_shifts(
    db: DbDep,
    game_id: int,
) -> GameShiftsResponse:
    """Get shift data for a specific game.

    Returns per-player TOI breakdown with period-by-period details.
    """
    # First get game info to determine home/away teams
    game_query = """
        SELECT home_team_id, away_team_id, home_team_abbr, away_team_abbr
        FROM mv_game_summary
        WHERE game_id = $1
    """
    game_row = await db.fetchrow(game_query, game_id)

    if not game_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game with ID {game_id} not found",
        )

    home_team_id = game_row["home_team_id"]
    away_team_id = game_row["away_team_id"]
    home_team_abbr = game_row["home_team_abbr"]
    away_team_abbr = game_row["away_team_abbr"]

    # Get shift data aggregated by player
    shifts_query = """
        SELECT
            s.player_id,
            p.first_name || ' ' || p.last_name as player_name,
            p.sweater_number,
            p.position_code as position,
            s.team_id,
            t.abbreviation as team_abbr,
            COUNT(*) as total_shifts,
            SUM(s.duration) as total_toi_seconds,
            SUM(CASE WHEN s.period = 1 THEN s.duration ELSE 0 END) as period_1_toi,
            SUM(CASE WHEN s.period = 2 THEN s.duration ELSE 0 END) as period_2_toi,
            SUM(CASE WHEN s.period = 3 THEN s.duration ELSE 0 END) as period_3_toi,
            SUM(CASE WHEN s.period > 3 THEN s.duration ELSE 0 END) as ot_toi
        FROM game_shifts s
        JOIN players p ON s.player_id = p.player_id
        JOIN teams t ON s.team_id = t.team_id
        WHERE s.game_id = $1
        GROUP BY s.player_id, p.first_name, p.last_name, p.sweater_number,
                 p.position_code, s.team_id, t.abbreviation
        ORDER BY s.team_id, SUM(s.duration) DESC
    """
    shift_rows = await db.fetch(shifts_query, game_id)

    home_players: list[PlayerShiftSummary] = []
    away_players: list[PlayerShiftSummary] = []

    for row in shift_rows:
        total_toi = row["total_toi_seconds"] or 0
        total_shifts = row["total_shifts"] or 0
        avg_shift = total_toi / total_shifts if total_shifts > 0 else 0.0

        player_summary = PlayerShiftSummary(
            player_id=row["player_id"],
            player_name=row["player_name"],
            sweater_number=row["sweater_number"],
            position=row["position"],
            team_id=row["team_id"],
            team_abbr=row["team_abbr"],
            total_toi_seconds=total_toi,
            total_toi_display=_format_toi(total_toi),
            total_shifts=total_shifts,
            avg_shift_seconds=round(avg_shift, 1),
            period_1_toi=row["period_1_toi"] or 0,
            period_2_toi=row["period_2_toi"] or 0,
            period_3_toi=row["period_3_toi"] or 0,
            ot_toi=row["ot_toi"] or 0,
        )

        if row["team_id"] == home_team_id:
            home_players.append(player_summary)
        else:
            away_players.append(player_summary)

    return GameShiftsResponse(
        game_id=game_id,
        home_team_id=home_team_id,
        home_team_abbr=home_team_abbr,
        away_team_id=away_team_id,
        away_team_abbr=away_team_abbr,
        home_players=home_players,
        away_players=away_players,
    )


# =============================================================================
# Player Game Log
# =============================================================================


@router.get(
    "/players/{player_id}/games",
    response_model=PlayerGameLogResponse,
    summary="Get Player Game Log",
    description="Get a player's recent games with stats",
)
async def get_player_games(
    db: DbDep,
    player_id: int,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 25,
    season: Annotated[
        str | None, Query(description="Filter by season (e.g., '20242025')")
    ] = None,
) -> PlayerGameLogResponse:
    """Get a player's game log with per-game statistics.

    Returns recent games with stats, clickable to navigate to game details.
    """
    # Get player info
    player_query = """
        SELECT player_id, full_name, position_type
        FROM mv_player_summary
        WHERE player_id = $1
    """
    player_row = await db.fetchrow(player_query, player_id)

    if not player_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player with ID {player_id} not found",
        )

    player_name = player_row["full_name"]
    position_type = player_row["position_type"]

    # Build WHERE clauses for game log
    conditions: list[str] = []
    params: list[object] = [player_id]
    param_idx = 2

    if season:
        conditions.append(f"g.season_name = ${param_idx}")
        params.append(season)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    # Determine if player is a goalie
    is_goalie = position_type == "G"

    if is_goalie:
        # Get goalie game log
        count_query = f"""
            SELECT COUNT(*)
            FROM game_goalie_stats gs
            JOIN mv_game_summary g ON gs.game_id = g.game_id
            WHERE gs.player_id = $1 AND {where_clause}
        """
        total_items = await db.fetchval(count_query, *params)

        total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 0
        offset = (page - 1) * per_page

        games_query = f"""
            SELECT
                g.game_id,
                g.game_date,
                g.season_id,
                CASE
                    WHEN gs.team_id = g.home_team_id THEN g.away_team_id
                    ELSE g.home_team_id
                END as opponent_team_id,
                CASE
                    WHEN gs.team_id = g.home_team_id THEN g.away_team_abbr
                    ELSE g.home_team_abbr
                END as opponent_abbr,
                CASE
                    WHEN gs.team_id = g.home_team_id THEN g.away_team_name
                    ELSE g.home_team_name
                END as opponent_name,
                gs.team_id = g.home_team_id as is_home,
                CASE
                    WHEN g.winner_team_id = gs.team_id THEN 'W'
                    WHEN g.is_overtime THEN 'OTL'
                    WHEN g.is_shootout THEN 'SOL'
                    ELSE 'L'
                END as result,
                CASE
                    WHEN gs.team_id = g.home_team_id THEN g.home_score
                    ELSE g.away_score
                END as player_team_score,
                CASE
                    WHEN gs.team_id = g.home_team_id THEN g.away_score
                    ELSE g.home_score
                END as opponent_score,
                gs.saves,
                gs.shots_against,
                gs.save_pct,
                gs.decision
            FROM game_goalie_stats gs
            JOIN mv_game_summary g ON gs.game_id = g.game_id
            WHERE gs.player_id = $1 AND {where_clause}
            ORDER BY g.game_date DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([per_page, offset])
        game_rows = await db.fetch(games_query, *params)

        games = [
            PlayerGameEntry(
                game_id=row["game_id"],
                game_date=row["game_date"],
                season_id=row["season_id"],
                opponent_team_id=row["opponent_team_id"],
                opponent_abbr=row["opponent_abbr"],
                opponent_name=row["opponent_name"],
                is_home=row["is_home"],
                result=row["result"],
                player_team_score=row["player_team_score"],
                opponent_score=row["opponent_score"],
                saves=row["saves"],
                shots_against=row["shots_against"],
                save_pct=row["save_pct"],
                decision=row["decision"],
            )
            for row in game_rows
        ]
    else:
        # Get skater game log
        count_query = f"""
            SELECT COUNT(*)
            FROM game_skater_stats ss
            JOIN mv_game_summary g ON ss.game_id = g.game_id
            WHERE ss.player_id = $1 AND {where_clause}
        """
        total_items = await db.fetchval(count_query, *params)

        total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 0
        offset = (page - 1) * per_page

        games_query = f"""
            SELECT
                g.game_id,
                g.game_date,
                g.season_id,
                CASE
                    WHEN ss.team_id = g.home_team_id THEN g.away_team_id
                    ELSE g.home_team_id
                END as opponent_team_id,
                CASE
                    WHEN ss.team_id = g.home_team_id THEN g.away_team_abbr
                    ELSE g.home_team_abbr
                END as opponent_abbr,
                CASE
                    WHEN ss.team_id = g.home_team_id THEN g.away_team_name
                    ELSE g.home_team_name
                END as opponent_name,
                ss.team_id = g.home_team_id as is_home,
                CASE
                    WHEN g.winner_team_id = ss.team_id THEN 'W'
                    WHEN g.is_overtime THEN 'OTL'
                    WHEN g.is_shootout THEN 'SOL'
                    ELSE 'L'
                END as result,
                CASE
                    WHEN ss.team_id = g.home_team_id THEN g.home_score
                    ELSE g.away_score
                END as player_team_score,
                CASE
                    WHEN ss.team_id = g.home_team_id THEN g.away_score
                    ELSE g.home_score
                END as opponent_score,
                ss.goals,
                ss.assists,
                ss.points,
                ss.plus_minus,
                ss.pim,
                ss.shots,
                ss.toi_seconds
            FROM game_skater_stats ss
            JOIN mv_game_summary g ON ss.game_id = g.game_id
            WHERE ss.player_id = $1 AND {where_clause}
            ORDER BY g.game_date DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([per_page, offset])
        game_rows = await db.fetch(games_query, *params)

        games = [
            PlayerGameEntry(
                game_id=row["game_id"],
                game_date=row["game_date"],
                season_id=row["season_id"],
                opponent_team_id=row["opponent_team_id"],
                opponent_abbr=row["opponent_abbr"],
                opponent_name=row["opponent_name"],
                is_home=row["is_home"],
                result=row["result"],
                player_team_score=row["player_team_score"],
                opponent_score=row["opponent_score"],
                goals=row["goals"],
                assists=row["assists"],
                points=row["points"],
                plus_minus=row["plus_minus"],
                pim=row["pim"],
                shots=row["shots"],
                toi_display=_format_toi(row["toi_seconds"]),
            )
            for row in game_rows
        ]

    return PlayerGameLogResponse(
        player_id=player_id,
        player_name=player_name,
        position_type=position_type,
        games=games,
        pagination=PaginationMeta(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


# =============================================================================
# Team Recent Games
# =============================================================================


@router.get(
    "/teams/{team_id}/games",
    response_model=TeamRecentGamesResponse,
    summary="Get Team Games",
    description="Get a team's recent and upcoming games",
)
async def get_team_games(
    db: DbDep,
    team_id: int,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 25,
    season: Annotated[
        str | None, Query(description="Filter by season (e.g., '20242025')")
    ] = None,
) -> TeamRecentGamesResponse:
    """Get a team's recent and upcoming games.

    Returns games where the team is either home or away.
    """
    # Get team info
    team_query = """
        SELECT team_id, name, abbreviation
        FROM teams
        WHERE team_id = $1
    """
    team_row = await db.fetchrow(team_query, team_id)

    if not team_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with ID {team_id} not found",
        )

    team_name = team_row["name"]
    team_abbr = team_row["abbreviation"]

    # Build WHERE clauses
    conditions: list[str] = ["(home_team_id = $1 OR away_team_id = $1)"]
    params: list[object] = [team_id]
    param_idx = 2

    if season:
        conditions.append(f"season_name = ${param_idx}")
        params.append(season)
        param_idx += 1

    where_clause = " AND ".join(conditions)

    # Get total count
    count_query = f"SELECT COUNT(*) FROM mv_game_summary WHERE {where_clause}"
    total_items = await db.fetchval(count_query, *params)

    total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 0
    offset = (page - 1) * per_page

    # Get games
    games_query = f"""
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
    game_rows = await db.fetch(games_query, *params)

    games = [GameSummary(**dict(row)) for row in game_rows]

    return TeamRecentGamesResponse(
        team_id=team_id,
        team_name=team_name,
        team_abbr=team_abbr,
        games=games,
        pagination=PaginationMeta(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )
