"""Unit tests for InjuryDownloader.

Tests the parsing of injury data from DailyFaceoff.com.
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
    InjuryDownloader,
    InjuryRecord,
    InjuryStatus,
    TeamInjuries,
)

# --- Fixtures ---


@pytest.fixture
def config() -> DailyFaceoffConfig:
    """Create test config."""
    return DailyFaceoffConfig()


@pytest.fixture
def downloader(config: DailyFaceoffConfig) -> InjuryDownloader:
    """Create downloader instance."""
    return InjuryDownloader(config)


@pytest.fixture
def sample_team_next_data() -> dict[str, Any]:
    """Sample __NEXT_DATA__ structure with team injury data."""
    return {
        "props": {
            "pageProps": {
                "players": [
                    {
                        "name": "Anthony Stolarz",
                        "injuryStatus": "ir",
                        "playerId": "12345",
                        "details": "Upper-body injury suffered in practice",
                        "updatedAt": "2025-12-15T10:00:00Z",
                    },
                    {
                        "name": "Chris Tanev",
                        "injuryStatus": "out",
                        "playerId": "12346",
                        "details": "Undisclosed condition",
                    },
                    {
                        "name": "Auston Matthews",
                        "injuryStatus": None,  # Not injured
                        "playerId": "12347",
                    },
                ],
            }
        }
    }


@pytest.fixture
def sample_league_next_data() -> dict[str, Any]:
    """Sample __NEXT_DATA__ structure with league injury data."""
    return {
        "props": {
            "pageProps": {
                "news": [
                    {
                        "playerName": "Connor McDavid",
                        "teamAbbreviation": "EDM",
                        "newsCategoryName": "Injury",
                        "details": "Ankle injury suffered in game vs Calgary",
                        "playerId": "99999",
                        "createdAt": "2025-12-20T15:30:00Z",
                    },
                    {
                        "playerName": "Sidney Crosby",
                        "teamAbbreviation": "PIT",
                        "newsCategoryName": "Injury",
                        "details": "Lower-body injury, day-to-day",
                        "playerId": "88888",
                    },
                    {
                        "playerName": "Alex Ovechkin",
                        "teamAbbreviation": "WSH",
                        "newsCategoryName": "Trade",  # Not an injury
                        "details": "Trade rumors",
                    },
                ],
            }
        }
    }


@pytest.fixture
def html_with_team_injuries(sample_team_next_data: dict[str, Any]) -> str:
    """Generate HTML with team injury data."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <script id="__NEXT_DATA__" type="application/json">
        {json.dumps(sample_team_next_data)}
        </script>
    </body>
    </html>
    """


@pytest.fixture
def html_with_league_injuries(sample_league_next_data: dict[str, Any]) -> str:
    """Generate HTML with league injury data."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <script id="__NEXT_DATA__" type="application/json">
        {json.dumps(sample_league_next_data)}
        </script>
    </body>
    </html>
    """


@pytest.fixture
def html_with_injury_classes() -> str:
    """Generate HTML with injury CSS classes."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <div class="player ir">
            <a href="/players/news/test-player/12345">Test Player</a>
        </div>
        <div class="player out">
            <a href="/players/news/another-player/12346">Another Player</a>
        </div>
        <div class="player">
            <a href="/players/news/healthy-player/12347">Healthy Player</a>
        </div>
    </body>
    </html>
    """


# --- InjuryStatus Tests ---


class TestInjuryStatus:
    """Tests for InjuryStatus enum."""

    def test_enum_values(self) -> None:
        """Test enum has expected values."""
        assert InjuryStatus.IR.value == "ir"
        assert InjuryStatus.DTD.value == "day-to-day"
        assert InjuryStatus.OUT.value == "out"
        assert InjuryStatus.QUESTIONABLE.value == "questionable"
        assert InjuryStatus.GMD.value == "game-time-decision"

    def test_from_string_ir(self) -> None:
        """Test from_string for IR status."""
        assert InjuryStatus.from_string("ir") == InjuryStatus.IR
        assert InjuryStatus.from_string("IR") == InjuryStatus.IR
        assert InjuryStatus.from_string("injured reserve") == InjuryStatus.IR

    def test_from_string_dtd(self) -> None:
        """Test from_string for DTD status."""
        assert InjuryStatus.from_string("dtd") == InjuryStatus.DTD
        assert InjuryStatus.from_string("day-to-day") == InjuryStatus.DTD

    def test_from_string_out(self) -> None:
        """Test from_string for OUT status."""
        assert InjuryStatus.from_string("out") == InjuryStatus.OUT
        assert InjuryStatus.from_string("OUT") == InjuryStatus.OUT

    def test_from_string_gmd(self) -> None:
        """Test from_string for GMD status."""
        assert InjuryStatus.from_string("gmd") == InjuryStatus.GMD
        assert InjuryStatus.from_string("gtd") == InjuryStatus.GMD
        assert InjuryStatus.from_string("game-time-decision") == InjuryStatus.GMD

    def test_from_string_none(self) -> None:
        """Test from_string returns None for unknown."""
        assert InjuryStatus.from_string(None) is None
        assert InjuryStatus.from_string("") is None
        assert InjuryStatus.from_string("unknown") is None


# --- Data Class Tests ---


class TestInjuryRecord:
    """Tests for InjuryRecord dataclass."""

    def test_create_minimal(self) -> None:
        """Test creating record with minimal fields."""
        record = InjuryRecord(
            player_name="Test Player",
            team_id=10,
            team_abbreviation="TOR",
            injury_type=None,
            status=None,
            expected_return=None,
            details=None,
            player_id=None,
            updated_at=None,
        )
        assert record.player_name == "Test Player"
        assert record.team_id == 10
        assert record.team_abbreviation == "TOR"

    def test_create_full(self) -> None:
        """Test creating record with all fields."""
        now = datetime.now(UTC)
        record = InjuryRecord(
            player_name="Test Player",
            team_id=10,
            team_abbreviation="TOR",
            injury_type="upper-body",
            status=InjuryStatus.IR,
            expected_return="Week-to-week",
            details="Suffered injury in practice",
            player_id="12345",
            updated_at=now,
        )
        assert record.injury_type == "upper-body"
        assert record.status == InjuryStatus.IR
        assert record.expected_return == "Week-to-week"
        assert record.updated_at == now

    def test_frozen(self) -> None:
        """Test that InjuryRecord is immutable."""
        record = InjuryRecord(
            player_name="Test",
            team_id=10,
            team_abbreviation="TOR",
            injury_type=None,
            status=None,
            expected_return=None,
            details=None,
            player_id=None,
            updated_at=None,
        )
        with pytest.raises(AttributeError):
            record.player_name = "Changed"  # type: ignore[misc]


class TestTeamInjuries:
    """Tests for TeamInjuries dataclass."""

    def test_create_team_injuries(self) -> None:
        """Test creating TeamInjuries."""
        now = datetime.now(UTC)
        injury = InjuryRecord(
            player_name="Test",
            team_id=10,
            team_abbreviation="TOR",
            injury_type=None,
            status=InjuryStatus.IR,
            expected_return=None,
            details=None,
            player_id=None,
            updated_at=None,
        )
        team_injuries = TeamInjuries(
            team_id=10,
            team_abbreviation="TOR",
            injuries=(injury,),
            fetched_at=now,
        )
        assert team_injuries.team_id == 10
        assert len(team_injuries.injuries) == 1
        assert team_injuries.fetched_at == now


# --- Downloader Property Tests ---


class TestDownloaderProperties:
    """Tests for InjuryDownloader properties."""

    def test_data_type(self, downloader: InjuryDownloader) -> None:
        """Test data_type property."""
        assert downloader.data_type == "injuries"

    def test_page_path(self, downloader: InjuryDownloader) -> None:
        """Test page_path property."""
        assert downloader.page_path == "line-combinations"

    def test_source_name(self, downloader: InjuryDownloader) -> None:
        """Test source_name property."""
        assert downloader.source_name == "dailyfaceoff_injuries"


# --- JSON Parsing Tests ---


class TestParseFromJson:
    """Tests for JSON parsing methods."""

    def test_parse_team_injuries_from_json(
        self,
        downloader: InjuryDownloader,
        html_with_team_injuries: str,
    ) -> None:
        """Test parsing team injuries from __NEXT_DATA__."""
        soup = BeautifulSoup(html_with_team_injuries, "lxml")

        injuries = downloader._parse_injuries_from_json(soup, 10, "TOR")
        assert len(injuries) == 2  # Only 2 have injury status

        # Check first injury
        stolarz = next(i for i in injuries if "Stolarz" in i.player_name)
        assert stolarz.status == InjuryStatus.IR
        assert stolarz.player_id == "12345"
        assert "upper-body" in (stolarz.injury_type or "").lower()

    def test_parse_no_json(self, downloader: InjuryDownloader) -> None:
        """Test parsing when no __NEXT_DATA__ exists."""
        html = "<!DOCTYPE html><html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")

        injuries = downloader._parse_injuries_from_json(soup, 10, "TOR")
        assert injuries == []

    def test_parse_invalid_json(self, downloader: InjuryDownloader) -> None:
        """Test parsing with invalid JSON."""
        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <script id="__NEXT_DATA__">{invalid}</script>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")

        injuries = downloader._parse_injuries_from_json(soup, 10, "TOR")
        assert injuries == []


class TestParseLeagueInjuries:
    """Tests for league injuries parsing."""

    def test_parse_league_injuries_from_json(
        self,
        downloader: InjuryDownloader,
        html_with_league_injuries: str,
    ) -> None:
        """Test parsing league injuries from JSON."""
        soup = BeautifulSoup(html_with_league_injuries, "lxml")

        injuries = downloader._parse_league_injuries_page(soup)
        assert len(injuries) == 2  # Trade news excluded

        # Check McDavid injury
        mcdavid = next(i for i in injuries if "McDavid" in i.player_name)
        assert mcdavid.team_abbreviation == "EDM"
        assert "ankle" in (mcdavid.injury_type or "").lower()

    def test_news_item_to_injury_not_injury_category(
        self, downloader: InjuryDownloader
    ) -> None:
        """Test news item with non-injury category is skipped."""
        item = {
            "playerName": "Test Player",
            "newsCategoryName": "Trade",
            "teamAbbreviation": "TOR",
        }
        result = downloader._news_item_to_injury(item)
        assert result is None

    def test_news_item_to_injury_no_name(self, downloader: InjuryDownloader) -> None:
        """Test news item without player name is skipped."""
        item = {
            "newsCategoryName": "Injury",
            "teamAbbreviation": "TOR",
        }
        result = downloader._news_item_to_injury(item)
        assert result is None


# --- HTML Parsing Tests ---


class TestParseFromHtml:
    """Tests for HTML parsing methods."""

    def test_parse_injuries_from_html_classes(
        self,
        downloader: InjuryDownloader,
        html_with_injury_classes: str,
    ) -> None:
        """Test parsing injuries from CSS classes."""
        soup = BeautifulSoup(html_with_injury_classes, "lxml")

        injuries = downloader._parse_injuries_from_html(soup, 10, "TOR")
        assert len(injuries) == 2  # Only IR and OUT players

        # Check statuses
        statuses = [i.status for i in injuries]
        assert InjuryStatus.IR in statuses
        assert InjuryStatus.OUT in statuses

    def test_parse_no_injuries_html(self, downloader: InjuryDownloader) -> None:
        """Test parsing when no injury elements exist."""
        html = "<!DOCTYPE html><html><body><div>No injuries</div></body></html>"
        soup = BeautifulSoup(html, "lxml")

        injuries = downloader._parse_injuries_from_html(soup, 10, "TOR")
        assert injuries == []


# --- Helper Method Tests ---


class TestHelperMethods:
    """Tests for helper methods."""

    def test_extract_injury_type_upper_body(self, downloader: InjuryDownloader) -> None:
        """Test extracting upper-body injury type."""
        result = downloader._extract_injury_type("Upper-body injury in practice")
        assert result == "upper-body"

    def test_extract_injury_type_lower_body(self, downloader: InjuryDownloader) -> None:
        """Test extracting lower-body injury type."""
        result = downloader._extract_injury_type("Lower body injury")
        assert result == "lower-body"

    def test_extract_injury_type_specific(self, downloader: InjuryDownloader) -> None:
        """Test extracting specific injury types."""
        assert downloader._extract_injury_type("Knee surgery") == "knee"
        assert downloader._extract_injury_type("Shoulder injury") == "shoulder"
        assert downloader._extract_injury_type("Concussion protocol") == "concussion"

    def test_extract_injury_type_not_found(self, downloader: InjuryDownloader) -> None:
        """Test when injury type not found."""
        result = downloader._extract_injury_type("Some vague injury")
        assert result is None

    def test_get_team_id_from_abbr(self, downloader: InjuryDownloader) -> None:
        """Test getting team ID from abbreviation."""
        assert downloader._get_team_id_from_abbr("TOR") == 10
        assert downloader._get_team_id_from_abbr("EDM") == 22
        assert downloader._get_team_id_from_abbr("INVALID") == 0

    def test_dict_to_injury_record(self, downloader: InjuryDownloader) -> None:
        """Test converting dict to InjuryRecord."""
        data = {
            "name": "Test Player",
            "injuryStatus": "ir",
            "playerId": "12345",
            "details": "Upper-body injury",
            "updatedAt": "2025-12-15T10:00:00Z",
        }
        record = downloader._dict_to_injury_record(data, 10, "TOR")

        assert record is not None
        assert record.player_name == "Test Player"
        assert record.status == InjuryStatus.IR
        assert record.injury_type == "upper-body"
        assert record.player_id == "12345"
        assert record.updated_at is not None

    def test_dict_to_injury_record_no_name(self, downloader: InjuryDownloader) -> None:
        """Test dict without name returns None."""
        data = {"injuryStatus": "ir"}
        result = downloader._dict_to_injury_record(data, 10, "TOR")
        assert result is None

    def test_dict_to_injury_record_alternative_keys(
        self, downloader: InjuryDownloader
    ) -> None:
        """Test dict with alternative key names."""
        data = {
            "playerName": "Alt Name",
            "status": "out",
            "injuryDetails": "Knee injury",
        }
        record = downloader._dict_to_injury_record(data, 10, "TOR")

        assert record is not None
        assert record.player_name == "Alt Name"
        assert record.status == InjuryStatus.OUT
        assert record.injury_type == "knee"


# --- Serialization Tests ---


class TestSerialization:
    """Tests for dictionary conversion."""

    def test_injury_to_dict(self, downloader: InjuryDownloader) -> None:
        """Test converting InjuryRecord to dict."""
        now = datetime.now(UTC)
        record = InjuryRecord(
            player_name="Test Player",
            team_id=10,
            team_abbreviation="TOR",
            injury_type="upper-body",
            status=InjuryStatus.IR,
            expected_return="Week-to-week",
            details="Injury details",
            player_id="12345",
            updated_at=now,
        )
        result = downloader._injury_to_dict(record)

        assert result["player_name"] == "Test Player"
        assert result["team_id"] == 10
        assert result["status"] == "ir"
        assert result["injury_type"] == "upper-body"
        assert result["updated_at"] == now.isoformat()

    def test_injury_to_dict_null_status(self, downloader: InjuryDownloader) -> None:
        """Test injury to dict with null status."""
        record = InjuryRecord(
            player_name="Test",
            team_id=10,
            team_abbreviation="TOR",
            injury_type=None,
            status=None,
            expected_return=None,
            details=None,
            player_id=None,
            updated_at=None,
        )
        result = downloader._injury_to_dict(record)

        assert result["status"] is None
        assert result["updated_at"] is None

    def test_team_injuries_to_dict(self, downloader: InjuryDownloader) -> None:
        """Test converting TeamInjuries to dict."""
        now = datetime.now(UTC)
        injury = InjuryRecord(
            player_name="Test",
            team_id=10,
            team_abbreviation="TOR",
            injury_type=None,
            status=InjuryStatus.IR,
            expected_return=None,
            details=None,
            player_id=None,
            updated_at=None,
        )
        team_injuries = TeamInjuries(
            team_id=10,
            team_abbreviation="TOR",
            injuries=(injury,),
            fetched_at=now,
        )
        result = downloader._team_injuries_to_dict(team_injuries)

        assert result["team_id"] == 10
        assert result["count"] == 1
        assert len(result["injuries"]) == 1


# --- Parse Page Tests ---


class TestParsePage:
    """Tests for the main _parse_page method."""

    @pytest.mark.asyncio
    async def test_parse_page_with_injuries(
        self,
        downloader: InjuryDownloader,
        html_with_team_injuries: str,
    ) -> None:
        """Test _parse_page with injury data."""
        soup = BeautifulSoup(html_with_team_injuries, "lxml")

        result = await downloader._parse_page(soup, 10)

        assert result["team_id"] == 10
        assert result["team_abbreviation"] == "TOR"
        assert result["count"] == 2
        assert len(result["injuries"]) == 2

    @pytest.mark.asyncio
    async def test_parse_page_no_injuries(self, downloader: InjuryDownloader) -> None:
        """Test _parse_page with no injury data."""
        html = "<!DOCTYPE html><html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")

        result = await downloader._parse_page(soup, 10)

        assert result["team_id"] == 10
        assert result["count"] == 0
        assert result["injuries"] == []


# --- Download Tests ---


class TestDownloadTeam:
    """Tests for download_team method."""

    @pytest.mark.asyncio
    async def test_download_team_success(
        self,
        downloader: InjuryDownloader,
        html_with_team_injuries: str,
    ) -> None:
        """Test successful team download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status = 200
        mock_response.content = html_with_team_injuries.encode("utf-8")

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await downloader.download_team(10)

            assert result.status.value == "completed"
            assert result.data["team_id"] == 10
            assert result.data["count"] == 2


