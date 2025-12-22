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
) -> CoverageResponse:
    """Get data coverage summary from materialized view.

    Returns coverage statistics showing data completeness ("gas tank" levels)
    for each season across multiple categories: games, boxscore, pbp, shifts,
    players, and HTML reports.
    """
    # Build the query based on filters
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

    # Build response
    seasons = []
    latest_refresh: datetime | None = None

    for row in rows:
        season_id = row["season_id"]
        categories = _build_categories(dict(row), season_id)

        season = SeasonCoverage(
            season_id=season_id,
            season_label=row["season_label"] or f"{season_id}",
            is_current=row["is_current"] or False,
            categories=categories,
            game_logs_total=row["game_logs_total"] or 0,
            players_with_game_logs=row["players_with_game_logs"] or 0,
            refreshed_at=row["refreshed_at"],
        )
        seasons.append(season)

        # Track latest refresh time
        if row["refreshed_at"] and (
            latest_refresh is None or row["refreshed_at"] > latest_refresh
        ):
            latest_refresh = row["refreshed_at"]

    return CoverageResponse(
        seasons=seasons,
        refreshed_at=latest_refresh or datetime.now(UTC),
    )
