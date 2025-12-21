"""Reconciliation service for cross-source data validation.

This service compares data from multiple sources (NHL JSON API, Play-by-Play,
Shift Charts) to identify discrepancies and ensure data quality.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

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
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# Tolerance thresholds
TOI_TOLERANCE_SECONDS = 5  # Allow 5 second difference in TOI comparisons


@dataclass
class ReconciliationService:
    """Service for reconciling data across multiple sources.

    Compares:
    - Goals: PBP events vs Boxscore vs Player stats sum
    - TOI: Shift charts vs Boxscore
    - Penalties: PBP events vs Team stats
    - Shots: PBP events vs Team stats
    """

    _instance: ReconciliationService | None = field(default=None, repr=False)

    @classmethod
    def get_instance(cls) -> ReconciliationService:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================================
    # Dashboard Summary
    # =========================================================================

    async def get_dashboard_summary(
        self, db: DatabaseService, season_id: int
    ) -> ReconciliationDashboardResponse:
        """Get dashboard summary with aggregated reconciliation statistics.

        Args:
            db: Database service
            season_id: Season ID (e.g., 20242025)

        Returns:
            Dashboard response with summary statistics
        """
        # Get total games for season
        total_games = await db.fetchval(
            "SELECT COUNT(*) FROM games WHERE season_id = $1 AND game_state = 'OFF'",
            season_id,
        )

        # Run reconciliation checks for all games
        goal_checks = await self._get_goal_discrepancies(db, season_id)
        toi_checks = await self._get_toi_discrepancies(db, season_id)
        penalty_checks = await self._get_penalty_discrepancies(db, season_id)
        shot_checks = await self._get_shot_discrepancies(db, season_id)

        # Aggregate all checks
        all_checks = goal_checks + toi_checks + penalty_checks + shot_checks
        total_checks = len(all_checks)
        failed_checks = [c for c in all_checks if not c.passed]
        passed_checks = total_checks - len(failed_checks)

        # Count games with discrepancies
        games_with_issues: set[str] = set()
        for check in failed_checks:
            games_with_issues.add(check.entity_id)

        # Calculate rates
        pass_rate = passed_checks / total_checks if total_checks > 0 else 1.0
        goal_passed = sum(1 for c in goal_checks if c.passed)
        goal_reconciliation_rate = (
            goal_passed / len(goal_checks) if goal_checks else 1.0
        )
        penalty_passed = sum(1 for c in penalty_checks if c.passed)
        penalty_reconciliation_rate = (
            penalty_passed / len(penalty_checks) if penalty_checks else 1.0
        )
        toi_passed = sum(1 for c in toi_checks if c.passed)
        toi_reconciliation_rate = toi_passed / len(toi_checks) if toi_checks else 1.0

        # Get problem games (most discrepancies)
        game_discrepancy_count: dict[str, int] = {}
        for check in failed_checks:
            game_discrepancy_count[check.entity_id] = (
                game_discrepancy_count.get(check.entity_id, 0) + 1
            )

        # Sort by count descending, take top 10
        sorted_games = sorted(
            game_discrepancy_count.items(), key=lambda x: x[1], reverse=True
        )[:10]

        problem_games: list[GameReconciliation] = []
        for game_id_str, disc_count in sorted_games:
            game_id = int(game_id_str)
            game_info = await db.fetchrow(
                """
                SELECT g.game_id, g.game_date, ht.abbreviation as home_team,
                       at.abbreviation as away_team
                FROM games g
                JOIN teams ht ON g.home_team_id = ht.team_id
                JOIN teams at ON g.away_team_id = at.team_id
                WHERE g.game_id = $1 AND g.season_id = $2
                """,
                game_id,
                season_id,
            )
            if game_info:
                discrepancies = [c for c in failed_checks if c.entity_id == game_id_str]
                problem_games.append(
                    GameReconciliation(
                        game_id=game_info["game_id"],
                        game_date=game_info["game_date"],
                        home_team=game_info["home_team"],
                        away_team=game_info["away_team"],
                        checks_passed=0,  # Will be filled if needed
                        checks_failed=disc_count,
                        discrepancies=discrepancies,
                    )
                )

        summary = ReconciliationSummary(
            season_id=season_id,
            total_games=total_games or 0,
            games_with_discrepancies=len(games_with_issues),
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=len(failed_checks),
            pass_rate=pass_rate,
            goal_reconciliation_rate=goal_reconciliation_rate,
            penalty_reconciliation_rate=penalty_reconciliation_rate,
            toi_reconciliation_rate=toi_reconciliation_rate,
            problem_games=problem_games,
        )

        # Calculate quality score (0-100)
        quality_score = pass_rate * 100

        return ReconciliationDashboardResponse(
            summary=summary,
            last_run=None,  # TODO: Track last run time
            quality_score=quality_score,
            timestamp=datetime.now(UTC),
        )

    # =========================================================================
    # Game-Level Reconciliation
    # =========================================================================

    async def get_game_reconciliation(
        self, db: DatabaseService, game_id: int
    ) -> GameReconciliationDetail:
        """Get detailed reconciliation for a single game.

        Args:
            db: Database service
            game_id: NHL game ID

        Returns:
            Detailed game reconciliation with all checks
        """
        # Get game info
        game_info = await db.fetchrow(
            """
            SELECT g.game_id, g.season_id, g.game_date,
                   ht.abbreviation as home_team, at.abbreviation as away_team
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            WHERE g.game_id = $1
            """,
            game_id,
        )

        if not game_info:
            raise ValueError(f"Game {game_id} not found")

        season_id = game_info["season_id"]

        # Run all checks for this game
        all_checks: list[ReconciliationCheck] = []

        # Goal checks
        goal_checks = await self._check_game_goals(db, game_id, season_id)
        all_checks.extend(goal_checks)

        # TOI checks
        toi_checks = await self._check_game_toi(db, game_id, season_id)
        all_checks.extend(toi_checks)

        # Penalty checks
        penalty_checks = await self._check_game_penalties(db, game_id, season_id)
        all_checks.extend(penalty_checks)

        # Shot checks
        shot_checks = await self._check_game_shots(db, game_id, season_id)
        all_checks.extend(shot_checks)

        # Determine sources available
        sources_available: list[str] = []
        sources_missing: list[str] = []

        # Check if we have boxscore data
        has_boxscore = await db.fetchval(
            "SELECT COUNT(*) > 0 FROM game_team_stats WHERE game_id = $1",
            game_id,
        )
        if has_boxscore:
            sources_available.append("boxscore")
        else:
            sources_missing.append("boxscore")

        # Check if we have PBP data
        has_pbp = await db.fetchval(
            "SELECT COUNT(*) > 0 FROM game_events WHERE game_id = $1",
            game_id,
        )
        if has_pbp:
            sources_available.append("play_by_play")
        else:
            sources_missing.append("play_by_play")

        # Check if we have shift data
        has_shifts = await db.fetchval(
            "SELECT COUNT(*) > 0 FROM game_shifts WHERE game_id = $1",
            game_id,
        )
        if has_shifts:
            sources_available.append("shift_charts")
        else:
            sources_missing.append("shift_charts")

        discrepancies = [c for c in all_checks if not c.passed]

        return GameReconciliationDetail(
            game_id=game_info["game_id"],
            game_date=game_info["game_date"],
            home_team=game_info["home_team"],
            away_team=game_info["away_team"],
            checks_passed=len(all_checks) - len(discrepancies),
            checks_failed=len(discrepancies),
            discrepancies=discrepancies,
            all_checks=all_checks,
            sources_available=sources_available,
            sources_missing=sources_missing,
        )

    # =========================================================================
    # Games List
    # =========================================================================

    async def get_games_with_discrepancies(
        self,
        db: DatabaseService,
        season_id: int,
        page: int = 1,
        page_size: int = 20,
        discrepancy_type: str | None = None,
    ) -> ReconciliationGamesResponse:
        """Get paginated list of games with reconciliation status.

        Args:
            db: Database service
            season_id: Season ID
            page: Page number (1-indexed)
            page_size: Items per page
            discrepancy_type: Filter by type (goal, toi, penalty, shot)

        Returns:
            Paginated games response
        """
        # Get all completed games
        games = await db.fetch(
            """
            SELECT g.game_id, g.game_date, ht.abbreviation as home_team,
                   at.abbreviation as away_team
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            WHERE g.season_id = $1 AND g.game_state = 'OFF'
            ORDER BY g.game_date DESC
            """,
            season_id,
        )

        # Run checks based on filter
        all_game_results: list[GameReconciliation] = []

        for game in games:
            game_id = game["game_id"]
            checks: list[ReconciliationCheck] = []

            if discrepancy_type is None or discrepancy_type == "goal":
                checks.extend(await self._check_game_goals(db, game_id, season_id))
            if discrepancy_type is None or discrepancy_type == "toi":
                checks.extend(await self._check_game_toi(db, game_id, season_id))
            if discrepancy_type is None or discrepancy_type == "penalty":
                checks.extend(await self._check_game_penalties(db, game_id, season_id))
            if discrepancy_type is None or discrepancy_type == "shot":
                checks.extend(await self._check_game_shots(db, game_id, season_id))

            discrepancies = [c for c in checks if not c.passed]

            all_game_results.append(
                GameReconciliation(
                    game_id=game["game_id"],
                    game_date=game["game_date"],
                    home_team=game["home_team"],
                    away_team=game["away_team"],
                    checks_passed=len(checks) - len(discrepancies),
                    checks_failed=len(discrepancies),
                    discrepancies=discrepancies,
                )
            )

        # Filter to only games with discrepancies
        games_with_issues = [g for g in all_game_results if g.checks_failed > 0]

        # Sort by number of discrepancies (most first)
        games_with_issues.sort(key=lambda g: g.checks_failed, reverse=True)

        # Paginate
        total = len(games_with_issues)
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        start = (page - 1) * page_size
        end = start + page_size

        return ReconciliationGamesResponse(
            games=games_with_issues[start:end],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    # =========================================================================
    # Batch Reconciliation
    # =========================================================================

    async def run_batch_reconciliation(
        self, db: DatabaseService, season_id: int, force: bool = False
    ) -> BatchReconciliationResponse:
        """Trigger batch reconciliation for a season.

        Args:
            db: Database service
            season_id: Season ID
            force: Force re-run even if already reconciled

        Returns:
            Batch reconciliation response with run_id
        """
        # For now, reconciliation is run on-demand (no persistence)
        # In the future, we could store results in a reconciliation_results table

        # Create a fake run_id based on timestamp
        run_id = int(datetime.now(UTC).timestamp())

        return BatchReconciliationResponse(
            run_id=run_id,
            status="started",
            message=f"Reconciliation started for season {season_id}",
        )

    # =========================================================================
    # Individual Check Methods
    # =========================================================================

    async def _get_goal_discrepancies(
        self, db: DatabaseService, season_id: int
    ) -> list[ReconciliationCheck]:
        """Get goal count discrepancies across all games in a season."""
        checks: list[ReconciliationCheck] = []

        # Get all completed games
        games = await db.fetch(
            "SELECT game_id FROM games WHERE season_id = $1 AND game_state = 'OFF'",
            season_id,
        )

        for game in games:
            game_checks = await self._check_game_goals(db, game["game_id"], season_id)
            checks.extend(game_checks)

        return checks

    async def _get_toi_discrepancies(
        self, db: DatabaseService, season_id: int
    ) -> list[ReconciliationCheck]:
        """Get TOI discrepancies across all games in a season."""
        checks: list[ReconciliationCheck] = []

        games = await db.fetch(
            "SELECT game_id FROM games WHERE season_id = $1 AND game_state = 'OFF'",
            season_id,
        )

        for game in games:
            game_checks = await self._check_game_toi(db, game["game_id"], season_id)
            checks.extend(game_checks)

        return checks

    async def _get_penalty_discrepancies(
        self, db: DatabaseService, season_id: int
    ) -> list[ReconciliationCheck]:
        """Get penalty discrepancies across all games in a season."""
        checks: list[ReconciliationCheck] = []

        games = await db.fetch(
            "SELECT game_id FROM games WHERE season_id = $1 AND game_state = 'OFF'",
            season_id,
        )

        for game in games:
            game_checks = await self._check_game_penalties(
                db, game["game_id"], season_id
            )
            checks.extend(game_checks)

        return checks

    async def _get_shot_discrepancies(
        self, db: DatabaseService, season_id: int
    ) -> list[ReconciliationCheck]:
        """Get shot count discrepancies across all games in a season."""
        checks: list[ReconciliationCheck] = []

        games = await db.fetch(
            "SELECT game_id FROM games WHERE season_id = $1 AND game_state = 'OFF'",
            season_id,
        )

        for game in games:
            game_checks = await self._check_game_shots(db, game["game_id"], season_id)
            checks.extend(game_checks)

        return checks

    # =========================================================================
    # Per-Game Check Methods
    # =========================================================================

    async def _check_game_goals(
        self, db: DatabaseService, game_id: int, season_id: int
    ) -> list[ReconciliationCheck]:
        """Check goal counts from multiple sources for a single game."""
        checks: list[ReconciliationCheck] = []

        # Get goals from PBP events
        pbp_goals = await db.fetchval(
            """
            SELECT COUNT(*) FROM game_events
            WHERE game_id = $1 AND event_type = 'goal'
            """,
            game_id,
        )

        # Get goals from team stats (boxscore)
        boxscore_goals = await db.fetchval(
            """
            SELECT COALESCE(SUM(goals), 0) FROM game_team_stats
            WHERE game_id = $1 AND season_id = $2
            """,
            game_id,
            season_id,
        )

        # Get goals from player stats sum
        player_goals = await db.fetchval(
            """
            SELECT COALESCE(SUM(goals), 0) FROM game_skater_stats
            WHERE game_id = $1 AND season_id = $2
            """,
            game_id,
            season_id,
        )

        # Compare PBP vs Boxscore
        if pbp_goals is not None and boxscore_goals is not None:
            passed = pbp_goals == boxscore_goals
            checks.append(
                ReconciliationCheck(
                    rule_name="goal_count_pbp_vs_boxscore",
                    passed=passed,
                    source_a="play_by_play",
                    source_a_value=pbp_goals,
                    source_b="boxscore",
                    source_b_value=boxscore_goals,
                    difference=abs(pbp_goals - boxscore_goals) if not passed else None,
                    entity_type="game",
                    entity_id=str(game_id),
                )
            )

        # Compare Boxscore vs Player Stats
        if boxscore_goals is not None and player_goals is not None:
            passed = boxscore_goals == player_goals
            checks.append(
                ReconciliationCheck(
                    rule_name="goal_count_boxscore_vs_players",
                    passed=passed,
                    source_a="boxscore",
                    source_a_value=boxscore_goals,
                    source_b="player_stats_sum",
                    source_b_value=player_goals,
                    difference=(
                        abs(boxscore_goals - player_goals) if not passed else None
                    ),
                    entity_type="game",
                    entity_id=str(game_id),
                )
            )

        return checks

    async def _check_game_toi(
        self, db: DatabaseService, game_id: int, season_id: int
    ) -> list[ReconciliationCheck]:
        """Check TOI from shift charts vs boxscore for a single game."""
        checks: list[ReconciliationCheck] = []

        # Get players with both shift and boxscore data
        players = await db.fetch(
            """
            SELECT DISTINCT gss.player_id
            FROM game_skater_stats gss
            WHERE gss.game_id = $1 AND gss.season_id = $2
              AND gss.toi_seconds IS NOT NULL
            """,
            game_id,
            season_id,
        )

        for player in players:
            player_id = player["player_id"]

            # Get TOI from shifts
            shift_toi = await db.fetchval(
                """
                SELECT COALESCE(SUM(duration_seconds), 0)
                FROM game_shifts
                WHERE game_id = $1 AND player_id = $2 AND is_goal_event = FALSE
                """,
                game_id,
                player_id,
            )

            # Get TOI from boxscore
            boxscore_toi = await db.fetchval(
                """
                SELECT toi_seconds FROM game_skater_stats
                WHERE game_id = $1 AND season_id = $2 AND player_id = $3
                """,
                game_id,
                season_id,
                player_id,
            )

            if shift_toi is not None and boxscore_toi is not None:
                difference = abs(shift_toi - boxscore_toi)
                passed = difference <= TOI_TOLERANCE_SECONDS

                checks.append(
                    ReconciliationCheck(
                        rule_name="toi_shifts_vs_boxscore",
                        passed=passed,
                        source_a="shift_charts",
                        source_a_value=shift_toi,
                        source_b="boxscore",
                        source_b_value=boxscore_toi,
                        difference=difference if not passed else None,
                        entity_type="player",
                        entity_id=str(game_id),  # Group by game for summary
                    )
                )

        return checks

    async def _check_game_penalties(
        self, db: DatabaseService, game_id: int, season_id: int
    ) -> list[ReconciliationCheck]:
        """Check penalty counts from PBP vs team stats."""
        checks: list[ReconciliationCheck] = []

        # Get penalty count from PBP
        pbp_penalties = await db.fetchval(
            """
            SELECT COUNT(*) FROM game_events
            WHERE game_id = $1 AND event_type = 'penalty'
            """,
            game_id,
        )

        # Get total PIM from team stats
        team_pim = await db.fetchval(
            """
            SELECT COALESCE(SUM(pim), 0) FROM game_team_stats
            WHERE game_id = $1 AND season_id = $2
            """,
            game_id,
            season_id,
        )

        # Note: We can't directly compare count vs PIM since a penalty can be
        # 2, 4, 5, 10 minutes. But we can flag if PBP has penalties but team
        # stats show 0 PIM (or vice versa).
        if pbp_penalties is not None and team_pim is not None:
            # Check for consistency: both should be 0 or both > 0
            passed = (pbp_penalties == 0 and team_pim == 0) or (
                pbp_penalties > 0 and team_pim > 0
            )

            checks.append(
                ReconciliationCheck(
                    rule_name="penalty_consistency",
                    passed=passed,
                    source_a="play_by_play_count",
                    source_a_value=pbp_penalties,
                    source_b="team_stats_pim",
                    source_b_value=team_pim,
                    difference=None,  # Not directly comparable
                    entity_type="game",
                    entity_id=str(game_id),
                )
            )

        return checks

    async def _check_game_shots(
        self, db: DatabaseService, game_id: int, season_id: int
    ) -> list[ReconciliationCheck]:
        """Check shot counts from PBP vs team stats."""
        checks: list[ReconciliationCheck] = []

        # Get shots from PBP (shots on goal)
        pbp_shots = await db.fetchval(
            """
            SELECT COUNT(*) FROM game_events
            WHERE game_id = $1 AND event_type = 'shot-on-goal'
            """,
            game_id,
        )

        # Get shots from team stats
        team_shots = await db.fetchval(
            """
            SELECT COALESCE(SUM(shots), 0) FROM game_team_stats
            WHERE game_id = $1 AND season_id = $2
            """,
            game_id,
            season_id,
        )

        # Note: Goals are also shots on goal, so we need to add them
        pbp_goals = await db.fetchval(
            """
            SELECT COUNT(*) FROM game_events
            WHERE game_id = $1 AND event_type = 'goal'
            """,
            game_id,
        )

        if pbp_shots is not None and pbp_goals is not None and team_shots is not None:
            total_pbp_sog = pbp_shots + pbp_goals
            passed = total_pbp_sog == team_shots

            checks.append(
                ReconciliationCheck(
                    rule_name="shot_count_pbp_vs_boxscore",
                    passed=passed,
                    source_a="play_by_play",
                    source_a_value=total_pbp_sog,
                    source_b="boxscore",
                    source_b_value=team_shots,
                    difference=abs(total_pbp_sog - team_shots) if not passed else None,
                    entity_type="game",
                    entity_id=str(game_id),
                )
            )

        return checks
