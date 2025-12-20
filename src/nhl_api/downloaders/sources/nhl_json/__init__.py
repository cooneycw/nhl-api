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
from nhl_api.downloaders.sources.nhl_json.player_game_log import (
    PLAYOFFS,
    REGULAR_SEASON,
    GoalieGameStats,
    ParsedPlayerGameLog,
    PlayerGameLogDownloader,
    PlayerGameLogDownloaderConfig,
    SkaterGameStats,
    create_player_game_log_downloader,
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
    "GoalieGameStats",
    "GoalieRecentGame",
    "GoalieSeasonStats",
    "NHL_TEAM_ABBREVS",
    "PLAYOFFS",
    "ParsedPlayByPlay",
    "ParsedPlayerGameLog",
    "ParsedPlayerLanding",
    "ParsedRoster",
    "ParsedStandings",
    "PlayByPlayDownloader",
    "PlayByPlayDownloaderConfig",
    "PlayerGameLogDownloader",
    "PlayerGameLogDownloaderConfig",
    "PlayerInfo",
    "PlayerLandingDownloader",
    "PlayerLandingDownloaderConfig",
    "REGULAR_SEASON",
    "RecordSplit",
    "RosterDownloader",
    "ScheduleDownloader",
    "SkaterCareerStats",
    "SkaterGameStats",
    "SkaterRecentGame",
    "SkaterSeasonStats",
    "StandingsDownloader",
    "StreakInfo",
    "TeamStandings",
    "create_play_by_play_downloader",
    "create_player_game_log_downloader",
    "create_roster_downloader",
    "create_standings_downloader",
]
