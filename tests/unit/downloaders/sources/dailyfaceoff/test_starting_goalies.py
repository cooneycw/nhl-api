"""Unit tests for StartingGoaliesDownloader."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.dailyfaceoff import (
    ConfirmationStatus,
    GoalieStart,
    StartingGoaliesDownloader,
    TonightsGoalies,
)


class TestConfirmationStatus:
    """Tests for ConfirmationStatus enum."""

    def test_from_strength_id_confirmed(self) -> None:
        """Test confirmed status from strength ID 2."""
        status = ConfirmationStatus.from_strength_id(2)
        assert status == ConfirmationStatus.CONFIRMED

    def test_from_strength_id_likely(self) -> None:
        """Test likely status from strength ID 3."""
        status = ConfirmationStatus.from_strength_id(3)
        assert status == ConfirmationStatus.LIKELY

    def test_from_strength_id_unconfirmed(self) -> None:
        """Test unconfirmed status from other strength IDs."""
        assert ConfirmationStatus.from_strength_id(1) == ConfirmationStatus.UNCONFIRMED
        assert ConfirmationStatus.from_strength_id(0) == ConfirmationStatus.UNCONFIRMED
        assert (
            ConfirmationStatus.from_strength_id(None) == ConfirmationStatus.UNCONFIRMED
        )

    def test_from_string_confirmed(self) -> None:
        """Test confirmed status from string."""
        assert (
            ConfirmationStatus.from_string("confirmed") == ConfirmationStatus.CONFIRMED
        )
        assert (
            ConfirmationStatus.from_string("Confirmed") == ConfirmationStatus.CONFIRMED
        )
        assert (
            ConfirmationStatus.from_string("CONFIRMED") == ConfirmationStatus.CONFIRMED
        )

    def test_from_string_likely(self) -> None:
        """Test likely status from string."""
        assert ConfirmationStatus.from_string("likely") == ConfirmationStatus.LIKELY
        assert ConfirmationStatus.from_string("Likely") == ConfirmationStatus.LIKELY
        assert ConfirmationStatus.from_string("expected") == ConfirmationStatus.LIKELY

    def test_from_string_unconfirmed(self) -> None:
        """Test unconfirmed status from string."""
        assert (
            ConfirmationStatus.from_string("unknown") == ConfirmationStatus.UNCONFIRMED
        )
        assert ConfirmationStatus.from_string(None) == ConfirmationStatus.UNCONFIRMED
        assert ConfirmationStatus.from_string("") == ConfirmationStatus.UNCONFIRMED


class TestGoalieStart:
    """Tests for GoalieStart dataclass."""

    def test_create_goalie_start(self) -> None:
        """Test creating a goalie start with all fields."""
        game_time = datetime(2025, 12, 21, 18, 0, 0, tzinfo=UTC)
        goalie = GoalieStart(
            goalie_name="Connor Hellebuyck",
            goalie_id=12345,
            team_id=52,
            team_abbreviation="WPG",
            opponent_id=10,
            opponent_abbreviation="TOR",
            game_time=game_time,
            status=ConfirmationStatus.CONFIRMED,
            is_home=True,
            wins=20,
            losses=8,
            otl=2,
            save_pct=0.925,
            gaa=2.35,
            shutouts=3,
        )
        assert goalie.goalie_name == "Connor Hellebuyck"
        assert goalie.goalie_id == 12345
        assert goalie.team_id == 52
        assert goalie.team_abbreviation == "WPG"
        assert goalie.opponent_id == 10
        assert goalie.opponent_abbreviation == "TOR"
        assert goalie.game_time == game_time
        assert goalie.status == ConfirmationStatus.CONFIRMED
        assert goalie.is_home is True
        assert goalie.wins == 20
        assert goalie.losses == 8
        assert goalie.otl == 2
        assert goalie.save_pct == 0.925
        assert goalie.gaa == 2.35
        assert goalie.shutouts == 3

    def test_create_goalie_start_minimal(self) -> None:
        """Test creating a goalie start with minimal fields."""
        game_time = datetime.now(UTC)
        goalie = GoalieStart(
            goalie_name="Test Goalie",
            goalie_id=1,
            team_id=0,
            team_abbreviation="",
            opponent_id=0,
            opponent_abbreviation="",
            game_time=game_time,
            status=ConfirmationStatus.UNCONFIRMED,
            is_home=False,
        )
        assert goalie.goalie_name == "Test Goalie"
        assert goalie.wins is None
        assert goalie.losses is None
        assert goalie.save_pct is None

    def test_goalie_start_is_frozen(self) -> None:
        """Test that goalie start is immutable."""
        goalie = GoalieStart(
            goalie_name="Test",
            goalie_id=1,
            team_id=0,
            team_abbreviation="",
            opponent_id=0,
            opponent_abbreviation="",
            game_time=datetime.now(UTC),
            status=ConfirmationStatus.UNCONFIRMED,
            is_home=False,
        )
        with pytest.raises(AttributeError):
            goalie.goalie_name = "Changed"  # type: ignore[misc]


class TestTonightsGoalies:
    """Tests for TonightsGoalies dataclass."""

    def test_create_tonights_goalies(self) -> None:
        """Test creating tonight's goalies container."""
        tonights = TonightsGoalies()
        assert tonights.starts == []
        assert tonights.game_date is None
        assert isinstance(tonights.fetched_at, datetime)

    def test_tonights_goalies_with_starts(self) -> None:
        """Test tonight's goalies with actual starts."""
        game_time = datetime(2025, 12, 21, 19, 0, 0, tzinfo=UTC)
        start = GoalieStart(
            goalie_name="Test Goalie",
            goalie_id=1,
            team_id=10,
            team_abbreviation="TOR",
            opponent_id=6,
            opponent_abbreviation="BOS",
            game_time=game_time,
            status=ConfirmationStatus.CONFIRMED,
            is_home=True,
        )
        tonights = TonightsGoalies(
            starts=[start],
            game_date=game_time,
        )
        assert len(tonights.starts) == 1
        assert tonights.game_date == game_time


