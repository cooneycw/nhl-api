"""Unit tests for database connection service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nhl_api.services.db.connection import DatabaseError, DatabaseService


def create_mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Create a properly mocked asyncpg pool."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
    mock_conn.fetch = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
    mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
    mock_conn.fetchval = AsyncMock(return_value=42)

    @asynccontextmanager
    async def mock_acquire() -> AsyncIterator[Any]:
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.acquire = mock_acquire
    mock_pool.close = AsyncMock()

    return mock_pool, mock_conn


class TestDatabaseService:
    """Tests for DatabaseService class."""

    def test_init_defaults(self) -> None:
        """Test default initialization."""
        db = DatabaseService()
        assert db.min_connections == 2
        assert db.max_connections == 10
        assert db.secret_id is None
        assert not db.is_connected

    def test_init_custom(self) -> None:
        """Test custom initialization."""
        db = DatabaseService(
            min_connections=5,
            max_connections=20,
            secret_id="custom-secret",
        )
        assert db.min_connections == 5
        assert db.max_connections == 20
        assert db.secret_id == "custom-secret"

    def test_pool_raises_when_not_connected(self) -> None:
        """Test that pool property raises when not connected."""
        db = DatabaseService()
        with pytest.raises(DatabaseError) as exc_info:
            _ = db.pool
        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_creates_pool(self) -> None:
        """Test that connect creates a connection pool."""
        db = DatabaseService()

        mock_pool, _ = create_mock_pool()
        mock_creds = MagicMock()
        mock_creds.host = "localhost"
        mock_creds.port = 5432
        mock_creds.database = "testdb"
        mock_creds.username = "user"
        mock_creds.password = "pass"

        async def mock_create_pool(**kwargs: Any) -> Any:
            return mock_pool

        with (
            patch(
                "nhl_api.services.db.connection.get_db_credentials",
                return_value=mock_creds,
            ),
            patch(
                "nhl_api.services.db.connection.asyncpg.create_pool",
                side_effect=mock_create_pool,
            ),
        ):
            await db.connect()
            assert db.is_connected

    @pytest.mark.asyncio
    async def test_disconnect_closes_pool(self) -> None:
        """Test that disconnect closes the pool."""
        db = DatabaseService()
        mock_pool, _ = create_mock_pool()
        db._pool = mock_pool

        await db.disconnect()

        mock_pool.close.assert_called_once()
        assert not db.is_connected

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager."""
        mock_pool, _ = create_mock_pool()
        mock_creds = MagicMock()
        mock_creds.host = "localhost"
        mock_creds.port = 5432
        mock_creds.database = "testdb"
        mock_creds.username = "user"
        mock_creds.password = "pass"

        async def mock_create_pool(**kwargs: Any) -> Any:
            return mock_pool

        with (
            patch(
                "nhl_api.services.db.connection.get_db_credentials",
                return_value=mock_creds,
            ),
            patch(
                "nhl_api.services.db.connection.asyncpg.create_pool",
                side_effect=mock_create_pool,
            ),
        ):
            async with DatabaseService() as db:
                assert db.is_connected

            mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query(self) -> None:
        """Test execute method."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        db._pool = mock_pool

        result = await db.execute("INSERT INTO test VALUES ($1)", 1)

        assert result == "INSERT 0 1"
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_query(self) -> None:
        """Test fetch method."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        db._pool = mock_pool

        result = await db.fetch("SELECT * FROM test")

        assert len(result) == 2
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetchval_query(self) -> None:
        """Test fetchval method."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        db._pool = mock_pool

        result = await db.fetchval("SELECT COUNT(*) FROM test")

        assert result == 42
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_table_exists(self) -> None:
        """Test table_exists method."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchval.return_value = True
        db._pool = mock_pool

        result = await db.table_exists("test_table")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_table_count(self) -> None:
        """Test get_table_count method."""
        db = DatabaseService()
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.fetchval.return_value = 100
        db._pool = mock_pool

        result = await db.get_table_count("test_table")

        assert result == 100
