"""Tests for the BoxscoreDownloader."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.base.protocol import DownloadError, DownloadStatus
from nhl_api.downloaders.base.rate_limiter import RateLimiter
from nhl_api.downloaders.base.retry_handler import RetryHandler
from nhl_api.downloaders.sources.nhl_json.boxscore import (
    BoxscoreDownloader,
    BoxscoreDownloaderConfig,
    GoalieStats,
    ParsedBoxscore,
    SkaterStats,
    TeamBoxscore,
)
from nhl_api.utils.http_client import HTTPClient, HTTPResponse

# Sample API response data for testing
SAMPLE_BOXSCORE_RESPONSE: dict[str, Any] = {
    "id": 2024020500,
    "season": 20242025,
    "gameType": 2,
    "gameDate": "2024-12-15",
    "gameState": "OFF",
    "venue": {"default": "Scotiabank Arena"},
    "gameOutcome": {"lastPeriodType": "REG"},
    "homeTeam": {
        "id": 10,
        "abbrev": "TOR",
        "commonName": {"default": "Maple Leafs"},
        "score": 4,
        "sog": 32,
    },
    "awayTeam": {
        "id": 8,
        "abbrev": "MTL",
        "commonName": {"default": "Canadiens"},
        "score": 2,
        "sog": 28,
    },
    "playerByGameStats": {
        "homeTeam": {
            "forwards": [
                {
                    "playerId": 8478483,
                    "name": {"default": "Auston Matthews"},
                    "sweaterNumber": 34,
                    "position": "C",
                    "goals": 2,
                    "assists": 1,
                    "points": 3,
                    "plusMinus": 2,
                    "pim": 0,
                    "sog": 5,
                    "hits": 2,
                    "blockedShots": 0,
                    "giveaways": 1,
                    "takeaways": 2,
                    "faceoffWinningPctg": 55.5,
                    "toi": "22:15",
                    "shifts": 28,
                    "powerPlayGoals": 1,
                    "shorthandedGoals": 0,
                },
            ],
            "defense": [
                {
                    "playerId": 8477939,
                    "name": {"default": "Morgan Rielly"},
                    "sweaterNumber": 44,
                    "position": "D",
                    "goals": 0,
                    "assists": 2,
                    "points": 2,
                    "plusMinus": 1,
                    "pim": 2,
                    "sog": 3,
                    "hits": 1,
                    "blockedShots": 3,
                    "giveaways": 0,
                    "takeaways": 1,
                    "faceoffWinningPctg": 0.0,
                    "toi": "24:30",
                    "shifts": 30,
                    "powerPlayGoals": 0,
                    "shorthandedGoals": 0,
                },
            ],
            "goalies": [
                {
                    "playerId": 8479361,
                    "name": {"default": "Joseph Woll"},
                    "sweaterNumber": 60,
                    "saveShotsAgainst": "26/28",
                    "goalsAgainst": 2,
                    "savePctg": 0.929,
                    "toi": "60:00",
                    "evenStrengthShotsAgainst": "20/21",
                    "powerPlayShotsAgainst": "4/5",
                    "shorthandedShotsAgainst": "2/2",
                    "starter": True,
                    "decision": "W",
                },
            ],
        },
        "awayTeam": {
            "forwards": [
                {
                    "playerId": 8478402,
                    "name": {"default": "Nick Suzuki"},
                    "sweaterNumber": 14,
                    "position": "C",
                    "goals": 1,
                    "assists": 0,
                    "points": 1,
                    "plusMinus": -1,
                    "pim": 0,
                    "sog": 4,
                    "hits": 1,
                    "blockedShots": 1,
                    "giveaways": 2,
                    "takeaways": 0,
                    "faceoffWinningPctg": 48.0,
                    "toi": "21:45",
                    "shifts": 27,
                    "powerPlayGoals": 0,
                    "shorthandedGoals": 0,
                },
            ],
            "defense": [],
            "goalies": [
                {
                    "playerId": 8480382,
                    "name": {"default": "Samuel Montembeault"},
                    "sweaterNumber": 35,
                    "saveShotsAgainst": "28/32",
                    "goalsAgainst": 4,
                    "savePctg": 0.875,
                    "toi": "58:30",
                    "evenStrengthShotsAgainst": "22/24",
                    "powerPlayShotsAgainst": "4/6",
                    "shorthandedShotsAgainst": "2/2",
                    "starter": True,
                    "decision": "L",
                },
            ],
        },
    },
}

SAMPLE_OT_RESPONSE: dict[str, Any] = {
    **SAMPLE_BOXSCORE_RESPONSE,
    "gameOutcome": {"lastPeriodType": "OT"},
}

SAMPLE_SO_RESPONSE: dict[str, Any] = {
    **SAMPLE_BOXSCORE_RESPONSE,
    "gameOutcome": {"lastPeriodType": "SO"},
}


class TestBoxscoreDownloaderConfig:
    """Tests for BoxscoreDownloaderConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = BoxscoreDownloaderConfig()

        assert config.base_url == "https://api-web.nhle.com"
        assert config.requests_per_second == 5.0
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.http_timeout == 30.0
        assert config.health_check_url == "/v1/schedule/now"
        assert config.include_raw_response is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = BoxscoreDownloaderConfig(
            base_url="https://custom.api.com",
            requests_per_second=10.0,
            max_retries=5,
            include_raw_response=True,
        )

        assert config.base_url == "https://custom.api.com"
        assert config.requests_per_second == 10.0
        assert config.max_retries == 5
        assert config.include_raw_response is True


