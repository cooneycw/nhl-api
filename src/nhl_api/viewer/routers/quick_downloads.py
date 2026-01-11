"""Quick Download endpoints for simplified download interface.

Provides 5 simplified download actions:
- Pre-season: Download current season pre-season games
- Regular: Download current season regular games
- Playoffs: Download current season playoffs
- External: Refresh DailyFaceoff + QuantHockey data
- Prior Season: Download a selected historical season
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db
from nhl_api.viewer.routers.downloads import SOURCE_DISPLAY_NAMES
from nhl_api.viewer.schemas.quick_downloads import (
    PriorSeasonRequest,
    QuickDownloadResponse,
    SyncStatusItem,
    SyncStatusResponse,
)
from nhl_api.viewer.services.download_service import DownloadService

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(prefix="/downloads/quick", tags=["quick-downloads"])

# Game type constants
GAME_TYPE_PRESEASON = 1
GAME_TYPE_REGULAR = 2
GAME_TYPE_PLAYOFFS = 3
GAME_TYPE_EXTERNAL = 0  # For external sources (no game type filtering)

# Game type display labels
GAME_TYPE_LABELS = {
    0: "External",
    1: "Pre-season",
    2: "Regular Season",
    3: "Playoffs",
}

# Core NHL JSON sources for game-based downloads
CORE_NHL_SOURCES = [
    "nhl_schedule",
    "nhl_boxscore",
    "nhl_pbp",
]

# HTML report sources
HTML_REPORT_SOURCES = [
    "html_gs",
    "html_es",
    "html_pl",
    "html_fs",
    "html_fc",
    "html_ro",
    "html_ss",
    "html_th",
    "html_tv",
]

# Shift chart source
SHIFT_CHART_SOURCES = ["shift_chart"]

# External sources
EXTERNAL_SOURCES = [
    "dailyfaceoff_lines",
    "dailyfaceoff_power_play",
    "dailyfaceoff_penalty_kill",
    "dailyfaceoff_injuries",
    "dailyfaceoff_starting_goalies",
    "quanthockey_player_stats",
]

# All game-based sources for season downloads
ALL_GAME_SOURCES = CORE_NHL_SOURCES + HTML_REPORT_SOURCES + SHIFT_CHART_SOURCES


async def _get_current_season(db: DatabaseService) -> tuple[int, str]:
    """Get current season ID and label.

    Returns:
        Tuple of (season_id, season_label)

    Raises:
        HTTPException: If no current season is configured
    """
    row = await db.fetchrow(
        """
        SELECT season_id, start_year, end_year
        FROM seasons
        WHERE is_current = TRUE
        LIMIT 1
        """
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No current season configured in database",
        )
    return row["season_id"], f"{row['start_year']}-{row['end_year']}"


async def _start_downloads(
    db: DatabaseService,
    sources: list[str],
    season_id: int,
    game_types: list[int],
    action_name: str,
) -> list[int]:
    """Start download batches for given sources.

    Schedule downloads run first to ensure game records exist before
    other game-based downloads attempt to persist their data.

    Args:
        db: Database service
        sources: List of source names to download
        season_id: Season ID to download
        game_types: Game types to filter (1=pre, 2=regular, 3=playoffs)
        action_name: Name of the quick action for logging

    Returns:
        List of batch IDs that were started
    """
    service = DownloadService.get_instance()
    batch_ids: list[int] = []

    # Run schedule first if present - other sources depend on game records existing
    if "nhl_schedule" in sources:
        try:
            schedule_batch_id = await service.start_download(
                db=db,
                source_name="nhl_schedule",
                season_id=season_id,
                game_types=game_types,
                force=False,
            )
            batch_ids.append(schedule_batch_id)

            # Wait for schedule to complete before starting dependent downloads
            schedule_task = service._active_downloads.get(schedule_batch_id)
            if schedule_task:
                await schedule_task.task
        except ValueError:
            # Schedule already running or can't be started
            pass

    # Start remaining sources in parallel
    remaining_sources = [s for s in sources if s != "nhl_schedule"]
    for source_name in remaining_sources:
        try:
            batch_id = await service.start_download(
                db=db,
                source_name=source_name,
                season_id=season_id,
                game_types=game_types,
                force=False,  # Use delta sync by default
            )
            batch_ids.append(batch_id)
        except ValueError:
            # Skip sources that can't be started (already running, etc.)
            continue

    return batch_ids


@router.get(
    "/sync-status",
    response_model=SyncStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Sync Status",
    description="Get last sync timestamps for current season sources",
)
async def get_sync_status(db: DbDep) -> SyncStatusResponse:
    """Get sync status for current season.

    Returns last sync times for all sources to display in UI.
    """
    season_id, season_label = await _get_current_season(db)

    # Get all sync timestamps for current season
    rows = await db.fetch(
        """
        SELECT
            ds.name AS source_name,
            sst.game_type,
            sst.last_synced_at,
            sst.items_synced_count
        FROM data_sources ds
        LEFT JOIN source_sync_timestamps sst
            ON ds.source_id = sst.source_id
            AND sst.season_id = $1
        WHERE ds.is_active = TRUE
        ORDER BY ds.source_type, ds.source_id, sst.game_type
        """,
        season_id,
    )

    # Build sync status items
    items: list[SyncStatusItem] = []
    now = datetime.now(UTC)
    stale_threshold = now - timedelta(hours=24)

    for row in rows:
        source_name = row["source_name"]
        game_type = row["game_type"] if row["game_type"] is not None else 0
        last_synced = row["last_synced_at"]
        items_count = row["items_synced_count"] or 0

        # Determine if stale (never synced or >24h old)
        is_stale = last_synced is None or last_synced < stale_threshold

        items.append(
            SyncStatusItem(
                source_name=source_name,
                source_display_name=SOURCE_DISPLAY_NAMES.get(source_name, source_name),
                game_type=game_type,
                game_type_label=GAME_TYPE_LABELS.get(game_type, "Unknown"),
                last_synced_at=last_synced,
                items_synced_count=items_count,
                is_stale=is_stale,
            )
        )

    return SyncStatusResponse(
        season_id=season_id,
        season_label=season_label,
        items=items,
    )


@router.post(
    "/preseason",
    response_model=QuickDownloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Download Pre-season",
    description="Download all pre-season data for current season",
)
async def download_preseason(db: DbDep) -> QuickDownloadResponse:
    """Download current season pre-season games.

    Starts downloads for all game-based sources filtered to pre-season games.
    Uses delta sync to only fetch games completed since last sync.
    """
    season_id, season_label = await _get_current_season(db)
    game_types = [GAME_TYPE_PRESEASON]

    batch_ids = await _start_downloads(
        db, ALL_GAME_SOURCES, season_id, game_types, "preseason"
    )

    return QuickDownloadResponse(
        action="preseason",
        season_id=season_id,
        season_label=season_label,
        batches_started=len(batch_ids),
        message=f"Started {len(batch_ids)} pre-season download batches",
        batch_ids=batch_ids,
    )


@router.post(
    "/regular",
    response_model=QuickDownloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Download Regular Season",
    description="Download all regular season data for current season",
)
async def download_regular(db: DbDep) -> QuickDownloadResponse:
    """Download current season regular season games.

    Starts downloads for all game-based sources filtered to regular season.
    Uses delta sync to only fetch games completed since last sync.
    """
    season_id, season_label = await _get_current_season(db)
    game_types = [GAME_TYPE_REGULAR]

    batch_ids = await _start_downloads(
        db, ALL_GAME_SOURCES, season_id, game_types, "regular"
    )

    return QuickDownloadResponse(
        action="regular",
        season_id=season_id,
        season_label=season_label,
        batches_started=len(batch_ids),
        message=f"Started {len(batch_ids)} regular season download batches",
        batch_ids=batch_ids,
    )


@router.post(
    "/playoffs",
    response_model=QuickDownloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Download Playoffs",
    description="Download all playoff data for current season",
)
async def download_playoffs(db: DbDep) -> QuickDownloadResponse:
    """Download current season playoff games.

    Starts downloads for all game-based sources filtered to playoffs.
    Uses delta sync to only fetch games completed since last sync.
    """
    season_id, season_label = await _get_current_season(db)
    game_types = [GAME_TYPE_PLAYOFFS]

    batch_ids = await _start_downloads(
        db, ALL_GAME_SOURCES, season_id, game_types, "playoffs"
    )

    return QuickDownloadResponse(
        action="playoffs",
        season_id=season_id,
        season_label=season_label,
        batches_started=len(batch_ids),
        message=f"Started {len(batch_ids)} playoff download batches",
        batch_ids=batch_ids,
    )


@router.post(
    "/external",
    response_model=QuickDownloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Update External Sources",
    description="Refresh DailyFaceoff and QuantHockey data",
)
async def download_external(db: DbDep) -> QuickDownloadResponse:
    """Refresh external data sources.

    Starts downloads for DailyFaceoff and QuantHockey sources.
    These are full refreshes (not delta synced) as they provide
    point-in-time snapshots rather than game-based data.
    """
    season_id, season_label = await _get_current_season(db)
    game_types = [GAME_TYPE_EXTERNAL]  # External sources don't filter by game type

    batch_ids = await _start_downloads(
        db, EXTERNAL_SOURCES, season_id, game_types, "external"
    )

    return QuickDownloadResponse(
        action="external",
        season_id=season_id,
        season_label=season_label,
        batches_started=len(batch_ids),
        message=f"Started {len(batch_ids)} external source download batches",
        batch_ids=batch_ids,
    )


@router.post(
    "/prior-season/{season_id}",
    response_model=QuickDownloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Download Prior Season",
    description="Download full prior season (all game types)",
)
async def download_prior_season(
    db: DbDep,
    season_id: Annotated[
        int, Path(description="Season ID to download (e.g., 20232024)")
    ],
    request: PriorSeasonRequest | None = None,
) -> QuickDownloadResponse:
    """Download a full prior season.

    Downloads all game types (pre-season, regular, playoffs) for the
    specified season. Optionally filter to specific game types via request body.
    """
    # Validate season exists
    row = await db.fetchrow(
        """
        SELECT season_id, start_year, end_year, is_current
        FROM seasons
        WHERE season_id = $1
        """,
        season_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Season {season_id} not found",
        )

    season_label = f"{row['start_year']}-{row['end_year']}"
    game_types = request.game_types if request else [1, 2, 3]

    batch_ids = await _start_downloads(
        db, ALL_GAME_SOURCES, season_id, game_types, "prior_season"
    )

    return QuickDownloadResponse(
        action="prior_season",
        season_id=season_id,
        season_label=season_label,
        batches_started=len(batch_ids),
        message=f"Started {len(batch_ids)} prior season download batches for {season_label}",
        batch_ids=batch_ids,
    )


@router.get(
    "/seasons",
    status_code=status.HTTP_200_OK,
    summary="List Available Seasons",
    description="Get list of seasons available for prior season download",
)
async def list_seasons(db: DbDep) -> list[dict[str, int | str]]:
    """List available seasons for prior season download.

    Returns all non-current seasons in descending order.
    """
    rows = await db.fetch(
        """
        SELECT season_id, start_year, end_year, is_current
        FROM seasons
        WHERE is_current = FALSE
        ORDER BY season_id DESC
        """
    )

    return [
        {
            "season_id": row["season_id"],
            "start_year": row["start_year"],
            "end_year": row["end_year"],
            "label": f"{row['start_year']}-{row['end_year']}",
        }
        for row in rows
    ]