class TestDownloadLeagueInjuries:
    """Tests for download_league_injuries method."""

    @pytest.mark.asyncio
    async def test_download_league_injuries_success(
        self,
        downloader: InjuryDownloader,
        html_with_league_injuries: str,
    ) -> None:
        """Test successful league injuries download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status = 200
        mock_response.content = html_with_league_injuries.encode("utf-8")

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await downloader.download_league_injuries()

            assert result.status.value == "completed"
            assert result.data["count"] == 2
            assert len(result.data["injuries"]) == 2

    @pytest.mark.asyncio
    async def test_download_league_injuries_failure(
        self, downloader: InjuryDownloader
    ) -> None:
        """Test failed league injuries download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status = 404

        with patch.object(downloader, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(
                Exception,
                match="Failed to fetch injuries page|download",
            ):
                await downloader.download_league_injuries()


# --- Edge Cases ---


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_find_injured_players_empty_data(
        self, downloader: InjuryDownloader
    ) -> None:
        """Test finding injuries in empty data."""
        result = downloader._find_injured_players({}, 10, "TOR")
        assert result == []

    def test_find_injured_players_in_list(self, downloader: InjuryDownloader) -> None:
        """Test finding injuries in list data."""
        data = [
            {"name": "Player 1", "injuryStatus": "ir"},
            {"name": "Player 2", "injuryStatus": None},
        ]
        result = downloader._find_injured_players(data, 10, "TOR")
        assert len(result) == 1

    def test_deep_search_injuries_max_depth(self, downloader: InjuryDownloader) -> None:
        """Test deep search respects max depth."""
        data: dict[str, Any] = {"name": "Test", "injuryStatus": "ir"}
        for _ in range(15):
            data = {"nested": data}

        result = downloader._deep_search_injuries(data, 10, "TOR", max_depth=5)
        assert result == []

    def test_deep_search_injuries_in_list(self, downloader: InjuryDownloader) -> None:
        """Test deep search through lists."""
        data = {
            "players": [
                {"name": "Healthy"},
                {"name": "Injured", "injuryStatus": "out"},
            ]
        }
        result = downloader._deep_search_injuries(data, 10, "TOR")
        assert len(result) == 1
        assert result[0].player_name == "Injured"

    def test_extract_injury_from_element_no_link(
        self, downloader: InjuryDownloader
    ) -> None:
        """Test extraction fails without player link."""
        html = '<div class="ir">No link here</div>'
        soup = BeautifulSoup(html, "lxml")
        element = soup.find("div")
        assert element is not None

        result = downloader._extract_injury_from_element(element, 10, "TOR")
        assert result is None

    def test_parse_league_injuries_from_html_with_entries(
        self, downloader: InjuryDownloader
    ) -> None:
        """Test parsing league injuries from HTML entries."""
        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <article class="news-item">
                <a href="/players/news/test-player/12345">Test Player</a>
                <a href="/teams/toronto-maple-leafs/news">Toronto (TOR)</a>
                <div class="details">Upper-body injury</div>
            </article>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")

        injuries = downloader._parse_league_injuries_from_html(soup)
        assert len(injuries) == 1
        assert injuries[0].player_name == "Test Player"
        assert injuries[0].team_abbreviation == "TOR"
        assert injuries[0].injury_type == "upper-body"
