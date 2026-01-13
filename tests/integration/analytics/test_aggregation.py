"""Integration tests for aggregation service (T030-T033).

Validates aggregation functionality at all levels:
- T030: Shift-level aggregation
- T031: Period-level aggregation
- T032: Game-level aggregation
- T033: Season-level line combinations

Issue: #263 - Wave 5: Aggregation Functions
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from nhl_api.services.analytics.aggregation import (
    AggregationFilters,
    AggregationService,
    GameAggregation,
    LineCombinationStats,
    PeriodAggregation,
    SeasonAggregation,
    ShiftAggregation,
)
from tests.integration.analytics.conftest import make_records

if TYPE_CHECKING:
    from nhl_api.services.db.connection import DatabaseService


class TestAggregateShiftsIntegration:
    """Integration tests for shift-level aggregation (T030)."""

    @pytest.mark.asyncio
    async def test_aggregate_shifts_single_player(self) -> None:
        """Should aggregate shifts for a single player."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    # First shift
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "shift_number": 1,
                        "period": 1,
                        "start_second": 0,
                        "end_second": 45,
                        "toi_seconds": 46,
                        "situation_code": "5v5",
                        "situation_toi": 46,
                    },
                    # Second shift with PP time
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "shift_number": 2,
                        "period": 1,
                        "start_second": 120,
                        "end_second": 165,
                        "toi_seconds": 35,
                        "situation_code": "5v5",
                        "situation_toi": 35,
                    },
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "shift_number": 2,
                        "period": 1,
                        "start_second": 120,
                        "end_second": 165,
                        "toi_seconds": 11,
                        "situation_code": "5v4",
                        "situation_toi": 11,
                    },
                ]
            )
        )

        service = AggregationService(db)
        shifts = await service.aggregate_shifts(2024020500)

        assert len(shifts) == 2
        assert all(isinstance(s, ShiftAggregation) for s in shifts)

        # Check first shift
        shift1 = shifts[0]
        assert shift1.player_id == 8478402
        assert shift1.shift_number == 1
        assert shift1.toi_seconds == 46
        assert shift1.by_situation == {"5v5": 46}

        # Check second shift (combined situations)
        shift2 = shifts[1]
        assert shift2.shift_number == 2
        assert shift2.toi_seconds == 46  # 35 + 11
        assert shift2.by_situation == {"5v5": 35, "5v4": 11}

    @pytest.mark.asyncio
    async def test_aggregate_shifts_multiple_players(self) -> None:
        """Should aggregate shifts for multiple players."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "shift_number": 1,
                        "period": 1,
                        "start_second": 0,
                        "end_second": 45,
                        "toi_seconds": 46,
                        "situation_code": "5v5",
                        "situation_toi": 46,
                    },
                    {
                        "player_id": 8477934,
                        "game_id": 2024020500,
                        "shift_number": 1,
                        "period": 1,
                        "start_second": 0,
                        "end_second": 42,
                        "toi_seconds": 43,
                        "situation_code": "5v5",
                        "situation_toi": 43,
                    },
                ]
            )
        )

        service = AggregationService(db)
        shifts = await service.aggregate_shifts(2024020500)

        assert len(shifts) == 2
        player_ids = {s.player_id for s in shifts}
        assert player_ids == {8478402, 8477934}

    @pytest.mark.asyncio
    async def test_aggregate_shifts_with_player_filter(self) -> None:
        """Should filter to specific players."""
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])

        service = AggregationService(db)
        filters = AggregationFilters(player_ids=[8478402])
        await service.aggregate_shifts(2024020500, filters)

        # Verify fetch was called with player filter
        call_args = db.fetch.call_args
        assert 8478402 in call_args[0]


class TestAggregatePeriodsIntegration:
    """Integration tests for period-level aggregation (T031)."""

    @pytest.mark.asyncio
    async def test_aggregate_periods_all_periods(self) -> None:
        """Should aggregate across all periods."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "period": 1,
                        "situation_code": "5v5",
                        "toi_seconds": 380,
                        "shift_count": 7,
                    },
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "period": 1,
                        "situation_code": "5v4",
                        "toi_seconds": 40,
                        "shift_count": 2,
                    },
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "period": 2,
                        "situation_code": "5v5",
                        "toi_seconds": 400,
                        "shift_count": 8,
                    },
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "period": 3,
                        "situation_code": "5v5",
                        "toi_seconds": 350,
                        "shift_count": 7,
                    },
                ]
            )
        )

        service = AggregationService(db)
        periods = await service.aggregate_periods(2024020500)

        assert len(periods) == 3
        assert all(isinstance(p, PeriodAggregation) for p in periods)

        # Check period 1 (combined situations)
        p1 = next(p for p in periods if p.period == 1)
        assert p1.toi_seconds == 420  # 380 + 40
        assert p1.by_situation == {"5v5": 380, "5v4": 40}

        # Check totals
        total_toi = sum(p.toi_seconds for p in periods)
        assert total_toi == 1170  # 420 + 400 + 350

    @pytest.mark.asyncio
    async def test_aggregate_periods_with_situation_filter(self) -> None:
        """Should filter to specific situations."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "period": 1,
                        "situation_code": "5v5",
                        "toi_seconds": 380,
                        "shift_count": 7,
                    },
                ]
            )
        )

        service = AggregationService(db)
        filters = AggregationFilters(situation_codes=["5v5"])
        periods = await service.aggregate_periods(2024020500, filters)

        assert len(periods) == 1
        assert periods[0].by_situation == {"5v5": 380}


class TestAggregateGameIntegration:
    """Integration tests for game-level aggregation (T032)."""

    @pytest.mark.asyncio
    async def test_aggregate_game_all_players(self) -> None:
        """Should aggregate game stats for all players."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "situation_code": "5v5",
                        "toi_seconds": 1100,
                        "period_count": 3,
                        "shift_count": 20,
                    },
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "situation_code": "5v4",
                        "toi_seconds": 150,
                        "period_count": 3,
                        "shift_count": 5,
                    },
                    {
                        "player_id": 8477934,
                        "game_id": 2024020500,
                        "situation_code": "5v5",
                        "toi_seconds": 1050,
                        "period_count": 3,
                        "shift_count": 18,
                    },
                ]
            )
        )

        service = AggregationService(db)
        game_stats = await service.aggregate_game(2024020500)

        assert len(game_stats) == 2
        assert all(isinstance(g, GameAggregation) for g in game_stats)

        # Should be sorted by TOI descending
        assert game_stats[0].player_id == 8478402
        assert game_stats[0].toi_seconds == 1250
        assert game_stats[1].player_id == 8477934
        assert game_stats[1].toi_seconds == 1050

    @pytest.mark.asyncio
    async def test_aggregate_game_situation_breakdown(self) -> None:
        """Should include situation breakdown."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "situation_code": "5v5",
                        "toi_seconds": 1000,
                        "period_count": 3,
                        "shift_count": 18,
                    },
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "situation_code": "5v4",
                        "toi_seconds": 120,
                        "period_count": 2,
                        "shift_count": 4,
                    },
                    {
                        "player_id": 8478402,
                        "game_id": 2024020500,
                        "situation_code": "4v5",
                        "toi_seconds": 80,
                        "period_count": 2,
                        "shift_count": 3,
                    },
                ]
            )
        )

        service = AggregationService(db)
        game_stats = await service.aggregate_game(2024020500)

        assert len(game_stats) == 1
        assert game_stats[0].by_situation == {
            "5v5": 1000,
            "5v4": 120,
            "4v5": 80,
        }


class TestAggregateSeasonIntegration:
    """Integration tests for season-level aggregation."""

    @pytest.mark.asyncio
    async def test_aggregate_season_all_players(self) -> None:
        """Should aggregate season stats for all players."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    {
                        "player_id": 8478402,
                        "season_id": 20242025,
                        "situation_code": "5v5",
                        "toi_seconds": 45000,
                        "game_count": 40,
                    },
                    {
                        "player_id": 8478402,
                        "season_id": 20242025,
                        "situation_code": "5v4",
                        "toi_seconds": 4000,
                        "game_count": 40,
                    },
                    {
                        "player_id": 8477934,
                        "season_id": 20242025,
                        "situation_code": "5v5",
                        "toi_seconds": 42000,
                        "game_count": 38,
                    },
                ]
            )
        )

        service = AggregationService(db)
        season_stats = await service.aggregate_season(20242025)

        assert len(season_stats) == 2
        assert all(isinstance(s, SeasonAggregation) for s in season_stats)

        # Should be sorted by TOI descending
        mcdavid = season_stats[0]
        assert mcdavid.player_id == 8478402
        assert mcdavid.toi_seconds == 49000  # 45000 + 4000
        assert mcdavid.game_count == 40
        assert mcdavid.avg_toi_per_game == 1225.0

    @pytest.mark.asyncio
    async def test_aggregate_season_with_filters(self) -> None:
        """Should apply filters to season aggregation."""
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])

        service = AggregationService(db)
        filters = AggregationFilters(
            situation_codes=["5v5"],
            exclude_empty_net=True,
        )
        await service.aggregate_season(20242025, filters)

        # Verify filters applied
        call_args = db.fetch.call_args
        assert "5v5" in call_args[0]


