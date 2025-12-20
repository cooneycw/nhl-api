"""Tests for Play-by-Play Downloader."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.base.protocol import DownloadError
from nhl_api.downloaders.sources.nhl_json.play_by_play import (
    EventPlayer,
    EventType,
    GameEvent,
    ParsedPlayByPlay,
    PlayByPlayDownloader,
    PlayByPlayDownloaderConfig,
    PlayerRole,
    create_play_by_play_downloader,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_goal_event_type(self) -> None:
        """Test goal event type."""
        assert EventType.GOAL.value == "goal"

    def test_shot_on_goal_event_type(self) -> None:
        """Test shot-on-goal event type."""
        assert EventType.SHOT_ON_GOAL.value == "shot-on-goal"

    def test_all_event_types_exist(self) -> None:
        """Test all expected event types exist."""
        expected_types = [
            "goal",
            "shot-on-goal",
            "missed-shot",
            "blocked-shot",
            "hit",
            "giveaway",
            "takeaway",
            "faceoff",
            "penalty",
            "stoppage",
            "period-start",
            "period-end",
        ]
        for event_type in expected_types:
            assert event_type in [e.value for e in EventType]


class TestPlayerRole:
    """Tests for PlayerRole enum."""

    def test_scorer_role(self) -> None:
        """Test scorer role."""
        assert PlayerRole.SCORER.value == "scorer"

    def test_goalie_role(self) -> None:
        """Test goalie role."""
        assert PlayerRole.GOALIE.value == "goalie"


class TestEventPlayer:
    """Tests for EventPlayer dataclass."""

    def test_create_event_player(self) -> None:
        """Test creating an EventPlayer."""
        player = EventPlayer(
            player_id=8478402,
            name="Connor McDavid",
            team_id=22,
            team_abbrev="EDM",
            role="scorer",
            sweater_number=97,
        )

        assert player.player_id == 8478402
        assert player.name == "Connor McDavid"
        assert player.team_id == 22
        assert player.team_abbrev == "EDM"
        assert player.role == "scorer"
        assert player.sweater_number == 97

    def test_event_player_is_frozen(self) -> None:
        """Test that EventPlayer is immutable."""
        player = EventPlayer(
            player_id=8478402,
            name="Connor McDavid",
            team_id=22,
            team_abbrev="EDM",
            role="scorer",
        )

        with pytest.raises(AttributeError):
            player.player_id = 12345  # type: ignore[misc]


class TestGameEvent:
    """Tests for GameEvent dataclass."""

    def test_create_game_event(self) -> None:
        """Test creating a GameEvent."""
        event = GameEvent(
            event_id=123,
            event_type="goal",
            period=2,
            period_type="REG",
            time_in_period="12:34",
            time_remaining="07:26",
            sort_order=456,
            x_coord=45.5,
            y_coord=-20.0,
            zone="O",
            home_score=2,
            away_score=1,
        )

        assert event.event_id == 123
        assert event.event_type == "goal"
        assert event.period == 2
        assert event.time_in_period == "12:34"
        assert event.x_coord == 45.5
        assert event.y_coord == -20.0
        assert event.zone == "O"

    def test_game_event_with_players(self) -> None:
        """Test GameEvent with players."""
        players = (
            EventPlayer(
                player_id=8478402,
                name="Connor McDavid",
                team_id=22,
                team_abbrev="EDM",
                role="scorer",
            ),
            EventPlayer(
                player_id=8477934,
                name="Leon Draisaitl",
                team_id=22,
                team_abbrev="EDM",
                role="assist1",
            ),
        )

        event = GameEvent(
            event_id=123,
            event_type="goal",
            period=1,
            period_type="REG",
            time_in_period="05:00",
            time_remaining="15:00",
            sort_order=100,
            players=players,
        )

        assert len(event.players) == 2
        assert event.players[0].role == "scorer"
        assert event.players[1].role == "assist1"

    def test_game_event_is_frozen(self) -> None:
        """Test that GameEvent is immutable."""
        event = GameEvent(
            event_id=123,
            event_type="goal",
            period=1,
            period_type="REG",
            time_in_period="05:00",
            time_remaining="15:00",
            sort_order=100,
        )

        with pytest.raises(AttributeError):
            event.event_id = 456  # type: ignore[misc]


class TestParsedPlayByPlay:
    """Tests for ParsedPlayByPlay dataclass."""

    def test_create_parsed_play_by_play(self) -> None:
        """Test creating ParsedPlayByPlay."""
        pbp = ParsedPlayByPlay(
            game_id=2024020500,
            season_id=20242025,
            game_date="2024-12-20",
            game_type=2,
            game_state="OFF",
            home_team_id=22,
            home_team_abbrev="EDM",
            away_team_id=20,
            away_team_abbrev="CGY",
            venue_name="Rogers Place",
        )

        assert pbp.game_id == 2024020500
        assert pbp.season_id == 20242025
        assert pbp.home_team_abbrev == "EDM"
        assert pbp.away_team_abbrev == "CGY"

    def test_total_events_property(self) -> None:
        """Test total_events property."""
        events = [
            GameEvent(
                event_id=i,
                event_type="goal",
                period=1,
                period_type="REG",
                time_in_period="05:00",
                time_remaining="15:00",
                sort_order=i,
            )
            for i in range(5)
        ]

        pbp = ParsedPlayByPlay(
            game_id=2024020500,
            season_id=20242025,
            game_date="2024-12-20",
            game_type=2,
            game_state="OFF",
            home_team_id=22,
            home_team_abbrev="EDM",
            away_team_id=20,
            away_team_abbrev="CGY",
            venue_name="Rogers Place",
            events=events,
        )

        assert pbp.total_events == 5

    def test_get_events_by_type(self) -> None:
        """Test filtering events by type."""
        events = [
            GameEvent(
                event_id=1,
                event_type="goal",
                period=1,
                period_type="REG",
                time_in_period="05:00",
                time_remaining="15:00",
                sort_order=1,
            ),
            GameEvent(
                event_id=2,
                event_type="shot-on-goal",
                period=1,
                period_type="REG",
                time_in_period="06:00",
                time_remaining="14:00",
                sort_order=2,
            ),
            GameEvent(
                event_id=3,
                event_type="goal",
                period=2,
                period_type="REG",
                time_in_period="10:00",
                time_remaining="10:00",
                sort_order=3,
            ),
        ]

        pbp = ParsedPlayByPlay(
            game_id=2024020500,
            season_id=20242025,
            game_date="2024-12-20",
            game_type=2,
            game_state="OFF",
            home_team_id=22,
            home_team_abbrev="EDM",
            away_team_id=20,
            away_team_abbrev="CGY",
            venue_name="Rogers Place",
            events=events,
        )

        goals = pbp.get_events_by_type("goal")
        assert len(goals) == 2

        shots = pbp.get_events_by_type("shot-on-goal")
        assert len(shots) == 1

    def test_get_events_by_period(self) -> None:
        """Test filtering events by period."""
        events = [
            GameEvent(
                event_id=1,
                event_type="goal",
                period=1,
                period_type="REG",
                time_in_period="05:00",
                time_remaining="15:00",
                sort_order=1,
            ),
            GameEvent(
                event_id=2,
                event_type="shot-on-goal",
                period=1,
                period_type="REG",
                time_in_period="06:00",
                time_remaining="14:00",
                sort_order=2,
            ),
            GameEvent(
                event_id=3,
                event_type="goal",
                period=2,
                period_type="REG",
                time_in_period="10:00",
                time_remaining="10:00",
                sort_order=3,
            ),
        ]

        pbp = ParsedPlayByPlay(
            game_id=2024020500,
            season_id=20242025,
            game_date="2024-12-20",
            game_type=2,
            game_state="OFF",
            home_team_id=22,
            home_team_abbrev="EDM",
            away_team_id=20,
            away_team_abbrev="CGY",
            venue_name="Rogers Place",
            events=events,
        )

        period_1_events = pbp.get_events_by_period(1)
        assert len(period_1_events) == 2

        period_2_events = pbp.get_events_by_period(2)
        assert len(period_2_events) == 1


class TestPlayByPlayDownloader:
    """Tests for PlayByPlayDownloader class."""

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
    def downloader(
        self, mock_http_client: MagicMock, mock_rate_limiter: MagicMock
    ) -> PlayByPlayDownloader:
        """Create a PlayByPlayDownloader with mock HTTP client."""
        config = PlayByPlayDownloaderConfig(
            base_url="https://api-web.nhle.com",
            requests_per_second=10.0,
        )
        dl = PlayByPlayDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False  # Don't close the mock
        return dl

    def test_source_name(self, downloader: PlayByPlayDownloader) -> None:
        """Test source_name property."""
        assert downloader.source_name == "nhl_json_play_by_play"

    def test_set_game_ids(self, downloader: PlayByPlayDownloader) -> None:
        """Test setting game IDs."""
        game_ids = [2024020001, 2024020002, 2024020003]
        downloader.set_game_ids(game_ids)
        assert downloader._game_ids == game_ids

    async def test_fetch_game_success(
        self,
        downloader: PlayByPlayDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful game fetch."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "season": 20242025,
            "gameDate": "2024-12-20",
            "gameType": 2,
            "gameState": "OFF",
            "venue": {"default": "Rogers Place"},
            "homeTeam": {"id": 22, "abbrev": "EDM"},
            "awayTeam": {"id": 20, "abbrev": "CGY"},
            "plays": [
                {
                    "eventId": 1,
                    "typeDescKey": "period-start",
                    "sortOrder": 1,
                    "periodDescriptor": {"number": 1, "periodType": "REG"},
                    "timeInPeriod": "00:00",
                    "timeRemaining": "20:00",
                    "details": {},
                },
                {
                    "eventId": 2,
                    "typeDescKey": "faceoff",
                    "sortOrder": 2,
                    "periodDescriptor": {"number": 1, "periodType": "REG"},
                    "timeInPeriod": "00:00",
                    "timeRemaining": "20:00",
                    "details": {
                        "xCoord": 0,
                        "yCoord": 0,
                        "zoneCode": "N",
                        "winningPlayerId": 8478402,
                        "losingPlayerId": 8477934,
                    },
                },
            ],
        }
        mock_http_client.get.return_value = mock_response

        result = await downloader._fetch_game(2024020500)

        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert result["home_team_abbrev"] == "EDM"
        assert result["away_team_abbrev"] == "CGY"
        assert result["total_events"] == 2
        assert len(result["events"]) == 2

    async def test_fetch_game_http_error(
        self,
        downloader: PlayByPlayDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of HTTP error."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 404
        mock_response.retry_after = None
        mock_http_client.get.return_value = mock_response

        with pytest.raises(DownloadError) as exc_info:
            await downloader._fetch_game(2024020500)

        assert "Failed to fetch play-by-play" in str(exc_info.value)
        assert "404" in str(exc_info.value)

    async def test_fetch_season_games_no_ids(
        self,
        downloader: PlayByPlayDownloader,
    ) -> None:
        """Test _fetch_season_games with no game IDs set."""
        game_ids = []
        async for game_id in downloader._fetch_season_games(20242025):
            game_ids.append(game_id)

        assert game_ids == []

    async def test_fetch_season_games_with_ids(
        self,
        downloader: PlayByPlayDownloader,
    ) -> None:
        """Test _fetch_season_games with game IDs set."""
        expected_ids = [2024020001, 2024020002, 2024020003]
        downloader.set_game_ids(expected_ids)

        game_ids = []
        async for game_id in downloader._fetch_season_games(20242025):
            game_ids.append(game_id)

        assert game_ids == expected_ids


class TestPlayByPlayDownloaderParsing:
    """Tests for play-by-play parsing methods."""

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
    def downloader(
        self, mock_http_client: MagicMock, mock_rate_limiter: MagicMock
    ) -> PlayByPlayDownloader:
        """Create a PlayByPlayDownloader with mock HTTP client."""
        config = PlayByPlayDownloaderConfig()
        dl = PlayByPlayDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False
        return dl

    def test_parse_goal_event(self, downloader: PlayByPlayDownloader) -> None:
        """Test parsing a goal event."""
        play = {
            "eventId": 100,
            "typeDescKey": "goal",
            "sortOrder": 100,
            "periodDescriptor": {"number": 2, "periodType": "REG"},
            "timeInPeriod": "12:34",
            "timeRemaining": "07:26",
            "homeScore": 2,
            "awayScore": 1,
            "homeSOG": 15,
            "awaySOG": 12,
            "details": {
                "xCoord": 75.5,
                "yCoord": -10.0,
                "zoneCode": "O",
                "eventOwnerTeamId": 22,
                "scoringPlayerId": 8478402,
                "assist1PlayerId": 8477934,
                "shotType": "wrist",
                "scoringPlayerTotal": 25,
            },
        }

        event = downloader._parse_event(play, home_team_id=22, away_team_id=20)

        assert event.event_id == 100
        assert event.event_type == "goal"
        assert event.period == 2
        assert event.time_in_period == "12:34"
        assert event.x_coord == 75.5
        assert event.y_coord == -10.0
        assert event.zone == "O"
        assert event.home_score == 2
        assert event.away_score == 1
        assert event.event_owner_team_id == 22
        assert len(event.players) == 2
        assert event.details["shot_type"] == "wrist"
        assert event.details["scorer_season_total"] == 25

    def test_parse_penalty_event(self, downloader: PlayByPlayDownloader) -> None:
        """Test parsing a penalty event."""
        play = {
            "eventId": 200,
            "typeDescKey": "penalty",
            "sortOrder": 200,
            "periodDescriptor": {"number": 1, "periodType": "REG"},
            "timeInPeriod": "08:00",
            "timeRemaining": "12:00",
            "details": {
                "eventOwnerTeamId": 20,
                "committedByPlayerId": 8477934,
                "drawnByPlayerId": 8478402,
                "typeCode": "MIN",
                "duration": 2,
                "descKey": "tripping",
            },
        }

        event = downloader._parse_event(play, home_team_id=22, away_team_id=20)

        assert event.event_type == "penalty"
        assert event.details["penalty_type"] == "MIN"
        assert event.details["duration"] == 2
        assert event.details["penalty_desc"] == "tripping"
        assert len(event.players) == 2

    def test_parse_hit_event(self, downloader: PlayByPlayDownloader) -> None:
        """Test parsing a hit event."""
        play = {
            "eventId": 300,
            "typeDescKey": "hit",
            "sortOrder": 300,
            "periodDescriptor": {"number": 2, "periodType": "REG"},
            "timeInPeriod": "15:00",
            "timeRemaining": "05:00",
            "details": {
                "xCoord": -50.0,
                "yCoord": 20.0,
                "zoneCode": "D",
                "eventOwnerTeamId": 22,
                "hittingPlayerId": 8478402,
                "hitteePlayerId": 8477934,
            },
        }

        event = downloader._parse_event(play, home_team_id=22, away_team_id=20)

        assert event.event_type == "hit"
        assert event.x_coord == -50.0
        assert event.y_coord == 20.0
        assert event.zone == "D"
        assert len(event.players) == 2

        player_roles = {p.role for p in event.players}
        assert "hitter" in player_roles
        assert "hittee" in player_roles

    def test_parse_faceoff_event(self, downloader: PlayByPlayDownloader) -> None:
        """Test parsing a faceoff event."""
        play = {
            "eventId": 400,
            "typeDescKey": "faceoff",
            "sortOrder": 400,
            "periodDescriptor": {"number": 1, "periodType": "REG"},
            "timeInPeriod": "00:00",
            "timeRemaining": "20:00",
            "details": {
                "xCoord": 0,
                "yCoord": 0,
                "zoneCode": "N",
                "winningPlayerId": 8478402,
                "losingPlayerId": 8477934,
            },
        }

        event = downloader._parse_event(play, home_team_id=22, away_team_id=20)

        assert event.event_type == "faceoff"
        assert event.x_coord == 0
        assert event.y_coord == 0
        assert event.zone == "N"
        assert len(event.players) == 2

        player_roles = {p.role for p in event.players}
        assert "winner" in player_roles
        assert "loser" in player_roles

    def test_parse_stoppage_event(self, downloader: PlayByPlayDownloader) -> None:
        """Test parsing a stoppage event."""
        play = {
            "eventId": 500,
            "typeDescKey": "stoppage",
            "sortOrder": 500,
            "periodDescriptor": {"number": 2, "periodType": "REG"},
            "timeInPeriod": "10:00",
            "timeRemaining": "10:00",
            "details": {
                "reason": "puck-frozen",
            },
        }

        event = downloader._parse_event(play, home_team_id=22, away_team_id=20)

        assert event.event_type == "stoppage"
        assert event.details["reason"] == "puck-frozen"
        assert event.description == "puck-frozen"

    def test_parse_event_with_missing_fields(
        self, downloader: PlayByPlayDownloader
    ) -> None:
        """Test parsing event with minimal data."""
        play = {
            "eventId": 600,
            "typeDescKey": "period-start",
            "sortOrder": 600,
            "periodDescriptor": {"number": 1},
            "timeInPeriod": "00:00",
            "timeRemaining": "20:00",
        }

        event = downloader._parse_event(play, home_team_id=22, away_team_id=20)

        assert event.event_id == 600
        assert event.event_type == "period-start"
        assert event.period == 1
        assert event.period_type == "REG"  # default
        assert event.x_coord is None
        assert event.y_coord is None
        assert event.zone is None

    def test_extract_shot_details(self, downloader: PlayByPlayDownloader) -> None:
        """Test extracting shot-specific details."""
        details = {
            "shotType": "slap",
            "awaySOG": 10,
            "homeSOG": 15,
        }

        extra = downloader._extract_event_details("shot-on-goal", details)

        assert extra["shot_type"] == "slap"
        assert extra["away_sog"] == 10
        assert extra["home_sog"] == 15

    def test_extract_goal_details(self, downloader: PlayByPlayDownloader) -> None:
        """Test extracting goal-specific details."""
        details = {
            "shotType": "wrist",
            "scoringPlayerTotal": 30,
            "assist1PlayerTotal": 45,
            "assist2PlayerTotal": 20,
            "highlightClipSharingUrl": "https://example.com/highlight",
        }

        extra = downloader._extract_event_details("goal", details)

        assert extra["shot_type"] == "wrist"
        assert extra["scorer_season_total"] == 30
        assert extra["assist1_season_total"] == 45
        assert extra["assist2_season_total"] == 20
        assert extra["highlight_url"] == "https://example.com/highlight"


class TestPlayByPlayDownloaderConversion:
    """Tests for data conversion methods."""

    @pytest.fixture
    def downloader(self) -> PlayByPlayDownloader:
        """Create a PlayByPlayDownloader."""
        return PlayByPlayDownloader(PlayByPlayDownloaderConfig())

    def test_player_to_dict(self, downloader: PlayByPlayDownloader) -> None:
        """Test converting EventPlayer to dict."""
        player = EventPlayer(
            player_id=8478402,
            name="Connor McDavid",
            team_id=22,
            team_abbrev="EDM",
            role="scorer",
            sweater_number=97,
        )

        result = downloader._player_to_dict(player)

        assert result["player_id"] == 8478402
        assert result["name"] == "Connor McDavid"
        assert result["team_id"] == 22
        assert result["role"] == "scorer"
        assert result["sweater_number"] == 97

    def test_event_to_dict(self, downloader: PlayByPlayDownloader) -> None:
        """Test converting GameEvent to dict."""
        event = GameEvent(
            event_id=100,
            event_type="goal",
            period=2,
            period_type="REG",
            time_in_period="12:34",
            time_remaining="07:26",
            sort_order=100,
            x_coord=75.5,
            y_coord=-10.0,
            zone="O",
            home_score=2,
            away_score=1,
        )

        result = downloader._event_to_dict(event)

        assert result["event_id"] == 100
        assert result["event_type"] == "goal"
        assert result["period"] == 2
        assert result["x_coord"] == 75.5
        assert result["home_score"] == 2

    def test_play_by_play_to_dict(self, downloader: PlayByPlayDownloader) -> None:
        """Test converting ParsedPlayByPlay to dict."""
        events = [
            GameEvent(
                event_id=1,
                event_type="goal",
                period=1,
                period_type="REG",
                time_in_period="05:00",
                time_remaining="15:00",
                sort_order=1,
            ),
        ]

        pbp = ParsedPlayByPlay(
            game_id=2024020500,
            season_id=20242025,
            game_date="2024-12-20",
            game_type=2,
            game_state="OFF",
            home_team_id=22,
            home_team_abbrev="EDM",
            away_team_id=20,
            away_team_abbrev="CGY",
            venue_name="Rogers Place",
            events=events,
        )

        result = downloader._play_by_play_to_dict(pbp)

        assert result["game_id"] == 2024020500
        assert result["home_team_abbrev"] == "EDM"
        assert result["total_events"] == 1
        assert len(result["events"]) == 1


class TestCreatePlayByPlayDownloader:
    """Tests for the factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating downloader with default settings."""
        downloader = create_play_by_play_downloader()

        assert downloader.source_name == "nhl_json_play_by_play"
        assert downloader.config.base_url == "https://api-web.nhle.com"
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_settings(self) -> None:
        """Test creating downloader with custom settings."""
        downloader = create_play_by_play_downloader(
            requests_per_second=10.0,
            max_retries=5,
        )

        assert downloader.config.requests_per_second == 10.0
        assert downloader.config.max_retries == 5


class TestPlayByPlayDownloaderConfig:
    """Tests for PlayByPlayDownloaderConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = PlayByPlayDownloaderConfig()

        assert config.base_url == "https://api-web.nhle.com"
        assert config.requests_per_second == 5.0
        assert config.max_retries == 3
        assert config.http_timeout == 30.0
        assert config.health_check_url == "/v1/schedule/now"
        assert config.include_raw_response is False

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = PlayByPlayDownloaderConfig(
            requests_per_second=10.0,
            max_retries=5,
            include_raw_response=True,
        )

        assert config.requests_per_second == 10.0
        assert config.max_retries == 5
        assert config.include_raw_response is True
