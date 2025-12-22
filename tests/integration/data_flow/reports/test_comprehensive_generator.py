"""Tests for comprehensive validation report generator.

Tests both console output generation and JSON export functionality.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nhl_api.validation.results import (
    ValidationSummary,
    make_failed,
    make_passed,
)
from tests.integration.data_flow.reports.comprehensive_generator import (
    ComprehensiveReportGenerator,
)
from tests.integration.data_flow.reports.enhanced_models import (
    ComprehensiveValidationReport,
    ValidationStageResult,
)


@pytest.fixture
def sample_validation_summary() -> ValidationSummary:
    """Create a sample validation summary for testing."""
    results = [
        make_passed("boxscore_points_sum", "boxscore", "Points = goals + assists"),
        make_passed("boxscore_shots_valid", "boxscore", "Shots >= goals"),
        make_failed(
            "boxscore_goals_sum",
            "boxscore",
            "Team goals (5) != sum of player goals (4)",
            severity="error",
            details={"team_goals": 5, "player_sum": 4},
        ),
    ]
    return ValidationSummary.from_results(
        source_type="boxscore", entity_id="2024020001", results=results
    )


@pytest.fixture
def sample_report(
    sample_validation_summary: ValidationSummary,
) -> ComprehensiveValidationReport:
    """Create a sample comprehensive report for testing."""
    report = ComprehensiveValidationReport(
        game_id=2024020001,
        season_id=20242025,
        test_id="test123",
        generated_at=datetime(2024, 12, 22, 10, 30, 0, tzinfo=UTC),
    )

    # Add internal consistency results
    report.add_internal_consistency_result("boxscore", sample_validation_summary)

    # Add cross-source validation results
    report.json_cross_validation = ValidationStageResult(
        stage_name="JSON Cross-Validation",
        total_checks=10,
        passed=9,
        failed=1,
        warnings=0,
        discrepancies=(
            make_failed(
                "goals_pbp_boxscore",
                "cross_source",
                "PBP goals (5) != Boxscore goals (4)",
            ),
        ),
    )

    return report


class TestComprehensiveReportGenerator:
    """Tests for ComprehensiveReportGenerator class."""

    def test_generator_initialization(self) -> None:
        """Test generator can be initialized with options."""
        gen = ComprehensiveReportGenerator(use_color=False, box_width=80)
        assert gen.use_color is False
        assert gen.box_width == 80

    def test_generator_defaults(self) -> None:
        """Test generator uses sensible defaults."""
        gen = ComprehensiveReportGenerator()
        assert gen.use_color is True
        assert gen.box_width == 66

    def test_generate_console_basic(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test basic console report generation."""
        gen = ComprehensiveReportGenerator(use_color=False)
        output = gen.generate_console(sample_report)

        # Check report structure
        assert "NHL API Data Validation Report" in output
        assert "Game: 2024020001" in output
        assert "Season: 20242025" in output
        assert "INTERNAL RECONCILIATION" in output
        assert "boxscore" in output

    def test_generate_console_with_colors(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test console report with ANSI colors."""
        gen = ComprehensiveReportGenerator(use_color=True)
        output = gen.generate_console(sample_report)

        # Check for ANSI color codes
        assert "\033[" in output  # Has ANSI codes

    def test_generate_console_without_colors(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test console report without colors."""
        gen = ComprehensiveReportGenerator(use_color=False)
        output = gen.generate_console(sample_report)

        # No ANSI codes
        assert "\033[" not in output

    def test_generate_console_with_box_drawing(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test console report uses box drawing characters."""
        gen = ComprehensiveReportGenerator(use_color=False)
        output = gen.generate_console(sample_report)

        # Check for box drawing characters
        assert "╔" in output  # Top-left
        assert "╗" in output  # Top-right
        assert "╚" in output  # Bottom-left
        assert "╝" in output  # Bottom-right
        assert "═" in output  # Horizontal
        assert "║" in output  # Vertical

    def test_generate_console_shows_discrepancies(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test console report includes discrepancies section."""
        gen = ComprehensiveReportGenerator(use_color=False)
        output = gen.generate_console(sample_report)

        assert "DISCREPANCIES" in output
        assert "boxscore_goals_sum" in output
        assert "Team goals (5) != sum of player goals (4)" in output

    def test_generate_console_filter_by_severity_error(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test filtering discrepancies by error severity."""
        gen = ComprehensiveReportGenerator(use_color=False)
        output = gen.generate_console(sample_report, severity_filter="error")

        assert "DISCREPANCIES" in output
        assert "boxscore_goals_sum" in output  # This is an error

    def test_generate_console_filter_by_severity_warning(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test filtering discrepancies by warning severity."""
        gen = ComprehensiveReportGenerator(use_color=False)
        output = gen.generate_console(sample_report, severity_filter="warning")

        # Should not show error-level discrepancies
        # (sample only has errors, so no discrepancies shown)
        if "DISCREPANCIES" in output:
            assert "(0 found)" in output or "boxscore_goals_sum" not in output

    def test_generate_console_filter_by_source(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test filtering discrepancies by source."""
        gen = ComprehensiveReportGenerator(use_color=False)
        output = gen.generate_console(sample_report, source_filter="boxscore")

        if "DISCREPANCIES" in output:
            assert "boxscore_goals_sum" in output

    def test_generate_json_basic(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test basic JSON report generation."""
        gen = ComprehensiveReportGenerator()
        output = gen.generate_json(sample_report, pretty=False)

        # Should be valid JSON
        import json

        data = json.loads(output)

        assert data["game_id"] == 2024020001
        assert data["season_id"] == 20242025
        assert data["test_id"] == "test123"
        assert "summary" in data
        assert "stages" in data
        assert "discrepancies" in data

    def test_generate_json_pretty(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test pretty-printed JSON generation."""
        gen = ComprehensiveReportGenerator()
        output = gen.generate_json(sample_report, pretty=True)

        # Pretty-printed should have indentation
        assert "  " in output or "\t" in output
        assert "\n" in output

    def test_generate_json_includes_summary(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test JSON includes summary statistics."""
        gen = ComprehensiveReportGenerator()
        output = gen.generate_json(sample_report)

        import json

        data = json.loads(output)

        assert "summary" in data
        assert "total_checks" in data["summary"]
        assert "passed" in data["summary"]
        assert "failed" in data["summary"]
        assert "warnings" in data["summary"]
        assert "pass_rate" in data["summary"]

    def test_generate_json_includes_stages(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test JSON includes stage-specific results."""
        gen = ComprehensiveReportGenerator()
        output = gen.generate_json(sample_report)

        import json

        data = json.loads(output)

        assert "stages" in data
        assert "internal_consistency" in data["stages"]
        assert "boxscore" in data["stages"]["internal_consistency"]

    def test_generate_json_includes_discrepancies(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test JSON includes all discrepancies."""
        gen = ComprehensiveReportGenerator()
        output = gen.generate_json(sample_report)

        import json

        data = json.loads(output)

        assert "discrepancies" in data
        assert len(data["discrepancies"]) > 0

        # Check discrepancy structure
        disc = data["discrepancies"][0]
        assert "rule_name" in disc
        assert "source_type" in disc
        assert "severity" in disc
        assert "message" in disc


class TestValidationStageResult:
    """Tests for ValidationStageResult dataclass."""

    def test_validation_stage_result_creation(self) -> None:
        """Test creating a validation stage result."""
        result = ValidationStageResult(
            stage_name="Test Stage",
            total_checks=10,
            passed=8,
            failed=1,
            warnings=1,
        )

        assert result.stage_name == "Test Stage"
        assert result.total_checks == 10
        assert result.passed == 8
        assert result.failed == 1
        assert result.warnings == 1

    def test_validation_stage_pass_rate(self) -> None:
        """Test pass rate calculation."""
        result = ValidationStageResult(
            stage_name="Test",
            total_checks=10,
            passed=8,
            failed=2,
            warnings=0,
        )

        assert result.pass_rate == 80.0

    def test_validation_stage_pass_rate_zero_checks(self) -> None:
        """Test pass rate when no checks performed."""
        result = ValidationStageResult(
            stage_name="Test",
            total_checks=0,
            passed=0,
            failed=0,
            warnings=0,
        )

        assert result.pass_rate == 0.0


class TestComprehensiveValidationReport:
    """Tests for ComprehensiveValidationReport dataclass."""

    def test_report_creation(self) -> None:
        """Test creating a comprehensive validation report."""
        report = ComprehensiveValidationReport(
            game_id=2024020001,
            season_id=20242025,
        )

        assert report.game_id == 2024020001
        assert report.season_id == 20242025
        assert report.test_id  # Auto-generated
        assert report.generated_at  # Auto-generated

    def test_report_total_checks(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test total checks aggregation."""
        # Sample has 3 internal consistency checks + 10 cross-validation checks
        assert sample_report.total_checks == 13

    def test_report_passed_checks(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test passed checks aggregation."""
        # 2 passed internal + 9 passed cross-validation = 11
        assert sample_report.passed_checks == 11

    def test_report_failed_checks(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test failed checks aggregation."""
        # 1 failed internal + 1 failed cross-validation = 2
        assert sample_report.failed_checks == 2

    def test_report_pass_rate(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test overall pass rate calculation."""
        # 11 passed / 13 total = ~84.6%
        assert 84 <= sample_report.pass_rate <= 85

    def test_report_get_all_discrepancies(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test getting all discrepancies."""
        discrepancies = sample_report.get_all_discrepancies()

        # Should have 2 failures (1 internal + 1 cross-source)
        assert len(discrepancies) == 2

    def test_report_get_discrepancies_by_severity(
        self, sample_report: ComprehensiveValidationReport
    ) -> None:
        """Test filtering discrepancies by severity."""
        errors = sample_report.get_discrepancies_by_severity("error")

        # All sample failures are errors
        assert len(errors) == 2

        warnings = sample_report.get_discrepancies_by_severity("warning")
        assert len(warnings) == 0
