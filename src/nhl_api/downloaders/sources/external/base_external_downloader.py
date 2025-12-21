"""Base class for external (third-party) data source downloaders.

This module provides the base implementation for downloading data from
external sources like QuantHockey and DailyFaceoff. It extends BaseDownloader
with features specific to third-party sites:

- Custom User-Agent with respectful bot identifier
- More conservative rate limiting (0.5 req/s default)
- Response validation hooks
- Raw response preservation
- Flexible download patterns (not tied to NHL game IDs)

Example usage:
    class DailyFaceoffDownloader(BaseExternalDownloader):
        @property
        def source_name(self) -> str:
            return "dailyfaceoff_lines"

        async def _parse_response(
            self, response: HTTPResponse, context: dict[str, Any]
        ) -> dict[str, Any]:
            # Parse DailyFaceoff HTML
            soup = BeautifulSoup(response.content, "lxml")
            return self._extract_line_data(soup)

    config = ExternalDownloaderConfig(
        base_url="https://www.dailyfaceoff.com",
    )
    async with DailyFaceoffDownloader(config) as downloader:
        result = await downloader.fetch_resource("/teams/boston-bruins/line-combinations")
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
    from nhl_api.utils.http_client import HTTPClient, HTTPResponse

logger = logging.getLogger(__name__)

# Conservative rate limit for external sources (requests per second)
DEFAULT_EXTERNAL_RATE_LIMIT = 0.5  # 1 request every 2 seconds

# Respectful User-Agent for third-party sites
DEFAULT_USER_AGENT = (
    "NHL-API-Collector/1.0 (Data Research; github.com/cooneycw/nhl-api)"
)


# =============================================================================
# Exception Classes
# =============================================================================


class ExternalSourceError(DownloadError):
    """Base exception for external source errors.

    Extends DownloadError with URL tracking for external sources.
    """

    def __init__(
        self,
        message: str,
        source: str | None = None,
        url: str | None = None,
        cause: Exception | None = None,
        game_id: int | None = None,
    ) -> None:
        """Initialize the external source error.

        Args:
            message: Human-readable error description
            source: Data source name where error occurred
            url: URL that caused the error
            cause: Original exception that caused this error
            game_id: Game ID if error is game-specific
        """
        super().__init__(message, source=source, game_id=game_id, cause=cause)
        self.url = url

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.url:
            parts.append(f"url={self.url}")
        return " ".join(parts)


class ValidationError(ExternalSourceError):
    """Raised when response validation fails.

    This error indicates the response was received but doesn't meet
    validation criteria (wrong status, empty content, invalid format).
    """

    def __init__(
        self,
        message: str,
        response_status: int | None = None,
        content_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the validation error.

        Args:
            message: Human-readable error description
            response_status: HTTP status code of the response
            content_type: Content-Type header value
            **kwargs: Additional arguments for ExternalSourceError
        """
        super().__init__(message, **kwargs)
        self.response_status = response_status
        self.content_type = content_type


class ContentParsingError(ExternalSourceError):
    """Raised when response content cannot be parsed.

    This error indicates the response was valid but parsing failed
    (malformed HTML, unexpected structure, missing data).
    """

    pass


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class ExternalDownloaderConfig(DownloaderConfig):
    """Configuration for external data source downloaders.

    Extends DownloaderConfig with settings appropriate for third-party sites.
    Uses more conservative defaults to respect external site policies.

    Attributes:
        base_url: Base URL for the external source (required)
        requests_per_second: Rate limit - conservative default (0.5 req/s)
        max_retries: Maximum retry attempts
        retry_base_delay: Initial delay between retries (longer for external)
        http_timeout: HTTP request timeout (longer for external sites)
        health_check_url: URL for health check (relative to base_url)
        user_agent: User-Agent header for requests
        custom_headers: Additional HTTP headers to send
        store_raw_response: Whether to preserve raw bytes in results
        validate_response: Enable response validation hooks
        require_content: Fail if response body is empty
    """

    base_url: str = ""  # Required - no default
    requests_per_second: float = DEFAULT_EXTERNAL_RATE_LIMIT
    max_retries: int = 3
    retry_base_delay: float = 2.0  # Longer initial delay for external sites
    http_timeout: float = 45.0  # External sites may be slower
    health_check_url: str = ""
    user_agent: str = DEFAULT_USER_AGENT
    custom_headers: dict[str, str] = field(default_factory=dict)
    store_raw_response: bool = True
    validate_response: bool = True
    require_content: bool = True


