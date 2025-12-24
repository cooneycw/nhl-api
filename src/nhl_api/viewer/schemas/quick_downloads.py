"""Quick Download API schemas for simplified download interface.

Provides schemas for:
- Quick download actions (preseason, regular, playoffs, external, prior)
- Sync status for displaying last sync times
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# =============================================================================
# Sync Status
# =============================================================================


class SyncStatusItem(BaseModel):
    """Sync status for a single source/game_type combination."""

    source_name: str
    source_display_name: str
    game_type: int
    game_type_label: str  # "Pre-season", "Regular", "Playoffs", "External"
    last_synced_at: datetime | None
    items_synced_count: int
    is_stale: bool  # True if sync is >24h old or never synced


class SyncStatusResponse(BaseModel):
    """Sync status for quick download display."""

    season_id: int
    season_label: str
    items: list[SyncStatusItem]


# =============================================================================
# Quick Download Responses
# =============================================================================


class QuickDownloadResponse(BaseModel):
    """Response after starting a quick download."""

    action: str  # "preseason", "regular", "playoffs", "external", "prior_season"
    season_id: int
    season_label: str
    batches_started: int
    message: str
    batch_ids: list[int]


# =============================================================================
# Prior Season Request
# =============================================================================


class PriorSeasonRequest(BaseModel):
    """Request for prior season download (optional game types)."""

    game_types: list[int] = [1, 2, 3]  # All game types by default
