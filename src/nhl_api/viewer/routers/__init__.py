"""API routers for the NHL Data Viewer backend."""

from nhl_api.viewer.routers import (
    coverage,
    downloads,
    entities,
    health,
    monitoring,
    reconciliation,
    validation,
)

__all__ = [
    "coverage",
    "downloads",
    "entities",
    "health",
    "monitoring",
    "reconciliation",
    "validation",
]
