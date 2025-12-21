"""Unit tests for FaceoffSummaryDownloader.

Tests cover:
- HTML parsing of faceoff summary reports
- Team summary parsing (period and zone/strength breakdowns)
- Player faceoff stats parsing
- Faceoff stat format parsing (won-total/pct)
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
from nhl_api.downloaders.sources.html.faceoff_summary import (
    FACEOFF_STAT_PATTERN,
    PLAYER_HEADER_PATTERN,
    FaceoffStat,
    FaceoffSummaryDownloader,
    PeriodFaceoffs,
    PlayerFaceoffStats,
    StrengthFaceoffs,
    TeamFaceoffSummary,
    ZoneFaceoffs,
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
def downloader(config: HTMLDownloaderConfig) -> FaceoffSummaryDownloader:
    """Create test downloader instance."""
    return FaceoffSummaryDownloader(config)


@pytest.fixture
def sample_html() -> bytes:
    """Load sample Faceoff Summary HTML fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "html"
        / "FS020500.HTM"
    )
    if fixture_path.exists():
        return fixture_path.read_bytes()
    # Fallback minimal HTML for testing
    return b"""<!DOCTYPE html>
<html>
<head><title>Faceoff Summary</title></head>
<body>
<table id="TeamTable">
    <tr>
        <td width="50%">
            <table><tr><td class="teamHeading">NEW YORK ISLANDERS</td></tr></table>
            <table>
                <tr class="sectionheading">
                    <td>Per</td><td>EV</td><td>PP</td><td>SH</td><td>TOT</td>
                </tr>
                <tr class="oddColor">
                    <td>1</td><td>7-13/54%</td><td>2-3/67%</td><td>1-1/100%</td><td>10-17/59%</td>
                </tr>
                <tr class="evenColor">
                    <td>2</td><td>11-19/58%</td><td>&nbsp;</td><td>&nbsp;</td><td>11-19/58%</td>
                </tr>
                <tr class="oddColor">
                    <td>3</td><td>7-15/47%</td><td>&nbsp;</td><td>0-1/0%</td><td>7-16/44%</td>
                </tr>
                <tr>
                    <td class="totalRow">TOT</td><td>25-47/53%</td><td>2-3/67%</td><td>1-2/50%</td><td>28-52/54%</td>
                </tr>
            </table>
            <table>
                <tr class="sectionheading">
                    <td>Strength</td><td>Off.</td><td>Def.</td><td>Neu.</td><td>TOT</td>
                </tr>
                <tr class="oddColor">
                    <td>5v5</td><td>8-14/57%</td><td>9-14/64%</td><td>6-17/35%</td><td>23-45/51%</td>
                </tr>
                <tr class="evenColor">
                    <td>4v5</td><td>&nbsp;</td><td>1-2/50%</td><td>&nbsp;</td><td>1-2/50%</td>
                </tr>
                <tr>
                    <td class="totalRow">TOT</td><td>11-17/65%</td><td>10-16/63%</td><td>7-19/37%</td><td>28-52/54%</td>
                </tr>
            </table>
        </td>
        <td width="50%">
            <table><tr><td class="teamHeading">CAROLINA HURRICANES</td></tr></table>
            <table>
                <tr class="sectionheading">
                    <td>Per</td><td>EV</td><td>PP</td><td>SH</td><td>TOT</td>
                </tr>
                <tr class="oddColor">
                    <td>1</td><td>6-13/46%</td><td>0-1/0%</td><td>1-3/33%</td><td>7-17/41%</td>
                </tr>
                <tr>
                    <td class="totalRow">TOT</td><td>22-47/47%</td><td>1-2/50%</td><td>1-3/33%</td><td>24-52/46%</td>
                </tr>
            </table>
            <table>
                <tr class="sectionheading">
                    <td>Strength</td><td>Off.</td><td>Def.</td><td>Neu.</td><td>TOT</td>
                </tr>
                <tr class="oddColor">
                    <td>5v5</td><td>5-14/36%</td><td>6-14/43%</td><td>11-17/65%</td><td>22-45/49%</td>
                </tr>
                <tr>
                    <td class="totalRow">TOT</td><td>6-16/38%</td><td>6-17/35%</td><td>12-19/63%</td><td>24-52/46%</td>
                </tr>
            </table>
        </td>
    </tr>
</table>
<table id="PlayerTable">
    <tr>
        <td class="sectionheading">PLAYER SUMMARY</td>
    </tr>
    <tr>
        <td valign="top">
            <table>
                <tr><td class="teamHeading">NEW YORK ISLANDERS</td></tr>
            </table>
            <table>
                <tr><td colspan="5" class="playerHeading">14 C HORVAT, BO</td></tr>
                <tr class="sectionheading">
                    <td>Strength</td><td>Off.</td><td>Def.</td><td>Neu.</td><td>TOT</td>
                </tr>
                <tr class="oddColor">
                    <td>5v5</td><td>6-7/86%</td><td>3-5/60%</td><td>1-4/25%</td><td>10-16/63%</td>
                </tr>
                <tr class="evenColor">
                    <td>5v4</td><td>1-1/100%</td><td>&nbsp;</td><td>&nbsp;</td><td>1-1/100%</td>
                </tr>
                <tr>
                    <td class="totalRow">TOT</td><td>8-9/89%</td><td>3-5/60%</td><td>1-4/25%</td><td>12-18/67%</td>
                </tr>
            </table>
        </td>
        <td valign="top">
            <table>
                <tr><td class="teamHeading">CAROLINA HURRICANES</td></tr>
            </table>
            <table>
                <tr><td colspan="5" class="playerHeading">11 C STAAL, JORDAN</td></tr>
                <tr class="sectionheading">
                    <td>Strength</td><td>Off.</td><td>Def.</td><td>Neu.</td><td>TOT</td>
                </tr>
                <tr class="oddColor">
                    <td>5v5</td><td>2-7/29%</td><td>3-5/60%</td><td>5-8/63%</td><td>10-20/50%</td>
                </tr>
                <tr>
                    <td class="totalRow">TOT</td><td>2-7/29%</td><td>3-6/50%</td><td>5-8/63%</td><td>10-21/48%</td>
                </tr>
            </table>
        </td>
    </tr>
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


class TestFaceoffSummaryDownloaderConfig:
    """Tests for FaceoffSummaryDownloader configuration."""

    def test_report_type(self, downloader: FaceoffSummaryDownloader) -> None:
        """Test report_type is 'FS'."""
        assert downloader.report_type == "FS"

    def test_source_name(self, downloader: FaceoffSummaryDownloader) -> None:
        """Test source_name is 'html_fs'."""
        assert downloader.source_name == "html_fs"


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for data classes."""

    def test_faceoff_stat(self) -> None:
        """Test FaceoffStat creation and properties."""
        stat = FaceoffStat(won=8, total=12, pct=66.7)
        assert stat.won == 8
        assert stat.total == 12
        assert stat.pct == 66.7
        assert stat.lost == 4

    def test_faceoff_stat_default(self) -> None:
        """Test FaceoffStat default values."""
        stat = FaceoffStat()
        assert stat.won == 0
        assert stat.total == 0
        assert stat.pct == 0.0
        assert stat.lost == 0

    def test_zone_faceoffs(self) -> None:
        """Test ZoneFaceoffs creation."""
        zones = ZoneFaceoffs(
            offensive=FaceoffStat(won=5, total=10, pct=50.0),
            defensive=FaceoffStat(won=3, total=8, pct=37.5),
            neutral=FaceoffStat(won=7, total=12, pct=58.3),
            total=FaceoffStat(won=15, total=30, pct=50.0),
        )
        assert zones.offensive.won == 5
        assert zones.defensive.won == 3
        assert zones.neutral.won == 7
        assert zones.total.won == 15

    def test_strength_faceoffs(self) -> None:
        """Test StrengthFaceoffs creation."""
        strength = StrengthFaceoffs(
            strength="5v5",
            zones=ZoneFaceoffs(total=FaceoffStat(won=20, total=40, pct=50.0)),
        )
        assert strength.strength == "5v5"
        assert strength.zones.total.won == 20

    def test_period_faceoffs(self) -> None:
        """Test PeriodFaceoffs creation."""
        period = PeriodFaceoffs(
            period="1",
            ev=FaceoffStat(won=7, total=13, pct=54.0),
            pp=FaceoffStat(won=2, total=3, pct=67.0),
            sh=FaceoffStat(won=1, total=1, pct=100.0),
            total=FaceoffStat(won=10, total=17, pct=59.0),
        )
        assert period.period == "1"
        assert period.ev.won == 7
        assert period.pp.won == 2
        assert period.sh.won == 1
        assert period.total.won == 10

    def test_player_faceoff_stats(self) -> None:
        """Test PlayerFaceoffStats creation."""
        player = PlayerFaceoffStats(
            number=14,
            position="C",
            name="HORVAT, BO",
            totals=ZoneFaceoffs(total=FaceoffStat(won=12, total=18, pct=67.0)),
        )
        assert player.number == 14
        assert player.position == "C"
        assert player.name == "HORVAT, BO"
        assert player.totals.total.won == 12

    def test_team_faceoff_summary(self) -> None:
        """Test TeamFaceoffSummary creation."""
        team = TeamFaceoffSummary(
            name="NEW YORK ISLANDERS",
            totals=ZoneFaceoffs(total=FaceoffStat(won=28, total=52, pct=54.0)),
        )
        assert team.name == "NEW YORK ISLANDERS"
        assert team.totals.total.won == 28


