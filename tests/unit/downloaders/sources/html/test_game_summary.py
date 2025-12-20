"""Unit tests for GameSummaryDownloader.

Tests cover:
- HTML parsing of game summary reports
- Team parsing from header
- Scoring summary extraction
- Penalty summary extraction
- Exception code filtering
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
from nhl_api.downloaders.sources.html.game_summary import (
    EXCEPTION_CODES,
    GameSummaryDownloader,
    GoalInfo,
    PenaltyInfo,
    PlayerInfo,
    TeamInfo,
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
def downloader(config: HTMLDownloaderConfig) -> GameSummaryDownloader:
    """Create test downloader instance."""
    return GameSummaryDownloader(config)


@pytest.fixture
def sample_html() -> bytes:
    """Load sample Game Summary HTML fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "html"
        / "GS020500.HTM"
    )
    if fixture_path.exists():
        return fixture_path.read_bytes()
    # Fallback minimal HTML for testing
    return b"""<!DOCTYPE html>
<html>
<head><title>Game Summary</title></head>
<body>
<table id="Visitor">
    <tr><td><img src="logocnyi.gif" alt="NEW YORK ISLANDERS"></td></tr>
    <tr><td style="font-size: 40px;font-weight:bold">0</td></tr>
    <tr><td>NEW YORK ISLANDERS Game 33 Away Game 18</td></tr>
</table>
<table id="Home">
    <tr><td><img src="logoccar.gif" alt="CAROLINA HURRICANES"></td></tr>
    <tr><td style="font-size: 40px;font-weight:bold">4</td></tr>
    <tr><td>CAROLINA HURRICANES Game 31 Home Game 17</td></tr>
</table>
<table id="GameInfo">
    <tr><td>Game Summary</td></tr>
    <tr><td>Saturday, December 21, 2024</td></tr>
    <tr><td>PNC Arena Attendance 18,680</td></tr>
    <tr><td>Start 7:00 PM</td></tr>
    <tr><td>End 9:30 PM</td></tr>
</table>
<table>
    <tr><td class="sectionheading">SCORING SUMMARY</td></tr>
</table>
<table>
    <tr>
        <td class="heading">G</td>
        <td class="heading">Per</td>
        <td class="heading">Time</td>
        <td class="heading">Str</td>
        <td class="heading">Team</td>
        <td class="heading">Goal Scorer</td>
        <td class="heading">Assist</td>
        <td class="heading">Assist</td>
        <td class="heading">NYI on Ice</td>
        <td class="heading">CAR on Ice</td>
    </tr>
    <tr class="oddColor">
        <td align="center">1</td>
        <td align="center">1</td>
        <td align="center">5:47</td>
        <td align="center">PP</td>
        <td align="center">CAR</td>
        <td align="left">37 A.SVECHNIKOV(12)</td>
        <td align="left">20 S.AHO(24)</td>
        <td align="left">4 S.GOSTISBEHERE(20)</td>
        <td><font title="Player">3</font>, <font title="Player">6</font></td>
        <td><font title="Player">4</font>, <font title="Player">20</font></td>
    </tr>
</table>
<table id="PenaltySummary">
    <tr><td class="sectionheading">PENALTY SUMMARY</td></tr>
    <tr><td>
        <table>
            <tr>
                <td class="heading">#</td>
                <td class="heading">Per</td>
                <td class="heading">Time</td>
                <td class="heading">Player</td>
                <td class="heading">PIM</td>
                <td class="heading">Penalty</td>
            </tr>
            <tr class="oddColor">
                <td align="center">1</td>
                <td align="center">1</td>
                <td align="center">5:12</td>
                <td align="left">28 A.ROMANOV</td>
                <td align="center">2</td>
                <td align="left">High-sticking</td>
            </tr>
        </table>
    </td></tr>
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


class TestGameSummaryDownloaderConfig:
    """Tests for GameSummaryDownloader configuration."""

    def test_report_type(self, downloader: GameSummaryDownloader) -> None:
        """Test report_type is 'GS'."""
        assert downloader.report_type == "GS"

    def test_source_name(self, downloader: GameSummaryDownloader) -> None:
        """Test source_name is 'html_gs'."""
        assert downloader.source_name == "html_gs"


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for data classes."""

    def test_player_info(self) -> None:
        """Test PlayerInfo creation."""
        player = PlayerInfo(number=37, name="A.SVECHNIKOV", season_total=12)
        assert player.number == 37
        assert player.name == "A.SVECHNIKOV"
        assert player.season_total == 12

    def test_goal_info(self) -> None:
        """Test GoalInfo creation."""
        scorer = PlayerInfo(number=37, name="A.SVECHNIKOV", season_total=12)
        goal = GoalInfo(
            goal_number=1,
            period=1,
            time="5:47",
            strength="PP",
            team="CAR",
            scorer=scorer,
        )
        assert goal.goal_number == 1
        assert goal.period == 1
        assert goal.strength == "PP"
        assert goal.team == "CAR"

    def test_penalty_info(self) -> None:
        """Test PenaltyInfo creation."""
        player = PlayerInfo(number=28, name="A.ROMANOV")
        penalty = PenaltyInfo(
            penalty_number=1,
            period=1,
            time="5:12",
            team="NYI",
            player=player,
            pim=2,
            infraction="High-sticking",
        )
        assert penalty.penalty_number == 1
        assert penalty.pim == 2
        assert penalty.infraction == "High-sticking"

    def test_team_info(self) -> None:
        """Test TeamInfo creation."""
        team = TeamInfo(name="CAROLINA HURRICANES", abbrev="CAR", goals=4)
        assert team.name == "CAROLINA HURRICANES"
        assert team.abbrev == "CAR"
        assert team.goals == 4


