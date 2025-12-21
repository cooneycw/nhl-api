"""Shared fixtures for DailyFaceoff integration tests."""

from __future__ import annotations

import pytest

from nhl_api.downloaders.sources.dailyfaceoff import (
    DailyFaceoffConfig,
    InjuryDownloader,
    LineCombinationsDownloader,
    PenaltyKillDownloader,
    PowerPlayDownloader,
    StartingGoaliesDownloader,
)

# =============================================================================
# Constants
# =============================================================================

# Test team: Toronto Maple Leafs (well-populated data, large market)
TEST_TEAM_ID = 10
TEST_TEAM_ABBREV = "TOR"
TEST_TEAM_SLUG = "toronto-maple-leafs"

# Alternative test teams for variety
SECONDARY_TEAM_ID = 6  # Boston Bruins
SECONDARY_TEAM_ABBREV = "BOS"


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def dailyfaceoff_config() -> DailyFaceoffConfig:
    """Configuration for integration tests.

    Uses a respectful rate limit since we're hitting the real site.
    """
    return DailyFaceoffConfig(
        requests_per_second=0.5,  # Slower than default to be respectful
        max_retries=2,
        http_timeout=30.0,
    )


@pytest.fixture
def fast_config() -> DailyFaceoffConfig:
    """Fast configuration for unit-style tests with mocks."""
    return DailyFaceoffConfig(
        requests_per_second=100.0,
        max_retries=1,
        http_timeout=10.0,
    )


# =============================================================================
# Team Fixtures
# =============================================================================


@pytest.fixture
def test_team_id() -> int:
    """Primary test team ID (Toronto Maple Leafs)."""
    return TEST_TEAM_ID


@pytest.fixture
def test_team_abbrev() -> str:
    """Primary test team abbreviation."""
    return TEST_TEAM_ABBREV


@pytest.fixture
def secondary_team_id() -> int:
    """Secondary test team ID (Boston Bruins)."""
    return SECONDARY_TEAM_ID


# =============================================================================
# Downloader Fixtures
# =============================================================================


@pytest.fixture
def line_combinations_downloader(
    dailyfaceoff_config: DailyFaceoffConfig,
) -> LineCombinationsDownloader:
    """Create a LineCombinationsDownloader for testing."""
    return LineCombinationsDownloader(dailyfaceoff_config)


@pytest.fixture
def power_play_downloader(
    dailyfaceoff_config: DailyFaceoffConfig,
) -> PowerPlayDownloader:
    """Create a PowerPlayDownloader for testing."""
    return PowerPlayDownloader(dailyfaceoff_config)


@pytest.fixture
def penalty_kill_downloader(
    dailyfaceoff_config: DailyFaceoffConfig,
) -> PenaltyKillDownloader:
    """Create a PenaltyKillDownloader for testing."""
    return PenaltyKillDownloader(dailyfaceoff_config)


@pytest.fixture
def injury_downloader(
    dailyfaceoff_config: DailyFaceoffConfig,
) -> InjuryDownloader:
    """Create an InjuryDownloader for testing."""
    return InjuryDownloader(dailyfaceoff_config)


@pytest.fixture
def starting_goalies_downloader(
    dailyfaceoff_config: DailyFaceoffConfig,
) -> StartingGoaliesDownloader:
    """Create a StartingGoaliesDownloader for testing."""
    return StartingGoaliesDownloader(dailyfaceoff_config)
