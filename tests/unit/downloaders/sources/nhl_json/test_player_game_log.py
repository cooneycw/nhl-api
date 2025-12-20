"""Tests for Player Game Log Downloader."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.nhl_json.player_game_log import (
    PLAYOFFS,
    REGULAR_SEASON,
    GoalieGameStats,
    ParsedPlayerGameLog,
    PlayerGameLogDownloader,
    PlayerGameLogDownloaderConfig,
    SkaterGameStats,
    _get_localized,
    _parse_date,
    create_player_game_log_downloader,
)

# Sample skater game data for testing
SAMPLE_SKATER_GAME = {
    "gameId": 2024020500,
    "gameDate": "2025-01-15",
    "teamAbbrev": "EDM",
    "opponentAbbrev": "CGY",
    "homeRoadFlag": "H",
    "goals": 2,
    "assists": 1,
    "points": 3,
    "plusMinus": 2,
    "pim": 0,
    "shots": 5,
    "shifts": 28,
    "toi": "22:15",
    "powerPlayGoals": 1,
    "powerPlayPoints": 2,
    "shorthandedGoals": 0,
    "shorthandedPoints": 0,
    "gameWinningGoals": 1,
    "otGoals": 0,
}

SAMPLE_GOALIE_GAME = {
    "gameId": 2024020501,
    "gameDate": "2025-01-16",
    "teamAbbrev": "NSH",
    "opponentAbbrev": "COL",
    "homeRoadFlag": "R",
    "gamesStarted": 1,
    "decision": "W",
    "shotsAgainst": 32,
    "goalsAgainst": 2,
    "savePctg": 0.938,
    "shutouts": 0,
    "toi": "60:00",
    "goals": 0,
    "assists": 0,
    "pim": 0,
}

SAMPLE_SKATER_RESPONSE = {
    "gameLog": [SAMPLE_SKATER_GAME],
}

SAMPLE_GOALIE_RESPONSE = {
    "gameLog": [SAMPLE_GOALIE_GAME],
}


@pytest.mark.unit
class TestPlayerGameLogDownloaderConfig:
    """Tests for PlayerGameLogDownloaderConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = PlayerGameLogDownloaderConfig()
        assert config.base_url == "https://api-web.nhle.com"
        assert config.requests_per_second == 5.0
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.http_timeout == 30.0
        assert config.include_raw_response is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = PlayerGameLogDownloaderConfig(
            base_url="https://custom.api.com",
            requests_per_second=10.0,
            max_retries=5,
            include_raw_response=True,
        )
        assert config.base_url == "https://custom.api.com"
        assert config.requests_per_second == 10.0
        assert config.max_retries == 5
        assert config.include_raw_response is True


@pytest.mark.unit
class TestSkaterGameStats:
    """Tests for SkaterGameStats dataclass."""

    def test_creation(self) -> None:
        """Test creating SkaterGameStats."""
        game = SkaterGameStats(
            game_id=2024020500,
            game_date=date(2025, 1, 15),
            team_abbrev="EDM",
            opponent_abbrev="CGY",
            home_road_flag="H",
            goals=2,
            assists=1,
            points=3,
            plus_minus=2,
            pim=0,
            shots=5,
            shifts=28,
            toi="22:15",
            power_play_goals=1,
            power_play_points=2,
            shorthanded_goals=0,
            shorthanded_points=0,
            game_winning_goals=1,
            ot_goals=0,
        )
        assert game.game_id == 2024020500
        assert game.goals == 2
        assert game.assists == 1
        assert game.points == 3
        assert game.toi == "22:15"

    def test_immutable(self) -> None:
        """Test that SkaterGameStats is immutable."""
        game = SkaterGameStats(
            game_id=2024020500,
            game_date=date(2025, 1, 15),
            team_abbrev="EDM",
            opponent_abbrev="CGY",
            home_road_flag="H",
            goals=2,
            assists=1,
            points=3,
            plus_minus=2,
            pim=0,
            shots=5,
            shifts=28,
            toi="22:15",
            power_play_goals=1,
            power_play_points=2,
            shorthanded_goals=0,
            shorthanded_points=0,
            game_winning_goals=1,
            ot_goals=0,
        )
        with pytest.raises(AttributeError):
            game.goals = 5  # type: ignore[misc]


