"""Data flow integration tests.

This module contains end-to-end tests for the NHL API data pipeline,
validating the complete flow from download through storage.

Test Categories:
- test_full_data_flow: Complete pipeline test for fixture game
- test_individual_source_*: Per-source validation tests
- test_report_generation: Verify report output

Markers:
- @pytest.mark.integration: Integration tests (default)
- @pytest.mark.data_validation: Data validation tests
- @pytest.mark.live: Tests that require network access
"""

from __future__ import annotations

import pytest

from tests.integration.data_flow.reports.generator import ReportGenerator
from tests.integration.data_flow.reports.models import DataFlowReport
from tests.integration.data_flow.sources.registry import SourceRegistry
from tests.integration.data_flow.stages.download import DownloadStage
from tests.integration.data_flow.stages.storage import MockDatabaseService, StorageStage


@pytest.mark.integration
@pytest.mark.data_validation
class TestDataFlowInfrastructure:
    """Tests for data flow test infrastructure components."""

    def test_source_registry_has_sources(self) -> None:
        """Verify source registry has expected sources."""
        sources = SourceRegistry.get_all_sources()
        assert len(sources) >= 8, "Expected at least 8 sources"

        # Verify expected source names exist
        names = SourceRegistry.get_source_names()
        assert "nhl_json_boxscore" in names
        assert "nhl_json_play_by_play" in names
        assert "nhl_stats_shift_charts" in names

    def test_source_definitions_valid(self) -> None:
        """Verify all source definitions are valid."""
        for source in SourceRegistry.get_all_sources():
            assert source.name, "Source name required"
            assert source.display_name, "Display name required"
            assert source.downloader_class, "Downloader class required"
            assert source.config_class, "Config class required"

            # Verify classes can be loaded
            try:
                source.get_downloader_class()
                source.get_config_class()
            except (ImportError, AttributeError) as e:
                pytest.fail(f"Failed to load classes for {source.name}: {e}")

    def test_persist_sources_have_target_tables(self) -> None:
        """Verify persist sources define target tables."""
        for source in SourceRegistry.get_persist_sources():
            assert source.has_persist, f"{source.name} should have persist"
            assert source.target_tables, f"{source.name} should have target tables"

    def test_mock_database_service(self) -> None:
        """Test MockDatabaseService functionality."""
        db = MockDatabaseService()

        assert db.is_connected
        db.set_table_count("games", 100)
        assert db._table_counts["games"] == 100

        db.reset()
        assert not db._persist_calls
        assert not db._table_counts


@pytest.mark.integration
@pytest.mark.data_validation
class TestDownloadStage:
    """Tests for the download stage."""

    def test_download_stage_creation(self) -> None:
        """Test download stage can be created."""
        stage = DownloadStage()
        assert stage is not None

    def test_download_stage_with_rate_limit(self) -> None:
        """Test download stage respects rate limit override."""
        stage = DownloadStage(rate_limit_override=10.0)
        assert stage.rate_limit_override == 10.0

    @pytest.mark.asyncio
    async def test_download_source_creates_result(
        self,
        download_stage: DownloadStage,
    ) -> None:
        """Test download creates proper result object."""
        source = SourceRegistry.get_source("nhl_json_boxscore")

        # This will fail without network, but should return a proper result
        result = await download_stage.download_source(source, game_id=2024020001)

        assert result.source_name == "nhl_json_boxscore"
        assert result.download_time_ms >= 0
        # Result may succeed or fail depending on network
        assert result.success or result.error is not None


@pytest.mark.integration
@pytest.mark.data_validation
class TestStorageStage:
    """Tests for the storage stage."""

    def test_storage_stage_creation(self, mock_db: MockDatabaseService) -> None:
        """Test storage stage can be created."""
        stage = StorageStage(mock_db)
        assert stage.db is mock_db

    @pytest.mark.asyncio
    async def test_storage_skip_no_persist(
        self,
        storage_stage: StorageStage,
    ) -> None:
        """Test storage skips sources without persist."""
        # Create a source definition without persist
        from tests.integration.data_flow.sources.registry import (
            SourceDefinition,
            SourceType,
        )
        from tests.integration.data_flow.stages.download import DownloadStageResult

        source = SourceDefinition(
            name="test_no_persist",
            display_name="Test",
            downloader_class="nhl_api.downloaders.sources.nhl_json.schedule.ScheduleDownloader",
            config_class="nhl_api.downloaders.base.base_downloader.DownloaderConfig",
            source_type=SourceType.GAME,
            has_persist=False,
        )

        download_result = DownloadStageResult(
            source_name="test_no_persist",
            success=True,
            download_time_ms=100,
            data={"test": "data"},
        )

        result = await storage_stage.persist_and_verify(source, download_result)

        assert result.success
        assert result.rows_affected == 0
        assert result.error is None


