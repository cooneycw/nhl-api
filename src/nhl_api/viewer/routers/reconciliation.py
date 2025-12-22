"""Reconciliation endpoints for cross-source data validation.

Provides endpoints for:
- Dashboard summary with aggregated statistics
- Games list with reconciliation status
- Game-level reconciliation detail
- Batch reconciliation trigger
- Export functionality (CSV/JSON)
"""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db
from nhl_api.viewer.schemas.reconciliation import (
    BatchReconciliationRequest,
    BatchReconciliationResponse,
    GameReconciliationDetail,
    ReconciliationDashboardResponse,
    ReconciliationGamesResponse,
)
from nhl_api.viewer.services.reconciliation_service import ReconciliationService

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

# Singleton service instance
_service = ReconciliationService()


# =============================================================================
# Dashboard Endpoint
# =============================================================================


@router.get(
    "/dashboard",
    response_model=ReconciliationDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Reconciliation Dashboard",
    description="Get aggregated reconciliation statistics for a season",
)
async def get_dashboard(
    db: DbDep,
    season_id: int = Query(
        ...,
        description="Season ID (e.g., 20242025)",
        ge=20102011,
        le=20302031,
    ),
) -> ReconciliationDashboardResponse:
    """Get reconciliation dashboard with summary statistics.

    Includes:
    - Total games and games with discrepancies
    - Pass rates for different check types (goals, TOI, penalties, shots)
    - Top 10 problem games
    - Overall data quality score
    """
    return await _service.get_dashboard_summary(db, season_id)


# =============================================================================
# Games List Endpoint
# =============================================================================


@router.get(
    "/games",
    response_model=ReconciliationGamesResponse,
    status_code=status.HTTP_200_OK,
    summary="Games with Discrepancies",
    description="Get paginated list of games with reconciliation status",
)
async def get_games(
    db: DbDep,
    season_id: int = Query(
        ...,
        description="Season ID (e.g., 20242025)",
        ge=20102011,
        le=20302031,
    ),
    discrepancy_type: str | None = Query(
        None,
        description="Filter by discrepancy type: goal, toi, penalty, shot",
        pattern="^(goal|toi|penalty|shot)$",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> ReconciliationGamesResponse:
    """Get paginated list of games with discrepancies.

    Returns games sorted by number of discrepancies (most first).
    Only games with at least one discrepancy are included.
    """
    return await _service.get_games_with_discrepancies(
        db,
        season_id,
        page=page,
        page_size=page_size,
        discrepancy_type=discrepancy_type,
    )


# =============================================================================
# Game Detail Endpoint
# =============================================================================


@router.get(
    "/games/{game_id}",
    response_model=GameReconciliationDetail,
    status_code=status.HTTP_200_OK,
    summary="Game Reconciliation Detail",
    description="Get detailed reconciliation for a specific game",
)
async def get_game_detail(
    db: DbDep,
    game_id: int,
) -> GameReconciliationDetail:
    """Get detailed reconciliation for a single game.

    Includes all checks (passed and failed), available data sources,
    and missing data sources.
    """
    try:
        return await _service.get_game_reconciliation(db, game_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None


# =============================================================================
# Batch Reconciliation Endpoint
# =============================================================================


@router.post(
    "/run",
    response_model=BatchReconciliationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Batch Reconciliation",
    description="Start batch reconciliation for a season",
)
async def run_batch_reconciliation(
    db: DbDep,
    request: BatchReconciliationRequest,
) -> BatchReconciliationResponse:
    """Trigger batch reconciliation for a season.

    Returns immediately with a run_id that can be used to track progress
    or export results.
    """
    return await _service.run_batch_reconciliation(
        db,
        request.season_id,
        force=request.force,
    )


# =============================================================================
# Export Endpoint
# =============================================================================


@router.get(
    "/export/{run_id}",
    status_code=status.HTTP_200_OK,
    summary="Export Reconciliation Results",
    description="Export reconciliation results as CSV or JSON",
)
async def export_results(
    db: DbDep,
    run_id: int,
    format: Literal["csv", "json"] = Query(
        "json",
        description="Export format: csv or json",
    ),
    season_id: int = Query(
        ...,
        description="Season ID to export (e.g., 20242025)",
        ge=20102011,
        le=20302031,
    ),
) -> StreamingResponse:
    """Export reconciliation results.

    The run_id is currently not used for filtering (results are computed
    on-demand), but is included for future caching/persistence support.
    """
    # Get all games with discrepancies
    games_response = await _service.get_games_with_discrepancies(
        db,
        season_id,
        page=1,
        page_size=10000,  # Get all games
    )

    if format == "json":
        # Export as JSON
        export_data = {
            "run_id": run_id,
            "season_id": season_id,
            "total_games": games_response.total,
            "games": [
                {
                    "game_id": game.game_id,
                    "game_date": game.game_date.isoformat(),
                    "home_team": game.home_team,
                    "away_team": game.away_team,
                    "checks_passed": game.checks_passed,
                    "checks_failed": game.checks_failed,
                    "discrepancies": [
                        {
                            "rule_name": d.rule_name,
                            "source_a": d.source_a,
                            "source_a_value": d.source_a_value,
                            "source_b": d.source_b,
                            "source_b_value": d.source_b_value,
                            "difference": d.difference,
                        }
                        for d in game.discrepancies
                    ],
                }
                for game in games_response.games
            ],
        }

        json_bytes = json.dumps(export_data, indent=2).encode("utf-8")

        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=reconciliation_{season_id}_{run_id}.json"
            },
        )

    else:  # CSV format
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "game_id",
                "game_date",
                "home_team",
                "away_team",
                "checks_passed",
                "checks_failed",
                "rule_name",
                "source_a",
                "source_a_value",
                "source_b",
                "source_b_value",
                "difference",
            ]
        )

        # Write rows - one per discrepancy
        for game in games_response.games:
            if game.discrepancies:
                for d in game.discrepancies:
                    writer.writerow(
                        [
                            game.game_id,
                            game.game_date.isoformat(),
                            game.home_team,
                            game.away_team,
                            game.checks_passed,
                            game.checks_failed,
                            d.rule_name,
                            d.source_a,
                            d.source_a_value,
                            d.source_b,
                            d.source_b_value,
                            d.difference,
                        ]
                    )
            else:
                # Game with no discrepancies (shouldn't happen in filtered list)
                writer.writerow(
                    [
                        game.game_id,
                        game.game_date.isoformat(),
                        game.home_team,
                        game.away_team,
                        game.checks_passed,
                        game.checks_failed,
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )

        csv_bytes = output.getvalue().encode("utf-8")

        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=reconciliation_{season_id}_{run_id}.csv"
            },
        )