@pytest.mark.unit
class TestGoalieGameStats:
    """Tests for GoalieGameStats dataclass."""

    def test_creation(self) -> None:
        """Test creating GoalieGameStats."""
        game = GoalieGameStats(
            game_id=2024020501,
            game_date=date(2025, 1, 16),
            team_abbrev="NSH",
            opponent_abbrev="COL",
            home_road_flag="R",
            games_started=1,
            decision="W",
            shots_against=32,
            goals_against=2,
            save_pct=0.938,
            shutouts=0,
            toi="60:00",
            goals=0,
            assists=0,
            pim=0,
        )
        assert game.game_id == 2024020501
        assert game.decision == "W"
        assert game.shots_against == 32
        assert game.save_pct == 0.938

    def test_immutable(self) -> None:
        """Test that GoalieGameStats is immutable."""
        game = GoalieGameStats(
            game_id=2024020501,
            game_date=date(2025, 1, 16),
            team_abbrev="NSH",
            opponent_abbrev="COL",
            home_road_flag="R",
            games_started=1,
            decision="W",
            shots_against=32,
            goals_against=2,
            save_pct=0.938,
            shutouts=0,
            toi="60:00",
            goals=0,
            assists=0,
            pim=0,
        )
        with pytest.raises(AttributeError):
            game.decision = "L"  # type: ignore[misc]


@pytest.mark.unit
class TestParsedPlayerGameLog:
    """Tests for ParsedPlayerGameLog dataclass."""

    def test_skater_game_log(self) -> None:
        """Test creating skater game log."""
        games = (
            SkaterGameStats(
                game_id=2024020500,
                game_date=date(2025, 1, 15),
                team_abbrev="EDM",
                opponent_abbrev="CGY",
                home_road_flag="H",
                goals=2,
                assists=1,
                points=3,
                plus_minus=2,
                pim=0,
                shots=5,
                shifts=28,
                toi="22:15",
                power_play_goals=1,
                power_play_points=2,
                shorthanded_goals=0,
                shorthanded_points=0,
                game_winning_goals=1,
                ot_goals=0,
            ),
        )
        game_log = ParsedPlayerGameLog(
            player_id=8478402,
            season_id=20242025,
            game_type=REGULAR_SEASON,
            is_goalie=False,
            games=games,
        )
        assert game_log.player_id == 8478402
        assert game_log.game_count == 1
        assert game_log.total_goals == 2
        assert game_log.total_assists == 1
        assert game_log.is_goalie is False

    def test_goalie_game_log(self) -> None:
        """Test creating goalie game log."""
        games = (
            GoalieGameStats(
                game_id=2024020501,
                game_date=date(2025, 1, 16),
                team_abbrev="NSH",
                opponent_abbrev="COL",
                home_road_flag="R",
                games_started=1,
                decision="W",
                shots_against=32,
                goals_against=2,
                save_pct=0.938,
                shutouts=0,
                toi="60:00",
                goals=0,
                assists=1,
                pim=0,
            ),
        )
        game_log = ParsedPlayerGameLog(
            player_id=8477424,
            season_id=20242025,
            game_type=REGULAR_SEASON,
            is_goalie=True,
            games=games,
        )
        assert game_log.player_id == 8477424
        assert game_log.is_goalie is True
        assert game_log.total_assists == 1

    def test_to_dict_skater(self) -> None:
        """Test to_dict for skater game log."""
        games = (
            SkaterGameStats(
                game_id=2024020500,
                game_date=date(2025, 1, 15),
                team_abbrev="EDM",
                opponent_abbrev="CGY",
                home_road_flag="H",
                goals=2,
                assists=1,
                points=3,
                plus_minus=2,
                pim=0,
                shots=5,
                shifts=28,
                toi="22:15",
                power_play_goals=1,
                power_play_points=2,
                shorthanded_goals=0,
                shorthanded_points=0,
                game_winning_goals=1,
                ot_goals=0,
            ),
        )
        game_log = ParsedPlayerGameLog(
            player_id=8478402,
            season_id=20242025,
            game_type=REGULAR_SEASON,
            is_goalie=False,
            games=games,
        )
        result = game_log.to_dict()
        assert result["player_id"] == 8478402
        assert result["game_count"] == 1
        assert "points" in result["games"][0]
        assert "shots" in result["games"][0]

    def test_to_dict_goalie(self) -> None:
        """Test to_dict for goalie game log."""
        games = (
            GoalieGameStats(
                game_id=2024020501,
                game_date=date(2025, 1, 16),
                team_abbrev="NSH",
                opponent_abbrev="COL",
                home_road_flag="R",
                games_started=1,
                decision="W",
                shots_against=32,
                goals_against=2,
                save_pct=0.938,
                shutouts=0,
                toi="60:00",
                goals=0,
                assists=0,
                pim=0,
            ),
        )
        game_log = ParsedPlayerGameLog(
            player_id=8477424,
            season_id=20242025,
            game_type=REGULAR_SEASON,
            is_goalie=True,
            games=games,
        )
        result = game_log.to_dict()
        assert result["is_goalie"] is True
        assert "decision" in result["games"][0]
        assert "save_pct" in result["games"][0]


