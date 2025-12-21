"""Unit tests for LineCombinationsDownloader."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.dailyfaceoff import (
    DefensivePair,
    ForwardLine,
    GoalieDepth,
    LineCombinationsDownloader,
    PlayerInfo,
    TeamLineup,
)

# Path to fixtures
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "dailyfaceoff"
)


class TestPlayerInfo:
    """Tests for PlayerInfo dataclass."""

    def test_create_player(self) -> None:
        """Test creating a player info."""
        player = PlayerInfo(
            player_id=1001,
            name="Brad Marchand",
            jersey_number=63,
            position="lw",
        )
        assert player.player_id == 1001
        assert player.name == "Brad Marchand"
        assert player.jersey_number == 63
        assert player.position == "lw"

    def test_player_is_frozen(self) -> None:
        """Test that player is immutable."""
        player = PlayerInfo(
            player_id=1,
            name="Test",
            jersey_number=1,
            position="c",
        )
        with pytest.raises(AttributeError):
            player.name = "Changed"  # type: ignore[misc]


class TestForwardLine:
    """Tests for ForwardLine dataclass."""

    def test_create_full_line(self) -> None:
        """Test creating a complete forward line."""
        lw = PlayerInfo(player_id=1, name="LW", jersey_number=1, position="lw")
        c = PlayerInfo(player_id=2, name="C", jersey_number=2, position="c")
        rw = PlayerInfo(player_id=3, name="RW", jersey_number=3, position="rw")

        line = ForwardLine(line_number=1, left_wing=lw, center=c, right_wing=rw)
        assert line.line_number == 1
        assert line.left_wing is not None
        assert line.center is not None
        assert line.right_wing is not None

    def test_create_partial_line(self) -> None:
        """Test creating a line with missing players."""
        line = ForwardLine(line_number=2, left_wing=None, center=None, right_wing=None)
        assert line.line_number == 2
        assert line.left_wing is None
        assert line.center is None
        assert line.right_wing is None

    def test_line_is_frozen(self) -> None:
        """Test that line is immutable."""
        line = ForwardLine(line_number=1, left_wing=None, center=None, right_wing=None)
        with pytest.raises(AttributeError):
            line.line_number = 2  # type: ignore[misc]


class TestDefensivePair:
    """Tests for DefensivePair dataclass."""

    def test_create_full_pair(self) -> None:
        """Test creating a complete defensive pair."""
        ld = PlayerInfo(player_id=1, name="LD", jersey_number=1, position="ld")
        rd = PlayerInfo(player_id=2, name="RD", jersey_number=2, position="rd")

        pair = DefensivePair(pair_number=1, left_defense=ld, right_defense=rd)
        assert pair.pair_number == 1
        assert pair.left_defense is not None
        assert pair.right_defense is not None

    def test_create_partial_pair(self) -> None:
        """Test creating a pair with missing players."""
        pair = DefensivePair(pair_number=3, left_defense=None, right_defense=None)
        assert pair.pair_number == 3
        assert pair.left_defense is None
        assert pair.right_defense is None


class TestGoalieDepth:
    """Tests for GoalieDepth dataclass."""

    def test_create_full_goalies(self) -> None:
        """Test creating full goalie depth."""
        starter = PlayerInfo(
            player_id=1, name="Starter", jersey_number=30, position="g1"
        )
        backup = PlayerInfo(player_id=2, name="Backup", jersey_number=35, position="g2")

        goalies = GoalieDepth(starter=starter, backup=backup)
        assert goalies.starter is not None
        assert goalies.backup is not None

    def test_create_empty_goalies(self) -> None:
        """Test creating empty goalie depth."""
        goalies = GoalieDepth(starter=None, backup=None)
        assert goalies.starter is None
        assert goalies.backup is None


class TestTeamLineup:
    """Tests for TeamLineup dataclass."""

    def test_create_lineup(self) -> None:
        """Test creating team lineup."""
        lines = tuple(
            ForwardLine(line_number=i, left_wing=None, center=None, right_wing=None)
            for i in range(1, 5)
        )
        pairs = tuple(
            DefensivePair(pair_number=i, left_defense=None, right_defense=None)
            for i in range(1, 4)
        )
        goalies = GoalieDepth(starter=None, backup=None)
        now = datetime.now(UTC)

        lineup = TeamLineup(
            team_id=6,
            team_abbreviation="BOS",
            forward_lines=lines,
            defensive_pairs=pairs,
            goalies=goalies,
            fetched_at=now,
        )
        assert lineup.team_id == 6
        assert lineup.team_abbreviation == "BOS"
        assert len(lineup.forward_lines) == 4
        assert len(lineup.defensive_pairs) == 3
        assert lineup.goalies is not None
        assert lineup.fetched_at == now


class TestLineCombinationsDownloader:
    """Tests for LineCombinationsDownloader."""

    def test_data_type(self) -> None:
        """Test data_type property."""
        downloader = LineCombinationsDownloader()
        assert downloader.data_type == "line_combinations"

    def test_page_path(self) -> None:
        """Test page_path property."""
        downloader = LineCombinationsDownloader()
        assert downloader.page_path == "line-combinations"

    def test_source_name(self) -> None:
        """Test source_name property."""
        downloader = LineCombinationsDownloader()
        assert downloader.source_name == "dailyfaceoff_line_combinations"

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
        downloader = LineCombinationsDownloader()
        result = downloader._extract_next_data(soup)
        assert result is not None
        assert result["props"]["pageProps"]["test"] == "data"

    def test_extract_next_data_missing(self) -> None:
        """Test extracting __NEXT_DATA__ from HTML without it."""
        html = "<html><body>No data here</body></html>"
        soup = BeautifulSoup(html, "lxml")
        downloader = LineCombinationsDownloader()
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
        downloader = LineCombinationsDownloader()
        result = downloader._extract_next_data(soup)
        assert result is None

    def test_get_players_from_next_data(self) -> None:
        """Test navigating to players array."""
        next_data: dict[str, Any] = {
            "props": {"pageProps": {"combinations": {"players": [{"name": "Test"}]}}}
        }
        downloader = LineCombinationsDownloader()
        result = downloader._get_players_from_next_data(next_data)
        assert len(result) == 1
        assert result[0]["name"] == "Test"

    def test_get_players_from_next_data_missing_path(self) -> None:
        """Test navigating when path doesn't exist."""
        next_data: dict[str, Any] = {"props": {}}
        downloader = LineCombinationsDownloader()
        result = downloader._get_players_from_next_data(next_data)
        assert result == []

    def test_parse_player_valid(self) -> None:
        """Test parsing a valid player."""
        player_data = {
            "playerId": 1001,
            "name": "Brad Marchand",
            "jerseyNumber": 63,
            "positionIdentifier": "lw",
        }
        downloader = LineCombinationsDownloader()
        player = downloader._parse_player(player_data)
        assert player is not None
        assert player.player_id == 1001
        assert player.name == "Brad Marchand"
        assert player.jersey_number == 63
        assert player.position == "lw"

    def test_parse_player_missing_name(self) -> None:
        """Test parsing player without required name field."""
        player_data = {
            "playerId": 1001,
            "jerseyNumber": 63,
            "positionIdentifier": "lw",
        }
        downloader = LineCombinationsDownloader()
        player = downloader._parse_player(player_data)
        assert player is None

    def test_parse_player_missing_player_id(self) -> None:
        """Test parsing player without required playerId field."""
        player_data = {
            "name": "Test Player",
            "jerseyNumber": 63,
            "positionIdentifier": "lw",
        }
        downloader = LineCombinationsDownloader()
        player = downloader._parse_player(player_data)
        assert player is None

    def test_parse_player_no_jersey_number(self) -> None:
        """Test parsing player without jersey number (uses 0)."""
        player_data = {
            "playerId": 1001,
            "name": "Test Player",
            "positionIdentifier": "lw",
        }
        downloader = LineCombinationsDownloader()
        player = downloader._parse_player(player_data)
        assert player is not None
        assert player.jersey_number == 0

    def test_get_player_by_position(self) -> None:
        """Test finding a player by group and position."""
        players_data = [
            {
                "playerId": 1,
                "name": "LW",
                "jerseyNumber": 1,
                "positionIdentifier": "lw",
                "groupIdentifier": "f1",
            },
            {
                "playerId": 2,
                "name": "C",
                "jerseyNumber": 2,
                "positionIdentifier": "c",
                "groupIdentifier": "f1",
            },
        ]
        downloader = LineCombinationsDownloader()
        player = downloader._get_player_by_position(players_data, "f1", "c")
        assert player is not None
        assert player.name == "C"

    def test_get_player_by_position_not_found(self) -> None:
        """Test finding a player that doesn't exist."""
        players_data = [
            {
                "playerId": 1,
                "name": "LW",
                "jerseyNumber": 1,
                "positionIdentifier": "lw",
                "groupIdentifier": "f1",
            },
        ]
        downloader = LineCombinationsDownloader()
        player = downloader._get_player_by_position(players_data, "f1", "rw")
        assert player is None

    def test_parse_forward_line(self) -> None:
        """Test parsing a forward line."""
        players_data = [
            {
                "playerId": 1,
                "name": "LW",
                "jerseyNumber": 1,
                "positionIdentifier": "lw",
                "groupIdentifier": "f1",
            },
            {
                "playerId": 2,
                "name": "C",
                "jerseyNumber": 2,
                "positionIdentifier": "c",
                "groupIdentifier": "f1",
            },
            {
                "playerId": 3,
                "name": "RW",
                "jerseyNumber": 3,
                "positionIdentifier": "rw",
                "groupIdentifier": "f1",
            },
        ]
        downloader = LineCombinationsDownloader()
        line = downloader._parse_forward_line(players_data, "f1", 1)
        assert line.line_number == 1
        assert line.left_wing is not None
        assert line.left_wing.name == "LW"
        assert line.center is not None
        assert line.center.name == "C"
        assert line.right_wing is not None
        assert line.right_wing.name == "RW"

    def test_parse_forward_line_partial(self) -> None:
        """Test parsing an incomplete forward line."""
        players_data = [
            {
                "playerId": 1,
                "name": "C",
                "jerseyNumber": 2,
                "positionIdentifier": "c",
                "groupIdentifier": "f2",
            },
        ]
        downloader = LineCombinationsDownloader()
        line = downloader._parse_forward_line(players_data, "f2", 2)
        assert line.line_number == 2
        assert line.left_wing is None
        assert line.center is not None
        assert line.right_wing is None

    def test_parse_defensive_pair(self) -> None:
        """Test parsing a defensive pair."""
        players_data = [
            {
                "playerId": 1,
                "name": "LD",
                "jerseyNumber": 27,
                "positionIdentifier": "ld",
                "groupIdentifier": "d1",
            },
            {
                "playerId": 2,
                "name": "RD",
                "jerseyNumber": 73,
                "positionIdentifier": "rd",
                "groupIdentifier": "d1",
            },
        ]
        downloader = LineCombinationsDownloader()
        pair = downloader._parse_defensive_pair(players_data, "d1", 1)
        assert pair.pair_number == 1
        assert pair.left_defense is not None
        assert pair.left_defense.name == "LD"
        assert pair.right_defense is not None
        assert pair.right_defense.name == "RD"

    def test_parse_goalies(self) -> None:
        """Test parsing goalie depth."""
        players_data = [
            {
                "playerId": 1,
                "name": "Starter",
                "jerseyNumber": 1,
                "positionIdentifier": "g1",
                "groupIdentifier": "g",
            },
            {
                "playerId": 2,
                "name": "Backup",
                "jerseyNumber": 70,
                "positionIdentifier": "g2",
                "groupIdentifier": "g",
            },
        ]
        downloader = LineCombinationsDownloader()
        goalies = downloader._parse_goalies(players_data)
        assert goalies.starter is not None
        assert goalies.starter.name == "Starter"
        assert goalies.backup is not None
        assert goalies.backup.name == "Backup"

    def test_empty_result(self) -> None:
        """Test creating empty result."""
        downloader = LineCombinationsDownloader()
        result = downloader._empty_result(6, "BOS")

        assert "forward_lines" in result
        assert "defensive_pairs" in result
        assert "goalies" in result
        assert "fetched_at" in result
        assert len(result["forward_lines"]) == 4
        assert len(result["defensive_pairs"]) == 3

    def test_to_dict_converts_lineup(self) -> None:
        """Test converting lineup to dictionary."""
        lw = PlayerInfo(player_id=1, name="LW", jersey_number=63, position="lw")
        line = ForwardLine(line_number=1, left_wing=lw, center=None, right_wing=None)
        lines = (line,) + tuple(
            ForwardLine(line_number=i, left_wing=None, center=None, right_wing=None)
            for i in range(2, 5)
        )
        pairs = tuple(
            DefensivePair(pair_number=i, left_defense=None, right_defense=None)
            for i in range(1, 4)
        )
        goalies = GoalieDepth(starter=None, backup=None)
        now = datetime.now(UTC)

        lineup = TeamLineup(
            team_id=6,
            team_abbreviation="BOS",
            forward_lines=lines,
            defensive_pairs=pairs,
            goalies=goalies,
            fetched_at=now,
        )
        downloader = LineCombinationsDownloader()
        result = downloader._to_dict(lineup)

        assert result["forward_lines"][0]["line_number"] == 1
        assert result["forward_lines"][0]["left_wing"]["name"] == "LW"
        assert result["forward_lines"][0]["center"] is None
        assert result["fetched_at"] == now.isoformat()

    def test_player_to_dict(self) -> None:
        """Test converting player to dict."""
        player = PlayerInfo(
            player_id=1001,
            name="Brad Marchand",
            jersey_number=63,
            position="lw",
        )
        downloader = LineCombinationsDownloader()
        result = downloader._player_to_dict(player)

        assert result["player_id"] == 1001
        assert result["name"] == "Brad Marchand"
        assert result["jersey_number"] == 63
        assert result["position"] == "lw"


