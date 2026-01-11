"""Integration tests for event count validation (T015).

Validates that event counts from game_events table match the official
boxscore totals for goals, shots, hits, and blocks.

The key validation is:
- Count of each event type from game_events table
- Should match the corresponding totals from boxscores table
- Goals + shot-on-goal = total shots

Issue: #260 - Wave 2: Validation & Quality (T015)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from nhl_api.validation.analytics_validation import (
    AnalyticsValidator,
    EventCountValidation,
    ValidationSeverity,
)
from tests.integration.analytics.conftest import make_record, make_records

if TYPE_CHECKING:
    pass


class TestEventCountValidation:
    """Tests for event count validation against boxscore."""

    @pytest.mark.asyncio
    async def test_validate_event_counts_exact_match(
        self, sample_game_info: dict
    ) -> None:
        """Event counts should pass when they match boxscore exactly."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return make_record(
                    {
                        "home_goals": 4,
                        "away_goals": 2,
                        "home_shots": 35,
                        "away_shots": 28,
                        "home_hits": 22,
                        "away_hits": 18,
                        "home_blocks": 15,
                        "away_blocks": 12,
                    }
                )
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_events" in query:
                return make_records(
                    [
                        {"event_type": "goal", "count": 6},  # 4 + 2
                        {
                            "event_type": "shot-on-goal",
                            "count": 57,
                        },  # 35 + 28 - 6 goals
                        {"event_type": "hit", "count": 40},  # 22 + 18
                        {"event_type": "blocked-shot", "count": 27},  # 15 + 12
                    ]
                )
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_event_counts(game_id=2024020500)

        assert len(validations) == 4
        for v in validations:
            assert isinstance(v, EventCountValidation)
            assert v.is_valid
            assert v.difference == 0

    @pytest.mark.asyncio
    async def test_validate_goals_match(self, sample_game_info: dict) -> None:
        """Goal count should match boxscore."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return make_record(
                    {
                        "home_goals": 4,
                        "away_goals": 2,
                        "home_shots": 35,
                        "away_shots": 28,
                        "home_hits": 22,
                        "away_hits": 18,
                        "home_blocks": 15,
                        "away_blocks": 12,
                    }
                )
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_events" in query:
                return make_records(
                    [
                        {"event_type": "goal", "count": 6},
                        {"event_type": "shot-on-goal", "count": 57},
                        {"event_type": "hit", "count": 40},
                        {"event_type": "blocked-shot", "count": 27},
                    ]
                )
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_event_counts(game_id=2024020500)

        goal_validation = next((v for v in validations if v.event_type == "goal"), None)
        assert goal_validation is not None
        assert goal_validation.expected_count == 6
        assert goal_validation.attributed_count == 6
        assert goal_validation.is_valid

    @pytest.mark.asyncio
    async def test_validate_shots_include_goals(self, sample_game_info: dict) -> None:
        """Shot count should include goals (goals + shots-on-goal = total shots)."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return make_record(
                    {
                        "home_goals": 4,
                        "away_goals": 2,
                        "home_shots": 35,
                        "away_shots": 28,
                        "home_hits": 0,
                        "away_hits": 0,
                        "home_blocks": 0,
                        "away_blocks": 0,
                    }
                )
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_events" in query:
                return make_records(
                    [
                        {"event_type": "goal", "count": 6},
                        {"event_type": "shot-on-goal", "count": 57},  # 63 - 6 = 57
                    ]
                )
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_event_counts(game_id=2024020500)

        shot_validation = next(
            (v for v in validations if v.event_type == "shot-on-goal"), None
        )
        assert shot_validation is not None
        # Expected: 35 + 28 = 63
        # Actual: 57 (shots) + 6 (goals) = 63
        assert shot_validation.expected_count == 63
        assert shot_validation.attributed_count == 63
        assert shot_validation.is_valid

    @pytest.mark.asyncio
    async def test_validate_event_counts_mismatch(self, sample_game_info: dict) -> None:
        """Should detect mismatches in event counts."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return make_record(
                    {
                        "home_goals": 4,
                        "away_goals": 2,
                        "home_shots": 35,
                        "away_shots": 28,
                        "home_hits": 22,
                        "away_hits": 18,
                        "home_blocks": 15,
                        "away_blocks": 12,
                    }
                )
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_events" in query:
                return make_records(
                    [
                        {"event_type": "goal", "count": 5},  # Should be 6
                        {"event_type": "shot-on-goal", "count": 57},
                        {"event_type": "hit", "count": 40},
                        {"event_type": "blocked-shot", "count": 27},
                    ]
                )
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db, event_tolerance=0)
        validations = await validator.validate_event_counts(game_id=2024020500)

        goal_validation = next((v for v in validations if v.event_type == "goal"), None)
        assert goal_validation is not None
        assert not goal_validation.is_valid
        assert goal_validation.difference == 1

    @pytest.mark.asyncio
    async def test_validate_event_counts_no_boxscore(
        self, sample_game_info: dict
    ) -> None:
        """Should handle missing boxscore gracefully."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None  # No boxscore
            return None

        db.fetchrow = mock_fetchrow
        db.fetch = AsyncMock(return_value=[])
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_event_counts(game_id=2024020500)

        # Should have no validations when boxscore missing
        assert len(validations) == 0

    @pytest.mark.asyncio
    async def test_validate_event_counts_game_not_found(self) -> None:
        """Should raise ValueError when game not found."""
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)

        validator = AnalyticsValidator(db)

        with pytest.raises(ValueError, match="Game 9999999 not found"):
            await validator.validate_event_counts(game_id=9999999)