class TestLineCombinationsIntegration:
    """Integration tests for line combinations (T033)."""

    @pytest.mark.asyncio
    async def test_get_line_combinations_basic(self) -> None:
        """Should return line combination stats."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    {
                        "sorted_players": [8477934, 8478402, 8478421],
                        "season_id": 20242025,
                        "situation_code": "5v5",
                        "toi_seconds": 5000,
                        "game_count": 30,
                    },
                    {
                        "sorted_players": [8477934, 8478402, 8478421],
                        "season_id": 20242025,
                        "situation_code": "5v4",
                        "toi_seconds": 500,
                        "game_count": 25,
                    },
                    {
                        "sorted_players": [8477846, 8477904, 8478042],
                        "season_id": 20242025,
                        "situation_code": "5v5",
                        "toi_seconds": 3000,
                        "game_count": 20,
                    },
                ]
            )
        )

        service = AggregationService(db)
        lines = await service.get_line_combinations(20242025, min_toi=300)

        assert len(lines) == 2
        assert all(isinstance(line, LineCombinationStats) for line in lines)

        # Should be sorted by TOI
        assert lines[0].toi_together == 5500  # Combined 5v5 + 5v4
        assert lines[0].player_ids == frozenset({8477934, 8478402, 8478421})
        assert lines[0].by_situation == {"5v5": 5000, "5v4": 500}

    @pytest.mark.asyncio
    async def test_get_line_combinations_with_player_count(self) -> None:
        """Should filter by player count."""
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])

        service = AggregationService(db)
        await service.get_line_combinations(
            20242025,
            min_players=5,  # Full 5-player lines only
            max_players=5,
        )

        # Verify player count params passed
        call_args = db.fetch.call_args
        assert 5 in call_args[0]

    @pytest.mark.asyncio
    async def test_get_line_combinations_empty_result(self) -> None:
        """Should handle no line combinations found."""
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])

        service = AggregationService(db)
        lines = await service.get_line_combinations(20242025, min_toi=10000)

        assert lines == []


class TestPlayerTOISummaryIntegration:
    """Integration tests for player TOI summary."""

    @pytest.mark.asyncio
    async def test_get_player_toi_summary_found(self) -> None:
        """Should return player summary when found."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=make_records(
                [
                    {
                        "player_id": 8478402,
                        "season_id": 20242025,
                        "situation_code": "5v5",
                        "toi_seconds": 50000,
                        "game_count": 41,
                    },
                ]
            )
        )

        service = AggregationService(db)
        summary = await service.get_player_toi_summary(8478402, 20242025)

        assert summary is not None
        assert summary.player_id == 8478402
        assert summary.toi_seconds == 50000
        assert summary.game_count == 41
        assert summary.avg_toi_per_game == pytest.approx(1219.51, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_player_toi_summary_not_found(self) -> None:
        """Should return None when player not found."""
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])

        service = AggregationService(db)
        summary = await service.get_player_toi_summary(9999999, 20242025)

        assert summary is None


