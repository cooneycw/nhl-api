"""Unit tests for ProgressRepository."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.services.db.connection import DatabaseService
from nhl_api.services.db.progress_repo import ProgressEntry, ProgressRepository


def create_mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Create a properly mocked asyncpg pool."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=42)

    @asynccontextmanager
    async def mock_acquire() -> AsyncIterator[Any]:
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.acquire = mock_acquire
    mock_pool.close = AsyncMock()

    return mock_pool, mock_conn


def create_mock_record(
    progress_id: int = 1,
    source_id: int = 1,
    season_id: int | None = 20242025,
    item_key: str = "2024020001",
    status: str = "pending",
    attempts: int = 0,
    batch_id: int | None = None,
    last_attempt_at: datetime | None = None,
    completed_at: datetime | None = None,
    error_message: str | None = None,
    response_size_bytes: int | None = None,
    response_time_ms: int | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a mock database record for testing."""
    if created_at is None:
        created_at = datetime.now(UTC)
    return {
        "progress_id": progress_id,
        "source_id": source_id,
        "season_id": season_id,
        "item_key": item_key,
        "status": status,
        "attempts": attempts,
        "batch_id": batch_id,
        "last_attempt_at": last_attempt_at,
        "completed_at": completed_at,
        "error_message": error_message,
        "response_size_bytes": response_size_bytes,
        "response_time_ms": response_time_ms,
        "created_at": created_at,
    }


class TestProgressEntry:
    """Tests for ProgressEntry dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """Test creating ProgressEntry with required fields."""
        entry = ProgressEntry(
            progress_id=1,
            source_id=2,
            season_id=20242025,
            item_key="2024020001",
            status="pending",
            attempts=0,
        )
        assert entry.progress_id == 1
        assert entry.source_id == 2
        assert entry.season_id == 20242025
        assert entry.item_key == "2024020001"
        assert entry.status == "pending"
        assert entry.attempts == 0

    def test_optional_fields_default_to_none(self) -> None:
        """Test that optional fields default to None."""
        entry = ProgressEntry(
            progress_id=1,
            source_id=2,
            season_id=None,
            item_key="player_123",
            status="pending",
            attempts=0,
        )
        assert entry.batch_id is None
        assert entry.last_attempt_at is None
        assert entry.completed_at is None
        assert entry.error_message is None
        assert entry.response_size_bytes is None
        assert entry.response_time_ms is None
        assert entry.created_at is None

    def test_is_frozen(self) -> None:
        """Test that ProgressEntry is immutable."""
        entry = ProgressEntry(
            progress_id=1,
            source_id=2,
            season_id=20242025,
            item_key="2024020001",
            status="pending",
            attempts=0,
        )
        with pytest.raises(AttributeError):
            entry.status = "success"  # type: ignore[misc]

    def test_from_record(self) -> None:
        """Test creating ProgressEntry from database record."""
        now = datetime.now(UTC)
        record = create_mock_record(
            progress_id=42,
            source_id=3,
            season_id=20232024,
            item_key="2023020500",
            status="success",
            attempts=2,
            batch_id=10,
            last_attempt_at=now,
            completed_at=now,
            error_message=None,
            response_size_bytes=1024,
            response_time_ms=150,
            created_at=now,
        )
        entry = ProgressEntry.from_record(record)

        assert entry.progress_id == 42
        assert entry.source_id == 3
        assert entry.season_id == 20232024
        assert entry.item_key == "2023020500"
        assert entry.status == "success"
        assert entry.attempts == 2
        assert entry.batch_id == 10
        assert entry.response_size_bytes == 1024
        assert entry.response_time_ms == 150


class TestProgressRepositoryInit:
    """Tests for ProgressRepository initialization."""

    def test_stores_db_reference(self) -> None:
        """Test that repository stores database reference."""
        db = DatabaseService()
        repo = ProgressRepository(db)
        assert repo.db is db


class TestUpsertProgress:
    """Tests for upsert_progress method."""

    @pytest.mark.asyncio
    async def test_inserts_new_entry(self) -> None:
        """Test inserting a new progress entry."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchval.return_value = 42
        db._pool = mock_pool

        repo = ProgressRepository(db)
        progress_id = await repo.upsert_progress(
            source_id=1,
            item_key="2024020001",
            season_id=20242025,
        )

        assert progress_id == 42
        mock_conn.fetchval.assert_called_once()
        call_args = mock_conn.fetchval.call_args
        assert "INSERT INTO download_progress" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_with_batch_id(self) -> None:
        """Test inserting with batch_id."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchval.return_value = 43
        db._pool = mock_pool

        repo = ProgressRepository(db)
        progress_id = await repo.upsert_progress(
            source_id=1,
            item_key="2024020001",
            season_id=20242025,
            batch_id=10,
        )

        assert progress_id == 43
        # Verify batch_id was passed
        call_args = mock_conn.fetchval.call_args
        assert 10 in call_args[0]  # batch_id should be in args

    @pytest.mark.asyncio
    async def test_with_custom_status(self) -> None:
        """Test inserting with custom status."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchval.return_value = 44
        db._pool = mock_pool

        repo = ProgressRepository(db)
        progress_id = await repo.upsert_progress(
            source_id=1,
            item_key="2024020001",
            status="skipped",
        )

        assert progress_id == 44
        # Verify status was passed
        call_args = mock_conn.fetchval.call_args
        assert "skipped" in call_args[0]

    @pytest.mark.asyncio
    async def test_with_null_season_id(self) -> None:
        """Test inserting with null season_id."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchval.return_value = 45
        db._pool = mock_pool

        repo = ProgressRepository(db)
        progress_id = await repo.upsert_progress(
            source_id=1,
            item_key="player_123",
            season_id=None,
        )

        assert progress_id == 45


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_returns_entry_when_found(self) -> None:
        """Test returning entry when found."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchrow.return_value = create_mock_record(progress_id=42)
        db._pool = mock_pool

        repo = ProgressRepository(db)
        entry = await repo.get_by_id(42)

        assert entry is not None
        assert entry.progress_id == 42
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        """Test returning None when not found."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchrow.return_value = None
        db._pool = mock_pool

        repo = ProgressRepository(db)
        entry = await repo.get_by_id(999)

        assert entry is None


class TestGetByKey:
    """Tests for get_by_key method."""

    @pytest.mark.asyncio
    async def test_returns_entry_when_found(self) -> None:
        """Test returning entry by unique key."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchrow.return_value = create_mock_record(
            source_id=1, season_id=20242025, item_key="2024020001"
        )
        db._pool = mock_pool

        repo = ProgressRepository(db)
        entry = await repo.get_by_key(1, 20242025, "2024020001")

        assert entry is not None
        assert entry.item_key == "2024020001"

    @pytest.mark.asyncio
    async def test_with_null_season_id(self) -> None:
        """Test get_by_key with null season_id."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchrow.return_value = create_mock_record(
            source_id=1, season_id=None, item_key="player_123"
        )
        db._pool = mock_pool

        repo = ProgressRepository(db)
        entry = await repo.get_by_key(1, None, "player_123")

        assert entry is not None
        assert entry.season_id is None
        # Verify the NULL query was used
        call_args = mock_conn.fetchrow.call_args
        assert "season_id IS NULL" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        """Test returning None when key not found."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchrow.return_value = None
        db._pool = mock_pool

        repo = ProgressRepository(db)
        entry = await repo.get_by_key(1, 20242025, "nonexistent")

        assert entry is None


