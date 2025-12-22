"""Source registry for data flow testing.

Provides centralized definitions of all testable data sources
with their metadata, downloader classes, and target tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# Base URLs for different API sources
NHL_API_BASE_URL = "https://api-web.nhle.com"
NHL_API_BASE_URL_V1 = "https://api-web.nhle.com/v1"
NHL_STATS_API_BASE_URL = "https://api.nhle.com/stats/rest/en"


class SourceType(Enum):
    """Type of data source based on how it's accessed."""

    GAME = "game"  # Requires game_id
    SEASON = "season"  # Season-level data
    TEAM = "team"  # Team-based data
    PLAYER = "player"  # Player-based data
    DATE = "date"  # Date-based data


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    """Definition of a testable data source.

    Attributes:
        name: Unique identifier for the source (e.g., "nhl_json_boxscore")
        display_name: Human-readable name for reports
        downloader_class: Fully qualified class name for lazy loading
        config_class: Fully qualified config class name
        source_type: Type of source (game, season, team, etc.)
        has_persist: Whether the downloader has a persist() method
        target_tables: Database tables populated by this source
        requires_game_id: Whether download_game() requires a game ID
        default_base_url: Default base URL for this source
    """

    name: str
    display_name: str
    downloader_class: str
    config_class: str
    source_type: SourceType
    has_persist: bool
    target_tables: tuple[str, ...] = field(default_factory=tuple)
    requires_game_id: bool = True
    default_base_url: str | None = None

    def get_downloader_class(self) -> type[Any]:
        """Lazily load and return the downloader class."""
        module_path, class_name = self.downloader_class.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, class_name)  # type: ignore[no-any-return]

    def get_config_class(self) -> type[Any]:
        """Lazily load and return the config class."""
        module_path, class_name = self.config_class.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, class_name)  # type: ignore[no-any-return]

    def create_downloader(self, **config_overrides: Any) -> Any:
        """Create a downloader instance with optional config overrides.

        Args:
            **config_overrides: Override default config values

        Returns:
            Configured downloader instance
        """
        config_cls = self.get_config_class()
        downloader_cls = self.get_downloader_class()

        # For base DownloaderConfig, we need to provide base_url
        # Config classes that inherit with defaults don't need this
        if self.default_base_url and "base_url" not in config_overrides:
            # Check if config class requires base_url (base class does)
            import inspect

            sig = inspect.signature(config_cls)
            if "base_url" in sig.parameters:
                param = sig.parameters["base_url"]
                if param.default is inspect.Parameter.empty:
                    config_overrides["base_url"] = self.default_base_url

        # Create config with any overrides
        config = config_cls(**config_overrides) if config_overrides else config_cls()

        return downloader_cls(config)


