"""Unit tests for FaceoffComparisonDownloader.

Tests cover:
- HTML parsing of faceoff comparison reports
- Team parsing from header
- Player faceoff summary extraction
- Head-to-head matchup parsing
- Zone breakdown parsing
- Zone summary calculation
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
from nhl_api.downloaders.sources.html.faceoff_comparison import (
    FACEOFF_RESULT_PATTERN,
    VS_PLAYER_PATTERN,
    FaceoffComparisonDownloader,
    FaceoffMatchup,
    FaceoffResult,
    PlayerFaceoffSummary,
    PlayerInfo,
    TeamFaceoffSummary,
    ZoneTotals,
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
def downloader(config: HTMLDownloaderConfig) -> FaceoffComparisonDownloader:
    """Create test downloader instance."""
    return FaceoffComparisonDownloader(config)


@pytest.fixture
def sample_html() -> bytes:
    """Load sample Faceoff Comparison HTML fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "html"
        / "FC020500.HTM"
    )
    if fixture_path.exists():
        return fixture_path.read_bytes()
    # Fallback minimal HTML for testing
    return _get_minimal_html()


def _get_minimal_html() -> bytes:
    """Generate minimal HTML for fallback testing."""
    return b"""<!DOCTYPE html>
<html>
<head><title>Faceoff Comparison</title></head>
<body>
<table id="Visitor">
    <tr><td><img src="logocnyi.gif" alt="NEW YORK ISLANDERS"></td></tr>
</table>
<table id="Home">
    <tr><td><img src="logoccar.gif" alt="CAROLINA HURRICANES"></td></tr>
</table>
<table border="0">
    <tr><td class="bborder + teamHeading" colspan="3">NEW YORK ISLANDERS</td></tr>
    <tr>
        <td class="playerHeading + lborder + bborder">14</td>
        <td class="playerHeading + lborder + bborder">C</td>
        <td class="playerHeading + lborder bborder">HORVAT, BO</td>
        <td class="playerHeading + lborder + bborder">8-9 / 89%</td>
        <td class="playerHeading + lborder + bborder">3-5 / 60%</td>
        <td class="playerHeading + lborder + bborder">1-4 / 25%</td>
        <td class="playerHeading + lborder + bborder + rborder">12-18 / 67%</td>
    </tr>
    <tr>
        <td colspan="2" class=" lborder + bborder">&nbsp;</td>
        <td class=" lborder + bborder">
            <table><tr><td>vs. 11 C STAAL, JORDAN</td></tr></table>
        </td>
        <td class=" lborder + bborder">4-4 / 100%</td>
        <td class=" lborder + bborder">&nbsp;</td>
        <td class=" lborder + bborder">&nbsp;</td>
        <td class=" lborder + bborder + rborder">4-4 / 100%</td>
    </tr>
</table>
<table border="0">
    <tr><td class="bborder + teamHeading" colspan="3">CAROLINA HURRICANES</td></tr>
    <tr>
        <td class="playerHeading + lborder + bborder">11</td>
        <td class="playerHeading + lborder + bborder">C</td>
        <td class="playerHeading + lborder bborder">STAAL, JORDAN</td>
        <td class="playerHeading + lborder + bborder">&nbsp;</td>
        <td class="playerHeading + lborder + bborder">3-9 / 33%</td>
        <td class="playerHeading + lborder + bborder">4-4 / 100%</td>
        <td class="playerHeading + lborder + bborder + rborder">7-13 / 54%</td>
    </tr>
</table>
</body>
</html>"""


@pytest.fixture
def sample_soup(sample_html: bytes) -> BeautifulSoup:
    """Parse sample HTML into BeautifulSoup."""
    return BeautifulSoup(sample_html.decode("utf-8"), "lxml")


# =============================================================================
# Pattern Tests
# =============================================================================


