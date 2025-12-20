"""Tests for the PlayerLandingDownloader."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.base.protocol import DownloadError
from nhl_api.downloaders.base.rate_limiter import RateLimiter
from nhl_api.downloaders.base.retry_handler import RetryHandler
from nhl_api.downloaders.sources.nhl_json.player_landing import (
    DraftDetails,
    GoalieCareerStats,
    GoalieRecentGame,
    GoalieSeasonStats,
    ParsedPlayerLanding,
    PlayerLandingDownloader,
    PlayerLandingDownloaderConfig,
    SkaterCareerStats,
    SkaterRecentGame,
    SkaterSeasonStats,
)
from nhl_api.utils.http_client import HTTPClient, HTTPResponse

# Sample skater API response data for testing
SAMPLE_SKATER_RESPONSE: dict[str, Any] = {
    "playerId": 8478402,
    "isActive": True,
    "currentTeamId": 22,
    "currentTeamAbbrev": "EDM",
    "firstName": {"default": "Connor"},
    "lastName": {"default": "McDavid"},
    "sweaterNumber": 97,
    "position": "C",
    "shootsCatches": "L",
    "heightInInches": 73,
    "heightInCentimeters": 185,
    "weightInPounds": 194,
    "weightInKilograms": 88,
    "birthDate": "1997-01-13",
    "birthCity": {"default": "Richmond Hill"},
    "birthStateProvince": {"default": "Ontario"},
    "birthCountry": "CAN",
    "headshot": "https://assets.nhle.com/mugs/nhl/20252026/EDM/8478402.png",
    "heroImage": "https://assets.nhle.com/mugs/actionshots/1296x729/8478402.jpg",
    "draftDetails": {
        "year": 2015,
        "teamAbbrev": "EDM",
        "round": 1,
        "pickInRound": 1,
        "overallPick": 1,
    },
    "inTop100AllTime": 0,
    "inHHOF": 0,
    "careerTotals": {
        "regularSeason": {
            "gamesPlayed": 747,
            "goals": 382,
            "assists": 758,
            "points": 1140,
            "plusMinus": 170,
            "pim": 300,
            "gameWinningGoals": 73,
            "otGoals": 16,
            "shots": 2518,
            "shootingPctg": 0.1517,
            "powerPlayGoals": 93,
            "powerPlayPoints": 388,
            "shorthandedGoals": 9,
            "shorthandedPoints": 19,
            "avgToi": "21:46",
            "faceoffWinningPctg": 0.4777,
        },
        "playoffs": {
            "gamesPlayed": 96,
            "goals": 44,
            "assists": 106,
            "points": 150,
            "plusMinus": 31,
            "pim": 28,
            "gameWinningGoals": 5,
            "otGoals": 2,
            "shots": 330,
            "shootingPctg": 0.1333,
            "powerPlayGoals": 13,
            "powerPlayPoints": 54,
            "shorthandedGoals": 2,
            "shorthandedPoints": 3,
            "avgToi": "23:38",
            "faceoffWinningPctg": 0.459,
        },
    },
    "seasonTotals": [
        {
            "season": 20152016,
            "gameTypeId": 2,
            "leagueAbbrev": "NHL",
            "teamName": {"default": "Edmonton Oilers"},
            "gamesPlayed": 45,
            "goals": 16,
            "assists": 32,
            "points": 48,
            "plusMinus": -1,
            "pim": 18,
            "gameWinningGoals": 5,
            "powerPlayGoals": 3,
            "shorthandedGoals": 0,
            "shots": 105,
            "shootingPctg": 0.1524,
            "avgToi": "18:53",
            "faceoffWinningPctg": 0.4123,
            "sequence": 1,
        },
        {
            "season": 20162017,
            "gameTypeId": 2,
            "leagueAbbrev": "NHL",
            "teamName": {"default": "Edmonton Oilers"},
            "gamesPlayed": 82,
            "goals": 30,
            "assists": 70,
            "points": 100,
            "plusMinus": 27,
            "pim": 26,
            "gameWinningGoals": 6,
            "powerPlayGoals": 3,
            "shorthandedGoals": 1,
            "shots": 251,
            "shootingPctg": 0.1195,
            "avgToi": "21:08",
            "faceoffWinningPctg": 0.4318,
            "sequence": 1,
        },
    ],
    "last5Games": [
        {
            "gameId": 2025020534,
            "gameDate": "2025-12-18",
            "opponentAbbrev": "BOS",
            "homeRoadFlag": "R",
            "teamAbbrev": "EDM",
            "goals": 1,
            "assists": 1,
            "points": 2,
            "plusMinus": 1,
            "pim": 0,
            "shots": 3,
            "toi": "22:56",
            "shifts": 24,
            "powerPlayGoals": 0,
            "shorthandedGoals": 1,
        },
        {
            "gameId": 2025020524,
            "gameDate": "2025-12-16",
            "opponentAbbrev": "PIT",
            "homeRoadFlag": "R",
            "teamAbbrev": "EDM",
            "goals": 2,
            "assists": 2,
            "points": 4,
            "plusMinus": 0,
            "pim": 0,
            "shots": 6,
            "toi": "22:31",
            "shifts": 17,
            "powerPlayGoals": 1,
            "shorthandedGoals": 0,
        },
    ],
}

# Sample goalie API response data for testing
SAMPLE_GOALIE_RESPONSE: dict[str, Any] = {
    "playerId": 8477424,
    "isActive": True,
    "currentTeamId": 18,
    "currentTeamAbbrev": "NSH",
    "firstName": {"default": "Juuse"},
    "lastName": {"default": "Saros"},
    "sweaterNumber": 74,
    "position": "G",
    "shootsCatches": "L",
    "heightInInches": 71,
    "heightInCentimeters": 180,
    "weightInPounds": 180,
    "weightInKilograms": 82,
    "birthDate": "1995-04-19",
    "birthCity": {"default": "Forssa"},
    "birthCountry": "FIN",
    "headshot": "https://assets.nhle.com/mugs/nhl/20252026/NSH/8477424.png",
    "heroImage": "https://assets.nhle.com/mugs/actionshots/1296x729/8477424.jpg",
    "draftDetails": {
        "year": 2013,
        "teamAbbrev": "NSH",
        "round": 4,
        "pickInRound": 8,
        "overallPick": 99,
    },
    "inTop100AllTime": 0,
    "inHHOF": 0,
    "careerTotals": {
        "regularSeason": {
            "gamesPlayed": 434,
            "gamesStarted": 417,
            "wins": 214,
            "losses": 161,
            "otLosses": 41,
            "shutouts": 27,
            "goalsAgainstAvg": 2.695504,
            "savePctg": 0.91334,
            "goalsAgainst": 1119,
            "shotsAgainst": 12901,
            "goals": 0,
            "assists": 8,
            "pim": 10,
            "timeOnIce": "24908:07",
        },
        "playoffs": {
            "gamesPlayed": 23,
            "gamesStarted": 16,
            "wins": 5,
            "losses": 11,
            "otLosses": 0,
            "shutouts": 0,
            "goalsAgainstAvg": 2.453231,
            "savePctg": 0.911458,
            "goalsAgainst": 51,
            "shotsAgainst": 576,
            "goals": 0,
            "assists": 1,
            "pim": 2,
            "timeOnIce": "1247:20",
        },
    },
    "seasonTotals": [
        {
            "season": 20162017,
            "gameTypeId": 2,
            "leagueAbbrev": "NHL",
            "teamName": {"default": "Nashville Predators"},
            "gamesPlayed": 21,
            "gamesStarted": 17,
            "wins": 10,
            "losses": 8,
            "otLosses": 2,
            "shutouts": 1,
            "goalsAgainst": 41,
            "goalsAgainstAvg": 2.35,
            "shotsAgainst": 478,
            "savePctg": 0.914,
            "timeOnIce": "1048:07",
            "sequence": 1,
        },
    ],
    "last5Games": [
        {
            "gameId": 2025020532,
            "gameDate": "2025-12-17",
            "opponentAbbrev": "CAR",
            "homeRoadFlag": "H",
            "teamAbbrev": "NSH",
            "decision": "L",
            "goalsAgainst": 3,
            "shotsAgainst": 36,
            "savePctg": 0.916667,
            "toi": "57:58",
            "gamesStarted": 1,
        },
        {
            "gameId": 2025020517,
            "gameDate": "2025-12-15",
            "opponentAbbrev": "STL",
            "homeRoadFlag": "R",
            "teamAbbrev": "NSH",
            "decision": "W",
            "goalsAgainst": 2,
            "shotsAgainst": 22,
            "savePctg": 0.909091,
            "toi": "60:00",
            "gamesStarted": 1,
        },
    ],
}

# Sample response for undrafted player
SAMPLE_UNDRAFTED_RESPONSE: dict[str, Any] = {
    **SAMPLE_SKATER_RESPONSE,
    "playerId": 8477999,
    "draftDetails": None,
}

# Sample response for inactive player
SAMPLE_INACTIVE_RESPONSE: dict[str, Any] = {
    **SAMPLE_SKATER_RESPONSE,
    "playerId": 8471675,
    "isActive": False,
    "currentTeamId": None,
    "currentTeamAbbrev": None,
    "inHHOF": 1,
    "inTop100AllTime": 1,
}


class TestPlayerLandingDownloaderConfig:
    """Tests for PlayerLandingDownloaderConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = PlayerLandingDownloaderConfig()

        assert config.base_url == "https://api-web.nhle.com"
        assert config.requests_per_second == 5.0
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.http_timeout == 30.0
        assert config.health_check_url == "/v1/schedule/now"
        assert config.include_raw_response is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = PlayerLandingDownloaderConfig(
            base_url="https://custom.api.com",
            requests_per_second=10.0,
            max_retries=5,
            include_raw_response=True,
        )

        assert config.base_url == "https://custom.api.com"
        assert config.requests_per_second == 10.0
        assert config.max_retries == 5
        assert config.include_raw_response is True


