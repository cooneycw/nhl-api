"""Validation for NHL API data.

This package provides validators for:
- Internal consistency: Check data consistency within each source
- Cross-source: Check data consistency across multiple sources

Example usage:
    from nhl_api.validation import InternalConsistencyValidator, CrossSourceValidator

    # Internal consistency validation
    internal = InternalConsistencyValidator()
    results = internal.validate_boxscore(boxscore_data)

    # Cross-source validation
    cross = CrossSourceValidator()
    results = cross.validate_pbp_vs_boxscore(pbp_data, boxscore_data)

    for result in results:
        if not result.passed:
            print(f"{result.severity}: {result.message}")
"""

from nhl_api.validation.cross_source_validator import CrossSourceValidator
from nhl_api.validation.internal_consistency import InternalConsistencyValidator
from nhl_api.validation.results import (
    InternalValidationResult,
    ValidationSummary,
    make_failed,
    make_passed,
)

__all__ = [
    "CrossSourceValidator",
    "InternalConsistencyValidator",
    "InternalValidationResult",
    "ValidationSummary",
    "make_passed",
    "make_failed",
]
