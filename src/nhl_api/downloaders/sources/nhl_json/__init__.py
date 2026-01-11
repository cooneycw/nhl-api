"""NHL JSON API downloaders.

This package contains downloaders for the NHL's public JSON API
at api-web.nhle.com/v1/.
"""

from nhl_api.downloaders.sources.nhl_json.boxscore import BoxscoreDownloader
from nhl_api.downloaders.sources.nhl_json.gamecenter_landing import (
    GamecenterLandingDownloader,
    GamecenterLandingDownloaderConfig,
    GameHighlight,
    ParsedGamecenterLanding,
    TeamMatchup,
    ThreeStar,
    create_gamecenter_landing_downloader,
)
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
from nhl_api.downloaders.sources.nhl_json.right_rail import (
    BroadcastInfo,
    LastGame,
    ParsedRightRail,
    RightRailDownloader,
    RightRailDownloaderConfig,
    TeamSeasonSeries,
    create_right_rail_downloader,
)
from nhl_api.downloaders.sources.nhl_json.roster import (
    ALL_TEAM_ABBREVS,
    CURRENT_TEAM_ABBREVS,
    NHL_TEAM_ABBREVS,
    TEAM_RELOCATIONS,
    ParsedRoster,
    PlayerInfo,
    RosterDownloader,
    create_roster_downloader,
    get_teams_for_season,
    resolve_team_abbrev,
)
from nhl_api.downloaders.sources.nhl_json.schedule import ScheduleDownloader
from nhl_api.downloaders.sources.nhl_json.season_info import (
    SeasonInfo,
    SeasonInfoDownloader,
    SeasonInfoDownloaderConfig,
    create_season_info_downloader,
)
from nhl_api.downloaders.sources.nhl_json.standings import (
    ParsedStandings,
    RecordSplit,
    StandingsDownloader,
    StreakInfo,
    TeamStandings,
    create_standings_downloader,
)
from nhl_api.downloaders.sources.nhl_json.team_prospects import (
    ParsedTeamProspects,
    ProspectInfo,
    TeamProspectsDownloader,
    TeamProspectsDownloaderConfig,
    create_team_prospects_downloader,
)

__all__ = [
    # Constants
    "ALL_TEAM_ABBREVS",
    "CURRENT_TEAM_ABBREVS",
    "NHL_TEAM_ABBREVS",
    "PLAYOFFS",
    "REGULAR_SEASON",
    "TEAM_RELOCATIONS",
    # Boxscore
    "BoxscoreDownloader",
    # Gamecenter Landing
    "GamecenterLandingDownloader",
    "GamecenterLandingDownloaderConfig",
    "GameHighlight",
    "ParsedGamecenterLanding",
    "TeamMatchup",
    "ThreeStar",
    "create_gamecenter_landing_downloader",
    # Play-by-Play
    "DraftDetails",
    "EventPlayer",
    "GameEvent",
    "ParsedPlayByPlay",
    "PlayByPlayDownloader",
    "PlayByPlayDownloaderConfig",
    "create_play_by_play_downloader",
    # Player Game Log
    "GoalieGameStats",
    "ParsedPlayerGameLog",
    "PlayerGameLogDownloader",
    "PlayerGameLogDownloaderConfig",
    "SkaterGameStats",
    "create_player_game_log_downloader",
    # Player Landing
    "GoalieCareerStats",
    "GoalieRecentGame",
    "GoalieSeasonStats",
    "ParsedPlayerLanding",
    "PlayerLandingDownloader",
    "PlayerLandingDownloaderConfig",
    "SkaterCareerStats",
    "SkaterRecentGame",
    "SkaterSeasonStats",
    # Right Rail
    "BroadcastInfo",
    "LastGame",
    "ParsedRightRail",
    "RightRailDownloader",
    "RightRailDownloaderConfig",
    "TeamSeasonSeries",
    "create_right_rail_downloader",
    # Roster
    "ParsedRoster",
    "PlayerInfo",
    "RosterDownloader",
    "create_roster_downloader",
    "get_teams_for_season",
    "resolve_team_abbrev",
    # Schedule
    "ScheduleDownloader",
    # Season Info
    "SeasonInfo",
    "SeasonInfoDownloader",
    "SeasonInfoDownloaderConfig",
    "create_season_info_downloader",
    # Standings
    "ParsedStandings",
    "RecordSplit",
    "StandingsDownloader",
    "StreakInfo",
    "TeamStandings",
    "create_standings_downloader",
    # Team Prospects
    "ParsedTeamProspects",
    "ProspectInfo",
    "TeamProspectsDownloader",
    "TeamProspectsDownloaderConfig",
    "create_team_prospects_downloader",
]
