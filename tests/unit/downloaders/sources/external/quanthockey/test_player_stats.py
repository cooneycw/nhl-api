"""Unit tests for QuantHockeyPlayerStatsDownloader."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.downloaders.sources.external.quanthockey.player_stats import (
    MAX_PAGES,
    PLAYERS_PER_PAGE,
    QUANTHOCKEY_RATE_LIMIT,
    QuantHockeyConfig,
    QuantHockeyPlayerStatsDownloader,
)
from nhl_api.models.quanthockey import (
    QuantHockeySeasonData,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def config() -> QuantHockeyConfig:
    """Create a test configuration."""
    return QuantHockeyConfig()


@pytest.fixture
def downloader(config: QuantHockeyConfig) -> QuantHockeyPlayerStatsDownloader:
    """Create a test downloader instance."""
    return QuantHockeyPlayerStatsDownloader(config)


@pytest.fixture
def sample_html_row() -> str:
    """Sample HTML table row for a player."""
    return """
    <tr>
        <td>1</td>
        <td><a href="/player/8478402">Connor McDavid</a></td>
        <td><a href="/nhl/teams/edm">EDM</a></td>
        <td>28</td>
        <td>C</td>
        <td>82</td>
        <td>64</td>
        <td>89</td>
        <td>153</td>
        <td>36</td>
        <td>40</td>
        <td>22.5</td>
        <td>18.0</td>
        <td>3.5</td>
        <td>1.0</td>
        <td>44</td>
        <td>18</td>
        <td>2</td>
        <td>12</td>
        <td>3</td>
        <td>59</td>
        <td>28</td>
        <td>2</td>
        <td>8</td>
        <td>1</td>
        <td>103</td>
        <td>46</td>
        <td>4</td>
        <td>20</td>
        <td>4</td>
        <td>30.1</td>
        <td>1.90</td>
        <td>2.64</td>
        <td>4.54</td>
        <td>1.47</td>
        <td>1.97</td>
        <td>3.44</td>
        <td>3.08</td>
        <td>4.80</td>
        <td>7.89</td>
        <td>0.78</td>
        <td>1.09</td>
        <td>1.87</td>
        <td>299</td>
        <td>21.4</td>
        <td>45</td>
        <td>12</td>
        <td>856</td>
        <td>644</td>
        <td>57.1</td>
        <td>CAN</td>
    </tr>
    """


@pytest.fixture
def sample_html_page(sample_html_row: str) -> str:
    """Sample HTML page with player statistics table."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>NHL Players Stats 2024-25</title></head>
    <body>
        <table id="stats" class="sortable">
            <thead>
                <tr>
                    <th>Rk</th>
                    <th>Name</th>
                    <th>Team</th>
                    <th>Age</th>
                    <th>Pos</th>
                    <th>GP</th>
                    <th>G</th>
                    <th>A</th>
                    <th>P</th>
                    <th>PIM</th>
                    <th>+/-</th>
                    <!-- ... more headers ... -->
                </tr>
            </thead>
            <tbody>
                {sample_html_row}
            </tbody>
        </table>
        <div class="pagination">
            <a href="?page=1">1</a>
            <a href="?page=2">2</a>
            <a href="?page=3">3</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_page_no_next() -> str:
    """Sample HTML page without pagination (last page)."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <table id="stats" class="sortable">
            <thead>
                <tr><th>Rk</th><th>Name</th></tr>
            </thead>
            <tbody>
            </tbody>
        </table>
    </body>
    </html>
    """


# =============================================================================
# Configuration Tests
# =============================================================================


