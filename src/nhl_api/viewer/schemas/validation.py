"""Validation API Pydantic schemas.

Provides schemas for:
- Validation rules configuration
- Validation run history and results
- Data quality scores
- Discrepancy tracking and resolution
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# =============================================================================
# Validation Rules
# =============================================================================


class ValidationRule(BaseModel):
    """Validation rule definition."""

    rule_id: int = Field(description="Rule ID")
    name: str = Field(description="Rule name (e.g., 'goal_reconciliation')")
    description: str | None = Field(default=None, description="Rule description")
    category: str = Field(
        description="Rule category: cross_file, internal, completeness, accuracy"
    )
    severity: str = Field(
        default="warning", description="Rule severity: error, warning, info"
    )
    is_active: bool = Field(default=True, description="Whether the rule is active")
    config: dict[str, Any] | None = Field(
        default=None, description="Rule-specific configuration"
    )


class ValidationRulesResponse(BaseModel):
    """List of validation rules."""

    rules: list[ValidationRule] = Field(description="List of validation rules")
    total: int = Field(ge=0, description="Total number of rules")


# =============================================================================
# Validation Results
# =============================================================================


class ValidationResult(BaseModel):
    """Individual validation check result."""

    result_id: int = Field(description="Result ID")
    rule_id: int = Field(description="Associated rule ID")
    rule_name: str = Field(description="Rule name for display")
    game_id: int | None = Field(default=None, description="Game ID if game-specific")
    passed: bool = Field(description="Whether the check passed")
    severity: str | None = Field(default=None, description="Result severity")
    message: str | None = Field(default=None, description="Validation message")
    details: dict[str, Any] | None = Field(
        default=None, description="Structured discrepancy data"
    )
    source_values: dict[str, Any] | None = Field(
        default=None, description="Source comparison values"
    )
    created_at: datetime = Field(description="When the result was created")


# =============================================================================
# Validation Runs
# =============================================================================


class ValidationRunSummary(BaseModel):
    """Summary of a validation run."""

    run_id: int = Field(description="Run ID")
    season_id: int | None = Field(
        default=None, description="Season ID if season-scoped"
    )
    started_at: datetime = Field(description="When the run started")
    completed_at: datetime | None = Field(
        default=None, description="When the run completed"
    )
    status: Literal["running", "completed", "failed"] = Field(description="Run status")
    rules_checked: int = Field(ge=0, default=0, description="Number of rules checked")
    total_passed: int = Field(ge=0, default=0, description="Number of passed checks")
    total_failed: int = Field(ge=0, default=0, description="Number of failed checks")
    total_warnings: int = Field(ge=0, default=0, description="Number of warnings")


class ValidationRunDetail(ValidationRunSummary):
    """Detailed validation run with results."""

    results: list[ValidationResult] = Field(
        default_factory=list, description="Validation results for this run"
    )
    metadata: dict[str, Any] | None = Field(default=None, description="Run metadata")


class ValidationRunsResponse(BaseModel):
    """Paginated list of validation runs."""

    runs: list[ValidationRunSummary] = Field(description="List of validation runs")
    total: int = Field(ge=0, description="Total runs matching filters")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    pages: int = Field(ge=0, description="Total number of pages")


# =============================================================================
# Quality Scores
# =============================================================================


class QualityScore(BaseModel):
    """Data quality score for an entity."""

    score_id: int = Field(description="Score record ID")
    season_id: int = Field(description="Season ID")
    game_id: int | None = Field(default=None, description="Game ID if game-specific")
    entity_type: Literal["season", "game"] = Field(
        description="Type of entity being scored"
    )
    entity_id: str = Field(description="Entity identifier")

    # Quality dimensions (0-100 scale)
    completeness_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Data completeness (0-100)"
    )
    accuracy_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Data accuracy (0-100)"
    )
    consistency_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Cross-source consistency (0-100)"
    )
    timeliness_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Data freshness (0-100)"
    )
    overall_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Overall quality (0-100)"
    )

    # Check counts
    total_checks: int = Field(ge=0, default=0, description="Total checks performed")
    passed_checks: int = Field(ge=0, default=0, description="Number of passed checks")
    failed_checks: int = Field(ge=0, default=0, description="Number of failed checks")
    warning_checks: int = Field(ge=0, default=0, description="Number of warnings")

    calculated_at: datetime = Field(description="When the score was calculated")


class QualityScoresResponse(BaseModel):
    """Paginated list of quality scores."""

    scores: list[QualityScore] = Field(description="List of quality scores")
    total: int = Field(ge=0, description="Total scores matching filters")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    pages: int = Field(ge=0, description="Total number of pages")


# =============================================================================
# Discrepancies
# =============================================================================


class DiscrepancySummary(BaseModel):
    """Summary of a data discrepancy."""

    discrepancy_id: int = Field(description="Discrepancy ID")
    rule_id: int = Field(description="Associated rule ID")
    rule_name: str = Field(description="Rule name for display")
    game_id: int | None = Field(default=None, description="Game ID if game-specific")
    season_id: int | None = Field(default=None, description="Season ID")
    entity_type: str | None = Field(
        default=None, description="Entity type: goal, assist, player, shift, etc."
    )
    entity_id: str | None = Field(default=None, description="Entity identifier")
    field_name: str | None = Field(default=None, description="Field with discrepancy")
    source_a: str | None = Field(default=None, description="First source name")
    source_b: str | None = Field(default=None, description="Second source name")
    resolution_status: Literal["open", "resolved", "ignored"] = Field(
        default="open", description="Resolution status"
    )
    created_at: datetime = Field(description="When the discrepancy was found")


class DiscrepancyDetail(DiscrepancySummary):
    """Detailed discrepancy with source values."""

    source_a_value: str | None = Field(
        default=None, description="Value from first source"
    )
    source_b_value: str | None = Field(
        default=None, description="Value from second source"
    )
    resolution_notes: str | None = Field(
        default=None, description="Notes on resolution"
    )
    resolved_at: datetime | None = Field(
        default=None, description="When the discrepancy was resolved"
    )
    result_id: int | None = Field(
        default=None, description="Associated validation result ID"
    )


class DiscrepanciesResponse(BaseModel):
    """Paginated list of discrepancies."""

    discrepancies: list[DiscrepancySummary] = Field(description="List of discrepancies")
    total: int = Field(ge=0, description="Total discrepancies matching filters")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    pages: int = Field(ge=0, description="Total number of pages")
