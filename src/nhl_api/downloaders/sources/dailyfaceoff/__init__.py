"""DailyFaceoff downloaders for NHL team lineup data.

This package provides downloaders for extracting lineup and roster
information from DailyFaceoff.com.

Available downloaders:
- BaseDailyFaceoffDownloader: Base class for all DailyFaceoff downloaders

Example usage:
    from nhl_api.downloaders.sources.dailyfaceoff import (
        BaseDailyFaceoffDownloader,
        DailyFaceoffConfig,
        TEAM_SLUGS,
    )
"""

from nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader import (
    DAILYFACEOFF_CONFIG,
    BaseDailyFaceoffDownloader,
    DailyFaceoffConfig,
)
from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import (
    TEAM_ABBREVIATIONS,
    TEAM_SLUGS,
    get_team_abbreviation,
    get_team_slug,
)

__all__ = [
    "BaseDailyFaceoffDownloader",
    "DAILYFACEOFF_CONFIG",
    "DailyFaceoffConfig",
    "TEAM_SLUGS",
    "TEAM_ABBREVIATIONS",
    "get_team_slug",
    "get_team_abbreviation",
]