class TestLineCombinationsDownloaderIntegration:
    """Integration tests using fixture file."""

    @pytest.fixture
    def fixture_html(self) -> str:
        """Load fixture HTML."""
        fixture_path = FIXTURES_DIR / "line_combinations_full.html"
        return fixture_path.read_text()

    @pytest.fixture
    def fixture_soup(self, fixture_html: str) -> BeautifulSoup:
        """Parse fixture HTML into BeautifulSoup."""
        return BeautifulSoup(fixture_html, "lxml")

    @pytest.mark.asyncio
    async def test_parse_page_full(self, fixture_soup: BeautifulSoup) -> None:
        """Test parsing full fixture page."""
        downloader = LineCombinationsDownloader()
        result = await downloader._parse_page(fixture_soup, 6)

        # Check forward lines
        assert "forward_lines" in result
        assert len(result["forward_lines"]) == 4

        # First line
        line1 = result["forward_lines"][0]
        assert line1["line_number"] == 1
        assert line1["left_wing"]["name"] == "Brad Marchand"
        assert line1["center"]["name"] == "Elias Lindholm"
        assert line1["right_wing"]["name"] == "David Pastrnak"

        # Check defensive pairs
        assert "defensive_pairs" in result
        assert len(result["defensive_pairs"]) == 3

        pair1 = result["defensive_pairs"][0]
        assert pair1["pair_number"] == 1
        assert pair1["left_defense"]["name"] == "Hampus Lindholm"
        assert pair1["right_defense"]["name"] == "Charlie McAvoy"

        # Check goalies
        assert "goalies" in result
        assert result["goalies"]["starter"]["name"] == "Jeremy Swayman"
        assert result["goalies"]["backup"]["name"] == "Joonas Korpisalo"

    @pytest.mark.asyncio
    async def test_parse_page_filters_non_lines(
        self, fixture_soup: BeautifulSoup
    ) -> None:
        """Test that power play players are filtered out from lines."""
        downloader = LineCombinationsDownloader()
        result = await downloader._parse_page(fixture_soup, 6)

        # PP players should not appear in line combinations
        # (they have groupIdentifier pp1/pp2, not f1/f2/f3/f4)
        for line in result["forward_lines"]:
            for pos in ["left_wing", "center", "right_wing"]:
                if line[pos]:
                    # PP players have position sk1, sk2, etc.
                    assert line[pos]["position"] in ["lw", "c", "rw"]

    @pytest.mark.asyncio
    async def test_parse_page_empty_html(self) -> None:
        """Test parsing page with no __NEXT_DATA__."""
        html = "<html><body>Empty</body></html>"
        soup = BeautifulSoup(html, "lxml")
        downloader = LineCombinationsDownloader()
        result = await downloader._parse_page(soup, 6)

        # Should return empty lines
        assert all(
            line["left_wing"] is None
            and line["center"] is None
            and line["right_wing"] is None
            for line in result["forward_lines"]
        )


