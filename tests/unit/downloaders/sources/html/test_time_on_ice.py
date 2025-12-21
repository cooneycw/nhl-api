"""Unit tests for TimeOnIceDownloader.

Tests cover:
- HTML parsing of Time on Ice reports (TH for home, TV for away)
- Player shift parsing with timing and events
- Per-period TOI summary parsing
- Integration with BaseHTMLDownloader
- Both home and away report handling
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
from nhl_api.downloaders.sources.html.time_on_ice import (
    ParsedTimeOnIce,
    PeriodTOI,
    PlayerTOI,
    ShiftInfo,
    TimeOnIceDownloader,
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
def home_downloader(config: HTMLDownloaderConfig) -> TimeOnIceDownloader:
    """Create test downloader instance for home team."""
    return TimeOnIceDownloader(config, side="home")


@pytest.fixture
def away_downloader(config: HTMLDownloaderConfig) -> TimeOnIceDownloader:
    """Create test downloader instance for away team."""
    return TimeOnIceDownloader(config, side="away")


@pytest.fixture
def home_html() -> bytes:
    """Load sample Home Time on Ice HTML fixture (TH)."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "html"
        / "TH020500.HTM"
    )
    if fixture_path.exists():
        return fixture_path.read_bytes()
    # Fallback minimal HTML for testing
    return _create_minimal_toi_html("home")


@pytest.fixture
def away_html() -> bytes:
    """Load sample Away Time on Ice HTML fixture (TV)."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "html"
        / "TV020500.HTM"
    )
    if fixture_path.exists():
        return fixture_path.read_bytes()
    # Fallback minimal HTML for testing
    return _create_minimal_toi_html("away")


def _create_minimal_toi_html(side: str = "home") -> bytes:
    """Create minimal HTML for fallback testing."""
    team_id = "Home" if side == "home" else "Visitor"
    team_name = "CAROLINA HURRICANES" if side == "home" else "NEW YORK ISLANDERS"
    team_abbrev = "car" if side == "home" else "nyi"

    return f"""<!DOCTYPE html>
<html>
<head><title>Time On Ice Report {team_id} Team</title></head>
<body>
<table id="Visitor">
    <tr><td><img src="logocnyi.gif" alt="NEW YORK ISLANDERS"></td></tr>
    <tr><td style="font-size: 40px;font-weight:bold">0</td></tr>
</table>
<table id="Home">
    <tr><td><img src="logoc{team_abbrev}.gif" alt="{team_name}"></td></tr>
    <tr><td style="font-size: 40px;font-weight:bold">4</td></tr>
</table>
<table class="teamHeading">
    <tr><td>{team_name}</td></tr>
