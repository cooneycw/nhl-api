"""Unit tests for PowerPlayDownloader."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.dailyfaceoff import (
    PowerPlayDownloader,
    PowerPlayPlayer,
    PowerPlayUnit,
    TeamPowerPlay,
)

# Path to fixtures
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "dailyfaceoff"
)


class TestPowerPlayPlayer:
    """Tests for PowerPlayPlayer dataclass."""

    def test_create_player(self) -> None:
        """Test creating a player with all fields."""
        player = PowerPlayPlayer(
            player_id=28001,
            name="Morgan Geekie",
            jersey_number=39,
            position="sk1",
            rating=74.5,
            season_goals=25,
            season_assists=14,
            season_points=39,
        )
        assert player.player_id == 28001
        assert player.name == "Morgan Geekie"
        assert player.jersey_number == 39
        assert player.position == "sk1"
        assert player.rating == 74.5
        assert player.season_goals == 25
        assert player.season_assists == 14
        assert player.season_points == 39

    def test_create_player_minimal(self) -> None:
        """Test creating a player with minimal fields."""
        player = PowerPlayPlayer(
            player_id=12345,
            name="Test Player",
            jersey_number=1,
            position="sk1",
        )
        assert player.player_id == 12345
        assert player.name == "Test Player"
        assert player.rating is None
        assert player.season_goals is None
        assert player.season_assists is None
        assert player.season_points is None

    def test_player_is_frozen(self) -> None:
        """Test that player is immutable."""
        player = PowerPlayPlayer(
            player_id=1,
            name="Test",
            jersey_number=1,
            position="sk1",
        )
        with pytest.raises(AttributeError):
            player.name = "Changed"  # type: ignore[misc]


class TestPowerPlayUnit:
    """Tests for PowerPlayUnit dataclass."""

    def test_create_unit(self) -> None:
        """Test creating a power play unit."""
        players = tuple(
            PowerPlayPlayer(
                player_id=i,
                name=f"Player {i}",
                jersey_number=i,
                position=f"sk{i}",
            )
            for i in range(1, 6)
        )
        unit = PowerPlayUnit(unit_number=1, players=players)
        assert unit.unit_number == 1
        assert len(unit.players) == 5

    def test_unit_too_many_players(self) -> None:
        """Test that unit rejects more than 5 players."""
        players = tuple(
            PowerPlayPlayer(
                player_id=i,
                name=f"Player {i}",
                jersey_number=i,
                position=f"sk{i}",
            )
            for i in range(1, 8)  # 7 players
        )
        with pytest.raises(ValueError, match="cannot have more than 5 players"):
            PowerPlayUnit(unit_number=1, players=players)

    def test_unit_is_frozen(self) -> None:
        """Test that unit is immutable."""
        unit = PowerPlayUnit(unit_number=1, players=())
        with pytest.raises(AttributeError):
            unit.unit_number = 2  # type: ignore[misc]


class TestTeamPowerPlay:
    """Tests for TeamPowerPlay dataclass."""

    def test_create_team_pp(self) -> None:
        """Test creating team power play data."""
        now = datetime.now(UTC)
        team_pp = TeamPowerPlay(
            team_id=6,
            team_abbreviation="BOS",
            pp1=None,
            pp2=None,
            fetched_at=now,
        )
        assert team_pp.team_id == 6
        assert team_pp.team_abbreviation == "BOS"
        assert team_pp.pp1 is None
        assert team_pp.pp2 is None
        assert team_pp.fetched_at == now

    def test_team_pp_with_units(self) -> None:
        """Test team PP with actual units."""
        players = tuple(
            PowerPlayPlayer(
                player_id=i,
                name=f"Player {i}",
                jersey_number=i,
                position=f"sk{i}",
            )
            for i in range(1, 6)
        )
        pp1 = PowerPlayUnit(unit_number=1, players=players)
        pp2 = PowerPlayUnit(unit_number=2, players=players)
        now = datetime.now(UTC)

        team_pp = TeamPowerPlay(
            team_id=6,
            team_abbreviation="BOS",
            pp1=pp1,
            pp2=pp2,
            fetched_at=now,
        )
        assert team_pp.pp1 is not None
        assert team_pp.pp2 is not None
        assert len(team_pp.pp1.players) == 5
        assert len(team_pp.pp2.players) == 5


class TestPowerPlayDownloader:
    """Tests for PowerPlayDownloader."""

    def test_data_type(self) -> None:
        """Test data_type property."""
        downloader = PowerPlayDownloader()
        assert downloader.data_type == "power_play"

    def test_page_path(self) -> None:
        """Test page_path property."""
        downloader = PowerPlayDownloader()
        assert downloader.page_path == "line-combinations"

    def test_source_name(self) -> None:
        """Test source_name property."""
        downloader = PowerPlayDownloader()
        assert downloader.source_name == "dailyfaceoff_power_play"

    def test_extract_next_data_valid(self) -> None:
        """Test extracting __NEXT_DATA__ from valid HTML."""
        html = """
        <!DOCTYPE html>
        <html>
        <head></head>
        <body>
        <script id="__NEXT_DATA__" type="application/json">
        {"props": {"pageProps": {"test": "data"}}}
        </script>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        downloader = PowerPlayDownloader()
        result = downloader._extract_next_data(soup)
        assert result is not None
        assert result["props"]["pageProps"]["test"] == "data"

    def test_extract_next_data_missing(self) -> None:
        """Test extracting __NEXT_DATA__ from HTML without it."""
        html = "<html><body>No data here</body></html>"
        soup = BeautifulSoup(html, "lxml")
        downloader = PowerPlayDownloader()
        result = downloader._extract_next_data(soup)
        assert result is None

    def test_extract_next_data_invalid_json(self) -> None:
        """Test extracting __NEXT_DATA__ with invalid JSON."""
        html = """
        <html>
        <body>
        <script id="__NEXT_DATA__" type="application/json">
        {invalid json}
        </script>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        downloader = PowerPlayDownloader()
        result = downloader._extract_next_data(soup)
        assert result is None

    def test_get_players_from_next_data(self) -> None:
        """Test navigating to players array."""
        next_data = {
            "props": {"pageProps": {"combinations": {"players": [{"name": "Test"}]}}}
        }
        downloader = PowerPlayDownloader()
        result = downloader._get_players_from_next_data(next_data)
        assert len(result) == 1
        assert result[0]["name"] == "Test"

    def test_get_players_from_next_data_missing_path(self) -> None:
        """Test navigating when path doesn't exist."""
        next_data: dict[str, Any] = {"props": {}}
        downloader = PowerPlayDownloader()
        result = downloader._get_players_from_next_data(next_data)
        assert result == []

    def test_get_players_from_next_data_none(self) -> None:
        """Test navigating with None values in path."""
        next_data: dict[str, Any] = {"props": None}
        downloader = PowerPlayDownloader()
        result = downloader._get_players_from_next_data(next_data)
        assert result == []

    def test_parse_player_valid(self) -> None:
        """Test parsing a valid player."""
        player_data = {
            "playerId": 28001,
            "name": "Morgan Geekie",
            "jerseyNumber": 39,
            "positionIdentifier": "sk1",
            "rating": 74.5,
            "season": {
                "goals": 25,
                "assists": 14,
                "points": 39,
            },
        }
        downloader = PowerPlayDownloader()
        player = downloader._parse_player(player_data)
        assert player is not None
        assert player.player_id == 28001
        assert player.name == "Morgan Geekie"
        assert player.jersey_number == 39
        assert player.position == "sk1"
        assert player.rating == 74.5
        assert player.season_goals == 25
        assert player.season_assists == 14
        assert player.season_points == 39

    def test_parse_player_missing_name(self) -> None:
        """Test parsing player without required name field."""
        player_data = {
            "playerId": 28001,
            "jerseyNumber": 39,
            "positionIdentifier": "sk1",
        }
        downloader = PowerPlayDownloader()
        player = downloader._parse_player(player_data)
        assert player is None

    def test_parse_player_missing_player_id(self) -> None:
        """Test parsing player without required playerId field."""
        player_data = {
            "name": "Test Player",
            "jerseyNumber": 39,
            "positionIdentifier": "sk1",
        }
        downloader = PowerPlayDownloader()
        player = downloader._parse_player(player_data)
        assert player is None

    def test_parse_player_missing_position(self) -> None:
        """Test parsing player without required position field."""
        player_data = {
            "playerId": 28001,
            "name": "Test Player",
            "jerseyNumber": 39,
        }
        downloader = PowerPlayDownloader()
        player = downloader._parse_player(player_data)
        assert player is None

    def test_parse_player_no_jersey_number(self) -> None:
        """Test parsing player without jersey number (uses 0)."""
        player_data = {
            "playerId": 28001,
            "name": "Test Player",
            "positionIdentifier": "sk1",
        }
        downloader = PowerPlayDownloader()
        player = downloader._parse_player(player_data)
        assert player is not None
        assert player.jersey_number == 0

    def test_parse_player_no_season_stats(self) -> None:
        """Test parsing player without season stats."""
        player_data = {
            "playerId": 28001,
            "name": "Test Player",
            "jerseyNumber": 99,
            "positionIdentifier": "sk1",
        }
        downloader = PowerPlayDownloader()
        player = downloader._parse_player(player_data)
        assert player is not None
        assert player.season_goals is None
        assert player.season_assists is None
        assert player.season_points is None

    def test_parse_player_null_season(self) -> None:
        """Test parsing player with null season object."""
        player_data = {
            "playerId": 28001,
            "name": "Test Player",
            "jerseyNumber": 99,
            "positionIdentifier": "sk1",
            "season": None,
        }
        downloader = PowerPlayDownloader()
        player = downloader._parse_player(player_data)
        assert player is not None
        assert player.season_goals is None

    def test_parse_unit_valid(self) -> None:
        """Test parsing a valid power play unit."""
        players_data = [
            {
                "playerId": i,
                "name": f"Player {i}",
                "jerseyNumber": i,
                "positionIdentifier": f"sk{i}",
                "groupIdentifier": "pp1",
            }
            for i in range(1, 6)
        ]
        downloader = PowerPlayDownloader()
        unit = downloader._parse_unit(players_data, "pp1", 1)
        assert unit is not None
        assert unit.unit_number == 1
        assert len(unit.players) == 5

    def test_parse_unit_empty(self) -> None:
        """Test parsing when no players match the group."""
        players_data = [
            {
                "playerId": 1,
                "name": "Player 1",
                "jerseyNumber": 1,
                "positionIdentifier": "sk1",
                "groupIdentifier": "pp2",  # Different group
            }
        ]
        downloader = PowerPlayDownloader()
        unit = downloader._parse_unit(players_data, "pp1", 1)
        assert unit is None

    def test_parse_unit_sorted_by_position(self) -> None:
        """Test that players are sorted by position."""
        # Add players in reverse order
        players_data = [
            {
                "playerId": 5,
                "name": "Player 5",
                "jerseyNumber": 5,
                "positionIdentifier": "sk5",
                "groupIdentifier": "pp1",
            },
            {
                "playerId": 1,
                "name": "Player 1",
                "jerseyNumber": 1,
                "positionIdentifier": "sk1",
                "groupIdentifier": "pp1",
            },
            {
                "playerId": 3,
                "name": "Player 3",
                "jerseyNumber": 3,
                "positionIdentifier": "sk3",
                "groupIdentifier": "pp1",
            },
        ]
        downloader = PowerPlayDownloader()
        unit = downloader._parse_unit(players_data, "pp1", 1)
        assert unit is not None
        assert unit.players[0].position == "sk1"
        assert unit.players[1].position == "sk3"
        assert unit.players[2].position == "sk5"

    def test_to_dict_full(self) -> None:
        """Test converting TeamPowerPlay to dict."""
        players = tuple(
            PowerPlayPlayer(
                player_id=i,
                name=f"Player {i}",
                jersey_number=i,
                position=f"sk{i}",
                rating=50.0 + i,
                season_goals=10 + i,
                season_assists=20 + i,
                season_points=30 + i,
            )
            for i in range(1, 6)
        )
        pp1 = PowerPlayUnit(unit_number=1, players=players)
        now = datetime.now(UTC)
        team_pp = TeamPowerPlay(
            team_id=6,
            team_abbreviation="BOS",
            pp1=pp1,
            pp2=None,
            fetched_at=now,
        )
        downloader = PowerPlayDownloader()
        result = downloader._to_dict(team_pp)

        assert "pp1" in result
        assert "pp2" in result
        assert "fetched_at" in result
        assert result["pp1"]["unit_number"] == 1
        assert len(result["pp1"]["players"]) == 5
        assert result["pp2"] is None
        assert result["fetched_at"] == now.isoformat()

    def test_to_dict_empty(self) -> None:
        """Test converting TeamPowerPlay with no units to dict."""
        now = datetime.now(UTC)
        team_pp = TeamPowerPlay(
            team_id=6,
            team_abbreviation="BOS",
            pp1=None,
            pp2=None,
            fetched_at=now,
        )
        downloader = PowerPlayDownloader()
        result = downloader._to_dict(team_pp)

        assert result["pp1"] is None
        assert result["pp2"] is None

    def test_player_to_dict(self) -> None:
        """Test converting player to dict."""
        player = PowerPlayPlayer(
            player_id=28001,
            name="Test Player",
            jersey_number=39,
            position="sk1",
            rating=74.5,
            season_goals=25,
            season_assists=14,
            season_points=39,
        )
        downloader = PowerPlayDownloader()
        result = downloader._player_to_dict(player)

        assert result["player_id"] == 28001
        assert result["name"] == "Test Player"
        assert result["jersey_number"] == 39
        assert result["position"] == "sk1"
        assert result["rating"] == 74.5
        assert result["season_goals"] == 25
        assert result["season_assists"] == 14
        assert result["season_points"] == 39

    def test_empty_result(self) -> None:
        """Test creating empty result."""
        downloader = PowerPlayDownloader()
        result = downloader._empty_result(6, "BOS")

        assert result["pp1"] is None
        assert result["pp2"] is None
        assert "fetched_at" in result


