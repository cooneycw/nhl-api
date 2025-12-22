"""Data validation endpoints.

Provides endpoints for:
- Validation rules listing
- Validation run history and results
- Data quality scores by entity
- Discrepancy management and tracking
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db
from nhl_api.viewer.schemas.validation import (
    DiscrepanciesResponse,
    DiscrepancyDetail,
    QualityScore,
    QualityScoresResponse,
    ValidationRulesResponse,
    ValidationRunDetail,
    ValidationRunsResponse,
)
from nhl_api.viewer.services.validation_service import ValidationService

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(prefix="/validation", tags=["validation"])

# Singleton service instance
_service = ValidationService()


# =============================================================================
# Validation Rules
# =============================================================================


@router.get(
    "/rules",
    response_model=ValidationRulesResponse,
    status_code=status.HTTP_200_OK,
    summary="List Validation Rules",
    description="Get all validation rules with optional filters",
)
async def get_validation_rules(
    db: DbDep,
    category: str | None = Query(
        None,
        description="Filter by category: cross_file, internal, completeness, accuracy",
        pattern="^(cross_file|internal|completeness|accuracy)$",
    ),
    is_active: bool | None = Query(
        None,
        description="Filter by active status",
    ),
) -> ValidationRulesResponse:
    """Get all validation rules.

    Returns a list of all configured validation rules.
    Optionally filter by category or active status.
    """
    return await _service.get_validation_rules(
        db,
        category=category,
        is_active=is_active,
    )


# =============================================================================
# Validation Runs
# =============================================================================


@router.get(
    "/runs",
    response_model=ValidationRunsResponse,
    status_code=status.HTTP_200_OK,
    summary="List Validation Runs",
    description="Get paginated list of validation runs with status",
)
async def get_validation_runs(
    db: DbDep,
    season_id: int | None = Query(
        None,
        description="Filter by season ID (e.g., 20242025)",
        ge=20102011,
        le=20302031,
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> ValidationRunsResponse:
    """Get paginated list of validation runs.

    Returns runs sorted by start time (most recent first).
    Each run includes summary counts of passed/failed checks.
    """
    return await _service.get_validation_runs(
        db,
        season_id=season_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/runs/{run_id}",
    response_model=ValidationRunDetail,
    status_code=status.HTTP_200_OK,
    summary="Validation Run Detail",
    description="Get detailed validation run with rule results",
)
async def get_validation_run(
    db: DbDep,
    run_id: int,
) -> ValidationRunDetail:
    """Get detailed validation run with results.

    Returns the run summary plus all individual validation results.
    Results are sorted with failures first.
    """
    try:
        return await _service.get_validation_run(db, run_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None


# =============================================================================
# Quality Scores
# =============================================================================


@router.get(
    "/scores",
    response_model=QualityScoresResponse,
    status_code=status.HTTP_200_OK,
    summary="List Quality Scores",
    description="Get quality scores by entity type",
)
async def get_quality_scores(
    db: DbDep,
    season_id: int | None = Query(
        None,
        description="Filter by season ID (e.g., 20242025)",
        ge=20102011,
        le=20302031,
    ),
    entity_type: Literal["season", "game"] | None = Query(
        None,
        description="Filter by entity type: season or game",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> QualityScoresResponse:
    """Get paginated list of quality scores.

    Returns scores sorted by overall score (lowest first).
    Includes completeness, accuracy, consistency, and timeliness dimensions.
    """
    return await _service.get_quality_scores(
        db,
        season_id=season_id,
        entity_type=entity_type,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/scores/{entity_type}/{entity_id}",
    response_model=QualityScore,
    status_code=status.HTTP_200_OK,
    summary="Entity Quality Score",
    description="Get quality score for a specific entity",
)
async def get_entity_score(
    db: DbDep,
    entity_type: Literal["season", "game"],
    entity_id: str,
) -> QualityScore:
    """Get quality score for a specific entity.

    Entity type can be 'season' or 'game'.
    For seasons, entity_id is the season ID (e.g., 20242025).
    For games, entity_id is the game ID.
    """
    try:
        return await _service.get_entity_score(db, entity_type, entity_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None


# =============================================================================
# Discrepancies
# =============================================================================


@router.get(
    "/discrepancies",
    response_model=DiscrepanciesResponse,
    status_code=status.HTTP_200_OK,
    summary="List Discrepancies",
    description="Get cross-source data mismatches",
)
async def get_discrepancies(
    db: DbDep,
    season_id: int | None = Query(
        None,
        description="Filter by season ID (e.g., 20242025)",
        ge=20102011,
        le=20302031,
    ),
    status_filter: Literal["open", "resolved", "ignored"] | None = Query(
        None,
        alias="status",
        description="Filter by resolution status",
    ),
    entity_type: str | None = Query(
        None,
        description="Filter by entity type (goal, assist, player, shift, etc.)",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> DiscrepanciesResponse:
    """Get paginated list of discrepancies.

    Returns discrepancies sorted by creation time (most recent first).
    Filter by season, resolution status, or entity type.
    """
    return await _service.get_discrepancies(
        db,
        season_id=season_id,
        status=status_filter,
        entity_type=entity_type,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/discrepancies/{discrepancy_id}",
    response_model=DiscrepancyDetail,
    status_code=status.HTTP_200_OK,
    summary="Discrepancy Detail",
    description="Get discrepancy detail with source values",
)
async def get_discrepancy(
    db: DbDep,
    discrepancy_id: int,
) -> DiscrepancyDetail:
    """Get detailed discrepancy with source values.

    Includes the actual values from each source that caused the discrepancy,
    plus any resolution notes.
    """
    try:
        return await _service.get_discrepancy(db, discrepancy_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
