"""Coverage endpoints for data completeness dashboard.

Provides endpoints for:
- Coverage summary showing data completeness per season
- "Gas tank" visualization data with percentages by category
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from fastapi import APIRouter, Depends, Query, status

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db
from nhl_api.viewer.schemas.coverage import (
    CategoryCoverage,
    CoverageResponse,
    SeasonCoverage,
)

# Game type mapping: numeric ID to database codes
GAME_TYPE_MAP = {
    1: ["PR"],  # Preseason
    2: ["R"],  # Regular season
    3: ["P"],  # Playoffs
    4: ["A"],  # All-Star
}

# All completed game states
COMPLETED_GAME_STATES = ("FINAL", "OFF")

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(prefix="/coverage", tags=["coverage"])


# Category configuration for display names and link paths
CATEGORY_CONFIG = {
    "games": {
        "display_name": "Games Downloaded",
        "link_template": "/games?season={season_id}",
    },
    "boxscore": {
        "display_name": "Boxscore Data",
        "link_template": "/games?season={season_id}&has_boxscore=true",
    },
    "pbp": {
        "display_name": "Play-by-Play",
        "link_template": "/games?season={season_id}&has_pbp=true",
    },
    "shifts": {
        "display_name": "Shift Charts",
        "link_template": "/games?season={season_id}&has_shifts=true",
    },
    "players": {
        "display_name": "Player Profiles",
        "link_template": "/players?season={season_id}",
    },
    "html": {
        "display_name": "HTML Reports",
        "link_template": "/games?season={season_id}&has_html=true",
    },
}


def _calculate_percentage(actual: int, expected: int) -> float | None:
    """Calculate percentage, returning None if expected is 0."""
    if expected <= 0:
        return None
    return round((actual / expected) * 100, 1)


async def _get_filtered_coverage(
    db: DatabaseService,
    season_id: int,
    game_type_codes: list[str],
) -> dict[str, Any]:
    """Query coverage data directly from base tables with game_type filtering.

    This bypasses the materialized view to provide per-game-type coverage stats.
    """
    # Query for game counts with game_type filter
    game_query = """
        SELECT
            COUNT(*) FILTER (WHERE UPPER(game_state) IN ('FINAL', 'OFF')) AS games_final,
            COUNT(*) AS games_total
        FROM games
        WHERE season_id = $1 AND game_type = ANY($2::varchar[])
    """
    game_row = await db.fetchrow(game_query, season_id, game_type_codes)
    games_final = game_row["games_final"] if game_row else 0
    games_total = game_row["games_total"] if game_row else 0

    # Boxscore counts
    boxscore_query = """
        SELECT COUNT(DISTINCT gts.game_id) AS boxscore_actual
        FROM games g
        LEFT JOIN game_team_stats gts ON g.game_id = gts.game_id AND g.season_id = gts.season_id
        WHERE g.season_id = $1
          AND g.game_type = ANY($2::varchar[])
          AND UPPER(g.game_state) IN ('FINAL', 'OFF')
    """
    box_row = await db.fetchrow(boxscore_query, season_id, game_type_codes)
    boxscore_actual = box_row["boxscore_actual"] if box_row else 0

    # PBP counts
    pbp_query = """
        SELECT COUNT(DISTINCT ge.game_id) AS pbp_actual
        FROM games g
        LEFT JOIN game_events ge ON g.game_id = ge.game_id
        WHERE g.season_id = $1
          AND g.game_type = ANY($2::varchar[])
          AND UPPER(g.game_state) IN ('FINAL', 'OFF')
    """
    pbp_row = await db.fetchrow(pbp_query, season_id, game_type_codes)
    pbp_actual = pbp_row["pbp_actual"] if pbp_row else 0

    # Shifts counts
    shifts_query = """
        SELECT COUNT(DISTINCT gs.game_id) AS shifts_actual
        FROM games g
        LEFT JOIN game_shifts gs ON g.game_id = gs.game_id
        WHERE g.season_id = $1
          AND g.game_type = ANY($2::varchar[])
          AND UPPER(g.game_state) IN ('FINAL', 'OFF')
    """
    shifts_row = await db.fetchrow(shifts_query, season_id, game_type_codes)
    shifts_actual = shifts_row["shifts_actual"] if shifts_row else 0

    # HTML download counts (from download_progress)
    html_query = """
        SELECT COUNT(DISTINCT dp.item_key) AS html_actual
        FROM download_progress dp
        JOIN data_sources ds ON dp.source_id = ds.source_id
        WHERE ds.name LIKE 'html_%'
          AND dp.status = 'success'
          AND dp.season_id = $1
    """
    html_row = await db.fetchrow(html_query, season_id)
    html_actual = html_row["html_actual"] if html_row else 0

    # Player counts (same as MV - not game-type specific)
    player_query = """
        SELECT
            COUNT(DISTINCT tr.player_id) AS players_expected,
            COUNT(DISTINCT CASE
                WHEN p.height_inches IS NOT NULL AND p.birth_date IS NOT NULL
                THEN tr.player_id
            END) AS players_actual
        FROM team_rosters tr
        JOIN players p ON tr.player_id = p.player_id
        WHERE tr.season_id = $1
    """
    player_row = await db.fetchrow(player_query, season_id)
    players_expected = player_row["players_expected"] if player_row else 0
    players_actual = player_row["players_actual"] if player_row else 0

    # Game logs (same as MV - not game-type specific)
    game_log_query = """
        SELECT
            COUNT(*) AS game_logs_total,
            COUNT(DISTINCT player_id) AS players_with_game_logs
        FROM player_game_logs
        WHERE season_id = $1
    """
    gl_row = await db.fetchrow(game_log_query, season_id)
    game_logs_total = gl_row["game_logs_total"] if gl_row else 0
    players_with_game_logs = gl_row["players_with_game_logs"] if gl_row else 0

    # Get season label
    season_query = """
        SELECT
            CAST(start_year AS TEXT) || '-' || CAST(end_year AS TEXT) AS season_label,
            is_current
        FROM seasons
        WHERE season_id = $1
    """
    season_row = await db.fetchrow(season_query, season_id)
    season_label = season_row["season_label"] if season_row else str(season_id)
    is_current = season_row["is_current"] if season_row else False

    return {
        "season_id": season_id,
        "season_label": season_label,
        "is_current": is_current,
        "games_scheduled": games_total,  # Use total for game type as "scheduled"
        "games_final": games_final,
        "games_total": games_total,
        "boxscore_expected": games_final,
        "boxscore_actual": boxscore_actual,
        "pbp_expected": games_final,
        "pbp_actual": pbp_actual,
        "shifts_expected": games_final,
        "shifts_actual": shifts_actual,
        "players_expected": players_expected,
        "players_actual": players_actual,
        "html_expected": games_final,
        "html_actual": html_actual,
        "game_logs_total": game_logs_total,
        "players_with_game_logs": players_with_game_logs,
        "refreshed_at": datetime.now(UTC),
    }


def _build_categories(row: Mapping[str, Any], season_id: int) -> list[CategoryCoverage]:
    """Build category coverage list from database row."""
    categories = []

    # Games category
    categories.append(
        CategoryCoverage(
            name="games",
            display_name=CATEGORY_CONFIG["games"]["display_name"],
            actual=row["games_final"] or 0,
            expected=row["games_scheduled"] or 0,
            percentage=_calculate_percentage(
                row["games_final"] or 0, row["games_scheduled"] or 0
            ),
            link_path=CATEGORY_CONFIG["games"]["link_template"].format(
                season_id=season_id
            ),
        )
    )

    # Boxscore category
    categories.append(
        CategoryCoverage(
            name="boxscore",
            display_name=CATEGORY_CONFIG["boxscore"]["display_name"],
            actual=row["boxscore_actual"] or 0,
            expected=row["boxscore_expected"] or 0,
            percentage=_calculate_percentage(
                row["boxscore_actual"] or 0, row["boxscore_expected"] or 0
            ),
            link_path=CATEGORY_CONFIG["boxscore"]["link_template"].format(
                season_id=season_id
            ),
        )
    )

    # Play-by-play category
    categories.append(
        CategoryCoverage(
            name="pbp",
            display_name=CATEGORY_CONFIG["pbp"]["display_name"],
            actual=row["pbp_actual"] or 0,
            expected=row["pbp_expected"] or 0,
            percentage=_calculate_percentage(
                row["pbp_actual"] or 0, row["pbp_expected"] or 0
            ),
            link_path=CATEGORY_CONFIG["pbp"]["link_template"].format(
                season_id=season_id
            ),
        )
    )

    # Shifts category
    categories.append(
        CategoryCoverage(
            name="shifts",
            display_name=CATEGORY_CONFIG["shifts"]["display_name"],
            actual=row["shifts_actual"] or 0,
            expected=row["shifts_expected"] or 0,
            percentage=_calculate_percentage(
                row["shifts_actual"] or 0, row["shifts_expected"] or 0
            ),
            link_path=CATEGORY_CONFIG["shifts"]["link_template"].format(
                season_id=season_id
            ),
        )
    )

    # Players category
    categories.append(
        CategoryCoverage(
            name="players",
            display_name=CATEGORY_CONFIG["players"]["display_name"],
            actual=row["players_actual"] or 0,
            expected=row["players_expected"] or 0,
            percentage=_calculate_percentage(
                row["players_actual"] or 0, row["players_expected"] or 0
            ),
            link_path=CATEGORY_CONFIG["players"]["link_template"].format(
                season_id=season_id
            ),
        )
    )

    # HTML reports category
    categories.append(
        CategoryCoverage(
            name="html",
            display_name=CATEGORY_CONFIG["html"]["display_name"],
            actual=row["html_actual"] or 0,
            expected=row["html_expected"] or 0,
            percentage=_calculate_percentage(
                row["html_actual"] or 0, row["html_expected"] or 0
            ),
            link_path=CATEGORY_CONFIG["html"]["link_template"].format(
                season_id=season_id
            ),
        )
    )

    return categories


@router.get(
    "/summary",
    response_model=CoverageResponse,
    status_code=status.HTTP_200_OK,
    summary="Coverage Summary",
    description="Get data coverage statistics for all seasons",
)
async def get_coverage_summary(
    db: DbDep,
    season_ids: Annotated[
        list[int] | None, Query(description="Filter to specific seasons")
    ] = None,
    include_all: Annotated[
        bool, Query(description="Include all seasons (not just recent)")
    ] = False,
    game_type: Annotated[
        int | None,
        Query(
            description="Filter by game type: 1=Preseason, 2=Regular, 3=Playoffs, 4=All-Star"
        ),
    ] = None,
) -> CoverageResponse:
    """Get data coverage summary.

    When game_type is not specified, uses the materialized view for performance.
    When game_type is specified, queries base tables directly for filtered stats.

    Returns coverage statistics showing data completeness ("gas tank" levels)
    for each season across multiple categories: games, boxscore, pbp, shifts,
    players, and HTML reports.
    """
    # If game_type filter is requested, use direct queries instead of MV
    if game_type is not None:
        game_type_codes = GAME_TYPE_MAP.get(game_type, ["R"])

        # Determine which seasons to query
        if season_ids:
            target_seasons = season_ids
        elif include_all:
            # Get all seasons from database
            all_seasons_query = "SELECT season_id FROM seasons ORDER BY season_id DESC"
            season_rows = await db.fetch(all_seasons_query)
            target_seasons = [r["season_id"] for r in season_rows]
        else:
            # Default: current season plus last 2 (3 total)
            recent_query = """
                SELECT season_id FROM seasons ORDER BY season_id DESC LIMIT 3
            """
            season_rows = await db.fetch(recent_query)
            target_seasons = [r["season_id"] for r in season_rows]

        # Query each season with game_type filter
        seasons = []
        latest_refresh: datetime | None = None

        for sid in target_seasons:
            row = await _get_filtered_coverage(db, sid, game_type_codes)
            categories = _build_categories(row, sid)

            season = SeasonCoverage(
                season_id=row["season_id"],
                season_label=row["season_label"] or f"{sid}",
                is_current=row["is_current"] or False,
                categories=categories,
                game_logs_total=row["game_logs_total"] or 0,
                players_with_game_logs=row["players_with_game_logs"] or 0,
                refreshed_at=row["refreshed_at"],
            )
            seasons.append(season)

            if row["refreshed_at"] and (
                latest_refresh is None or row["refreshed_at"] > latest_refresh
            ):
                latest_refresh = row["refreshed_at"]

        return CoverageResponse(
            seasons=seasons,
            refreshed_at=latest_refresh or datetime.now(UTC),
        )

    # No game_type filter - use materialized view for performance
    if season_ids:
        # Filter to specific seasons
        query = """
            SELECT
                season_id, season_label, is_current,
                games_scheduled, games_final, games_total,
                boxscore_expected, boxscore_actual, boxscore_pct,
                pbp_expected, pbp_actual, pbp_pct,
                shifts_expected, shifts_actual, shifts_pct,
                players_expected, players_actual, players_pct,
                html_expected, html_actual, html_pct,
                game_logs_total, players_with_game_logs,
                refreshed_at
            FROM mv_data_coverage
            WHERE season_id = ANY($1::int[])
            ORDER BY season_id DESC
        """
        rows = await db.fetch(query, season_ids)
    elif include_all:
        # Get all seasons
        query = """
            SELECT
                season_id, season_label, is_current,
                games_scheduled, games_final, games_total,
                boxscore_expected, boxscore_actual, boxscore_pct,
                pbp_expected, pbp_actual, pbp_pct,
                shifts_expected, shifts_actual, shifts_pct,
                players_expected, players_actual, players_pct,
                html_expected, html_actual, html_pct,
                game_logs_total, players_with_game_logs,
                refreshed_at
            FROM mv_data_coverage
            ORDER BY season_id DESC
        """
        rows = await db.fetch(query)
    else:
        # Default: current season plus last 2 seasons (3 total)
        query = """
            SELECT
                season_id, season_label, is_current,
                games_scheduled, games_final, games_total,
                boxscore_expected, boxscore_actual, boxscore_pct,
                pbp_expected, pbp_actual, pbp_pct,
                shifts_expected, shifts_actual, shifts_pct,
                players_expected, players_actual, players_pct,
                html_expected, html_actual, html_pct,
                game_logs_total, players_with_game_logs,
                refreshed_at
            FROM mv_data_coverage
            ORDER BY season_id DESC
            LIMIT 3
        """
        rows = await db.fetch(query)

    # Build response from MV rows
    mv_seasons: list[SeasonCoverage] = []
    mv_latest_refresh: datetime | None = None

    for row in rows:
        row_season_id = row["season_id"]
        categories = _build_categories(dict(row), row_season_id)

        mv_season = SeasonCoverage(
            season_id=row_season_id,
            season_label=row["season_label"] or f"{row_season_id}",
            is_current=row["is_current"] or False,
            categories=categories,
            game_logs_total=row["game_logs_total"] or 0,
            players_with_game_logs=row["players_with_game_logs"] or 0,
            refreshed_at=row["refreshed_at"],
        )
        mv_seasons.append(mv_season)

        # Track latest refresh time
        if row["refreshed_at"] and (
            mv_latest_refresh is None or row["refreshed_at"] > mv_latest_refresh
        ):
            mv_latest_refresh = row["refreshed_at"]

    return CoverageResponse(
        seasons=mv_seasons,
        refreshed_at=mv_latest_refresh or datetime.now(UTC),
    )
