"""Integration tests for cross-source validation with real data.

These tests download real game data and validate consistency across sources.
They require network access and are marked with `live` to skip in CI.

Run with: pytest tests/integration/data_flow/test_cross_source_validation.py -v --live
"""
# mypy: disable-error-code="arg-type,attr-defined"

from __future__ import annotations

import pytest

from nhl_api.validation import CrossSourceValidator

# Test game ID - a completed regular season game
TEST_GAME_ID = 2024020500


@pytest.mark.integration
@pytest.mark.data_validation
@pytest.mark.live
class TestCrossSourceValidationLive:
    """Live cross-source validation tests."""

    @pytest.fixture
    def validator(self) -> CrossSourceValidator:
        """Get a cross-source validator instance."""
        return CrossSourceValidator()

    @pytest.mark.asyncio
    async def test_pbp_vs_boxscore_goals(self, validator: CrossSourceValidator) -> None:
        """Verify real game has matching goal counts between PBP and Boxscore.

        This test downloads a real game's PBP and Boxscore data, then validates
        that the goal counts match across sources.
        """
        from nhl_api.downloaders.sources.nhl_json.boxscore import (
            BoxscoreDownloader,
            BoxscoreDownloaderConfig,
        )
        from nhl_api.downloaders.sources.nhl_json.play_by_play import (
            PlayByPlayDownloader,
            PlayByPlayDownloaderConfig,
        )
        from nhl_api.validation.rules.cross_source import validate_goals_pbp_vs_boxscore

        # Download boxscore
        box_config = BoxscoreDownloaderConfig(requests_per_second=10.0)
        async with BoxscoreDownloader(box_config) as box_downloader:
            box_result = await box_downloader.download_game(TEST_GAME_ID)
            assert box_result.success
            boxscore = box_result.data

        # Download PBP
        pbp_config = PlayByPlayDownloaderConfig(requests_per_second=10.0)
        async with PlayByPlayDownloader(pbp_config) as pbp_downloader:
            pbp_result = await pbp_downloader.download_game(TEST_GAME_ID)
            assert pbp_result.success
            pbp = pbp_result.data

        # Validate
        results = validate_goals_pbp_vs_boxscore(pbp, boxscore)

        # All goal validations should pass for a completed game
        assert len(results) == 2
        for result in results:
            assert result.passed, f"Failed: {result.message}"

    @pytest.mark.asyncio
    async def test_shifts_vs_boxscore_toi(
        self, validator: CrossSourceValidator
    ) -> None:
        """Verify real game has matching TOI between Shift Chart and Boxscore.

        This test downloads a real game's shift chart and boxscore data, then
        validates that player TOI values match within tolerance.
        """
        from nhl_api.downloaders.sources.nhl_json.boxscore import (
            BoxscoreDownloader,
            BoxscoreDownloaderConfig,
        )
        from nhl_api.downloaders.sources.nhl_stats.shift_charts import (
            ShiftChartsDownloader,
            ShiftChartsDownloaderConfig,
        )
        from nhl_api.validation.rules.cross_source import (
            validate_toi_shifts_vs_boxscore,
        )

        # Download boxscore
        box_config = BoxscoreDownloaderConfig(requests_per_second=10.0)
        async with BoxscoreDownloader(box_config) as box_downloader:
            box_result = await box_downloader.download_game(TEST_GAME_ID)
            assert box_result.success
            boxscore = box_result.data

        # Download shifts
        shift_config = ShiftChartsDownloaderConfig(requests_per_second=10.0)
        async with ShiftChartsDownloader(shift_config) as shift_downloader:
            shift_result = await shift_downloader.download_game(TEST_GAME_ID)
            assert shift_result.success
            shifts = shift_result.data

        # Validate
        results = validate_toi_shifts_vs_boxscore(shifts, boxscore)

        # Should have exactly one summary result
        assert len(results) == 1
        # TOI should mostly match - allow some warnings but not majority failures
        result = results[0]
        if not result.passed and result.details:
            mismatched_pct = result.details.get("players_mismatched", 0) / max(
                result.details.get("players_checked", 1), 1
            )
            assert mismatched_pct < 0.5, f"Too many TOI mismatches: {result.message}"

    @pytest.mark.asyncio
    async def test_full_cross_source_validation(
        self, validator: CrossSourceValidator
    ) -> None:
        """Run full cross-source validation on a real game.

        Downloads all relevant sources and runs complete validation.
        """
        from nhl_api.downloaders.sources.nhl_json.boxscore import (
            BoxscoreDownloader,
            BoxscoreDownloaderConfig,
        )
        from nhl_api.downloaders.sources.nhl_json.play_by_play import (
            PlayByPlayDownloader,
            PlayByPlayDownloaderConfig,
        )
        from nhl_api.downloaders.sources.nhl_stats.shift_charts import (
            ShiftChartsDownloader,
            ShiftChartsDownloaderConfig,
        )

        # Download all sources
        box_config = BoxscoreDownloaderConfig(requests_per_second=10.0)
        async with BoxscoreDownloader(box_config) as box_downloader:
            box_result = await box_downloader.download_game(TEST_GAME_ID)
            assert box_result.success
            boxscore = box_result.data

        pbp_config = PlayByPlayDownloaderConfig(requests_per_second=10.0)
        async with PlayByPlayDownloader(pbp_config) as pbp_downloader:
            pbp_result = await pbp_downloader.download_game(TEST_GAME_ID)
            assert pbp_result.success
            pbp = pbp_result.data

        shift_config = ShiftChartsDownloaderConfig(requests_per_second=10.0)
        async with ShiftChartsDownloader(shift_config) as shift_downloader:
            shift_result = await shift_downloader.download_game(TEST_GAME_ID)
            assert shift_result.success
            shifts = shift_result.data

        # Run full validation
        results = validator.validate_all(
            pbp=pbp,
            boxscore=boxscore,
            shifts=shifts,
        )

        # Get summary
        summary = validator.get_summary(TEST_GAME_ID, results)

        # Should have run multiple checks
        assert summary.total_checks > 0

        # Calculate pass rate
        pass_rate = summary.passed / max(summary.total_checks, 1)

        # Real data should have high consistency (>80% pass rate)
        assert pass_rate >= 0.8, (
            f"Cross-source validation pass rate too low: {pass_rate:.1%} "
            f"({summary.passed}/{summary.total_checks})"
        )