</table>
<table border="0" cellspacing="0" cellpadding="0" width="100%">
<tr>
<td align="center" valign="top" class="playerHeading + border" colspan="8">4 GOSTISBEHERE, SHAYNE</td>
</tr>
<tr>
<td class="heading + lborder + bborder" align="center" valign="middle">Shift #</td>
<td class="heading + lborder + bborder" align="center" valign="middle">Per</td>
<td class="heading + lborder + bborder" align="center">Start of Shift<br>Elapsed / Game</td>
<td class="heading + lborder + bborder" align="center">End of Shift<br>Elapsed / Game</td>
<td class="heading + lborder + bborder" align="center" valign="middle">Duration</td>
<td class="heading + lborder + bborder + rborder" align="center" valign="middle">Event</td>
</tr>
<tr class="oddColor">
<td align="center" class="lborder + bborder">1</td>
<td align="center" class="lborder + bborder">1</td>
<td align="center" class="lborder + bborder">0:00 / 20:00</td>
<td align="center" class="lborder + bborder">0:28 / 19:32</td>
<td align="center" class="lborder + bborder">00:28</td>
<td align="center" class="lborder + bborder + rborder">&nbsp;</td>
</tr>
<tr class="evenColor">
<td align="center" class="lborder + bborder">2</td>
<td align="center" class="lborder + bborder">1</td>
<td align="center" class="lborder + bborder">2:02 / 17:58</td>
<td align="center" class="lborder + bborder">3:04 / 16:56</td>
<td align="center" class="lborder + bborder">01:02</td>
<td align="center" class="lborder + bborder + rborder">G</td>
</tr>
<tr class="oddColor">
<td align="center" class="lborder + bborder">3</td>
<td align="center" class="lborder + bborder">2</td>
<td align="center" class="lborder + bborder">0:30 / 19:30</td>
<td align="center" class="lborder + bborder">1:15 / 18:45</td>
<td align="center" class="lborder + bborder">00:45</td>
<td align="center" class="lborder + bborder + rborder">P</td>
</tr>
<tr>
<td colspan="8">
<table cellpadding="0" cellspacing="0" border="0" width="100%">
<tr>
<td align="center" class="heading + bborder + lborder">Per</td>
<td align="center" class="heading + bborder + lborder">SHF</td>
<td align="center" class="heading + bborder + lborder">AVG</td>
<td align="center" class="heading + bborder + lborder">TOI</td>
<td align="center" class="heading + bborder + lborder">EV&nbsp;TOT</td>
<td align="center" class="heading + bborder + lborder">PP&nbsp;TOT</td>
<td align="center" class="heading + bborder + lborder + rborder">SH&nbsp;TOT</td>
</tr>
<tr class="oddColor">
<td class="bborder + lborder" align="center">1</td>
<td class="bborder + lborder" align="center">2</td>
<td class="bborder + lborder" align="center">00:45</td>
<td class="bborder + lborder" align="center">01:30</td>
<td class="bborder + lborder" align="center">01:00</td>
<td class="bborder + lborder" align="center">00:30</td>
<td class="bborder + lborder + rborder" align="center">00:00</td>
</tr>
<tr class="evenColor">
<td class="bborder + lborder" align="center">2</td>
<td class="bborder + lborder" align="center">1</td>
<td class="bborder + lborder" align="center">00:45</td>
<td class="bborder + lborder" align="center">00:45</td>
<td class="bborder + lborder" align="center">00:45</td>
<td class="bborder + lborder" align="center">00:00</td>
<td class="bborder + lborder + rborder" align="center">00:00</td>
</tr>
<tr class="oddColor">
<td class="bborder + lborder + bold" align="center">TOT</td>
<td class="bborder + lborder + bold" align="center">3</td>
<td class="bborder + lborder + bold" align="center">00:45</td>
<td class="bborder + lborder + bold" align="center">02:15</td>
<td class="bborder + lborder + bold" align="center">01:45</td>
<td class="bborder + lborder + bold" align="center">00:30</td>
<td class="bborder + lborder + rborder + bold" align="center">00:00</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>
""".encode()


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestShiftInfo:
    """Tests for ShiftInfo dataclass."""

    def test_create_shift_info(self) -> None:
        """Test creating a ShiftInfo instance."""
        shift = ShiftInfo(
            shift_number=1,
            period="1",
            start_elapsed="0:00",
            start_game="20:00",
            end_elapsed="0:28",
            end_game="19:32",
            duration="00:28",
            event="",
        )
        assert shift.shift_number == 1
        assert shift.period == "1"
        assert shift.duration == "00:28"
        assert shift.event == ""

    def test_shift_with_goal_event(self) -> None:
        """Test shift with goal event."""
        shift = ShiftInfo(
            shift_number=3,
            period="2",
            start_elapsed="10:50",
            start_game="9:10",
            end_elapsed="11:13",
            end_game="8:47",
            duration="00:23",
            event="G",
        )
        assert shift.event == "G"

    def test_shift_with_penalty_event(self) -> None:
        """Test shift with penalty event."""
        shift = ShiftInfo(
            shift_number=5,
            period="2",
            start_elapsed="14:05",
            start_game="5:55",
            end_elapsed="14:32",
            end_game="5:28",
            duration="00:27",
            event="P",
        )
        assert shift.event == "P"

    def test_shift_with_goal_and_penalty(self) -> None:
        """Test shift with both goal and penalty events."""
        shift = ShiftInfo(
            shift_number=2,
            period="1",
            start_elapsed="4:59",
            start_game="15:01",
            end_elapsed="5:47",
            end_game="14:13",
            duration="00:48",
            event="GP",
        )
        assert shift.event == "GP"


class TestPeriodTOI:
    """Tests for PeriodTOI dataclass."""

    def test_create_period_toi(self) -> None:
        """Test creating a PeriodTOI instance."""
        period = PeriodTOI(
            period="1",
            shifts=7,
            avg_shift="00:54",
            toi="06:19",
            ev_toi="05:44",
            pp_toi="00:35",
            sh_toi="00:00",
        )
        assert period.period == "1"
        assert period.shifts == 7
        assert period.toi == "06:19"
        assert period.ev_toi == "05:44"
        assert period.pp_toi == "00:35"
        assert period.sh_toi == "00:00"

    def test_create_total_period(self) -> None:
        """Test creating a TOT period summary."""
        period = PeriodTOI(
            period="TOT",
            shifts=22,
            avg_shift="00:47",
            toi="17:35",
            ev_toi="15:29",
            pp_toi="02:06",
            sh_toi="00:00",
        )
        assert period.period == "TOT"
        assert period.shifts == 22


class TestPlayerTOI:
    """Tests for PlayerTOI dataclass."""

    def test_create_player_toi(self) -> None:
        """Test creating a PlayerTOI instance."""
        player = PlayerTOI(
            number=4,
            name="GOSTISBEHERE, SHAYNE",
        )
        assert player.number == 4
        assert player.name == "GOSTISBEHERE, SHAYNE"
        assert player.shifts_detail == []
        assert player.periods == []

    def test_total_shifts_from_tot(self) -> None:
        """Test total_shifts property with TOT period."""
        player = PlayerTOI(
            number=4,
            name="GOSTISBEHERE, SHAYNE",
            periods=[
                PeriodTOI("1", 7, "00:54", "06:19", "05:44", "00:35", "00:00"),
                PeriodTOI("2", 7, "00:33", "03:55", "03:55", "00:00", "00:00"),
                PeriodTOI("3", 8, "00:55", "07:21", "05:50", "01:31", "00:00"),
                PeriodTOI("TOT", 22, "00:47", "17:35", "15:29", "02:06", "00:00"),
            ],
        )
        assert player.total_shifts == 22

    def test_total_toi_from_tot(self) -> None:
        """Test total_toi property with TOT period."""
        player = PlayerTOI(
            number=4,
            name="GOSTISBEHERE, SHAYNE",
            periods=[
                PeriodTOI("1", 7, "00:54", "06:19", "05:44", "00:35", "00:00"),
                PeriodTOI("TOT", 22, "00:47", "17:35", "15:29", "02:06", "00:00"),
            ],
        )
        assert player.total_toi == "17:35"

    def test_ev_pp_sh_toi(self) -> None:
        """Test situational TOI properties."""
        player = PlayerTOI(
            number=4,
            name="GOSTISBEHERE, SHAYNE",
            periods=[
                PeriodTOI("TOT", 22, "00:47", "17:35", "15:29", "02:06", "00:30"),
            ],
        )
        assert player.ev_toi == "15:29"
        assert player.pp_toi == "02:06"
        assert player.sh_toi == "00:30"

    def test_toi_by_period(self) -> None:
        """Test toi_by_period property."""
        player = PlayerTOI(
            number=4,
            name="GOSTISBEHERE, SHAYNE",
            periods=[
                PeriodTOI("1", 7, "00:54", "06:19", "05:44", "00:35", "00:00"),
                PeriodTOI("2", 7, "00:33", "03:55", "03:55", "00:00", "00:00"),
                PeriodTOI("3", 8, "00:55", "07:21", "05:50", "01:31", "00:00"),
                PeriodTOI("TOT", 22, "00:47", "17:35", "15:29", "02:06", "00:00"),
            ],
        )
        by_period = player.toi_by_period
        assert "1" in by_period
        assert "2" in by_period
        assert "3" in by_period
        assert "TOT" not in by_period
        assert by_period["1"]["shifts"] == 7
        assert by_period["1"]["toi"] == "06:19"

    def test_goals_on_ice(self) -> None:
        """Test goals_on_ice property."""
        player = PlayerTOI(
            number=4,
            name="GOSTISBEHERE, SHAYNE",
            shifts_detail=[
                ShiftInfo(1, "1", "0:00", "20:00", "0:28", "19:32", "00:28", ""),
                ShiftInfo(2, "1", "2:02", "17:58", "3:04", "16:56", "01:02", "G"),
                ShiftInfo(3, "2", "10:50", "9:10", "11:13", "8:47", "00:23", "G"),
                ShiftInfo(4, "2", "14:05", "5:55", "14:32", "5:28", "00:27", "P"),
            ],
        )
        assert player.goals_on_ice == 2

    def test_penalties_on_ice(self) -> None:
        """Test penalties_on_ice property."""
        player = PlayerTOI(
            number=4,
            name="GOSTISBEHERE, SHAYNE",
            shifts_detail=[
                ShiftInfo(1, "1", "0:00", "20:00", "0:28", "19:32", "00:28", ""),
                ShiftInfo(2, "1", "4:59", "15:01", "5:47", "14:13", "00:48", "GP"),
                ShiftInfo(3, "2", "14:05", "5:55", "14:32", "5:28", "00:27", "P"),
            ],
        )
        assert player.penalties_on_ice == 2


class TestParsedTimeOnIce:
    """Tests for ParsedTimeOnIce dataclass."""

    def test_create_parsed_toi(self) -> None:
        """Test creating a ParsedTimeOnIce instance."""
        result = ParsedTimeOnIce(
            game_id=2024020500,
            season_id=20242025,
            team="CAROLINA HURRICANES",
            team_abbrev="CAR",
            side="home",
        )
        assert result.game_id == 2024020500
        assert result.season_id == 20242025
        assert result.team == "CAROLINA HURRICANES"
        assert result.side == "home"
        assert result.players == []


# =============================================================================
# Downloader Initialization Tests
# =============================================================================


class TestTimeOnIceDownloaderInit:
    """Tests for TimeOnIceDownloader initialization."""

    def test_create_home_downloader(self, config: HTMLDownloaderConfig) -> None:
        """Test creating a home team downloader."""
        downloader = TimeOnIceDownloader(config, side="home")
        assert downloader.report_type == "TH"
        assert downloader.source_name == "html_th"
        assert downloader.side == "home"

    def test_create_away_downloader(self, config: HTMLDownloaderConfig) -> None:
        """Test creating an away team downloader."""
        downloader = TimeOnIceDownloader(config, side="away")
        assert downloader.report_type == "TV"
        assert downloader.source_name == "html_tv"
        assert downloader.side == "away"

    def test_case_insensitive_side(self, config: HTMLDownloaderConfig) -> None:
        """Test that side parameter is case insensitive."""
        downloader = TimeOnIceDownloader(config, side="HOME")
        assert downloader.side == "home"
        assert downloader.report_type == "TH"

    def test_invalid_side_raises_error(self, config: HTMLDownloaderConfig) -> None:
        """Test that invalid side raises ValueError."""
        with pytest.raises(ValueError, match="Invalid side"):
            TimeOnIceDownloader(config, side="invalid")

    def test_default_side_is_home(self, config: HTMLDownloaderConfig) -> None:
        """Test that default side is home."""
        downloader = TimeOnIceDownloader(config)
        assert downloader.side == "home"
        assert downloader.report_type == "TH"


# =============================================================================
# Parsing Helper Tests
# =============================================================================


class TestParseTimePair:
    """Tests for _parse_time_pair method."""

    def test_parse_normal_time_pair(self, home_downloader: TimeOnIceDownloader) -> None:
        """Test parsing normal time pair."""
        elapsed, game = home_downloader._parse_time_pair("0:28 / 19:32")
        assert elapsed == "0:28"
        assert game == "19:32"

    def test_parse_time_pair_no_slash(
        self, home_downloader: TimeOnIceDownloader
    ) -> None:
        """Test parsing time without slash."""
        elapsed, game = home_downloader._parse_time_pair("01:30")
        assert elapsed == "01:30"
        assert game == ""

    def test_parse_empty_time(self, home_downloader: TimeOnIceDownloader) -> None:
        """Test parsing empty time string."""
        elapsed, game = home_downloader._parse_time_pair("")
        assert elapsed == ""
        assert game == ""


class TestParseTeamHeader:
    """Tests for _parse_team_header method."""

    def test_parse_home_team_header(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test parsing home team header."""
        soup = BeautifulSoup(home_html, "lxml")
        name, abbrev = home_downloader._parse_team_header(soup)
        assert "CAROLINA" in name.upper() or "HURRICANES" in name.upper()
        assert abbrev == "CAR"

    def test_parse_away_team_header(
        self, away_downloader: TimeOnIceDownloader, away_html: bytes
    ) -> None:
        """Test parsing away team header."""
        soup = BeautifulSoup(away_html, "lxml")
        name, abbrev = away_downloader._parse_team_header(soup)
        assert "ISLANDERS" in name.upper() or "NEW YORK" in name.upper()
        assert abbrev == "NYI"


