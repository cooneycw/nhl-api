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
    "GameSummaryDownloader",
    "GoalInfo",
    "HTML_DOWNLOADER_CONFIG",
    "HTMLDownloaderConfig",
    "ParsedGameSummary",
    "ParsedPlayByPlay",
    "PenaltyInfo",
    "PlayByPlayDownloader",
    "PlayByPlayEvent",
    "PlayerInfo",
    "PlayerOnIce",
    "TeamInfo",
]
