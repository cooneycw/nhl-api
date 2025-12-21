"""NHL HTML Report downloaders.

This package contains downloaders for NHL HTML game reports
from www.nhl.com/scores/htmlreports.

Report Types:
- GS: Game Summary
- ES: Event Summary
- PL: Play-by-Play
- FS: Faceoff Summary
- FC: Faceoff Comparison
- RO: Roster Report
- SS: Shot Summary
- TH: Home Time on Ice
- TV: Visitor Time on Ice
"""

from nhl_api.downloaders.sources.html.base_html_downloader import (
    HTML_DOWNLOADER_CONFIG,
    BaseHTMLDownloader,
    HTMLDownloaderConfig,
)
from nhl_api.downloaders.sources.html.event_summary import (
    EventSummaryDownloader,
    GoalieStats,
    ParsedEventSummary,
    PlayerStats,
    TeamEventSummary,
)
from nhl_api.downloaders.sources.html.faceoff_comparison import (
    FaceoffComparisonDownloader,
    FaceoffMatchup,
    FaceoffResult,
    ParsedFaceoffComparison,
    PlayerFaceoffSummary,
)
from nhl_api.downloaders.sources.html.faceoff_comparison import (
    TeamFaceoffSummary as FCTeamFaceoffSummary,
)
from nhl_api.downloaders.sources.html.faceoff_summary import (
    FaceoffStat,
    FaceoffSummaryDownloader,
    ParsedFaceoffSummary,
    PeriodFaceoffs,
    PlayerFaceoffStats,
    StrengthFaceoffs,
    TeamFaceoffSummary,
    ZoneFaceoffs,
)
from nhl_api.downloaders.sources.html.game_summary import (
    GameSummaryDownloader,
    GoalInfo,
    ParsedGameSummary,
    PenaltyInfo,
    PlayerInfo,
    TeamInfo,
)
from nhl_api.downloaders.sources.html.play_by_play import (
    EventPlayer,
    ParsedPlayByPlay,
    PlayByPlayDownloader,
    PlayByPlayEvent,
    PlayerOnIce,
)
from nhl_api.downloaders.sources.html.roster import (
    CoachInfo,
    OfficialInfo,
    ParsedRoster,
    PlayerRoster,
    RosterDownloader,
    TeamRoster,
)
from nhl_api.downloaders.sources.html.shot_summary import (
    ParsedShotSummary,
    PeriodSituationStats,
    PlayerShotSummary,
    ShotSummaryDownloader,
    SituationStats,
    TeamShotSummary,
)

__all__ = [
    "BaseHTMLDownloader",
    "CoachInfo",
    "EventPlayer",
    "EventSummaryDownloader",
    "FaceoffComparisonDownloader",
    "FaceoffMatchup",
    "FaceoffResult",
    "FaceoffStat",
    "FaceoffSummaryDownloader",
    "FCTeamFaceoffSummary",
    "GameSummaryDownloader",
    "GoalieStats",
    "GoalInfo",
    "HTML_DOWNLOADER_CONFIG",
    "HTMLDownloaderConfig",
    "OfficialInfo",
    "ParsedEventSummary",
    "ParsedFaceoffComparison",
    "ParsedFaceoffSummary",
    "ParsedGameSummary",
    "ParsedPlayByPlay",
    "ParsedRoster",
    "ParsedShotSummary",
    "PenaltyInfo",
    "PeriodFaceoffs",
    "PeriodSituationStats",
    "PlayByPlayDownloader",
    "PlayByPlayEvent",
    "PlayerFaceoffStats",
    "PlayerFaceoffSummary",
    "PlayerInfo",
    "PlayerOnIce",
    "PlayerRoster",
    "PlayerShotSummary",
    "PlayerStats",
    "RosterDownloader",
    "ShotSummaryDownloader",
    "SituationStats",
    "StrengthFaceoffs",
    "TeamEventSummary",
    "TeamFaceoffSummary",
    "TeamInfo",
    "TeamRoster",
    "TeamShotSummary",
    "ZoneFaceoffs",
]