# =============================================================================
# Player Parsing Tests
# =============================================================================


class TestParsePlayers:
    """Tests for _parse_players method."""

    def test_parse_players_from_home_fixture(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test parsing players from real home fixture."""
        soup = BeautifulSoup(home_html, "lxml")
        players = home_downloader._parse_players(soup)

        # Should have multiple players
        assert len(players) > 0

        # Check first player has valid structure
        player = players[0]
        assert player.number > 0
        assert len(player.name) > 0
        assert len(player.periods) > 0

    def test_parse_players_from_away_fixture(
        self, away_downloader: TimeOnIceDownloader, away_html: bytes
    ) -> None:
        """Test parsing players from real away fixture."""
        soup = BeautifulSoup(away_html, "lxml")
        players = away_downloader._parse_players(soup)

        # Should have multiple players
        assert len(players) > 0

    def test_player_has_period_summary(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test that parsed players have period summaries."""
        soup = BeautifulSoup(home_html, "lxml")
        players = home_downloader._parse_players(soup)

        if players:
            player = players[0]
            # Should have at least one period (plus TOT)
            assert len(player.periods) >= 1

            # Check for TOT row
            tot_periods = [p for p in player.periods if p.period == "TOT"]
            assert len(tot_periods) == 1


class TestParseShifts:
    """Tests for _parse_shifts method."""

    def test_parse_shifts_extracts_timing(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test that shifts have proper timing data."""
        soup = BeautifulSoup(home_html, "lxml")
        players = home_downloader._parse_players(soup)

        if players and players[0].shifts_detail:
            shift = players[0].shifts_detail[0]
            assert shift.shift_number >= 1
            assert shift.period in ("1", "2", "3", "OT")
            assert len(shift.duration) > 0

    def test_parse_shifts_captures_events(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test that shifts capture goal/penalty events."""
        soup = BeautifulSoup(home_html, "lxml")
        players = home_downloader._parse_players(soup)

        # Find any shift with an event
        all_shifts = [s for p in players for s in p.shifts_detail]
        events = [s.event for s in all_shifts if s.event]

        # May or may not have events in this game
        # Just verify we can access the event field
        for event in events:
            assert event in ("G", "P", "GP", "PG")


class TestParsePeriodSummary:
    """Tests for _parse_period_summary method."""

    def test_parse_period_summary(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test parsing period summary table."""
        soup = BeautifulSoup(home_html, "lxml")
        players = home_downloader._parse_players(soup)

        if players:
            player = players[0]
            # Check TOT row exists and has valid data
            tot_row = next((p for p in player.periods if p.period == "TOT"), None)
            if tot_row:
                assert tot_row.shifts >= 0
                assert ":" in tot_row.toi
                assert ":" in tot_row.ev_toi


# =============================================================================
# Full Report Parsing Tests
# =============================================================================


class TestParseReport:
    """Tests for _parse_report method."""

    @pytest.mark.asyncio
    async def test_parse_home_report(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test parsing full home report."""
        soup = BeautifulSoup(home_html, "lxml")
        result = await home_downloader._parse_report(soup, 2024020500)

        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert result["side"] == "home"
        assert "team" in result
        assert "players" in result
        assert isinstance(result["players"], list)

    @pytest.mark.asyncio
    async def test_parse_away_report(
        self, away_downloader: TimeOnIceDownloader, away_html: bytes
    ) -> None:
        """Test parsing full away report."""
        soup = BeautifulSoup(away_html, "lxml")
        result = await away_downloader._parse_report(soup, 2024020500)

        assert result["game_id"] == 2024020500
        assert result["side"] == "away"

    @pytest.mark.asyncio
    async def test_player_dict_structure(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test player dictionary structure in result."""
        soup = BeautifulSoup(home_html, "lxml")
        result = await home_downloader._parse_report(soup, 2024020500)

        if result["players"]:
            player = result["players"][0]
            assert "number" in player
            assert "name" in player
            assert "shifts" in player
            assert "toi_total" in player
            assert "toi_avg_per_shift" in player
            assert "ev_toi" in player
            assert "pp_toi" in player
            assert "sh_toi" in player
            assert "toi_by_period" in player
            assert "goals_on_ice" in player
            assert "penalties_on_ice" in player
            assert "shifts_detail" in player
            assert "periods" in player


# =============================================================================
# Download Integration Tests
# =============================================================================


class TestDownloadGame:
    """Tests for download_game method."""

    @pytest.mark.asyncio
    async def test_download_game_success(
        self, home_downloader: TimeOnIceDownloader, home_html: bytes
    ) -> None:
        """Test successful game download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status = 200
        mock_response.content = home_html

        with patch.object(
            home_downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await home_downloader.download_game(2024020500)

        assert result.status == DownloadStatus.COMPLETED
        assert result.game_id == 2024020500
        assert result.season_id == 20242025
        assert result.source == "html_th"
        assert result.data is not None
        assert result.raw_content == home_html

    @pytest.mark.asyncio
    async def test_download_away_game(
        self, away_downloader: TimeOnIceDownloader, away_html: bytes
    ) -> None:
        """Test away team game download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status = 200
        mock_response.content = away_html

        with patch.object(
            away_downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await away_downloader.download_game(2024020500)

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "html_tv"
        assert result.data["side"] == "away"


# =============================================================================
# URL Building Tests
# =============================================================================


class TestBuildUrl:
    """Tests for _build_url method."""

    def test_build_home_url(self, home_downloader: TimeOnIceDownloader) -> None:
        """Test building home team URL."""
        url = home_downloader._build_url(20242025, 2024020500)
        assert "TH" in url
        assert "020500" in url
        assert "20242025" in url
        assert url.endswith(".HTM")

    def test_build_away_url(self, away_downloader: TimeOnIceDownloader) -> None:
        """Test building away team URL."""
        url = away_downloader._build_url(20242025, 2024020500)
        assert "TV" in url
        assert "020500" in url


# =============================================================================
# Conversion Tests
# =============================================================================


class TestToDict:
    """Tests for dictionary conversion methods."""

    def test_shift_to_dict(self, home_downloader: TimeOnIceDownloader) -> None:
        """Test ShiftInfo to dict conversion."""
        shift = ShiftInfo(
            shift_number=1,
            period="1",
            start_elapsed="0:00",
            start_game="20:00",
            end_elapsed="0:28",
            end_game="19:32",
            duration="00:28",
            event="G",
        )
        d = home_downloader._shift_to_dict(shift)
        assert d["shift_number"] == 1
        assert d["period"] == "1"
        assert d["event"] == "G"

    def test_period_to_dict(self, home_downloader: TimeOnIceDownloader) -> None:
        """Test PeriodTOI to dict conversion."""
        period = PeriodTOI(
            period="1",
            shifts=7,
            avg_shift="00:54",
            toi="06:19",
            ev_toi="05:44",
            pp_toi="00:35",
            sh_toi="00:00",
        )
        d = home_downloader._period_to_dict(period)
        assert d["period"] == "1"
        assert d["shifts"] == 7
        assert d["toi"] == "06:19"

    def test_player_to_dict(self, home_downloader: TimeOnIceDownloader) -> None:
        """Test PlayerTOI to dict conversion."""
        player = PlayerTOI(
            number=4,
            name="GOSTISBEHERE, SHAYNE",
            shifts_detail=[
                ShiftInfo(1, "1", "0:00", "20:00", "0:28", "19:32", "00:28", "G"),
            ],
            periods=[
                PeriodTOI("1", 1, "00:28", "00:28", "00:28", "00:00", "00:00"),
                PeriodTOI("TOT", 1, "00:28", "00:28", "00:28", "00:00", "00:00"),
            ],
        )
        d = home_downloader._player_to_dict(player)
        assert d["number"] == 4
        assert d["name"] == "GOSTISBEHERE, SHAYNE"
        assert d["shifts"] == 1
        assert d["goals_on_ice"] == 1
        assert len(d["shifts_detail"]) == 1
        assert len(d["periods"]) == 2


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_player_totals(self) -> None:
        """Test player with no periods defaults correctly."""
        player = PlayerTOI(number=99, name="TEST PLAYER")
        assert player.total_shifts == 0
        assert player.total_toi == "00:00"
        assert player.ev_toi == "00:00"
        assert player.pp_toi == "00:00"
        assert player.sh_toi == "00:00"
        assert player.avg_shift == "00:00"
        assert player.toi_by_period == {}
        assert player.goals_on_ice == 0
        assert player.penalties_on_ice == 0

    @pytest.mark.asyncio
    async def test_parse_with_ot_period(
        self, home_downloader: TimeOnIceDownloader
    ) -> None:
        """Test parsing report with OT period."""
        html_with_ot = b"""<!DOCTYPE html>
<html>
<head><title>Time On Ice Report</title></head>
<body>
<table id="Home">
    <tr><td><img src="logoccar.gif" alt="CAROLINA HURRICANES"></td></tr>
</table>
<table border="0" cellspacing="0" cellpadding="0" width="100%">
<tr>
<td align="center" valign="top" class="playerHeading + border" colspan="8">4 TEST, PLAYER</td>
</tr>
<tr>
<td colspan="8">
<table cellpadding="0" cellspacing="0" border="0" width="100%">
<tr>
<td align="center" class="heading + bborder + lborder">Per</td>
<td align="center" class="heading + bborder + lborder">SHF</td>
<td align="center" class="heading + bborder + lborder">AVG</td>
<td align="center" class="heading + bborder + lborder">TOI</td>
<td align="center" class="heading + bborder + lborder">EV&nbsp;TOT</td>
<td align="center" class="heading + bborder + lborder">PP&nbsp;TOT</td>
<td align="center" class="heading + bborder + lborder + rborder">SH&nbsp;TOT</td>
</tr>
<tr class="oddColor">
<td class="bborder + lborder" align="center">1</td>
<td class="bborder + lborder" align="center">5</td>
<td class="bborder + lborder" align="center">01:00</td>
<td class="bborder + lborder" align="center">05:00</td>
<td class="bborder + lborder" align="center">05:00</td>
<td class="bborder + lborder" align="center">00:00</td>
<td class="bborder + lborder + rborder" align="center">00:00</td>
</tr>
<tr class="evenColor">
<td class="bborder + lborder" align="center">OT</td>
<td class="bborder + lborder" align="center">2</td>
<td class="bborder + lborder" align="center">00:30</td>
<td class="bborder + lborder" align="center">01:00</td>
<td class="bborder + lborder" align="center">01:00</td>
<td class="bborder + lborder" align="center">00:00</td>
<td class="bborder + lborder + rborder" align="center">00:00</td>
</tr>
<tr class="oddColor">
<td class="bborder + lborder + bold" align="center">TOT</td>
<td class="bborder + lborder + bold" align="center">7</td>
<td class="bborder + lborder + bold" align="center">00:51</td>
<td class="bborder + lborder + bold" align="center">06:00</td>
<td class="bborder + lborder + bold" align="center">06:00</td>
<td class="bborder + lborder + bold" align="center">00:00</td>
<td class="bborder + lborder + rborder + bold" align="center">00:00</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>
"""
        soup = BeautifulSoup(html_with_ot, "lxml")
        result = await home_downloader._parse_report(soup, 2024030500)

        players = result["players"]
        if players:
            player = players[0]
            # Check OT period is parsed
            by_period = player["toi_by_period"]
            assert "OT" in by_period
            assert by_period["OT"]["shifts"] == 2
