"""Unit tests for validation router endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nhl_api.viewer.dependencies import set_db_service
from nhl_api.viewer.routers import validation
from nhl_api.viewer.schemas.validation import (
    DiscrepanciesResponse,
    DiscrepancyDetail,
    DiscrepancySummary,
    QualityScore,
    QualityScoresResponse,
    ValidationResult,
    ValidationRule,
    ValidationRulesResponse,
    ValidationRunDetail,
    ValidationRunsResponse,
    ValidationRunSummary,
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
    """Create a test FastAPI app with validation router."""
    app = FastAPI()
    app.include_router(validation.router, prefix="/api/v1")
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
# Validation Rules Endpoint Tests
# =============================================================================


class TestValidationRulesEndpoint:
    """Test GET /validation/rules endpoint."""

    def test_get_rules_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Rules endpoint returns 200 with list of rules."""
        mock_response = ValidationRulesResponse(
            rules=[
                ValidationRule(
                    rule_id=1,
                    name="goal_reconciliation",
                    description="Goals match between sources",
                    category="cross_file",
                    severity="error",
                    is_active=True,
                    config=None,
                ),
                ValidationRule(
                    rule_id=2,
                    name="toi_validation",
                    description="TOI matches between sources",
                    category="cross_file",
                    severity="warning",
                    is_active=True,
                    config=None,
                ),
            ],
            total=2,
        )

        with patch.object(
            validation._service, "get_validation_rules", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/rules")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["rules"]) == 2
            assert data["rules"][0]["name"] == "goal_reconciliation"

    def test_get_rules_with_category_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Rules endpoint accepts category filter."""
        mock_response = ValidationRulesResponse(
            rules=[
                ValidationRule(
                    rule_id=1,
                    name="goal_reconciliation",
                    description="Goals match",
                    category="cross_file",
                    severity="error",
                    is_active=True,
                    config=None,
                ),
            ],
            total=1,
        )

        with patch.object(
            validation._service, "get_validation_rules", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/rules?category=cross_file")

            assert response.status_code == 200
            mock_method.assert_called_once()

    def test_get_rules_invalid_category(self, test_client: TestClient) -> None:
        """Rules endpoint rejects invalid category."""
        response = test_client.get("/api/v1/validation/rules?category=invalid_category")
        assert response.status_code == 422

    def test_get_rules_empty(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Rules endpoint returns empty list when no rules."""
        mock_response = ValidationRulesResponse(rules=[], total=0)

        with patch.object(
            validation._service, "get_validation_rules", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/rules")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["rules"] == []


# =============================================================================
# Validation Runs Endpoint Tests
# =============================================================================


class TestValidationRunsEndpoint:
    """Test GET /validation/runs endpoint."""

    def test_get_runs_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Runs endpoint returns 200 with paginated list."""
        now = datetime.now(UTC)
        mock_response = ValidationRunsResponse(
            runs=[
                ValidationRunSummary(
                    run_id=1,
                    season_id=20242025,
                    started_at=now,
                    completed_at=now,
                    status="completed",
                    rules_checked=10,
                    total_passed=8,
                    total_failed=2,
                    total_warnings=1,
                ),
            ],
            total=1,
            page=1,
            page_size=20,
            pages=1,
        )

        with patch.object(
            validation._service, "get_validation_runs", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/runs")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["runs"]) == 1
            assert data["runs"][0]["status"] == "completed"

    def test_get_runs_with_season_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Runs endpoint accepts season_id filter."""
        mock_response = ValidationRunsResponse(
            runs=[], total=0, page=1, page_size=20, pages=1
        )

        with patch.object(
            validation._service, "get_validation_runs", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/runs?season_id=20242025")

            assert response.status_code == 200
            mock_method.assert_called_once()

    def test_get_runs_pagination(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Runs endpoint accepts pagination parameters."""
        mock_response = ValidationRunsResponse(
            runs=[], total=0, page=2, page_size=50, pages=0
        )

        with patch.object(
            validation._service, "get_validation_runs", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/runs?page=2&page_size=50")

            assert response.status_code == 200


class TestValidationRunDetailEndpoint:
    """Test GET /validation/runs/{run_id} endpoint."""

    def test_get_run_detail_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Run detail endpoint returns 200 with results."""
        now = datetime.now(UTC)
        mock_response = ValidationRunDetail(
            run_id=1,
            season_id=20242025,
            started_at=now,
            completed_at=now,
            status="completed",
            rules_checked=10,
            total_passed=9,
            total_failed=1,
            total_warnings=0,
            results=[
                ValidationResult(
                    result_id=1,
                    rule_id=1,
                    rule_name="goal_reconciliation",
                    game_id=2024020001,
                    passed=False,
                    severity="error",
                    message="Goal count mismatch",
                    details={"expected": 3, "actual": 2},
                    source_values={"pbp": 3, "boxscore": 2},
                    created_at=now,
                ),
            ],
            metadata=None,
        )

        with patch.object(
            validation._service, "get_validation_run", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/runs/1")

            assert response.status_code == 200
            data = response.json()
            assert data["run_id"] == 1
            assert len(data["results"]) == 1

    def test_get_run_detail_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Run detail endpoint returns 404 for nonexistent run."""
        with patch.object(
            validation._service, "get_validation_run", new_callable=AsyncMock
        ) as mock_method:
            mock_method.side_effect = ValueError("Validation run 999 not found")

            response = test_client.get("/api/v1/validation/runs/999")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]


# =============================================================================
# Quality Scores Endpoint Tests
# =============================================================================


class TestQualityScoresEndpoint:
    """Test GET /validation/scores endpoint."""

    def test_get_scores_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Scores endpoint returns 200 with paginated list."""
        now = datetime.now(UTC)
        mock_response = QualityScoresResponse(
            scores=[
                QualityScore(
                    score_id=1,
                    season_id=20242025,
                    game_id=None,
                    entity_type="season",
                    entity_id="20242025",
                    completeness_score=95.0,
                    accuracy_score=98.0,
                    consistency_score=96.0,
                    timeliness_score=100.0,
                    overall_score=97.25,
                    total_checks=100,
                    passed_checks=97,
                    failed_checks=3,
                    warning_checks=2,
                    calculated_at=now,
                ),
            ],
            total=1,
            page=1,
            page_size=20,
            pages=1,
        )

        with patch.object(
            validation._service, "get_quality_scores", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/scores")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["scores"][0]["overall_score"] == 97.25

    def test_get_scores_with_entity_type_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Scores endpoint accepts entity_type filter."""
        mock_response = QualityScoresResponse(
            scores=[], total=0, page=1, page_size=20, pages=1
        )

        with patch.object(
            validation._service, "get_quality_scores", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/scores?entity_type=game")

            assert response.status_code == 200


class TestEntityScoreEndpoint:
    """Test GET /validation/scores/{entity_type}/{entity_id} endpoint."""

    def test_get_entity_score_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Entity score endpoint returns 200 with score."""
        now = datetime.now(UTC)
        mock_response = QualityScore(
            score_id=1,
            season_id=20242025,
            game_id=2024020001,
            entity_type="game",
            entity_id="2024020001",
            completeness_score=100.0,
            accuracy_score=95.0,
            consistency_score=100.0,
            timeliness_score=100.0,
            overall_score=98.75,
            total_checks=20,
            passed_checks=19,
            failed_checks=1,
            warning_checks=0,
            calculated_at=now,
        )

        with patch.object(
            validation._service, "get_entity_score", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/scores/game/2024020001")

            assert response.status_code == 200
            data = response.json()
            assert data["entity_type"] == "game"
            assert data["entity_id"] == "2024020001"

    def test_get_entity_score_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Entity score endpoint returns 404 when no score."""
        with patch.object(
            validation._service, "get_entity_score", new_callable=AsyncMock
        ) as mock_method:
            mock_method.side_effect = ValueError(
                "No quality score found for game 999999"
            )

            response = test_client.get("/api/v1/validation/scores/game/999999")

            assert response.status_code == 404


# =============================================================================
# Discrepancies Endpoint Tests
# =============================================================================


class TestDiscrepanciesEndpoint:
    """Test GET /validation/discrepancies endpoint."""

    def test_get_discrepancies_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Discrepancies endpoint returns 200 with paginated list."""
        now = datetime.now(UTC)
        mock_response = DiscrepanciesResponse(
            discrepancies=[
                DiscrepancySummary(
                    discrepancy_id=1,
                    rule_id=1,
                    rule_name="goal_reconciliation",
                    game_id=2024020001,
                    season_id=20242025,
                    entity_type="goal",
                    entity_id="goal_1",
                    field_name="count",
                    source_a="pbp",
                    source_b="boxscore",
                    resolution_status="open",
                    created_at=now,
                ),
            ],
            total=1,
            page=1,
            page_size=20,
            pages=1,
        )

        with patch.object(
            validation._service, "get_discrepancies", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/discrepancies")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["discrepancies"][0]["resolution_status"] == "open"

    def test_get_discrepancies_with_status_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Discrepancies endpoint accepts status filter."""
        mock_response = DiscrepanciesResponse(
            discrepancies=[], total=0, page=1, page_size=20, pages=1
        )

        with patch.object(
            validation._service, "get_discrepancies", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get(
                "/api/v1/validation/discrepancies?status=resolved"
            )

            assert response.status_code == 200

    def test_get_discrepancies_with_entity_type_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Discrepancies endpoint accepts entity_type filter."""
        mock_response = DiscrepanciesResponse(
            discrepancies=[], total=0, page=1, page_size=20, pages=1
        )

        with patch.object(
            validation._service, "get_discrepancies", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get(
                "/api/v1/validation/discrepancies?entity_type=goal"
            )

            assert response.status_code == 200


class TestDiscrepancyDetailEndpoint:
    """Test GET /validation/discrepancies/{discrepancy_id} endpoint."""

    def test_get_discrepancy_detail_success(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Discrepancy detail endpoint returns 200 with full details."""
        now = datetime.now(UTC)
        mock_response = DiscrepancyDetail(
            discrepancy_id=1,
            rule_id=1,
            rule_name="goal_reconciliation",
            game_id=2024020001,
            season_id=20242025,
            entity_type="goal",
            entity_id="goal_1",
            field_name="count",
            source_a="pbp",
            source_a_value="3",
            source_b="boxscore",
            source_b_value="2",
            resolution_status="open",
            resolution_notes=None,
            created_at=now,
            resolved_at=None,
            result_id=1,
        )

        with patch.object(
            validation._service, "get_discrepancy", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = mock_response

            response = test_client.get("/api/v1/validation/discrepancies/1")

            assert response.status_code == 200
            data = response.json()
            assert data["discrepancy_id"] == 1
            assert data["source_a_value"] == "3"
            assert data["source_b_value"] == "2"

    def test_get_discrepancy_detail_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Discrepancy detail endpoint returns 404 for nonexistent."""
        with patch.object(
            validation._service, "get_discrepancy", new_callable=AsyncMock
        ) as mock_method:
            mock_method.side_effect = ValueError("Discrepancy 999 not found")

            response = test_client.get("/api/v1/validation/discrepancies/999")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
