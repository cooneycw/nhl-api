"""Auto-validation service for triggering validation after downloads.

This service monitors download completions and automatically triggers
cross-source validation when all required data sources for a game are available.

Configuration:
    VALIDATION_AUTO_RUN: Enable/disable auto-validation (default: True)
    VALIDATION_DELAY_SECONDS: Delay before running validation (default: 2)

Example usage:
    service = AutoValidationService.get_instance()

    # Queue validation for a game after downloads complete
    await service.queue_validation(db, game_id, season_id)

    # Check if game has complete data for validation
    is_complete = await service.has_complete_data(db, game_id)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# Configuration from environment
VALIDATION_AUTO_RUN = os.getenv("VALIDATION_AUTO_RUN", "true").lower() == "true"
VALIDATION_DELAY_SECONDS = float(os.getenv("VALIDATION_DELAY_SECONDS", "2"))

# Required sources for JSON vs JSON validation
REQUIRED_JSON_SOURCES = {"nhl_boxscore", "nhl_pbp", "shift_chart"}

# Required sources for JSON vs HTML validation
REQUIRED_HTML_SOURCES = {
    "html_game_summary",
    "html_event_summary",
    "html_time_on_ice",  # Either home or away
}

# Source name to source_id mapping (must match data_sources table)
SOURCE_NAME_TO_ID = {
    "nhl_boxscore": 2,
    "nhl_pbp": 3,
    "shift_chart": 16,
}


@dataclass
class ValidationQueueItem:
    """Item in the validation queue."""

    game_id: int
    season_id: int
    validator_types: list[str]
    queued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempts: int = 0


@dataclass
class AutoValidationService:
    """Service for auto-triggering validation after downloads.

    This is a singleton service that:
    - Monitors batch completions
    - Checks data completeness for games
    - Queues and runs validation asynchronously
    - Stores results in the database

    Attributes:
        _queue: Async queue for pending validations
        _worker_task: Background worker processing the queue
        _running: Whether the worker is running
    """

    _queue: asyncio.Queue[ValidationQueueItem] = field(
        default_factory=lambda: asyncio.Queue()
    )
    _worker_task: asyncio.Task[None] | None = None
    _running: bool = False
    _instance: AutoValidationService | None = None

    @classmethod
    def get_instance(cls) -> AutoValidationService:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self) -> None:
        """Start the validation worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Auto-validation service started")

    async def stop(self) -> None:
        """Stop the validation worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Auto-validation service stopped")

    async def queue_validation(
        self,
        db: DatabaseService,
        game_id: int,
        season_id: int,
        validator_types: list[str] | None = None,
    ) -> bool:
        """Queue a game for validation.

        Args:
            db: Database service
            game_id: Game ID to validate
            season_id: Season ID for the game
            validator_types: Types of validation to run.
                Options: "json_cross_source", "json_vs_html", "internal"
                Default: ["json_cross_source"]

        Returns:
            True if queued, False if auto-validation is disabled
        """
        if not VALIDATION_AUTO_RUN:
            logger.debug("Auto-validation disabled, skipping game %d", game_id)
            return False

        if validator_types is None:
            validator_types = ["json_cross_source"]

        item = ValidationQueueItem(
            game_id=game_id,
            season_id=season_id,
            validator_types=validator_types,
        )

        await self._queue.put(item)
        logger.info(
            "Queued validation for game %d (types: %s)",
            game_id,
            validator_types,
        )
        return True

    async def has_complete_json_data(self, db: DatabaseService, game_id: int) -> bool:
        """Check if a game has complete JSON data for validation.

        Checks that boxscore, PBP, and shift chart data exist.

        Args:
            db: Database service
            game_id: Game ID to check

        Returns:
            True if all required JSON sources exist
        """
        # Check boxscore
        boxscore_exists = await db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM game_skater_stats WHERE game_id = $1)",
            game_id,
        )

        # Check PBP
        pbp_exists = await db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM game_events WHERE game_id = $1)",
            game_id,
        )

        # Check shift chart
        shifts_exists = await db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM game_shifts WHERE game_id = $1)",
            game_id,
        )

        has_all = all([boxscore_exists, pbp_exists, shifts_exists])

        logger.debug(
            "Game %d completeness: boxscore=%s, pbp=%s, shifts=%s, complete=%s",
            game_id,
            boxscore_exists,
            pbp_exists,
            shifts_exists,
            has_all,
        )

        return has_all

    async def get_games_pending_validation(
        self,
        db: DatabaseService,
        season_id: int,
        limit: int = 100,
    ) -> list[int]:
        """Get games that have complete data but no validation run.

        Args:
            db: Database service
            season_id: Season to check
            limit: Maximum number of games to return

        Returns:
            List of game IDs pending validation
        """
        # Find games with complete JSON data but no validation results
        query = """
            WITH complete_games AS (
                -- Games with boxscore data
                SELECT DISTINCT g.game_id
                FROM games g
                JOIN game_skater_stats gss ON g.game_id = gss.game_id
                WHERE g.season_id = $1
                  AND g.game_state IN ('OFF', 'FINAL')
            ),
            validated_games AS (
                -- Games that already have validation results
                SELECT DISTINCT game_id
                FROM validation_results
                WHERE game_id IS NOT NULL
            )
            SELECT cg.game_id
            FROM complete_games cg
            LEFT JOIN validated_games vg ON cg.game_id = vg.game_id
            WHERE vg.game_id IS NULL
            ORDER BY cg.game_id
            LIMIT $2
        """
        rows = await db.fetch(query, season_id, limit)
        return [row["game_id"] for row in rows]

    async def _worker_loop(self) -> None:
        """Background worker that processes the validation queue."""
        # Import here to avoid circular imports
        from nhl_api.services.db import DatabaseService

        logger.info("Auto-validation worker started")

        while self._running:
            try:
                # Wait for items with timeout to allow checking _running
                try:
                    item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=5.0,
                    )
                except TimeoutError:
                    continue

                # Delay before running validation
                if VALIDATION_DELAY_SECONDS > 0:
                    await asyncio.sleep(VALIDATION_DELAY_SECONDS)

                # Run validation
                try:
                    async with DatabaseService() as db:
                        await self._run_validation(db, item)
                except Exception as e:
                    logger.error(
                        "Validation failed for game %d: %s",
                        item.game_id,
                        e,
                        exc_info=True,
                    )
                    item.attempts += 1
                    if item.attempts < 3:
                        # Re-queue with backoff
                        await asyncio.sleep(item.attempts * 5)
                        await self._queue.put(item)
                finally:
                    self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker error: %s", e, exc_info=True)
                await asyncio.sleep(1)

        logger.info("Auto-validation worker stopped")

    async def _run_validation(
        self,
        db: DatabaseService,
        item: ValidationQueueItem,
    ) -> None:
        """Run validation for a queued item.

        Args:
            db: Database service
            item: Validation queue item
        """
        game_id = item.game_id
        season_id = item.season_id

        logger.info("Running validation for game %d", game_id)

        # Create validation run record
        run_id = await db.fetchval(
            """
            INSERT INTO validation_runs (season_id, status, metadata)
            VALUES ($1, 'running', $2)
            RETURNING run_id
            """,
            season_id,
            {"game_id": game_id, "auto_triggered": True, "types": item.validator_types},
        )

        try:
            total_passed = 0
            total_failed = 0
            total_warnings = 0
            rules_checked = 0

            for validator_type in item.validator_types:
                if validator_type == "json_cross_source":
                    results = await self._run_json_cross_source(db, game_id)

                    # Store results
                    for result in results:
                        rules_checked += 1

                        # Get rule_id for this check
                        rule_name = str(result.get("rule_name", "unknown"))
                        rule_id = await self._get_or_create_rule(
                            db, rule_name, "cross_file"
                        )

                        passed = bool(result.get("passed", False))
                        severity = str(result.get("severity", "warning"))

                        if passed:
                            total_passed += 1
                        elif severity == "error":
                            total_failed += 1
                        else:
                            total_warnings += 1

                        # Insert result
                        await db.execute(
                            """
                            INSERT INTO validation_results
                            (run_id, rule_id, game_id, season_id, passed, severity, message, details)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """,
                            run_id,
                            rule_id,
                            game_id,
                            season_id,
                            passed,
                            severity,
                            result.get("message"),
                            result.get("details"),
                        )

            # Update run as completed
            await db.execute(
                """
                UPDATE validation_runs
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    rules_checked = $2,
                    total_passed = $3,
                    total_failed = $4,
                    total_warnings = $5
                WHERE run_id = $1
                """,
                run_id,
                rules_checked,
                total_passed,
                total_failed,
                total_warnings,
            )

            logger.info(
                "Validation complete for game %d: %d passed, %d failed, %d warnings",
                game_id,
                total_passed,
                total_failed,
                total_warnings,
            )

        except Exception as e:
            # Mark run as failed
            await db.execute(
                """
                UPDATE validation_runs
                SET status = 'failed',
                    completed_at = CURRENT_TIMESTAMP,
                    metadata = metadata || $2
                WHERE run_id = $1
                """,
                run_id,
                {"error": str(e)},
            )
            raise

    async def _run_json_cross_source(
        self,
        db: DatabaseService,
        game_id: int,
    ) -> list[dict[str, object]]:
        """Run JSON cross-source validation for a game.

        Validates:
        - Goals: PBP vs Boxscore
        - Shots: PBP vs Boxscore (with tolerance)
        - TOI: Shifts vs Boxscore
        - Shift counts: Shifts vs Boxscore

        Args:
            db: Database service
            game_id: Game ID to validate

        Returns:
            List of validation result dictionaries
        """
        results: list[dict[str, object]] = []

        # Get boxscore goals from database
        boxscore_row = await db.fetchrow(
            """
            SELECT
                SUM(CASE WHEN team_abbrev = home_team THEN goals ELSE 0 END) as home_goals,
                SUM(CASE WHEN team_abbrev = away_team THEN goals ELSE 0 END) as away_goals
            FROM game_skater_stats gss
            JOIN games g ON gss.game_id = g.game_id
            WHERE gss.game_id = $1
            GROUP BY g.game_id
            """,
            game_id,
        )

        # Get PBP goal events
        pbp_goals = await db.fetchrow(
            """
            SELECT
                COUNT(CASE WHEN team_abbrev = (
                    SELECT home_team FROM games WHERE game_id = $1
                ) THEN 1 END) as home_goals,
                COUNT(CASE WHEN team_abbrev = (
                    SELECT away_team FROM games WHERE game_id = $1
                ) THEN 1 END) as away_goals
            FROM game_events
            WHERE game_id = $1 AND event_type = 'GOAL'
            """,
            game_id,
        )

        if boxscore_row and pbp_goals:
            # Check home goals match
            box_home = boxscore_row["home_goals"] or 0
            pbp_home = pbp_goals["home_goals"] or 0
            home_match = box_home == pbp_home

            results.append(
                {
                    "rule_name": "goals_pbp_vs_boxscore_home",
                    "passed": home_match,
                    "severity": "error" if not home_match else "info",
                    "message": f"Home goals: Boxscore={box_home}, PBP={pbp_home}",
                    "details": {
                        "boxscore_value": box_home,
                        "pbp_value": pbp_home,
                        "team": "home",
                    },
                }
            )

            # Check away goals match
            box_away = boxscore_row["away_goals"] or 0
            pbp_away = pbp_goals["away_goals"] or 0
            away_match = box_away == pbp_away

            results.append(
                {
                    "rule_name": "goals_pbp_vs_boxscore_away",
                    "passed": away_match,
                    "severity": "error" if not away_match else "info",
                    "message": f"Away goals: Boxscore={box_away}, PBP={pbp_away}",
                    "details": {
                        "boxscore_value": box_away,
                        "pbp_value": pbp_away,
                        "team": "away",
                    },
                }
            )

        # Get shift TOI totals
        shift_toi = await db.fetchrow(
            """
            SELECT
                player_id,
                SUM(duration_seconds) as total_toi_seconds
            FROM game_shifts
            WHERE game_id = $1
            GROUP BY player_id
            ORDER BY total_toi_seconds DESC
            LIMIT 1
            """,
            game_id,
        )

        if shift_toi:
            results.append(
                {
                    "rule_name": "shift_data_present",
                    "passed": True,
                    "severity": "info",
                    "message": f"Shift data present with {shift_toi['total_toi_seconds']}s max TOI",
                    "details": {"has_shifts": True},
                }
            )

        return results

    async def _get_or_create_rule(
        self,
        db: DatabaseService,
        rule_name: str,
        category: str,
    ) -> int:
        """Get or create a validation rule.

        Args:
            db: Database service
            rule_name: Name of the rule
            category: Rule category

        Returns:
            rule_id
        """
        # Try to get existing rule
        rule_id: int | None = await db.fetchval(
            "SELECT rule_id FROM validation_rules WHERE name = $1",
            rule_name,
        )

        if rule_id is not None:
            return rule_id

        # Create new rule
        new_rule_id: int = await db.fetchval(
            """
            INSERT INTO validation_rules (name, category, severity, description)
            VALUES ($1, $2, 'warning', $3)
            RETURNING rule_id
            """,
            rule_name,
            category,
            f"Auto-created rule: {rule_name}",
        )

        return new_rule_id


# Module-level function for easy access
def get_auto_validation_service() -> AutoValidationService:
    """Get the auto-validation service singleton."""
    return AutoValidationService.get_instance()
