"""Unit tests for LineCombinationsDownloader."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.dailyfaceoff import (
    DailyFaceoffConfig,
    DefensivePair,
    ForwardLine,
    GoalieDepth,
    LineCombinationsDownloader,
    PlayerInfo,
    TeamLineup,
)

# Sample HTML that simulates DailyFaceoff structure
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Toronto Maple Leafs Line Combinations</title></head>
<body>
<div class="lineup-container">
    <!-- Forward Lines -->
    <div class="line" data-group="f1">
        <div class="player" data-position="lw">
            <a href="/players/news/matthew-knies/12345">#23 Matthew Knies</a>
        </div>
        <div class="player" data-position="c">
            <a href="/players/news/auston-matthews/12346">#34 Auston Matthews</a>
        </div>
        <div class="player" data-position="rw">
            <a href="/players/news/mitch-marner/12347">#16 Mitch Marner</a>
        </div>
    </div>
    <div class="line" data-group="f2">
        <div class="player" data-position="lw">
            <a href="/players/news/bobby-mcmann/12348">#74 Bobby McMann</a>
        </div>
        <div class="player" data-position="c">
            <a href="/players/news/john-tavares/12349">#91 John Tavares</a>
        </div>
        <div class="player" data-position="rw">
            <a href="/players/news/william-nylander/12350">#88 William Nylander</a>
        </div>
    </div>
    <div class="line" data-group="f3">
        <div class="player" data-position="lw">
            <a href="/players/news/max-domi/12351">#11 Max Domi</a>
        </div>
        <div class="player" data-position="c">
            <a href="/players/news/pontus-holmberg/12352">#29 Pontus Holmberg</a>
        </div>
        <div class="player" data-position="rw">
            <a href="/players/news/nick-robertson/12353">#89 Nick Robertson</a>
        </div>
    </div>
    <div class="line" data-group="f4">
        <div class="player" data-position="lw">
            <a href="/players/news/steven-lorentz/12354">#22 Steven Lorentz</a>
        </div>
        <div class="player" data-position="c">
            <a href="/players/news/david-kampf/12355">#64 David Kampf</a>
        </div>
        <div class="player" data-position="rw">
            <a href="/players/news/ryan-reaves/12356">#75 Ryan Reaves</a>
        </div>
    </div>

    <!-- Defensive Pairs -->
    <div class="pair" data-group="d1">
        <div class="player" data-position="ld">
            <a href="/players/news/morgan-rielly/12357">#44 Morgan Rielly</a>
        </div>
        <div class="player" data-position="rd">
            <a href="/players/news/chris-tanev/12358">#8 Chris Tanev</a>
        </div>
    </div>
    <div class="pair" data-group="d2">
        <div class="player" data-position="ld">
            <a href="/players/news/oliver-ekman-larsson/12359">#77 Oliver Ekman-Larsson</a>
        </div>
        <div class="player" data-position="rd">
            <a href="/players/news/jake-mccabe/12360">#22 Jake McCabe</a>
        </div>
    </div>
    <div class="pair" data-group="d3">
        <div class="player" data-position="ld">
            <a href="/players/news/simon-benoit/12361">#64 Simon Benoit</a>
        </div>
        <div class="player" data-position="rd">
            <a href="/players/news/conor-timmins/12362">#25 Conor Timmins</a>
        </div>
    </div>

    <!-- Goalies -->
    <div class="goalie" data-group="g1">
        <span>Starting Goalie</span>
        <div class="player" data-position="g">
            <a href="/players/news/joseph-woll/12363">#60 Joseph Woll</a>
        </div>
    </div>
    <div class="goalie" data-group="g2">
        <span>Backup Goalie</span>
        <div class="player" data-position="g">
            <a href="/players/news/dennis-hildeby/12364">#35 Dennis Hildeby</a>
        </div>
    </div>
</div>
</body>
</html>
"""

# Minimal HTML with missing data
MINIMAL_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="lineup-container">
    <div class="line" data-group="f1">
        <div class="player" data-position="c">
            <a href="/players/news/auston-matthews/12346">Auston Matthews</a>
        </div>
    </div>
</div>
</body>
</html>
"""

# HTML with injury indicators
INJURY_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="lineup-container">
    <div class="line" data-group="f1">
        <div class="player injured" data-position="lw" data-injury="ir">
            <a href="/players/news/injured-player/12345">#10 Injured Player</a>
        </div>
    </div>
</div>
</body>
</html>
"""


