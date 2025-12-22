"""Internal consistency validator for NHL API data.

Validates data consistency within each source (not cross-source validation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nhl_api.validation.constants import (
    SOURCE_BOXSCORE,
    SOURCE_HTML_ES,
    SOURCE_HTML_FS,
    SOURCE_HTML_GS,
    SOURCE_HTML_SS,
    SOURCE_HTML_TOI,
    SOURCE_PBP,
    SOURCE_SHIFTS,
    SOURCE_STANDINGS,
)
from nhl_api.validation.results import InternalValidationResult, ValidationSummary
from nhl_api.validation.rules import (
    validate_boxscore,
    validate_event_summary,
    validate_faceoff_summary,
    validate_game_summary,
    validate_play_by_play,
    validate_shift_chart,
    validate_shot_summary,
    validate_standings,
    validate_time_on_ice,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.html.event_summary import ParsedEventSummary
    from nhl_api.downloaders.sources.html.faceoff_summary import ParsedFaceoffSummary
    from nhl_api.downloaders.sources.html.game_summary import ParsedGameSummary
    from nhl_api.downloaders.sources.html.shot_summary import ParsedShotSummary
    from nhl_api.downloaders.sources.html.time_on_ice import ParsedTimeOnIce
    from nhl_api.downloaders.sources.nhl_json.boxscore import ParsedBoxscore
    from nhl_api.downloaders.sources.nhl_json.play_by_play import ParsedPlayByPlay
    from nhl_api.downloaders.sources.nhl_json.standings import ParsedStandings
    from nhl_api.models.shifts import ParsedShiftChart


class InternalConsistencyValidator:
    """Validator for internal data consistency.

    Validates that data within each source is self-consistent:
    - Boxscore: player stats sum to team totals, points = goals + assists
    - Play-by-play: valid time ranges, chronological events, assist counts
    - Shift charts: valid durations, no overlaps, sequential numbering
    - Standings: GP = W + L + OTL, points = W*2 + OTL
    - HTML reports: internal sums match totals

    Example:
        validator = InternalConsistencyValidator()
        results = validator.validate_boxscore(boxscore)

        for result in results:
            if not result.passed:
                print(f"{result.severity}: {result.message}")
    """

    def validate_boxscore(
        self, boxscore: ParsedBoxscore
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of boxscore data.

        Checks:
        - Player points = goals + assists
        - Team goals = sum of player goals
        - Shots >= goals
        - PP goals <= total goals
        - Valid percentage ranges

        Args:
            boxscore: Parsed boxscore data

        Returns:
            List of validation results
        """
        return validate_boxscore(boxscore)

    def validate_play_by_play(
        self, pbp: ParsedPlayByPlay
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of play-by-play data.

        Checks:
        - 0-2 assists per goal
        - Valid period time ranges
        - Chronological event ordering
        - Sequential period numbers
        - Non-decreasing scores and SOG

        Args:
            pbp: Parsed play-by-play data

        Returns:
            List of validation results
        """
        return validate_play_by_play(pbp)

    def validate_shift_chart(
        self, shifts: ParsedShiftChart
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of shift chart data.

        Checks:
        - End time > start time
        - Duration matches time difference
        - No overlapping shifts for same player
        - Valid period numbers
        - Sequential shift numbers

        Args:
            shifts: Parsed shift chart data

        Returns:
            List of validation results
        """
        return validate_shift_chart(shifts)

    def validate_standings(
        self, standings: ParsedStandings
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of standings data.

        Checks:
        - GP = W + L + OTL
        - Points = W*2 + OTL
        - Goal differential = GF - GA
        - Win breakdown consistency
        - Valid percentage ranges

        Args:
            standings: Parsed standings data

        Returns:
            List of validation results
        """
        return validate_standings(standings)

    def validate_event_summary(
        self, event_summary: ParsedEventSummary
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of HTML event summary.

        Checks:
        - Player stats sum to team totals

        Args:
            event_summary: Parsed event summary data

        Returns:
            List of validation results
        """
        return validate_event_summary(event_summary)

    def validate_game_summary(
        self, game_summary: ParsedGameSummary
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of HTML game summary.

        Checks:
        - Period goals sum to final score

        Args:
            game_summary: Parsed game summary data

        Returns:
            List of validation results
        """
        return validate_game_summary(game_summary)

    def validate_faceoff_summary(
        self, faceoff_summary: ParsedFaceoffSummary
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of HTML faceoff summary.

        Checks:
        - Faceoff wins + losses = total

        Args:
            faceoff_summary: Parsed faceoff summary data

        Returns:
            List of validation results
        """
        return validate_faceoff_summary(faceoff_summary)

    def validate_shot_summary(
        self, shot_summary: ParsedShotSummary
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of HTML shot summary.

        Checks:
        - Zone shots sum to total

        Args:
            shot_summary: Parsed shot summary data

        Returns:
            List of validation results
        """
        return validate_shot_summary(shot_summary)

    def validate_time_on_ice(
        self, toi: ParsedTimeOnIce
    ) -> list[InternalValidationResult]:
        """Validate internal consistency of HTML time on ice.

        Checks:
        - Shift durations sum to period TOI

        Args:
            toi: Parsed time on ice data

        Returns:
            List of validation results
        """
        return validate_time_on_ice(toi)

    def get_boxscore_summary(self, boxscore: ParsedBoxscore) -> ValidationSummary:
        """Get validation summary for boxscore data.

        Args:
            boxscore: Parsed boxscore data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_boxscore(boxscore)
        return ValidationSummary.from_results(
            source_type=SOURCE_BOXSCORE,
            entity_id=str(boxscore.game_id),
            results=results,
        )

    def get_pbp_summary(self, pbp: ParsedPlayByPlay) -> ValidationSummary:
        """Get validation summary for play-by-play data.

        Args:
            pbp: Parsed play-by-play data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_play_by_play(pbp)
        return ValidationSummary.from_results(
            source_type=SOURCE_PBP,
            entity_id=str(pbp.game_id),
            results=results,
        )

    def get_shifts_summary(self, shifts: ParsedShiftChart) -> ValidationSummary:
        """Get validation summary for shift chart data.

        Args:
            shifts: Parsed shift chart data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_shift_chart(shifts)
        return ValidationSummary.from_results(
            source_type=SOURCE_SHIFTS,
            entity_id=str(shifts.game_id),
            results=results,
        )

    def get_standings_summary(self, standings: ParsedStandings) -> ValidationSummary:
        """Get validation summary for standings data.

        Args:
            standings: Parsed standings data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_standings(standings)
        return ValidationSummary.from_results(
            source_type=SOURCE_STANDINGS,
            entity_id=str(standings.season_id),
            results=results,
        )

    def get_event_summary_summary(
        self, event_summary: ParsedEventSummary
    ) -> ValidationSummary:
        """Get validation summary for HTML event summary.

        Args:
            event_summary: Parsed event summary data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_event_summary(event_summary)
        return ValidationSummary.from_results(
            source_type=SOURCE_HTML_ES,
            entity_id=str(event_summary.game_id),
            results=results,
        )

    def get_game_summary_summary(
        self, game_summary: ParsedGameSummary
    ) -> ValidationSummary:
        """Get validation summary for HTML game summary.

        Args:
            game_summary: Parsed game summary data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_game_summary(game_summary)
        return ValidationSummary.from_results(
            source_type=SOURCE_HTML_GS,
            entity_id=str(game_summary.game_id),
            results=results,
        )

    def get_faceoff_summary_summary(
        self, faceoff_summary: ParsedFaceoffSummary
    ) -> ValidationSummary:
        """Get validation summary for HTML faceoff summary.

        Args:
            faceoff_summary: Parsed faceoff summary data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_faceoff_summary(faceoff_summary)
        return ValidationSummary.from_results(
            source_type=SOURCE_HTML_FS,
            entity_id=str(faceoff_summary.game_id),
            results=results,
        )

    def get_shot_summary_summary(
        self, shot_summary: ParsedShotSummary
    ) -> ValidationSummary:
        """Get validation summary for HTML shot summary.

        Args:
            shot_summary: Parsed shot summary data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_shot_summary(shot_summary)
        return ValidationSummary.from_results(
            source_type=SOURCE_HTML_SS,
            entity_id=str(shot_summary.game_id),
            results=results,
        )

    def get_toi_summary(self, toi: ParsedTimeOnIce) -> ValidationSummary:
        """Get validation summary for HTML time on ice.

        Args:
            toi: Parsed time on ice data

        Returns:
            ValidationSummary with aggregated results
        """
        results = self.validate_time_on_ice(toi)
        return ValidationSummary.from_results(
            source_type=SOURCE_HTML_TOI,
            entity_id=str(toi.game_id),
            results=results,
        )