class TestEventCountValidationIssues:
    """Tests for event validation issue generation."""

    @pytest.mark.asyncio
    async def test_generates_warning_on_mismatch(self, sample_game_info: dict) -> None:
        """Should generate warning when event counts don't match."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return make_record(
                    {
                        "home_goals": 4,
                        "away_goals": 2,
                        "home_shots": 35,
                        "away_shots": 28,
                        "home_hits": 22,
                        "away_hits": 18,
                        "home_blocks": 15,
                        "away_blocks": 12,
                    }
                )
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_events" in query:
                return make_records(
                    [
                        {"event_type": "goal", "count": 5},  # Missing 1 goal
                        {"event_type": "shot-on-goal", "count": 57},
                        {"event_type": "hit", "count": 40},
                        {"event_type": "blocked-shot", "count": 27},
                    ]
                )
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db, event_tolerance=0)
        result = await validator.validate_game(game_id=2024020500)

        event_issues = [i for i in result.issues if i.category == "event_counts"]
        assert len(event_issues) >= 1

        goal_issue = next((i for i in event_issues if "goal" in i.message), None)
        assert goal_issue is not None
        assert goal_issue.severity == ValidationSeverity.WARNING

    @pytest.mark.asyncio
    async def test_generates_warning_on_missing_boxscore(
        self, sample_game_info: dict
    ) -> None:
        """Should generate warning when boxscore is missing."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow
        db.fetch = AsyncMock(return_value=[])
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        result = await validator.validate_game(game_id=2024020500)

        boxscore_issues = [
            i
            for i in result.issues
            if i.category == "event_counts" and "boxscore" in i.message.lower()
        ]
        assert len(boxscore_issues) == 1
        assert boxscore_issues[0].severity == ValidationSeverity.WARNING


class TestEventCountValidationEdgeCases:
    """Edge case tests for event count validation."""

    @pytest.mark.asyncio
    async def test_handles_zero_events(self, sample_game_info: dict) -> None:
        """Should handle games with zero events of a type."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return make_record(
                    {
                        "home_goals": 0,
                        "away_goals": 0,
                        "home_shots": 0,
                        "away_shots": 0,
                        "home_hits": 0,
                        "away_hits": 0,
                        "home_blocks": 0,
                        "away_blocks": 0,
                    }
                )
            return None

        db.fetchrow = mock_fetchrow
        db.fetch = AsyncMock(return_value=[])  # No events
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_event_counts(game_id=2024020500)

        # All should be valid with zero counts
        for v in validations:
            assert v.expected_count == 0
            assert v.attributed_count == 0
            assert v.is_valid

    @pytest.mark.asyncio
    async def test_handles_null_boxscore_values(self, sample_game_info: dict) -> None:
        """Should handle NULL values in boxscore gracefully."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return make_record(
                    {
                        "home_goals": 4,
                        "away_goals": None,  # NULL
                        "home_shots": None,  # NULL
                        "away_shots": 28,
                        "home_hits": None,
                        "away_hits": None,
                        "home_blocks": None,
                        "away_blocks": None,
                    }
                )
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_events" in query:
                return make_records(
                    [
                        {"event_type": "goal", "count": 4},
                    ]
                )
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_event_counts(game_id=2024020500)

        # Should handle NULLs as 0
        goal_validation = next((v for v in validations if v.event_type == "goal"), None)
        assert goal_validation is not None
        # home_goals=4 + away_goals=None (treated as 0) = 4
        assert goal_validation.expected_count == 4
