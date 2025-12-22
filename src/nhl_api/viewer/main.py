"""NHL Data Viewer Backend - FastAPI Application.

Main entry point for the viewer backend service. Provides:
- FastAPI app with lifespan management for database connection
- CORS configuration for frontend integration
- API routing with versioning
- OpenAPI documentation

Usage:
    # Development
    uvicorn nhl_api.viewer.main:app --reload

    # Production
    uvicorn nhl_api.viewer.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.config import get_settings
from nhl_api.viewer.dependencies import set_db_service
from nhl_api.viewer.routers import (
    downloads,
    entities,
    health,
    monitoring,
    reconciliation,
    validation,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events.

    Handles:
    - Database connection pool initialization on startup
    - Clean shutdown of database connections

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the application during its lifetime.
    """
    settings = get_settings()

    # Startup
    logger.info("Starting NHL Data Viewer backend...")

    # Initialize database connection
    db = DatabaseService(
        min_connections=settings.db_min_connections,
        max_connections=settings.db_max_connections,
    )

    try:
        await db.connect()
        set_db_service(db)

        # Set start time for uptime tracking
        from nhl_api.viewer.routers.health import set_start_time

        set_start_time(time.time())

        logger.info("Database connection established")

        yield  # Application runs here

    finally:
        # Shutdown
        logger.info("Shutting down NHL Data Viewer backend...")
        set_db_service(None)
        await db.disconnect()
        logger.info("Database connection closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(downloads.router, prefix=f"/api/{settings.api_version}")
    app.include_router(monitoring.router, prefix=f"/api/{settings.api_version}")
    app.include_router(entities.router, prefix=f"/api/{settings.api_version}")
    app.include_router(reconciliation.router, prefix=f"/api/{settings.api_version}")
    app.include_router(validation.router, prefix=f"/api/{settings.api_version}")

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint with API information."""
        return {
            "name": settings.api_title,
            "version": settings.api_version,
            "docs": "/docs",
        }

    # API info endpoint
    @app.get(f"/api/{settings.api_version}/info")
    async def api_info() -> dict[str, str]:
        """API version and metadata."""
        return {
            "api_version": settings.api_version,
            "title": settings.api_title,
            "description": settings.api_description,
        }

    return app


# Create the app instance
app = create_app()