@pytest.mark.unit
class TestParseDateFunction:
    """Tests for _parse_date helper function."""

    def test_valid_date(self) -> None:
        """Test parsing valid date string."""
        result = _parse_date("2025-01-15")
        assert result == date(2025, 1, 15)

    def test_none_date(self) -> None:
        """Test parsing None returns None."""
        assert _parse_date(None) is None

    def test_empty_date(self) -> None:
        """Test parsing empty string returns None."""
        assert _parse_date("") is None

    def test_invalid_date(self) -> None:
        """Test parsing invalid date returns None."""
        assert _parse_date("not-a-date") is None


@pytest.mark.unit
class TestGetLocalizedFunction:
    """Tests for _get_localized helper function."""

    def test_dict_with_default(self) -> None:
        """Test getting default from dict."""
        obj = {"default": "Boston", "fr": "Boston"}
        assert _get_localized(obj) == "Boston"

    def test_string_value(self) -> None:
        """Test returning string directly."""
        assert _get_localized("Boston") == "Boston"

    def test_none_value(self) -> None:
        """Test None returns empty string."""
        assert _get_localized(None) == ""

    def test_dict_without_default(self) -> None:
        """Test dict without default key."""
        obj = {"fr": "Boston"}
        assert _get_localized(obj) == ""


@pytest.mark.unit
class TestGameTypeConstants:
    """Tests for game type constants."""

    def test_regular_season_value(self) -> None:
        """Test regular season constant."""
        assert REGULAR_SEASON == 2

    def test_playoffs_value(self) -> None:
        """Test playoffs constant."""
        assert PLAYOFFS == 3


@pytest.mark.unit
class TestPlayerGameLogDownloaderInit:
    """Tests for PlayerGameLogDownloader initialization."""

    def test_initialization(self) -> None:
        """Test basic initialization."""
        config = PlayerGameLogDownloaderConfig()
        downloader = PlayerGameLogDownloader(config)
        assert downloader.config == config
        assert downloader._players == []

    def test_initialization_with_players(self) -> None:
        """Test initialization with player list."""
        config = PlayerGameLogDownloaderConfig()
        players = [(8478402, 20242025, 2), (8477424, 20242025, 2)]
        downloader = PlayerGameLogDownloader(config, players=players)
        assert downloader._players == players

    def test_initialization_default_config(self) -> None:
        """Test initialization with default config."""
        downloader = PlayerGameLogDownloader()
        assert downloader.config.base_url == "https://api-web.nhle.com"

    def test_set_players(self) -> None:
        """Test setting player list."""
        downloader = PlayerGameLogDownloader()
        players = [(8478402, 20242025, 2)]
        downloader.set_players(players)
        assert downloader._players == players

    def test_set_players_copies_list(self) -> None:
        """Test that set_players creates a copy."""
        downloader = PlayerGameLogDownloader()
        players = [(8478402, 20242025, 2)]
        downloader.set_players(players)
        players.append((8477424, 20242025, 2))
        assert len(downloader._players) == 1


