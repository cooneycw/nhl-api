"""Pydantic schemas for viewer API responses."""

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
from nhl_api.viewer.schemas.entities import (
    DivisionTeams,
    GameDetail,
    GameListResponse,
    GameSummary,
    PaginationMeta,
    PlayerDetail,
    PlayerListResponse,
    PlayerSummary,
    TeamDetail,
    TeamListResponse,
    TeamSummary,
    TeamWithRoster,
)

__all__ = [
    # Downloads
    "ActiveDownload",
    "ActiveDownloadsResponse",
    "BatchCreated",
    "CancelDownloadResponse",
    "DownloadOptionsResponse",
    "DownloadStartRequest",
    "DownloadStartResponse",
    "SeasonOption",
    "SourceGroup",
    "SourceOption",
    # Entities
    "DivisionTeams",
    "GameDetail",
    "GameListResponse",
    "GameSummary",
    "PaginationMeta",
    "PlayerDetail",
    "PlayerListResponse",
    "PlayerSummary",
    "TeamDetail",
    "TeamListResponse",
    "TeamSummary",
    "TeamWithRoster",
]