class TestGetPending:
    """Tests for get_pending method."""

    @pytest.mark.asyncio
    async def test_returns_pending_entries(self) -> None:
        """Test returning pending entries."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetch.return_value = [
            create_mock_record(progress_id=1, status="pending"),
            create_mock_record(progress_id=2, status="pending"),
        ]
        db._pool = mock_pool

        repo = ProgressRepository(db)
        entries = await repo.get_pending(1, 20242025)

        assert len(entries) == 2
        assert all(e.status == "pending" for e in entries)

    @pytest.mark.asyncio
    async def test_respects_limit(self) -> None:
        """Test that limit parameter is applied."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetch.return_value = [create_mock_record(progress_id=1)]
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.get_pending(1, 20242025, limit=10)

        call_args = mock_conn.fetch.call_args
        assert "LIMIT 10" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_with_null_season_id(self) -> None:
        """Test get_pending with null season_id."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetch.return_value = []
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.get_pending(1, None)

        call_args = mock_conn.fetch.call_args
        assert "season_id IS NULL" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self) -> None:
        """Test returning empty list when no pending entries."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetch.return_value = []
        db._pool = mock_pool

        repo = ProgressRepository(db)
        entries = await repo.get_pending(1, 20242025)

        assert entries == []


class TestGetIncomplete:
    """Tests for get_incomplete method."""

    @pytest.mark.asyncio
    async def test_returns_pending_and_failed(self) -> None:
        """Test returning both pending and failed entries."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetch.return_value = [
            create_mock_record(progress_id=1, status="pending"),
            create_mock_record(progress_id=2, status="failed"),
        ]
        db._pool = mock_pool

        repo = ProgressRepository(db)
        entries = await repo.get_incomplete(1, 20242025)

        assert len(entries) == 2
        # Verify query filters by both statuses
        call_args = mock_conn.fetch.call_args
        assert "pending" in call_args[0][0]
        assert "failed" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_with_null_season_id(self) -> None:
        """Test get_incomplete with null season_id."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetch.return_value = []
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.get_incomplete(1, None)

        call_args = mock_conn.fetch.call_args
        assert "season_id IS NULL" in call_args[0][0]


