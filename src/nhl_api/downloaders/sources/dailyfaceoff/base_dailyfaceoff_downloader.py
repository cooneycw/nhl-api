"""Base class for DailyFaceoff downloaders.

This module provides the base implementation for downloading and parsing
data from DailyFaceoff.com, which provides NHL team lineup information
including line combinations, power play units, and starting goalies.

Example usage:
    class LineCombinationsDownloader(BaseDailyFaceoffDownloader):
        @property
        def data_type(self) -> str:
            return "line_combinations"

        async def download_team(self, team_id: int) -> dict[str, Any]:
            # Implementation
            ...
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import (
    DownloadError,
    DownloadResult,
    DownloadStatus,
)
from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import (
    TEAM_SLUGS,
    get_team_abbreviation,
    get_team_slug,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.base.rate_limiter import RateLimiter
    from nhl_api.downloaders.base.retry_handler import RetryHandler
    from nhl_api.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

# DailyFaceoff base URL
DAILYFACEOFF_BASE_URL = "https://www.dailyfaceoff.com"

# Conservative rate limit for DailyFaceoff (requests per second)
# Being respectful to external sites
DEFAULT_DAILYFACEOFF_RATE_LIMIT = 1.0

# User agent for requests
DEFAULT_USER_AGENT = "NHL-API-Collector/1.0 (Data Research)"


@dataclass
class DailyFaceoffConfig(DownloaderConfig):
    """Configuration for DailyFaceoff downloaders.

    Attributes:
        base_url: Base URL for DailyFaceoff website
        requests_per_second: Rate limit for requests (conservative for external sites)
        max_retries: Maximum retry attempts for failed requests
        retry_base_delay: Initial delay between retries in seconds
        http_timeout: HTTP request timeout in seconds
        health_check_url: URL path for health check
        user_agent: User agent string for HTTP requests
    """

    base_url: str = DAILYFACEOFF_BASE_URL
    requests_per_second: float = DEFAULT_DAILYFACEOFF_RATE_LIMIT
    max_retries: int = 3
    retry_base_delay: float = 2.0  # Longer delay for external site
    http_timeout: float = 30.0
    health_check_url: str = "/teams"
    user_agent: str = DEFAULT_USER_AGENT


# Default configuration instance
DAILYFACEOFF_CONFIG = DailyFaceoffConfig()


class BaseDailyFaceoffDownloader(BaseDownloader):
    """Abstract base class for DailyFaceoff downloaders.

    This class extends BaseDownloader with DailyFaceoff-specific functionality:
    - Team ID to URL slug mapping
    - HTML parsing with BeautifulSoup
    - Team-based download iteration

    Subclasses must implement:
    - data_type: Property returning the type of data being downloaded
    - page_path: Property returning the page path for the data type
    - _parse_page: Method to parse the HTML into structured data

    Example:
        class LineCombinationsDownloader(BaseDailyFaceoffDownloader):
            @property
            def data_type(self) -> str:
                return "line_combinations"

            @property
            def page_path(self) -> str:
                return "line-combinations"

            async def _parse_page(
                self, soup: BeautifulSoup, team_id: int
            ) -> dict[str, Any]:
                # Extract line combination data from HTML
                ...

        config = DailyFaceoffConfig()
        async with LineCombinationsDownloader(config) as downloader:
            result = await downloader.download_team(10)  # Toronto Maple Leafs
    """

    def __init__(
        self,
        config: DailyFaceoffConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        team_ids: list[int] | None = None,
    ) -> None:
        """Initialize the DailyFaceoff downloader.

        Args:
            config: Downloader configuration
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            team_ids: Optional list of team IDs to download (default: all active teams)
        """
        super().__init__(
            config or DailyFaceoffConfig(),
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
        )
        # Default to all teams except historical Arizona Coyotes
        self._team_ids: list[int] = team_ids or [
            tid
            for tid in TEAM_SLUGS.keys()
            if tid != 53  # Exclude Arizona (relocated)
        ]
        self._config: DailyFaceoffConfig  # Type hint for IDE

    @property
    @abstractmethod
    def data_type(self) -> str:
        """Type of data being downloaded.

        Examples: "line_combinations", "power_play", "starting_goalies"

        Returns:
            Data type identifier
        """
        ...

    @property
    @abstractmethod
    def page_path(self) -> str:
        """URL path segment for this data type.

        This is appended to the team URL to form the full page URL.
        Examples: "line-combinations", "power-play", "starting-goalies"

        Returns:
            URL path segment
        """
        ...

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source.

        Returns:
            Source name in format 'dailyfaceoff_{data_type}'
        """
        return f"dailyfaceoff_{self.data_type}"

    @abstractmethod
    async def _parse_page(self, soup: BeautifulSoup, team_id: int) -> dict[str, Any]:
        """Parse the DailyFaceoff page into structured data.

        This method should be implemented by subclasses to handle
        page-specific parsing logic.

        Args:
            soup: Parsed BeautifulSoup document
            team_id: NHL team ID

        Returns:
            Parsed page data as a dictionary

        Raises:
            DownloadError: If parsing fails
        """
        ...

    def set_team_ids(self, team_ids: list[int]) -> None:
        """Set team IDs for bulk download.

        Args:
            team_ids: List of NHL team IDs to download
        """
        self._team_ids = list(team_ids)
        logger.debug(
            "%s: Set %d team IDs for download",
            self.source_name,
            len(self._team_ids),
        )

    def _get_team_slug(self, team_id: int) -> str:
        """Get DailyFaceoff URL slug for a team.

        Args:
            team_id: NHL team ID

        Returns:
            DailyFaceoff URL slug

        Raises:
            KeyError: If team_id is not recognized
        """
        return get_team_slug(team_id)

    def _get_team_abbreviation(self, team_id: int) -> str:
        """Get NHL abbreviation for a team.

        Args:
            team_id: NHL team ID

        Returns:
            Three-letter team abbreviation

        Raises:
            KeyError: If team_id is not recognized
        """
        return get_team_abbreviation(team_id)

    def _build_team_url(self, team_id: int) -> str:
        """Build DailyFaceoff team page URL.

        DailyFaceoff team pages use the format:
        https://www.dailyfaceoff.com/teams/{slug}/{page_path}

        Args:
            team_id: NHL team ID

        Returns:
            Full URL for the team page
        """
        slug = self._get_team_slug(team_id)
        return f"{self.config.base_url}/teams/{slug}/{self.page_path}"

    def _parse_html(self, content: bytes) -> BeautifulSoup:
        """Parse HTML content with lxml parser.

        Args:
            content: Raw HTML bytes

        Returns:
            Parsed BeautifulSoup document
        """
        # Decode with error replacement for malformed characters
        html_text = content.decode("utf-8", errors="replace")
        return BeautifulSoup(html_text, "lxml")

    def _validate_html(self, content: bytes) -> bool:
        """Validate that content is HTML.

        Args:
            content: Raw bytes to validate

        Returns:
            True if content appears to be HTML
        """
        sample = content[:500].decode("utf-8", errors="replace").lower()
        return "<html" in sample or "<!doctype" in sample

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Not used for DailyFaceoff - downloads are team-based.

        DailyFaceoff data is organized by team, not by game.
        Use download_team() or download_all_teams() instead.

        Args:
            game_id: Not used

        Raises:
            NotImplementedError: Always, as this method is not applicable
        """
        raise NotImplementedError(
            f"{self.source_name}: DailyFaceoff downloads are team-based. "
            "Use download_team() or download_all_teams() instead."
        )

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Not used for DailyFaceoff - downloads are team-based.

        This method yields nothing as DailyFaceoff data is organized by team.

        Args:
            season_id: Not used

        Yields:
            Nothing
        """
        logger.warning(
            "%s: DailyFaceoff downloads are team-based. "
            "Use download_all_teams() instead of download_season().",
            self.source_name,
        )
        return
        yield  # Make this a generator that yields nothing

    async def download_team(self, team_id: int) -> DownloadResult:
        """Download data for a specific team.

        Args:
            team_id: NHL team ID

        Returns:
            DownloadResult with the team data

        Raises:
            DownloadError: If the download fails after retries
        """
        url = self._build_team_url(team_id)
        abbreviation = self._get_team_abbreviation(team_id)

        logger.debug(
            "%s: Downloading %s for team %s (%d)",
            self.source_name,
            self.data_type,
            abbreviation,
            team_id,
        )

        try:
            # Use relative path for _get() method
            path = url.replace(self.config.base_url, "")
            response = await self._get(path)

            if not response.is_success:
                raise DownloadError(
                    f"Failed to fetch team page: HTTP {response.status}",
                    source=self.source_name,
                )

            # Get raw content
            raw_content = response.content

            # Validate HTML content
            if not self._validate_html(raw_content):
                raise DownloadError(
                    "Response is not valid HTML",
                    source=self.source_name,
                )

            # Parse HTML
            soup = self._parse_html(raw_content)

            # Call subclass parser
            parsed_data = await self._parse_page(soup, team_id)

            return DownloadResult(
                source=self.source_name,
                season_id=0,  # DailyFaceoff shows current data, no season ID
                game_id=0,  # Not game-specific
                data={
                    "team_id": team_id,
                    "team_abbreviation": abbreviation,
                    **parsed_data,
                },
                status=DownloadStatus.COMPLETED,
                raw_content=raw_content,
            )

        except DownloadError:
            raise
        except Exception as e:
            logger.exception(
                "%s: Error downloading team %d",
                self.source_name,
                team_id,
            )
            raise DownloadError(
                f"Failed to download team {team_id}: {e}",
                source=self.source_name,
                cause=e,
            ) from e

    async def download_all_teams(self) -> AsyncGenerator[DownloadResult, None]:
        """Download data for all configured teams.

        Yields:
            DownloadResult for each team

        Raises:
            DownloadError: If a critical error prevents continuation
        """
        logger.info(
            "%s: Starting download for %d teams",
            self.source_name,
            len(self._team_ids),
        )

        self.set_total_items(len(self._team_ids))
        current_item = 0

        for team_id in self._team_ids:
            current_item += 1
            abbreviation = self._get_team_abbreviation(team_id)

            # Notify progress
            self._notify_progress(
                current=current_item,
                total=len(self._team_ids),
                status=DownloadStatus.DOWNLOADING,
                message=f"Downloading {abbreviation}",
            )

            try:
                result = await self.download_team(team_id)
                yield result

            except DownloadError as e:
                logger.warning(
                    "%s: Failed to download team %s (%d): %s",
                    self.source_name,
                    abbreviation,
                    team_id,
                    e,
                )
                yield DownloadResult(
                    source=self.source_name,
                    season_id=0,
                    game_id=0,
                    data={"team_id": team_id, "team_abbreviation": abbreviation},
                    status=DownloadStatus.FAILED,
                    error_message=str(e),
                )

        logger.info(
            "%s: Completed download for %d teams",
            self.source_name,
            len(self._team_ids),
        )
