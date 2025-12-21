"""Unit tests for QuantHockeyCareerStatsDownloader."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.downloaders.sources.external.quanthockey.career_stats import (
    CATEGORY_URL_MAP,
    MAX_PAGES,
    PLAYERS_PER_PAGE,
    CareerStatCategory,
    QuantHockeyCareerStatsDownloader,
)
from nhl_api.downloaders.sources.external.quanthockey.player_stats import (
    QuantHockeyConfig,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def config() -> QuantHockeyConfig:
    """Create a test configuration."""
    return QuantHockeyConfig()


@pytest.fixture
def downloader(config: QuantHockeyConfig) -> QuantHockeyCareerStatsDownloader:
    """Create a test downloader instance."""
    return QuantHockeyCareerStatsDownloader(config)


@pytest.fixture
def sample_career_html_row() -> str:
    """Sample HTML table row for a career stats player."""
    return """
    <tr>
        <td>1</td>
        <td><a href="/player/8447400">Wayne Gretzky</a></td>
        <td>EDM, LAK, STL, NYR</td>
        <td>1961</td>
        <td>C</td>
        <td>1487</td>
        <td>894</td>
        <td>1963</td>
        <td>2857</td>
        <td>577</td>
        <td>520</td>
        <td>204</td>
        <td>91</td>
        <td>5088</td>
        <td>17.6</td>
    </tr>
    """


@pytest.fixture
def sample_career_html_page(sample_career_html_row: str) -> str:
    """Sample HTML page with career statistics table."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>NHL All-Time Points Leaders</title></head>
    <body>
        <table id="stats" class="sortable">
            <thead>
                <tr>
                    <th>Rk</th>
                    <th>Name</th>
                    <th>Team</th>
                    <th>Born</th>
                    <th>Pos</th>
                    <th>GP</th>
                    <th>G</th>
                    <th>A</th>
                    <th>P</th>
                    <th>PIM</th>
                    <th>+/-</th>
                    <th>PPG</th>
                    <th>GWG</th>
                    <th>SOG</th>
                    <th>S%</th>
                </tr>
            </thead>
            <tbody>
                {sample_career_html_row}
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
def sample_career_html_page_no_next() -> str:
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
# CareerStatCategory Tests
# =============================================================================


class TestCareerStatCategory:
    """Tests for CareerStatCategory enum."""

    def test_all_categories_have_url_mapping(self) -> None:
        """Test that all categories have URL mappings."""
        for category in CareerStatCategory:
            assert category in CATEGORY_URL_MAP

    def test_category_values(self) -> None:
        """Test category value strings."""
        assert CareerStatCategory.POINTS.value == "points"
        assert CareerStatCategory.GOALS.value == "goals"
        assert CareerStatCategory.ASSISTS.value == "assists"
        assert CareerStatCategory.GAMES_PLAYED.value == "games-played"
        assert CareerStatCategory.PENALTY_MINUTES.value == "penalty-minutes"
        assert CareerStatCategory.PLUS_MINUS.value == "plus-minus"
        assert CareerStatCategory.POWER_PLAY_GOALS.value == "power-play-goals"
        assert CareerStatCategory.GAME_WINNING_GOALS.value == "game-winning-goals"
        assert CareerStatCategory.SHOTS_ON_GOAL.value == "shots-on-goal"

    def test_url_mapping_format(self) -> None:
        """Test that URL mappings have expected format."""
        for _category, url_segment in CATEGORY_URL_MAP.items():
            assert "nhl-players-all-time" in url_segment
            assert "-leaders" in url_segment


# =============================================================================
# Downloader Initialization Tests
# =============================================================================


