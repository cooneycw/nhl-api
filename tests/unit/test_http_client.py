"""Tests for the HTTP client utility."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from nhl_api.utils.http_client import (
    ConnectionError,
    ContentType,
    HTTPClient,
    HTTPClientConfig,
    HTTPClientError,
    HTTPResponse,
    TimeoutError,
    create_nhl_api_client,
    create_nhl_html_client,
)

if TYPE_CHECKING:
    pass


class TestHTTPClientConfig:
    """Tests for HTTPClientConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that default configuration values are set correctly."""
        config = HTTPClientConfig()

        assert config.timeout == 30.0
        assert config.connect_timeout == 10.0
        assert config.total_timeout == 300.0
        assert config.user_agent == "NHL-API-Client/1.0 (Research)"
        assert config.max_connections == 100
        assert config.max_connections_per_host == 10
        assert config.enable_cookies is True
        assert config.verify_ssl is True

    def test_custom_values(self) -> None:
        """Test creating config with custom values."""
        config = HTTPClientConfig(
            timeout=60.0,
            connect_timeout=15.0,
            user_agent="CustomAgent/2.0",
            max_connections=50,
            enable_cookies=False,
            verify_ssl=False,
        )

        assert config.timeout == 60.0
        assert config.connect_timeout == 15.0
        assert config.user_agent == "CustomAgent/2.0"
        assert config.max_connections == 50
        assert config.enable_cookies is False
        assert config.verify_ssl is False

    def test_config_is_immutable(self) -> None:
        """Test that HTTPClientConfig is frozen (immutable)."""
        config = HTTPClientConfig()

        with pytest.raises(AttributeError):
            config.timeout = 999.0  # type: ignore[misc]

    def test_default_headers_property(self) -> None:
        """Test that default_headers returns correct values."""
        config = HTTPClientConfig(user_agent="TestAgent/1.0")
        headers = config.default_headers

        assert headers["User-Agent"] == "TestAgent/1.0"
        assert "Accept" in headers
        assert "Accept-Encoding" in headers
        assert "Accept-Language" in headers


class TestContentType:
    """Tests for ContentType enum."""

    def test_content_type_values(self) -> None:
        """Verify all expected content type values exist."""
        assert ContentType.JSON.value == "application/json"
        assert ContentType.HTML.value == "text/html"
        assert ContentType.TEXT.value == "text/plain"
        assert ContentType.BINARY.value == "application/octet-stream"

    def test_content_type_count(self) -> None:
        """Verify the expected number of content types."""
        assert len(ContentType) == 4


class TestHTTPResponse:
    """Tests for HTTPResponse dataclass."""

    def test_basic_response(self) -> None:
        """Test creating a basic response."""
        response = HTTPResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            content=b'{"key": "value"}',
            url="https://example.com/api",
        )

        assert response.status == 200
        assert response.headers["Content-Type"] == "application/json"
        assert response.content == b'{"key": "value"}'
        assert response.url == "https://example.com/api"

    def test_json_parsing(self) -> None:
        """Test parsing response content as JSON."""
        response = HTTPResponse(
            status=200,
            headers={},
            content=b'{"name": "test", "value": 123}',
            url="https://example.com",
        )

        data = response.json()
        assert data == {"name": "test", "value": 123}

    def test_json_parsing_invalid(self) -> None:
        """Test that invalid JSON raises ValueError."""
        response = HTTPResponse(
            status=200,
            headers={},
            content=b"not valid json",
            url="https://example.com",
        )

        with pytest.raises(ValueError, match="Invalid JSON"):
            response.json()

    def test_text_method(self) -> None:
        """Test getting response content as text."""
        response = HTTPResponse(
            status=200,
            headers={},
            content=b"Hello, World!",
            url="https://example.com",
        )

        assert response.text() == "Hello, World!"

    def test_text_method_with_encoding(self) -> None:
        """Test text method with custom encoding."""
        response = HTTPResponse(
            status=200,
            headers={},
            content="Héllo".encode(),
            url="https://example.com",
        )

        assert response.text(encoding="utf-8") == "Héllo"

    def test_is_success_true(self) -> None:
        """Test is_success returns True for 2xx status."""
        for status in [200, 201, 204, 299]:
            response = HTTPResponse(
                status=status, headers={}, content=b"", url="https://example.com"
            )
            assert response.is_success, f"Expected True for status {status}"

    def test_is_success_false(self) -> None:
        """Test is_success returns False for non-2xx status."""
        for status in [199, 301, 400, 404, 500]:
            response = HTTPResponse(
                status=status, headers={}, content=b"", url="https://example.com"
            )
            assert not response.is_success, f"Expected False for status {status}"

    def test_is_rate_limited(self) -> None:
        """Test is_rate_limited property."""
        response_429 = HTTPResponse(
            status=429, headers={}, content=b"", url="https://example.com"
        )
        response_200 = HTTPResponse(
            status=200, headers={}, content=b"", url="https://example.com"
        )

        assert response_429.is_rate_limited
        assert not response_200.is_rate_limited

    def test_is_server_error(self) -> None:
        """Test is_server_error property."""
        for status in [500, 502, 503, 504, 599]:
            response = HTTPResponse(
                status=status, headers={}, content=b"", url="https://example.com"
            )
            assert response.is_server_error, f"Expected True for status {status}"

        for status in [200, 400, 404, 499]:
            response = HTTPResponse(
                status=status, headers={}, content=b"", url="https://example.com"
            )
            assert not response.is_server_error, f"Expected False for status {status}"

    def test_is_client_error(self) -> None:
        """Test is_client_error property."""
        for status in [400, 401, 403, 404, 422, 499]:
            response = HTTPResponse(
                status=status, headers={}, content=b"", url="https://example.com"
            )
            assert response.is_client_error, f"Expected True for status {status}"

        for status in [200, 301, 399, 500]:
            response = HTTPResponse(
                status=status, headers={}, content=b"", url="https://example.com"
            )
            assert not response.is_client_error, f"Expected False for status {status}"

    def test_retry_after_present(self) -> None:
        """Test retry_after when header is present."""
        response = HTTPResponse(
            status=429,
            headers={"Retry-After": "30"},
            content=b"",
            url="https://example.com",
        )

        assert response.retry_after == 30.0

    def test_retry_after_missing(self) -> None:
        """Test retry_after when header is missing."""
        response = HTTPResponse(
            status=429, headers={}, content=b"", url="https://example.com"
        )

        assert response.retry_after is None

    def test_retry_after_invalid(self) -> None:
        """Test retry_after with invalid header value."""
        response = HTTPResponse(
            status=429,
            headers={"Retry-After": "not-a-number"},
            content=b"",
            url="https://example.com",
        )

        assert response.retry_after is None

    def test_detect_content_type_json(self) -> None:
        """Test content type detection for JSON."""
        content_type = HTTPResponse._detect_content_type(
            "application/json; charset=utf-8"
        )
        assert content_type == ContentType.JSON

    def test_detect_content_type_html(self) -> None:
        """Test content type detection for HTML."""
        content_type = HTTPResponse._detect_content_type("text/html")
        assert content_type == ContentType.HTML

    def test_detect_content_type_text(self) -> None:
        """Test content type detection for plain text."""
        content_type = HTTPResponse._detect_content_type("text/plain")
        assert content_type == ContentType.TEXT

    def test_detect_content_type_binary(self) -> None:
        """Test content type detection for unknown types."""
        content_type = HTTPResponse._detect_content_type("application/pdf")
        assert content_type == ContentType.BINARY


class TestHTTPClientErrors:
    """Tests for HTTP client exception classes."""

    def test_http_client_error_basic(self) -> None:
        """Test basic HTTPClientError creation."""
        error = HTTPClientError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.url is None
        assert error.cause is None

    def test_http_client_error_with_context(self) -> None:
        """Test HTTPClientError with full context."""
        cause = ValueError("Original error")
        error = HTTPClientError(
            "Failed to fetch",
            url="https://example.com",
            cause=cause,
        )

        assert "Failed to fetch" in str(error)
        assert error.url == "https://example.com"
        assert error.cause is cause

    def test_connection_error_inheritance(self) -> None:
        """Test that ConnectionError inherits from HTTPClientError."""
        error = ConnectionError("Connection refused")
        assert isinstance(error, HTTPClientError)

    def test_timeout_error_inheritance(self) -> None:
        """Test that TimeoutError inherits from HTTPClientError."""
        error = TimeoutError("Request timed out")
        assert isinstance(error, HTTPClientError)


@pytest.mark.asyncio
class TestHTTPClient:
    """Tests for HTTPClient class."""

    async def test_client_context_manager(self) -> None:
        """Test that client works as async context manager."""
        async with HTTPClient() as client:
            assert client.is_open

        assert not client.is_open

    async def test_client_with_custom_config(self) -> None:
        """Test creating client with custom configuration."""
        config = HTTPClientConfig(timeout=60.0, max_connections=50)
        async with HTTPClient(config) as client:
            assert client.config.timeout == 60.0
            assert client.config.max_connections == 50

    async def test_client_close_is_idempotent(self) -> None:
        """Test that calling close multiple times is safe."""
        client = HTTPClient()
        await client._create_session()
        assert client.is_open

        await client.close()
        assert not client.is_open

        # Should not raise
        await client.close()
        assert not client.is_open

    async def test_get_request_success(self) -> None:
        """Test successful GET request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.url = "https://api.example.com/data"
        mock_response.read = AsyncMock(return_value=b'{"result": "success"}')

        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            async with HTTPClient() as client:
                response = await client.get("https://api.example.com/data")

            assert response.status == 200
            assert response.json() == {"result": "success"}

    async def test_get_request_with_params(self) -> None:
        """Test GET request with query parameters."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.url = "https://api.example.com/search?q=test"
        mock_response.read = AsyncMock(return_value=b"{}")

        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            async with HTTPClient() as client:
                await client.get(
                    "https://api.example.com/search",
                    params={"q": "test"},
                )

            # Verify params were passed
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["params"] == {"q": "test"}

    async def test_get_request_with_custom_headers(self) -> None:
        """Test GET request with custom headers."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.url = "https://api.example.com/data"
        mock_response.read = AsyncMock(return_value=b"{}")

        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            async with HTTPClient() as client:
                await client.get(
                    "https://api.example.com/data",
                    headers={"X-Custom-Header": "value"},
                )

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["headers"]["X-Custom-Header"] == "value"

    async def test_post_request_with_json(self) -> None:
        """Test POST request with JSON body."""
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.url = "https://api.example.com/create"
        mock_response.read = AsyncMock(return_value=b'{"id": 123}')

        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            async with HTTPClient() as client:
                response = await client.post(
                    "https://api.example.com/create",
                    json={"name": "test"},
                )

            assert response.status == 201
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["json"] == {"name": "test"}

    async def test_post_request_with_data(self) -> None:
        """Test POST request with raw data."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.url = "https://api.example.com/upload"
        mock_response.read = AsyncMock(return_value=b"OK")

        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            async with HTTPClient() as client:
                await client.post(
                    "https://api.example.com/upload",
                    data=b"raw data",
                )

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["data"] == b"raw data"

    async def test_connection_error_handling(self) -> None:
        """Test that connection errors are properly wrapped."""
        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.side_effect = (
                aiohttp.ClientConnectorError(
                    connection_key=MagicMock(), os_error=OSError("Connection refused")
                )
            )

            async with HTTPClient() as client:
                with pytest.raises(ConnectionError) as exc_info:
                    await client.get("https://api.example.com/data")

                assert exc_info.value.url == "https://api.example.com/data"

    async def test_timeout_error_handling(self) -> None:
        """Test that timeout errors are properly wrapped."""
        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.side_effect = (
                aiohttp.ServerTimeoutError("Request timed out")
            )

            async with HTTPClient() as client:
                with pytest.raises(TimeoutError) as exc_info:
                    await client.get("https://api.example.com/data")

                assert exc_info.value.url == "https://api.example.com/data"

    async def test_generic_client_error_handling(self) -> None:
        """Test that generic client errors are properly wrapped."""
        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.side_effect = aiohttp.ClientError(
                "Generic error"
            )

            async with HTTPClient() as client:
                with pytest.raises(HTTPClientError):
                    await client.get("https://api.example.com/data")

    async def test_health_check_success(self) -> None:
        """Test health check returns True on success."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.url = "https://api.example.com/health"
        mock_response.read = AsyncMock(return_value=b"OK")

        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            async with HTTPClient() as client:
                result = await client.health_check("https://api.example.com/health")

            assert result is True

    async def test_health_check_failure(self) -> None:
        """Test health check returns False on error."""
        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.side_effect = (
                aiohttp.ClientConnectorError(
                    connection_key=MagicMock(), os_error=OSError("Connection refused")
                )
            )

            async with HTTPClient() as client:
                result = await client.health_check("https://api.example.com/health")

            assert result is False

    async def test_health_check_non_success_status(self) -> None:
        """Test health check returns False on non-2xx status."""
        mock_response = AsyncMock()
        mock_response.status = 503
        mock_response.headers = {}
        mock_response.url = "https://api.example.com/health"
        mock_response.read = AsyncMock(return_value=b"Service Unavailable")

        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            async with HTTPClient() as client:
                result = await client.health_check("https://api.example.com/health")

            assert result is False

    async def test_custom_timeout_per_request(self) -> None:
        """Test that per-request timeout override works."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.url = "https://api.example.com/slow"
        mock_response.read = AsyncMock(return_value=b"{}")

        with patch.object(aiohttp.ClientSession, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response

            async with HTTPClient() as client:
                await client.get("https://api.example.com/slow", timeout=120.0)

            call_kwargs = mock_request.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"].total == 120.0

    async def test_clear_cookies(self) -> None:
        """Test clearing cookies."""
        async with HTTPClient() as client:
            # Should not raise
            client.clear_cookies()

    async def test_get_cookies_no_cookies(self) -> None:
        """Test getting cookies when none exist."""
        async with HTTPClient() as client:
            cookies = client.get_cookies("https://example.com")
            assert cookies == {}


class TestFactoryFunctions:
    """Tests for HTTP client factory functions."""

    def test_create_nhl_api_client(self) -> None:
        """Test creating NHL API client with correct configuration."""
        client = create_nhl_api_client()

        assert client.config.timeout == 30.0
        assert client.config.max_connections_per_host == 5
        assert "NHL-API-Client" in client.config.user_agent

    def test_create_nhl_html_client(self) -> None:
        """Test creating NHL HTML client with correct configuration."""
        client = create_nhl_html_client()

        assert client.config.timeout == 45.0
        assert client.config.max_connections_per_host == 3
        assert client.config.enable_cookies is True
        assert "Mozilla" in client.config.user_agent


@pytest.mark.asyncio
class TestHTTPResponseFromAiohttp:
    """Tests for HTTPResponse.from_aiohttp_response class method."""

    async def test_from_aiohttp_response(self) -> None:
        """Test creating HTTPResponse from aiohttp response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {
            "Content-Type": "application/json",
            "X-Custom": "value",
        }
        mock_response.url = "https://example.com/api"
        mock_response.read = AsyncMock(return_value=b'{"key": "value"}')

        response = await HTTPResponse.from_aiohttp_response(mock_response)

        assert response.status == 200
        assert response.headers["Content-Type"] == "application/json"
        assert response.headers["X-Custom"] == "value"
        assert response.url == "https://example.com/api"
        assert response.content == b'{"key": "value"}'
        assert response.content_type == ContentType.JSON

    async def test_from_aiohttp_response_html(self) -> None:
        """Test creating HTTPResponse from HTML aiohttp response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.url = "https://example.com/page"
        mock_response.read = AsyncMock(return_value=b"<html></html>")

        response = await HTTPResponse.from_aiohttp_response(mock_response)

        assert response.content_type == ContentType.HTML
