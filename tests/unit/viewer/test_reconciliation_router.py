"""Unit tests for reconciliation router endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nhl_api.viewer.dependencies import set_db_service
from nhl_api.viewer.routers import reconciliation
from nhl_api.viewer.schemas.reconciliation import (
    BatchReconciliationResponse,
    GameReconciliation,
    GameReconciliationDetail,
    ReconciliationCheck,
    ReconciliationDashboardResponse,
    ReconciliationGamesResponse,
    ReconciliationSummary,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_db_service() -> MagicMock:
    """Create a mock DatabaseService."""
    mock = MagicMock()
    mock.is_connected = True
    mock.fetchval = AsyncMock(return_value=1)
    mock.fetch = AsyncMock(return_value=[])
    mock.fetchrow = AsyncMock(return_value=None)
    mock.execute = AsyncMock(return_value="OK")
    return mock


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app with reconciliation router."""
    app = FastAPI()
    app.include_router(reconciliation.router, prefix="/api/v1")
    return app


@pytest.fixture
def test_client(
    test_app: FastAPI, mock_db_service: MagicMock
) -> Generator[TestClient, None, None]:
    """Create a test client with mocked database."""
    set_db_service(mock_db_service)
    client = TestClient(test_app)
    yield client
    set_db_service(None)


# =============================================================================
# Dashboard Endpoint Tests
# =============================================================================


