"""HTTP client utility with connection pooling and async support.

This module provides a shared HTTP client for making requests to NHL APIs
and websites. It uses aiohttp for async operations with built-in support
for connection pooling, timeouts, and proper header management.

Example usage:
    async with HTTPClient() as client:
        response = await client.get("https://api-web.nhle.com/v1/schedule/now")
        data = response.json()

    # Or with custom configuration
    config = HTTPClientConfig(timeout=60, user_agent="MyApp/1.0")
    async with HTTPClient(config) as client:
        response = await client.get(url)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Content types for HTTP responses."""

    JSON = "application/json"
    HTML = "text/html"
    TEXT = "text/plain"
    BINARY = "application/octet-stream"


@dataclass(frozen=True, slots=True)
class HTTPClientConfig:
    """Configuration for the HTTP client.

    Attributes:
        timeout: Request timeout in seconds
        connect_timeout: Connection timeout in seconds
        total_timeout: Total operation timeout in seconds
        user_agent: User-Agent header value
        max_connections: Maximum number of connections in the pool
        max_connections_per_host: Maximum connections per host
        enable_cookies: Whether to enable cookie handling
        verify_ssl: Whether to verify SSL certificates
    """

    timeout: float = 30.0
    connect_timeout: float = 10.0
    total_timeout: float = 300.0
    user_agent: str = "NHL-API-Client/1.0 (Research)"
    max_connections: int = 100
    max_connections_per_host: int = 10
    enable_cookies: bool = True
    verify_ssl: bool = True

    @property
    def default_headers(self) -> dict[str, str]:
        """Get default headers for all requests."""
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/html, */*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
        }


@dataclass
class HTTPResponse:
    """Wrapper for HTTP response data.

    Attributes:
        status: HTTP status code
        headers: Response headers
        content: Raw response content as bytes
        url: Final URL after redirects
        content_type: Detected content type
    """

    status: int
    headers: dict[str, str]
    content: bytes
    url: str
    content_type: ContentType = ContentType.BINARY

    @classmethod
    async def from_aiohttp_response(
        cls, response: aiohttp.ClientResponse
    ) -> HTTPResponse:
        """Create HTTPResponse from aiohttp response.

        Args:
            response: The aiohttp ClientResponse object

        Returns:
            HTTPResponse with all data extracted
        """
        content = await response.read()
        content_type = cls._detect_content_type(
            response.headers.get("Content-Type", "")
        )

        return cls(
            status=response.status,
            headers=dict(response.headers),
            content=content,
            url=str(response.url),
            content_type=content_type,
        )

    @staticmethod
    def _detect_content_type(content_type_header: str) -> ContentType:
        """Detect content type from header value."""
        header_lower = content_type_header.lower()
        if "application/json" in header_lower:
            return ContentType.JSON
        if "text/html" in header_lower:
            return ContentType.HTML
        if "text/plain" in header_lower:
            return ContentType.TEXT
        return ContentType.BINARY

    def json(self) -> Any:
        """Parse response content as JSON.

        Returns:
            Parsed JSON data

        Raises:
            ValueError: If content is not valid JSON
        """
        import json

        try:
            return json.loads(self.content.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}") from e

    def text(self, encoding: str = "utf-8") -> str:
        """Get response content as text.

        Args:
            encoding: Character encoding to use

        Returns:
            Decoded text content
        """
        return self.content.decode(encoding)

    @property
    def is_success(self) -> bool:
        """Check if response indicates success (2xx status)."""
        return 200 <= self.status < 300

    @property
    def is_rate_limited(self) -> bool:
        """Check if response indicates rate limiting."""
        return self.status == 429

    @property
    def is_server_error(self) -> bool:
        """Check if response indicates server error (5xx status)."""
        return 500 <= self.status < 600

    @property
    def is_client_error(self) -> bool:
        """Check if response indicates client error (4xx status)."""
        return 400 <= self.status < 500

    @property
    def retry_after(self) -> float | None:
        """Get Retry-After header value if present.

        Returns:
            Seconds to wait before retry, or None if not specified
        """
        retry_after = self.headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            return float(retry_after)
        except ValueError:
            return None


class HTTPClientError(Exception):
    """Base exception for HTTP client errors."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.cause = cause


class ConnectionError(HTTPClientError):
    """Raised when connection to server fails."""

    pass


class TimeoutError(HTTPClientError):
    """Raised when request times out."""

    pass


class HTTPClient:
    """Async HTTP client with connection pooling.

    This client manages a connection pool for efficient HTTP requests.
    It should be used as an async context manager to ensure proper
    resource cleanup.

    Example:
        async with HTTPClient() as client:
            response = await client.get("https://api-web.nhle.com/v1/schedule/now")
            if response.is_success:
                data = response.json()
    """

    def __init__(self, config: HTTPClientConfig | None = None) -> None:
        """Initialize the HTTP client.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or HTTPClientConfig()
        self._session: aiohttp.ClientSession | None = None
        self._connector: aiohttp.TCPConnector | None = None
        self._cookie_jar: aiohttp.CookieJar | aiohttp.DummyCookieJar | None = None

    async def __aenter__(self) -> HTTPClient:
        """Enter async context and create session."""
        await self._create_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context and cleanup resources."""
        await self.close()

    async def _create_session(self) -> None:
        """Create the aiohttp session with connection pooling."""
        if self._session is not None:
            return

        # Create connector with connection pooling
        self._connector = aiohttp.TCPConnector(
            limit=self.config.max_connections,
            limit_per_host=self.config.max_connections_per_host,
            ssl=self.config.verify_ssl,
            enable_cleanup_closed=True,
        )

        # Create cookie jar if cookies are enabled
        if self.config.enable_cookies:
            self._cookie_jar = aiohttp.CookieJar()
        else:
            self._cookie_jar = aiohttp.DummyCookieJar()

        # Create timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=self.config.total_timeout,
            connect=self.config.connect_timeout,
            sock_read=self.config.timeout,
        )

        # Create the session
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            cookie_jar=self._cookie_jar,
            timeout=timeout,
            headers=self.config.default_headers,
        )

        logger.debug(
            "Created HTTP session with pool size %d", self.config.max_connections
        )

    async def close(self) -> None:
        """Close the session and release resources."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            self._connector = None
            self._cookie_jar = None
            logger.debug("Closed HTTP session")

    @property
    def is_open(self) -> bool:
        """Check if the session is open."""
        return self._session is not None and not self._session.closed

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure session exists and return it.

        Returns:
            The active aiohttp session

        Raises:
            RuntimeError: If session is not initialized
        """
        if self._session is None:
            await self._create_session()
        if self._session is None:
            raise RuntimeError("HTTP session not initialized")
        return self._session

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HTTPResponse:
        """Perform a GET request.

        Args:
            url: The URL to request
            headers: Additional headers to send
            params: Query parameters to append to URL
            timeout: Override default timeout for this request

        Returns:
            HTTPResponse with response data

        Raises:
            ConnectionError: If connection fails
            TimeoutError: If request times out
            HTTPClientError: For other HTTP errors
        """
        return await self._request(
            "GET", url, headers=headers, params=params, timeout=timeout
        )

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        data: bytes | str | None = None,
        json: Any = None,
        timeout: float | None = None,
    ) -> HTTPResponse:
        """Perform a POST request.

        Args:
            url: The URL to request
            headers: Additional headers to send
            params: Query parameters to append to URL
            data: Raw data to send in body
            json: JSON data to send in body (will be serialized)
            timeout: Override default timeout for this request

        Returns:
            HTTPResponse with response data

        Raises:
            ConnectionError: If connection fails
            TimeoutError: If request times out
            HTTPClientError: For other HTTP errors
        """
        return await self._request(
            "POST",
            url,
            headers=headers,
            params=params,
            data=data,
            json=json,
            timeout=timeout,
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        data: bytes | str | None = None,
        json: Any = None,
        timeout: float | None = None,
    ) -> HTTPResponse:
        """Perform an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: The URL to request
            headers: Additional headers to send
            params: Query parameters to append to URL
            data: Raw data to send in body
            json: JSON data to send in body
            timeout: Override default timeout for this request

        Returns:
            HTTPResponse with response data

        Raises:
            ConnectionError: If connection fails
            TimeoutError: If request times out
            HTTPClientError: For other HTTP errors
        """
        session = await self._ensure_session()

        # Build request kwargs
        kwargs: dict[str, Any] = {}
        if headers:
            kwargs["headers"] = dict(headers)
        if params:
            kwargs["params"] = dict(params)
        if data is not None:
            kwargs["data"] = data
        if json is not None:
            kwargs["json"] = json
        if timeout is not None:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)

        logger.debug("HTTP %s %s", method, url)

        try:
            async with session.request(method, url, **kwargs) as response:
                http_response = await HTTPResponse.from_aiohttp_response(response)
                logger.debug("HTTP %s %s -> %d", method, url, http_response.status)
                return http_response

        except aiohttp.ClientConnectorError as e:
            logger.warning("Connection error for %s: %s", url, e)
            raise ConnectionError(
                f"Failed to connect to {url}", url=url, cause=e
            ) from e

        except aiohttp.ServerTimeoutError as e:
            logger.warning("Timeout for %s: %s", url, e)
            raise TimeoutError(f"Request timed out for {url}", url=url, cause=e) from e

        except aiohttp.ClientError as e:
            logger.warning("HTTP error for %s: %s", url, e)
            raise HTTPClientError(f"HTTP error for {url}: {e}", url=url, cause=e) from e

    async def health_check(self, url: str, *, timeout: float = 5.0) -> bool:
        """Check if a URL is accessible.

        Performs a lightweight request to verify connectivity.

        Args:
            url: The URL to check
            timeout: Timeout for the health check

        Returns:
            True if the URL is accessible, False otherwise
        """
        try:
            response = await self.get(url, timeout=timeout)
            return response.is_success
        except HTTPClientError:
            return False

    def get_cookies(self, url: str) -> dict[str, str]:
        """Get cookies for a specific URL.

        Args:
            url: The URL to get cookies for

        Returns:
            Dictionary of cookie names to values
        """
        if self._cookie_jar is None or not self.config.enable_cookies:
            return {}

        from yarl import URL

        cookies = {}
        for cookie in self._cookie_jar:
            # Check if cookie applies to this URL
            cookie_url = URL(f"http://{cookie['domain']}")
            request_url = URL(url)
            if cookie_url.host and request_url.host:
                if request_url.host.endswith(cookie_url.host.lstrip(".")):
                    cookies[cookie.key] = cookie.value
        return cookies

    def clear_cookies(self) -> None:
        """Clear all stored cookies."""
        if self._cookie_jar is not None:
            self._cookie_jar.clear()
            logger.debug("Cleared all cookies")


# Pre-configured clients for common use cases
def create_nhl_api_client() -> HTTPClient:
    """Create an HTTP client configured for NHL JSON API.

    Returns:
        HTTPClient configured for api-web.nhle.com
    """
    config = HTTPClientConfig(
        timeout=30.0,
        user_agent="NHL-API-Client/1.0 (Research)",
        max_connections_per_host=5,
    )
    return HTTPClient(config)


def create_nhl_html_client() -> HTTPClient:
    """Create an HTTP client configured for NHL HTML reports.

    Returns:
        HTTPClient configured for www.nhl.com HTML reports
    """
    config = HTTPClientConfig(
        timeout=45.0,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36",
        max_connections_per_host=3,
        enable_cookies=True,
    )
    return HTTPClient(config)