@pytest.mark.unit
class TestPlayerGameLogDownloaderDownload:
    """Tests for PlayerGameLogDownloader download methods."""

    @pytest.mark.asyncio
    async def test_download_skater_success(self) -> None:
        """Test successful skater download."""
        config = PlayerGameLogDownloaderConfig()
        downloader = PlayerGameLogDownloader(config)

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SKATER_RESPONSE

        with patch.object(downloader, "_get", AsyncMock(return_value=mock_response)):
            result = await downloader.download_player_season(8478402, 20242025, 2)

        assert result.status == DownloadStatus.COMPLETED
        assert result.data is not None
        assert result.data["player_id"] == 8478402
        assert result.data["is_goalie"] is False
        assert result.data["game_count"] == 1
        assert result.data["games"][0]["goals"] == 2

    @pytest.mark.asyncio
    async def test_download_goalie_success(self) -> None:
        """Test successful goalie download."""
        config = PlayerGameLogDownloaderConfig()
        downloader = PlayerGameLogDownloader(config)

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_GOALIE_RESPONSE

        with patch.object(downloader, "_get", AsyncMock(return_value=mock_response)):
            result = await downloader.download_player_season(8477424, 20242025, 2)

        assert result.status == DownloadStatus.COMPLETED
        assert result.data is not None
        assert result.data["is_goalie"] is True
        assert result.data["games"][0]["decision"] == "W"

    @pytest.mark.asyncio
    async def test_download_empty_game_log(self) -> None:
        """Test downloading empty game log."""
        config = PlayerGameLogDownloaderConfig()
        downloader = PlayerGameLogDownloader(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"gameLog": []}

        with patch.object(downloader, "_get", AsyncMock(return_value=mock_response)):
            result = await downloader.download_player_season(8478402, 20242025, 2)

        assert result.status == DownloadStatus.COMPLETED
        assert result.data is not None
        assert result.data["game_count"] == 0

    @pytest.mark.asyncio
    async def test_download_http_error(self) -> None:
        """Test handling HTTP error."""
        config = PlayerGameLogDownloaderConfig()
        downloader = PlayerGameLogDownloader(config)

        with patch.object(
            downloader, "_get", AsyncMock(side_effect=Exception("Connection failed"))
        ):
            result = await downloader.download_player_season(8478402, 20242025, 2)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
        assert "Connection failed" in result.error_message

    @pytest.mark.asyncio
    async def test_download_returns_correct_source(self) -> None:
        """Test that download result has correct source name."""
        config = PlayerGameLogDownloaderConfig()
        downloader = PlayerGameLogDownloader(config)

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SKATER_RESPONSE

        with patch.object(downloader, "_get", AsyncMock(return_value=mock_response)):
            result = await downloader.download_player_season(8478402, 20242025, 2)

        assert result.source == "nhl_json_player_game_log"
        assert result.season_id == 20242025


@pytest.mark.unit
class TestPlayerGameLogDownloaderDownloadAll:
    """Tests for download_all method."""

    @pytest.mark.asyncio
    async def test_download_all_success(self) -> None:
        """Test downloading all configured players."""
        config = PlayerGameLogDownloaderConfig()
        players = [
            (8478402, 20242025, 2),
            (8477424, 20242025, 2),
        ]
        downloader = PlayerGameLogDownloader(config, players=players)

        mock_response1 = MagicMock()
        mock_response1.json.return_value = SAMPLE_SKATER_RESPONSE
        mock_response2 = MagicMock()
        mock_response2.json.return_value = SAMPLE_GOALIE_RESPONSE

        with patch.object(
            downloader, "_get", AsyncMock(side_effect=[mock_response1, mock_response2])
        ):
            results = []
            async for result in downloader.download_all():
                results.append(result)

        assert len(results) == 2
        assert results[0].status == DownloadStatus.COMPLETED
        assert results[1].status == DownloadStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_download_all_no_players(self) -> None:
        """Test download_all with no players configured."""
        config = PlayerGameLogDownloaderConfig()
        downloader = PlayerGameLogDownloader(config)

        results = []
        async for result in downloader.download_all():
            results.append(result)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_download_all_with_failures(self) -> None:
        """Test download_all continues despite failures."""
        config = PlayerGameLogDownloaderConfig()
        players = [
            (8478402, 20242025, 2),
            (8477424, 20242025, 2),
        ]
        downloader = PlayerGameLogDownloader(config, players=players)

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SKATER_RESPONSE

        with patch.object(
            downloader,
            "_get",
            AsyncMock(side_effect=[Exception("First failed"), mock_response]),
        ):
            results = []
            async for result in downloader.download_all():
                results.append(result)

        assert len(results) == 2
        assert results[0].status == DownloadStatus.FAILED
        assert results[1].status == DownloadStatus.COMPLETED


