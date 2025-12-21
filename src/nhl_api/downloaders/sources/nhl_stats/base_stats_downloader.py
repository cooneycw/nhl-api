"""Base downloader for NHL Stats REST API.

This module provides a base implementation for downloading data from the
NHL Stats REST API at api.nhle.com/stats/rest/en/. This is a different
API from the main game data API (api-web.nhle.com).

Key differences from nhl_json downloaders:
- Different base URL: api.nhle.com/stats/rest/en
- Uses Cayenne expression query parameters (e.g., ?cayenneExp=gameId=2024020500)
- Response format: {"data": [...], "total": N}

Example usage:
    class ShiftChartsDownloader(BaseStatsDownloader):
        @property
        def source_name(self) -> str:
            return "nhl_stats_shift_charts"

        async def _fetch_game(self, game_id: int) -> dict[str, Any]:
            path = f"/shiftcharts?cayenneExp=gameId={game_id}"
            response = await self._get(path)
            return self._parse_response(response.json(), game_id)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import DownloadError

if TYPE_CHECKING:
    from collections.abc import Callable

    from nhl_api.downloaders.base.rate_limiter import RateLimiter
    from nhl_api.downloaders.base.retry_handler import RetryHandler
    from nhl_api.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

# NHL Stats REST API base URL
NHL_STATS_API_BASE_URL = "https://api.nhle.com/stats/rest/en"

# Default rate limit (requests per second)
DEFAULT_STATS_RATE_LIMIT = 5.0


@dataclass
class StatsDownloaderConfig(DownloaderConfig):
    """Configuration for NHL Stats API downloaders.

    Extends base DownloaderConfig with defaults specific to the
    NHL Stats REST API.

    Attributes:
        base_url: Base URL for the Stats API (default: api.nhle.com)
        requests_per_second: Rate limit (default: 5.0)
        max_retries: Maximum retry attempts (default: 3)
        retry_base_delay: Initial delay between retries (default: 1.0)
        http_timeout: HTTP request timeout (default: 30.0)
        health_check_url: URL for health check (empty for Stats API)
    """

    base_url: str = NHL_STATS_API_BASE_URL
    requests_per_second: float = DEFAULT_STATS_RATE_LIMIT
    max_retries: int = 3
    retry_base_delay: float = 1.0
    http_timeout: float = 30.0
    health_check_url: str = ""  # Stats API has no health check endpoint


class BaseStatsDownloader(BaseDownloader):
    """Base class for NHL Stats REST API downloaders.

    This class extends BaseDownloader with functionality specific to the
    NHL Stats REST API:
    - Configured for api.nhle.com/stats/rest/en base URL
    - Handles Cayenne expression query parameters
    - Parses {"data": [...], "total": N} response format

    Subclasses must implement:
    - source_name: Property returning unique source identifier
    - _fetch_game: Method to fetch and parse data for a single game
    - _fetch_season_games: Method to yield game IDs for a season

    Example:
        class ShiftChartsDownloader(BaseStatsDownloader):
            @property
            def source_name(self) -> str:
                return "nhl_stats_shift_charts"

            async def _fetch_game(self, game_id: int) -> dict[str, Any]:
                path = f"/shiftcharts?cayenneExp=gameId={game_id}"
                response = await self._get(path)
                if not response.is_success:
                    raise DownloadError(...)
                return self._parse_response(response.json(), game_id)
    """

    def __init__(
        self,
        config: StatsDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        game_ids: list[int] | None = None,
    ) -> None:
        """Initialize the Stats API downloader.

        Args:
            config: Downloader configuration (default: StatsDownloaderConfig)
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            game_ids: Optional list of game IDs to download
        """
        super().__init__(
            config or StatsDownloaderConfig(),
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
        )
        self._game_ids: list[int] = list(game_ids) if game_ids else []

    def set_game_ids(self, game_ids: list[int]) -> None:
        """Set the list of game IDs to download.

        This is typically populated from the Schedule downloader before
        calling download_season().

        Args:
            game_ids: List of NHL game IDs
        """
        self._game_ids = list(game_ids)
        logger.debug(
            "%s: Set %d game IDs for download",
            self.source_name,
            len(self._game_ids),
        )

    def get_game_ids(self) -> list[int]:
        """Get the current list of game IDs.

        Returns:
            List of game IDs set for download
        """
        return list(self._game_ids)

    @staticmethod
    def _build_cayenne_path(
        endpoint: str,
        *,
        game_id: int | None = None,
        **extra_params: Any,
    ) -> str:
        """Build a path with Cayenne expression parameters.

        The NHL Stats API uses Cayenne expressions for filtering.
        This helper builds the proper query string format.

        Args:
            endpoint: API endpoint (e.g., "/shiftcharts")
            game_id: Optional game ID to filter by
            **extra_params: Additional Cayenne parameters

        Returns:
            Full path with query parameters

        Example:
            >>> BaseStatsDownloader._build_cayenne_path(
            ...     "/shiftcharts",
            ...     game_id=2024020500
            ... )
            '/shiftcharts?cayenneExp=gameId=2024020500'
        """
        expressions = []

        if game_id is not None:
            expressions.append(f"gameId={game_id}")

        for key, value in extra_params.items():
            if value is not None:
                expressions.append(f"{key}={value}")

        if not expressions:
            return endpoint

        cayenne_exp = " and ".join(expressions)
        return f"{endpoint}?cayenneExp={cayenne_exp}"

    def _validate_stats_response(
        self,
        data: dict[str, Any],
        *,
        game_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Validate and extract data from Stats API response.

        Stats API responses have the format:
        {"data": [...], "total": N}

        Args:
            data: Raw response JSON
            game_id: Optional game ID for error messages

        Returns:
            List of records from the "data" field

        Raises:
            DownloadError: If response format is invalid
        """
        if not isinstance(data, dict):
            raise DownloadError(
                f"Invalid response format: expected dict, got {type(data).__name__}",
                source=self.source_name,
                game_id=game_id,
            )

        if "data" not in data:
            raise DownloadError(
                "Invalid response format: missing 'data' field",
                source=self.source_name,
                game_id=game_id,
            )

        records = data["data"]
        if not isinstance(records, list):
            raise DownloadError(
                f"Invalid response format: 'data' should be a list, got {type(records).__name__}",
                source=self.source_name,
                game_id=game_id,
            )

        total = data.get("total", len(records))
        logger.debug(
            "%s: Received %d records (total: %d) for game %s",
            self.source_name,
            len(records),
            total,
            game_id,
        )

        return records
