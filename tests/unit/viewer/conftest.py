"""Pytest fixtures for viewer backend tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from nhl_api.viewer.config import get_settings
from nhl_api.viewer.dependencies import set_db_service
from nhl_api.viewer.routers import entities, health, monitoring, validation

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_db_service() -> MagicMock:
    """Create a mock DatabaseService."""
    mock = MagicMock()
    mock.is_connected = True
    mock.fetchval = AsyncMock(return_value=1)
    mock.fetch = AsyncMock(return_value=[])
    mock.fetchrow = AsyncMock(return_value=None)
    mock.execute = AsyncMock(return_value="OK")
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    return mock


@pytest.fixture
def test_client(mock_db_service: MagicMock) -> Generator[TestClient, None, None]:
    """Create a test client with mocked database.

    This bypasses the lifespan context manager to use
    a mock database instead of a real connection.
    """
    settings = get_settings()

    # Create app without lifespan for testing
    app = FastAPI(title="Test App")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(monitoring.router, prefix="/api/v1")
    app.include_router(entities.router, prefix="/api/v1")
    app.include_router(validation.router, prefix="/api/v1")

    @app.get("/api/v1/info")
    async def api_info() -> dict[str, str]:
        return {"api_version": "v1", "title": "Test", "description": "Test"}

    # Set mock db service
    set_db_service(mock_db_service)

    client = TestClient(app)
    yield client

    # Cleanup
    set_db_service(None)
