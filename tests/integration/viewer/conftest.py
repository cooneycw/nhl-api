"""Pytest fixtures for viewer backend integration tests.

These fixtures provide a real FastAPI app with lifespan management,
using a mock DatabaseService to avoid AWS Secrets Manager and real DB dependencies.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from httpx import AsyncClient


class MockDatabaseService:
    """Mock DatabaseService for testing lifespan without real database."""

    def __init__(
        self,
        *,
        min_connections: int = 2,
        max_connections: int = 10,
        secret_id: str | None = None,
        should_fail: bool = False,
    ) -> None:
        """Initialize mock service."""
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.secret_id = secret_id
        self._connected = False
        self._should_fail = should_fail
        self.connect_called = False
        self.disconnect_called = False

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected

    async def connect(self) -> None:
        """Simulate database connection."""
        self.connect_called = True
        if self._should_fail:
            from nhl_api.services.db import DatabaseError

            raise DatabaseError("Failed to connect to database: Connection refused")
        self._connected = True

    async def disconnect(self) -> None:
        """Simulate database disconnection."""
        self.disconnect_called = True
        self._connected = False

    async def fetchval(self, query: str, *args: object, **kwargs: object) -> int:
        """Mock fetchval - returns 1 for health checks."""
        return 1


def _clear_module_cache() -> None:
    """Clear relevant modules from cache to allow fresh imports."""
    # Clear ALL nhl_api modules to ensure clean slate
    modules_to_clear = [m for m in list(sys.modules.keys()) if m.startswith("nhl_api")]
    for mod in modules_to_clear:
        del sys.modules[mod]


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client with app lifespan using mock DB.

    This fixture:
    1. Clears module cache
    2. Monkey-patches DatabaseService with MockDatabaseService
    3. Starts the real app with lifespan via asgi-lifespan
    4. Provides an httpx.AsyncClient for making requests
    5. Restores original DatabaseService
    """
    import httpx
    from asgi_lifespan import LifespanManager

    # Clear module cache
    _clear_module_cache()

    # Import fresh and patch both locations
    import nhl_api.services.db as db_module
    import nhl_api.services.db.connection as connection_module

    original_db_service_conn = connection_module.DatabaseService
    original_db_service_pkg = db_module.DatabaseService

    # Replace with mock in both locations (monkey-patch for testing)
    connection_module.DatabaseService = MockDatabaseService  # type: ignore[misc, assignment]
    db_module.DatabaseService = MockDatabaseService  # type: ignore[misc, assignment]

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
            ) as client:
                yield client
    finally:
        # Restore originals (monkey-patch restoration)
        connection_module.DatabaseService = original_db_service_conn  # type: ignore[misc]
        db_module.DatabaseService = original_db_service_pkg  # type: ignore[misc]


@pytest.fixture
async def async_client_with_tracking() -> (
    AsyncGenerator[tuple[AsyncClient, MockDatabaseService], None]
):
    """Create an async client that tracks database service calls.

    Returns tuple of (client, db_service) for assertions on lifecycle.
    """
    import httpx
    from asgi_lifespan import LifespanManager

    # Create a shared instance to track across lifespan
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

    # Replace with tracking mock in both locations (monkey-patch for testing)
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
            ) as client:
                assert tracked_instance is not None
                yield client, tracked_instance
    finally:
        # Restore originals (monkey-patch restoration)
        connection_module.DatabaseService = original_db_service_conn  # type: ignore[misc]
        db_module.DatabaseService = original_db_service_pkg  # type: ignore[misc]


@pytest.fixture
async def failing_async_client() -> AsyncGenerator[None, None]:
    """Create an async client with a failing database service.

    Used to test startup failure handling. The fixture verifies that
    DatabaseError is raised when the database connection fails during startup.
    """
    from asgi_lifespan import LifespanManager

    class FailingMockDatabaseService(MockDatabaseService):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(should_fail=True)

    # Clear module cache BEFORE any nhl_api imports
    _clear_module_cache()

    # Import fresh after clearing cache
    import nhl_api.services.db as db_module
    import nhl_api.services.db.connection as connection_module

    # Import DatabaseError after clearing cache to get the correct class
    DatabaseError = connection_module.DatabaseError  # noqa: N806

    original_db_service_conn = connection_module.DatabaseService
    original_db_service_pkg = db_module.DatabaseService

    # Replace with failing mock in both locations (monkey-patch for testing)
    connection_module.DatabaseService = FailingMockDatabaseService  # type: ignore[misc, assignment]
    db_module.DatabaseService = FailingMockDatabaseService  # type: ignore[misc, assignment]

    try:
        # Clear main module to pick up patched DatabaseService
        if "nhl_api.viewer.main" in sys.modules:
            del sys.modules["nhl_api.viewer.main"]

        from nhl_api.viewer.main import create_app

        app = create_app()

        # App startup should fail with database error
        with pytest.raises(DatabaseError, match="Failed to connect to database"):
            async with LifespanManager(app):
                pass

        yield
    finally:
        # Restore originals
        connection_module.DatabaseService = original_db_service_conn  # type: ignore[misc]
        db_module.DatabaseService = original_db_service_pkg  # type: ignore[misc]
