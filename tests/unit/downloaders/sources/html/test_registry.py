"""Unit tests for HTML Downloader Registry.

Tests the registry and factory pattern for creating HTML report downloaders.
"""

from __future__ import annotations

import pytest

from nhl_api.downloaders.sources.html import (
    HTML_DOWNLOADER_CONFIG,
    BaseHTMLDownloader,
    EventSummaryDownloader,
    FaceoffComparisonDownloader,
    FaceoffSummaryDownloader,
    GameSummaryDownloader,
    HTMLDownloaderConfig,
    HTMLDownloaderRegistry,
    PlayByPlayDownloader,
    RosterDownloader,
    ShotSummaryDownloader,
    TimeOnIceDownloader,
)


class TestHTMLDownloaderRegistry:
    """Tests for HTMLDownloaderRegistry class."""

    # =========================================================================
    # Test DOWNLOADERS mapping
    # =========================================================================

    def test_downloaders_contains_all_report_types(self) -> None:
        """Verify all expected report types are registered."""
        expected_types = {"GS", "ES", "PL", "FS", "FC", "RO", "SS", "TH", "TV"}
        assert set(HTMLDownloaderRegistry.DOWNLOADERS.keys()) == expected_types

    def test_report_types_list(self) -> None:
        """Verify REPORT_TYPES list matches DOWNLOADERS keys."""
        assert set(HTMLDownloaderRegistry.REPORT_TYPES) == set(
            HTMLDownloaderRegistry.DOWNLOADERS.keys()
        )

    def test_time_on_ice_types(self) -> None:
        """Verify TIME_ON_ICE_TYPES contains TH and TV."""
        assert HTMLDownloaderRegistry.TIME_ON_ICE_TYPES == frozenset({"TH", "TV"})

    # =========================================================================
    # Test create() - Standard Downloaders
    # =========================================================================

    def test_create_game_summary(self) -> None:
        """Create GameSummaryDownloader."""
        downloader = HTMLDownloaderRegistry.create("GS")
        assert isinstance(downloader, GameSummaryDownloader)
        assert downloader.report_type == "GS"
        assert downloader.source_name == "html_gs"

    def test_create_event_summary(self) -> None:
        """Create EventSummaryDownloader."""
        downloader = HTMLDownloaderRegistry.create("ES")
        assert isinstance(downloader, EventSummaryDownloader)
        assert downloader.report_type == "ES"
        assert downloader.source_name == "html_es"

    def test_create_play_by_play(self) -> None:
        """Create PlayByPlayDownloader."""
        downloader = HTMLDownloaderRegistry.create("PL")
        assert isinstance(downloader, PlayByPlayDownloader)
        assert downloader.report_type == "PL"
        assert downloader.source_name == "html_pl"

    def test_create_faceoff_summary(self) -> None:
        """Create FaceoffSummaryDownloader."""
        downloader = HTMLDownloaderRegistry.create("FS")
        assert isinstance(downloader, FaceoffSummaryDownloader)
        assert downloader.report_type == "FS"
        assert downloader.source_name == "html_fs"

    def test_create_faceoff_comparison(self) -> None:
        """Create FaceoffComparisonDownloader."""
        downloader = HTMLDownloaderRegistry.create("FC")
        assert isinstance(downloader, FaceoffComparisonDownloader)
        assert downloader.report_type == "FC"
        assert downloader.source_name == "html_fc"

    def test_create_roster(self) -> None:
        """Create RosterDownloader."""
        downloader = HTMLDownloaderRegistry.create("RO")
        assert isinstance(downloader, RosterDownloader)
        assert downloader.report_type == "RO"
        assert downloader.source_name == "html_ro"

    def test_create_shot_summary(self) -> None:
        """Create ShotSummaryDownloader."""
        downloader = HTMLDownloaderRegistry.create("SS")
        assert isinstance(downloader, ShotSummaryDownloader)
        assert downloader.report_type == "SS"
        assert downloader.source_name == "html_ss"

    # =========================================================================
    # Test create() - TimeOnIce Special Cases
    # =========================================================================

    def test_create_time_on_ice_home(self) -> None:
        """Create TimeOnIceDownloader for home team (TH)."""
        downloader = HTMLDownloaderRegistry.create("TH")
        assert isinstance(downloader, TimeOnIceDownloader)
        assert downloader.report_type == "TH"
        assert downloader.source_name == "html_th"
        assert downloader._side == "home"  # noqa: SLF001

    def test_create_time_on_ice_visitor(self) -> None:
        """Create TimeOnIceDownloader for visitor team (TV)."""
        downloader = HTMLDownloaderRegistry.create("TV")
        assert isinstance(downloader, TimeOnIceDownloader)
        assert downloader.report_type == "TV"
        assert downloader.source_name == "html_tv"
        assert downloader._side == "away"  # noqa: SLF001

    # =========================================================================
    # Test create() - Case Insensitivity
    # =========================================================================

    def test_create_lowercase(self) -> None:
        """Create downloader with lowercase report type."""
        downloader = HTMLDownloaderRegistry.create("gs")
        assert isinstance(downloader, GameSummaryDownloader)
        assert downloader.report_type == "GS"

    def test_create_mixed_case(self) -> None:
        """Create downloader with mixed case report type."""
        downloader = HTMLDownloaderRegistry.create("Gs")
        assert isinstance(downloader, GameSummaryDownloader)

    # =========================================================================
    # Test create() - Invalid Report Types
    # =========================================================================

    def test_create_invalid_report_type(self) -> None:
        """Raise ValueError for unknown report type."""
        with pytest.raises(ValueError, match="Unknown report type: XX"):
            HTMLDownloaderRegistry.create("XX")

    def test_create_empty_report_type(self) -> None:
        """Raise ValueError for empty report type."""
        with pytest.raises(ValueError, match="Unknown report type:"):
            HTMLDownloaderRegistry.create("")

    # =========================================================================
    # Test create() - Custom Configuration
    # =========================================================================

    def test_create_with_custom_config(self) -> None:
        """Create downloader with custom configuration."""
        custom_config = HTMLDownloaderConfig(
            requests_per_second=1.0,
            max_retries=5,
        )
        downloader = HTMLDownloaderRegistry.create("GS", custom_config)
        assert downloader.config.requests_per_second == 1.0
        assert downloader.config.max_retries == 5

    def test_create_with_default_config(self) -> None:
        """Create downloader uses default config when not specified."""
        downloader = HTMLDownloaderRegistry.create("GS")
        # Should use default HTML config
        assert downloader.config.base_url == HTML_DOWNLOADER_CONFIG.base_url
        assert (
            downloader.config.requests_per_second
            == HTML_DOWNLOADER_CONFIG.requests_per_second
        )

    def test_create_with_game_ids(self) -> None:
        """Create downloader with game IDs."""
        game_ids = [2024020001, 2024020002, 2024020003]
        downloader = HTMLDownloaderRegistry.create("GS", game_ids=game_ids)
        assert downloader._game_ids == game_ids  # noqa: SLF001

    # =========================================================================
    # Test create_all()
    # =========================================================================

    def test_create_all_returns_all_report_types(self) -> None:
        """create_all returns all registered report types."""
        downloaders = HTMLDownloaderRegistry.create_all()
        assert set(downloaders.keys()) == set(HTMLDownloaderRegistry.REPORT_TYPES)

    def test_create_all_returns_correct_instances(self) -> None:
        """create_all returns correct downloader instances."""
        downloaders = HTMLDownloaderRegistry.create_all()

        assert isinstance(downloaders["GS"], GameSummaryDownloader)
        assert isinstance(downloaders["ES"], EventSummaryDownloader)
        assert isinstance(downloaders["PL"], PlayByPlayDownloader)
        assert isinstance(downloaders["FS"], FaceoffSummaryDownloader)
        assert isinstance(downloaders["FC"], FaceoffComparisonDownloader)
        assert isinstance(downloaders["RO"], RosterDownloader)
        assert isinstance(downloaders["SS"], ShotSummaryDownloader)
        assert isinstance(downloaders["TH"], TimeOnIceDownloader)
        assert isinstance(downloaders["TV"], TimeOnIceDownloader)

    def test_create_all_time_on_ice_sides(self) -> None:
        """create_all sets correct side for TimeOnIce downloaders."""
        downloaders = HTMLDownloaderRegistry.create_all()

        # Cast to TimeOnIceDownloader for type checker
        toi_home = downloaders["TH"]
        toi_away = downloaders["TV"]
        assert isinstance(toi_home, TimeOnIceDownloader)
        assert isinstance(toi_away, TimeOnIceDownloader)
        assert toi_home._side == "home"  # noqa: SLF001
        assert toi_away._side == "away"  # noqa: SLF001

    def test_create_all_with_custom_config(self) -> None:
        """create_all with custom configuration."""
        custom_config = HTMLDownloaderConfig(requests_per_second=0.5)
        downloaders = HTMLDownloaderRegistry.create_all(custom_config)

        for downloader in downloaders.values():
            assert downloader.config.requests_per_second == 0.5

    def test_create_all_with_game_ids(self) -> None:
        """create_all with game IDs."""
        game_ids = [2024020001, 2024020002]
        downloaders = HTMLDownloaderRegistry.create_all(game_ids=game_ids)

        for downloader in downloaders.values():
            assert downloader._game_ids == game_ids  # noqa: SLF001

    # =========================================================================
    # Test default_config()
    # =========================================================================

    def test_default_config_returns_html_config(self) -> None:
        """default_config returns HTMLDownloaderConfig instance."""
        config = HTMLDownloaderRegistry.default_config()
        assert config is HTML_DOWNLOADER_CONFIG

    def test_default_config_values(self) -> None:
        """default_config has expected values."""
        config = HTMLDownloaderRegistry.default_config()
        assert config.base_url == "https://www.nhl.com/scores/htmlreports"
        assert config.requests_per_second == 2.0
        assert config.max_retries == 3

    # =========================================================================
    # Test get_source_name()
    # =========================================================================

    @pytest.mark.parametrize(
        ("report_type", "expected_name"),
        [
            ("GS", "html_gs"),
            ("ES", "html_es"),
            ("PL", "html_pl"),
            ("FS", "html_fs"),
            ("FC", "html_fc"),
            ("RO", "html_ro"),
            ("SS", "html_ss"),
            ("TH", "html_th"),
            ("TV", "html_tv"),
        ],
    )
    def test_get_source_name(self, report_type: str, expected_name: str) -> None:
        """get_source_name returns correct source name."""
        assert HTMLDownloaderRegistry.get_source_name(report_type) == expected_name

    def test_get_source_name_lowercase(self) -> None:
        """get_source_name handles lowercase input."""
        assert HTMLDownloaderRegistry.get_source_name("gs") == "html_gs"

    def test_get_source_name_invalid(self) -> None:
        """get_source_name raises ValueError for invalid type."""
        with pytest.raises(ValueError, match="Unknown report type"):
            HTMLDownloaderRegistry.get_source_name("XX")

    # =========================================================================
    # Test get_downloader_class()
    # =========================================================================

    @pytest.mark.parametrize(
        ("report_type", "expected_class"),
        [
            ("GS", GameSummaryDownloader),
            ("ES", EventSummaryDownloader),
            ("PL", PlayByPlayDownloader),
            ("FS", FaceoffSummaryDownloader),
            ("FC", FaceoffComparisonDownloader),
            ("RO", RosterDownloader),
            ("SS", ShotSummaryDownloader),
            ("TH", TimeOnIceDownloader),
            ("TV", TimeOnIceDownloader),
        ],
    )
    def test_get_downloader_class(
        self, report_type: str, expected_class: type[BaseHTMLDownloader]
    ) -> None:
        """get_downloader_class returns correct class."""
        assert (
            HTMLDownloaderRegistry.get_downloader_class(report_type) is expected_class
        )

    def test_get_downloader_class_lowercase(self) -> None:
        """get_downloader_class handles lowercase input."""
        assert (
            HTMLDownloaderRegistry.get_downloader_class("gs") is GameSummaryDownloader
        )

    def test_get_downloader_class_invalid(self) -> None:
        """get_downloader_class raises ValueError for invalid type."""
        with pytest.raises(ValueError, match="Unknown report type"):
            HTMLDownloaderRegistry.get_downloader_class("XX")

    # =========================================================================
    # Test is_valid_report_type()
    # =========================================================================

    @pytest.mark.parametrize(
        "report_type",
        ["GS", "ES", "PL", "FS", "FC", "RO", "SS", "TH", "TV"],
    )
    def test_is_valid_report_type_valid(self, report_type: str) -> None:
        """is_valid_report_type returns True for valid types."""
        assert HTMLDownloaderRegistry.is_valid_report_type(report_type) is True

    @pytest.mark.parametrize(
        "report_type",
        ["gs", "es", "pl", "fs", "fc", "ro", "ss", "th", "tv"],
    )
    def test_is_valid_report_type_lowercase(self, report_type: str) -> None:
        """is_valid_report_type handles lowercase input."""
        assert HTMLDownloaderRegistry.is_valid_report_type(report_type) is True

    @pytest.mark.parametrize(
        "report_type",
        ["XX", "", "INVALID", "G", "GSS"],
    )
    def test_is_valid_report_type_invalid(self, report_type: str) -> None:
        """is_valid_report_type returns False for invalid types."""
        assert HTMLDownloaderRegistry.is_valid_report_type(report_type) is False

    # =========================================================================
    # Test all downloaders are BaseHTMLDownloader subclasses
    # =========================================================================

    def test_all_downloaders_inherit_from_base(self) -> None:
        """All registered downloaders inherit from BaseHTMLDownloader."""
        for report_type, downloader_class in HTMLDownloaderRegistry.DOWNLOADERS.items():
            assert issubclass(downloader_class, BaseHTMLDownloader), (
                f"{report_type}: {downloader_class.__name__} does not inherit "
                f"from BaseHTMLDownloader"
            )

    def test_all_created_downloaders_are_base_instances(self) -> None:
        """All created downloaders are BaseHTMLDownloader instances."""
        downloaders = HTMLDownloaderRegistry.create_all()
        for report_type, downloader in downloaders.items():
            assert isinstance(downloader, BaseHTMLDownloader), (
                f"{report_type}: {type(downloader).__name__} is not a "
                f"BaseHTMLDownloader instance"
            )
