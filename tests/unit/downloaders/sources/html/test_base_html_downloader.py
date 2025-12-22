"""Unit tests for BaseHTMLDownloader.

Tests cover:
- Configuration and initialization
- URL building for NHL HTML reports
- HTML parsing and validation
- Utility methods (safe_int, safe_float, parse_player_info, etc.)
- Download flow with mocked HTTP responses
- Error handling
- Raw content preservation
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.base.protocol import DownloadError, DownloadStatus
from nhl_api.downloaders.sources.html.base_html_downloader import (
    HTML_DOWNLOADER_CONFIG,
    BaseHTMLDownloader,
    HTMLDownloaderConfig,
)

# =============================================================================
# Test Fixtures
# =============================================================================


class ConcreteHTMLDownloader(BaseHTMLDownloader):
    """Concrete implementation for testing abstract base class."""

    @property
    def report_type(self) -> str:
        return "GS"

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Simple parser for testing."""
        title = soup.find("title")
        return {
            "game_id": game_id,
            "title": title.get_text(strip=True) if title else None,
            "parsed": True,
        }


@pytest.fixture
def config() -> HTMLDownloaderConfig:
    """Create test configuration."""
    return HTMLDownloaderConfig(
        base_url="https://www.nhl.com/scores/htmlreports",
        requests_per_second=10.0,  # Fast for testing
        max_retries=2,
        http_timeout=5.0,
        store_raw_html=True,
    )


@pytest.fixture
def downloader(config: HTMLDownloaderConfig) -> ConcreteHTMLDownloader:
    """Create test downloader instance."""
    return ConcreteHTMLDownloader(config)


@pytest.fixture
def sample_html() -> bytes:
    """Sample HTML content for testing."""
    return b"""<!DOCTYPE html>
<html>
<head><title>Game Summary</title></head>
<body>
<table id="stats">
    <tr><th>Player</th><th>Goals</th><th>Assists</th></tr>
    <tr><td>72 T.THOMPSON(5)</td><td>1</td><td>2</td></tr>
    <tr><td>91 J.STAMKOS</td><td>0</td><td>1</td></tr>
</table>
</body>
</html>"""


@pytest.fixture
def sample_soup(sample_html: bytes) -> BeautifulSoup:
    """Parse sample HTML into BeautifulSoup."""
    return BeautifulSoup(sample_html.decode("utf-8"), "lxml")


# =============================================================================
# Configuration Tests
# =============================================================================


class TestHTMLDownloaderConfig:
    """Tests for HTMLDownloaderConfig."""

    def test_default_config_values(self) -> None:
        """Test default configuration values."""
        config = HTMLDownloaderConfig()
        assert config.base_url == "https://www.nhl.com/scores/htmlreports"
        assert config.requests_per_second == 2.0
        assert config.max_retries == 3
        assert config.http_timeout == 45.0
        assert config.store_raw_html is True

    def test_custom_config_values(self) -> None:
        """Test custom configuration values."""
        config = HTMLDownloaderConfig(
            base_url="https://custom.url",
            requests_per_second=5.0,
            max_retries=5,
            http_timeout=60.0,
            store_raw_html=False,
        )
        assert config.base_url == "https://custom.url"
        assert config.requests_per_second == 5.0
        assert config.max_retries == 5
        assert config.http_timeout == 60.0
        assert config.store_raw_html is False

    def test_default_config_instance(self) -> None:
        """Test the default config singleton."""
        assert (
            HTML_DOWNLOADER_CONFIG.base_url == "https://www.nhl.com/scores/htmlreports"
        )
        assert HTML_DOWNLOADER_CONFIG.requests_per_second == 2.0


# =============================================================================
# Initialization Tests
# =============================================================================