class TestDraftDetails:
    """Tests for DraftDetails dataclass."""

    def test_creation(self) -> None:
        """Test DraftDetails creation."""
        draft = DraftDetails(
            year=2015,
            team_abbrev="EDM",
            round=1,
            pick_in_round=1,
            overall_pick=1,
        )

        assert draft.year == 2015
        assert draft.team_abbrev == "EDM"
        assert draft.round == 1
        assert draft.pick_in_round == 1
        assert draft.overall_pick == 1

    def test_immutable(self) -> None:
        """Test that DraftDetails is immutable."""
        draft = DraftDetails(
            year=2015,
            team_abbrev="EDM",
            round=1,
            pick_in_round=1,
            overall_pick=1,
        )

        with pytest.raises(AttributeError):
            draft.year = 2016  # type: ignore[misc]


class TestSkaterCareerStats:
    """Tests for SkaterCareerStats dataclass."""

    def test_creation(self) -> None:
        """Test SkaterCareerStats creation."""
        stats = SkaterCareerStats(
            games_played=747,
            goals=382,
            assists=758,
            points=1140,
            plus_minus=170,
            pim=300,
            game_winning_goals=73,
            ot_goals=16,
            shots=2518,
            shooting_pct=0.1517,
            power_play_goals=93,
            power_play_points=388,
            shorthanded_goals=9,
            shorthanded_points=19,
            avg_toi="21:46",
            faceoff_winning_pct=0.4777,
        )

        assert stats.games_played == 747
        assert stats.goals == 382
        assert stats.points == 1140
        assert stats.avg_toi == "21:46"


