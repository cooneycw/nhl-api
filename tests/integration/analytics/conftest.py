"""Pytest fixtures for analytics integration tests.

Provides fixtures for testing analytics validation with real database connections.

Issue: #260 - Wave 2: Validation & Quality
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Mapping
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

if TYPE_CHECKING:
    from nhl_api.services.db.connection import DatabaseService


class DictLikeRecord(Mapping):
    """A dict-like object that also supports attribute access for test mocking.

    This mimics asyncpg Record behavior where you can access values via
    both record["key"] and record.key.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __getattr__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError as err:
            raise AttributeError(
                f"'{type(self).__name__}' has no attribute '{key}'"
            ) from err

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()


def make_record(data: dict[str, Any]) -> DictLikeRecord:
    """Helper to create a DictLikeRecord from a dict."""
    return DictLikeRecord(data)


def make_records(data_list: list[dict[str, Any]]) -> list[DictLikeRecord]:
    """Helper to create a list of DictLikeRecords from a list of dicts."""
    return [DictLikeRecord(d) for d in data_list]


@pytest.fixture
def sample_game_id() -> int:
    """Sample game ID for testing."""
    return 2024020500


@pytest.fixture
def sample_season_id() -> int:
    """Sample season ID for testing."""
    return 20242025


@pytest.fixture
def sample_game_info(sample_game_id: int, sample_season_id: int) -> dict:
    """Sample game metadata."""
    return {
        "game_id": sample_game_id,
        "season_id": sample_season_id,
        "home_team_id": 22,  # Edmonton Oilers
        "away_team_id": 25,  # Dallas Stars
        "period": 3,
    }


@pytest.fixture
def sample_shifts() -> list[dict]:
    """Sample shift data for testing."""
    return [
        {
            "player_id": 8478402,  # McDavid
            "team_id": 22,
            "total_seconds": 1250,
            "shift_count": 25,
        },
        {
            "player_id": 8477934,  # Draisaitl
            "team_id": 22,
            "total_seconds": 1180,
            "shift_count": 24,
        },
        {
            "player_id": 8477846,  # Roope Hintz
            "team_id": 25,
            "total_seconds": 1100,
            "shift_count": 22,
        },
    ]


@pytest.fixture
def sample_boxscore() -> dict:
    """Sample boxscore data."""
    return {
        "home_goals": 4,
        "away_goals": 2,
        "home_shots": 35,
        "away_shots": 28,
        "home_hits": 22,
        "away_hits": 18,
        "home_blocks": 15,
        "away_blocks": 12,
    }


@pytest.fixture
def sample_events() -> list[dict]:
    """Sample game events."""
    return [
        {"event_type": "goal", "count": 6},
        {"event_type": "shot-on-goal", "count": 57},
        {"event_type": "hit", "count": 40},
        {"event_type": "blocked-shot", "count": 27},
    ]


@pytest.fixture
def sample_snapshots() -> list[dict]:
    """Sample second snapshots for validation."""
    return [
        {
            "game_second": 0,
            "situation_code": "5v5",
            "home_skater_count": 5,
            "away_skater_count": 5,
            "home_goalie_id": 8479973,
            "away_goalie_id": 8477970,
        },
        {
            "game_second": 100,
            "situation_code": "5v4",
            "home_skater_count": 5,
            "away_skater_count": 4,
            "home_goalie_id": 8479973,
            "away_goalie_id": 8477970,
        },
        {
            "game_second": 3550,
            "situation_code": "EN6v5",
            "home_skater_count": 6,
            "away_skater_count": 5,
            "home_goalie_id": None,  # Empty net
            "away_goalie_id": 8477970,
        },
    ]


@pytest.fixture
def mock_db_service(
    sample_game_info: dict,
    sample_shifts: list[dict],
    sample_boxscore: dict,
    sample_events: list[dict],
    sample_snapshots: list[dict],
) -> AsyncMock:
    """Create a mock database service with pre-configured responses."""
    db = AsyncMock()

    # Configure fetchrow for game info
    async def mock_fetchrow(query: str, *args):
        if "FROM games" in query:
            return make_record(sample_game_info)
        if "FROM boxscores" in query:
            return make_record(sample_boxscore)
        return None

    db.fetchrow = mock_fetchrow

    # Configure fetch for lists
    async def mock_fetch(query: str, *args):
        if "FROM game_shifts" in query:
            return make_records(sample_shifts)
        if "FROM game_events" in query:
            return make_records(sample_events)
        if "FROM second_snapshots" in query:
            return make_records(sample_snapshots)
        if "FROM html_toi_reports" in query:
            return []  # No HTML reports by default
        return []

    db.fetch = mock_fetch

    # Configure fetchval for counts
    async def mock_fetchval(query: str, *args):
        if "COUNT(*)" in query and "second_snapshots" in query:
            # Return TOI close to original
            player_id = args[1] if len(args) > 1 else None
            for shift in sample_shifts:
                if shift["player_id"] == player_id:
                    return shift["total_seconds"]
            return 0
        return 0

    db.fetchval = mock_fetchval

    return db


@pytest.fixture
async def live_db_service() -> AsyncGenerator[DatabaseService | None, None]:
    """Get a live database connection if available.

    This fixture attempts to connect to the actual database.
    If not available, yields None and tests should be skipped.
    """
    # Check if we have database credentials
    if not os.environ.get("DB_HOST") and not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        yield None
        return

    try:
        from nhl_api.services.db.connection import DatabaseService

        async with DatabaseService() as db:
            yield db
    except Exception:
        yield None
