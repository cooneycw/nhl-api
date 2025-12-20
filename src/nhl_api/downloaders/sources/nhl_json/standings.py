"""NHL Standings Downloader.

Downloads league standings from the NHL JSON API (api-web.nhle.com/v1/).
Provides methods to fetch current standings, historical standings by date,
and available seasons for standings data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import DownloadError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com/v1"


@dataclass(frozen=True, slots=True)
class StreakInfo:
    """Streak information for a team."""

    code: str  # W, L, OT
    count: int


@dataclass(frozen=True, slots=True)
class RecordSplit:
    """Win-loss record for a specific context (home, road, L10)."""

    wins: int
    losses: int
    ot_losses: int
    points: int
    goals_for: int
    goals_against: int


@dataclass(frozen=True, slots=True)
class TeamStandings:
    """Complete standings entry for a single team.

    Contains all record, ranking, and trend information.
    """

    # Team identification
    team_abbrev: str
    team_name: str
    team_common_name: str
    team_logo_url: str | None

    # Division/Conference
    conference_abbrev: str
    conference_name: str
    division_abbrev: str
    division_name: str

    # Season
    season_id: int

    # Core record
    games_played: int
    wins: int
    losses: int
    ot_losses: int
    points: int
    point_pctg: float

    # Goals
    goals_for: int
    goals_against: int
    goal_differential: int

    # Win types
    regulation_wins: int
    regulation_plus_ot_wins: int
    shootout_wins: int
    shootout_losses: int

    # Rankings
    league_sequence: int
    conference_sequence: int
    division_sequence: int
    wildcard_sequence: int

    # Streak
    streak: StreakInfo | None

    # Splits
    home_record: RecordSplit | None
    road_record: RecordSplit | None
    last_10_record: RecordSplit | None

    # Playoff status
    clinch_indicator: str | None  # x=playoff, y=division, z=presidents, e=eliminated


@dataclass(frozen=True, slots=True)
class ParsedStandings:
    """Complete standings snapshot.

    Contains standings for all teams at a point in time.
    """

    standings_date: date
    season_id: int
    standings: tuple[TeamStandings, ...]

    @property
    def team_count(self) -> int:
        """Return number of teams in standings."""
        return len(self.standings)

    def get_by_conference(self, conference: str) -> tuple[TeamStandings, ...]:
        """Get teams by conference abbreviation."""
        return tuple(t for t in self.standings if t.conference_abbrev == conference)

    def get_by_division(self, division: str) -> tuple[TeamStandings, ...]:
        """Get teams by division abbreviation."""
        return tuple(t for t in self.standings if t.division_abbrev == division)

    def get_team(self, team_abbrev: str) -> TeamStandings | None:
        """Get standings for a specific team."""
        for team in self.standings:
            if team.team_abbrev == team_abbrev:
                return team
        return None


def _parse_record_split(data: dict[str, Any] | None) -> RecordSplit | None:
    """Parse a home/road/L10 record split.

    Args:
        data: Raw split data from API

    Returns:
        Parsed RecordSplit or None if no data
    """
    if not data:
        return None

    return RecordSplit(
        wins=data.get("wins", 0),
        losses=data.get("losses", 0),
        ot_losses=data.get("otLosses", 0),
        points=data.get("points", 0),
        goals_for=data.get("goalFor", 0),
        goals_against=data.get("goalAgainst", 0),
    )


def _parse_streak(data: dict[str, Any]) -> StreakInfo | None:
    """Parse streak information.

    Args:
        data: Team data containing streak info

    Returns:
        Parsed StreakInfo or None
    """
    streak_code = data.get("streakCode")
    streak_count = data.get("streakCount")

    if streak_code and streak_count is not None:
        return StreakInfo(code=streak_code, count=streak_count)
    return None


def _parse_team_standings(data: dict[str, Any]) -> TeamStandings:
    """Parse standings for a single team.

    Args:
        data: Raw team standings data from API

    Returns:
        Parsed TeamStandings object
    """
    # Parse team name - handle localized name format
    team_name_obj = data.get("teamName", {})
    if isinstance(team_name_obj, dict):
        team_name = team_name_obj.get("default", "")
    else:
        team_name = str(team_name_obj) if team_name_obj else ""

    team_common_name_obj = data.get("teamCommonName", {})
    if isinstance(team_common_name_obj, dict):
        team_common_name = team_common_name_obj.get("default", "")
    else:
        team_common_name = str(team_common_name_obj) if team_common_name_obj else ""

    return TeamStandings(
        team_abbrev=data.get("teamAbbrev", {}).get("default", ""),
        team_name=team_name,
        team_common_name=team_common_name,
        team_logo_url=data.get("teamLogo"),
        conference_abbrev=data.get("conferenceAbbrev", ""),
        conference_name=data.get("conferenceName", ""),
        division_abbrev=data.get("divisionAbbrev", ""),
        division_name=data.get("divisionName", ""),
        season_id=data.get("seasonId", 0),
        games_played=data.get("gamesPlayed", 0),
        wins=data.get("wins", 0),
        losses=data.get("losses", 0),
        ot_losses=data.get("otLosses", 0),
        points=data.get("points", 0),
        point_pctg=data.get("pointPctg", 0.0),
        goals_for=data.get("goalFor", 0),
        goals_against=data.get("goalAgainst", 0),
        goal_differential=data.get("goalDifferential", 0),
        regulation_wins=data.get("regulationWins", 0),
        regulation_plus_ot_wins=data.get("regulationPlusOtWins", 0),
        shootout_wins=data.get("shootoutWins", 0),
        shootout_losses=data.get("shootoutLosses", 0),
        league_sequence=data.get("leagueSequence", 0),
        conference_sequence=data.get("conferenceSequence", 0),
        division_sequence=data.get("divisionSequence", 0),
        wildcard_sequence=data.get("wildcardSequence", 0),
        streak=_parse_streak(data),
        home_record=_parse_record_split(data.get("homeRecord")),
        road_record=_parse_record_split(data.get("roadRecord")),
        last_10_record=_parse_record_split(data.get("l10Record")),
        clinch_indicator=data.get("clinchIndicator"),
    )


def _parse_standings(data: dict[str, Any], standings_date: date) -> ParsedStandings:
    """Parse complete standings response.

    Args:
        data: Raw standings data from API
        standings_date: Date of the standings

    Returns:
        Parsed standings object
    """
    standings_list = data.get("standings", [])
    teams = tuple(_parse_team_standings(team) for team in standings_list)

    # Get season ID from first team if available
    season_id = teams[0].season_id if teams else 0

    return ParsedStandings(
        standings_date=standings_date,
        season_id=season_id,
        standings=teams,
    )


class StandingsDownloader(BaseDownloader):
    """Downloads NHL league standings.

    Supports multiple access patterns:
    - Current standings: get_current_standings()
    - Historical standings: get_standings_for_date()
    - Available seasons: get_available_seasons()

    Example:
        config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        async with StandingsDownloader(config) as downloader:
            # Get current standings
            standings = await downloader.get_current_standings()

            # Get historical standings
            standings = await downloader.get_standings_for_date(
                date(2024, 12, 1)
            )

            # Access team data
            bruins = standings.get_team("BOS")
            eastern = standings.get_by_conference("E")
    """

    @property
    def source_name(self) -> str:
        """Return unique identifier for this source."""
        return "nhl_json_standings"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Not used for standings downloads.

        Standings downloads are date-based, not game-based.
        """
        return {"_note": "Standings downloads are date-based, not game-based"}

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Not used for standings downloads.

        Use get_current_standings() or get_standings_for_date() instead.

        Args:
            season_id: NHL season ID (not used)

        Yields:
            Nothing - this method is not applicable for standings
        """
        return
        yield  # Make this a generator (never reached)

    async def get_current_standings(self) -> ParsedStandings:
        """Get current league standings.

        Returns:
            ParsedStandings with all teams' current standings

        Raises:
            DownloadError: If standings cannot be fetched
        """
        logger.debug("Fetching current standings")

        response = await self._get("standings/now")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch current standings: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        standings = _parse_standings(data, date.today())

        logger.info(
            "Fetched standings for %d teams (season %d)",
            standings.team_count,
            standings.season_id,
        )

        return standings

    async def get_standings_for_date(self, standings_date: date) -> ParsedStandings:
        """Get standings for a specific date.

        Args:
            standings_date: Date to fetch standings for

        Returns:
            ParsedStandings for the specified date

        Raises:
            DownloadError: If standings cannot be fetched
        """
        date_str = standings_date.isoformat()
        logger.debug("Fetching standings for %s", date_str)

        response = await self._get(f"standings/{date_str}")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch standings for {date_str}: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        standings = _parse_standings(data, standings_date)

        logger.info(
            "Fetched standings for %d teams on %s",
            standings.team_count,
            date_str,
        )

        return standings

    async def get_available_seasons(self) -> list[dict[str, Any]]:
        """Get information about all seasons with standings data.

        Returns detailed season information including:
        - Season ID
        - Whether conferences/divisions were used
        - Scoring rules (OT loss points, ties, etc.)
        - Date ranges for standings

        Returns:
            List of season info dictionaries

        Raises:
            DownloadError: If seasons cannot be fetched
        """
        logger.debug("Fetching available standings seasons")

        response = await self._get("standings-season")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch standings seasons: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        seasons: list[dict[str, Any]] = data.get("seasons", [])

        logger.info("Found %d seasons with standings data", len(seasons))

        return seasons

    async def get_standings_range(
        self,
        start_date: date,
        end_date: date,
        interval_days: int = 7,
    ) -> list[ParsedStandings]:
        """Get standings snapshots over a date range.

        Useful for tracking standings progression over time.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            interval_days: Days between snapshots (default 7 for weekly)

        Returns:
            List of standings snapshots

        Raises:
            DownloadError: If any standings fetch fails
        """
        from datetime import timedelta

        logger.info(
            "Fetching standings from %s to %s (every %d days)",
            start_date,
            end_date,
            interval_days,
        )

        snapshots: list[ParsedStandings] = []
        current_date = start_date

        while current_date <= end_date:
            try:
                standings = await self.get_standings_for_date(current_date)
                snapshots.append(standings)
            except DownloadError as e:
                logger.warning("No standings for %s: %s", current_date, e)

            current_date += timedelta(days=interval_days)

        logger.info("Retrieved %d standings snapshots", len(snapshots))

        return snapshots


def create_standings_downloader(
    *,
    requests_per_second: float = 5.0,
    max_retries: int = 3,
) -> StandingsDownloader:
    """Factory function to create a configured StandingsDownloader.

    Args:
        requests_per_second: Rate limit for API calls
        max_retries: Maximum retry attempts

    Returns:
        Configured StandingsDownloader instance
    """
    config = DownloaderConfig(
        base_url=NHL_API_BASE_URL,
        requests_per_second=requests_per_second,
        max_retries=max_retries,
        health_check_url="standings/now",
    )
    return StandingsDownloader(config)
