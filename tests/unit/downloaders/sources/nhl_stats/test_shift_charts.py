"""Unit tests for ShiftChartsDownloader.

Tests cover:
- Configuration and initialization
- Shift record parsing
- Shift chart parsing
- Goal event handling
- Download flow
- Factory function
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.downloaders.base.protocol import DownloadError
from nhl_api.downloaders.sources.nhl_stats.shift_charts import (
    ShiftChartsDownloader,
    ShiftChartsDownloaderConfig,
    create_shift_charts_downloader,
)
from nhl_api.models.shifts import GOAL_TYPE_CODE, SHIFT_TYPE_CODE, ParsedShiftChart

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def config() -> ShiftChartsDownloaderConfig:
    """Create test configuration."""
    return ShiftChartsDownloaderConfig(
        requests_per_second=10.0,  # Fast for testing
        max_retries=2,
        http_timeout=5.0,
        include_raw_response=False,
    )


@pytest.fixture
def downloader(config: ShiftChartsDownloaderConfig) -> ShiftChartsDownloader:
    """Create test downloader instance."""
    return ShiftChartsDownloader(config)


@pytest.fixture
def sample_api_response() -> dict[str, Any]:
    """Load sample API response from fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "nhl_stats"
        / "shift_charts_2024020500.json"
    )
    with open(fixture_path) as f:
        return cast(dict[str, Any], json.load(f))


@pytest.fixture
def sample_shift_record() -> dict[str, Any]:
    """Sample shift record from API."""
    return {
        "id": 14765329,
        "detailCode": 0,
        "duration": "00:47",
        "endTime": "01:15",
        "eventDescription": None,
        "eventDetails": None,
        "eventNumber": 109,
        "firstName": "Brent",
        "gameId": 2024020500,
        "hexValue": "#C8102E",
        "lastName": "Burns",
        "period": 1,
        "playerId": 8470613,
        "shiftNumber": 1,
        "startTime": "00:28",
        "teamAbbrev": "CAR",
        "teamId": 12,
        "teamName": "Carolina Hurricanes",
        "typeCode": 517,
    }


@pytest.fixture
def goal_event_record() -> dict[str, Any]:
    """Sample goal event record from API."""
    return {
        "id": 14765999,
        "detailCode": 803,
        "duration": None,
        "endTime": "05:30",
        "eventDescription": "EVG",
        "eventDetails": "Jordan Staal",
        "eventNumber": 200,
        "firstName": "Jordan",
        "gameId": 2024020500,
        "hexValue": "#C8102E",
        "lastName": "Staal",
        "period": 1,
        "playerId": 8473533,
        "shiftNumber": 5,
        "startTime": "05:30",
        "teamAbbrev": "CAR",
        "teamId": 12,
        "teamName": "Carolina Hurricanes",
        "typeCode": 505,
    }


# =============================================================================
# Configuration Tests
# =============================================================================


