"""Integration tests for situation code validation (T016).

Validates that situation codes in second_snapshots are correctly
calculated from the skater counts and goalie presence.

The key validation is:
- For each second snapshot, recalculate the expected situation code
- Compare against the stored situation_code
- Verify empty net detection is correct

Situation code format:
- Regular: "5v5", "5v4", "4v5", "4v4", "3v3", etc.
- Empty net home: "EN6v5", "EN5v4", etc.
- Empty net away: "5v6EN", "4v5EN", etc.

Issue: #260 - Wave 2: Validation & Quality (T016)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from nhl_api.models.second_snapshots import calculate_situation_code
from nhl_api.validation.analytics_validation import (
    AnalyticsValidator,
    SituationCodeValidation,
    ValidationSeverity,
)
from tests.integration.analytics.conftest import make_record, make_records

if TYPE_CHECKING:
    pass


class TestSituationCodeCalculation:
    """Tests for the situation code calculation function."""

    def test_5v5_situation(self) -> None:
        """Standard 5v5 even strength."""
        code = calculate_situation_code(
            home_skaters=5,
            away_skaters=5,
            home_empty_net=False,
            away_empty_net=False,
        )
        assert code == "5v5"

    def test_5v4_power_play(self) -> None:
        """Home team power play."""
        code = calculate_situation_code(
            home_skaters=5,
            away_skaters=4,
            home_empty_net=False,
            away_empty_net=False,
        )
        assert code == "5v4"

    def test_4v5_penalty_kill(self) -> None:
        """Home team penalty kill."""
        code = calculate_situation_code(
            home_skaters=4,
            away_skaters=5,
            home_empty_net=False,
            away_empty_net=False,
        )
        assert code == "4v5"

    def test_4v4_even_strength(self) -> None:
        """4v4 after offsetting minors."""
        code = calculate_situation_code(
            home_skaters=4,
            away_skaters=4,
            home_empty_net=False,
            away_empty_net=False,
        )
        assert code == "4v4"

    def test_3v3_overtime(self) -> None:
        """3v3 overtime format."""
        code = calculate_situation_code(
            home_skaters=3,
            away_skaters=3,
            home_empty_net=False,
            away_empty_net=False,
        )
        assert code == "3v3"

    def test_5v3_two_man_advantage(self) -> None:
        """5v3 double power play."""
        code = calculate_situation_code(
            home_skaters=5,
            away_skaters=3,
            home_empty_net=False,
            away_empty_net=False,
        )
        assert code == "5v3"

    def test_empty_net_home(self) -> None:
        """Home team pulled goalie."""
        code = calculate_situation_code(
            home_skaters=5,
            away_skaters=5,
            home_empty_net=True,
            away_empty_net=False,
        )
        # EN prefix indicates home empty net
        assert code.startswith("EN")
        assert code == "EN6v5"

    def test_empty_net_away(self) -> None:
        """Away team pulled goalie."""
        code = calculate_situation_code(
            home_skaters=5,
            away_skaters=5,
            home_empty_net=False,
            away_empty_net=True,
        )
        # EN suffix indicates away empty net
        assert code.endswith("EN")
        assert code == "5v6EN"

    def test_empty_net_home_on_power_play(self) -> None:
        """Home pulled goalie while on power play (6v4)."""
        code = calculate_situation_code(
            home_skaters=5,
            away_skaters=4,
            home_empty_net=True,
            away_empty_net=False,
        )
        # Home has empty net, so gets +1 displayed
        assert "EN" in code
        assert code == "EN6v4"


class TestSituationCodeValidation:
    """Tests for situation code validation in snapshots."""

    @pytest.mark.asyncio
    async def test_validate_situation_codes_all_correct(
        self, sample_game_info: dict
    ) -> None:
        """All situation codes should be valid when correctly calculated."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM second_snapshots" in query:
                return make_records(
                    [
                        {
                            "game_second": 0,
                            "situation_code": "5v5",
                            "home_skater_count": 5,
                            "away_skater_count": 5,
                            "home_goalie_id": 8479973,
                            "away_goalie_id": 8477970,
                        },
                        {
                            "game_second": 100,
                            "situation_code": "5v4",
                            "home_skater_count": 5,
                            "away_skater_count": 4,
                            "home_goalie_id": 8479973,
                            "away_goalie_id": 8477970,
                        },
                        {
                            "game_second": 200,
                            "situation_code": "4v4",
                            "home_skater_count": 4,
                            "away_skater_count": 4,
                            "home_goalie_id": 8479973,
                            "away_goalie_id": 8477970,
                        },
                    ]
                )
            if "FROM game_shifts" in query:
                return []
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_situation_codes(game_id=2024020500)

        # No issues means all codes are correct
        assert len(validations) == 0

    @pytest.mark.asyncio
    async def test_validate_situation_codes_detects_mismatch(
        self, sample_game_info: dict
    ) -> None:
        """Should detect situation code mismatches."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM second_snapshots" in query:
                return make_records(
                    [
                        {
                            "game_second": 0,
                            "situation_code": "5v4",  # WRONG - should be 5v5
                            "home_skater_count": 5,
                            "away_skater_count": 5,
                            "home_goalie_id": 8479973,
                            "away_goalie_id": 8477970,
                        },
                    ]
                )
            if "FROM game_shifts" in query:
                return []
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_situation_codes(game_id=2024020500)

        assert len(validations) == 1
        assert isinstance(validations[0], SituationCodeValidation)
        assert not validations[0].is_valid
        assert validations[0].expected_code == "5v5"
        assert validations[0].actual_code == "5v4"

    @pytest.mark.asyncio
    async def test_validate_empty_net_situation(self, sample_game_info: dict) -> None:
        """Should correctly validate empty net situation codes."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM second_snapshots" in query:
                return make_records(
                    [
                        {
                            "game_second": 3550,
                            "situation_code": "EN6v5",  # Home empty net
                            "home_skater_count": 5,  # Base skaters
                            "away_skater_count": 5,
                            "home_goalie_id": None,  # Pulled goalie
                            "away_goalie_id": 8477970,
                        },
                    ]
                )
            if "FROM game_shifts" in query:
                return []
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_situation_codes(game_id=2024020500)

        # Should be valid (empty net correctly calculated)
        assert len(validations) == 0

    @pytest.mark.asyncio
    async def test_validate_situation_codes_game_not_found(self) -> None:
        """Should raise ValueError when game not found."""
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)

        validator = AnalyticsValidator(db)

        with pytest.raises(ValueError, match="Game 9999999 not found"):
            await validator.validate_situation_codes(game_id=9999999)


