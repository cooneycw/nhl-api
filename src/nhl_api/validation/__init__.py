"""Internal consistency validation for NHL API data.

This package provides validators that check data consistency within each source,
complementing the cross-source reconciliation service.

Example usage:
    from nhl_api.validation import InternalConsistencyValidator

    validator = InternalConsistencyValidator()
    results = validator.validate_boxscore(boxscore_data)

    for result in results:
        if not result.passed:
            print(f"{result.severity}: {result.message}")
"""

from nhl_api.validation.internal_consistency import InternalConsistencyValidator
from nhl_api.validation.results import (
    InternalValidationResult,
    ValidationSummary,
    make_failed,
    make_passed,
)

__all__ = [
    "InternalConsistencyValidator",
    "InternalValidationResult",
    "ValidationSummary",
    "make_passed",
    "make_failed",
]
