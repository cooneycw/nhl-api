"""Tests for health check endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_healthy_when_db_connected(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test health check returns healthy status when DB is connected."""
        mock_db_service.fetchval = AsyncMock(return_value=1)

        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Healthy"
        assert data["database"]["connected"] is True
        assert data["database"]["latency_ms"] is not None
        assert "uptime_seconds" in data
        assert "timestamp" in data

    def test_health_returns_degraded_when_db_error(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test health check returns degraded when DB query fails."""
        mock_db_service.fetchval = AsyncMock(side_effect=Exception("Connection failed"))

        response = test_client.get("/health")

        assert response.status_code == 200  # Still returns 200 but degraded
        data = response.json()
        assert data["status"] == "Degraded"
        assert data["database"]["connected"] is False
        assert data["database"]["error"] is not None

    def test_health_response_structure(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test health response has all required fields."""
        mock_db_service.fetchval = AsyncMock(return_value=1)

        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Check all expected fields exist
        assert "status" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data
        assert "database" in data
        assert "connected" in data["database"]


class TestLivenessProbe:
    """Tests for /health/live endpoint."""

    def test_liveness_always_returns_ok(self, test_client: TestClient) -> None:
        """Test liveness probe always returns OK."""
        response = test_client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestReadinessProbe:
    """Tests for /health/ready endpoint."""

    def test_readiness_returns_ready_when_db_connected(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test readiness returns ready when DB is connected."""
        mock_db_service.fetchval = AsyncMock(return_value=1)

        response = test_client.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_readiness_returns_503_when_db_unavailable(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test readiness returns 503 when DB is unavailable."""
        mock_db_service.fetchval = AsyncMock(side_effect=Exception("DB error"))

        response = test_client.get("/health/ready")

        assert response.status_code == 503
