"""Shared pytest fixtures for NHL API tests.

This module provides reusable fixtures for testing the NHL API library.
Fixtures are organized into categories:
- Sample data fixtures (players, teams, games)
- Mock API client fixtures
- Temporary storage fixtures
- Async fixtures

Usage:
    # In any test file, fixtures are automatically available:
    def test_example(sample_player_data, mock_api_client):
        player = sample_player_data
        assert player["id"] == 8478402
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.python import Function


# =============================================================================
# Test Collection Hook
# =============================================================================


def pytest_collection_modifyitems(config: Config, items: list[Function]) -> None:
    """Ensure unit tests run before integration tests.

    Integration tests in tests/integration/viewer/ use _clear_module_cache()
    which can affect patching in subsequent unit tests. Running unit tests
    first prevents this test pollution issue.
    """

    def sort_key(item: Function) -> tuple[int, str]:
        # Unit tests (tests/unit/) get priority 0, integration tests get 1
        path_str = str(item.fspath)
        if "/integration/" in path_str:
            return (1, path_str)
        return (0, path_str)

    items.sort(key=sort_key)


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture
def test_data_dir() -> Path:
    """Return the path to the test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def load_json_fixture(test_data_dir: Path) -> Callable[[str], dict[str, Any]]:
    """Factory fixture to load JSON test data files.

    Usage:
        def test_example(load_json_fixture):
            data = load_json_fixture("player_response.json")
    """

    def _load(filename: str) -> dict[str, Any]:
        filepath = test_data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Test fixture not found: {filepath}")
        with open(filepath) as f:
            result: dict[str, Any] = json.load(f)
            return result

    return _load


# =============================================================================
# Sample Player Data
# =============================================================================


@pytest.fixture
def sample_player_data() -> dict[str, Any]:
    """Sample NHL player data (Connor McDavid)."""
    return {
        "id": 8478402,
        "fullName": "Connor McDavid",
        "firstName": "Connor",
        "lastName": "McDavid",
        "primaryNumber": "97",
        "birthDate": "1997-01-13",
        "birthCity": "Richmond Hill",
        "birthStateProvince": "ON",
        "birthCountry": "CAN",
        "nationality": "CAN",
        "height": "6' 1\"",
        "weight": 193,
        "active": True,
        "alternateCaptain": False,
        "captain": True,
        "rookie": False,
        "shootsCatches": "L",
        "currentTeam": {
            "id": 22,
            "name": "Edmonton Oilers",
            "abbreviation": "EDM",
        },
        "primaryPosition": {
            "code": "C",
            "name": "Center",
            "type": "Forward",
            "abbreviation": "C",
        },
    }


@pytest.fixture
def sample_player_stats() -> dict[str, Any]:
    """Sample NHL player statistics."""
    return {
        "playerId": 8478402,
        "season": "20242025",
        "stats": {
            "gamesPlayed": 40,
            "goals": 22,
            "assists": 45,
            "points": 67,
            "plusMinus": 15,
            "pim": 18,
            "powerPlayGoals": 8,
            "powerPlayPoints": 25,
            "shortHandedGoals": 0,
            "shortHandedPoints": 0,
            "gameWinningGoals": 4,
            "overTimeGoals": 1,
            "shots": 150,
            "shotPct": 14.67,
            "timeOnIcePerGame": "22:30",
            "faceOffPct": 51.2,
        },
    }


@pytest.fixture
def sample_goalie_data() -> dict[str, Any]:
    """Sample NHL goalie data (Stuart Skinner)."""
    return {
        "id": 8479973,
        "fullName": "Stuart Skinner",
        "firstName": "Stuart",
        "lastName": "Skinner",
        "primaryNumber": "74",
        "birthDate": "1998-11-01",
        "birthCity": "Edmonton",
        "birthStateProvince": "AB",
        "birthCountry": "CAN",
        "nationality": "CAN",
        "height": "6' 4\"",
        "weight": 217,
        "active": True,
        "currentTeam": {
            "id": 22,
            "name": "Edmonton Oilers",
            "abbreviation": "EDM",
        },
        "primaryPosition": {
            "code": "G",
            "name": "Goalie",
            "type": "Goalie",
            "abbreviation": "G",
        },
    }