@pytest.mark.unit
class TestPlayerGameLogDownloaderParsing:
    """Tests for parsing logic."""

    def test_parse_skater_game(self) -> None:
        """Test parsing skater game data."""
        downloader = PlayerGameLogDownloader()
        result = downloader._parse_skater_game(SAMPLE_SKATER_GAME)

        assert result.game_id == 2024020500
        assert result.game_date == date(2025, 1, 15)
        assert result.team_abbrev == "EDM"
        assert result.goals == 2
        assert result.assists == 1
        assert result.power_play_goals == 1

    def test_parse_goalie_game(self) -> None:
        """Test parsing goalie game data."""
        downloader = PlayerGameLogDownloader()
        result = downloader._parse_goalie_game(SAMPLE_GOALIE_GAME)

        assert result.game_id == 2024020501
        assert result.game_date == date(2025, 1, 16)
        assert result.team_abbrev == "NSH"
        assert result.decision == "W"
        assert result.shots_against == 32
        assert result.save_pct == 0.938

    def test_parse_game_log_detects_skater(self) -> None:
        """Test that game log correctly detects skater."""
        downloader = PlayerGameLogDownloader()
        result = downloader._parse_game_log(
            SAMPLE_SKATER_RESPONSE, 8478402, 20242025, 2
        )

        assert result.is_goalie is False
        assert isinstance(result.games[0], SkaterGameStats)

    def test_parse_game_log_detects_goalie(self) -> None:
        """Test that game log correctly detects goalie."""
        downloader = PlayerGameLogDownloader()
        result = downloader._parse_game_log(
            SAMPLE_GOALIE_RESPONSE, 8477424, 20242025, 2
        )

        assert result.is_goalie is True
        assert isinstance(result.games[0], GoalieGameStats)

    def test_parse_missing_date_fallback(self) -> None:
        """Test fallback for missing game date."""
        downloader = PlayerGameLogDownloader()
        game_data = {**SAMPLE_SKATER_GAME, "gameDate": None}
        result = downloader._parse_skater_game(game_data)

        assert result.game_date == date(1900, 1, 1)

    def test_parse_missing_decision(self) -> None:
        """Test handling goalie with no decision."""
        downloader = PlayerGameLogDownloader()
        game_data = {**SAMPLE_GOALIE_GAME}
        del game_data["decision"]
        result = downloader._parse_goalie_game(game_data)

        assert result.decision is None


@pytest.mark.unit
class TestCreatePlayerGameLogDownloader:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating downloader with defaults."""
        downloader = create_player_game_log_downloader()
        assert downloader.config.base_url == "https://api-web.nhle.com"
        assert downloader._players == []

    def test_create_with_custom_config(self) -> None:
        """Test creating downloader with custom config."""
        downloader = create_player_game_log_downloader(
            base_url="https://custom.api.com",
            requests_per_second=10.0,
            include_raw_response=True,
        )
        assert downloader.config.base_url == "https://custom.api.com"
        assert downloader.config.requests_per_second == 10.0
        config = downloader.config
        assert isinstance(config, PlayerGameLogDownloaderConfig)
        assert config.include_raw_response is True

    def test_create_with_players(self) -> None:
        """Test creating downloader with players."""
        players = [(8478402, 20242025, 2)]
        downloader = create_player_game_log_downloader(players=players)
        assert downloader._players == players
