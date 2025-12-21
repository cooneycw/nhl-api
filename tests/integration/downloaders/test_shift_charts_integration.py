"""Integration tests for ShiftChartsDownloader.

These tests verify end-to-end functionality with mocked HTTP responses,
simulating real API behavior without hitting the actual NHL Stats API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.downloaders.sources.nhl_stats import (
    ShiftChartsDownloader,
    ShiftChartsDownloaderConfig,
    create_shift_charts_downloader,
)
from nhl_api.models.shifts import GOAL_TYPE_CODE, SHIFT_TYPE_CODE

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_api_response() -> dict[str, Any]:
    """Load sample API response from fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent
        / "fixtures"
        / "nhl_stats"
        / "shift_charts_2024020500.json"
    )
    with open(fixture_path) as f:
        return cast(dict[str, Any], json.load(f))


@pytest.fixture
def large_api_response() -> dict[str, Any]:
    """Generate a larger API response for stress testing."""
    shifts = []
    for i in range(500):
        shifts.append(
            {
                "id": 14765329 + i,
                "detailCode": 0,
                "duration": f"00:{(i % 60):02d}",
                "endTime": f"{(i // 60):02d}:{(i % 60):02d}",
                "eventDescription": None,
                "eventDetails": None,
                "eventNumber": 100 + i,
                "firstName": f"Player{i}",
                "gameId": 2024020500,
                "hexValue": "#C8102E",
                "lastName": f"Test{i}",
                "period": (i // 100) + 1,
                "playerId": 8470000 + i,
                "shiftNumber": (i % 30) + 1,
                "startTime": f"{(i // 60):02d}:00",
                "teamAbbrev": "CAR" if i % 2 == 0 else "NYI",
                "teamId": 12 if i % 2 == 0 else 2,
                "teamName": "Carolina Hurricanes"
                if i % 2 == 0
                else "New York Islanders",
                "typeCode": 517,
            }
        )
    return {"data": shifts, "total": len(shifts)}


@pytest.fixture
def downloader() -> ShiftChartsDownloader:
    """Create a test downloader."""
    config = ShiftChartsDownloaderConfig(
        requests_per_second=100.0,  # Fast for testing
        max_retries=2,
    )
    return ShiftChartsDownloader(config)


# =============================================================================
# End-to-End Download Tests
# =============================================================================


class TestEndToEndDownload:
    """End-to-end download flow tests."""

    @pytest.mark.asyncio
    async def test_download_single_game(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test downloading shift data for a single game."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = sample_api_response

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await downloader._fetch_game(2024020500)

        assert result["game_id"] == 2024020500
        assert result["total_shifts"] == 7
        assert len(result["shifts"]) == 7

        # Verify correct API path was called
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert "/shiftcharts" in call_args
        assert "gameId=2024020500" in call_args

    @pytest.mark.asyncio
    async def test_download_season_with_multiple_games(
        self, sample_api_response: dict[str, Any]
    ) -> None:
        """Test downloading shift data for multiple games in a season."""
        config = ShiftChartsDownloaderConfig(requests_per_second=100.0)
        game_ids = [2024020500, 2024020501, 2024020502]
        downloader = ShiftChartsDownloader(config, game_ids=game_ids)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = sample_api_response

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            results = []
            async with downloader:
                async for result in downloader.download_season(20242025):
                    results.append(result)

        assert len(results) == 3
        assert all(r.is_successful for r in results)
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_download_handles_partial_failures(
        self, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that download continues when some games fail."""
        config = ShiftChartsDownloaderConfig(requests_per_second=100.0, max_retries=1)
        game_ids = [2024020500, 2024020501, 2024020502]
        downloader = ShiftChartsDownloader(config, game_ids=game_ids)

        call_count = 0

        async def mock_get_with_failures(path: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            response = MagicMock()

            # Second game fails
            if "2024020501" in path:
                response.is_success = False
                response.status = 404
            else:
                response.is_success = True
                response.json.return_value = sample_api_response

            return response

        with patch.object(downloader, "_get", side_effect=mock_get_with_failures):
            results = []
            async with downloader:
                async for result in downloader.download_season(20242025):
                    results.append(result)

        # Should have 3 results (2 success, 1 failure after retries)
        assert len(results) == 3
        successful = [r for r in results if r.is_successful]
        failed = [r for r in results if not r.is_successful]
        assert len(successful) == 2
        assert len(failed) == 1


# =============================================================================
# Data Parsing Tests
# =============================================================================


class TestDataParsing:
    """Tests for parsing shift chart data."""

    def test_parse_regular_shifts(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test parsing regular shift records."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        # Find regular shifts (not goal events)
        regular_shifts = [s for s in chart.shifts if s.type_code == SHIFT_TYPE_CODE]
        assert len(regular_shifts) == 6

        # Check first shift
        first_shift = chart.shifts[0]
        assert first_shift.player_id == 8470613
        assert first_shift.first_name == "Brent"
        assert first_shift.last_name == "Burns"
        assert first_shift.duration_seconds == 47

    def test_parse_goal_events(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test parsing goal event records."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        # Find goal events
        goal_events = [s for s in chart.shifts if s.type_code == GOAL_TYPE_CODE]
        assert len(goal_events) == 1

        goal = goal_events[0]
        assert goal.is_goal_event is True
        assert goal.event_description == "EVG"
        assert goal.event_details == "Jordan Staal"
        assert goal.duration_seconds == 0

    def test_parse_large_dataset(
        self, downloader: ShiftChartsDownloader, large_api_response: dict[str, Any]
    ) -> None:
        """Test parsing a large number of shifts."""
        records = large_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        assert chart.total_shifts == 500
        assert len(chart.shifts) == 500

        # Verify both teams are represented
        team_ids = {s.team_id for s in chart.shifts}
        assert 12 in team_ids  # CAR
        assert 2 in team_ids  # NYI

    def test_team_identification(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that home and away teams are identified."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        # Both team IDs should be present
        assert chart.home_team_id is not None
        assert chart.away_team_id is not None
        assert chart.home_team_id != chart.away_team_id

        team_ids = {chart.home_team_id, chart.away_team_id}
        assert 12 in team_ids  # CAR
        assert 2 in team_ids  # NYI

    def test_season_id_extraction(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that season ID is correctly extracted from game ID."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        assert chart.season_id == 20242025


# =============================================================================
# Model Helper Method Tests
# =============================================================================


class TestModelHelperMethods:
    """Tests for ParsedShiftChart helper methods."""

    def test_get_player_shifts(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test filtering shifts by player."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        # Brent Burns has player_id 8470613
        burns_shifts = chart.get_player_shifts(8470613)
        assert len(burns_shifts) == 3  # 3 shifts in fixture

        for shift in burns_shifts:
            assert shift.player_id == 8470613
            assert shift.first_name == "Brent"

    def test_get_player_toi(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test calculating total time on ice for a player."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        # Brent Burns: 47 + 57 + 48 = 152 seconds
        toi = chart.get_player_toi(8470613)
        assert toi == 152

    def test_get_period_shifts(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test filtering shifts by period."""
        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        period1_shifts = chart.get_period_shifts(1)
        period2_shifts = chart.get_period_shifts(2)

        assert len(period1_shifts) == 6
        assert len(period2_shifts) == 1

        for shift in period1_shifts:
            assert shift.period == 1


# =============================================================================
# Persistence Integration Tests
# =============================================================================


class TestPersistenceIntegration:
    """Integration tests for database persistence."""

    @pytest.mark.asyncio
    async def test_persist_full_chart(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test persisting a complete shift chart to database."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        records = sample_api_response["data"]
        chart = downloader._parse_shift_chart(records, 2024020500)

        count = await downloader.persist(mock_db, [chart])

        assert count == 7
        assert mock_db.execute.call_count == 7

        # Verify SQL contains correct table name
        first_call = mock_db.execute.call_args_list[0]
        assert "game_shifts" in first_call[0][0]

    @pytest.mark.asyncio
    async def test_persist_multiple_charts(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test persisting multiple shift charts."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        records = sample_api_response["data"]
        chart1 = downloader._parse_shift_chart(records, 2024020500)
        chart2 = downloader._parse_shift_chart(records, 2024020501)

        count = await downloader.persist(mock_db, [chart1, chart2])

        assert count == 14  # 7 shifts * 2 charts
        assert mock_db.execute.call_count == 14


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryIntegration:
    """Integration tests for factory function."""

    def test_create_downloader_with_game_ids(self) -> None:
        """Test creating downloader with game IDs."""
        game_ids = [2024020500, 2024020501]
        downloader = create_shift_charts_downloader()
        downloader.set_game_ids(game_ids)

        assert downloader.get_game_ids() == game_ids
        assert downloader.source_name == "shift_chart"

    @pytest.mark.asyncio
    async def test_downloader_context_manager(self) -> None:
        """Test downloader works as async context manager."""
        downloader = create_shift_charts_downloader()

        async with downloader:
            assert downloader._http_client is not None

    @pytest.mark.asyncio
    async def test_downloader_configurable_rate_limit(self) -> None:
        """Test that rate limit is configurable."""
        downloader = create_shift_charts_downloader(
            requests_per_second=2.0,
            max_retries=5,
        )

        assert downloader.config.requests_per_second == 2.0
        assert downloader.config.max_retries == 5


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_handles_empty_response(
        self, downloader: ShiftChartsDownloader
    ) -> None:
        """Test handling of empty API response."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"data": [], "total": 0}

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await downloader._fetch_game(2024020500)

        assert result["game_id"] == 2024020500
        assert result["total_shifts"] == 0
        assert len(result["shifts"]) == 0

    @pytest.mark.asyncio
    async def test_handles_malformed_records(
        self, downloader: ShiftChartsDownloader
    ) -> None:
        """Test handling of malformed shift records."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "data": [
                {"id": 123},  # Minimal record
                {"id": 456, "playerId": 8470613},  # Partial record
            ],
            "total": 2,
        }

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await downloader._fetch_game(2024020500)

        assert result["total_shifts"] == 2
        # Should use default values for missing fields
        assert result["shifts"][0]["player_id"] == 0
        assert result["shifts"][1]["player_id"] == 8470613

    @pytest.mark.asyncio
    async def test_handles_http_error(self, downloader: ShiftChartsDownloader) -> None:
        """Test handling of HTTP errors."""
        from nhl_api.downloaders.base.protocol import DownloadError

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status = 500

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(DownloadError) as exc_info:
                await downloader._fetch_game(2024020500)

            assert exc_info.value.game_id == 2024020500
            assert "500" in str(exc_info.value)


# =============================================================================
# Raw Response Tests
# =============================================================================


class TestRawResponse:
    """Tests for raw response inclusion."""

    @pytest.mark.asyncio
    async def test_includes_raw_when_configured(
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

    @pytest.mark.asyncio
    async def test_excludes_raw_by_default(
        self, downloader: ShiftChartsDownloader, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that raw response is excluded by default."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = sample_api_response

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await downloader._fetch_game(2024020500)

        assert "_raw" not in result