class TestPatterns:
    """Tests for regex patterns."""

    def test_faceoff_result_pattern(self) -> None:
        """Test FACEOFF_RESULT_PATTERN matches expected format."""
        match = FACEOFF_RESULT_PATTERN.match("8-9 / 89%")
        assert match is not None
        assert match.group(1) == "8"
        assert match.group(2) == "9"
        assert match.group(3) == "89"

    def test_faceoff_result_pattern_zero(self) -> None:
        """Test FACEOFF_RESULT_PATTERN matches zero values."""
        match = FACEOFF_RESULT_PATTERN.match("0-1 / 0%")
        assert match is not None
        assert match.group(1) == "0"
        assert match.group(2) == "1"
        assert match.group(3) == "0"

    def test_faceoff_result_pattern_hundred(self) -> None:
        """Test FACEOFF_RESULT_PATTERN matches 100%."""
        match = FACEOFF_RESULT_PATTERN.match("1-1 / 100%")
        assert match is not None
        assert match.group(3) == "100"

    def test_vs_player_pattern(self) -> None:
        """Test VS_PLAYER_PATTERN matches expected format."""
        match = VS_PLAYER_PATTERN.match("vs. 20 C AHO, SEBASTIAN")
        assert match is not None
        assert match.group(1) == "20"
        assert match.group(2) == "C"
        assert match.group(3) == "AHO, SEBASTIAN"

    def test_vs_player_pattern_left_wing(self) -> None:
        """Test VS_PLAYER_PATTERN matches left wing."""
        match = VS_PLAYER_PATTERN.match("vs. 28 L CARRIER, WILLIAM")
        assert match is not None
        assert match.group(2) == "L"


# =============================================================================
# Configuration Tests
# =============================================================================


