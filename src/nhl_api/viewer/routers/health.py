"""Health check endpoints for monitoring.

Provides endpoints for load balancers, Kubernetes probes,
and monitoring systems to verify service health.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.config import get_settings
from nhl_api.viewer.dependencies import get_db

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(tags=["health"])

# Track startup time for uptime calculation
_start_time: float = time.time()


def set_start_time(start: float) -> None:
    """Set the application start time for uptime tracking."""
    global _start_time
    _start_time = start


class DatabaseStatus(BaseModel):
    """Database connectivity status."""

    connected: bool
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    uptime_seconds: float
    timestamp: str
    database: DatabaseStatus


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Check service health including database connectivity",
)
async def health_check(
    db: DbDep,
) -> HealthResponse:
    """Check the health of the service and its dependencies.

    Returns:
        HealthResponse with status, version, uptime, and DB status.
    """
    settings = get_settings()

    # Check database connectivity
    db_status = await _check_database(db)

    # Determine overall status
    overall_status = "healthy" if db_status.connected else "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.api_version,
        uptime_seconds=time.time() - _start_time,
        timestamp=datetime.now(UTC).isoformat(),
        database=db_status,
    )


async def _check_database(db: DatabaseService) -> DatabaseStatus:
    """Check database connectivity and measure latency.

    Args:
        db: The database service to check.

    Returns:
        DatabaseStatus with connection info.
    """
    start = time.perf_counter()

    try:
        # Simple connectivity test
        result = await db.fetchval("SELECT 1")
        latency = (time.perf_counter() - start) * 1000  # Convert to ms

        return DatabaseStatus(
            connected=result == 1,
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        return DatabaseStatus(
            connected=False,
            error=str(e),
        )


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Simple liveness check for Kubernetes",
)
async def liveness() -> dict[str, str]:
    """Simple liveness probe - always returns OK if service is running."""
    return {"status": "ok"}


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Readiness check verifying database connectivity",
)
async def readiness(
    db: DbDep,
) -> dict[str, str]:
    """Readiness probe - checks if service can handle requests.

    Returns 200 if database is connected, 503 otherwise.
    """
    try:
        await db.fetchval("SELECT 1")
        return {"status": "ready"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        ) from None
