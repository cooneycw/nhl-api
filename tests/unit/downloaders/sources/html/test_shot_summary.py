"""Unit tests for ShotSummaryDownloader.

Tests cover:
- HTML parsing of shot summary reports
- Team summary parsing (goals-shots by period)
- Player summary parsing with per-period breakdown
- Goals-shots format parsing
- Integration with BaseHTMLDownloader
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.html.base_html_downloader import (
    HTMLDownloaderConfig,
)
from nhl_api.downloaders.sources.html.shot_summary import (
    PeriodSituationStats,
    PlayerShotSummary,
    ShotSummaryDownloader,
    SituationStats,
    TeamShotSummary,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def config() -> HTMLDownloaderConfig:
    """Create test configuration."""
    return HTMLDownloaderConfig(
        base_url="https://www.nhl.com/scores/htmlreports",
        requests_per_second=10.0,
        max_retries=2,
        http_timeout=5.0,
        store_raw_html=True,
    )


@pytest.fixture
def downloader(config: HTMLDownloaderConfig) -> ShotSummaryDownloader:
    """Create test downloader instance."""
    return ShotSummaryDownloader(config)


@pytest.fixture
def sample_html() -> bytes:
    """Load sample Shot Summary HTML fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "html"
        / "SS020500.HTM"
    )
    if fixture_path.exists():
        return fixture_path.read_bytes()
    # Fallback minimal HTML for testing
    return _create_minimal_shot_summary_html()


