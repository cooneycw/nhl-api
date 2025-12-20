"""Progress tracker for resumable downloads.

This module provides in-memory progress tracking with database persistence,
enabling resumable downloads and real-time progress updates.

The tracker maintains per-item state (games, players, etc.) and synchronizes
with the database via ProgressRepository. It supports:
- Loading existing progress state from DB for resume
- Real-time callbacks for UI updates
- Aggregated statistics for monitoring
- Batch operations for efficient tracking

Example usage:
    from nhl_api.downloaders.progress import ProgressTracker
    from nhl_api.services.db import DatabaseService, ProgressRepository

    async with DatabaseService() as db:
        repo = ProgressRepository(db)
        tracker = ProgressTracker(
            repo,
            source_id=1,
            season_id=20242025,
            on_progress=lambda event: print(f"Progress: {event}"),
        )

        # Resume from last checkpoint
        await tracker.load_state()

        # Track downloads
        for game_id in games:
            if tracker.should_download(str(game_id)):
                await tracker.start_item(str(game_id))
                try:
                    # ... download logic ...
                    await tracker.complete_item(str(game_id))
                except Exception as e:
                    await tracker.fail_item(str(game_id), str(e))
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from nhl_api.services.db.progress_repo import ProgressRepository

logger = logging.getLogger(__name__)


class ProgressState(Enum):
    """State of a download item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Event emitted when progress changes.

    Attributes:
        source_id: Data source identifier.
        season_id: Season identifier (optional).
        item_key: Item being tracked (game_id, player_id, etc.).
        state: Current state of the item.
        stats: Aggregated progress statistics.
        message: Optional status message.
        timestamp: When the event occurred.
    """

    source_id: int
    item_key: str
    state: ProgressState
    stats: ProgressStats
    season_id: int | None = None
    message: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ProgressStats:
    """Aggregated progress statistics.

    Attributes:
        total: Total items to process (None if unknown).
        pending: Items waiting to be processed.
        in_progress: Items currently being processed.
        success: Successfully completed items.
        failed: Failed items.
        skipped: Skipped items.
        started_at: When tracking started.
        last_update: Last state change time.
    """

    total: int | None = None
    pending: int = 0
    in_progress: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_update: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def completed(self) -> int:
        """Total completed items (success + failed + skipped)."""
        return self.success + self.failed + self.skipped

    @property
    def processed(self) -> int:
        """Total processed items (completed + in_progress)."""
        return self.completed + self.in_progress

    @property
    def success_rate(self) -> float:
        """Success rate as percentage (0-100)."""
        if self.completed == 0:
            return 0.0
        return (self.success / self.completed) * 100

    @property
    def progress_percent(self) -> float:
        """Overall progress as percentage (0-100)."""
        if self.total is None or self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100

    @property
    def is_complete(self) -> bool:
        """Check if all items are processed."""
        if self.total is None:
            return False
        return self.completed >= self.total


class ProgressCallback(Protocol):
    """Protocol for progress callback functions."""

    def __call__(self, event: ProgressEvent) -> None:
        """Called when progress changes.

        Args:
            event: The progress event with current state and stats.
        """
        ...


@dataclass
class _ItemState:
    """Internal state for a tracked item."""

    key: str
    state: ProgressState
    progress_id: int | None = None
    attempts: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProgressTracker:
    """Track download progress with in-memory state and DB persistence.

    This class provides:
    - In-memory state for fast access during downloads
    - Database persistence via ProgressRepository for resume
    - Real-time callbacks for UI updates
    - Aggregated statistics for monitoring

    The tracker is designed to work with the download framework:
    1. Load existing state before starting (for resume)
    2. Register items to be downloaded
    3. Track item state transitions (start -> success/fail)
    4. Query which items need downloading

    Example:
        >>> tracker = ProgressTracker(repo, source_id=1, season_id=20242025)
        >>> await tracker.load_state()  # Resume from DB
        >>> for game_id in games:
        ...     if tracker.should_download(str(game_id)):
        ...         await tracker.start_item(str(game_id))
        ...         # ... download ...
        ...         await tracker.complete_item(str(game_id))
    """

    def __init__(
        self,
        repository: ProgressRepository,
        source_id: int,
        *,
        season_id: int | None = None,
        batch_id: int | None = None,
        on_progress: ProgressCallback | Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        """Initialize the progress tracker.

        Args:
            repository: Database repository for persistence.
            source_id: Data source identifier.
            season_id: Season identifier (optional).
            batch_id: Batch identifier for grouping (optional).
            on_progress: Callback for progress updates.
        """
        self._repo = repository
        self._source_id = source_id
        self._season_id = season_id
        self._batch_id = batch_id
        self._on_progress = on_progress

        # In-memory state
        self._items: dict[str, _ItemState] = {}
        self._stats = ProgressStats()
        self._started = False

        logger.debug(
            "Initialized ProgressTracker: source_id=%d, season_id=%s",
            source_id,
            season_id,
        )

    @property
    def source_id(self) -> int:
        """Data source identifier."""
        return self._source_id

    @property
    def season_id(self) -> int | None:
        """Season identifier."""
        return self._season_id

    @property
    def stats(self) -> ProgressStats:
        """Current progress statistics."""
        return self._stats

    @property
    def is_complete(self) -> bool:
        """Check if all registered items are processed."""
        return self._stats.is_complete

    async def load_state(self) -> int:
        """Load existing progress state from database.

        This method should be called before starting downloads to enable
        resume functionality. It loads all existing progress entries and
        populates the in-memory state.

        Returns:
            Number of entries loaded from database.
        """
        # Load incomplete items (pending + failed)
        entries = await self._repo.get_incomplete(self._source_id, self._season_id)

        for entry in entries:
            state = ProgressState.PENDING
            if entry.status == "failed":
                state = ProgressState.FAILED

            self._items[entry.item_key] = _ItemState(
                key=entry.item_key,
                state=state,
                progress_id=entry.progress_id,
                attempts=entry.attempts,
                error_message=entry.error_message,
            )

        # Update stats based on loaded state
        self._stats.pending = sum(
            1 for item in self._items.values() if item.state == ProgressState.PENDING
        )
        self._stats.failed = sum(
            1 for item in self._items.values() if item.state == ProgressState.FAILED
        )

        self._started = True
        logger.info(
            "Loaded %d incomplete items (pending=%d, failed=%d) for source_id=%d, season_id=%s",
            len(entries),
            self._stats.pending,
            self._stats.failed,
            self._source_id,
            self._season_id,
        )

        return len(entries)

    def set_total(self, total: int) -> None:
        """Set the total number of items to process.

        Args:
            total: Total item count.
        """
        self._stats.total = total
        logger.debug("Set total items to %d", total)

    async def register_item(self, item_key: str) -> int:
        """Register an item for tracking.

        Creates a pending entry in the database if it doesn't exist.

        Args:
            item_key: Unique identifier for the item.

        Returns:
            The progress_id from the database.
        """
        if item_key in self._items:
            item = self._items[item_key]
            if item.progress_id is not None:
                return item.progress_id

        # Create or update in database
        progress_id = await self._repo.upsert_progress(
            source_id=self._source_id,
            item_key=item_key,
            season_id=self._season_id,
            batch_id=self._batch_id,
            status="pending",
        )

        # Update in-memory state
        if item_key not in self._items:
            self._items[item_key] = _ItemState(
                key=item_key,
                state=ProgressState.PENDING,
                progress_id=progress_id,
            )
            self._stats.pending += 1
        else:
            self._items[item_key].progress_id = progress_id

        return progress_id

    async def register_items(self, item_keys: list[str]) -> None:
        """Register multiple items for tracking.

        More efficient than calling register_item individually.

        Args:
            item_keys: List of unique identifiers.
        """
        for item_key in item_keys:
            await self.register_item(item_key)

        if self._stats.total is None:
            self._stats.total = len(self._items)

        logger.debug("Registered %d items for tracking", len(item_keys))

    def should_download(self, item_key: str) -> bool:
        """Check if an item should be downloaded.

        Returns True if the item is pending or failed (for retry).
        Returns False if already completed or in progress.

        Args:
            item_key: Item identifier.

        Returns:
            True if the item needs to be downloaded.
        """
        if item_key not in self._items:
            return True  # Unknown items should be downloaded

        item = self._items[item_key]
        return item.state in (ProgressState.PENDING, ProgressState.FAILED)

    def get_pending_items(self) -> list[str]:
        """Get all pending item keys.

        Returns:
            List of item keys that need to be downloaded.
        """
        return [
            key
            for key, item in self._items.items()
            if item.state == ProgressState.PENDING
        ]

    def get_failed_items(self) -> list[str]:
        """Get all failed item keys.

        Returns:
            List of item keys that failed and may be retried.
        """
        return [
            key
            for key, item in self._items.items()
            if item.state == ProgressState.FAILED
        ]

    async def start_item(self, item_key: str) -> None:
        """Mark an item as in progress.

        Args:
            item_key: Item identifier.
        """
        # Ensure item is registered
        if item_key not in self._items:
            await self.register_item(item_key)

        item = self._items[item_key]
        old_state = item.state

        # Update in-memory state
        item.state = ProgressState.IN_PROGRESS
        item.started_at = datetime.now(UTC)
        item.attempts += 1

        # Update stats
        if old_state == ProgressState.PENDING:
            self._stats.pending -= 1
        elif old_state == ProgressState.FAILED:
            self._stats.failed -= 1
        self._stats.in_progress += 1
        self._stats.last_update = datetime.now(UTC)

        # Update database
        if item.progress_id is not None:
            await self._repo.increment_attempts(item.progress_id)

        # Notify callback
        self._notify(item_key, ProgressState.IN_PROGRESS)

        logger.debug("Started item %s (attempt %d)", item_key, item.attempts)

    async def complete_item(
        self,
        item_key: str,
        *,
        response_size_bytes: int | None = None,
        response_time_ms: int | None = None,
    ) -> None:
        """Mark an item as successfully completed.

        Args:
            item_key: Item identifier.
            response_size_bytes: Size of downloaded data (optional).
            response_time_ms: Download time in milliseconds (optional).
        """
        if item_key not in self._items:
            logger.warning("Completing unknown item: %s", item_key)
            return

        item = self._items[item_key]

        # Update in-memory state
        item.state = ProgressState.SUCCESS
        item.completed_at = datetime.now(UTC)
        item.error_message = None

        # Update stats
        if self._stats.in_progress > 0:
            self._stats.in_progress -= 1
        self._stats.success += 1
        self._stats.last_update = datetime.now(UTC)

        # Update database
        if item.progress_id is not None:
            await self._repo.mark_success(
                item.progress_id,
                response_size_bytes=response_size_bytes,
                response_time_ms=response_time_ms,
            )

        # Notify callback
        self._notify(item_key, ProgressState.SUCCESS)

        logger.debug("Completed item %s", item_key)

    async def fail_item(self, item_key: str, error_message: str) -> None:
        """Mark an item as failed.

        Args:
            item_key: Item identifier.
            error_message: Description of the failure.
        """
        if item_key not in self._items:
            logger.warning("Failing unknown item: %s", item_key)
            return

        item = self._items[item_key]

        # Update in-memory state
        item.state = ProgressState.FAILED
        item.error_message = error_message

        # Update stats
        if self._stats.in_progress > 0:
            self._stats.in_progress -= 1
        self._stats.failed += 1
        self._stats.last_update = datetime.now(UTC)

        # Update database
        if item.progress_id is not None:
            await self._repo.mark_failed(item.progress_id, error_message)

        # Notify callback
        self._notify(item_key, ProgressState.FAILED, message=error_message)

        logger.debug("Failed item %s: %s", item_key, error_message)

    async def skip_item(self, item_key: str, reason: str | None = None) -> None:
        """Mark an item as skipped.

        Args:
            item_key: Item identifier.
            reason: Reason for skipping (optional).
        """
        if item_key not in self._items:
            await self.register_item(item_key)

        item = self._items[item_key]
        old_state = item.state

        # Update in-memory state
        item.state = ProgressState.SKIPPED
        item.completed_at = datetime.now(UTC)

        # Update stats
        if old_state == ProgressState.PENDING:
            self._stats.pending -= 1
        elif old_state == ProgressState.IN_PROGRESS:
            self._stats.in_progress -= 1
        elif old_state == ProgressState.FAILED:
            self._stats.failed -= 1
        self._stats.skipped += 1
        self._stats.last_update = datetime.now(UTC)

        # Update database
        if item.progress_id is not None:
            await self._repo.mark_skipped(item.progress_id, reason)

        # Notify callback
        self._notify(item_key, ProgressState.SKIPPED, message=reason)

        logger.debug("Skipped item %s: %s", item_key, reason)

    async def reset_failed(self) -> int:
        """Reset all failed items to pending status.

        Returns:
            Number of items reset.
        """
        # Reset in database
        count = await self._repo.reset_failed(self._source_id, self._season_id)

        # Reset in-memory state
        for item in self._items.values():
            if item.state == ProgressState.FAILED:
                item.state = ProgressState.PENDING
                item.error_message = None

        # Update stats
        self._stats.pending += self._stats.failed
        self._stats.failed = 0
        self._stats.last_update = datetime.now(UTC)

        logger.info("Reset %d failed items to pending", count)
        return count

    def get_item_state(self, item_key: str) -> ProgressState | None:
        """Get the current state of an item.

        Args:
            item_key: Item identifier.

        Returns:
            Current state or None if item not tracked.
        """
        item = self._items.get(item_key)
        return item.state if item else None

    def get_item_attempts(self, item_key: str) -> int:
        """Get the number of attempts for an item.

        Args:
            item_key: Item identifier.

        Returns:
            Number of attempts (0 if not tracked).
        """
        item = self._items.get(item_key)
        return item.attempts if item else 0

    def _notify(
        self,
        item_key: str,
        state: ProgressState,
        *,
        message: str | None = None,
    ) -> None:
        """Send progress event to callback.

        Args:
            item_key: Item identifier.
            state: New state.
            message: Optional message.
        """
        if self._on_progress is None:
            return

        event = ProgressEvent(
            source_id=self._source_id,
            season_id=self._season_id,
            item_key=item_key,
            state=state,
            stats=ProgressStats(
                total=self._stats.total,
                pending=self._stats.pending,
                in_progress=self._stats.in_progress,
                success=self._stats.success,
                failed=self._stats.failed,
                skipped=self._stats.skipped,
                started_at=self._stats.started_at,
                last_update=self._stats.last_update,
            ),
            message=message,
        )

        try:
            self._on_progress(event)
        except Exception:
            logger.exception("Error in progress callback")

    def __repr__(self) -> str:
        return (
            f"ProgressTracker("
            f"source_id={self._source_id}, "
            f"season_id={self._season_id}, "
            f"items={len(self._items)}, "
            f"stats={self._stats})"
        )
