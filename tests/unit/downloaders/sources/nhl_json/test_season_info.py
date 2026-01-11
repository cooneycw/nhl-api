"""Tests for Season Info Downloader."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.sources.nhl_json.season_info import (
    SeasonInfoDownloader,
    SeasonInfoDownloaderConfig,
    _parse_date,
    _parse_season,
    create_season_info_downloader,
)


@pytest.mark.unit
class TestParseDate:
    """Tests for _parse_date function."""

    def test_parse_valid_date(self) -> None:
        """Test parsing a valid date string."""
        result = _parse_date("2024-10-04")

        assert result == date(2024, 10, 4)

    def test_parse_none(self) -> None:
        """Test parsing None returns None."""
        result = _parse_date(None)

        assert result is None

    def test_parse_invalid_date(self) -> None:
        """Test parsing invalid date returns None."""
        result = _parse_date("not-a-date")

        assert result is None


@pytest.mark.unit
class TestParseSeason:
    """Tests for _parse_season function."""

    def test_parse_season_complete(self) -> None:
        """Test parsing complete season data."""
        season_data = {
            "id": 20242025,
            "regularSeasonStartDate": "2024-10-04",
            "regularSeasonEndDate": "2025-04-17",
            "playoffEndDate": "2025-04-19",
            "seasonEndDate": "2025-06-30",
            "numberOfGames": 82,
            "tiesInUse": False,
            "olympicsParticipation": False,
            "conferencesInUse": True,
            "divisionsInUse": True,
        }

        result = _parse_season(season_data)

        assert result.season_id == 20242025
        assert result.regular_season_start == date(2024, 10, 4)
        assert result.regular_season_end == date(2025, 4, 17)
        assert result.number_of_games == 82
        assert result.ties_in_use is False
        assert result.conference_in_use is True
        assert result.division_in_use is True

    def test_parse_season_minimal(self) -> None:
        """Test parsing minimal season data."""
        season_data = {"id": 20242025}

        result = _parse_season(season_data)

        assert result.season_id == 20242025
        assert result.regular_season_start is None
        assert result.number_of_games == 82  # default
        assert result.ties_in_use is False

    def test_parse_historical_season(self) -> None:
        """Test parsing a historical season with ties."""
        season_data = {
            "id": 19992000,
            "regularSeasonStartDate": "1999-10-01",
            "regularSeasonEndDate": "2000-04-09",
            "numberOfGames": 82,
            "tiesInUse": True,
            "conferencesInUse": True,
            "divisionsInUse": True,
        }

        result = _parse_season(season_data)

        assert result.season_id == 19992000
        assert result.ties_in_use is True


@pytest.mark.unit
class TestSeasonInfoDownloader:
    """Tests for SeasonInfoDownloader class."""

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
    ) -> SeasonInfoDownloader:
        """Create a downloader instance with mocks."""
        config = SeasonInfoDownloaderConfig()
        dl = SeasonInfoDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False  # Don't close the mock
        return dl

    def test_source_name(self, downloader: SeasonInfoDownloader) -> None:
        """Test that source_name returns correct identifier."""
        assert downloader.source_name == "nhl_json_season_info"

    @pytest.mark.asyncio
    async def test_get_all_seasons(
        self,
        downloader: SeasonInfoDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching all seasons."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = [
            {"id": 20242025, "numberOfGames": 82},
            {"id": 20232024, "numberOfGames": 82},
            {"id": 20222023, "numberOfGames": 82},
        ]
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_all_seasons()

        assert len(result) == 3
        # Should be sorted newest first
        assert result[0].season_id == 20242025
        assert result[1].season_id == 20232024
        assert result[2].season_id == 20222023

    @pytest.mark.asyncio
    async def test_get_season_specific(
        self,
        downloader: SeasonInfoDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching a specific season."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = [
            {"id": 20242025, "numberOfGames": 82},
            {"id": 20232024, "numberOfGames": 82},
        ]
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_season(20232024)

        assert result is not None
        assert result.season_id == 20232024

    @pytest.mark.asyncio
    async def test_get_season_not_found(
        self,
        downloader: SeasonInfoDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching a non-existent season."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = [
            {"id": 20242025, "numberOfGames": 82},
        ]
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_season(19001901)

        assert result is None

    @pytest.mark.asyncio
    async def test_caching(
        self,
        downloader: SeasonInfoDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that results are cached."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = [{"id": 20242025}]
        mock_http_client.get.return_value = mock_response

        # First call should fetch
        await downloader.get_all_seasons()
        # Second call should use cache
        await downloader.get_all_seasons()

        # HTTP should only be called once
        assert mock_http_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_force_refresh(
        self,
        downloader: SeasonInfoDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test force refresh bypasses cache."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = [{"id": 20242025}]
        mock_http_client.get.return_value = mock_response

        await downloader.get_all_seasons()
        await downloader.get_all_seasons(force_refresh=True)

        # Should be called twice
        assert mock_http_client.get.call_count == 2


@pytest.mark.unit
class TestFactoryFunction:
    """Tests for create_season_info_downloader factory."""

    def test_create_with_defaults(self) -> None:
        """Test factory with default parameters."""
        downloader = create_season_info_downloader()

        assert isinstance(downloader, SeasonInfoDownloader)
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_params(self) -> None:
        """Test factory with custom parameters."""
        downloader = create_season_info_downloader(
            requests_per_second=2.0,
            max_retries=5,
        )

        assert downloader.config.requests_per_second == 2.0
        assert downloader.config.max_retries == 5
