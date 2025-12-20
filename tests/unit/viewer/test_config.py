"""Tests for viewer configuration."""

from __future__ import annotations

import pytest


class TestViewerSettings:
    """Tests for ViewerSettings."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        # Clear cache to get fresh settings
        from nhl_api.viewer.config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        assert settings.host == "127.0.0.1"
        assert settings.port == 8000
        assert settings.debug is False
        assert settings.api_version == "v1"
        assert "http://localhost:5173" in settings.cors_origins

        # Cleanup
        get_settings.cache_clear()

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable overrides."""
        from nhl_api.viewer.config import get_settings

        get_settings.cache_clear()

        monkeypatch.setenv("VIEWER_HOST", "0.0.0.0")
        monkeypatch.setenv("VIEWER_PORT", "8080")
        monkeypatch.setenv("VIEWER_DEBUG", "true")

        settings = get_settings()

        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.debug is True

        # Cleanup
        get_settings.cache_clear()

    def test_api_settings(self) -> None:
        """Test API configuration values."""
        from nhl_api.viewer.config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        assert settings.api_title == "NHL Data Viewer API"
        assert "monitoring" in settings.api_description.lower()

        # Cleanup
        get_settings.cache_clear()

    def test_db_pool_settings(self) -> None:
        """Test database pool configuration."""
        from nhl_api.viewer.config import get_settings

        get_settings.cache_clear()

        settings = get_settings()

        assert settings.db_min_connections == 2
        assert settings.db_max_connections == 10

        # Cleanup
        get_settings.cache_clear()
