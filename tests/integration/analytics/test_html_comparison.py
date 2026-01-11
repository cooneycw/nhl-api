"""Integration tests for HTML shift report comparison (T017).

Validates that analytics TOI data matches the official NHL HTML shift
reports (TV/TH time-on-ice reports).

The key validation is:
- For each player, compare analytics TOI to HTML report TOI
- Validate shift counts match
- Flag discrepancies above tolerance

Issue: #260 - Wave 2: Validation & Quality (T017)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from nhl_api.validation.analytics_validation import (
    AnalyticsValidator,
    HTMLComparisonResult,
    ValidationSeverity,
)
from tests.integration.analytics.conftest import make_record, make_records

if TYPE_CHECKING:
    pass


class TestHTMLComparison:
    """Tests for comparing analytics to HTML shift reports."""

    @pytest.mark.asyncio
    async def test_compare_html_toi_exact_match(self, sample_game_info: dict) -> None:
        """Should pass when analytics TOI matches HTML report exactly."""
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
                        },
                    ]
                )
            if "FROM html_toi_reports" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "toi_seconds": 1250,
                            "shift_count": 25,
                        },
                    ]
                )
            if "FROM second_snapshots" in query:
                return []
            return []

        db.fetch = mock_fetch

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1250  # Exact match
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db)
        comparisons = await validator.compare_to_html_reports(game_id=2024020500)

        assert len(comparisons) == 1
        assert isinstance(comparisons[0], HTMLComparisonResult)
        assert comparisons[0].is_valid
        assert comparisons[0].difference_seconds == 0

    @pytest.mark.asyncio
    async def test_compare_html_toi_within_tolerance(
        self, sample_game_info: dict
    ) -> None:
        """Should pass when TOI difference is within tolerance."""
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
                        },
                    ]
                )
            if "FROM html_toi_reports" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "toi_seconds": 1251,  # 1 second difference
                            "shift_count": 25,
                        },
                    ]
                )
            if "FROM second_snapshots" in query:
                return []
            return []

        db.fetch = mock_fetch

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1250
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db, shift_tolerance=2)
        comparisons = await validator.compare_to_html_reports(game_id=2024020500)

        assert len(comparisons) == 1
        assert comparisons[0].is_valid
        assert comparisons[0].difference_seconds == 1

    @pytest.mark.asyncio
    async def test_compare_html_toi_exceeds_tolerance(
        self, sample_game_info: dict
    ) -> None:
        """Should fail when TOI difference exceeds tolerance."""
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
                        },
                    ]
                )
            if "FROM html_toi_reports" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "toi_seconds": 1260,  # 10 second difference
                            "shift_count": 25,
                        },
                    ]
                )
            if "FROM second_snapshots" in query:
                return []
            return []

        db.fetch = mock_fetch

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1250
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db, shift_tolerance=2)
        comparisons = await validator.compare_to_html_reports(game_id=2024020500)

        assert len(comparisons) == 1
        assert not comparisons[0].is_valid
        assert comparisons[0].difference_seconds == 10

    @pytest.mark.asyncio
    async def test_compare_html_no_reports_available(
        self, sample_game_info: dict
    ) -> None:
        """Should return empty list when no HTML reports available."""
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
                        },
                    ]
                )
            if "FROM html_toi_reports" in query:
                return []  # No HTML data
            if "FROM second_snapshots" in query:
                return []
            return []

        db.fetch = mock_fetch

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1250
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db)
        comparisons = await validator.compare_to_html_reports(game_id=2024020500)

        assert len(comparisons) == 0

    @pytest.mark.asyncio
    async def test_compare_html_game_not_found(self) -> None:
        """Should raise ValueError when game not found."""
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)

        validator = AnalyticsValidator(db)

        with pytest.raises(ValueError, match="Game 9999999 not found"):
            await validator.compare_to_html_reports(game_id=9999999)


class TestHTMLComparisonIssues:
    """Tests for HTML comparison issue generation."""

    @pytest.mark.asyncio
    async def test_generates_info_when_no_html_data(
        self, sample_game_info: dict
    ) -> None:
        """Should generate INFO issue when HTML reports not available."""
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

        html_issues = [i for i in result.issues if i.category == "html_comparison"]
        assert len(html_issues) == 1
        assert html_issues[0].severity == ValidationSeverity.INFO
        assert "No HTML TOI data" in html_issues[0].message

    @pytest.mark.asyncio
    async def test_generates_warning_on_mismatch(self, sample_game_info: dict) -> None:
        """Should generate WARNING when HTML vs analytics TOI differs."""
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
                        },
                    ]
                )
            if "FROM html_toi_reports" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "toi_seconds": 1270,  # 20 second difference
                            "shift_count": 25,
                        },
                    ]
                )
            if "FROM second_snapshots" in query:
                return []
            return []

        db.fetch = mock_fetch

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1250
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db, shift_tolerance=2)
        result = await validator.validate_game(game_id=2024020500)

        html_issues = [
            i
            for i in result.issues
            if i.category == "html_comparison" and "mismatch" in i.message.lower()
        ]
        assert len(html_issues) == 1
        assert html_issues[0].severity == ValidationSeverity.WARNING
        assert "8478402" in html_issues[0].message


class TestHTMLComparisonMultiplePlayers:
    """Tests for HTML comparison with multiple players."""

    @pytest.mark.asyncio
    async def test_compares_all_players_from_html(self, sample_game_info: dict) -> None:
        """Should compare all players in HTML report."""
        db = AsyncMock()
        home_team_id = sample_game_info["home_team_id"]
        away_team_id = sample_game_info["away_team_id"]

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
                            "team_id": home_team_id,
                            "total_seconds": 1250,
                            "shift_count": 25,
                        },
                        {
                            "player_id": 8477934,
                            "team_id": home_team_id,
                            "total_seconds": 1180,
                            "shift_count": 24,
                        },
                        {
                            "player_id": 8477846,
                            "team_id": away_team_id,
                            "total_seconds": 1100,
                            "shift_count": 22,
                        },
                    ]
                )
            if "FROM html_toi_reports" in query:
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": home_team_id,
                            "toi_seconds": 1250,
                            "shift_count": 25,
                        },
                        {
                            "player_id": 8477934,
                            "team_id": home_team_id,
                            "toi_seconds": 1180,
                            "shift_count": 24,
                        },
                        {
                            "player_id": 8477846,
                            "team_id": away_team_id,
                            "toi_seconds": 1100,
                            "shift_count": 22,
                        },
                    ]
                )
            if "FROM second_snapshots" in query:
                return []
            return []

        db.fetch = mock_fetch

        player_toi = {8478402: 1250, 8477934: 1180, 8477846: 1100}

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query and len(args) > 1:
                player_id = args[1]
                return player_toi.get(player_id, 0)
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db)
        comparisons = await validator.compare_to_html_reports(game_id=2024020500)

        assert len(comparisons) == 3
        assert all(c.is_valid for c in comparisons)
        assert {c.player_id for c in comparisons} == {8478402, 8477934, 8477846}

    @pytest.mark.asyncio
    async def test_handles_partial_html_data(self, sample_game_info: dict) -> None:
        """Should handle when HTML has fewer players than analytics."""
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
                        },
                        {
                            "player_id": 8477934,
                            "team_id": 22,
                            "total_seconds": 1180,
                            "shift_count": 24,
                        },
                    ]
                )
            if "FROM html_toi_reports" in query:
                # Only one player in HTML
                return make_records(
                    [
                        {
                            "player_id": 8478402,
                            "team_id": 22,
                            "toi_seconds": 1250,
                            "shift_count": 25,
                        },
                    ]
                )
            if "FROM second_snapshots" in query:
                return []
            return []

        db.fetch = mock_fetch

        async def mock_fetchval(query: str, *args):
            if "COUNT(*)" in query:
                return 1250 if 8478402 in args else 1180
            return 0

        db.fetchval = mock_fetchval

        validator = AnalyticsValidator(db)
        comparisons = await validator.compare_to_html_reports(game_id=2024020500)

        # Only should have comparison for player in HTML
        assert len(comparisons) == 1
        assert comparisons[0].player_id == 8478402
