"""Unit tests for BaseStatsDownloader.

Tests cover:
- Configuration and initialization
- Cayenne expression path building
- Response validation
- Game ID management
- Download flow integration
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest

from nhl_api.downloaders.base.protocol import DownloadError
from nhl_api.downloaders.sources.nhl_stats.base_stats_downloader import (
    DEFAULT_STATS_RATE_LIMIT,
    NHL_STATS_API_BASE_URL,
    BaseStatsDownloader,
    StatsDownloaderConfig,
)

# =============================================================================
# Test Fixtures
# =============================================================================


class ConcreteStatsDownloader(BaseStatsDownloader):
    """Concrete implementation for testing abstract base class."""

    @property
    def source_name(self) -> str:
        return "nhl_stats_test"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Simple fetch for testing."""
        return {"game_id": game_id, "shifts": []}

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Yield game IDs for testing."""
        self.set_total_items(len(self._game_ids))
        for game_id in self._game_ids:
            yield game_id


@pytest.fixture
def config() -> StatsDownloaderConfig:
    """Create test configuration."""
    return StatsDownloaderConfig(
        base_url=NHL_STATS_API_BASE_URL,
        requests_per_second=10.0,  # Fast for testing
        max_retries=2,
        http_timeout=5.0,
    )


@pytest.fixture
def downloader(config: StatsDownloaderConfig) -> ConcreteStatsDownloader:
    """Create test downloader instance."""
    return ConcreteStatsDownloader(config)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestStatsDownloaderConfig:
    """Tests for StatsDownloaderConfig."""

    def test_default_config_values(self) -> None:
        """Test default configuration values."""
        config = StatsDownloaderConfig()
        assert config.base_url == NHL_STATS_API_BASE_URL
        assert config.requests_per_second == DEFAULT_STATS_RATE_LIMIT
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.http_timeout == 30.0
        assert config.health_check_url == ""

    def test_custom_config_values(self) -> None:
        """Test custom configuration values."""
        config = StatsDownloaderConfig(
            base_url="https://custom.api",
            requests_per_second=10.0,
            max_retries=5,
            retry_base_delay=2.0,
            http_timeout=60.0,
        )
        assert config.base_url == "https://custom.api"
        assert config.requests_per_second == 10.0
        assert config.max_retries == 5
        assert config.retry_base_delay == 2.0
        assert config.http_timeout == 60.0

    def test_base_url_constant(self) -> None:
        """Test the base URL constant."""
        assert NHL_STATS_API_BASE_URL == "https://api.nhle.com/stats/rest/en"

    def test_default_rate_limit_constant(self) -> None:
        """Test the default rate limit constant."""
        assert DEFAULT_STATS_RATE_LIMIT == 5.0


# =============================================================================
# Initialization Tests
# =============================================================================


class TestBaseStatsDownloaderInit:
    """Tests for BaseStatsDownloader initialization."""

    def test_source_name(self, downloader: ConcreteStatsDownloader) -> None:
        """Test source_name property."""
        assert downloader.source_name == "nhl_stats_test"

    def test_default_game_ids(self, downloader: ConcreteStatsDownloader) -> None:
        """Test default empty game IDs."""
        assert downloader._game_ids == []

    def test_init_with_game_ids(self, config: StatsDownloaderConfig) -> None:
        """Test initialization with game IDs."""
        game_ids = [2024020001, 2024020002]
        downloader = ConcreteStatsDownloader(config, game_ids=game_ids)
        assert downloader._game_ids == game_ids

    def test_init_with_none_config(self) -> None:
        """Test initialization with None config uses defaults."""
        downloader = ConcreteStatsDownloader(None)
        assert downloader.config.base_url == NHL_STATS_API_BASE_URL
        assert downloader.config.requests_per_second == DEFAULT_STATS_RATE_LIMIT


# =============================================================================
# Game ID Management Tests
# =============================================================================


class TestGameIdManagement:
    """Tests for game ID management methods."""

    def test_set_game_ids(self, downloader: ConcreteStatsDownloader) -> None:
        """Test setting game IDs."""
        game_ids = [2024020001, 2024020002, 2024020003]
        downloader.set_game_ids(game_ids)
        assert downloader._game_ids == game_ids

    def test_set_game_ids_copies_list(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that set_game_ids creates a copy."""
        game_ids = [2024020001, 2024020002]
        downloader.set_game_ids(game_ids)
        game_ids.append(2024020003)  # Modify original
        assert len(downloader._game_ids) == 2  # Should not be affected

    def test_get_game_ids(self, downloader: ConcreteStatsDownloader) -> None:
        """Test getting game IDs."""
        game_ids = [2024020001, 2024020002]
        downloader.set_game_ids(game_ids)
        result = downloader.get_game_ids()
        assert result == game_ids

    def test_get_game_ids_returns_copy(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that get_game_ids returns a copy."""
        game_ids = [2024020001, 2024020002]
        downloader.set_game_ids(game_ids)
        result = downloader.get_game_ids()
        result.append(2024020003)  # Modify returned list
        assert len(downloader._game_ids) == 2  # Should not be affected

    def test_set_empty_game_ids(self, downloader: ConcreteStatsDownloader) -> None:
        """Test setting empty game IDs list."""
        downloader.set_game_ids([2024020001])  # First set some
        downloader.set_game_ids([])  # Then clear
        assert downloader._game_ids == []


# =============================================================================
# Cayenne Path Building Tests
# =============================================================================


class TestBuildCayennePath:
    """Tests for _build_cayenne_path static method."""

    def test_simple_endpoint_no_params(self) -> None:
        """Test endpoint with no parameters."""
        path = BaseStatsDownloader._build_cayenne_path("/shiftcharts")
        assert path == "/shiftcharts"

    def test_endpoint_with_game_id(self) -> None:
        """Test endpoint with game ID."""
        path = BaseStatsDownloader._build_cayenne_path(
            "/shiftcharts",
            game_id=2024020500,
        )
        assert path == "/shiftcharts?cayenneExp=gameId=2024020500"

    def test_endpoint_with_extra_params(self) -> None:
        """Test endpoint with additional parameters."""
        path = BaseStatsDownloader._build_cayenne_path(
            "/shiftcharts",
            game_id=2024020500,
            playerId=8470613,
        )
        assert "cayenneExp=" in path
        assert "gameId=2024020500" in path
        assert "playerId=8470613" in path
        assert " and " in path  # Multiple params joined with 'and'

    def test_endpoint_with_none_values_ignored(self) -> None:
        """Test that None values are ignored."""
        path = BaseStatsDownloader._build_cayenne_path(
            "/shiftcharts",
            game_id=2024020500,
            playerId=None,
        )
        assert path == "/shiftcharts?cayenneExp=gameId=2024020500"
        assert "playerId" not in path

    def test_endpoint_with_only_extra_params(self) -> None:
        """Test endpoint with only extra parameters (no game_id)."""
        path = BaseStatsDownloader._build_cayenne_path(
            "/players",
            teamId=12,
        )
        assert path == "/players?cayenneExp=teamId=12"

    def test_endpoint_preserves_leading_slash(self) -> None:
        """Test that leading slash is preserved."""
        path = BaseStatsDownloader._build_cayenne_path(
            "/shiftcharts",
            game_id=2024020500,
        )
        assert path.startswith("/shiftcharts")


# =============================================================================
# Response Validation Tests
# =============================================================================


class TestValidateStatsResponse:
    """Tests for _validate_stats_response method."""

    def test_valid_response(self, downloader: ConcreteStatsDownloader) -> None:
        """Test validation of a valid response."""
        data = {
            "data": [
                {"id": 1, "value": "test1"},
                {"id": 2, "value": "test2"},
            ],
            "total": 2,
        }
        result = downloader._validate_stats_response(data)
        assert len(result) == 2
        assert result[0]["id"] == 1

    def test_valid_response_without_total(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test validation of response without total field."""
        data = {
            "data": [
                {"id": 1},
            ],
        }
        result = downloader._validate_stats_response(data)
        assert len(result) == 1

    def test_empty_data_list(self, downloader: ConcreteStatsDownloader) -> None:
        """Test validation with empty data list."""
        data = {"data": [], "total": 0}
        result = downloader._validate_stats_response(data)
        assert result == []

    def test_invalid_response_not_dict(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that non-dict response raises error."""
        with pytest.raises(DownloadError) as exc_info:
            downloader._validate_stats_response("not a dict")  # type: ignore[arg-type]
        assert "expected dict" in str(exc_info.value)

    def test_invalid_response_missing_data(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that response without 'data' field raises error."""
        with pytest.raises(DownloadError) as exc_info:
            downloader._validate_stats_response({"total": 0})
        assert "missing 'data' field" in str(exc_info.value)

    def test_invalid_response_data_not_list(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that non-list 'data' field raises error."""
        with pytest.raises(DownloadError) as exc_info:
            downloader._validate_stats_response({"data": "not a list"})
        assert "'data' should be a list" in str(exc_info.value)

    def test_validation_includes_game_id_in_error(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that game_id is included in error."""
        with pytest.raises(DownloadError) as exc_info:
            downloader._validate_stats_response(
                {"wrong": "format"},
                game_id=2024020500,
            )
        assert exc_info.value.game_id == 2024020500


# =============================================================================
# Download Flow Tests
# =============================================================================


class TestDownloadFlow:
    """Tests for download flow."""

    @pytest.mark.asyncio
    async def test_fetch_game_returns_data(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that _fetch_game returns expected data."""
        result = await downloader._fetch_game(2024020500)
        assert result["game_id"] == 2024020500
        assert "shifts" in result

    @pytest.mark.asyncio
    async def test_fetch_season_games_yields_game_ids(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that _fetch_season_games yields game IDs."""
        game_ids = [2024020001, 2024020002, 2024020003]
        downloader.set_game_ids(game_ids)

        results = []
        async for game_id in downloader._fetch_season_games(20242025):
            results.append(game_id)

        assert results == game_ids

    @pytest.mark.asyncio
    async def test_fetch_season_games_empty_when_no_ids(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that _fetch_season_games yields nothing when no IDs set."""
        results = []
        async for game_id in downloader._fetch_season_games(20242025):
            results.append(game_id)
        assert results == []


# =============================================================================
# Integration with Base Downloader Tests
# =============================================================================


class TestBaseDownloaderIntegration:
    """Tests for integration with BaseDownloader."""

    def test_inherits_from_base_downloader(
        self, downloader: ConcreteStatsDownloader
    ) -> None:
        """Test that we inherit from BaseDownloader."""
        from nhl_api.downloaders.base.base_downloader import BaseDownloader

        assert isinstance(downloader, BaseDownloader)

    def test_config_inherits_from_downloader_config(self) -> None:
        """Test that config inherits from DownloaderConfig."""
        from nhl_api.downloaders.base.base_downloader import DownloaderConfig

        assert issubclass(StatsDownloaderConfig, DownloaderConfig)

    def test_has_progress_callback_support(self, config: StatsDownloaderConfig) -> None:
        """Test that progress callback is supported."""
        callback = MagicMock()
        downloader = ConcreteStatsDownloader(config, progress_callback=callback)
        assert downloader._progress_callback == callback

    def test_has_rate_limiter(self, downloader: ConcreteStatsDownloader) -> None:
        """Test that rate limiter is initialized."""
        assert downloader._rate_limiter is not None

    def test_has_retry_handler(self, downloader: ConcreteStatsDownloader) -> None:
        """Test that retry handler is initialized."""
        assert downloader._retry_handler is not None


# =============================================================================
# Module Export Tests
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_exports_from_init(self) -> None:
        """Test that all expected classes are exported."""
        from nhl_api.downloaders.sources.nhl_stats import (
            DEFAULT_STATS_RATE_LIMIT,
            NHL_STATS_API_BASE_URL,
            BaseStatsDownloader,
            StatsDownloaderConfig,
        )

        assert BaseStatsDownloader is not None
        assert StatsDownloaderConfig is not None
        assert NHL_STATS_API_BASE_URL == "https://api.nhle.com/stats/rest/en"
        assert DEFAULT_STATS_RATE_LIMIT == 5.0

    def test_exports_from_sources_init(self) -> None:
        """Test that classes are exported from sources package."""
        from nhl_api.downloaders.sources import (
            BaseStatsDownloader,
            StatsDownloaderConfig,
        )

        assert BaseStatsDownloader is not None
        assert StatsDownloaderConfig is not None