class TestPlayerInfo:
    """Tests for PlayerInfo dataclass."""

    def test_create_player_info(self) -> None:
        """Test creating PlayerInfo."""
        player = PlayerInfo(
            name="Auston Matthews",
            jersey_number=34,
            injury_status=None,
            player_id="12346",
        )
        assert player.name == "Auston Matthews"
        assert player.jersey_number == 34
        assert player.injury_status is None
        assert player.player_id == "12346"

    def test_player_info_defaults(self) -> None:
        """Test PlayerInfo default values."""
        player = PlayerInfo(name="Test Player")
        assert player.jersey_number is None
        assert player.injury_status is None
        assert player.player_id is None

    def test_player_info_frozen(self) -> None:
        """Test PlayerInfo is immutable."""
        player = PlayerInfo(name="Test")
        with pytest.raises(AttributeError):
            player.name = "Changed"  # type: ignore


class TestForwardLine:
    """Tests for ForwardLine dataclass."""

    def test_create_forward_line(self) -> None:
        """Test creating ForwardLine."""
        line = ForwardLine(
            line_number=1,
            left_wing=PlayerInfo(name="LW"),
            center=PlayerInfo(name="C"),
            right_wing=PlayerInfo(name="RW"),
        )
        assert line.line_number == 1
        assert line.left_wing.name == "LW"
        assert line.center.name == "C"
        assert line.right_wing.name == "RW"


class TestDefensivePair:
    """Tests for DefensivePair dataclass."""

    def test_create_defensive_pair(self) -> None:
        """Test creating DefensivePair."""
        pair = DefensivePair(
            pair_number=1,
            left_defense=PlayerInfo(name="LD"),
            right_defense=PlayerInfo(name="RD"),
        )
        assert pair.pair_number == 1
        assert pair.left_defense.name == "LD"
        assert pair.right_defense.name == "RD"


class TestGoalieDepth:
    """Tests for GoalieDepth dataclass."""

    def test_create_goalie_depth(self) -> None:
        """Test creating GoalieDepth."""
        goalies = GoalieDepth(
            starter=PlayerInfo(name="Starter"),
            backup=PlayerInfo(name="Backup"),
        )
        assert goalies.starter is not None
        assert goalies.starter.name == "Starter"
        assert goalies.backup is not None
        assert goalies.backup.name == "Backup"

    def test_goalie_depth_none(self) -> None:
        """Test GoalieDepth with None values."""
        goalies = GoalieDepth(starter=None, backup=None)
        assert goalies.starter is None
        assert goalies.backup is None


class TestTeamLineup:
    """Tests for TeamLineup dataclass."""

    def test_create_team_lineup(self) -> None:
        """Test creating TeamLineup."""
        lineup = TeamLineup(
            team_id=10,
            team_abbreviation="TOR",
        )
        assert lineup.team_id == 10
        assert lineup.team_abbreviation == "TOR"
        assert lineup.forward_lines == []
        assert lineup.defensive_pairs == []
        assert lineup.goalies is None
        assert isinstance(lineup.fetched_at, datetime)


class TestLineCombinationsDownloader:
    """Tests for LineCombinationsDownloader."""

    def test_data_type(self) -> None:
        """Test data_type property."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        assert downloader.data_type == "line_combinations"

    def test_page_path(self) -> None:
        """Test page_path property."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        assert downloader.page_path == "line-combinations"

    def test_source_name(self) -> None:
        """Test source_name property."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        assert downloader.source_name == "dailyfaceoff_line_combinations"


class TestParsePage:
    """Tests for _parse_page method."""

    @pytest.mark.asyncio
    async def test_parse_full_lineup(self) -> None:
        """Test parsing a complete lineup."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")

        result = await downloader._parse_page(soup, 10)

        assert result["team_id"] == 10
        assert result["team_abbreviation"] == "TOR"
        assert "forward_lines" in result
        assert "defensive_pairs" in result
        assert "goalies" in result
        assert "fetched_at" in result

    @pytest.mark.asyncio
    async def test_parse_minimal_html(self) -> None:
        """Test parsing minimal HTML."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        soup = BeautifulSoup(MINIMAL_HTML, "lxml")

        result = await downloader._parse_page(soup, 10)

        assert result["team_id"] == 10
        # Should have at least partial data
        assert "forward_lines" in result


class TestParseForwardLines:
    """Tests for _parse_forward_lines method."""

    def test_parse_forward_lines(self) -> None:
        """Test parsing forward lines from HTML."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")

        lines = downloader._parse_forward_lines(soup)

        assert len(lines) == 4
        assert lines[0].line_number == 1
        assert lines[1].line_number == 2
        assert lines[2].line_number == 3
        assert lines[3].line_number == 4

    def test_parse_empty_forward_lines(self) -> None:
        """Test parsing when no forward lines exist."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        soup = BeautifulSoup("<html><body></body></html>", "lxml")

        lines = downloader._parse_forward_lines(soup)

        assert lines == []


class TestParseDefensivePairs:
    """Tests for _parse_defensive_pairs method."""

    def test_parse_defensive_pairs(self) -> None:
        """Test parsing defensive pairs from HTML."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")

        pairs = downloader._parse_defensive_pairs(soup)

        assert len(pairs) == 3
        assert pairs[0].pair_number == 1
        assert pairs[1].pair_number == 2
        assert pairs[2].pair_number == 3


