"""NHL JSON API Team Prospects Downloader.

Downloads team prospect pipeline data from the NHL JSON API.

API Endpoint: GET https://api-web.nhle.com/v1/roster/{team}/prospects

Example usage:
    config = TeamProspectsDownloaderConfig()
    async with TeamProspectsDownloader(config) as downloader:
        prospects = await downloader.get_team_prospects("TOR")
        all_prospects = await downloader.get_all_prospects()
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import DownloadError

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com"

# Default rate limit for NHL API (requests per second)
DEFAULT_RATE_LIMIT = 5.0

# Current NHL team abbreviations
CURRENT_TEAM_ABBREVS = [
    "ANA",
    "ARI",
    "BOS",
    "BUF",
    "CGY",
    "CAR",
    "CHI",
    "COL",
    "CBJ",
    "DAL",
    "DET",
    "EDM",
    "FLA",
    "LAK",
    "MIN",
    "MTL",
    "NSH",
    "NJD",
    "NYI",
    "NYR",
    "OTT",
    "PHI",
    "PIT",
    "SJS",
    "SEA",
    "STL",
    "TBL",
    "TOR",
    "UTA",
    "VAN",
    "VGK",
    "WSH",
    "WPG",
]


@dataclass
class TeamProspectsDownloaderConfig(DownloaderConfig):
    """Configuration for the Team Prospects Downloader.

    Attributes:
        base_url: Base URL for the NHL API
        requests_per_second: Rate limit for API requests
        max_retries: Maximum retry attempts for failed requests
        retry_base_delay: Initial delay between retries in seconds
        http_timeout: HTTP request timeout in seconds
        health_check_url: URL path for health check endpoint
    """

    base_url: str = NHL_API_BASE_URL
    requests_per_second: float = DEFAULT_RATE_LIMIT
    max_retries: int = 3
    retry_base_delay: float = 1.0
    http_timeout: float = 30.0
    health_check_url: str = "/v1/schedule/now"


@dataclass(frozen=True, slots=True)
class ProspectInfo:
    """Prospect player information.

    Attributes:
        player_id: NHL player ID
        first_name: First name
        last_name: Last name
        full_name: Full display name
        sweater_number: Jersey number (if assigned)
        position: Position code (C, L, R, D, G)
        height_inches: Height in inches
        weight_lbs: Weight in pounds
        birth_date: Birth date string
        birth_city: Birth city
        birth_country: Birth country code
        shoots_catches: Shoots/catches (L or R)
        team_abbrev: Team abbreviation
        current_team_name: Current team/league (AHL, NCAA, etc.)
        draft_year: Year drafted
        draft_round: Round drafted
        draft_pick: Pick number in round
        draft_overall: Overall pick number
    """

    player_id: int
    first_name: str
    last_name: str
    full_name: str
    sweater_number: int | None
    position: str
    height_inches: int
    weight_lbs: int
    birth_date: str | None
    birth_city: str | None
    birth_country: str | None
    shoots_catches: str
    team_abbrev: str
    current_team_name: str | None
    draft_year: int | None
    draft_round: int | None
    draft_pick: int | None
    draft_overall: int | None


@dataclass
class ParsedTeamProspects:
    """Parsed team prospects data.

    Attributes:
        team_abbrev: Team abbreviation
        forwards: List of forward prospects
        defensemen: List of defenseman prospects
        goalies: List of goalie prospects
    """

    team_abbrev: str
    forwards: list[ProspectInfo]
    defensemen: list[ProspectInfo]
    goalies: list[ProspectInfo]

    @property
    def all_prospects(self) -> list[ProspectInfo]:
        """Get all prospects across all positions."""
        return self.forwards + self.defensemen + self.goalies


def _parse_prospect(player_data: dict[str, Any], team_abbrev: str) -> ProspectInfo:
    """Parse a prospect entry.

    Args:
        player_data: Raw player data from API
        team_abbrev: Team abbreviation

    Returns:
        Parsed ProspectInfo object
    """
    # Parse height from feet-inches format (e.g., "6' 2\"")
    height_str = player_data.get("heightInInches", 0)
    if isinstance(height_str, str):
        try:
            # Handle format like 74 (just inches) or "6' 2\""
            height_inches = int(height_str)
        except ValueError:
            height_inches = 0
    else:
        height_inches = height_str or 0

    # Parse draft info
    draft_details = player_data.get("draftDetails", {})

    return ProspectInfo(
        player_id=player_data.get("id", 0),
        first_name=player_data.get("firstName", {}).get("default", ""),
        last_name=player_data.get("lastName", {}).get("default", ""),
        full_name=f"{player_data.get('firstName', {}).get('default', '')} {player_data.get('lastName', {}).get('default', '')}".strip(),
        sweater_number=player_data.get("sweaterNumber"),
        position=player_data.get("positionCode", ""),
        height_inches=height_inches,
        weight_lbs=player_data.get("weightInPounds", 0),
        birth_date=player_data.get("birthDate"),
        birth_city=player_data.get("birthCity", {}).get("default"),
        birth_country=player_data.get("birthCountry"),
        shoots_catches=player_data.get("shootsCatches", ""),
        team_abbrev=team_abbrev,
        current_team_name=player_data.get("currentTeamAbbrev"),
        draft_year=draft_details.get("year"),
        draft_round=draft_details.get("round"),
        draft_pick=draft_details.get("pickInRound"),
        draft_overall=draft_details.get("overallPick"),
    )


def _parse_team_prospects(
    data: dict[str, Any], team_abbrev: str
) -> ParsedTeamProspects:
    """Parse the full prospects response.

    Args:
        data: Raw API response
        team_abbrev: Team abbreviation

    Returns:
        Parsed ParsedTeamProspects object
    """
    forwards = []
    defensemen = []
    goalies = []

    # Parse forwards
    for player_data in data.get("forwards", []):
        forwards.append(_parse_prospect(player_data, team_abbrev))

    # Parse defensemen
    for player_data in data.get("defensemen", []):
        defensemen.append(_parse_prospect(player_data, team_abbrev))

    # Parse goalies
    for player_data in data.get("goalies", []):
        goalies.append(_parse_prospect(player_data, team_abbrev))

    return ParsedTeamProspects(
        team_abbrev=team_abbrev,
        forwards=forwards,
        defensemen=defensemen,
        goalies=goalies,
    )


class TeamProspectsDownloader(BaseDownloader):
    """Downloads NHL team prospect pipeline data.

    Provides access to prospect information for each team including:
    - Basic player info (name, position, size)
    - Draft information
    - Current team/league

    Example:
        config = TeamProspectsDownloaderConfig()
        async with TeamProspectsDownloader(config) as downloader:
            prospects = await downloader.get_team_prospects("TOR")
            all_prospects = await downloader.get_all_prospects()
    """

    def __init__(
        self,
        config: TeamProspectsDownloaderConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the downloader.

        Args:
            config: Downloader configuration
            **kwargs: Additional arguments passed to BaseDownloader
        """
        if config is None:
            config = TeamProspectsDownloaderConfig()
        super().__init__(config, **kwargs)

    @property
    def source_name(self) -> str:
        """Return unique identifier for this source."""
        return "nhl_json_team_prospects"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Not applicable for prospects - returns empty dict.

        Args:
            game_id: Not used

        Returns:
            Empty dictionary
        """
        # Prospects are not game-specific
        return {}

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Not applicable for prospects.

        Args:
            season_id: Not used

        Yields:
            Nothing
        """
        # This downloader doesn't iterate over games
        return
        yield  # Make this a generator  # noqa: B901

    async def get_team_prospects(self, team_abbrev: str) -> ParsedTeamProspects:
        """Get prospects for a specific team.

        Args:
            team_abbrev: Team abbreviation (e.g., "TOR", "MTL")

        Returns:
            Parsed team prospects data

        Raises:
            DownloadError: If the fetch fails
        """
        logger.debug("Fetching prospects for %s", team_abbrev)

        response = await self._get(f"/v1/roster/{team_abbrev}/prospects")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch prospects for {team_abbrev}: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        return _parse_team_prospects(data, team_abbrev)

    async def get_all_prospects(
        self,
        *,
        teams: list[str] | None = None,
    ) -> dict[str, ParsedTeamProspects]:
        """Get prospects for all teams.

        Args:
            teams: Optional list of team abbreviations to fetch.
                   If None, fetches all current NHL teams.

        Returns:
            Dictionary mapping team abbreviation to prospects data
        """
        if teams is None:
            teams = CURRENT_TEAM_ABBREVS

        self.set_total_items(len(teams))
        results = {}

        for team in teams:
            try:
                prospects = await self.get_team_prospects(team)
                results[team] = prospects
                logger.debug(
                    "Fetched %d prospects for %s",
                    len(prospects.all_prospects),
                    team,
                )
            except DownloadError as e:
                logger.warning("Failed to fetch prospects for %s: %s", team, e)
                continue

        logger.info("Fetched prospects for %d teams", len(results))
        return results

    async def persist(
        self,
        db: DatabaseService,
        prospects: ParsedTeamProspects,
    ) -> int:
        """Persist prospect data to the database.

        Args:
            db: Database service instance
            prospects: Parsed prospects data

        Returns:
            Number of records upserted
        """
        count = 0

        for prospect in prospects.all_prospects:
            await db.execute(
                """
                INSERT INTO prospects (
                    player_id, first_name, last_name, position,
                    height_inches, weight_lbs, birth_date, birth_country,
                    shoots_catches, team_abbrev, current_team_name,
                    draft_year, draft_round, draft_pick, draft_overall
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (player_id) DO UPDATE SET
                    team_abbrev = EXCLUDED.team_abbrev,
                    current_team_name = EXCLUDED.current_team_name,
                    height_inches = EXCLUDED.height_inches,
                    weight_lbs = EXCLUDED.weight_lbs,
                    updated_at = CURRENT_TIMESTAMP
                """,
                prospect.player_id,
                prospect.first_name,
                prospect.last_name,
                prospect.position,
                prospect.height_inches,
                prospect.weight_lbs,
                prospect.birth_date,
                prospect.birth_country,
                prospect.shoots_catches,
                prospect.team_abbrev,
                prospect.current_team_name,
                prospect.draft_year,
                prospect.draft_round,
                prospect.draft_pick,
                prospect.draft_overall,
            )
            count += 1

        logger.info(
            "Persisted %d prospects for %s",
            count,
            prospects.team_abbrev,
        )
        return count


def create_team_prospects_downloader(
    *,
    requests_per_second: float = DEFAULT_RATE_LIMIT,
    max_retries: int = 3,
) -> TeamProspectsDownloader:
    """Factory function to create a configured TeamProspectsDownloader.

    Args:
        requests_per_second: Rate limit for API calls
        max_retries: Maximum retry attempts

    Returns:
        Configured TeamProspectsDownloader instance
    """
    config = TeamProspectsDownloaderConfig(
        requests_per_second=requests_per_second,
        max_retries=max_retries,
    )
    return TeamProspectsDownloader(config)