class TestPowerPlayDownloaderIntegration:
    """Integration tests using fixture file."""

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load fixture HTML."""
        fixture_path = FIXTURES_DIR / "line_combinations_boston.html"
        return fixture_path.read_text()

    @pytest.fixture
    def fixture_soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML into BeautifulSoup."""
        return BeautifulSoup(fixture_html, "lxml")

    @pytest.mark.asyncio
    async def test_parse_page_full(self, fixture_soup: BeautifulSoup) -> None:
        """Test parsing full fixture page."""
        downloader = PowerPlayDownloader()
        result = await downloader._parse_page(fixture_soup, 6)

        assert result["pp1"] is not None
        assert result["pp2"] is not None

        # Check PP1
        pp1 = result["pp1"]
        assert pp1["unit_number"] == 1
        assert len(pp1["players"]) == 5
        assert pp1["players"][0]["name"] == "Morgan Geekie"
        assert pp1["players"][0]["jersey_number"] == 39
        assert pp1["players"][0]["rating"] == 74.5
        assert pp1["players"][0]["season_goals"] == 25

        # Check PP2
        pp2 = result["pp2"]
        assert pp2["unit_number"] == 2
        assert len(pp2["players"]) == 5
        assert pp2["players"][0]["name"] == "Pavel Zacha"

    @pytest.mark.asyncio
    async def test_parse_page_filters_non_pp(self, fixture_soup: BeautifulSoup) -> None:
        """Test that non-PP players are filtered out."""
        downloader = PowerPlayDownloader()
        result = await downloader._parse_page(fixture_soup, 6)

        # Elias Lindholm is in l1 (1st line), not PP
        pp1_names = [p["name"] for p in result["pp1"]["players"]]
        pp2_names = [p["name"] for p in result["pp2"]["players"]]
        all_pp_names = pp1_names + pp2_names

        assert "Elias Lindholm" not in all_pp_names

    @pytest.mark.asyncio
    async def test_parse_page_empty_html(self) -> None:
        """Test parsing page with no __NEXT_DATA__."""
        html = "<html><body>Empty</body></html>"
        soup = BeautifulSoup(html, "lxml")
        downloader = PowerPlayDownloader()
        result = await downloader._parse_page(soup, 6)

        assert result["pp1"] is None
        assert result["pp2"] is None


