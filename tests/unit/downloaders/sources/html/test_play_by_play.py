"""Unit tests for PlayByPlayDownloader.

Tests cover:
- HTML parsing of play-by-play reports
- Event type parsing (FAC, GOAL, SHOT, HIT, PENL, etc.)
- Player on ice extraction
- Description parsing for various event types
- Integration with BaseHTMLDownloader
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.html.base_html_downloader import (
    HTMLDownloaderConfig,
)
from nhl_api.downloaders.sources.html.play_by_play import (
    EVENT_TYPES,
    EventPlayer,
    ParsedPlayByPlay,
    PlayByPlayDownloader,
    PlayByPlayEvent,
    PlayerOnIce,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def config() -> HTMLDownloaderConfig:
    """Create test configuration."""
    return HTMLDownloaderConfig(
        base_url="https://www.nhl.com/scores/htmlreports",
        requests_per_second=10.0,
        max_retries=2,
        http_timeout=5.0,
        store_raw_html=True,
    )


@pytest.fixture
def downloader(config: HTMLDownloaderConfig) -> PlayByPlayDownloader:
    """Create test downloader instance."""
    return PlayByPlayDownloader(config)


@pytest.fixture
def sample_html() -> bytes:
    """Load sample Play-by-Play HTML fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "html"
        / "PL020500.HTM"
    )
    if fixture_path.exists():
        return fixture_path.read_bytes()
    # Fallback minimal HTML for testing
    return b"""<!DOCTYPE html>
<html>
<head><title>Play By Play</title></head>
<body>
<table id="Visitor">
    <tr><td><img src="logocnyi.gif" alt="NEW YORK ISLANDERS"></td></tr>
    <tr><td style="font-size: 40px;font-weight:bold">0</td></tr>
</table>
<table id="Home">
    <tr><td><img src="logoccar.gif" alt="CAROLINA HURRICANES"></td></tr>
    <tr><td style="font-size: 40px;font-weight:bold">4</td></tr>
</table>
<table>
    <tr>
        <td class="heading">#</td>
        <td class="heading">Per</td>
        <td class="heading">Str</td>
        <td class="heading">Time</td>
        <td class="heading">Event</td>
        <td class="heading">Description</td>
        <td class="heading">NYI On Ice</td>
        <td class="heading">CAR On Ice</td>
    </tr>
    <tr id="PL-1" class="evenColor">
        <td align="center">1</td>
        <td align="center">1</td>
        <td align="center"></td>
        <td align="center">0:00<br>20:00</td>
        <td align="center">PSTR</td>
        <td>Period Start- Local time: 7:38 EST</td>
        <td>
            <table><tr>
                <td><table><tr><td><font title="Center - BO HORVAT">14</font></td></tr><tr><td>C</td></tr></table></td>
                <td><table><tr><td><font title="Goalie - ILYA SOROKIN">30</font></td></tr><tr><td>G</td></tr></table></td>
            </tr></table>
        </td>
        <td>
            <table><tr>
                <td><table><tr><td><font title="Center - JESPERI KOTKANIEMI">82</font></td></tr><tr><td>C</td></tr></table></td>
                <td><table><tr><td><font title="Goalie - PYOTR KOCHETKOV">52</font></td></tr><tr><td>G</td></tr></table></td>
            </tr></table>
        </td>
    </tr>
    <tr id="PL-5" class="evenColor">
        <td align="center">5</td>
        <td align="center">1</td>
        <td align="center">EV</td>
        <td align="center">0:00<br>20:00</td>
        <td align="center">FAC</td>
        <td>CAR won Neu. Zone - NYI #14 HORVAT vs CAR #82 KOTKANIEMI</td>
        <td></td>
        <td></td>
    </tr>
    <tr id="PL-10" class="oddColor">
        <td align="center">10</td>
        <td align="center">1</td>
        <td align="center">EV</td>
        <td align="center">1:30<br>18:30</td>
        <td align="center">SHOT</td>
        <td>CAR ONGOAL - #48 MARTINOOK, Backhand , Off. Zone, 23 ft. </td>
        <td></td>
        <td></td>
    </tr>
    <tr id="PL-32" class="oddColor">
        <td align="center" class="penalty">32</td>
        <td class="penalty" align="center">1</td>
        <td class="penalty" align="center">EV</td>
        <td class="penalty" align="center">5:12<br>14:48</td>
        <td class="penalty" align="center">PENL</td>
        <td class="penalty">NYI #28 ROMANOV High-sticking(2 min), Def. Zone Drawn By: CAR #50 ROBINSON</td>
        <td></td>
        <td></td>
    </tr>
    <tr id="PL-36" class="oddColor">
        <td align="center" class="goal">36</td>
        <td class="goal" align="center">1</td>
        <td class="goal" align="center">PP</td>
        <td class="goal" align="center">5:47<br>14:13</td>
        <td class="goal" align="center">GOAL</td>
        <td class="goal">CAR #37 SVECHNIKOV(12), Wrist , Off. Zone, 6 ft.<br>Assists: #20 AHO(24); #4 GOSTISBEHERE(20) </td>
        <td></td>
        <td></td>
    </tr>
    <tr id="PL-40" class="evenColor">
        <td align="center">40</td>
        <td align="center">1</td>
        <td align="center">EV</td>
        <td align="center">7:00<br>13:00</td>
        <td align="center">HIT</td>
        <td>CAR #37 SVECHNIKOV HIT NYI #8 DOBSON, Neu. Zone</td>
        <td></td>
        <td></td>
    </tr>
    <tr id="PL-45" class="oddColor">
        <td align="center">45</td>
        <td align="center">1</td>
        <td align="center">EV</td>
        <td align="center">8:00<br>12:00</td>
        <td align="center">GIVE</td>
        <td>CAR GIVEAWAY - #4 GOSTISBEHERE, Def. Zone</td>
        <td></td>
        <td></td>
    </tr>
    <tr id="PL-50" class="evenColor">
        <td align="center">50</td>
        <td align="center">1</td>
        <td align="center">EV</td>
        <td align="center">9:00<br>11:00</td>
        <td align="center">TAKE</td>
        <td>CAR TAKEAWAY - #20 AHO, Off. Zone</td>
        <td></td>
        <td></td>
    </tr>
    <tr id="PL-55" class="oddColor">
        <td align="center">55</td>
        <td align="center">1</td>
        <td align="center">EV</td>
        <td align="center">10:00<br>10:00</td>
        <td align="center">BLOCK</td>
        <td>NYI #7 TSYPLAKOV BLOCKED BY CAR #82 KOTKANIEMI, Wrist, Def. Zone </td>
        <td></td>
        <td></td>
    </tr>
    <tr id="PL-60" class="evenColor">
        <td align="center">60</td>
        <td align="center">1</td>
        <td align="center">EV</td>
        <td align="center">11:00<br>9:00</td>
        <td align="center">MISS</td>
        <td>NYI #14 HORVAT, Wrist, Wide of Net, Off. Zone, 43 ft.</td>
        <td></td>
        <td></td>
    </tr>
</table>
</body>
</html>"""


