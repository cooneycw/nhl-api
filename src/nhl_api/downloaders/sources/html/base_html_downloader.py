"""Base class for NHL HTML Report downloaders.

This module provides the base implementation for downloading and parsing
NHL HTML game reports from www.nhl.com/scores/htmlreports.

HTML reports provide detailed game information in a structured HTML format
that requires BeautifulSoup parsing with the lxml parser.

Example usage:
    class GameSummaryDownloader(BaseHTMLDownloader):
        @property
        def report_type(self) -> str:
            return "GS"

        async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
            # Parse game summary HTML
            ...
"""

from __future__ import annotations

import logging
import re
from abc import abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import (
    DownloadError,
    DownloadResult,
    DownloadStatus,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.base.rate_limiter import RateLimiter
    from nhl_api.downloaders.base.retry_handler import RetryHandler
    from nhl_api.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

# NHL HTML reports base URL
NHL_HTML_BASE_URL = "https://www.nhl.com/scores/htmlreports"

# Conservative rate limit for HTML reports (requests per second)
DEFAULT_HTML_RATE_LIMIT = 2.0

# Pattern for parsing player info: "72 T.THOMPSON(34)" -> {number, name, stat}
PLAYER_PATTERN = re.compile(r"(\d+)?\s*([A-Z][A-Z.\s'-]+)(?:\((\d+)\))?")

# Pattern for parsing time on ice: "12:34" -> (minutes, seconds)
TOI_PATTERN = re.compile(r"(\d+):(\d{2})")


@dataclass
class HTMLDownloaderConfig(DownloaderConfig):
    """Configuration for HTML report downloaders.

    Attributes:
        base_url: Base URL for NHL HTML reports
        requests_per_second: Rate limit for requests (conservative for HTML)
        max_retries: Maximum retry attempts for failed requests
        retry_base_delay: Initial delay between retries in seconds
        http_timeout: HTTP request timeout in seconds
        health_check_url: Not used for HTML reports
        store_raw_html: Whether to preserve raw HTML bytes in results
    """

    base_url: str = NHL_HTML_BASE_URL
    requests_per_second: float = DEFAULT_HTML_RATE_LIMIT
    max_retries: int = 3
    retry_base_delay: float = 1.0
    http_timeout: float = 45.0  # HTML pages can be slower
    health_check_url: str = ""
    store_raw_html: bool = True


# Default configuration instance
HTML_DOWNLOADER_CONFIG = HTMLDownloaderConfig()


class BaseHTMLDownloader(BaseDownloader):
    """Abstract base class for NHL HTML report downloaders.

    This class extends BaseDownloader with HTML-specific functionality:
    - BeautifulSoup parsing with lxml
    - HTML validation
    - URL building for NHL report format
    - Utility methods for parsing HTML tables and player info
    - Raw HTML preservation for reprocessing

    Subclasses must implement:
    - report_type: Property returning report code (GS, ES, PL, etc.)
    - _parse_report: Method to parse the HTML into structured data

    Example:
        class GameSummaryDownloader(BaseHTMLDownloader):
            @property
            def report_type(self) -> str:
                return "GS"

            async def _parse_report(
                self, soup: BeautifulSoup, game_id: int
            ) -> dict[str, Any]:
                # Extract game summary data from HTML
                ...

        config = HTMLDownloaderConfig()
        async with GameSummaryDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)
            # result.raw_content contains original HTML bytes
            # result.data contains parsed data
    """

    def __init__(
        self,
        config: HTMLDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        game_ids: list[int] | None = None,
    ) -> None:
        """Initialize the HTML downloader.

        Args:
            config: Downloader configuration
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            game_ids: Optional list of game IDs for season download
        """
        super().__init__(
            config or HTMLDownloaderConfig(),
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
        )
        self._game_ids: list[int] = game_ids or []
        self._store_raw = getattr(config, "store_raw_html", True)
        self._last_raw_content: bytes | None = None
        self._config: HTMLDownloaderConfig  # Type hint for IDE

    @property
    @abstractmethod
    def report_type(self) -> str:
        """Report type code (GS, ES, PL, FS, FC, RO, SS, TH, TV).

        Returns:
            Two-letter report type code used in NHL URL
        """
        ...

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source.

        Returns:
            Source name in format 'html_{report_type}' (e.g., 'html_gs')
        """
        return f"html_{self.report_type.lower()}"

    @abstractmethod
    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse the HTML report into structured data.

        This method should be implemented by subclasses to handle
        report-specific parsing logic.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Parsed report data as a dictionary

        Raises:
            DownloadError: If parsing fails
        """
        ...

    def set_game_ids(self, game_ids: list[int]) -> None:
        """Set game IDs for season download.

        Args:
            game_ids: List of NHL game IDs
        """
        self._game_ids = list(game_ids)
        logger.debug(
            "%s: Set %d game IDs for download",
            self.source_name,
            len(self._game_ids),
        )

    def _build_url(self, season_id: int, game_id: int) -> str:
        """Build NHL HTML report URL.

        NHL HTML reports use the format:
        https://www.nhl.com/scores/htmlreports/{season}/{report_type}{game_suffix}.HTM

        Args:
            season_id: NHL season ID (e.g., 20242025)
            game_id: NHL game ID (e.g., 2024020500)

        Returns:
            Full URL for the HTML report
        """
        # Extract game suffix (last 6 digits of game_id)
        game_suffix = f"{game_id:010d}"[-6:]
        return f"{self.config.base_url}/{season_id}/{self.report_type}{game_suffix}.HTM"

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
        # Check first 500 bytes for HTML markers
        sample = content[:500].decode("utf-8", errors="replace").lower()
        return "<html" in sample or "<!doctype" in sample

    def _extract_season_from_game_id(self, game_id: int) -> int:
        """Extract season ID from game ID.

        Game IDs are formatted as YYYYTTNNNN where:
        - YYYY = season start year
        - TT = game type (01=preseason, 02=regular, 03=playoffs)
        - NNNN = game number

        Args:
            game_id: NHL game ID

        Returns:
            Season ID in format YYYYYYYY (e.g., 20242025)
        """
        season_start = game_id // 1000000
        return season_start * 10000 + season_start + 1

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Fetch and parse HTML report for a single game.

        Args:
            game_id: NHL game ID

        Returns:
            Parsed report data as a dictionary

        Raises:
            DownloadError: If fetch or parse fails
        """
        season_id = self._extract_season_from_game_id(game_id)
        url = self._build_url(season_id, game_id)

        logger.debug(
            "%s: Fetching report for game %d from %s",
            self.source_name,
            game_id,
            url,
        )

        try:
            # Use relative path for _get() method
            path = url.replace(self.config.base_url, "")
            response = await self._get(path)

            if not response.is_success:
                raise DownloadError(
                    f"Failed to fetch HTML report: HTTP {response.status}",
                    source=self.source_name,
                    game_id=game_id,
                )

            # Get raw content
            raw_content = response.content

            # Validate HTML content
            if not self._validate_html(raw_content):
                raise DownloadError(
                    "Response is not valid HTML",
                    source=self.source_name,
                    game_id=game_id,
                )

            # Parse HTML
            soup = self._parse_html(raw_content)

            # Call subclass parser
            parsed_data = await self._parse_report(soup, game_id)

            # Store raw content reference for the download_game override
            self._last_raw_content = raw_content

            return parsed_data

        except DownloadError:
            raise
        except Exception as e:
            logger.exception(
                "%s: Error processing HTML for game %d",
                self.source_name,
                game_id,
            )
            raise DownloadError(
                f"Failed to process HTML report: {e}",
                source=self.source_name,
                game_id=game_id,
                cause=e,
            ) from e

    async def download_game(self, game_id: int) -> DownloadResult:
        """Download HTML report for a specific game.

        Overrides base method to include raw HTML content in result.

        Args:
            game_id: NHL game ID

        Returns:
            DownloadResult with parsed data and raw HTML

        Raises:
            DownloadError: If download fails
        """
        self._last_raw_content = None

        try:
            data = await self._fetch_game(game_id)
            season_id = self._extract_season_from_game_id(game_id)

            return DownloadResult(
                source=self.source_name,
                season_id=season_id,
                game_id=game_id,
                data=data,
                status=DownloadStatus.COMPLETED,
                raw_content=self._last_raw_content if self._store_raw else None,
            )

        except DownloadError:
            raise
        except Exception as e:
            logger.exception(
                "%s: Unexpected error downloading game %d",
                self.source_name,
                game_id,
            )
            raise DownloadError(
                f"Failed to download game {game_id}: {e}",
                source=self.source_name,
                game_id=game_id,
                cause=e,
            ) from e

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Yield game IDs for a season.

        Args:
            season_id: NHL season ID (e.g., 20242025)

        Yields:
            Game IDs for the season
        """
        if not self._game_ids:
            logger.warning(
                "%s: No game IDs set for season %d. "
                "Use set_game_ids() to provide game IDs from Schedule Downloader.",
                self.source_name,
                season_id,
            )
            return

        # Update total for progress tracking
        self.set_total_items(len(self._game_ids))

        logger.info(
            "%s: Downloading %d HTML reports for season %d",
            self.source_name,
            len(self._game_ids),
            season_id,
        )

        for game_id in self._game_ids:
            yield game_id

    # =========================================================================
    # HTML Parsing Utilities
    # =========================================================================

    def _extract_table_rows(
        self,
        soup: BeautifulSoup,
        table_id: str | None = None,
        table_attrs: dict[str, Any] | None = None,
        skip_header: bool = True,
    ) -> list[Tag]:
        """Extract rows from an HTML table.

        Args:
            soup: BeautifulSoup document or element
            table_id: Optional table ID to find
            table_attrs: Optional table attributes to match
            skip_header: Whether to skip header row(s)

        Returns:
            List of table row elements
        """
        # Find table
        if table_id:
            table = soup.find("table", id=table_id)
        elif table_attrs:
            table = soup.find("table", attrs=table_attrs)
        else:
            table = soup.find("table")

        if not table:
            return []

        # Get all rows as a list
        rows: list[Tag] = list(table.find_all("tr"))

        # Skip header if requested
        if skip_header and rows:
            # Check if first row contains th elements
            first_row = rows[0]
            if first_row.find("th"):
                rows = rows[1:]

        return rows

    def _get_text(self, element: Tag | None, default: str = "") -> str:
        """Safely extract text from an element.

        Args:
            element: BeautifulSoup element
            default: Default value if element is None

        Returns:
            Stripped text content or default
        """
        if element is None:
            return default
        return element.get_text(strip=True)

    def _safe_int(self, value: str | None, default: int | None = None) -> int | None:
        """Safely parse integer from string.

        Args:
            value: String to parse
            default: Default value if parsing fails

        Returns:
            Parsed integer or default
        """
        if value is None:
            return default
        try:
            # Remove common non-numeric characters
            cleaned = value.strip().replace(",", "").replace(" ", "")
            return int(cleaned) if cleaned else default
        except (ValueError, AttributeError):
            return default

    def _safe_float(
        self, value: str | None, default: float | None = None
    ) -> float | None:
        """Safely parse float from string.

        Args:
            value: String to parse
            default: Default value if parsing fails

        Returns:
            Parsed float or default
        """
        if value is None:
            return default
        try:
            # Remove common non-numeric characters except decimal
            cleaned = value.strip().replace(",", "").replace("%", "").replace(" ", "")
            return float(cleaned) if cleaned else default
        except (ValueError, AttributeError):
            return default

    def _parse_player_info(self, text: str) -> dict[str, Any]:
        """Parse player info from NHL HTML format.

        NHL HTML reports format player info as:
        "72 T.THOMPSON(34)" where:
        - 72 is the jersey number
        - T.THOMPSON is the name
        - (34) is an optional statistic

        Args:
            text: Raw player info text

        Returns:
            Dictionary with 'number', 'name', and 'stat' keys
        """
        text = text.strip()
        match = PLAYER_PATTERN.match(text)

        if match:
            return {
                "number": int(match.group(1)) if match.group(1) else None,
                "name": match.group(2).strip(),
                "stat": int(match.group(3)) if match.group(3) else None,
            }

        # Fallback: return text as name
        return {"number": None, "name": text, "stat": None}

    def _parse_toi(self, toi_str: str) -> int:
        """Parse time on ice string to total seconds.

        Args:
            toi_str: Time string in "MM:SS" format

        Returns:
            Total seconds
        """
        match = TOI_PATTERN.match(toi_str.strip())
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            return minutes * 60 + seconds
        return 0

    def _get_cell_text(self, row: Tag, index: int, default: str = "") -> str:
        """Get text from a specific cell in a table row.

        Args:
            row: Table row element
            index: Cell index (0-based)
            default: Default value if cell not found

        Returns:
            Cell text or default
        """
        cells = row.find_all(["td", "th"])
        if 0 <= index < len(cells):
            return self._get_text(cells[index], default)
        return default

    def _find_tables_by_header(
        self, soup: BeautifulSoup, header_text: str
    ) -> list[Tag]:
        """Find tables that contain specific header text.

        Args:
            soup: BeautifulSoup document
            header_text: Text to search for in table headers

        Returns:
            List of matching table elements
        """
        tables = []
        for table in soup.find_all("table"):
            # Check for header row containing the text
            header_row = table.find("tr")
            if header_row:
                header_cells = header_row.find_all(["th", "td"])
                for cell in header_cells:
                    if header_text.lower() in self._get_text(cell).lower():
                        tables.append(table)
                        break
        return tables
