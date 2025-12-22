"""Validation result dataclasses.

Provides standardized result types for internal consistency validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class InternalValidationResult:
    """Result of a single internal consistency check.

    Attributes:
        rule_name: Unique identifier for the validation rule (e.g., "boxscore_goals_sum")
        passed: Whether the validation check passed
        severity: Importance level - "error" for data corruption, "warning" for
                  inconsistencies, "info" for minor issues
        message: Human-readable description of the result
        details: Structured data for debugging (actual values, expected values, etc.)
        source_type: Type of data source (e.g., "boxscore", "pbp", "shifts")
        entity_id: Identifier for the entity being validated (e.g., game_id)
    """

    rule_name: str
    passed: bool
    severity: Severity
    message: str
    details: dict[str, Any] | None = None
    source_type: str = ""
    entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Summary of validation run on a single entity.

    Attributes:
        source_type: Type of data source validated
        entity_id: Identifier for the entity (e.g., game_id)
        total_checks: Total number of validation checks performed
        passed: Number of checks that passed
        failed: Number of checks that failed (severity=error)
        warnings: Number of warnings (severity=warning)
        results: Tuple of all individual validation results
    """

    source_type: str
    entity_id: str
    total_checks: int
    passed: int
    failed: int
    warnings: int
    results: tuple[InternalValidationResult, ...] = field(default_factory=tuple)

    @classmethod
    def from_results(
        cls,
        source_type: str,
        entity_id: str,
        results: list[InternalValidationResult],
    ) -> ValidationSummary:
        """Create a summary from a list of validation results.

        Args:
            source_type: Type of data source validated
            entity_id: Identifier for the entity
            results: List of individual validation results

        Returns:
            ValidationSummary with aggregated counts
        """
        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        failed_count = sum(1 for r in results if not r.passed and r.severity == "error")
        warning_count = sum(
            1 for r in results if not r.passed and r.severity == "warning"
        )

        return cls(
            source_type=source_type,
            entity_id=entity_id,
            total_checks=total,
            passed=passed_count,
            failed=failed_count,
            warnings=warning_count,
            results=tuple(results),
        )


def make_passed(
    rule_name: str,
    source_type: str,
    message: str = "",
    entity_id: str | None = None,
    severity: Severity = "info",
) -> InternalValidationResult:
    """Create a passing validation result.

    Args:
        rule_name: Unique rule identifier
        source_type: Type of data source
        message: Optional success message
        entity_id: Optional entity identifier
        severity: Severity level (default "info" for passed checks)

    Returns:
        InternalValidationResult with passed=True
    """
    return InternalValidationResult(
        rule_name=rule_name,
        passed=True,
        severity=severity,
        message=message or f"{rule_name} passed",
        source_type=source_type,
        entity_id=entity_id,
    )


def make_failed(
    rule_name: str,
    source_type: str,
    message: str,
    severity: Severity = "error",
    details: dict[str, Any] | None = None,
    entity_id: str | None = None,
) -> InternalValidationResult:
    """Create a failing validation result.

    Args:
        rule_name: Unique rule identifier
        source_type: Type of data source
        message: Description of the failure
        severity: Severity level (default "error")
        details: Structured data about the failure
        entity_id: Optional entity identifier

    Returns:
        InternalValidationResult with passed=False
    """
    return InternalValidationResult(
        rule_name=rule_name,
        passed=False,
        severity=severity,
        message=message,
        details=details,
        source_type=source_type,
        entity_id=entity_id,
    )
