"""QuantHockey All-Time Career Statistics Downloader.

This module provides the downloader for fetching all-time career player
statistics from quanthockey.com records pages. It supports multiple
leaderboard categories (points, goals, assists, etc.) and pagination.

QuantHockey URL patterns:
    https://www.quanthockey.com/nhl/records/nhl-players-all-time-points-leaders.html
    https://www.quanthockey.com/nhl/records/nhl-players-all-time-goals-leaders.html
    https://www.quanthockey.com/nhl/records/nhl-players-all-time-assists-leaders.html

Example usage:
    config = QuantHockeyConfig(
        base_url="https://www.quanthockey.com",
        requests_per_second=0.5,  # 1 request every 2 seconds
    )
    async with QuantHockeyCareerStatsDownloader(config) as downloader:
        leaders = await downloader.download_leaders(
            CareerStatCategory.POINTS,
            top_n=100
        )
        for player in leaders:
            print(f"{player.name}: {player.points} points")
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.sources.external.base_external_downloader import (
    BaseExternalDownloader,
    ContentParsingError,
)
from nhl_api.downloaders.sources.external.quanthockey.player_stats import (
    QuantHockeyConfig,
)
from nhl_api.models.quanthockey import (
    QuantHockeyPlayerCareerStats,
    _safe_float,
    _safe_int,
)

if TYPE_CHECKING:
    from nhl_api.utils.http_client import HTTPResponse

logger = logging.getLogger(__name__)

# Number of players per page on QuantHockey
PLAYERS_PER_PAGE = 20

# Maximum pages to fetch (20 pages = 400 players)
MAX_PAGES = 20


class CareerStatCategory(Enum):
    """Categories for career statistics leaderboards.

    Each category corresponds to a specific all-time leaders page on QuantHockey.
    """

    POINTS = "points"
    GOALS = "goals"
    ASSISTS = "assists"
    GAMES_PLAYED = "games-played"
    PENALTY_MINUTES = "penalty-minutes"
    PLUS_MINUS = "plus-minus"
    POWER_PLAY_GOALS = "power-play-goals"
    GAME_WINNING_GOALS = "game-winning-goals"
    SHOTS_ON_GOAL = "shots-on-goal"


# Mapping of category to URL path segment
CATEGORY_URL_MAP: dict[CareerStatCategory, str] = {
    CareerStatCategory.POINTS: "nhl-players-all-time-points-leaders",
    CareerStatCategory.GOALS: "nhl-players-all-time-goals-leaders",
    CareerStatCategory.ASSISTS: "nhl-players-all-time-assists-leaders",
    CareerStatCategory.GAMES_PLAYED: "nhl-players-all-time-games-played-leaders",
    CareerStatCategory.PENALTY_MINUTES: "nhl-players-all-time-penalty-minutes-leaders",
    CareerStatCategory.PLUS_MINUS: "nhl-players-all-time-plus-minus-leaders",
    CareerStatCategory.POWER_PLAY_GOALS: "nhl-players-all-time-power-play-goals-leaders",
    CareerStatCategory.GAME_WINNING_GOALS: "nhl-players-all-time-game-winning-goals-leaders",
    CareerStatCategory.SHOTS_ON_GOAL: "nhl-players-all-time-shots-on-goal-leaders",
}


class QuantHockeyCareerStatsDownloader(BaseExternalDownloader):
    """Downloader for QuantHockey all-time career statistics.

    Fetches and parses career statistics from QuantHockey's all-time records pages.
    Supports multiple leaderboard categories and pagination.

    Features:
    - Multiple category support (points, goals, assists, etc.)
    - Pagination support (20 players per page)
    - Configurable top_n limit
    - Conservative rate limiting (1 req per 2 sec)
    - Robust HTML parsing with BeautifulSoup

    Example:
        config = QuantHockeyConfig()
        async with QuantHockeyCareerStatsDownloader(config) as downloader:
            # Get top 100 all-time points leaders
            leaders = await downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=100
            )
    """

    config: QuantHockeyConfig  # Type hint for IDE support

    def __init__(
        self,
        config: QuantHockeyConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the QuantHockey career stats downloader.

        Args:
            config: Downloader configuration (uses defaults if None)
            **kwargs: Additional arguments for BaseExternalDownloader
        """
        super().__init__(config or QuantHockeyConfig(), **kwargs)

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "quanthockey_career_stats"

    # =========================================================================
    # URL Building
    # =========================================================================

    def _build_category_url(
        self,
        category: CareerStatCategory,
        page: int = 1,
    ) -> str:
        """Build URL for a career statistics category page.

        Args:
            category: Statistics category to fetch
            page: Page number (1-indexed)

        Returns:
            Full URL for the category page
        """
        url_segment = CATEGORY_URL_MAP[category]
        path = f"/nhl/records/{url_segment}.html"

        if page > 1:
            path = f"{path}?page={page}"

        return f"{self.config.base_url}{path}"

    # =========================================================================
    # HTML Parsing
    # =========================================================================

    def _extract_player_row(
        self,
        row: Tag,
        category: CareerStatCategory,
    ) -> QuantHockeyPlayerCareerStats | None:
        """Extract career statistics from a table row.

        Args:
            row: BeautifulSoup Tag for the table row (<tr>)
            category: The category being parsed (affects column interpretation)

        Returns:
            QuantHockeyPlayerCareerStats or None if row is invalid
        """
        cells = row.find_all("td")
        if len(cells) < 10:
            # Not a valid player row
            return None

        try:
            # Extract text from each cell
            row_data: list[str] = []
            for cell in cells:
                text = cell.get_text(strip=True)
                row_data.append(text)

            # Career tables have this structure (may vary slightly by category):
            # 0: Rank
            # 1: Name
            # 2: Team(s) - may have multiple
            # 3: Born/Birth Year
            # 4: Position
            # 5: GP (Games Played)
            # 6: G (Goals)
            # 7: A (Assists)
            # 8: P (Points)
            # 9: PIM (Penalty Minutes)
            # 10+: Additional stats depending on category

            # Parse birth year to extract first/last season estimates
            birth_year = _safe_int(row_data[3]) if len(row_data) > 3 else 0
            # Estimate career span (players typically debut at ~20 and play ~15 seasons)
            first_season = birth_year + 20 if birth_year > 1900 else 0
            last_season = birth_year + 40 if birth_year > 1900 else 0

            # Calculate seasons from GP if possible (rough estimate: ~60 GP/season)
            gp = _safe_int(row_data[5]) if len(row_data) > 5 else 0
            seasons_played = max(1, gp // 60) if gp > 0 else 0

            # Parse core stats
            stats = QuantHockeyPlayerCareerStats(
                name=row_data[1].strip() if len(row_data) > 1 else "",
                position=row_data[4].strip().upper() if len(row_data) > 4 else "",
                nationality="",  # Not typically on career pages
                first_season=first_season,
                last_season=last_season,
                seasons_played=seasons_played,
                games_played=gp,
                goals=_safe_int(row_data[6]) if len(row_data) > 6 else 0,
                assists=_safe_int(row_data[7]) if len(row_data) > 7 else 0,
                points=_safe_int(row_data[8]) if len(row_data) > 8 else 0,
                pim=_safe_int(row_data[9]) if len(row_data) > 9 else 0,
                plus_minus=_safe_int(row_data[10]) if len(row_data) > 10 else 0,
                # Additional stats parsed based on available columns
                pp_goals=_safe_int(row_data[11]) if len(row_data) > 11 else 0,
                gw_goals=_safe_int(row_data[12]) if len(row_data) > 12 else 0,
                shots_on_goal=_safe_int(row_data[13]) if len(row_data) > 13 else 0,
                shooting_pct=_safe_float(row_data[14]) if len(row_data) > 14 else 0.0,
            )

            return stats

        except (ValueError, IndexError) as e:
            logger.warning("Failed to parse career player row: %s", e)
            return None

    def _parse_career_table(
        self,
        html_content: str,
        category: CareerStatCategory,
    ) -> list[QuantHockeyPlayerCareerStats]:
        """Parse career statistics from HTML content.

        Args:
            html_content: Raw HTML content
            category: Statistics category being parsed

        Returns:
            List of player career statistics
        """
        soup = BeautifulSoup(html_content, "lxml")
        players: list[QuantHockeyPlayerCareerStats] = []

        # Find the main statistics table
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
                        if len(cells) >= 8:  # Career table has at least 8 columns
                            stats_table = table
                            break

        if not stats_table:
            logger.warning("Could not find career statistics table in HTML")
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

                player = self._extract_player_row(row, category)
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

        # Check for numbered pagination
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
            context: Request context (category, page)

        Returns:
            Dictionary with parsed player data
        """
        html_content = response.text()
        category = context.get("category", CareerStatCategory.POINTS)

        players = self._parse_career_table(html_content, category)
        has_next = self._has_next_page(html_content, context.get("page", 1))

        return {
            "players": [p.to_dict() for p in players],
            "player_count": len(players),
            "has_next_page": has_next,
        }

    # =========================================================================
    # Download Methods
    # =========================================================================

    async def download_leaders(
        self,
        category: CareerStatCategory,
        *,
        top_n: int = 100,
        max_pages: int = MAX_PAGES,
    ) -> list[QuantHockeyPlayerCareerStats]:
        """Download career statistics leaders for a category.

        Fetches all pages of career statistics up to the specified limits.
        Uses rate limiting and retries for robust operation.

        Args:
            category: Statistics category to fetch (points, goals, etc.)
            top_n: Maximum number of players to fetch
            max_pages: Maximum number of pages to fetch (default 20)

        Returns:
            List of player career statistics, sorted by the category

        Raises:
            ExternalSourceError: If download fails
            ContentParsingError: If parsing fails
        """
        all_players: list[QuantHockeyPlayerCareerStats] = []
        page = 1

        logger.info(
            "Starting QuantHockey career stats download for %s (top_n=%d, max_pages=%d)",
            category.value,
            top_n,
            max_pages,
        )

        while page <= max_pages:
            url = self._build_category_url(category, page)
            context = {"category": category, "page": page}

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
                player = QuantHockeyPlayerCareerStats.from_dict(p_dict, validate=True)
                all_players.append(player)

            logger.debug(
                "Page %d: fetched %d players (total: %d)",
                page,
                len(players_data),
                len(all_players),
            )

            # Check if we've reached limits
            if len(all_players) >= top_n:
                all_players = all_players[:top_n]
                logger.info("Reached top_n limit (%d)", top_n)
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
            "QuantHockey career stats download complete: %d players fetched for %s",
            len(all_players),
            category.value,
        )

        return all_players

    async def download_all_categories(
        self,
        *,
        top_n: int = 100,
    ) -> dict[CareerStatCategory, list[QuantHockeyPlayerCareerStats]]:
        """Download leaders for all career stat categories.

        Convenience method to fetch top players across all categories.
        Note: This makes multiple requests with rate limiting.

        Args:
            top_n: Maximum number of players per category

        Returns:
            Dictionary mapping category to list of players
        """
        results: dict[CareerStatCategory, list[QuantHockeyPlayerCareerStats]] = {}

        for category in CareerStatCategory:
            logger.info("Downloading %s leaders...", category.value)
            leaders = await self.download_leaders(category, top_n=top_n)
            results[category] = leaders

        return results
