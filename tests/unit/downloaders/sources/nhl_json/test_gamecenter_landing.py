"""Tests for Gamecenter Landing Downloader."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.sources.nhl_json.gamecenter_landing import (
    GamecenterLandingDownloader,
    GamecenterLandingDownloaderConfig,
    _parse_highlight,
    _parse_landing,
    _parse_team_matchup,
    _parse_three_star,
    create_gamecenter_landing_downloader,
)


@pytest.mark.unit
class TestParseThreeStar:
    """Tests for _parse_three_star function."""

    def test_parse_three_star_complete(self) -> None:
        """Test parsing a complete three star entry."""
        star_data = {
            "playerId": 8478402,
            "name": {"default": "Connor McDavid"},
            "teamAbbrev": "EDM",
            "position": "C",
            "goals": 2,
            "assists": 3,
        }

        result = _parse_three_star(star_data, 1)

        assert result.star == 1
        assert result.player_id == 8478402
        assert result.name == "Connor McDavid"
        assert result.team_abbrev == "EDM"
        assert result.position == "C"
        assert result.goals == 2
        assert result.assists == 3
        assert result.points == 5

    def test_parse_three_star_minimal(self) -> None:
        """Test parsing a minimal three star entry."""
        star_data: dict[str, Any] = {}

        result = _parse_three_star(star_data, 2)

        assert result.star == 2
        assert result.player_id == 0
        assert result.name == "Unknown"
        assert result.team_abbrev == ""
        assert result.points == 0


@pytest.mark.unit
class TestParseHighlight:
    """Tests for _parse_highlight function."""

    def test_parse_highlight_complete(self) -> None:
        """Test parsing a complete highlight entry."""
        highlight_data = {
            "id": 12345,
            "title": "McDavid Goal",
            "description": "Connor McDavid scores a beauty",
            "duration": 45,
            "thumbnail": {"src": "https://example.com/thumb.jpg"},
            "playbacks": [{"url": "https://example.com/video.mp4"}],
        }

        result = _parse_highlight(highlight_data)

        assert result.highlight_id == 12345
        assert result.title == "McDavid Goal"
        assert result.description == "Connor McDavid scores a beauty"
        assert result.duration == 45
        assert result.thumbnail_url == "https://example.com/thumb.jpg"
        assert result.video_url == "https://example.com/video.mp4"

    def test_parse_highlight_no_playbacks(self) -> None:
        """Test parsing highlight without playbacks."""
        highlight_data = {
            "id": 12346,
            "title": "Game Recap",
            "description": "Full game highlights",
            "duration": 120,
        }

        result = _parse_highlight(highlight_data)

        assert result.highlight_id == 12346
        assert result.video_url is None
        assert result.thumbnail_url is None


@pytest.mark.unit
class TestParseTeamMatchup:
    """Tests for _parse_team_matchup function."""

    def test_parse_team_matchup_complete(self) -> None:
        """Test parsing complete team matchup data."""
        team_data = {
            "id": 22,
            "abbrev": "EDM",
            "name": {"default": "Oilers"},
            "record": "25-10-3",
            "powerPlayPct": 25.5,
            "penaltyKillPct": 82.3,
        }

        result = _parse_team_matchup(team_data)

        assert result.team_id == 22
        assert result.abbrev == "EDM"
        assert result.name == "Oilers"
        assert result.record == "25-10-3"
        assert result.power_play_pct == 25.5
        assert result.penalty_kill_pct == 82.3


@pytest.mark.unit
class TestParseLanding:
    """Tests for _parse_landing function."""

    def test_parse_landing_completed_game(self) -> None:
        """Test parsing a completed game landing page."""
        data = {
            "id": 2024020500,
            "season": 20242025,
            "gameType": 2,
            "gameState": "OFF",
            "venue": {"default": "Rogers Place"},
            "attendance": 18347,
            "neutralSite": False,
            "firstStar": {
                "playerId": 8478402,
                "name": {"default": "Connor McDavid"},
                "teamAbbrev": "EDM",
                "position": "C",
                "goals": 2,
                "assists": 1,
            },
            "secondStar": {
                "playerId": 8477934,
                "name": {"default": "Leon Draisaitl"},
                "teamAbbrev": "EDM",
                "position": "C",
                "goals": 1,
                "assists": 2,
            },
            "thirdStar": {
                "playerId": 8479339,
                "name": {"default": "Evan Bouchard"},
                "teamAbbrev": "EDM",
                "position": "D",
                "goals": 0,
                "assists": 3,
            },
            "homeTeam": {
                "id": 22,
                "abbrev": "EDM",
                "name": {"default": "Oilers"},
                "record": "25-10-3",
            },
            "awayTeam": {
                "id": 20,
                "abbrev": "CGY",
                "name": {"default": "Flames"},
                "record": "15-20-5",
            },
        }

        result = _parse_landing(data)

        assert result.game_id == 2024020500
        assert result.season_id == 20242025
        assert result.game_type == 2
        assert result.game_state == "OFF"
        assert result.venue == "Rogers Place"
        assert result.attendance == 18347
        assert len(result.three_stars) == 3
        assert result.three_stars[0].star == 1
        assert result.three_stars[0].name == "Connor McDavid"
        assert result.home_team is not None
        assert result.home_team.abbrev == "EDM"
        assert result.away_team is not None
        assert result.away_team.abbrev == "CGY"
        assert result.neutral_site is False

    def test_parse_landing_future_game(self) -> None:
        """Test parsing a future game landing page."""
        data = {
            "id": 2024020600,
            "season": 20242025,
            "gameType": 2,
            "gameState": "FUT",
            "venue": {"default": "Madison Square Garden"},
            "homeTeam": {"id": 3, "abbrev": "NYR", "name": {"default": "Rangers"}},
            "awayTeam": {"id": 4, "abbrev": "PHI", "name": {"default": "Flyers"}},
        }

        result = _parse_landing(data)

        assert result.game_state == "FUT"
        assert len(result.three_stars) == 0
        assert result.attendance is None

    def test_parse_landing_include_raw(self) -> None:
        """Test parsing with raw data inclusion."""
        data = {"id": 2024020500, "season": 20242025}

        result = _parse_landing(data, include_raw=True)

        assert result.raw_data is not None
        assert result.raw_data["id"] == 2024020500


@pytest.mark.unit
class TestGamecenterLandingDownloader:
    """Tests for GamecenterLandingDownloader class."""

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
    ) -> GamecenterLandingDownloader:
        """Create a downloader instance with mocks."""
        config = GamecenterLandingDownloaderConfig()
        dl = GamecenterLandingDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False  # Don't close the mock
        return dl

    def test_source_name(self, downloader: GamecenterLandingDownloader) -> None:
        """Test that source_name returns correct identifier."""
        assert downloader.source_name == "nhl_json_gamecenter_landing"

    @pytest.mark.asyncio
    async def test_fetch_game_success(
        self,
        downloader: GamecenterLandingDownloader,
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
            "id": 2024020500,
            "season": 20242025,
            "gameType": 2,
            "gameState": "OFF",
        }
        mock_http_client.get.return_value = mock_response

        result = await downloader._fetch_game(2024020500)

        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025


@pytest.mark.unit
class TestFactoryFunction:
    """Tests for create_gamecenter_landing_downloader factory."""

    def test_create_with_defaults(self) -> None:
        """Test factory with default parameters."""
        downloader = create_gamecenter_landing_downloader()

        assert isinstance(downloader, GamecenterLandingDownloader)
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_params(self) -> None:
        """Test factory with custom parameters."""
        downloader = create_gamecenter_landing_downloader(
            requests_per_second=2.0,
            max_retries=5,
            include_raw_response=True,
        )

        assert downloader.config.requests_per_second == 2.0
        assert downloader.config.max_retries == 5
