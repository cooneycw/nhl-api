"""Unit tests for ProgressTracker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.downloaders.progress.tracker import (
    ProgressEvent,
    ProgressState,
    ProgressStats,
    ProgressTracker,
)
from nhl_api.services.db.progress_repo import ProgressEntry, ProgressRepository


def create_mock_repo() -> MagicMock:
    """Create a mock ProgressRepository."""
    repo = MagicMock(spec=ProgressRepository)
    repo.upsert_progress = AsyncMock(return_value=1)
    repo.get_incomplete = AsyncMock(return_value=[])
    repo.increment_attempts = AsyncMock(return_value=1)
    repo.mark_success = AsyncMock()
    repo.mark_failed = AsyncMock()
    repo.mark_skipped = AsyncMock()
    repo.reset_failed = AsyncMock(return_value=0)
    return repo


def create_mock_entry(
    progress_id: int = 1,
    source_id: int = 1,
    season_id: int | None = 20242025,
    item_key: str = "2024020001",
    status: str = "pending",
    attempts: int = 0,
    error_message: str | None = None,
) -> ProgressEntry:
    """Create a mock ProgressEntry."""
    return ProgressEntry(
        progress_id=progress_id,
        source_id=source_id,
        season_id=season_id,
        item_key=item_key,
        status=status,
        attempts=attempts,
        error_message=error_message,
    )


class TestProgressState:
    """Tests for ProgressState enum."""

    def test_has_expected_values(self) -> None:
        """Test that all expected states exist."""
        assert ProgressState.PENDING.value == "pending"
        assert ProgressState.IN_PROGRESS.value == "in_progress"
        assert ProgressState.SUCCESS.value == "success"
        assert ProgressState.FAILED.value == "failed"
        assert ProgressState.SKIPPED.value == "skipped"


class TestProgressStats:
    """Tests for ProgressStats dataclass."""

    def test_default_values(self) -> None:
        """Test default values are correct."""
        stats = ProgressStats()
        assert stats.total is None
        assert stats.pending == 0
        assert stats.in_progress == 0
        assert stats.success == 0
        assert stats.failed == 0
        assert stats.skipped == 0

    def test_completed_property(self) -> None:
        """Test completed property calculation."""
        stats = ProgressStats(success=10, failed=2, skipped=3)
        assert stats.completed == 15

    def test_processed_property(self) -> None:
        """Test processed property calculation."""
        stats = ProgressStats(success=10, failed=2, skipped=3, in_progress=5)
        assert stats.processed == 20

    def test_success_rate_with_completions(self) -> None:
        """Test success rate calculation."""
        stats = ProgressStats(success=8, failed=2)
        assert stats.success_rate == 80.0

    def test_success_rate_with_no_completions(self) -> None:
        """Test success rate is 0 with no completions."""
        stats = ProgressStats()
        assert stats.success_rate == 0.0

    def test_progress_percent_with_total(self) -> None:
        """Test progress percentage calculation."""
        stats = ProgressStats(total=100, success=25, failed=5, skipped=10)
        assert stats.progress_percent == 40.0

    def test_progress_percent_without_total(self) -> None:
        """Test progress percentage is 0 without total."""
        stats = ProgressStats(success=25)
        assert stats.progress_percent == 0.0

    def test_is_complete_when_done(self) -> None:
        """Test is_complete when all items processed."""
        stats = ProgressStats(total=10, success=8, failed=2)
        assert stats.is_complete is True

    def test_is_complete_when_not_done(self) -> None:
        """Test is_complete when items remain."""
        stats = ProgressStats(total=10, success=5)
        assert stats.is_complete is False

    def test_is_complete_without_total(self) -> None:
        """Test is_complete is False without total."""
        stats = ProgressStats(success=100)
        assert stats.is_complete is False


class TestProgressEvent:
    """Tests for ProgressEvent dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """Test creating event with required fields."""
        stats = ProgressStats()
        event = ProgressEvent(
            source_id=1,
            item_key="game_123",
            state=ProgressState.IN_PROGRESS,
            stats=stats,
        )
        assert event.source_id == 1
        assert event.item_key == "game_123"
        assert event.state == ProgressState.IN_PROGRESS
        assert event.stats is stats

    def test_optional_fields(self) -> None:
        """Test optional fields."""
        stats = ProgressStats()
        event = ProgressEvent(
            source_id=1,
            item_key="game_123",
            state=ProgressState.FAILED,
            stats=stats,
            season_id=20242025,
            message="Connection failed",
        )
        assert event.season_id == 20242025
        assert event.message == "Connection failed"

    def test_is_frozen(self) -> None:
        """Test that event is immutable."""
        stats = ProgressStats()
        event = ProgressEvent(
            source_id=1,
            item_key="game_123",
            state=ProgressState.PENDING,
            stats=stats,
        )
        with pytest.raises(AttributeError):
            event.state = ProgressState.SUCCESS  # type: ignore[misc]