# Default configuration instance
EXTERNAL_DOWNLOADER_CONFIG = ExternalDownloaderConfig()


# =============================================================================
# Base External Downloader
# =============================================================================


class BaseExternalDownloader(BaseDownloader):
    """Abstract base class for third-party data source downloaders.

    This class extends BaseDownloader with features specific to external sources:
    - Custom User-Agent and headers
    - More conservative rate limiting
    - Response validation hooks
    - Raw response preservation
    - Non-game-based download patterns

    Subclasses must implement:
    - source_name: Property returning unique source identifier
    - _parse_response: Method to parse response into structured data

    Subclasses may override:
    - _validate_response: Custom validation logic
    - _build_url: Source-specific URL construction
    - source_category: Grouping for related sources

    Example:
        class QuantHockeySeasonDownloader(BaseExternalDownloader):
            @property
            def source_name(self) -> str:
                return "quanthockey_season"

            async def _parse_response(
                self, response: HTTPResponse, context: dict[str, Any]
            ) -> dict[str, Any]:
                # Parse QuantHockey HTML
                ...

        config = ExternalDownloaderConfig(
            base_url="https://www.quanthockey.com",
        )
        async with QuantHockeySeasonDownloader(config) as downloader:
            result = await downloader.fetch_resource("/nhl/seasons/2024-25.html")
    """

    config: ExternalDownloaderConfig  # Type hint for IDE support

    def __init__(
        self,
        config: ExternalDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> None:
        """Initialize the external downloader.

        Args:
            config: Downloader configuration
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
        """
        super().__init__(
            config or ExternalDownloaderConfig(),
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
        )
        self._store_raw = (
            getattr(config, "store_raw_response", True) if config else True
        )
        self._last_raw_content: bytes | None = None

    @property
    def source_category(self) -> str:
        """Category for grouping related sources.

        Default implementation returns the first part of source_name
        (before the first underscore).

        Examples:
            - "quanthockey_season" -> "quanthockey"
            - "dailyfaceoff_lines" -> "dailyfaceoff"
        """
        return self.source_name.split("_")[0]

    # =========================================================================
    # Request Methods
    # =========================================================================

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for requests.

        Combines User-Agent with custom headers from config.
        Standard browser-like headers are included for compatibility.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        headers.update(self.config.custom_headers)
        return headers

    async def _get_with_headers(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HTTPResponse:
        """Perform a GET request with external source headers.

        Extends base _get to add User-Agent and custom headers.
        This method is rate-limited and retried automatically.

        Args:
            url: Full URL or path (appended to base_url if relative)
            params: Optional query parameters
            headers: Optional additional headers (merged with defaults)

        Returns:
            HTTP response

        Raises:
            ExternalSourceError: If request fails after retries
        """
        # Build full URL if needed
        if not url.startswith(("http://", "https://")):
            url = f"{self.config.base_url.rstrip('/')}/{url.lstrip('/')}"

        # Merge headers
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        # Use parent's _get which handles rate limiting and retries
        # We need to temporarily store headers for the request
        client = await self._ensure_client()

        from nhl_api.downloaders.base.retry_handler import RetryableError

        async def do_request() -> HTTPResponse:
            await self._rate_limiter.wait()
            response = await client.get(url, params=params, headers=request_headers)

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

        try:
            return await self._retry_handler.execute(
                do_request,
                operation_name=f"{self.source_name}:GET:{url}",
                source=self.source_name,
            )
        except Exception as e:
            if isinstance(e, ExternalSourceError):
                raise
            raise ExternalSourceError(
                f"Request failed: {e}",
                source=self.source_name,
                url=url,
                cause=e if isinstance(e, Exception) else None,
            ) from e

    # =========================================================================
    # Validation Methods
    # =========================================================================

    async def _validate_response(self, response: HTTPResponse) -> bool:
        """Validate that response is acceptable.

        Default implementation checks:
        - Status code is 2xx
        - Content is not empty (if require_content=True)

        Subclasses can override for source-specific validation.

        Args:
            response: HTTP response to validate

        Returns:
            True if response is valid

        Raises:
            ValidationError: If response fails validation
        """
        if not self.config.validate_response:
            return True

        # Check status
        if not response.is_success:
            raise ValidationError(
                f"Request failed with status {response.status}",
                response_status=response.status,
                source=self.source_name,
            )

        # Check content
        if self.config.require_content:
            content = response.content
            if not content or len(content) == 0:
                raise ValidationError(
                    "Response body is empty",
                    response_status=response.status,
                    source=self.source_name,
                )

        return True

    # =========================================================================
    # Abstract Methods
    # =========================================================================

    @abstractmethod
    async def _parse_response(
        self,
        response: HTTPResponse,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse response content into structured data.

        This method must be implemented by subclasses to handle
        source-specific parsing logic.

        Args:
            response: HTTP response to parse
            context: Additional context (URL, params, etc.)

        Returns:
            Parsed data as dictionary

        Raises:
            ContentParsingError: If parsing fails
        """
        ...

    # =========================================================================
    # High-Level Methods
    # =========================================================================

    async def fetch_resource(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> DownloadResult:
        """Fetch a resource from the external source.

        This is the primary download method for external sources.
        It handles the full download flow: request, validation,
        parsing, and result creation.

        Args:
            path: URL path relative to base_url
            params: Optional query parameters
            context: Optional context for result metadata

        Returns:
            DownloadResult with parsed data

        Raises:
            ExternalSourceError: If download fails
            ValidationError: If response validation fails
            ContentParsingError: If parsing fails
        """
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        context = context or {}
        context["url"] = url
        context["path"] = path
        context["params"] = params

        logger.debug(
            "%s: Fetching resource %s",
            self.source_name,
            url,
        )

        try:
            # Fetch with headers
            response = await self._get_with_headers(url, params=params)

            # Validate response
            await self._validate_response(response)

            # Store raw content if configured
            raw_content: bytes | None = None
            if self._store_raw:
                raw_content = response.content
                self._last_raw_content = raw_content

            # Parse response
            try:
                data = await self._parse_response(response, context)
            except ContentParsingError:
                raise
            except Exception as e:
                raise ContentParsingError(
                    f"Failed to parse response: {e}",
                    source=self.source_name,
                    url=url,
                    cause=e,
                ) from e

            return DownloadResult(
                source=self.source_name,
                season_id=context.get("season_id", 0),
                data=data,
                downloaded_at=datetime.now(UTC),
                game_id=context.get("game_id"),
                status=DownloadStatus.COMPLETED,
                raw_content=raw_content,
            )

        except (ExternalSourceError, ValidationError, ContentParsingError):
            raise
        except Exception as e:
            logger.exception(
                "%s: Unexpected error fetching %s",
                self.source_name,
                url,
            )
            raise ExternalSourceError(
                f"Failed to fetch resource: {e}",
                source=self.source_name,
                url=url,
                cause=e,
            ) from e

    async def fetch_page(
        self,
        url: str,
        *,
        validate: bool = True,
    ) -> tuple[HTTPResponse, bytes]:
        """Fetch a page and return both response and content.

        Lower-level method for custom parsing workflows where
        you need direct access to the response and content.

        Args:
            url: Full URL or path relative to base_url
            validate: Whether to run validation (default True)

        Returns:
            Tuple of (HTTPResponse, content bytes)

        Raises:
            ExternalSourceError: If request fails
            ValidationError: If validation fails
        """
        response = await self._get_with_headers(url)

        if validate:
            await self._validate_response(response)

        content = response.content
        if self._store_raw:
            self._last_raw_content = content

        return response, content

    # =========================================================================
    # Default Implementations of Base Methods
    # =========================================================================

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Default implementation raises NotImplementedError.

        External sources may not support game-based downloads.
        Subclasses that support games should override this method.

        Args:
            game_id: NHL game ID

        Returns:
            Game data as dictionary

        Raises:
            NotImplementedError: By default, external sources don't support this
        """
        raise NotImplementedError(
            f"{self.source_name} does not support game-based downloads. "
            "Use fetch_resource() or source-specific methods instead."
        )

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Default implementation yields nothing.

        External sources may use different season structures.
        Subclasses that support season downloads should override this.

        Args:
            season_id: NHL season ID

        Yields:
            Game IDs (empty by default)
        """
        logger.warning(
            "%s: _fetch_season_games not implemented for external sources. "
            "Use fetch_resource() or source-specific methods instead.",
            self.source_name,
        )
        return
        yield  # Make it a generator

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _build_url(self, path: str, **kwargs: Any) -> str:
        """Build URL for a request.

        Default implementation joins base_url with path.
        Subclasses can override for complex URL patterns.

        Args:
            path: URL path
            **kwargs: Additional URL components (ignored by default)

        Returns:
            Full URL string
        """
        return f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"

    @property
    def last_raw_content(self) -> bytes | None:
        """Get the raw content from the last request.

        Useful for debugging or reprocessing.
        Only available if store_raw_response=True in config.
        """
        return self._last_raw_content
