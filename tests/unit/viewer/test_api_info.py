"""Tests for API info endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestApiInfo:
    """Tests for /api/v1/info endpoint."""

    def test_api_info_returns_version(self, test_client: TestClient) -> None:
        """Test API info returns version information."""
        response = test_client.get("/api/v1/info")

        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        assert data["api_version"] == "v1"

    def test_api_info_returns_title(self, test_client: TestClient) -> None:
        """Test API info returns title."""
        response = test_client.get("/api/v1/info")

        assert response.status_code == 200
        data = response.json()
        assert "title" in data


class TestStubEndpoints:
    """Tests for stub endpoints."""

    def test_monitoring_status_returns_coming_soon(
        self, test_client: TestClient
    ) -> None:
        """Test monitoring status stub returns coming soon message."""
        response = test_client.get("/api/v1/monitoring/status")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "coming soon" in data["message"].lower()

    def test_validation_status_returns_coming_soon(
        self, test_client: TestClient
    ) -> None:
        """Test validation status stub returns coming soon message."""
        response = test_client.get("/api/v1/validation/status")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "coming soon" in data["message"].lower()