class TestGoalieCareerStats:
    """Tests for GoalieCareerStats dataclass."""

    def test_creation(self) -> None:
        """Test GoalieCareerStats creation."""
        stats = GoalieCareerStats(
            games_played=434,
            games_started=417,
            wins=214,
            losses=161,
            ot_losses=41,
            shutouts=27,
            goals_against_avg=2.695504,
            save_pct=0.91334,
            goals_against=1119,
            shots_against=12901,
            goals=0,
            assists=8,
            pim=10,
            time_on_ice="24908:07",
        )

        assert stats.games_played == 434
        assert stats.wins == 214
        assert stats.save_pct == 0.91334
        assert stats.shutouts == 27


class TestSkaterSeasonStats:
    """Tests for SkaterSeasonStats dataclass."""

    def test_creation(self) -> None:
        """Test SkaterSeasonStats creation."""
        stats = SkaterSeasonStats(
            season=20162017,
            game_type_id=2,
            league_abbrev="NHL",
            team_name="Edmonton Oilers",
            games_played=82,
            goals=30,
            assists=70,
            points=100,
            plus_minus=27,
            pim=26,
            game_winning_goals=6,
            power_play_goals=3,
            shorthanded_goals=1,
            shots=251,
            shooting_pct=0.1195,
            avg_toi="21:08",
            faceoff_winning_pct=0.4318,
            sequence=1,
        )

        assert stats.season == 20162017
        assert stats.points == 100
        assert stats.team_name == "Edmonton Oilers"


