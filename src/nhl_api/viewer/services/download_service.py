"""Download orchestration service for viewer-triggered downloads.

This service manages async download tasks triggered from the viewer UI.
It maintains an in-memory registry of active downloads and coordinates
with the database for batch tracking.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import DownloaderConfig

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com/v1"

# Map source names to their source_id in the data_sources table
# These IDs are seeded in migrations/008_provenance.sql
SOURCE_NAME_TO_ID = {
    "nhl_schedule": 1,
    "nhl_boxscore": 2,
    "nhl_pbp": 3,
    "nhl_roster": 4,
    "nhl_standings": 5,
    "nhl_player": 6,
    # HTML sources (7-15) will be added when implemented
    "shift_chart": 16,  # NHL Stats API shift charts
}


@dataclass
class ActiveDownloadTask:
    """Tracks an active download task."""

    batch_id: int
    source_id: int
    source_name: str
    source_type: str
    season_id: int
    started_at: datetime
    task: asyncio.Task[None]
    cancel_requested: bool = False
    items_total: int | None = None
    items_completed: int = 0
    items_failed: int = 0


@dataclass
class DownloadService:
    """Manages download tasks triggered from viewer.

    This is designed as a singleton to track active downloads across
    multiple API requests. Use get_instance() to access.
    """

    _active_downloads: dict[int, ActiveDownloadTask] = field(default_factory=dict)

    # Singleton instance
    _instance: DownloadService | None = None

    @classmethod
    def get_instance(cls) -> DownloadService:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start_download(
        self,
        db: DatabaseService,
        source_name: str,
        season_id: int,
        force: bool = False,
    ) -> int:
        """Start a download for a specific source and season.

        Args:
            db: Database service
            source_name: Name of the data source (e.g., "nhl_schedule")
            season_id: Season ID (e.g., 20242025)
            force: Re-download even if already completed

        Returns:
            batch_id of the created download batch
        """
        # Get source info from database
        source_row = await db.fetchrow(
            "SELECT source_id, source_type FROM data_sources WHERE name = $1",
            source_name,
        )

        if not source_row:
            raise ValueError(f"Unknown source: {source_name}")

        source_id = source_row["source_id"]
        source_type = source_row["source_type"]

        # Create batch in database
        batch_id: int = await db.fetchval(
            """
            INSERT INTO import_batches (source_id, season_id, status)
            VALUES ($1, $2, 'running')
            RETURNING batch_id
            """,
            source_id,
            season_id,
        )

        logger.info(
            "Created batch %d for %s season %d",
            batch_id,
            source_name,
            season_id,
        )

        # Create and start async task
        task = asyncio.create_task(
            self._run_download(db, batch_id, source_name, source_type, season_id, force)
        )

        # Track the active download
        self._active_downloads[batch_id] = ActiveDownloadTask(
            batch_id=batch_id,
            source_id=source_id,
            source_name=source_name,
            source_type=source_type,
            season_id=season_id,
            started_at=datetime.now(UTC),
            task=task,
        )

        return batch_id

    async def cancel_download(self, db: DatabaseService, batch_id: int) -> bool:
        """Cancel an active download.

        Args:
            db: Database service
            batch_id: Batch ID to cancel

        Returns:
            True if cancelled, False if not found
        """
        if batch_id not in self._active_downloads:
            return False

        download = self._active_downloads[batch_id]
        download.cancel_requested = True
        download.task.cancel()

        # Update database
        await db.execute(
            """
            UPDATE import_batches
            SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP
            WHERE batch_id = $1
            """,
            batch_id,
        )

        logger.info("Cancelled batch %d", batch_id)
        return True

    def get_active_downloads(self) -> list[dict[str, Any]]:
        """Get list of active downloads with progress.

        Returns:
            List of active download info dictionaries
        """
        result: list[dict[str, Any]] = []
        for download in self._active_downloads.values():
            # Calculate progress percent
            progress_percent = None
            if download.items_total and download.items_total > 0:
                completed = download.items_completed + download.items_failed
                progress_percent = (completed / download.items_total) * 100

            result.append(
                {
                    "batch_id": download.batch_id,
                    "source_id": download.source_id,
                    "source_name": download.source_name,
                    "source_type": download.source_type,
                    "season_id": download.season_id,
                    "started_at": download.started_at,
                    "items_total": download.items_total,
                    "items_completed": download.items_completed,
                    "items_failed": download.items_failed,
                    "progress_percent": progress_percent,
                }
            )

        return result

    async def _run_download(
        self,
        db: DatabaseService,
        batch_id: int,
        source_name: str,
        source_type: str,
        season_id: int,
        force: bool,
    ) -> None:
        """Execute the download for a specific source and season.

        This runs in an async task and updates progress in the database.
        """
        try:
            if source_type == "nhl_json":
                await self._run_nhl_json_download(
                    db, batch_id, source_name, season_id, force
                )
            elif source_type == "shift_chart":
                await self._run_shift_chart_download(
                    db, batch_id, source_name, season_id, force
                )
            elif source_type == "html_report":
                # HTML downloaders not yet implemented
                logger.warning("HTML downloaders not yet implemented: %s", source_name)
                await self._complete_batch(db, batch_id, "failed", "Not implemented")
            else:
                logger.error("Unknown source type: %s", source_type)
                await self._complete_batch(
                    db, batch_id, "failed", "Unknown source type"
                )

        except asyncio.CancelledError:
            logger.info("Download cancelled for batch %d", batch_id)
            # Status already updated in cancel_download()

        except Exception as e:
            logger.exception("Download failed for batch %d", batch_id)
            await self._complete_batch(db, batch_id, "failed", str(e))

        finally:
            # Remove from active downloads
            self._active_downloads.pop(batch_id, None)

    async def _run_nhl_json_download(
        self,
        db: DatabaseService,
        batch_id: int,
        source_name: str,
        season_id: int,
        force: bool,
    ) -> None:
        """Run a download for an NHL JSON API source."""
        from nhl_api.downloaders.sources.nhl_json import (
            BoxscoreDownloader,
            PlayByPlayDownloader,
            PlayerLandingDownloader,
            RosterDownloader,
            ScheduleDownloader,
            StandingsDownloader,
        )

        config = DownloaderConfig(base_url=NHL_API_BASE_URL)

        # Map source names to downloader classes
        downloader_map = {
            "nhl_schedule": ScheduleDownloader,
            "nhl_boxscore": BoxscoreDownloader,
            "nhl_pbp": PlayByPlayDownloader,
            "nhl_roster": RosterDownloader,
            "nhl_standings": StandingsDownloader,
            "nhl_player": PlayerLandingDownloader,
        }

        downloader_cls = downloader_map.get(source_name)
        if not downloader_cls:
            raise ValueError(f"No downloader for source: {source_name}")

        active_download = self._active_downloads.get(batch_id)

        async with downloader_cls(config) as downloader:
            # Handle different downloader types
            if source_name == "nhl_schedule":
                await self._download_schedule(
                    db, batch_id, downloader, season_id, active_download
                )
            elif source_name in ("nhl_boxscore", "nhl_pbp"):
                await self._download_game_based(
                    db, batch_id, downloader, season_id, active_download, source_name
                )
            elif source_name == "nhl_roster":
                await self._download_rosters(
                    db, batch_id, downloader, season_id, active_download
                )
            elif source_name == "nhl_standings":
                await self._download_standings(
                    db, batch_id, downloader, season_id, active_download
                )
            elif source_name == "nhl_player":
                await self._download_player_landing(
                    db, batch_id, downloader, season_id, active_download
                )

        await self._complete_batch(db, batch_id, "completed")

    async def _run_shift_chart_download(
        self,
        db: DatabaseService,
        batch_id: int,
        source_name: str,
        season_id: int,
        force: bool,
    ) -> None:
        """Run a download for NHL Stats API shift charts."""
        from nhl_api.downloaders.sources.nhl_json import ScheduleDownloader
        from nhl_api.downloaders.sources.nhl_stats import (
            ShiftChartsDownloader,
            ShiftChartsDownloaderConfig,
        )

        active_download = self._active_downloads.get(batch_id)

        # First get completed game IDs from schedule
        schedule_config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        schedule_dl = ScheduleDownloader(schedule_config)
        async with schedule_dl:
            games = await schedule_dl.get_season_schedule(season_id)

        # Filter to only completed games
        completed_games = [g for g in games if g.game_state in ("OFF", "FINAL")]
        game_ids = [g.game_id for g in completed_games]

        logger.info(
            "Downloading shift charts for %d completed games (filtered from %d total)",
            len(game_ids),
            len(games),
        )

        if active_download:
            active_download.items_total = len(game_ids)

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            len(game_ids),
            batch_id,
        )

        # Create shift charts downloader
        config = ShiftChartsDownloaderConfig()
        shift_dl = ShiftChartsDownloader(config, game_ids=game_ids)

        # Collect results for batch persistence
        successful_results: list[Any] = []

        async with shift_dl:
            async for result in shift_dl.download_season(season_id):
                if active_download and active_download.cancel_requested:
                    raise asyncio.CancelledError()

                if result.is_successful:
                    successful_results.append(result.data)
                    if active_download:
                        active_download.items_completed += 1
                    await db.execute(
                        "UPDATE import_batches SET items_success = items_success + 1 WHERE batch_id = $1",
                        batch_id,
                    )
                else:
                    if active_download:
                        active_download.items_failed += 1
                    await db.execute(
                        "UPDATE import_batches SET items_failed = items_failed + 1 WHERE batch_id = $1",
                        batch_id,
                    )

        # Persist all collected shift charts
        if successful_results:
            persisted = await shift_dl.persist(db, successful_results)
            logger.info(
                "Persisted %d shifts for season %d",
                persisted,
                season_id,
            )

        await self._complete_batch(db, batch_id, "completed")

    async def _download_schedule(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download schedule for a season."""
        games = await downloader.get_season_schedule(season_id)

        if active_download:
            active_download.items_total = len(games)

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            len(games),
            batch_id,
        )

        # Persist games to database
        persisted = await downloader.persist(db, games)

        if active_download:
            active_download.items_completed = persisted

        await db.execute(
            "UPDATE import_batches SET items_success = $1 WHERE batch_id = $2",
            persisted,
            batch_id,
        )

        logger.info(
            "Downloaded and persisted %d games for season %d", persisted, season_id
        )

    async def _download_game_based(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        active_download: ActiveDownloadTask | None,
        source_name: str = "",
    ) -> None:
        """Download game-based data (boxscore, play-by-play)."""
        from nhl_api.downloaders.sources.nhl_json import ScheduleDownloader

        # First get game IDs from schedule
        schedule_config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        schedule_dl = ScheduleDownloader(schedule_config)
        async with schedule_dl:
            games = await schedule_dl.get_season_schedule(season_id)

        # Filter to only completed games - future games return 404 for boxscore/pbp
        completed_games = [g for g in games if g.game_state in ("OFF", "FINAL")]
        game_ids = [g.game_id for g in completed_games]
        downloader.set_game_ids(game_ids)

        logger.info(
            "Downloading %s for %d completed games (filtered from %d total)",
            source_name,
            len(game_ids),
            len(games),
        )

        if active_download:
            active_download.items_total = len(game_ids)

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            len(game_ids),
            batch_id,
        )

        # Collect results for persistence
        successful_results: list[dict[str, Any]] = []

        # Download each game
        async for result in downloader.download_season(season_id):
            if active_download and active_download.cancel_requested:
                raise asyncio.CancelledError()

            if result.is_successful:
                successful_results.append(result.data)
                if active_download:
                    active_download.items_completed += 1
                await db.execute(
                    "UPDATE import_batches SET items_success = items_success + 1 WHERE batch_id = $1",
                    batch_id,
                )
            else:
                if active_download:
                    active_download.items_failed += 1
                await db.execute(
                    "UPDATE import_batches SET items_failed = items_failed + 1 WHERE batch_id = $1",
                    batch_id,
                )

        # Persist collected results
        if successful_results:
            if source_name == "nhl_boxscore":
                await downloader.persist(db, successful_results)
                logger.info(
                    "Persisted %d boxscores for season %d",
                    len(successful_results),
                    season_id,
                )
            elif source_name == "nhl_pbp":
                persisted = await downloader.persist(db, successful_results)
                logger.info(
                    "Persisted %d play-by-play events for season %d",
                    persisted,
                    season_id,
                )

    async def _download_rosters(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download rosters for all teams."""
        from nhl_api.downloaders.sources.nhl_json import NHL_TEAM_ABBREVS

        teams = NHL_TEAM_ABBREVS

        if active_download:
            active_download.items_total = len(teams)

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            len(teams),
            batch_id,
        )

        for team_abbrev in teams:
            if active_download and active_download.cancel_requested:
                raise asyncio.CancelledError()

            try:
                await downloader.get_roster_for_season(team_abbrev, season_id)
                if active_download:
                    active_download.items_completed += 1
                await db.execute(
                    "UPDATE import_batches SET items_success = items_success + 1 WHERE batch_id = $1",
                    batch_id,
                )
            except Exception as e:
                logger.warning("Failed to download roster for %s: %s", team_abbrev, e)
                if active_download:
                    active_download.items_failed += 1
                await db.execute(
                    "UPDATE import_batches SET items_failed = items_failed + 1 WHERE batch_id = $1",
                    batch_id,
                )

    async def _download_standings(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download standings snapshots for a season and persist to database."""
        # Get current standings (single snapshot)
        if active_download:
            active_download.items_total = 1

        await db.execute(
            "UPDATE import_batches SET items_total = 1 WHERE batch_id = $1",
            batch_id,
        )

        try:
            standings = await downloader.get_current_standings()

            # Persist standings to database
            persisted = await downloader.persist(db, standings)

            if active_download:
                active_download.items_completed = 1
            await db.execute(
                "UPDATE import_batches SET items_success = $1 WHERE batch_id = $2",
                persisted,
                batch_id,
            )
            logger.info("Downloaded and persisted standings for %d teams", persisted)
        except Exception as e:
            logger.warning("Failed to download standings: %s", e)
            if active_download:
                active_download.items_failed = 1
            await db.execute(
                "UPDATE import_batches SET items_failed = 1 WHERE batch_id = $1",
                batch_id,
            )

    async def _download_player_landing(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download player landing pages."""
        # Get player IDs from rosters
        from nhl_api.downloaders.sources.nhl_json import (
            NHL_TEAM_ABBREVS,
            RosterDownloader,
        )

        roster_config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        player_ids: set[int] = set()

        roster_dl = RosterDownloader(roster_config)
        async with roster_dl:
            for team_abbrev in NHL_TEAM_ABBREVS:
                try:
                    roster = await roster_dl.get_roster_for_season(
                        team_abbrev, season_id
                    )
                    for player in roster.forwards + roster.defensemen + roster.goalies:
                        player_ids.add(player.player_id)
                except Exception as e:
                    logger.warning("Failed to get roster for %s: %s", team_abbrev, e)

        downloader.set_player_ids(list(player_ids))

        if active_download:
            active_download.items_total = len(player_ids)

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            len(player_ids),
            batch_id,
        )

        # Download each player
        async for result in downloader.download_all():
            if active_download and active_download.cancel_requested:
                raise asyncio.CancelledError()

            if result.is_successful:
                if active_download:
                    active_download.items_completed += 1
                await db.execute(
                    "UPDATE import_batches SET items_success = items_success + 1 WHERE batch_id = $1",
                    batch_id,
                )
            else:
                if active_download:
                    active_download.items_failed += 1
                await db.execute(
                    "UPDATE import_batches SET items_failed = items_failed + 1 WHERE batch_id = $1",
                    batch_id,
                )

    async def _complete_batch(
        self,
        db: DatabaseService,
        batch_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Mark a batch as complete."""
        await db.execute(
            """
            UPDATE import_batches
            SET status = $1, completed_at = CURRENT_TIMESTAMP, error_message = $2
            WHERE batch_id = $3
            """,
            status,
            error_message,
            batch_id,
        )
        logger.info("Batch %d completed with status: %s", batch_id, status)
