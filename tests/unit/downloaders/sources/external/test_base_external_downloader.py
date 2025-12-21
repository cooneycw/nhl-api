"""Unit tests for BaseExternalDownloader.

Tests cover:
- Configuration and initialization
- Header setup and User-Agent
- Response validation
- Request methods with rate limiting
- Fetch resource flow
- Error handling
- Exception classes
- Default method behavior
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.external.base_external_downloader import (
    DEFAULT_EXTERNAL_RATE_LIMIT,
    DEFAULT_USER_AGENT,
    EXTERNAL_DOWNLOADER_CONFIG,
    BaseExternalDownloader,
    ContentParsingError,
    ExternalDownloaderConfig,
    ExternalSourceError,
    ValidationError,
)
from nhl_api.utils.http_client import HTTPResponse

# =============================================================================
# Test Fixtures
# =============================================================================


class ConcreteExternalDownloader(BaseExternalDownloader):
    """Concrete implementation for testing abstract base class."""

    @property
    def source_name(self) -> str:
        return "test_external"

    async def _parse_response(
        self,
        response: HTTPResponse,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Simple parser for testing."""
        content = response.content.decode("utf-8") if response.content else ""
        return {
            "content_length": len(content),
            "url": context.get("url", ""),
            "parsed": True,
        }


