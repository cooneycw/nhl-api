"""DailyFaceoff downloaders for NHL team lineup data.

This package provides downloaders for extracting lineup and roster
information from DailyFaceoff.com.

Available downloaders:
- BaseDailyFaceoffDownloader: Base class for all DailyFaceoff downloaders
- PenaltyKillDownloader: Penalty kill unit configurations (PK1, PK2)
- PowerPlayDownloader: Download power play unit configurations (PP1, PP2)
- InjuryDownloader: Injury tracking (team and league-wide)

Example usage:
    from nhl_api.downloaders.sources.dailyfaceoff import (
        PenaltyKillDownloader,
        PowerPlayDownloader,
        InjuryDownloader,
        DailyFaceoffConfig,
    )

    config = DailyFaceoffConfig()
    async with PenaltyKillDownloader(config) as downloader:
        result = await downloader.download_team(10)  # Toronto

    async with PowerPlayDownloader() as downloader:
        result = await downloader.download_team(6)  # Boston Bruins
        print(result.data["pp1"])

    async with InjuryDownloader(config) as downloader:
        result = await downloader.download_team(10)  # Toronto team injuries
        league = await downloader.download_league_injuries()  # All injuries
"""

from nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader import (
    DAILYFACEOFF_CONFIG,
    BaseDailyFaceoffDownloader,
    DailyFaceoffConfig,
)
from nhl_api.downloaders.sources.dailyfaceoff.injuries import (
    InjuryDownloader,
    InjuryRecord,
    InjuryStatus,
    TeamInjuries,
)
from nhl_api.downloaders.sources.dailyfaceoff.penalty_kill import (
    PenaltyKillDownloader,
    PenaltyKillUnit,
    PKPlayer,
    TeamPenaltyKill,
)
from nhl_api.downloaders.sources.dailyfaceoff.power_play import (
    PowerPlayDownloader,
    PowerPlayPlayer,
    PowerPlayUnit,
    TeamPowerPlay,
)
from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import (
    TEAM_ABBREVIATIONS,
    TEAM_SLUGS,
    get_team_abbreviation,
    get_team_slug,
)

__all__ = [
    # Base
    "BaseDailyFaceoffDownloader",
    "DAILYFACEOFF_CONFIG",
    "DailyFaceoffConfig",
    # Injuries
    "InjuryDownloader",
    "InjuryRecord",
    "InjuryStatus",
    "TeamInjuries",
    # Penalty Kill
    "PenaltyKillDownloader",
    "PenaltyKillUnit",
    "PKPlayer",
    "TeamPenaltyKill",
    # Power Play
    "PowerPlayDownloader",
    "PowerPlayPlayer",
    "PowerPlayUnit",
    "TeamPowerPlay",
    # Team Mapping
    "TEAM_SLUGS",
    "TEAM_ABBREVIATIONS",
    "get_team_slug",
    "get_team_abbreviation",
]