class TestAggregationWithLiveDatabase:
    """Tests with live database connection (skipped if unavailable)."""

    @pytest.fixture
    def db_available(self, live_db_service: DatabaseService | None) -> bool:
        """Check if database is available."""
        return live_db_service is not None

    @pytest.mark.asyncio
    async def test_aggregate_game_live(
        self, live_db_service: DatabaseService | None
    ) -> None:
        """Aggregate game with live database."""
        if live_db_service is None:
            pytest.skip("Database not available")

        service = AggregationService(live_db_service)

        # Query for any game with data
        game_id = await live_db_service.fetchval(
            "SELECT game_id FROM second_snapshots LIMIT 1"
        )

        if game_id is None:
            pytest.skip("No second_snapshots data available")

        game_stats = await service.aggregate_game(game_id)

        assert isinstance(game_stats, list)
        if game_stats:
            assert all(isinstance(g, GameAggregation) for g in game_stats)
            # At least one player should have data
            assert any(g.toi_seconds > 0 for g in game_stats)

    @pytest.mark.asyncio
    async def test_line_combinations_live(
        self, live_db_service: DatabaseService | None
    ) -> None:
        """Get line combinations with live database."""
        if live_db_service is None:
            pytest.skip("Database not available")

        service = AggregationService(live_db_service)

        # Get a season with data
        season_id = await live_db_service.fetchval(
            "SELECT DISTINCT season_id FROM second_snapshots LIMIT 1"
        )

        if season_id is None:
            pytest.skip("No second_snapshots data available")

        lines = await service.get_line_combinations(
            season_id,
            min_toi=60,  # Low threshold for testing
        )

        assert isinstance(lines, list)
        # May or may not have data depending on season
