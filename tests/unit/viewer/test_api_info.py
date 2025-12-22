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


class TestValidationEndpoints:
    """Tests for validation API endpoints."""

    def test_validation_rules_returns_list(self, test_client: TestClient) -> None:
        """Test validation rules endpoint returns list."""
        response = test_client.get("/api/v1/validation/rules")

        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "total" in data
