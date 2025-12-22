"""Monitoring API Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

# =============================================================================
# Pagination
# =============================================================================


class PaginatedResponse(BaseModel):
    """Base model for paginated responses."""

    total: int
    page: int
    page_size: int
    pages: int


# =============================================================================
# Dashboard
# =============================================================================


class DashboardStats(BaseModel):
    """Overall system statistics for dashboard."""

    active_batches: int
    completed_today: int
    failed_today: int
    success_rate_24h: float | None
    total_items_24h: int
    sources_healthy: int
    sources_degraded: int
    sources_error: int


class RecentFailure(BaseModel):
    """Summary of a recent failure for dashboard."""

    progress_id: int
    source_name: str
    item_key: str
    error_message: str | None
    last_attempt_at: datetime | None


class DashboardResponse(BaseModel):
    """Complete dashboard response."""

    stats: DashboardStats
    recent_failures: list[RecentFailure]
    timestamp: datetime


# =============================================================================
# Batches
# =============================================================================


class BatchSummary(BaseModel):
    """Summary of a batch for list view."""

    batch_id: int
    source_id: int
    source_name: str
    source_type: str
    season_id: int | None
    season_name: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    items_total: int
    items_success: int
    items_failed: int
    items_skipped: int
    success_rate: float
    completion_rate: float


class BatchListResponse(PaginatedResponse):
    """Paginated list of batches."""

    batches: list[BatchSummary]


class DownloadItem(BaseModel):
    """Individual download item in a batch."""

    progress_id: int
    item_key: str
    status: str
    attempts: int
    last_attempt_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    response_size_bytes: int | None
    response_time_ms: int | None


class BatchDetail(BaseModel):
    """Detailed batch information with downloads."""

    batch_id: int
    source_id: int
    source_name: str
    source_type: str
    season_id: int | None
    season_name: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    items_total: int
    items_success: int
    items_failed: int
    items_skipped: int
    success_rate: float
    completion_rate: float
    error_message: str | None
    metadata: dict[str, Any] | None
    downloads: list[DownloadItem]


# =============================================================================
# Failures
# =============================================================================


class FailedDownload(BaseModel):
    """Failed download with details."""

    progress_id: int
    batch_id: int | None
    source_id: int
    source_name: str
    source_type: str
    season_id: int | None
    item_key: str
    status: str
    attempts: int
    last_attempt_at: datetime | None
    error_message: str | None


class FailureListResponse(PaginatedResponse):
    """Paginated list of failures."""

    failures: list[FailedDownload]


class RetryResponse(BaseModel):
    """Response after queuing retry."""

    progress_id: int
    status: str
    message: str


class CleanupResponse(BaseModel):
    """Response after cleanup operation."""

    batches_deleted: int
    downloads_deleted: int
    message: str


class DeleteSeasonResponse(BaseModel):
    """Response after deleting season data."""

    season_id: int
    dry_run: bool
    deleted_counts: dict[str, int]
    total_records_deleted: int
    execution_time_ms: float
    message: str


# =============================================================================
# Sources
# =============================================================================


class SourceHealth(BaseModel):
    """Health status for a data source."""

    source_id: int
    source_name: str
    source_type: str
    is_active: bool
    rate_limit_ms: int | None
    max_concurrent: int | None
    latest_batch_id: int | None
    latest_status: str | None
    latest_started_at: datetime | None
    latest_completed_at: datetime | None
    batches_last_24h: int
    items_last_24h: int
    success_last_24h: int
    failed_last_24h: int
    success_rate_24h: float | None
    total_batches: int
    total_items_all_time: int
    success_items_all_time: int
    health_status: str
    refreshed_at: datetime | None


class SourceListResponse(BaseModel):
    """List of source health statuses."""

    sources: list[SourceHealth]
    total: int


# =============================================================================
# Timeseries
# =============================================================================


class TimeseriesDataPoint(BaseModel):
    """Single data point in timeseries."""

    timestamp: datetime
    success_count: int
    failure_count: int
    total_count: int


class TimeseriesResponse(BaseModel):
    """Timeseries data for progress chart."""

    period: str  # "24h", "7d", "30d"
    data: list[TimeseriesDataPoint]
    generated_at: datetime
