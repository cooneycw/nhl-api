"""Cross-source validation for NHL API data.

This module provides a validator that checks data consistency across multiple
JSON API sources for the same game:
- Play-by-Play vs Boxscore: goals, shots
- Shift Chart vs Boxscore: TOI, shift counts
- Schedule vs Boxscore: final scores

Example usage:
    from nhl_api.validation import CrossSourceValidator

    validator = CrossSourceValidator()

    # Validate PBP against Boxscore
    results = validator.validate_pbp_vs_boxscore(pbp, boxscore)

    # Validate all available sources
    results = validator.validate_all(
        pbp=pbp_data,
        boxscore=boxscore_data,
        shifts=shift_data,
        schedule=schedule_data,
    )

    for result in results:
        if not result.passed:
            print(f"{result.severity}: {result.message}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nhl_api.validation.constants import SOURCE_CROSS
from nhl_api.validation.results import InternalValidationResult, ValidationSummary
from nhl_api.validation.rules.cross_source import (
    validate_final_score_schedule_vs_boxscore,
    validate_goals_pbp_vs_boxscore,
    validate_shift_count_shifts_vs_boxscore,
    validate_shots_pbp_vs_boxscore,
    validate_toi_shifts_vs_boxscore,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.nhl_json.boxscore import ParsedBoxscore
    from nhl_api.downloaders.sources.nhl_json.play_by_play import ParsedPlayByPlay
    from nhl_api.downloaders.sources.nhl_json.schedule import GameInfo
    from nhl_api.models.shifts import ParsedShiftChart


class CrossSourceValidator:
    """Validator for cross-source data consistency.

    Validates that data is consistent across multiple sources for the same game:
    - Goals: PBP events match Boxscore scores
    - Shots: PBP shot events ~ Boxscore team shots
    - TOI: Shift chart TOI ~ Boxscore player TOI
    - Shift count: Shift chart shifts ~ Boxscore player shifts
    - Final score: Schedule matches Boxscore

    Example:
        validator = CrossSourceValidator()
        results = validator.validate_pbp_vs_boxscore(pbp, boxscore)

        for result in results:
            if not result.passed:
                print(f"{result.severity}: {result.message}")

    Attributes:
        None - stateless validator
    """

    def validate_pbp_vs_boxscore(
        self,
        pbp: ParsedPlayByPlay,
        boxscore: ParsedBoxscore,
    ) -> list[InternalValidationResult]:
        """Validate PBP data against Boxscore.

        Checks:
        - Goal counts match (exact match required)
        - Shot counts match (with tolerance of +/-2)

        Args:
            pbp: Parsed play-by-play data
            boxscore: Parsed boxscore data

        Returns:
            List of validation results
        """
        results: list[InternalValidationResult] = []
        results.extend(validate_goals_pbp_vs_boxscore(pbp, boxscore))
        results.extend(validate_shots_pbp_vs_boxscore(pbp, boxscore))
        return results

    def validate_shifts_vs_boxscore(
        self,
        shifts: ParsedShiftChart,
        boxscore: ParsedBoxscore,
    ) -> list[InternalValidationResult]:
        """Validate Shift Chart data against Boxscore.

        Checks:
        - Player TOI matches (with tolerance of +/-5 seconds)
        - Player shift counts match (with tolerance of +/-1)

        Args:
            shifts: Parsed shift chart data
            boxscore: Parsed boxscore data

        Returns:
            List of validation results
        """
        results: list[InternalValidationResult] = []
        results.extend(validate_toi_shifts_vs_boxscore(shifts, boxscore))
        results.extend(validate_shift_count_shifts_vs_boxscore(shifts, boxscore))
        return results

    def validate_schedule_vs_boxscore(
        self,
        schedule: GameInfo,
        boxscore: ParsedBoxscore,
    ) -> list[InternalValidationResult]:
        """Validate Schedule data against Boxscore.

        Checks:
        - Final scores match (exact match required)

        Args:
            schedule: Game info from schedule
            boxscore: Parsed boxscore data

        Returns:
            List of validation results
        """
        return validate_final_score_schedule_vs_boxscore(schedule, boxscore)

    def validate_all(
        self,
        pbp: ParsedPlayByPlay | None = None,
        boxscore: ParsedBoxscore | None = None,
        shifts: ParsedShiftChart | None = None,
        schedule: Any | None = None,
    ) -> list[InternalValidationResult]:
        """Run all available cross-source validations.

        Only runs validations where all required sources are provided.
        Boxscore is required as the reference source for all validations.

        Args:
            pbp: Parsed play-by-play data (optional)
            boxscore: Parsed boxscore data (required for any validation)
            shifts: Parsed shift chart data (optional)
            schedule: Game info from schedule (optional)

        Returns:
            List of all validation results
        """
        results: list[InternalValidationResult] = []

        # Boxscore is required for all validations
        if boxscore is None:
            return results

        # PBP vs Boxscore validations
        if pbp is not None:
            results.extend(self.validate_pbp_vs_boxscore(pbp, boxscore))

        # Shifts vs Boxscore validations
        if shifts is not None:
            results.extend(self.validate_shifts_vs_boxscore(shifts, boxscore))

        # Schedule vs Boxscore validations
        if schedule is not None:
            results.extend(self.validate_schedule_vs_boxscore(schedule, boxscore))

        return results

    def get_summary(
        self,
        game_id: int,
        results: list[InternalValidationResult],
    ) -> ValidationSummary:
        """Get validation summary for cross-source checks.

        Args:
            game_id: NHL game ID
            results: List of validation results to summarize

        Returns:
            ValidationSummary with aggregated counts
        """
        return ValidationSummary.from_results(
            source_type=SOURCE_CROSS,
            entity_id=str(game_id),
            results=results,
        )
