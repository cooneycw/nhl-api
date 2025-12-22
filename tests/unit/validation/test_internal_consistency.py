"""Tests for the main InternalConsistencyValidator class."""
# mypy: disable-error-code="arg-type,type-arg"

from __future__ import annotations

import pytest

from nhl_api.validation import (
    InternalConsistencyValidator,
    InternalValidationResult,
    ValidationSummary,
)


class MockSkaterStats:
    """Mock skater stats for testing."""

    def __init__(
        self,
        player_id: int = 8471214,
        name: str = "Test Player",
        sweater_number: int = 11,
        goals: int = 1,
        assists: int = 2,
        points: int = 3,
        power_play_goals: int = 0,
        shorthanded_goals: int = 0,
        faceoff_pct: float = 50.0,
        toi: str = "15:00",
    ):
        self.player_id = player_id
        self.name = name
        self.sweater_number = sweater_number
        self.goals = goals
        self.assists = assists
        self.points = points
        self.power_play_goals = power_play_goals
        self.shorthanded_goals = shorthanded_goals
        self.faceoff_pct = faceoff_pct
        self.toi = toi


class MockGoalieStats:
    """Mock goalie stats for testing."""

    def __init__(
        self,
        player_id: int = 8471215,
        name: str = "Test Goalie",
        saves: int = 25,
        shots_against: int = 27,
        save_pct: float = 0.926,
        toi: str = "60:00",
    ):
        self.player_id = player_id
        self.name = name
        self.saves = saves
        self.shots_against = shots_against
        self.save_pct = save_pct
        self.toi = toi


class MockTeamBoxscore:
    """Mock team boxscore for testing."""

    def __init__(
        self,
        abbrev: str = "BOS",
        score: int = 3,
        shots_on_goal: int = 30,
        skaters: list[Any] | None = None,
        goalies: list[Any] | None = None,
    ):
        self.abbrev = abbrev
        self.score = score
        self.shots_on_goal = shots_on_goal
        self.skaters = skaters or []
        self.goalies = goalies or []


class MockParsedBoxscore:
    """Mock parsed boxscore for testing."""

    def __init__(
        self,
        home_team: MockTeamBoxscore | None = None,
        away_team: MockTeamBoxscore | None = None,
        home_skaters: list[Any] | None = None,
        away_skaters: list[Any] | None = None,
        home_goalies: list[Any] | None = None,
        away_goalies: list[Any] | None = None,
        game_id: int = 2024020500,
    ):
        self.home_team = home_team or MockTeamBoxscore()
        self.away_team = away_team or MockTeamBoxscore(abbrev="TOR")
        self.home_skaters = home_skaters or []
        self.away_skaters = away_skaters or []
        self.home_goalies = home_goalies or []
        self.away_goalies = away_goalies or []
        self.game_id = game_id


class TestInternalConsistencyValidator:
    """Tests for InternalConsistencyValidator class."""

    def test_validate_boxscore_returns_results(self):
        """Validator should return list of results for boxscore."""
        validator = InternalConsistencyValidator()
        skaters = [MockSkaterStats(goals=3, assists=2, points=5)]
        home = MockTeamBoxscore(score=3, shots_on_goal=30)
        boxscore = MockParsedBoxscore(home_team=home, home_skaters=skaters)

        results = validator.validate_boxscore(boxscore)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, InternalValidationResult) for r in results)

    def test_get_boxscore_summary_returns_summary(self):
        """Validator should return ValidationSummary for boxscore."""
        validator = InternalConsistencyValidator()
        skaters = [MockSkaterStats(goals=3, assists=2, points=5)]
        home = MockTeamBoxscore(score=3, shots_on_goal=30)
        boxscore = MockParsedBoxscore(home_team=home, home_skaters=skaters)

        summary = validator.get_boxscore_summary(boxscore)

        assert isinstance(summary, ValidationSummary)
        assert summary.source_type == "boxscore"
        assert summary.entity_id == "2024020500"
        assert summary.total_checks > 0


class TestValidationSummary:
    """Tests for ValidationSummary class."""

    def test_from_results_all_passed(self):
        """Summary should correctly count all passed results."""
        results = [
            InternalValidationResult(
                rule_name="test_rule",
                passed=True,
                severity="info",
                message="Test passed",
                source_type="test",
                entity_id="123",
            ),
            InternalValidationResult(
                rule_name="test_rule_2",
                passed=True,
                severity="info",
                message="Test passed 2",
                source_type="test",
                entity_id="123",
            ),
        ]

        summary = ValidationSummary.from_results("test", "123", results)

        assert summary.total_checks == 2
        assert summary.passed == 2
        assert summary.failed == 0
        assert summary.warnings == 0

    def test_from_results_with_failures(self):
        """Summary should correctly count failed results."""
        results = [
            InternalValidationResult(
                rule_name="test_rule",
                passed=True,
                severity="info",
                message="Test passed",
                source_type="test",
                entity_id="123",
            ),
            InternalValidationResult(
                rule_name="test_rule_2",
                passed=False,
                severity="error",
                message="Test failed",
                source_type="test",
                entity_id="123",
            ),
        ]

        summary = ValidationSummary.from_results("test", "123", results)

        assert summary.total_checks == 2
        assert summary.passed == 1
        assert summary.failed == 1

    def test_from_results_with_warnings(self):
        """Summary should correctly count warning results."""
        results = [
            InternalValidationResult(
                rule_name="test_rule",
                passed=False,
                severity="warning",
                message="Test warning",
                source_type="test",
                entity_id="123",
            ),
        ]

        summary = ValidationSummary.from_results("test", "123", results)

        assert summary.total_checks == 1
        assert summary.passed == 0
        # Warnings are NOT counted as failed, only counted as warnings
        assert summary.warnings == 1


class TestInternalValidationResult:
    """Tests for InternalValidationResult dataclass."""

    def test_result_is_frozen(self):
        """Result should be immutable."""
        result = InternalValidationResult(
            rule_name="test_rule",
            passed=True,
            severity="info",
            message="Test",
            source_type="test",
            entity_id="123",
        )

        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore

    def test_result_with_details(self):
        """Result should accept optional details."""
        details = {"key": "value", "count": 5}
        result = InternalValidationResult(
            rule_name="test_rule",
            passed=False,
            severity="error",
            message="Test failed",
            details=details,
            source_type="test",
            entity_id="123",
        )

        assert result.details == details
        assert result.details["key"] == "value"

    def test_result_default_details_is_none(self):
        """Result details should default to None."""
        result = InternalValidationResult(
            rule_name="test_rule",
            passed=True,
            severity="info",
            message="Test",
            source_type="test",
            entity_id="123",
        )

        assert result.details is None