class TestParseGoalies:
    """Tests for _parse_goalies method."""

    def test_parse_goalies(self) -> None:
        """Test parsing goalies from HTML."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")

        goalies = downloader._parse_goalies(soup)

        assert goalies is not None
        # Note: actual parsing depends on HTML structure


class TestExtractPlayerInfo:
    """Tests for _extract_player_info method."""

    def test_extract_player_with_link(self) -> None:
        """Test extracting player info from element with link."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)

        html = """
        <div class="player">
            <a href="/players/news/auston-matthews/12346">#34 Auston Matthews</a>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("div", class_="player")
        assert element is not None

        player = downloader._extract_player_info(element)

        assert player.name == "#34 Auston Matthews"
        assert player.jersey_number == 34
        assert player.player_id == "12346"

    def test_extract_player_with_injury(self) -> None:
        """Test extracting player info with injury status."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)

        html = """
        <div class="player injured" data-injury="ir">
            <a href="/players/news/injured-player/12345">#10 Injured Player</a>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("div", class_="player")
        assert element is not None

        player = downloader._extract_player_info(element)

        assert "Injured Player" in player.name
        assert player.injury_status == "ir"


class TestToDict:
    """Tests for _to_dict method."""

    def test_to_dict(self) -> None:
        """Test converting TeamLineup to dictionary."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)

        lineup = TeamLineup(
            team_id=10,
            team_abbreviation="TOR",
            forward_lines=[
                ForwardLine(
                    line_number=1,
                    left_wing=PlayerInfo(name="LW"),
                    center=PlayerInfo(name="C"),
                    right_wing=PlayerInfo(name="RW"),
                )
            ],
            defensive_pairs=[
                DefensivePair(
                    pair_number=1,
                    left_defense=PlayerInfo(name="LD"),
                    right_defense=PlayerInfo(name="RD"),
                )
            ],
            goalies=GoalieDepth(
                starter=PlayerInfo(name="Starter"),
                backup=PlayerInfo(name="Backup"),
            ),
            fetched_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        result = downloader._to_dict(lineup)

        assert result["team_id"] == 10
        assert result["team_abbreviation"] == "TOR"
        assert len(result["forward_lines"]) == 1
        assert result["forward_lines"][0]["line_number"] == 1
        assert result["forward_lines"][0]["left_wing"]["name"] == "LW"
        assert len(result["defensive_pairs"]) == 1
        assert result["goalies"]["starter"]["name"] == "Starter"
        assert result["fetched_at"] == "2025-01-01T12:00:00+00:00"


class TestPlayerToDict:
    """Tests for _player_to_dict method."""

    def test_player_to_dict(self) -> None:
        """Test converting PlayerInfo to dictionary."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)

        player = PlayerInfo(
            name="Auston Matthews",
            jersey_number=34,
            injury_status=None,
            player_id="12346",
        )

        result = downloader._player_to_dict(player)

        assert result is not None
        assert result["name"] == "Auston Matthews"
        assert result["jersey_number"] == 34
        assert result["injury_status"] is None
        assert result["player_id"] == "12346"

    def test_player_to_dict_none(self) -> None:
        """Test converting None player."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)

        result = downloader._player_to_dict(None)
        assert result is None

    def test_player_to_dict_empty_name(self) -> None:
        """Test converting player with empty name."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)

        player = PlayerInfo(name="")
        result = downloader._player_to_dict(player)
        assert result is None


class TestDownloadTeam:
    """Tests for download_team integration."""

    @pytest.mark.asyncio
    async def test_download_team_success(self) -> None:
        """Test successful team download."""
        config = DailyFaceoffConfig()
        downloader = LineCombinationsDownloader(config)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = SAMPLE_HTML.encode("utf-8")

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                result = await downloader.download_team(10)

        assert result.status == DownloadStatus.COMPLETED
        assert result.data["team_id"] == 10
        assert result.data["team_abbreviation"] == "TOR"
        assert "forward_lines" in result.data
        assert "defensive_pairs" in result.data
        assert "goalies" in result.data