@pytest.fixture
def sample_soup(sample_html: bytes) -> BeautifulSoup:
    """Parse sample HTML into BeautifulSoup."""
    return BeautifulSoup(sample_html.decode("utf-8"), "lxml")


# =============================================================================
# Configuration Tests
# =============================================================================


class TestPlayByPlayDownloaderConfig:
    """Tests for PlayByPlayDownloader configuration."""

    def test_report_type(self, downloader: PlayByPlayDownloader) -> None:
        """Test report_type is 'PL'."""
        assert downloader.report_type == "PL"

    def test_source_name(self, downloader: PlayByPlayDownloader) -> None:
        """Test source_name is 'html_pl'."""
        assert downloader.source_name == "html_pl"


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for data classes."""

    def test_player_on_ice(self) -> None:
        """Test PlayerOnIce creation."""
        player = PlayerOnIce(number=14, position="C", name="BO HORVAT")
        assert player.number == 14
        assert player.position == "C"
        assert player.name == "BO HORVAT"

    def test_event_player(self) -> None:
        """Test EventPlayer creation."""
        player = EventPlayer(
            number=37,
            name="SVECHNIKOV",
            team="CAR",
            role="scorer",
            stat=12,
        )
        assert player.number == 37
        assert player.name == "SVECHNIKOV"
        assert player.team == "CAR"
        assert player.role == "scorer"
        assert player.stat == 12

    def test_play_by_play_event(self) -> None:
        """Test PlayByPlayEvent creation."""
        event = PlayByPlayEvent(
            event_number=36,
            period=1,
            strength="PP",
            time_elapsed="5:47",
            time_remaining="14:13",
            event_type="GOAL",
            description="CAR #37 SVECHNIKOV(12), Wrist, Off. Zone, 6 ft.",
            team="CAR",
            zone="Off",
            shot_type="Wrist",
            distance=6,
        )
        assert event.event_number == 36
        assert event.period == 1
        assert event.strength == "PP"
        assert event.event_type == "GOAL"
        assert event.team == "CAR"
        assert event.zone == "Off"
        assert event.shot_type == "Wrist"
        assert event.distance == 6

    def test_parsed_play_by_play(self) -> None:
        """Test ParsedPlayByPlay creation."""
        result = ParsedPlayByPlay(
            game_id=2024020500,
            season_id=20242025,
            away_team="NYI",
            home_team="CAR",
            events=[],
        )
        assert result.game_id == 2024020500
        assert result.season_id == 20242025
        assert result.away_team == "NYI"
        assert result.home_team == "CAR"


# =============================================================================
# Event Types Tests
# =============================================================================


class TestEventTypes:
    """Tests for event type constants."""

    def test_event_types_defined(self) -> None:
        """Test EVENT_TYPES contains expected values."""
        assert "FAC" in EVENT_TYPES
        assert "GOAL" in EVENT_TYPES
        assert "SHOT" in EVENT_TYPES
        assert "MISS" in EVENT_TYPES
        assert "BLOCK" in EVENT_TYPES
        assert "HIT" in EVENT_TYPES
        assert "GIVE" in EVENT_TYPES
        assert "TAKE" in EVENT_TYPES
        assert "PENL" in EVENT_TYPES
        assert "STOP" in EVENT_TYPES
        assert "PSTR" in EVENT_TYPES
        assert "PEND" in EVENT_TYPES


# =============================================================================
# Team Parsing Tests
# =============================================================================


class TestTeamParsing:
    """Tests for team information parsing."""

    def test_parse_teams(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of team information."""
        away, home = downloader._parse_teams(sample_soup)

        assert away == "NYI"
        assert home == "CAR"

    def test_team_name_to_abbrev(self, downloader: PlayByPlayDownloader) -> None:
        """Test team name to abbreviation mapping."""
        assert downloader._team_name_to_abbrev("NEW YORK ISLANDERS") == "NYI"
        assert downloader._team_name_to_abbrev("CAROLINA HURRICANES") == "CAR"
        assert downloader._team_name_to_abbrev("BOSTON BRUINS") == "BOS"
        assert downloader._team_name_to_abbrev("TORONTO MAPLE LEAFS") == "TOR"
        assert downloader._team_name_to_abbrev("UNKNOWN TEAM") == "UNK"


