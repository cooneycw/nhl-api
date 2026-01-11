"""Tests for Right Rail Downloader."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.sources.nhl_json.right_rail import (
    RightRailDownloader,
    RightRailDownloaderConfig,
    _parse_broadcast,
    _parse_last_game,
    _parse_right_rail,
    _parse_season_series,
    create_right_rail_downloader,
)


@pytest.mark.unit
class TestParseBroadcast:
    """Tests for _parse_broadcast function."""

    def test_parse_broadcast_complete(self) -> None:
        """Test parsing a complete broadcast entry."""
        broadcast_data = {
            "network": "ESPN+",
            "countryCode": "US",
            "type": "national",
            "startTime": "2024-12-21T00:00:00Z",
        }

        result = _parse_broadcast(broadcast_data)

        assert result.network == "ESPN+"
        assert result.country_code == "US"
        assert result.broadcast_type == "national"
        assert result.start_time == "2024-12-21T00:00:00Z"

    def test_parse_broadcast_minimal(self) -> None:
        """Test parsing minimal broadcast data."""
        broadcast_data: dict[str, Any] = {}

        result = _parse_broadcast(broadcast_data)

        assert result.network == ""
        assert result.country_code == ""
        assert result.start_time is None


@pytest.mark.unit
class TestParseSeasonSeries:
    """Tests for _parse_season_series function."""

    def test_parse_season_series_complete(self) -> None:
        """Test parsing complete season series data."""
        team_data = {
            "wins": 2,
            "losses": 1,
            "otLosses": 0,
        }

        result = _parse_season_series(team_data, 22, "EDM")

        assert result.team_id == 22
        assert result.abbrev == "EDM"
        assert result.wins == 2
        assert result.losses == 1
        assert result.ot_losses == 0


@pytest.mark.unit
class TestParseLastGame:
    """Tests for _parse_last_game function."""

    def test_parse_last_game_complete(self) -> None:
        """Test parsing a complete last game entry."""
        game_data = {
            "id": 2024020300,
            "gameDate": "2024-12-01",
            "homeTeam": {"abbrev": "EDM", "score": 5},
            "awayTeam": {"abbrev": "CGY", "score": 3},
        }

        result = _parse_last_game(game_data)

        assert result.game_id == 2024020300
        assert result.game_date == "2024-12-01"
        assert result.home_team_abbrev == "EDM"
        assert result.away_team_abbrev == "CGY"
        assert result.home_score == 5
        assert result.away_score == 3


@pytest.mark.unit
class TestParseRightRail:
    """Tests for _parse_right_rail function."""

    def test_parse_right_rail_complete(self) -> None:
        """Test parsing complete right rail data."""
        data = {
            "id": 2024020500,
            "season": 20242025,
            "broadcasts": [
                {"network": "ESPN+", "countryCode": "US", "type": "national"},
                {"network": "SN", "countryCode": "CA", "type": "national"},
            ],
            "seasonSeries": {
                "series": [
                    {"teamId": 22, "teamAbbrev": "EDM", "wins": 2, "losses": 1},
                    {"teamId": 20, "teamAbbrev": "CGY", "wins": 1, "losses": 2},
                ]
            },
        }

        result = _parse_right_rail(data)

        assert result.game_id == 2024020500
        assert result.season_id == 20242025
        assert len(result.broadcasts) == 2
        assert result.broadcasts[0].network == "ESPN+"
        assert result.home_series is not None
        assert result.home_series.abbrev == "EDM"
        assert result.away_series is not None
        assert result.away_series.abbrev == "CGY"

    def test_parse_right_rail_minimal(self) -> None:
        """Test parsing minimal right rail data."""
        data = {"id": 2024020500}

        result = _parse_right_rail(data)

        assert result.game_id == 2024020500
        assert len(result.broadcasts) == 0
        assert result.home_series is None
        assert result.away_series is None

    def test_parse_right_rail_include_raw(self) -> None:
        """Test parsing with raw data inclusion."""
        data = {"id": 2024020500, "season": 20242025}

        result = _parse_right_rail(data, include_raw=True)

        assert result.raw_data is not None
        assert result.raw_data["id"] == 2024020500


@pytest.mark.unit
class TestRightRailDownloader:
    """Tests for RightRailDownloader class."""

    @pytest.fixture
    def mock_http_client(self) -> MagicMock:
        """Create a mock HTTP client."""
        client = MagicMock()
        client.get = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_rate_limiter(self) -> MagicMock:
        """Create a mock rate limiter."""
        limiter = MagicMock()
        limiter.wait = AsyncMock()
        return limiter

    @pytest.fixture
    def downloader(
        self, mock_http_client: MagicMock, mock_rate_limiter: MagicMock
    ) -> RightRailDownloader:
        """Create a downloader instance with mocks."""
        config = RightRailDownloaderConfig()
        dl = RightRailDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False  # Don't close the mock
        return dl

    def test_source_name(self, downloader: RightRailDownloader) -> None:
        """Test that source_name returns correct identifier."""
        assert downloader.source_name == "nhl_json_right_rail"

    @pytest.mark.asyncio
    async def test_fetch_game_success(
        self,
        downloader: RightRailDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful game fetch."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "id": 2024020500,
            "season": 20242025,
            "broadcasts": [],
        }
        mock_http_client.get.return_value = mock_response

        result = await downloader._fetch_game(2024020500)

        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025


@pytest.mark.unit
class TestFactoryFunction:
    """Tests for create_right_rail_downloader factory."""

    def test_create_with_defaults(self) -> None:
        """Test factory with default parameters."""
        downloader = create_right_rail_downloader()

        assert isinstance(downloader, RightRailDownloader)
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_params(self) -> None:
        """Test factory with custom parameters."""
        downloader = create_right_rail_downloader(
            requests_per_second=2.0,
            max_retries=5,
            include_raw_response=True,
        )

        assert downloader.config.requests_per_second == 2.0
        assert downloader.config.max_retries == 5
