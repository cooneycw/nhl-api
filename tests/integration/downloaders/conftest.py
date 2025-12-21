"""Shared fixtures for downloader integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from nhl_api.downloaders.sources.html import (
    HTMLDownloaderConfig,
    HTMLDownloaderRegistry,
)

# =============================================================================
# Constants
# =============================================================================

# Known good game for testing (2024-25 season, game 500)
TEST_GAME_ID = 2024020500
TEST_SEASON_ID = 20242025

# Path to HTML fixtures
HTML_FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures" / "html"


# =============================================================================
# HTML Downloader Fixtures
# =============================================================================


@pytest.fixture
def html_downloader_config() -> HTMLDownloaderConfig:
    """Fast configuration for integration tests."""
    return HTMLDownloaderConfig(
        requests_per_second=100.0,  # Fast for testing with mocks
        max_retries=2,
        http_timeout=10.0,
    )


@pytest.fixture
def known_game_id() -> int:
    """A game ID known to have all report types available."""
    return TEST_GAME_ID


@pytest.fixture
def known_season_id() -> int:
    """Season ID corresponding to the known game."""
    return TEST_SEASON_ID


@pytest.fixture
def html_fixtures_path() -> Path:
    """Path to HTML fixture files."""
    return HTML_FIXTURES_PATH


# =============================================================================
# HTML Fixture Loaders
# =============================================================================


def load_html_fixture(report_type: str) -> bytes:
    """Load HTML fixture file for a report type.

    Args:
        report_type: Report type code (GS, ES, PL, etc.)

    Returns:
        Raw HTML content as bytes
    """
    # Map report type to fixture filename
    filename = f"{report_type}020500.HTM"
    fixture_path = HTML_FIXTURES_PATH / filename

    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    return fixture_path.read_bytes()


@pytest.fixture
def gs_fixture() -> bytes:
    """Game Summary (GS) HTML fixture."""
    return load_html_fixture("GS")


@pytest.fixture
def es_fixture() -> bytes:
    """Event Summary (ES) HTML fixture."""
    return load_html_fixture("ES")


@pytest.fixture
def pl_fixture() -> bytes:
    """Play-by-Play (PL) HTML fixture."""
    return load_html_fixture("PL")


@pytest.fixture
def fs_fixture() -> bytes:
    """Faceoff Summary (FS) HTML fixture."""
    return load_html_fixture("FS")


@pytest.fixture
def fc_fixture() -> bytes:
    """Faceoff Comparison (FC) HTML fixture."""
    return load_html_fixture("FC")


@pytest.fixture
def ro_fixture() -> bytes:
    """Roster Report (RO) HTML fixture."""
    return load_html_fixture("RO")


@pytest.fixture
def ss_fixture() -> bytes:
    """Shot Summary (SS) HTML fixture."""
    return load_html_fixture("SS")


@pytest.fixture
def th_fixture() -> bytes:
    """Home Time on Ice (TH) HTML fixture."""
    return load_html_fixture("TH")


@pytest.fixture
def tv_fixture() -> bytes:
    """Visitor Time on Ice (TV) HTML fixture."""
    return load_html_fixture("TV")


@pytest.fixture
def all_html_fixtures() -> dict[str, bytes]:
    """All HTML fixtures keyed by report type."""
    return {
        report_type: load_html_fixture(report_type)
        for report_type in HTMLDownloaderRegistry.REPORT_TYPES
    }
