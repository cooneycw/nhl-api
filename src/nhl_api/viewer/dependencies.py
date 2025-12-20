"""FastAPI dependency injection providers.

This module provides dependencies for use in route handlers,
enabling clean separation of concerns and testability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from nhl_api.services.db import DatabaseService


# Global reference to the database service
# Set during app lifespan startup
_db_service: DatabaseService | None = None


def set_db_service(db: DatabaseService | None) -> None:
    """Set the global database service reference.

    Called during app lifespan to initialize/cleanup.

    Args:
        db: The DatabaseService instance, or None to clear.
    """
    global _db_service
    _db_service = db


async def get_db() -> AsyncGenerator[DatabaseService, None]:
    """Dependency to get the database service.

    Yields:
        The connected DatabaseService instance.

    Raises:
        RuntimeError: If database is not initialized.

    Example:
        @router.get("/data")
        async def get_data(db: DatabaseService = Depends(get_db)):
            result = await db.fetchval("SELECT 1")
    """
    if _db_service is None:
        raise RuntimeError("Database service not initialized")
    yield _db_service
