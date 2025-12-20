"""Tests for monitoring endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestDashboardEndpoint:
    """Tests for GET /api/v1/monitoring/dashboard."""

    def test_dashboard_returns_stats(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test dashboard returns all expected stats."""
        # Setup mocks
        mock_db_service.fetchval = AsyncMock(
            side_effect=[5, 10, 2]
        )  # active, completed, failed
        mock_db_service.fetchrow = AsyncMock(
            return_value={
                "total_items": 1000,
                "success_rate": 95.5,
                "healthy": 3,
                "degraded": 1,
                "error": 0,
            }
        )
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "progress_id": 1,
                    "source_name": "nhl_schedule",
                    "item_key": "2024020100",
                    "error_message": "Connection timeout",
                    "last_attempt_at": datetime.now(UTC),
                }
            ]
        )

        response = test_client.get("/api/v1/monitoring/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "recent_failures" in data
        assert "timestamp" in data
        assert data["stats"]["active_batches"] == 5
        assert data["stats"]["completed_today"] == 10
        assert data["stats"]["failed_today"] == 2
        assert data["stats"]["success_rate_24h"] == 95.5
        assert data["stats"]["sources_healthy"] == 3
        assert len(data["recent_failures"]) == 1

    def test_dashboard_handles_empty_database(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test dashboard handles no data gracefully."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetchrow = AsyncMock(
            return_value={
                "total_items": 0,
                "success_rate": None,
                "healthy": 0,
                "degraded": 0,
                "error": 0,
            }
        )
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["active_batches"] == 0
        assert data["stats"]["success_rate_24h"] is None
        assert data["recent_failures"] == []

    def test_dashboard_includes_recent_failures(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test dashboard includes up to 10 recent failures."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetchrow = AsyncMock(
            return_value={
                "total_items": 0,
                "success_rate": None,
                "healthy": 0,
                "degraded": 0,
                "error": 0,
            }
        )
        # Return 5 failures
        failures = [
            {
                "progress_id": i,
                "source_name": f"source_{i}",
                "item_key": f"key_{i}",
                "error_message": f"Error {i}",
                "last_attempt_at": datetime.now(UTC),
            }
            for i in range(5)
        ]
        mock_db_service.fetch = AsyncMock(return_value=failures)

        response = test_client.get("/api/v1/monitoring/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert len(data["recent_failures"]) == 5


class TestBatchListEndpoint:
    """Tests for GET /api/v1/monitoring/batches."""

    def test_list_batches_default_pagination(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test batch list with default pagination."""
        mock_db_service.fetchval = AsyncMock(return_value=1)
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "batch_id": 1,
                    "source_id": 1,
                    "source_name": "nhl_schedule",
                    "source_type": "api",
                    "season_id": 20242025,
                    "season_name": "2024-25",
                    "status": "completed",
                    "started_at": datetime.now(UTC),
                    "completed_at": datetime.now(UTC),
                    "duration_seconds": 120.5,
                    "items_total": 100,
                    "items_success": 98,
                    "items_failed": 2,
                    "items_skipped": 0,
                    "success_rate": 98.0,
                    "completion_rate": 100.0,
                }
            ]
        )

        response = test_client.get("/api/v1/monitoring/batches")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["batches"]) == 1
        assert data["batches"][0]["batch_id"] == 1

    def test_list_batches_with_pagination(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test batch list with custom page and page_size."""
        mock_db_service.fetchval = AsyncMock(return_value=50)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/batches?page=2&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["pages"] == 5  # 50 / 10 = 5

    def test_list_batches_filter_by_status(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test filtering batches by status."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/batches?status=failed")

        assert response.status_code == 200

    def test_list_batches_filter_by_source(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test filtering batches by source_id."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/batches?source_id=1")

        assert response.status_code == 200

    def test_list_batches_empty_result(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test empty batch list."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/batches")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["batches"] == []
        assert data["pages"] == 1


class TestBatchDetailEndpoint:
    """Tests for GET /api/v1/monitoring/batches/{batch_id}."""

    def test_get_batch_detail(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test getting batch detail with downloads."""
        mock_db_service.fetchrow = AsyncMock(
            return_value={
                "batch_id": 1,
                "source_id": 1,
                "source_name": "nhl_schedule",
                "source_type": "api",
                "season_id": 20242025,
                "season_name": "2024-25",
                "status": "completed",
                "started_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC),
                "duration_seconds": 120.5,
                "items_total": 2,
                "items_success": 1,
                "items_failed": 1,
                "items_skipped": 0,
                "success_rate": 50.0,
                "completion_rate": 100.0,
                "error_message": None,
                "metadata": {"key": "value"},
            }
        )
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "progress_id": 1,
                    "item_key": "2024020100",
                    "status": "completed",
                    "attempts": 1,
                    "last_attempt_at": datetime.now(UTC),
                    "completed_at": datetime.now(UTC),
                    "error_message": None,
                    "response_size_bytes": 1024,
                    "response_time_ms": 250,
                },
                {
                    "progress_id": 2,
                    "item_key": "2024020101",
                    "status": "failed",
                    "attempts": 3,
                    "last_attempt_at": datetime.now(UTC),
                    "completed_at": None,
                    "error_message": "Connection timeout",
                    "response_size_bytes": None,
                    "response_time_ms": None,
                },
            ]
        )

        response = test_client.get("/api/v1/monitoring/batches/1")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == 1
        assert len(data["downloads"]) == 2
        assert data["metadata"] == {"key": "value"}

    def test_batch_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test 404 for non-existent batch."""
        mock_db_service.fetchrow = AsyncMock(return_value=None)

        response = test_client.get("/api/v1/monitoring/batches/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_batch_with_no_downloads(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test batch with empty downloads list."""
        mock_db_service.fetchrow = AsyncMock(
            return_value={
                "batch_id": 1,
                "source_id": 1,
                "source_name": "nhl_schedule",
                "source_type": "api",
                "season_id": None,
                "season_name": None,
                "status": "running",
                "started_at": datetime.now(UTC),
                "completed_at": None,
                "duration_seconds": None,
                "items_total": 0,
                "items_success": 0,
                "items_failed": 0,
                "items_skipped": 0,
                "success_rate": 0.0,
                "completion_rate": 0.0,
                "error_message": None,
                "metadata": None,
            }
        )
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/batches/1")

        assert response.status_code == 200
        data = response.json()
        assert data["downloads"] == []


class TestFailuresEndpoint:
    """Tests for GET /api/v1/monitoring/failures."""

    def test_list_failures(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test listing failures with pagination."""
        mock_db_service.fetchval = AsyncMock(return_value=1)
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "progress_id": 1,
                    "batch_id": 1,
                    "source_id": 1,
                    "source_name": "nhl_schedule",
                    "source_type": "api",
                    "season_id": 20242025,
                    "item_key": "2024020100",
                    "status": "failed",
                    "attempts": 3,
                    "last_attempt_at": datetime.now(UTC),
                    "error_message": "Connection timeout",
                }
            ]
        )

        response = test_client.get("/api/v1/monitoring/failures")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["failures"]) == 1
        assert data["failures"][0]["status"] == "failed"

    def test_list_failures_filter_by_source(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test filtering failures by source_id."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/failures?source_id=1")

        assert response.status_code == 200

    def test_list_failures_empty(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test empty failures list."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/failures")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["failures"] == []


class TestRetryEndpoint:
    """Tests for POST /api/v1/monitoring/failures/{progress_id}/retry."""

    def test_retry_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test successful retry queue."""
        mock_db_service.fetchval = AsyncMock(return_value=1)

        response = test_client.post("/api/v1/monitoring/failures/1/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["progress_id"] == 1
        assert data["status"] == "pending"
        assert "queued" in data["message"].lower()

    def test_retry_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test 404 for non-existent or non-failed item."""
        mock_db_service.fetchval = AsyncMock(return_value=None)

        response = test_client.post("/api/v1/monitoring/failures/999/retry")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestSourcesEndpoint:
    """Tests for GET /api/v1/monitoring/sources."""

    def test_list_sources_active_only(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test listing only active sources (default)."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "source_id": 1,
                    "source_name": "nhl_schedule",
                    "source_type": "api",
                    "is_active": True,
                    "rate_limit_ms": 1000,
                    "max_concurrent": 5,
                    "latest_batch_id": 10,
                    "latest_status": "completed",
                    "latest_started_at": datetime.now(UTC),
                    "latest_completed_at": datetime.now(UTC),
                    "batches_last_24h": 5,
                    "items_last_24h": 500,
                    "success_last_24h": 495,
                    "failed_last_24h": 5,
                    "success_rate_24h": 99.0,
                    "total_batches": 100,
                    "total_items_all_time": 10000,
                    "success_items_all_time": 9900,
                    "health_status": "healthy",
                    "refreshed_at": datetime.now(UTC),
                }
            ]
        )

        response = test_client.get("/api/v1/monitoring/sources")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["sources"]) == 1
        assert data["sources"][0]["health_status"] == "healthy"

    def test_list_sources_all(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test listing all sources including inactive."""
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/monitoring/sources?active_only=false")

        assert response.status_code == 200

    def test_sources_health_status_order(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test sources are ordered by health status."""
        # Return sources in different health states
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "source_id": 1,
                    "source_name": "source_error",
                    "source_type": "api",
                    "is_active": True,
                    "rate_limit_ms": None,
                    "max_concurrent": None,
                    "latest_batch_id": None,
                    "latest_status": None,
                    "latest_started_at": None,
                    "latest_completed_at": None,
                    "batches_last_24h": 0,
                    "items_last_24h": 0,
                    "success_last_24h": 0,
                    "failed_last_24h": 0,
                    "success_rate_24h": None,
                    "total_batches": 0,
                    "total_items_all_time": 0,
                    "success_items_all_time": 0,
                    "health_status": "error",
                    "refreshed_at": None,
                },
                {
                    "source_id": 2,
                    "source_name": "source_healthy",
                    "source_type": "api",
                    "is_active": True,
                    "rate_limit_ms": None,
                    "max_concurrent": None,
                    "latest_batch_id": None,
                    "latest_status": None,
                    "latest_started_at": None,
                    "latest_completed_at": None,
                    "batches_last_24h": 0,
                    "items_last_24h": 0,
                    "success_last_24h": 0,
                    "failed_last_24h": 0,
                    "success_rate_24h": None,
                    "total_batches": 0,
                    "total_items_all_time": 0,
                    "success_items_all_time": 0,
                    "health_status": "healthy",
                    "refreshed_at": None,
                },
            ]
        )

        response = test_client.get("/api/v1/monitoring/sources")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        # Error status should come first due to ORDER BY
        assert data["sources"][0]["health_status"] == "error"