class FailingParser(BaseExternalDownloader):
    """Downloader that fails during parsing."""

    @property
    def source_name(self) -> str:
        return "failing_parser"

    async def _parse_response(
        self,
        response: HTTPResponse,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Parser that always fails."""
        raise ValueError("Parsing failed intentionally")


@pytest.fixture
def config() -> ExternalDownloaderConfig:
    """Create test configuration."""
    return ExternalDownloaderConfig(
        base_url="https://example.com",
        requests_per_second=10.0,  # Fast for testing
        max_retries=2,
        http_timeout=5.0,
        store_raw_response=True,
    )


@pytest.fixture
def downloader(config: ExternalDownloaderConfig) -> ConcreteExternalDownloader:
    """Create test downloader instance."""
    return ConcreteExternalDownloader(config)


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create mock HTTP client."""
    client = MagicMock()
    client._create_session = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_response() -> MagicMock:
    """Create mock HTTP response."""
    response = MagicMock(spec=HTTPResponse)
    response.is_success = True
    response.is_rate_limited = False
    response.is_server_error = False
    response.status = 200
    response.content = b"<html><body>Test content</body></html>"
    response.retry_after = None
    return response


@pytest.fixture
def empty_response() -> MagicMock:
    """Create mock HTTP response with empty content."""
    response = MagicMock(spec=HTTPResponse)
    response.is_success = True
    response.is_rate_limited = False
    response.is_server_error = False
    response.status = 200
    response.content = b""
    response.retry_after = None
    return response


# =============================================================================
# Configuration Tests
# =============================================================================


class TestExternalDownloaderConfig:
    """Tests for ExternalDownloaderConfig."""

    def test_default_config_values(self) -> None:
        """Test default configuration values are conservative."""
        config = ExternalDownloaderConfig()
        assert config.base_url == ""
        assert config.requests_per_second == DEFAULT_EXTERNAL_RATE_LIMIT
        assert config.requests_per_second == 0.5
        assert config.max_retries == 3
        assert config.retry_base_delay == 2.0
        assert config.http_timeout == 45.0
        assert config.user_agent == DEFAULT_USER_AGENT
        assert config.custom_headers == {}
        assert config.store_raw_response is True
        assert config.validate_response is True
        assert config.require_content is True

    def test_custom_config_values(self) -> None:
        """Test custom configuration values."""
        custom_headers = {"X-Custom": "value"}
        config = ExternalDownloaderConfig(
            base_url="https://custom.example.com",
            requests_per_second=1.0,
            max_retries=5,
            retry_base_delay=3.0,
            http_timeout=60.0,
            user_agent="Custom-Agent/1.0",
            custom_headers=custom_headers,
            store_raw_response=False,
            validate_response=False,
            require_content=False,
        )
        assert config.base_url == "https://custom.example.com"
        assert config.requests_per_second == 1.0
        assert config.max_retries == 5
        assert config.retry_base_delay == 3.0
        assert config.http_timeout == 60.0
        assert config.user_agent == "Custom-Agent/1.0"
        assert config.custom_headers == custom_headers
        assert config.store_raw_response is False
        assert config.validate_response is False
        assert config.require_content is False

    def test_default_config_instance(self) -> None:
        """Test the default config singleton."""
        assert EXTERNAL_DOWNLOADER_CONFIG.base_url == ""
        assert EXTERNAL_DOWNLOADER_CONFIG.requests_per_second == 0.5
        assert EXTERNAL_DOWNLOADER_CONFIG.user_agent == DEFAULT_USER_AGENT

    def test_rate_limit_more_conservative_than_base(self) -> None:
        """Test that default rate limit is more conservative than BaseDownloader."""
        # BaseDownloader uses 5.0, we should use 0.5
        config = ExternalDownloaderConfig()
        assert config.requests_per_second < 5.0
        assert config.requests_per_second == 0.5

    def test_config_inherits_from_downloader_config(self) -> None:
        """Test that config inherits base DownloaderConfig fields."""
        config = ExternalDownloaderConfig(base_url="https://test.com")
        # These are inherited from DownloaderConfig
        assert hasattr(config, "base_url")
        assert hasattr(config, "requests_per_second")
        assert hasattr(config, "max_retries")
        assert hasattr(config, "retry_base_delay")
        assert hasattr(config, "http_timeout")
        assert hasattr(config, "health_check_url")


# =============================================================================
# Initialization Tests
# =============================================================================


class TestBaseExternalDownloaderInit:
    """Tests for BaseExternalDownloader initialization."""

    def test_source_name_property(self, downloader: ConcreteExternalDownloader) -> None:
        """Test source_name property is required."""
        assert downloader.source_name == "test_external"

    def test_source_category_default(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test source_category is derived from source_name."""
        assert downloader.source_category == "test"

    def test_source_category_with_multiple_underscores(
        self, config: ExternalDownloaderConfig
    ) -> None:
        """Test source_category with complex source_name."""

        class MultiUnderscoreDownloader(BaseExternalDownloader):
            @property
            def source_name(self) -> str:
                return "quanthockey_season_stats"

            async def _parse_response(
                self, response: HTTPResponse, context: dict[str, Any]
            ) -> dict[str, Any]:
                return {}

        downloader = MultiUnderscoreDownloader(config)
        assert downloader.source_category == "quanthockey"

    def test_init_with_default_config(self) -> None:
        """Test initialization with default config."""
        downloader = ConcreteExternalDownloader()
        assert downloader.config.base_url == ""
        assert downloader.config.requests_per_second == 0.5

    def test_init_stores_raw_response_setting(
        self, config: ExternalDownloaderConfig
    ) -> None:
        """Test that store_raw_response setting is captured."""
        downloader = ConcreteExternalDownloader(config)
        assert downloader._store_raw is True

        config_no_raw = ExternalDownloaderConfig(
            base_url="https://example.com",
            store_raw_response=False,
        )
        downloader_no_raw = ConcreteExternalDownloader(config_no_raw)
        assert downloader_no_raw._store_raw is False


# =============================================================================
# Header Tests
# =============================================================================


class TestHeaders:
    """Tests for HTTP header handling."""

    def test_get_headers_includes_user_agent(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test that User-Agent is included in headers."""
        headers = downloader._get_headers()
        assert "User-Agent" in headers
        assert headers["User-Agent"] == downloader.config.user_agent

    def test_get_headers_includes_accept(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test that Accept header is included."""
        headers = downloader._get_headers()
        assert "Accept" in headers
        assert "text/html" in headers["Accept"]

    def test_get_headers_includes_accept_language(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test that Accept-Language header is included."""
        headers = downloader._get_headers()
        assert "Accept-Language" in headers
        assert "en-US" in headers["Accept-Language"]

    def test_get_headers_merges_custom_headers(self) -> None:
        """Test that custom headers are merged."""
        config = ExternalDownloaderConfig(
            base_url="https://example.com",
            custom_headers={"X-Custom": "test-value", "X-Api-Key": "secret"},
        )
        downloader = ConcreteExternalDownloader(config)
        headers = downloader._get_headers()
        assert headers["X-Custom"] == "test-value"
        assert headers["X-Api-Key"] == "secret"
        # Standard headers should still be present
        assert "User-Agent" in headers

    def test_custom_headers_override_defaults(self) -> None:
        """Test that custom headers can override defaults."""
        config = ExternalDownloaderConfig(
            base_url="https://example.com",
            custom_headers={"Accept": "application/json"},
        )
        downloader = ConcreteExternalDownloader(config)
        headers = downloader._get_headers()
        assert headers["Accept"] == "application/json"


# =============================================================================
# Response Validation Tests
# =============================================================================


@pytest.mark.asyncio
class TestResponseValidation:
    """Tests for response validation."""

    async def test_validate_success_response(
        self, downloader: ConcreteExternalDownloader, mock_response: MagicMock
    ) -> None:
        """Test validation passes for 2xx responses with content."""
        result = await downloader._validate_response(mock_response)
        assert result is True

    async def test_validate_rejects_failed_status(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test validation fails for non-2xx responses."""
        response = MagicMock(spec=HTTPResponse)
        response.is_success = False
        response.status = 404
        response.content = b"Not Found"

        with pytest.raises(ValidationError) as exc_info:
            await downloader._validate_response(response)

        assert exc_info.value.response_status == 404
        assert "404" in str(exc_info.value)

    async def test_validate_rejects_empty_content(
        self, downloader: ConcreteExternalDownloader, empty_response: MagicMock
    ) -> None:
        """Test validation fails for empty response when require_content=True."""
        with pytest.raises(ValidationError) as exc_info:
            await downloader._validate_response(empty_response)

        assert "empty" in str(exc_info.value).lower()

    async def test_validate_allows_empty_when_disabled(
        self, empty_response: MagicMock
    ) -> None:
        """Test empty content allowed when require_content=False."""
        config = ExternalDownloaderConfig(
            base_url="https://example.com",
            require_content=False,
        )
        downloader = ConcreteExternalDownloader(config)
        result = await downloader._validate_response(empty_response)
        assert result is True

    async def test_validate_skipped_when_disabled(
        self,
    ) -> None:
        """Test validation is skipped when validate_response=False."""
        config = ExternalDownloaderConfig(
            base_url="https://example.com",
            validate_response=False,
        )
        downloader = ConcreteExternalDownloader(config)

        # Even a failed response should pass
        response = MagicMock(spec=HTTPResponse)
        response.is_success = False
        response.status = 500
        response.content = b""

        result = await downloader._validate_response(response)
        assert result is True


# =============================================================================
# Fetch Resource Tests
# =============================================================================


@pytest.mark.asyncio
class TestFetchResource:
    """Tests for fetch_resource method."""

    async def test_fetch_resource_success(
        self,
        downloader: ConcreteExternalDownloader,
        mock_http_client: MagicMock,
        mock_response: MagicMock,
    ) -> None:
        """Test successful resource fetch."""
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch.object(downloader, "_http_client", mock_http_client):
            with patch.object(downloader._rate_limiter, "wait", AsyncMock()):
                result = await downloader.fetch_resource("/test/path")

        assert result.status == DownloadStatus.COMPLETED
        assert result.is_successful
        assert result.source == "test_external"
        assert result.data["parsed"] is True

    async def test_fetch_resource_stores_raw_content(
        self,
        downloader: ConcreteExternalDownloader,
        mock_http_client: MagicMock,
        mock_response: MagicMock,
    ) -> None:
        """Test raw content is stored when configured."""
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch.object(downloader, "_http_client", mock_http_client):
            with patch.object(downloader._rate_limiter, "wait", AsyncMock()):
                result = await downloader.fetch_resource("/test/path")

        assert result.raw_content is not None
        assert result.raw_content == mock_response.content
        assert downloader.last_raw_content == mock_response.content

    async def test_fetch_resource_with_context(
        self,
        downloader: ConcreteExternalDownloader,
        mock_http_client: MagicMock,
        mock_response: MagicMock,
    ) -> None:
        """Test fetch with custom context."""
        mock_http_client.get = AsyncMock(return_value=mock_response)
        context = {"season_id": 20242025, "game_id": 2024020001}

        with patch.object(downloader, "_http_client", mock_http_client):
            with patch.object(downloader._rate_limiter, "wait", AsyncMock()):
                result = await downloader.fetch_resource("/test/path", context=context)

        assert result.season_id == 20242025
        assert result.game_id == 2024020001

    async def test_fetch_resource_validation_failure(
        self,
        downloader: ConcreteExternalDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetch fails on validation error."""
        failed_response = MagicMock(spec=HTTPResponse)
        failed_response.is_success = False
        failed_response.is_rate_limited = False
        failed_response.is_server_error = False
        failed_response.status = 404
        failed_response.content = b"Not Found"

        mock_http_client.get = AsyncMock(return_value=failed_response)

        with patch.object(downloader, "_http_client", mock_http_client):
            with patch.object(downloader._rate_limiter, "wait", AsyncMock()):
                with pytest.raises(ValidationError):
                    await downloader.fetch_resource("/not/found")

    async def test_fetch_resource_parse_error(
        self,
        mock_http_client: MagicMock,
        mock_response: MagicMock,
    ) -> None:
        """Test fetch fails on parse error."""
        config = ExternalDownloaderConfig(base_url="https://example.com")
        downloader = FailingParser(config)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch.object(downloader, "_http_client", mock_http_client):
            with patch.object(downloader._rate_limiter, "wait", AsyncMock()):
                with pytest.raises(ContentParsingError) as exc_info:
                    await downloader.fetch_resource("/test/path")

        assert "Parsing failed" in str(exc_info.value.cause)


# =============================================================================
# Default Method Behavior Tests
# =============================================================================


@pytest.mark.asyncio
class TestDefaultMethodBehavior:
    """Tests for default implementations of base methods."""

    async def test_fetch_game_raises_not_implemented(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test _fetch_game raises NotImplementedError by default."""
        with pytest.raises(NotImplementedError) as exc_info:
            await downloader._fetch_game(2024020001)

        assert "test_external" in str(exc_info.value)
        assert "game-based downloads" in str(exc_info.value)

    async def test_fetch_season_games_yields_nothing(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test _fetch_season_games yields empty by default."""
        game_ids = []
        async for game_id in downloader._fetch_season_games(20242025):
            game_ids.append(game_id)

        assert game_ids == []


# =============================================================================
# Exception Tests
# =============================================================================


class TestExternalSourceErrors:
    """Tests for custom exception classes."""

    def test_external_source_error_includes_url(self) -> None:
        """Test ExternalSourceError includes URL."""
        error = ExternalSourceError(
            "Test error",
            source="test_source",
            url="https://example.com/page",
        )
        assert error.url == "https://example.com/page"
        assert "test_source" in str(error)
        assert "url=https://example.com/page" in str(error)

    def test_external_source_error_without_url(self) -> None:
        """Test ExternalSourceError without URL."""
        error = ExternalSourceError("Test error", source="test_source")
        assert error.url is None
        assert "test_source" in str(error)
        assert "url=" not in str(error)

    def test_validation_error_attributes(self) -> None:
        """Test ValidationError includes status and content_type."""
        error = ValidationError(
            "Validation failed",
            response_status=404,
            content_type="text/html",
            source="test_source",
        )
        assert error.response_status == 404
        assert error.content_type == "text/html"
        assert error.source == "test_source"

    def test_validation_error_inherits_from_external_source_error(self) -> None:
        """Test ValidationError is an ExternalSourceError."""
        error = ValidationError("Test")
        assert isinstance(error, ExternalSourceError)

    def test_content_parsing_error(self) -> None:
        """Test ContentParsingError for parse failures."""
        cause = ValueError("Invalid JSON")
        error = ContentParsingError(
            "Failed to parse response",
            source="test_source",
            url="https://example.com/api",
            cause=cause,
        )
        assert error.source == "test_source"
        assert error.url == "https://example.com/api"
        assert error.cause == cause

    def test_content_parsing_error_inherits_from_external_source_error(self) -> None:
        """Test ContentParsingError is an ExternalSourceError."""
        error = ContentParsingError("Test")
        assert isinstance(error, ExternalSourceError)


# =============================================================================
# URL Building Tests
# =============================================================================


class TestURLBuilding:
    """Tests for URL building."""

    def test_build_url_simple_path(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test URL building with simple path."""
        url = downloader._build_url("/stats/page")
        assert url == "https://example.com/stats/page"

    def test_build_url_handles_trailing_slash(self) -> None:
        """Test URL building handles trailing slash in base_url."""
        config = ExternalDownloaderConfig(base_url="https://example.com/")
        downloader = ConcreteExternalDownloader(config)
        url = downloader._build_url("/stats/page")
        assert url == "https://example.com/stats/page"

    def test_build_url_handles_no_leading_slash(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test URL building handles path without leading slash."""
        url = downloader._build_url("stats/page")
        assert url == "https://example.com/stats/page"


# =============================================================================
# Utility Tests
# =============================================================================


class TestUtilities:
    """Tests for utility methods."""

    def test_last_raw_content_initially_none(
        self, downloader: ConcreteExternalDownloader
    ) -> None:
        """Test last_raw_content is None initially."""
        assert downloader.last_raw_content is None

    @pytest.mark.asyncio
    async def test_last_raw_content_after_fetch(
        self,
        downloader: ConcreteExternalDownloader,
        mock_http_client: MagicMock,
        mock_response: MagicMock,
    ) -> None:
        """Test last_raw_content is set after fetch."""
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch.object(downloader, "_http_client", mock_http_client):
            with patch.object(downloader._rate_limiter, "wait", AsyncMock()):
                await downloader.fetch_resource("/test")

        assert downloader.last_raw_content == mock_response.content


# =============================================================================
# Integration-Like Tests
# =============================================================================


@pytest.mark.asyncio
class TestFetchPage:
    """Tests for fetch_page method."""

    async def test_fetch_page_returns_response_and_content(
        self,
        downloader: ConcreteExternalDownloader,
        mock_http_client: MagicMock,
        mock_response: MagicMock,
    ) -> None:
        """Test fetch_page returns both response and content."""
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch.object(downloader, "_http_client", mock_http_client):
            with patch.object(downloader._rate_limiter, "wait", AsyncMock()):
                response, content = await downloader.fetch_page("/test")

        assert response == mock_response
        assert content == mock_response.content

    async def test_fetch_page_without_validation(
        self,
        downloader: ConcreteExternalDownloader,
        mock_http_client: MagicMock,
    ) -> None:
        """Test fetch_page can skip validation."""
        failed_response = MagicMock(spec=HTTPResponse)
        failed_response.is_success = False
        failed_response.is_rate_limited = False
        failed_response.is_server_error = False
        failed_response.status = 404
        failed_response.content = b"Not Found"

        mock_http_client.get = AsyncMock(return_value=failed_response)

        with patch.object(downloader, "_http_client", mock_http_client):
            with patch.object(downloader._rate_limiter, "wait", AsyncMock()):
                # Should not raise because validate=False
                response, content = await downloader.fetch_page(
                    "/not/found", validate=False
                )

        assert response.status == 404
