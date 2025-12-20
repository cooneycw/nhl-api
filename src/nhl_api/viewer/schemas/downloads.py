"""Download management API Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# =============================================================================
# Download Options
# =============================================================================


class SeasonOption(BaseModel):
    """Available season for download selection."""

    season_id: int
    start_year: int
    end_year: int
    is_current: bool
    label: str  # User-friendly label, e.g., "2024-2025"


class SourceOption(BaseModel):
    """Available data source for download selection."""

    source_id: int
    name: str
    source_type: str  # nhl_json, html_report, etc.
    description: str | None
    display_name: str  # User-friendly name, e.g., "Boxscore"
    is_active: bool


class SourceGroup(BaseModel):
    """Group of sources by type."""

    source_type: str
    display_name: str  # e.g., "NHL JSON API", "HTML Reports"
    sources: list[SourceOption]


class DownloadOptionsResponse(BaseModel):
    """Available download options for UI selection."""

    seasons: list[SeasonOption]
    source_groups: list[SourceGroup]


# =============================================================================
# Start Download
# =============================================================================


class DownloadStartRequest(BaseModel):
    """Request to start a download."""

    season_ids: list[int]
    source_names: list[str]  # e.g., ["nhl_schedule", "nhl_boxscore"]
    force: bool = False  # Re-download even if already completed


class BatchCreated(BaseModel):
    """Info about a created batch."""

    batch_id: int
    source_name: str
    season_id: int


class DownloadStartResponse(BaseModel):
    """Response after starting downloads."""

    batches: list[BatchCreated]
    message: str


# =============================================================================
# Active Downloads
# =============================================================================


class ActiveDownload(BaseModel):
    """Currently running download task."""

    batch_id: int
    source_id: int
    source_name: str
    source_type: str
    season_id: int
    season_label: str
    started_at: datetime
    items_total: int | None
    items_completed: int
    items_failed: int
    progress_percent: float | None


class ActiveDownloadsResponse(BaseModel):
    """List of currently running downloads."""

    downloads: list[ActiveDownload]
    count: int


# =============================================================================
# Cancel Download
# =============================================================================


class CancelDownloadResponse(BaseModel):
    """Response after cancelling a download."""

    batch_id: int
    cancelled: bool
    message: str