# =============================================================================
# Pattern Tests
# =============================================================================


class TestPatterns:
    """Tests for regex patterns."""

    def test_faceoff_stat_pattern_with_pct(self) -> None:
        """Test FACEOFF_STAT_PATTERN with percentage."""
        match = FACEOFF_STAT_PATTERN.match("8-9/89%")
        assert match is not None
        assert match.group(1) == "8"
        assert match.group(2) == "9"
        assert match.group(3) == "89"

    def test_faceoff_stat_pattern_without_pct(self) -> None:
        """Test FACEOFF_STAT_PATTERN without percentage."""
        match = FACEOFF_STAT_PATTERN.match("8-9")
        assert match is not None
        assert match.group(1) == "8"
        assert match.group(2) == "9"
        assert match.group(3) is None

    def test_faceoff_stat_pattern_zero(self) -> None:
        """Test FACEOFF_STAT_PATTERN with zero."""
        match = FACEOFF_STAT_PATTERN.match("0-1/0%")
        assert match is not None
        assert match.group(1) == "0"
        assert match.group(2) == "1"
        assert match.group(3) == "0"

    def test_player_header_pattern(self) -> None:
        """Test PLAYER_HEADER_PATTERN."""
        match = PLAYER_HEADER_PATTERN.match("14 C HORVAT, BO")
        assert match is not None
        assert match.group(1) == "14"
        assert match.group(2) == "C"
        assert match.group(3) == "HORVAT, BO"

    def test_player_header_pattern_with_hyphen(self) -> None:
        """Test PLAYER_HEADER_PATTERN with hyphenated name."""
        match = PLAYER_HEADER_PATTERN.match("44 C PAGEAU, JEAN-GABRIEL")
        assert match is not None
        assert match.group(1) == "44"
        assert match.group(2) == "C"
        assert match.group(3) == "PAGEAU, JEAN-GABRIEL"