# =============================================================================
# Sample Team Data
# =============================================================================


@pytest.fixture
def sample_team_data() -> dict[str, Any]:
    """Sample NHL team data (Edmonton Oilers)."""
    return {
        "id": 22,
        "name": "Edmonton Oilers",
        "abbreviation": "EDM",
        "teamName": "Oilers",
        "locationName": "Edmonton",
        "firstYearOfPlay": "1979",
        "division": {
            "id": 15,
            "name": "Pacific",
            "abbreviation": "P",
        },
        "conference": {
            "id": 5,
            "name": "Western",
            "abbreviation": "W",
        },
        "venue": {
            "id": 5100,
            "name": "Rogers Place",
            "city": "Edmonton",
            "timeZone": {
                "id": "America/Edmonton",
                "offset": -7,
                "tz": "MST",
            },
        },
        "officialSiteUrl": "http://www.edmontonoilers.com/",
        "active": True,
    }


@pytest.fixture
def sample_team_roster() -> list[dict[str, Any]]:
    """Sample NHL team roster (partial)."""
    return [
        {
            "person": {
                "id": 8478402,
                "fullName": "Connor McDavid",
            },
            "jerseyNumber": "97",
            "position": {"code": "C", "name": "Center"},
        },
        {
            "person": {
                "id": 8477934,
                "fullName": "Leon Draisaitl",
            },
            "jerseyNumber": "29",
            "position": {"code": "C", "name": "Center"},
        },
        {
            "person": {
                "id": 8479973,
                "fullName": "Stuart Skinner",
            },
            "jerseyNumber": "74",
            "position": {"code": "G", "name": "Goalie"},
        },
    ]


# =============================================================================
# Sample Game Data
# =============================================================================


@pytest.fixture
def sample_game_data() -> dict[str, Any]:
    """Sample NHL game data."""
    return {
        "gamePk": 2024020500,
        "gameType": "R",
        "season": "20242025",
        "gameDate": "2024-12-20",
        "status": {
            "abstractGameState": "Final",
            "codedGameState": "7",
            "detailedState": "Final",
            "statusCode": "7",
        },
        "teams": {
            "away": {
                "team": {
                    "id": 25,
                    "name": "Dallas Stars",
                    "abbreviation": "DAL",
                },
                "score": 2,
            },
            "home": {
                "team": {
                    "id": 22,
                    "name": "Edmonton Oilers",
                    "abbreviation": "EDM",
                },
                "score": 4,
            },
        },
        "venue": {
            "id": 5100,
            "name": "Rogers Place",
        },
    }


@pytest.fixture
def sample_schedule_data() -> dict[str, Any]:
    """Sample NHL schedule data."""
    return {
        "dates": [
            {
                "date": "2024-12-20",
                "totalGames": 8,
                "games": [
                    {
                        "gamePk": 2024020500,
                        "gameType": "R",
                        "gameDate": "2024-12-20T19:00:00Z",
                        "status": {"detailedState": "Scheduled"},
                        "teams": {
                            "away": {"team": {"id": 25, "name": "Dallas Stars"}},
                            "home": {"team": {"id": 22, "name": "Edmonton Oilers"}},
                        },
                    },
                ],
            },
        ],
    }


# =============================================================================
# Mock API Client Fixtures
# =============================================================================


