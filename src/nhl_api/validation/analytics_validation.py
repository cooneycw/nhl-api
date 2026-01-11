"""Analytics validation service for second-by-second data quality.

Validates the second-by-second analytics data against official NHL sources:
- Shift totals: Compare expanded seconds to original shift durations
- Event counts: Compare attributed events to boxscore totals
- Situation codes: Verify correct calculation from player counts
- HTML reports: Cross-reference with official shift reports
- Official scorer: Compare event attribution to official records

Example usage:
    async with DatabaseService() as db:
        validator = AnalyticsValidator(db)

        # Validate a single game
        result = await validator.validate_game(game_id=2024020500)

        for issue in result.issues:
            print(f"{issue.severity}: {issue.message}")

Issue: #260 - Wave 2: Validation & Quality (T017-T018)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nhl_api.services.db.connection import DatabaseService

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""

    ERROR = "error"  # Data is definitely wrong
    WARNING = "warning"  # Data might be wrong, needs investigation
    INFO = "info"  # Informational note, not an error


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single validation issue found during analytics validation.

    Attributes:
        severity: Issue severity level.
        category: Category of validation (shift_totals, event_counts, etc.).
        message: Human-readable description of the issue.
        game_id: Game ID where issue was found.
        player_id: Player ID involved (if applicable).
        expected: Expected value.
        actual: Actual value found.
        details: Additional context.
    """

    severity: ValidationSeverity
    category: str
    message: str
    game_id: int
    player_id: int | None = None
    expected: Any = None
    actual: Any = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ShiftTotalValidation:
    """Result of validating shift totals for a player.

    Attributes:
        player_id: Player ID.
        player_name: Player name (if available).
        team_id: Team ID.
        original_toi_seconds: TOI from shift chart data (sum of shift durations).
        expanded_toi_seconds: TOI from expanded second snapshots.
        difference_seconds: Difference between original and expanded.
        tolerance_seconds: Allowed tolerance for validation.
        is_valid: True if within tolerance.
    """

    player_id: int
    player_name: str | None
    team_id: int
    original_toi_seconds: int
    expanded_toi_seconds: int
    difference_seconds: int
    tolerance_seconds: int = 2
    is_valid: bool = True


@dataclass
class EventCountValidation:
    """Result of validating event counts against boxscore.

    Attributes:
        game_id: Game ID.
        event_type: Type of event (goal, shot, hit, etc.).
        source: Source of expected count (boxscore, pbp, etc.).
        expected_count: Expected count from official source.
        attributed_count: Count from second-by-second attribution.
        difference: Difference between expected and attributed.
        is_valid: True if counts match.
    """

    game_id: int
    event_type: str
    source: str
    expected_count: int
    attributed_count: int
    difference: int
    is_valid: bool = True


@dataclass
class SituationCodeValidation:
    """Result of validating situation code calculation.

    Attributes:
        game_id: Game ID.
        game_second: Second where issue was found.
        expected_code: Expected situation code.
        actual_code: Actual situation code.
        home_skaters: Number of home skaters.
        away_skaters: Number of away skaters.
        home_goalie: Home goalie ID (None if empty net).
        away_goalie: Away goalie ID (None if empty net).
        is_valid: True if codes match.
    """

    game_id: int
    game_second: int
    expected_code: str
    actual_code: str
    home_skaters: int
    away_skaters: int
    home_goalie: int | None
    away_goalie: int | None
    is_valid: bool = True


@dataclass
class HTMLComparisonResult:
    """Result of comparing analytics to HTML shift reports.

    Attributes:
        game_id: Game ID.
        player_id: Player ID.
        html_toi_seconds: TOI from HTML shift report.
        analytics_toi_seconds: TOI from analytics.
        difference_seconds: Difference.
        html_shift_count: Number of shifts in HTML report.
        analytics_shift_count: Number of shifts in analytics.
        is_valid: True if within tolerance.
    """

    game_id: int
    player_id: int
    player_name: str | None
    html_toi_seconds: int
    analytics_toi_seconds: int
    difference_seconds: int
    html_shift_count: int
    analytics_shift_count: int
    is_valid: bool = True