class TestPowerPlayDownloaderDownload:
    """Tests for download_team method."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock HTTP response."""
        fixture_path = FIXTURES_DIR / "line_combinations_boston.html"
        content = fixture_path.read_bytes()

        response = MagicMock()
        response.is_success = True
        response.status = 200
        response.content = content
        return response

    @pytest.mark.asyncio
    async def test_download_team_success(self, mock_response: MagicMock) -> None:
        """Test successful team download."""
        downloader = PowerPlayDownloader()
        object.__setattr__(downloader, "_get", AsyncMock(return_value=mock_response))

        result = await downloader.download_team(6)

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "dailyfaceoff_power_play"
        assert result.data["team_id"] == 6
        assert result.data["team_abbreviation"] == "BOS"
        assert result.data["pp1"] is not None
        assert result.data["pp2"] is not None

    @pytest.mark.asyncio
    async def test_download_team_http_error(self) -> None:
        """Test handling HTTP error."""
        response = MagicMock()
        response.is_success = False
        response.status = 404

        downloader = PowerPlayDownloader()
        object.__setattr__(downloader, "_get", AsyncMock(return_value=response))

        from nhl_api.downloaders.base.protocol import DownloadError

        with pytest.raises(DownloadError, match="HTTP 404"):
            await downloader.download_team(6)

    @pytest.mark.asyncio
    async def test_download_team_invalid_html(self) -> None:
        """Test handling invalid HTML response."""
        response = MagicMock()
        response.is_success = True
        response.status = 200
        response.content = b'{"json": "not html"}'

        downloader = PowerPlayDownloader()
        object.__setattr__(downloader, "_get", AsyncMock(return_value=response))

        from nhl_api.downloaders.base.protocol import DownloadError

        with pytest.raises(DownloadError, match="not valid HTML"):
            await downloader.download_team(6)