class TestDashboardEndpoint:
    """Test GET /reconciliation/dashboard endpoint."""

    def test_dashboard_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Dashboard returns 200 with valid season_id."""
        mock_summary = ReconciliationDashboardResponse(
            summary=ReconciliationSummary(
                season_id=20242025,
                total_games=100,
                games_with_discrepancies=5,
                total_checks=400,
                passed_checks=395,
                failed_checks=5,
                pass_rate=0.9875,
                goal_reconciliation_rate=0.99,
                penalty_reconciliation_rate=0.98,
                toi_reconciliation_rate=0.97,
                problem_games=[],
            ),
            last_run=None,
            quality_score=98.75,
            timestamp=datetime.now(),
        )

        with patch.object(
            reconciliation._service, "get_dashboard_summary", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_summary

            response = test_client.get(
                "/api/v1/reconciliation/dashboard?season_id=20242025"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["season_id"] == 20242025
            assert data["quality_score"] == 98.75

    def test_dashboard_missing_season_id(self, test_client: TestClient) -> None:
        """Dashboard returns 422 when season_id is missing."""
        response = test_client.get("/api/v1/reconciliation/dashboard")
        assert response.status_code == 422

    def test_dashboard_invalid_season_id(self, test_client: TestClient) -> None:
        """Dashboard returns 422 for invalid season_id."""
        response = test_client.get("/api/v1/reconciliation/dashboard?season_id=invalid")
        assert response.status_code == 422


# =============================================================================
# Games List Endpoint Tests
# =============================================================================


class TestGamesEndpoint:
    """Test GET /reconciliation/games endpoint."""

    def test_games_list_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Games list returns 200 with valid parameters."""
        mock_response = ReconciliationGamesResponse(
            games=[
                GameReconciliation(
                    game_id=2024020001,
                    game_date=date(2024, 10, 8),
                    home_team="BOS",
                    away_team="FLA",
                    checks_passed=3,
                    checks_failed=1,
                    discrepancies=[],
                )
            ],
            total=1,
            page=1,
            page_size=20,
            pages=1,
        )

        with patch.object(
            reconciliation._service,
            "get_games_with_discrepancies",
            new_callable=AsyncMock,
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get(
                "/api/v1/reconciliation/games?season_id=20242025"
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["games"]) == 1
            assert data["total"] == 1

    def test_games_list_with_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Games list filters by discrepancy type."""
        mock_response = ReconciliationGamesResponse(
            games=[],
            total=0,
            page=1,
            page_size=20,
            pages=0,
        )

        with patch.object(
            reconciliation._service,
            "get_games_with_discrepancies",
            new_callable=AsyncMock,
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get(
                "/api/v1/reconciliation/games?season_id=20242025&discrepancy_type=goal"
            )

            assert response.status_code == 200
            mock_method.assert_called_once()
            call_args = mock_method.call_args
            assert call_args.kwargs["discrepancy_type"] == "goal"

    def test_games_list_invalid_filter(self, test_client: TestClient) -> None:
        """Games list returns 422 for invalid discrepancy type."""
        response = test_client.get(
            "/api/v1/reconciliation/games?season_id=20242025&discrepancy_type=invalid"
        )
        assert response.status_code == 422

    def test_games_list_pagination(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Games list respects pagination parameters."""
        mock_response = ReconciliationGamesResponse(
            games=[],
            total=100,
            page=3,
            page_size=10,
            pages=10,
        )

        with patch.object(
            reconciliation._service,
            "get_games_with_discrepancies",
            new_callable=AsyncMock,
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get(
                "/api/v1/reconciliation/games?season_id=20242025&page=3&page_size=10"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 3
            assert data["page_size"] == 10


# =============================================================================
# Game Detail Endpoint Tests
# =============================================================================


class TestGameDetailEndpoint:
    """Test GET /reconciliation/games/{game_id} endpoint."""

    def test_game_detail_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Game detail returns 200 for existing game."""
        mock_detail = GameReconciliationDetail(
            game_id=2024020001,
            game_date=date(2024, 10, 8),
            home_team="BOS",
            away_team="FLA",
            checks_passed=3,
            checks_failed=1,
            discrepancies=[
                ReconciliationCheck(
                    rule_name="goal_count_pbp_vs_boxscore",
                    passed=False,
                    source_a="play_by_play",
                    source_a_value=5,
                    source_b="boxscore",
                    source_b_value=6,
                    difference=1.0,
                    entity_type="game",
                    entity_id="2024020001",
                )
            ],
            all_checks=[],
            sources_available=["boxscore", "play_by_play", "shift_charts"],
            sources_missing=[],
        )

        with patch.object(
            reconciliation._service, "get_game_reconciliation", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_detail

            response = test_client.get("/api/v1/reconciliation/games/2024020001")

            assert response.status_code == 200
            data = response.json()
            assert data["game_id"] == 2024020001
            assert len(data["discrepancies"]) == 1
            assert "boxscore" in data["sources_available"]

    def test_game_detail_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Game detail returns 404 for non-existent game."""
        with patch.object(
            reconciliation._service, "get_game_reconciliation", new_callable=AsyncMock
        ) as mock_method:
            mock_method.side_effect = ValueError("Game 999999999 not found")

            response = test_client.get("/api/v1/reconciliation/games/999999999")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]


# =============================================================================
# Batch Reconciliation Endpoint Tests
# =============================================================================


class TestBatchReconciliationEndpoint:
    """Test POST /reconciliation/run endpoint."""

    def test_run_reconciliation_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Batch reconciliation returns 202 with run_id."""
        mock_response = BatchReconciliationResponse(
            run_id=1234567890,
            status="started",
            message="Reconciliation started for season 20242025",
        )

        with patch.object(
            reconciliation._service, "run_batch_reconciliation", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.post(
                "/api/v1/reconciliation/run",
                json={"season_id": 20242025, "force": False},
            )

            assert response.status_code == 202
            data = response.json()
            assert data["run_id"] == 1234567890
            assert data["status"] == "started"

    def test_run_reconciliation_with_force(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Batch reconciliation passes force flag."""
        mock_response = BatchReconciliationResponse(
            run_id=1234567890,
            status="started",
            message="Reconciliation started for season 20242025",
        )

        with patch.object(
            reconciliation._service, "run_batch_reconciliation", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.post(
                "/api/v1/reconciliation/run",
                json={"season_id": 20242025, "force": True},
            )

            assert response.status_code == 202
            mock_method.assert_called_once()
            call_args = mock_method.call_args
            assert call_args.kwargs["force"] is True


# =============================================================================
# Export Endpoint Tests
# =============================================================================


class TestExportEndpoint:
    """Test GET /reconciliation/export/{run_id} endpoint."""

    def test_export_json_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Export returns JSON with discrepancies."""
        mock_response = ReconciliationGamesResponse(
            games=[
                GameReconciliation(
                    game_id=2024020001,
                    game_date=date(2024, 10, 8),
                    home_team="BOS",
                    away_team="FLA",
                    checks_passed=3,
                    checks_failed=1,
                    discrepancies=[
                        ReconciliationCheck(
                            rule_name="goal_count_pbp_vs_boxscore",
                            passed=False,
                            source_a="play_by_play",
                            source_a_value=5,
                            source_b="boxscore",
                            source_b_value=6,
                            difference=1.0,
                            entity_type="game",
                            entity_id="2024020001",
                        )
                    ],
                )
            ],
            total=1,
            page=1,
            page_size=10000,
            pages=1,
        )

        with patch.object(
            reconciliation._service,
            "get_games_with_discrepancies",
            new_callable=AsyncMock,
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get(
                "/api/v1/reconciliation/export/123?season_id=20242025&format=json"
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
            assert "attachment" in response.headers["content-disposition"]

            data = response.json()
            assert data["run_id"] == 123
            assert data["season_id"] == 20242025
            assert len(data["games"]) == 1

    def test_export_csv_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Export returns CSV with discrepancies."""
        mock_response = ReconciliationGamesResponse(
            games=[
                GameReconciliation(
                    game_id=2024020001,
                    game_date=date(2024, 10, 8),
                    home_team="BOS",
                    away_team="FLA",
                    checks_passed=3,
                    checks_failed=1,
                    discrepancies=[
                        ReconciliationCheck(
                            rule_name="goal_count_pbp_vs_boxscore",
                            passed=False,
                            source_a="play_by_play",
                            source_a_value=5,
                            source_b="boxscore",
                            source_b_value=6,
                            difference=1.0,
                            entity_type="game",
                            entity_id="2024020001",
                        )
                    ],
                )
            ],
            total=1,
            page=1,
            page_size=10000,
            pages=1,
        )

        with patch.object(
            reconciliation._service,
            "get_games_with_discrepancies",
            new_callable=AsyncMock,
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get(
                "/api/v1/reconciliation/export/123?season_id=20242025&format=csv"
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            assert "attachment" in response.headers["content-disposition"]

            # Check CSV content
            content = response.text
            lines = content.strip().split("\n")
            assert len(lines) == 2  # Header + 1 data row
            assert "game_id" in lines[0]
            assert "2024020001" in lines[1]

    def test_export_empty_results(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Export handles empty results."""
        mock_response = ReconciliationGamesResponse(
            games=[],
            total=0,
            page=1,
            page_size=10000,
            pages=0,
        )

        with patch.object(
            reconciliation._service,
            "get_games_with_discrepancies",
            new_callable=AsyncMock,
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get(
                "/api/v1/reconciliation/export/123?season_id=20242025&format=json"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["games"] == []
            assert data["total_games"] == 0