class TestBaseHTMLDownloaderInit:
    """Tests for BaseHTMLDownloader initialization."""

    def test_source_name(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test source_name property."""
        assert downloader.source_name == "html_gs"

    def test_report_type(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test report_type property."""
        assert downloader.report_type == "GS"

    def test_set_game_ids(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test setting game IDs."""
        game_ids = [2024020001, 2024020002, 2024020003]
        downloader.set_game_ids(game_ids)
        assert downloader._game_ids == game_ids

    def test_init_with_game_ids(self, config: HTMLDownloaderConfig) -> None:
        """Test initialization with game IDs."""
        game_ids = [2024020001, 2024020002]
        downloader = ConcreteHTMLDownloader(config, game_ids=game_ids)
        assert downloader._game_ids == game_ids


# =============================================================================
# URL Building Tests
# =============================================================================


class TestURLBuilding:
    """Tests for URL building."""

    def test_build_url_regular_season(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test URL building for regular season game."""
        url = downloader._build_url(20242025, 2024020500)
        expected = "https://www.nhl.com/scores/htmlreports/20242025/GS020500.HTM"
        assert url == expected

    def test_build_url_playoff_game(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test URL building for playoff game."""
        url = downloader._build_url(20242025, 2024030111)
        expected = "https://www.nhl.com/scores/htmlreports/20242025/GS030111.HTM"
        assert url == expected

    def test_build_url_preseason_game(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test URL building for preseason game."""
        url = downloader._build_url(20242025, 2024010001)
        expected = "https://www.nhl.com/scores/htmlreports/20242025/GS010001.HTM"
        assert url == expected

    def test_extract_season_from_game_id(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test extracting season ID from game ID."""
        assert downloader._extract_season_from_game_id(2024020001) == 20242025
        assert downloader._extract_season_from_game_id(2023030411) == 20232024
        assert downloader._extract_season_from_game_id(2022010005) == 20222023


# =============================================================================
# HTML Parsing Tests
# =============================================================================


class TestHTMLParsing:
    """Tests for HTML parsing and validation."""

    def test_parse_html(
        self, downloader: ConcreteHTMLDownloader, sample_html: bytes
    ) -> None:
        """Test HTML parsing."""
        soup = downloader._parse_html(sample_html)
        assert soup is not None
        title = soup.find("title")
        assert title is not None
        assert title.get_text() == "Game Summary"

    def test_parse_html_with_encoding_errors(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test HTML parsing with encoding errors."""
        # Invalid UTF-8 bytes
        bad_html = b"<html><body>\xff\xfe Invalid bytes</body></html>"
        soup = downloader._parse_html(bad_html)
        # Should not raise, but replace invalid characters
        assert soup is not None

    def test_validate_html_valid(
        self, downloader: ConcreteHTMLDownloader, sample_html: bytes
    ) -> None:
        """Test validation of valid HTML."""
        assert downloader._validate_html(sample_html) is True

    def test_validate_html_doctype(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test validation with DOCTYPE."""
        html = b"<!DOCTYPE html><html><body></body></html>"
        assert downloader._validate_html(html) is True

    def test_validate_html_invalid(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test validation of invalid content."""
        not_html = b'{"json": "data"}'
        assert downloader._validate_html(not_html) is False

    def test_validate_html_empty(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test validation of empty content."""
        assert downloader._validate_html(b"") is False


# =============================================================================
# Utility Method Tests
# =============================================================================


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_text(
        self, downloader: ConcreteHTMLDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test _get_text method."""
        title = sample_soup.find("title")
        assert downloader._get_text(title) == "Game Summary"

    def test_get_text_none(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test _get_text with None."""
        assert downloader._get_text(None) == ""
        assert downloader._get_text(None, "default") == "default"

    def test_safe_int_valid(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test _safe_int with valid input."""
        assert downloader._safe_int("123") == 123
        assert downloader._safe_int("  456  ") == 456
        assert downloader._safe_int("1,234") == 1234

    def test_safe_int_invalid(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test _safe_int with invalid input."""
        assert downloader._safe_int("abc") is None
        assert downloader._safe_int("abc", 0) == 0
        assert downloader._safe_int("") is None
        assert downloader._safe_int(None) is None

    def test_safe_float_valid(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test _safe_float with valid input."""
        assert downloader._safe_float("12.5") == 12.5
        assert downloader._safe_float("  3.14  ") == 3.14
        assert downloader._safe_float("50%") == 50.0
        assert downloader._safe_float("1,234.56") == 1234.56

    def test_safe_float_invalid(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test _safe_float with invalid input."""
        assert downloader._safe_float("abc") is None
        assert downloader._safe_float("abc", 0.0) == 0.0
        assert downloader._safe_float("") is None
        assert downloader._safe_float(None) is None

    def test_parse_player_info_full(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test _parse_player_info with full format."""
        result = downloader._parse_player_info("72 T.THOMPSON(34)")
        assert result["number"] == 72
        assert result["name"] == "T.THOMPSON"
        assert result["stat"] == 34

    def test_parse_player_info_no_stat(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test _parse_player_info without stat."""
        result = downloader._parse_player_info("91 J.STAMKOS")
        assert result["number"] == 91
        assert result["name"] == "J.STAMKOS"
        assert result["stat"] is None

    def test_parse_player_info_no_number(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test _parse_player_info without number."""
        result = downloader._parse_player_info("S.CROSBY(12)")
        assert result["number"] is None
        assert result["name"] == "S.CROSBY"
        assert result["stat"] == 12

    def test_parse_player_info_name_only(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test _parse_player_info with name only."""
        result = downloader._parse_player_info("A.OVECHKIN")
        assert result["number"] is None
        assert result["name"] == "A.OVECHKIN"
        assert result["stat"] is None

    def test_parse_toi(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test _parse_toi method."""
        assert downloader._parse_toi("12:34") == 754  # 12*60 + 34
        assert downloader._parse_toi("00:45") == 45
        assert downloader._parse_toi("20:00") == 1200
        assert downloader._parse_toi("  5:30  ") == 330

    def test_parse_toi_invalid(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test _parse_toi with invalid input."""
        assert downloader._parse_toi("invalid") == 0
        assert downloader._parse_toi("") == 0


class TestTableExtraction:
    """Tests for table extraction methods."""

    def test_extract_table_rows_by_id(
        self, downloader: ConcreteHTMLDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test extracting rows by table ID."""
        rows = downloader._extract_table_rows(sample_soup, table_id="stats")
        # Should skip header row
        assert len(rows) == 2

    def test_extract_table_rows_skip_header(
        self, downloader: ConcreteHTMLDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test that header row is skipped."""
        rows = downloader._extract_table_rows(
            sample_soup, table_id="stats", skip_header=True
        )
        # First row should be data, not header
        first_cell = rows[0].find("td")
        assert first_cell is not None
        assert "72 T.THOMPSON" in first_cell.get_text()

    def test_extract_table_rows_include_header(
        self, downloader: ConcreteHTMLDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test including header row."""
        rows = downloader._extract_table_rows(
            sample_soup, table_id="stats", skip_header=False
        )
        # Should include header
        assert len(rows) == 3

    def test_extract_table_rows_no_table(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test extraction when table not found."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        rows = downloader._extract_table_rows(soup, table_id="nonexistent")
        assert rows == []

    def test_get_cell_text(
        self, downloader: ConcreteHTMLDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test _get_cell_text method."""
        rows = downloader._extract_table_rows(sample_soup, table_id="stats")
        first_row = rows[0]
        assert "T.THOMPSON" in downloader._get_cell_text(first_row, 0)
        assert downloader._get_cell_text(first_row, 1) == "1"
        assert downloader._get_cell_text(first_row, 2) == "2"

    def test_get_cell_text_out_of_bounds(
        self, downloader: ConcreteHTMLDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test _get_cell_text with out of bounds index."""
        rows = downloader._extract_table_rows(sample_soup, table_id="stats")
        first_row = rows[0]
        assert downloader._get_cell_text(first_row, 99) == ""
        assert downloader._get_cell_text(first_row, 99, "default") == "default"


# =============================================================================
# Download Flow Tests
# =============================================================================


class TestDownloadFlow:
    """Tests for download flow."""

    @pytest.mark.asyncio
    async def test_download_game_success(
        self,
        downloader: ConcreteHTMLDownloader,
        sample_html: bytes,
    ) -> None:
        """Test successful game download."""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                result = await downloader.download_game(2024020500)

        assert result.is_successful
        assert result.status == DownloadStatus.COMPLETED
        assert result.game_id == 2024020500
        assert result.season_id == 20242025
        assert result.source == "html_gs"
        assert result.data["parsed"] is True
        assert result.raw_content == sample_html

    @pytest.mark.asyncio
    async def test_download_game_http_error(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test download with HTTP error."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status = 404

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                with pytest.raises(DownloadError) as exc_info:
                    await downloader.download_game(2024020500)

        assert "HTTP 404" in str(exc_info.value)
        assert exc_info.value.source == "html_gs"
        assert exc_info.value.game_id == 2024020500

    @pytest.mark.asyncio
    async def test_download_game_invalid_html(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test download with invalid HTML content."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = b'{"json": "not html"}'

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                with pytest.raises(DownloadError) as exc_info:
                    await downloader.download_game(2024020500)

        assert "not valid HTML" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_game_without_raw_content(self, sample_html: bytes) -> None:
        """Test download without storing raw content."""
        config = HTMLDownloaderConfig(store_raw_html=False)
        downloader = ConcreteHTMLDownloader(config)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                result = await downloader.download_game(2024020500)

        assert result.is_successful
        assert result.raw_content is None  # Not stored

    @pytest.mark.asyncio
    async def test_fetch_season_games_no_ids(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test season download with no game IDs set."""
        game_ids = []
        async for game_id in downloader._fetch_season_games(20242025):
            game_ids.append(game_id)

        assert game_ids == []

    @pytest.mark.asyncio
    async def test_fetch_season_games_with_ids(
        self, downloader: ConcreteHTMLDownloader
    ) -> None:
        """Test season download with game IDs set."""
        expected_ids = [2024020001, 2024020002, 2024020003]
        downloader.set_game_ids(expected_ids)

        game_ids = []
        async for game_id in downloader._fetch_season_games(20242025):
            game_ids.append(game_id)

        assert game_ids == expected_ids


# =============================================================================
# Integration Pattern Tests
# =============================================================================


class TestViewerIntegration:
    """Tests for viewer/monitoring integration patterns."""

    def test_source_name_format(self, downloader: ConcreteHTMLDownloader) -> None:
        """Test source_name follows expected format for viewer."""
        # Viewer expects source_name for data_sources table
        assert downloader.source_name.startswith("html_")
        assert downloader.source_name == "html_gs"

    @pytest.mark.asyncio
    async def test_download_result_fields(
        self,
        downloader: ConcreteHTMLDownloader,
        sample_html: bytes,
    ) -> None:
        """Test DownloadResult has all fields needed for viewer."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                result = await downloader.download_game(2024020500)

        # These fields are used by the monitoring API
        assert hasattr(result, "source")
        assert hasattr(result, "season_id")
        assert hasattr(result, "game_id")
        assert hasattr(result, "status")
        assert hasattr(result, "data")
        assert hasattr(result, "raw_content")
        assert hasattr(result, "error_message")

        # Status should be valid DownloadStatus
        assert result.status in list(DownloadStatus)


# =============================================================================
# HTML Persistence Tests
# =============================================================================


class TestHTMLPersistence:
    """Tests for HTML report persistence to disk."""

    @pytest.mark.asyncio
    async def test_html_persisted_on_download(
        self,
        tmp_path: Path,
        sample_html: bytes,
    ) -> None:
        """Test that HTML is saved to disk when download succeeds."""
        # Create config with custom base_dir for testing
        config = HTMLDownloaderConfig(
            store_raw_html=True,
            persist_html=True,
        )
        downloader = ConcreteHTMLDownloader(config)

        # Override storage manager to use temp directory

        from nhl_api.utils.html_storage import HTMLStorageManager

        downloader._storage_manager = HTMLStorageManager(base_dir=tmp_path)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                result = await downloader.download_game(2024020500)

        # Verify download succeeded
        assert result.status == DownloadStatus.COMPLETED

        # Verify HTML was persisted to disk
        expected_path = tmp_path / "20242025" / "GS" / "2024020500.HTM"
        assert expected_path.exists()

        # Verify content matches
        saved_html = expected_path.read_bytes()
        assert saved_html == sample_html

    @pytest.mark.asyncio
    async def test_persistence_disabled_via_config(
        self,
        tmp_path: Path,
        sample_html: bytes,
    ) -> None:
        """Test that persistence can be disabled via config."""
        config = HTMLDownloaderConfig(
            store_raw_html=True,
            persist_html=False,  # Disabled
        )
        downloader = ConcreteHTMLDownloader(config)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                result = await downloader.download_game(2024020500)

        # Verify download succeeded
        assert result.status == DownloadStatus.COMPLETED

        # Verify no HTML was persisted
        # (storage manager should not be initialized)
        assert downloader._storage_manager is None

        # Verify temp directory is empty (no files created)
        assert not (tmp_path / "20242025").exists()

    @pytest.mark.asyncio
    async def test_download_continues_if_persistence_fails(
        self,
        sample_html: bytes,
    ) -> None:
        """Test that download succeeds even if HTML persistence fails."""
        config = HTMLDownloaderConfig(
            store_raw_html=True,
            persist_html=True,
        )
        downloader = ConcreteHTMLDownloader(config)

        # Mock storage manager to raise exception
        mock_storage = MagicMock()
        mock_storage.save_html.side_effect = OSError("Disk full")
        downloader._storage_manager = mock_storage

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                # Should not raise, persistence failure is non-fatal
                result = await downloader.download_game(2024020500)

        # Verify download succeeded despite persistence failure
        assert result.status == DownloadStatus.COMPLETED
        assert result.raw_content == sample_html

    @pytest.mark.asyncio
    async def test_multiple_downloads_create_separate_files(
        self,
        tmp_path: Path,
        sample_html: bytes,
    ) -> None:
        """Test that multiple downloads create separate HTML files."""
        config = HTMLDownloaderConfig(
            store_raw_html=True,
            persist_html=True,
        )
        downloader = ConcreteHTMLDownloader(config)

        # Override storage manager to use temp directory
        from nhl_api.utils.html_storage import HTMLStorageManager

        downloader._storage_manager = HTMLStorageManager(base_dir=tmp_path)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                # Download multiple games
                await downloader.download_game(2024020001)
                await downloader.download_game(2024020002)
                await downloader.download_game(2024020003)

        # Verify all files were created
        assert (tmp_path / "20242025" / "GS" / "2024020001.HTM").exists()
        assert (tmp_path / "20242025" / "GS" / "2024020002.HTM").exists()
        assert (tmp_path / "20242025" / "GS" / "2024020003.HTM").exists()

    @pytest.mark.asyncio
    async def test_different_report_types_create_separate_directories(
        self,
        tmp_path: Path,
        sample_html: bytes,
    ) -> None:
        """Test that different report types are stored in separate directories."""

        # Create two different downloader types
        class ESDownloader(ConcreteHTMLDownloader):
            @property
            def report_type(self) -> str:
                return "ES"

        class PLDownloader(ConcreteHTMLDownloader):
            @property
            def report_type(self) -> str:
                return "PL"

        config = HTMLDownloaderConfig(
            store_raw_html=True,
            persist_html=True,
        )

        es_downloader = ESDownloader(config)
        pl_downloader = PLDownloader(config)

        # Override storage managers to use temp directory
        from nhl_api.utils.html_storage import HTMLStorageManager

        es_downloader._storage_manager = HTMLStorageManager(base_dir=tmp_path)
        pl_downloader._storage_manager = HTMLStorageManager(base_dir=tmp_path)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        # Download from both downloaders
        with patch.object(
            es_downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with es_downloader:
                await es_downloader.download_game(2024020500)

        with patch.object(
            pl_downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with pl_downloader:
                await pl_downloader.download_game(2024020500)

        # Verify separate directories were created
        assert (tmp_path / "20242025" / "ES" / "2024020500.HTM").exists()
        assert (tmp_path / "20242025" / "PL" / "2024020500.HTM").exists()
