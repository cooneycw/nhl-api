"""Unit tests for PenaltyKillDownloader.

Tests the parsing of penalty kill unit data from DailyFaceoff.com.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.sources.dailyfaceoff import (
    DailyFaceoffConfig,
    PenaltyKillDownloader,
    PenaltyKillUnit,
    PKPlayer,
    TeamPenaltyKill,
)

# --- Fixtures ---


@pytest.fixture
def config() -> DailyFaceoffConfig:
    """Create test config."""
    return DailyFaceoffConfig()


@pytest.fixture
def downloader(config: DailyFaceoffConfig) -> PenaltyKillDownloader:
    """Create downloader instance."""
    return PenaltyKillDownloader(config)


@pytest.fixture
def sample_next_data() -> dict[str, Any]:
    """Sample __NEXT_DATA__ structure with PK data.

    Matches real DailyFaceoff structure: props.pageProps.combinations.players[]
    with each player having a groupIdentifier and positionIdentifier.
    """
    return {
        "props": {
            "pageProps": {
                "combinations": {
                    "players": [
                        # PK1 forwards (sk1, sk2)
                        {
                            "name": "Scott Laughton",
                            "jerseyNumber": 21,
                            "positionIdentifier": "sk1",
                            "playerId": "12345",
                            "groupIdentifier": "pk1",
                        },
                        {
                            "name": "Steven Lorentz",
                            "jerseyNumber": 17,
                            "positionIdentifier": "sk2",
                            "playerId": "12346",
                            "groupIdentifier": "pk1",
                        },
                        # PK1 defensemen (sk3, sk4)
                        {
                            "name": "Jake McCabe",
                            "jerseyNumber": 22,
                            "positionIdentifier": "sk3",
                            "playerId": "12347",
                            "groupIdentifier": "pk1",
                        },
                        {
                            "name": "Henry Thrun",
                            "jerseyNumber": 3,
                            "positionIdentifier": "sk4",
                            "playerId": "12348",
                            "groupIdentifier": "pk1",
                        },
                        # PK2 forwards (sk1, sk2)
                        {
                            "name": "Nicolas Roy",
                            "jerseyNumber": 10,
                            "positionIdentifier": "sk1",
                            "playerId": "12349",
                            "groupIdentifier": "pk2",
                        },
                        {
                            "name": "Matthew Knies",
                            "jerseyNumber": 23,
                            "positionIdentifier": "sk2",
                            "playerId": "12350",
                            "groupIdentifier": "pk2",
                        },
                        # PK2 defensemen (sk3, sk4)
                        {
                            "name": "Simon Benoit",
                            "jerseyNumber": 6,
                            "positionIdentifier": "sk3",
                            "playerId": "12351",
                            "groupIdentifier": "pk2",
                        },
                        {
                            "name": "Troy Stecher",
                            "jerseyNumber": 51,
                            "positionIdentifier": "sk4",
                            "playerId": "12352",
                            "groupIdentifier": "pk2",
                        },
                    ],
                },
            },
        },
    }


@pytest.fixture
def html_with_next_data(sample_next_data: dict[str, Any]) -> str:
    """Generate HTML with embedded Next.js data."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <script id="__NEXT_DATA__" type="application/json">
        {json.dumps(sample_next_data)}
        </script>
    </body>
    </html>
    """


@pytest.fixture
def html_with_data_attributes() -> str:
    """Generate HTML with data attributes for PK units."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <div data-group="pk1">
            <a href="/players/news/scott-laughton/12345" data-position="C">#21 Scott Laughton</a>
            <a href="/players/news/steven-lorentz/12346" data-position="F">#17 Steven Lorentz</a>
            <a href="/players/news/jake-mccabe/12347" data-position="D">#22 Jake McCabe</a>
            <a href="/players/news/henry-thrun/12348" data-position="D">#3 Henry Thrun</a>
        </div>
        <div data-group="pk2">
            <a href="/players/news/nicolas-roy/12349" data-position="C">#10 Nicolas Roy</a>
            <a href="/players/news/matthew-knies/12350" data-position="LW">#23 Matthew Knies</a>
            <a href="/players/news/simon-benoit/12351" data-position="D">#6 Simon Benoit</a>
            <a href="/players/news/troy-stecher/12352" data-position="D">#51 Troy Stecher</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def html_with_section_structure() -> str:
    """Generate HTML with section-based structure."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <section>
            <h3>1st Penalty Kill Unit</h3>
            <div>
                <a href="/players/news/player-one/1001">Player One</a>
                <a href="/players/news/player-two/1002">Player Two</a>
                <a href="/players/news/player-three/1003">Player Three</a>
                <a href="/players/news/player-four/1004">Player Four</a>
            </div>
        </section>
        <section>
            <h3>2nd Penalty Kill Unit</h3>
            <div>
                <a href="/players/news/player-five/1005">Player Five</a>
                <a href="/players/news/player-six/1006">Player Six</a>
                <a href="/players/news/player-seven/1007">Player Seven</a>
                <a href="/players/news/player-eight/1008">Player Eight</a>
            </div>
        </section>
    </body>
    </html>
    """


