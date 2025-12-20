"""Abstract base class for NHL data downloaders.

This module provides a base implementation that composes the common downloader
components: HTTP client, rate limiter, and retry handler. Concrete implementations
override the abstract methods to handle source-specific download logic.

Example usage:
    class ScheduleDownloader(BaseDownloader):
        @property
        def source_name(self) -> str:
            return "nhl_json_schedule"

        async def _fetch_game(self, game_id: int) -> dict[str, Any]:
            response = await self._get(f"/v1/gamecenter/{game_id}/boxscore")
            return response.json()

        async def _fetch_season_games(self, season_id: int) -> AsyncIterator[int]:
            # Yield game IDs for the season
            ...
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from nhl_api.downloaders.base.protocol import (
    DownloadError,
    DownloadResult,
    DownloadStatus,
    HealthCheckError,
)
from nhl_api.downloaders.base.rate_limiter import RateLimiter
from nhl_api.downloaders.base.retry_handler import (
    RetryableError,
    RetryConfig,
    RetryHandler,
)
from nhl_api.utils.http_client import (
    HTTPClient,
    HTTPClientConfig,
    HTTPResponse,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Callable

logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Progress callbacks receive updates during download operations.
    They can be used for UI updates, logging, or progress tracking.
    """

    def __call__(
        self,
        *,
        source: str,
        current: int,
        total: int | None,
        game_id: int | None = None,
        status: DownloadStatus = DownloadStatus.DOWNLOADING,
        message: str | None = None,
    ) -> None:
        """Called with progress updates.

        Args:
            source: Name of the data source
            current: Current item number (1-indexed)
            total: Total items if known, None otherwise
            game_id: Current game ID if applicable
            status: Current download status
            message: Optional status message
        """
        ...


@dataclass
class DownloaderConfig:
    """Configuration for base downloader.

    Attributes:
        base_url: Base URL for API requests
        requests_per_second: Rate limit for requests
        max_retries: Maximum retry attempts
        retry_base_delay: Initial delay between retries in seconds
        http_timeout: HTTP request timeout in seconds
        health_check_url: URL for health check (relative to base_url)
    """

    base_url: str
    requests_per_second: float = 5.0
    max_retries: int = 3
    retry_base_delay: float = 1.0
    http_timeout: float = 30.0
    health_check_url: str = ""


