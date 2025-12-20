"""Tests for the BaseDownloader abstract class."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
    DownloadProgress,
)
from nhl_api.downloaders.base.protocol import (
    DownloadError,
    DownloadStatus,
    HealthCheckError,
)
from nhl_api.downloaders.base.rate_limiter import RateLimiter
from nhl_api.downloaders.base.retry_handler import RetryHandler
from nhl_api.utils.http_client import HTTPClient, HTTPResponse


class TestDownloaderConfig:
    """Tests for DownloaderConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = DownloaderConfig(base_url="https://api.example.com")

        assert config.base_url == "https://api.example.com"
        assert config.requests_per_second == 5.0
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.http_timeout == 30.0
        assert config.health_check_url == ""

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = DownloaderConfig(
            base_url="https://custom.api.com",
            requests_per_second=10.0,
            max_retries=5,
            retry_base_delay=2.0,
            http_timeout=60.0,
            health_check_url="/health",
        )

        assert config.base_url == "https://custom.api.com"
        assert config.requests_per_second == 10.0
        assert config.max_retries == 5
        assert config.retry_base_delay == 2.0
        assert config.http_timeout == 60.0
        assert config.health_check_url == "/health"


class TestDownloadProgress:
    """Tests for DownloadProgress dataclass."""

    def test_initial_state(self) -> None:
        """Test initial progress state."""
        progress = DownloadProgress(source="test_source")

        assert progress.source == "test_source"
        assert progress.total_items is None
        assert progress.completed_items == 0
        assert progress.failed_items == 0
        assert progress.skipped_items == 0
        assert progress.current_game_id is None
        assert progress.errors == []
        assert progress.processed_items == 0
        assert progress.success_rate == 0.0
        assert not progress.is_complete

    def test_processed_items(self) -> None:
        """Test processed_items calculation."""
        progress = DownloadProgress(
            source="test",
            completed_items=5,
            failed_items=2,
            skipped_items=3,
        )

        assert progress.processed_items == 10

    def test_success_rate(self) -> None:
        """Test success rate calculation."""
        progress = DownloadProgress(
            source="test",
            completed_items=8,
            failed_items=2,
        )

        assert progress.success_rate == 80.0

    def test_success_rate_no_items(self) -> None:
        """Test success rate with no processed items."""
        progress = DownloadProgress(source="test")
        assert progress.success_rate == 0.0

    def test_is_complete(self) -> None:
        """Test is_complete property."""
        # Not complete when total is None
        progress = DownloadProgress(source="test", completed_items=5)
        assert not progress.is_complete

        # Not complete when processed < total
        progress = DownloadProgress(
            source="test",
            total_items=10,
            completed_items=5,
        )
        assert not progress.is_complete

        # Complete when processed >= total
        progress = DownloadProgress(
            source="test",
            total_items=10,
            completed_items=10,
        )
        assert progress.is_complete

    def test_started_at_default(self) -> None:
        """Test that started_at defaults to current time."""
        before = datetime.now(UTC)
        progress = DownloadProgress(source="test")
        after = datetime.now(UTC)

        assert before <= progress.started_at <= after