@pytest.mark.integration
@pytest.mark.data_validation
class TestCrossSourceValidationUnit:
    """Non-live integration tests for cross-source validation infrastructure."""

    def test_validator_instantiation(self) -> None:
        """Verify CrossSourceValidator can be instantiated."""
        validator = CrossSourceValidator()
        assert validator is not None

    def test_validator_has_expected_methods(self) -> None:
        """Verify CrossSourceValidator has all expected methods."""
        validator = CrossSourceValidator()

        assert hasattr(validator, "validate_pbp_vs_boxscore")
        assert hasattr(validator, "validate_shifts_vs_boxscore")
        assert hasattr(validator, "validate_schedule_vs_boxscore")
        assert hasattr(validator, "validate_all")
        assert hasattr(validator, "get_summary")

    def test_validator_imports(self) -> None:
        """Verify all cross-source validation functions can be imported."""
        from nhl_api.validation.rules.cross_source import (
            validate_final_score_schedule_vs_boxscore,
            validate_goals_pbp_vs_boxscore,
            validate_shift_count_shifts_vs_boxscore,
            validate_shots_pbp_vs_boxscore,
            validate_toi_shifts_vs_boxscore,
        )

        # All should be callable
        assert callable(validate_goals_pbp_vs_boxscore)
        assert callable(validate_shots_pbp_vs_boxscore)
        assert callable(validate_toi_shifts_vs_boxscore)
        assert callable(validate_shift_count_shifts_vs_boxscore)
        assert callable(validate_final_score_schedule_vs_boxscore)
