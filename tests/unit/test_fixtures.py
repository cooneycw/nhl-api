"""Tests to verify that fixtures work correctly.

These tests serve dual purposes:
1. Validate that fixtures are properly configured
2. Demonstrate fixture usage patterns for developers
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSampleDataFixtures:
    """Tests for sample data fixtures."""

    @pytest.mark.unit
    def test_sample_player_data_structure(
        self, sample_player_data: dict[str, Any]
    ) -> None:
        """Verify sample player data has expected structure."""
        assert sample_player_data["id"] == 8478402
        assert sample_player_data["fullName"] == "Connor McDavid"
        assert sample_player_data["primaryNumber"] == "97"
        assert sample_player_data["currentTeam"]["abbreviation"] == "EDM"
        assert sample_player_data["primaryPosition"]["code"] == "C"

    @pytest.mark.unit
    def test_sample_player_stats_structure(
        self, sample_player_stats: dict[str, Any]
    ) -> None:
        """Verify sample player stats has expected structure."""
        assert sample_player_stats["playerId"] == 8478402
        assert sample_player_stats["season"] == "20242025"
        stats = sample_player_stats["stats"]
        assert "goals" in stats
        assert "assists" in stats
        assert stats["goals"] + stats["assists"] == stats["points"]

    @pytest.mark.unit
    def test_sample_goalie_data_structure(
        self, sample_goalie_data: dict[str, Any]
    ) -> None:
        """Verify sample goalie data has expected structure."""
        assert sample_goalie_data["id"] == 8479973
        assert sample_goalie_data["fullName"] == "Stuart Skinner"
        assert sample_goalie_data["primaryPosition"]["code"] == "G"

    @pytest.mark.unit
    def test_sample_team_data_structure(self, sample_team_data: dict[str, Any]) -> None:
        """Verify sample team data has expected structure."""
        assert sample_team_data["id"] == 22
        assert sample_team_data["name"] == "Edmonton Oilers"
        assert sample_team_data["abbreviation"] == "EDM"
        assert sample_team_data["division"]["name"] == "Pacific"
        assert sample_team_data["conference"]["name"] == "Western"

    @pytest.mark.unit
    def test_sample_team_roster_structure(
        self, sample_team_roster: list[dict[str, Any]]
    ) -> None:
        """Verify sample team roster has expected structure."""
        assert len(sample_team_roster) == 3
        mcdavid = sample_team_roster[0]
        assert mcdavid["person"]["fullName"] == "Connor McDavid"
        assert mcdavid["jerseyNumber"] == "97"

    @pytest.mark.unit
    def test_sample_game_data_structure(self, sample_game_data: dict[str, Any]) -> None:
        """Verify sample game data has expected structure."""
        assert sample_game_data["gamePk"] == 2024020500
        assert sample_game_data["gameType"] == "R"  # Regular season
        assert sample_game_data["teams"]["home"]["score"] == 4
        assert sample_game_data["teams"]["away"]["score"] == 2

    @pytest.mark.unit
    def test_sample_schedule_data_structure(
        self, sample_schedule_data: dict[str, Any]
    ) -> None:
        """Verify sample schedule data has expected structure."""
        assert len(sample_schedule_data["dates"]) == 1
        date_entry = sample_schedule_data["dates"][0]
        assert date_entry["date"] == "2024-12-20"
        assert len(date_entry["games"]) == 1


class TestJsonFixtureLoader:
    """Tests for JSON fixture loading."""

    @pytest.mark.unit
    def test_test_data_dir_exists(self, test_data_dir: Path) -> None:
        """Verify test data directory path is correct."""
        assert test_data_dir.exists()
        assert test_data_dir.is_dir()
        assert test_data_dir.name == "data"

    @pytest.mark.unit
    def test_load_json_fixture_player(
        self, load_json_fixture: Callable[[str], dict[str, Any]]
    ) -> None:
        """Test loading player JSON fixture."""
        data = load_json_fixture("player_response.json")
        assert data["fullName"] == "Connor McDavid"
        assert data["id"] == 8478402

    @pytest.mark.unit
    def test_load_json_fixture_team(
        self, load_json_fixture: Callable[[str], dict[str, Any]]
    ) -> None:
        """Test loading team JSON fixture."""
        data = load_json_fixture("team_response.json")
        assert data["name"] == "Edmonton Oilers"

    @pytest.mark.unit
    def test_load_json_fixture_game(
        self, load_json_fixture: Callable[[str], dict[str, Any]]
    ) -> None:
        """Test loading game JSON fixture."""
        data = load_json_fixture("game_response.json")
        assert data["gamePk"] == 2024020500
        assert "linescore" in data

    @pytest.mark.unit
    def test_load_json_fixture_not_found(
        self, load_json_fixture: Callable[[str], dict[str, Any]]
    ) -> None:
        """Test that missing fixture raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Test fixture not found"):
            load_json_fixture("nonexistent.json")


