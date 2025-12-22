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

    # All source names that have persist methods
    PERSIST_SOURCE_NAMES: tuple[str, ...] = tuple(GAME_SOURCES.keys())

    # Game-level sources (require game_id for download_game)
    GAME_LEVEL_SOURCE_NAMES: tuple[str, ...] = (
        "nhl_json_boxscore",
        "nhl_json_play_by_play",
        "nhl_stats_shift_charts",
    )

    @classmethod
    def get_source(cls, name: str) -> SourceDefinition:
        """Get a source definition by name.

        Args:
            name: Source name (e.g., "nhl_json_boxscore")

        Returns:
            SourceDefinition for the source

        Raises:
            KeyError: If source not found
        """
        if name in cls.GAME_SOURCES:
            return cls.GAME_SOURCES[name]
        raise KeyError(f"Unknown source: {name}")

    @classmethod
    def get_all_sources(cls) -> list[SourceDefinition]:
        """Get all registered source definitions.

        Returns:
            List of all SourceDefinition objects
        """
        return list(cls.GAME_SOURCES.values())

    @classmethod
    def get_persist_sources(cls) -> list[SourceDefinition]:
        """Get sources that have persist methods.

        Returns:
            List of SourceDefinition objects with has_persist=True
        """
        return [s for s in cls.GAME_SOURCES.values() if s.has_persist]

    @classmethod
    def get_game_level_sources(cls) -> list[SourceDefinition]:
        """Get sources that download per-game data.

        Returns:
            List of SourceDefinition objects that require game_id
        """
        return [s for s in cls.GAME_SOURCES.values() if s.requires_game_id]

    @classmethod
    def get_source_names(cls) -> list[str]:
        """Get all source names.

        Returns:
            List of source name strings
        """
        return list(cls.GAME_SOURCES.keys())