@dataclass
class DownloadProgress:
    """Tracks progress of a download operation.

    Attributes:
        source: Name of the data source
        total_items: Total items to download (None if unknown)
        completed_items: Number of completed items
        failed_items: Number of failed items
        skipped_items: Number of skipped items
        current_game_id: Currently downloading game ID
        started_at: When the download started
        errors: List of errors encountered
    """

    source: str
    total_items: int | None = None
    completed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    current_game_id: int | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    errors: list[str] = field(default_factory=list)

    @property
    def processed_items(self) -> int:
        """Total number of processed items (success + failed + skipped)."""
        return self.completed_items + self.failed_items + self.skipped_items

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage (0-100)."""
        if self.processed_items == 0:
            return 0.0
        return (self.completed_items / self.processed_items) * 100

    @property
    def is_complete(self) -> bool:
        """Check if download is complete."""
        if self.total_items is None:
            return False
        return self.processed_items >= self.total_items


class BaseDownloader(ABC):
    """Abstract base class for NHL data downloaders.

    This class provides common functionality for all downloaders:
    - HTTP client with connection pooling
    - Rate limiting to avoid API throttling
    - Retry logic with exponential backoff
    - Progress tracking and callbacks
    - Error handling and logging

    Subclasses must implement:
    - source_name: Property returning unique source identifier
    - _fetch_game: Method to fetch data for a single game
    - _fetch_season_games: Method to yield game IDs for a season

    Example:
        class BoxscoreDownloader(BaseDownloader):
            @property
            def source_name(self) -> str:
                return "nhl_json_boxscore"

            async def _fetch_game(self, game_id: int) -> dict[str, Any]:
                response = await self._get(f"/v1/gamecenter/{game_id}/boxscore")
                return response.json()

            async def _fetch_season_games(
                self, season_id: int
            ) -> AsyncIterator[int]:
                # Fetch schedule and yield game IDs
                ...
    """

    def __init__(
        self,
        config: DownloaderConfig,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: ProgressCallback | Callable[..., None] | None = None,
    ) -> None:
        """Initialize the base downloader.

        Args:
            config: Downloader configuration
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
        """
        self.config = config
        self._progress_callback = progress_callback
        self._progress: DownloadProgress | None = None

        # Initialize or use provided components
        self._http_client = http_client
        self._owns_http_client = http_client is None

        self._rate_limiter = rate_limiter or RateLimiter(
            requests_per_second=config.requests_per_second,
        )

        self._retry_handler = retry_handler or RetryHandler(
            RetryConfig(
                max_retries=config.max_retries,
                base_delay=config.retry_base_delay,
            )
        )

        logger.debug(
            "Initialized %s with rate_limit=%.1f req/s, max_retries=%d",
            self.source_name,
            config.requests_per_second,
            config.max_retries,
        )

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source.

        Examples: "nhl_json_schedule", "nhl_json_boxscore", "html_gs"
        """
        ...

    @abstractmethod
    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Fetch data for a single game.

        This method should be implemented by subclasses to handle
        source-specific data fetching logic.

        Args:
            game_id: NHL game ID

        Returns:
            Parsed game data as a dictionary

        Raises:
            DownloadError: If the fetch fails
        """
        ...

    @abstractmethod
    def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Yield game IDs for a season.

        This method should be implemented by subclasses to provide
        the list of games available for a given season.

        Args:
            season_id: NHL season ID (e.g., 20242025)

        Yields:
            Game IDs for the season
        """
        ...

    async def __aenter__(self) -> BaseDownloader:
        """Enter async context and initialize HTTP client."""
        if self._http_client is None:
            self._http_client = HTTPClient(
                HTTPClientConfig(timeout=self.config.http_timeout)
            )
            await self._http_client._create_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context and cleanup resources."""
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.close()
            self._http_client = None

    async def _ensure_client(self) -> HTTPClient:
        """Ensure HTTP client is initialized.

        Returns:
            The HTTP client instance

        Raises:
            RuntimeError: If client is not initialized
        """
        if self._http_client is None:
            raise RuntimeError(
                f"{self.source_name}: HTTP client not initialized. "
                "Use 'async with downloader:' context manager."
            )
        return self._http_client

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> HTTPResponse:
        """Perform a rate-limited GET request with retry.

        Args:
            path: URL path (appended to base_url)
            params: Optional query parameters

        Returns:
            HTTP response

        Raises:
            DownloadError: If request fails after retries
        """
        client = await self._ensure_client()
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"

        async def do_request() -> HTTPResponse:
            await self._rate_limiter.wait()
            response = await client.get(url, params=params)

            if response.is_rate_limited:
                raise RetryableError(
                    f"Rate limited: {url}",
                    status_code=429,
                    retry_after=response.retry_after,
                    source=self.source_name,
                )

            if response.is_server_error:
                raise RetryableError(
                    f"Server error {response.status}: {url}",
                    status_code=response.status,
                    source=self.source_name,
                )

            return response

        return await self._retry_handler.execute(
            do_request,
            operation_name=f"{self.source_name}:GET:{path}",
            source=self.source_name,
        )

    def _notify_progress(
        self,
        *,
        current: int,
        total: int | None = None,
        game_id: int | None = None,
        status: DownloadStatus = DownloadStatus.DOWNLOADING,
        message: str | None = None,
    ) -> None:
        """Notify progress callback if registered.

        Args:
            current: Current item number
            total: Total items if known
            game_id: Current game ID if applicable
            status: Current status
            message: Optional message
        """
        if self._progress_callback is not None:
            self._progress_callback(
                source=self.source_name,
                current=current,
                total=total,
                game_id=game_id,
                status=status,
                message=message,
            )

    def _update_progress(
        self,
        *,
        completed: bool = False,
        failed: bool = False,
        skipped: bool = False,
        game_id: int | None = None,
        error: str | None = None,
    ) -> None:
        """Update internal progress tracking.

        Args:
            completed: Whether item completed successfully
            failed: Whether item failed
            skipped: Whether item was skipped
            game_id: Current game ID
            error: Error message if failed
        """
        if self._progress is None:
            return

        self._progress.current_game_id = game_id

        if completed:
            self._progress.completed_items += 1
        elif failed:
            self._progress.failed_items += 1
            if error:
                self._progress.errors.append(error)
        elif skipped:
            self._progress.skipped_items += 1

    async def download_season(
        self, season_id: int, *, force: bool = False
    ) -> AsyncIterator[DownloadResult]:
        """Download all data for a season.

        Args:
            season_id: NHL season ID (e.g., 20242025)
            force: If True, re-download even if data exists

        Yields:
            DownloadResult for each downloaded game

        Raises:
            DownloadError: If a critical error prevents continuation
        """
        logger.info(
            "%s: Starting season download for %d (force=%s)",
            self.source_name,
            season_id,
            force,
        )

        # Initialize progress tracking
        self._progress = DownloadProgress(source=self.source_name)
        current_item = 0

        try:
            async for game_id in self._fetch_season_games(season_id):
                current_item += 1
                self._progress.current_game_id = game_id

                # Notify progress
                self._notify_progress(
                    current=current_item,
                    total=self._progress.total_items,
                    game_id=game_id,
                    status=DownloadStatus.DOWNLOADING,
                )

                try:
                    result = await self.download_game(game_id)
                    self._update_progress(
                        completed=result.is_successful,
                        failed=not result.is_successful,
                        game_id=game_id,
                        error=result.error_message,
                    )
                    yield result

                except DownloadError as e:
                    logger.warning(
                        "%s: Failed to download game %d: %s",
                        self.source_name,
                        game_id,
                        e,
                    )
                    self._update_progress(
                        failed=True,
                        game_id=game_id,
                        error=str(e),
                    )
                    yield DownloadResult(
                        source=self.source_name,
                        season_id=season_id,
                        game_id=game_id,
                        data={},
                        status=DownloadStatus.FAILED,
                        error_message=str(e),
                    )

        finally:
            logger.info(
                "%s: Season %d download complete. Success: %d, Failed: %d, Skipped: %d",
                self.source_name,
                season_id,
                self._progress.completed_items,
                self._progress.failed_items,
                self._progress.skipped_items,
            )
            self._progress = None

    async def download_game(self, game_id: int) -> DownloadResult:
        """Download data for a specific game.

        Args:
            game_id: NHL game ID

        Returns:
            DownloadResult with the game data

        Raises:
            DownloadError: If the download fails after retries
        """
        logger.debug("%s: Downloading game %d", self.source_name, game_id)

        try:
            data = await self._fetch_game(game_id)

            # Extract season_id from game_id (first 4 digits + next 4 digits)
            # e.g., 2024020001 -> 20242025
            season_start = game_id // 1000000
            season_id = season_start * 10000 + season_start + 1

            return DownloadResult(
                source=self.source_name,
                season_id=season_id,
                game_id=game_id,
                data=data,
                status=DownloadStatus.COMPLETED,
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

    async def health_check(self) -> bool:
        """Check if the data source is accessible.

        Returns:
            True if the source is healthy

        Raises:
            HealthCheckError: If health check fails
        """
        if not self.config.health_check_url:
            logger.warning(
                "%s: No health check URL configured, assuming healthy",
                self.source_name,
            )
            return True

        try:
            client = await self._ensure_client()
            url = (
                f"{self.config.base_url.rstrip('/')}/"
                f"{self.config.health_check_url.lstrip('/')}"
            )
            response = await client.get(url, timeout=5.0)

            if response.is_success:
                logger.debug("%s: Health check passed", self.source_name)
                return True

            raise HealthCheckError(
                f"Health check returned status {response.status}",
                source=self.source_name,
            )

        except HealthCheckError:
            raise
        except Exception as e:
            logger.warning(
                "%s: Health check failed: %s",
                self.source_name,
                e,
            )
            raise HealthCheckError(
                f"Health check failed: {e}",
                source=self.source_name,
                cause=e,
            ) from e

    @property
    def progress(self) -> DownloadProgress | None:
        """Get current download progress if a download is in progress."""
        return self._progress

    def set_total_items(self, total: int) -> None:
        """Set the total number of items for progress tracking.

        This can be called by subclasses when the total count becomes known.

        Args:
            total: Total number of items to download
        """
        if self._progress is not None:
            self._progress.total_items = total
