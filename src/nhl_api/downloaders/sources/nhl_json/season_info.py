"""NHL JSON API Season Info Downloader.

Downloads season metadata from the NHL JSON API, including
start/end dates, regular season and playoff structure.

API Endpoint: GET https://api-web.nhle.com/v1/season

Example usage:
    config = SeasonInfoDownloaderConfig()
    async with SeasonInfoDownloader(config) as downloader:
        seasons = await downloader.get_all_seasons()
        current = await downloader.get_current_season()
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import date
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


@dataclass
class SeasonInfoDownloaderConfig(DownloaderConfig):
    """Configuration for the Season Info Downloader.

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
class SeasonInfo:
    """Season metadata.

    Attributes:
        season_id: Season ID (e.g., 20242025)
        regular_season_start: Start date of regular season
        regular_season_end: End date of regular season
        playoff_start: Start date of playoffs
        playoff_end: End date of playoffs (estimated)
        number_of_games: Number of regular season games per team
        ties_in_use: Whether ties are possible (historical)
        olympics_participation: Whether players participated in Olympics
        conference_in_use: Whether conferences are in use
        division_in_use: Whether divisions are in use
    """

    season_id: int
    regular_season_start: date | None
    regular_season_end: date | None
    playoff_start: date | None
    playoff_end: date | None
    number_of_games: int
    ties_in_use: bool
    olympics_participation: bool
    conference_in_use: bool
    division_in_use: bool


def _parse_date(date_str: str | None) -> date | None:
    """Parse a date string to a date object.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Parsed date or None
    """
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        logger.warning("Failed to parse date: %s", date_str)
        return None


def _parse_season(season_data: dict[str, Any]) -> SeasonInfo:
    """Parse a season entry.

    Args:
        season_data: Raw season data from API

    Returns:
        Parsed SeasonInfo object
    """
    return SeasonInfo(
        season_id=season_data.get("id", 0),
        regular_season_start=_parse_date(season_data.get("regularSeasonStartDate")),
        regular_season_end=_parse_date(season_data.get("regularSeasonEndDate")),
        playoff_start=_parse_date(season_data.get("playoffEndDate")),
        playoff_end=_parse_date(season_data.get("seasonEndDate")),
        number_of_games=season_data.get("numberOfGames", 82),
        ties_in_use=season_data.get("tiesInUse", False),
        olympics_participation=season_data.get("olympicsParticipation", False),
        conference_in_use=season_data.get("conferencesInUse", True),
        division_in_use=season_data.get("divisionsInUse", True),
    )


class SeasonInfoDownloader(BaseDownloader):
    """Downloads NHL season metadata.

    The season endpoint provides information about:
    - All NHL seasons and their dates
    - Regular season and playoff windows
    - League structure (conferences, divisions)

    Example:
        config = SeasonInfoDownloaderConfig()
        async with SeasonInfoDownloader(config) as downloader:
            seasons = await downloader.get_all_seasons()
            current = await downloader.get_current_season()
    """

    def __init__(
        self,
        config: SeasonInfoDownloaderConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the downloader.

        Args:
            config: Downloader configuration
            **kwargs: Additional arguments passed to BaseDownloader
        """
        if config is None:
            config = SeasonInfoDownloaderConfig()
        super().__init__(config, **kwargs)
        self._cached_seasons: list[SeasonInfo] | None = None

    @property
    def source_name(self) -> str:
        """Return unique identifier for this source."""
        return "nhl_json_season_info"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Not applicable for season info - returns empty dict.

        Args:
            game_id: Not used

        Returns:
            Empty dictionary
        """
        # Season info is not game-specific
        return {}

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Not applicable for season info.

        Args:
            season_id: Not used

        Yields:
            Nothing
        """
        # This downloader doesn't iterate over games
        return
        yield  # Make this a generator  # noqa: B901

    async def get_all_seasons(self, *, force_refresh: bool = False) -> list[SeasonInfo]:
        """Get metadata for all NHL seasons.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of all season info objects
        """
        if self._cached_seasons is not None and not force_refresh:
            return self._cached_seasons

        logger.debug("Fetching all season info")

        response = await self._get("/v1/season")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch season info: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        seasons = []

        # The API returns a list of season objects
        for season_data in data if isinstance(data, list) else data.get("data", []):
            seasons.append(_parse_season(season_data))

        # Sort by season ID descending (newest first)
        seasons.sort(key=lambda s: s.season_id, reverse=True)
        self._cached_seasons = seasons

        logger.info("Fetched info for %d seasons", len(seasons))
        return seasons

    async def get_season(self, season_id: int) -> SeasonInfo | None:
        """Get metadata for a specific season.

        Args:
            season_id: Season ID (e.g., 20242025)

        Returns:
            Season info or None if not found
        """
        seasons = await self.get_all_seasons()
        for season in seasons:
            if season.season_id == season_id:
                return season
        return None

    async def get_current_season(self) -> SeasonInfo | None:
        """Get the current NHL season.

        Returns the season whose regular season window contains today's date,
        or the most recent season if between seasons.

        Returns:
            Current season info or None
        """
        seasons = await self.get_all_seasons()
        today = date.today()

        # Find season where today falls within the dates
        for season in seasons:
            if season.regular_season_start and season.playoff_end:
                if season.regular_season_start <= today <= season.playoff_end:
                    return season

        # If not in any season, return the most recent
        return seasons[0] if seasons else None

    async def persist(
        self,
        db: DatabaseService,
        seasons: list[SeasonInfo] | None = None,
    ) -> int:
        """Persist season info to the database.

        Args:
            db: Database service instance
            seasons: List of seasons to persist (fetches if not provided)

        Returns:
            Number of records upserted
        """
        if seasons is None:
            seasons = await self.get_all_seasons()

        count = 0
        for season in seasons:
            await db.execute(
                """
                INSERT INTO seasons (
                    season_id, regular_season_start, regular_season_end,
                    playoff_start, playoff_end, number_of_games,
                    ties_in_use, olympics_participation,
                    conferences_in_use, divisions_in_use
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (season_id) DO UPDATE SET
                    regular_season_start = EXCLUDED.regular_season_start,
                    regular_season_end = EXCLUDED.regular_season_end,
                    playoff_start = EXCLUDED.playoff_start,
                    playoff_end = EXCLUDED.playoff_end,
                    number_of_games = EXCLUDED.number_of_games,
                    ties_in_use = EXCLUDED.ties_in_use,
                    olympics_participation = EXCLUDED.olympics_participation,
                    conferences_in_use = EXCLUDED.conferences_in_use,
                    divisions_in_use = EXCLUDED.divisions_in_use,
                    updated_at = CURRENT_TIMESTAMP
                """,
                season.season_id,
                season.regular_season_start,
                season.regular_season_end,
                season.playoff_start,
                season.playoff_end,
                season.number_of_games,
                season.ties_in_use,
                season.olympics_participation,
                season.conference_in_use,
                season.division_in_use,
            )
            count += 1

        logger.info("Persisted %d season records", count)
        return count


def create_season_info_downloader(
    *,
    requests_per_second: float = DEFAULT_RATE_LIMIT,
    max_retries: int = 3,
) -> SeasonInfoDownloader:
    """Factory function to create a configured SeasonInfoDownloader.

    Args:
        requests_per_second: Rate limit for API calls
        max_retries: Maximum retry attempts

    Returns:
        Configured SeasonInfoDownloader instance
    """
    config = SeasonInfoDownloaderConfig(
        requests_per_second=requests_per_second,
        max_retries=max_retries,
    )
    return SeasonInfoDownloader(config)