class TestProgressTrackerInit:
    """Tests for ProgressTracker initialization."""

    def test_stores_config(self) -> None:
        """Test that tracker stores configuration."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1, season_id=20242025, batch_id=5)
        assert tracker.source_id == 1
        assert tracker.season_id == 20242025

    def test_initializes_empty_state(self) -> None:
        """Test that tracker starts with empty state."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        assert tracker.stats.pending == 0
        assert tracker.stats.success == 0
        assert tracker.stats.total is None

    def test_repr(self) -> None:
        """Test string representation."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1, season_id=20242025)
        repr_str = repr(tracker)
        assert "source_id=1" in repr_str
        assert "season_id=20242025" in repr_str


class TestLoadState:
    """Tests for load_state method."""

    @pytest.mark.asyncio
    async def test_loads_incomplete_entries(self) -> None:
        """Test loading incomplete entries from database."""
        repo = create_mock_repo()
        repo.get_incomplete.return_value = [
            create_mock_entry(progress_id=1, item_key="game_1", status="pending"),
            create_mock_entry(progress_id=2, item_key="game_2", status="failed"),
        ]

        tracker = ProgressTracker(repo, source_id=1, season_id=20242025)
        count = await tracker.load_state()

        assert count == 2
        assert tracker.stats.pending == 1
        assert tracker.stats.failed == 1
        repo.get_incomplete.assert_called_once_with(1, 20242025)

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_db(self) -> None:
        """Test returns zero when no entries in database."""
        repo = create_mock_repo()
        repo.get_incomplete.return_value = []

        tracker = ProgressTracker(repo, source_id=1)
        count = await tracker.load_state()

        assert count == 0

    @pytest.mark.asyncio
    async def test_preserves_progress_ids(self) -> None:
        """Test that progress IDs from DB are preserved."""
        repo = create_mock_repo()
        repo.get_incomplete.return_value = [
            create_mock_entry(progress_id=42, item_key="game_1", status="pending"),
        ]

        tracker = ProgressTracker(repo, source_id=1)
        await tracker.load_state()

        # Start item should use existing progress_id
        await tracker.start_item("game_1")
        repo.increment_attempts.assert_called_once_with(42)


class TestSetTotal:
    """Tests for set_total method."""

    def test_sets_total(self) -> None:
        """Test setting total items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        tracker.set_total(100)
        assert tracker.stats.total == 100

    def test_updates_is_complete(self) -> None:
        """Test that is_complete reflects total."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        assert tracker.is_complete is False
        tracker.set_total(0)
        # With 0 total and 0 completed, is_complete is True (nothing to do)
        assert tracker.is_complete is True


class TestRegisterItem:
    """Tests for register_item method."""

    @pytest.mark.asyncio
    async def test_creates_db_entry(self) -> None:
        """Test that register_item creates database entry."""
        repo = create_mock_repo()
        repo.upsert_progress.return_value = 42

        tracker = ProgressTracker(repo, source_id=1, season_id=20242025, batch_id=5)
        progress_id = await tracker.register_item("game_123")

        assert progress_id == 42
        repo.upsert_progress.assert_called_once_with(
            source_id=1,
            item_key="game_123",
            season_id=20242025,
            batch_id=5,
            status="pending",
        )

    @pytest.mark.asyncio
    async def test_updates_stats(self) -> None:
        """Test that register_item updates pending count."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)

        await tracker.register_item("game_1")
        await tracker.register_item("game_2")

        assert tracker.stats.pending == 2

    @pytest.mark.asyncio
    async def test_returns_existing_progress_id(self) -> None:
        """Test that re-registering returns existing progress_id."""
        repo = create_mock_repo()
        repo.upsert_progress.return_value = 42

        tracker = ProgressTracker(repo, source_id=1)
        id1 = await tracker.register_item("game_1")
        id2 = await tracker.register_item("game_1")

        assert id1 == 42
        assert id2 == 42
        # Should only create once
        assert repo.upsert_progress.call_count == 1