class TestTeamBoxscore:
    """Tests for TeamBoxscore dataclass."""

    def test_creation(self) -> None:
        """Test TeamBoxscore creation."""
        team = TeamBoxscore(
            team_id=10,
            abbrev="TOR",
            name="Maple Leafs",
            score=4,
            shots_on_goal=32,
            is_home=True,
        )

        assert team.team_id == 10
        assert team.abbrev == "TOR"
        assert team.name == "Maple Leafs"
        assert team.score == 4
        assert team.shots_on_goal == 32
        assert team.is_home is True

    def test_immutable(self) -> None:
        """Test that TeamBoxscore is immutable."""
        team = TeamBoxscore(
            team_id=10,
            abbrev="TOR",
            name="Maple Leafs",
            score=4,
            shots_on_goal=32,
            is_home=True,
        )

        with pytest.raises(AttributeError):
            team.score = 5  # type: ignore[misc]


class TestSkaterStats:
    """Tests for SkaterStats dataclass."""

    def test_creation(self) -> None:
        """Test SkaterStats creation."""
        skater = SkaterStats(
            player_id=8478483,
            name="Auston Matthews",
            sweater_number=34,
            position="C",
            goals=2,
            assists=1,
            points=3,
            plus_minus=2,
            pim=0,
            shots=5,
            hits=2,
            blocked_shots=0,
            giveaways=1,
            takeaways=2,
            faceoff_pct=55.5,
            toi="22:15",
            shifts=28,
            power_play_goals=1,
            shorthanded_goals=0,
            team_id=10,
        )

        assert skater.player_id == 8478483
        assert skater.name == "Auston Matthews"
        assert skater.goals == 2
        assert skater.assists == 1
        assert skater.points == 3
        assert skater.toi == "22:15"


class TestGoalieStats:
    """Tests for GoalieStats dataclass."""

    def test_creation(self) -> None:
        """Test GoalieStats creation."""
        goalie = GoalieStats(
            player_id=8479361,
            name="Joseph Woll",
            sweater_number=60,
            saves=26,
            shots_against=28,
            goals_against=2,
            save_pct=0.929,
            toi="60:00",
            even_strength_shots_against="20/21",
            power_play_shots_against="4/5",
            shorthanded_shots_against="2/2",
            is_starter=True,
            decision="W",
            team_id=10,
        )

        assert goalie.player_id == 8479361
        assert goalie.name == "Joseph Woll"
        assert goalie.saves == 26
        assert goalie.save_pct == 0.929
        assert goalie.decision == "W"


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
def boxscore_config() -> BoxscoreDownloaderConfig:
    """Create a test downloader config."""
    return BoxscoreDownloaderConfig(
        requests_per_second=10.0,
        max_retries=2,
    )


@pytest.fixture
def mock_success_response() -> MagicMock:
    """Create a mock successful HTTP response."""
    response = MagicMock(spec=HTTPResponse)
    response.is_success = True
    response.is_rate_limited = False
    response.is_server_error = False
    response.json.return_value = SAMPLE_BOXSCORE_RESPONSE
    return response