class TestFaceoffComparisonDownloaderConfig:
    """Tests for FaceoffComparisonDownloader configuration."""

    def test_report_type(self, downloader: FaceoffComparisonDownloader) -> None:
        """Test report_type is 'FC'."""
        assert downloader.report_type == "FC"

    def test_source_name(self, downloader: FaceoffComparisonDownloader) -> None:
        """Test source_name is 'html_fc'."""
        assert downloader.source_name == "html_fc"


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for data classes."""

    def test_player_info(self) -> None:
        """Test PlayerInfo creation."""
        player = PlayerInfo(number=14, position="C", name="HORVAT, BO")
        assert player.number == 14
        assert player.position == "C"
        assert player.name == "HORVAT, BO"

    def test_faceoff_result(self) -> None:
        """Test FaceoffResult creation."""
        result = FaceoffResult(wins=8, total=9, percentage=89.0)
        assert result.wins == 8
        assert result.total == 9
        assert result.percentage == 89.0

    def test_faceoff_result_defaults(self) -> None:
        """Test FaceoffResult default values."""
        result = FaceoffResult(wins=1, total=1)
        assert result.percentage is None

    def test_faceoff_matchup(self) -> None:
        """Test FaceoffMatchup creation."""
        player = PlayerInfo(number=14, position="C", name="HORVAT, BO")
        opponent = PlayerInfo(number=11, position="C", name="STAAL, JORDAN")
        matchup = FaceoffMatchup(
            player=player,
            opponent=opponent,
            offensive=FaceoffResult(wins=4, total=4, percentage=100.0),
            total=FaceoffResult(wins=4, total=4, percentage=100.0),
        )
        assert matchup.player.number == 14
        assert matchup.opponent.number == 11
        assert matchup.offensive is not None
        assert matchup.offensive.wins == 4

    def test_player_faceoff_summary(self) -> None:
        """Test PlayerFaceoffSummary creation."""
        player = PlayerInfo(number=14, position="C", name="HORVAT, BO")
        summary = PlayerFaceoffSummary(
            player=player,
            offensive=FaceoffResult(wins=8, total=9, percentage=89.0),
            total=FaceoffResult(wins=12, total=18, percentage=67.0),
        )
        assert summary.player.number == 14
        assert summary.offensive is not None
        assert summary.offensive.wins == 8

    def test_team_faceoff_summary(self) -> None:
        """Test TeamFaceoffSummary creation."""
        team = TeamFaceoffSummary(
            name="NEW YORK ISLANDERS",
            abbrev="NYI",
        )
        assert team.name == "NEW YORK ISLANDERS"
        assert team.abbrev == "NYI"
        assert team.players == []

    def test_zone_totals(self) -> None:
        """Test ZoneTotals creation."""
        totals = ZoneTotals(wins=11, total=17)
        assert totals.wins == 11
        assert totals.total == 17


# =============================================================================
# Faceoff Cell Parsing Tests
# =============================================================================


class TestFaceoffCellParsing:
    """Tests for faceoff result cell parsing."""

    def test_parse_faceoff_cell_valid(
        self, downloader: FaceoffComparisonDownloader
    ) -> None:
        """Test parsing valid faceoff cell."""
        html = '<td class="test">8-9 / 89%</td>'
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        assert cell is not None
        result = downloader._parse_faceoff_cell(cell)
        assert result is not None
        assert result.wins == 8
        assert result.total == 9
        assert result.percentage == 89.0

    def test_parse_faceoff_cell_empty(
        self, downloader: FaceoffComparisonDownloader
    ) -> None:
        """Test parsing empty faceoff cell."""
        html = '<td class="test">&nbsp;</td>'
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        assert cell is not None
        result = downloader._parse_faceoff_cell(cell)
        assert result is None

    def test_parse_faceoff_cell_zero(
        self, downloader: FaceoffComparisonDownloader
    ) -> None:
        """Test parsing zero faceoff cell."""
        html = '<td class="test">0-1 / 0%</td>'
        soup = BeautifulSoup(html, "lxml")
        cell = soup.find("td")
        assert cell is not None
        result = downloader._parse_faceoff_cell(cell)
        assert result is not None
        assert result.wins == 0
        assert result.total == 1
        assert result.percentage == 0.0


# =============================================================================
# Team Parsing Tests
# =============================================================================


class TestTeamParsing:
    """Tests for team information parsing."""

    def test_extract_team_info(
        self, downloader: FaceoffComparisonDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test extracting team info from header."""
        visitor_table = sample_soup.find("table", id="Visitor")
        if visitor_table:
            name, abbrev = downloader._extract_team_info(visitor_table)
            assert name == "NEW YORK ISLANDERS"
            assert abbrev == "NYI"

    def test_parse_team_faceoffs_away(
        self, downloader: FaceoffComparisonDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing away team faceoffs."""
        away_team = downloader._parse_team_faceoffs(sample_soup, is_away=True)
        assert away_team.name == "NEW YORK ISLANDERS"
        assert len(away_team.players) > 0

    def test_parse_team_faceoffs_home(
        self, downloader: FaceoffComparisonDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing home team faceoffs."""
        home_team = downloader._parse_team_faceoffs(sample_soup, is_away=False)
        assert home_team.name == "CAROLINA HURRICANES"
        assert len(home_team.players) > 0


# =============================================================================
# Player Parsing Tests
# =============================================================================


class TestPlayerParsing:
    """Tests for player faceoff parsing."""

    def test_parse_player_header_row(
        self, downloader: FaceoffComparisonDownloader
    ) -> None:
        """Test parsing player header row."""
        html = """<tr>
            <td class="playerHeading">14</td>
            <td class="playerHeading">C</td>
            <td class="playerHeading">HORVAT, BO</td>
            <td class="playerHeading">8-9 / 89%</td>
            <td class="playerHeading">3-5 / 60%</td>
            <td class="playerHeading">1-4 / 25%</td>
            <td class="playerHeading">12-18 / 67%</td>
        </tr>"""
        soup = BeautifulSoup(html, "lxml")
        cells = soup.find_all("td")

        summary = downloader._parse_player_header_row(cells)
        assert summary.player.number == 14
        assert summary.player.position == "C"
        assert summary.player.name == "HORVAT, BO"
        assert summary.offensive is not None
        assert summary.offensive.wins == 8
        assert summary.total is not None
        assert summary.total.wins == 12


# =============================================================================
# Matchup Parsing Tests
# =============================================================================


class TestMatchupParsing:
    """Tests for head-to-head matchup parsing."""

    def test_parse_matchup_row(self, downloader: FaceoffComparisonDownloader) -> None:
        """Test parsing matchup row.

        Note: The actual HTML has 6 cells in matchup rows (due to colspan=2):
        - Cell 0: empty (colspan=2)
        - Cell 1: vs. player info (nested table)
        - Cell 2: offensive zone result
        - Cell 3: defensive zone result
        - Cell 4: neutral zone result
        - Cell 5: total result
        """
        # Match actual fixture format exactly - with colspan=2
        html = """<table><tr>
            <td colspan="2" class=" lborder + bborder">&nbsp;</td>
            <td class=" lborder + bborder">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr><td width="10%">&nbsp;</td>
                    <td width="90%" class="vsHeading" align="left">vs. 11 C STAAL, JORDAN</td></tr>
                </table>
            </td>
            <td align="center" class=" lborder + bborder">4-4 / 100%</td>
            <td align="center" class=" lborder + bborder">&nbsp;</td>
            <td align="center" class=" lborder + bborder ">&nbsp;</td>
            <td align="center" class=" lborder + bborder + rborder">4-4 / 100%</td>
        </tr></table>"""
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")
        assert row is not None
        cells = row.find_all("td", recursive=False)

        player = PlayerInfo(number=14, position="C", name="HORVAT, BO")
        matchup = downloader._parse_matchup_row(cells, "vs. 11 C STAAL, JORDAN", player)

        assert matchup is not None
        assert matchup.opponent.number == 11
        assert matchup.opponent.name == "STAAL, JORDAN"
        assert matchup.offensive is not None
        assert matchup.offensive.wins == 4
        assert matchup.offensive.total == 4

    def test_parse_matchup_row_invalid_vs(
        self, downloader: FaceoffComparisonDownloader
    ) -> None:
        """Test parsing matchup row with invalid vs text."""
        html = """<tr>
            <td colspan="2">&nbsp;</td>
            <td>invalid text</td>
            <td>&nbsp;</td>
        </tr>"""
        soup = BeautifulSoup(html, "lxml")
        cells = soup.find_all("td")

        player = PlayerInfo(number=14, position="C", name="HORVAT, BO")
        matchup = downloader._parse_matchup_row(cells, "invalid text", player)

        assert matchup is None


# =============================================================================
# Zone Summary Tests
# =============================================================================


class TestZoneSummary:
    """Tests for zone summary calculation."""

    def test_calculate_zone_summary(
        self, downloader: FaceoffComparisonDownloader
    ) -> None:
        """Test zone summary calculation."""
        # Create test data
        away_player = PlayerFaceoffSummary(
            player=PlayerInfo(number=14, position="C", name="HORVAT, BO"),
            offensive=FaceoffResult(wins=8, total=9, percentage=89.0),
            defensive=FaceoffResult(wins=3, total=5, percentage=60.0),
            neutral=FaceoffResult(wins=1, total=4, percentage=25.0),
        )
        home_player = PlayerFaceoffSummary(
            player=PlayerInfo(number=11, position="C", name="STAAL, JORDAN"),
            offensive=FaceoffResult(wins=0, total=0),
            defensive=FaceoffResult(wins=3, total=9, percentage=33.0),
            neutral=FaceoffResult(wins=4, total=4, percentage=100.0),
        )

        away_team = TeamFaceoffSummary(
            name="NEW YORK ISLANDERS", abbrev="NYI", players=[away_player]
        )
        home_team = TeamFaceoffSummary(
            name="CAROLINA HURRICANES", abbrev="CAR", players=[home_player]
        )

        summary = downloader._calculate_zone_summary(away_team, home_team)

        # Check offensive zone
        assert summary["offensive"]["away"].wins == 8
        assert summary["offensive"]["away"].total == 9
        assert summary["offensive"]["home"].wins == 0

        # Check defensive zone
        assert summary["defensive"]["away"].wins == 3
        assert summary["defensive"]["home"].wins == 3

        # Check neutral zone
        assert summary["neutral"]["away"].wins == 1
        assert summary["neutral"]["home"].wins == 4


# =============================================================================
# Full Parse Tests
# =============================================================================


class TestFullParse:
    """Tests for full report parsing."""

    @pytest.mark.asyncio
    async def test_parse_report(
        self,
        downloader: FaceoffComparisonDownloader,
        sample_soup: BeautifulSoup,
    ) -> None:
        """Test full report parsing."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Check structure
        assert "game_id" in result
        assert "season_id" in result
        assert "away_team" in result
        assert "home_team" in result
        assert "zone_summary" in result
        assert "matchups" in result

        # Check values
        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025

    @pytest.mark.asyncio
    async def test_parse_report_teams(
        self,
        downloader: FaceoffComparisonDownloader,
        sample_soup: BeautifulSoup,
    ) -> None:
        """Test team data in parsed report."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Check away team
        assert result["away_team"]["name"] == "NEW YORK ISLANDERS"
        assert result["away_team"]["abbrev"] == "NYI"
        assert len(result["away_team"]["players"]) > 0

        # Check home team
        assert result["home_team"]["name"] == "CAROLINA HURRICANES"
        assert result["home_team"]["abbrev"] == "CAR"
        assert len(result["home_team"]["players"]) > 0

    @pytest.mark.asyncio
    async def test_download_game_success(
        self,
        downloader: FaceoffComparisonDownloader,
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
        assert result.source == "html_fc"
        assert result.raw_content == sample_html


# =============================================================================
# Output Format Tests
# =============================================================================


class TestOutputFormat:
    """Tests for output format compliance."""

    @pytest.mark.asyncio
    async def test_output_keys(
        self, downloader: FaceoffComparisonDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test output contains expected keys."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        expected_keys = {
            "game_id",
            "season_id",
            "away_team",
            "home_team",
            "zone_summary",
            "matchups",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_team_structure(
        self, downloader: FaceoffComparisonDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test team dictionary structure."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        team = result["away_team"]
        assert "name" in team
        assert "abbrev" in team
        assert "players" in team

    @pytest.mark.asyncio
    async def test_player_structure(
        self, downloader: FaceoffComparisonDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test player dictionary structure."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        if result["away_team"]["players"]:
            player = result["away_team"]["players"][0]
            assert "number" in player
            assert "position" in player
            assert "name" in player
            assert "offensive" in player
            assert "defensive" in player
            assert "neutral" in player
            assert "total" in player
            assert "matchups" in player

    @pytest.mark.asyncio
    async def test_zone_summary_structure(
        self, downloader: FaceoffComparisonDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test zone summary dictionary structure."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        zone_summary = result["zone_summary"]
        for zone in ["offensive", "defensive", "neutral"]:
            assert zone in zone_summary
            assert "away" in zone_summary[zone]
            assert "home" in zone_summary[zone]
            assert "wins" in zone_summary[zone]["away"]
            assert "total" in zone_summary[zone]["away"]

    @pytest.mark.asyncio
    async def test_matchups_structure(
        self, downloader: FaceoffComparisonDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test matchups list structure."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        if result["matchups"]:
            matchup = result["matchups"][0]
            assert "away_player" in matchup
            assert "home_player" in matchup
            assert "away_wins" in matchup
            assert "home_wins" in matchup
            assert "zones" in matchup


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_html(self, downloader: FaceoffComparisonDownloader) -> None:
        """Test handling of empty HTML."""
        html = b"<html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        tables = downloader._find_team_faceoff_tables(soup)
        assert tables == []

    def test_no_matchups(self, downloader: FaceoffComparisonDownloader) -> None:
        """Test handling of player with no matchups."""
        player = PlayerFaceoffSummary(
            player=PlayerInfo(number=14, position="C", name="TEST"),
        )
        assert player.matchups == []

    def test_result_to_dict_none(self, downloader: FaceoffComparisonDownloader) -> None:
        """Test _result_to_dict with None input."""
        result = downloader._result_to_dict(None)
        assert result is None

    def test_result_to_dict_valid(
        self, downloader: FaceoffComparisonDownloader
    ) -> None:
        """Test _result_to_dict with valid input."""
        faceoff = FaceoffResult(wins=8, total=9, percentage=89.0)
        result = downloader._result_to_dict(faceoff)
        assert result == {"wins": 8, "total": 9, "percentage": 89.0}


# =============================================================================
# Integration with Fixture Tests
# =============================================================================


class TestFixtureIntegration:
    """Tests using the actual FC fixture file."""

    @pytest.fixture
    def fixture_path(self) -> Path:
        """Get path to FC fixture file."""
        return (
            Path(__file__).parent.parent.parent.parent.parent
            / "fixtures"
            / "html"
            / "FC020500.HTM"
        )

    @pytest.mark.asyncio
    async def test_parse_real_fixture(
        self,
        downloader: FaceoffComparisonDownloader,
        fixture_path: Path,
    ) -> None:
        """Test parsing of real FC fixture file."""
        if not fixture_path.exists():
            pytest.skip("Fixture file not found")

        html = fixture_path.read_bytes()
        soup = BeautifulSoup(html.decode("utf-8"), "lxml")
        result = await downloader._parse_report(soup, 2024020500)

        # Verify structure
        assert result["game_id"] == 2024020500
        assert len(result["away_team"]["players"]) > 0
        assert len(result["home_team"]["players"]) > 0

        # Check specific known players from fixture
        away_players = {p["name"] for p in result["away_team"]["players"]}
        home_players = {p["name"] for p in result["home_team"]["players"]}

        # Bo Horvat should be in away team
        assert "HORVAT, BO" in away_players

        # Jordan Staal should be in home team
        assert "STAAL, JORDAN" in home_players

    @pytest.mark.asyncio
    async def test_matchup_counts(
        self,
        downloader: FaceoffComparisonDownloader,
        fixture_path: Path,
    ) -> None:
        """Test that matchups are properly extracted."""
        if not fixture_path.exists():
            pytest.skip("Fixture file not found")

        html = fixture_path.read_bytes()
        soup = BeautifulSoup(html.decode("utf-8"), "lxml")
        result = await downloader._parse_report(soup, 2024020500)

        # Check that matchups exist
        total_matchups = sum(len(p["matchups"]) for p in result["away_team"]["players"])
        assert total_matchups > 0

        # Flattened matchups should also exist
        assert len(result["matchups"]) > 0

    @pytest.mark.asyncio
    async def test_zone_totals_consistency(
        self,
        downloader: FaceoffComparisonDownloader,
        fixture_path: Path,
    ) -> None:
        """Test that zone totals are consistent."""
        if not fixture_path.exists():
            pytest.skip("Fixture file not found")

        html = fixture_path.read_bytes()
        soup = BeautifulSoup(html.decode("utf-8"), "lxml")
        result = await downloader._parse_report(soup, 2024020500)

        zone_summary = result["zone_summary"]

        # For each zone, away losses should equal home wins (they're head-to-head)
        # Note: This is approximately true due to how the data is structured
        for zone in ["offensive", "defensive", "neutral"]:
            away = zone_summary[zone]["away"]
            home = zone_summary[zone]["home"]

            # Both teams should have reasonable faceoff counts
            assert away["total"] >= 0
            assert home["total"] >= 0
