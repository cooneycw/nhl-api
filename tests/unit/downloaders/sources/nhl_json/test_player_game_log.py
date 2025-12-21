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
    _game_type_to_string,
    _get_localized,
    _parse_date,
    _toi_to_seconds,
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


@pytest.mark.unit
class TestToiToSeconds:
    """Tests for _toi_to_seconds helper function."""

    def test_valid_toi(self) -> None:
        """Test converting valid TOI string."""
        assert _toi_to_seconds("22:15") == 22 * 60 + 15

    def test_zero_toi(self) -> None:
        """Test converting zero TOI."""
        assert _toi_to_seconds("00:00") == 0

    def test_full_period(self) -> None:
        """Test converting full period TOI."""
        assert _toi_to_seconds("20:00") == 1200

    def test_overtime_toi(self) -> None:
        """Test converting overtime goalie TOI."""
        assert _toi_to_seconds("65:00") == 3900

    def test_empty_string(self) -> None:
        """Test empty string returns 0."""
        assert _toi_to_seconds("") == 0

    def test_none_value(self) -> None:
        """Test None-like value returns 0."""
        # The function handles empty strings
        assert _toi_to_seconds("") == 0

    def test_invalid_format(self) -> None:
        """Test invalid format returns 0."""
        assert _toi_to_seconds("invalid") == 0

    def test_single_part(self) -> None:
        """Test single number returns 0."""
        assert _toi_to_seconds("22") == 0


@pytest.mark.unit
class TestGameTypeToString:
    """Tests for _game_type_to_string helper function."""

    def test_regular_season(self) -> None:
        """Test regular season returns R."""
        assert _game_type_to_string(REGULAR_SEASON) == "R"
        assert _game_type_to_string(2) == "R"

    def test_playoffs(self) -> None:
        """Test playoffs returns P."""
        assert _game_type_to_string(PLAYOFFS) == "P"
        assert _game_type_to_string(3) == "P"

    def test_unknown_defaults_to_regular(self) -> None:
        """Test unknown game type defaults to R."""
        assert _game_type_to_string(0) == "R"
        assert _game_type_to_string(99) == "R"


