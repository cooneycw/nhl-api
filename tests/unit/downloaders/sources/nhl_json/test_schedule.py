"""Tests for Schedule Downloader."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.base.base_downloader import DownloaderConfig
from nhl_api.downloaders.sources.nhl_json.schedule import (
    GameInfo,
    ScheduleDownloader,
    _parse_game,
    create_schedule_downloader,
)


@pytest.mark.unit
class TestParseGame:
    """Tests for _parse_game function."""

    def test_parse_complete_game(self) -> None:
        """Test parsing a completed game with all fields."""
        game_data = {
            "id": 2024020521,
            "season": 20242025,
            "gameType": 2,
            "startTimeUTC": "2024-12-21T00:00:00Z",
            "venue": {"default": "KeyBank Center"},
            "homeTeam": {
                "id": 7,
                "abbrev": "BUF",
                "score": 3,
            },
            "awayTeam": {
                "id": 10,
                "abbrev": "TOR",
                "score": 6,
            },
            "gameState": "OFF",
            "period": 3,
        }

        result = _parse_game(game_data)

        assert result.game_id == 2024020521
        assert result.season_id == 20242025
        assert result.game_type == 2
        assert result.home_team_id == 7
        assert result.home_team_abbrev == "BUF"
        assert result.home_score == 3
        assert result.away_team_id == 10
        assert result.away_team_abbrev == "TOR"
        assert result.away_score == 6
        assert result.game_state == "OFF"
        assert result.venue_name == "KeyBank Center"
        assert not result.is_overtime
        assert not result.is_shootout

    def test_parse_overtime_game(self) -> None:
        """Test parsing a game that went to overtime."""
        game_data = {
            "id": 2024020500,
            "season": 20242025,
            "gameType": 2,
            "startTimeUTC": "2024-12-20T00:00:00Z",
            "homeTeam": {"id": 1, "abbrev": "NJD", "score": 3},
            "awayTeam": {"id": 2, "abbrev": "NYI", "score": 2},
            "gameState": "OFF",
            "period": 4,
            "periodDescriptor": {"periodType": "OT"},
        }

        result = _parse_game(game_data)

        assert result.is_overtime is True
        assert result.is_shootout is False
        assert result.period == 4

    def test_parse_shootout_game(self) -> None:
        """Test parsing a game that went to shootout."""
        game_data = {
            "id": 2024020501,
            "season": 20242025,
            "gameType": 2,
            "startTimeUTC": "2024-12-20T01:00:00Z",
            "homeTeam": {"id": 3, "abbrev": "NYR", "score": 4},
            "awayTeam": {"id": 4, "abbrev": "PHI", "score": 3},
            "gameState": "OFF",
            "period": 5,
            "periodDescriptor": {"periodType": "SO"},
        }

        result = _parse_game(game_data)

        assert result.is_shootout is True
        assert result.period == 5

    def test_parse_scheduled_game(self) -> None:
        """Test parsing a future/scheduled game."""
        game_data = {
            "id": 2024020600,
            "season": 20242025,
            "gameType": 2,
            "startTimeUTC": "2024-12-25T18:00:00Z",
            "homeTeam": {"id": 22, "abbrev": "EDM"},
            "awayTeam": {"id": 20, "abbrev": "CGY"},
            "gameState": "FUT",
        }

        result = _parse_game(game_data)

        assert result.game_state == "FUT"
        assert result.home_score is None
        assert result.away_score is None
        assert result.period is None

    def test_parse_minimal_game(self) -> None:
        """Test parsing a game with minimal data."""
        game_data = {
            "id": 2024020100,
            "homeTeam": {},
            "awayTeam": {},
        }

        result = _parse_game(game_data)

        assert result.game_id == 2024020100
        assert result.season_id == 0
        assert result.game_type == 2  # default
        assert result.home_team_id == 0
        assert result.away_team_id == 0


@pytest.mark.unit
class TestScheduleDownloader:
    """Tests for ScheduleDownloader class."""

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
    ) -> ScheduleDownloader:
        """Create a ScheduleDownloader with mock HTTP client."""
        config = DownloaderConfig(
            base_url="https://api-web.nhle.com/v1",
            requests_per_second=10.0,
        )
        dl = ScheduleDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False  # Don't close the mock
        return dl

    def test_source_name(self, downloader: ScheduleDownloader) -> None:
        """Test source_name property."""
        assert downloader.source_name == "nhl_json_schedule"

    async def test_get_schedule_for_date(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching schedule for a specific date."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "gameWeek": [
                {
                    "date": "2024-12-20",
                    "games": [
                        {
                            "id": 2024020521,
                            "season": 20242025,
                            "gameType": 2,
                            "startTimeUTC": "2024-12-21T00:00:00Z",
                            "homeTeam": {"id": 7, "abbrev": "BUF"},
                            "awayTeam": {"id": 10, "abbrev": "TOR"},
                            "gameState": "FUT",
                        },
                        {
                            "id": 2024020522,
                            "season": 20242025,
                            "gameType": 2,
                            "startTimeUTC": "2024-12-21T01:00:00Z",
                            "homeTeam": {"id": 22, "abbrev": "EDM"},
                            "awayTeam": {"id": 20, "abbrev": "CGY"},
                            "gameState": "FUT",
                        },
                    ],
                }
            ]
        }
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_schedule_for_date(date(2024, 12, 20))

        assert len(result) == 2
        assert result[0].game_id == 2024020521
        assert result[1].game_id == 2024020522
        mock_http_client.get.assert_called_once()

    async def test_get_schedule_for_date_empty(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching schedule for a date with no games."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {"gameWeek": []}
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_schedule_for_date(date(2024, 7, 4))

        assert len(result) == 0

    async def test_get_schedule_for_week(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching schedule for a full week (all days from gameWeek)."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        # Simulate a week with games on multiple days
        mock_response.json.return_value = {
            "gameWeek": [
                {
                    "date": "2024-12-16",
                    "games": [
                        {
                            "id": 2024020500,
                            "season": 20242025,
                            "gameType": 2,
                            "startTimeUTC": "2024-12-17T00:00:00Z",
                            "homeTeam": {"id": 1, "abbrev": "NJD"},
                            "awayTeam": {"id": 2, "abbrev": "NYI"},
                            "gameState": "OFF",
                        },
                    ],
                },
                {
                    "date": "2024-12-17",
                    "games": [
                        {
                            "id": 2024020510,
                            "season": 20242025,
                            "gameType": 2,
                            "startTimeUTC": "2024-12-18T00:00:00Z",
                            "homeTeam": {"id": 3, "abbrev": "NYR"},
                            "awayTeam": {"id": 4, "abbrev": "PHI"},
                            "gameState": "OFF",
                        },
                        {
                            "id": 2024020511,
                            "season": 20242025,
                            "gameType": 2,
                            "startTimeUTC": "2024-12-18T01:00:00Z",
                            "homeTeam": {"id": 5, "abbrev": "PIT"},
                            "awayTeam": {"id": 6, "abbrev": "BOS"},
                            "gameState": "OFF",
                        },
                    ],
                },
                {
                    "date": "2024-12-18",
                    "games": [
                        {
                            "id": 2024020520,
                            "season": 20242025,
                            "gameType": 2,
                            "startTimeUTC": "2024-12-19T00:00:00Z",
                            "homeTeam": {"id": 7, "abbrev": "BUF"},
                            "awayTeam": {"id": 8, "abbrev": "OTT"},
                            "gameState": "OFF",
                        },
                    ],
                },
            ]
        }
        mock_http_client.get.return_value = mock_response

        # Should get ALL games from all days, not just the anchor date
        result = await downloader.get_schedule_for_week(date(2024, 12, 17))

        # 1 + 2 + 1 = 4 games across 3 days
        assert len(result) == 4
        game_ids = [g.game_id for g in result]
        assert 2024020500 in game_ids  # Dec 16
        assert 2024020510 in game_ids  # Dec 17
        assert 2024020511 in game_ids  # Dec 17
        assert 2024020520 in game_ids  # Dec 18
        mock_http_client.get.assert_called_once()


@pytest.mark.unit
class TestCreateScheduleDownloader:
    """Tests for the factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating downloader with default settings."""
        downloader = create_schedule_downloader()

        assert downloader.source_name == "nhl_json_schedule"
        assert downloader.config.base_url == "https://api-web.nhle.com/v1"
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_settings(self) -> None:
        """Test creating downloader with custom settings."""
        downloader = create_schedule_downloader(
            requests_per_second=10.0,
            max_retries=5,
        )

        assert downloader.config.requests_per_second == 10.0
        assert downloader.config.max_retries == 5


@pytest.mark.unit
class TestGameInfo:
    """Tests for GameInfo dataclass."""

    def test_game_info_creation(self) -> None:
        """Test creating GameInfo object."""
        game = GameInfo(
            game_id=2024020521,
            season_id=20242025,
            game_type=2,
            game_date=date(2024, 12, 20),
            start_time_utc=datetime(2024, 12, 21, 0, 0, tzinfo=UTC),
            venue_name="KeyBank Center",
            home_team_id=7,
            home_team_abbrev="BUF",
            home_score=3,
            away_team_id=10,
            away_team_abbrev="TOR",
            away_score=6,
            game_state="OFF",
        )

        assert game.game_id == 2024020521
        assert game.game_date == date(2024, 12, 20)
        assert game.home_score == 3
        assert game.away_score == 6


@pytest.mark.unit
class TestParseGameEdgeCases:
    """Tests for edge cases in _parse_game."""

    def test_parse_invalid_start_time(self) -> None:
        """Test parsing game with invalid start time format."""
        game_data = {
            "id": 2024020100,
            "season": 20242025,
            "gameType": 2,
            "startTimeUTC": "invalid-datetime-format",
            "homeTeam": {"id": 1, "abbrev": "BOS"},
            "awayTeam": {"id": 2, "abbrev": "NYR"},
            "gameState": "FUT",
        }

        result = _parse_game(game_data)

        # Should parse successfully with None start_time
        assert result.game_id == 2024020100
        assert result.start_time_utc is None
        # Should use today's date as fallback
        assert result.game_date == date.today()


@pytest.mark.unit
class TestScheduleDownloaderAdvanced:
    """Advanced tests for ScheduleDownloader class."""

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
    ) -> ScheduleDownloader:
        """Create a ScheduleDownloader with mock HTTP client."""
        config = DownloaderConfig(
            base_url="https://api-web.nhle.com/v1",
            requests_per_second=10.0,
        )
        dl = ScheduleDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False
        return dl

    async def test_fetch_game(
        self,
        downloader: ScheduleDownloader,
    ) -> None:
        """Test _fetch_game returns minimal game data."""
        result = await downloader._fetch_game(2024020521)

        assert result["id"] == 2024020521
        assert result["season"] == 20242025  # Derived from game ID: 2024 * 10000 + 2025
        assert result["gameType"] == 2
        assert "_source" in result

    async def test_get_schedule_for_date_failure(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of failed schedule fetch."""
        from nhl_api.downloaders.base.protocol import DownloadError

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 500
        mock_response.retry_after = None
        mock_http_client.get.return_value = mock_response

        with pytest.raises(DownloadError) as exc_info:
            await downloader.get_schedule_for_date(date(2024, 12, 20))

        assert "Failed to fetch schedule" in str(exc_info.value)
        assert "500" in str(exc_info.value)

    async def test_get_schedule_for_date_with_parse_error(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that parse errors for individual games are logged but not fatal."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "gameWeek": [
                {
                    "date": "2024-12-20",
                    "games": [
                        # Valid game
                        {
                            "id": 2024020521,
                            "season": 20242025,
                            "gameType": 2,
                            "startTimeUTC": "2024-12-21T00:00:00Z",
                            "homeTeam": {"id": 7, "abbrev": "BUF"},
                            "awayTeam": {"id": 10, "abbrev": "TOR"},
                            "gameState": "FUT",
                        },
                        # Invalid game (missing required id key)
                        {"homeTeam": {}, "awayTeam": {}},
                    ],
                }
            ]
        }
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_schedule_for_date(date(2024, 12, 20))

        # Should return only the valid game
        assert len(result) == 1
        assert result[0].game_id == 2024020521

    async def test_get_games_in_range(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching games in a date range."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "gameWeek": [
                {
                    "date": "2024-12-20",
                    "games": [
                        {
                            "id": 2024020521,
                            "season": 20242025,
                            "gameType": 2,
                            "startTimeUTC": "2024-12-20T00:00:00Z",
                            "homeTeam": {"id": 7, "abbrev": "BUF"},
                            "awayTeam": {"id": 10, "abbrev": "TOR"},
                            "gameState": "OFF",
                        },
                    ],
                }
            ]
        }
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_games_in_range(
            date(2024, 12, 20),
            date(2024, 12, 25),
        )

        assert len(result) >= 1
        assert result[0].game_id == 2024020521

    async def test_get_games_in_range_handles_errors(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that get_games_in_range handles errors gracefully."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 404
        mock_response.retry_after = None
        mock_http_client.get.return_value = mock_response

        # Should not raise, just return empty list
        result = await downloader.get_games_in_range(
            date(2024, 12, 20),
            date(2024, 12, 25),
        )

        assert result == []

    async def test_get_season_schedule(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching full season schedule."""

        async def mock_get_response(url: str, **kwargs: Any) -> MagicMock:
            """Return mock response with date matching the request."""
            response = MagicMock()
            response.is_success = True
            response.is_rate_limited = False
            response.is_server_error = False
            response.status = 200
            response.retry_after = None

            # Extract date from URL like "schedule/2024-09-15"
            date_str = url.split("/")[-1]

            response.json.return_value = {
                "gameWeek": [
                    {
                        "date": date_str,
                        "games": [
                            {
                                "id": 2024020001,
                                "season": 20242025,
                                "gameType": 2,
                                "startTimeUTC": f"{date_str}T00:00:00Z",
                                "homeTeam": {"id": 1, "abbrev": "BOS"},
                                "awayTeam": {"id": 2, "abbrev": "NYR"},
                                "gameState": "OFF",
                            },
                        ],
                    }
                ]
            }
            return response

        mock_http_client.get.side_effect = mock_get_response

        result = await downloader.get_season_schedule(20242025)

        # Should have found games (deduplicated across weeks)
        assert len(result) >= 1
        assert result[0].game_id == 2024020001

    async def test_get_season_schedule_with_game_type_filter(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test season schedule filtering by game type."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None

        # Mix of preseason (1) and regular season (2) games
        mock_response.json.return_value = {
            "gameWeek": [
                {
                    "date": "2024-09-20",
                    "games": [
                        {
                            "id": 2024010001,
                            "season": 20242025,
                            "gameType": 1,  # preseason
                            "startTimeUTC": "2024-09-20T00:00:00Z",
                            "homeTeam": {"id": 1, "abbrev": "BOS"},
                            "awayTeam": {"id": 2, "abbrev": "NYR"},
                            "gameState": "OFF",
                        },
                        {
                            "id": 2024020001,
                            "season": 20242025,
                            "gameType": 2,  # regular season
                            "startTimeUTC": "2024-09-20T00:00:00Z",
                            "homeTeam": {"id": 3, "abbrev": "TOR"},
                            "awayTeam": {"id": 4, "abbrev": "MTL"},
                            "gameState": "OFF",
                        },
                    ],
                }
            ]
        }
        mock_http_client.get.return_value = mock_response

        # Filter for regular season only
        result = await downloader.get_season_schedule(20242025, game_type=2)

        # Check that preseason games were filtered out
        for game in result:
            assert game.game_type == 2

    async def test_get_season_schedule_skips_wrong_season(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that games from wrong season are filtered out."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None

        mock_response.json.return_value = {
            "gameWeek": [
                {
                    "date": "2024-10-01",
                    "games": [
                        {
                            "id": 2024020001,
                            "season": 20232024,  # Wrong season!
                            "gameType": 2,
                            "startTimeUTC": "2024-10-01T00:00:00Z",
                            "homeTeam": {"id": 1, "abbrev": "BOS"},
                            "awayTeam": {"id": 2, "abbrev": "NYR"},
                            "gameState": "OFF",
                        },
                    ],
                }
            ]
        }
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_season_schedule(20242025)

        # Games from wrong season should be filtered out
        assert all(g.season_id == 20242025 for g in result)

    async def test_fetch_season_games_generator(
        self,
        downloader: ScheduleDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test _fetch_season_games async generator."""

        async def mock_get_response(url: str, **kwargs: Any) -> MagicMock:
            """Return mock response with date matching the request."""
            response = MagicMock()
            response.is_success = True
            response.is_rate_limited = False
            response.is_server_error = False
            response.status = 200
            response.retry_after = None

            # Extract date from URL like "schedule/2024-09-15"
            date_str = url.split("/")[-1]

            response.json.return_value = {
                "gameWeek": [
                    {
                        "date": date_str,
                        "games": [
                            {
                                "id": 2024020001,
                                "season": 20242025,
                                "gameType": 2,
                                "startTimeUTC": f"{date_str}T00:00:00Z",
                                "homeTeam": {"id": 1, "abbrev": "BOS"},
                                "awayTeam": {"id": 2, "abbrev": "NYR"},
                                "gameState": "OFF",
                            },
                        ],
                    }
                ]
            }
            return response

        mock_http_client.get.side_effect = mock_get_response

        game_ids = []
        async for game_id in downloader._fetch_season_games(20242025):
            game_ids.append(game_id)

        assert len(game_ids) >= 1


@pytest.mark.unit
class TestScheduleDownloaderPersist:
    """Tests for ScheduleDownloader.persist() method."""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """Create a mock database service."""
        db = MagicMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def downloader(self) -> ScheduleDownloader:
        """Create a ScheduleDownloader for testing."""
        config = DownloaderConfig(
            base_url="https://api-web.nhle.com/v1",
            requests_per_second=10.0,
        )
        return ScheduleDownloader(config)

    @pytest.fixture
    def sample_games(self) -> list[GameInfo]:
        """Create sample games for testing."""
        return [
            GameInfo(
                game_id=2024020001,
                season_id=20242025,
                game_type=2,
                game_date=date(2024, 10, 8),
                start_time_utc=datetime(2024, 10, 8, 23, 0, tzinfo=UTC),
                venue_name="TD Garden",
                home_team_id=6,
                home_team_abbrev="BOS",
                home_score=3,
                away_team_id=10,
                away_team_abbrev="TOR",
                away_score=2,
                game_state="FINAL",
                period=3,
                is_overtime=False,
                is_shootout=False,
            ),
            GameInfo(
                game_id=2024020002,
                season_id=20242025,
                game_type=2,
                game_date=date(2024, 10, 8),
                start_time_utc=datetime(2024, 10, 9, 0, 0, tzinfo=UTC),
                venue_name="Madison Square Garden",
                home_team_id=3,
                home_team_abbrev="NYR",
                home_score=4,
                away_team_id=1,
                away_team_abbrev="NJD",
                away_score=5,
                game_state="FINAL",
                period=4,
                is_overtime=True,
                is_shootout=False,
            ),
        ]

    async def test_persist_empty_list(
        self,
        downloader: ScheduleDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test persisting an empty list returns 0."""
        result = await downloader.persist(mock_db, [])

        assert result == 0
        mock_db.execute.assert_not_called()

    async def test_persist_single_game(
        self,
        downloader: ScheduleDownloader,
        mock_db: MagicMock,
        sample_games: list[GameInfo],
    ) -> None:
        """Test persisting a single game."""
        result = await downloader.persist(mock_db, [sample_games[0]])

        assert result == 1
        mock_db.execute.assert_called_once()

        # Verify the SQL was called with correct parameters
        call_args = mock_db.execute.call_args
        assert call_args[0][1] == 2024020001  # game_id
        assert call_args[0][2] == 20242025  # season_id
        assert call_args[0][3] == "R"  # game_type (2 -> "R")
        assert call_args[0][4] == date(2024, 10, 8)  # game_date

    async def test_persist_multiple_games(
        self,
        downloader: ScheduleDownloader,
        mock_db: MagicMock,
        sample_games: list[GameInfo],
    ) -> None:
        """Test persisting multiple games."""
        result = await downloader.persist(mock_db, sample_games)

        assert result == 2
        assert mock_db.execute.call_count == 2

    async def test_persist_game_type_mapping(
        self,
        downloader: ScheduleDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test that game types are correctly mapped to string codes."""
        test_cases = [
            (1, "PR"),  # Preseason
            (2, "R"),  # Regular
            (3, "P"),  # Playoffs
            (4, "A"),  # All-Star
        ]

        for game_type_int, expected_code in test_cases:
            mock_db.execute.reset_mock()

            game = GameInfo(
                game_id=2024020001,
                season_id=20242025,
                game_type=game_type_int,
                game_date=date(2024, 10, 8),
                start_time_utc=None,
                venue_name=None,
                home_team_id=1,
                home_team_abbrev="BOS",
                home_score=None,
                away_team_id=2,
                away_team_abbrev="NYR",
                away_score=None,
                game_state="FUT",
            )

            await downloader.persist(mock_db, [game])

            call_args = mock_db.execute.call_args
            assert call_args[0][3] == expected_code, (
                f"Expected {expected_code} for game_type {game_type_int}"
            )

    async def test_persist_game_outcome_regular(
        self,
        downloader: ScheduleDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test game outcome is REG for regulation win."""
        game = GameInfo(
            game_id=2024020001,
            season_id=20242025,
            game_type=2,
            game_date=date(2024, 10, 8),
            start_time_utc=None,
            venue_name=None,
            home_team_id=1,
            home_team_abbrev="BOS",
            home_score=3,
            away_team_id=2,
            away_team_abbrev="NYR",
            away_score=2,
            game_state="FINAL",
            period=3,
            is_overtime=False,
            is_shootout=False,
        )

        await downloader.persist(mock_db, [game])

        call_args = mock_db.execute.call_args
        # game_outcome is the 14th parameter (index 13 in 0-indexed after SQL)
        assert call_args[0][14] == "REG"

    async def test_persist_game_outcome_overtime(
        self,
        downloader: ScheduleDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test game outcome is OT for overtime win."""
        game = GameInfo(
            game_id=2024020001,
            season_id=20242025,
            game_type=2,
            game_date=date(2024, 10, 8),
            start_time_utc=None,
            venue_name=None,
            home_team_id=1,
            home_team_abbrev="BOS",
            home_score=3,
            away_team_id=2,
            away_team_abbrev="NYR",
            away_score=2,
            game_state="FINAL",
            period=4,
            is_overtime=True,
            is_shootout=False,
        )

        await downloader.persist(mock_db, [game])

        call_args = mock_db.execute.call_args
        assert call_args[0][14] == "OT"

    async def test_persist_game_outcome_shootout(
        self,
        downloader: ScheduleDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test game outcome is SO for shootout win."""
        game = GameInfo(
            game_id=2024020001,
            season_id=20242025,
            game_type=2,
            game_date=date(2024, 10, 8),
            start_time_utc=None,
            venue_name=None,
            home_team_id=1,
            home_team_abbrev="BOS",
            home_score=3,
            away_team_id=2,
            away_team_abbrev="NYR",
            away_score=2,
            game_state="FINAL",
            period=5,
            is_overtime=True,
            is_shootout=True,
        )

        await downloader.persist(mock_db, [game])

        call_args = mock_db.execute.call_args
        assert call_args[0][14] == "SO"

    async def test_persist_future_game_no_outcome(
        self,
        downloader: ScheduleDownloader,
        mock_db: MagicMock,
    ) -> None:
        """Test future games have no game outcome."""
        game = GameInfo(
            game_id=2024020001,
            season_id=20242025,
            game_type=2,
            game_date=date(2024, 12, 25),
            start_time_utc=datetime(2024, 12, 25, 20, 0, tzinfo=UTC),
            venue_name="TD Garden",
            home_team_id=1,
            home_team_abbrev="BOS",
            home_score=None,
            away_team_id=2,
            away_team_abbrev="NYR",
            away_score=None,
            game_state="FUT",
        )

        await downloader.persist(mock_db, [game])

        call_args = mock_db.execute.call_args
        assert call_args[0][14] is None  # No game outcome for future games