class TestQuantHockeyConfig:
    """Tests for QuantHockeyConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = QuantHockeyConfig()

        assert config.base_url == "https://www.quanthockey.com"
        assert config.requests_per_second == QUANTHOCKEY_RATE_LIMIT
        assert config.retry_base_delay == 3.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = QuantHockeyConfig(
            base_url="https://custom.quanthockey.com",
            requests_per_second=0.25,
            retry_base_delay=5.0,
        )

        assert config.base_url == "https://custom.quanthockey.com"
        assert config.requests_per_second == 0.25
        assert config.retry_base_delay == 5.0

    def test_inherits_from_external_config(self) -> None:
        """Test that config inherits from ExternalDownloaderConfig."""
        config = QuantHockeyConfig()

        # Should have inherited attributes
        assert hasattr(config, "user_agent")
        assert hasattr(config, "store_raw_response")
        assert hasattr(config, "validate_response")


# =============================================================================
# Downloader Initialization Tests
# =============================================================================


class TestDownloaderInit:
    """Tests for downloader initialization."""

    def test_source_name(self, downloader: QuantHockeyPlayerStatsDownloader) -> None:
        """Test source name property."""
        assert downloader.source_name == "quanthockey_player_stats"

    def test_default_config(self) -> None:
        """Test initialization with default config."""
        downloader = QuantHockeyPlayerStatsDownloader()

        assert downloader.config.base_url == "https://www.quanthockey.com"

    def test_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = QuantHockeyConfig(requests_per_second=0.25)
        downloader = QuantHockeyPlayerStatsDownloader(config)

        assert downloader.config.requests_per_second == 0.25


# =============================================================================
# Season ID Conversion Tests
# =============================================================================


class TestSeasonIdConversion:
    """Tests for season ID to name conversion."""

    def test_season_id_to_name_standard(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test standard season ID conversion."""
        assert downloader._season_id_to_name(20242025) == "2024-25"
        assert downloader._season_id_to_name(20232024) == "2023-24"
        assert downloader._season_id_to_name(19992000) == "1999-00"

    def test_season_id_to_name_invalid(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test invalid season ID raises error."""
        with pytest.raises(ValueError, match="Invalid season ID format"):
            downloader._season_id_to_name(2024)

        with pytest.raises(ValueError, match="Invalid season ID format"):
            downloader._season_id_to_name(202425)


# =============================================================================
# URL Building Tests
# =============================================================================


class TestUrlBuilding:
    """Tests for URL construction."""

    def test_build_season_url_page_1(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test URL building for first page."""
        url = downloader._build_season_url(20242025, page=1)

        assert (
            url
            == "https://www.quanthockey.com/nhl/seasons/2024-25-nhl-players-stats.html"
        )

    def test_build_season_url_page_2(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test URL building for subsequent pages."""
        url = downloader._build_season_url(20242025, page=2)

        assert (
            url
            == "https://www.quanthockey.com/nhl/seasons/2024-25-nhl-players-stats.html?page=2"
        )

    def test_build_season_url_different_seasons(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test URL building for different seasons."""
        url_2023 = downloader._build_season_url(20232024, page=1)
        url_2020 = downloader._build_season_url(20192020, page=1)

        assert "2023-24" in url_2023
        assert "2019-20" in url_2020


# =============================================================================
# HTML Parsing Tests
# =============================================================================


class TestHtmlParsing:
    """Tests for HTML parsing functionality."""

    def test_parse_stats_table_with_players(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_page: str
    ) -> None:
        """Test parsing a table with player data."""
        players = downloader._parse_stats_table(sample_html_page, 20242025)

        assert len(players) == 1
        player = players[0]
        assert player.name == "Connor McDavid"
        assert player.team == "EDM"
        assert player.position == "C"
        assert player.games_played == 82
        assert player.goals == 64
        assert player.assists == 89
        assert player.points == 153

    def test_parse_stats_table_empty(
        self,
        downloader: QuantHockeyPlayerStatsDownloader,
        sample_html_page_no_next: str,
    ) -> None:
        """Test parsing an empty table."""
        players = downloader._parse_stats_table(sample_html_page_no_next, 20242025)

        assert len(players) == 0

    def test_parse_stats_table_no_table(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test parsing HTML with no stats table."""
        html = "<html><body><p>No stats here</p></body></html>"
        players = downloader._parse_stats_table(html, 20242025)

        assert len(players) == 0

    def test_parse_stats_table_with_stat_values(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_page: str
    ) -> None:
        """Test that all stat fields are correctly parsed."""
        players = downloader._parse_stats_table(sample_html_page, 20242025)
        player = players[0]

        # Verify TOI fields
        assert player.toi_avg == 22.5
        assert player.toi_es == 18.0
        assert player.toi_pp == 3.5
        assert player.toi_sh == 1.0

        # Verify situational goals
        assert player.es_goals == 44
        assert player.pp_goals == 18
        assert player.sh_goals == 2
        assert player.gw_goals == 12
        assert player.ot_goals == 3

        # Verify per-60 rates
        assert player.goals_per_60 == 1.90
        assert player.assists_per_60 == 2.64
        assert player.points_per_60 == 4.54

        # Verify shooting stats
        assert player.shots_on_goal == 299
        assert player.shooting_pct == 21.4

        # Verify faceoffs
        assert player.faceoffs_won == 856
        assert player.faceoffs_lost == 644
        assert player.faceoff_pct == 57.1


# =============================================================================
# Pagination Detection Tests
# =============================================================================


class TestPaginationDetection:
    """Tests for pagination detection."""

    def test_has_next_page_with_links(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_page: str
    ) -> None:
        """Test detecting next page from pagination links."""
        assert downloader._has_next_page(sample_html_page, 1) is True
        assert downloader._has_next_page(sample_html_page, 2) is True

    def test_has_next_page_no_pagination(
        self,
        downloader: QuantHockeyPlayerStatsDownloader,
        sample_html_page_no_next: str,
    ) -> None:
        """Test detecting no next page."""
        assert downloader._has_next_page(sample_html_page_no_next, 1) is False

    def test_has_next_page_with_next_link(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test detecting next page from 'Next' text link."""
        html = """
        <html><body>
            <div class="pagination">
                <a href="?page=2">Next ►</a>
            </div>
        </body></html>
        """
        assert downloader._has_next_page(html, 1) is True


# =============================================================================
# Extract Player Row Tests
# =============================================================================


class TestExtractPlayerRow:
    """Tests for extracting player data from table rows."""

    def test_extract_player_row_valid(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_row: str
    ) -> None:
        """Test extracting player from valid row."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(sample_html_row, "lxml")
        row = soup.find("tr")
        assert row is not None

        player = downloader._extract_player_row(row, 20242025)

        assert player is not None
        assert player.name == "Connor McDavid"
        assert player.season_id == 20242025

    def test_extract_player_row_insufficient_cells(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test extracting player from row with too few cells."""
        from bs4 import BeautifulSoup

        html = "<tr><td>1</td><td>Name</td></tr>"
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")
        assert row is not None

        player = downloader._extract_player_row(row, 20242025)

        assert player is None


# =============================================================================
# Download Season Tests
# =============================================================================


class TestDownloadSeason:
    """Tests for download_player_stats method."""

    @pytest.mark.asyncio
    async def test_download_player_stats_single_page(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_page: str
    ) -> None:
        """Test downloading a single page of player stats."""
        # Create page without next link for single page test
        sample_html_no_next = sample_html_page.replace(
            '<a href="?page=2">2</a>', ""
        ).replace('<a href="?page=3">3</a>', "")

        # Create mock response with text() as a method
        mock_response = MagicMock()
        mock_response.text = MagicMock(return_value=sample_html_no_next)
        mock_response.content = sample_html_no_next.encode()
        mock_response.is_success = True
        mock_response.status = 200

        with patch.object(
            downloader, "_get_with_headers", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                players = await downloader.download_player_stats(20242025, max_pages=1)

        assert len(players) == 1
        assert players[0].name == "Connor McDavid"

    @pytest.mark.asyncio
    async def test_download_player_stats_max_players_limit(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_page: str
    ) -> None:
        """Test that max_players limit is respected."""
        mock_response = MagicMock()
        mock_response.text = MagicMock(return_value=sample_html_page)
        mock_response.content = sample_html_page.encode()
        mock_response.is_success = True
        mock_response.status = 200

        with patch.object(
            downloader, "_get_with_headers", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                players = await downloader.download_player_stats(
                    20242025, max_players=1, max_pages=10
                )

        # Should stop after reaching max_players
        assert len(players) <= 1

    @pytest.mark.asyncio
    async def test_download_player_stats_max_pages_limit(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_page: str
    ) -> None:
        """Test that max_pages limit is respected."""
        mock_response = MagicMock()
        mock_response.text = MagicMock(return_value=sample_html_page)
        mock_response.content = sample_html_page.encode()
        mock_response.is_success = True
        mock_response.status = 200

        with patch.object(
            downloader, "_get_with_headers", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                await downloader.download_player_stats(20242025, max_pages=2)

        # Should have made at most 2 requests (may stop earlier if no next page)
        assert mock_get.call_count <= 2


# =============================================================================
# Download Season Data Tests
# =============================================================================


class TestDownloadSeasonData:
    """Tests for download_player_stats_data method."""

    @pytest.mark.asyncio
    async def test_download_player_stats_data_returns_container(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_page: str
    ) -> None:
        """Test that download_player_stats_data returns QuantHockeySeasonData."""
        # Create page without next link
        sample_html_no_next = sample_html_page.replace(
            '<a href="?page=2">2</a>', ""
        ).replace('<a href="?page=3">3</a>', "")

        mock_response = MagicMock()
        mock_response.text = MagicMock(return_value=sample_html_no_next)
        mock_response.content = sample_html_no_next.encode()
        mock_response.is_success = True
        mock_response.status = 200

        with patch.object(
            downloader, "_get_with_headers", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                season_data = await downloader.download_season_data(
                    20242025, max_pages=1
                )

        assert isinstance(season_data, QuantHockeySeasonData)
        assert season_data.season_id == 20242025
        assert season_data.season_name == "2024-25"
        assert season_data.player_count == 1
        assert len(season_data.players) == 1
        assert season_data.download_timestamp != ""


# =============================================================================
# Parse Response Tests
# =============================================================================


class TestParseResponse:
    """Tests for _parse_response method."""

    @pytest.mark.asyncio
    async def test_parse_response_returns_dict(
        self, downloader: QuantHockeyPlayerStatsDownloader, sample_html_page: str
    ) -> None:
        """Test that _parse_response returns expected structure."""
        mock_response = MagicMock()
        mock_response.text = MagicMock(return_value=sample_html_page)

        context: dict[str, Any] = {"season_id": 20242025, "page": 1}
        result = await downloader._parse_response(mock_response, context)

        assert isinstance(result, dict)
        assert "players" in result
        assert "player_count" in result
        assert "has_next_page" in result
        assert result["player_count"] == 1
        assert result["has_next_page"] is True


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_rate_limit_is_conservative(self) -> None:
        """Test that rate limit is appropriately conservative."""
        assert QUANTHOCKEY_RATE_LIMIT == 0.5  # 1 request every 2 seconds

    def test_players_per_page(self) -> None:
        """Test players per page constant."""
        assert PLAYERS_PER_PAGE == 20

    def test_max_pages(self) -> None:
        """Test max pages constant."""
        assert MAX_PAGES == 20


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_malformed_html(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test parsing malformed HTML doesn't crash."""
        malformed_html = "<html><table<tr><td>broken"
        players = downloader._parse_stats_table(malformed_html, 20242025)

        # Should return empty list, not raise
        assert isinstance(players, list)

    def test_parse_unicode_characters(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test parsing player names with unicode characters."""
        html = (
            """
        <html><body>
            <table id="stats">
                <tbody>
                    <tr>
                        <td>1</td>
                        <td>Patrice Bergéron</td>
                        <td>BOS</td>
                        <td>38</td>
                        <td>C</td>
                        """
            + "<td>0</td>" * 46
            + """
                        <td></td>
                    </tr>
                </tbody>
            </table>
        </body></html>
        """
        )
        players = downloader._parse_stats_table(html, 20232024)

        assert len(players) == 1
        assert "Bergéron" in players[0].name

    def test_season_id_boundary_years(
        self, downloader: QuantHockeyPlayerStatsDownloader
    ) -> None:
        """Test season IDs at year boundaries."""
        # Century boundary
        assert downloader._season_id_to_name(19992000) == "1999-00"

        # Future season
        assert downloader._season_id_to_name(20252026) == "2025-26"
