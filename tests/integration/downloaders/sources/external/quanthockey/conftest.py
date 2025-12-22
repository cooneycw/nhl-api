"""Shared fixtures for QuantHockey integration tests."""

from __future__ import annotations

import pytest

from nhl_api.downloaders.sources.external.quanthockey import (
    QuantHockeyCareerStatsDownloader,
    QuantHockeyPlayerStatsDownloader,
)
from nhl_api.downloaders.sources.external.quanthockey.career_stats import (
    CareerStatCategory,
)
from nhl_api.downloaders.sources.external.quanthockey.player_stats import (
    QuantHockeyConfig,
)

# =============================================================================
# Constants
# =============================================================================

# Current NHL season for testing
CURRENT_SEASON_ID = 20242025

# Previous season for testing
PREVIOUS_SEASON_ID = 20232024

# Known all-time points leader (Wayne Gretzky)
KNOWN_POINTS_LEADER = "Wayne Gretzky"

# Known all-time goals leader (Wayne Gretzky)
KNOWN_GOALS_LEADER = "Wayne Gretzky"


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def quanthockey_config() -> QuantHockeyConfig:
    """Configuration for integration tests.

    Uses a conservative rate limit since we're hitting the real site.
    """
    return QuantHockeyConfig(
        requests_per_second=0.5,  # 1 request every 2 seconds
        max_retries=2,
        http_timeout=30.0,
    )


@pytest.fixture
def fast_config() -> QuantHockeyConfig:
    """Fast configuration for unit-style tests with mocks."""
    return QuantHockeyConfig(
        requests_per_second=100.0,
        max_retries=1,
        http_timeout=10.0,
    )


# =============================================================================
# Season Fixtures
# =============================================================================


@pytest.fixture
def current_season_id() -> int:
    """Current NHL season ID (2024-25)."""
    return CURRENT_SEASON_ID


@pytest.fixture
def previous_season_id() -> int:
    """Previous NHL season ID (2023-24)."""
    return PREVIOUS_SEASON_ID


# =============================================================================
# Downloader Fixtures
# =============================================================================


@pytest.fixture
def player_stats_downloader(
    quanthockey_config: QuantHockeyConfig,
) -> QuantHockeyPlayerStatsDownloader:
    """Create a QuantHockeyPlayerStatsDownloader for testing."""
    return QuantHockeyPlayerStatsDownloader(quanthockey_config)


@pytest.fixture
def career_stats_downloader(
    quanthockey_config: QuantHockeyConfig,
) -> QuantHockeyCareerStatsDownloader:
    """Create a QuantHockeyCareerStatsDownloader for testing."""
    return QuantHockeyCareerStatsDownloader(quanthockey_config)


# =============================================================================
# Category Fixtures
# =============================================================================


@pytest.fixture
def points_category() -> CareerStatCategory:
    """Points category for career stats."""
    return CareerStatCategory.POINTS


@pytest.fixture
def goals_category() -> CareerStatCategory:
    """Goals category for career stats."""
    return CareerStatCategory.GOALS