class TestBoxscoreDownloaderInit:
    """Tests for BoxscoreDownloader initialization."""

    def test_initialization(self, boxscore_config: BoxscoreDownloaderConfig) -> None:
        """Test basic initialization."""
        downloader = BoxscoreDownloader(boxscore_config)

        assert downloader.config == boxscore_config
        assert downloader.source_name == "nhl_json_boxscore"
        assert downloader._game_ids == []
        assert downloader._http_client is None

    def test_initialization_with_game_ids(
        self, boxscore_config: BoxscoreDownloaderConfig
    ) -> None:
        """Test initialization with game IDs."""
        game_ids = [2024020001, 2024020002, 2024020003]
        downloader = BoxscoreDownloader(boxscore_config, game_ids=game_ids)

        assert downloader._game_ids == game_ids

    def test_initialization_default_config(self) -> None:
        """Test initialization with default config."""
        downloader = BoxscoreDownloader()

        assert downloader.config.base_url == "https://api-web.nhle.com"
        assert downloader.source_name == "nhl_json_boxscore"

    def test_set_game_ids(self, boxscore_config: BoxscoreDownloaderConfig) -> None:
        """Test setting game IDs."""
        downloader = BoxscoreDownloader(boxscore_config)

        game_ids = [2024020001, 2024020002]
        downloader.set_game_ids(game_ids)

        assert downloader._game_ids == game_ids

    def test_set_game_ids_copies_list(
        self, boxscore_config: BoxscoreDownloaderConfig
    ) -> None:
        """Test that set_game_ids copies the list."""
        downloader = BoxscoreDownloader(boxscore_config)

        game_ids = [2024020001, 2024020002]
        downloader.set_game_ids(game_ids)

        # Modify original list
        game_ids.append(2024020003)

        # Downloader should not be affected
        assert len(downloader._game_ids) == 2


