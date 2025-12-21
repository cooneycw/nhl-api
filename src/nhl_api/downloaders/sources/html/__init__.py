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
from nhl_api.downloaders.sources.html.faceoff_comparison import (
    FaceoffComparisonDownloader,
    FaceoffMatchup,
    FaceoffResult,
    ParsedFaceoffComparison,
    PlayerFaceoffSummary,
    TeamFaceoffSummary,
)
from nhl_api.downloaders.sources.html.game_summary import (
    GameSummaryDownloader,
    GoalInfo,
    ParsedGameSummary,
    PenaltyInfo,
    PlayerInfo,
    TeamInfo,
)

__all__ = [
    "BaseHTMLDownloader",
    "FaceoffComparisonDownloader",
    "FaceoffMatchup",
    "FaceoffResult",
    "GameSummaryDownloader",
    "GoalInfo",
    "HTML_DOWNLOADER_CONFIG",
    "HTMLDownloaderConfig",
    "ParsedFaceoffComparison",
    "ParsedGameSummary",
    "PenaltyInfo",
    "PlayerFaceoffSummary",
    "PlayerInfo",
    "TeamFaceoffSummary",
    "TeamInfo",
]
