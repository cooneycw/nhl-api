"""Storage stage validation for data flow tests.

This module handles persisting downloaded data to the database
and verifying that tables are properly populated.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService
    from tests.integration.data_flow.sources.registry import SourceDefinition
    from tests.integration.data_flow.stages.download import DownloadStageResult

logger = logging.getLogger(__name__)


@dataclass
class StorageStageResult:
    """Result of a storage operation for a single source.

    Attributes:
        source_name: Identifier of the data source
        success: Whether the persist completed successfully
        persist_time_ms: Time taken to persist in milliseconds
        rows_affected: Number of rows inserted/updated
        tables_populated: Mapping of table names to new row counts
        error: Error message if persist failed
        persisted_at: Timestamp when persist completed
    """

    source_name: str
    success: bool
    persist_time_ms: float
    rows_affected: int = 0
    tables_populated: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    persisted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_data(self) -> bool:
        """Check if any data was persisted."""
        return self.rows_affected > 0 or any(self.tables_populated.values())

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAILED"
        return (
            f"StorageStageResult({self.source_name}={status}, "
            f"rows={self.rows_affected}, {self.persist_time_ms:.1f}ms)"
        )


class MockDatabaseService:
    """Mock database service for testing without real database.

    This mock tracks persist calls and simulates table counts
    for validation purposes.
    """

    def __init__(self) -> None:
        """Initialize mock database service."""
        self._connected = True
        self._table_counts: dict[str, int] = {}
        self._persist_calls: list[dict[str, Any]] = []
        self._execute_count = 0

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected

    async def connect(self) -> None:
        """Simulate database connection."""
        self._connected = True

    async def disconnect(self) -> None:
        """Simulate database disconnection."""
        self._connected = False

    async def execute(self, query: str, *args: object, **kwargs: object) -> str:
        """Mock execute - tracks calls and returns success."""
        self._execute_count += 1
        self._persist_calls.append({"query": query[:100], "args_count": len(args)})
        return "INSERT 0 1"

    async def executemany(
        self, query: str, args: list[tuple[Any, ...]], **kwargs: object
    ) -> None:
        """Mock executemany - tracks calls."""
        self._execute_count += len(args)
        self._persist_calls.append({"query": query[:100], "batch_size": len(args)})

    async def fetch(
        self, query: str, *args: object, **kwargs: object
    ) -> list[dict[str, Any]]:
        """Mock fetch - returns empty list."""
        return []

    async def fetchrow(
        self, query: str, *args: object, **kwargs: object
    ) -> dict[str, Any] | None:
        """Mock fetchrow - returns None."""
        return None

    async def fetchval(
        self, query: str, *args: object, column: int = 0, **kwargs: object
    ) -> Any:
        """Mock fetchval - returns simulated count for COUNT queries."""
        # Simulate row count for COUNT queries
        if "COUNT" in query.upper():
            return self._execute_count
        return 1

    async def table_exists(self, table_name: str, schema: str = "public") -> bool:
        """Mock table_exists - always returns True."""
        return True

    async def get_table_count(self, table_name: str) -> int:
        """Mock get_table_count - returns tracked count."""
        return self._table_counts.get(table_name, 0)

    def set_table_count(self, table_name: str, count: int) -> None:
        """Set simulated table count for testing."""
        self._table_counts[table_name] = count

    def get_persist_calls(self) -> list[dict[str, Any]]:
        """Get list of persist calls made."""
        return self._persist_calls

    def reset(self) -> None:
        """Reset mock state."""
        self._persist_calls.clear()
        self._table_counts.clear()
        self._execute_count = 0


class StorageStage:
    """Storage stage for data flow testing.

    Handles persisting downloaded data to the database and
    verifying table population.
    """

    def __init__(self, db: DatabaseService | MockDatabaseService) -> None:
        """Initialize storage stage.

        Args:
            db: Database service (real or mock)
        """
        self.db = db

    async def _get_table_counts(self, tables: tuple[str, ...]) -> dict[str, int]:
        """Get current row counts for specified tables.

        Args:
            tables: Tuple of table names

        Returns:
            Dictionary mapping table names to row counts
        """
        counts: dict[str, int] = {}
        for table in tables:
            try:
                count = await self.db.get_table_count(table)
                counts[table] = count
            except Exception as e:
                logger.warning(f"Failed to get count for {table}: {e}")
                counts[table] = 0
        return counts

    async def persist_and_verify(
        self,
        source: SourceDefinition,
        download_result: DownloadStageResult,
    ) -> StorageStageResult:
        """Persist downloaded data and verify storage.

        Args:
            source: Source definition with persist info
            download_result: Result from download stage

        Returns:
            StorageStageResult with outcome
        """
        # Skip if source doesn't have persist
        if not source.has_persist:
            return StorageStageResult(
                source_name=source.name,
                success=True,
                persist_time_ms=0,
                rows_affected=0,
                tables_populated={},
                error=None,
            )

        # Skip if download failed
        if not download_result.success or download_result.data is None:
            return StorageStageResult(
                source_name=source.name,
                success=False,
                persist_time_ms=0,
                rows_affected=0,
                tables_populated={},
                error=f"Skipped: download failed - {download_result.error}",
            )

        start_time = time.perf_counter()

        try:
            # Get counts before persist
            before_counts = await self._get_table_counts(source.target_tables)

            # Create downloader and call persist
            downloader = source.create_downloader()

            # Call persist method (assumes it exists based on has_persist)
            if hasattr(downloader, "persist"):
                rows = await downloader.persist(self.db, [download_result.data])
            else:
                rows = 0

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Get counts after persist
            after_counts = await self._get_table_counts(source.target_tables)

            # Calculate differences
            tables_populated = {
                table: after_counts[table] - before_counts[table]
                for table in source.target_tables
            }

            return StorageStageResult(
                source_name=source.name,
                success=True,
                persist_time_ms=elapsed_ms,
                rows_affected=rows if isinstance(rows, int) else 0,
                tables_populated=tables_populated,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(f"Persist failed for {source.name}: {e}")

            return StorageStageResult(
                source_name=source.name,
                success=False,
                persist_time_ms=elapsed_ms,
                error=str(e),
            )

    async def persist_all(
        self,
        sources: list[SourceDefinition],
        download_results: dict[str, DownloadStageResult],
    ) -> dict[str, StorageStageResult]:
        """Persist all downloaded data.

        Args:
            sources: List of source definitions
            download_results: Results from download stage

        Returns:
            Dictionary mapping source names to storage results
        """
        results: dict[str, StorageStageResult] = {}

        for source in sources:
            if not source.has_persist:
                results[source.name] = StorageStageResult(
                    source_name=source.name,
                    success=True,
                    persist_time_ms=0,
                    error="No persist method",
                )
                continue

            download_result = download_results.get(source.name)
            if download_result is None:
                results[source.name] = StorageStageResult(
                    source_name=source.name,
                    success=False,
                    persist_time_ms=0,
                    error="No download result",
                )
                continue

            result = await self.persist_and_verify(source, download_result)
            results[source.name] = result

            logger.info(
                f"Persisted {source.name}: "
                f"{'OK' if result.success else 'FAILED'} "
                f"(rows={result.rows_affected}, {result.persist_time_ms:.1f}ms)"
            )

        return results

    @staticmethod
    def summarize_results(
        results: dict[str, StorageStageResult],
    ) -> dict[str, Any]:
        """Generate summary statistics for storage results.

        Args:
            results: Dictionary of storage results

        Returns:
            Summary dictionary with counts and timing
        """
        total = len(results)
        passed = sum(1 for r in results.values() if r.success)
        failed = total - passed
        total_rows = sum(r.rows_affected for r in results.values())
        total_time_ms = sum(r.persist_time_ms for r in results.values())

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / total * 100) if total > 0 else 0,
            "total_rows": total_rows,
            "total_time_ms": total_time_ms,
            "failed_sources": [
                r.source_name for r in results.values() if not r.success
            ],
        }
