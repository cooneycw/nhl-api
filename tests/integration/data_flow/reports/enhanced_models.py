"""Enhanced data models for comprehensive validation reports.

This module extends the basic data flow report models to include
validation results from all stages: download, storage, view, and reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from nhl_api.validation.results import InternalValidationResult, ValidationSummary
    from tests.integration.data_flow.reports.models import DataFlowReport


@dataclass(frozen=True, slots=True)
class ValidationStageResult:
    """Result from a validation stage (internal, cross-source, etc.).

    Attributes:
        stage_name: Name of the validation stage
        total_checks: Total validation checks performed
        passed: Number of checks that passed
        failed: Number of checks that failed (severity=error)
        warnings: Number of warnings (severity=warning)
        discrepancies: List of specific validation failures
    """

    stage_name: str
    total_checks: int
    passed: int
    failed: int
    warnings: int
    discrepancies: tuple[InternalValidationResult, ...] = field(default_factory=tuple)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total_checks == 0:
            return 0.0
        return (self.passed / self.total_checks) * 100


@dataclass
class ComprehensiveValidationReport:
    """Complete validation report for a game across all stages.

    This extends DataFlowReport with validation results from:
    - Download stage (source availability)
    - Storage stage (table population, data types, FK constraints)
    - View stage (API endpoint accessibility)
    - Internal consistency (data validity within each source)
    - Cross-source reconciliation (JSON vs JSON, JSON vs HTML)

    Attributes:
        game_id: Game ID being validated
        season_id: Season ID
        test_id: Unique identifier for this validation run
        generated_at: Timestamp when report was generated
        data_flow_report: Basic download + storage results
        internal_consistency: Results from internal consistency validators
        json_cross_validation: Results from JSON cross-source validation (optional)
        json_html_validation: Results from JSON vs HTML validation (optional)
        view_stage: Results from view stage validation (optional)
    """

    game_id: int
    season_id: int | None = None
    test_id: str = field(default_factory=lambda: str(uuid4())[:8])
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    data_flow_report: DataFlowReport | None = None
    internal_consistency: dict[str, ValidationSummary] = field(default_factory=dict)
    json_cross_validation: ValidationStageResult | None = None
    json_html_validation: ValidationStageResult | None = None
    view_stage: ValidationStageResult | None = None

    @property
    def total_checks(self) -> int:
        """Total validation checks across all stages."""
        total = 0
        # Internal consistency
        for summary in self.internal_consistency.values():
            total += summary.total_checks
        # Cross-source validation
        if self.json_cross_validation:
            total += self.json_cross_validation.total_checks
        if self.json_html_validation:
            total += self.json_html_validation.total_checks
        if self.view_stage:
            total += self.view_stage.total_checks
        return total

    @property
    def passed_checks(self) -> int:
        """Total passed checks across all stages."""
        passed = 0
        for summary in self.internal_consistency.values():
            passed += summary.passed
        if self.json_cross_validation:
            passed += self.json_cross_validation.passed
        if self.json_html_validation:
            passed += self.json_html_validation.passed
        if self.view_stage:
            passed += self.view_stage.passed
        return passed

    @property
    def failed_checks(self) -> int:
        """Total failed checks (errors) across all stages."""
        failed = 0
        for summary in self.internal_consistency.values():
            failed += summary.failed
        if self.json_cross_validation:
            failed += self.json_cross_validation.failed
        if self.json_html_validation:
            failed += self.json_html_validation.failed
        if self.view_stage:
            failed += self.view_stage.failed
        return failed

    @property
    def warning_checks(self) -> int:
        """Total warnings across all stages."""
        warnings = 0
        for summary in self.internal_consistency.values():
            warnings += summary.warnings
        if self.json_cross_validation:
            warnings += self.json_cross_validation.warnings
        if self.json_html_validation:
            warnings += self.json_html_validation.warnings
        if self.view_stage:
            warnings += self.view_stage.warnings
        return warnings

    @property
    def pass_rate(self) -> float:
        """Overall pass rate as percentage."""
        if self.total_checks == 0:
            return 0.0
        return (self.passed_checks / self.total_checks) * 100

    def add_internal_consistency_result(
        self, source_name: str, summary: ValidationSummary
    ) -> None:
        """Add an internal consistency validation summary.

        Args:
            source_name: Name of the source (boxscore, pbp, etc.)
            summary: ValidationSummary with results
        """
        self.internal_consistency[source_name] = summary

    def get_all_discrepancies(self) -> list[InternalValidationResult]:
        """Get all validation failures across all stages.

        Returns:
            List of all failed validation results
        """
        discrepancies: list[InternalValidationResult] = []

        # Internal consistency failures
        for summary in self.internal_consistency.values():
            for result in summary.results:
                if not result.passed:
                    discrepancies.append(result)

        # Cross-source validation failures
        if self.json_cross_validation:
            discrepancies.extend(self.json_cross_validation.discrepancies)
        if self.json_html_validation:
            discrepancies.extend(self.json_html_validation.discrepancies)
        if self.view_stage:
            discrepancies.extend(self.view_stage.discrepancies)

        return discrepancies

    def get_discrepancies_by_severity(
        self, severity: str
    ) -> list[InternalValidationResult]:
        """Get validation failures filtered by severity level.

        Args:
            severity: Severity level to filter by ("error", "warning", "info")

        Returns:
            List of validation results matching the severity
        """
        return [d for d in self.get_all_discrepancies() if d.severity == severity]