class TestGoalieSeasonStats:
    """Tests for GoalieSeasonStats dataclass."""

    def test_creation(self) -> None:
        """Test GoalieSeasonStats creation."""
        stats = GoalieSeasonStats(
            season=20162017,
            game_type_id=2,
            league_abbrev="NHL",
            team_name="Nashville Predators",
            games_played=21,
            games_started=17,
            wins=10,
            losses=8,
            ot_losses=2,
            shutouts=1,
            goals_against=41,
            goals_against_avg=2.35,
            shots_against=478,
            save_pct=0.914,
            time_on_ice="1048:07",
            sequence=1,
        )

        assert stats.season == 20162017
        assert stats.wins == 10
        assert stats.save_pct == 0.914


class TestSkaterRecentGame:
    """Tests for SkaterRecentGame dataclass."""

    def test_creation(self) -> None:
        """Test SkaterRecentGame creation."""
        game = SkaterRecentGame(
            game_id=2025020534,
            game_date="2025-12-18",
            opponent_abbrev="BOS",
            home_road_flag="R",
            team_abbrev="EDM",
            goals=1,
            assists=1,
            points=2,
            plus_minus=1,
            pim=0,
            shots=3,
            toi="22:56",
            shifts=24,
            power_play_goals=0,
            shorthanded_goals=1,
        )

        assert game.game_id == 2025020534
        assert game.points == 2
        assert game.shorthanded_goals == 1


class TestGoalieRecentGame:
    """Tests for GoalieRecentGame dataclass."""

    def test_creation(self) -> None:
        """Test GoalieRecentGame creation."""
        game = GoalieRecentGame(
            game_id=2025020532,
            game_date="2025-12-17",
            opponent_abbrev="CAR",
            home_road_flag="H",
            team_abbrev="NSH",
            decision="L",
            goals_against=3,
            saves=33,
            shots_against=36,
            save_pct=0.916667,
            toi="57:58",
            games_started=1,
        )

        assert game.game_id == 2025020532
        assert game.decision == "L"
        assert game.saves == 33


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create a mock HTTP client."""
    client = AsyncMock(spec=HTTPClient)
    client._create_session = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_rate_limiter() -> MagicMock:
    """Create a mock rate limiter."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.wait = AsyncMock(return_value=0.0)
    return limiter


@pytest.fixture
def mock_retry_handler() -> MagicMock:
    """Create a mock retry handler."""
    handler = MagicMock(spec=RetryHandler)

    async def execute_passthrough(
        operation: Any, operation_name: str = "", source: str | None = None
    ) -> Any:
        return await operation()

    handler.execute = AsyncMock(side_effect=execute_passthrough)
    return handler


@pytest.fixture
def player_landing_config() -> PlayerLandingDownloaderConfig:
    """Create a test downloader config."""
    return PlayerLandingDownloaderConfig(
        requests_per_second=10.0,
        max_retries=2,
    )


@pytest.fixture
def mock_skater_response() -> MagicMock:
    """Create a mock successful HTTP response for skater."""
    response = MagicMock(spec=HTTPResponse)
    response.is_success = True
    response.is_rate_limited = False
    response.is_server_error = False
    response.json.return_value = SAMPLE_SKATER_RESPONSE
    return response


@pytest.fixture
def mock_goalie_response() -> MagicMock:
    """Create a mock successful HTTP response for goalie."""
    response = MagicMock(spec=HTTPResponse)
    response.is_success = True
    response.is_rate_limited = False
    response.is_server_error = False
    response.json.return_value = SAMPLE_GOALIE_RESPONSE
    return response