# =============================================================================
# Event Parsing Tests
# =============================================================================


class TestEventParsing:
    """Tests for event parsing."""

    def test_parse_events(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of all events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        # Should have multiple events
        assert len(events) >= 1

        # Check first event
        first_event = events[0]
        assert first_event.event_number >= 1
        assert first_event.period == 1

    def test_parse_faceoff_event(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of faceoff events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        faceoffs = [e for e in events if e.event_type == "FAC"]
        if faceoffs:
            fac = faceoffs[0]
            assert fac.event_type == "FAC"
            assert fac.zone == "Neu"
            assert len(fac.players) == 2
            # Winner and loser
            roles = [p.role for p in fac.players]
            assert "winner" in roles
            assert "loser" in roles

    def test_parse_goal_event(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of goal events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        goals = [e for e in events if e.event_type == "GOAL"]
        if goals:
            goal = goals[0]
            assert goal.event_type == "GOAL"
            assert goal.team == "CAR"
            assert goal.strength == "PP"
            assert goal.zone == "Off"
            assert goal.shot_type == "Wrist"
            assert goal.distance == 6

            # Check players (scorer and assists)
            assert len(goal.players) >= 1
            scorer = next((p for p in goal.players if p.role == "scorer"), None)
            assert scorer is not None
            assert scorer.number == 37
            assert "SVECHNIKOV" in scorer.name
            assert scorer.stat == 12

    def test_parse_shot_event(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of shot events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        shots = [e for e in events if e.event_type == "SHOT"]
        if shots:
            shot = shots[0]
            assert shot.event_type == "SHOT"
            assert shot.team == "CAR"
            assert shot.zone == "Off"
            assert len(shot.players) >= 1
            shooter = shot.players[0]
            assert shooter.role == "shooter"

    def test_parse_penalty_event(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of penalty events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        penalties = [e for e in events if e.event_type == "PENL"]
        if penalties:
            penalty = penalties[0]
            assert penalty.event_type == "PENL"
            assert penalty.team == "NYI"
            assert penalty.zone == "Def"

            # Check penalized player
            penalized = next(
                (p for p in penalty.players if p.role == "penalized"), None
            )
            assert penalized is not None
            assert penalized.number == 28
            assert "ROMANOV" in penalized.name

            # Check drawn by player
            drew = next((p for p in penalty.players if p.role == "drew_penalty"), None)
            assert drew is not None
            assert drew.number == 50
            assert "ROBINSON" in drew.name

    def test_parse_hit_event(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of hit events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        hits = [e for e in events if e.event_type == "HIT"]
        if hits:
            hit = hits[0]
            assert hit.event_type == "HIT"
            assert hit.team in ("CAR", "NYI")  # Either team can hit
            assert hit.zone in ("Off", "Def", "Neu")
            assert len(hit.players) == 2

            # Check hitter and hittee
            hitter = next((p for p in hit.players if p.role == "hitter"), None)
            hittee = next((p for p in hit.players if p.role == "hittee"), None)
            assert hitter is not None
            assert hittee is not None
            assert hitter.number > 0
            assert hittee.number > 0

    def test_parse_giveaway_event(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of giveaway events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        gives = [e for e in events if e.event_type == "GIVE"]
        if gives:
            give = gives[0]
            assert give.event_type == "GIVE"
            assert give.team == "CAR"
            assert give.zone == "Def"
            assert len(give.players) >= 1
            giver = give.players[0]
            assert giver.role == "giver"
            assert giver.number == 4

    def test_parse_takeaway_event(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of takeaway events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        takes = [e for e in events if e.event_type == "TAKE"]
        if takes:
            take = takes[0]
            assert take.event_type == "TAKE"
            assert take.team in ("CAR", "NYI")  # Either team can have takeaway
            assert take.zone in ("Off", "Def", "Neu")
            assert len(take.players) >= 1
            taker = take.players[0]
            assert taker.role == "taker"
            assert taker.number > 0

    def test_parse_block_event(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of blocked shot events."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        blocks = [e for e in events if e.event_type == "BLOCK"]
        if blocks:
            block = blocks[0]
            assert block.event_type == "BLOCK"
            assert block.team == "NYI"
            assert block.zone == "Def"
            assert len(block.players) >= 1

            shooter = next((p for p in block.players if p.role == "shooter"), None)
            blocker = next((p for p in block.players if p.role == "blocker"), None)
            if shooter:
                assert shooter.number == 7
            if blocker:
                assert blocker.number == 82


# =============================================================================
# Players On Ice Tests
# =============================================================================


class TestPlayersOnIce:
    """Tests for players on ice parsing."""

    def test_parse_players_on_ice(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test parsing of players on ice."""
        events = downloader._parse_events(sample_soup, "NYI", "CAR")

        # Find an event with players on ice
        event_with_players = None
        for event in events:
            if event.away_on_ice or event.home_on_ice:
                event_with_players = event
                break

        if event_with_players:
            # Check away team players
            if event_with_players.away_on_ice:
                player = event_with_players.away_on_ice[0]
                assert player.number > 0
                assert player.position in ("C", "L", "R", "D", "G")
                assert player.name  # Should have a name

            # Check home team players
            if event_with_players.home_on_ice:
                player = event_with_players.home_on_ice[0]
                assert player.number > 0
                assert player.position in ("C", "L", "R", "D", "G")


# =============================================================================
# Description Parsing Tests
# =============================================================================


class TestDescriptionParsing:
    """Tests for event description parsing methods."""

    def test_parse_faceoff(self, downloader: PlayByPlayDownloader) -> None:
        """Test faceoff description parsing."""
        desc = "CAR won Neu. Zone - NYI #14 HORVAT vs CAR #82 KOTKANIEMI"
        team, players = downloader._parse_faceoff(desc)

        assert team == "CAR"
        assert len(players) == 2

        winner = next((p for p in players if p.role == "winner"), None)
        loser = next((p for p in players if p.role == "loser"), None)

        assert winner is not None
        assert winner.number == 82
        assert "KOTKANIEMI" in winner.name
        assert winner.team == "CAR"

        assert loser is not None
        assert loser.number == 14
        assert "HORVAT" in loser.name
        assert loser.team == "NYI"

    def test_parse_goal(self, downloader: PlayByPlayDownloader) -> None:
        """Test goal description parsing."""
        desc = "CAR #37 SVECHNIKOV(12), Wrist , Off. Zone, 6 ft.\nAssists: #20 AHO(24); #4 GOSTISBEHERE(20)"
        team, players = downloader._parse_goal(desc)

        assert team == "CAR"
        assert len(players) >= 1

        scorer = next((p for p in players if p.role == "scorer"), None)
        assert scorer is not None
        assert scorer.number == 37
        assert "SVECHNIKOV" in scorer.name
        assert scorer.stat == 12

        assist1 = next((p for p in players if p.role == "assist1"), None)
        if assist1:
            assert assist1.number == 20
            assert "AHO" in assist1.name

    def test_parse_shot(self, downloader: PlayByPlayDownloader) -> None:
        """Test shot description parsing."""
        desc = "CAR ONGOAL - #48 MARTINOOK, Backhand , Off. Zone, 23 ft."
        team, players = downloader._parse_shot(desc)

        assert team == "CAR"
        assert len(players) >= 1

        shooter = players[0]
        assert shooter.number == 48
        assert "MARTINOOK" in shooter.name
        assert shooter.role == "shooter"

    def test_parse_penalty(self, downloader: PlayByPlayDownloader) -> None:
        """Test penalty description parsing."""
        desc = (
            "NYI #28 ROMANOV High-sticking(2 min), Def. Zone Drawn By: CAR #50 ROBINSON"
        )
        team, players = downloader._parse_penalty(desc)

        assert team == "NYI"
        assert len(players) == 2

        penalized = next((p for p in players if p.role == "penalized"), None)
        assert penalized is not None
        assert penalized.number == 28
        assert "ROMANOV" in penalized.name

        drew = next((p for p in players if p.role == "drew_penalty"), None)
        assert drew is not None
        assert drew.number == 50
        assert "ROBINSON" in drew.name
        assert drew.team == "CAR"

    def test_parse_hit(self, downloader: PlayByPlayDownloader) -> None:
        """Test hit description parsing."""
        desc = "CAR #37 SVECHNIKOV HIT NYI #8 DOBSON, Neu. Zone"
        team, players = downloader._parse_hit(desc)

        assert team == "CAR"
        assert len(players) == 2

        hitter = next((p for p in players if p.role == "hitter"), None)
        assert hitter is not None
        assert hitter.number == 37

        hittee = next((p for p in players if p.role == "hittee"), None)
        assert hittee is not None
        assert hittee.number == 8

    def test_parse_giveaway(self, downloader: PlayByPlayDownloader) -> None:
        """Test giveaway description parsing."""
        desc = "CAR GIVEAWAY - #4 GOSTISBEHERE, Def. Zone"
        team, players = downloader._parse_giveaway_takeaway(desc, "GIVE")

        assert team == "CAR"
        assert len(players) == 1
        assert players[0].number == 4
        assert players[0].role == "giver"

    def test_parse_takeaway(self, downloader: PlayByPlayDownloader) -> None:
        """Test takeaway description parsing."""
        desc = "CAR TAKEAWAY - #20 AHO, Off. Zone"
        team, players = downloader._parse_giveaway_takeaway(desc, "TAKE")

        assert team == "CAR"
        assert len(players) == 1
        assert players[0].number == 20
        assert players[0].role == "taker"

    def test_parse_block(self, downloader: PlayByPlayDownloader) -> None:
        """Test blocked shot description parsing."""
        desc = "NYI #7 TSYPLAKOV BLOCKED BY CAR #82 KOTKANIEMI, Wrist, Def. Zone"
        team, players = downloader._parse_block(desc)

        assert team == "NYI"
        assert len(players) == 2

        shooter = next((p for p in players if p.role == "shooter"), None)
        assert shooter is not None
        assert shooter.number == 7

        blocker = next((p for p in players if p.role == "blocker"), None)
        assert blocker is not None
        assert blocker.number == 82


# =============================================================================
# Full Parse Tests
# =============================================================================


class TestFullParse:
    """Tests for full report parsing."""

    @pytest.mark.asyncio
    async def test_parse_report(
        self,
        downloader: PlayByPlayDownloader,
        sample_soup: BeautifulSoup,
    ) -> None:
        """Test full report parsing."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Check structure
        assert "game_id" in result
        assert "season_id" in result
        assert "away_team" in result
        assert "home_team" in result
        assert "events" in result

        # Check values
        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert result["away_team"] == "NYI"
        assert result["home_team"] == "CAR"

        # Should have events
        assert len(result["events"]) >= 1

    @pytest.mark.asyncio
    async def test_download_game_success(
        self,
        downloader: PlayByPlayDownloader,
        sample_html: bytes,
    ) -> None:
        """Test successful game download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = sample_html

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            async with downloader:
                result = await downloader.download_game(2024020500)

        assert result.is_successful
        assert result.status == DownloadStatus.COMPLETED
        assert result.game_id == 2024020500
        assert result.source == "html_pl"
        assert result.raw_content == sample_html


# =============================================================================
# Output Format Tests
# =============================================================================


class TestOutputFormat:
    """Tests for output format compliance."""

    @pytest.mark.asyncio
    async def test_to_dict_output_format(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test _to_dict output format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Verify expected keys
        expected_keys = {
            "game_id",
            "season_id",
            "away_team",
            "home_team",
            "events",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_event_dict_format(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test event dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        if result["events"]:
            event = result["events"][0]
            expected_keys = {
                "event_number",
                "period",
                "strength",
                "time_elapsed",
                "time_remaining",
                "event_type",
                "description",
                "team",
                "zone",
                "shot_type",
                "distance",
                "players",
                "away_on_ice",
                "home_on_ice",
            }
            assert set(event.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_player_dict_format(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test player dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Find an event with players
        for event in result["events"]:
            if event["players"]:
                player = event["players"][0]
                expected_keys = {"number", "name", "team", "role", "stat"}
                assert set(player.keys()) == expected_keys
                break

    @pytest.mark.asyncio
    async def test_player_on_ice_dict_format(
        self, downloader: PlayByPlayDownloader, sample_soup: BeautifulSoup
    ) -> None:
        """Test player on ice dictionary format."""
        result = await downloader._parse_report(sample_soup, 2024020500)

        # Find an event with players on ice
        for event in result["events"]:
            if event["away_on_ice"]:
                player = event["away_on_ice"][0]
                expected_keys = {"number", "position", "name"}
                assert set(player.keys()) == expected_keys
                break


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_description(self, downloader: PlayByPlayDownloader) -> None:
        """Test parsing empty description."""
        team, players = downloader._parse_faceoff("")
        assert team is None
        assert players == []

    def test_malformed_faceoff(self, downloader: PlayByPlayDownloader) -> None:
        """Test parsing malformed faceoff."""
        team, players = downloader._parse_faceoff("Some invalid text")
        assert team is None
        assert players == []

    def test_goal_without_assists(self, downloader: PlayByPlayDownloader) -> None:
        """Test goal without assists."""
        desc = "CAR #37 SVECHNIKOV(12), Wrist , Off. Zone, 6 ft."
        team, players = downloader._parse_goal(desc)

        assert team == "CAR"
        assert len(players) == 1
        assert players[0].role == "scorer"

    def test_penalty_without_drawn_by(self, downloader: PlayByPlayDownloader) -> None:
        """Test penalty without drawn by."""
        desc = "NYI #28 ROMANOV High-sticking(2 min), Def. Zone"
        team, players = downloader._parse_penalty(desc)

        assert team == "NYI"
        assert len(players) == 1
        assert players[0].role == "penalized"

    def test_unknown_team_abbrev(self, downloader: PlayByPlayDownloader) -> None:
        """Test unknown team name to abbreviation."""
        abbrev = downloader._team_name_to_abbrev("FAKE TEAM NAME")
        assert abbrev == "FAK"  # Takes first 3 characters


# =============================================================================
# Integration Tests with Real Fixture
# =============================================================================


class TestRealFixture:
    """Tests using real HTML fixture if available."""

    @pytest.mark.asyncio
    async def test_real_fixture_parsing(self, downloader: PlayByPlayDownloader) -> None:
        """Test parsing of real fixture file."""
        fixture_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "fixtures"
            / "html"
            / "PL020500.HTM"
        )

        if not fixture_path.exists():
            pytest.skip("Real fixture not available")

        html = fixture_path.read_bytes()
        soup = BeautifulSoup(html.decode("utf-8"), "lxml")

        result = await downloader._parse_report(soup, 2024020500)

        # Verify we got meaningful data
        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert result["away_team"] == "NYI"
        assert result["home_team"] == "CAR"

        # Should have many events (a real game has 200-400 events)
        assert len(result["events"]) > 50

        # Verify we have different event types
        event_types = {e["event_type"] for e in result["events"]}
        assert "FAC" in event_types
        assert "SHOT" in event_types
        assert "GOAL" in event_types

        # Verify goals have proper structure
        goals = [e for e in result["events"] if e["event_type"] == "GOAL"]
        assert len(goals) >= 4  # Game was 4-0

        for goal in goals:
            assert goal["team"] == "CAR"
            scorer = next((p for p in goal["players"] if p["role"] == "scorer"), None)
            assert scorer is not None
            assert scorer["number"] > 0