# --- Data Class Tests ---


class TestPKPlayer:
    """Tests for PKPlayer dataclass."""

    def test_create_minimal(self) -> None:
        """Test creating player with only name."""
        player = PKPlayer(name="Test Player")
        assert player.name == "Test Player"
        assert player.jersey_number is None
        assert player.position is None
        assert player.player_id is None

    def test_create_full(self) -> None:
        """Test creating player with all fields."""
        player = PKPlayer(
            name="Test Player",
            jersey_number=99,
            position="D",
            player_id="12345",
        )
        assert player.name == "Test Player"
        assert player.jersey_number == 99
        assert player.position == "D"
        assert player.player_id == "12345"

    def test_frozen(self) -> None:
        """Test that PKPlayer is immutable."""
        player = PKPlayer(name="Test")
        with pytest.raises(AttributeError):
            player.name = "Changed"  # type: ignore[misc]


class TestPenaltyKillUnit:
    """Tests for PenaltyKillUnit dataclass."""

    def test_create_unit(self) -> None:
        """Test creating a PK unit."""
        forwards = (
            PKPlayer(name="Forward 1", position="C"),
            PKPlayer(name="Forward 2", position="LW"),
        )
        defensemen = (
            PKPlayer(name="Defenseman 1", position="D"),
            PKPlayer(name="Defenseman 2", position="D"),
        )
        unit = PenaltyKillUnit(
            unit_number=1,
            forwards=forwards,
            defensemen=defensemen,
        )
        assert unit.unit_number == 1
        assert len(unit.forwards) == 2
        assert len(unit.defensemen) == 2

    def test_frozen(self) -> None:
        """Test that PenaltyKillUnit is immutable."""
        unit = PenaltyKillUnit(
            unit_number=1,
            forwards=(),
            defensemen=(),
        )
        with pytest.raises(AttributeError):
            unit.unit_number = 2  # type: ignore[misc]


class TestTeamPenaltyKill:
    """Tests for TeamPenaltyKill dataclass."""

    def test_create_team_pk(self) -> None:
        """Test creating team PK data."""
        pk1 = PenaltyKillUnit(unit_number=1, forwards=(), defensemen=())
        pk2 = PenaltyKillUnit(unit_number=2, forwards=(), defensemen=())
        now = datetime.now(UTC)

        team_pk = TeamPenaltyKill(
            team_id=10,
            team_abbreviation="TOR",
            pk1=pk1,
            pk2=pk2,
            fetched_at=now,
        )

        assert team_pk.team_id == 10
        assert team_pk.team_abbreviation == "TOR"
        assert team_pk.pk1 == pk1
        assert team_pk.pk2 == pk2
        assert team_pk.fetched_at == now


# --- Downloader Property Tests ---


class TestDownloaderProperties:
    """Tests for PenaltyKillDownloader properties."""

    def test_data_type(self, downloader: PenaltyKillDownloader) -> None:
        """Test data_type property."""
        assert downloader.data_type == "penalty_kill"

    def test_page_path(self, downloader: PenaltyKillDownloader) -> None:
        """Test page_path property."""
        assert downloader.page_path == "line-combinations"

    def test_source_name(self, downloader: PenaltyKillDownloader) -> None:
        """Test source_name property."""
        assert downloader.source_name == "dailyfaceoff_penalty_kill"


