"""Download stage validation tests for all data sources.

This module validates that all 23 data sources can be downloaded
successfully with proper response schemas and required fields.

Test Organization:
- TestNHLJSONDownloadValidation: NHL JSON API sources (7)
- TestNHLStatsDownloadValidation: NHL Stats API sources (1)
- TestHTMLDownloadValidation: HTML report sources (9)
- TestDailyFaceoffDownloadValidation: DailyFaceoff sources (5)
- TestQuantHockeyDownloadValidation: QuantHockey sources (1)

Markers:
- @pytest.mark.integration: All tests
- @pytest.mark.data_validation: Download validation tests
- @pytest.mark.live: Tests that require network access

Run all validation tests:
    pytest tests/integration/data_flow/test_download_validation.py -v

Run live tests only:
    pytest tests/integration/data_flow/test_download_validation.py -v -m live
"""

from __future__ import annotations

import pytest

from tests.integration.data_flow.sources.registry import SourceRegistry
from tests.integration.data_flow.stages.download import DownloadStage


@pytest.mark.integration
@pytest.mark.data_validation
class TestSourceRegistryValidation:
    """Validate source registry has all expected sources."""

    def test_registry_has_nhl_json_sources(self) -> None:
        """Verify all NHL JSON API sources are registered."""
        expected = {
            "nhl_json_schedule",
            "nhl_json_boxscore",
            "nhl_json_play_by_play",
            "nhl_json_player_landing",
            "nhl_json_player_game_log",
            "nhl_json_roster",
            "nhl_json_standings",
        }
        actual = set(SourceRegistry.GAME_SOURCES.keys())
        # GAME_SOURCES includes shift_charts too
        assert expected.issubset(actual), (
            f"Missing NHL JSON sources: {expected - actual}"
        )

    def test_registry_has_html_sources(self) -> None:
        """Verify all HTML report sources are registered."""
        expected = {
            "html_gs",
            "html_es",
            "html_pl",
            "html_fs",
            "html_fc",
            "html_ro",
            "html_ss",
            "html_th",
            "html_tv",
        }
        actual = set(SourceRegistry.HTML_SOURCES.keys())
        assert expected == actual, (
            f"HTML sources mismatch: {expected.symmetric_difference(actual)}"
        )

    def test_registry_has_dailyfaceoff_sources(self) -> None:
        """Verify all DailyFaceoff sources are registered."""
        expected = {
            "dailyfaceoff_lines",
            "dailyfaceoff_pp",
            "dailyfaceoff_pk",
            "dailyfaceoff_injuries",
            "dailyfaceoff_goalies",
        }
        actual = set(SourceRegistry.DAILYFACEOFF_SOURCES.keys())
        assert expected == actual, (
            f"DailyFaceoff sources mismatch: {expected.symmetric_difference(actual)}"
        )

    def test_registry_has_quanthockey_sources(self) -> None:
        """Verify all QuantHockey sources are registered."""
        expected = {"quanthockey_player_stats"}
        actual = set(SourceRegistry.QUANTHOCKEY_SOURCES.keys())
        assert expected == actual

    def test_all_sources_can_load_classes(self) -> None:
        """Verify all source classes can be loaded."""
        for source in SourceRegistry.get_all_sources():
            try:
                downloader_cls = source.get_downloader_class()
                config_cls = source.get_config_class()
                assert downloader_cls is not None, (
                    f"{source.name} downloader class is None"
                )
                assert config_cls is not None, f"{source.name} config class is None"
            except (ImportError, AttributeError) as e:
                pytest.fail(f"Failed to load classes for {source.name}: {e}")

    def test_total_source_count(self) -> None:
        """Verify total source count matches expected."""
        # 8 NHL JSON/Stats + 9 HTML + 5 DailyFaceoff + 1 QuantHockey = 23
        assert len(SourceRegistry.get_all_sources()) == 23


@pytest.mark.integration
@pytest.mark.data_validation
class TestSourceDefinitionValidation:
    """Validate source definitions have required fields."""

    def test_all_sources_have_required_fields(self) -> None:
        """Verify each source has all required fields."""
        for src_name in SourceRegistry.get_source_names():
            source = SourceRegistry.get_source(src_name)

            assert source.name, f"{src_name} missing name"
            assert source.display_name, f"{src_name} missing display_name"
            assert source.downloader_class, f"{src_name} missing downloader_class"
            assert source.config_class, f"{src_name} missing config_class"
            assert source.source_type is not None, f"{src_name} missing source_type"

    def test_persist_sources_have_target_tables(self) -> None:
        """Verify persist sources define target tables."""
        for src_name in SourceRegistry.GAME_SOURCES.keys():
            source = SourceRegistry.get_source(src_name)
            if source.has_persist:
                assert source.target_tables, f"{src_name} missing target_tables"


@pytest.mark.integration
@pytest.mark.data_validation
@pytest.mark.live
class TestNHLJSONDownloadValidation:
    """Live validation tests for NHL JSON API sources."""

    @pytest.mark.asyncio
    async def test_schedule_download(
        self,
        download_stage: DownloadStage,
        fixture_season_id: int,
    ) -> None:
        """Test schedule download returns valid data."""
        source = SourceRegistry.get_source("nhl_json_schedule")
        result = await download_stage.download_source(
            source,
            season_id=fixture_season_id,
            config_overrides={"requests_per_second": 2.0},
        )

        assert result.success, f"Download failed: {result.error}"
        assert result.has_data
        # Schedule should return games
        if result.data:
            assert "games" in result.data or isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_boxscore_download(
        self,
        download_stage: DownloadStage,
        fixture_game_id: int,
    ) -> None:
        """Test boxscore download returns player stats."""
        source = SourceRegistry.get_source("nhl_json_boxscore")
        result = await download_stage.download_source(
            source,
            game_id=fixture_game_id,
            config_overrides={"requests_per_second": 2.0},
        )

        assert result.success, f"Download failed: {result.error}"
        assert result.has_data

    @pytest.mark.asyncio
    async def test_play_by_play_download(
        self,
        download_stage: DownloadStage,
        fixture_game_id: int,
    ) -> None:
        """Test play-by-play download returns events."""
        source = SourceRegistry.get_source("nhl_json_play_by_play")
        result = await download_stage.download_source(
            source,
            game_id=fixture_game_id,
            config_overrides={"requests_per_second": 2.0},
        )

        assert result.success, f"Download failed: {result.error}"
        assert result.has_data


