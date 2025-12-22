"""Tests for coverage endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from nhl_api.viewer.routers.coverage import (
    CATEGORY_CONFIG,
    _build_categories,
    _calculate_percentage,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestCalculatePercentage:
    """Tests for _calculate_percentage helper."""

    def test_normal_calculation(self) -> None:
        """Test normal percentage calculation."""
        assert _calculate_percentage(50, 100) == 50.0
        assert _calculate_percentage(75, 100) == 75.0
        assert _calculate_percentage(100, 100) == 100.0

    def test_zero_expected_returns_none(self) -> None:
        """Test that zero expected returns None."""
        assert _calculate_percentage(0, 0) is None
        assert _calculate_percentage(50, 0) is None

    def test_negative_expected_returns_none(self) -> None:
        """Test that negative expected returns None."""
        assert _calculate_percentage(50, -10) is None

    def test_rounds_to_one_decimal(self) -> None:
        """Test percentage is rounded to one decimal place."""
        assert _calculate_percentage(1, 3) == 33.3
        assert _calculate_percentage(2, 3) == 66.7


class TestBuildCategories:
    """Tests for _build_categories helper."""

    def test_builds_all_categories(self) -> None:
        """Test all six categories are built."""
        row = {
            "games_scheduled": 100,
            "games_final": 80,
            "boxscore_expected": 80,
            "boxscore_actual": 75,
            "pbp_expected": 80,
            "pbp_actual": 70,
            "shifts_expected": 80,
            "shifts_actual": 65,
            "players_expected": 500,
            "players_actual": 450,
            "html_expected": 80,
            "html_actual": 60,
        }

        categories = _build_categories(row, 20242025)

        assert len(categories) == 6
        names = [c.name for c in categories]
        assert names == ["games", "boxscore", "pbp", "shifts", "players", "html"]

    def test_builds_correct_link_paths(self) -> None:
        """Test link paths include season filter."""
        row = {
            "games_scheduled": 100,
            "games_final": 80,
            "boxscore_expected": 80,
            "boxscore_actual": 75,
            "pbp_expected": 80,
            "pbp_actual": 70,
            "shifts_expected": 80,
            "shifts_actual": 65,
            "players_expected": 500,
            "players_actual": 450,
            "html_expected": 80,
            "html_actual": 60,
        }

        categories = _build_categories(row, 20242025)

        # Check all links include season parameter
        for cat in categories:
            assert "season=20242025" in cat.link_path

    def test_handles_null_values(self) -> None:
        """Test null values are converted to zero."""
        row = {
            "games_scheduled": None,
            "games_final": None,
            "boxscore_expected": None,
            "boxscore_actual": None,
            "pbp_expected": None,
            "pbp_actual": None,
            "shifts_expected": None,
            "shifts_actual": None,
            "players_expected": None,
            "players_actual": None,
            "html_expected": None,
            "html_actual": None,
        }

        categories = _build_categories(row, 20242025)

        for cat in categories:
            assert cat.actual == 0
            assert cat.expected == 0
            assert cat.percentage is None


class TestCategoryConfig:
    """Tests for category configuration."""

    def test_all_categories_have_config(self) -> None:
        """Test all expected categories are configured."""
        expected = ["games", "boxscore", "pbp", "shifts", "players", "html"]
        for name in expected:
            assert name in CATEGORY_CONFIG
            assert "display_name" in CATEGORY_CONFIG[name]
            assert "link_template" in CATEGORY_CONFIG[name]


class TestCoverageSummaryEndpoint:
    """Tests for GET /api/v1/coverage/summary."""

    def test_summary_returns_seasons(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test summary returns season data with categories."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "season_id": 20242025,
                    "season_label": "2024-2025",
                    "is_current": True,
                    "games_scheduled": 1312,
                    "games_final": 800,
                    "games_total": 800,
                    "boxscore_expected": 800,
                    "boxscore_actual": 750,
                    "boxscore_pct": 93.75,
                    "pbp_expected": 800,
                    "pbp_actual": 700,
                    "pbp_pct": 87.5,
                    "shifts_expected": 800,
                    "shifts_actual": 650,
                    "shifts_pct": 81.25,
                    "players_expected": 1000,
                    "players_actual": 900,
                    "players_pct": 90.0,
                    "html_expected": 800,
                    "html_actual": 600,
                    "html_pct": 75.0,
                    "game_logs_total": 45000,
                    "players_with_game_logs": 850,
                    "refreshed_at": datetime.now(UTC),
                }
            ]
        )

        response = test_client.get("/api/v1/coverage/summary")

        assert response.status_code == 200
        data = response.json()
        assert "seasons" in data
        assert "refreshed_at" in data
        assert len(data["seasons"]) == 1

        season = data["seasons"][0]
        assert season["season_id"] == 20242025
        assert season["season_label"] == "2024-2025"
        assert season["is_current"] is True
        assert len(season["categories"]) == 6
        assert season["game_logs_total"] == 45000
        assert season["players_with_game_logs"] == 850

    def test_summary_calculates_percentages(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test percentages are calculated correctly."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "season_id": 20242025,
                    "season_label": "2024-2025",
                    "is_current": True,
                    "games_scheduled": 100,
                    "games_final": 50,
                    "games_total": 50,
                    "boxscore_expected": 50,
                    "boxscore_actual": 25,
                    "boxscore_pct": 50.0,
                    "pbp_expected": 50,
                    "pbp_actual": 0,
                    "pbp_pct": 0.0,
                    "shifts_expected": 50,
                    "shifts_actual": 50,
                    "shifts_pct": 100.0,
                    "players_expected": 100,
                    "players_actual": 33,
                    "players_pct": 33.0,
                    "html_expected": 0,
                    "html_actual": 0,
                    "html_pct": None,
                    "game_logs_total": 0,
                    "players_with_game_logs": 0,
                    "refreshed_at": datetime.now(UTC),
                }
            ]
        )

        response = test_client.get("/api/v1/coverage/summary")

        assert response.status_code == 200
        data = response.json()
        categories = {c["name"]: c for c in data["seasons"][0]["categories"]}

        assert categories["games"]["percentage"] == 50.0
        assert categories["boxscore"]["percentage"] == 50.0
        assert categories["shifts"]["percentage"] == 100.0
        assert categories["players"]["percentage"] == 33.0
        # html has 0 expected, should be None
        assert categories["html"]["percentage"] is None

    def test_summary_handles_empty_database(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test summary handles no data gracefully."""
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/coverage/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["seasons"] == []

    def test_summary_with_season_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test filtering by specific seasons."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "season_id": 20232024,
                    "season_label": "2023-2024",
                    "is_current": False,
                    "games_scheduled": 1312,
                    "games_final": 1312,
                    "games_total": 1312,
                    "boxscore_expected": 1312,
                    "boxscore_actual": 1312,
                    "boxscore_pct": 100.0,
                    "pbp_expected": 1312,
                    "pbp_actual": 1312,
                    "pbp_pct": 100.0,
                    "shifts_expected": 1312,
                    "shifts_actual": 1312,
                    "shifts_pct": 100.0,
                    "players_expected": 1000,
                    "players_actual": 1000,
                    "players_pct": 100.0,
                    "html_expected": 1312,
                    "html_actual": 1312,
                    "html_pct": 100.0,
                    "game_logs_total": 50000,
                    "players_with_game_logs": 1000,
                    "refreshed_at": datetime.now(UTC),
                }
            ]
        )

        response = test_client.get("/api/v1/coverage/summary?season_ids=20232024")

        assert response.status_code == 200
        data = response.json()
        assert len(data["seasons"]) == 1
        assert data["seasons"][0]["season_id"] == 20232024

    def test_summary_with_include_all(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test include_all returns all seasons."""
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/coverage/summary?include_all=true")

        assert response.status_code == 200
        # Verify the query was called (include_all path)
        mock_db_service.fetch.assert_called_once()

    def test_summary_default_limit_3_seasons(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test default returns at most 3 seasons."""
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/coverage/summary")

        assert response.status_code == 200
        # Check that the SQL includes LIMIT 3
        call_args = mock_db_service.fetch.call_args
        query = call_args[0][0] if call_args[0] else call_args[1].get("query", "")
        assert "LIMIT 3" in query

    def test_summary_multiple_seasons(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test response with multiple seasons."""
        base_row = {
            "games_scheduled": 1312,
            "games_final": 1312,
            "games_total": 1312,
            "boxscore_expected": 1312,
            "boxscore_actual": 1312,
            "boxscore_pct": 100.0,
            "pbp_expected": 1312,
            "pbp_actual": 1312,
            "pbp_pct": 100.0,
            "shifts_expected": 1312,
            "shifts_actual": 1312,
            "shifts_pct": 100.0,
            "players_expected": 1000,
            "players_actual": 1000,
            "players_pct": 100.0,
            "html_expected": 1312,
            "html_actual": 1312,
            "html_pct": 100.0,
            "game_logs_total": 50000,
            "players_with_game_logs": 1000,
            "refreshed_at": datetime.now(UTC),
        }

        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    **base_row,
                    "season_id": 20242025,
                    "season_label": "2024-2025",
                    "is_current": True,
                },
                {
                    **base_row,
                    "season_id": 20232024,
                    "season_label": "2023-2024",
                    "is_current": False,
                },
                {
                    **base_row,
                    "season_id": 20222023,
                    "season_label": "2022-2023",
                    "is_current": False,
                },
            ]
        )

        response = test_client.get("/api/v1/coverage/summary")

        assert response.status_code == 200
        data = response.json()
        assert len(data["seasons"]) == 3
        # Should be in descending order
        assert data["seasons"][0]["season_id"] == 20242025
        assert data["seasons"][1]["season_id"] == 20232024
        assert data["seasons"][2]["season_id"] == 20222023

    def test_summary_handles_null_refresh_time(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test handling of null refreshed_at."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "season_id": 20242025,
                    "season_label": "2024-2025",
                    "is_current": True,
                    "games_scheduled": 100,
                    "games_final": 50,
                    "games_total": 50,
                    "boxscore_expected": 50,
                    "boxscore_actual": 25,
                    "boxscore_pct": 50.0,
                    "pbp_expected": 50,
                    "pbp_actual": 25,
                    "pbp_pct": 50.0,
                    "shifts_expected": 50,
                    "shifts_actual": 25,
                    "shifts_pct": 50.0,
                    "players_expected": 100,
                    "players_actual": 50,
                    "players_pct": 50.0,
                    "html_expected": 50,
                    "html_actual": 25,
                    "html_pct": 50.0,
                    "game_logs_total": 0,
                    "players_with_game_logs": 0,
                    "refreshed_at": None,
                }
            ]
        )

        response = test_client.get("/api/v1/coverage/summary")

        assert response.status_code == 200
        data = response.json()
        # When no seasons have refreshed_at, it should still return a timestamp
        assert data["refreshed_at"] is not None

    def test_summary_category_display_names(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test categories have correct display names."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "season_id": 20242025,
                    "season_label": "2024-2025",
                    "is_current": True,
                    "games_scheduled": 100,
                    "games_final": 50,
                    "games_total": 50,
                    "boxscore_expected": 50,
                    "boxscore_actual": 25,
                    "boxscore_pct": 50.0,
                    "pbp_expected": 50,
                    "pbp_actual": 25,
                    "pbp_pct": 50.0,
                    "shifts_expected": 50,
                    "shifts_actual": 25,
                    "shifts_pct": 50.0,
                    "players_expected": 100,
                    "players_actual": 50,
                    "players_pct": 50.0,
                    "html_expected": 50,
                    "html_actual": 25,
                    "html_pct": 50.0,
                    "game_logs_total": 0,
                    "players_with_game_logs": 0,
                    "refreshed_at": datetime.now(UTC),
                }
            ]
        )

        response = test_client.get("/api/v1/coverage/summary")

        assert response.status_code == 200
        data = response.json()
        categories = {c["name"]: c for c in data["seasons"][0]["categories"]}

        assert categories["games"]["display_name"] == "Games Downloaded"
        assert categories["boxscore"]["display_name"] == "Boxscore Data"
        assert categories["pbp"]["display_name"] == "Play-by-Play"
        assert categories["shifts"]["display_name"] == "Shift Charts"
        assert categories["players"]["display_name"] == "Player Profiles"
        assert categories["html"]["display_name"] == "HTML Reports"