class ConcreteDownloader(BaseDownloader):
    """Concrete implementation for testing."""

    def __init__(
        self,
        config: DownloaderConfig,
        game_data: dict[int, dict[str, Any]] | None = None,
        season_games: list[int] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._game_data = game_data or {}
        self._season_games = season_games or []

    @property
    def source_name(self) -> str:
        return "test_source"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        if game_id in self._game_data:
            return self._game_data[game_id]
        raise DownloadError(
            f"Game {game_id} not found",
            source=self.source_name,
            game_id=game_id,
        )

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        for game_id in self._season_games:
            yield game_id


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create a mock HTTP client."""
    client = AsyncMock(spec=HTTPClient)
    client._create_session = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_rate_limiter() -> MagicMock:
    """Create a mock rate limiter."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.wait = AsyncMock(return_value=0.0)
    return limiter


@pytest.fixture
def mock_retry_handler() -> MagicMock:
    """Create a mock retry handler."""
    handler = MagicMock(spec=RetryHandler)

    async def execute_passthrough(
        operation: Any, operation_name: str = "", source: str | None = None
    ) -> Any:
        return await operation()

    handler.execute = AsyncMock(side_effect=execute_passthrough)
    return handler


@pytest.fixture
def downloader_config() -> DownloaderConfig:
    """Create a test downloader config."""
    return DownloaderConfig(
        base_url="https://api.test.com",
        requests_per_second=10.0,
        max_retries=2,
        health_check_url="/health",
    )


class TestBaseDownloaderInit:
    """Tests for BaseDownloader initialization."""

    def test_initialization(self, downloader_config: DownloaderConfig) -> None:
        """Test basic initialization."""
        downloader = ConcreteDownloader(downloader_config)

        assert downloader.config == downloader_config
        assert downloader.source_name == "test_source"
        assert downloader._http_client is None
        assert downloader._owns_http_client is True
        assert isinstance(downloader._rate_limiter, RateLimiter)
        assert isinstance(downloader._retry_handler, RetryHandler)

    def test_initialization_with_custom_components(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test initialization with custom components."""
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        assert downloader._http_client is mock_http_client
        assert downloader._owns_http_client is False
        assert downloader._rate_limiter is mock_rate_limiter
        assert downloader._retry_handler is mock_retry_handler

    def test_initialization_with_progress_callback(
        self, downloader_config: DownloaderConfig
    ) -> None:
        """Test initialization with progress callback."""
        callback = MagicMock()
        downloader = ConcreteDownloader(
            downloader_config,
            progress_callback=callback,
        )

        assert downloader._progress_callback is callback


@pytest.mark.asyncio
class TestBaseDownloaderContext:
    """Tests for BaseDownloader context manager."""

    async def test_context_creates_client(
        self, downloader_config: DownloaderConfig
    ) -> None:
        """Test that context manager creates HTTP client."""
        downloader = ConcreteDownloader(downloader_config)

        with patch.object(HTTPClient, "_create_session", new_callable=AsyncMock):
            async with downloader:
                assert downloader._http_client is not None

    async def test_context_closes_owned_client(
        self, downloader_config: DownloaderConfig
    ) -> None:
        """Test that context manager closes owned HTTP client."""
        downloader = ConcreteDownloader(downloader_config)

        with patch.object(HTTPClient, "_create_session", new_callable=AsyncMock):
            with patch.object(
                HTTPClient, "close", new_callable=AsyncMock
            ) as mock_close:
                async with downloader:
                    pass
                mock_close.assert_called_once()

    async def test_context_does_not_close_external_client(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test that external HTTP client is not closed."""
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
        )

        async with downloader:
            pass

        mock_http_client.close.assert_not_called()


@pytest.mark.asyncio
class TestBaseDownloaderDownloadGame:
    """Tests for BaseDownloader.download_game."""

    async def test_download_game_success(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful game download."""
        game_data = {"homeTeam": {"score": 3}, "awayTeam": {"score": 2}}
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            game_data={2024020001: game_data},
        )

        async with downloader:
            result = await downloader.download_game(2024020001)

        assert result.is_successful
        assert result.game_id == 2024020001
        assert result.source == "test_source"
        assert result.data == game_data
        assert result.status == DownloadStatus.COMPLETED

    async def test_download_game_extracts_season_id(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test that season ID is extracted from game ID."""
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            game_data={2024020001: {}},
        )

        async with downloader:
            result = await downloader.download_game(2024020001)

        # 2024020001 -> season 2024 -> season_id 20242025
        assert result.season_id == 20242025

    async def test_download_game_failure(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test game download failure."""
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            game_data={},  # No data for any game
        )

        async with downloader:
            with pytest.raises(DownloadError) as exc_info:
                await downloader.download_game(2024020001)

        assert exc_info.value.game_id == 2024020001
        assert exc_info.value.source == "test_source"


@pytest.mark.asyncio
class TestBaseDownloaderDownloadSeason:
    """Tests for BaseDownloader.download_season."""

    async def test_download_season_success(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful season download."""
        game_data = {
            2024020001: {"game": 1},
            2024020002: {"game": 2},
            2024020003: {"game": 3},
        }
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            game_data=game_data,
            season_games=[2024020001, 2024020002, 2024020003],
        )

        async with downloader:
            results = [r async for r in downloader.download_season(20242025)]

        assert len(results) == 3
        assert all(r.is_successful for r in results)
        assert [r.game_id for r in results] == [2024020001, 2024020002, 2024020003]

    async def test_download_season_with_failures(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test season download with some failures."""
        game_data = {
            2024020001: {"game": 1},
            # 2024020002 is missing (will fail)
            2024020003: {"game": 3},
        }
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            game_data=game_data,
            season_games=[2024020001, 2024020002, 2024020003],
        )

        async with downloader:
            results = [r async for r in downloader.download_season(20242025)]

        assert len(results) == 3
        assert results[0].is_successful
        assert not results[1].is_successful
        assert results[1].status == DownloadStatus.FAILED
        assert results[2].is_successful

    async def test_download_season_progress_callback(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test progress callback is called during season download."""
        callback = MagicMock()
        game_data: dict[int, dict[str, Any]] = {2024020001: {}, 2024020002: {}}
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            game_data=game_data,
            season_games=[2024020001, 2024020002],
            progress_callback=callback,
        )

        async with downloader:
            _ = [r async for r in downloader.download_season(20242025)]

        # Should be called for each game
        assert callback.call_count == 2

        # Verify callback arguments
        calls = callback.call_args_list
        assert calls[0].kwargs["current"] == 1
        assert calls[0].kwargs["game_id"] == 2024020001
        assert calls[1].kwargs["current"] == 2
        assert calls[1].kwargs["game_id"] == 2024020002

    async def test_download_season_progress_tracking(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test progress tracking during season download."""
        game_data: dict[int, dict[str, Any]] = {2024020001: {}}
        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            game_data=game_data,
            season_games=[2024020001, 2024020002],  # Two games requested
        )

        async with downloader:
            _ = [r async for r in downloader.download_season(20242025)]

        # Progress should be cleared after download
        assert downloader.progress is None


@pytest.mark.asyncio
class TestBaseDownloaderHealthCheck:
    """Tests for BaseDownloader.health_check."""

    async def test_health_check_success(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful health check."""
        mock_response = MagicMock(spec=HTTPResponse)
        mock_response.is_success = True
        mock_http_client.get = AsyncMock(return_value=mock_response)

        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
        )

        async with downloader:
            result = await downloader.health_check()

        assert result is True
        mock_http_client.get.assert_called_once()

    async def test_health_check_failure(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test health check failure."""
        mock_response = MagicMock(spec=HTTPResponse)
        mock_response.is_success = False
        mock_response.status = 503
        mock_http_client.get = AsyncMock(return_value=mock_response)

        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
        )

        async with downloader:
            with pytest.raises(HealthCheckError):
                await downloader.health_check()

    async def test_health_check_no_url_configured(
        self,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test health check when no URL is configured."""
        config = DownloaderConfig(
            base_url="https://api.test.com",
            health_check_url="",  # No health check URL
        )
        downloader = ConcreteDownloader(
            config,
            http_client=mock_http_client,
        )

        async with downloader:
            result = await downloader.health_check()

        assert result is True
        mock_http_client.get.assert_not_called()

    async def test_health_check_connection_error(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test health check with connection error."""
        mock_http_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
        )

        async with downloader:
            with pytest.raises(HealthCheckError) as exc_info:
                await downloader.health_check()

        assert "Connection refused" in str(exc_info.value)


@pytest.mark.asyncio
class TestBaseDownloaderGet:
    """Tests for BaseDownloader._get method."""

    async def test_get_success(
        self,
        downloader_config: DownloaderConfig,
        mock_http_client: AsyncMock,
        mock_rate_limiter: MagicMock,
        mock_retry_handler: MagicMock,
    ) -> None:
        """Test successful GET request."""
        mock_response = MagicMock(spec=HTTPResponse)
        mock_response.is_rate_limited = False
        mock_response.is_server_error = False
        mock_http_client.get = AsyncMock(return_value=mock_response)

        downloader = ConcreteDownloader(
            downloader_config,
            http_client=mock_http_client,
            rate_limiter=mock_rate_limiter,
            retry_handler=mock_retry_handler,
        )

        async with downloader:
            response = await downloader._get("/test/path")

        assert response is mock_response
        mock_rate_limiter.wait.assert_called()

    async def test_get_requires_client(
        self,
        downloader_config: DownloaderConfig,
    ) -> None:
        """Test that _get raises error without client."""
        downloader = ConcreteDownloader(downloader_config)

        with pytest.raises(RuntimeError, match="HTTP client not initialized"):
            await downloader._get("/test/path")


class TestSetTotalItems:
    """Tests for set_total_items method."""

    def test_set_total_items(self, downloader_config: DownloaderConfig) -> None:
        """Test setting total items for progress tracking."""
        downloader = ConcreteDownloader(downloader_config)
        downloader._progress = DownloadProgress(source="test")

        downloader.set_total_items(100)

        assert downloader._progress.total_items == 100

    def test_set_total_items_no_progress(
        self, downloader_config: DownloaderConfig
    ) -> None:
        """Test setting total items when no progress exists."""
        downloader = ConcreteDownloader(downloader_config)

        # Should not raise
        downloader.set_total_items(100)
