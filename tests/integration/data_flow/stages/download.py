"""Download stage validation for data flow tests.

This module handles downloading data from all configured sources
and capturing results for validation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.integration.data_flow.sources.registry import SourceDefinition

logger = logging.getLogger(__name__)


@dataclass
class DownloadStageResult:
    """Result of a download operation for a single source.

    Attributes:
        source_name: Identifier of the data source
        success: Whether the download completed successfully
        download_time_ms: Time taken to download in milliseconds
        data: Parsed data from the download (if successful)
        raw_content: Raw bytes content (if preserved)
        error: Error message if download failed
        game_id: Game ID used for the download (if applicable)
        downloaded_at: Timestamp when download completed
    """

    source_name: str
    success: bool
    download_time_ms: float
    data: Any | None = None
    raw_content: bytes | None = None
    error: str | None = None
    game_id: int | None = None
    downloaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_data(self) -> bool:
        """Check if the result has data."""
        return self.data is not None

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAILED"
        return f"DownloadStageResult({self.source_name}={status}, {self.download_time_ms:.1f}ms)"


class DownloadStage:
    """Download stage for data flow testing.

    Handles downloading data from configured sources and capturing
    results for validation in subsequent stages.
    """

    def __init__(self, *, rate_limit_override: float | None = None) -> None:
        """Initialize download stage.

        Args:
            rate_limit_override: Override rate limit for faster testing
        """
        self.rate_limit_override = rate_limit_override

    async def download_source(
        self,
        source: SourceDefinition,
        game_id: int | None = None,
        season_id: int | None = None,
        team_id: int | None = None,
        *,
        config_overrides: dict[str, Any] | None = None,
    ) -> DownloadStageResult:
        """Download data from a single source.

        Args:
            source: Source definition to download from
            game_id: Game ID for game-level sources
            season_id: Season ID for season-level sources
            team_id: Team ID for team-level sources (DailyFaceoff)
            config_overrides: Optional config overrides

        Returns:
            DownloadStageResult with outcome
        """
        start_time = time.perf_counter()
        overrides = config_overrides or {}

        # Apply rate limit override if set
        if self.rate_limit_override is not None:
            overrides["requests_per_second"] = self.rate_limit_override

        try:
            downloader = source.create_downloader(**overrides)

            # Choose download method based on source type
            if source.requires_game_id and game_id is not None:
                result = await downloader.download_game(game_id)
                data = result.data if hasattr(result, "data") else result
            elif team_id is not None and hasattr(downloader, "download_team"):
                # Team-based sources (DailyFaceoff)
                result = await downloader.download_team(team_id)
                data = result.data if hasattr(result, "data") else result
            elif season_id is not None:
                # For season-level sources, download first item
                async for result in downloader.download_season(season_id):
                    data = result.data if hasattr(result, "data") else result
                    break
                else:
                    data = None
            else:
                # Fallback: use health check to verify connectivity
                await downloader.health_check()
                data = {"health_check": True}

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            return DownloadStageResult(
                source_name=source.name,
                success=True,
                download_time_ms=elapsed_ms,
                data=data,
                game_id=game_id,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(f"Download failed for {source.name}: {e}")

            return DownloadStageResult(
                source_name=source.name,
                success=False,
                download_time_ms=elapsed_ms,
                error=str(e),
                game_id=game_id,
            )

    async def download_game_sources(
        self,
        sources: list[SourceDefinition],
        game_id: int,
        *,
        config_overrides: dict[str, Any] | None = None,
    ) -> dict[str, DownloadStageResult]:
        """Download data from all game-level sources.

        Args:
            sources: List of source definitions to download from
            game_id: Game ID to download
            config_overrides: Optional config overrides

        Returns:
            Dictionary mapping source names to results
        """
        results: dict[str, DownloadStageResult] = {}

        for source in sources:
            if not source.requires_game_id:
                continue

            result = await self.download_source(
                source,
                game_id=game_id,
                config_overrides=config_overrides,
            )
            results[source.name] = result

            logger.info(
                f"Downloaded {source.name}: "
                f"{'OK' if result.success else 'FAILED'} "
                f"({result.download_time_ms:.1f}ms)"
            )

        return results

    async def download_all_sources(
        self,
        sources: list[SourceDefinition],
        game_id: int | None = None,
        season_id: int | None = None,
        *,
        config_overrides: dict[str, Any] | None = None,
    ) -> dict[str, DownloadStageResult]:
        """Download data from all configured sources.

        Args:
            sources: List of source definitions to download from
            game_id: Game ID for game-level sources
            season_id: Season ID for season-level sources
            config_overrides: Optional config overrides

        Returns:
            Dictionary mapping source names to results
        """
        results: dict[str, DownloadStageResult] = {}

        for source in sources:
            result = await self.download_source(
                source,
                game_id=game_id if source.requires_game_id else None,
                season_id=season_id,
                config_overrides=config_overrides,
            )
            results[source.name] = result

            logger.info(
                f"Downloaded {source.name}: "
                f"{'OK' if result.success else 'FAILED'} "
                f"({result.download_time_ms:.1f}ms)"
            )

        return results

    @staticmethod
    def summarize_results(
        results: dict[str, DownloadStageResult],
    ) -> dict[str, Any]:
        """Generate summary statistics for download results.

        Args:
            results: Dictionary of download results

        Returns:
            Summary dictionary with counts and timing
        """
        total = len(results)
        passed = sum(1 for r in results.values() if r.success)
        failed = total - passed
        total_time_ms = sum(r.download_time_ms for r in results.values())

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / total * 100) if total > 0 else 0,
            "total_time_ms": total_time_ms,
            "avg_time_ms": (total_time_ms / total) if total > 0 else 0,
            "failed_sources": [
                r.source_name for r in results.values() if not r.success
            ],
        }