@pytest.mark.integration
@pytest.mark.data_validation
class TestReportGeneration:
    """Tests for report generation."""

    def test_empty_report(self, report_generator: ReportGenerator) -> None:
        """Test report generation with empty report."""
        report = DataFlowReport()
        output = report_generator.generate(report)

        assert "Data Flow Test Report" in output
        assert "Summary" in output
        assert "Total Sources | 0" in output

    def test_report_with_results(self, report_generator: ReportGenerator) -> None:
        """Test report generation with mock results."""
        from tests.integration.data_flow.stages.download import DownloadStageResult
        from tests.integration.data_flow.stages.storage import StorageStageResult

        report = DataFlowReport(game_id=2024020001, season_id=20242025)

        # Add a successful result
        download_result = DownloadStageResult(
            source_name="nhl_json_boxscore",
            success=True,
            download_time_ms=150,
            data={"test": "data"},
        )
        storage_result = StorageStageResult(
            source_name="nhl_json_boxscore",
            success=True,
            persist_time_ms=50,
            rows_affected=10,
            tables_populated={"game_skater_stats": 5, "game_goalie_stats": 2},
        )

        report.add_source_result(
            source_name="nhl_json_boxscore",
            display_name="Boxscore",
            download_result=download_result,
            storage_result=storage_result,
        )

        output = report_generator.generate(report)

        assert "Game ID:** 2024020001" in output
        assert "Boxscore" in output
        assert "game_skater_stats" in output

    def test_console_summary(self, report_generator: ReportGenerator) -> None:
        """Test console summary generation."""
        from tests.integration.data_flow.stages.download import DownloadStageResult

        report = DataFlowReport()
        report.add_source_result(
            source_name="test",
            display_name="Test Source",
            download_result=DownloadStageResult(
                source_name="test",
                success=True,
                download_time_ms=100,
            ),
        )
        report.mark_completed()

        summary = report_generator.generate_console_summary(report)

        assert "Data Flow Test" in summary
        assert "1/1 passed" in summary


@pytest.mark.integration
@pytest.mark.data_validation
@pytest.mark.live
class TestLiveDataFlow:
    """Live tests that require network access.

    These tests are skipped by default. Run with:
        pytest -m live tests/integration/data_flow/
    """

    @pytest.mark.asyncio
    async def test_boxscore_download_live(
        self,
        fixture_game_id: int,
        download_stage: DownloadStage,
    ) -> None:
        """Test live boxscore download."""
        source = SourceRegistry.get_source("nhl_json_boxscore")

        result = await download_stage.download_source(
            source,
            game_id=fixture_game_id,
            config_overrides={"requests_per_second": 2.0},
        )

        assert result.success, f"Download failed: {result.error}"
        assert result.has_data
        assert result.download_time_ms > 0

    @pytest.mark.asyncio
    async def test_play_by_play_download_live(
        self,
        fixture_game_id: int,
        download_stage: DownloadStage,
    ) -> None:
        """Test live play-by-play download."""
        source = SourceRegistry.get_source("nhl_json_play_by_play")

        result = await download_stage.download_source(
            source,
            game_id=fixture_game_id,
            config_overrides={"requests_per_second": 2.0},
        )

        assert result.success, f"Download failed: {result.error}"
        assert result.has_data

    @pytest.mark.asyncio
    async def test_shift_charts_download_live(
        self,
        fixture_game_id: int,
        download_stage: DownloadStage,
    ) -> None:
        """Test live shift charts download."""
        source = SourceRegistry.get_source("nhl_stats_shift_charts")

        result = await download_stage.download_source(
            source,
            game_id=fixture_game_id,
            config_overrides={"requests_per_second": 2.0},
        )

        assert result.success, f"Download failed: {result.error}"
        assert result.has_data

    @pytest.mark.asyncio
    async def test_full_game_data_flow_live(
        self,
        fixture_game_id: int,
        fixture_season_id: int,
        download_stage: DownloadStage,
        mock_db: MockDatabaseService,
        report_generator: ReportGenerator,
    ) -> None:
        """Test complete data flow for game-level sources.

        Downloads from all game-level sources and generates report.
        Uses mock database for storage validation.
        """
        storage_stage = StorageStage(mock_db)
        game_sources = SourceRegistry.get_game_level_sources()
        report = DataFlowReport(game_id=fixture_game_id, season_id=fixture_season_id)

        # Download and persist each source
        for source in game_sources:
            download_result = await download_stage.download_source(
                source,
                game_id=fixture_game_id,
                config_overrides={"requests_per_second": 2.0},
            )

            storage_result = None
            if source.has_persist and download_result.success:
                storage_result = await storage_stage.persist_and_verify(
                    source, download_result
                )

            report.add_source_result(
                source_name=source.name,
                display_name=source.display_name,
                download_result=download_result,
                storage_result=storage_result,
            )

        report.mark_completed()

        # Generate and print report
        print("\n" + report_generator.generate(report))
        print("\n" + report_generator.generate_console_summary(report))

        # Assert success rate
        assert report.success_rate >= 80, (
            f"Success rate too low: {report.success_rate:.1f}%\n"
            f"Failed sources: {[s.source_name for s in report.get_failed_sources()]}"
        )