# --- Parsing Tests ---


class TestParseFromJson:
    """Tests for JSON parsing methods."""

    def test_parse_from_next_data(
        self,
        downloader: PenaltyKillDownloader,
        html_with_next_data: str,
    ) -> None:
        """Test parsing from __NEXT_DATA__."""
        soup = BeautifulSoup(html_with_next_data, "lxml")

        pk1_players = downloader._parse_from_json(soup, "pk1")
        assert len(pk1_players) == 4
        assert pk1_players[0].name == "Scott Laughton"
        assert pk1_players[0].jersey_number == 21
        assert pk1_players[0].position == "sk1"  # DailyFaceoff uses sk1-sk4 identifiers

        pk2_players = downloader._parse_from_json(soup, "pk2")
        assert len(pk2_players) == 4
        assert pk2_players[0].name == "Nicolas Roy"

    def test_parse_no_next_data(
        self,
        downloader: PenaltyKillDownloader,
    ) -> None:
        """Test parsing when no __NEXT_DATA__ exists."""
        html = "<!DOCTYPE html><html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")

        players = downloader._parse_from_json(soup, "pk1")
        assert players == []

    def test_parse_invalid_json(
        self,
        downloader: PenaltyKillDownloader,
    ) -> None:
        """Test parsing with invalid JSON."""
        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <script id="__NEXT_DATA__">
            {invalid json}
            </script>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")

        players = downloader._parse_from_json(soup, "pk1")
        assert players == []


class TestParseFromHtml:
    """Tests for HTML attribute parsing."""

    def test_parse_from_data_attributes(
        self,
        downloader: PenaltyKillDownloader,
        html_with_data_attributes: str,
    ) -> None:
        """Test parsing from data-group attributes."""
        soup = BeautifulSoup(html_with_data_attributes, "lxml")

        pk1_players = downloader._parse_from_html_data(soup, "pk1")
        assert len(pk1_players) == 4
        # Players are found via links inside the data-group div
        assert any("Scott Laughton" in p.name for p in pk1_players)

    def test_parse_no_data_attributes(
        self,
        downloader: PenaltyKillDownloader,
    ) -> None:
        """Test parsing when no data attributes exist."""
        html = "<!DOCTYPE html><html><body><div>No data</div></body></html>"
        soup = BeautifulSoup(html, "lxml")

        players = downloader._parse_from_html_data(soup, "pk1")
        assert players == []


class TestParseFromStructure:
    """Tests for structure-based parsing."""

    def test_parse_from_section_headers(
        self,
        downloader: PenaltyKillDownloader,
        html_with_section_structure: str,
    ) -> None:
        """Test parsing from section headers."""
        soup = BeautifulSoup(html_with_section_structure, "lxml")

        pk1_players = downloader._parse_from_structure(soup, "pk1")
        assert len(pk1_players) == 4
        assert pk1_players[0].name == "Player One"

    def test_parse_no_matching_structure(
        self,
        downloader: PenaltyKillDownloader,
    ) -> None:
        """Test parsing with no matching structure."""
        html = "<!DOCTYPE html><html><body><p>No PK data</p></body></html>"
        soup = BeautifulSoup(html, "lxml")

        players = downloader._parse_from_structure(soup, "pk1")
        assert players == []


# --- Helper Method Tests ---


