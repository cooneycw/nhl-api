"""Pytest fixtures for data flow integration tests.

This module provides fixtures for testing the complete data pipeline
from download through storage and validation.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from tests.integration.data_flow.reports.generator import ReportGenerator
from tests.integration.data_flow.reports.models import DataFlowReport
from tests.integration.data_flow.sources.registry import (
    SourceDefinition,
    SourceRegistry,
)
from tests.integration.data_flow.stages.download import DownloadStage
from tests.integration.data_flow.stages.storage import MockDatabaseService, StorageStage

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from nhl_api.services.db import DatabaseService

# =============================================================================
# Fixture Game Constants
# =============================================================================

# Primary fixture game: Season opener BUF @ NJ, Oct 4, 2024
FIXTURE_GAME_ID = 2024020001
FIXTURE_SEASON_ID = 20242025

# Alternative fixture for testing (already used in HTML tests)
ALT_FIXTURE_GAME_ID = 2024020500
ALT_FIXTURE_SEASON_ID = 20242025


# =============================================================================
# Game Fixtures
# =============================================================================


@pytest.fixture
def fixture_game_id() -> int:
    """Primary game ID for data flow testing.

    Returns game 2024020001 (BUF @ NJ, Oct 4, 2024 - season opener).
    """
    return FIXTURE_GAME_ID


@pytest.fixture
def fixture_season_id() -> int:
    """Season ID for the fixture game."""
    return FIXTURE_SEASON_ID


@pytest.fixture
def alt_fixture_game_id() -> int:
    """Alternative game ID for additional testing."""
    return ALT_FIXTURE_GAME_ID


# =============================================================================
# Registry Fixtures
# =============================================================================


@pytest.fixture
def source_registry() -> type[SourceRegistry]:
    """Get the source registry class."""
    return SourceRegistry


@pytest.fixture
def persist_sources() -> list[SourceDefinition]:
    """Get all sources with persist methods."""
    return SourceRegistry.get_persist_sources()


@pytest.fixture
def game_level_sources() -> list[SourceDefinition]:
    """Get all game-level sources."""
    return SourceRegistry.get_game_level_sources()


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def mock_db() -> MockDatabaseService:
    """Create a mock database service for testing.

    Returns a MockDatabaseService that tracks persist calls
    without requiring a real database.
    """
    return MockDatabaseService()


@pytest.fixture
async def test_db() -> AsyncGenerator[DatabaseService | MockDatabaseService, None]:
    """Get test database service.

    If USE_REAL_DB=true, returns a real DatabaseService.
    Otherwise, returns a MockDatabaseService.
    """
    use_real_db = os.getenv("USE_REAL_DB", "false").lower() == "true"

    if use_real_db:
        from nhl_api.services.db import DatabaseService

        db = DatabaseService()
        await db.connect()
        try:
            yield db
        finally:
            await db.disconnect()
    else:
        yield MockDatabaseService()


# =============================================================================
# Stage Fixtures
# =============================================================================


@pytest.fixture
def download_stage() -> DownloadStage:
    """Create download stage for testing.

    Uses a high rate limit for faster testing.
    """
    return DownloadStage(rate_limit_override=100.0)


@pytest.fixture
def storage_stage(mock_db: MockDatabaseService) -> StorageStage:
    """Create storage stage with mock database."""
    return StorageStage(mock_db)


@pytest.fixture
async def storage_stage_real(
    test_db: DatabaseService | MockDatabaseService,
) -> StorageStage:
    """Create storage stage with test database (real or mock)."""
    return StorageStage(test_db)


# =============================================================================
# Report Fixtures
# =============================================================================


@pytest.fixture
def report_generator() -> ReportGenerator:
    """Create report generator."""
    return ReportGenerator()


@pytest.fixture
def empty_report() -> DataFlowReport:
    """Create an empty report for testing."""
    return DataFlowReport()


@pytest.fixture
def report_with_game(fixture_game_id: int, fixture_season_id: int) -> DataFlowReport:
    """Create a report initialized with fixture game."""
    return DataFlowReport(game_id=fixture_game_id, season_id=fixture_season_id)


# =============================================================================
# Source Name Fixtures (for parametrization)
# =============================================================================


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Generate parameterized tests for source names.

    This hook enables @pytest.mark.parametrize("source_name", ...)
    to use all registered source names.
    """
    if "source_name" in metafunc.fixturenames:
        # Check if test has a specific marker for source selection
        markers = list(metafunc.definition.iter_markers("source_type"))
        if markers:
            source_type = markers[0].args[0]
            if source_type == "persist":
                names = SourceRegistry.PERSIST_SOURCE_NAMES
            elif source_type == "game_level":
                names = SourceRegistry.GAME_LEVEL_SOURCE_NAMES
            else:
                names = tuple(SourceRegistry.get_source_names())
        else:
            names = tuple(SourceRegistry.get_source_names())
        metafunc.parametrize("source_name", names)
