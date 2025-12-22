"""Coverage API Pydantic schemas.

Schemas for data coverage "gas tank" dashboard visualization.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CategoryCoverage(BaseModel):
    """Coverage statistics for a single data category."""

    name: str  # games, boxscore, pbp, shifts, players, html
    display_name: str  # Human-readable name
    actual: int  # Count of items downloaded
    expected: int  # Count of items expected
    percentage: float | None  # Calculated percentage (None if expected is 0)
    link_path: str  # Deep link to filtered explorer view


class SeasonCoverage(BaseModel):
    """Coverage statistics for a single season."""

    season_id: int
    season_label: str  # e.g., "2024-2025"
    is_current: bool
    categories: list[CategoryCoverage]
    game_logs_total: int
    players_with_game_logs: int
    refreshed_at: datetime | None


class CoverageResponse(BaseModel):
    """Response containing coverage data for multiple seasons."""

    seasons: list[SeasonCoverage]
    refreshed_at: datetime | None