class TestShiftChartsDownloaderConfig:
    """Tests for ShiftChartsDownloaderConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ShiftChartsDownloaderConfig()
        assert config.base_url == "https://api.nhle.com/stats/rest/en"
        assert config.requests_per_second == 5.0
        assert config.max_retries == 3
        assert config.include_raw_response is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = ShiftChartsDownloaderConfig(
            requests_per_second=10.0,
            include_raw_response=True,
        )
        assert config.requests_per_second == 10.0
        assert config.include_raw_response is True


# =============================================================================
# Initialization Tests
# =============================================================================


class TestShiftChartsDownloaderInit:
    """Tests for ShiftChartsDownloader initialization."""

    def test_source_name(self, downloader: ShiftChartsDownloader) -> None:
        """Test source_name property matches data_sources table."""
        assert downloader.source_name == "shift_chart"

    def test_default_game_ids(self, downloader: ShiftChartsDownloader) -> None:
        """Test default empty game IDs."""
        assert downloader._game_ids == []

    def test_init_with_game_ids(self, config: ShiftChartsDownloaderConfig) -> None:
        """Test initialization with game IDs."""
        game_ids = [2024020500, 2024020501]
        downloader = ShiftChartsDownloader(config, game_ids=game_ids)
        assert downloader._game_ids == game_ids


# =============================================================================
# Shift Record Parsing Tests
# =============================================================================


class TestParseShiftRecord:
    """Tests for _parse_shift_record method."""

    def test_parse_regular_shift(
        self, downloader: ShiftChartsDownloader, sample_shift_record: dict[str, Any]
    ) -> None:
        """Test parsing a regular shift record."""
        shift = downloader._parse_shift_record(sample_shift_record, 2024020500)

        assert shift.shift_id == 14765329
        assert shift.game_id == 2024020500
        assert shift.player_id == 8470613
        assert shift.first_name == "Brent"
        assert shift.last_name == "Burns"
        assert shift.team_id == 12
        assert shift.team_abbrev == "CAR"
        assert shift.period == 1
        assert shift.shift_number == 1
        assert shift.start_time == "00:28"
        assert shift.end_time == "01:15"
        assert shift.duration_seconds == 47
        assert shift.type_code == SHIFT_TYPE_CODE
        assert shift.is_goal_event is False
        assert shift.hex_value == "#C8102E"

    def test_parse_goal_event(
        self, downloader: ShiftChartsDownloader, goal_event_record: dict[str, Any]
    ) -> None:
        """Test parsing a goal event record."""
        shift = downloader._parse_shift_record(goal_event_record, 2024020500)

        assert shift.type_code == GOAL_TYPE_CODE
        assert shift.is_goal_event is True
        assert shift.event_description == "EVG"
        assert shift.event_details == "Jordan Staal"
        assert shift.detail_code == 803
        assert shift.duration_seconds == 0  # Null duration

    def test_parse_missing_fields(self, downloader: ShiftChartsDownloader) -> None:
        """Test parsing with missing fields uses defaults."""
        record = {"id": 123}
        shift = downloader._parse_shift_record(record, 2024020500)

        assert shift.shift_id == 123
        assert shift.game_id == 2024020500
        assert shift.player_id == 0
        assert shift.first_name == ""
        assert shift.start_time == "00:00"
        assert shift.duration_seconds == 0


# =============================================================================
# Shift Chart Parsing Tests
# =============================================================================


class TestParseShiftChart:
    """Tests for _parse_shift_chart method."""

    def test_parse_shift_chart(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test parsing a full shift chart."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        assert chart.game_id == 2024020500
        assert chart.season_id == 20242025
        assert chart.total_shifts == 7
        assert len(chart.shifts) == 7

    def test_parse_empty_chart(self, downloader: ShiftChartsDownloader) -> None:
        """Test parsing an empty shift chart."""
        chart = downloader._parse_shift_chart([], 2024020500)

        assert chart.game_id == 2024020500
        assert chart.total_shifts == 0
        assert len(chart.shifts) == 0
        assert chart.home_team_id is None
        assert chart.away_team_id is None

    def test_team_ids_extracted(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that team IDs are extracted from shifts."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        # Both teams should be identified
        team_ids = {chart.home_team_id, chart.away_team_id}
        assert 12 in team_ids  # CAR
        assert 2 in team_ids  # NYI


# =============================================================================
# Fetch Game Tests
# =============================================================================


class TestFetchGame:
    """Tests for _fetch_game method."""

    @pytest.mark.asyncio
    async def test_fetch_game_success(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test successful game fetch."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = sample_api_response

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await downloader._fetch_game(2024020500)

        assert result["game_id"] == 2024020500
        assert "shifts" in result
        assert len(result["shifts"]) == 7
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_game_http_error(
        self, downloader: ShiftChartsDownloader
    ) -> None:
        """Test handling of HTTP errors."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status = 404

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(DownloadError) as exc_info:
                await downloader._fetch_game(2024020500)

            assert exc_info.value.game_id == 2024020500
            assert "404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_game_includes_raw_response(
        self, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that raw response is included when configured."""
        config = ShiftChartsDownloaderConfig(include_raw_response=True)
        downloader = ShiftChartsDownloader(config)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = sample_api_response

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await downloader._fetch_game(2024020500)

        assert "_raw" in result
        assert result["_raw"] == sample_api_response


# =============================================================================
# Fetch Season Games Tests
# =============================================================================


class TestFetchSeasonGames:
    """Tests for _fetch_season_games method."""

    @pytest.mark.asyncio
    async def test_fetch_season_games_yields_ids(
        self, downloader: ShiftChartsDownloader
    ) -> None:
        """Test that _fetch_season_games yields game IDs."""
        game_ids = [2024020500, 2024020501, 2024020502]
        downloader.set_game_ids(game_ids)

        results = []
        async for game_id in downloader._fetch_season_games(20242025):
            results.append(game_id)

        assert results == game_ids

    @pytest.mark.asyncio
    async def test_fetch_season_games_empty(
        self, downloader: ShiftChartsDownloader
    ) -> None:
        """Test that empty game IDs yields nothing."""
        results = []
        async for game_id in downloader._fetch_season_games(20242025):
            results.append(game_id)
        assert results == []


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateShiftChartsDownloader:
    """Tests for create_shift_charts_downloader factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating downloader with default settings."""
        downloader = create_shift_charts_downloader()

        assert downloader.source_name == "shift_chart"
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_settings(self) -> None:
        """Test creating downloader with custom settings."""
        downloader = create_shift_charts_downloader(
            requests_per_second=10.0,
            max_retries=5,
            include_raw_response=True,
        )

        assert downloader.config.requests_per_second == 10.0
        assert downloader.config.max_retries == 5
        assert downloader._config.include_raw_response is True


# =============================================================================
# Module Export Tests
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_exports_from_nhl_stats(self) -> None:
        """Test that classes are exported from nhl_stats package."""
        from nhl_api.downloaders.sources.nhl_stats import (
            ShiftChartsDownloader,
            ShiftChartsDownloaderConfig,
            create_shift_charts_downloader,
        )

        assert ShiftChartsDownloader is not None
        assert ShiftChartsDownloaderConfig is not None
        assert create_shift_charts_downloader is not None


# =============================================================================
# Integration with Models Tests
# =============================================================================


class TestModelIntegration:
    """Tests for integration with shift models."""

    def test_parsed_chart_is_correct_type(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that parser returns correct model type."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        assert isinstance(chart, ParsedShiftChart)

    def test_to_dict_produces_valid_result(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that to_dict produces valid serializable result."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)
        result = chart.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert len(json_str) > 0

        # Should contain expected keys
        assert "game_id" in result
        assert "shifts" in result
        assert isinstance(result["shifts"], list)


# =============================================================================
# Persistence Tests
# =============================================================================


class TestPersist:
    """Tests for persist method."""

    @pytest.mark.asyncio
    async def test_persist_empty_list(self, downloader: ShiftChartsDownloader) -> None:
        """Test persisting an empty list returns 0."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        count = await downloader.persist(mock_db, [])
        assert count == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_single_shift_chart(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test persisting a single shift chart."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        count = await downloader.persist(mock_db, [chart])

        # Should have called execute for each shift
        assert count == 7
        assert mock_db.execute.call_count == 7

    @pytest.mark.asyncio
    async def test_persist_from_dict(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test persisting from dict representation."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)
        chart_dict = chart.to_dict()

        count = await downloader.persist(mock_db, [chart_dict])

        assert count == 7
        assert mock_db.execute.call_count == 7

    @pytest.mark.asyncio
    async def test_persist_sql_parameters(
        self, downloader: ShiftChartsDownloader
    ) -> None:
        """Test that correct parameters are passed to SQL."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        from nhl_api.models.shifts import ParsedShiftChart, ShiftRecord

        shift = ShiftRecord(
            shift_id=123,
            game_id=2024020500,
            player_id=8470613,
            first_name="Brent",
            last_name="Burns",
            team_id=12,
            team_abbrev="CAR",
            period=1,
            shift_number=1,
            start_time="00:28",
            end_time="01:15",
            duration_seconds=47,
            is_goal_event=False,
        )
        chart = ParsedShiftChart(
            game_id=2024020500,
            season_id=20242025,
            total_shifts=1,
            shifts=[shift],
        )

        await downloader.persist(mock_db, [chart])

        # Verify the execute call parameters
        call_args = mock_db.execute.call_args
        assert call_args is not None
        args = call_args[0]

        # SQL statement should contain INSERT
        assert "INSERT INTO game_shifts" in args[0]
        # Check positional parameters
        assert args[1] == 123  # shift_id
        assert args[2] == 2024020500  # game_id
        assert args[3] == 8470613  # player_id
        assert args[4] == 12  # team_id
        assert args[5] == 1  # period
        assert args[6] == 1  # shift_number
        assert args[7] == "00:28"  # start_time
        assert args[8] == "01:15"  # end_time
        assert args[9] == 47  # duration_seconds
        assert args[10] is False  # is_goal_event
        assert args[11] is None  # event_description

    @pytest.mark.asyncio
    async def test_persist_goal_event(self, downloader: ShiftChartsDownloader) -> None:
        """Test persisting a goal event shift."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        from nhl_api.models.shifts import GOAL_TYPE_CODE, ParsedShiftChart, ShiftRecord

        shift = ShiftRecord(
            shift_id=456,
            game_id=2024020500,
            player_id=8473533,
            first_name="Jordan",
            last_name="Staal",
            team_id=12,
            team_abbrev="CAR",
            period=1,
            shift_number=5,
            start_time="05:30",
            end_time="05:30",
            duration_seconds=0,
            type_code=GOAL_TYPE_CODE,
            is_goal_event=True,
            event_description="EVG",
        )
        chart = ParsedShiftChart(
            game_id=2024020500,
            season_id=20242025,
            total_shifts=1,
            shifts=[shift],
        )

        await downloader.persist(mock_db, [chart])

        call_args = mock_db.execute.call_args
        args = call_args[0]
        assert args[10] is True  # is_goal_event
        assert args[11] == "EVG"  # event_description
