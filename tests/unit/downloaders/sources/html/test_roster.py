"""Unit tests for RosterDownloader."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.sources.html.base_html_downloader import HTMLDownloaderConfig
from nhl_api.downloaders.sources.html.roster import (
    CAPTAIN_PATTERN,
    CoachInfo,
    OfficialInfo,
    ParsedRoster,
    PlayerRoster,
    RosterDownloader,
    TeamRoster,
)

if TYPE_CHECKING:
    pass


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "html"


class TestCaptainPattern:
    """Tests for captain designation pattern."""

    def test_captain_pattern_matches_captain(self) -> None:
        """Test pattern matches captain designation."""
        match = CAPTAIN_PATTERN.match("ANDERS LEE  (C)")
        assert match is not None
        assert match.group(1) == "ANDERS LEE"
        assert match.group(2) == "C"

    def test_captain_pattern_matches_alternate(self) -> None:
        """Test pattern matches alternate captain designation."""
        match = CAPTAIN_PATTERN.match("BROCK NELSON  (A)")
        assert match is not None
        assert match.group(1) == "BROCK NELSON"
        assert match.group(2) == "A"

    def test_captain_pattern_no_match_regular_player(self) -> None:
        """Test pattern does not match regular player."""
        match = CAPTAIN_PATTERN.match("ADAM PELECH")
        assert match is None

    def test_captain_pattern_handles_single_space(self) -> None:
        """Test pattern handles single space before designation."""
        match = CAPTAIN_PATTERN.match("JORDAN STAAL (C)")
        assert match is not None
        assert match.group(1) == "JORDAN STAAL"


class TestPlayerRoster:
    """Tests for PlayerRoster dataclass."""

    def test_player_roster_defaults(self) -> None:
        """Test PlayerRoster default values."""
        player = PlayerRoster(number=10, position="C", name="TEST PLAYER")
        assert player.number == 10
        assert player.position == "C"
        assert player.name == "TEST PLAYER"
        assert player.is_starter is False
        assert player.is_captain is False
        assert player.is_alternate is False

    def test_player_roster_with_flags(self) -> None:
        """Test PlayerRoster with flags set."""
        player = PlayerRoster(
            number=27,
            position="L",
            name="ANDERS LEE",
            is_starter=True,
            is_captain=True,
            is_alternate=False,
        )
        assert player.is_starter is True
        assert player.is_captain is True
        assert player.is_alternate is False


class TestCoachInfo:
    """Tests for CoachInfo dataclass."""

    def test_coach_info_defaults(self) -> None:
        """Test CoachInfo default role."""
        coach = CoachInfo(name="Patrick Roy")
        assert coach.name == "Patrick Roy"
        assert coach.role == "Head Coach"

    def test_coach_info_custom_role(self) -> None:
        """Test CoachInfo with custom role."""
        coach = CoachInfo(name="John Doe", role="Assistant Coach")
        assert coach.role == "Assistant Coach"


class TestOfficialInfo:
    """Tests for OfficialInfo dataclass."""

    def test_official_info_referee(self) -> None:
        """Test OfficialInfo for referee."""
        official = OfficialInfo(number=7, name="Garrett Rank", role="Referee")
        assert official.number == 7
        assert official.name == "Garrett Rank"
        assert official.role == "Referee"

    def test_official_info_linesman(self) -> None:
        """Test OfficialInfo for linesman."""
        official = OfficialInfo(number=56, name="Julien Fournier", role="Linesman")
        assert official.number == 56
        assert official.role == "Linesman"


class TestTeamRoster:
    """Tests for TeamRoster dataclass."""

    def test_team_roster_defaults(self) -> None:
        """Test TeamRoster default values."""
        team = TeamRoster(name="CAROLINA HURRICANES", abbrev="CAR")
        assert team.name == "CAROLINA HURRICANES"
        assert team.abbrev == "CAR"
        assert team.skaters == []
        assert team.goalies == []
        assert team.scratches == []
        assert team.coaches == []


class TestParsedRoster:
    """Tests for ParsedRoster dataclass."""

    def test_parsed_roster_defaults(self) -> None:
        """Test ParsedRoster default values."""
        roster = ParsedRoster(
            game_id=2024020500,
            season_id=20242025,
            date="Tuesday, December 17, 2024",
            venue="Lenovo Center",
            attendance=18700,
            away_team=TeamRoster(name="NEW YORK ISLANDERS", abbrev="NYI"),
            home_team=TeamRoster(name="CAROLINA HURRICANES", abbrev="CAR"),
        )
        assert roster.game_id == 2024020500
        assert roster.referees == []
        assert roster.linesmen == []


class TestRosterDownloader:
    """Tests for RosterDownloader class."""

    @pytest.fixture
    def config(self) -> HTMLDownloaderConfig:
        """Create test configuration."""
        return HTMLDownloaderConfig()

    @pytest.fixture
    def downloader(self, config: HTMLDownloaderConfig) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(config)

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    def test_report_type(self, downloader: RosterDownloader) -> None:
        """Test report_type property."""
        assert downloader.report_type == "RO"

    def test_source_name(self, downloader: RosterDownloader) -> None:
        """Test source_name property."""
        assert downloader.source_name == "html_ro"


class TestRosterDownloaderParseGameInfo:
    """Tests for _parse_game_info method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    def test_parse_game_info(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing game info from fixture."""
        date, venue, attendance = downloader._parse_game_info(soup)
        assert date == "Tuesday, December 17, 2024"
        assert venue == "Lenovo Center"
        assert attendance == 18700

    def test_parse_game_info_no_game_info_table(
        self, downloader: RosterDownloader
    ) -> None:
        """Test parsing when GameInfo table is missing."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        date, venue, attendance = downloader._parse_game_info(soup)
        assert date == ""
        assert venue == ""
        assert attendance is None


class TestRosterDownloaderParseTeamAbbrevs:
    """Tests for _parse_team_abbrevs method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    def test_parse_team_abbrevs(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing team abbreviations from fixture."""
        away_abbrev, home_abbrev = downloader._parse_team_abbrevs(soup)
        assert away_abbrev == "NYI"
        assert home_abbrev == "CAR"

    def test_parse_team_abbrevs_no_tables(self, downloader: RosterDownloader) -> None:
        """Test parsing when Visitor/Home tables are missing."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        away_abbrev, home_abbrev = downloader._parse_team_abbrevs(soup)
        assert away_abbrev == ""
        assert home_abbrev == ""


class TestRosterDownloaderParseTeamNames:
    """Tests for _parse_team_names method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    def test_parse_team_names(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing team names from fixture."""
        away_name, home_name = downloader._parse_team_names(soup)
        assert away_name == "NEW YORK ISLANDERS"
        assert home_name == "CAROLINA HURRICANES"


class TestRosterDownloaderParsePlayerRosters:
    """Tests for _parse_player_rosters method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    def test_parse_player_rosters(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing player rosters from fixture."""
        away_players, home_players = downloader._parse_player_rosters(soup)

        # Check away team has players
        assert len(away_players) > 0
        assert len(home_players) > 0

        # Check specific player from fixture
        adam_pelech = next((p for p in away_players if p.name == "ADAM PELECH"), None)
        assert adam_pelech is not None
        assert adam_pelech.number == 3
        assert adam_pelech.position == "D"
        assert adam_pelech.is_starter is True

    def test_parse_player_rosters_includes_goalies(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test that goalies are included in player rosters."""
        away_players, home_players = downloader._parse_player_rosters(soup)

        # Check for goalies
        away_goalies = [p for p in away_players if p.position == "G"]
        home_goalies = [p for p in home_players if p.position == "G"]

        assert len(away_goalies) >= 1
        assert len(home_goalies) >= 1

    def test_parse_captain_designation(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing captain and alternate captain designations."""
        away_players, home_players = downloader._parse_player_rosters(soup)

        # Find Anders Lee (captain)
        anders_lee = next((p for p in away_players if "ANDERS LEE" in p.name), None)
        assert anders_lee is not None
        assert anders_lee.is_captain is True

        # Find Jordan Staal (home captain)
        jordan_staal = next((p for p in home_players if "JORDAN STAAL" in p.name), None)
        assert jordan_staal is not None
        assert jordan_staal.is_captain is True

    def test_parse_alternate_captain(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing alternate captain designation."""
        away_players, home_players = downloader._parse_player_rosters(soup)

        # Find Brock Nelson (alternate)
        brock_nelson = next((p for p in away_players if "BROCK NELSON" in p.name), None)
        assert brock_nelson is not None
        assert brock_nelson.is_alternate is True
        assert brock_nelson.is_captain is False


class TestRosterDownloaderParseScratches:
    """Tests for _parse_scratches method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    def test_parse_scratches(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing scratches from fixture."""
        away_scratches, home_scratches = downloader._parse_scratches(soup)

        # Both teams should have scratches
        assert len(away_scratches) >= 1
        assert len(home_scratches) >= 1

        # Check specific scratch player
        matt_martin = next((p for p in away_scratches if p.name == "MATT MARTIN"), None)
        assert matt_martin is not None
        assert matt_martin.number == 17
        assert matt_martin.position == "L"

    def test_parse_scratches_no_section(self, downloader: RosterDownloader) -> None:
        """Test parsing when scratches section is missing."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        away_scratches, home_scratches = downloader._parse_scratches(soup)
        assert away_scratches == []
        assert home_scratches == []


class TestRosterDownloaderParseCoaches:
    """Tests for _parse_coaches method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    def test_parse_coaches(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing coaches from fixture."""
        away_coaches, home_coaches = downloader._parse_coaches(soup)

        # Both teams should have head coach
        assert len(away_coaches) >= 1
        assert len(home_coaches) >= 1

        # Check specific coaches
        assert away_coaches[0].name == "Patrick Roy"
        assert away_coaches[0].role == "Head Coach"
        assert home_coaches[0].name == "Rod Brind'Amour"

    def test_parse_coaches_no_section(self, downloader: RosterDownloader) -> None:
        """Test parsing when coaches section is missing."""
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        away_coaches, home_coaches = downloader._parse_coaches(soup)
        assert away_coaches == []
        assert home_coaches == []


class TestRosterDownloaderParseOfficials:
    """Tests for _parse_officials method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    def test_parse_officials(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test parsing officials from fixture."""
        referees, linesmen = downloader._parse_officials(soup)

        # Should have referees and linesmen
        assert len(referees) >= 1
        assert len(linesmen) >= 1

        # Check specific referee
        garrett_rank = next((r for r in referees if "Garrett Rank" in r.name), None)
        assert garrett_rank is not None
        assert garrett_rank.number == 7
        assert garrett_rank.role == "Referee"


class TestRosterDownloaderIsStarter:
    """Tests for _is_starter method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    def test_is_starter_bold_list(self, downloader: RosterDownloader) -> None:
        """Test _is_starter with class as list."""
        soup = BeautifulSoup('<td class="bold">3</td>', "lxml")
        cell = soup.find("td")
        assert cell is not None
        assert downloader._is_starter(cell) is True

    def test_is_starter_bold_combined(self, downloader: RosterDownloader) -> None:
        """Test _is_starter with combined class."""
        soup = BeautifulSoup('<td class="bold + italic">27</td>', "lxml")
        cell = soup.find("td")
        assert cell is not None
        assert downloader._is_starter(cell) is True

    def test_is_starter_no_bold(self, downloader: RosterDownloader) -> None:
        """Test _is_starter without bold class."""
        soup = BeautifulSoup('<td class="">8</td>', "lxml")
        cell = soup.find("td")
        assert cell is not None
        assert downloader._is_starter(cell) is False


class TestRosterDownloaderParsePlayerRow:
    """Tests for _parse_player_row method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    def test_parse_player_row_valid(self, downloader: RosterDownloader) -> None:
        """Test parsing a valid player row."""
        html = """
        <tr>
            <td class="bold">3</td>
            <td class="bold">D</td>
            <td class="bold">ADAM PELECH</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        cells = soup.find_all("td")
        player = downloader._parse_player_row(cells)

        assert player is not None
        assert player.number == 3
        assert player.position == "D"
        assert player.name == "ADAM PELECH"
        assert player.is_starter is True

    def test_parse_player_row_with_captain(self, downloader: RosterDownloader) -> None:
        """Test parsing a player row with captain designation."""
        html = """
        <tr>
            <td class="italic">27</td>
            <td class="italic">L</td>
            <td class="italic">ANDERS LEE  (C)</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        cells = soup.find_all("td")
        player = downloader._parse_player_row(cells)

        assert player is not None
        assert player.name == "ANDERS LEE"
        assert player.is_captain is True
        assert player.is_alternate is False

    def test_parse_player_row_with_alternate(
        self, downloader: RosterDownloader
    ) -> None:
        """Test parsing a player row with alternate captain designation."""
        html = """
        <tr>
            <td>29</td>
            <td>C</td>
            <td>BROCK NELSON  (A)</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        cells = soup.find_all("td")
        player = downloader._parse_player_row(cells)

        assert player is not None
        assert player.name == "BROCK NELSON"
        assert player.is_alternate is True
        assert player.is_captain is False

    def test_parse_player_row_invalid_position(
        self, downloader: RosterDownloader
    ) -> None:
        """Test parsing with invalid position returns None."""
        html = """
        <tr>
            <td>10</td>
            <td>X</td>
            <td>INVALID PLAYER</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        cells = soup.find_all("td")
        player = downloader._parse_player_row(cells)

        assert player is None

    def test_parse_player_row_insufficient_cells(
        self, downloader: RosterDownloader
    ) -> None:
        """Test parsing with insufficient cells returns None."""
        html = """
        <tr>
            <td>10</td>
            <td>C</td>
        </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        cells = soup.find_all("td")
        player = downloader._parse_player_row(cells)

        assert player is None


class TestRosterDownloaderRosterToDict:
    """Tests for _roster_to_dict method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    def test_roster_to_dict(self, downloader: RosterDownloader) -> None:
        """Test converting ParsedRoster to dictionary."""
        roster = ParsedRoster(
            game_id=2024020500,
            season_id=20242025,
            date="Tuesday, December 17, 2024",
            venue="Lenovo Center",
            attendance=18700,
            away_team=TeamRoster(
                name="NEW YORK ISLANDERS",
                abbrev="NYI",
                skaters=[
                    PlayerRoster(number=3, position="D", name="ADAM PELECH"),
                ],
                goalies=[
                    PlayerRoster(number=30, position="G", name="ILYA SOROKIN"),
                ],
                coaches=[CoachInfo(name="Patrick Roy")],
            ),
            home_team=TeamRoster(
                name="CAROLINA HURRICANES",
                abbrev="CAR",
            ),
            referees=[OfficialInfo(number=7, name="Garrett Rank", role="Referee")],
            linesmen=[OfficialInfo(number=56, name="Julien Fournier", role="Linesman")],
        )

        result = downloader._roster_to_dict(roster)

        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert result["date"] == "Tuesday, December 17, 2024"
        assert result["venue"] == "Lenovo Center"
        assert result["attendance"] == 18700
        assert result["away_team"]["name"] == "NEW YORK ISLANDERS"
        assert result["away_team"]["abbrev"] == "NYI"
        assert len(result["away_team"]["skaters"]) == 1
        assert len(result["away_team"]["goalies"]) == 1
        assert result["away_team"]["skaters"][0]["number"] == 3
        assert len(result["referees"]) == 1
        assert result["referees"][0]["name"] == "Garrett Rank"


class TestRosterDownloaderParseReport:
    """Tests for _parse_report integration."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load test fixture HTML."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_text(encoding="utf-8")

    @pytest.fixture
    def soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML."""
        return BeautifulSoup(fixture_html, "lxml")

    @pytest.mark.asyncio
    async def test_parse_report_full(
        self, downloader: RosterDownloader, soup: BeautifulSoup
    ) -> None:
        """Test full report parsing."""
        result = await downloader._parse_report(soup, 2024020500)

        # Basic structure
        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert result["date"] == "Tuesday, December 17, 2024"
        assert result["venue"] == "Lenovo Center"
        assert result["attendance"] == 18700

        # Teams
        assert result["away_team"]["name"] == "NEW YORK ISLANDERS"
        assert result["away_team"]["abbrev"] == "NYI"
        assert result["home_team"]["name"] == "CAROLINA HURRICANES"
        assert result["home_team"]["abbrev"] == "CAR"

        # Players
        assert len(result["away_team"]["skaters"]) > 0
        assert len(result["away_team"]["goalies"]) > 0
        assert len(result["home_team"]["skaters"]) > 0
        assert len(result["home_team"]["goalies"]) > 0

        # Coaches
        assert len(result["away_team"]["coaches"]) >= 1
        assert len(result["home_team"]["coaches"]) >= 1
        assert result["away_team"]["coaches"][0]["name"] == "Patrick Roy"
        assert result["home_team"]["coaches"][0]["name"] == "Rod Brind'Amour"

        # Officials
        assert len(result["referees"]) >= 1
        assert len(result["linesmen"]) >= 1


class TestRosterDownloaderDownloadGame:
    """Tests for download_game method."""

    @pytest.fixture
    def downloader(self) -> RosterDownloader:
        """Create downloader instance."""
        return RosterDownloader(HTMLDownloaderConfig())

    @pytest.fixture
    def fixture_html(self) -> bytes:
        """Load test fixture HTML as bytes."""
        fixture_path = FIXTURES_DIR / "RO020500.HTM"
        return fixture_path.read_bytes()

    @pytest.mark.asyncio
    async def test_download_game_success(
        self, downloader: RosterDownloader, fixture_html: bytes
    ) -> None:
        """Test successful game download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = fixture_html

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with downloader:
                result = await downloader.download_game(2024020500)

            assert result.source == "html_ro"
            assert result.game_id == 2024020500
            assert result.season_id == 20242025
            assert result.data["away_team"]["name"] == "NEW YORK ISLANDERS"
            assert result.raw_content is not None