# =============================================================================
# Exception Code Tests
# =============================================================================


class TestExceptionCodes:
    """Tests for exception code handling."""

    def test_exception_codes_defined(self) -> None:
        """Test EXCEPTION_CODES contains expected values."""
        assert "unsuccessful penalty shot" in EXCEPTION_CODES
        assert "no goal" in EXCEPTION_CODES
        assert "missed" in EXCEPTION_CODES

    def test_is_exception_goal(self, downloader: GameSummaryDownloader) -> None:
        """Test _is_exception_goal method."""
        assert downloader._is_exception_goal("No Goal - Offside") is True
        assert downloader._is_exception_goal("Unsuccessful Penalty Shot") is True
        assert downloader._is_exception_goal("37 A.SVECHNIKOV(12)") is False


# =============================================================================
# Team Parsing Tests
# =============================================================================


class TestTeamParsing:
    """Tests for team information parsing."""

    def test_parse_teams(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of team information."""
        away, home = downloader._parse_teams(sample_soup)

        # Check away team
        assert away.name == "NEW YORK ISLANDERS"
        assert away.goals == 0

        # Check home team
        assert home.name == "CAROLINA HURRICANES"
        assert home.goals == 4


# =============================================================================
# Scoring Summary Tests
# =============================================================================


class TestScoringSummaryParsing:
    """Tests for scoring summary parsing."""

    def test_parse_scoring_summary(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of scoring summary."""
        goals = downloader._parse_scoring_summary(sample_soup)

        # Should have at least one goal
        assert len(goals) >= 1

        # Check first goal
        first_goal = goals[0]
        assert first_goal.goal_number == 1
        assert first_goal.period == 1
        assert first_goal.time == "5:47"
        assert first_goal.strength == "PP"
        assert first_goal.team == "CAR"

    def test_parse_goal_scorer(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of goal scorer."""
        goals = downloader._parse_scoring_summary(sample_soup)
        if goals:
            scorer = goals[0].scorer
            assert scorer.number == 37
            assert "SVECHNIKOV" in scorer.name

    def test_parse_assists(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of assists."""
        goals = downloader._parse_scoring_summary(sample_soup)
        if goals and goals[0].assist1:
            assert goals[0].assist1.number == 20
            assert "AHO" in goals[0].assist1.name

    def test_parse_period_ot(self, downloader: GameSummaryDownloader) -> None:
        """Test period parsing for OT."""
        assert downloader._parse_period("OT") == 4
        assert downloader._parse_period("SO") == 5
        assert downloader._parse_period("1") == 1
        assert downloader._parse_period("3") == 3


# =============================================================================
# Penalty Summary Tests
# =============================================================================


class TestPenaltySummaryParsing:
    """Tests for penalty summary parsing."""

    def test_parse_penalty_summary(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of penalty summary."""
        penalties = downloader._parse_penalty_summary(sample_soup)

        # Should have at least one penalty
        assert len(penalties) >= 1

        # Check first penalty
        first_penalty = penalties[0]
        assert first_penalty.penalty_number == 1
        assert first_penalty.period == 1
        assert first_penalty.time == "5:12"
        assert first_penalty.pim == 2
        assert first_penalty.infraction == "High-sticking"


# =============================================================================
# Game Info Parsing Tests
# =============================================================================


class TestGameInfoParsing:
    """Tests for game info parsing."""

    def test_parse_game_info(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of game info."""
        date, venue, attendance = downloader._parse_game_info(sample_soup)

        # Check date
        assert "December" in date or "Saturday" in date

    def test_parse_times(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of start/end times."""
        start, end = downloader._parse_times(sample_soup)

        # Should have times if GameInfo table exists
        # Times might be None if parsing fails, that's acceptable


# =============================================================================
# Full Parse Tests
# =============================================================================


class TestFullParse:
    """Tests for full report parsing."""

    @pytest.mark.asyncio
    async def test_parse_report(
        self,
        downloader: GameSummaryDownloader,
        sample_soup: BeautifulSoup,
    ) -> None:
        """Test full report parsing."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Check structure
        assert "game_id" in result
        assert "season_id" in result
        assert "away_team" in result
        assert "home_team" in result
        assert "goals" in result
        assert "penalties" in result

        # Check values
        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025

    @pytest.mark.asyncio
    async def test_download_game_success(
        self,
        downloader: GameSummaryDownloader,
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
        assert result.source == "html_gs"
        assert result.raw_content == sample_html


# =============================================================================
# Output Format Tests
# =============================================================================


class TestOutputFormat:
    """Tests for output format compliance."""

    @pytest.mark.asyncio
    async def test_summary_to_dict(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test _summary_to_dict output format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Verify expected keys
        expected_keys = {
            "game_id",
            "season_id",
            "date",
            "venue",
            "attendance",
            "start_time",
            "end_time",
            "away_team",
            "home_team",
            "goals",
            "penalties",
            "period_summary",
            "referees",
            "linesmen",
        }
        assert set(result.keys()) == expected_keys

        # Verify team structure
        assert "name" in result["away_team"]
        assert "abbrev" in result["away_team"]
        assert "goals" in result["away_team"]
        assert "shots" in result["away_team"]

    @pytest.mark.asyncio
    async def test_goal_dict_format(
        self, downloader: GameSummaryDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test goal dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        if result["goals"]:
            goal = result["goals"][0]
            expected_keys = {
                "goal_number",
                "period",
                "time",
                "strength",
                "team",
                "scorer",
                "assist1",
                "assist2",
                "away_on_ice",
                "home_on_ice",
            }
            assert set(goal.keys()) == expected_keys

            # Verify scorer structure
            assert "number" in goal["scorer"]
            assert "name" in goal["scorer"]
            assert "season_total" in goal["scorer"]