def _create_minimal_shot_summary_html() -> bytes:
    """Create minimal HTML for fallback testing."""
    return b"""<!DOCTYPE html>
<html>
<head><title>Shot Summary</title></head>
<body>
<table id="Visitor">
    <tr><td><img src="logocnyi.gif" alt="NEW YORK ISLANDERS"></td></tr>
    <tr><td style="font-size: 40px;font-weight:bold">0</td></tr>
</table>
<table id="Home">
    <tr><td><img src="logoccar.gif" alt="CAROLINA HURRICANES"></td></tr>
    <tr><td style="font-size: 40px;font-weight:bold">4</td></tr>
</table>
<table>
    <tr><td class="sectionheading">TEAM SUMMARY (Goals-Shots)</td></tr>
</table>
<tr valign="top">
<td align="center" width="100%">
<table id="ShotsSummary" border="0" cellpadding="0" cellspacing="5" width="100%">
<tr>
<td width="50%" valign="top">
    <table>
        <tr class="heading">
            <td>Per</td><td>EV</td><td>PP</td><td>SH</td><td>TOT</td>
        </tr>
        <tr class="oddColor">
            <td>1</td><td>0-11</td><td>0-1</td><td>0-1</td><td>0-13</td>
        </tr>
        <tr class="evenColor">
            <td>2</td><td>0-10</td><td>&nbsp;</td><td>&nbsp;</td><td>0-10</td>
        </tr>
        <tr class="oddColor">
            <td>3</td><td>0-4</td><td>&nbsp;</td><td>&nbsp;</td><td>0-4</td>
        </tr>
        <tr class="evenColor">
            <td>TOT</td><td>0-25</td><td>0-1</td><td>0-1</td><td>0-27</td>
        </tr>
    </table>
</td>
<td width="50%" valign="top">
    <table>
        <tr class="heading">
            <td>Per</td><td>EV</td><td>PP</td><td>SH</td><td>TOT</td>
        </tr>
        <tr class="oddColor">
            <td>1</td><td>1-10</td><td>1-1</td><td>&nbsp;</td><td>2-11</td>
        </tr>
        <tr class="evenColor">
            <td>2</td><td>2-12</td><td>&nbsp;</td><td>&nbsp;</td><td>2-12</td>
        </tr>
        <tr class="oddColor">
            <td>3</td><td>0-6</td><td>&nbsp;</td><td>&nbsp;</td><td>0-6</td>
        </tr>
        <tr class="evenColor">
            <td>TOT</td><td>3-28</td><td>1-1</td><td>&nbsp;</td><td>4-29</td>
        </tr>
    </table>
</td>
</tr>
</table>
</td>
</tr>
<table>
    <tr><td class="sectionheading">PLAYER SUMMARY (Goals-Shots)</td></tr>
</table>
<tr valign="top">
<td align="center" width="100%">
<table id="ShotsSummary" border="0" cellpadding="0" cellspacing="5" width="100%">
<tr>
<td width="50%" valign="top">
    <table>
        <tr>
            <td class="lborder + bborder">
                <table>
                    <tr><td align="center">13</td></tr>
                    <tr><td align="center">MATHEW</td></tr>
                    <tr><td align="center">BARZAL</td></tr>
                </table>
            </td>
            <td class="bborder" valign="top">
                <table>
                    <tr class="oddColor" valign="top">
                        <td>1</td><td>0-2</td><td>&nbsp;</td><td>&nbsp;</td><td>0-2</td>
                    </tr>
                    <tr class="evenColor" valign="top">
                        <td>2</td><td>0-1</td><td>&nbsp;</td><td>&nbsp;</td><td>0-1</td>
                    </tr>
                    <tr class="oddColor" valign="top">
                        <td>3</td><td>0-1</td><td>&nbsp;</td><td>&nbsp;</td><td>0-1</td>
                    </tr>
                    <tr class="evenColor" valign="top">
                        <td>TOT</td><td>0-4</td><td>&nbsp;</td><td>&nbsp;</td><td>0-4</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</td>
<td width="50%" valign="top">
    <table>
        <tr>
            <td class="lborder + bborder">
                <table>
                    <tr><td align="center">37</td></tr>
                    <tr><td align="center">ANDREI</td></tr>
                    <tr><td align="center">SVECHNIKOV</td></tr>
                </table>
            </td>
            <td class="bborder" valign="top">
                <table>
                    <tr class="oddColor" valign="top">
                        <td>1</td><td>1-2</td><td>&nbsp;</td><td>&nbsp;</td><td>1-2</td>
                    </tr>
                    <tr class="evenColor" valign="top">
                        <td>2</td><td>1-3</td><td>&nbsp;</td><td>&nbsp;</td><td>1-3</td>
                    </tr>
                    <tr class="oddColor" valign="top">
                        <td>3</td><td>0-1</td><td>&nbsp;</td><td>&nbsp;</td><td>0-1</td>
                    </tr>
                    <tr class="evenColor" valign="top">
                        <td>TOT</td><td>2-6</td><td>&nbsp;</td><td>&nbsp;</td><td>2-6</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</td>
</tr>
</table>
</td>
</tr>
</body>
</html>"""


@pytest.fixture
def sample_soup(sample_html: bytes) -> BeautifulSoup:
    """Parse sample HTML into BeautifulSoup."""
    return BeautifulSoup(sample_html.decode("utf-8"), "lxml")


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestSituationStats:
    """Tests for SituationStats dataclass."""

    def test_default_values(self) -> None:
        """Test default initialization."""
        stats = SituationStats()
        assert stats.goals == 0
        assert stats.shots == 0

    def test_custom_values(self) -> None:
        """Test initialization with custom values."""
        stats = SituationStats(goals=2, shots=15)
        assert stats.goals == 2
        assert stats.shots == 15


class TestPeriodSituationStats:
    """Tests for PeriodSituationStats dataclass."""

    def test_default_values(self) -> None:
        """Test default initialization."""
        period = PeriodSituationStats(period="1")
        assert period.period == "1"
        assert period.even_strength.goals == 0
        assert period.even_strength.shots == 0
        assert period.power_play.goals == 0
        assert period.power_play.shots == 0
        assert period.shorthanded.goals == 0
        assert period.shorthanded.shots == 0
        assert period.total.goals == 0
        assert period.total.shots == 0

    def test_with_stats(self) -> None:
        """Test initialization with stats."""
        period = PeriodSituationStats(
            period="2",
            even_strength=SituationStats(goals=2, shots=10),
            power_play=SituationStats(goals=1, shots=3),
            shorthanded=SituationStats(goals=0, shots=1),
            total=SituationStats(goals=3, shots=14),
        )
        assert period.period == "2"
        assert period.even_strength.goals == 2
        assert period.even_strength.shots == 10
        assert period.power_play.goals == 1
        assert period.power_play.shots == 3
        assert period.total.goals == 3
        assert period.total.shots == 14


