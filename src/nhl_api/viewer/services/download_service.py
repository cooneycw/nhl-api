"""Download orchestration service for viewer-triggered downloads.

This service manages async download tasks triggered from the viewer UI.
It maintains an in-memory registry of active downloads and coordinates
with the database for batch tracking.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import DownloaderConfig

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com/v1"

# Map source names to their source_id in the data_sources table
# These IDs must match what's in the database (queried from data_sources table)
SOURCE_NAME_TO_ID = {
    # NHL JSON API sources (IDs from 008_provenance.sql)
    "nhl_schedule": 1,
    "nhl_boxscore": 2,
    "nhl_pbp": 3,
    "nhl_roster": 4,
    "nhl_standings": 5,
    "nhl_player": 6,
    "nhl_player_game_log": 20,
    # HTML report sources (IDs from 008_provenance.sql)
    "html_game_summary": 7,  # Mapped from html_gs
    "html_event_summary": 8,  # Mapped from html_es
    "html_time_on_ice": 15,  # Mapped from html_th (home side)
    "html_faceoff_summary": 10,  # Mapped from html_fs
    "html_shot_summary": 13,  # Mapped from html_ss
    # Shift charts (ID from 008_provenance.sql)
    "shift_chart": 16,
    # DailyFaceoff sources (IDs from 022_dailyfaceoff.sql)
    "dailyfaceoff_lines": 18,
    "dailyfaceoff_power_play": 23,
    "dailyfaceoff_penalty_kill": 24,
    "dailyfaceoff_injuries": 25,
    "dailyfaceoff_starting_goalies": 26,
    # QuantHockey sources (IDs from 023_quanthockey.sql)
    "quanthockey_player_stats": 21,
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
    game_types: list[int] = field(
        default_factory=lambda: [2]
    )  # Default: regular season
    cancel_requested: bool = False
    items_total: int | None = None
    items_completed: int = 0
    items_failed: int = 0


@dataclass
class SyncTimestamp:
    """Represents a sync timestamp from the database."""

    source_id: int
    season_id: int
    game_type: int
    last_synced_at: datetime
    items_synced_count: int
    last_batch_id: int | None


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
        game_types: list[int] | None = None,
        force: bool = False,
    ) -> int:
        """Start a download for a specific source and season.

        Args:
            db: Database service
            source_name: Name of the data source (e.g., "nhl_schedule")
            season_id: Season ID (e.g., 20242025)
            game_types: Game types to include (1=pre, 2=regular, 3=playoffs)
            force: Re-download even if already completed

        Returns:
            batch_id of the created download batch
        """
        if game_types is None:
            game_types = [2]  # Default to regular season only
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
            self._run_download(
                db, batch_id, source_name, source_type, season_id, game_types, force
            )
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
            game_types=game_types,
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

    async def _get_last_sync(
        self,
        db: DatabaseService,
        source_id: int,
        season_id: int,
        game_type: int,
    ) -> SyncTimestamp | None:
        """Get last sync timestamp for a source/season/game_type.

        Args:
            db: Database service
            source_id: Source ID from data_sources table
            season_id: Season ID (e.g., 20242025)
            game_type: Game type (1=pre, 2=regular, 3=playoffs, 0=external)

        Returns:
            SyncTimestamp if found, None otherwise
        """
        row = await db.fetchrow(
            """
            SELECT source_id, season_id, game_type, last_synced_at,
                   items_synced_count, last_batch_id
            FROM source_sync_timestamps
            WHERE source_id = $1 AND season_id = $2 AND game_type = $3
            """,
            source_id,
            season_id,
            game_type,
        )

        if not row:
            return None

        return SyncTimestamp(
            source_id=row["source_id"],
            season_id=row["season_id"],
            game_type=row["game_type"],
            last_synced_at=row["last_synced_at"],
            items_synced_count=row["items_synced_count"],
            last_batch_id=row["last_batch_id"],
        )

    async def _update_sync_timestamp(
        self,
        db: DatabaseService,
        source_id: int,
        season_id: int,
        game_type: int,
        items_count: int,
        batch_id: int,
    ) -> None:
        """Update sync timestamp after successful batch.

        Uses upsert to create or update the timestamp.

        Args:
            db: Database service
            source_id: Source ID from data_sources table
            season_id: Season ID
            game_type: Game type (1=pre, 2=regular, 3=playoffs, 0=external)
            items_count: Number of items synced in this batch
            batch_id: The batch ID that completed the sync
        """
        await db.execute(
            """
            INSERT INTO source_sync_timestamps
                (source_id, season_id, game_type, last_synced_at, items_synced_count, last_batch_id)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP, $4, $5)
            ON CONFLICT (source_id, season_id, game_type) DO UPDATE SET
                last_synced_at = CURRENT_TIMESTAMP,
                items_synced_count = source_sync_timestamps.items_synced_count + EXCLUDED.items_synced_count,
                last_batch_id = EXCLUDED.last_batch_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            source_id,
            season_id,
            game_type,
            items_count,
            batch_id,
        )

        logger.debug(
            "Updated sync timestamp: source=%d season=%d game_type=%d items=%d",
            source_id,
            season_id,
            game_type,
            items_count,
        )

    async def _run_download(
        self,
        db: DatabaseService,
        batch_id: int,
        source_name: str,
        source_type: str,
        season_id: int,
        game_types: list[int],
        force: bool,
    ) -> None:
        """Execute the download for a specific source and season.

        This runs in an async task and updates progress in the database.
        """
        try:
            if source_type == "nhl_json":
                await self._run_nhl_json_download(
                    db, batch_id, source_name, season_id, game_types, force
                )
            elif source_type == "shift_chart":
                await self._run_shift_chart_download(
                    db, batch_id, source_name, season_id, game_types, force
                )
            elif source_type == "dailyfaceoff":
                await self._run_dailyfaceoff_download(
                    db, batch_id, source_name, season_id, force
                )
            elif source_type == "quanthockey":
                await self._run_quanthockey_download(
                    db, batch_id, source_name, season_id, force
                )
            elif source_type == "html_report":
                await self._run_html_report_download(
                    db, batch_id, source_name, season_id, game_types, force
                )
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
        game_types: list[int],
        force: bool,
    ) -> None:
        """Run a download for an NHL JSON API source."""
        from nhl_api.downloaders.sources.nhl_json import (
            BoxscoreDownloader,
            PlayByPlayDownloader,
            PlayerGameLogDownloader,
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
            "nhl_player_game_log": PlayerGameLogDownloader,
        }

        downloader_cls = downloader_map.get(source_name)
        if not downloader_cls:
            raise ValueError(f"No downloader for source: {source_name}")

        active_download = self._active_downloads.get(batch_id)

        async with downloader_cls(config) as downloader:
            # Handle different downloader types
            if source_name == "nhl_schedule":
                await self._download_schedule(
                    db, batch_id, downloader, season_id, game_types, active_download
                )
            elif source_name in ("nhl_boxscore", "nhl_pbp"):
                items_synced = await self._download_game_based(
                    db,
                    batch_id,
                    downloader,
                    season_id,
                    game_types,
                    active_download,
                    source_name,
                )
                # Update sync timestamps for each game_type
                source_id = SOURCE_NAME_TO_ID.get(source_name)
                if source_id and items_synced > 0:
                    for gt in game_types:
                        await self._update_sync_timestamp(
                            db, source_id, season_id, gt, items_synced, batch_id
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
            elif source_name == "nhl_player_game_log":
                await self._download_player_game_logs(
                    db, batch_id, downloader, season_id, active_download
                )

        await self._complete_batch(db, batch_id, "completed")

    async def _run_shift_chart_download(
        self,
        db: DatabaseService,
        batch_id: int,
        source_name: str,
        season_id: int,
        game_types: list[int],
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
            all_games = await schedule_dl.get_season_schedule(season_id)

        # Filter by game types first, then by completed status
        type_filtered = [g for g in all_games if g.game_type in game_types]
        completed_games = [g for g in type_filtered if g.game_state in ("OFF", "FINAL")]

        # Delta filtering: Check last sync timestamp and filter by game date
        source_id = SOURCE_NAME_TO_ID.get(source_name)
        delta_filtered_games = completed_games
        is_delta_sync = False

        if source_id:
            # Get the earliest sync timestamp across all specified game_types
            earliest_sync: datetime | None = None
            for gt in game_types:
                sync_ts = await self._get_last_sync(db, source_id, season_id, gt)
                if sync_ts:
                    if earliest_sync is None or sync_ts.last_synced_at < earliest_sync:
                        earliest_sync = sync_ts.last_synced_at

            if earliest_sync:
                # Filter to games after the earliest sync
                sync_date = earliest_sync.date()
                delta_filtered_games = [
                    g for g in completed_games if g.game_date > sync_date
                ]
                is_delta_sync = True
                logger.info(
                    "Shift charts delta sync: filtering %d completed games to %d since %s",
                    len(completed_games),
                    len(delta_filtered_games),
                    sync_date.isoformat(),
                )

        game_ids = [g.game_id for g in delta_filtered_games]

        logger.info(
            "Downloading shift charts for %d %sgames (game_types=%s, %d total)",
            len(game_ids),
            "delta " if is_delta_sync else "completed ",
            game_types,
            len(all_games),
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

            # Update sync timestamps for each game_type
            if source_id:
                for gt in game_types:
                    await self._update_sync_timestamp(
                        db, source_id, season_id, gt, len(successful_results), batch_id
                    )

        await self._complete_batch(db, batch_id, "completed")

    async def _run_dailyfaceoff_download(
        self,
        db: DatabaseService,
        batch_id: int,
        source_name: str,
        season_id: int,
        force: bool,
    ) -> None:
        """Run a download for DailyFaceoff data sources.

        DailyFaceoff data is team-based (not game-based), so we iterate
        through all 32 teams rather than games.
        """
        from nhl_api.downloaders.sources.dailyfaceoff import (
            DailyFaceoffConfig,
            InjuryDownloader,
            LineCombinationsDownloader,
            PenaltyKillDownloader,
            PowerPlayDownloader,
            StartingGoaliesDownloader,
        )

        config = DailyFaceoffConfig()
        active_download = self._active_downloads.get(batch_id)
        snapshot_date = date.today()

        # Map source names to downloader classes
        downloader_map: dict[str, type] = {
            "dailyfaceoff_lines": LineCombinationsDownloader,
            "dailyfaceoff_power_play": PowerPlayDownloader,
            "dailyfaceoff_penalty_kill": PenaltyKillDownloader,
            "dailyfaceoff_injuries": InjuryDownloader,
            "dailyfaceoff_starting_goalies": StartingGoaliesDownloader,
        }

        downloader_cls = downloader_map.get(source_name)
        if not downloader_cls:
            raise ValueError(f"No downloader for source: {source_name}")

        logger.info(
            "Starting DailyFaceoff download: %s for season %d",
            source_name,
            season_id,
        )

        async with downloader_cls(config) as downloader:
            # Starting goalies is date-based, not team-based
            if source_name == "dailyfaceoff_starting_goalies":
                await self._download_starting_goalies(
                    db, batch_id, downloader, season_id, snapshot_date, active_download
                )
            else:
                # Team-based downloads (lines, PP, PK, injuries)
                await self._download_team_based_dailyfaceoff(
                    db,
                    batch_id,
                    downloader,
                    source_name,
                    season_id,
                    snapshot_date,
                    active_download,
                )

        await self._complete_batch(db, batch_id, "completed")

    async def _run_quanthockey_download(
        self,
        db: DatabaseService,
        batch_id: int,
        source_name: str,
        season_id: int,
        force: bool,
    ) -> None:
        """Run a download for QuantHockey player statistics.

        QuantHockey data is season-based (not game or team based), so we
        download all player stats for the entire season in one batch.
        """
        from nhl_api.downloaders.sources.external.quanthockey import (
            QuantHockeyConfig,
            QuantHockeyPlayerStatsDownloader,
        )

        config = QuantHockeyConfig()
        active_download = self._active_downloads.get(batch_id)
        snapshot_date = date.today()

        logger.info(
            "Starting QuantHockey download: %s for season %d",
            source_name,
            season_id,
        )

        # QuantHockey fetches all players in a single season download
        # Set items_total to 1 (we're downloading one season's worth of data)
        if active_download:
            active_download.items_total = 1

        await db.execute(
            "UPDATE import_batches SET items_total = 1 WHERE batch_id = $1",
            batch_id,
        )

        downloader = QuantHockeyPlayerStatsDownloader(config)
        async with downloader:
            try:
                # Download all player stats for the season
                players = await downloader.download_player_stats(
                    season_id,
                    max_players=None,  # Get all players
                    max_pages=20,  # Up to 400 players
                )

                logger.info(
                    "Downloaded %d players from QuantHockey for season %d",
                    len(players),
                    season_id,
                )

                # Persist to database
                persisted = await downloader.persist(
                    db, players, season_id, snapshot_date
                )

                logger.info(
                    "Persisted %d QuantHockey player records for season %d",
                    persisted,
                    season_id,
                )

                if active_download:
                    active_download.items_completed = 1
                await db.execute(
                    "UPDATE import_batches SET items_success = 1 WHERE batch_id = $1",
                    batch_id,
                )

            except Exception:
                logger.exception(
                    "Failed to download QuantHockey stats for season %d", season_id
                )
                if active_download:
                    active_download.items_failed = 1
                await db.execute(
                    "UPDATE import_batches SET items_failed = 1 WHERE batch_id = $1",
                    batch_id,
                )
                raise

        await self._complete_batch(db, batch_id, "completed")

    async def _download_team_based_dailyfaceoff(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        source_name: str,
        season_id: int,
        snapshot_date: Any,  # date type
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download DailyFaceoff data for all teams.

        This handles lines, power play, penalty kill, and injuries which
        are all team-based downloads.
        """
        from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import TEAM_SLUGS

        # Get all active team IDs (exclude Arizona Coyotes)
        team_ids = [tid for tid in TEAM_SLUGS.keys() if tid != 53]

        if active_download:
            active_download.items_total = len(team_ids)

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            len(team_ids),
            batch_id,
        )

        logger.info(
            "Downloading %s for %d teams",
            source_name,
            len(team_ids),
        )

        # Collect results for batch persistence
        successful_results: list[tuple[str, dict[str, Any]]] = []

        async for result in downloader.download_all_teams():
            if active_download and active_download.cancel_requested:
                raise asyncio.CancelledError()

            team_abbrev = result.data.get("team_abbreviation", "")

            if result.is_successful:
                successful_results.append((team_abbrev, result.data))
                if active_download:
                    active_download.items_completed += 1
                await db.execute(
                    "UPDATE import_batches SET items_success = items_success + 1 WHERE batch_id = $1",
                    batch_id,
                )
            else:
                logger.warning(
                    "Failed to download %s for team %s: %s",
                    source_name,
                    team_abbrev,
                    result.error_message,
                )
                if active_download:
                    active_download.items_failed += 1
                await db.execute(
                    "UPDATE import_batches SET items_failed = items_failed + 1 WHERE batch_id = $1",
                    batch_id,
                )

        # Persist all collected results
        if successful_results:
            total_persisted = 0
            for team_abbrev, data in successful_results:
                try:
                    # DailyFaceoff persist methods extract team_abbrev from data
                    count = await downloader.persist(db, data, season_id, snapshot_date)
                    total_persisted += count
                except Exception as e:
                    logger.warning(
                        "Failed to persist %s for %s: %s",
                        source_name,
                        team_abbrev,
                        e,
                    )

            logger.info(
                "Persisted %d %s records for season %d",
                total_persisted,
                source_name,
                season_id,
            )

    async def _download_starting_goalies(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        snapshot_date: Any,  # date type
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download DailyFaceoff starting goalies for today's games.

        Starting goalies is a league-wide page, not team-by-team.
        """
        if active_download:
            active_download.items_total = 1

        await db.execute(
            "UPDATE import_batches SET items_total = 1 WHERE batch_id = $1",
            batch_id,
        )

        try:
            # Download the starting goalies page
            result = await downloader.download_tonight()

            if result.is_successful:
                # Persist the starting goalies
                count = await downloader.persist(db, result.data, snapshot_date)
                logger.info(
                    "Persisted %d starting goalie records for %s",
                    count,
                    snapshot_date,
                )

                if active_download:
                    active_download.items_completed = 1
                await db.execute(
                    "UPDATE import_batches SET items_success = 1 WHERE batch_id = $1",
                    batch_id,
                )
            else:
                logger.warning(
                    "Failed to download starting goalies: %s",
                    result.error_message,
                )
                if active_download:
                    active_download.items_failed = 1
                await db.execute(
                    "UPDATE import_batches SET items_failed = 1 WHERE batch_id = $1",
                    batch_id,
                )

        except Exception:
            logger.exception("Error downloading starting goalies")
            if active_download:
                active_download.items_failed = 1
            await db.execute(
                "UPDATE import_batches SET items_failed = 1 WHERE batch_id = $1",
                batch_id,
            )

    async def _run_html_report_download(
        self,
        db: DatabaseService,
        batch_id: int,
        source_name: str,
        season_id: int,
        game_types: list[int],
        force: bool,
    ) -> None:
        """Run a download for NHL HTML reports.

        HTML reports are game-based. We first fetch the schedule to get game IDs,
        then download and parse each HTML report.
        """
        from nhl_api.downloaders.sources.html import (
            EventSummaryDownloader,
            FaceoffSummaryDownloader,
            GameSummaryDownloader,
            HTMLDownloaderConfig,
            ShotSummaryDownloader,
            TimeOnIceDownloader,
        )
        from nhl_api.downloaders.sources.nhl_json import ScheduleDownloader

        config = HTMLDownloaderConfig()
        active_download = self._active_downloads.get(batch_id)

        # Map source names to downloader classes
        # Names must match what's in the data_sources table
        downloader_map: dict[str, type] = {
            "html_game_summary": GameSummaryDownloader,
            "html_event_summary": EventSummaryDownloader,
            "html_faceoff_summary": FaceoffSummaryDownloader,
            "html_shot_summary": ShotSummaryDownloader,
            # Database aliases (from 008_provenance.sql)
            "html_gs": GameSummaryDownloader,
            "html_es": EventSummaryDownloader,
            "html_fs": FaceoffSummaryDownloader,
            "html_ss": ShotSummaryDownloader,
        }

        # Time on Ice has special handling (home/away sides)
        is_toi = source_name in ("html_time_on_ice", "html_th", "html_tv")

        # Get completed game IDs from schedule
        schedule_config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        schedule_dl = ScheduleDownloader(schedule_config)
        async with schedule_dl:
            all_games = await schedule_dl.get_season_schedule(season_id)

        # Filter by game types and completed status
        type_filtered = [g for g in all_games if g.game_type in game_types]
        completed_games = [g for g in type_filtered if g.game_state in ("OFF", "FINAL")]

        # Delta filtering: Check last sync timestamp and filter by game date
        source_id = SOURCE_NAME_TO_ID.get(source_name)
        delta_filtered_games = completed_games
        is_delta_sync = False

        if source_id:
            # Get the earliest sync timestamp across all specified game_types
            earliest_sync: datetime | None = None
            for gt in game_types:
                sync_ts = await self._get_last_sync(db, source_id, season_id, gt)
                if sync_ts:
                    if earliest_sync is None or sync_ts.last_synced_at < earliest_sync:
                        earliest_sync = sync_ts.last_synced_at

            if earliest_sync:
                # Filter to games after the earliest sync
                sync_date = earliest_sync.date()
                delta_filtered_games = [
                    g for g in completed_games if g.game_date > sync_date
                ]
                is_delta_sync = True
                logger.info(
                    "HTML report delta sync: filtering %d completed games to %d since %s",
                    len(completed_games),
                    len(delta_filtered_games),
                    sync_date.isoformat(),
                )

        game_ids = [g.game_id for g in delta_filtered_games]

        # For TOI, we download both home and away for each game
        total_items = len(game_ids) * 2 if is_toi else len(game_ids)

        logger.info(
            "Downloading %s for %d %sgames (game_types=%s)",
            source_name,
            len(game_ids),
            "delta " if is_delta_sync else "completed ",
            game_types,
        )

        if active_download:
            active_download.items_total = total_items

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            total_items,
            batch_id,
        )

        successful_results: list[dict[str, Any]] = []

        if is_toi:
            # Download both home and away TOI
            for side in ["home", "away"]:
                downloader = TimeOnIceDownloader(config, side=side)
                downloader.set_game_ids(game_ids)

                async with downloader:
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

            # Persist collected TOI data
            if successful_results:
                # Use one of the downloaders for persist (they all have same persist method)
                toi_dl = TimeOnIceDownloader(config, side="home")
                persisted = await toi_dl.persist(db, successful_results)
                logger.info(
                    "Persisted %d HTML time on ice records for season %d",
                    persisted,
                    season_id,
                )
        else:
            # Standard single-sided HTML reports
            downloader_cls = downloader_map.get(source_name)
            if not downloader_cls:
                raise ValueError(f"No downloader for source: {source_name}")

            downloader = downloader_cls(config)
            downloader.set_game_ids(game_ids)

            async with downloader:
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
                persisted = await downloader.persist(db, successful_results)
                logger.info(
                    "Persisted %d %s records for season %d",
                    persisted,
                    source_name,
                    season_id,
                )

                # Update sync timestamps for each game_type
                if source_id:
                    for gt in game_types:
                        await self._update_sync_timestamp(
                            db,
                            source_id,
                            season_id,
                            gt,
                            len(successful_results),
                            batch_id,
                        )

        await self._complete_batch(db, batch_id, "completed")

    async def _download_schedule(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        game_types: list[int],
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download schedule for a season, filtered by game types."""
        # Fetch all games, then filter by game_types
        all_games = await downloader.get_season_schedule(season_id)
        games = [g for g in all_games if g.game_type in game_types]

        logger.info(
            "Filtered schedule: %d games matching game_types %s (from %d total)",
            len(games),
            game_types,
            len(all_games),
        )

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
        game_types: list[int],
        active_download: ActiveDownloadTask | None,
        source_name: str = "",
    ) -> int:
        """Download game-based data (boxscore, play-by-play) with delta tracking.

        Returns:
            Number of items successfully downloaded (for sync timestamp tracking)
        """
        from nhl_api.downloaders.sources.nhl_json import ScheduleDownloader

        # Get source_id for sync timestamp lookup
        source_id = SOURCE_NAME_TO_ID.get(source_name)

        # First get game IDs from schedule
        schedule_config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        schedule_dl = ScheduleDownloader(schedule_config)
        async with schedule_dl:
            all_games = await schedule_dl.get_season_schedule(season_id)

        # Filter by game types first, then by completed status
        type_filtered = [g for g in all_games if g.game_type in game_types]
        completed_games = [g for g in type_filtered if g.game_state in ("OFF", "FINAL")]

        # Delta filtering: Check last sync timestamp and filter by game date
        delta_filtered_games = completed_games
        is_delta_sync = False

        if source_id:
            # Get the earliest sync timestamp across all specified game_types
            earliest_sync: datetime | None = None
            for gt in game_types:
                sync_ts = await self._get_last_sync(db, source_id, season_id, gt)
                if sync_ts:
                    if earliest_sync is None or sync_ts.last_synced_at < earliest_sync:
                        earliest_sync = sync_ts.last_synced_at

            if earliest_sync:
                # Filter to games after the earliest sync
                # Convert datetime to date for comparison with game_date
                sync_date = earliest_sync.date()
                delta_filtered_games = [
                    g for g in completed_games if g.game_date > sync_date
                ]
                is_delta_sync = True
                logger.info(
                    "Delta sync: filtering %d completed games to %d since %s",
                    len(completed_games),
                    len(delta_filtered_games),
                    sync_date.isoformat(),
                )

        game_ids = [g.game_id for g in delta_filtered_games]
        downloader.set_game_ids(game_ids)

        logger.info(
            "Downloading %s for %d %sgames (game_types=%s, %d total in season)",
            source_name,
            len(game_ids),
            "delta " if is_delta_sync else "completed ",
            game_types,
            len(all_games),
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

        return len(successful_results)

    async def _download_rosters(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download rosters for all teams and persist to database."""
        from nhl_api.downloaders.sources.nhl_json import get_teams_for_season
        from nhl_api.downloaders.sources.nhl_json.roster import ParsedRoster

        # Use season-appropriate team list (handles ARI→UTA relocation)
        teams = get_teams_for_season(season_id)

        if active_download:
            active_download.items_total = len(teams)

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            len(teams),
            batch_id,
        )

        # Collect all rosters for persistence
        rosters: list[ParsedRoster] = []

        for team_abbrev in teams:
            if active_download and active_download.cancel_requested:
                raise asyncio.CancelledError()

            try:
                roster = await downloader.get_roster_for_season(team_abbrev, season_id)
                rosters.append(roster)
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

        # Persist collected rosters to database
        if rosters:
            persisted = await downloader.persist(db, rosters)
            logger.info(
                "Downloaded and persisted %d roster entries for season %d",
                persisted,
                season_id,
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
        """Download player landing pages and persist to database."""
        # Get player IDs from rosters
        from nhl_api.downloaders.sources.nhl_json import (
            RosterDownloader,
            get_teams_for_season,
        )

        roster_config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        player_ids: set[int] = set()

        # Use season-appropriate team list (handles ARI→UTA relocation)
        teams = get_teams_for_season(season_id)
        roster_dl = RosterDownloader(roster_config)
        async with roster_dl:
            for team_abbrev in teams:
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

        # Collect successful results for persistence
        successful_results: list[dict[str, Any]] = []

        # Download each player
        async for result in downloader.download_all():
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

        # Persist collected player data
        if successful_results:
            persisted = await downloader.persist(db, successful_results)
            logger.info(
                "Persisted landing data for %d players for season %d",
                persisted,
                season_id,
            )

    async def _download_player_game_logs(
        self,
        db: DatabaseService,
        batch_id: int,
        downloader: Any,
        season_id: int,
        active_download: ActiveDownloadTask | None,
    ) -> None:
        """Download player game logs and persist to database."""
        # Get player IDs from rosters
        from nhl_api.downloaders.sources.nhl_json import (
            RosterDownloader,
            get_teams_for_season,
        )
        from nhl_api.downloaders.sources.nhl_json.player_game_log import REGULAR_SEASON

        roster_config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        player_ids: set[int] = set()

        # Use season-appropriate team list (handles ARI→UTA relocation)
        teams = get_teams_for_season(season_id)
        roster_dl = RosterDownloader(roster_config)
        async with roster_dl:
            for team_abbrev in teams:
                try:
                    roster = await roster_dl.get_roster_for_season(
                        team_abbrev, season_id
                    )
                    for player in roster.forwards + roster.defensemen + roster.goalies:
                        player_ids.add(player.player_id)
                except Exception as e:
                    logger.warning("Failed to get roster for %s: %s", team_abbrev, e)

        # Set players for game log download (player_id, season_id, game_type)
        players_list = [(pid, season_id, REGULAR_SEASON) for pid in player_ids]
        downloader.set_players(players_list)

        if active_download:
            active_download.items_total = len(player_ids)

        await db.execute(
            "UPDATE import_batches SET items_total = $1 WHERE batch_id = $2",
            len(player_ids),
            batch_id,
        )

        # Collect successful results for persistence
        successful_results: list[dict[str, Any]] = []

        # Download each player's game log
        async for result in downloader.download_all():
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

        # Persist collected game logs
        if successful_results:
            persisted = await downloader.persist(db, successful_results)
            logger.info(
                "Persisted %d game log entries for season %d",
                persisted,
                season_id,
            )

    async def _complete_batch(
        self,
        db: DatabaseService,
        batch_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Mark a batch as complete and refresh monitoring views."""
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

        # Refresh materialized views for monitoring
        # Use CONCURRENTLY to avoid blocking reads
        try:
            await db.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_download_batch_stats"
            )
            await db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_source_health")
            await db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_game_summary")
            logger.debug("Refreshed materialized views after batch %d", batch_id)
        except Exception as e:
            # Don't fail the batch if view refresh fails
            logger.warning("Failed to refresh materialized views: %s", e)

        # Trigger auto-validation for relevant sources
        if status == "completed":
            await self._maybe_trigger_auto_validation(db, batch_id)

    async def _maybe_trigger_auto_validation(
        self,
        db: DatabaseService,
        batch_id: int,
    ) -> None:
        """Check if auto-validation should be triggered after batch completion.

        Auto-validation is triggered for game-based sources (boxscore, PBP, shifts)
        when all required data is present for a game.

        Args:
            db: Database service
            batch_id: Completed batch ID
        """
        from nhl_api.viewer.services.auto_validation_service import (
            VALIDATION_AUTO_RUN,
            get_auto_validation_service,
        )

        if not VALIDATION_AUTO_RUN:
            return

        # Get batch info
        batch = await db.fetchrow(
            """
            SELECT source_id, season_id
            FROM import_batches
            WHERE batch_id = $1
            """,
            batch_id,
        )

        if not batch:
            return

        # Only trigger for sources that are part of validation
        validation_source_ids = {2, 3, 16}  # boxscore, pbp, shift_chart
        if batch["source_id"] not in validation_source_ids:
            return

        season_id = batch["season_id"]
        auto_validation = get_auto_validation_service()

        # Get games that now have complete data
        games = await auto_validation.get_games_pending_validation(
            db, season_id, limit=50
        )

        if not games:
            logger.debug("No games pending validation for season %d", season_id)
            return

        logger.info(
            "Queueing auto-validation for %d games in season %d",
            len(games),
            season_id,
        )

        # Ensure worker is running
        await auto_validation.start()

        # Queue each game for validation
        for game_id in games:
            await auto_validation.queue_validation(
                db, game_id, season_id, validator_types=["json_cross_source"]
            )