class TestMockApiClient:
    """Tests for mock API client fixtures."""

    @pytest.mark.unit
    def test_mock_api_client_get_player(
        self,
        mock_api_client: MagicMock,
        sample_player_data: dict[str, Any],
    ) -> None:
        """Test mock API client returns sample player data."""
        result = mock_api_client.get_player(8478402)
        assert result == sample_player_data
        mock_api_client.get_player.assert_called_once_with(8478402)

    @pytest.mark.unit
    def test_mock_api_client_get_team(
        self,
        mock_api_client: MagicMock,
        sample_team_data: dict[str, Any],
    ) -> None:
        """Test mock API client returns sample team data."""
        result = mock_api_client.get_team(22)
        assert result == sample_team_data

    @pytest.mark.unit
    def test_mock_api_client_get_game(
        self,
        mock_api_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test mock API client returns sample game data."""
        result = mock_api_client.get_game(2024020500)
        assert result == sample_game_data

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mock_async_api_client(
        self,
        mock_async_api_client: AsyncMock,
        sample_player_data: dict[str, Any],
    ) -> None:
        """Test async mock API client works with await."""
        result = await mock_async_api_client.get_player(8478402)
        assert result == sample_player_data


class TestTempStorageFixtures:
    """Tests for temporary storage fixtures."""

    @pytest.mark.unit
    def test_temp_data_dir_structure(self, temp_data_dir: Path) -> None:
        """Verify temp data directory has expected subdirectories."""
        assert (temp_data_dir / "cache").exists()
        assert (temp_data_dir / "raw").exists()
        assert (temp_data_dir / "processed").exists()

    @pytest.mark.unit
    def test_temp_cache_file_exists(self, temp_cache_file: Path) -> None:
        """Verify temp cache file is created with content."""
        assert temp_cache_file.exists()
        import json

        data = json.loads(temp_cache_file.read_text())
        assert "cached_at" in data
        assert "expires_at" in data

    @pytest.mark.unit
    def test_temp_db_path(self, temp_db_path: Path) -> None:
        """Verify temp database path is in temp directory."""
        assert temp_db_path.name == "test_nhl.db"
        assert "tmp" in str(temp_db_path) or "temp" in str(temp_db_path).lower()


class TestEnvironmentFixtures:
    """Tests for environment variable fixtures."""

    @pytest.mark.unit
    def test_mock_env_vars_set(self, mock_env_vars: dict[str, str]) -> None:
        """Verify mock environment variables are set."""
        import os

        assert os.environ.get("NHL_API_BASE_URL") == "https://api-web.nhle.com"
        assert os.environ.get("NHL_API_TIMEOUT") == "30"
        assert os.environ.get("NHL_CACHE_TTL") == "3600"

    @pytest.mark.unit
    def test_mock_env_vars_returns_dict(self, mock_env_vars: dict[str, str]) -> None:
        """Verify mock_env_vars returns the set variables."""
        assert "NHL_API_BASE_URL" in mock_env_vars
        assert mock_env_vars["NHL_API_TIMEOUT"] == "30"