class TestHelperMethods:
    """Tests for helper methods."""

    def test_is_forward_with_position(self, downloader: PenaltyKillDownloader) -> None:
        """Test _is_forward with position data."""
        assert downloader._is_forward(PKPlayer(name="Test", position="C"))
        assert downloader._is_forward(PKPlayer(name="Test", position="LW"))
        assert downloader._is_forward(PKPlayer(name="Test", position="RW"))
        assert downloader._is_forward(PKPlayer(name="Test", position="F"))
        assert not downloader._is_forward(PKPlayer(name="Test", position="D"))

    def test_is_forward_without_position(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test _is_forward defaults to True."""
        assert downloader._is_forward(PKPlayer(name="Test"))

    def test_is_defenseman_with_position(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test _is_defenseman with position data."""
        assert downloader._is_defenseman(PKPlayer(name="Test", position="D"))
        assert downloader._is_defenseman(PKPlayer(name="Test", position="LD"))
        assert downloader._is_defenseman(PKPlayer(name="Test", position="RD"))
        assert not downloader._is_defenseman(PKPlayer(name="Test", position="C"))

    def test_is_defenseman_without_position(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test _is_defenseman defaults to False."""
        assert not downloader._is_defenseman(PKPlayer(name="Test"))

    def test_dict_to_player(self, downloader: PenaltyKillDownloader) -> None:
        """Test converting dict to PKPlayer."""
        data = {
            "name": "Test Player",
            "jerseyNumber": 99,
            "position": "C",
            "playerId": "12345",
        }
        player = downloader._dict_to_player(data)

        assert player is not None
        assert player.name == "Test Player"
        assert player.jersey_number == 99
        assert player.position == "C"
        assert player.player_id == "12345"

    def test_dict_to_player_alternative_keys(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test dict_to_player with alternative key names."""
        data = {
            "playerName": "Alt Player",
            "number": "77",
            "positionCode": "D",
            "id": 99999,
        }
        player = downloader._dict_to_player(data)

        assert player is not None
        assert player.name == "Alt Player"
        assert player.jersey_number == 77
        assert player.position == "D"
        assert player.player_id == "99999"

    def test_dict_to_player_no_name(self, downloader: PenaltyKillDownloader) -> None:
        """Test dict_to_player returns None without name."""
        data = {"jerseyNumber": 99}
        player = downloader._dict_to_player(data)
        assert player is None


class TestExtractPlayerFromElement:
    """Tests for extracting players from HTML elements."""

    def test_extract_from_link(self, downloader: PenaltyKillDownloader) -> None:
        """Test extracting from player link."""
        html = '<a href="/players/news/test-player/12345">#99 Test Player</a>'
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("a")
        assert element is not None

        player = downloader._extract_player_from_element(element)

        assert player is not None
        assert player.name == "#99 Test Player"
        assert player.player_id == "12345"
        assert player.jersey_number == 99

    def test_extract_no_link(self, downloader: PenaltyKillDownloader) -> None:
        """Test extracting from non-link element."""
        html = "<span>Some Player</span>"
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("span")
        assert element is not None

        player = downloader._extract_player_from_element(element)

        assert player is not None
        assert player.name == "Some Player"


# --- Serialization Tests ---


class TestSerialization:
    """Tests for dictionary conversion."""

    def test_player_to_dict(self, downloader: PenaltyKillDownloader) -> None:
        """Test converting player to dict."""
        player = PKPlayer(
            name="Test Player",
            jersey_number=99,
            position="C",
            player_id="12345",
        )
        result = downloader._player_to_dict(player)

        assert result == {
            "name": "Test Player",
            "jersey_number": 99,
            "position": "C",
            "player_id": "12345",
        }

    def test_unit_to_dict(self, downloader: PenaltyKillDownloader) -> None:
        """Test converting unit to dict."""
        unit = PenaltyKillUnit(
            unit_number=1,
            forwards=(PKPlayer(name="Forward 1"),),
            defensemen=(PKPlayer(name="Defenseman 1"),),
        )
        result = downloader._unit_to_dict(unit)

        assert result["unit_number"] == 1
        assert len(result["forwards"]) == 1
        assert len(result["defensemen"]) == 1

    def test_to_dict(self, downloader: PenaltyKillDownloader) -> None:
        """Test converting TeamPenaltyKill to dict."""
        pk1 = PenaltyKillUnit(unit_number=1, forwards=(), defensemen=())
        now = datetime.now(UTC)

        team_pk = TeamPenaltyKill(
            team_id=10,
            team_abbreviation="TOR",
            pk1=pk1,
            pk2=None,
            fetched_at=now,
        )
        result = downloader._to_dict(team_pk)

        assert result["team_id"] == 10
        assert result["team_abbreviation"] == "TOR"
        assert result["pk1"] is not None
        assert result["pk2"] is None
        assert result["fetched_at"] == now.isoformat()


# --- Parse Page Tests ---


class TestParsePage:
    """Tests for the main _parse_page method."""

    @pytest.mark.asyncio
    async def test_parse_page_with_next_data(
        self,
        downloader: PenaltyKillDownloader,
        html_with_next_data: str,
    ) -> None:
        """Test _parse_page with Next.js data."""
        soup = BeautifulSoup(html_with_next_data, "lxml")

        result = await downloader._parse_page(soup, 10)

        assert result["team_id"] == 10
        assert result["team_abbreviation"] == "TOR"
        assert result["pk1"] is not None
        assert result["pk2"] is not None
        assert len(result["pk1"]["forwards"]) >= 0
        assert len(result["pk1"]["defensemen"]) >= 0

    @pytest.mark.asyncio
    async def test_parse_page_no_data(
        self,
        downloader: PenaltyKillDownloader,
    ) -> None:
        """Test _parse_page with no PK data."""
        html = "<!DOCTYPE html><html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")

        result = await downloader._parse_page(soup, 10)

        assert result["team_id"] == 10
        assert result["pk1"] is None
        assert result["pk2"] is None


# --- Integration Tests ---


class TestDownloadTeam:
    """Tests for download_team method."""

    @pytest.mark.asyncio
    async def test_download_team_success(
        self,
        downloader: PenaltyKillDownloader,
        html_with_next_data: str,
    ) -> None:
        """Test successful team download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status = 200
        mock_response.content = html_with_next_data.encode("utf-8")

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await downloader.download_team(10)

            assert result.status.value == "completed"
            assert result.data["team_id"] == 10
            assert result.data["team_abbreviation"] == "TOR"

    @pytest.mark.asyncio
    async def test_download_team_failure(
        self,
        downloader: PenaltyKillDownloader,
    ) -> None:
        """Test failed team download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status = 404

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(
                Exception,
                match="Failed to fetch team page|download",
            ):
                await downloader.download_team(10)


# --- Edge Cases ---


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_pk_unit_no_players(self, downloader: PenaltyKillDownloader) -> None:
        """Test parsing unit with no players found."""
        html = "<!DOCTYPE html><html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")

        result = downloader._parse_pk_unit(soup, 1)
        assert result is None

    def test_extract_names_from_text(self, downloader: PenaltyKillDownloader) -> None:
        """Test extracting names via regex."""
        text = '"playerName": "John Doe", "name": "Jane Smith"'
        players = downloader._extract_names_from_text(text)

        assert len(players) == 2
        assert players[0].name == "John Doe"
        assert players[1].name == "Jane Smith"

    def test_extract_names_from_text_short_names_filtered(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test that very short names are filtered out."""
        text = '"name": "AB", "name": "Joe Smith"'
        players = downloader._extract_names_from_text(text)

        # "AB" should be filtered (len <= 2)
        assert len(players) == 1
        assert players[0].name == "Joe Smith"

    def test_search_for_group_nested(self, downloader: PenaltyKillDownloader) -> None:
        """Test deep search for group data."""
        data = {
            "level1": {
                "level2": {
                    "items": [{"groupIdentifier": "pk1", "players": [{"name": "Test"}]}]
                }
            }
        }
        players = downloader._search_for_group(data, "pk1")
        assert len(players) == 1
        assert players[0].name == "Test"

    def test_search_for_group_in_list(self, downloader: PenaltyKillDownloader) -> None:
        """Test search for group when data is in a list."""
        data = [
            {"groupIdentifier": "other"},
            {"groupIdentifier": "pk1", "players": [{"name": "Test Player"}]},
        ]
        players = downloader._search_for_group(data, "pk1")
        assert len(players) == 1
        assert players[0].name == "Test Player"

    def test_deep_search_max_depth(self, downloader: PenaltyKillDownloader) -> None:
        """Test deep search respects max depth."""
        # Create deeply nested structure
        data: dict[str, Any] = {"groupIdentifier": "pk1", "players": []}
        for _ in range(15):
            data = {"nested": data}

        # Should not find with shallow depth
        players = downloader._deep_search_group(data, "pk1", max_depth=5)
        assert players == []

    def test_deep_search_in_list(self, downloader: PenaltyKillDownloader) -> None:
        """Test deep search through lists."""
        data = {
            "formations": [
                {"groupIdentifier": "other"},
                {"groupIdentifier": "pk1", "players": [{"name": "Found"}]},
            ]
        }
        players = downloader._deep_search_group(data, "pk1")
        assert len(players) == 1
        assert players[0].name == "Found"

    def test_extract_players_from_group_with_skaters(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test extracting players from group with 'skaters' key."""
        group = {
            "groupIdentifier": "pk1",
            "skaters": [
                {"name": "Skater One", "position": "C"},
                {"name": "Skater Two", "position": "D"},
            ],
        }
        players = downloader._extract_players_from_group(group)
        assert len(players) == 2
        assert players[0].name == "Skater One"

    def test_extract_players_from_group_with_position_slots(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test extracting players from position slot keys."""
        group = {
            "groupIdentifier": "pk1",
            "sk1": {"name": "Player One"},
            "sk2": {"name": "Player Two"},
            "sk3": {"name": "Player Three"},
            "sk4": {"name": "Player Four"},
        }
        players = downloader._extract_players_from_group(group)
        assert len(players) == 4

    def test_extract_player_script_with_groupidentifier(
        self,
        downloader: PenaltyKillDownloader,
    ) -> None:
        """Test parsing from script with groupIdentifier pattern."""
        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <script>
            var data = {"groupIdentifier":"pk1","players":[{"name":"Script Player"}]};
            </script>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        players = downloader._parse_from_json(soup, "pk1")
        assert len(players) == 1
        assert players[0].name == "Script Player"

    def test_extract_player_from_element_with_position_class(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test extracting player with position from CSS class."""
        html = '<div class="forward"><a href="/players/news/test/123">Test Forward</a></div>'
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("div")
        assert element is not None

        player = downloader._extract_player_from_element(element)
        assert player is not None
        assert player.name == "Test Forward"
        assert player.position == "F"

    def test_extract_player_from_element_with_defense_class(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test extracting player with defense position from CSS class."""
        html = '<div class="defense"><a href="/players/news/test/456">Test Defense</a></div>'
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("div")
        assert element is not None

        player = downloader._extract_player_from_element(element)
        assert player is not None
        assert player.name == "Test Defense"
        assert player.position == "D"

    def test_extract_player_from_element_with_data_position(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test extracting player with data-position attribute."""
        html = '<a href="/players/news/test/789" data-position="LW">Left Winger</a>'
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("a")
        assert element is not None

        player = downloader._extract_player_from_element(element)
        assert player is not None
        assert player.name == "Left Winger"
        assert player.position == "LW"

    def test_parse_from_html_data_with_groupidentifier(
        self,
        downloader: PenaltyKillDownloader,
    ) -> None:
        """Test parsing from data-groupidentifier attribute."""
        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <div data-groupidentifier="pk1">
                <a href="/players/news/player1/111">Player One</a>
                <a href="/players/news/player2/222">Player Two</a>
            </div>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        players = downloader._parse_from_html_data(soup, "pk1")
        assert len(players) == 2

    def test_dict_to_player_with_fullname(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test dict_to_player with fullName key."""
        data = {"fullName": "Full Name Player"}
        player = downloader._dict_to_player(data)
        assert player is not None
        assert player.name == "Full Name Player"

    def test_is_forward_uppercase_positions(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test _is_forward with uppercase position names."""
        assert downloader._is_forward(PKPlayer(name="Test", position="CENTER"))
        assert downloader._is_forward(PKPlayer(name="Test", position="FORWARD"))

    def test_is_defenseman_uppercase_positions(
        self, downloader: PenaltyKillDownloader
    ) -> None:
        """Test _is_defenseman with uppercase position names."""
        assert downloader._is_defenseman(PKPlayer(name="Test", position="DEFENSE"))
        assert downloader._is_defenseman(PKPlayer(name="Test", position="DEFENSEMAN"))