class TestLineCombinationsDownloaderDownload:
    """Tests for download_team method."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock HTTP response."""
        fixture_path = FIXTURES_DIR / "line_combinations_full.html"
        content = fixture_path.read_bytes()

        response = MagicMock()
        response.is_success = True
        response.status = 200
        response.content = content
        return response

    @pytest.mark.asyncio
    async def test_download_team_success(self, mock_response: MagicMock) -> None:
        """Test successful team download."""
        downloader = LineCombinationsDownloader()
        object.__setattr__(downloader, "_get", AsyncMock(return_value=mock_response))

        result = await downloader.download_team(6)

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "dailyfaceoff_line_combinations"
        assert result.data["team_id"] == 6
        assert result.data["team_abbreviation"] == "BOS"
        assert "forward_lines" in result.data
        assert "defensive_pairs" in result.data
        assert "goalies" in result.data

    @pytest.mark.asyncio
    async def test_download_team_http_error(self) -> None:
        """Test handling HTTP error."""
        response = MagicMock()
        response.is_success = False
        response.status = 404

        downloader = LineCombinationsDownloader()
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

        downloader = LineCombinationsDownloader()
        object.__setattr__(downloader, "_get", AsyncMock(return_value=response))

        from nhl_api.downloaders.base.protocol import DownloadError

        with pytest.raises(DownloadError, match="not valid HTML"):
            await downloader.download_team(6)


class TestLineCombinationsDownloaderBulk:
    """Tests for download_all_teams method."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock HTTP response."""
        fixture_path = FIXTURES_DIR / "line_combinations_full.html"
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
        downloader = LineCombinationsDownloader(team_ids=[6, 10, 1])
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

        downloader = LineCombinationsDownloader(team_ids=[6, 2, 1])  # BOS, NYI, NJD
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
