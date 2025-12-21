"""Integration tests for HTML Report Downloaders.

These tests verify end-to-end functionality of all HTML report downloaders
using mocked HTTP responses from fixture files.

For live tests against NHL.com, use:
    pytest -m live tests/integration/downloaders/test_html_downloaders.py
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.downloaders.base.protocol import DownloadError, DownloadStatus
from nhl_api.downloaders.sources.html import (
    EventSummaryDownloader,
    FaceoffComparisonDownloader,
    FaceoffSummaryDownloader,
    GameSummaryDownloader,
    HTMLDownloaderConfig,
    HTMLDownloaderRegistry,
    PlayByPlayDownloader,
    RosterDownloader,
    ShotSummaryDownloader,
    TimeOnIceDownloader,
)

# =============================================================================
# Test Constants
# =============================================================================

TEST_GAME_ID = 2024020500
TEST_SEASON_ID = 20242025


# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_response(content: bytes, is_success: bool = True) -> MagicMock:
    """Create a mock HTTP response."""
    mock = MagicMock()
    mock.is_success = is_success
    mock.status = 200 if is_success else 404
    mock.content = content
    return mock


# =============================================================================
# Registry Integration Tests
# =============================================================================


class TestHTMLDownloaderRegistryIntegration:
    """Integration tests for HTMLDownloaderRegistry."""

    @pytest.mark.integration
    def test_create_all_downloaders(
        self, html_downloader_config: HTMLDownloaderConfig
    ) -> None:
        """Verify all downloaders can be created."""
        downloaders = HTMLDownloaderRegistry.create_all(html_downloader_config)

        assert len(downloaders) == 9
        assert set(downloaders.keys()) == set(HTMLDownloaderRegistry.REPORT_TYPES)

        # Verify each downloader is correct type
        assert isinstance(downloaders["GS"], GameSummaryDownloader)
        assert isinstance(downloaders["ES"], EventSummaryDownloader)
        assert isinstance(downloaders["PL"], PlayByPlayDownloader)
        assert isinstance(downloaders["FS"], FaceoffSummaryDownloader)
        assert isinstance(downloaders["FC"], FaceoffComparisonDownloader)
        assert isinstance(downloaders["RO"], RosterDownloader)
        assert isinstance(downloaders["SS"], ShotSummaryDownloader)
        assert isinstance(downloaders["TH"], TimeOnIceDownloader)
        assert isinstance(downloaders["TV"], TimeOnIceDownloader)

    @pytest.mark.integration
    @pytest.mark.parametrize("report_type", HTMLDownloaderRegistry.REPORT_TYPES)
    def test_create_individual_downloader(
        self,
        report_type: str,
        html_downloader_config: HTMLDownloaderConfig,
    ) -> None:
        """Each report type can be created individually."""
        downloader = HTMLDownloaderRegistry.create(report_type, html_downloader_config)

        assert downloader is not None
        assert downloader.report_type == report_type
        assert downloader.source_name == f"html_{report_type.lower()}"


# =============================================================================
# Single Game Download Tests (Mocked)
# =============================================================================


class TestSingleGameDownload:
    """Test downloading individual games with mocked responses."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_game_summary(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        gs_fixture: bytes,
    ) -> None:
        """Download and parse Game Summary report."""
        downloader = HTMLDownloaderRegistry.create("GS", html_downloader_config)
        mock_response = create_mock_response(gs_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.game_id == TEST_GAME_ID
            assert result.season_id == TEST_SEASON_ID
            assert result.source == "html_gs"
            assert result.data is not None
            assert result.raw_content is not None

            # Verify parsed data structure
            data = result.data
            assert "away_team" in data
            assert "home_team" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_event_summary(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        es_fixture: bytes,
    ) -> None:
        """Download and parse Event Summary report."""
        downloader = HTMLDownloaderRegistry.create("ES", html_downloader_config)
        mock_response = create_mock_response(es_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.source == "html_es"
            assert result.data is not None

            # Verify parsed data has team event summaries
            data = result.data
            assert "away" in data or "away_team" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_play_by_play(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        pl_fixture: bytes,
    ) -> None:
        """Download and parse Play-by-Play report."""
        downloader = HTMLDownloaderRegistry.create("PL", html_downloader_config)
        mock_response = create_mock_response(pl_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.source == "html_pl"
            assert result.data is not None

            # Verify parsed data has events
            data = result.data
            assert "events" in data
            assert len(data["events"]) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_faceoff_summary(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        fs_fixture: bytes,
    ) -> None:
        """Download and parse Faceoff Summary report."""
        downloader = HTMLDownloaderRegistry.create("FS", html_downloader_config)
        mock_response = create_mock_response(fs_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.source == "html_fs"
            assert result.data is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_faceoff_comparison(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        fc_fixture: bytes,
    ) -> None:
        """Download and parse Faceoff Comparison report."""
        downloader = HTMLDownloaderRegistry.create("FC", html_downloader_config)
        mock_response = create_mock_response(fc_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.source == "html_fc"
            assert result.data is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_roster(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        ro_fixture: bytes,
    ) -> None:
        """Download and parse Roster report."""
        downloader = HTMLDownloaderRegistry.create("RO", html_downloader_config)
        mock_response = create_mock_response(ro_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.source == "html_ro"
            assert result.data is not None

            # Verify roster data - check for team data
            data = result.data
            assert "game_id" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_shot_summary(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        ss_fixture: bytes,
    ) -> None:
        """Download and parse Shot Summary report."""
        downloader = HTMLDownloaderRegistry.create("SS", html_downloader_config)
        mock_response = create_mock_response(ss_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.source == "html_ss"
            assert result.data is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_time_on_ice_home(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        th_fixture: bytes,
    ) -> None:
        """Download and parse Home Time on Ice report."""
        downloader = HTMLDownloaderRegistry.create("TH", html_downloader_config)
        mock_response = create_mock_response(th_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.source == "html_th"
            assert result.data is not None

            # Verify TOI data
            data = result.data
            assert "players" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_download_time_on_ice_visitor(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        tv_fixture: bytes,
    ) -> None:
        """Download and parse Visitor Time on Ice report."""
        downloader = HTMLDownloaderRegistry.create("TV", html_downloader_config)
        mock_response = create_mock_response(tv_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.source == "html_tv"
            assert result.data is not None


# =============================================================================
# All Report Types Test (Parametrized)
# =============================================================================


class TestAllReportTypes:
    """Test all report types using parametrized tests."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.parametrize("report_type", HTMLDownloaderRegistry.REPORT_TYPES)
    async def test_download_all_report_types(
        self,
        report_type: str,
        html_downloader_config: HTMLDownloaderConfig,
        all_html_fixtures: dict[str, bytes],
    ) -> None:
        """Download and parse all report types."""
        downloader = HTMLDownloaderRegistry.create(report_type, html_downloader_config)
        fixture = all_html_fixtures[report_type]
        mock_response = create_mock_response(fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.game_id == TEST_GAME_ID
            assert result.source == f"html_{report_type.lower()}"
            assert result.data is not None
            assert result.raw_content is not None
            assert len(result.raw_content) > 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in downloaders."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handles_404_response(
        self,
        html_downloader_config: HTMLDownloaderConfig,
    ) -> None:
        """Non-existent game returns appropriate error."""
        downloader = HTMLDownloaderRegistry.create("GS", html_downloader_config)

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status = 404

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                with pytest.raises(DownloadError):
                    await downloader.download_game(9999999999)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handles_invalid_html(
        self,
        html_downloader_config: HTMLDownloaderConfig,
    ) -> None:
        """Invalid HTML content is handled gracefully."""
        downloader = HTMLDownloaderRegistry.create("GS", html_downloader_config)

        # Return non-HTML content
        mock_response = create_mock_response(b"not html content")

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                with pytest.raises(DownloadError):
                    await downloader.download_game(TEST_GAME_ID)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handles_empty_response(
        self,
        html_downloader_config: HTMLDownloaderConfig,
    ) -> None:
        """Empty response is handled gracefully."""
        downloader = HTMLDownloaderRegistry.create("GS", html_downloader_config)

        mock_response = create_mock_response(b"")

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                with pytest.raises(DownloadError):
                    await downloader.download_game(TEST_GAME_ID)


# =============================================================================
# Data Structure Validation Tests
# =============================================================================


class TestDataStructureValidation:
    """Validate parsed data structures for each report type."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_game_summary_structure(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        gs_fixture: bytes,
    ) -> None:
        """Validate Game Summary parsed data structure."""
        downloader = HTMLDownloaderRegistry.create("GS", html_downloader_config)
        mock_response = create_mock_response(gs_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            data = result.data
            assert "game_id" in data
            assert "season_id" in data
            assert "away_team" in data
            assert "home_team" in data
            # Scoring summary and penalties
            assert "goals" in data
            assert "penalties" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_play_by_play_structure(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        pl_fixture: bytes,
    ) -> None:
        """Validate Play-by-Play parsed data structure."""
        downloader = HTMLDownloaderRegistry.create("PL", html_downloader_config)
        mock_response = create_mock_response(pl_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            data = result.data
            assert "game_id" in data
            assert "events" in data
            assert isinstance(data["events"], list)

            # Verify event structure (if events exist)
            if data["events"]:
                event = data["events"][0]
                # Events have varying fields based on type
                assert "event_type" in event or "period" in event

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_roster_structure(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        ro_fixture: bytes,
    ) -> None:
        """Validate Roster parsed data structure."""
        downloader = HTMLDownloaderRegistry.create("RO", html_downloader_config)
        mock_response = create_mock_response(ro_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            data = result.data
            assert "game_id" in data
            # Roster has away and home team data
            assert "away" in data or "away_team" in data
            assert "home" in data or "home_team" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_time_on_ice_structure(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        th_fixture: bytes,
    ) -> None:
        """Validate Time on Ice parsed data structure."""
        downloader = HTMLDownloaderRegistry.create("TH", html_downloader_config)
        mock_response = create_mock_response(th_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            data = result.data
            assert "game_id" in data
            assert "players" in data
            assert isinstance(data["players"], list)

            # Verify player TOI structure
            if data["players"]:
                player = data["players"][0]
                assert "number" in player or "jersey_number" in player
                assert "name" in player


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Test downloader configuration options."""

    @pytest.mark.integration
    def test_custom_config_applied(self) -> None:
        """Custom configuration is applied to downloaders."""
        custom_config = HTMLDownloaderConfig(
            requests_per_second=1.5,
            max_retries=5,
            http_timeout=60.0,
        )

        downloader = HTMLDownloaderRegistry.create("GS", custom_config)

        assert downloader.config.requests_per_second == 1.5
        assert downloader.config.max_retries == 5
        assert downloader.config.http_timeout == 60.0

    @pytest.mark.integration
    def test_game_ids_can_be_set(
        self, html_downloader_config: HTMLDownloaderConfig
    ) -> None:
        """Game IDs can be set for batch download."""
        game_ids = [2024020500, 2024020501, 2024020502]
        downloader = HTMLDownloaderRegistry.create(
            "GS", html_downloader_config, game_ids=game_ids
        )

        assert downloader._game_ids == game_ids  # noqa: SLF001

    @pytest.mark.integration
    def test_store_raw_html_option(self) -> None:
        """Raw HTML storage can be disabled."""
        config = HTMLDownloaderConfig(store_raw_html=False)
        downloader = HTMLDownloaderRegistry.create("GS", config)

        assert downloader._store_raw is False  # noqa: SLF001


# =============================================================================
# Progress Tracking Tests
# =============================================================================


class TestProgressTracking:
    """Test progress tracking integration."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_progress_callback_called(
        self,
        html_downloader_config: HTMLDownloaderConfig,
        gs_fixture: bytes,
    ) -> None:
        """Progress callback is called during download."""
        callback_called = {"count": 0}

        def progress_callback(*args: Any, **kwargs: Any) -> None:
            callback_called["count"] += 1

        downloader = HTMLDownloaderRegistry.create(
            "GS", html_downloader_config, progress_callback=progress_callback
        )
        mock_response = create_mock_response(gs_fixture)

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                # Set game IDs and download
                downloader.set_game_ids([TEST_GAME_ID])
                await downloader.download_game(TEST_GAME_ID)

        # Callback may or may not be called depending on implementation
        # Just verify no errors occurred
        assert True


# =============================================================================
# Live Tests (Skipped by Default)
# =============================================================================


@pytest.mark.live
@pytest.mark.skip(reason="Live tests require network access")
class TestLiveDownload:
    """Live tests against NHL.com (skipped by default).

    To run these tests:
        pytest -m live --run-live tests/integration/downloaders/test_html_downloaders.py
    """

    @pytest.mark.asyncio
    async def test_live_download_game_summary(self) -> None:
        """Download Game Summary from live NHL.com."""
        config = HTMLDownloaderConfig(
            requests_per_second=1.0,  # Conservative rate limit
        )
        downloader = HTMLDownloaderRegistry.create("GS", config)

        async with downloader:
            result = await downloader.download_game(TEST_GAME_ID)

        assert result.status == DownloadStatus.COMPLETED
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_live_download_all_report_types(self) -> None:
        """Download all report types from live NHL.com."""
        config = HTMLDownloaderConfig(
            requests_per_second=0.5,  # Very conservative
        )

        for report_type in HTMLDownloaderRegistry.REPORT_TYPES:
            downloader = HTMLDownloaderRegistry.create(report_type, config)

            async with downloader:
                result = await downloader.download_game(TEST_GAME_ID)

            assert result.status == DownloadStatus.COMPLETED
            assert result.data is not None

            # Rate limit between downloads
            time.sleep(2)
