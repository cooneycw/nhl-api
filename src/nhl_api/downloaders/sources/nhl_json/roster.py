"""NHL Roster Downloader.

Downloads team rosters from the NHL JSON API (api-web.nhle.com/v1/).
Provides methods to fetch current rosters, historical rosters by season,
and available seasons for each team.
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
    from collections.abc import AsyncGenerator, Sequence

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com/v1"


@dataclass(frozen=True, slots=True)
class PlayerInfo:
    """Parsed player information from roster response.

    Contains all biographical and roster information for a player.
    """

    player_id: int
    first_name: str
    last_name: str
    sweater_number: int | None
    position_code: str  # L, R, C, D, G
    shoots_catches: str  # L or R
    height_inches: int
    weight_pounds: int
    height_cm: int
    weight_kg: int
    birth_date: date | None
    birth_city: str | None
    birth_country: str | None
    birth_state_province: str | None
    headshot_url: str | None
    team_abbrev: str  # Team this player is on


@dataclass(frozen=True, slots=True)
class ParsedRoster:
    """Complete roster for a team.

    Contains lists of forwards, defensemen, and goalies.
    """

    team_abbrev: str
    season_id: int | None  # None for current roster
    forwards: tuple[PlayerInfo, ...]
    defensemen: tuple[PlayerInfo, ...]
    goalies: tuple[PlayerInfo, ...]

    @property
    def all_players(self) -> tuple[PlayerInfo, ...]:
        """Return all players on the roster."""
        return self.forwards + self.defensemen + self.goalies

    @property
    def player_count(self) -> int:
        """Return total number of players on roster."""
        return len(self.forwards) + len(self.defensemen) + len(self.goalies)


def _parse_localized_name(name_obj: dict[str, Any] | None) -> str:
    """Parse a localized name object, returning the default value.

    Args:
        name_obj: Object with 'default' and potentially other locale keys

    Returns:
        The default name or empty string if not available
    """
    if not name_obj:
        return ""
    result = name_obj.get("default", "")
    return str(result) if result else ""


def _parse_birth_date(date_str: str | None) -> date | None:
    """Parse a birth date string to date object.

    Args:
        date_str: ISO format date string (YYYY-MM-DD)

    Returns:
        Parsed date or None if parsing fails
    """
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        logger.warning("Failed to parse birth date: %s", date_str)
        return None


def _parse_player(player_data: dict[str, Any], team_abbrev: str) -> PlayerInfo:
    """Parse a single player from the roster response.

    Args:
        player_data: Raw player data from API
        team_abbrev: Team abbreviation for this roster

    Returns:
        Parsed PlayerInfo object
    """
    return PlayerInfo(
        player_id=player_data["id"],
        first_name=_parse_localized_name(player_data.get("firstName")),
        last_name=_parse_localized_name(player_data.get("lastName")),
        sweater_number=player_data.get("sweaterNumber"),
        position_code=player_data.get("positionCode", ""),
        shoots_catches=player_data.get("shootsCatches", ""),
        height_inches=player_data.get("heightInInches", 0),
        weight_pounds=player_data.get("weightInPounds", 0),
        height_cm=player_data.get("heightInCentimeters", 0),
        weight_kg=player_data.get("weightInKilograms", 0),
        birth_date=_parse_birth_date(player_data.get("birthDate")),
        birth_city=_parse_localized_name(player_data.get("birthCity")),
        birth_country=player_data.get("birthCountry"),
        birth_state_province=_parse_localized_name(
            player_data.get("birthStateProvince")
        ),
        headshot_url=player_data.get("headshot"),
        team_abbrev=team_abbrev,
    )


def _parse_roster(
    data: dict[str, Any], team_abbrev: str, season_id: int | None = None
) -> ParsedRoster:
    """Parse a complete roster response.

    Args:
        data: Raw roster data from API
        team_abbrev: Team abbreviation
        season_id: Season ID if historical roster, None for current

    Returns:
        Parsed roster object
    """
    forwards = tuple(_parse_player(p, team_abbrev) for p in data.get("forwards", []))
    defensemen = tuple(
        _parse_player(p, team_abbrev) for p in data.get("defensemen", [])
    )
    goalies = tuple(_parse_player(p, team_abbrev) for p in data.get("goalies", []))

    return ParsedRoster(
        team_abbrev=team_abbrev,
        season_id=season_id,
        forwards=forwards,
        defensemen=defensemen,
        goalies=goalies,
    )


# All 32 NHL team abbreviations
NHL_TEAM_ABBREVS: tuple[str, ...] = (
    "ANA",  # Anaheim Ducks
    "ARI",  # Arizona Coyotes (relocated to UTA 2024)
    "BOS",  # Boston Bruins
    "BUF",  # Buffalo Sabres
    "CAR",  # Carolina Hurricanes
    "CBJ",  # Columbus Blue Jackets
    "CGY",  # Calgary Flames
    "CHI",  # Chicago Blackhawks
    "COL",  # Colorado Avalanche
    "DAL",  # Dallas Stars
    "DET",  # Detroit Red Wings
    "EDM",  # Edmonton Oilers
    "FLA",  # Florida Panthers
    "LAK",  # Los Angeles Kings
    "MIN",  # Minnesota Wild
    "MTL",  # Montreal Canadiens
    "NJD",  # New Jersey Devils
    "NSH",  # Nashville Predators
    "NYI",  # New York Islanders
    "NYR",  # New York Rangers
    "OTT",  # Ottawa Senators
    "PHI",  # Philadelphia Flyers
    "PIT",  # Pittsburgh Penguins
    "SEA",  # Seattle Kraken
    "SJS",  # San Jose Sharks
    "STL",  # St. Louis Blues
    "TBL",  # Tampa Bay Lightning
    "TOR",  # Toronto Maple Leafs
    "UTA",  # Utah Hockey Club (formerly ARI)
    "VAN",  # Vancouver Canucks
    "VGK",  # Vegas Golden Knights
    "WPG",  # Winnipeg Jets
    "WSH",  # Washington Capitals
)


class RosterDownloader(BaseDownloader):
    """Downloads NHL team rosters.

    Supports multiple access patterns:
    - Current roster: get_current_roster()
    - Historical roster: get_roster_for_season()
    - All teams: download_all_current_rosters()
    - Available seasons: get_available_seasons()

    Example:
        config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        async with RosterDownloader(config) as downloader:
            # Get current Boston roster
            roster = await downloader.get_current_roster("BOS")

            # Get historical roster
            roster = await downloader.get_roster_for_season("BOS", 20232024)

            # Download all current rosters
            async for roster in downloader.download_all_current_rosters():
                print(f"{roster.team_abbrev}: {roster.player_count} players")
    """

    @property
    def source_name(self) -> str:
        """Return unique identifier for this source."""
        return "nhl_json_roster"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Not used for roster downloads.

        Roster downloads are team-based, not game-based.
        """
        # This method is required by BaseDownloader but not applicable
        # for roster downloads which are team-centric
        return {"_note": "Roster downloads are team-based, not game-based"}

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Not used for roster downloads.

        Roster downloads are team-based, not game-based.
        Use download_all_current_rosters() or download_rosters_for_season()
        instead.

        Args:
            season_id: NHL season ID (not used)

        Yields:
            Nothing - this method is not applicable for roster downloads
        """
        # This method is required by BaseDownloader but not applicable
        # for roster downloads which are team-centric
        return
        yield  # Make this a generator (never reached)

    async def get_current_roster(self, team_abbrev: str) -> ParsedRoster:
        """Get the current roster for a team.

        Args:
            team_abbrev: Team abbreviation (e.g., "BOS", "NYR")

        Returns:
            ParsedRoster with all current players

        Raises:
            DownloadError: If the roster cannot be fetched
        """
        logger.debug("Fetching current roster for %s", team_abbrev)

        response = await self._get(f"roster/{team_abbrev}/current")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch roster for {team_abbrev}: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        roster = _parse_roster(data, team_abbrev)

        logger.info(
            "Fetched %d players for %s (F:%d D:%d G:%d)",
            roster.player_count,
            team_abbrev,
            len(roster.forwards),
            len(roster.defensemen),
            len(roster.goalies),
        )

        return roster

    async def get_roster_for_season(
        self, team_abbrev: str, season_id: int
    ) -> ParsedRoster:
        """Get the roster for a team in a specific season.

        Args:
            team_abbrev: Team abbreviation (e.g., "BOS", "NYR")
            season_id: Season ID (e.g., 20232024)

        Returns:
            ParsedRoster for the specified season

        Raises:
            DownloadError: If the roster cannot be fetched
        """
        logger.debug("Fetching roster for %s season %d", team_abbrev, season_id)

        response = await self._get(f"roster/{team_abbrev}/{season_id}")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch roster for {team_abbrev} "
                f"season {season_id}: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        roster = _parse_roster(data, team_abbrev, season_id)

        logger.info(
            "Fetched %d players for %s season %d",
            roster.player_count,
            team_abbrev,
            season_id,
        )

        return roster

    async def get_available_seasons(self, team_abbrev: str) -> list[int]:
        """Get all seasons with roster data available for a team.

        Args:
            team_abbrev: Team abbreviation (e.g., "BOS", "NYR")

        Returns:
            List of season IDs (e.g., [20232024, 20222023, ...])

        Raises:
            DownloadError: If the seasons cannot be fetched
        """
        logger.debug("Fetching available seasons for %s", team_abbrev)

        response = await self._get(f"roster-season/{team_abbrev}")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch seasons for {team_abbrev}: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        # API returns list of season strings like "20232024"
        seasons = [int(s) for s in data if s.isdigit()]

        logger.info("Found %d seasons for %s", len(seasons), team_abbrev)

        return sorted(seasons, reverse=True)

    async def download_all_current_rosters(
        self, team_abbrevs: Sequence[str] | None = None
    ) -> list[ParsedRoster]:
        """Download current rosters for multiple teams.

        Args:
            team_abbrevs: List of team abbreviations to download.
                         If None, downloads all 32 NHL teams.

        Returns:
            List of ParsedRoster objects

        Raises:
            DownloadError: If any roster cannot be fetched
        """
        teams = team_abbrevs if team_abbrevs is not None else NHL_TEAM_ABBREVS
        self.set_total_items(len(teams))

        logger.info("Downloading rosters for %d teams", len(teams))

        rosters: list[ParsedRoster] = []
        for team in teams:
            try:
                roster = await self.get_current_roster(team)
                rosters.append(roster)
            except DownloadError as e:
                logger.warning("Failed to download roster for %s: %s", team, e)
                # Continue with other teams

        logger.info(
            "Downloaded %d rosters with %d total players",
            len(rosters),
            sum(r.player_count for r in rosters),
        )

        return rosters

    async def download_rosters_for_season(
        self,
        season_id: int,
        team_abbrevs: Sequence[str] | None = None,
    ) -> list[ParsedRoster]:
        """Download rosters for multiple teams for a specific season.

        Args:
            season_id: Season ID (e.g., 20232024)
            team_abbrevs: List of team abbreviations to download.
                         If None, downloads all 32 NHL teams.

        Returns:
            List of ParsedRoster objects

        Raises:
            DownloadError: If any roster cannot be fetched
        """
        teams = team_abbrevs if team_abbrevs is not None else NHL_TEAM_ABBREVS
        self.set_total_items(len(teams))

        logger.info("Downloading rosters for %d teams season %d", len(teams), season_id)

        rosters: list[ParsedRoster] = []
        for team in teams:
            try:
                roster = await self.get_roster_for_season(team, season_id)
                rosters.append(roster)
            except DownloadError as e:
                # Some teams may not have existed in older seasons
                logger.debug("No roster for %s season %d: %s", team, season_id, e)

        logger.info(
            "Downloaded %d rosters for season %d with %d total players",
            len(rosters),
            season_id,
            sum(r.player_count for r in rosters),
        )

        return rosters

    async def get_player_by_id(
        self, player_id: int, team_abbrevs: Sequence[str] | None = None
    ) -> PlayerInfo | None:
        """Find a player by ID across team rosters.

        This searches current rosters to find a player. For more complete
        player info, use the Player Landing downloader.

        Args:
            player_id: NHL player ID
            team_abbrevs: Teams to search. If None, searches all teams.

        Returns:
            PlayerInfo if found, None otherwise
        """
        teams = team_abbrevs if team_abbrevs is not None else NHL_TEAM_ABBREVS

        for team in teams:
            try:
                roster = await self.get_current_roster(team)
                for player in roster.all_players:
                    if player.player_id == player_id:
                        return player
            except DownloadError:
                continue

        return None


def create_roster_downloader(
    *,
    requests_per_second: float = 5.0,
    max_retries: int = 3,
) -> RosterDownloader:
    """Factory function to create a configured RosterDownloader.

    Args:
        requests_per_second: Rate limit for API calls
        max_retries: Maximum retry attempts

    Returns:
        Configured RosterDownloader instance
    """
    config = DownloaderConfig(
        base_url=NHL_API_BASE_URL,
        requests_per_second=requests_per_second,
        max_retries=max_retries,
        health_check_url="roster/BOS/current",
    )
    return RosterDownloader(config)