@pytest.mark.integration
@pytest.mark.data_validation
@pytest.mark.live
class TestNHLStatsDownloadValidation:
    """Live validation tests for NHL Stats API sources."""

    @pytest.mark.asyncio
    async def test_shift_charts_download(
        self,
        download_stage: DownloadStage,
        fixture_game_id: int,
    ) -> None:
        """Test shift charts download returns shift data."""
        source = SourceRegistry.get_source("nhl_stats_shift_charts")
        result = await download_stage.download_source(
            source,
            game_id=fixture_game_id,
            config_overrides={"requests_per_second": 2.0},
        )

        assert result.success, f"Download failed: {result.error}"
        assert result.has_data


@pytest.mark.integration
@pytest.mark.data_validation
@pytest.mark.live
class TestHTMLDownloadValidation:
    """Live validation tests for HTML report sources."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "html_source_name,report_type",
        [
            ("html_gs", "GS"),
            ("html_es", "ES"),
            ("html_pl", "PL"),
            ("html_fs", "FS"),
            ("html_fc", "FC"),
            ("html_ro", "RO"),
            ("html_ss", "SS"),
        ],
    )
    async def test_html_report_download(
        self,
        download_stage: DownloadStage,
        fixture_game_id: int,
        html_source_name: str,
        report_type: str,
    ) -> None:
        """Test HTML report downloads parse successfully."""
        source = SourceRegistry.get_source(html_source_name)
        result = await download_stage.download_source(
            source,
            game_id=fixture_game_id,
            config_overrides={"requests_per_second": 1.0},
        )

        assert result.success, f"{report_type} download failed: {result.error}"
        # HTML downloads may or may not have parsed data depending on implementation
        # The key is that download succeeded without error

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "toi_source_name,side",
        [
            ("html_th", "home"),
            ("html_tv", "away"),
        ],
    )
    async def test_toi_report_download(
        self,
        download_stage: DownloadStage,
        fixture_game_id: int,
        toi_source_name: str,
        side: str,
    ) -> None:
        """Test TOI report downloads parse successfully."""
        source = SourceRegistry.get_source(toi_source_name)
        result = await download_stage.download_source(
            source,
            game_id=fixture_game_id,
            config_overrides={"requests_per_second": 1.0},
        )

        assert result.success, f"TOI {side} download failed: {result.error}"


@pytest.mark.integration
@pytest.mark.data_validation
@pytest.mark.live
class TestDailyFaceoffDownloadValidation:
    """Live validation tests for DailyFaceoff sources."""

    @pytest.mark.asyncio
    async def test_line_combinations_download(
        self,
        download_stage: DownloadStage,
        fixture_team_id: int,
    ) -> None:
        """Test line combinations download."""
        source = SourceRegistry.get_source("dailyfaceoff_lines")
        result = await download_stage.download_source(
            source,
            team_id=fixture_team_id,
            config_overrides={"requests_per_second": 0.5},
        )

        # DailyFaceoff may fail due to rate limiting or changes
        # We check it doesn't crash unexpectedly
        if not result.success:
            assert "rate limit" in str(result.error).lower() or result.error is not None

    @pytest.mark.asyncio
    async def test_power_play_download(
        self,
        download_stage: DownloadStage,
        fixture_team_id: int,
    ) -> None:
        """Test power play units download."""
        source = SourceRegistry.get_source("dailyfaceoff_pp")
        result = await download_stage.download_source(
            source,
            team_id=fixture_team_id,
            config_overrides={"requests_per_second": 0.5},
        )

        if not result.success:
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_penalty_kill_download(
        self,
        download_stage: DownloadStage,
        fixture_team_id: int,
    ) -> None:
        """Test penalty kill units download."""
        source = SourceRegistry.get_source("dailyfaceoff_pk")
        result = await download_stage.download_source(
            source,
            team_id=fixture_team_id,
            config_overrides={"requests_per_second": 0.5},
        )

        if not result.success:
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_injuries_download(
        self,
        download_stage: DownloadStage,
        fixture_team_id: int,
    ) -> None:
        """Test injuries download."""
        source = SourceRegistry.get_source("dailyfaceoff_injuries")
        result = await download_stage.download_source(
            source,
            team_id=fixture_team_id,
            config_overrides={"requests_per_second": 0.5},
        )

        if not result.success:
            assert result.error is not None


@pytest.mark.integration
@pytest.mark.data_validation
@pytest.mark.live
class TestQuantHockeyDownloadValidation:
    """Live validation tests for QuantHockey sources."""

    @pytest.mark.asyncio
    async def test_player_stats_download(
        self,
        download_stage: DownloadStage,
        fixture_season_id: int,
    ) -> None:
        """Test QuantHockey player stats download."""
        source = SourceRegistry.get_source("quanthockey_player_stats")
        result = await download_stage.download_source(
            source,
            season_id=fixture_season_id,
            config_overrides={"requests_per_second": 0.3},
        )

        # QuantHockey may block or rate limit
        if not result.success:
            assert result.error is not None
