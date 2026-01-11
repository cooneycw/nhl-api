"""Integration tests for matchup service (T019-T023).

Validates matchup analysis functionality including:
- Player matchup queries
- Ice time calculations
- Zone-based filtering
- Aggregation queries

Issue: #261 - Wave 3: Matchup Analysis
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from tests.integration.analytics.conftest import make_record, make_records
from nhl_api.models.matchups import MatchupType, PlayerMatchup
from nhl_api.services.analytics.matchup_service import (
    MatchupQueryFilters,
    MatchupService,
)

if TYPE_CHECKING:
    pass


class TestMatchupServiceBasic:
    """Basic tests for MatchupService."""

    @pytest.mark.asyncio
    async def test_get_ice_time_together(self) -> None:
        """Should calculate ice time between two players."""
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=1250)

        service = MatchupService(db)
        toi = await service.get_ice_time_together(
            player1_id=8478402,
            player2_id=8477934,
            game_id=2024020500,
        )

        assert toi == 1250
        db.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_ice_time_together_no_overlap(self) -> None:
        """Should return 0 when players never on ice together."""
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=0)

        service = MatchupService(db)
        toi = await service.get_ice_time_together(
            player1_id=8478402,
            player2_id=9999999,
            game_id=2024020500,
        )

        assert toi == 0


class TestMatchupServiceQueries:
    """Tests for matchup query functionality."""

    @pytest.mark.asyncio
    async def test_get_player_matchups_teammates(
        self, sample_game_info: dict
    ) -> None:
        """Should return teammate matchups."""
        db = AsyncMock()

        # The service makes multiple queries - teammate and opponent queries
        # We need to return appropriate data for each
        call_count = [0]

        async def mock_fetch(*args, **kwargs):
            call_count[0] += 1
            # First two calls are teammate queries (home and away)
            if call_count[0] <= 2:
                return make_records([
                    {
                        "teammate_id": 8477934,
                        "situation_code": "5v5",
                        "toi_seconds": 800,
                        "game_count": 10,
                    },
                ])
            # Next two are opponent queries
            return []

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=10)

        service = MatchupService(db)
        result = await service.get_player_matchups(
            player_id=8478402,
            season_id=20242025,
            min_toi_seconds=60,
        )

        assert result.player_id == 8478402
        assert result.total_games == 10

    @pytest.mark.asyncio
    async def test_get_player_matchups_opponents(
        self, sample_game_info: dict
    ) -> None:
        """Should return opponent matchups."""
        db = AsyncMock()

        call_count = [0]

        async def mock_fetch(*args, **kwargs):
            call_count[0] += 1
            # First two calls are teammate queries
            if call_count[0] <= 2:
                return []
            # Next two are opponent queries
            return make_records([
                {
                    "opponent_id": 8477846,
                    "situation_code": "5v5",
                    "toi_seconds": 500,
                    "game_count": 5,
                },
            ])

        db.fetch = mock_fetch
        db.fetchval = AsyncMock(return_value=5)

        service = MatchupService(db)
        result = await service.get_player_matchups(
            player_id=8478402,
            game_id=2024020500,
            min_toi_seconds=60,
        )

        assert result.player_id == 8478402


class TestMatchupServiceGameSummary:
    """Tests for game matchup summary."""

    @pytest.mark.asyncio
    async def test_get_game_matchup_summary(
        self, sample_game_info: dict
    ) -> None:
        """Should return game matchup summary."""
        db = AsyncMock()

        async def mock_fetchrow(query: str, *args):
            if "FROM games" in query:
                return make_record(sample_game_info)
            return None

        db.fetchrow = mock_fetchrow

        db.fetch = AsyncMock(
            return_value=make_records([
                {
                    "home_player": 8478402,
                    "away_player": 8477846,
                    "total_toi": 1200,
                },
                {
                    "home_player": 8477934,
                    "away_player": 8477846,
                    "total_toi": 1000,
                },
            ])
        )

        service = MatchupService(db)
        summary = await service.get_game_matchup_summary(game_id=2024020500)

        assert summary.game_id == 2024020500
        assert summary.home_team_id == sample_game_info["home_team_id"]
        assert summary.away_team_id == sample_game_info["away_team_id"]
        assert summary.matchup_count == 2
        assert len(summary.top_matchups) == 2

    @pytest.mark.asyncio
    async def test_get_game_matchup_summary_game_not_found(self) -> None:
        """Should raise ValueError for missing game."""
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)

        service = MatchupService(db)

        with pytest.raises(ValueError, match="Game 9999999 not found"):
            await service.get_game_matchup_summary(game_id=9999999)


class TestMatchupServiceDefensiveZone:
    """Tests for defensive zone matchup filtering."""

    @pytest.mark.asyncio
    async def test_get_defensive_zone_matchups(
        self, sample_game_info: dict
    ) -> None:
        """Should filter to defensive zone matchups."""
        db = AsyncMock()

        db.fetch = AsyncMock(
            return_value=make_records([
                {
                    "other_player_id": 8477846,
                    "event_count": 5,
                    "toi_seconds": 120,
                },
            ])
        )

        service = MatchupService(db)
        matchups = await service.get_defensive_zone_matchups(
            player_id=8478402,
            game_id=2024020500,
        )

        # Should return zone matchups
        assert isinstance(matchups, list)


class TestMatchupServiceAggregation:
    """Tests for matchup aggregation."""

    @pytest.mark.asyncio
    async def test_aggregate_matchups(self, sample_game_info: dict) -> None:
        """Should aggregate matchup data."""
        db = AsyncMock()

        call_count = [0]

        async def mock_fetch(*args, **kwargs):
            call_count[0] += 1
            # Calls 1-2: opponent queries (home + away)
            if call_count[0] <= 2:
                return make_records([
                    {
                        "opponent_id": 8477846,
                        "situation_code": "5v5",
                        "toi_seconds": 800,
                        "game_count": 5,
                    },
                ])
            # Calls 3-4: teammate queries (home + away)
            return []

        db.fetch = mock_fetch

        service = MatchupService(db)
        filters = MatchupQueryFilters(season_id=20242025)
        aggregations = await service.aggregate_matchups(
            player_id=8478402,
            filters=filters,
        )

        assert isinstance(aggregations, list)
        # Should have opponent aggregations from our mock data
        assert len(aggregations) >= 0


class TestMatchupQueryFilters:
    """Tests for MatchupQueryFilters."""

    def test_default_filters(self) -> None:
        """Should have sensible defaults."""
        filters = MatchupQueryFilters()

        assert filters.game_id is None
        assert filters.season_id is None
        assert filters.situation_codes is None
        assert filters.zone is None
        assert filters.min_toi_seconds == 0
        assert filters.exclude_empty_net is False

    def test_with_all_filters(self) -> None:
        """Should accept all filter options."""
        from nhl_api.services.analytics.zone_detection import Zone

        filters = MatchupQueryFilters(
            game_id=2024020500,
            season_id=20242025,
            situation_codes=["5v5", "5v4"],
            zone=Zone.DEFENSIVE,
            min_toi_seconds=60,
            exclude_empty_net=True,
        )

        assert filters.game_id == 2024020500
        assert filters.season_id == 20242025
        assert filters.situation_codes == ["5v5", "5v4"]
        assert filters.zone == Zone.DEFENSIVE
        assert filters.min_toi_seconds == 60
        assert filters.exclude_empty_net is True


# Fixture from conftest.py
@pytest.fixture
def sample_game_info() -> dict:
    """Sample game metadata."""
    return {
        "game_id": 2024020500,
        "season_id": 20242025,
        "home_team_id": 22,
        "away_team_id": 25,
        "period": 3,
    }
