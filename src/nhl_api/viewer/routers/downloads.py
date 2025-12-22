"""Download management endpoints.

Provides endpoints for:
- Listing available download options (seasons, sources)
- Triggering new downloads
- Viewing active downloads with progress
- Cancelling running downloads
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.dependencies import get_db
from nhl_api.viewer.schemas.downloads import (
    ActiveDownload,
    ActiveDownloadsResponse,
    BatchCreated,
    CancelDownloadResponse,
    DownloadOptionsResponse,
    DownloadStartRequest,
    DownloadStartResponse,
    SeasonOption,
    SourceGroup,
    SourceOption,
)
from nhl_api.viewer.services.download_service import DownloadService

# Type alias for dependency injection
DbDep = Annotated[DatabaseService, Depends(get_db)]

router = APIRouter(prefix="/downloads", tags=["downloads"])


# Human-friendly display names for source types
SOURCE_TYPE_DISPLAY = {
    "nhl_json": "NHL JSON API",
    "html_report": "HTML Game Reports",
    "shift_chart": "Shift Charts",
    "quanthockey": "QuantHockey",
    "dailyfaceoff": "DailyFaceoff",
}

# Human-friendly display names for individual sources
SOURCE_DISPLAY_NAMES = {
    "nhl_schedule": "Schedule",
    "nhl_boxscore": "Boxscores",
    "nhl_pbp": "Play-by-Play",
    "nhl_roster": "Rosters",
    "nhl_standings": "Standings",
    "nhl_player": "Player Profiles",
    # HTML sources
    "html_gs": "Game Summary (GS)",
    "html_es": "Event Summary (ES)",
    "html_pl": "Play-by-Play (PL)",
    "html_fs": "Faceoff Summary (FS)",
    "html_fc": "Faceoff Comparison (FC)",
    "html_ro": "Roster Report (RO)",
    "html_ss": "Shot Summary (SS)",
    "html_th": "Time on Ice - Home (TH)",
    "html_tv": "Time on Ice - Visitor (TV)",
    # DailyFaceoff sources
    "dailyfaceoff_lines": "Line Combinations",
    "dailyfaceoff_power_play": "Power Play Units",
    "dailyfaceoff_penalty_kill": "Penalty Kill Units",
    "dailyfaceoff_injuries": "Injuries",
    "dailyfaceoff_starting_goalies": "Starting Goalies",
}


@router.get(
    "/options",
    response_model=DownloadOptionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Download Options",
    description="Get available seasons and data sources for download selection",
)
async def get_download_options(db: DbDep) -> DownloadOptionsResponse:
    """Get available seasons and sources for download selection.

    Returns seasons and sources grouped by type for UI checkbox display.
    """
    # Query seasons from database
    season_rows = await db.fetch(
        """
        SELECT season_id, start_year, end_year, is_current
        FROM seasons
        ORDER BY season_id DESC
        """
    )

    seasons = [
        SeasonOption(
            season_id=row["season_id"],
            start_year=row["start_year"],
            end_year=row["end_year"],
            is_current=row["is_current"],
            label=f"{row['start_year']}-{row['end_year']}",
        )
        for row in season_rows
    ]

    # Query active data sources grouped by type
    source_rows = await db.fetch(
        """
        SELECT source_id, name, source_type, description, is_active
        FROM data_sources
        WHERE is_active = TRUE
        ORDER BY source_type, source_id
        """
    )

    # Group sources by type
    groups_map: dict[str, list[SourceOption]] = {}
    for row in source_rows:
        source_type = row["source_type"]
        if source_type not in groups_map:
            groups_map[source_type] = []

        groups_map[source_type].append(
            SourceOption(
                source_id=row["source_id"],
                name=row["name"],
                source_type=source_type,
                description=row["description"],
                display_name=SOURCE_DISPLAY_NAMES.get(row["name"], row["name"]),
                is_active=row["is_active"],
            )
        )

    # Convert to list of groups
    source_groups = [
        SourceGroup(
            source_type=source_type,
            display_name=SOURCE_TYPE_DISPLAY.get(source_type, source_type),
            sources=sources,
        )
        for source_type, sources in groups_map.items()
    ]

    return DownloadOptionsResponse(
        seasons=seasons,
        source_groups=source_groups,
    )


@router.post(
    "/start",
    response_model=DownloadStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Download",
    description="Trigger download for selected seasons and sources",
)
async def start_download(
    request: DownloadStartRequest,
    db: DbDep,
) -> DownloadStartResponse:
    """Start async downloads for selected seasons and sources.

    Creates a batch for each season/source combination and starts
    background tasks to perform the downloads.
    """
    if not request.season_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one season must be selected",
        )

    if not request.source_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one source must be selected",
        )

    service = DownloadService.get_instance()
    batches: list[BatchCreated] = []

    for source_name in request.source_names:
        for season_id in request.season_ids:
            try:
                batch_id = await service.start_download(
                    db=db,
                    source_name=source_name,
                    season_id=season_id,
                    game_types=request.game_types,
                    force=request.force,
                )
                batches.append(
                    BatchCreated(
                        batch_id=batch_id,
                        source_name=source_name,
                        season_id=season_id,
                    )
                )
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                ) from e

    return DownloadStartResponse(
        batches=batches,
        message=f"Started {len(batches)} download batch(es)",
    )


@router.get(
    "/active",
    response_model=ActiveDownloadsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Active Downloads",
    description="Get currently running downloads with progress",
)
async def get_active_downloads(db: DbDep) -> ActiveDownloadsResponse:
    """Get list of currently running downloads with progress.

    Progress includes items_total, items_completed, and progress_percent.
    """
    service = DownloadService.get_instance()
    active = service.get_active_downloads()

    # Enrich with season labels
    downloads = []
    for dl in active:
        # Get season label
        season_row = await db.fetchrow(
            "SELECT start_year, end_year FROM seasons WHERE season_id = $1",
            dl["season_id"],
        )
        season_label = (
            f"{season_row['start_year']}-{season_row['end_year']}"
            if season_row
            else str(dl["season_id"])
        )

        downloads.append(
            ActiveDownload(
                batch_id=dl["batch_id"],
                source_id=dl["source_id"],
                source_name=dl["source_name"],
                source_type=dl["source_type"],
                season_id=dl["season_id"],
                season_label=season_label,
                started_at=dl["started_at"],
                items_total=dl["items_total"],
                items_completed=dl["items_completed"],
                items_failed=dl["items_failed"],
                progress_percent=dl["progress_percent"],
            )
        )

    return ActiveDownloadsResponse(
        downloads=downloads,
        count=len(downloads),
    )


@router.post(
    "/{batch_id}/cancel",
    response_model=CancelDownloadResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Download",
    description="Cancel a running download batch",
)
async def cancel_download(batch_id: int, db: DbDep) -> CancelDownloadResponse:
    """Cancel a running download.

    Sets cancel flag and updates batch status to 'cancelled'.
    """
    service = DownloadService.get_instance()
    cancelled = await service.cancel_download(db, batch_id)

    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active download with batch_id {batch_id} not found",
        )

    return CancelDownloadResponse(
        batch_id=batch_id,
        cancelled=True,
        message=f"Download batch {batch_id} has been cancelled",
    )
