"""DailyFaceoff downloaders for NHL team lineup data.

This package provides downloaders for extracting lineup and roster
information from DailyFaceoff.com.

Available downloaders:
- BaseDailyFaceoffDownloader: Base class for all DailyFaceoff downloaders
- LineCombinationsDownloader: Line combinations (forward lines, defensive pairs, goalies)
- PenaltyKillDownloader: Penalty kill unit configurations (PK1, PK2)
- PowerPlayDownloader: Download power play unit configurations (PP1, PP2)

Example usage:
    from nhl_api.downloaders.sources.dailyfaceoff import (
        LineCombinationsDownloader,
        PenaltyKillDownloader,
        PowerPlayDownloader,
        DailyFaceoffConfig,
    )

    async with LineCombinationsDownloader() as downloader:
        result = await downloader.download_team(6)  # Boston Bruins
        print(result.data["forward_lines"])
"""

from nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader import (
    DAILYFACEOFF_CONFIG,
    BaseDailyFaceoffDownloader,
    DailyFaceoffConfig,
)
from nhl_api.downloaders.sources.dailyfaceoff.line_combinations import (
    DefensivePair,
    ForwardLine,
    GoalieDepth,
    LineCombinationsDownloader,
    PlayerInfo,
    TeamLineup,
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
    # Line Combinations
    "LineCombinationsDownloader",
    "ForwardLine",
    "DefensivePair",
    "GoalieDepth",
    "PlayerInfo",
    "TeamLineup",
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
