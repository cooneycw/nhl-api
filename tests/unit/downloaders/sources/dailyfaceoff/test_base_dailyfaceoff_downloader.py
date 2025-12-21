"""Unit tests for BaseDailyFaceoffDownloader."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.base.protocol import DownloadError, DownloadStatus
from nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader import (
    DAILYFACEOFF_BASE_URL,
    DEFAULT_DAILYFACEOFF_RATE_LIMIT,
    BaseDailyFaceoffDownloader,
    DailyFaceoffConfig,
)
from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import TEAM_SLUGS


class ConcreteDownloader(BaseDailyFaceoffDownloader):
    """Concrete implementation for testing."""

    @property
    def data_type(self) -> str:
        return "test_data"

    @property
    def page_path(self) -> str:
        return "test-page"

    async def _parse_page(self, soup: BeautifulSoup, team_id: int) -> dict[str, Any]:
        return {"parsed": True, "team_id": team_id}


class TestDailyFaceoffConfig:
    """Tests for DailyFaceoffConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = DailyFaceoffConfig()
        assert config.base_url == DAILYFACEOFF_BASE_URL
        assert config.requests_per_second == DEFAULT_DAILYFACEOFF_RATE_LIMIT
        assert config.max_retries == 3
        assert config.retry_base_delay == 2.0
        assert config.http_timeout == 30.0
        assert config.health_check_url == "/teams"

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = DailyFaceoffConfig(
            requests_per_second=0.5,
            max_retries=5,
            http_timeout=60.0,
        )
        assert config.requests_per_second == 0.5
        assert config.max_retries == 5
        assert config.http_timeout == 60.0

    def test_conservative_rate_limit(self) -> None:
        """Verify default rate limit is conservative (1 req/s or less)."""
        assert DEFAULT_DAILYFACEOFF_RATE_LIMIT <= 1.0


