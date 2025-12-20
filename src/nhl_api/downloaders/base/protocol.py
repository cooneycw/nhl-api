"""Downloader protocol and data types.

This module defines the interface that all NHL data downloaders must implement.
Using Python's Protocol (structural subtyping) allows for flexible implementations
without requiring inheritance.

Example usage:
    class ScheduleDownloader:
        @property
        def source_name(self) -> str:
            return "nhl_json_schedule"

        async def download_season(self, season_id: int) -> AsyncIterator[DownloadResult]:
            async for game in self._fetch_games(season_id):
                yield DownloadResult(
                    source=self.source_name,
                    game_id=game["id"],
                    season_id=season_id,
                    data=game,
                    downloaded_at=datetime.now(UTC),
                )

        async def download_game(self, game_id: int) -> DownloadResult:
            ...

        async def health_check(self) -> bool:
            ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class DownloadStatus(Enum):
    """Status of a download operation."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # For already-downloaded items


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Result of a download operation.

    Attributes:
        source: Name of the data source (e.g., "nhl_json_schedule", "html_gs")
        game_id: NHL game ID if applicable, None for season-level data
        season_id: NHL season ID (e.g., 20242025)
        data: Parsed data as a dictionary
        downloaded_at: Timestamp when the download completed
        status: Current status of the download
        raw_content: Original bytes if preservation is needed (e.g., HTML)
        error_message: Error details if status is FAILED
        retry_count: Number of retries attempted
    """

    source: str
    season_id: int
    data: dict[str, Any]
    downloaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    game_id: int | None = None
    status: DownloadStatus = DownloadStatus.COMPLETED
    raw_content: bytes | None = None
    error_message: str | None = None
    retry_count: int = 0

    def __post_init__(self) -> None:
        """Validate the download result."""
        if self.status == DownloadStatus.FAILED and not self.error_message:
            object.__setattr__(
                self, "error_message", "Download failed with no error message"
            )

    @property
    def is_successful(self) -> bool:
        """Check if the download was successful."""
        return self.status == DownloadStatus.COMPLETED

    @property
    def is_game_level(self) -> bool:
        """Check if this result is for a specific game."""
        return self.game_id is not None


@runtime_checkable
class Downloader(Protocol):
    """Protocol defining the interface for NHL data downloaders.

    All downloaders must implement this protocol to ensure consistent
    behavior across different data sources (JSON API, HTML reports, etc.).

    The protocol uses structural subtyping, so classes don't need to
    explicitly inherit from it - they just need to implement the methods.
    """

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source.

        Examples: "nhl_json_schedule", "nhl_json_boxscore", "html_gs", "html_es"
        """
        ...

    async def download_season(
        self, season_id: int, *, force: bool = False
    ) -> AsyncIterator[DownloadResult]:
        """Download all data for a season.

        Args:
            season_id: NHL season ID (e.g., 20242025 for 2024-25 season)
            force: If True, re-download even if data exists

        Yields:
            DownloadResult for each downloaded item (game, report, etc.)

        Raises:
            DownloadError: If a critical error occurs that prevents continuation
        """
        ...

    async def download_game(self, game_id: int) -> DownloadResult:
        """Download data for a specific game.

        Args:
            game_id: NHL game ID

        Returns:
            DownloadResult with the game data

        Raises:
            DownloadError: If the download fails after retries
        """
        ...

    async def health_check(self) -> bool:
        """Check if the data source is accessible.

        Returns:
            True if the source is healthy and ready for downloads
        """
        ...


class DownloadError(Exception):
    """Base exception for download errors."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        game_id: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize the download error.

        Args:
            message: Human-readable error description
            source: Data source name where error occurred
            game_id: Game ID if error is game-specific
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.source = source
        self.game_id = game_id
        self.cause = cause

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.source:
            parts.append(f"source={self.source}")
        if self.game_id:
            parts.append(f"game_id={self.game_id}")
        return " ".join(parts)


class RateLimitError(DownloadError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class HealthCheckError(DownloadError):
    """Raised when health check fails."""

    pass