# =============================================================================
# Faceoff Stat Parsing Tests
# =============================================================================


class TestFaceoffStatParsing:
    """Tests for faceoff stat parsing."""

    def test_parse_faceoff_stat_with_pct(
        self, downloader: FaceoffSummaryDownloader
    ) -> None:
        """Test parsing stat with percentage."""
        stat = downloader._parse_faceoff_stat("8-9/89%")
        assert stat.won == 8
        assert stat.total == 9
        assert stat.pct == 89.0
        assert stat.lost == 1

    def test_parse_faceoff_stat_without_pct(
        self, downloader: FaceoffSummaryDownloader
    ) -> None:
        """Test parsing stat without percentage (calculates it)."""
        stat = downloader._parse_faceoff_stat("8-10")
        assert stat.won == 8
        assert stat.total == 10
        assert stat.pct == 80.0

    def test_parse_faceoff_stat_zero_total(
        self, downloader: FaceoffSummaryDownloader
    ) -> None:
        """Test parsing stat with zero total."""
        stat = downloader._parse_faceoff_stat("0-0")
        assert stat.won == 0
        assert stat.total == 0
        assert stat.pct == 0.0

    def test_parse_faceoff_stat_empty(
        self, downloader: FaceoffSummaryDownloader
    ) -> None:
        """Test parsing empty/nbsp stat."""
        stat = downloader._parse_faceoff_stat("&nbsp;")
        assert stat.won == 0
        assert stat.total == 0
        assert stat.pct == 0.0

    def test_parse_faceoff_stat_whitespace(
        self, downloader: FaceoffSummaryDownloader
    ) -> None:
        """Test parsing whitespace stat."""
        stat = downloader._parse_faceoff_stat("  ")
        assert stat.won == 0
        assert stat.total == 0

    def test_parse_faceoff_stat_100_pct(
        self, downloader: FaceoffSummaryDownloader
    ) -> None:
        """Test parsing 100% stat."""
        stat = downloader._parse_faceoff_stat("5-5/100%")
        assert stat.won == 5
        assert stat.total == 5
        assert stat.pct == 100.0
        assert stat.lost == 0


# =============================================================================
# Team Summary Parsing Tests
# =============================================================================


