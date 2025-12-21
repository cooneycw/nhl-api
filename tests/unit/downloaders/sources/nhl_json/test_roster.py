"""Tests for Roster Downloader."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.base.base_downloader import DownloaderConfig
from nhl_api.downloaders.base.protocol import DownloadError
from nhl_api.downloaders.sources.nhl_json.roster import (
    NHL_TEAM_ABBREVS,
    ParsedRoster,
    PlayerInfo,
    RosterDownloader,
    _parse_birth_date,
    _parse_localized_name,
    _parse_player,
    _parse_roster,
    create_roster_downloader,
)

# Sample player data for testing
SAMPLE_FORWARD = {
    "id": 8478402,
    "headshot": "https://assets.nhle.com/mugs/nhl/20242025/BOS/8478402.png",
    "firstName": {"default": "David"},
    "lastName": {"default": "Pastrnak"},
    "sweaterNumber": 88,
    "positionCode": "R",
    "shootsCatches": "R",
    "heightInInches": 72,
    "weightInPounds": 194,
    "heightInCentimeters": 183,
    "weightInKilograms": 88,
    "birthDate": "1996-05-25",
    "birthCity": {"default": "Havirov"},
    "birthCountry": "CZE",
}

SAMPLE_DEFENSEMAN = {
    "id": 8479325,
    "headshot": "https://assets.nhle.com/mugs/nhl/20242025/BOS/8479325.png",
    "firstName": {"default": "Charlie"},
    "lastName": {"default": "McAvoy"},
    "sweaterNumber": 73,
    "positionCode": "D",
    "shootsCatches": "R",
    "heightInInches": 72,
    "weightInPounds": 209,
    "heightInCentimeters": 183,
    "weightInKilograms": 95,
    "birthDate": "1997-12-21",
    "birthCity": {"default": "Long Beach"},
    "birthCountry": "USA",
    "birthStateProvince": {"default": "NY"},
}

SAMPLE_GOALIE = {
    "id": 8480280,
    "headshot": "https://assets.nhle.com/mugs/nhl/20242025/BOS/8480280.png",
    "firstName": {"default": "Jeremy"},
    "lastName": {"default": "Swayman"},
    "sweaterNumber": 1,
    "positionCode": "G",
    "shootsCatches": "L",
    "heightInInches": 74,
    "weightInPounds": 195,
    "heightInCentimeters": 188,
    "weightInKilograms": 88,
    "birthDate": "1998-11-24",
    "birthCity": {"default": "Anchorage"},
    "birthCountry": "USA",
    "birthStateProvince": {"default": "AK"},
}


@pytest.mark.unit
class TestParseLocalizedName:
    """Tests for _parse_localized_name function."""

    def test_parse_default_name(self) -> None:
        """Test parsing a name with default key."""
        name_obj = {"default": "David"}
        assert _parse_localized_name(name_obj) == "David"

    def test_parse_name_with_multiple_locales(self) -> None:
        """Test parsing a name with multiple locales."""
        name_obj = {"default": "David", "cs": "David", "fi": "David"}
        assert _parse_localized_name(name_obj) == "David"

    def test_parse_none_returns_empty_string(self) -> None:
        """Test that None returns empty string."""
        assert _parse_localized_name(None) == ""

    def test_parse_empty_dict_returns_empty_string(self) -> None:
        """Test that empty dict returns empty string."""
        assert _parse_localized_name({}) == ""


@pytest.mark.unit
class TestParseBirthDate:
    """Tests for _parse_birth_date function."""

    def test_parse_valid_date(self) -> None:
        """Test parsing a valid ISO date string."""
        result = _parse_birth_date("1996-05-25")
        assert result == date(1996, 5, 25)

    def test_parse_none_returns_none(self) -> None:
        """Test that None returns None."""
        assert _parse_birth_date(None) is None

    def test_parse_invalid_date_returns_none(self) -> None:
        """Test that invalid date returns None."""
        assert _parse_birth_date("invalid-date") is None

    def test_parse_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        assert _parse_birth_date("") is None


@pytest.mark.unit
class TestParsePlayer:
    """Tests for _parse_player function."""

    def test_parse_forward(self) -> None:
        """Test parsing a forward player."""
        player = _parse_player(SAMPLE_FORWARD, "BOS")

        assert player.player_id == 8478402
        assert player.first_name == "David"
        assert player.last_name == "Pastrnak"
        assert player.sweater_number == 88
        assert player.position_code == "R"
        assert player.shoots_catches == "R"
        assert player.height_inches == 72
        assert player.weight_pounds == 194
        assert player.height_cm == 183
        assert player.weight_kg == 88
        assert player.birth_date == date(1996, 5, 25)
        assert player.birth_city == "Havirov"
        assert player.birth_country == "CZE"
        assert player.birth_state_province is None or player.birth_state_province == ""
        assert player.headshot_url is not None
        assert player.team_abbrev == "BOS"

    def test_parse_defenseman_with_state(self) -> None:
        """Test parsing a defenseman with birth state."""
        player = _parse_player(SAMPLE_DEFENSEMAN, "BOS")

        assert player.player_id == 8479325
        assert player.first_name == "Charlie"
        assert player.last_name == "McAvoy"
        assert player.position_code == "D"
        assert player.birth_country == "USA"
        assert player.birth_state_province == "NY"

    def test_parse_goalie(self) -> None:
        """Test parsing a goalie."""
        player = _parse_player(SAMPLE_GOALIE, "BOS")

        assert player.player_id == 8480280
        assert player.first_name == "Jeremy"
        assert player.last_name == "Swayman"
        assert player.position_code == "G"
        assert player.shoots_catches == "L"

    def test_parse_player_with_missing_fields(self) -> None:
        """Test parsing a player with minimal data."""
        minimal_data = {
            "id": 12345,
        }
        player = _parse_player(minimal_data, "NYR")

        assert player.player_id == 12345
        assert player.first_name == ""
        assert player.last_name == ""
        assert player.sweater_number is None
        assert player.position_code == ""
        assert player.height_inches == 0
        assert player.weight_pounds == 0
        assert player.birth_date is None
        assert player.team_abbrev == "NYR"


@pytest.mark.unit
class TestParseRoster:
    """Tests for _parse_roster function."""

    def test_parse_complete_roster(self) -> None:
        """Test parsing a complete roster with all positions."""
        roster_data = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [SAMPLE_DEFENSEMAN],
            "goalies": [SAMPLE_GOALIE],
        }

        roster = _parse_roster(roster_data, "BOS")

        assert roster.team_abbrev == "BOS"
        assert roster.season_id is None
        assert len(roster.forwards) == 1
        assert len(roster.defensemen) == 1
        assert len(roster.goalies) == 1
        assert roster.player_count == 3

    def test_parse_roster_with_season(self) -> None:
        """Test parsing a historical roster with season ID."""
        roster_data = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [],
            "goalies": [],
        }

        roster = _parse_roster(roster_data, "BOS", 20232024)

        assert roster.season_id == 20232024

    def test_parse_empty_roster(self) -> None:
        """Test parsing an empty roster."""
        roster_data: dict[str, Any] = {}

        roster = _parse_roster(roster_data, "BOS")

        assert len(roster.forwards) == 0
        assert len(roster.defensemen) == 0
        assert len(roster.goalies) == 0
        assert roster.player_count == 0

    def test_all_players_property(self) -> None:
        """Test the all_players property."""
        roster_data = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [SAMPLE_DEFENSEMAN],
            "goalies": [SAMPLE_GOALIE],
        }

        roster = _parse_roster(roster_data, "BOS")
        all_players = roster.all_players

        assert len(all_players) == 3
        assert all_players[0].position_code == "R"  # Forward first
        assert all_players[1].position_code == "D"  # Then defenseman
        assert all_players[2].position_code == "G"  # Then goalie


@pytest.mark.unit
class TestParsedRoster:
    """Tests for ParsedRoster dataclass."""

    def test_parsed_roster_is_frozen(self) -> None:
        """Test that ParsedRoster is immutable."""
        roster = ParsedRoster(
            team_abbrev="BOS",
            season_id=None,
            forwards=(),
            defensemen=(),
            goalies=(),
        )

        with pytest.raises(AttributeError):
            roster.team_abbrev = "NYR"  # type: ignore[misc]


@pytest.mark.unit
class TestPlayerInfo:
    """Tests for PlayerInfo dataclass."""

    def test_player_info_is_frozen(self) -> None:
        """Test that PlayerInfo is immutable."""
        player = PlayerInfo(
            player_id=1,
            first_name="Test",
            last_name="Player",
            sweater_number=1,
            position_code="C",
            shoots_catches="L",
            height_inches=72,
            weight_pounds=200,
            height_cm=183,
            weight_kg=91,
            birth_date=None,
            birth_city=None,
            birth_country=None,
            birth_state_province=None,
            headshot_url=None,
            team_abbrev="BOS",
        )

        with pytest.raises(AttributeError):
            player.first_name = "Changed"  # type: ignore[misc]


@pytest.mark.unit
class TestNHLTeamAbbrevs:
    """Tests for NHL_TEAM_ABBREVS constant."""

    def test_all_32_teams_present(self) -> None:
        """Test that all 32 NHL teams are present."""
        # 32 teams, but ARI relocated to UTA so we have 33 total
        assert len(NHL_TEAM_ABBREVS) == 33

    def test_common_teams_present(self) -> None:
        """Test that common teams are in the list."""
        assert "BOS" in NHL_TEAM_ABBREVS
        assert "NYR" in NHL_TEAM_ABBREVS
        assert "MTL" in NHL_TEAM_ABBREVS
        assert "TOR" in NHL_TEAM_ABBREVS
        assert "CHI" in NHL_TEAM_ABBREVS

    def test_expansion_teams_present(self) -> None:
        """Test that expansion teams are in the list."""
        assert "SEA" in NHL_TEAM_ABBREVS  # Seattle Kraken (2021)
        assert "VGK" in NHL_TEAM_ABBREVS  # Vegas Golden Knights (2017)
        assert "UTA" in NHL_TEAM_ABBREVS  # Utah Hockey Club (2024)


@pytest.mark.unit
class TestRosterDownloader:
    """Tests for RosterDownloader class."""

    @pytest.fixture
    def mock_http_client(self) -> MagicMock:
        """Create a mock HTTP client."""
        client = MagicMock()
        client.get = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_rate_limiter(self) -> MagicMock:
        """Create a mock rate limiter."""
        limiter = MagicMock()
        limiter.wait = AsyncMock()
        return limiter

    @pytest.fixture
    def config(self) -> DownloaderConfig:
        """Create a test configuration."""
        return DownloaderConfig(
            base_url="https://api-web.nhle.com/v1",
            requests_per_second=10.0,
        )

    @pytest.fixture
    def downloader(
        self,
        config: DownloaderConfig,
        mock_http_client: MagicMock,
        mock_rate_limiter: MagicMock,
    ) -> RosterDownloader:
        """Create a RosterDownloader with mock HTTP client."""
        dl = RosterDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False  # Don't close the mock
        return dl

    def test_source_name(self, downloader: RosterDownloader) -> None:
        """Test that source_name returns correct identifier."""
        assert downloader.source_name == "nhl_json_roster"

    @pytest.mark.asyncio
    async def test_get_current_roster_success(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful current roster download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [SAMPLE_DEFENSEMAN],
            "goalies": [SAMPLE_GOALIE],
        }

        mock_http_client.get = AsyncMock(return_value=mock_response)

        roster = await downloader.get_current_roster("BOS")

        assert roster.team_abbrev == "BOS"
        assert roster.player_count == 3
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_roster_failure(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of failed roster download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 404

        mock_http_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadError) as exc_info:
            await downloader.get_current_roster("INVALID")

        assert "Failed to fetch roster" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_roster_for_season_success(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful historical roster download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [],
            "goalies": [],
        }

        mock_http_client.get = AsyncMock(return_value=mock_response)

        roster = await downloader.get_roster_for_season("BOS", 20232024)

        assert roster.team_abbrev == "BOS"
        assert roster.season_id == 20232024
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_roster_for_season_failure(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of failed historical roster download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 404

        mock_http_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadError) as exc_info:
            await downloader.get_roster_for_season("BOS", 19001901)

        assert "Failed to fetch roster" in str(exc_info.value)
        assert "season 19001901" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_available_seasons_success(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful seasons list download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = ["20232024", "20222023", "20212022"]

        mock_http_client.get = AsyncMock(return_value=mock_response)

        seasons = await downloader.get_available_seasons("BOS")

        assert seasons == [20232024, 20222023, 20212022]
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_available_seasons_failure(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of failed seasons download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 404

        mock_http_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadError) as exc_info:
            await downloader.get_available_seasons("INVALID")

        assert "Failed to fetch seasons" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_all_current_rosters_success(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test downloading multiple team rosters."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [],
            "goalies": [],
        }

        mock_http_client.get = AsyncMock(return_value=mock_response)

        rosters = await downloader.download_all_current_rosters(["BOS", "NYR"])

        assert len(rosters) == 2
        assert rosters[0].team_abbrev == "BOS"

    @pytest.mark.asyncio
    async def test_download_all_current_rosters_partial_failure(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that download continues when one team fails."""
        success_response = MagicMock()
        success_response.is_success = True
        success_response.is_rate_limited = False
        success_response.is_server_error = False
        success_response.status = 200
        success_response.retry_after = None
        success_response.json.return_value = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [],
            "goalies": [],
        }

        fail_response = MagicMock()
        fail_response.is_success = False
        fail_response.is_rate_limited = False
        fail_response.is_server_error = False
        fail_response.status = 404

        # First call fails, second succeeds
        mock_http_client.get = AsyncMock(side_effect=[fail_response, success_response])

        rosters = await downloader.download_all_current_rosters(["INVALID", "BOS"])

        # Should still get the successful one
        assert len(rosters) == 1
        assert rosters[0].team_abbrev == "BOS"

    @pytest.mark.asyncio
    async def test_download_rosters_for_season_success(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test downloading historical rosters for multiple teams."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [],
            "goalies": [],
        }

        mock_http_client.get = AsyncMock(return_value=mock_response)

        rosters = await downloader.download_rosters_for_season(20232024, ["BOS", "NYR"])

        assert len(rosters) == 2
        assert all(r.season_id == 20232024 for r in rosters)

    @pytest.mark.asyncio
    async def test_get_player_by_id_found(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test finding a player by ID."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "forwards": [SAMPLE_FORWARD],
            "defensemen": [],
            "goalies": [],
        }

        mock_http_client.get = AsyncMock(return_value=mock_response)

        player = await downloader.get_player_by_id(8478402, ["BOS"])

        assert player is not None
        assert player.player_id == 8478402
        assert player.last_name == "Pastrnak"

    @pytest.mark.asyncio
    async def test_get_player_by_id_not_found(
        self,
        downloader: RosterDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test when player is not found."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "forwards": [],
            "defensemen": [],
            "goalies": [],
        }

        mock_http_client.get = AsyncMock(return_value=mock_response)

        player = await downloader.get_player_by_id(9999999, ["BOS"])

        assert player is None

    @pytest.mark.asyncio
    async def test_fetch_game_not_applicable(
        self, downloader: RosterDownloader
    ) -> None:
        """Test that _fetch_game returns placeholder for roster downloads."""
        result = await downloader._fetch_game(12345)

        assert "_note" in result
        assert "team-based" in result["_note"]


