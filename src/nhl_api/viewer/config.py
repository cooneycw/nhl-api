"""Viewer backend configuration using pydantic-settings.

Loads configuration from environment variables with sensible defaults.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ViewerSettings(BaseSettings):
    """Configuration for the NHL Data Viewer backend.

    All settings can be overridden via environment variables.
    The prefix VIEWER_ is used for all settings.

    Example:
        export VIEWER_HOST=0.0.0.0
        export VIEWER_PORT=8080
    """

    model_config = SettingsConfigDict(
        env_prefix="VIEWER_",
        case_sensitive=False,
    )

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # API settings
    api_version: str = "v1"
    api_title: str = "NHL Data Viewer API"
    api_description: str = "Backend API for NHL Data Viewer monitoring and exploration"

    # CORS settings
    cors_origins: list[str] = ["http://localhost:5173"]  # Vite dev server default
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # Database settings (for pool sizing)
    db_min_connections: int = 2
    db_max_connections: int = 10


@lru_cache
def get_settings() -> ViewerSettings:
    """Get cached settings instance.

    Returns:
        ViewerSettings loaded from environment.
    """
    return ViewerSettings()