@pytest.fixture
def mock_http_response() -> MagicMock:
    """Create a mock HTTP response object."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = {}
    response.text = "{}"
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def mock_api_client(
    sample_player_data: dict[str, Any],
    sample_team_data: dict[str, Any],
    sample_game_data: dict[str, Any],
) -> MagicMock:
    """Create a mock NHL API client with pre-configured responses.

    The mock client has methods that return sample data:
    - get_player(player_id) -> sample_player_data
    - get_team(team_id) -> sample_team_data
    - get_game(game_id) -> sample_game_data

    Usage:
        def test_example(mock_api_client):
            player = mock_api_client.get_player(8478402)
            assert player["fullName"] == "Connor McDavid"
    """
    client = MagicMock()
    client.get_player.return_value = sample_player_data
    client.get_team.return_value = sample_team_data
    client.get_game.return_value = sample_game_data
    client.get_players.return_value = [sample_player_data]
    client.get_teams.return_value = [sample_team_data]
    return client


@pytest.fixture
def mock_async_api_client(
    sample_player_data: dict[str, Any],
    sample_team_data: dict[str, Any],
    sample_game_data: dict[str, Any],
) -> AsyncMock:
    """Create an async mock NHL API client.

    Usage:
        async def test_example(mock_async_api_client):
            player = await mock_async_api_client.get_player(8478402)
            assert player["fullName"] == "Connor McDavid"
    """
    client = AsyncMock()
    client.get_player.return_value = sample_player_data
    client.get_team.return_value = sample_team_data
    client.get_game.return_value = sample_game_data
    client.get_players.return_value = [sample_player_data]
    client.get_teams.return_value = [sample_team_data]
    return client


# =============================================================================
# Temporary Storage Fixtures
# =============================================================================


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test data storage.

    This creates a structured temp directory mimicking the data storage layout:
    - cache/
    - raw/
    - processed/

    Usage:
        def test_example(temp_data_dir):
            cache_file = temp_data_dir / "cache" / "players.json"
            cache_file.write_text('{"players": []}')
    """
    cache_dir = tmp_path / "cache"
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    cache_dir.mkdir()
    raw_dir.mkdir()
    processed_dir.mkdir()

    return tmp_path


@pytest.fixture
def temp_cache_file(temp_data_dir: Path) -> Path:
    """Create a temporary cache file with sample data."""
    cache_file = temp_data_dir / "cache" / "test_cache.json"
    cache_data = {
        "cached_at": "2024-12-20T12:00:00Z",
        "expires_at": "2024-12-21T12:00:00Z",
        "data": {},
    }
    cache_file.write_text(json.dumps(cache_data))
    return cache_file


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Return a path for a temporary SQLite database.

    Usage:
        def test_example(temp_db_path):
            conn = sqlite3.connect(temp_db_path)
            # ... use database
    """
    return tmp_path / "test_nhl.db"


# =============================================================================
# Environment Fixtures
# =============================================================================


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set up mock environment variables for testing.

    Usage:
        def test_example(mock_env_vars):
            # Environment is pre-configured
            assert os.environ.get("NHL_API_BASE_URL") is not None
    """
    env_vars = {
        "NHL_API_BASE_URL": "https://api-web.nhle.com",
        "NHL_API_TIMEOUT": "30",
        "NHL_CACHE_TTL": "3600",
        "NHL_DATA_DIR": "/tmp/nhl_test_data",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def freeze_time(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], datetime]:
    """Factory fixture to freeze time for tests.

    Usage:
        def test_example(freeze_time):
            freeze_time("2024-12-20T12:00:00")
            # datetime.now() returns frozen time
    """

    def _freeze(time_str: str) -> datetime:
        frozen = datetime.fromisoformat(time_str)

        class FrozenDatetime:
            @classmethod
            def now(cls, tz: Any = None) -> datetime:
                if tz:
                    return frozen.replace(tzinfo=tz)
                return frozen

            @classmethod
            def utcnow(cls) -> datetime:
                return frozen

        monkeypatch.setattr("datetime.datetime", FrozenDatetime)
        return frozen

    return _freeze
