"""Unit tests for ReconciliationService."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from nhl_api.viewer.services.reconciliation_service import (
    TOI_TOLERANCE_SECONDS,
    ReconciliationService,
)


@pytest.fixture
def service() -> ReconciliationService:
    """Create a ReconciliationService instance."""
    return ReconciliationService()


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock DatabaseService."""
    mock = MagicMock()
    mock.fetchval = AsyncMock(return_value=0)
    mock.fetch = AsyncMock(return_value=[])
    mock.fetchrow = AsyncMock(return_value=None)
    mock.execute = AsyncMock(return_value="OK")
    return mock


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_instance_returns_same_instance(self) -> None:
        """get_instance should return the same instance."""
        # Reset singleton for clean test
        ReconciliationService._instance = None

        instance1 = ReconciliationService.get_instance()
        instance2 = ReconciliationService.get_instance()

        assert instance1 is instance2

        # Cleanup
        ReconciliationService._instance = None


# =============================================================================
# Goal Reconciliation Tests
# =============================================================================


class TestGoalReconciliation:
    """Test goal count reconciliation logic."""

    @pytest.mark.asyncio
    async def test_goals_match_all_sources(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """All three sources agree on goal count."""
        # PBP goals, boxscore goals, player goals all = 5
        mock_db.fetchval = AsyncMock(return_value=5)

        checks = await service._check_game_goals(mock_db, 2024020001, 20242025)

        assert len(checks) == 2
        assert all(c.passed for c in checks)
        assert checks[0].rule_name == "goal_count_pbp_vs_boxscore"
        assert checks[1].rule_name == "goal_count_boxscore_vs_players"

    @pytest.mark.asyncio
    async def test_goals_pbp_boxscore_mismatch(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """PBP and boxscore disagree on goal count."""
        # Return different values for each query
        call_count = 0

        async def side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # PBP goals
                return 5
            elif call_count == 2:  # Boxscore goals
                return 6
            else:  # Player goals
                return 6

        mock_db.fetchval = AsyncMock(side_effect=side_effect)

        checks = await service._check_game_goals(mock_db, 2024020001, 20242025)

        assert len(checks) == 2
        # First check (PBP vs Boxscore) should fail
        assert not checks[0].passed
        assert checks[0].difference == 1.0
        assert checks[0].source_a_value == 5
        assert checks[0].source_b_value == 6

    @pytest.mark.asyncio
    async def test_goals_boxscore_player_mismatch(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Boxscore and player stats sum disagree."""
        call_count = 0

        async def side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # PBP goals
                return 5
            elif call_count == 2:  # Boxscore goals
                return 5
            else:  # Player goals
                return 4  # Missing a goal in player stats

        mock_db.fetchval = AsyncMock(side_effect=side_effect)

        checks = await service._check_game_goals(mock_db, 2024020001, 20242025)

        assert len(checks) == 2
        # First check passes, second fails
        assert checks[0].passed
        assert not checks[1].passed
        assert checks[1].difference == 1.0


# =============================================================================
# TOI Reconciliation Tests
# =============================================================================


class TestTOIReconciliation:
    """Test time-on-ice reconciliation logic."""

    @pytest.mark.asyncio
    async def test_toi_matches_within_tolerance(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """TOI matches within 5 second tolerance."""
        # One player with TOI data
        mock_db.fetch = AsyncMock(return_value=[{"player_id": 8471214}])

        call_count = 0

        async def fetchval_side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Shift TOI
                return 1200  # 20 minutes
            else:  # Boxscore TOI
                return 1203  # 20:03 - within tolerance

        mock_db.fetchval = AsyncMock(side_effect=fetchval_side_effect)

        checks = await service._check_game_toi(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert checks[0].passed
        assert checks[0].rule_name == "toi_shifts_vs_boxscore"

    @pytest.mark.asyncio
    async def test_toi_exceeds_tolerance(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """TOI difference exceeds 5 second tolerance."""
        mock_db.fetch = AsyncMock(return_value=[{"player_id": 8471214}])

        call_count = 0

        async def fetchval_side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Shift TOI
                return 1200  # 20 minutes
            else:  # Boxscore TOI
                return 1210  # 10 seconds difference > 5 second tolerance

        mock_db.fetchval = AsyncMock(side_effect=fetchval_side_effect)

        checks = await service._check_game_toi(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert not checks[0].passed
        assert checks[0].difference == 10

    @pytest.mark.asyncio
    async def test_toi_exact_tolerance_boundary(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """TOI at exactly 5 second tolerance should pass."""
        mock_db.fetch = AsyncMock(return_value=[{"player_id": 8471214}])

        call_count = 0

        async def fetchval_side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 1200
            else:
                return 1200 + TOI_TOLERANCE_SECONDS  # Exactly at tolerance

        mock_db.fetchval = AsyncMock(side_effect=fetchval_side_effect)

        checks = await service._check_game_toi(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert checks[0].passed  # Exactly at tolerance should pass

    @pytest.mark.asyncio
    async def test_toi_no_players(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """No players with TOI data returns empty checks."""
        mock_db.fetch = AsyncMock(return_value=[])

        checks = await service._check_game_toi(mock_db, 2024020001, 20242025)

        assert len(checks) == 0


# =============================================================================
# Penalty Reconciliation Tests
# =============================================================================


class TestPenaltyReconciliation:
    """Test penalty reconciliation logic."""

    @pytest.mark.asyncio
    async def test_penalties_both_zero(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """No penalties in either source passes."""
        mock_db.fetchval = AsyncMock(return_value=0)

        checks = await service._check_game_penalties(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert checks[0].passed
        assert checks[0].rule_name == "penalty_consistency"

    @pytest.mark.asyncio
    async def test_penalties_both_nonzero(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Both sources have penalties passes."""
        call_count = 0

        async def side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # PBP penalty count
                return 5
            else:  # Team PIM
                return 14  # 5 penalties with various durations

        mock_db.fetchval = AsyncMock(side_effect=side_effect)

        checks = await service._check_game_penalties(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert checks[0].passed

    @pytest.mark.asyncio
    async def test_penalties_inconsistent_pbp_zero(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """PBP shows 0 penalties but team stats has PIM - fails."""
        call_count = 0

        async def side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # PBP penalty count
                return 0
            else:  # Team PIM
                return 4  # 2 minor penalties

        mock_db.fetchval = AsyncMock(side_effect=side_effect)

        checks = await service._check_game_penalties(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert not checks[0].passed

    @pytest.mark.asyncio
    async def test_penalties_inconsistent_pim_zero(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """PBP shows penalties but team stats has 0 PIM - fails."""
        call_count = 0

        async def side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # PBP penalty count
                return 3
            else:  # Team PIM
                return 0

        mock_db.fetchval = AsyncMock(side_effect=side_effect)

        checks = await service._check_game_penalties(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert not checks[0].passed


# =============================================================================
# Shot Reconciliation Tests
# =============================================================================


class TestShotReconciliation:
    """Test shot count reconciliation logic."""

    @pytest.mark.asyncio
    async def test_shots_match(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Shot counts match (shots + goals = total)."""
        call_count = 0

        async def side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # PBP shots on goal
                return 25
            elif call_count == 2:  # Team shots from boxscore
                return 30
            else:  # PBP goals
                return 5  # 25 + 5 = 30

        mock_db.fetchval = AsyncMock(side_effect=side_effect)

        checks = await service._check_game_shots(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert checks[0].passed
        assert checks[0].source_a_value == 30  # shots + goals
        assert checks[0].source_b_value == 30

    @pytest.mark.asyncio
    async def test_shots_mismatch(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Shot counts don't match."""
        call_count = 0

        async def side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # PBP shots on goal
                return 25
            elif call_count == 2:  # Team shots from boxscore
                return 32  # Different from PBP
            else:  # PBP goals
                return 5

        mock_db.fetchval = AsyncMock(side_effect=side_effect)

        checks = await service._check_game_shots(mock_db, 2024020001, 20242025)

        assert len(checks) == 1
        assert not checks[0].passed
        assert checks[0].difference == 2.0  # |30 - 32| = 2


# =============================================================================
# Dashboard Summary Tests
# =============================================================================


class TestDashboardSummary:
    """Test dashboard summary aggregation."""

    @pytest.mark.asyncio
    async def test_dashboard_no_games(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Dashboard with no games returns zero counts."""
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])

        result = await service.get_dashboard_summary(mock_db, 20242025)

        assert result.summary.total_games == 0
        assert result.summary.total_checks == 0
        assert result.summary.pass_rate == 1.0
        assert result.quality_score == 100.0

    @pytest.mark.asyncio
    async def test_dashboard_with_discrepancies(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Dashboard correctly aggregates discrepancies."""

        # Different fetch calls return different results based on query content
        async def fetch_side_effect(query: str, *args: Any) -> list[dict[str, Any]]:
            if "game_skater_stats" in query:
                # TOI player query - return empty to skip player checks
                return []
            elif "game_id" in query:
                # Games query
                return [{"game_id": 2024020001}]
            return []

        mock_db.fetch = AsyncMock(side_effect=fetch_side_effect)
        # Mock fetchval for various counts
        mock_db.fetchval = AsyncMock(return_value=5)

        result = await service.get_dashboard_summary(mock_db, 20242025)

        assert result.summary.season_id == 20242025
        assert result.timestamp is not None


# =============================================================================
# Game Reconciliation Detail Tests
# =============================================================================


class TestGameReconciliationDetail:
    """Test game-level reconciliation."""

    @pytest.mark.asyncio
    async def test_game_not_found(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Non-existent game raises ValueError."""
        mock_db.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Game 999999999 not found"):
            await service.get_game_reconciliation(mock_db, 999999999)

    @pytest.mark.asyncio
    async def test_game_with_all_sources(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Game with all data sources available."""
        mock_db.fetchrow = AsyncMock(
            return_value={
                "game_id": 2024020001,
                "season_id": 20242025,
                "game_date": date(2024, 10, 8),
                "home_team": "BOS",
                "away_team": "FLA",
            }
        )
        mock_db.fetchval = AsyncMock(return_value=True)  # All sources present
        mock_db.fetch = AsyncMock(return_value=[])  # No TOI checks

        result = await service.get_game_reconciliation(mock_db, 2024020001)

        assert result.game_id == 2024020001
        assert result.home_team == "BOS"
        assert result.away_team == "FLA"
        assert "boxscore" in result.sources_available
        assert "play_by_play" in result.sources_available
        assert "shift_charts" in result.sources_available

    @pytest.mark.asyncio
    async def test_game_missing_sources(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Game with missing data sources."""
        mock_db.fetchrow = AsyncMock(
            return_value={
                "game_id": 2024020001,
                "season_id": 20242025,
                "game_date": date(2024, 10, 8),
                "home_team": "BOS",
                "away_team": "FLA",
            }
        )
        mock_db.fetchval = AsyncMock(return_value=False)  # No sources
        mock_db.fetch = AsyncMock(return_value=[])

        result = await service.get_game_reconciliation(mock_db, 2024020001)

        assert "boxscore" in result.sources_missing
        assert "play_by_play" in result.sources_missing
        assert "shift_charts" in result.sources_missing


# =============================================================================
# Games List Tests
# =============================================================================


class TestGamesList:
    """Test games list with discrepancies."""

    @pytest.mark.asyncio
    async def test_pagination(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Pagination works correctly."""
        fetch_call_count = 0

        async def fetch_side_effect(*args: Any) -> list[dict[str, Any]]:
            nonlocal fetch_call_count
            fetch_call_count += 1
            if fetch_call_count == 1:  # First call is games list
                return [
                    {
                        "game_id": 2024020001,
                        "game_date": date(2024, 10, 8),
                        "home_team": "BOS",
                        "away_team": "FLA",
                    },
                    {
                        "game_id": 2024020002,
                        "game_date": date(2024, 10, 9),
                        "home_team": "NYR",
                        "away_team": "TOR",
                    },
                    {
                        "game_id": 2024020003,
                        "game_date": date(2024, 10, 10),
                        "home_team": "MTL",
                        "away_team": "DET",
                    },
                ]
            else:  # TOI player fetches return empty
                return []

        mock_db.fetch = AsyncMock(side_effect=fetch_side_effect)

        # Make all games have discrepancies
        call_count = 0

        async def fetchval_side_effect(*args: Any) -> int:
            nonlocal call_count
            call_count += 1
            # Alternate values to create discrepancies
            return call_count % 2

        mock_db.fetchval = AsyncMock(side_effect=fetchval_side_effect)

        result = await service.get_games_with_discrepancies(
            mock_db, 20242025, page=1, page_size=2
        )

        assert result.page == 1
        assert result.page_size == 2


# =============================================================================
# Batch Reconciliation Tests
# =============================================================================


class TestBatchReconciliation:
    """Test batch reconciliation trigger."""

    @pytest.mark.asyncio
    async def test_batch_returns_run_id(
        self, service: ReconciliationService, mock_db: MagicMock
    ) -> None:
        """Batch reconciliation returns a run_id."""
        result = await service.run_batch_reconciliation(mock_db, 20242025)

        assert result.run_id > 0
        assert result.status == "started"
        assert "20242025" in result.message