class TestPlayerLandingDownloaderInit:
    """Tests for PlayerLandingDownloader initialization."""

    def test_initialization(
        self, player_landing_config: PlayerLandingDownloaderConfig
    ) -> None:
        """Test basic initialization."""
        downloader = PlayerLandingDownloader(player_landing_config)

        assert downloader.config == player_landing_config
        assert downloader.source_name == "nhl_json_player_landing"
        assert downloader._player_ids == []
        assert downloader._http_client is None

    def test_initialization_with_player_ids(
        self, player_landing_config: PlayerLandingDownloaderConfig
    ) -> None:
        """Test initialization with player IDs."""
        player_ids = [8478402, 8479318, 8477492]
        downloader = PlayerLandingDownloader(
            player_landing_config, player_ids=player_ids
        )

        assert downloader._player_ids == player_ids

    def test_initialization_default_config(self) -> None:
        """Test initialization with default config."""
        downloader = PlayerLandingDownloader()

        assert downloader.config.base_url == "https://api-web.nhle.com"
        assert downloader.source_name == "nhl_json_player_landing"

    def test_set_player_ids(
        self, player_landing_config: PlayerLandingDownloaderConfig
    ) -> None:
        """Test setting player IDs."""
        downloader = PlayerLandingDownloader(player_landing_config)

        player_ids = [8478402, 8479318]
        downloader.set_player_ids(player_ids)

        assert downloader._player_ids == player_ids

    def test_set_player_ids_copies_list(
        self, player_landing_config: PlayerLandingDownloaderConfig
    ) -> None:
        """Test that set_player_ids copies the list."""
        downloader = PlayerLandingDownloader(player_landing_config)

        player_ids = [8478402, 8479318]
        downloader.set_player_ids(player_ids)

        # Modify original list
        player_ids.append(8477492)

        # Downloader should not be affected
        assert len(downloader._player_ids) == 2


