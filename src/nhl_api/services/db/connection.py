"""Database connection management with connection pooling.

This module provides async PostgreSQL connection management using asyncpg,
with automatic credential retrieval from AWS Secrets Manager.

Usage:
    from nhl_api.services.db import DatabaseService

    async with DatabaseService() as db:
        result = await db.fetchval("SELECT 1")

    # Or for long-running applications:
    db = DatabaseService()
    await db.connect()
    try:
        result = await db.fetchval("SELECT 1")
    finally:
        await db.disconnect()
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import asyncpg

from nhl_api.config.secrets import get_db_credentials

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when database operations fail."""

    pass


class DatabaseService:
    """Async PostgreSQL database service with connection pooling.

    Provides a high-level interface for database operations with:
    - Automatic connection pooling via asyncpg
    - Credential retrieval from AWS Secrets Manager
    - Context manager support for automatic cleanup
    - Transaction support

    Attributes:
        pool: The asyncpg connection pool (None until connect() is called).
        min_connections: Minimum pool size.
        max_connections: Maximum pool size.

    Example:
        >>> async with DatabaseService() as db:
        ...     count = await db.fetchval("SELECT COUNT(*) FROM players")
        ...     print(f"Players: {count}")
    """

    def __init__(
        self,
        *,
        min_connections: int = 2,
        max_connections: int = 10,
        secret_id: str | None = None,
    ) -> None:
        """Initialize the database service.

        Args:
            min_connections: Minimum number of connections in the pool.
            max_connections: Maximum number of connections in the pool.
            secret_id: AWS Secrets Manager secret ID for credentials.
                       Defaults to NHL_DB_SECRET_ID env var or 'nhl-api'.
        """
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.secret_id = secret_id
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool, raising if not connected."""
        if self._pool is None:
            raise DatabaseError(
                "Database not connected. Call connect() first or use async context manager."
            )
        return self._pool

    @property
    def is_connected(self) -> bool:
        """Check if the database is connected."""
        return self._pool is not None

    async def connect(self) -> None:
        """Initialize the connection pool.

        Retrieves credentials from AWS Secrets Manager and creates
        an asyncpg connection pool.

        Raises:
            DatabaseError: If connection fails.
        """
        if self._pool is not None:
            logger.warning("Database already connected")
            return

        try:
            creds = get_db_credentials(self.secret_id)
            self._pool = await asyncpg.create_pool(
                host=creds.host,
                port=creds.port,
                database=creds.database,
                user=creds.username,
                password=creds.password,
                min_size=self.min_connections,
                max_size=self.max_connections,
            )
            logger.info(f"Connected to database: {creds.database}@{creds.host}")
        except Exception as e:
            raise DatabaseError(f"Failed to connect to database: {e}") from e

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Database connection closed")

    async def __aenter__(self) -> DatabaseService:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()

    # Query methods

    async def execute(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> str:
        """Execute a query and return the status.

        Args:
            query: SQL query to execute.
            *args: Query parameters.
            timeout: Query timeout in seconds.

        Returns:
            Query status string (e.g., "INSERT 0 1").
        """
        async with self.pool.acquire() as conn:
            result: str = await conn.execute(query, *args, timeout=timeout)
            return result

    async def executemany(
        self, query: str, args: list[tuple[Any, ...]], *, timeout: float | None = None
    ) -> None:
        """Execute a query with multiple parameter sets.

        Args:
            query: SQL query to execute.
            args: List of parameter tuples.
            timeout: Query timeout in seconds.
        """
        async with self.pool.acquire() as conn:
            await conn.executemany(query, args, timeout=timeout)

    async def fetch(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> list[Any]:
        """Execute a query and return all rows.

        Args:
            query: SQL query to execute.
            *args: Query parameters.
            timeout: Query timeout in seconds.

        Returns:
            List of Record objects.
        """
        async with self.pool.acquire() as conn:
            rows: list[Any] = await conn.fetch(query, *args, timeout=timeout)
            return rows

    async def fetchrow(
        self, query: str, *args: Any, timeout: float | None = None
    ) -> Any | None:
        """Execute a query and return the first row.

        Args:
            query: SQL query to execute.
            *args: Query parameters.
            timeout: Query timeout in seconds.

        Returns:
            A Record object or None if no rows.
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    async def fetchval(
        self,
        query: str,
        *args: Any,
        column: int = 0,
        timeout: float | None = None,
    ) -> Any:
        """Execute a query and return a single value.

        Args:
            query: SQL query to execute.
            *args: Query parameters.
            column: Column index to return.
            timeout: Query timeout in seconds.

        Returns:
            The value at the specified column.
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        """Create a transaction context.

        Yields:
            An asyncpg Connection within a transaction.

        Example:
            >>> async with db.transaction() as conn:
            ...     await conn.execute("INSERT INTO ...")
            ...     await conn.execute("UPDATE ...")
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    # Utility methods

    async def table_exists(self, table_name: str, schema: str = "public") -> bool:
        """Check if a table exists.

        Args:
            table_name: Name of the table.
            schema: Schema name (default: public).

        Returns:
            True if the table exists.
        """
        result = await self.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )
            """,
            schema,
            table_name,
        )
        return bool(result)

    async def get_table_count(self, table_name: str) -> int:
        """Get the row count of a table.

        Args:
            table_name: Name of the table.

        Returns:
            Number of rows in the table.
        """
        # Use identifier quoting for safety
        result = await self.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')
        return int(result) if result else 0