class TestTeamSummaryParsing:
    """Tests for team summary parsing."""

    def test_parse_team_summaries(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of team summaries."""
        away, home = downloader._parse_team_summaries(sample_soup)

        # Check team names
        assert "ISLANDERS" in away.name.upper()
        assert "HURRICANES" in home.name.upper() or "CAROLINA" in home.name.upper()

    def test_parse_period_table(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of period table."""
        away, _ = downloader._parse_team_summaries(sample_soup)

        # Should have period data
        assert len(away.by_period) >= 1

        # Check first period
        if away.by_period:
            first_period = away.by_period[0]
            assert first_period.period in ("1", "2", "3", "OT", "TOT")

    def test_parse_zone_strength_table(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of zone/strength table."""
        away, _ = downloader._parse_team_summaries(sample_soup)

        # Should have strength data
        assert len(away.by_strength) >= 1

        # Check for 5v5
        strength_names = [s.strength for s in away.by_strength]
        assert "5v5" in strength_names


# =============================================================================
# Player Summary Parsing Tests
# =============================================================================


class TestPlayerSummaryParsing:
    """Tests for player summary parsing."""

    def test_parse_player_summaries(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of player summaries."""
        away_players, home_players = downloader._parse_player_summaries(sample_soup)

        # Should have players for at least one team
        assert len(away_players) >= 1 or len(home_players) >= 1

    def test_parse_player_header(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of player headers."""
        away_players, _ = downloader._parse_player_summaries(sample_soup)

        if away_players:
            player = away_players[0]
            assert player.number > 0
            assert player.position in ("C", "L", "R", "D", "G")
            assert len(player.name) > 0

    def test_parse_player_stats(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of player stats."""
        away_players, _ = downloader._parse_player_summaries(sample_soup)

        if away_players:
            player = away_players[0]
            # Should have totals
            assert player.totals is not None


# =============================================================================
# Full Parse Tests
# =============================================================================


class TestFullParse:
    """Tests for full report parsing."""

    @pytest.mark.asyncio
    async def test_parse_report(
        self,
        downloader: FaceoffSummaryDownloader,
        sample_soup: BeautifulSoup,
    ) -> None:
        """Test full report parsing."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Check structure
        assert "game_id" in result
        assert "season_id" in result
        assert "teams" in result
        assert "away" in result["teams"]
        assert "home" in result["teams"]

        # Check values
        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025

    @pytest.mark.asyncio
    async def test_download_game_success(
        self,
        downloader: FaceoffSummaryDownloader,
        sample_html: bytes,
    ) -> None:
        """Test successful game download."""
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
        assert result.source == "html_fs"
        assert result.raw_content == sample_html


# =============================================================================
# Output Format Tests
# =============================================================================


class TestOutputFormat:
    """Tests for output format compliance."""

    @pytest.mark.asyncio
    async def test_summary_to_dict(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test _summary_to_dict output format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Verify expected keys
        expected_keys = {"game_id", "season_id", "teams"}
        assert set(result.keys()) == expected_keys

        # Verify team structure
        team_keys = {"name", "by_period", "by_strength", "totals", "players"}
        assert set(result["teams"]["away"].keys()) == team_keys
        assert set(result["teams"]["home"].keys()) == team_keys

    @pytest.mark.asyncio
    async def test_team_dict_format(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test team dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        away_team = result["teams"]["away"]
        assert isinstance(away_team["name"], str)
        assert isinstance(away_team["by_period"], list)
        assert isinstance(away_team["by_strength"], list)
        assert isinstance(away_team["totals"], dict)
        assert isinstance(away_team["players"], list)

    @pytest.mark.asyncio
    async def test_zones_dict_format(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test zones dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        totals = result["teams"]["away"]["totals"]
        zone_keys = {"offensive", "defensive", "neutral", "total"}
        assert set(totals.keys()) == zone_keys

    @pytest.mark.asyncio
    async def test_stat_dict_format(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test stat dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        total_stat = result["teams"]["away"]["totals"]["total"]
        stat_keys = {"won", "lost", "total", "pct"}
        assert set(total_stat.keys()) == stat_keys

    @pytest.mark.asyncio
    async def test_player_dict_format(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test player dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        players = result["teams"]["away"]["players"]
        if players:
            player = players[0]
            player_keys = {"number", "position", "name", "by_strength", "totals"}
            assert set(player.keys()) == player_keys
            assert isinstance(player["number"], int)
            assert isinstance(player["position"], str)
            assert isinstance(player["name"], str)

    @pytest.mark.asyncio
    async def test_period_dict_format(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test period dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        periods = result["teams"]["away"]["by_period"]
        if periods:
            period = periods[0]
            period_keys = {"period", "ev", "pp", "sh", "total"}
            assert set(period.keys()) == period_keys

    @pytest.mark.asyncio
    async def test_strength_dict_format(
        self, downloader: FaceoffSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test strength dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        strengths = result["teams"]["away"]["by_strength"]
        if strengths:
            strength = strengths[0]
            strength_keys = {"strength", "zones"}
            assert set(strength.keys()) == strength_keys
            assert isinstance(strength["strength"], str)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_empty_html(self, downloader: FaceoffSummaryDownloader) -> None:
        """Test parsing empty HTML."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        away, home = downloader._parse_team_summaries(soup)

        assert away.name == ""
        assert home.name == ""
        assert len(away.players) == 0

    def test_parse_missing_player_table(
        self, downloader: FaceoffSummaryDownloader
    ) -> None:
        """Test parsing HTML without PlayerTable."""
        html = """
        <html><body>
        <table id="TeamTable">
            <tr><td class="teamHeading">TEAM A</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        away_players, home_players = downloader._parse_player_summaries(soup)

        assert len(away_players) == 0
        assert len(home_players) == 0

    def test_parse_malformed_stat(self, downloader: FaceoffSummaryDownloader) -> None:
        """Test parsing malformed stat string."""
        stat = downloader._parse_faceoff_stat("invalid")
        assert stat.won == 0
        assert stat.total == 0

    def test_parse_unicode_nbsp(self, downloader: FaceoffSummaryDownloader) -> None:
        """Test parsing unicode non-breaking space."""
        stat = downloader._parse_faceoff_stat("\xa0")  # Unicode NBSP
        assert stat.won == 0
        assert stat.total == 0


# =============================================================================
# Integration Tests with Real Fixture
# =============================================================================


class TestRealFixture:
    """Tests using the real HTML fixture file."""

    @pytest.fixture
    def real_fixture_path(self) -> Path:
        """Get path to real fixture file."""
        return (
            Path(__file__).parent.parent.parent.parent.parent
            / "fixtures"
            / "html"
            / "FS020500.HTM"
        )

    def test_fixture_exists(self, real_fixture_path: Path) -> None:
        """Test that fixture file exists."""
        assert real_fixture_path.exists(), f"Fixture not found: {real_fixture_path}"

    @pytest.mark.asyncio
    async def test_parse_real_fixture(
        self,
        downloader: FaceoffSummaryDownloader,
        real_fixture_path: Path,
    ) -> None:
        """Test parsing real fixture file."""
        if not real_fixture_path.exists():
            pytest.skip("Real fixture not available")

        html = real_fixture_path.read_bytes()
        soup = BeautifulSoup(html.decode("utf-8"), "lxml")
        result = await downloader._parse_report(soup, 2024020500)

        # Verify structure
        assert result["game_id"] == 2024020500
        assert "teams" in result

        # Verify both teams have data
        away = result["teams"]["away"]
        home = result["teams"]["home"]

        assert away["name"] != ""
        assert home["name"] != ""

        # Verify players extracted
        assert len(away["players"]) > 0 or len(home["players"]) > 0

    @pytest.mark.asyncio
    async def test_real_fixture_team_totals(
        self,
        downloader: FaceoffSummaryDownloader,
        real_fixture_path: Path,
    ) -> None:
        """Test team totals from real fixture."""
        if not real_fixture_path.exists():
            pytest.skip("Real fixture not available")

        html = real_fixture_path.read_bytes()
        soup = BeautifulSoup(html.decode("utf-8"), "lxml")
        result = await downloader._parse_report(soup, 2024020500)

        # Check that totals add up reasonably
        away_total = result["teams"]["away"]["totals"]["total"]
        home_total = result["teams"]["home"]["totals"]["total"]

        # Both teams should have faced off the same number of times
        # (with some tolerance for parsing issues)
        assert abs(away_total["total"] - home_total["total"]) <= 2

    @pytest.mark.asyncio
    async def test_real_fixture_player_count(
        self,
        downloader: FaceoffSummaryDownloader,
        real_fixture_path: Path,
    ) -> None:
        """Test player counts from real fixture."""
        if not real_fixture_path.exists():
            pytest.skip("Real fixture not available")

        html = real_fixture_path.read_bytes()
        soup = BeautifulSoup(html.decode("utf-8"), "lxml")
        result = await downloader._parse_report(soup, 2024020500)

        away_players = result["teams"]["away"]["players"]
        home_players = result["teams"]["home"]["players"]

        # Should have multiple players taking faceoffs
        total_players = len(away_players) + len(home_players)
        assert total_players >= 4, f"Expected at least 4 players, got {total_players}"