@pytest.mark.asyncio
class TestBoxscoreDownloaderDownloadGame:
    """Tests for BoxscoreDownloader.download_game."""

    async def test_download_game_success(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_success_response: MagicMock,
    ) -> None:
        """Test successful game download."""
        mock_http_client.get = AsyncMock(return_value=mock_success_response)

        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_game(2024020500)

        assert result.is_successful
        assert result.game_id == 2024020500
        assert result.source == "nhl_json_boxscore"
        assert result.status == DownloadStatus.COMPLETED

        # Verify parsed data
        data = result.data
        assert data["game_id"] == 2024020500
        assert data["season_id"] == 20242025
        assert data["home_team"]["abbrev"] == "TOR"
        assert data["home_team"]["score"] == 4
        assert data["away_team"]["abbrev"] == "MTL"
        assert data["away_team"]["score"] == 2

    async def test_download_game_parses_skaters(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_success_response: MagicMock,
    ) -> None:
        """Test that skater stats are parsed correctly."""
        mock_http_client.get = AsyncMock(return_value=mock_success_response)

        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_game(2024020500)

        data = result.data

        # Check home skaters (forwards + defense)
        assert len(data["home_skaters"]) == 2
        matthews = data["home_skaters"][0]
        assert matthews["player_id"] == 8478483
        assert matthews["name"] == "Auston Matthews"
        assert matthews["goals"] == 2
        assert matthews["assists"] == 1
        assert matthews["power_play_goals"] == 1

        rielly = data["home_skaters"][1]
        assert rielly["player_id"] == 8477939
        assert rielly["position"] == "D"

    async def test_download_game_parses_goalies(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_success_response: MagicMock,
    ) -> None:
        """Test that goalie stats are parsed correctly."""
        mock_http_client.get = AsyncMock(return_value=mock_success_response)

        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_game(2024020500)

        data = result.data

        # Check home goalie
        assert len(data["home_goalies"]) == 1
        woll = data["home_goalies"][0]
        assert woll["player_id"] == 8479361
        assert woll["name"] == "Joseph Woll"
        assert woll["saves"] == 26
        assert woll["shots_against"] == 28
        assert woll["save_pct"] == 0.929
        assert woll["decision"] == "W"
        assert woll["is_starter"] is True

    async def test_download_game_overtime(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test parsing overtime game."""
        response = MagicMock(spec=HTTPResponse)
        response.is_success = True
        response.is_rate_limited = False
        response.is_server_error = False
        response.json.return_value = SAMPLE_OT_RESPONSE
        mock_http_client.get = AsyncMock(return_value=response)

        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_game(2024020500)

        data = result.data
        assert data["is_overtime"] is True
        assert data["is_shootout"] is False

    async def test_download_game_shootout(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test parsing shootout game."""
        response = MagicMock(spec=HTTPResponse)
        response.is_success = True
        response.is_rate_limited = False
        response.is_server_error = False
        response.json.return_value = SAMPLE_SO_RESPONSE
        mock_http_client.get = AsyncMock(return_value=response)

        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_game(2024020500)

        data = result.data
        assert data["is_overtime"] is True
        assert data["is_shootout"] is True

    async def test_download_game_http_error(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
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

        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            with pytest.raises(DownloadError) as exc_info:
                await downloader.download_game(2024020500)

        assert exc_info.value.game_id == 2024020500
        assert exc_info.value.source == "nhl_json_boxscore"
        assert "HTTP 404" in str(exc_info.value)

    async def test_download_game_json_parse_error(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
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

        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            with pytest.raises(DownloadError) as exc_info:
                await downloader.download_game(2024020500)

        assert "parse boxscore JSON" in str(exc_info.value)

    async def test_download_game_includes_raw_response(
        self,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_success_response: MagicMock,
    ) -> None:
        """Test including raw response in result."""
        config = BoxscoreDownloaderConfig(include_raw_response=True)
        mock_http_client.get = AsyncMock(return_value=mock_success_response)

        downloader = BoxscoreDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            result = await downloader.download_game(2024020500)

        assert "_raw" in result.data
        assert result.data["_raw"] == SAMPLE_BOXSCORE_RESPONSE


@pytest.mark.asyncio
class TestBoxscoreDownloaderDownloadSeason:
    """Tests for BoxscoreDownloader.download_season."""

    async def test_download_season_success(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_success_response: MagicMock,
    ) -> None:
        """Test successful season download."""
        mock_http_client.get = AsyncMock(return_value=mock_success_response)

        game_ids = [2024020001, 2024020002, 2024020003]
        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
            game_ids=game_ids,
        )

        async with downloader:
            results = [r async for r in downloader.download_season(20242025)]

        assert len(results) == 3
        assert all(r.is_successful for r in results)

    async def test_download_season_no_game_ids(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test season download with no game IDs."""
        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
        )

        async with downloader:
            results = [r async for r in downloader.download_season(20242025)]

        assert len(results) == 0

    async def test_download_season_progress_callback(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
        mock_success_response: MagicMock,
    ) -> None:
        """Test progress callback is called during season download."""
        mock_http_client.get = AsyncMock(return_value=mock_success_response)
        callback = MagicMock()

        game_ids = [2024020001, 2024020002]
        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
            game_ids=game_ids,
            progress_callback=callback,
        )

        async with downloader:
            _ = [r async for r in downloader.download_season(20242025)]

        assert callback.call_count == 2

    async def test_download_season_with_failures(
        self,
        boxscore_config: BoxscoreDownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test season download with some failures."""
        success_response = MagicMock(spec=HTTPResponse)
        success_response.is_success = True
        success_response.is_rate_limited = False
        success_response.is_server_error = False
        success_response.json.return_value = SAMPLE_BOXSCORE_RESPONSE

        failure_response = MagicMock(spec=HTTPResponse)
        failure_response.is_success = False
        failure_response.is_rate_limited = False
        failure_response.is_server_error = False
        failure_response.status = 404

        # First call succeeds, second fails, third succeeds
        mock_http_client.get = AsyncMock(
            side_effect=[success_response, failure_response, success_response]
        )

        game_ids = [2024020001, 2024020002, 2024020003]
        downloader = BoxscoreDownloader(
            boxscore_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
            game_ids=game_ids,
        )

        async with downloader:
            results = [r async for r in downloader.download_season(20242025)]

        assert len(results) == 3
        assert results[0].is_successful
        assert not results[1].is_successful
        assert results[1].status == DownloadStatus.FAILED
        assert results[2].is_successful


class TestBoxscoreDownloaderParsing:
    """Tests for BoxscoreDownloader parsing methods."""

    def test_parse_team(self) -> None:
        """Test _parse_team method."""
        downloader = BoxscoreDownloader()

        team_data = {
            "id": 10,
            "abbrev": "TOR",
            "commonName": {"default": "Maple Leafs"},
            "score": 4,
            "sog": 32,
        }

        result = downloader._parse_team(team_data, is_home=True)

        assert result.team_id == 10
        assert result.abbrev == "TOR"
        assert result.name == "Maple Leafs"
        assert result.score == 4
        assert result.shots_on_goal == 32
        assert result.is_home is True

    def test_parse_team_missing_fields(self) -> None:
        """Test _parse_team with missing fields uses defaults."""
        downloader = BoxscoreDownloader()

        team_data: dict[str, Any] = {}
        result = downloader._parse_team(team_data, is_home=False)

        assert result.team_id == 0
        assert result.abbrev == ""
        assert result.name == ""
        assert result.score == 0
        assert result.shots_on_goal == 0

    def test_parse_single_skater(self) -> None:
        """Test _parse_single_skater method."""
        downloader = BoxscoreDownloader()

        player_data = {
            "playerId": 8478483,
            "name": {"default": "Auston Matthews"},
            "sweaterNumber": 34,
            "position": "C",
            "goals": 2,
            "assists": 1,
            "points": 3,
            "plusMinus": 2,
            "pim": 0,
            "sog": 5,
            "hits": 2,
            "blockedShots": 0,
            "giveaways": 1,
            "takeaways": 2,
            "faceoffWinningPctg": 55.5,
            "toi": "22:15",
            "shifts": 28,
            "powerPlayGoals": 1,
            "shorthandedGoals": 0,
        }

        result = downloader._parse_single_skater(player_data, team_id=10)

        assert result.player_id == 8478483
        assert result.name == "Auston Matthews"
        assert result.goals == 2
        assert result.team_id == 10

    def test_parse_single_goalie(self) -> None:
        """Test _parse_single_goalie method."""
        downloader = BoxscoreDownloader()

        player_data = {
            "playerId": 8479361,
            "name": {"default": "Joseph Woll"},
            "sweaterNumber": 60,
            "saveShotsAgainst": "26/28",
            "goalsAgainst": 2,
            "savePctg": 0.929,
            "toi": "60:00",
            "evenStrengthShotsAgainst": "20/21",
            "powerPlayShotsAgainst": "4/5",
            "shorthandedShotsAgainst": "2/2",
            "starter": True,
            "decision": "W",
        }

        result = downloader._parse_single_goalie(player_data, team_id=10)

        assert result.player_id == 8479361
        assert result.name == "Joseph Woll"
        assert result.saves == 26
        assert result.shots_against == 28
        assert result.is_starter is True
        assert result.decision == "W"
        assert result.team_id == 10

    def test_parse_goalie_saves_format(self) -> None:
        """Test parsing different save formats."""
        downloader = BoxscoreDownloader()

        # Test "saves/shots" format
        player_data = {
            "playerId": 1,
            "name": {"default": "Test Goalie"},
            "sweaterNumber": 30,
            "saveShotsAgainst": "30/35",
            "goalsAgainst": 5,
            "savePctg": 0.857,
            "toi": "60:00",
        }

        result = downloader._parse_single_goalie(player_data, team_id=1)
        assert result.saves == 30
        assert result.shots_against == 35

    def test_parse_boxscore_regular_game(self) -> None:
        """Test full boxscore parsing for regular game."""
        downloader = BoxscoreDownloader()

        result = downloader._parse_boxscore(SAMPLE_BOXSCORE_RESPONSE, 2024020500)

        assert result.game_id == 2024020500
        assert result.season_id == 20242025
        assert result.game_date == "2024-12-15"
        assert result.game_state == "OFF"
        assert result.venue_name == "Scotiabank Arena"
        assert result.is_overtime is False
        assert result.is_shootout is False

        assert result.home_team.abbrev == "TOR"
        assert result.away_team.abbrev == "MTL"

        assert len(result.home_skaters) == 2
        assert len(result.away_skaters) == 1
        assert len(result.home_goalies) == 1
        assert len(result.away_goalies) == 1

    def test_boxscore_to_dict(self) -> None:
        """Test converting ParsedBoxscore to dictionary."""
        downloader = BoxscoreDownloader()

        boxscore = ParsedBoxscore(
            game_id=2024020500,
            season_id=20242025,
            game_date="2024-12-15",
            game_type=2,
            game_state="OFF",
            home_team=TeamBoxscore(
                team_id=10,
                abbrev="TOR",
                name="Maple Leafs",
                score=4,
                shots_on_goal=32,
                is_home=True,
            ),
            away_team=TeamBoxscore(
                team_id=8,
                abbrev="MTL",
                name="Canadiens",
                score=2,
                shots_on_goal=28,
                is_home=False,
            ),
            home_skaters=[],
            away_skaters=[],
            home_goalies=[],
            away_goalies=[],
            venue_name="Scotiabank Arena",
            is_overtime=False,
            is_shootout=False,
        )

        result = downloader._boxscore_to_dict(boxscore)

        assert result["game_id"] == 2024020500
        assert result["home_team"]["abbrev"] == "TOR"
        assert result["away_team"]["score"] == 2
        assert result["venue_name"] == "Scotiabank Arena"
