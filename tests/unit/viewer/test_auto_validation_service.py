"""Unit tests for AutoValidationService."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.viewer.services.auto_validation_service import (
    AutoValidationService,
    ValidationQueueItem,
    get_auto_validation_service,
)


@pytest.fixture
def service() -> AutoValidationService:
    """Create a fresh AutoValidationService instance."""
    # Reset singleton for clean test
    AutoValidationService._instance = None
    return AutoValidationService()


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock DatabaseService."""
    mock = MagicMock()
    mock.fetchval = AsyncMock(return_value=0)
    mock.fetch = AsyncMock(return_value=[])
    mock.fetchrow = AsyncMock(return_value=None)
    mock.execute = AsyncMock(return_value="OK")
    return mock


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_instance_returns_same_instance(self) -> None:
        """get_instance should return the same instance."""
        # Reset singleton for clean test
        AutoValidationService._instance = None

        instance1 = AutoValidationService.get_instance()
        instance2 = AutoValidationService.get_instance()

        assert instance1 is instance2

        # Cleanup
        AutoValidationService._instance = None

    def test_get_auto_validation_service_returns_singleton(self) -> None:
        """get_auto_validation_service should return singleton."""
        # Reset singleton for clean test
        AutoValidationService._instance = None

        service1 = get_auto_validation_service()
        service2 = get_auto_validation_service()

        assert service1 is service2

        # Cleanup
        AutoValidationService._instance = None


# =============================================================================
# Queue Item Tests
# =============================================================================


class TestValidationQueueItem:
    """Test ValidationQueueItem dataclass."""

    def test_defaults(self) -> None:
        """QueueItem should have sensible defaults."""
        item = ValidationQueueItem(
            game_id=2024020001,
            season_id=20242025,
            validator_types=["json_cross_source"],
        )

        assert item.game_id == 2024020001
        assert item.season_id == 20242025
        assert item.validator_types == ["json_cross_source"]
        assert item.attempts == 0
        assert isinstance(item.queued_at, datetime)

    def test_queued_at_is_utc(self) -> None:
        """QueueItem queued_at should be UTC."""
        item = ValidationQueueItem(
            game_id=2024020001,
            season_id=20242025,
            validator_types=["json_cross_source"],
        )

        # Check timezone is UTC
        assert item.queued_at.tzinfo is not None


# =============================================================================
# Completeness Check Tests
# =============================================================================


