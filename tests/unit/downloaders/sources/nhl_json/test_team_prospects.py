"""Tests for Team Prospects Downloader."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.sources.nhl_json.team_prospects import (
    TeamProspectsDownloader,
    TeamProspectsDownloaderConfig,
    _parse_prospect,
    _parse_team_prospects,
    create_team_prospects_downloader,
)


@pytest.mark.unit
class TestParseProspect:
    """Tests for _parse_prospect function."""

    def test_parse_prospect_complete(self) -> None:
        """Test parsing a complete prospect entry."""
        player_data = {
            "id": 8484144,
            "firstName": {"default": "Connor"},
            "lastName": {"default": "Bedard"},
            "sweaterNumber": 98,
            "positionCode": "C",
            "heightInInches": 70,
            "weightInPounds": 185,
            "birthDate": "2005-07-17",
            "birthCity": {"default": "North Vancouver"},
            "birthCountry": "CAN",
            "shootsCatches": "R",
            "currentTeamAbbrev": "CHI",
            "draftDetails": {
                "year": 2023,
                "round": 1,
                "pickInRound": 1,
                "overallPick": 1,
            },
        }

        result = _parse_prospect(player_data, "CHI")

        assert result.player_id == 8484144
        assert result.first_name == "Connor"
        assert result.last_name == "Bedard"
        assert result.full_name == "Connor Bedard"
        assert result.sweater_number == 98
        assert result.position == "C"
        assert result.height_inches == 70
        assert result.weight_lbs == 185
        assert result.birth_date == "2005-07-17"
        assert result.birth_country == "CAN"
        assert result.shoots_catches == "R"
        assert result.team_abbrev == "CHI"
        assert result.draft_year == 2023
        assert result.draft_round == 1
        assert result.draft_pick == 1
        assert result.draft_overall == 1

    def test_parse_prospect_minimal(self) -> None:
        """Test parsing minimal prospect data."""
        player_data = {
            "id": 8484000,
            "firstName": {"default": "Test"},
            "lastName": {"default": "Player"},
        }

        result = _parse_prospect(player_data, "TOR")

        assert result.player_id == 8484000
        assert result.first_name == "Test"
        assert result.last_name == "Player"
        assert result.team_abbrev == "TOR"
        assert result.draft_year is None
        assert result.draft_overall is None

    def test_parse_prospect_undrafted(self) -> None:
        """Test parsing an undrafted prospect."""
        player_data = {
            "id": 8484001,
            "firstName": {"default": "Undrafted"},
            "lastName": {"default": "Player"},
            "positionCode": "D",
            "draftDetails": {},  # Empty draft details
        }

        result = _parse_prospect(player_data, "MTL")

        assert result.draft_year is None
        assert result.draft_round is None
        assert result.draft_pick is None
        assert result.draft_overall is None


@pytest.mark.unit
class TestParseTeamProspects:
    """Tests for _parse_team_prospects function."""

    def test_parse_team_prospects_complete(self) -> None:
        """Test parsing complete team prospects data."""
        data = {
            "forwards": [
                {
                    "id": 8484144,
                    "firstName": {"default": "Connor"},
                    "lastName": {"default": "Bedard"},
                    "positionCode": "C",
                },
                {
                    "id": 8484145,
                    "firstName": {"default": "Test"},
                    "lastName": {"default": "Forward"},
                    "positionCode": "L",
                },
            ],
            "defensemen": [
                {
                    "id": 8484146,
                    "firstName": {"default": "Test"},
                    "lastName": {"default": "Defenseman"},
                    "positionCode": "D",
                },
            ],
            "goalies": [
                {
                    "id": 8484147,
                    "firstName": {"default": "Test"},
                    "lastName": {"default": "Goalie"},
                    "positionCode": "G",
                },
            ],
        }

        result = _parse_team_prospects(data, "CHI")

        assert result.team_abbrev == "CHI"
        assert len(result.forwards) == 2
        assert len(result.defensemen) == 1
        assert len(result.goalies) == 1
        assert len(result.all_prospects) == 4

    def test_parse_team_prospects_empty(self) -> None:
        """Test parsing empty prospects data."""
        data: dict[str, Any] = {}

        result = _parse_team_prospects(data, "TOR")

        assert result.team_abbrev == "TOR"
        assert len(result.forwards) == 0
        assert len(result.defensemen) == 0
        assert len(result.goalies) == 0
        assert len(result.all_prospects) == 0


@pytest.mark.unit
class TestTeamProspectsDownloader:
    """Tests for TeamProspectsDownloader class."""

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
    ) -> TeamProspectsDownloader:
        """Create a downloader instance with mocks."""
        config = TeamProspectsDownloaderConfig()
        dl = TeamProspectsDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False  # Don't close the mock
        return dl

    def test_source_name(self, downloader: TeamProspectsDownloader) -> None:
        """Test that source_name returns correct identifier."""
        assert downloader.source_name == "nhl_json_team_prospects"

    @pytest.mark.asyncio
    async def test_get_team_prospects(
        self,
        downloader: TeamProspectsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching team prospects."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "forwards": [
                {
                    "id": 8484144,
                    "firstName": {"default": "Connor"},
                    "lastName": {"default": "Bedard"},
                    "positionCode": "C",
                }
            ],
            "defensemen": [],
            "goalies": [],
        }
        mock_http_client.get.return_value = mock_response

        result = await downloader.get_team_prospects("CHI")

        assert result.team_abbrev == "CHI"
        assert len(result.forwards) == 1
        assert result.forwards[0].first_name == "Connor"

    @pytest.mark.asyncio
    async def test_get_all_prospects(
        self,
        downloader: TeamProspectsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetching all teams' prospects."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "forwards": [
                {
                    "id": 8484144,
                    "firstName": {"default": "Test"},
                    "lastName": {"default": "Player"},
                }
            ],
            "defensemen": [],
            "goalies": [],
        }
        mock_http_client.get.return_value = mock_response

        # Limit to 2 teams for testing
        result = await downloader.get_all_prospects(teams=["TOR", "MTL"])

        assert len(result) == 2
        assert "TOR" in result
        assert "MTL" in result


@pytest.mark.unit
class TestFactoryFunction:
    """Tests for create_team_prospects_downloader factory."""

    def test_create_with_defaults(self) -> None:
        """Test factory with default parameters."""
        downloader = create_team_prospects_downloader()

        assert isinstance(downloader, TeamProspectsDownloader)
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_params(self) -> None:
        """Test factory with custom parameters."""
        downloader = create_team_prospects_downloader(
            requests_per_second=2.0,
            max_retries=5,
        )

        assert downloader.config.requests_per_second == 2.0
        assert downloader.config.max_retries == 5