@pytest.mark.unit
class TestCreateRosterDownloader:
    """Tests for create_roster_downloader factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating downloader with default parameters."""
        downloader = create_roster_downloader()

        assert downloader.source_name == "nhl_json_roster"
        assert downloader.config.base_url == "https://api-web.nhle.com/v1"
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_params(self) -> None:
        """Test creating downloader with custom parameters."""
        downloader = create_roster_downloader(
            requests_per_second=10.0,
            max_retries=5,
        )

        assert downloader.config.requests_per_second == 10.0
        assert downloader.config.max_retries == 5

    def test_health_check_url_set(self) -> None:
        """Test that health check URL is configured."""
        downloader = create_roster_downloader()

        assert downloader.config.health_check_url == "roster/BOS/current"


@pytest.mark.unit
class TestRosterDownloaderPersist:
    """Tests for RosterDownloader.persist() method."""

    @pytest.fixture
    def mock_http_client(self) -> MagicMock:
        """Create a mock HTTP client."""
        client = MagicMock()
        client.get = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_rate_limiter(self) -> MagicMock:
        """Create a mock rate limiter."""
        limiter = MagicMock()
        limiter.wait = AsyncMock()
        return limiter

    @pytest.fixture
    def config(self) -> DownloaderConfig:
        """Create a test configuration."""
        return DownloaderConfig(
            base_url="https://api-web.nhle.com/v1",
            requests_per_second=10.0,
        )

    @pytest.fixture
    def downloader(
        self,
        config: DownloaderConfig,
        mock_http_client: MagicMock,
        mock_rate_limiter: MagicMock,
    ) -> RosterDownloader:
        """Create a RosterDownloader with mock HTTP client."""
        dl = RosterDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False
        return dl

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """Create a mock DatabaseService."""
        db = MagicMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def sample_roster(self) -> ParsedRoster:
        """Create a sample roster for testing."""
        forward = PlayerInfo(
            player_id=8478402,
            first_name="David",
            last_name="Pastrnak",
            sweater_number=88,
            position_code="R",
            shoots_catches="R",
            height_inches=72,
            weight_pounds=194,
            height_cm=183,
            weight_kg=88,
            birth_date=date(1996, 5, 25),
            birth_city="Havirov",
            birth_country="CZE",
            birth_state_province=None,
            headshot_url="https://example.com/pastrnak.png",
            team_abbrev="BOS",
        )
        defenseman = PlayerInfo(
            player_id=8479325,
            first_name="Charlie",
            last_name="McAvoy",
            sweater_number=73,
            position_code="D",
            shoots_catches="R",
            height_inches=72,
            weight_pounds=209,
            height_cm=183,
            weight_kg=95,
            birth_date=date(1997, 12, 21),
            birth_city="Long Beach",
            birth_country="USA",
            birth_state_province="NY",
            headshot_url="https://example.com/mcavoy.png",
            team_abbrev="BOS",
        )
        goalie = PlayerInfo(
            player_id=8480280,
            first_name="Jeremy",
            last_name="Swayman",
            sweater_number=1,
            position_code="G",
            shoots_catches="L",
            height_inches=74,
            weight_pounds=195,
            height_cm=188,
            weight_kg=88,
            birth_date=date(1998, 11, 24),
            birth_city="Anchorage",
            birth_country="USA",
            birth_state_province="AK",
            headshot_url="https://example.com/swayman.png",
            team_abbrev="BOS",
        )
        return ParsedRoster(
            team_abbrev="BOS",
            season_id=20242025,
            forwards=(forward,),
            defensemen=(defenseman,),
            goalies=(goalie,),
        )

    @pytest.mark.asyncio
    async def test_persist_empty_list(
        self,
        downloader: RosterDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test persisting an empty roster list returns 0."""
        result = await downloader.persist(mock_db, [])

        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_single_roster(
        self,
        downloader: RosterDownloader,
        mock_db: MagicMock,
        sample_roster: ParsedRoster,
    ) -> None:
        """Test persisting a single roster with multiple players."""
        result = await downloader.persist(mock_db, [sample_roster])

        # Should persist 3 players (forward, defenseman, goalie)
        assert result == 3
        # 6 calls: 2 per player (player insert + roster insert)
        assert mock_db.execute.call_count == 6

    @pytest.mark.asyncio
    async def test_persist_multiple_rosters(
        self,
        downloader: RosterDownloader,
        mock_db: MagicMock,
        sample_roster: ParsedRoster,
    ) -> None:
        """Test persisting multiple rosters."""
        # Create a second roster
        second_roster = ParsedRoster(
            team_abbrev="NYR",
            season_id=20242025,
            forwards=(
                PlayerInfo(
                    player_id=8478550,
                    first_name="Artemi",
                    last_name="Panarin",
                    sweater_number=10,
                    position_code="L",
                    shoots_catches="R",
                    height_inches=71,
                    weight_pounds=180,
                    height_cm=180,
                    weight_kg=82,
                    birth_date=date(1991, 10, 30),
                    birth_city="Korkino",
                    birth_country="RUS",
                    birth_state_province=None,
                    headshot_url="https://example.com/panarin.png",
                    team_abbrev="NYR",
                ),
            ),
            defensemen=(),
            goalies=(),
        )

        result = await downloader.persist(mock_db, [sample_roster, second_roster])

        # 3 from first roster + 1 from second roster
        assert result == 4
        # 8 calls: 6 from first roster + 2 from second roster
        assert mock_db.execute.call_count == 8

    @pytest.mark.asyncio
    async def test_persist_roster_type_assignment(
        self,
        downloader: RosterDownloader,
        mock_db: MagicMock,
        sample_roster: ParsedRoster,
    ) -> None:
        """Test that roster_type is assigned correctly based on position."""
        await downloader.persist(mock_db, [sample_roster])

        # Check the roster insert calls for roster_type
        calls = mock_db.execute.call_args_list

        # Forward (position R) should be 'forward'
        roster_call_1 = calls[1]  # Second call is roster insert for forward
        assert roster_call_1[0][0].strip().startswith("INSERT INTO team_rosters")
        assert roster_call_1[0][6] == "forward"

        # Defenseman (position D) should be 'defenseman'
        roster_call_2 = calls[3]  # Fourth call is roster insert for defenseman
        assert roster_call_2[0][6] == "defenseman"

        # Goalie (position G) should be 'goalie'
        roster_call_3 = calls[5]  # Sixth call is roster insert for goalie
        assert roster_call_3[0][6] == "goalie"

    @pytest.mark.asyncio
    async def test_persist_uses_default_season_when_none(
        self,
        downloader: RosterDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test that persist uses default season when roster.season_id is None."""
        roster = ParsedRoster(
            team_abbrev="BOS",
            season_id=None,  # No season ID
            forwards=(
                PlayerInfo(
                    player_id=12345,
                    first_name="Test",
                    last_name="Player",
                    sweater_number=99,
                    position_code="C",
                    shoots_catches="L",
                    height_inches=72,
                    weight_pounds=200,
                    height_cm=183,
                    weight_kg=91,
                    birth_date=None,
                    birth_city=None,
                    birth_country=None,
                    birth_state_province=None,
                    headshot_url=None,
                    team_abbrev="BOS",
                ),
            ),
            defensemen=(),
            goalies=(),
        )

        await downloader.persist(mock_db, [roster])

        # Check that season_id defaulted to 20242025
        roster_insert_call = mock_db.execute.call_args_list[1]
        # Position 2 in the args is season_id
        assert roster_insert_call[0][2] == 20242025

    @pytest.mark.asyncio
    async def test_persist_handles_zero_height_weight(
        self,
        downloader: RosterDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test that zero height/weight are converted to None."""
        roster = ParsedRoster(
            team_abbrev="BOS",
            season_id=20242025,
            forwards=(
                PlayerInfo(
                    player_id=12345,
                    first_name="Test",
                    last_name="Player",
                    sweater_number=None,
                    position_code="C",
                    shoots_catches="",
                    height_inches=0,  # Zero height
                    weight_pounds=0,  # Zero weight
                    height_cm=0,
                    weight_kg=0,
                    birth_date=None,
                    birth_city=None,
                    birth_country=None,
                    birth_state_province=None,
                    headshot_url=None,
                    team_abbrev="BOS",
                ),
            ),
            defensemen=(),
            goalies=(),
        )

        await downloader.persist(mock_db, [roster])

        # Check player insert call
        player_insert_call = mock_db.execute.call_args_list[0]
        # Position 8 is height_inches, position 9 is weight_lbs
        assert player_insert_call[0][8] is None  # height_inches
        assert player_insert_call[0][9] is None  # weight_lbs
        assert (
            player_insert_call[0][10] is None
        )  # shoots_catches (empty string -> None)

    @pytest.mark.asyncio
    async def test_persist_player_upsert_sql_structure(
        self,
        downloader: RosterDownloader,
        mock_db: MagicMock,
        sample_roster: ParsedRoster,
    ) -> None:
        """Test that player upsert SQL has correct structure."""
        await downloader.persist(mock_db, [sample_roster])

        # Check the first call (player insert)
        player_call = mock_db.execute.call_args_list[0]
        sql = player_call[0][0]

        # Verify key SQL elements
        assert "INSERT INTO players" in sql
        assert "ON CONFLICT (player_id) DO UPDATE SET" in sql
        assert "updated_at = CURRENT_TIMESTAMP" in sql

    @pytest.mark.asyncio
    async def test_persist_roster_upsert_sql_structure(
        self,
        downloader: RosterDownloader,
        mock_db: MagicMock,
        sample_roster: ParsedRoster,
    ) -> None:
        """Test that roster upsert SQL has correct structure."""
        await downloader.persist(mock_db, [sample_roster])

        # Check the second call (roster insert)
        roster_call = mock_db.execute.call_args_list[1]
        sql = roster_call[0][0]

        # Verify key SQL elements
        assert "INSERT INTO team_rosters" in sql
        assert "ON CONFLICT (team_abbrev, season_id, player_id, snapshot_date)" in sql
        assert "DO UPDATE SET" in sql
