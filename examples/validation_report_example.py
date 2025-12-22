"""Example script demonstrating comprehensive validation report generation.

This script shows how to create and display validation reports with:
- Console output with box drawing and colors
- JSON export for programmatic use
- Filtering by severity and source

Usage:
    python examples/validation_report_example.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from tests.integration.data_flow.reports import (
    ComprehensiveReportGenerator,
    ComprehensiveValidationReport,
    ValidationStageResult,
)

from nhl_api.validation.results import (
    ValidationSummary,
    make_failed,
    make_passed,
)


def create_sample_report() -> ComprehensiveValidationReport:
    """Create a sample validation report for demonstration."""
    # Create report for a game
    report = ComprehensiveValidationReport(
        game_id=2024020500,
        season_id=20242025,
        test_id="demo_report",
        generated_at=datetime.now(UTC),
    )

    # Add boxscore validation results
    boxscore_results = [
        make_passed(
            "boxscore_points_sum", "boxscore", "All player points = goals + assists"
        ),
        make_passed("boxscore_shots_valid", "boxscore", "All shots >= goals"),
        make_passed(
            "boxscore_team_goals", "boxscore", "Team goals = sum of player goals"
        ),
        make_failed(
            "boxscore_faceoff_pct",
            "boxscore",
            "Faceoff percentage out of range: 125.5%",
            severity="error",
            details={"player": "Matthews", "faceoff_pct": 125.5},
        ),
    ]
    boxscore_summary = ValidationSummary.from_results(
        source_type="boxscore",
        entity_id="2024020500",
        results=boxscore_results,
    )
    report.add_internal_consistency_result("boxscore", boxscore_summary)

    # Add play-by-play validation results
    pbp_results = [
        make_passed("pbp_assists_count", "pbp", "All goal events have 0-2 assists"),
        make_passed("pbp_time_ranges", "pbp", "All events within valid time ranges"),
        make_passed("pbp_chronological", "pbp", "Events in chronological order"),
        make_failed(
            "pbp_score_monotonic",
            "pbp",
            "Score decreased: Period 2, 14:30 (from 3-2 to 2-2)",
            severity="error",
            details={"period": 2, "time": "14:30", "from": "3-2", "to": "2-2"},
        ),
        make_failed(
            "pbp_shot_distance",
            "pbp",
            "Shot distance suspiciously high: 250 feet",
            severity="warning",
            details={"event_idx": 142, "distance": 250},
        ),
    ]
    pbp_summary = ValidationSummary.from_results(
        source_type="pbp",
        entity_id="2024020500",
        results=pbp_results,
    )
    report.add_internal_consistency_result("pbp", pbp_summary)

    # Add shift chart validation results
    shifts_results = [
        make_passed(
            "shifts_duration", "shifts", "All shift durations match time difference"
        ),
        make_passed(
            "shifts_no_overlap", "shifts", "No overlapping shifts for same player"
        ),
        make_passed("shifts_sequential", "shifts", "Shift numbers are sequential"),
    ]
    shifts_summary = ValidationSummary.from_results(
        source_type="shifts",
        entity_id="2024020500",
        results=shifts_results,
    )
    report.add_internal_consistency_result("shifts", shifts_summary)

    # Add cross-source validation (JSON vs JSON)
    report.json_cross_validation = ValidationStageResult(
        stage_name="JSON Cross-Validation",
        total_checks=8,
        passed=7,
        failed=1,
        warnings=0,
        discrepancies=(
            make_failed(
                "goals_pbp_boxscore",
                "cross_source",
                "PBP goal count (5) != Boxscore total goals (4)",
                severity="error",
                details={"pbp_goals": 5, "boxscore_goals": 4},
            ),
        ),
    )

    # Add cross-source validation (JSON vs HTML)
    report.json_html_validation = ValidationStageResult(
        stage_name="JSON vs HTML Validation",
        total_checks=12,
        passed=10,
        failed=0,
        warnings=2,
        discrepancies=(
            make_failed(
                "roster_name_mismatch",
                "cross_source",
                'Player name mismatch: "Mitch Marner" vs "Mitchell Marner"',
                severity="warning",
                details={"json_name": "Mitch Marner", "html_name": "Mitchell Marner"},
            ),
            make_failed(
                "roster_scratch_missing",
                "cross_source",
                "Scratch missing in JSON roster: John Smith (#44)",
                severity="warning",
                details={"player": "John Smith", "number": 44},
            ),
        ),
    )

    return report


def main() -> None:
    """Run the validation report example."""
    print("=" * 80)
    print("NHL API Validation Report Generator - Example")
    print("=" * 80)
    print()

    # Create sample report
    report = create_sample_report()

    # Generate and display console report
    generator = ComprehensiveReportGenerator(use_color=True, box_width=66)

    print("1. Full Report with Colors")
    print("-" * 80)
    console_output = generator.generate_console(report)
    print(console_output)
    print()

    print("2. Filter by Error Severity Only")
    print("-" * 80)
    errors_only = generator.generate_console(report, severity_filter="error")
    print(errors_only)
    print()

    print("3. Filter by Boxscore Source")
    print("-" * 80)
    boxscore_only = generator.generate_console(report, source_filter="boxscore")
    print(boxscore_only)
    print()

    print("4. JSON Export (first 500 chars)")
    print("-" * 80)
    json_output = generator.generate_json(report, pretty=True)
    print(json_output[:500] + "...")
    print()

    print("5. Summary Statistics")
    print("-" * 80)
    print(f"Total Checks: {report.total_checks}")
    print(f"Passed: {report.passed_checks}")
    print(f"Failed: {report.failed_checks}")
    print(f"Warnings: {report.warning_checks}")
    print(f"Pass Rate: {report.pass_rate:.1f}%")
    print()

    print("6. All Discrepancies")
    print("-" * 80)
    for i, disc in enumerate(report.get_all_discrepancies(), 1):
        print(f"{i}. [{disc.severity.upper()}] {disc.rule_name}")
        print(f"   {disc.message}")
        if disc.details:
            print(f"   Details: {disc.details}")
        print()


if __name__ == "__main__":
    main()
