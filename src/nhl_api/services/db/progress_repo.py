"""Repository for download progress tracking.

This module provides database persistence for tracking download progress,
enabling resumable downloads and progress monitoring.

Usage:
    from nhl_api.services.db import DatabaseService, ProgressRepository

    async with DatabaseService() as db:
        repo = ProgressRepository(db)
        progress_id = await repo.upsert_progress(
            source_id=1,
            item_key="2024020001",
            season_id=20242025,
        )
        await repo.mark_success(progress_id)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nhl_api.services.db.connection import DatabaseService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProgressEntry:
    """Represents a download_progress table row.

    Attributes:
        progress_id: Primary key.
        source_id: Foreign key to data_sources table.
        season_id: Foreign key to seasons table (optional).
        item_key: Unique identifier for the item (game_id, player_id, etc.).
        status: Current status (pending, success, failed, skipped).
        attempts: Number of download attempts.
        batch_id: Foreign key to import_batches table (optional).
        last_attempt_at: Timestamp of last attempt.
        completed_at: Timestamp of successful completion.
        error_message: Error message if failed.
        response_size_bytes: Size of downloaded response.
        response_time_ms: Response time in milliseconds.
        created_at: Timestamp of record creation.
    """

    progress_id: int
    source_id: int
    season_id: int | None
    item_key: str
    status: str
    attempts: int
    batch_id: int | None = None
    last_attempt_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    response_size_bytes: int | None = None
    response_time_ms: int | None = None
    created_at: datetime | None = None

    @classmethod
    def from_record(cls, record: Any) -> ProgressEntry:
        """Create a ProgressEntry from an asyncpg Record.

        Args:
            record: An asyncpg Record object.

        Returns:
            A ProgressEntry instance.
        """
        return cls(
            progress_id=record["progress_id"],
            source_id=record["source_id"],
            season_id=record["season_id"],
            item_key=record["item_key"],
            status=record["status"],
            attempts=record["attempts"],
            batch_id=record["batch_id"],
            last_attempt_at=record["last_attempt_at"],
            completed_at=record["completed_at"],
            error_message=record["error_message"],
            response_size_bytes=record["response_size_bytes"],
            response_time_ms=record["response_time_ms"],
            created_at=record["created_at"],
        )


class ProgressRepository:
    """Repository for download_progress table operations.

    Provides methods for tracking download progress with support for:
    - Upsert operations for idempotent progress tracking
    - Status updates (success, failed, skipped)
    - Querying pending and incomplete items
    - Batch-level statistics
    - Retry tracking

    Example:
        >>> repo = ProgressRepository(db)
        >>> progress_id = await repo.upsert_progress(
        ...     source_id=1,
        ...     item_key="2024020001",
        ...     season_id=20242025,
        ... )
        >>> await repo.increment_attempts(progress_id)
        >>> await repo.mark_success(progress_id, response_time_ms=150)
    """

    def __init__(self, db: DatabaseService) -> None:
        """Initialize the repository.

        Args:
            db: Database service instance.
        """
        self.db = db

    # Create/Upsert operations

    async def upsert_progress(
        self,
        source_id: int,
        item_key: str,
        *,
        season_id: int | None = None,
        batch_id: int | None = None,
        status: str = "pending",
    ) -> int:
        """Create or update a progress entry.

        Uses PostgreSQL ON CONFLICT to handle existing entries.
        On conflict, updates batch_id (if provided) and status.

        Args:
            source_id: Data source ID.
            item_key: Unique item identifier (game_id, player_id, etc.).
            season_id: Season ID (optional).
            batch_id: Import batch ID (optional).
            status: Initial status (default: pending).

        Returns:
            The progress_id of the upserted entry.
        """
        query = """
            INSERT INTO download_progress (source_id, season_id, item_key, batch_id, status)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (source_id, season_id, item_key)
            DO UPDATE SET
                batch_id = COALESCE(EXCLUDED.batch_id, download_progress.batch_id),
                status = EXCLUDED.status,
                last_attempt_at = CURRENT_TIMESTAMP
            RETURNING progress_id
        """
        result = await self.db.fetchval(
            query, source_id, season_id, item_key, batch_id, status
        )
        logger.debug(
            "Upserted progress: source_id=%d, item_key=%s, progress_id=%d",
            source_id,
            item_key,
            result,
        )
        return int(result)

    # Read operations

    async def get_by_id(self, progress_id: int) -> ProgressEntry | None:
        """Get a progress entry by ID.

        Args:
            progress_id: The progress entry ID.

        Returns:
            The ProgressEntry or None if not found.
        """
        query = "SELECT * FROM download_progress WHERE progress_id = $1"
        record = await self.db.fetchrow(query, progress_id)
        if record is None:
            return None
        return ProgressEntry.from_record(record)

    async def get_by_key(
        self,
        source_id: int,
        season_id: int | None,
        item_key: str,
    ) -> ProgressEntry | None:
        """Get a progress entry by unique key.

        Args:
            source_id: Data source ID.
            season_id: Season ID (can be None).
            item_key: Item identifier.

        Returns:
            The ProgressEntry or None if not found.
        """
        if season_id is None:
            query = """
                SELECT * FROM download_progress
                WHERE source_id = $1 AND season_id IS NULL AND item_key = $2
            """
            record = await self.db.fetchrow(query, source_id, item_key)
        else:
            query = """
                SELECT * FROM download_progress
                WHERE source_id = $1 AND season_id = $2 AND item_key = $3
            """
            record = await self.db.fetchrow(query, source_id, season_id, item_key)
        if record is None:
            return None
        return ProgressEntry.from_record(record)

    async def get_pending(
        self,
        source_id: int,
        season_id: int | None,
        *,
        limit: int | None = None,
    ) -> list[ProgressEntry]:
        """Get pending progress entries.

        Args:
            source_id: Data source ID.
            season_id: Season ID (can be None).
            limit: Maximum number of entries to return.

        Returns:
            List of pending ProgressEntry objects.
        """
        if season_id is None:
            base_query = """
                SELECT * FROM download_progress
                WHERE source_id = $1 AND season_id IS NULL AND status = 'pending'
                ORDER BY created_at
            """
            params: tuple[Any, ...] = (source_id,)
        else:
            base_query = """
                SELECT * FROM download_progress
                WHERE source_id = $1 AND season_id = $2 AND status = 'pending'
                ORDER BY created_at
            """
            params = (source_id, season_id)

        if limit is not None:
            base_query += f" LIMIT {limit}"

        records = await self.db.fetch(base_query, *params)
        return [ProgressEntry.from_record(r) for r in records]

    async def get_incomplete(
        self,
        source_id: int,
        season_id: int | None,
    ) -> list[ProgressEntry]:
        """Get incomplete progress entries (pending or failed).

        Args:
            source_id: Data source ID.
            season_id: Season ID (can be None).

        Returns:
            List of incomplete ProgressEntry objects.
        """
        if season_id is None:
            query = """
                SELECT * FROM download_progress
                WHERE source_id = $1 AND season_id IS NULL
                    AND status IN ('pending', 'failed')
                ORDER BY created_at
            """
            records = await self.db.fetch(query, source_id)
        else:
            query = """
                SELECT * FROM download_progress
                WHERE source_id = $1 AND season_id = $2
                    AND status IN ('pending', 'failed')
                ORDER BY created_at
            """
            records = await self.db.fetch(query, source_id, season_id)
        return [ProgressEntry.from_record(r) for r in records]

    # Update operations

    async def mark_success(
        self,
        progress_id: int,
        *,
        response_size_bytes: int | None = None,
        response_time_ms: int | None = None,
    ) -> None:
        """Mark a progress entry as successful.

        Args:
            progress_id: The progress entry ID.
            response_size_bytes: Size of the response (optional).
            response_time_ms: Response time in milliseconds (optional).
        """
        query = """
            UPDATE download_progress
            SET status = 'success',
                completed_at = CURRENT_TIMESTAMP,
                response_size_bytes = $2,
                response_time_ms = $3
            WHERE progress_id = $1
        """
        await self.db.execute(query, progress_id, response_size_bytes, response_time_ms)
        logger.debug("Marked progress %d as success", progress_id)

    async def mark_failed(
        self,
        progress_id: int,
        error_message: str,
    ) -> None:
        """Mark a progress entry as failed.

        Args:
            progress_id: The progress entry ID.
            error_message: Description of the failure.
        """
        query = """
            UPDATE download_progress
            SET status = 'failed',
                error_message = $2,
                last_attempt_at = CURRENT_TIMESTAMP
            WHERE progress_id = $1
        """
        await self.db.execute(query, progress_id, error_message)
        logger.debug("Marked progress %d as failed: %s", progress_id, error_message)

    async def mark_skipped(
        self,
        progress_id: int,
        reason: str | None = None,
    ) -> None:
        """Mark a progress entry as skipped.

        Args:
            progress_id: The progress entry ID.
            reason: Reason for skipping (optional).
        """
        query = """
            UPDATE download_progress
            SET status = 'skipped',
                error_message = $2,
                completed_at = CURRENT_TIMESTAMP
            WHERE progress_id = $1
        """
        await self.db.execute(query, progress_id, reason)
        logger.debug("Marked progress %d as skipped", progress_id)

    async def increment_attempts(self, progress_id: int) -> int:
        """Increment the attempt count for a progress entry.

        Args:
            progress_id: The progress entry ID.

        Returns:
            The new attempt count.
        """
        query = """
            UPDATE download_progress
            SET attempts = attempts + 1,
                last_attempt_at = CURRENT_TIMESTAMP
            WHERE progress_id = $1
            RETURNING attempts
        """
        result = await self.db.fetchval(query, progress_id)
        logger.debug("Incremented attempts for progress %d to %d", progress_id, result)
        return int(result)

    # Batch operations

    async def get_batch_stats(self, batch_id: int) -> dict[str, int]:
        """Get statistics for a batch.

        Args:
            batch_id: The import batch ID.

        Returns:
            Dictionary with counts: {pending, success, failed, skipped, total}.
        """
        query = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'success') AS success,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                COUNT(*) FILTER (WHERE status = 'skipped') AS skipped,
                COUNT(*) AS total
            FROM download_progress
            WHERE batch_id = $1
        """
        record = await self.db.fetchrow(query, batch_id)
        if record is None:
            return {"pending": 0, "success": 0, "failed": 0, "skipped": 0, "total": 0}
        return {
            "pending": record["pending"] or 0,
            "success": record["success"] or 0,
            "failed": record["failed"] or 0,
            "skipped": record["skipped"] or 0,
            "total": record["total"] or 0,
        }

    async def reset_failed(
        self,
        source_id: int,
        season_id: int | None,
    ) -> int:
        """Reset failed entries to pending status.

        Args:
            source_id: Data source ID.
            season_id: Season ID (can be None).

        Returns:
            Number of entries reset.
        """
        if season_id is None:
            query = """
                UPDATE download_progress
                SET status = 'pending',
                    error_message = NULL,
                    last_attempt_at = CURRENT_TIMESTAMP
                WHERE source_id = $1 AND season_id IS NULL AND status = 'failed'
            """
            result = await self.db.execute(query, source_id)
        else:
            query = """
                UPDATE download_progress
                SET status = 'pending',
                    error_message = NULL,
                    last_attempt_at = CURRENT_TIMESTAMP
                WHERE source_id = $1 AND season_id = $2 AND status = 'failed'
            """
            result = await self.db.execute(query, source_id, season_id)

        # Parse "UPDATE N" to get count
        count = int(result.split()[-1]) if result else 0
        logger.info(
            "Reset %d failed entries for source_id=%d, season_id=%s",
            count,
            source_id,
            season_id,
        )
        return count
