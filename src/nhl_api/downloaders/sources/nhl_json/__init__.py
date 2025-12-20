"""NHL JSON API downloaders.

This package contains downloaders for the NHL's public JSON API
at api-web.nhle.com/v1/.
"""

from nhl_api.downloaders.sources.nhl_json.boxscore import BoxscoreDownloader
from nhl_api.downloaders.sources.nhl_json.play_by_play import (
    EventPlayer,
    GameEvent,
    ParsedPlayByPlay,
    PlayByPlayDownloader,
    PlayByPlayDownloaderConfig,
    create_play_by_play_downloader,
)
from nhl_api.downloaders.sources.nhl_json.roster import (
    NHL_TEAM_ABBREVS,
    ParsedRoster,
    PlayerInfo,
    RosterDownloader,
    create_roster_downloader,
)
from nhl_api.downloaders.sources.nhl_json.schedule import ScheduleDownloader
from nhl_api.downloaders.sources.nhl_json.standings import (
    ParsedStandings,
    RecordSplit,
    StandingsDownloader,
    StreakInfo,
    TeamStandings,
    create_standings_downloader,
)

__all__ = [
    "BoxscoreDownloader",
    "EventPlayer",
    "GameEvent",
    "NHL_TEAM_ABBREVS",
    "ParsedPlayByPlay",
    "ParsedRoster",
    "ParsedStandings",
    "PlayByPlayDownloader",
    "PlayByPlayDownloaderConfig",
    "PlayerInfo",
    "RecordSplit",
    "RosterDownloader",
    "ScheduleDownloader",
    "StandingsDownloader",
    "StreakInfo",
    "TeamStandings",
    "create_play_by_play_downloader",
    "create_roster_downloader",
    "create_standings_downloader",
]
