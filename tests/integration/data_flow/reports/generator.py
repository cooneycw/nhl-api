"""Report generator for data flow tests.

This module generates human-readable reports from data flow test results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.integration.data_flow.reports.models import DataFlowReport


class ReportGenerator:
    """Generator for data flow test reports.

    Produces markdown-formatted reports from test results.
    """

    def generate(self, report: DataFlowReport) -> str:
        """Generate a complete markdown report.

        Args:
            report: DataFlowReport with test results

        Returns:
            Markdown-formatted report string
        """
        lines = [
            self._header(report),
            self._summary(report),
            self._download_section(report),
            self._storage_section(report),
            self._source_details(report),
        ]
        return "\n".join(lines)

    def _header(self, report: DataFlowReport) -> str:
        """Generate report header."""
        lines = [
            "# Data Flow Test Report",
            "",
            f"**Test ID:** {report.test_id}",
        ]
        if report.game_id:
            lines.append(f"**Game ID:** {report.game_id}")
        if report.season_id:
            lines.append(f"**Season ID:** {report.season_id}")
        lines.append(f"**Duration:** {report.duration_seconds:.2f}s")
        lines.append("")
        return "\n".join(lines)

    def _summary(self, report: DataFlowReport) -> str:
        """Generate summary section."""
        lines = [
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Sources | {report.total_sources} |",
            f"| Passed | {report.passed_sources} |",
            f"| Failed | {report.failed_sources} |",
            f"| Success Rate | {report.success_rate:.1f}% |",
            "",
        ]
        return "\n".join(lines)

    def _download_section(self, report: DataFlowReport) -> str:
        """Generate download stage section."""
        stats = report.download_stats
        lines = [
            "## Download Stage",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total | {stats.total} |",
            f"| Passed | {stats.passed} |",
            f"| Failed | {stats.failed} |",
            f"| Success Rate | {stats.success_rate:.1f}% |",
            f"| Total Time | {stats.total_time_ms:.1f}ms |",
            "",
        ]

        # Add failed sources if any
        failed = [r for r in report.download_results.values() if not r.success]
        if failed:
            lines.append("### Failed Downloads")
            lines.append("")
            lines.append("| Source | Error |")
            lines.append("|--------|-------|")
            for r in failed:
                error = r.error or "Unknown error"
                # Truncate long errors
                if len(error) > 50:
                    error = error[:47] + "..."
                lines.append(f"| {r.source_name} | {error} |")
            lines.append("")

        return "\n".join(lines)

    def _storage_section(self, report: DataFlowReport) -> str:
        """Generate storage stage section."""
        stats = report.storage_stats
        lines = [
            "## Storage Stage",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total | {stats.total} |",
            f"| Passed | {stats.passed} |",
            f"| Failed | {stats.failed} |",
            f"| Skipped | {stats.skipped} |",
            f"| Success Rate | {stats.success_rate:.1f}% |",
            f"| Total Time | {stats.total_time_ms:.1f}ms |",
            "",
        ]

        # Add table population summary
        all_tables: dict[str, int] = {}
        for r in report.storage_results.values():
            for table, count in r.tables_populated.items():
                all_tables[table] = all_tables.get(table, 0) + count

        if all_tables:
            lines.append("### Tables Populated")
            lines.append("")
            lines.append("| Table | Rows Added |")
            lines.append("|-------|------------|")
            for table, count in sorted(all_tables.items()):
                lines.append(f"| {table} | {count} |")
            lines.append("")

        return "\n".join(lines)

    def _source_details(self, report: DataFlowReport) -> str:
        """Generate detailed source results section."""
        lines = [
            "## Source Details",
            "",
            "| Source | Download | Storage | Rows | Time (ms) |",
            "|--------|----------|---------|------|-----------|",
        ]

        for source in sorted(
            report.source_results.values(), key=lambda x: x.source_name
        ):
            dl_status = "✅" if source.download_success else "❌"
            if source.storage_success is None:
                st_status = "N/A"
            elif source.storage_success:
                st_status = "✅"
            else:
                st_status = "❌"

            lines.append(
                f"| {source.display_name} | {dl_status} | {st_status} | "
                f"{source.rows_affected} | {source.total_time_ms:.1f} |"
            )

        lines.append("")

        # Add error details for failed sources
        failed = report.get_failed_sources()
        if failed:
            lines.append("### Errors")
            lines.append("")
            for source in failed:
                lines.append(f"**{source.display_name}:** {source.error}")
                lines.append("")

        return "\n".join(lines)

    def generate_console_summary(self, report: DataFlowReport) -> str:
        """Generate a concise console-friendly summary.

        Args:
            report: DataFlowReport with test results

        Returns:
            Concise summary string for console output
        """
        status = "PASSED" if report.success_rate >= 80 else "FAILED"
        lines = [
            f"Data Flow Test {status}",
            f"  Sources: {report.passed_sources}/{report.total_sources} passed "
            f"({report.success_rate:.1f}%)",
            f"  Duration: {report.duration_seconds:.2f}s",
        ]

        failed = report.get_failed_sources()
        if failed:
            lines.append("  Failed:")
            for source in failed[:5]:  # Limit to first 5
                error = source.error or "Unknown"
                if len(error) > 40:
                    error = error[:37] + "..."
                lines.append(f"    - {source.display_name}: {error}")
            if len(failed) > 5:
                lines.append(f"    ... and {len(failed) - 5} more")

        return "\n".join(lines)