@pytest.mark.unit
class TestPlayerGameLogDownloaderPersist:
    """Tests for persist method."""

    @pytest.mark.asyncio
    async def test_persist_empty_list(self) -> None:
        """Test persisting empty list returns 0."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        result = await downloader.persist(mock_db, [])

        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_skater_game_log(self) -> None:
        """Test persisting skater game log."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_log = {
            "player_id": 8478402,
            "season_id": 20242025,
            "game_type": REGULAR_SEASON,
            "is_goalie": False,
            "games": [
                {
                    "game_id": 2024020500,
                    "game_date": "2025-01-15",
                    "team_abbrev": "EDM",
                    "opponent_abbrev": "CGY",
                    "home_road_flag": "H",
                    "goals": 2,
                    "assists": 1,
                    "points": 3,
                    "plus_minus": 2,
                    "pim": 0,
                    "toi": "22:15",
                    "shots": 5,
                    "shifts": 28,
                    "power_play_goals": 1,
                    "power_play_points": 2,
                    "shorthanded_goals": 0,
                    "shorthanded_points": 0,
                    "game_winning_goals": 1,
                    "ot_goals": 0,
                }
            ],
        }

        result = await downloader.persist(mock_db, [game_log])

        assert result == 1
        assert mock_db.execute.call_count == 1

        # Verify SQL structure
        call_args = mock_db.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO player_game_logs" in sql
        assert "ON CONFLICT (player_id, game_id)" in sql
        assert "is_goalie" in sql

    @pytest.mark.asyncio
    async def test_persist_goalie_game_log(self) -> None:
        """Test persisting goalie game log."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_log = {
            "player_id": 8477424,
            "season_id": 20242025,
            "game_type": REGULAR_SEASON,
            "is_goalie": True,
            "games": [
                {
                    "game_id": 2024020501,
                    "game_date": "2025-01-16",
                    "team_abbrev": "NSH",
                    "opponent_abbrev": "COL",
                    "home_road_flag": "R",
                    "goals": 0,
                    "assists": 0,
                    "pim": 0,
                    "toi": "60:00",
                    "games_started": 1,
                    "decision": "W",
                    "shots_against": 32,
                    "goals_against": 2,
                    "save_pct": 0.938,
                    "shutouts": 0,
                }
            ],
        }

        result = await downloader.persist(mock_db, [game_log])

        assert result == 1
        assert mock_db.execute.call_count == 1

        # Verify goalie-specific fields in SQL
        call_args = mock_db.execute.call_args
        sql = call_args[0][0]
        assert "decision" in sql
        assert "shots_against" in sql
        assert "save_pct" in sql

    @pytest.mark.asyncio
    async def test_persist_multiple_game_logs(self) -> None:
        """Test persisting multiple game logs."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_logs = [
            {
                "player_id": 8478402,
                "season_id": 20242025,
                "game_type": REGULAR_SEASON,
                "is_goalie": False,
                "games": [
                    {"game_id": 2024020500, "game_date": "2025-01-15", "toi": "22:15"},
                    {"game_id": 2024020501, "game_date": "2025-01-16", "toi": "20:00"},
                ],
            },
            {
                "player_id": 8477424,
                "season_id": 20242025,
                "game_type": REGULAR_SEASON,
                "is_goalie": True,
                "games": [
                    {"game_id": 2024020500, "game_date": "2025-01-15", "toi": "60:00"},
                ],
            },
        ]

        result = await downloader.persist(mock_db, game_logs)

        assert result == 3  # 2 skater games + 1 goalie game
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_persist_playoffs_game_type(self) -> None:
        """Test persisting playoff game log."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_log = {
            "player_id": 8478402,
            "season_id": 20242025,
            "game_type": PLAYOFFS,
            "is_goalie": False,
            "games": [
                {"game_id": 2024030111, "game_date": "2025-04-15", "toi": "25:00"}
            ],
        }

        result = await downloader.persist(mock_db, [game_log])

        assert result == 1
        # Verify game_type is "P" for playoffs
        call_args = mock_db.execute.call_args[0]
        # The game_type_str should be at index 4 (after player_id, game_id, season_id)
        assert call_args[4] == "P"

    @pytest.mark.asyncio
    async def test_persist_toi_conversion(self) -> None:
        """Test that TOI is converted to seconds."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_log = {
            "player_id": 8478402,
            "season_id": 20242025,
            "game_type": REGULAR_SEASON,
            "is_goalie": False,
            "games": [
                {"game_id": 2024020500, "game_date": "2025-01-15", "toi": "22:15"}
            ],
        }

        await downloader.persist(mock_db, [game_log])

        # TOI of 22:15 should be 1335 seconds
        call_args = mock_db.execute.call_args[0]
        # toi_seconds is at index 12 for skaters
        assert call_args[12] == 1335

    @pytest.mark.asyncio
    async def test_persist_missing_game_id_skipped(self) -> None:
        """Test that games without game_id are skipped."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_log = {
            "player_id": 8478402,
            "season_id": 20242025,
            "game_type": REGULAR_SEASON,
            "is_goalie": False,
            "games": [
                {"game_date": "2025-01-15", "toi": "22:15"},  # No game_id
            ],
        }

        result = await downloader.persist(mock_db, [game_log])

        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_invalid_date_handled(self) -> None:
        """Test that invalid date is handled gracefully."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_log = {
            "player_id": 8478402,
            "season_id": 20242025,
            "game_type": REGULAR_SEASON,
            "is_goalie": False,
            "games": [
                {
                    "game_id": 2024020500,
                    "game_date": "invalid-date",
                    "toi": "22:15",
                }
            ],
        }

        result = await downloader.persist(mock_db, [game_log])

        assert result == 1
        # game_date should be None when invalid
        call_args = mock_db.execute.call_args[0]
        assert call_args[8] is None  # game_date parameter

    @pytest.mark.asyncio
    async def test_persist_continues_on_error(self) -> None:
        """Test that persist continues on individual game error."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()
        # First call fails, second succeeds
        mock_db.execute.side_effect = [Exception("DB error"), None]

        game_logs = [
            {
                "player_id": 8478402,
                "season_id": 20242025,
                "game_type": REGULAR_SEASON,
                "is_goalie": False,
                "games": [
                    {"game_id": 2024020500, "game_date": "2025-01-15", "toi": "22:15"},
                    {"game_id": 2024020501, "game_date": "2025-01-16", "toi": "20:00"},
                ],
            }
        ]

        result = await downloader.persist(mock_db, game_logs)

        # First game fails, second succeeds
        assert result == 1
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_persist_sql_structure_skater(self) -> None:
        """Test SQL structure for skater persistence."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_log = {
            "player_id": 8478402,
            "season_id": 20242025,
            "game_type": REGULAR_SEASON,
            "is_goalie": False,
            "games": [
                {"game_id": 2024020500, "game_date": "2025-01-15", "toi": "22:15"}
            ],
        }

        await downloader.persist(mock_db, [game_log])

        sql = mock_db.execute.call_args[0][0]
        # Verify skater-specific columns
        assert "points" in sql
        assert "plus_minus" in sql
        assert "shots" in sql
        assert "shifts" in sql
        assert "power_play_goals" in sql
        assert "shorthanded_goals" in sql
        assert "game_winning_goals" in sql
        assert "ot_goals" in sql

    @pytest.mark.asyncio
    async def test_persist_sql_structure_goalie(self) -> None:
        """Test SQL structure for goalie persistence."""
        downloader = PlayerGameLogDownloader()
        mock_db = AsyncMock()

        game_log = {
            "player_id": 8477424,
            "season_id": 20242025,
            "game_type": REGULAR_SEASON,
            "is_goalie": True,
            "games": [
                {"game_id": 2024020500, "game_date": "2025-01-15", "toi": "60:00"}
            ],
        }

        await downloader.persist(mock_db, [game_log])

        sql = mock_db.execute.call_args[0][0]
        # Verify goalie-specific columns
        assert "games_started" in sql
        assert "decision" in sql
        assert "shots_against" in sql
        assert "goals_against" in sql
        assert "save_pct" in sql
        assert "shutouts" in sql