class TestStartingGoaliesDownloader:
    """Tests for StartingGoaliesDownloader."""

    @pytest.fixture
    def downloader(self) -> StartingGoaliesDownloader:
        """Create a StartingGoaliesDownloader instance."""
        return StartingGoaliesDownloader()

    @pytest.fixture
    def sample_next_data(self) -> dict[str, Any]:
        """Sample __NEXT_DATA__ JSON structure."""
        return {
            "props": {
                "pageProps": {
                    "games": [
                        {
                            "homeTeamSlug": "toronto-maple-leafs",
                            "awayTeamSlug": "boston-bruins",
                            "homeGoalieName": "Joseph Woll",
                            "homeGoalieId": 8479361,
                            "awayGoalieName": "Jeremy Swayman",
                            "awayGoalieId": 8480280,
                            "homeNewsStrengthId": 2,
                            "awayNewsStrengthId": 3,
                            "homeNewsStrengthName": "Confirmed",
                            "awayNewsStrengthName": "Likely",
                            "dateGmt": "2025-12-21T19:00:00.000Z",
                            "homeGoalieWins": 15,
                            "homeGoalieLosses": 5,
                            "homeGoalieOtl": 2,
                            "homeGoalieSavePct": 0.920,
                            "homeGoalieGaa": 2.50,
                            "homeGoalieShutouts": 2,
                            "awayGoalieWins": 18,
                            "awayGoalieLosses": 7,
                            "awayGoalieOtl": 1,
                            "awayGoalieSavePct": 0.915,
                            "awayGoalieGaa": 2.75,
                            "awayGoalieShutouts": 1,
                        },
                        {
                            "homeTeamSlug": "winnipeg-jets",
                            "awayTeamSlug": "edmonton-oilers",
                            "homeGoalieName": "Connor Hellebuyck",
                            "homeGoalieId": 8476945,
                            "awayGoalieName": "Stuart Skinner",
                            "awayGoalieId": 8479973,
                            "homeNewsStrengthId": 2,
                            "awayNewsStrengthId": 2,
                            "dateGmt": "2025-12-21T20:00:00.000Z",
                        },
                    ]
                }
            }
        }

    def test_properties(self, downloader: StartingGoaliesDownloader) -> None:
        """Test downloader properties."""
        assert downloader.data_type == "starting_goalies"
        assert downloader.page_path == "starting-goalies"
        assert downloader.source_name == "dailyfaceoff_starting_goalies"

    def test_extract_next_data(self, downloader: StartingGoaliesDownloader) -> None:
        """Test extracting __NEXT_DATA__ from HTML."""
        html = """
        <html>
            <head>
                <script id="__NEXT_DATA__" type="application/json">
                    {"props": {"pageProps": {"games": []}}}
                </script>
            </head>
            <body></body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        data = downloader._extract_next_data(soup)
        assert data is not None
        assert "props" in data

    def test_extract_next_data_missing(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling missing __NEXT_DATA__."""
        html = "<html><body>No data</body></html>"
        soup = BeautifulSoup(html, "lxml")
        data = downloader._extract_next_data(soup)
        assert data is None

    def test_extract_next_data_invalid_json(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling invalid JSON in __NEXT_DATA__."""
        html = """
        <html>
            <script id="__NEXT_DATA__">not valid json</script>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        data = downloader._extract_next_data(soup)
        assert data is None

    def test_get_games_from_next_data(
        self,
        downloader: StartingGoaliesDownloader,
        sample_next_data: dict[str, Any],
    ) -> None:
        """Test extracting games from NEXT_DATA."""
        games = downloader._get_games_from_next_data(sample_next_data)
        assert len(games) == 2
        assert games[0]["homeGoalieName"] == "Joseph Woll"
        assert games[1]["homeGoalieName"] == "Connor Hellebuyck"

    def test_get_games_from_next_data_empty(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling empty or invalid structure."""
        assert downloader._get_games_from_next_data({}) == []
        assert downloader._get_games_from_next_data({"props": {}}) == []
        assert downloader._get_games_from_next_data({"props": {"pageProps": {}}}) == []

    def test_parse_goalie_from_game_home(
        self,
        downloader: StartingGoaliesDownloader,
        sample_next_data: dict[str, Any],
    ) -> None:
        """Test parsing home goalie from game data."""
        game = sample_next_data["props"]["pageProps"]["games"][0]
        goalie = downloader._parse_goalie_from_game(game, is_home=True)

        assert goalie is not None
        assert goalie.goalie_name == "Joseph Woll"
        assert goalie.goalie_id == 8479361
        assert goalie.status == ConfirmationStatus.CONFIRMED
        assert goalie.is_home is True
        assert goalie.wins == 15
        assert goalie.losses == 5
        assert goalie.save_pct == 0.920
        assert goalie.gaa == 2.50

    def test_parse_goalie_from_game_away(
        self,
        downloader: StartingGoaliesDownloader,
        sample_next_data: dict[str, Any],
    ) -> None:
        """Test parsing away goalie from game data."""
        game = sample_next_data["props"]["pageProps"]["games"][0]
        goalie = downloader._parse_goalie_from_game(game, is_home=False)

        assert goalie is not None
        assert goalie.goalie_name == "Jeremy Swayman"
        assert goalie.goalie_id == 8480280
        assert goalie.status == ConfirmationStatus.LIKELY
        assert goalie.is_home is False
        assert goalie.wins == 18

    def test_parse_goalie_from_game_missing_name(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling missing goalie name."""
        game = {"homeGoalieId": 12345}  # No name
        goalie = downloader._parse_goalie_from_game(game, is_home=True)
        assert goalie is None

    def test_parse_goalie_from_game_missing_id(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling missing goalie ID."""
        game = {"homeGoalieName": "Test Goalie"}  # No ID
        goalie = downloader._parse_goalie_from_game(game, is_home=True)
        assert goalie is None

    def test_parse_game_time(self, downloader: StartingGoaliesDownloader) -> None:
        """Test parsing game time."""
        time = downloader._parse_game_time("2025-12-21T19:00:00.000Z")
        assert time.year == 2025
        assert time.month == 12
        assert time.day == 21
        assert time.hour == 19

    def test_parse_game_time_invalid(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling invalid game time."""
        time = downloader._parse_game_time("invalid")
        # Should return current time without raising
        assert isinstance(time, datetime)

    def test_parse_game_time_none(self, downloader: StartingGoaliesDownloader) -> None:
        """Test handling None game time."""
        time = downloader._parse_game_time(None)
        assert isinstance(time, datetime)

    def test_safe_int(self, downloader: StartingGoaliesDownloader) -> None:
        """Test safe integer conversion."""
        assert downloader._safe_int(5) == 5
        assert downloader._safe_int("10") == 10
        assert downloader._safe_int(None) is None
        assert downloader._safe_int("invalid") is None

    def test_safe_float(self, downloader: StartingGoaliesDownloader) -> None:
        """Test safe float conversion."""
        assert downloader._safe_float(0.920) == 0.920
        assert downloader._safe_float("2.5") == 2.5
        assert downloader._safe_float(None) is None
        assert downloader._safe_float("invalid") is None

    def test_parse_starting_goalies(
        self,
        downloader: StartingGoaliesDownloader,
        sample_next_data: dict[str, Any],
    ) -> None:
        """Test parsing full starting goalies page."""
        html = f"""
        <html>
            <script id="__NEXT_DATA__" type="application/json">
                {json.dumps(sample_next_data)}
            </script>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        tonights = downloader._parse_starting_goalies(soup)

        # 2 games * 2 goalies each = 4 starts
        assert len(tonights.starts) == 4
        assert tonights.game_date is not None

        # Check first game goalies
        goalie_names = [s.goalie_name for s in tonights.starts]
        assert "Joseph Woll" in goalie_names
        assert "Jeremy Swayman" in goalie_names
        assert "Connor Hellebuyck" in goalie_names
        assert "Stuart Skinner" in goalie_names

    def test_to_dict(self, downloader: StartingGoaliesDownloader) -> None:
        """Test converting TonightsGoalies to dictionary."""
        game_time = datetime(2025, 12, 21, 19, 0, 0, tzinfo=UTC)
        start = GoalieStart(
            goalie_name="Test Goalie",
            goalie_id=1,
            team_id=10,
            team_abbreviation="TOR",
            opponent_id=6,
            opponent_abbreviation="BOS",
            game_time=game_time,
            status=ConfirmationStatus.CONFIRMED,
            is_home=True,
            wins=10,
            losses=5,
        )
        tonights = TonightsGoalies(
            starts=[start],
            game_date=game_time,
        )

        result = downloader._to_dict(tonights)

        assert "starts" in result
        assert "game_date" in result
        assert "fetched_at" in result
        assert "game_count" in result
        assert result["game_count"] == 1
        assert len(result["starts"]) == 1

        start_dict = result["starts"][0]
        assert start_dict["goalie_name"] == "Test Goalie"
        assert start_dict["team_abbreviation"] == "TOR"
        assert start_dict["status"] == "confirmed"
        assert start_dict["wins"] == 10

    @pytest.mark.asyncio
    async def test_download_tonight_success(
        self,
        downloader: StartingGoaliesDownloader,
        sample_next_data: dict[str, Any],
    ) -> None:
        """Test successful download of tonight's goalies."""
        html_content = f"""
        <html>
            <script id="__NEXT_DATA__" type="application/json">
                {json.dumps(sample_next_data)}
            </script>
        </html>
        """.encode()

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = html_content
        mock_response.status = 200

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await downloader.download_tonight()

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "dailyfaceoff_starting_goalies"
        assert len(result.data["starts"]) == 4

    @pytest.mark.asyncio
    async def test_download_tonight_http_error(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling HTTP error during download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status = 500

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            with pytest.raises(Exception) as exc_info:
                await downloader.download_tonight()

            assert "Failed to fetch starting goalies" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_tonight_invalid_html(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling non-HTML response."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = b"not html content"
        mock_response.status = 200

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            with pytest.raises(Exception) as exc_info:
                await downloader.download_tonight()

            assert "not valid HTML" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_tonight_no_games(
        self, downloader: StartingGoaliesDownloader
    ) -> None:
        """Test handling page with no games."""
        html_content = b"""
        <html>
            <script id="__NEXT_DATA__" type="application/json">
                {"props": {"pageProps": {"games": []}}}
            </script>
        </html>
        """

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.content = html_content
        mock_response.status = 200

        with patch.object(
            downloader, "_get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await downloader.download_tonight()

        assert result.status == DownloadStatus.COMPLETED
        assert len(result.data["starts"]) == 0
        assert result.data["game_count"] == 0


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_starting_goalies_downloader(self) -> None:
        """Test creating downloader with factory function."""
        from nhl_api.downloaders.sources.dailyfaceoff.starting_goalies import (
            create_starting_goalies_downloader,
        )

        downloader = create_starting_goalies_downloader()
        assert isinstance(downloader, StartingGoaliesDownloader)

    def test_create_starting_goalies_downloader_with_config(self) -> None:
        """Test creating downloader with custom config."""
        from nhl_api.downloaders.sources.dailyfaceoff import DailyFaceoffConfig
        from nhl_api.downloaders.sources.dailyfaceoff.starting_goalies import (
            create_starting_goalies_downloader,
        )

        config = DailyFaceoffConfig(requests_per_second=0.5)
        downloader = create_starting_goalies_downloader(config)
        assert isinstance(downloader, StartingGoaliesDownloader)
        assert downloader.config.requests_per_second == 0.5
