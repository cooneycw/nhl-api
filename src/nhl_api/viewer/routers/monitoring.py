"""Monitoring endpoints for data pipeline status.

Provides endpoints for:
- Dashboard overview (active batches, success rates, recent failures)
- Batch listing and details
- Failed download tracking and retry
- Data source health status
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db
from nhl_api.viewer.schemas.monitoring import (
    BatchDetail,
    BatchListResponse,
    BatchSummary,
    DashboardResponse,
    DashboardStats,
    DownloadItem,
    FailedDownload,
    FailureListResponse,
    RecentFailure,
    RetryResponse,
    SourceHealth,
    SourceListResponse,
)

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# =============================================================================
# Dashboard Endpoint
# =============================================================================


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Dashboard Overview",
    description="Get overview statistics including active batches, success rates, and recent failures",
)
async def get_dashboard(db: DbDep) -> DashboardResponse:
    """Get dashboard overview with aggregated stats and recent failures."""
    # Get active batches count
    active_batches = await db.fetchval(
        "SELECT COUNT(*) FROM import_batches WHERE status = 'running'"
    )

    # Get completed today count
    completed_today = await db.fetchval(
        """
        SELECT COUNT(*) FROM import_batches
        WHERE status = 'completed' AND completed_at >= CURRENT_DATE
        """
    )

    # Get failed today count
    failed_today = await db.fetchval(
        """
        SELECT COUNT(*) FROM import_batches
        WHERE status = 'failed' AND completed_at >= CURRENT_DATE
        """
    )

    # Get 24h stats from source health view
    source_stats = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(items_last_24h), 0) as total_items,
            CASE WHEN SUM(items_last_24h) > 0
                 THEN ROUND((SUM(success_last_24h)::DECIMAL / SUM(items_last_24h)) * 100, 2)
                 ELSE NULL END as success_rate,
            COUNT(*) FILTER (WHERE health_status = 'healthy') as healthy,
            COUNT(*) FILTER (WHERE health_status = 'degraded') as degraded,
            COUNT(*) FILTER (WHERE health_status = 'error') as error
        FROM mv_source_health
        WHERE is_active = TRUE
        """
    )

    # Get recent failures (limit 10)
    failure_rows = await db.fetch(
        """
        SELECT
            dp.progress_id,
            ds.name as source_name,
            dp.item_key,
            dp.error_message,
            dp.last_attempt_at
        FROM download_progress dp
        JOIN data_sources ds ON dp.source_id = ds.source_id
        WHERE dp.status = 'failed'
        ORDER BY dp.last_attempt_at DESC NULLS LAST
        LIMIT 10
        """
    )

    recent_failures = [
        RecentFailure(
            progress_id=row["progress_id"],
            source_name=row["source_name"],
            item_key=row["item_key"],
            error_message=row["error_message"],
            last_attempt_at=row["last_attempt_at"],
        )
        for row in failure_rows
    ]

    stats = DashboardStats(
        active_batches=active_batches or 0,
        completed_today=completed_today or 0,
        failed_today=failed_today or 0,
        success_rate_24h=float(source_stats["success_rate"])
        if source_stats and source_stats["success_rate"]
        else None,
        total_items_24h=source_stats["total_items"] if source_stats else 0,
        sources_healthy=source_stats["healthy"] if source_stats else 0,
        sources_degraded=source_stats["degraded"] if source_stats else 0,
        sources_error=source_stats["error"] if source_stats else 0,
    )

    return DashboardResponse(
        stats=stats,
        recent_failures=recent_failures,
        timestamp=datetime.now(UTC),
    )


# =============================================================================
# Batches Endpoints
# =============================================================================


