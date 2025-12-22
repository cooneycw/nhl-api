"""Data models for data flow test reports.

This module defines the data structures used to capture and
represent test results across all stages of data flow testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from tests.integration.data_flow.stages.download import DownloadStageResult
    from tests.integration.data_flow.stages.storage import StorageStageResult


@dataclass
class StageStats:
    """Statistics for a single test stage.

    Attributes:
        total: Total number of sources tested
        passed: Number of successful tests
        failed: Number of failed tests
        skipped: Number of skipped tests
        total_time_ms: Total time for stage in milliseconds
    """

    total: int
    passed: int
    failed: int
    skipped: int = 0
    total_time_ms: float = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


@dataclass
class SourceResult:
    """Combined result for a single source across all stages.

    Attributes:
        source_name: Identifier of the data source
        display_name: Human-readable name
        download_success: Whether download succeeded
        download_time_ms: Download duration
        storage_success: Whether storage succeeded (None if N/A)
        storage_time_ms: Storage duration
        rows_affected: Number of rows persisted
        tables_populated: Mapping of tables to row counts
        error: Combined error message if any stage failed
    """

    source_name: str
    display_name: str
    download_success: bool
    download_time_ms: float
    storage_success: bool | None = None
    storage_time_ms: float = 0
    rows_affected: int = 0
    tables_populated: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    @property
    def overall_success(self) -> bool:
        """Check if all stages succeeded."""
        if not self.download_success:
            return False
        if self.storage_success is not None and not self.storage_success:
            return False
        return True

    @property
    def total_time_ms(self) -> float:
        """Total time across all stages."""
        return self.download_time_ms + self.storage_time_ms


@dataclass
class DataFlowReport:
    """Complete data flow test report.

    This is the main report object that aggregates all test results
    and provides summary statistics and report generation.

    Attributes:
        test_id: Unique identifier for this test run
        game_id: Game ID tested (if applicable)
        season_id: Season ID tested
        started_at: Timestamp when test started
        completed_at: Timestamp when test completed (None if in progress)
        source_results: Individual results per source
        download_results: Raw download stage results
        storage_results: Raw storage stage results
    """

    test_id: str = field(default_factory=lambda: str(uuid4())[:8])
    game_id: int | None = None
    season_id: int | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    source_results: dict[str, SourceResult] = field(default_factory=dict)
    download_results: dict[str, DownloadStageResult] = field(default_factory=dict)
    storage_results: dict[str, StorageStageResult] = field(default_factory=dict)

    @property
    def total_sources(self) -> int:
        """Total number of sources tested."""
        return len(self.source_results)

    @property
    def passed_sources(self) -> int:
        """Number of sources that passed all stages."""
        return sum(1 for r in self.source_results.values() if r.overall_success)

    @property
    def failed_sources(self) -> int:
        """Number of sources that failed any stage."""
        return self.total_sources - self.passed_sources

    @property
    def success_rate(self) -> float:
        """Overall success rate as percentage."""
        if self.total_sources == 0:
            return 0.0
        return (self.passed_sources / self.total_sources) * 100

    @property
    def duration_seconds(self) -> float:
        """Test duration in seconds."""
        if self.completed_at is None:
            end = datetime.now(UTC)
        else:
            end = self.completed_at
        return (end - self.started_at).total_seconds()

    @property
    def download_stats(self) -> StageStats:
        """Get statistics for download stage."""
        results = self.download_results.values()
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        total_time = sum(r.download_time_ms for r in results)
        return StageStats(
            total=len(results),
            passed=passed,
            failed=failed,
            total_time_ms=total_time,
        )

    @property
    def storage_stats(self) -> StageStats:
        """Get statistics for storage stage."""
        results = self.storage_results.values()
        passed = sum(1 for r in results if r.success)
        failed = sum(
            1 for r in results if not r.success and r.error != "No persist method"
        )
        skipped = sum(1 for r in results if r.error == "No persist method")
        total_time = sum(r.persist_time_ms for r in results)
        return StageStats(
            total=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            total_time_ms=total_time,
        )

    def get_failed_sources(self) -> list[SourceResult]:
        """Get list of sources that failed any stage."""
        return [r for r in self.source_results.values() if not r.overall_success]

    def get_passed_sources(self) -> list[SourceResult]:
        """Get list of sources that passed all stages."""
        return [r for r in self.source_results.values() if r.overall_success]

    def mark_completed(self) -> None:
        """Mark the test as completed with current timestamp."""
        self.completed_at = datetime.now(UTC)

    def add_source_result(
        self,
        source_name: str,
        display_name: str,
        download_result: DownloadStageResult,
        storage_result: StorageStageResult | None = None,
    ) -> None:
        """Add a combined result for a source.

        Args:
            source_name: Source identifier
            display_name: Human-readable name
            download_result: Result from download stage
            storage_result: Result from storage stage (optional)
        """
        self.download_results[source_name] = download_result

        storage_success = None
        storage_time = 0.0
        rows_affected = 0
        tables_populated: dict[str, int] = {}
        error = download_result.error

        if storage_result is not None:
            self.storage_results[source_name] = storage_result
            storage_success = storage_result.success
            storage_time = storage_result.persist_time_ms
            rows_affected = storage_result.rows_affected
            tables_populated = storage_result.tables_populated
            if not storage_result.success and storage_result.error:
                if error:
                    error = f"{error}; {storage_result.error}"
                else:
                    error = storage_result.error

        self.source_results[source_name] = SourceResult(
            source_name=source_name,
            display_name=display_name,
            download_success=download_result.success,
            download_time_ms=download_result.download_time_ms,
            storage_success=storage_success,
            storage_time_ms=storage_time,
            rows_affected=rows_affected,
            tables_populated=tables_populated,
            error=error,
        )