class TestPlayerShotSummary:
    """Tests for PlayerShotSummary dataclass."""

    def test_name_property(self) -> None:
        """Test full name property."""
        player = PlayerShotSummary(number=13, first_name="MATHEW", last_name="BARZAL")
        assert player.name == "MATHEW BARZAL"

    def test_total_shots_from_tot_period(self) -> None:
        """Test total_shots extracts from TOT period."""
        player = PlayerShotSummary(
            number=13,
            first_name="MATHEW",
            last_name="BARZAL",
            periods=[
                PeriodSituationStats(
                    period="1", total=SituationStats(goals=0, shots=2)
                ),
                PeriodSituationStats(
                    period="2", total=SituationStats(goals=0, shots=1)
                ),
                PeriodSituationStats(
                    period="TOT", total=SituationStats(goals=0, shots=4)
                ),
            ],
        )
        assert player.total_shots == 4

    def test_total_shots_sum_when_no_tot(self) -> None:
        """Test total_shots sums periods when no TOT."""
        player = PlayerShotSummary(
            number=13,
            first_name="MATHEW",
            last_name="BARZAL",
            periods=[
                PeriodSituationStats(
                    period="1", total=SituationStats(goals=0, shots=2)
                ),
                PeriodSituationStats(
                    period="2", total=SituationStats(goals=0, shots=1)
                ),
            ],
        )
        assert player.total_shots == 3

    def test_total_goals_from_tot_period(self) -> None:
        """Test total_goals extracts from TOT period."""
        player = PlayerShotSummary(
            number=37,
            first_name="ANDREI",
            last_name="SVECHNIKOV",
            periods=[
                PeriodSituationStats(
                    period="1", total=SituationStats(goals=1, shots=2)
                ),
                PeriodSituationStats(
                    period="TOT", total=SituationStats(goals=2, shots=6)
                ),
            ],
        )
        assert player.total_goals == 2


class TestTeamShotSummary:
    """Tests for TeamShotSummary dataclass."""

    def test_total_shots_from_tot_period(self) -> None:
        """Test team total_shots extracts from TOT period."""
        team = TeamShotSummary(
            name="CAROLINA HURRICANES",
            abbrev="CAR",
            periods=[
                PeriodSituationStats(
                    period="1", total=SituationStats(goals=2, shots=11)
                ),
                PeriodSituationStats(
                    period="TOT", total=SituationStats(goals=4, shots=29)
                ),
            ],
        )
        assert team.total_shots == 29
        assert team.total_goals == 4


# =============================================================================
# Downloader Configuration Tests
# =============================================================================


class TestShotSummaryDownloaderConfig:
    """Tests for ShotSummaryDownloader configuration."""

    def test_report_type(self, downloader: ShotSummaryDownloader) -> None:
        """Test report type is SS."""
        assert downloader.report_type == "SS"

    def test_source_name(self, downloader: ShotSummaryDownloader) -> None:
        """Test source name follows html_{type} pattern."""
        assert downloader.source_name == "html_ss"

    def test_config_defaults(self) -> None:
        """Test default configuration values."""
        config = HTMLDownloaderConfig()
        assert config.base_url == "https://www.nhl.com/scores/htmlreports"
        assert config.requests_per_second == 2.0
        assert config.store_raw_html is True


# =============================================================================
# URL Building Tests
# =============================================================================


