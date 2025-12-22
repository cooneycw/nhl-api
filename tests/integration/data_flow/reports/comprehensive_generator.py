"""Comprehensive validation report generator with enhanced console output.

This module generates detailed validation reports across all stages with:
- Fancy box drawing for console output
- Color-coded results (green/yellow/red)
- JSON export for programmatic use
- Filtering by stage, source, and severity
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from tests.integration.data_flow.reports.enhanced_models import (
        ComprehensiveValidationReport,
    )

# Box drawing characters (UTF-8)
BOX_TL = "╔"  # Top-left
BOX_TR = "╗"  # Top-right
BOX_BL = "╚"  # Bottom-left
BOX_BR = "╝"  # Bottom-right
BOX_H = "═"  # Horizontal
BOX_V = "║"  # Vertical
BOX_ML = "╠"  # Middle-left
BOX_MR = "╣"  # Middle-right
BOX_MC = "╬"  # Middle-center

# ANSI color codes
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


SeverityFilter = Literal["error", "warning", "info", "all"]


class ComprehensiveReportGenerator:
    """Generator for comprehensive validation reports.

    Produces both console-friendly output with box drawing and
    JSON exports for programmatic use.

    Example:
        generator = ComprehensiveReportGenerator()
        console_output = generator.generate_console(report)
        print(console_output)

        json_output = generator.generate_json(report)
        with open("report.json", "w") as f:
            f.write(json_output)
    """

    def __init__(self, *, use_color: bool = True, box_width: int = 66) -> None:
        """Initialize report generator.

        Args:
            use_color: Whether to use ANSI color codes
            box_width: Width of console boxes (default 66 for 80-char terminals)
        """
        self.use_color = use_color
        self.box_width = box_width

    def generate_console(
        self,
        report: ComprehensiveValidationReport,
        *,
        severity_filter: SeverityFilter = "all",
        source_filter: str | None = None,
    ) -> str:
        """Generate console-friendly report with box drawing.

        Args:
            report: ComprehensiveValidationReport with all validation results
            severity_filter: Filter discrepancies by severity ("error", "warning", "info", "all")
            source_filter: Optional source name to filter by

        Returns:
            Formatted console output string
        """
        lines: list[str] = []

        # Header
        lines.append(self._box_top())
        lines.append(self._box_line("NHL API Data Validation Report", center=True))

        # Game info
        game_str = f"Game: {report.game_id}"
        if report.season_id:
            game_str += f" (Season: {report.season_id})"
        lines.append(self._box_line(game_str, center=True))
        lines.append(self._box_separator())

        # Download stage (if available)
        if report.data_flow_report:
            lines.extend(self._download_stage_section(report))

        # Storage stage (if available)
        if report.data_flow_report:
            lines.extend(self._storage_stage_section(report))

        # View stage (if available)
        if report.view_stage:
            lines.extend(self._view_stage_section(report))

        # Internal consistency validation
        if report.internal_consistency:
            lines.extend(self._internal_consistency_section(report))

        # Cross-source reconciliation (JSON vs JSON)
        if report.json_cross_validation:
            lines.extend(self._json_cross_validation_section(report))

        # Cross-source reconciliation (JSON vs HTML)
        if report.json_html_validation:
            lines.extend(self._json_html_validation_section(report))

        # Overall summary
        lines.extend(self._overall_summary_section(report))

        # Discrepancies (if any)
        discrepancies = self._filter_discrepancies(
            report, severity_filter, source_filter
        )
        if discrepancies:
            lines.extend(self._discrepancies_section(discrepancies))

        lines.append(self._box_bottom())

        return "\n".join(lines)

    def generate_json(
        self,
        report: ComprehensiveValidationReport,
        *,
        pretty: bool = True,
    ) -> str:
        """Generate JSON report for programmatic use.

        Args:
            report: ComprehensiveValidationReport with all validation results
            pretty: Whether to pretty-print JSON (default True)

        Returns:
            JSON string
        """
        data: dict[str, Any] = {
            "game_id": report.game_id,
            "season_id": report.season_id,
            "test_id": report.test_id,
            "generated_at": report.generated_at.isoformat(),
            "summary": {
                "total_checks": report.total_checks,
                "passed": report.passed_checks,
                "failed": report.failed_checks,
                "warnings": report.warning_checks,
                "pass_rate": round(report.pass_rate, 2),
            },
            "stages": {},
            "discrepancies": [],
        }

        # Download stage
        if report.data_flow_report:
            data["stages"]["download"] = {
                "total": report.data_flow_report.download_stats.total,
                "passed": report.data_flow_report.download_stats.passed,
                "failed": report.data_flow_report.download_stats.failed,
                "success_rate": round(
                    report.data_flow_report.download_stats.success_rate, 1
                ),
            }

        # Storage stage
        if report.data_flow_report:
            data["stages"]["storage"] = {
                "total": report.data_flow_report.storage_stats.total,
                "passed": report.data_flow_report.storage_stats.passed,
                "failed": report.data_flow_report.storage_stats.failed,
                "skipped": report.data_flow_report.storage_stats.skipped,
                "success_rate": round(
                    report.data_flow_report.storage_stats.success_rate, 1
                ),
            }

        # Internal consistency
        if report.internal_consistency:
            data["stages"]["internal_consistency"] = {}
            for source_name, summary in report.internal_consistency.items():
                data["stages"]["internal_consistency"][source_name] = {
                    "total_checks": summary.total_checks,
                    "passed": summary.passed,
                    "failed": summary.failed,
                    "warnings": summary.warnings,
                }

        # Cross-source validation
        if report.json_cross_validation:
            data["stages"]["json_cross_validation"] = {
                "total_checks": report.json_cross_validation.total_checks,
                "passed": report.json_cross_validation.passed,
                "failed": report.json_cross_validation.failed,
                "warnings": report.json_cross_validation.warnings,
                "pass_rate": round(report.json_cross_validation.pass_rate, 1),
            }

        if report.json_html_validation:
            data["stages"]["json_html_validation"] = {
                "total_checks": report.json_html_validation.total_checks,
                "passed": report.json_html_validation.passed,
                "failed": report.json_html_validation.failed,
                "warnings": report.json_html_validation.warnings,
                "pass_rate": round(report.json_html_validation.pass_rate, 1),
            }

        # Discrepancies
        for disc in report.get_all_discrepancies():
            data["discrepancies"].append(
                {
                    "rule_name": disc.rule_name,
                    "source_type": disc.source_type,
                    "severity": disc.severity,
                    "message": disc.message,
                    "details": disc.details,
                    "entity_id": disc.entity_id,
                }
            )

        if pretty:
            return json.dumps(data, indent=2)
        return json.dumps(data)

    # =================================================================
    # Box Drawing Helpers
    # =================================================================

    def _box_top(self) -> str:
        """Generate box top border."""
        return f"{BOX_TL}{BOX_H * (self.box_width - 2)}{BOX_TR}"

    def _box_bottom(self) -> str:
        """Generate box bottom border."""
        return f"{BOX_BL}{BOX_H * (self.box_width - 2)}{BOX_BR}"

    def _box_separator(self) -> str:
        """Generate box horizontal separator."""
        return f"{BOX_ML}{BOX_H * (self.box_width - 2)}{BOX_MR}"

    def _box_line(self, text: str, *, center: bool = False) -> str:
        """Generate a box line with text.

        Args:
            text: Text to display
            center: Whether to center the text

        Returns:
            Formatted box line
        """
        content_width = self.box_width - 4  # 2 for borders, 2 for padding
        if center:
            text = text.center(content_width)
        else:
            text = text.ljust(content_width)
        return f"{BOX_V} {text} {BOX_V}"

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled.

        Args:
            text: Text to colorize
            color: Color code

        Returns:
            Colorized text (or original if colors disabled)
        """
        if not self.use_color:
            return text
        return f"{color}{text}{COLOR_RESET}"

    def _status_symbol(self, passed: bool, *, failed: bool = False) -> str:
        """Get status symbol with color.

        Args:
            passed: Whether check passed
            failed: Whether check failed (for warnings vs errors)

        Returns:
            Colored status symbol
        """
        if passed:
            return self._colorize("✓", COLOR_GREEN)
        if failed:
            return self._colorize("✗", COLOR_RED)
        return self._colorize("⚠", COLOR_YELLOW)

    # =================================================================
    # Section Generators
    # =================================================================

    def _download_stage_section(
        self, report: ComprehensiveValidationReport
    ) -> list[str]:
        """Generate download stage section."""
        lines: list[str] = []
        if not report.data_flow_report:
            return lines

        stats = report.data_flow_report.download_stats
        status = self._status_symbol(stats.success_rate >= 90)

        lines.append(
            self._box_line(
                f"DOWNLOAD STAGE:     {stats.passed}/{stats.total} sources OK     {status}"
            )
        )
        return lines

    def _storage_stage_section(
        self, report: ComprehensiveValidationReport
    ) -> list[str]:
        """Generate storage stage section."""
        lines: list[str] = []
        if not report.data_flow_report:
            return lines

        stats = report.data_flow_report.storage_stats
        status = self._status_symbol(stats.success_rate >= 90)

        lines.append(
            self._box_line(
                f"STORAGE STAGE:      {stats.passed}/{stats.total} tables populated         {status}"
            )
        )
        return lines

    def _view_stage_section(self, report: ComprehensiveValidationReport) -> list[str]:
        """Generate view stage section."""
        lines: list[str] = []
        if not report.view_stage:
            return lines

        stage = report.view_stage
        status = self._status_symbol(stage.pass_rate >= 90)

        lines.append(
            self._box_line(
                f"VIEW STAGE:         {stage.passed}/{stage.total_checks} endpoints accessible    {status}"
            )
        )
        return lines

    def _internal_consistency_section(
        self, report: ComprehensiveValidationReport
    ) -> list[str]:
        """Generate internal consistency validation section."""
        lines: list[str] = []
        lines.append(self._box_separator())
        lines.append(self._box_line("INTERNAL RECONCILIATION:"))

        for source_name, summary in report.internal_consistency.items():
            status = self._status_symbol(summary.failed == 0, failed=summary.failed > 0)
            lines.append(
                self._box_line(
                    f"  • {source_name:25} {summary.passed}/{summary.total_checks} checks passed      {status}"
                )
            )

        return lines

    def _json_cross_validation_section(
        self, report: ComprehensiveValidationReport
    ) -> list[str]:
        """Generate JSON cross-validation section."""
        lines: list[str] = []
        if not report.json_cross_validation:
            return lines

        lines.append(self._box_separator())
        lines.append(self._box_line("CROSS-SOURCE RECONCILIATION (JSON vs JSON):"))

        stage = report.json_cross_validation
        status = self._status_symbol(stage.failed == 0, failed=stage.failed > 0)

        lines.append(
            self._box_line(
                f"  • Goals (PBP vs Boxscore):  {self._format_check_result(stage)} {status}"
            )
        )

        return lines

    def _json_html_validation_section(
        self, report: ComprehensiveValidationReport
    ) -> list[str]:
        """Generate JSON vs HTML validation section."""
        lines: list[str] = []
        if not report.json_html_validation:
            return lines

        lines.append(self._box_separator())
        lines.append(self._box_line("CROSS-SOURCE RECONCILIATION (JSON vs HTML):"))

        stage = report.json_html_validation
        status = self._status_symbol(stage.failed == 0, failed=stage.failed > 0)

        lines.append(
            self._box_line(
                f"  • Goals (PBP vs GS):        {self._format_check_result(stage)} {status}"
            )
        )

        return lines

    def _overall_summary_section(
        self, report: ComprehensiveValidationReport
    ) -> list[str]:
        """Generate overall summary section."""
        lines: list[str] = []
        lines.append(self._box_separator())

        overall_status = self._colorize(
            f"{report.passed_checks}/{report.total_checks} checks passed ({report.pass_rate:.1f}%)",
            COLOR_GREEN
            if report.pass_rate >= 90
            else COLOR_YELLOW
            if report.pass_rate >= 70
            else COLOR_RED,
        )
        lines.append(self._box_line(f"OVERALL:  {overall_status}"))

        return lines

    def _discrepancies_section(self, discrepancies: list[Any]) -> list[str]:
        """Generate discrepancies section.

        Args:
            discrepancies: List of validation failures

        Returns:
            Formatted section lines
        """
        lines: list[str] = []
        lines.append(self._box_separator())
        lines.append(self._box_line(f"DISCREPANCIES ({len(discrepancies)} found):"))

        for disc in discrepancies[:10]:  # Limit to first 10
            severity_color = COLOR_RED if disc.severity == "error" else COLOR_YELLOW
            severity_str = self._colorize(disc.severity.upper(), severity_color)
            lines.append(self._box_line(f"  [{severity_str}] {disc.rule_name}"))
            lines.append(self._box_line(f"    {disc.message}"))

        if len(discrepancies) > 10:
            lines.append(self._box_line(f"    ... and {len(discrepancies) - 10} more"))

        return lines

    def _format_check_result(self, stage: Any) -> str:
        """Format a check result (e.g., 'PASS' or 'FAIL (5/10)')."""
        if stage.failed == 0:
            return "PASS"
        return f"FAIL ({stage.failed}/{stage.total_checks})"

    def _filter_discrepancies(
        self,
        report: ComprehensiveValidationReport,
        severity_filter: SeverityFilter,
        source_filter: str | None,
    ) -> list[Any]:
        """Filter discrepancies by severity and source.

        Args:
            report: ComprehensiveValidationReport
            severity_filter: Severity level to filter by
            source_filter: Optional source name to filter by

        Returns:
            Filtered list of discrepancies
        """
        discrepancies = report.get_all_discrepancies()

        # Filter by severity
        if severity_filter != "all":
            discrepancies = [d for d in discrepancies if d.severity == severity_filter]

        # Filter by source
        if source_filter:
            discrepancies = [d for d in discrepancies if d.source_type == source_filter]

        return discrepancies