class TestMarkSuccess:
    """Tests for mark_success method."""

    @pytest.mark.asyncio
    async def test_updates_status_to_success(self) -> None:
        """Test marking entry as successful."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.mark_success(42)

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "status = 'success'" in call_args[0][0]
        assert "completed_at = CURRENT_TIMESTAMP" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_stores_response_metrics(self) -> None:
        """Test storing response size and time."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.mark_success(42, response_size_bytes=1024, response_time_ms=150)

        call_args = mock_conn.execute.call_args
        assert 42 in call_args[0]  # progress_id
        assert 1024 in call_args[0]  # response_size_bytes
        assert 150 in call_args[0]  # response_time_ms


class TestMarkFailed:
    """Tests for mark_failed method."""

    @pytest.mark.asyncio
    async def test_updates_status_to_failed(self) -> None:
        """Test marking entry as failed."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.mark_failed(42, "Connection timeout")

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "status = 'failed'" in call_args[0][0]
        assert "error_message = $2" in call_args[0][0]
        assert "Connection timeout" in call_args[0]


class TestMarkSkipped:
    """Tests for mark_skipped method."""

    @pytest.mark.asyncio
    async def test_updates_status_to_skipped(self) -> None:
        """Test marking entry as skipped."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.mark_skipped(42, reason="Already exists")

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "status = 'skipped'" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_without_reason(self) -> None:
        """Test marking as skipped without reason."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.mark_skipped(42)

        mock_conn.execute.assert_called_once()


class TestIncrementAttempts:
    """Tests for increment_attempts method."""

    @pytest.mark.asyncio
    async def test_increments_count(self) -> None:
        """Test incrementing attempt count."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchval.return_value = 3
        db._pool = mock_pool

        repo = ProgressRepository(db)
        new_count = await repo.increment_attempts(42)

        assert new_count == 3
        call_args = mock_conn.fetchval.call_args
        assert "attempts = attempts + 1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_updates_last_attempt_at(self) -> None:
        """Test that last_attempt_at is updated."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchval.return_value = 1
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.increment_attempts(42)

        call_args = mock_conn.fetchval.call_args
        assert "last_attempt_at = CURRENT_TIMESTAMP" in call_args[0][0]


class TestGetBatchStats:
    """Tests for get_batch_stats method."""

    @pytest.mark.asyncio
    async def test_returns_counts_by_status(self) -> None:
        """Test returning status counts for a batch."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchrow.return_value = {
            "pending": 5,
            "success": 10,
            "failed": 2,
            "skipped": 1,
            "total": 18,
        }
        db._pool = mock_pool

        repo = ProgressRepository(db)
        stats = await repo.get_batch_stats(10)

        assert stats["pending"] == 5
        assert stats["success"] == 10
        assert stats["failed"] == 2
        assert stats["skipped"] == 1
        assert stats["total"] == 18

    @pytest.mark.asyncio
    async def test_returns_zeros_for_empty_batch(self) -> None:
        """Test returning zeros when batch has no entries."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchrow.return_value = None
        db._pool = mock_pool

        repo = ProgressRepository(db)
        stats = await repo.get_batch_stats(999)

        assert stats == {
            "pending": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
        }

    @pytest.mark.asyncio
    async def test_handles_null_counts(self) -> None:
        """Test handling NULL counts in results."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchrow.return_value = {
            "pending": None,
            "success": 5,
            "failed": None,
            "skipped": None,
            "total": 5,
        }
        db._pool = mock_pool

        repo = ProgressRepository(db)
        stats = await repo.get_batch_stats(10)

        assert stats["pending"] == 0
        assert stats["success"] == 5
        assert stats["failed"] == 0
        assert stats["skipped"] == 0


class TestResetFailed:
    """Tests for reset_failed method."""

    @pytest.mark.asyncio
    async def test_resets_failed_to_pending(self) -> None:
        """Test resetting failed entries to pending."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.execute.return_value = "UPDATE 5"
        db._pool = mock_pool

        repo = ProgressRepository(db)
        count = await repo.reset_failed(1, 20242025)

        assert count == 5
        call_args = mock_conn.execute.call_args
        assert "status = 'pending'" in call_args[0][0]
        assert "status = 'failed'" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_returns_zero_when_none_reset(self) -> None:
        """Test returning zero when no entries reset."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.execute.return_value = "UPDATE 0"
        db._pool = mock_pool

        repo = ProgressRepository(db)
        count = await repo.reset_failed(1, 20242025)

        assert count == 0

    @pytest.mark.asyncio
    async def test_with_null_season_id(self) -> None:
        """Test reset_failed with null season_id."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.execute.return_value = "UPDATE 3"
        db._pool = mock_pool

        repo = ProgressRepository(db)
        count = await repo.reset_failed(1, None)

        assert count == 3
        call_args = mock_conn.execute.call_args
        assert "season_id IS NULL" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_clears_error_message(self) -> None:
        """Test that error_message is cleared on reset."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.execute.return_value = "UPDATE 1"
        db._pool = mock_pool

        repo = ProgressRepository(db)
        await repo.reset_failed(1, 20242025)

        call_args = mock_conn.execute.call_args
        assert "error_message = NULL" in call_args[0][0]
