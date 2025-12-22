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

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db
from nhl_api.viewer.schemas.monitoring import (
    BatchDetail,
    BatchListResponse,
    BatchSummary,
    CleanupResponse,
    DashboardResponse,
    DashboardStats,
    DeleteSeasonResponse,
    DownloadItem,
    FailedDownload,
    FailureListResponse,
    RecentFailure,
    RetryResponse,
    SourceHealth,
    SourceListResponse,
    TimeseriesDataPoint,
    TimeseriesResponse,
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


@router.delete(
    "/cleanup",
    response_model=CleanupResponse,
    status_code=status.HTTP_200_OK,
    summary="Cleanup Failed Batches",
    description="Delete failed batches and their associated download records",
)
async def cleanup_failed_batches(
    db: DbDep,
    include_completed: bool = Query(
        default=False,
        description="Also delete completed batches older than retention days",
    ),
    retention_days: int = Query(
        default=7, ge=1, le=365, description="Days to retain (for completed batches)"
    ),
) -> CleanupResponse:
    """Delete failed batches and optionally old completed batches.

    This removes:
    - All failed batches and their download_progress records
    - Optionally: completed batches older than retention_days
    """
    # First, delete download_progress records for failed batches
    downloads_deleted = (
        await db.fetchval(
            """
        WITH deleted AS (
            DELETE FROM download_progress
            WHERE batch_id IN (
                SELECT batch_id FROM import_batches WHERE status = 'failed'
            )
            RETURNING 1
        )
        SELECT COUNT(*) FROM deleted
        """
        )
        or 0
    )

    # Delete failed batches
    batches_deleted = (
        await db.fetchval(
            """
        WITH deleted AS (
            DELETE FROM import_batches
            WHERE status = 'failed'
            RETURNING 1
        )
        SELECT COUNT(*) FROM deleted
        """
        )
        or 0
    )

    # Optionally delete old completed batches
    if include_completed:
        old_downloads = (
            await db.fetchval(
                """
            WITH deleted AS (
                DELETE FROM download_progress
                WHERE batch_id IN (
                    SELECT batch_id FROM import_batches
                    WHERE status = 'completed'
                      AND completed_at < NOW() - INTERVAL '1 day' * $1
                )
                RETURNING 1
            )
            SELECT COUNT(*) FROM deleted
            """,
                retention_days,
            )
            or 0
        )
        downloads_deleted += old_downloads

        old_batches = (
            await db.fetchval(
                """
            WITH deleted AS (
                DELETE FROM import_batches
                WHERE status = 'completed'
                  AND completed_at < NOW() - INTERVAL '1 day' * $1
                RETURNING 1
            )
            SELECT COUNT(*) FROM deleted
            """,
                retention_days,
            )
            or 0
        )
        batches_deleted += old_batches

    # Refresh materialized views to update dashboard
    await db.execute("SELECT refresh_viewer_views(concurrent := TRUE)")

    message = (
        f"Deleted {batches_deleted} batches and {downloads_deleted} download records"
    )
    if include_completed:
        message += f" (including completed batches older than {retention_days} days)"

    return CleanupResponse(
        batches_deleted=batches_deleted,
        downloads_deleted=downloads_deleted,
        message=message,
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


# =============================================================================
# Timeseries Endpoint
# =============================================================================


@router.get(
    "/timeseries",
    response_model=TimeseriesResponse,
    status_code=status.HTTP_200_OK,
    summary="Download Activity Timeseries",
    description="Get time-bucketed download activity for progress charts",
)
async def get_timeseries(
    db: DbDep,
    period: str = Query(
        default="24h",
        regex="^(24h|7d|30d)$",
        description="Time period: 24h (hourly), 7d (daily), 30d (daily)",
    ),
) -> TimeseriesResponse:
    """Get timeseries data for download activity visualization.

    Returns success/failure counts bucketed by time interval:
    - 24h: hourly buckets for the last 24 hours
    - 7d: daily buckets for the last 7 days
    - 30d: daily buckets for the last 30 days
    """
    # Determine interval and lookback based on period
    if period == "24h":
        interval = "hour"
        lookback = "24 hours"
    elif period == "7d":
        interval = "day"
        lookback = "7 days"
    else:  # 30d
        interval = "day"
        lookback = "30 days"

    # Query with time bucketing using date_trunc
    rows = await db.fetch(
        f"""
        WITH time_buckets AS (
            SELECT
                date_trunc($1, dp.completed_at) AS bucket,
                COUNT(*) FILTER (WHERE dp.status = 'success') AS success_count,
                COUNT(*) FILTER (WHERE dp.status = 'failed') AS failure_count,
                COUNT(*) AS total_count
            FROM download_progress dp
            WHERE dp.completed_at >= NOW() - INTERVAL '{lookback}'
              AND dp.completed_at IS NOT NULL
            GROUP BY date_trunc($1, dp.completed_at)
        )
        SELECT bucket, success_count, failure_count, total_count
        FROM time_buckets
        ORDER BY bucket ASC
        """,
        interval,
    )

    data = [
        TimeseriesDataPoint(
            timestamp=row["bucket"],
            success_count=row["success_count"] or 0,
            failure_count=row["failure_count"] or 0,
            total_count=row["total_count"] or 0,
        )
        for row in rows
    ]

    return TimeseriesResponse(
        period=period,
        data=data,
        generated_at=datetime.now(UTC),
    )


# =============================================================================
# Delete Season Data Endpoint
# =============================================================================


@router.delete(
    "/seasons/{season_id}/data",
    response_model=DeleteSeasonResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Season Data",
    description="Delete all data for a specific season (games, stats, downloads, etc.)",
)
async def delete_season_data(
    db: DbDep,
    season_id: int = Path(..., description="Season ID to delete (e.g., 20242025)"),
    dry_run: bool = Query(
        default=True,
        description="Preview deletion without executing (dry run mode)",
    ),
) -> DeleteSeasonResponse:
    """Delete all data for a specific season.

    **DANGEROUS OPERATION**: This permanently deletes all data for the specified season.

    Deletes in cascade order (respecting foreign keys):
    1. game_events
    2. game_skater_stats
    3. game_goalie_stats
    4. game_shifts
    5. game_team_stats
    6. player_game_logs
    7. games
    8. download_progress
    9. import_batches

    Args:
        season_id: The season ID to delete (e.g., 20242025)
        dry_run: If True (default), preview what would be deleted without executing

    Returns:
        DeleteSeasonResponse with counts of deleted records per table
    """
    import time

    start_time = time.time()
    deleted_counts: dict[str, int] = {}

    # Tables to delete from (in cascade order)
    tables = [
        "game_events",
        "game_skater_stats",
        "game_goalie_stats",
        "game_shifts",
        "game_team_stats",
        "player_game_logs",
        "games",
        "download_progress",
        "import_batches",
    ]

    if dry_run:
        # Dry run: count what would be deleted
        for table in tables:
            # Build appropriate WHERE clause based on table
            if table in ["download_progress", "import_batches"]:
                where_clause = f"WHERE season_id = {season_id}"
            elif table == "games":
                where_clause = f"WHERE season_id = {season_id}"
            elif table in [
                "game_events",
                "game_skater_stats",
                "game_goalie_stats",
                "game_shifts",
                "game_team_stats",
                "player_game_logs",
            ]:
                where_clause = f"WHERE game_id IN (SELECT game_id FROM games WHERE season_id = {season_id})"
            else:
                continue

            count = await db.fetchval(f"SELECT COUNT(*) FROM {table} {where_clause}")
            deleted_counts[table] = count or 0

    else:
        # Real deletion: execute within transaction
        async with db.transaction():
            # Delete game-related records first
            for table in [
                "game_events",
                "game_skater_stats",
                "game_goalie_stats",
                "game_shifts",
                "game_team_stats",
                "player_game_logs",
            ]:
                result = await db.fetchval(
                    f"""
                    WITH deleted AS (
                        DELETE FROM {table}
                        WHERE game_id IN (SELECT game_id FROM games WHERE season_id = $1)
                        RETURNING *
                    )
                    SELECT COUNT(*) FROM deleted
                    """,
                    season_id,
                )
                deleted_counts[table] = result or 0

            # Delete games
            result = await db.fetchval(
                """
                WITH deleted AS (
                    DELETE FROM games
                    WHERE season_id = $1
                    RETURNING *
                )
                SELECT COUNT(*) FROM deleted
                """,
                season_id,
            )
            deleted_counts["games"] = result or 0

            # Delete download monitoring records
            result = await db.fetchval(
                """
                WITH deleted AS (
                    DELETE FROM download_progress
                    WHERE season_id = $1
                    RETURNING *
                )
                SELECT COUNT(*) FROM deleted
                """,
                season_id,
            )
            deleted_counts["download_progress"] = result or 0

            result = await db.fetchval(
                """
                WITH deleted AS (
                    DELETE FROM import_batches
                    WHERE season_id = $1
                    RETURNING *
                )
                SELECT COUNT(*) FROM deleted
                """,
                season_id,
            )
            deleted_counts["import_batches"] = result or 0

        # Refresh materialized views after deletion
        await db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_summary")
        await db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_game_summary")
        await db.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_download_batch_stats"
        )
        await db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_source_health")
        await db.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_summary"
        )
        await db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_data_coverage")

    execution_time_ms = (time.time() - start_time) * 1000
    total_deleted = sum(deleted_counts.values())

    message = (
        f"Dry run: Would delete {total_deleted:,} records for season {season_id}"
        if dry_run
        else f"Successfully deleted {total_deleted:,} records for season {season_id}"
    )

    return DeleteSeasonResponse(
        season_id=season_id,
        dry_run=dry_run,
        deleted_counts=deleted_counts,
        total_records_deleted=total_deleted,
        execution_time_ms=execution_time_ms,
        message=message,
    )