class TestBaseDailyFaceoffDownloader:
    """Tests for BaseDailyFaceoffDownloader."""

    def test_source_name(self) -> None:
        """Test source_name property."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        assert downloader.source_name == "dailyfaceoff_test_data"

    def test_default_team_ids(self) -> None:
        """Test default team IDs excludes Arizona (relocated)."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        # Should have all teams except Arizona (ID 53)
        assert 53 not in downloader._team_ids
        assert len(downloader._team_ids) == len(TEAM_SLUGS) - 1

    def test_custom_team_ids(self) -> None:
        """Test custom team IDs."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config, team_ids=[10, 6, 1])
        assert downloader._team_ids == [10, 6, 1]

    def test_set_team_ids(self) -> None:
        """Test set_team_ids method."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        downloader.set_team_ids([20, 21, 22])
        assert downloader._team_ids == [20, 21, 22]

    def test_get_team_slug(self) -> None:
        """Test _get_team_slug method."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        assert downloader._get_team_slug(10) == "toronto-maple-leafs"
        assert downloader._get_team_slug(6) == "boston-bruins"

    def test_get_team_slug_invalid(self) -> None:
        """Test _get_team_slug with invalid team ID."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        with pytest.raises(KeyError):
            downloader._get_team_slug(999)

    def test_get_team_abbreviation(self) -> None:
        """Test _get_team_abbreviation method."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        assert downloader._get_team_abbreviation(10) == "TOR"
        assert downloader._get_team_abbreviation(6) == "BOS"

    def test_build_team_url(self) -> None:
        """Test _build_team_url method."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        url = downloader._build_team_url(10)
        expected = f"{DAILYFACEOFF_BASE_URL}/teams/toronto-maple-leafs/test-page"
        assert url == expected

    def test_build_team_url_all_teams(self) -> None:
        """Test _build_team_url for all teams."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        for team_id, slug in TEAM_SLUGS.items():
            url = downloader._build_team_url(team_id)
            expected = f"{DAILYFACEOFF_BASE_URL}/teams/{slug}/test-page"
            assert url == expected, f"Failed for team {team_id}"

    def test_parse_html(self) -> None:
        """Test _parse_html method."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        html = b"<html><body><h1>Test</h1></body></html>"
        soup = downloader._parse_html(html)
        h1 = soup.find("h1")
        assert h1 is not None
        assert h1.get_text() == "Test"

    def test_parse_html_with_encoding_errors(self) -> None:
        """Test _parse_html handles encoding errors."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        # Invalid UTF-8 bytes
        html = b"<html><body>\xff\xfe</body></html>"
        soup = downloader._parse_html(html)
        assert soup is not None

    def test_validate_html_valid(self) -> None:
        """Test _validate_html with valid HTML."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        assert downloader._validate_html(b"<!DOCTYPE html><html>")
        assert downloader._validate_html(b"<html><body>")

    def test_validate_html_invalid(self) -> None:
        """Test _validate_html with invalid content."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        assert not downloader._validate_html(b'{"json": "data"}')
        assert not downloader._validate_html(b"plain text")

    @pytest.mark.asyncio
    async def test_fetch_game_not_implemented(self) -> None:
        """Test _fetch_game raises NotImplementedError."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        with pytest.raises(NotImplementedError, match="team-based"):
            await downloader._fetch_game(2024020001)

    @pytest.mark.asyncio
    async def test_fetch_season_games_warns(self) -> None:
        """Test _fetch_season_games logs warning and yields nothing."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)
        games = [g async for g in downloader._fetch_season_games(20242025)]
        assert games == []


class TestDownloadTeam:
    """Tests for download_team method."""

    @pytest.mark.asyncio
    async def test_download_team_success(self) -> None:
        """Test successful team download."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = b"<!DOCTYPE html><html><body>Test</body></html>"

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                result = await downloader.download_team(10)

        assert result.status == DownloadStatus.COMPLETED
        assert result.data["team_id"] == 10
        assert result.data["team_abbreviation"] == "TOR"
        assert result.data["parsed"] is True
        assert result.raw_content == mock_response.content

    @pytest.mark.asyncio
    async def test_download_team_http_error(self) -> None:
        """Test team download with HTTP error."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status = 404

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                with pytest.raises(DownloadError, match="HTTP 404"):
                    await downloader.download_team(10)

    @pytest.mark.asyncio
    async def test_download_team_invalid_html(self) -> None:
        """Test team download with invalid HTML response."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = b'{"not": "html"}'

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                with pytest.raises(DownloadError, match="not valid HTML"):
                    await downloader.download_team(10)


class TestDownloadAllTeams:
    """Tests for download_all_teams method."""

    @pytest.mark.asyncio
    async def test_download_all_teams(self) -> None:
        """Test downloading all teams."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config, team_ids=[10, 6])

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = b"<!DOCTYPE html><html><body>Test</body></html>"

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                results = [r async for r in downloader.download_all_teams()]

        assert len(results) == 2
        assert results[0].data["team_abbreviation"] == "TOR"
        assert results[1].data["team_abbreviation"] == "BOS"

    @pytest.mark.asyncio
    async def test_download_all_teams_with_failure(self) -> None:
        """Test download_all_teams handles individual failures."""
        config = DailyFaceoffConfig()
        downloader = ConcreteDownloader(config, team_ids=[10, 6])

        # First call succeeds, second fails
        mock_response_success = MagicMock()
        mock_response_success.is_success = True
        mock_response_success.content = b"<!DOCTYPE html><html><body>Test</body></html>"

        mock_response_fail = MagicMock()
        mock_response_fail.is_success = False
        mock_response_fail.status = 500

        with patch.object(
            downloader,
            "_get",
            new_callable=AsyncMock,
            side_effect=[mock_response_success, mock_response_fail],
        ):
            async with downloader:
                results = [r async for r in downloader.download_all_teams()]

        assert len(results) == 2
        assert results[0].status == DownloadStatus.COMPLETED
        assert results[1].status == DownloadStatus.FAILED
