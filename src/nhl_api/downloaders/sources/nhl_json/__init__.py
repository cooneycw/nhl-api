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
from nhl_api.downloaders.sources.nhl_json.player_landing import (
    DraftDetails,
    GoalieCareerStats,
    GoalieRecentGame,
    GoalieSeasonStats,
    ParsedPlayerLanding,
    PlayerLandingDownloader,
    PlayerLandingDownloaderConfig,
    SkaterCareerStats,
    SkaterRecentGame,
    SkaterSeasonStats,
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
    "DraftDetails",
    "EventPlayer",
    "GameEvent",
    "GoalieCareerStats",
    "GoalieRecentGame",
    "GoalieSeasonStats",
    "NHL_TEAM_ABBREVS",
    "ParsedPlayByPlay",
    "ParsedPlayerLanding",
    "ParsedRoster",
    "ParsedStandings",
    "PlayByPlayDownloader",
    "PlayByPlayDownloaderConfig",
    "PlayerInfo",
    "PlayerLandingDownloader",
    "PlayerLandingDownloaderConfig",
    "RecordSplit",
    "RosterDownloader",
    "ScheduleDownloader",
    "SkaterCareerStats",
    "SkaterRecentGame",
    "SkaterSeasonStats",
    "StandingsDownloader",
    "StreakInfo",
    "TeamStandings",
    "create_play_by_play_downloader",
    "create_roster_downloader",
    "create_standings_downloader",
]