class TestURLBuilding:
    """Tests for URL building functionality."""

    def test_build_url(self, downloader: ShotSummaryDownloader) -> None:
        """Test URL construction for shot summary."""
        url = downloader._build_url(20242025, 2024020500)
        assert url == "https://www.nhl.com/scores/htmlreports/20242025/SS020500.HTM"

    def test_build_url_different_game(self, downloader: ShotSummaryDownloader) -> None:
        """Test URL construction for different game."""
        url = downloader._build_url(20232024, 2023021234)
        assert url == "https://www.nhl.com/scores/htmlreports/20232024/SS021234.HTM"


# =============================================================================
# Goals-Shots Parsing Tests
# =============================================================================


class TestGoalsShotsParsing:
    """Tests for goals-shots format parsing."""

    def test_parse_standard_format(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing standard goals-shots format."""
        stats = downloader._parse_goals_shots("2-15")
        assert stats.goals == 2
        assert stats.shots == 15

    def test_parse_zero_goals(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing zero goals."""
        stats = downloader._parse_goals_shots("0-11")
        assert stats.goals == 0
        assert stats.shots == 11

    def test_parse_empty_string(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing empty string."""
        stats = downloader._parse_goals_shots("")
        assert stats.goals == 0
        assert stats.shots == 0

    def test_parse_nbsp(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing non-breaking space."""
        stats = downloader._parse_goals_shots("&nbsp;")
        assert stats.goals == 0
        assert stats.shots == 0

    def test_parse_whitespace(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing whitespace."""
        stats = downloader._parse_goals_shots("  ")
        assert stats.goals == 0
        assert stats.shots == 0

    def test_parse_with_spaces(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing with extra spaces."""
        stats = downloader._parse_goals_shots(" 1 - 5 ")
        assert stats.goals == 1
        assert stats.shots == 5

    def test_parse_invalid_format(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing invalid format."""
        stats = downloader._parse_goals_shots("invalid")
        assert stats.goals == 0
        assert stats.shots == 0


# =============================================================================
# Team Header Parsing Tests
# =============================================================================


class TestTeamHeaderParsing:
    """Tests for team header parsing."""

    def test_parse_visitor_team(
        self, downloader: ShotSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing visitor team from header."""
        name, abbrev = downloader._parse_team_header(sample_soup, "Visitor")
        assert name == "NEW YORK ISLANDERS"
        assert abbrev == "NYI"

    def test_parse_home_team(
        self, downloader: ShotSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing home team from header."""
        name, abbrev = downloader._parse_team_header(sample_soup, "Home")
        assert name == "CAROLINA HURRICANES"
        assert abbrev == "CAR"

    def test_parse_missing_team(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing when team table is missing."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        name, abbrev = downloader._parse_team_header(soup, "Visitor")
        assert name == ""
        assert abbrev == ""


# =============================================================================
# Period Row Parsing Tests
# =============================================================================


class TestPeriodRowParsing:
    """Tests for period row parsing."""

    def test_parse_period_row(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing a complete period row."""
        html = """
        <tr class="oddColor">
            <td>1</td>
            <td>0-11</td>
            <td>0-1</td>
            <td>0-1</td>
            <td>0-13</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")
        assert row is not None
        period_stats = downloader._parse_period_row(row)

        assert period_stats is not None
        assert period_stats.period == "1"
        assert period_stats.even_strength.shots == 11
        assert period_stats.power_play.shots == 1
        assert period_stats.shorthanded.shots == 1
        assert period_stats.total.shots == 13

    def test_parse_period_row_with_empty_cells(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test parsing period row with empty cells."""
        html = """
        <tr class="evenColor">
            <td>2</td>
            <td>0-10</td>
            <td>&nbsp;</td>
            <td>&nbsp;</td>
            <td>0-10</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")
        assert row is not None
        period_stats = downloader._parse_period_row(row)

        assert period_stats is not None
        assert period_stats.period == "2"
        assert period_stats.even_strength.shots == 10
        assert period_stats.power_play.shots == 0
        assert period_stats.shorthanded.shots == 0
        assert period_stats.total.shots == 10

    def test_parse_period_row_tot(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing TOT (total) row."""
        html = """
        <tr class="evenColor">
            <td>TOT</td>
            <td>3-28</td>
            <td>1-1</td>
            <td>&nbsp;</td>
            <td>4-29</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")
        assert row is not None
        period_stats = downloader._parse_period_row(row)

        assert period_stats is not None
        assert period_stats.period == "TOT"
        assert period_stats.even_strength.goals == 3
        assert period_stats.even_strength.shots == 28
        assert period_stats.total.goals == 4
        assert period_stats.total.shots == 29

    def test_parse_period_row_insufficient_cells(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test parsing row with insufficient cells."""
        html = "<tr><td>1</td><td>0-5</td></tr>"
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")
        assert row is not None
        period_stats = downloader._parse_period_row(row)
        assert period_stats is None


# =============================================================================
# Full HTML Parsing Tests
# =============================================================================


class TestFullHTMLParsing:
    """Tests for complete HTML document parsing."""

    @pytest.mark.asyncio
    async def test_parse_report(
        self, downloader: ShotSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing complete report."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert "away_team" in result
        assert "home_team" in result

    @pytest.mark.asyncio
    async def test_parse_report_team_names(
        self, downloader: ShotSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test team names are parsed correctly."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        assert result["away_team"]["name"] == "NEW YORK ISLANDERS"
        assert result["away_team"]["abbrev"] == "NYI"
        assert result["home_team"]["name"] == "CAROLINA HURRICANES"
        assert result["home_team"]["abbrev"] == "CAR"


# =============================================================================
# Integration Tests
# =============================================================================


class TestDownloadIntegration:
    """Integration tests for download functionality."""

    @pytest.mark.asyncio
    async def test_download_game(
        self, downloader: ShotSummaryDownloader, sample_html: bytes
    ) -> None:
        """Test downloading and parsing a game."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status = 200
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await downloader.download_game(2024020500)

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "html_ss"
        assert result.game_id == 2024020500
        assert result.season_id == 20242025
        assert result.data is not None
        assert "away_team" in result.data
        assert "home_team" in result.data

    @pytest.mark.asyncio
    async def test_download_game_stores_raw_html(
        self, config: HTMLDownloaderConfig, sample_html: bytes
    ) -> None:
        """Test that raw HTML is stored when configured."""
        config.store_raw_html = True
        downloader = ShotSummaryDownloader(config)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status = 200
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await downloader.download_game(2024020500)

        assert result.raw_content is not None
        assert len(result.raw_content) > 0


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_html(self, downloader: ShotSummaryDownloader) -> None:
        """Test handling empty HTML."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        away_periods, home_periods = downloader._parse_team_summaries(soup)
        assert away_periods == []
        assert home_periods == []

    def test_missing_player_section(self, downloader: ShotSummaryDownloader) -> None:
        """Test handling missing player section."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        away_players, home_players = downloader._parse_player_summaries(soup)
        assert away_players == []
        assert home_players == []

    @pytest.mark.asyncio
    async def test_malformed_goals_shots(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test handling malformed goals-shots values."""
        # Various malformed inputs
        test_cases = [
            ("abc-def", SituationStats(goals=0, shots=0)),
            ("1-", SituationStats(goals=1, shots=0)),
            ("-5", SituationStats(goals=0, shots=5)),
            ("--", SituationStats(goals=0, shots=0)),
        ]
        for input_val, expected in test_cases:
            result = downloader._parse_goals_shots(input_val)
            assert result.goals == expected.goals, f"Failed for input: {input_val}"
            assert result.shots == expected.shots, f"Failed for input: {input_val}"


# =============================================================================
# Dictionary Conversion Tests
# =============================================================================


class TestDictionaryConversion:
    """Tests for dataclass to dictionary conversion."""

    def test_period_to_dict(self, downloader: ShotSummaryDownloader) -> None:
        """Test PeriodSituationStats to dict conversion."""
        period = PeriodSituationStats(
            period="1",
            even_strength=SituationStats(goals=1, shots=10),
            power_play=SituationStats(goals=1, shots=3),
            shorthanded=SituationStats(goals=0, shots=0),
            total=SituationStats(goals=2, shots=13),
        )
        result = downloader._period_to_dict(period)

        assert result["period"] == "1"
        assert result["even_strength"]["goals"] == 1
        assert result["even_strength"]["shots"] == 10
        assert result["power_play"]["goals"] == 1
        assert result["power_play"]["shots"] == 3
        assert result["total"]["goals"] == 2
        assert result["total"]["shots"] == 13

    def test_player_to_dict(self, downloader: ShotSummaryDownloader) -> None:
        """Test PlayerShotSummary to dict conversion."""
        player = PlayerShotSummary(
            number=13,
            first_name="MATHEW",
            last_name="BARZAL",
            periods=[
                PeriodSituationStats(
                    period="TOT", total=SituationStats(goals=0, shots=4)
                )
            ],
        )
        result = downloader._player_to_dict(player)

        assert result["number"] == 13
        assert result["first_name"] == "MATHEW"
        assert result["last_name"] == "BARZAL"
        assert result["name"] == "MATHEW BARZAL"
        assert result["total_shots"] == 4
        assert result["total_goals"] == 0
        assert len(result["periods"]) == 1

    def test_team_to_dict(self, downloader: ShotSummaryDownloader) -> None:
        """Test TeamShotSummary to dict conversion."""
        team = TeamShotSummary(
            name="CAROLINA HURRICANES",
            abbrev="CAR",
            periods=[
                PeriodSituationStats(
                    period="TOT", total=SituationStats(goals=4, shots=29)
                )
            ],
            players=[
                PlayerShotSummary(
                    number=37,
                    first_name="ANDREI",
                    last_name="SVECHNIKOV",
                    periods=[
                        PeriodSituationStats(
                            period="TOT", total=SituationStats(goals=2, shots=6)
                        )
                    ],
                )
            ],
        )
        result = downloader._team_to_dict(team)

        assert result["name"] == "CAROLINA HURRICANES"
        assert result["abbrev"] == "CAR"
        assert result["total_shots"] == 29
        assert result["total_goals"] == 4
        assert len(result["periods"]) == 1
        assert len(result["players"]) == 1
        assert result["players"][0]["name"] == "ANDREI SVECHNIKOV"


# =============================================================================
# Season Extraction Tests
# =============================================================================


class TestSeasonExtraction:
    """Tests for season ID extraction from game ID."""

    def test_extract_season_regular(self, downloader: ShotSummaryDownloader) -> None:
        """Test extracting season from regular season game ID."""
        season_id = downloader._extract_season_from_game_id(2024020500)
        assert season_id == 20242025

    def test_extract_season_playoffs(self, downloader: ShotSummaryDownloader) -> None:
        """Test extracting season from playoff game ID."""
        season_id = downloader._extract_season_from_game_id(2024030111)
        assert season_id == 20242025

    def test_extract_season_preseason(self, downloader: ShotSummaryDownloader) -> None:
        """Test extracting season from preseason game ID."""
        season_id = downloader._extract_season_from_game_id(2024010005)
        assert season_id == 20242025


# =============================================================================
# Set Game IDs Tests
# =============================================================================


class TestSetGameIds:
    """Tests for game ID management."""

    def test_set_game_ids(self, downloader: ShotSummaryDownloader) -> None:
        """Test setting game IDs."""
        game_ids = [2024020001, 2024020002, 2024020003]
        downloader.set_game_ids(game_ids)
        assert downloader._game_ids == game_ids

    def test_set_game_ids_empty(self, downloader: ShotSummaryDownloader) -> None:
        """Test setting empty game ID list."""
        downloader.set_game_ids([])
        assert downloader._game_ids == []


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestPlayerTotalGoalsNoTot:
    """Tests for player total goals when no TOT period."""

    def test_total_goals_sum_when_no_tot(self) -> None:
        """Test total_goals sums periods when no TOT period exists."""
        player = PlayerShotSummary(
            number=37,
            first_name="ANDREI",
            last_name="SVECHNIKOV",
            periods=[
                PeriodSituationStats(
                    period="1", total=SituationStats(goals=1, shots=2)
                ),
                PeriodSituationStats(
                    period="2", total=SituationStats(goals=1, shots=3)
                ),
            ],
        )
        assert player.total_goals == 2


class TestTeamTotalGoalsNoTot:
    """Tests for team total goals when no TOT period."""

    def test_total_goals_sum_when_no_tot(self) -> None:
        """Test team total_goals sums periods when no TOT."""
        team = TeamShotSummary(
            name="CAROLINA HURRICANES",
            abbrev="CAR",
            periods=[
                PeriodSituationStats(
                    period="1", total=SituationStats(goals=2, shots=11)
                ),
                PeriodSituationStats(
                    period="2", total=SituationStats(goals=2, shots=12)
                ),
            ],
        )
        assert team.total_goals == 4
        assert team.total_shots == 23


class TestTeamSummaryParsing:
    """Tests for team summary parsing with real structure."""

    def test_parse_situation_table_with_data(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test parsing a situation table directly."""
        html = """
        <div>
            <table>
                <tr class="heading">
                    <td>Per</td><td>EV</td><td>PP</td><td>SH</td><td>TOT</td>
                </tr>
                <tr class="oddColor">
                    <td>1</td><td>0-11</td><td>0-1</td><td>0-1</td><td>0-13</td>
                </tr>
                <tr class="evenColor">
                    <td>TOT</td><td>0-25</td><td>0-1</td><td>0-1</td><td>0-27</td>
                </tr>
            </table>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        container = soup.find("div")
        assert container is not None
        periods = downloader._parse_situation_table(container)

        assert len(periods) == 2
        assert periods[0].period == "1"
        assert periods[0].total.shots == 13
        assert periods[1].period == "TOT"
        assert periods[1].total.shots == 27

    def test_parse_situation_table_no_header(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test parsing situation table with no heading class."""
        html = """
        <table>
            <tr>
                <td>Per</td><td>EV</td><td>PP</td><td>SH</td><td>TOT</td>
            </tr>
            <tr class="oddColor">
                <td>1</td><td>0-5</td><td>0-1</td><td>0-0</td><td>0-6</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        assert table is not None
        periods = downloader._parse_situation_table(table)
        # No header with class="heading", so no periods found
        assert periods == []


class TestPlayerSummaryParsing:
    """Tests for player summary parsing."""

    def test_parse_player_column_with_data(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test parsing player column directly."""
        html = """
        <td valign="top">
            <table>
                <tr>
                    <td class="lborder + bborder">
                        <table>
                            <tr><td align="center">13</td></tr>
                            <tr><td align="center">MATHEW</td></tr>
                            <tr><td align="center">BARZAL</td></tr>
                        </table>
                    </td>
                    <td class="bborder" valign="top">
                        <table>
                            <tr class="oddColor" valign="top">
                                <td>1</td><td>0-2</td><td>0-0</td><td>0-0</td><td>0-2</td>
                            </tr>
                            <tr class="evenColor" valign="top">
                                <td>TOT</td><td>0-4</td><td>0-0</td><td>0-0</td><td>0-4</td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </td>
        """
        soup = BeautifulSoup(html, "lxml")
        container = soup.find("td")
        assert container is not None
        players = downloader._parse_player_column(container)

        assert len(players) == 1
        assert players[0].number == 13
        assert players[0].first_name == "MATHEW"
        assert players[0].last_name == "BARZAL"
        assert players[0].total_shots == 4

    def test_parse_player_column_no_player_table(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test parsing player column when no player table exists."""
        html = """
        <table>
            <tr>
                <td class="lborder + bborder">No player table here</td>
                <td class="bborder" valign="top">Stats</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        assert table is not None
        players = downloader._parse_player_column(table)
        assert players == []

    def test_parse_player_column_insufficient_rows(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test parsing player column with insufficient player info rows."""
        html = """
        <table>
            <tr>
                <td class="lborder + bborder">
                    <table>
                        <tr><td>13</td></tr>
                        <tr><td>BARZAL</td></tr>
                    </table>
                </td>
                <td class="bborder" valign="top">
                    <table>
                        <tr class="oddColor"><td>1</td><td>0-2</td><td>0-0</td><td>0-0</td><td>0-2</td></tr>
                    </table>
                </td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        assert table is not None
        players = downloader._parse_player_column(table)
        # Only 2 rows in player table, needs 3
        assert players == []

    def test_parse_player_stats_table_no_table(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test parsing player stats when no table exists."""
        html = "<td>No table here</td>"
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        assert cell is not None
        periods = downloader._parse_player_stats_table(cell)
        assert periods == []


class TestTeamSummaryEdgeCases:
    """Tests for team summary edge cases."""

    def test_missing_parent_row(self, downloader: ShotSummaryDownloader) -> None:
        """Test team summary when parent row is missing."""
        # Section heading without proper parent structure
        html = """
        <html><body>
        <td class="sectionheading">TEAM SUMMARY (Goals-Shots)</td>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        away_periods, home_periods = downloader._parse_team_summaries(soup)
        assert away_periods == []
        assert home_periods == []

    def test_missing_next_sibling_row(self, downloader: ShotSummaryDownloader) -> None:
        """Test team summary when next sibling row is missing."""
        html = """
        <html><body>
        <table>
            <tr><td class="sectionheading">TEAM SUMMARY (Goals-Shots)</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        away_periods, home_periods = downloader._parse_team_summaries(soup)
        assert away_periods == []
        assert home_periods == []

    def test_missing_shots_summary_table(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test team summary when ShotsSummary table is missing."""
        html = """
        <html><body>
        <table>
            <tr><td class="sectionheading">TEAM SUMMARY (Goals-Shots)</td></tr>
            <tr><td>No ShotsSummary table here</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        away_periods, home_periods = downloader._parse_team_summaries(soup)
        assert away_periods == []
        assert home_periods == []


class TestPlayerSummaryEdgeCases:
    """Tests for player summary edge cases."""

    def test_missing_parent_row(self, downloader: ShotSummaryDownloader) -> None:
        """Test player summary when parent row is missing."""
        html = """
        <html><body>
        <td class="sectionheading">PLAYER SUMMARY (Goals-Shots)</td>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        away_players, home_players = downloader._parse_player_summaries(soup)
        assert away_players == []
        assert home_players == []

    def test_missing_next_sibling_row(self, downloader: ShotSummaryDownloader) -> None:
        """Test player summary when next sibling row is missing."""
        html = """
        <html><body>
        <table>
            <tr><td class="sectionheading">PLAYER SUMMARY (Goals-Shots)</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        away_players, home_players = downloader._parse_player_summaries(soup)
        assert away_players == []
        assert home_players == []

    def test_missing_shots_summary_table(
        self, downloader: ShotSummaryDownloader
    ) -> None:
        """Test player summary when ShotsSummary table is missing."""
        html = """
        <html><body>
        <table>
            <tr><td class="sectionheading">PLAYER SUMMARY (Goals-Shots)</td></tr>
            <tr><td>No ShotsSummary table here</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        away_players, home_players = downloader._parse_player_summaries(soup)
        assert away_players == []
        assert home_players == []

    def test_invalid_player_number(self, downloader: ShotSummaryDownloader) -> None:
        """Test parsing when player number is not valid."""
        html = """
        <table>
            <tr>
                <td class="lborder + bborder">
                    <table>
                        <tr><td>ABC</td></tr>
                        <tr><td>MATHEW</td></tr>
                        <tr><td>BARZAL</td></tr>
                    </table>
                </td>
                <td class="bborder" valign="top">
                    <table>
                        <tr class="oddColor"><td>1</td><td>0-2</td><td>0-0</td><td>0-0</td><td>0-2</td></tr>
                    </table>
                </td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        assert table is not None
        players = downloader._parse_player_column(table)
        # Invalid number "ABC" should skip this player
        assert players == []
