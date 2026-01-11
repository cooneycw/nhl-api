"""Integration tests for shift total validation (T014).

Validates that expanded second-by-second snapshots match the original
shift duration totals from the game_shifts table.

The key validation is:
- Sum of shift durations for each player from game_shifts
- Should equal count of seconds player appears in second_snapshots
- With a tolerance of ±2 seconds for timing discrepancies

Issue: #260 - Wave 2: Validation & Quality (T014)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from nhl_api.validation.analytics_validation import (
    AnalyticsValidator,
    ShiftTotalValidation,
    ValidationSeverity,
)
from tests.integration.analytics.conftest import make_record, make_records

if TYPE_CHECKING:
    pass


class TestShiftTotalValidation:
    """Tests for shift total validation."""

    @pytest.mark.asyncio
    async def test_validate_shift_totals_exact_match(
        self, mock_db_service: AsyncMock
    ) -> None:
        """Shift totals should pass when exact match."""
        validator = AnalyticsValidator(mock_db_service)
        validations = await validator.validate_shift_totals(game_id=2024020500)

        assert len(validations) > 0
        for v in validations:
            assert isinstance(v, ShiftTotalValidation)
            assert v.is_valid
            assert v.difference_seconds <= v.tolerance_seconds

    @pytest.mark.asyncio
    async def test_validate_shift_totals_within_tolerance(
        self, sample_game_info: dict
    ) -> None:
        """Shift totals should pass when within tolerance."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_shifts" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "total_seconds": 1250,
                            "shift_count": 25,
                        }
                    ]
                )
            return []

        db.fetch = mock_fetch

        # Return expanded TOI with 1 second difference (within tolerance)
        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1251  # 1 second more than original
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db, shift_tolerance=2)
        validations = await validator.validate_shift_totals(game_id=2024020500)

        assert len(validations) == 1
        assert validations[0].is_valid
        assert validations[0].difference_seconds == 1

    @pytest.mark.asyncio
    async def test_validate_shift_totals_exceeds_tolerance(
        self, sample_game_info: dict
    ) -> None:
        """Shift totals should fail when exceeding tolerance."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_shifts" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "total_seconds": 1250,
                            "shift_count": 25,
                        }
                    ]
                )
            return []

        db.fetch = mock_fetch

        # Return expanded TOI with 10 second difference (exceeds tolerance)
        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1260  # 10 seconds more than original
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db, shift_tolerance=2)
        validations = await validator.validate_shift_totals(game_id=2024020500)

        assert len(validations) == 1
        assert not validations[0].is_valid
        assert validations[0].difference_seconds == 10

    @pytest.mark.asyncio
    async def test_validate_shift_totals_game_not_found(self) -> None:
        """Should raise ValueError when game not found."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            return None

        db.fetchrow = mock_fetchrow

        validator = AnalyticsValidator(db)

        with pytest.raises(ValueError, match="Game 9999999 not found"):
            await validator.validate_shift_totals(game_id=9999999)

    @pytest.mark.asyncio
    async def test_validate_shift_totals_multiple_players(
        self, sample_game_info: dict
    ) -> None:
        """Should validate all players in the game."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_shifts" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "total_seconds": 1250,
                            "shift_count": 25,
                        },
                        {
                            "player_id": 8477934,
                            "team_id": 22,
                            "total_seconds": 1180,
                            "shift_count": 24,
                        },
                        {
                            "player_id": 8477846,
                            "team_id": 25,
                            "total_seconds": 1100,
                            "shift_count": 22,
                        },
                    ]
                )
            return []

        db.fetch = mock_fetch

        # Return exact matches for each player
        player_toi = {8478402: 1250, 8477934: 1180, 8477846: 1100}

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                player_id = args[1] if len(args) > 1 else None
                return player_toi.get(player_id, 0)
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db)
        validations = await validator.validate_shift_totals(game_id=2024020500)

        assert len(validations) == 3
        assert all(v.is_valid for v in validations)
        assert {v.player_id for v in validations} == {8478402, 8477934, 8477846}

    @pytest.mark.asyncio
    async def test_validate_shift_totals_home_vs_away(
        self, sample_game_info: dict
    ) -> None:
        """Should correctly identify home vs away players."""
        db = AsyncMock()
        home_team_id = sample_game_info["home_team_id"]
        away_team_id = sample_game_info["away_team_id"]

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_shifts" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": home_team_id,
                            "total_seconds": 1250,
                            "shift_count": 25,
                        },
                        {
                            "player_id": 8477846,
                            "team_id": away_team_id,
                            "total_seconds": 1100,
                            "shift_count": 22,
                        },
                    ]
                )
            return []

        db.fetch = mock_fetch

        # Track which query was used for each player
        queries_used = []

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                queries_used.append((query, args))
                if "home_skater_ids" in query:
                    return 1250
                elif "away_skater_ids" in query:
                    return 1100
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db)
        validations = await validator.validate_shift_totals(game_id=2024020500)

        assert len(validations) == 2

        # Verify correct queries were used
        home_player_queries = [q for q, a in queries_used if "home_skater_ids" in q]
        away_player_queries = [q for q, a in queries_used if "away_skater_ids" in q]
        assert len(home_player_queries) == 1
        assert len(away_player_queries) == 1


class TestShiftTotalValidationWithIssues:
    """Tests for shift validation issue generation."""

    @pytest.mark.asyncio
    async def test_generates_warning_on_mismatch(self, sample_game_info: dict) -> None:
        """Should generate warning issue when totals don't match."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM game_shifts" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "total_seconds": 1250,
                            "shift_count": 25,
                        }
                    ]
                )
            return []

        db.fetch = mock_fetch

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1270  # 20 second mismatch
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db, shift_tolerance=2)
        result = await validator.validate_game(game_id=2024020500)

        shift_issues = [i for i in result.issues if i.category == "shift_totals"]
        assert len(shift_issues) == 1
        assert shift_issues[0].severity == ValidationSeverity.WARNING
        assert "8478402" in shift_issues[0].message
        assert shift_issues[0].expected == 1250
        assert shift_issues[0].actual == 1270


class TestShiftTotalValidationLive:
    """Live database tests for shift validation.

    These tests run against the actual database and are skipped
    if database credentials are not available.
    """

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        True,  # Normally would check for credentials
        reason="Live database tests require DB credentials",
    )
    async def test_live_validate_shift_totals(self, live_db_service) -> None:
        """Validate shift totals against live database."""
        if live_db_service is None:
            pytest.skip("No database connection available")

        # Use a known completed game
        game_id = 2024020100  # Early season game

        validator = AnalyticsValidator(live_db_service)
        validations = await validator.validate_shift_totals(game_id=game_id)

        # Should have validations for all players in game
        assert len(validations) > 0

        # Most players should be within tolerance
        valid_count = sum(1 for v in validations if v.is_valid)
        assert valid_count / len(validations) >= 0.95  # 95% should pass