class TestRegisterItems:
    """Tests for register_items method."""

    @pytest.mark.asyncio
    async def test_registers_multiple(self) -> None:
        """Test registering multiple items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)

        await tracker.register_items(["game_1", "game_2", "game_3"])

        assert tracker.stats.pending == 3
        assert repo.upsert_progress.call_count == 3

    @pytest.mark.asyncio
    async def test_sets_total_if_not_set(self) -> None:
        """Test that total is set from item count."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)

        await tracker.register_items(["game_1", "game_2"])

        assert tracker.stats.total == 2


class TestShouldDownload:
    """Tests for should_download method."""

    @pytest.mark.asyncio
    async def test_returns_true_for_unknown(self) -> None:
        """Test returns True for unknown items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        assert tracker.should_download("unknown_game") is True

    @pytest.mark.asyncio
    async def test_returns_true_for_pending(self) -> None:
        """Test returns True for pending items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        assert tracker.should_download("game_1") is True

    @pytest.mark.asyncio
    async def test_returns_true_for_failed(self) -> None:
        """Test returns True for failed items (retry)."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.fail_item("game_1", "Error")
        assert tracker.should_download("game_1") is True

    @pytest.mark.asyncio
    async def test_returns_false_for_success(self) -> None:
        """Test returns False for successful items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.complete_item("game_1")
        assert tracker.should_download("game_1") is False

    @pytest.mark.asyncio
    async def test_returns_false_for_in_progress(self) -> None:
        """Test returns False for in-progress items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        assert tracker.should_download("game_1") is False


class TestGetPendingItems:
    """Tests for get_pending_items method."""

    @pytest.mark.asyncio
    async def test_returns_pending_keys(self) -> None:
        """Test returning pending item keys."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.register_item("game_2")
        await tracker.start_item("game_2")

        pending = tracker.get_pending_items()

        assert pending == ["game_1"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_none_pending(self) -> None:
        """Test returns empty list when no pending items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        assert tracker.get_pending_items() == []


class TestGetFailedItems:
    """Tests for get_failed_items method."""

    @pytest.mark.asyncio
    async def test_returns_failed_keys(self) -> None:
        """Test returning failed item keys."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.register_item("game_2")
        await tracker.start_item("game_1")
        await tracker.fail_item("game_1", "Error")

        failed = tracker.get_failed_items()

        assert failed == ["game_1"]


class TestStartItem:
    """Tests for start_item method."""

    @pytest.mark.asyncio
    async def test_updates_state(self) -> None:
        """Test that start_item updates state to in_progress."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")

        assert tracker.get_item_state("game_1") == ProgressState.IN_PROGRESS
        assert tracker.stats.pending == 0
        assert tracker.stats.in_progress == 1

    @pytest.mark.asyncio
    async def test_increments_attempts_in_db(self) -> None:
        """Test that attempts are incremented in database."""
        repo = create_mock_repo()
        repo.upsert_progress.return_value = 42

        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")

        repo.increment_attempts.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_auto_registers_unknown_item(self) -> None:
        """Test that unknown items are auto-registered."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.start_item("new_game")

        assert tracker.get_item_state("new_game") == ProgressState.IN_PROGRESS
        repo.upsert_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_failed_to_in_progress(self) -> None:
        """Test starting a failed item (retry)."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.fail_item("game_1", "Error")

        assert tracker.stats.failed == 1

        await tracker.start_item("game_1")

        assert tracker.stats.failed == 0
        assert tracker.stats.in_progress == 1


class TestCompleteItem:
    """Tests for complete_item method."""

    @pytest.mark.asyncio
    async def test_updates_state(self) -> None:
        """Test that complete_item updates state to success."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.complete_item("game_1")

        assert tracker.get_item_state("game_1") == ProgressState.SUCCESS
        assert tracker.stats.in_progress == 0
        assert tracker.stats.success == 1

    @pytest.mark.asyncio
    async def test_marks_success_in_db(self) -> None:
        """Test that success is recorded in database."""
        repo = create_mock_repo()
        repo.upsert_progress.return_value = 42

        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.complete_item(
            "game_1", response_size_bytes=1024, response_time_ms=150
        )

        repo.mark_success.assert_called_once_with(
            42, response_size_bytes=1024, response_time_ms=150
        )

    @pytest.mark.asyncio
    async def test_handles_unknown_item(self) -> None:
        """Test completing unknown item logs warning but doesn't crash."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.complete_item("unknown")  # Should not raise


class TestFailItem:
    """Tests for fail_item method."""

    @pytest.mark.asyncio
    async def test_updates_state(self) -> None:
        """Test that fail_item updates state to failed."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.fail_item("game_1", "Connection timeout")

        assert tracker.get_item_state("game_1") == ProgressState.FAILED
        assert tracker.stats.in_progress == 0
        assert tracker.stats.failed == 1

    @pytest.mark.asyncio
    async def test_marks_failed_in_db(self) -> None:
        """Test that failure is recorded in database."""
        repo = create_mock_repo()
        repo.upsert_progress.return_value = 42

        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.fail_item("game_1", "Server error")

        repo.mark_failed.assert_called_once_with(42, "Server error")


class TestSkipItem:
    """Tests for skip_item method."""

    @pytest.mark.asyncio
    async def test_updates_state(self) -> None:
        """Test that skip_item updates state to skipped."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.skip_item("game_1", "Already exists")

        assert tracker.get_item_state("game_1") == ProgressState.SKIPPED
        assert tracker.stats.pending == 0
        assert tracker.stats.skipped == 1

    @pytest.mark.asyncio
    async def test_marks_skipped_in_db(self) -> None:
        """Test that skip is recorded in database."""
        repo = create_mock_repo()
        repo.upsert_progress.return_value = 42

        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.skip_item("game_1", "Already exists")

        repo.mark_skipped.assert_called_once_with(42, "Already exists")

    @pytest.mark.asyncio
    async def test_auto_registers_unknown_item(self) -> None:
        """Test that unknown items are auto-registered when skipping."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.skip_item("new_game", "Not needed")

        assert tracker.get_item_state("new_game") == ProgressState.SKIPPED


class TestResetFailed:
    """Tests for reset_failed method."""

    @pytest.mark.asyncio
    async def test_resets_in_memory_state(self) -> None:
        """Test that failed items are reset to pending in memory."""
        repo = create_mock_repo()
        repo.reset_failed.return_value = 1

        tracker = ProgressTracker(repo, source_id=1, season_id=20242025)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.fail_item("game_1", "Error")

        assert tracker.stats.failed == 1

        count = await tracker.reset_failed()

        assert count == 1
        assert tracker.stats.failed == 0
        assert tracker.stats.pending == 1
        assert tracker.get_item_state("game_1") == ProgressState.PENDING

    @pytest.mark.asyncio
    async def test_calls_db_reset(self) -> None:
        """Test that database reset is called."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1, season_id=20242025)

        await tracker.reset_failed()

        repo.reset_failed.assert_called_once_with(1, 20242025)


class TestGetItemState:
    """Tests for get_item_state method."""

    @pytest.mark.asyncio
    async def test_returns_state(self) -> None:
        """Test returning item state."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")

        assert tracker.get_item_state("game_1") == ProgressState.PENDING

    def test_returns_none_for_unknown(self) -> None:
        """Test returning None for unknown items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        assert tracker.get_item_state("unknown") is None


class TestGetItemAttempts:
    """Tests for get_item_attempts method."""

    @pytest.mark.asyncio
    async def test_returns_attempt_count(self) -> None:
        """Test returning attempt count."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.fail_item("game_1", "Error")
        await tracker.start_item("game_1")

        assert tracker.get_item_attempts("game_1") == 2

    def test_returns_zero_for_unknown(self) -> None:
        """Test returning 0 for unknown items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        assert tracker.get_item_attempts("unknown") == 0


class TestProgressCallback:
    """Tests for progress callbacks."""

    @pytest.mark.asyncio
    async def test_calls_callback_on_start(self) -> None:
        """Test that callback is called when item starts."""
        repo = create_mock_repo()
        events: list[ProgressEvent] = []

        def callback(event: ProgressEvent) -> None:
            events.append(event)

        tracker = ProgressTracker(repo, source_id=1, on_progress=callback)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")

        assert len(events) == 1
        assert events[0].item_key == "game_1"
        assert events[0].state == ProgressState.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_calls_callback_on_complete(self) -> None:
        """Test that callback is called when item completes."""
        repo = create_mock_repo()
        events: list[ProgressEvent] = []

        def callback(event: ProgressEvent) -> None:
            events.append(event)

        tracker = ProgressTracker(repo, source_id=1, on_progress=callback)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.complete_item("game_1")

        assert len(events) == 2
        assert events[1].state == ProgressState.SUCCESS

    @pytest.mark.asyncio
    async def test_calls_callback_on_fail(self) -> None:
        """Test that callback is called with error message."""
        repo = create_mock_repo()
        events: list[ProgressEvent] = []

        def callback(event: ProgressEvent) -> None:
            events.append(event)

        tracker = ProgressTracker(repo, source_id=1, on_progress=callback)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")
        await tracker.fail_item("game_1", "Connection failed")

        assert len(events) == 2
        assert events[1].state == ProgressState.FAILED
        assert events[1].message == "Connection failed"

    @pytest.mark.asyncio
    async def test_includes_stats_in_callback(self) -> None:
        """Test that callback includes current stats."""
        repo = create_mock_repo()
        events: list[ProgressEvent] = []

        def callback(event: ProgressEvent) -> None:
            events.append(event)

        tracker = ProgressTracker(repo, source_id=1, on_progress=callback)
        tracker.set_total(10)
        await tracker.register_item("game_1")
        await tracker.start_item("game_1")

        assert events[0].stats.total == 10
        assert events[0].stats.in_progress == 1

    @pytest.mark.asyncio
    async def test_handles_callback_exception(self) -> None:
        """Test that callback exceptions don't crash tracker."""
        repo = create_mock_repo()

        def bad_callback(event: ProgressEvent) -> None:
            raise ValueError("Callback error")

        tracker = ProgressTracker(repo, source_id=1, on_progress=bad_callback)
        await tracker.register_item("game_1")
        # Should not raise
        await tracker.start_item("game_1")
        await tracker.complete_item("game_1")


class TestIsComplete:
    """Tests for is_complete property."""

    @pytest.mark.asyncio
    async def test_is_complete_when_all_done(self) -> None:
        """Test is_complete returns True when all items processed."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        tracker.set_total(2)
        await tracker.register_item("game_1")
        await tracker.register_item("game_2")
        await tracker.start_item("game_1")
        await tracker.complete_item("game_1")
        await tracker.start_item("game_2")
        await tracker.complete_item("game_2")

        assert tracker.is_complete is True

    @pytest.mark.asyncio
    async def test_is_not_complete_with_pending(self) -> None:
        """Test is_complete returns False with pending items."""
        repo = create_mock_repo()
        tracker = ProgressTracker(repo, source_id=1)
        tracker.set_total(2)
        await tracker.register_item("game_1")
        await tracker.register_item("game_2")
        await tracker.start_item("game_1")
        await tracker.complete_item("game_1")

        assert tracker.is_complete is False