class SourceRegistry:
    """Registry of all data sources available for testing.

    Sources are organized by category:
    - GAME_SOURCES: Sources that download per-game data (with persist)
    - SEASON_SOURCES: Sources that download season-level data (with persist)
    - HTML_SOURCES: HTML report sources (parse-only, no persist)
    - EXTERNAL_SOURCES: Third-party sources (DailyFaceoff, QuantHockey)
    """

    # NHL JSON API sources with persist methods
    GAME_SOURCES: dict[str, SourceDefinition] = {
        "nhl_json_schedule": SourceDefinition(
            name="nhl_json_schedule",
            display_name="Schedule",
            downloader_class="nhl_api.downloaders.sources.nhl_json.schedule.ScheduleDownloader",
            config_class="nhl_api.downloaders.base.base_downloader.DownloaderConfig",
            source_type=SourceType.SEASON,
            has_persist=True,
            target_tables=("games",),
            requires_game_id=False,
            default_base_url=NHL_API_BASE_URL_V1,
        ),
        "nhl_json_boxscore": SourceDefinition(
            name="nhl_json_boxscore",
            display_name="Boxscore",
            downloader_class="nhl_api.downloaders.sources.nhl_json.boxscore.BoxscoreDownloader",
            # BoxscoreDownloaderConfig has default base_url
            config_class="nhl_api.downloaders.sources.nhl_json.boxscore.BoxscoreDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=True,
            target_tables=("game_skater_stats", "game_goalie_stats"),
            requires_game_id=True,
        ),
        "nhl_json_play_by_play": SourceDefinition(
            name="nhl_json_play_by_play",
            display_name="Play-by-Play",
            downloader_class="nhl_api.downloaders.sources.nhl_json.play_by_play.PlayByPlayDownloader",
            config_class="nhl_api.downloaders.sources.nhl_json.play_by_play.PlayByPlayDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=True,
            target_tables=("game_events",),
            requires_game_id=True,
        ),
        "nhl_json_player_landing": SourceDefinition(
            name="nhl_json_player_landing",
            display_name="Player Landing",
            downloader_class="nhl_api.downloaders.sources.nhl_json.player_landing.PlayerLandingDownloader",
            config_class="nhl_api.downloaders.sources.nhl_json.player_landing.PlayerLandingDownloaderConfig",
            source_type=SourceType.PLAYER,
            has_persist=True,
            target_tables=("players",),
            requires_game_id=False,
        ),
        "nhl_json_player_game_log": SourceDefinition(
            name="nhl_json_player_game_log",
            display_name="Player Game Log",
            downloader_class="nhl_api.downloaders.sources.nhl_json.player_game_log.PlayerGameLogDownloader",
            config_class="nhl_api.downloaders.sources.nhl_json.player_game_log.PlayerGameLogDownloaderConfig",
            source_type=SourceType.PLAYER,
            has_persist=True,
            target_tables=("player_game_logs",),
            requires_game_id=False,
        ),
        "nhl_json_roster": SourceDefinition(
            name="nhl_json_roster",
            display_name="Roster",
            downloader_class="nhl_api.downloaders.sources.nhl_json.roster.RosterDownloader",
            config_class="nhl_api.downloaders.base.base_downloader.DownloaderConfig",
            source_type=SourceType.TEAM,
            has_persist=True,
            target_tables=("team_rosters",),
            requires_game_id=False,
            default_base_url=NHL_API_BASE_URL,
        ),
        "nhl_json_standings": SourceDefinition(
            name="nhl_json_standings",
            display_name="Standings",
            downloader_class="nhl_api.downloaders.sources.nhl_json.standings.StandingsDownloader",
            config_class="nhl_api.downloaders.base.base_downloader.DownloaderConfig",
            source_type=SourceType.DATE,
            has_persist=True,
            target_tables=("standings_snapshots",),
            requires_game_id=False,
            default_base_url=NHL_API_BASE_URL,
        ),
        "nhl_stats_shift_charts": SourceDefinition(
            name="nhl_stats_shift_charts",
            display_name="Shift Charts",
            downloader_class="nhl_api.downloaders.sources.nhl_stats.shift_charts.ShiftChartsDownloader",
            config_class="nhl_api.downloaders.sources.nhl_stats.shift_charts.ShiftChartsDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=True,
            target_tables=("game_shifts",),
            requires_game_id=True,
        ),
    }

    # HTML Report sources (parse-only, no persist)
    HTML_SOURCES: dict[str, SourceDefinition] = {
        "html_gs": SourceDefinition(
            name="html_gs",
            display_name="Game Summary (GS)",
            downloader_class="nhl_api.downloaders.sources.html.game_summary.GameSummaryDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
        "html_es": SourceDefinition(
            name="html_es",
            display_name="Event Summary (ES)",
            downloader_class="nhl_api.downloaders.sources.html.event_summary.EventSummaryDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
        "html_pl": SourceDefinition(
            name="html_pl",
            display_name="Play-by-Play (PL)",
            downloader_class="nhl_api.downloaders.sources.html.play_by_play.PlayByPlayDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
        "html_fs": SourceDefinition(
            name="html_fs",
            display_name="Faceoff Summary (FS)",
            downloader_class="nhl_api.downloaders.sources.html.faceoff_summary.FaceoffSummaryDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
        "html_fc": SourceDefinition(
            name="html_fc",
            display_name="Faceoff Comparison (FC)",
            downloader_class="nhl_api.downloaders.sources.html.faceoff_comparison.FaceoffComparisonDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
        "html_ro": SourceDefinition(
            name="html_ro",
            display_name="Roster Report (RO)",
            downloader_class="nhl_api.downloaders.sources.html.roster.RosterDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
        "html_ss": SourceDefinition(
            name="html_ss",
            display_name="Shot Summary (SS)",
            downloader_class="nhl_api.downloaders.sources.html.shot_summary.ShotSummaryDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
        "html_th": SourceDefinition(
            name="html_th",
            display_name="TOI Home (TH)",
            downloader_class="nhl_api.downloaders.sources.html.time_on_ice.TimeOnIceDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
        "html_tv": SourceDefinition(
            name="html_tv",
            display_name="TOI Visitor (TV)",
            downloader_class="nhl_api.downloaders.sources.html.time_on_ice.TimeOnIceDownloader",
            config_class="nhl_api.downloaders.sources.html.base_html_downloader.HTMLDownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
            requires_game_id=True,
        ),
    }

    # DailyFaceoff sources (team-based, no persist)
    DAILYFACEOFF_SOURCES: dict[str, SourceDefinition] = {
        "dailyfaceoff_lines": SourceDefinition(
            name="dailyfaceoff_lines",
            display_name="Line Combinations",
            downloader_class="nhl_api.downloaders.sources.dailyfaceoff.line_combinations.LineCombinationsDownloader",
            config_class="nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader.DailyFaceoffConfig",
            source_type=SourceType.TEAM,
            has_persist=False,
            requires_game_id=False,
        ),
        "dailyfaceoff_pp": SourceDefinition(
            name="dailyfaceoff_pp",
            display_name="Power Play Units",
            downloader_class="nhl_api.downloaders.sources.dailyfaceoff.power_play.PowerPlayDownloader",
            config_class="nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader.DailyFaceoffConfig",
            source_type=SourceType.TEAM,
            has_persist=False,
            requires_game_id=False,
        ),
        "dailyfaceoff_pk": SourceDefinition(
            name="dailyfaceoff_pk",
            display_name="Penalty Kill Units",
            downloader_class="nhl_api.downloaders.sources.dailyfaceoff.penalty_kill.PenaltyKillDownloader",
            config_class="nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader.DailyFaceoffConfig",
            source_type=SourceType.TEAM,
            has_persist=False,
            requires_game_id=False,
        ),
        "dailyfaceoff_injuries": SourceDefinition(
            name="dailyfaceoff_injuries",
            display_name="Injuries",
            downloader_class="nhl_api.downloaders.sources.dailyfaceoff.injuries.InjuryDownloader",
            config_class="nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader.DailyFaceoffConfig",
            source_type=SourceType.TEAM,
            has_persist=False,
            requires_game_id=False,
        ),
        "dailyfaceoff_goalies": SourceDefinition(
            name="dailyfaceoff_goalies",
            display_name="Starting Goalies",
            downloader_class="nhl_api.downloaders.sources.dailyfaceoff.starting_goalies.StartingGoaliesDownloader",
            config_class="nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader.DailyFaceoffConfig",
            source_type=SourceType.DATE,
            has_persist=False,
            requires_game_id=False,
        ),
    }

    # QuantHockey sources (season-based, no persist)
    QUANTHOCKEY_SOURCES: dict[str, SourceDefinition] = {
        "quanthockey_player_stats": SourceDefinition(
            name="quanthockey_player_stats",
            display_name="QuantHockey Player Stats",
            downloader_class="nhl_api.downloaders.sources.external.quanthockey.player_stats.QuantHockeyPlayerStatsDownloader",
            config_class="nhl_api.downloaders.sources.external.quanthockey.player_stats.QuantHockeyConfig",
            source_type=SourceType.SEASON,
            has_persist=False,
            requires_game_id=False,
        ),
    }

    # All source names that have persist methods
    PERSIST_SOURCE_NAMES: tuple[str, ...] = tuple(GAME_SOURCES.keys())

    # Game-level sources (require game_id for download_game)
    GAME_LEVEL_SOURCE_NAMES: tuple[str, ...] = (
        "nhl_json_boxscore",
        "nhl_json_play_by_play",
        "nhl_stats_shift_charts",
    )

    # HTML game-level sources
    HTML_GAME_LEVEL_SOURCE_NAMES: tuple[str, ...] = tuple(HTML_SOURCES.keys())

    @classmethod
    def _all_source_dicts(cls) -> list[dict[str, SourceDefinition]]:
        """Return all source dictionaries."""
        return [
            cls.GAME_SOURCES,
            cls.HTML_SOURCES,
            cls.DAILYFACEOFF_SOURCES,
            cls.QUANTHOCKEY_SOURCES,
        ]

    @classmethod
    def get_source(cls, name: str) -> SourceDefinition:
        """Get a source definition by name.

        Args:
            name: Source name (e.g., "nhl_json_boxscore", "html_gs")

        Returns:
            SourceDefinition for the source

        Raises:
            KeyError: If source not found
        """
        for source_dict in cls._all_source_dicts():
            if name in source_dict:
                return source_dict[name]
        raise KeyError(f"Unknown source: {name}")

    @classmethod
    def get_all_sources(cls) -> list[SourceDefinition]:
        """Get all registered source definitions.

        Returns:
            List of all SourceDefinition objects
        """
        sources: list[SourceDefinition] = []
        for source_dict in cls._all_source_dicts():
            sources.extend(source_dict.values())
        return sources

    @classmethod
    def get_persist_sources(cls) -> list[SourceDefinition]:
        """Get sources that have persist methods.

        Returns:
            List of SourceDefinition objects with has_persist=True
        """
        return [s for s in cls.get_all_sources() if s.has_persist]

    @classmethod
    def get_game_level_sources(cls) -> list[SourceDefinition]:
        """Get sources that download per-game data (NHL JSON/Stats).

        Returns:
            List of SourceDefinition objects that require game_id
        """
        return [s for s in cls.GAME_SOURCES.values() if s.requires_game_id]

    @classmethod
    def get_html_sources(cls) -> list[SourceDefinition]:
        """Get all HTML report sources.

        Returns:
            List of HTML SourceDefinition objects
        """
        return list(cls.HTML_SOURCES.values())

    @classmethod
    def get_dailyfaceoff_sources(cls) -> list[SourceDefinition]:
        """Get all DailyFaceoff sources.

        Returns:
            List of DailyFaceoff SourceDefinition objects
        """
        return list(cls.DAILYFACEOFF_SOURCES.values())

    @classmethod
    def get_external_sources(cls) -> list[SourceDefinition]:
        """Get all external (third-party) sources.

        Returns:
            List of external SourceDefinition objects
        """
        return list(cls.DAILYFACEOFF_SOURCES.values()) + list(
            cls.QUANTHOCKEY_SOURCES.values()
        )

    @classmethod
    def get_source_names(cls) -> list[str]:
        """Get all source names.

        Returns:
            List of source name strings
        """
        names: list[str] = []
        for source_dict in cls._all_source_dicts():
            names.extend(source_dict.keys())
        return names

    @classmethod
    def get_sources_by_type(cls, source_type: SourceType) -> list[SourceDefinition]:
        """Get sources filtered by type.

        Args:
            source_type: Type to filter by (GAME, SEASON, TEAM, etc.)

        Returns:
            List of SourceDefinition objects matching the type
        """
        return [s for s in cls.get_all_sources() if s.source_type == source_type]
