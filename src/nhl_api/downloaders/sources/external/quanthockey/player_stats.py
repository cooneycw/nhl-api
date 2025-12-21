"""QuantHockey Player Season Statistics Downloader.

This module provides the downloader for fetching player season statistics
from quanthockey.com. It parses the 51-field player statistics table and
supports pagination to retrieve all players from a given season.

QuantHockey URL pattern:
    https://www.quanthockey.com/nhl/seasons/{YYYY-YY}-nhl-players-stats.html

Example usage:
    config = QuantHockeyConfig(
        base_url="https://www.quanthockey.com",
        requests_per_second=0.5,  # 1 request every 2 seconds
    )
    async with QuantHockeyPlayerStatsDownloader(config) as downloader:
        stats = await downloader.download_player_stats(20242025, max_players=100)
        for player in stats:
            print(f"{player.name}: {player.points} points")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.sources.external.base_external_downloader import (
    BaseExternalDownloader,
    ContentParsingError,
    ExternalDownloaderConfig,
)
from nhl_api.models.quanthockey import (
    QuantHockeyPlayerSeasonStats,
    QuantHockeySeasonData,
)

if TYPE_CHECKING:
    from nhl_api.utils.http_client import HTTPResponse

logger = logging.getLogger(__name__)

# Conservative rate limit for QuantHockey (1 request every 2 seconds)
QUANTHOCKEY_RATE_LIMIT = 0.5

# Number of players per page on QuantHockey
PLAYERS_PER_PAGE = 20

# Maximum pages to fetch (20 pages = 400 players)
MAX_PAGES = 20


@dataclass
class QuantHockeyConfig(ExternalDownloaderConfig):
    """Configuration for QuantHockey downloaders.

    Extends ExternalDownloaderConfig with QuantHockey-specific defaults.

    Attributes:
        base_url: QuantHockey base URL
        requests_per_second: Rate limit (conservative for external site)
        retry_base_delay: Longer delay for external site retries
    """

    base_url: str = "https://www.quanthockey.com"
    requests_per_second: float = QUANTHOCKEY_RATE_LIMIT
    retry_base_delay: float = 3.0  # Longer delay for external site


class QuantHockeyPlayerStatsDownloader(BaseExternalDownloader):
    """Downloader for QuantHockey player season statistics.

    Fetches and parses player statistics from QuantHockey's season pages.
    The site provides comprehensive 51-field player statistics including
    scoring, TOI, situational performance, and advanced metrics.

    Features:
    - Parse 51 fields per player from HTML tables
    - Pagination support (20 players per page, up to 20 pages)
    - Configurable max players limit
    - Conservative rate limiting (1 req per 2 sec)
    - Robust HTML parsing with BeautifulSoup

    Example:
        config = QuantHockeyConfig()
        async with QuantHockeyPlayerStatsDownloader(config) as downloader:
            # Get top 100 players from 2024-25 season
            stats = await downloader.download_player_stats(20242025, max_players=100)
    """

    config: QuantHockeyConfig  # Type hint for IDE support

    def __init__(
        self,
        config: QuantHockeyConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the QuantHockey downloader.

        Args:
            config: Downloader configuration (uses defaults if None)
            **kwargs: Additional arguments for BaseExternalDownloader
        """
        super().__init__(config or QuantHockeyConfig(), **kwargs)

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "quanthockey_player_stats"

    # =========================================================================
    # URL Building
    # =========================================================================

    def _season_id_to_name(self, season_id: int) -> str:
        """Convert NHL season ID to QuantHockey season name format.

        Args:
            season_id: NHL season ID (e.g., 20242025)

        Returns:
            Season name in YYYY-YY format (e.g., "2024-25")
        """
        season_str = str(season_id)
        if len(season_str) != 8:
            raise ValueError(f"Invalid season ID format: {season_id}")

        start_year = season_str[:4]
        end_year = season_str[6:8]
        return f"{start_year}-{end_year}"

    def _build_season_url(self, season_id: int, page: int = 1) -> str:
        """Build URL for a season statistics page.

        Args:
            season_id: NHL season ID (e.g., 20242025)
            page: Page number (1-indexed)

        Returns:
            Full URL for the season page
        """
        season_name = self._season_id_to_name(season_id)
        path = f"/nhl/seasons/{season_name}-nhl-players-stats.html"

        if page > 1:
            # QuantHockey uses ?page=N for pagination
            path = f"{path}?page={page}"

        return f"{self.config.base_url}{path}"

    # =========================================================================
    # HTML Parsing
    # =========================================================================

    def _extract_player_row(
        self, row: Tag, season_id: int
    ) -> QuantHockeyPlayerSeasonStats | None:
        """Extract player statistics from a table row.

        Args:
            row: BeautifulSoup Tag for the table row (<tr>)
            season_id: NHL season ID for the stats

        Returns:
            QuantHockeyPlayerSeasonStats or None if row is invalid
        """
        cells = row.find_all("td")
        if len(cells) < 50:
            # Not a valid player row
            return None

        try:
            # Extract text from each cell
            row_data: list[str] = []
            for cell in cells:
                # Get text, handling links and special content
                text = cell.get_text(strip=True)
                row_data.append(text)

            # Create stats from row data
            return QuantHockeyPlayerSeasonStats.from_row_data(
                row_data=row_data,
                season_id=season_id,
                validate=True,
            )
        except (ValueError, IndexError) as e:
            logger.warning("Failed to parse player row: %s", e)
            return None

    def _parse_stats_table(
        self,
        html_content: str,
        season_id: int,
    ) -> list[QuantHockeyPlayerSeasonStats]:
        """Parse player statistics from HTML content.

        Args:
            html_content: Raw HTML content
            season_id: NHL season ID

        Returns:
            List of player statistics
        """
        soup = BeautifulSoup(html_content, "lxml")
        players: list[QuantHockeyPlayerSeasonStats] = []

        # Find the main statistics table
        # QuantHockey uses tables with class containing "stats" or id "statsTable"
        stats_table = soup.find("table", {"id": "stats"})
        if not stats_table:
            stats_table = soup.find("table", class_=re.compile(r"stats|sortable"))
        if not stats_table:
            # Try finding any table with many columns
            for table in soup.find_all("table"):
                if isinstance(table, Tag):
                    first_row = table.find("tr")
                    if first_row and isinstance(first_row, Tag):
                        cells = first_row.find_all(["th", "td"])
                        if len(cells) >= 20:  # Stats table has many columns
                            stats_table = table
                            break

        if not stats_table:
            logger.warning("Could not find statistics table in HTML")
            return players

        # Find table body
        tbody = stats_table.find("tbody")
        if tbody and isinstance(tbody, Tag):
            rows = tbody.find_all("tr")
        else:
            rows = stats_table.find_all("tr")

        # Parse each row
        for row in rows:
            if isinstance(row, Tag):
                # Skip header rows
                if row.find("th"):
                    continue

                player = self._extract_player_row(row, season_id)
                if player:
                    players.append(player)

        return players

    def _has_next_page(self, html_content: str, current_page: int) -> bool:
        """Check if there's a next page of results.

        Args:
            html_content: Current page HTML content
            current_page: Current page number

        Returns:
            True if next page exists
        """
        soup = BeautifulSoup(html_content, "lxml")

        # Look for pagination links
        next_page = current_page + 1

        # Check for page=N links
        page_link = soup.find("a", href=re.compile(rf"page={next_page}"))
        if page_link:
            return True

        # Check for "Next" link
        for link in soup.find_all("a"):
            if isinstance(link, Tag):
                link_text = link.get_text(strip=True)
                if re.search(r"Next|►|>>", link_text):
                    return True

        # Check for numbered pagination (look for higher page number)
        pagination = soup.find(class_=re.compile(r"pagination|pager"))
        if pagination and isinstance(pagination, Tag):
            links = pagination.find_all("a")
            for link in links:
                try:
                    page_num = int(link.get_text(strip=True))
                    if page_num > current_page:
                        return True
                except ValueError:
                    continue

        return False

    # =========================================================================
    # Abstract Method Implementation
    # =========================================================================

    async def _parse_response(
        self,
        response: HTTPResponse,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse QuantHockey response into structured data.

        Args:
            response: HTTP response
            context: Request context (season_id, page)

        Returns:
            Dictionary with parsed player data
        """
        html_content = response.text()
        season_id = context.get("season_id", 0)

        players = self._parse_stats_table(html_content, season_id)
        has_next = self._has_next_page(html_content, context.get("page", 1))

        return {
            "players": [p.to_dict() for p in players],
            "player_count": len(players),
            "has_next_page": has_next,
        }

    # =========================================================================
    # Download Methods
    # =========================================================================

    async def download_player_stats(
        self,
        season_id: int,
        *,
        max_players: int | None = None,
        max_pages: int = MAX_PAGES,
    ) -> list[QuantHockeyPlayerSeasonStats]:
        """Download player statistics for a season.

        Fetches all pages of player statistics up to the specified limits.
        Uses rate limiting and retries for robust operation.

        Args:
            season_id: NHL season ID (e.g., 20242025)
            max_players: Maximum number of players to fetch (None = all)
            max_pages: Maximum number of pages to fetch (default 20)

        Returns:
            List of player statistics, sorted by rank

        Raises:
            ExternalSourceError: If download fails
            ContentParsingError: If parsing fails
        """
        all_players: list[QuantHockeyPlayerSeasonStats] = []
        page = 1

        logger.info(
            "Starting QuantHockey download for season %d (max_players=%s, max_pages=%d)",
            season_id,
            max_players,
            max_pages,
        )

        while page <= max_pages:
            url = self._build_season_url(season_id, page)
            context = {"season_id": season_id, "page": page}

            logger.debug("Fetching page %d: %s", page, url)

            # Fetch and parse page
            result = await self.fetch_resource(
                url.replace(self.config.base_url, ""),
                context=context,
            )

            data = result.data
            if not isinstance(data, dict):
                raise ContentParsingError(
                    "Unexpected response format",
                    source=self.source_name,
                    url=url,
                )

            # Convert player dicts back to dataclass objects
            players_data = data.get("players", [])
            for p_dict in players_data:
                player = QuantHockeyPlayerSeasonStats.from_dict(p_dict, validate=True)
                all_players.append(player)

            logger.debug(
                "Page %d: fetched %d players (total: %d)",
                page,
                len(players_data),
                len(all_players),
            )

            # Check if we've reached limits
            if max_players and len(all_players) >= max_players:
                all_players = all_players[:max_players]
                logger.info("Reached max_players limit (%d)", max_players)
                break

            # Check for more pages
            if not data.get("has_next_page", False):
                logger.debug("No more pages available")
                break

            if len(players_data) == 0:
                logger.debug("Empty page, stopping")
                break

            page += 1

        logger.info(
            "QuantHockey download complete: %d players fetched for season %d",
            len(all_players),
            season_id,
        )

        return all_players

    async def download_season_data(
        self,
        season_id: int,
        *,
        max_players: int | None = None,
        max_pages: int = MAX_PAGES,
    ) -> QuantHockeySeasonData:
        """Download player statistics as a QuantHockeySeasonData container.

        Convenience method that wraps download_player_stats() and returns
        a complete QuantHockeySeasonData object with metadata.

        Args:
            season_id: NHL season ID (e.g., 20242025)
            max_players: Maximum number of players to fetch (None = all)
            max_pages: Maximum number of pages to fetch (default 20)

        Returns:
            QuantHockeySeasonData with all player statistics
        """
        players = await self.download_player_stats(
            season_id,
            max_players=max_players,
            max_pages=max_pages,
        )

        return QuantHockeySeasonData(
            season_id=season_id,
            season_name=self._season_id_to_name(season_id),
            players=players,
            download_timestamp=datetime.now(UTC).isoformat(),
        )
