"""HTML Downloader Registry and Factory.

This module provides a registry and factory pattern for managing all HTML
report downloaders. It supports creating individual downloaders by report type
or creating all downloaders at once.

Example usage:
    # Create single downloader
    gs_downloader = HTMLDownloaderRegistry.create("GS")

    # Create all downloaders
    all_downloaders = HTMLDownloaderRegistry.create_all()

    # Use with custom config
    custom_config = HTMLDownloaderConfig(requests_per_second=1.0)
    downloader = HTMLDownloaderRegistry.create("ES", custom_config)

    # Get source name for database
    source_name = HTMLDownloaderRegistry.get_source_name("GS")  # "html_gs"
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nhl_api.downloaders.sources.html.base_html_downloader import (
    HTML_DOWNLOADER_CONFIG,
    BaseHTMLDownloader,
    HTMLDownloaderConfig,
)
from nhl_api.downloaders.sources.html.event_summary import EventSummaryDownloader
from nhl_api.downloaders.sources.html.faceoff_comparison import (
    FaceoffComparisonDownloader,
)
from nhl_api.downloaders.sources.html.faceoff_summary import FaceoffSummaryDownloader
from nhl_api.downloaders.sources.html.game_summary import GameSummaryDownloader
from nhl_api.downloaders.sources.html.play_by_play import PlayByPlayDownloader
from nhl_api.downloaders.sources.html.roster import RosterDownloader
from nhl_api.downloaders.sources.html.shot_summary import ShotSummaryDownloader
from nhl_api.downloaders.sources.html.time_on_ice import TimeOnIceDownloader

if TYPE_CHECKING:
    from collections.abc import Callable

    from nhl_api.downloaders.base.rate_limiter import RateLimiter
    from nhl_api.downloaders.base.retry_handler import RetryHandler
    from nhl_api.utils.http_client import HTTPClient


class HTMLDownloaderRegistry:
    """Registry for all HTML report downloaders.

    This class provides factory methods for creating HTML report downloaders.
    It supports all NHL HTML report types and handles special cases like
    the TimeOnIce downloader which requires a side parameter.

    Report Types:
        GS: Game Summary
        ES: Event Summary
        PL: Play-by-Play
        FS: Faceoff Summary
        FC: Faceoff Comparison
        RO: Roster Report
        SS: Shot Summary
        TH: Home Time on Ice
        TV: Visitor Time on Ice

    Example:
        # Create a single downloader
        downloader = HTMLDownloaderRegistry.create("GS")
        async with downloader:
            result = await downloader.download_game(2024020500)

        # Create all downloaders
        downloaders = HTMLDownloaderRegistry.create_all()
        for report_type, downloader in downloaders.items():
            print(f"{report_type}: {downloader.source_name}")
    """

    # Mapping of report types to downloader classes
    # TimeOnIce (TH/TV) maps to the same class with different side parameter
    DOWNLOADERS: dict[str, type[BaseHTMLDownloader]] = {
        "GS": GameSummaryDownloader,
        "ES": EventSummaryDownloader,
        "PL": PlayByPlayDownloader,
        "FS": FaceoffSummaryDownloader,
        "FC": FaceoffComparisonDownloader,
        "RO": RosterDownloader,
        "SS": ShotSummaryDownloader,
        "TH": TimeOnIceDownloader,
        "TV": TimeOnIceDownloader,
    }

    # All valid report type codes
    REPORT_TYPES: list[str] = list(DOWNLOADERS.keys())

    # Report types that require special handling
    TIME_ON_ICE_TYPES: frozenset[str] = frozenset({"TH", "TV"})

    @classmethod
    def create(
        cls,
        report_type: str,
        config: HTMLDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        game_ids: list[int] | None = None,
    ) -> BaseHTMLDownloader:
        """Create a downloader for a specific report type.

        Args:
            report_type: Report type code (GS, ES, PL, FS, FC, RO, SS, TH, TV)
            config: Optional downloader configuration. Uses default if not provided.
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            game_ids: Optional list of game IDs for season download

        Returns:
            Configured HTML downloader instance.

        Raises:
            ValueError: If report_type is not recognized.

        Example:
            # Create with default config
            gs = HTMLDownloaderRegistry.create("GS")

            # Create with custom config
            config = HTMLDownloaderConfig(requests_per_second=1.0)
            gs = HTMLDownloaderRegistry.create("GS", config)

            # Create Time on Ice for home team
            toi_home = HTMLDownloaderRegistry.create("TH")

            # Create Time on Ice for away team
            toi_away = HTMLDownloaderRegistry.create("TV")
        """
        report_type = report_type.upper()

        if report_type not in cls.DOWNLOADERS:
            raise ValueError(
                f"Unknown report type: {report_type}. Valid types: {cls.REPORT_TYPES}"
            )

        config = config or cls.default_config()
        downloader_class = cls.DOWNLOADERS[report_type]

        # TimeOnIce needs special handling for side parameter
        if report_type in cls.TIME_ON_ICE_TYPES:
            side = "home" if report_type == "TH" else "away"
            return TimeOnIceDownloader(
                config,
                side=side,
                http_client=http_client,
                rate_limiter=rate_limiter,
                retry_handler=retry_handler,
                progress_callback=progress_callback,
                game_ids=game_ids,
            )

        return downloader_class(
            config,
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
            game_ids=game_ids,
        )

    @classmethod
    def create_all(
        cls,
        config: HTMLDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        game_ids: list[int] | None = None,
    ) -> dict[str, BaseHTMLDownloader]:
        """Create all HTML downloaders.

        Args:
            config: Optional downloader configuration. Uses default if not provided.
            http_client: Optional shared HTTP client
            rate_limiter: Optional shared rate limiter
            retry_handler: Optional shared retry handler
            progress_callback: Optional callback for progress updates
            game_ids: Optional list of game IDs for season download

        Returns:
            Dictionary mapping report type to downloader instance.

        Example:
            downloaders = HTMLDownloaderRegistry.create_all()
            for report_type, downloader in downloaders.items():
                print(f"{report_type}: {downloader.source_name}")
        """
        return {
            report_type: cls.create(
                report_type,
                config,
                http_client=http_client,
                rate_limiter=rate_limiter,
                retry_handler=retry_handler,
                progress_callback=progress_callback,
                game_ids=game_ids,
            )
            for report_type in cls.REPORT_TYPES
        }

    @classmethod
    def default_config(cls) -> HTMLDownloaderConfig:
        """Return default configuration for HTML downloaders.

        Returns:
            Default HTMLDownloaderConfig instance
        """
        return HTML_DOWNLOADER_CONFIG

    @classmethod
    def get_source_name(cls, report_type: str) -> str:
        """Get the source name for a report type.

        The source name is used for database storage and monitoring.

        Args:
            report_type: Report type code (GS, ES, PL, etc.)

        Returns:
            Source name in format 'html_{report_type}' (e.g., 'html_gs')

        Raises:
            ValueError: If report_type is not recognized.

        Example:
            name = HTMLDownloaderRegistry.get_source_name("GS")  # "html_gs"
        """
        report_type = report_type.upper()

        if report_type not in cls.DOWNLOADERS:
            raise ValueError(
                f"Unknown report type: {report_type}. Valid types: {cls.REPORT_TYPES}"
            )

        return f"html_{report_type.lower()}"

    @classmethod
    def get_downloader_class(cls, report_type: str) -> type[BaseHTMLDownloader]:
        """Get the downloader class for a report type.

        This is useful for introspection or when you need the class
        rather than an instance.

        Args:
            report_type: Report type code (GS, ES, PL, etc.)

        Returns:
            Downloader class (not instance)

        Raises:
            ValueError: If report_type is not recognized.

        Example:
            cls = HTMLDownloaderRegistry.get_downloader_class("GS")
            print(cls.__name__)  # "GameSummaryDownloader"
        """
        report_type = report_type.upper()

        if report_type not in cls.DOWNLOADERS:
            raise ValueError(
                f"Unknown report type: {report_type}. Valid types: {cls.REPORT_TYPES}"
            )

        return cls.DOWNLOADERS[report_type]

    @classmethod
    def is_valid_report_type(cls, report_type: str) -> bool:
        """Check if a report type is valid.

        Args:
            report_type: Report type code to validate

        Returns:
            True if the report type is recognized, False otherwise

        Example:
            HTMLDownloaderRegistry.is_valid_report_type("GS")  # True
            HTMLDownloaderRegistry.is_valid_report_type("XX")  # False
        """
        return report_type.upper() in cls.DOWNLOADERS
