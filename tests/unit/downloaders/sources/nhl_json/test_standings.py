"""Tests for Standings Downloader."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.base.base_downloader import DownloaderConfig
from nhl_api.downloaders.base.protocol import DownloadError
from nhl_api.downloaders.sources.nhl_json.standings import (
    ParsedStandings,
    RecordSplit,
    StandingsDownloader,
    StreakInfo,
    _format_record_split,
    _parse_record_split,
    _parse_standings,
    _parse_streak,
    _parse_team_standings,
    create_standings_downloader,
)

# Sample team standings data for testing
SAMPLE_TEAM_STANDINGS = {
    "teamAbbrev": {"default": "BOS"},
    "teamName": {"default": "Boston Bruins"},
    "teamCommonName": {"default": "Bruins"},
    "teamLogo": "https://assets.nhle.com/logos/nhl/svg/BOS_light.svg",
    "conferenceAbbrev": "E",
    "conferenceName": "Eastern",
    "divisionAbbrev": "A",
    "divisionName": "Atlantic",
    "seasonId": 20242025,
    "gamesPlayed": 35,
    "wins": 22,
    "losses": 10,
    "otLosses": 3,
    "points": 47,
    "pointPctg": 0.671,
    "goalFor": 105,
    "goalAgainst": 78,
    "goalDifferential": 27,
    "regulationWins": 18,
    "regulationPlusOtWins": 20,
    "shootoutWins": 2,
    "shootoutLosses": 1,
    "leagueSequence": 5,
    "conferenceSequence": 3,
    "divisionSequence": 2,
    "wildcardSequence": 0,
    "streakCode": "W",
    "streakCount": 3,
    "homeRecord": {
        "wins": 12,
        "losses": 4,
        "otLosses": 1,
        "points": 25,
        "goalFor": 55,
        "goalAgainst": 35,
    },
    "roadRecord": {
        "wins": 10,
        "losses": 6,
        "otLosses": 2,
        "points": 22,
        "goalFor": 50,
        "goalAgainst": 43,
    },
    "l10Record": {
        "wins": 7,
        "losses": 2,
        "otLosses": 1,
        "points": 15,
        "goalFor": 28,
        "goalAgainst": 18,
    },
}

SAMPLE_STANDINGS_RESPONSE = {
    "standings": [SAMPLE_TEAM_STANDINGS],
}


@pytest.mark.unit
class TestStreakInfo:
    """Tests for StreakInfo dataclass."""

    def test_streak_info_creation(self) -> None:
        """Test creating StreakInfo."""
        streak = StreakInfo(code="W", count=3)
        assert streak.code == "W"
        assert streak.count == 3

    def test_streak_info_is_frozen(self) -> None:
        """Test that StreakInfo is immutable."""
        streak = StreakInfo(code="L", count=2)
        with pytest.raises(AttributeError):
            streak.code = "W"  # type: ignore[misc]


@pytest.mark.unit
class TestRecordSplit:
    """Tests for RecordSplit dataclass."""

    def test_record_split_creation(self) -> None:
        """Test creating RecordSplit."""
        split = RecordSplit(
            wins=10,
            losses=5,
            ot_losses=2,
            points=22,
            goals_for=50,
            goals_against=40,
        )
        assert split.wins == 10
        assert split.losses == 5
        assert split.ot_losses == 2
        assert split.points == 22

    def test_record_split_is_frozen(self) -> None:
        """Test that RecordSplit is immutable."""
        split = RecordSplit(
            wins=10, losses=5, ot_losses=2, points=22, goals_for=50, goals_against=40
        )
        with pytest.raises(AttributeError):
            split.wins = 20  # type: ignore[misc]


@pytest.mark.unit
class TestParseRecordSplit:
    """Tests for _parse_record_split function."""

    def test_parse_valid_record(self) -> None:
        """Test parsing valid record split data."""
        data = {
            "wins": 12,
            "losses": 4,
            "otLosses": 1,
            "points": 25,
            "goalFor": 55,
            "goalAgainst": 35,
        }
        result = _parse_record_split(data)

        assert result is not None
        assert result.wins == 12
        assert result.losses == 4
        assert result.ot_losses == 1
        assert result.points == 25
        assert result.goals_for == 55
        assert result.goals_against == 35

    def test_parse_none_returns_none(self) -> None:
        """Test that None returns None."""
        assert _parse_record_split(None) is None

    def test_parse_empty_dict_returns_none(self) -> None:
        """Test parsing empty dict returns None (empty dict is falsy)."""
        # Empty dict is falsy in Python, so `if not data:` returns True
        assert _parse_record_split({}) is None


@pytest.mark.unit
class TestParseStreak:
    """Tests for _parse_streak function."""

    def test_parse_valid_streak(self) -> None:
        """Test parsing valid streak data."""
        data = {"streakCode": "W", "streakCount": 3}
        result = _parse_streak(data)

        assert result is not None
        assert result.code == "W"
        assert result.count == 3

    def test_parse_missing_streak_code(self) -> None:
        """Test parsing with missing streak code."""
        data = {"streakCount": 3}
        assert _parse_streak(data) is None

    def test_parse_missing_streak_count(self) -> None:
        """Test parsing with missing streak count."""
        data = {"streakCode": "W"}
        assert _parse_streak(data) is None

    def test_parse_losing_streak(self) -> None:
        """Test parsing losing streak."""
        data = {"streakCode": "L", "streakCount": 2}
        result = _parse_streak(data)

        assert result is not None
        assert result.code == "L"
        assert result.count == 2


@pytest.mark.unit
class TestParseTeamStandings:
    """Tests for _parse_team_standings function."""

    def test_parse_complete_standings(self) -> None:
        """Test parsing complete team standings."""
        result = _parse_team_standings(SAMPLE_TEAM_STANDINGS)

        assert result.team_abbrev == "BOS"
        assert result.team_name == "Boston Bruins"
        assert result.team_common_name == "Bruins"
        assert result.conference_abbrev == "E"
        assert result.division_abbrev == "A"
        assert result.season_id == 20242025
        assert result.games_played == 35
        assert result.wins == 22
        assert result.losses == 10
        assert result.ot_losses == 3
        assert result.points == 47
        assert result.goal_differential == 27
        assert result.league_sequence == 5
        assert result.streak is not None
        assert result.streak.code == "W"
        assert result.streak.count == 3
        assert result.home_record is not None
        assert result.road_record is not None
        assert result.last_10_record is not None

    def test_parse_minimal_standings(self) -> None:
        """Test parsing minimal standings data."""
        data: dict[str, Any] = {
            "teamAbbrev": {"default": "NYR"},
        }
        result = _parse_team_standings(data)

        assert result.team_abbrev == "NYR"
        assert result.team_name == ""
        assert result.wins == 0
        assert result.points == 0
        assert result.streak is None
        assert result.home_record is None

    def test_parse_string_team_name(self) -> None:
        """Test parsing when team name is a string (not dict)."""
        data = {
            "teamAbbrev": {"default": "MTL"},
            "teamName": "Montreal Canadiens",
            "teamCommonName": "Canadiens",
        }
        result = _parse_team_standings(data)

        assert result.team_name == "Montreal Canadiens"
        assert result.team_common_name == "Canadiens"


@pytest.mark.unit
class TestParseStandings:
    """Tests for _parse_standings function."""

    def test_parse_complete_standings(self) -> None:
        """Test parsing complete standings response."""
        result = _parse_standings(SAMPLE_STANDINGS_RESPONSE, date(2024, 12, 20))

        assert result.standings_date == date(2024, 12, 20)
        assert result.season_id == 20242025
        assert result.team_count == 1
        assert result.standings[0].team_abbrev == "BOS"

    def test_parse_empty_standings(self) -> None:
        """Test parsing empty standings response."""
        result = _parse_standings({"standings": []}, date(2024, 12, 20))

        assert result.team_count == 0
        assert result.season_id == 0


@pytest.mark.unit
class TestParsedStandings:
    """Tests for ParsedStandings dataclass."""

    @pytest.fixture
    def sample_standings(self) -> ParsedStandings:
        """Create sample standings for testing."""
        return _parse_standings(SAMPLE_STANDINGS_RESPONSE, date(2024, 12, 20))

    def test_get_team_found(self, sample_standings: ParsedStandings) -> None:
        """Test getting team by abbreviation."""
        team = sample_standings.get_team("BOS")
        assert team is not None
        assert team.team_abbrev == "BOS"

    def test_get_team_not_found(self, sample_standings: ParsedStandings) -> None:
        """Test getting non-existent team."""
        team = sample_standings.get_team("XXX")
        assert team is None

    def test_get_by_conference(self, sample_standings: ParsedStandings) -> None:
        """Test getting teams by conference."""
        eastern = sample_standings.get_by_conference("E")
        assert len(eastern) == 1
        assert eastern[0].team_abbrev == "BOS"

    def test_get_by_division(self, sample_standings: ParsedStandings) -> None:
        """Test getting teams by division."""
        atlantic = sample_standings.get_by_division("A")
        assert len(atlantic) == 1
        assert atlantic[0].team_abbrev == "BOS"


@pytest.mark.unit
class TestTeamStandings:
    """Tests for TeamStandings dataclass."""

    def test_team_standings_is_frozen(self) -> None:
        """Test that TeamStandings is immutable."""
        standings = _parse_team_standings(SAMPLE_TEAM_STANDINGS)

        with pytest.raises(AttributeError):
            standings.wins = 50  # type: ignore[misc]


@pytest.mark.unit
class TestStandingsDownloader:
    """Tests for StandingsDownloader class."""

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
    def config(self) -> DownloaderConfig:
        """Create a test configuration."""
        return DownloaderConfig(
            base_url="https://api-web.nhle.com/v1",
            requests_per_second=10.0,
        )

    @pytest.fixture
    def downloader(
        self,
        config: DownloaderConfig,
        mock_http_client: MagicMock,
        mock_rate_limiter: MagicMock,
    ) -> StandingsDownloader:
        """Create a StandingsDownloader with mock HTTP client."""
        dl = StandingsDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False
        return dl

    def test_source_name(self, downloader: StandingsDownloader) -> None:
        """Test that source_name returns correct identifier."""
        assert downloader.source_name == "nhl_json_standings"

    @pytest.mark.asyncio
    async def test_get_current_standings_success(
        self,
        downloader: StandingsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful current standings download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = SAMPLE_STANDINGS_RESPONSE

        mock_http_client.get = AsyncMock(return_value=mock_response)

        standings = await downloader.get_current_standings()

        assert standings.team_count == 1
        assert standings.standings[0].team_abbrev == "BOS"
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_standings_failure(
        self,
        downloader: StandingsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of failed standings download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 500

        mock_http_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadError) as exc_info:
            await downloader.get_current_standings()

        assert "Failed to fetch current standings" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_standings_for_date_success(
        self,
        downloader: StandingsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful historical standings download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = SAMPLE_STANDINGS_RESPONSE

        mock_http_client.get = AsyncMock(return_value=mock_response)

        standings_date = date(2024, 12, 1)
        standings = await downloader.get_standings_for_date(standings_date)

        assert standings.standings_date == standings_date
        assert standings.team_count == 1

    @pytest.mark.asyncio
    async def test_get_standings_for_date_failure(
        self,
        downloader: StandingsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of failed historical standings download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 404

        mock_http_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadError) as exc_info:
            await downloader.get_standings_for_date(date(2000, 1, 1))

        assert "Failed to fetch standings" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_available_seasons_success(
        self,
        downloader: StandingsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful seasons list download."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = {
            "seasons": [
                {"seasonId": 20242025},
                {"seasonId": 20232024},
            ]
        }

        mock_http_client.get = AsyncMock(return_value=mock_response)

        seasons = await downloader.get_available_seasons()

        assert len(seasons) == 2

    @pytest.mark.asyncio
    async def test_get_available_seasons_failure(
        self,
        downloader: StandingsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of failed seasons download."""
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 500

        mock_http_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadError) as exc_info:
            await downloader.get_available_seasons()

        assert "Failed to fetch standings seasons" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_standings_range_success(
        self,
        downloader: StandingsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test downloading standings over a date range."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_response.status = 200
        mock_response.retry_after = None
        mock_response.json.return_value = SAMPLE_STANDINGS_RESPONSE

        mock_http_client.get = AsyncMock(return_value=mock_response)

        start = date(2024, 12, 1)
        end = date(2024, 12, 15)
        snapshots = await downloader.get_standings_range(start, end, interval_days=7)

        # Should have 3 snapshots: Dec 1, Dec 8, Dec 15
        assert len(snapshots) == 3

    @pytest.mark.asyncio
    async def test_get_standings_range_partial_failure(
        self,
        downloader: StandingsDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test that range download continues on individual failures."""
        success_response = MagicMock()
        success_response.is_success = True
        success_response.is_rate_limited = False
        success_response.is_server_error = False
        success_response.status = 200
        success_response.retry_after = None
        success_response.json.return_value = SAMPLE_STANDINGS_RESPONSE

        fail_response = MagicMock()
        fail_response.is_success = False
        fail_response.is_rate_limited = False
        fail_response.is_server_error = False
        fail_response.status = 404

        # First fails, second succeeds
        mock_http_client.get = AsyncMock(side_effect=[fail_response, success_response])

        start = date(2024, 12, 1)
        end = date(2024, 12, 8)
        snapshots = await downloader.get_standings_range(start, end, interval_days=7)

        # Should only have 1 snapshot (second one succeeded)
        assert len(snapshots) == 1

    @pytest.mark.asyncio
    async def test_fetch_game_not_applicable(
        self, downloader: StandingsDownloader
    ) -> None:
        """Test that _fetch_game returns placeholder."""
        result = await downloader._fetch_game(12345)

        assert "_note" in result
        assert "date-based" in result["_note"]


@pytest.mark.unit
class TestCreateStandingsDownloader:
    """Tests for create_standings_downloader factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating downloader with default parameters."""
        downloader = create_standings_downloader()

        assert downloader.source_name == "nhl_json_standings"
        assert downloader.config.base_url == "https://api-web.nhle.com/v1"
        assert downloader.config.requests_per_second == 5.0
        assert downloader.config.max_retries == 3

    def test_create_with_custom_params(self) -> None:
        """Test creating downloader with custom parameters."""
        downloader = create_standings_downloader(
            requests_per_second=10.0,
            max_retries=5,
        )

        assert downloader.config.requests_per_second == 10.0
        assert downloader.config.max_retries == 5

    def test_health_check_url_set(self) -> None:
        """Test that health check URL is configured."""
        downloader = create_standings_downloader()

        assert downloader.config.health_check_url == "standings/now"


@pytest.mark.unit
class TestFormatRecordSplit:
    """Tests for _format_record_split helper function."""

    def test_format_valid_record(self) -> None:
        """Test formatting a valid record split."""
        record = RecordSplit(
            wins=15, losses=5, ot_losses=2, points=32, goals_for=80, goals_against=60
        )
        result = _format_record_split(record)
        assert result == "15-5-2"

    def test_format_none_returns_none(self) -> None:
        """Test that None returns None."""
        assert _format_record_split(None) is None

    def test_format_zero_record(self) -> None:
        """Test formatting a zero record."""
        record = RecordSplit(
            wins=0, losses=0, ot_losses=0, points=0, goals_for=0, goals_against=0
        )
        result = _format_record_split(record)
        assert result == "0-0-0"


@pytest.mark.unit
class TestStandingsDownloaderPersist:
    """Tests for StandingsDownloader.persist() method."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create a mock database service."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

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
    def config(self) -> DownloaderConfig:
        """Create a test configuration."""
        return DownloaderConfig(
            base_url="https://api-web.nhle.com/v1",
            requests_per_second=10.0,
        )

    @pytest.fixture
    def downloader(
        self,
        config: DownloaderConfig,
        mock_http_client: MagicMock,
        mock_rate_limiter: MagicMock,
    ) -> StandingsDownloader:
        """Create a StandingsDownloader with mock HTTP client."""
        dl = StandingsDownloader(
            config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
        )
        dl._owns_http_client = False
        return dl

    @pytest.fixture
    def sample_standings(self) -> ParsedStandings:
        """Create sample standings for testing."""
        return _parse_standings(SAMPLE_STANDINGS_RESPONSE, date(2024, 12, 20))

    @pytest.mark.asyncio
    async def test_persist_empty_standings(
        self,
        downloader: StandingsDownloader,
        mock_db: AsyncMock,
    ) -> None:
        """Test persisting empty standings returns 0."""
        empty_standings = ParsedStandings(
            standings_date=date(2024, 12, 20),
            season_id=20242025,
            standings=(),
        )
        result = await downloader.persist(mock_db, empty_standings)
        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_single_team(
        self,
        downloader: StandingsDownloader,
        mock_db: AsyncMock,
        sample_standings: ParsedStandings,
    ) -> None:
        """Test persisting standings with one team."""
        result = await downloader.persist(mock_db, sample_standings)

        assert result == 1
        mock_db.execute.assert_called_once()

        # Verify the SQL call has correct team abbreviation
        call_args = mock_db.execute.call_args
        assert call_args[0][1] == "BOS"  # team_abbrev
        assert call_args[0][2] == 20242025  # season_id
        assert call_args[0][3] == date(2024, 12, 20)  # snapshot_date

    @pytest.mark.asyncio
    async def test_persist_multiple_teams(
        self,
        downloader: StandingsDownloader,
        mock_db: AsyncMock,
    ) -> None:
        """Test persisting standings with multiple teams."""
        # Create standings with 2 teams
        team2_data = SAMPLE_TEAM_STANDINGS.copy()
        team2_data["teamAbbrev"] = {"default": "NYR"}
        team2_data["teamName"] = {"default": "New York Rangers"}

        multi_team_response = {"standings": [SAMPLE_TEAM_STANDINGS, team2_data]}
        standings = _parse_standings(multi_team_response, date(2024, 12, 20))

        result = await downloader.persist(mock_db, standings)

        assert result == 2
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_persist_record_splits_formatted(
        self,
        downloader: StandingsDownloader,
        mock_db: AsyncMock,
        sample_standings: ParsedStandings,
    ) -> None:
        """Test that record splits are formatted correctly."""
        await downloader.persist(mock_db, sample_standings)

        call_args = mock_db.execute.call_args
        # home_record is parameter 27, road_record is 28, last_10 is 29
        assert call_args[0][27] == "12-4-1"  # home_record
        assert call_args[0][28] == "10-6-2"  # road_record
        assert call_args[0][29] == "7-2-1"  # last_10_record

    @pytest.mark.asyncio
    async def test_persist_streak_info(
        self,
        downloader: StandingsDownloader,
        mock_db: AsyncMock,
        sample_standings: ParsedStandings,
    ) -> None:
        """Test that streak info is extracted correctly."""
        await downloader.persist(mock_db, sample_standings)

        call_args = mock_db.execute.call_args
        # streak_code is parameter 25, streak_count is 26
        assert call_args[0][25] == "W"  # streak_code
        assert call_args[0][26] == 3  # streak_count

    @pytest.mark.asyncio
    async def test_persist_no_streak(
        self,
        downloader: StandingsDownloader,
        mock_db: AsyncMock,
    ) -> None:
        """Test persisting standings with no streak info."""
        # Create standings without streak
        no_streak_data = SAMPLE_TEAM_STANDINGS.copy()
        del no_streak_data["streakCode"]
        del no_streak_data["streakCount"]

        standings = _parse_standings(
            {"standings": [no_streak_data]}, date(2024, 12, 20)
        )
        await downloader.persist(mock_db, standings)

        call_args = mock_db.execute.call_args
        assert call_args[0][25] is None  # streak_code
        assert call_args[0][26] is None  # streak_count

    @pytest.mark.asyncio
    async def test_persist_no_record_splits(
        self,
        downloader: StandingsDownloader,
        mock_db: AsyncMock,
    ) -> None:
        """Test persisting standings without record splits."""
        # Create standings without record splits
        no_splits_data = SAMPLE_TEAM_STANDINGS.copy()
        del no_splits_data["homeRecord"]
        del no_splits_data["roadRecord"]
        del no_splits_data["l10Record"]

        standings = _parse_standings(
            {"standings": [no_splits_data]}, date(2024, 12, 20)
        )
        await downloader.persist(mock_db, standings)

        call_args = mock_db.execute.call_args
        assert call_args[0][27] is None  # home_record
        assert call_args[0][28] is None  # road_record
        assert call_args[0][29] is None  # last_10_record

    @pytest.mark.asyncio
    async def test_persist_all_fields_mapped(
        self,
        downloader: StandingsDownloader,
        mock_db: AsyncMock,
        sample_standings: ParsedStandings,
    ) -> None:
        """Test that all key fields are persisted correctly."""
        await downloader.persist(mock_db, sample_standings)

        call_args = mock_db.execute.call_args
        # Verify key fields
        assert call_args[0][1] == "BOS"  # team_abbrev
        assert call_args[0][4] == "E"  # conference_abbrev
        assert call_args[0][5] == "Eastern"  # conference_name
        assert call_args[0][6] == "A"  # division_abbrev
        assert call_args[0][7] == "Atlantic"  # division_name
        assert call_args[0][8] == 35  # games_played
        assert call_args[0][9] == 22  # wins
        assert call_args[0][10] == 10  # losses
        assert call_args[0][11] == 3  # ot_losses
        assert call_args[0][12] == 47  # points
        assert call_args[0][14] == 105  # goals_for
        assert call_args[0][15] == 78  # goals_against
        assert call_args[0][16] == 27  # goal_differential