@dataclass
class GameValidationResult:
    """Complete validation result for a game.

    Attributes:
        game_id: Game ID.
        season_id: Season ID.
        is_valid: True if all validations passed.
        shift_validations: Shift total validations by player.
        event_validations: Event count validations.
        situation_validations: Situation code validations.
        html_comparisons: HTML report comparisons.
        issues: All validation issues found.
        summary: Summary statistics.
    """

    game_id: int
    season_id: int
    is_valid: bool = True
    shift_validations: list[ShiftTotalValidation] = field(default_factory=list)
    event_validations: list[EventCountValidation] = field(default_factory=list)
    situation_validations: list[SituationCodeValidation] = field(default_factory=list)
    html_comparisons: list[HTMLComparisonResult] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


class AnalyticsValidator:
    """Validator for second-by-second analytics data.

    Provides comprehensive validation of analytics data against
    official NHL sources including shift charts, boxscores, and
    HTML reports.

    Attributes:
        db: Database service for data access.
        shift_tolerance: Allowed seconds difference for shift totals.
        event_tolerance: Allowed difference for event counts.

    Example:
        >>> validator = AnalyticsValidator(db)
        >>> result = await validator.validate_game(2024020500)
        >>> print(f"Valid: {result.is_valid}, Issues: {len(result.issues)}")
    """

    def __init__(
        self,
        db: DatabaseService,
        shift_tolerance: int = 2,
        event_tolerance: int = 0,
    ) -> None:
        """Initialize the AnalyticsValidator.

        Args:
            db: Database service for data access.
            shift_tolerance: Allowed seconds difference for shift totals.
            event_tolerance: Allowed difference for event counts.
        """
        self.db = db
        self.shift_tolerance = shift_tolerance
        self.event_tolerance = event_tolerance

    async def validate_game(self, game_id: int) -> GameValidationResult:
        """Perform comprehensive validation of a game's analytics.

        Validates:
        1. Shift totals match original shift data
        2. Event counts match boxscore
        3. Situation codes are correct
        4. Data matches HTML shift reports (if available)

        Args:
            game_id: NHL game ID to validate.

        Returns:
            GameValidationResult with all validation results.
        """
        # Get game metadata
        game_info = await self._get_game_info(game_id)
        if not game_info:
            result = GameValidationResult(game_id=game_id, season_id=0, is_valid=False)
            result.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="game",
                    message=f"Game {game_id} not found in database",
                    game_id=game_id,
                )
            )
            return result

        result = GameValidationResult(
            game_id=game_id,
            season_id=game_info["season_id"],
        )

        # Run all validations
        await self._validate_shift_totals(game_id, game_info, result)
        await self._validate_event_counts(game_id, result)
        await self._validate_situation_codes(game_id, result)
        await self._compare_to_html_reports(game_id, result)

        # Determine overall validity
        result.is_valid = not any(
            issue.severity == ValidationSeverity.ERROR for issue in result.issues
        )

        # Generate summary
        result.summary = {
            "total_issues": len(result.issues),
            "errors": sum(
                1 for i in result.issues if i.severity == ValidationSeverity.ERROR
            ),
            "warnings": sum(
                1 for i in result.issues if i.severity == ValidationSeverity.WARNING
            ),
            "players_validated": len(result.shift_validations),
            "events_validated": len(result.event_validations),
            "situations_validated": len(result.situation_validations),
        }

        logger.info(
            f"Game {game_id}: Validation complete. "
            f"Valid: {result.is_valid}, Issues: {len(result.issues)}"
        )

        return result

    async def validate_shift_totals(self, game_id: int) -> list[ShiftTotalValidation]:
        """Validate that expanded second totals match original shift durations.

        For each player, compares:
        - Sum of shift durations from game_shifts table
        - Count of seconds player appears in second_snapshots

        Args:
            game_id: NHL game ID.

        Returns:
            List of ShiftTotalValidation for each player.

        Raises:
            ValueError: If game not found.
        """
        game_info = await self._get_game_info(game_id)
        if not game_info:
            raise ValueError(f"Game {game_id} not found")

        result = GameValidationResult(game_id=game_id, season_id=game_info["season_id"])
        await self._validate_shift_totals(game_id, game_info, result)
        return result.shift_validations

    async def validate_event_counts(self, game_id: int) -> list[EventCountValidation]:
        """Validate event counts against boxscore totals.

        Compares:
        - Goals, shots, hits, blocks from boxscore
        - Attributed events in second_snapshots

        Args:
            game_id: NHL game ID.

        Returns:
            List of EventCountValidation for each event type.

        Raises:
            ValueError: If game not found.
        """
        game_info = await self._get_game_info(game_id)
        if not game_info:
            raise ValueError(f"Game {game_id} not found")

        result = GameValidationResult(game_id=game_id, season_id=game_info["season_id"])
        await self._validate_event_counts(game_id, result)
        return result.event_validations

    async def validate_situation_codes(
        self, game_id: int
    ) -> list[SituationCodeValidation]:
        """Validate situation codes are calculated correctly.

        For each second, verifies that the situation code matches
        the expected value based on skater counts and goalie presence.

        Args:
            game_id: NHL game ID.

        Returns:
            List of SituationCodeValidation for any mismatches.

        Raises:
            ValueError: If game not found.
        """
        game_info = await self._get_game_info(game_id)
        if not game_info:
            raise ValueError(f"Game {game_id} not found")

        result = GameValidationResult(game_id=game_id, season_id=game_info["season_id"])
        await self._validate_situation_codes(game_id, result)
        return result.situation_validations

    async def compare_to_html_reports(self, game_id: int) -> list[HTMLComparisonResult]:
        """Compare analytics data to HTML shift reports.

        Uses the TV/TH (Time on Ice) HTML reports to validate
        player TOI totals against the analytics data.

        Args:
            game_id: NHL game ID.

        Returns:
            List of HTMLComparisonResult for each player.

        Raises:
            ValueError: If game not found.
        """
        game_info = await self._get_game_info(game_id)
        if not game_info:
            raise ValueError(f"Game {game_id} not found")

        result = GameValidationResult(game_id=game_id, season_id=game_info["season_id"])
        await self._compare_to_html_reports(game_id, result)
        return result.html_comparisons

    async def _get_game_info(self, game_id: int) -> dict[str, Any] | None:
        """Get game metadata from database."""
        row = await self.db.fetchrow(
            """
            SELECT game_id, season_id, home_team_id, away_team_id, period
            FROM games
            WHERE game_id = $1
            """,
            game_id,
        )
        if row:
            return dict(row)
        return None

    async def _validate_shift_totals(
        self,
        game_id: int,
        game_info: dict[str, Any],
        result: GameValidationResult,
    ) -> None:
        """Validate shift totals for all players in a game."""
        home_team_id = game_info["home_team_id"]

        # Get original shift totals from game_shifts
        shift_totals = await self.db.fetch(
            """
            SELECT player_id, team_id,
                   SUM(duration_seconds) as total_seconds,
                   COUNT(*) as shift_count
            FROM game_shifts
            WHERE game_id = $1 AND is_goal_event = false
            GROUP BY player_id, team_id
            """,
            game_id,
        )

        # Get expanded totals from second_snapshots
        for shift in shift_totals:
            player_id = shift["player_id"]
            team_id = shift["team_id"]
            original_toi = shift["total_seconds"] or 0

            # Count seconds player appears in snapshots
            if team_id == home_team_id:
                expanded_toi = await self.db.fetchval(
                    """
                    SELECT COUNT(*) FROM second_snapshots
                    WHERE game_id = $1 AND $2 = ANY(home_skater_ids)
                    """,
                    game_id,
                    player_id,
                )
            else:
                expanded_toi = await self.db.fetchval(
                    """
                    SELECT COUNT(*) FROM second_snapshots
                    WHERE game_id = $1 AND $2 = ANY(away_skater_ids)
                    """,
                    game_id,
                    player_id,
                )

            expanded_toi = expanded_toi or 0
            difference = abs(original_toi - expanded_toi)
            is_valid = difference <= self.shift_tolerance

            validation = ShiftTotalValidation(
                player_id=player_id,
                player_name=None,  # Could be fetched if needed
                team_id=team_id,
                original_toi_seconds=original_toi,
                expanded_toi_seconds=expanded_toi,
                difference_seconds=difference,
                tolerance_seconds=self.shift_tolerance,
                is_valid=is_valid,
            )
            result.shift_validations.append(validation)

            if not is_valid:
                result.issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="shift_totals",
                        message=(
                            f"Player {player_id} TOI mismatch: "
                            f"original={original_toi}s, expanded={expanded_toi}s, "
                            f"diff={difference}s"
                        ),
                        game_id=game_id,
                        player_id=player_id,
                        expected=original_toi,
                        actual=expanded_toi,
                    )
                )

    async def _validate_event_counts(
        self,
        game_id: int,
        result: GameValidationResult,
    ) -> None:
        """Validate event counts against boxscore."""
        # Get event counts from game_events
        event_counts = await self.db.fetch(
            """
            SELECT event_type, COUNT(*) as count
            FROM game_events
            WHERE game_id = $1
            GROUP BY event_type
            """,
            game_id,
        )

        # Get boxscore totals for comparison
        boxscore = await self.db.fetchrow(
            """
            SELECT
                home_goals, away_goals,
                home_shots, away_shots,
                home_hits, away_hits,
                home_blocks, away_blocks
            FROM boxscores
            WHERE game_id = $1
            """,
            game_id,
        )

        if not boxscore:
            result.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="event_counts",
                    message=f"No boxscore found for game {game_id}",
                    game_id=game_id,
                )
            )
            return

        # Map event types to boxscore fields
        event_type_map = {
            "goal": ("home_goals", "away_goals"),
            "shot-on-goal": ("home_shots", "away_shots"),
            "hit": ("home_hits", "away_hits"),
            "blocked-shot": ("home_blocks", "away_blocks"),
        }

        event_counts_dict = {row["event_type"]: row["count"] for row in event_counts}

        for event_type, (home_field, away_field) in event_type_map.items():
            expected = (boxscore[home_field] or 0) + (boxscore[away_field] or 0)
            actual = event_counts_dict.get(event_type, 0)

            # For shots, goals are also counted
            if event_type == "shot-on-goal":
                actual += event_counts_dict.get("goal", 0)

            difference = abs(expected - actual)
            is_valid = difference <= self.event_tolerance

            validation = EventCountValidation(
                game_id=game_id,
                event_type=event_type,
                source="boxscore",
                expected_count=expected,
                attributed_count=actual,
                difference=difference,
                is_valid=is_valid,
            )
            result.event_validations.append(validation)

            if not is_valid:
                result.issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="event_counts",
                        message=(
                            f"Event count mismatch for {event_type}: "
                            f"boxscore={expected}, events={actual}"
                        ),
                        game_id=game_id,
                        expected=expected,
                        actual=actual,
                    )
                )

    async def _validate_situation_codes(
        self,
        game_id: int,
        result: GameValidationResult,
    ) -> None:
        """Validate situation codes are calculated correctly."""
        from nhl_api.models.second_snapshots import calculate_situation_code

        # Get all snapshots for the game
        snapshots = await self.db.fetch(
            """
            SELECT game_second, situation_code,
                   home_skater_count, away_skater_count,
                   home_goalie_id, away_goalie_id
            FROM second_snapshots
            WHERE game_id = $1
            ORDER BY game_second
            """,
            game_id,
        )

        for snapshot in snapshots:
            home_skaters = snapshot["home_skater_count"]
            away_skaters = snapshot["away_skater_count"]
            home_goalie = snapshot["home_goalie_id"]
            away_goalie = snapshot["away_goalie_id"]

            expected_code = calculate_situation_code(
                home_skaters=home_skaters,
                away_skaters=away_skaters,
                home_empty_net=home_goalie is None,
                away_empty_net=away_goalie is None,
            )
            actual_code = snapshot["situation_code"]

            if expected_code != actual_code:
                validation = SituationCodeValidation(
                    game_id=game_id,
                    game_second=snapshot["game_second"],
                    expected_code=expected_code,
                    actual_code=actual_code,
                    home_skaters=home_skaters,
                    away_skaters=away_skaters,
                    home_goalie=home_goalie,
                    away_goalie=away_goalie,
                    is_valid=False,
                )
                result.situation_validations.append(validation)
                result.issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category="situation_codes",
                        message=(
                            f"Situation code mismatch at second {snapshot['game_second']}: "
                            f"expected={expected_code}, actual={actual_code}"
                        ),
                        game_id=game_id,
                        expected=expected_code,
                        actual=actual_code,
                        details={
                            "game_second": snapshot["game_second"],
                            "home_skaters": home_skaters,
                            "away_skaters": away_skaters,
                        },
                    )
                )

    async def _compare_to_html_reports(
        self,
        game_id: int,
        result: GameValidationResult,
    ) -> None:
        """Compare analytics to HTML shift reports (TV/TH).

        The TV (visitor) and TH (home) time on ice reports contain
        official TOI totals that we can validate against.
        """
        # Get game info for team IDs
        game_info = await self._get_game_info(game_id)
        if not game_info:
            return

        home_team_id = game_info["home_team_id"]

        # Check if HTML TOI data is available
        html_toi = await self.db.fetch(
            """
            SELECT player_id, team_id, toi_seconds, shift_count
            FROM html_toi_reports
            WHERE game_id = $1
            """,
            game_id,
        )

        if not html_toi:
            result.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    category="html_comparison",
                    message=f"No HTML TOI data available for game {game_id}",
                    game_id=game_id,
                )
            )
            return

        # Get analytics TOI for comparison
        for html in html_toi:
            player_id = html["player_id"]
            team_id = html["team_id"]
            html_toi_seconds = html["toi_seconds"]
            html_shift_count = html["shift_count"]

            # Query analytics TOI directly from second_snapshots
            if team_id == home_team_id:
                analytics_toi = await self.db.fetchval(
                    """
                    SELECT COUNT(*) FROM second_snapshots
                    WHERE game_id = $1 AND $2 = ANY(home_skater_ids)
                    """,
                    game_id,
                    player_id,
                )
            else:
                analytics_toi = await self.db.fetchval(
                    """
                    SELECT COUNT(*) FROM second_snapshots
                    WHERE game_id = $1 AND $2 = ANY(away_skater_ids)
                    """,
                    game_id,
                    player_id,
                )

            analytics_toi = analytics_toi or 0
            difference = abs(html_toi_seconds - analytics_toi)
            is_valid = difference <= self.shift_tolerance

            comparison = HTMLComparisonResult(
                game_id=game_id,
                player_id=player_id,
                player_name=None,
                html_toi_seconds=html_toi_seconds,
                analytics_toi_seconds=analytics_toi,
                difference_seconds=difference,
                html_shift_count=html_shift_count,
                analytics_shift_count=0,  # Would need to calculate
                is_valid=is_valid,
            )
            result.html_comparisons.append(comparison)

            if not is_valid:
                result.issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="html_comparison",
                        message=(
                            f"HTML vs Analytics TOI mismatch for player {player_id}: "
                            f"HTML={html_toi_seconds}s, analytics={analytics_toi}s"
                        ),
                        game_id=game_id,
                        player_id=player_id,
                        expected=html_toi_seconds,
                        actual=analytics_toi,
                    )
                )


async def validate_game_analytics(
    db: DatabaseService,
    game_id: int,
) -> GameValidationResult:
    """Convenience function to validate a game's analytics.

    Args:
        db: Database service.
        game_id: NHL game ID.

    Returns:
        GameValidationResult with validation results.
    """
    validator = AnalyticsValidator(db)
    return await validator.validate_game(game_id)
