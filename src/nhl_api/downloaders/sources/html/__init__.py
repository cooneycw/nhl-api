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

__all__ = [
    "BaseHTMLDownloader",
    "EventPlayer",
    "EventSummaryDownloader",
    "FaceoffStat",
    "FaceoffSummaryDownloader",
    "GameSummaryDownloader",
    "GoalieStats",
    "GoalInfo",
    "HTML_DOWNLOADER_CONFIG",
    "HTMLDownloaderConfig",
    "ParsedEventSummary",
    "ParsedFaceoffSummary",
    "ParsedGameSummary",
    "ParsedPlayByPlay",
    "PenaltyInfo",
    "PeriodFaceoffs",
    "PlayByPlayDownloader",
    "PlayByPlayEvent",
    "PlayerFaceoffStats",
    "PlayerInfo",
    "PlayerOnIce",
    "PlayerStats",
    "StrengthFaceoffs",
    "TeamEventSummary",
    "TeamFaceoffSummary",
    "TeamInfo",
    "ZoneFaceoffs",
]
