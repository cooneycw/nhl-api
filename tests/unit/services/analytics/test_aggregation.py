"""Unit tests for AggregationService.

Tests the aggregation logic for shift, period, game, and season levels.

Issue: #263 - Wave 5: Aggregation Functions (T030-T033)
"""

from __future__ import annotations

from typing import Any
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


class DictLikeRecord:
    """A dict-like object that mimics asyncpg Record behavior."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __getattr__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError as err:
            raise AttributeError(
                f"'{type(self).__name__}' has no attribute '{key}'"
            ) from err

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()


def make_records(data_list: list[dict[str, Any]]) -> list[DictLikeRecord]:
    """Helper to create a list of DictLikeRecords from a list of dicts."""
    return [DictLikeRecord(d) for d in data_list]


class TestAggregationFilters:
    """Tests for AggregationFilters dataclass."""

    def test_default_values(self) -> None:
        """Default filters have sensible values."""
        filters = AggregationFilters()
        assert filters.player_ids is None
        assert filters.situation_codes is None
        assert filters.exclude_empty_net is False
        assert filters.exclude_stoppages is True

    def test_custom_values(self) -> None:
        """Custom filter values are stored."""
        filters = AggregationFilters(
            player_ids=[8478402, 8477934],
            situation_codes=["5v5", "5v4"],
            exclude_empty_net=True,
            exclude_stoppages=False,
        )
        assert filters.player_ids == [8478402, 8477934]
        assert filters.situation_codes == ["5v5", "5v4"]
        assert filters.exclude_empty_net is True
        assert filters.exclude_stoppages is False


class TestShiftAggregation:
    """Tests for ShiftAggregation dataclass."""

    def test_creation(self) -> None:
        """ShiftAggregation stores all values."""
        shift = ShiftAggregation(
            player_id=8478402,
            game_id=2024020500,
            shift_number=1,
            period=1,
            start_second=0,
            end_second=45,
            toi_seconds=46,
            by_situation={"5v5": 40, "5v4": 6},
        )
        assert shift.player_id == 8478402
        assert shift.game_id == 2024020500
        assert shift.shift_number == 1
        assert shift.period == 1
        assert shift.start_second == 0
        assert shift.end_second == 45
        assert shift.toi_seconds == 46
        assert shift.by_situation == {"5v5": 40, "5v4": 6}

    def test_default_by_situation(self) -> None:
        """by_situation defaults to empty dict."""
        shift = ShiftAggregation(
            player_id=8478402,
            game_id=2024020500,
            shift_number=1,
            period=1,
            start_second=0,
            end_second=45,
            toi_seconds=46,
        )
        assert shift.by_situation == {}


class TestPeriodAggregation:
    """Tests for PeriodAggregation dataclass."""

    def test_creation(self) -> None:
        """PeriodAggregation stores all values."""
        period = PeriodAggregation(
            player_id=8478402,
            game_id=2024020500,
            period=1,
            toi_seconds=420,
            shift_count=8,
            by_situation={"5v5": 380, "5v4": 40},
        )
        assert period.player_id == 8478402
        assert period.period == 1
        assert period.toi_seconds == 420
        assert period.shift_count == 8


class TestGameAggregation:
    """Tests for GameAggregation dataclass."""

    def test_creation(self) -> None:
        """GameAggregation stores all values."""
        game = GameAggregation(
            player_id=8478402,
            game_id=2024020500,
            toi_seconds=1250,
            period_count=3,
            shift_count=25,
            by_situation={"5v5": 1100, "5v4": 100, "4v5": 50},
        )
        assert game.player_id == 8478402
        assert game.game_id == 2024020500
        assert game.toi_seconds == 1250
        assert game.period_count == 3
        assert game.shift_count == 25


class TestSeasonAggregation:
    """Tests for SeasonAggregation dataclass."""

    def test_creation(self) -> None:
        """SeasonAggregation stores all values."""
        season = SeasonAggregation(
            player_id=8478402,
            season_id=20242025,
            toi_seconds=50000,
            game_count=40,
            avg_toi_per_game=1250.0,
            by_situation={"5v5": 45000, "5v4": 4000, "4v5": 1000},
        )
        assert season.player_id == 8478402
        assert season.season_id == 20242025
        assert season.toi_seconds == 50000
        assert season.game_count == 40
        assert season.avg_toi_per_game == 1250.0


class TestLineCombinationStats:
    """Tests for LineCombinationStats dataclass."""

    def test_creation(self) -> None:
        """LineCombinationStats stores all values."""
        line = LineCombinationStats(
            player_ids=frozenset({8478402, 8477934, 8478421}),
            season_id=20242025,
            toi_together=5000,
            game_count=30,
            by_situation={"5v5": 4500, "5v4": 500},
        )
        assert 8478402 in line.player_ids
        assert 8477934 in line.player_ids
        assert 8478421 in line.player_ids
        assert line.season_id == 20242025
        assert line.toi_together == 5000
        assert line.game_count == 30


class TestAggregationServiceBuildWhereClause:
    """Tests for _build_where_clause method."""

    @pytest.fixture
    def service(self) -> AggregationService:
        """Create AggregationService with mock db."""
        db = AsyncMock()
        return AggregationService(db)

    def test_no_filters(self, service: AggregationService) -> None:
        """No filters adds is_stoppage filter by default."""
        conditions, params, next_idx = service._build_where_clause(None)
        assert "is_stoppage = false" in conditions
        assert params == []
        assert next_idx == 1

    def test_with_game_id(self, service: AggregationService) -> None:
        """game_id filter is added."""
        conditions, params, next_idx = service._build_where_clause(
            None, game_id=2024020500
        )
        assert "game_id = $1" in conditions
        assert params == [2024020500]
        assert next_idx == 2

    def test_with_season_id(self, service: AggregationService) -> None:
        """season_id filter is added."""
        conditions, params, next_idx = service._build_where_clause(
            None, season_id=20242025
        )
        assert "season_id = $1" in conditions
        assert params == [20242025]
        assert next_idx == 2

    def test_with_situation_codes(self, service: AggregationService) -> None:
        """situation_codes filter is added."""
        filters = AggregationFilters(situation_codes=["5v5", "5v4"])
        conditions, params, next_idx = service._build_where_clause(filters)
        assert "situation_code IN ($1, $2)" in conditions
        assert params == ["5v5", "5v4"]

    def test_with_exclude_empty_net(self, service: AggregationService) -> None:
        """exclude_empty_net filter is added."""
        filters = AggregationFilters(exclude_empty_net=True)
        conditions, params, next_idx = service._build_where_clause(filters)
        assert "is_empty_net = false" in conditions

    def test_with_exclude_stoppages_false(self, service: AggregationService) -> None:
        """exclude_stoppages=False removes is_stoppage filter."""
        filters = AggregationFilters(exclude_stoppages=False)
        conditions, params, next_idx = service._build_where_clause(filters)
        assert "is_stoppage = false" not in conditions

    def test_with_table_alias(self, service: AggregationService) -> None:
        """Table alias is applied to conditions."""
        conditions, params, next_idx = service._build_where_clause(
            None, game_id=2024020500, table_alias="s"
        )
        assert "s.game_id = $1" in conditions


class TestAggregationServiceAggregateShifts:
    """Tests for aggregate_shifts method."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database service."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db: AsyncMock) -> AggregationService:
        """Create AggregationService with mock db."""
        return AggregationService(mock_db)

    @pytest.mark.asyncio
    async def test_aggregate_shifts_returns_list(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """aggregate_shifts returns list of ShiftAggregation."""
        mock_db.fetch.return_value = make_records(
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
                    "player_id": 8478402,
                    "game_id": 2024020500,
                    "shift_number": 2,
                    "period": 1,
                    "start_second": 120,
                    "end_second": 165,
                    "toi_seconds": 46,
                    "situation_code": "5v5",
                    "situation_toi": 46,
                },
            ]
        )

        result = await service.aggregate_shifts(2024020500)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(r, ShiftAggregation) for r in result)
        assert result[0].player_id == 8478402
        assert result[0].shift_number == 1

    @pytest.mark.asyncio
    async def test_aggregate_shifts_with_filters(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """aggregate_shifts applies filters."""
        mock_db.fetch.return_value = []

        filters = AggregationFilters(
            situation_codes=["5v5"],
            player_ids=[8478402],
        )
        await service.aggregate_shifts(2024020500, filters)

        # Verify fetch was called with parameters
        mock_db.fetch.assert_called_once()
        call_args = mock_db.fetch.call_args
        assert "5v5" in call_args[0]  # situation code in params

    @pytest.mark.asyncio
    async def test_aggregate_shifts_combines_situations(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """Multiple situations in same shift are combined."""
        mock_db.fetch.return_value = make_records(
            [
                {
                    "player_id": 8478402,
                    "game_id": 2024020500,
                    "shift_number": 1,
                    "period": 1,
                    "start_second": 0,
                    "end_second": 60,
                    "toi_seconds": 40,
                    "situation_code": "5v5",
                    "situation_toi": 40,
                },
                {
                    "player_id": 8478402,
                    "game_id": 2024020500,
                    "shift_number": 1,
                    "period": 1,
                    "start_second": 0,
                    "end_second": 60,
                    "toi_seconds": 21,
                    "situation_code": "5v4",
                    "situation_toi": 21,
                },
            ]
        )

        result = await service.aggregate_shifts(2024020500)

        assert len(result) == 1  # Single shift
        assert result[0].toi_seconds == 61  # Combined TOI
        assert result[0].by_situation == {"5v5": 40, "5v4": 21}


class TestAggregationServiceAggregatePeriods:
    """Tests for aggregate_periods method."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database service."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db: AsyncMock) -> AggregationService:
        """Create AggregationService with mock db."""
        return AggregationService(mock_db)

    @pytest.mark.asyncio
    async def test_aggregate_periods_returns_list(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """aggregate_periods returns list of PeriodAggregation."""
        mock_db.fetch.return_value = make_records(
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
            ]
        )

        result = await service.aggregate_periods(2024020500)

        assert isinstance(result, list)
        assert len(result) == 1  # Combined into one period
        assert isinstance(result[0], PeriodAggregation)
        assert result[0].player_id == 8478402
        assert result[0].period == 1
        assert result[0].toi_seconds == 420  # Combined
        assert result[0].by_situation == {"5v5": 380, "5v4": 40}


class TestAggregationServiceAggregateGame:
    """Tests for aggregate_game method."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database service."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db: AsyncMock) -> AggregationService:
        """Create AggregationService with mock db."""
        return AggregationService(mock_db)

    @pytest.mark.asyncio
    async def test_aggregate_game_returns_list(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """aggregate_game returns list of GameAggregation."""
        mock_db.fetch.return_value = make_records(
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

        result = await service.aggregate_game(2024020500)

        assert isinstance(result, list)
        assert len(result) == 2  # Two players
        assert all(isinstance(r, GameAggregation) for r in result)

        # Results should be sorted by TOI descending
        assert result[0].player_id == 8478402
        assert result[0].toi_seconds == 1250
        assert result[1].player_id == 8477934
        assert result[1].toi_seconds == 1050


class TestAggregationServiceAggregateSeason:
    """Tests for aggregate_season method."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database service."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db: AsyncMock) -> AggregationService:
        """Create AggregationService with mock db."""
        return AggregationService(mock_db)

    @pytest.mark.asyncio
    async def test_aggregate_season_returns_list(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """aggregate_season returns list of SeasonAggregation."""
        mock_db.fetch.return_value = make_records(
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
                    "player_id": 8478402,
                    "season_id": 20242025,
                    "situation_code": "4v5",
                    "toi_seconds": 1000,
                    "game_count": 38,
                },
            ]
        )

        result = await service.aggregate_season(20242025)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], SeasonAggregation)
        assert result[0].player_id == 8478402
        assert result[0].season_id == 20242025
        assert result[0].toi_seconds == 50000  # Combined
        assert result[0].game_count == 40  # Max
        assert result[0].avg_toi_per_game == 1250.0  # 50000 / 40

    @pytest.mark.asyncio
    async def test_aggregate_season_handles_zero_games(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """aggregate_season handles zero games (avoids division by zero)."""
        mock_db.fetch.return_value = make_records(
            [
                {
                    "player_id": 8478402,
                    "season_id": 20242025,
                    "situation_code": "5v5",
                    "toi_seconds": 0,
                    "game_count": 0,
                },
            ]
        )

        result = await service.aggregate_season(20242025)

        assert len(result) == 1
        assert result[0].avg_toi_per_game == 0.0


class TestAggregationServiceLineCombinations:
    """Tests for get_line_combinations method."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database service."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db: AsyncMock) -> AggregationService:
        """Create AggregationService with mock db."""
        return AggregationService(mock_db)

    @pytest.mark.asyncio
    async def test_get_line_combinations_returns_list(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """get_line_combinations returns list of LineCombinationStats."""
        mock_db.fetch.return_value = make_records(
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
            ]
        )

        result = await service.get_line_combinations(20242025, min_toi=300)

        assert isinstance(result, list)
        assert len(result) == 1  # Combined into one line
        assert isinstance(result[0], LineCombinationStats)
        assert result[0].player_ids == frozenset({8477934, 8478402, 8478421})
        assert result[0].toi_together == 5500
        assert result[0].game_count == 30
        assert result[0].by_situation == {"5v5": 5000, "5v4": 500}

    @pytest.mark.asyncio
    async def test_get_line_combinations_sorted_by_toi(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """Line combinations are sorted by TOI descending."""
        mock_db.fetch.return_value = make_records(
            [
                {
                    "sorted_players": [8477934, 8478402, 8478421],
                    "season_id": 20242025,
                    "situation_code": "5v5",
                    "toi_seconds": 3000,
                    "game_count": 30,
                },
                {
                    "sorted_players": [8477846, 8477904, 8478042],
                    "season_id": 20242025,
                    "situation_code": "5v5",
                    "toi_seconds": 5000,
                    "game_count": 25,
                },
            ]
        )

        result = await service.get_line_combinations(20242025)

        assert len(result) == 2
        assert result[0].toi_together == 5000  # Higher TOI first
        assert result[1].toi_together == 3000


class TestAggregationServicePlayerTOISummary:
    """Tests for get_player_toi_summary method."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create mock database service."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db: AsyncMock) -> AggregationService:
        """Create AggregationService with mock db."""
        return AggregationService(mock_db)

    @pytest.mark.asyncio
    async def test_get_player_toi_summary_returns_aggregation(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """get_player_toi_summary returns SeasonAggregation."""
        mock_db.fetch.return_value = make_records(
            [
                {
                    "player_id": 8478402,
                    "season_id": 20242025,
                    "situation_code": "5v5",
                    "toi_seconds": 50000,
                    "game_count": 40,
                },
            ]
        )

        result = await service.get_player_toi_summary(8478402, 20242025)

        assert result is not None
        assert isinstance(result, SeasonAggregation)
        assert result.player_id == 8478402

    @pytest.mark.asyncio
    async def test_get_player_toi_summary_returns_none_when_no_data(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """get_player_toi_summary returns None when player not found."""
        mock_db.fetch.return_value = []

        result = await service.get_player_toi_summary(9999999, 20242025)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_player_toi_summary_uses_provided_filters(
        self, service: AggregationService, mock_db: AsyncMock
    ) -> None:
        """get_player_toi_summary applies provided filters."""
        mock_db.fetch.return_value = make_records(
            [
                {
                    "player_id": 8478402,
                    "season_id": 20242025,
                    "situation_code": "5v5",
                    "toi_seconds": 45000,
                    "game_count": 40,
                },
            ]
        )

        filters = AggregationFilters(situation_codes=["5v5"])
        result = await service.get_player_toi_summary(8478402, 20242025, filters)

        assert result is not None
        # Filters should override player_ids with the specified player
        assert result.player_id == 8478402