class TestSituationCodeValidationIssues:
    """Tests for situation validation issue generation."""

    @pytest.mark.asyncio
    async def test_generates_error_on_mismatch(self, sample_game_info: dict) -> None:
        """Should generate ERROR (not warning) for situation code mismatches."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM second_snapshots" in query:
                return make_records(
                    [
                        {
                            "game_second": 100,
                            "situation_code": "5v4",  # Wrong
                            "home_skater_count": 5,
                            "away_skater_count": 5,  # Actually 5v5
                            "home_goalie_id": 8479973,
                            "away_goalie_id": 8477970,
                        },
                    ]
                )
            if "FROM game_shifts" in query:
                return []
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        result = await validator.validate_game(game_id=2024020500)

        situation_issues = [i for i in result.issues if i.category == "situation_codes"]
        assert len(situation_issues) == 1
        # Situation code errors should be ERROR severity
        assert situation_issues[0].severity == ValidationSeverity.ERROR

    @pytest.mark.asyncio
    async def test_mismatch_invalidates_game(self, sample_game_info: dict) -> None:
        """Situation code mismatch should mark game as invalid."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM second_snapshots" in query:
                return make_records(
                    [
                        {
                            "game_second": 100,
                            "situation_code": "4v5",  # Wrong
                            "home_skater_count": 5,
                            "away_skater_count": 5,  # Actually 5v5
                            "home_goalie_id": 8479973,
                            "away_goalie_id": 8477970,
                        },
                    ]
                )
            if "FROM game_shifts" in query:
                return []
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        result = await validator.validate_game(game_id=2024020500)

        # Game should be marked invalid due to ERROR severity issue
        assert not result.is_valid


class TestSituationCodeEdgeCases:
    """Edge case tests for situation code validation."""

    @pytest.mark.asyncio
    async def test_handles_unusual_skater_counts(self, sample_game_info: dict) -> None:
        """Should handle unusual but valid skater counts."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM second_snapshots" in query:
                return make_records(
                    [
                        # 3v3 overtime
                        {
                            "game_second": 3600,
                            "situation_code": "3v3",
                            "home_skater_count": 3,
                            "away_skater_count": 3,
                            "home_goalie_id": 8479973,
                            "away_goalie_id": 8477970,
                        },
                        # 4v3 in OT penalty
                        {
                            "game_second": 3700,
                            "situation_code": "4v3",
                            "home_skater_count": 4,
                            "away_skater_count": 3,
                            "home_goalie_id": 8479973,
                            "away_goalie_id": 8477970,
                        },
                    ]
                )
            if "FROM game_shifts" in query:
                return []
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        validations = await validator.validate_situation_codes(game_id=2024020500)

        # All valid
        assert len(validations) == 0

    @pytest.mark.asyncio
    async def test_handles_both_goalies_pulled(self, sample_game_info: dict) -> None:
        """Should handle extremely rare double empty net scenario."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            if "FROM boxscores" in query:
                return None
            return None

        db.fetchrow = mock_fetchrow

        async def mock_fetch(query: str, *args):
            if "FROM second_snapshots" in query:
                return make_records(
                    [
                        # Both goalies pulled (very rare but theoretically possible)
                        # When home_empty_net=True, the code will have EN prefix
                        {
                            "game_second": 3590,
                            "situation_code": "EN6v5",  # Home empty net takes precedence
                            "home_skater_count": 5,
                            "away_skater_count": 5,
                            "home_goalie_id": None,
                            "away_goalie_id": None,
                        },
                    ]
                )
            if "FROM game_shifts" in query:
                return []
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=0)

        validator = AnalyticsValidator(db)
        # Just verify it doesn't crash
        validations = await validator.validate_situation_codes(game_id=2024020500)
        # Result depends on how we handle this edge case
        assert isinstance(validations, list)

    @pytest.mark.asyncio
    async def test_handles_empty_snapshots(self, sample_game_info: dict) -> None:
        """Should handle games with no snapshots."""
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
        validations = await validator.validate_situation_codes(game_id=2024020500)

        # No snapshots = no validations (not an error)
        assert len(validations) == 0