@pytest.mark.asyncio
class TestPlayerLandingDownloaderDownloadPlayer:
    """Tests for PlayerLandingDownloader.download_player."""

    async def test_download_skater_success(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_skater_response: MagicMock,
    ) -> None:
        """Test successful skater download."""
        mock_http_client.get = AsyncMock(return_value=mock_skater_response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8478402)

        assert result.is_successful
        assert result.source == "nhl_json_player_landing"

        # Verify parsed data
        data = result.data
        assert data["player_id"] == 8478402
        assert data["full_name"] == "Connor McDavid"
        assert data["position"] == "C"
        assert data["is_goalie"] is False
        assert data["current_team_abbrev"] == "EDM"

    async def test_download_goalie_success(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_goalie_response: MagicMock,
    ) -> None:
        """Test successful goalie download."""
        mock_http_client.get = AsyncMock(return_value=mock_goalie_response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8477424)

        assert result.is_successful
        data = result.data
        assert data["player_id"] == 8477424
        assert data["full_name"] == "Juuse Saros"
        assert data["position"] == "G"
        assert data["is_goalie"] is True

    async def test_download_player_parses_career_stats(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_skater_response: MagicMock,
    ) -> None:
        """Test that career stats are parsed correctly."""
        mock_http_client.get = AsyncMock(return_value=mock_skater_response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8478402)

        data = result.data
        career = data["career_regular_season"]
        assert career["games_played"] == 747
        assert career["goals"] == 382
        assert career["assists"] == 758
        assert career["points"] == 1140

        playoffs = data["career_playoffs"]
        assert playoffs["games_played"] == 96
        assert playoffs["points"] == 150

    async def test_download_player_parses_season_stats(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_skater_response: MagicMock,
    ) -> None:
        """Test that season stats are parsed correctly."""
        mock_http_client.get = AsyncMock(return_value=mock_skater_response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8478402)

        data = result.data
        seasons = data["season_stats"]
        assert len(seasons) == 2

        first_season = seasons[0]
        assert first_season["season"] == 20152016
        assert first_season["games_played"] == 45
        assert first_season["points"] == 48

    async def test_download_player_parses_recent_games(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_skater_response: MagicMock,
    ) -> None:
        """Test that recent games are parsed correctly."""
        mock_http_client.get = AsyncMock(return_value=mock_skater_response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8478402)

        data = result.data
        games = data["last_5_games"]
        assert len(games) == 2

        first_game = games[0]
        assert first_game["game_id"] == 2025020534
        assert first_game["opponent_abbrev"] == "BOS"
        assert first_game["points"] == 2

    async def test_download_player_parses_draft_details(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_skater_response: MagicMock,
    ) -> None:
        """Test that draft details are parsed correctly."""
        mock_http_client.get = AsyncMock(return_value=mock_skater_response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8478402)

        data = result.data
        draft = data["draft_details"]
        assert draft["year"] == 2015
        assert draft["team_abbrev"] == "EDM"
        assert draft["round"] == 1
        assert draft["overall_pick"] == 1

    async def test_download_undrafted_player(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test parsing undrafted player."""
        response = MagicMock(spec=HTTPResponse)
        response.is_success = True
        response.is_rate_limited = False
        response.is_server_error = False
        response.json.return_value = SAMPLE_UNDRAFTED_RESPONSE
        mock_http_client.get = AsyncMock(return_value=response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8477999)

        data = result.data
        assert data["draft_details"] is None

    async def test_download_inactive_player(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test parsing inactive/retired player."""
        response = MagicMock(spec=HTTPResponse)
        response.is_success = True
        response.is_rate_limited = False
        response.is_server_error = False
        response.json.return_value = SAMPLE_INACTIVE_RESPONSE
        mock_http_client.get = AsyncMock(return_value=response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8471675)

        data = result.data
        assert data["is_active"] is False
        assert data["current_team_id"] is None
        assert data["in_hhof"] is True
        assert data["in_top_100_all_time"] is True

    async def test_download_player_http_error(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test download failure on HTTP error."""
        response = MagicMock(spec=HTTPResponse)
        response.is_success = False
        response.is_rate_limited = False
        response.is_server_error = False
        response.status = 404
        mock_http_client.get = AsyncMock(return_value=response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            with pytest.raises(DownloadError) as exc_info:
                await downloader.download_player(8478402)

        assert exc_info.value.source == "nhl_json_player_landing"
        assert "HTTP 404" in str(exc_info.value)
        assert "8478402" in str(exc_info.value)

    async def test_download_player_json_parse_error(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test download failure on JSON parse error."""
        response = MagicMock(spec=HTTPResponse)
        response.is_success = True
        response.is_rate_limited = False
        response.is_server_error = False
        response.json.side_effect = ValueError("Invalid JSON")
        mock_http_client.get = AsyncMock(return_value=response)

        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            with pytest.raises(DownloadError) as exc_info:
                await downloader.download_player(8478402)

        assert "landing JSON" in str(exc_info.value)

    async def test_download_player_includes_raw_response(
        self,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_skater_response: MagicMock,
    ) -> None:
        """Test including raw response in result."""
        config = PlayerLandingDownloaderConfig(include_raw_response=True)
        mock_http_client.get = AsyncMock(return_value=mock_skater_response)

        downloader = PlayerLandingDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_player(8478402)

        assert "_raw" in result.data
        assert result.data["_raw"] == SAMPLE_SKATER_RESPONSE


@pytest.mark.asyncio
class TestPlayerLandingDownloaderDownloadAll:
    """Tests for PlayerLandingDownloader.download_all."""

    async def test_download_all_success(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_skater_response: MagicMock,
    ) -> None:
        """Test successful batch download."""
        mock_http_client.get = AsyncMock(return_value=mock_skater_response)

        player_ids = [8478402, 8479318, 8477492]
        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
            player_ids=player_ids,
        )

        async with downloader:
            results = [r async for r in downloader.download_all()]

        assert len(results) == 3
        assert all(r.is_successful for r in results)

    async def test_download_all_no_player_ids(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test batch download with no player IDs."""
        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
        )

        async with downloader:
            results = [r async for r in downloader.download_all()]

        assert len(results) == 0

    async def test_download_all_with_failures(
        self,
        player_landing_config: PlayerLandingDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test batch download with some failures."""
        success_response = MagicMock(spec=HTTPResponse)
        success_response.is_success = True
        success_response.is_rate_limited = False
        success_response.is_server_error = False
        success_response.json.return_value = SAMPLE_SKATER_RESPONSE

        failure_response = MagicMock(spec=HTTPResponse)
        failure_response.is_success = False
        failure_response.is_rate_limited = False
        failure_response.is_server_error = False
        failure_response.status = 404

        # First call succeeds, second fails, third succeeds
        mock_http_client.get = AsyncMock(
            side_effect=[success_response, failure_response, success_response]
        )

        player_ids = [8478402, 8479318, 8477492]
        downloader = PlayerLandingDownloader(
            player_landing_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
            player_ids=player_ids,
        )

        async with downloader:
            results = [r async for r in downloader.download_all()]

        assert len(results) == 3
        assert results[0].is_successful
        assert not results[1].is_successful
        assert results[2].is_successful


class TestPlayerLandingDownloaderParsing:
    """Tests for PlayerLandingDownloader parsing methods."""

    def test_get_localized_with_dict(self) -> None:
        """Test _get_localized with dictionary input."""
        downloader = PlayerLandingDownloader()

        result = downloader._get_localized({"default": "Edmonton"})
        assert result == "Edmonton"

    def test_get_localized_with_string(self) -> None:
        """Test _get_localized with string input."""
        downloader = PlayerLandingDownloader()

        result = downloader._get_localized("Edmonton")
        assert result == "Edmonton"

    def test_get_localized_with_none(self) -> None:
        """Test _get_localized with None input."""
        downloader = PlayerLandingDownloader()

        result = downloader._get_localized(None)
        assert result == ""

    def test_parse_skater_career_stats(self) -> None:
        """Test _parse_skater_career_stats method."""
        downloader = PlayerLandingDownloader()

        data = {
            "gamesPlayed": 747,
            "goals": 382,
            "assists": 758,
            "points": 1140,
            "plusMinus": 170,
            "pim": 300,
            "gameWinningGoals": 73,
            "otGoals": 16,
            "shots": 2518,
            "shootingPctg": 0.1517,
            "powerPlayGoals": 93,
            "powerPlayPoints": 388,
            "shorthandedGoals": 9,
            "shorthandedPoints": 19,
            "avgToi": "21:46",
            "faceoffWinningPctg": 0.4777,
        }

        result = downloader._parse_skater_career_stats(data)

        assert result.games_played == 747
        assert result.goals == 382
        assert result.points == 1140
        assert result.avg_toi == "21:46"

    def test_parse_goalie_career_stats(self) -> None:
        """Test _parse_goalie_career_stats method."""
        downloader = PlayerLandingDownloader()

        data = {
            "gamesPlayed": 434,
            "gamesStarted": 417,
            "wins": 214,
            "losses": 161,
            "otLosses": 41,
            "shutouts": 27,
            "goalsAgainstAvg": 2.695504,
            "savePctg": 0.91334,
            "goalsAgainst": 1119,
            "shotsAgainst": 12901,
            "goals": 0,
            "assists": 8,
            "pim": 10,
            "timeOnIce": "24908:07",
        }

        result = downloader._parse_goalie_career_stats(data)

        assert result.games_played == 434
        assert result.wins == 214
        assert result.save_pct == 0.91334

    def test_parse_skater_season_stats(self) -> None:
        """Test _parse_skater_season_stats method."""
        downloader = PlayerLandingDownloader()

        data = {
            "season": 20162017,
            "gameTypeId": 2,
            "leagueAbbrev": "NHL",
            "teamName": {"default": "Edmonton Oilers"},
            "gamesPlayed": 82,
            "goals": 30,
            "assists": 70,
            "points": 100,
            "plusMinus": 27,
            "pim": 26,
            "gameWinningGoals": 6,
            "sequence": 1,
        }

        result = downloader._parse_skater_season_stats(data)

        assert result.season == 20162017
        assert result.team_name == "Edmonton Oilers"
        assert result.points == 100

    def test_parse_goalie_season_stats(self) -> None:
        """Test _parse_goalie_season_stats method."""
        downloader = PlayerLandingDownloader()

        data = {
            "season": 20162017,
            "gameTypeId": 2,
            "leagueAbbrev": "NHL",
            "teamName": {"default": "Nashville Predators"},
            "gamesPlayed": 21,
            "gamesStarted": 17,
            "wins": 10,
            "losses": 8,
            "otLosses": 2,
            "shutouts": 1,
            "sequence": 1,
        }

        result = downloader._parse_goalie_season_stats(data)

        assert result.season == 20162017
        assert result.team_name == "Nashville Predators"
        assert result.wins == 10

    def test_parse_skater_recent_game(self) -> None:
        """Test _parse_skater_recent_game method."""
        downloader = PlayerLandingDownloader()

        data = {
            "gameId": 2025020534,
            "gameDate": "2025-12-18",
            "opponentAbbrev": "BOS",
            "homeRoadFlag": "R",
            "teamAbbrev": "EDM",
            "goals": 1,
            "assists": 1,
            "points": 2,
            "plusMinus": 1,
            "pim": 0,
            "shots": 3,
            "toi": "22:56",
            "shifts": 24,
            "powerPlayGoals": 0,
            "shorthandedGoals": 1,
        }

        result = downloader._parse_skater_recent_game(data)

        assert result.game_id == 2025020534
        assert result.points == 2
        assert result.shorthanded_goals == 1

    def test_parse_goalie_recent_game(self) -> None:
        """Test _parse_goalie_recent_game method."""
        downloader = PlayerLandingDownloader()

        data = {
            "gameId": 2025020532,
            "gameDate": "2025-12-17",
            "opponentAbbrev": "CAR",
            "homeRoadFlag": "H",
            "teamAbbrev": "NSH",
            "decision": "L",
            "goalsAgainst": 3,
            "shotsAgainst": 36,
            "savePctg": 0.916667,
            "toi": "57:58",
            "gamesStarted": 1,
        }

        result = downloader._parse_goalie_recent_game(data)

        assert result.game_id == 2025020532
        assert result.decision == "L"
        assert result.saves == 33  # 36 - 3
        assert result.shots_against == 36

    def test_parse_player_landing_skater(self) -> None:
        """Test full parsing for skater."""
        downloader = PlayerLandingDownloader()

        result = downloader._parse_player_landing(SAMPLE_SKATER_RESPONSE)

        assert result.player_id == 8478402
        assert result.full_name == "Connor McDavid"
        assert result.position == "C"
        assert result.is_goalie is False
        assert result.current_team_abbrev == "EDM"
        assert result.draft_details is not None
        assert result.draft_details.overall_pick == 1

    def test_parse_player_landing_goalie(self) -> None:
        """Test full parsing for goalie."""
        downloader = PlayerLandingDownloader()

        result = downloader._parse_player_landing(SAMPLE_GOALIE_RESPONSE)

        assert result.player_id == 8477424
        assert result.full_name == "Juuse Saros"
        assert result.position == "G"
        assert result.is_goalie is True
        assert result.current_team_abbrev == "NSH"

    def test_player_to_dict(self) -> None:
        """Test converting ParsedPlayerLanding to dictionary."""
        downloader = PlayerLandingDownloader()

        player = ParsedPlayerLanding(
            player_id=8478402,
            is_active=True,
            first_name="Connor",
            last_name="McDavid",
            full_name="Connor McDavid",
            current_team_id=22,
            current_team_abbrev="EDM",
            sweater_number=97,
            position="C",
            shoots_catches="L",
            height_inches=73,
            height_cm=185,
            weight_lbs=194,
            weight_kg=88,
            birth_date="1997-01-13",
            birth_city="Richmond Hill",
            birth_state_province="Ontario",
            birth_country="CAN",
            headshot_url="https://example.com/headshot.png",
            hero_image_url="https://example.com/hero.jpg",
            draft_details=DraftDetails(
                year=2015,
                team_abbrev="EDM",
                round=1,
                pick_in_round=1,
                overall_pick=1,
            ),
            in_top_100_all_time=False,
            in_hhof=False,
            is_goalie=False,
        )

        result = downloader._player_to_dict(player)

        assert result["player_id"] == 8478402
        assert result["full_name"] == "Connor McDavid"
        assert result["current_team_abbrev"] == "EDM"
        assert result["draft_details"]["overall_pick"] == 1
        assert result["is_goalie"] is False
