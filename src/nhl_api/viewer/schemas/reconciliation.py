"""Reconciliation API Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# =============================================================================
# Reconciliation Checks
# =============================================================================


class ReconciliationCheck(BaseModel):
    """Single reconciliation check result."""

    rule_name: str = Field(description="Name of the validation rule")
    passed: bool = Field(description="Whether the check passed")
    source_a: str = Field(description="First data source name")
    source_a_value: Any = Field(description="Value from first source")
    source_b: str = Field(description="Second data source name")
    source_b_value: Any = Field(description="Value from second source")
    difference: float | None = Field(
        default=None, description="Numeric difference if applicable"
    )
    entity_type: Literal["game", "player", "team", "event"] = Field(
        description="Type of entity being checked"
    )
    entity_id: str = Field(description="ID of the entity")


# =============================================================================
# Game Reconciliation
# =============================================================================


class GameReconciliation(BaseModel):
    """Reconciliation results for a single game."""

    game_id: int = Field(description="NHL game ID")
    game_date: date = Field(description="Date of the game")
    home_team: str = Field(description="Home team abbreviation")
    away_team: str = Field(description="Away team abbreviation")
    checks_passed: int = Field(ge=0, description="Number of checks that passed")
    checks_failed: int = Field(ge=0, description="Number of checks that failed")
    discrepancies: list[ReconciliationCheck] = Field(
        default_factory=list, description="List of failed checks with details"
    )


class GameReconciliationDetail(GameReconciliation):
    """Detailed game reconciliation with all checks."""

    all_checks: list[ReconciliationCheck] = Field(
        default_factory=list, description="All checks (passed and failed)"
    )
    sources_available: list[str] = Field(
        default_factory=list, description="Data sources available for this game"
    )
    sources_missing: list[str] = Field(
        default_factory=list, description="Expected data sources that are missing"
    )


# =============================================================================
# Summary Statistics
# =============================================================================


class ReconciliationSummary(BaseModel):
    """Summary statistics for reconciliation dashboard."""

    season_id: int = Field(description="Season ID (e.g., 20242025)")
    total_games: int = Field(ge=0, description="Total games in season")
    games_with_discrepancies: int = Field(
        ge=0, description="Games with at least one discrepancy"
    )
    total_checks: int = Field(ge=0, description="Total checks performed")
    passed_checks: int = Field(ge=0, description="Number of passed checks")
    failed_checks: int = Field(ge=0, description="Number of failed checks")
    pass_rate: float = Field(
        ge=0.0, le=1.0, description="Pass rate as decimal (0.0-1.0)"
    )
    goal_reconciliation_rate: float = Field(
        ge=0.0, le=1.0, description="Goal check pass rate"
    )
    penalty_reconciliation_rate: float = Field(
        ge=0.0, le=1.0, description="Penalty check pass rate"
    )
    toi_reconciliation_rate: float = Field(
        ge=0.0, le=1.0, description="TOI check pass rate"
    )
    problem_games: list[GameReconciliation] = Field(
        default_factory=list, description="Games with most discrepancies"
    )


# =============================================================================
# Dashboard Response
# =============================================================================


class ReconciliationDashboardResponse(BaseModel):
    """Complete reconciliation dashboard response."""

    summary: ReconciliationSummary = Field(description="Summary statistics")
    last_run: datetime | None = Field(
        default=None, description="When reconciliation was last run"
    )
    quality_score: float = Field(
        ge=0.0, le=100.0, description="Overall data quality score (0-100)"
    )
    timestamp: datetime = Field(description="Response timestamp")


# =============================================================================
# Games List Response
# =============================================================================


class ReconciliationGamesResponse(BaseModel):
    """Paginated list of games with reconciliation status."""

    games: list[GameReconciliation] = Field(description="List of game reconciliations")
    total: int = Field(ge=0, description="Total games matching filters")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    pages: int = Field(ge=0, description="Total number of pages")


# =============================================================================
# Batch Reconciliation
# =============================================================================


class BatchReconciliationRequest(BaseModel):
    """Request to trigger batch reconciliation."""

    season_id: int = Field(description="Season to reconcile (e.g., 20242025)")
    force: bool = Field(
        default=False, description="Force re-run even if already reconciled"
    )


class BatchReconciliationResponse(BaseModel):
    """Response after triggering batch reconciliation."""

    run_id: int = Field(description="ID of the validation run")
    status: Literal["started", "queued", "already_running"] = Field(
        description="Status of the request"
    )
    message: str = Field(description="Human-readable status message")