class TestCompletenessCheck:
    """Test data completeness checking."""

    @pytest.mark.asyncio
    async def test_has_complete_json_data_all_present(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should return True when all JSON sources present."""
        # All sources exist
        mock_db.fetchval = AsyncMock(return_value=True)

        result = await service.has_complete_json_data(mock_db, 2024020001)

        assert result is True
        assert mock_db.fetchval.call_count == 3

    @pytest.mark.asyncio
    async def test_has_complete_json_data_missing_boxscore(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should return False when boxscore is missing."""
        # First call (boxscore) returns False
        mock_db.fetchval = AsyncMock(side_effect=[False, True, True])

        result = await service.has_complete_json_data(mock_db, 2024020001)

        assert result is False

    @pytest.mark.asyncio
    async def test_has_complete_json_data_missing_pbp(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should return False when PBP is missing."""
        # Second call (pbp) returns False
        mock_db.fetchval = AsyncMock(side_effect=[True, False, True])

        result = await service.has_complete_json_data(mock_db, 2024020001)

        assert result is False

    @pytest.mark.asyncio
    async def test_has_complete_json_data_missing_shifts(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should return False when shifts are missing."""
        # Third call (shifts) returns False
        mock_db.fetchval = AsyncMock(side_effect=[True, True, False])

        result = await service.has_complete_json_data(mock_db, 2024020001)

        assert result is False


# =============================================================================
# Queue Validation Tests
# =============================================================================


class TestQueueValidation:
    """Test validation queueing."""

    @pytest.mark.asyncio
    async def test_queue_validation_adds_to_queue(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """queue_validation should add item to queue."""
        with patch(
            "nhl_api.viewer.services.auto_validation_service.VALIDATION_AUTO_RUN", True
        ):
            result = await service.queue_validation(
                mock_db, 2024020001, 20242025, ["json_cross_source"]
            )

            assert result is True
            assert service._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_queue_validation_disabled(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """queue_validation should return False when disabled."""
        with patch(
            "nhl_api.viewer.services.auto_validation_service.VALIDATION_AUTO_RUN", False
        ):
            result = await service.queue_validation(
                mock_db, 2024020001, 20242025, ["json_cross_source"]
            )

            assert result is False
            assert service._queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_queue_validation_default_validator_types(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """queue_validation should use default validator types."""
        with patch(
            "nhl_api.viewer.services.auto_validation_service.VALIDATION_AUTO_RUN", True
        ):
            await service.queue_validation(mock_db, 2024020001, 20242025)

            item = await asyncio.wait_for(service._queue.get(), timeout=1.0)
            assert item.validator_types == ["json_cross_source"]


# =============================================================================
# Pending Games Tests
# =============================================================================


class TestGetGamesPendingValidation:
    """Test getting games pending validation."""

    @pytest.mark.asyncio
    async def test_returns_game_ids(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should return list of game IDs."""
        mock_db.fetch = AsyncMock(
            return_value=[
                {"game_id": 2024020001},
                {"game_id": 2024020002},
                {"game_id": 2024020003},
            ]
        )

        result = await service.get_games_pending_validation(mock_db, 20242025)

        assert result == [2024020001, 2024020002, 2024020003]

    @pytest.mark.asyncio
    async def test_respects_limit(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should pass limit to query."""
        mock_db.fetch = AsyncMock(return_value=[])

        await service.get_games_pending_validation(mock_db, 20242025, limit=10)

        # Verify limit was passed (second parameter after season_id)
        call_args = mock_db.fetch.call_args
        assert call_args[0][2] == 10  # Third positional arg is limit

    @pytest.mark.asyncio
    async def test_empty_when_no_pending(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should return empty list when no games pending."""
        mock_db.fetch = AsyncMock(return_value=[])

        result = await service.get_games_pending_validation(mock_db, 20242025)

        assert result == []


# =============================================================================
# Service Lifecycle Tests
# =============================================================================


class TestServiceLifecycle:
    """Test service start/stop."""

    @pytest.mark.asyncio
    async def test_start_creates_worker(self, service: AutoValidationService) -> None:
        """start should create worker task."""
        assert service._worker_task is None
        assert service._running is False

        await service.start()

        assert service._running is True
        assert service._worker_task is not None

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_worker(self, service: AutoValidationService) -> None:
        """stop should cancel worker task."""
        await service.start()
        assert service._running is True

        await service.stop()

        assert service._running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self, service: AutoValidationService) -> None:
        """Multiple starts should not create multiple workers."""
        await service.start()
        task1 = service._worker_task

        await service.start()
        task2 = service._worker_task

        assert task1 is task2

        # Cleanup
        await service.stop()


# =============================================================================
# Get or Create Rule Tests
# =============================================================================


class TestGetOrCreateRule:
    """Test rule lookup/creation."""

    @pytest.mark.asyncio
    async def test_returns_existing_rule_id(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should return existing rule_id if found."""
        mock_db.fetchval = AsyncMock(return_value=42)

        rule_id = await service._get_or_create_rule(mock_db, "test_rule", "cross_file")

        assert rule_id == 42
        # Should only call fetchval once (not insert)
        assert mock_db.fetchval.call_count == 1

    @pytest.mark.asyncio
    async def test_creates_rule_if_not_exists(
        self, service: AutoValidationService, mock_db: MagicMock
    ) -> None:
        """Should create rule if not found."""
        # First call returns None (not found), second returns new ID
        mock_db.fetchval = AsyncMock(side_effect=[None, 99])

        rule_id = await service._get_or_create_rule(mock_db, "new_rule", "internal")

        assert rule_id == 99
        assert mock_db.fetchval.call_count == 2