@router.get(
    "/batches",
    response_model=BatchListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Batches",
    description="Get paginated list of download batches with optional filters",
)
async def list_batches(
    db: DbDep,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    batch_status: str | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    source_id: int | None = Query(default=None, description="Filter by source ID"),
) -> BatchListResponse:
    """Get paginated list of batches with optional filters."""
    # Count total matching records
    total = await db.fetchval(
        """
        SELECT COUNT(*) FROM mv_download_batch_stats
        WHERE ($1::text IS NULL OR status = $1)
          AND ($2::int IS NULL OR source_id = $2)
        """,
        batch_status,
        source_id,
    )

    # Calculate pagination
    offset = (page - 1) * page_size
    pages = math.ceil(total / page_size) if total > 0 else 1

    # Get batch data
    rows = await db.fetch(
        """
        SELECT
            batch_id, source_id, source_name, source_type,
            season_id, season_name, status, started_at, completed_at,
            duration_seconds, items_total, items_success, items_failed,
            items_skipped, success_rate, completion_rate
        FROM mv_download_batch_stats
        WHERE ($1::text IS NULL OR status = $1)
          AND ($2::int IS NULL OR source_id = $2)
        ORDER BY started_at DESC
        LIMIT $3 OFFSET $4
        """,
        batch_status,
        source_id,
        page_size,
        offset,
    )

    batches = [
        BatchSummary(
            batch_id=row["batch_id"],
            source_id=row["source_id"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            season_id=row["season_id"],
            season_name=row["season_name"],
            status=row["status"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_seconds=float(row["duration_seconds"])
            if row["duration_seconds"]
            else None,
            items_total=row["items_total"] or 0,
            items_success=row["items_success"] or 0,
            items_failed=row["items_failed"] or 0,
            items_skipped=row["items_skipped"] or 0,
            success_rate=float(row["success_rate"]) if row["success_rate"] else 0.0,
            completion_rate=float(row["completion_rate"])
            if row["completion_rate"]
            else 0.0,
        )
        for row in rows
    ]

    return BatchListResponse(
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=pages,
        batches=batches,
    )


@router.get(
    "/batches/{batch_id}",
    response_model=BatchDetail,
    status_code=status.HTTP_200_OK,
    summary="Batch Detail",
    description="Get detailed information about a specific batch including its downloads",
)
async def get_batch_detail(
    db: DbDep,
    batch_id: int,
) -> BatchDetail:
    """Get batch detail with all download items."""
    # Get batch info
    batch = await db.fetchrow(
        """
        SELECT
            batch_id, source_id, source_name, source_type,
            season_id, season_name, status, started_at, completed_at,
            duration_seconds, items_total, items_success, items_failed,
            items_skipped, success_rate, completion_rate, error_message, metadata
        FROM mv_download_batch_stats
        WHERE batch_id = $1
        """,
        batch_id,
    )

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )

    # Get download items
    download_rows = await db.fetch(
        """
        SELECT
            progress_id, item_key, status, attempts,
            last_attempt_at, completed_at, error_message,
            response_size_bytes, response_time_ms
        FROM download_progress
        WHERE batch_id = $1
        ORDER BY
            CASE status
                WHEN 'failed' THEN 1
                WHEN 'pending' THEN 2
                ELSE 3
            END,
            last_attempt_at DESC NULLS LAST
        """,
        batch_id,
    )

    downloads = [
        DownloadItem(
            progress_id=row["progress_id"],
            item_key=row["item_key"],
            status=row["status"],
            attempts=row["attempts"] or 0,
            last_attempt_at=row["last_attempt_at"],
            completed_at=row["completed_at"],
            error_message=row["error_message"],
            response_size_bytes=row["response_size_bytes"],
            response_time_ms=row["response_time_ms"],
        )
        for row in download_rows
    ]

    return BatchDetail(
        batch_id=batch["batch_id"],
        source_id=batch["source_id"],
        source_name=batch["source_name"],
        source_type=batch["source_type"],
        season_id=batch["season_id"],
        season_name=batch["season_name"],
        status=batch["status"],
        started_at=batch["started_at"],
        completed_at=batch["completed_at"],
        duration_seconds=float(batch["duration_seconds"])
        if batch["duration_seconds"]
        else None,
        items_total=batch["items_total"] or 0,
        items_success=batch["items_success"] or 0,
        items_failed=batch["items_failed"] or 0,
        items_skipped=batch["items_skipped"] or 0,
        success_rate=float(batch["success_rate"]) if batch["success_rate"] else 0.0,
        completion_rate=float(batch["completion_rate"])
        if batch["completion_rate"]
        else 0.0,
        error_message=batch["error_message"],
        metadata=dict(batch["metadata"]) if batch["metadata"] else None,
        downloads=downloads,
    )


# =============================================================================
# Failures Endpoints
# =============================================================================


@router.get(
    "/failures",
    response_model=FailureListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Failures",
    description="Get paginated list of failed downloads",
)
async def list_failures(
    db: DbDep,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    source_id: int | None = Query(default=None, description="Filter by source ID"),
) -> FailureListResponse:
    """Get paginated list of failed downloads."""
    # Count total failures
    total = await db.fetchval(
        """
        SELECT COUNT(*) FROM download_progress
        WHERE status = 'failed'
          AND ($1::int IS NULL OR source_id = $1)
        """,
        source_id,
    )

    # Calculate pagination
    offset = (page - 1) * page_size
    pages = math.ceil(total / page_size) if total > 0 else 1

    # Get failure data
    rows = await db.fetch(
        """
        SELECT
            dp.progress_id, dp.batch_id, dp.source_id,
            ds.name as source_name, ds.source_type,
            dp.season_id, dp.item_key, dp.status,
            dp.attempts, dp.last_attempt_at, dp.error_message
        FROM download_progress dp
        JOIN data_sources ds ON dp.source_id = ds.source_id
        WHERE dp.status = 'failed'
          AND ($1::int IS NULL OR dp.source_id = $1)
        ORDER BY dp.last_attempt_at DESC NULLS LAST
        LIMIT $2 OFFSET $3
        """,
        source_id,
        page_size,
        offset,
    )

    failures = [
        FailedDownload(
            progress_id=row["progress_id"],
            batch_id=row["batch_id"],
            source_id=row["source_id"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            season_id=row["season_id"],
            item_key=row["item_key"],
            status=row["status"],
            attempts=row["attempts"] or 0,
            last_attempt_at=row["last_attempt_at"],
            error_message=row["error_message"],
        )
        for row in rows
    ]

    return FailureListResponse(
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=pages,
        failures=failures,
    )


@router.post(
    "/failures/{progress_id}/retry",
    response_model=RetryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retry Failed Download",
    description="Queue a failed download for retry by resetting its status to pending",
)
async def retry_failure(
    db: DbDep,
    progress_id: int,
) -> RetryResponse:
    """Queue a failed download for retry."""
    # Update the status to pending
    result = await db.fetchval(
        """
        UPDATE download_progress
        SET status = 'pending', attempts = 0, error_message = NULL
        WHERE progress_id = $1 AND status = 'failed'
        RETURNING progress_id
        """,
        progress_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed download {progress_id} not found or not in failed status",
        )

    return RetryResponse(
        progress_id=progress_id,
        status="pending",
        message="Download queued for retry",
    )


# =============================================================================
# Sources Endpoint
# =============================================================================


@router.get(
    "/sources",
    response_model=SourceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Sources",
    description="Get health status for all data sources",
)
async def list_sources(
    db: DbDep,
    active_only: bool = Query(default=True, description="Only show active sources"),
) -> SourceListResponse:
    """Get health status for all data sources."""
    rows = await db.fetch(
        """
        SELECT
            source_id, source_name, source_type, is_active,
            rate_limit_ms, max_concurrent, latest_batch_id, latest_status,
            latest_started_at, latest_completed_at, batches_last_24h,
            items_last_24h, success_last_24h, failed_last_24h,
            success_rate_24h, total_batches, total_items_all_time,
            success_items_all_time, health_status, refreshed_at
        FROM mv_source_health
        WHERE ($1::boolean IS FALSE OR is_active = TRUE)
        ORDER BY
            CASE health_status
                WHEN 'error' THEN 1
                WHEN 'degraded' THEN 2
                WHEN 'running' THEN 3
                ELSE 4
            END,
            source_name
        """,
        active_only,
    )

    sources = [
        SourceHealth(
            source_id=row["source_id"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            is_active=row["is_active"],
            rate_limit_ms=row["rate_limit_ms"],
            max_concurrent=row["max_concurrent"],
            latest_batch_id=row["latest_batch_id"],
            latest_status=row["latest_status"],
            latest_started_at=row["latest_started_at"],
            latest_completed_at=row["latest_completed_at"],
            batches_last_24h=row["batches_last_24h"] or 0,
            items_last_24h=row["items_last_24h"] or 0,
            success_last_24h=row["success_last_24h"] or 0,
            failed_last_24h=row["failed_last_24h"] or 0,
            success_rate_24h=float(row["success_rate_24h"])
            if row["success_rate_24h"]
            else None,
            total_batches=row["total_batches"] or 0,
            total_items_all_time=row["total_items_all_time"] or 0,
            success_items_all_time=row["success_items_all_time"] or 0,
            health_status=row["health_status"] or "unknown",
            refreshed_at=row["refreshed_at"],
        )
        for row in rows
    ]

    return SourceListResponse(
        sources=sources,
        total=len(sources),
    )