class TestDownloaderInit:
    """Tests for downloader initialization."""

    def test_source_name(self, downloader: QuantHockeyCareerStatsDownloader) -> None:
        """Test source name property."""
        assert downloader.source_name == "quanthockey_career_stats"

    def test_default_config(self) -> None:
        """Test initialization with default config."""
        downloader = QuantHockeyCareerStatsDownloader()

        assert downloader.config.base_url == "https://www.quanthockey.com"

    def test_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = QuantHockeyConfig(requests_per_second=0.25)
        downloader = QuantHockeyCareerStatsDownloader(config)

        assert downloader.config.requests_per_second == 0.25


# =============================================================================
# URL Building Tests
# =============================================================================


class TestUrlBuilding:
    """Tests for URL construction."""

    def test_build_category_url_points_page_1(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test URL building for points leaders, first page."""
        url = downloader._build_category_url(CareerStatCategory.POINTS, page=1)

        assert (
            url
            == "https://www.quanthockey.com/nhl/records/nhl-players-all-time-points-leaders.html"
        )

    def test_build_category_url_goals_page_1(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test URL building for goals leaders, first page."""
        url = downloader._build_category_url(CareerStatCategory.GOALS, page=1)

        assert (
            url
            == "https://www.quanthockey.com/nhl/records/nhl-players-all-time-goals-leaders.html"
        )

    def test_build_category_url_page_2(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test URL building for subsequent pages."""
        url = downloader._build_category_url(CareerStatCategory.POINTS, page=2)

        assert (
            url
            == "https://www.quanthockey.com/nhl/records/nhl-players-all-time-points-leaders.html?page=2"
        )

    def test_build_category_url_all_categories(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test URL building for all categories."""
        for category in CareerStatCategory:
            url = downloader._build_category_url(category, page=1)
            assert url.startswith("https://www.quanthockey.com/nhl/records/")
            assert url.endswith(".html")
            assert CATEGORY_URL_MAP[category] in url


# =============================================================================
# HTML Parsing Tests
# =============================================================================


class TestHtmlParsing:
    """Tests for HTML parsing functionality."""

    def test_parse_career_table_with_players(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test parsing a table with player data."""
        players = downloader._parse_career_table(
            sample_career_html_page, CareerStatCategory.POINTS
        )

        assert len(players) == 1
        player = players[0]
        assert player.name == "Wayne Gretzky"
        assert player.position == "C"
        assert player.games_played == 1487
        assert player.goals == 894
        assert player.assists == 1963
        assert player.points == 2857
        assert player.pim == 577
        assert player.plus_minus == 520

    def test_parse_career_table_empty(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page_no_next: str,
    ) -> None:
        """Test parsing an empty table."""
        players = downloader._parse_career_table(
            sample_career_html_page_no_next, CareerStatCategory.POINTS
        )

        assert len(players) == 0

    def test_parse_career_table_no_table(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test parsing HTML with no stats table."""
        html = "<html><body><p>No stats here</p></body></html>"
        players = downloader._parse_career_table(html, CareerStatCategory.POINTS)

        assert len(players) == 0

    def test_parse_career_table_with_additional_stats(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test that additional stat fields are correctly parsed."""
        players = downloader._parse_career_table(
            sample_career_html_page, CareerStatCategory.POINTS
        )
        player = players[0]

        # Verify additional stats
        assert player.pp_goals == 204
        assert player.gw_goals == 91
        assert player.shots_on_goal == 5088
        assert player.shooting_pct == 17.6


# =============================================================================
# Pagination Detection Tests
# =============================================================================


class TestPaginationDetection:
    """Tests for pagination detection."""

    def test_has_next_page_with_links(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test detecting next page from pagination links."""
        assert downloader._has_next_page(sample_career_html_page, 1) is True
        assert downloader._has_next_page(sample_career_html_page, 2) is True

    def test_has_next_page_no_pagination(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page_no_next: str,
    ) -> None:
        """Test detecting no next page."""
        assert downloader._has_next_page(sample_career_html_page_no_next, 1) is False

    def test_has_next_page_with_next_link(
        self, downloader: QuantHockeyCareerStatsDownloader
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
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_row: str,
    ) -> None:
        """Test extracting player from valid row."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(sample_career_html_row, "lxml")
        row = soup.find("tr")
        assert row is not None

        player = downloader._extract_player_row(row, CareerStatCategory.POINTS)

        assert player is not None
        assert player.name == "Wayne Gretzky"
        assert player.position == "C"
        assert player.games_played == 1487

    def test_extract_player_row_insufficient_cells(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test extracting player from row with too few cells."""
        from bs4 import BeautifulSoup

        html = "<tr><td>1</td><td>Name</td></tr>"
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")
        assert row is not None

        player = downloader._extract_player_row(row, CareerStatCategory.POINTS)

        assert player is None

    def test_extract_player_row_calculates_seasons(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_row: str,
    ) -> None:
        """Test that seasons played is calculated from GP."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(sample_career_html_row, "lxml")
        row = soup.find("tr")
        assert row is not None

        player = downloader._extract_player_row(row, CareerStatCategory.POINTS)

        assert player is not None
        # 1487 GP / 60 ≈ 24 seasons (rounded)
        assert player.seasons_played >= 20


# =============================================================================
# Download Leaders Tests
# =============================================================================


class TestDownloadLeaders:
    """Tests for download_leaders method."""

    @pytest.mark.asyncio
    async def test_download_leaders_single_page(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test downloading a single page of career stats."""
        # Create page without next link for single page test
        sample_html_no_next = sample_career_html_page.replace(
            '<a href="?page=2">2</a>', ""
        ).replace('<a href="?page=3">3</a>', "")

        # Create mock response
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
                players = await downloader.download_leaders(
                    CareerStatCategory.POINTS, max_pages=1
                )

        assert len(players) == 1
        assert players[0].name == "Wayne Gretzky"

    @pytest.mark.asyncio
    async def test_download_leaders_top_n_limit(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test that top_n limit is respected."""
        mock_response = MagicMock()
        mock_response.text = MagicMock(return_value=sample_career_html_page)
        mock_response.content = sample_career_html_page.encode()
        mock_response.is_success = True
        mock_response.status = 200

        with patch.object(
            downloader, "_get_with_headers", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                players = await downloader.download_leaders(
                    CareerStatCategory.POINTS, top_n=1, max_pages=10
                )

        # Should stop after reaching top_n
        assert len(players) <= 1

    @pytest.mark.asyncio
    async def test_download_leaders_max_pages_limit(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test that max_pages limit is respected."""
        mock_response = MagicMock()
        mock_response.text = MagicMock(return_value=sample_career_html_page)
        mock_response.content = sample_career_html_page.encode()
        mock_response.is_success = True
        mock_response.status = 200

        with patch.object(
            downloader, "_get_with_headers", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                await downloader.download_leaders(
                    CareerStatCategory.POINTS, max_pages=2
                )

        # Should have made at most 2 requests
        assert mock_get.call_count <= 2

    @pytest.mark.asyncio
    async def test_download_leaders_different_categories(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test downloading different stat categories."""
        sample_html_no_next = sample_career_html_page.replace(
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
                # Test goals category
                await downloader.download_leaders(CareerStatCategory.GOALS, max_pages=1)

                # Test assists category
                await downloader.download_leaders(
                    CareerStatCategory.ASSISTS, max_pages=1
                )

        # Should have made calls for both categories
        assert mock_get.call_count == 2


# =============================================================================
# Download All Categories Tests
# =============================================================================


class TestDownloadAllCategories:
    """Tests for download_all_categories method."""

    @pytest.mark.asyncio
    async def test_download_all_categories_returns_dict(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test that download_all_categories returns dict of all categories."""
        sample_html_no_next = sample_career_html_page.replace(
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
                results = await downloader.download_all_categories(top_n=1)

        assert isinstance(results, dict)
        # Should have entry for each category
        for category in CareerStatCategory:
            assert category in results
            assert isinstance(results[category], list)


# =============================================================================
# Parse Response Tests
# =============================================================================


class TestParseResponse:
    """Tests for _parse_response method."""

    @pytest.mark.asyncio
    async def test_parse_response_returns_dict(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test that _parse_response returns expected structure."""
        mock_response = MagicMock()
        mock_response.text = MagicMock(return_value=sample_career_html_page)

        context: dict[str, Any] = {"category": CareerStatCategory.POINTS, "page": 1}
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

    def test_players_per_page(self) -> None:
        """Test players per page constant."""
        assert PLAYERS_PER_PAGE == 20

    def test_max_pages(self) -> None:
        """Test max pages constant."""
        assert MAX_PAGES == 20

    def test_category_url_map_not_empty(self) -> None:
        """Test category URL map is populated."""
        assert len(CATEGORY_URL_MAP) == len(CareerStatCategory)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_malformed_html(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test parsing malformed HTML doesn't crash."""
        malformed_html = "<html><table<tr><td>broken"
        players = downloader._parse_career_table(
            malformed_html, CareerStatCategory.POINTS
        )

        # Should return empty list, not raise
        assert isinstance(players, list)

    def test_parse_unicode_characters(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test parsing player names with unicode characters."""
        html = """
        <html><body>
            <table id="stats">
                <tbody>
                    <tr>
                        <td>1</td>
                        <td>Jaromír Jágr</td>
                        <td>PIT, WSH, NYR, ...</td>
                        <td>1972</td>
                        <td>RW</td>
                        <td>1733</td>
                        <td>766</td>
                        <td>1155</td>
                        <td>1921</td>
                        <td>1167</td>
                        <td>322</td>
                        <td>217</td>
                        <td>135</td>
                        <td>5637</td>
                        <td>13.6</td>
                    </tr>
                </tbody>
            </table>
        </body></html>
        """
        players = downloader._parse_career_table(html, CareerStatCategory.POINTS)

        assert len(players) == 1
        assert "Jágr" in players[0].name

    def test_parse_row_missing_optional_fields(
        self, downloader: QuantHockeyCareerStatsDownloader
    ) -> None:
        """Test parsing row with missing optional fields."""
        html = """
        <html><body>
            <table id="stats">
                <tbody>
                    <tr>
                        <td>1</td>
                        <td>Test Player</td>
                        <td>TOR</td>
                        <td>1990</td>
                        <td>C</td>
                        <td>500</td>
                        <td>200</td>
                        <td>300</td>
                        <td>500</td>
                        <td>100</td>
                        <td>50</td>
                    </tr>
                </tbody>
            </table>
        </body></html>
        """
        players = downloader._parse_career_table(html, CareerStatCategory.POINTS)

        assert len(players) == 1
        player = players[0]
        assert player.name == "Test Player"
        assert player.goals == 200
        # Optional fields should default to 0
        assert player.pp_goals == 0
        assert player.gw_goals == 0

    def test_computed_properties(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test computed properties on career stats."""
        players = downloader._parse_career_table(
            sample_career_html_page, CareerStatCategory.POINTS
        )
        player = players[0]

        # Test per-game rates
        assert player.goals_per_game == pytest.approx(
            player.goals / player.games_played, rel=0.01
        )
        assert player.assists_per_game == pytest.approx(
            player.assists / player.games_played, rel=0.01
        )
        assert player.points_per_game == pytest.approx(
            player.points / player.games_played, rel=0.01
        )

    def test_career_span_property(
        self,
        downloader: QuantHockeyCareerStatsDownloader,
        sample_career_html_page: str,
    ) -> None:
        """Test career_span computed property."""
        players = downloader._parse_career_table(
            sample_career_html_page, CareerStatCategory.POINTS
        )
        player = players[0]

        # Career span should be formatted as "YYYY-YYYY"
        if player.first_season and player.last_season:
            assert "-" in player.career_span