class TestPowerPlayDownloaderBulk:
    """Tests for download_all_teams method."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock HTTP response."""
        fixture_path = FIXTURES_DIR / "line_combinations_boston.html"
        content = fixture_path.read_bytes()

        response = MagicMock()
        response.is_success = True
        response.status = 200
        response.content = content
        return response

    @pytest.mark.asyncio
    async def test_download_all_teams(self, mock_response: MagicMock) -> None:
        """Test downloading all teams."""
        # Only test with 3 teams for speed
        downloader = PowerPlayDownloader(team_ids=[6, 10, 1])
        object.__setattr__(downloader, "_get", AsyncMock(return_value=mock_response))

        results = []
        async for result in downloader.download_all_teams():
            results.append(result)

        assert len(results) == 3
        assert all(r.status == DownloadStatus.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_download_all_teams_with_failure(
        self, mock_response: MagicMock
    ) -> None:
        """Test that failures don't stop iteration."""

        # First call succeeds, second fails, third succeeds
        async def side_effect(path: str) -> MagicMock:
            if "new-york-islanders" in path:
                error_response = MagicMock()
                error_response.is_success = False
                error_response.status = 500
                return error_response
            return mock_response

        downloader = PowerPlayDownloader(team_ids=[6, 2, 1])  # BOS, NYI, NJD
        object.__setattr__(downloader, "_get", AsyncMock(side_effect=side_effect))

        results = []
        async for result in downloader.download_all_teams():
            results.append(result)

        assert len(results) == 3
        # BOS and NJD should succeed
        completed = [r for r in results if r.status == DownloadStatus.COMPLETED]
        failed = [r for r in results if r.status == DownloadStatus.FAILED]
        assert len(completed) == 2
        assert len(failed) == 1
