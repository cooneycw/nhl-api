"""Integration tests for viewer backend app lifecycle.

These tests verify the FastAPI application's lifespan management,
including database connection startup/shutdown and inline endpoints.

Coverage targets:
- src/nhl_api/viewer/main.py lines 52-81 (lifespan context manager)
- src/nhl_api/viewer/main.py lines 118-135 (inline endpoints)
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from tests.integration.viewer.conftest import MockDatabaseService, _clear_module_cache

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestAppLifecycle:
    """Tests for app startup and shutdown lifecycle."""

    async def test_app_starts_with_database_connection(
        self,
        async_client_with_tracking: tuple[AsyncClient, MockDatabaseService],
    ) -> None:
        """Test that app startup triggers database connection.

        Verifies that:
        - DatabaseService.connect() is called during startup
        - The database is marked as connected
        """
        client, db_service = async_client_with_tracking

        # Verify connect was called during startup
        assert db_service.connect_called is True
        assert db_service.is_connected is True

    async def test_app_shuts_down_cleanly(self) -> None:
        """Test that app shutdown closes database connection.

        Verifies that DatabaseService.disconnect() is called during shutdown.
        """
        import httpx
        from asgi_lifespan import LifespanManager

        # Track the instance across lifespan
        tracked_instance: MockDatabaseService | None = None

        class TrackedMockDatabaseService(MockDatabaseService):
            def __init__(self, **kwargs: object) -> None:
                nonlocal tracked_instance
                super().__init__()
                tracked_instance = self

        # Clear module cache
        _clear_module_cache()

        # Import fresh and patch both locations
        import nhl_api.services.db as db_module
        import nhl_api.services.db.connection as connection_module

        original_db_service_conn = connection_module.DatabaseService
        original_db_service_pkg = db_module.DatabaseService

        # Replace with tracking mock in both locations
        connection_module.DatabaseService = TrackedMockDatabaseService  # type: ignore[misc, assignment]
        db_module.DatabaseService = TrackedMockDatabaseService  # type: ignore[misc, assignment]

        try:
            # Clear main module to pick up patched DatabaseService
            if "nhl_api.viewer.main" in sys.modules:
                del sys.modules["nhl_api.viewer.main"]

            from nhl_api.viewer.main import create_app

            app = create_app()

            # Use LifespanManager to properly handle lifespan events
            async with LifespanManager(app) as manager:
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=manager.app),
                    base_url="http://testserver",
                ):
                    # During app lifetime
                    assert tracked_instance is not None
                    assert tracked_instance.connect_called is True
                    assert tracked_instance.disconnect_called is False

            # After exiting context, shutdown should have disconnected
            assert tracked_instance is not None
            assert tracked_instance.disconnect_called is True
            assert tracked_instance.is_connected is False
        finally:
            # Restore originals
            connection_module.DatabaseService = original_db_service_conn  # type: ignore[misc]
            db_module.DatabaseService = original_db_service_pkg  # type: ignore[misc]


class TestHealthEndpointsIntegration:
    """Integration tests for health endpoints with lifespan."""

    async def test_health_returns_healthy_with_database(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test /health endpoint returns healthy when DB is connected."""
        response = await async_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["connected"] is True
        assert "latency_ms" in data["database"]
        assert "uptime_seconds" in data
        assert "timestamp" in data
        assert "version" in data

    async def test_health_ready_returns_ready_with_database(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test /health/ready endpoint returns ready when DB is connected."""
        response = await async_client.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


class TestInlineEndpoints:
    """Integration tests for inline endpoints defined in create_app()."""

    async def test_root_endpoint_returns_api_info(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test root endpoint (/) returns expected API information.

        This tests the inline endpoint at main.py lines 118-125.
        """
        response = await async_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "NHL Data Viewer API"
        assert "version" in data
        assert data["version"] == "v1"
        assert "docs" in data
        assert data["docs"] == "/docs"

    async def test_api_info_endpoint_returns_metadata(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test /api/v1/info endpoint returns API metadata.

        This tests the inline endpoint at main.py lines 128-135.
        """
        response = await async_client.get("/api/v1/info")

        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        assert data["api_version"] == "v1"
        assert "title" in data
        assert data["title"] == "NHL Data Viewer API"
        assert "description" in data


class TestLifespanErrorHandling:
    """Tests for error handling during lifespan events."""

    async def test_startup_failure_propagates_error(
        self,
        failing_async_client: None,
    ) -> None:
        """Test that database connection failure during startup raises error.

        The failing_async_client fixture handles the assertion that
        DatabaseError is raised during startup.
        """
        # The fixture already asserts the error is raised
        # This test just confirms the fixture works correctly
        pass
