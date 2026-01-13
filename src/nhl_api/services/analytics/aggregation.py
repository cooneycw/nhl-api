"""Aggregation service for flexible TOI rollups at any level.

This module provides aggregation functions for second-by-second analytics
data at multiple levels: shift, period, game, and season.

Example usage:
    async with DatabaseService() as db:
        service = AggregationService(db)

        # Get shift-level aggregation for a game
        shifts = await service.aggregate_shifts(game_id=2024020500)

        # Get period-level aggregation
        periods = await service.aggregate_periods(game_id=2024020500)

        # Get game-level aggregation
        game = await service.aggregate_game(game_id=2024020500)

        # Get season-level line combinations
        lines = await service.get_line_combinations(
            season_id=20242025,
            min_toi=600,
        )

Issue: #263 - Wave 5: Aggregation Functions (T030-T033)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nhl_api.services.db.connection import DatabaseService

logger = logging.getLogger(__name__)


@dataclass
class AggregationFilters:
    """Filters for aggregation queries.

    Attributes:
        player_ids: Filter to specific players.
        situation_codes: Filter to specific situations (e.g., ["5v5"]).
        exclude_empty_net: Exclude empty net situations.
        exclude_stoppages: Exclude stoppage time (default True).
    """

    player_ids: list[int] | None = None
    situation_codes: list[str] | None = None
    exclude_empty_net: bool = False
    exclude_stoppages: bool = True


@dataclass
class ShiftAggregation:
    """Stats at shift level (continuous ice time segment).

    Represents aggregated TOI for a single player shift,
    defined as continuous seconds on ice without a gap.

    Attributes:
        player_id: NHL player ID.
        game_id: NHL game ID.
        shift_number: Shift ordinal within the game (1-based).
        period: Period number (1-5).
        start_second: Game second when shift started.
        end_second: Game second when shift ended.
        toi_seconds: Total ice time in seconds.
        by_situation: Breakdown by situation code.
    """

    player_id: int
    game_id: int
    shift_number: int
    period: int
    start_second: int
    end_second: int
    toi_seconds: int
    by_situation: dict[str, int] = field(default_factory=dict)


@dataclass
class PeriodAggregation:
    """Stats aggregated per period.

    Attributes:
        player_id: NHL player ID.
        game_id: NHL game ID.
        period: Period number (1-5).
        toi_seconds: Total ice time in seconds.
        shift_count: Number of shifts in this period.
        by_situation: Breakdown by situation code.
    """

    player_id: int
    game_id: int
    period: int
    toi_seconds: int
    shift_count: int
    by_situation: dict[str, int] = field(default_factory=dict)


@dataclass
class GameAggregation:
    """Stats aggregated per game.

    Attributes:
        player_id: NHL player ID.
        game_id: NHL game ID.
        toi_seconds: Total ice time in seconds.
        period_count: Number of periods with ice time.
        shift_count: Total number of shifts.
        by_situation: Breakdown by situation code.
    """

    player_id: int
    game_id: int
    toi_seconds: int
    period_count: int
    shift_count: int
    by_situation: dict[str, int] = field(default_factory=dict)


@dataclass
class SeasonAggregation:
    """Stats aggregated per season.

    Attributes:
        player_id: NHL player ID.
        season_id: Season ID (e.g., 20242025).
        toi_seconds: Total ice time in seconds.
        game_count: Number of games played.
        avg_toi_per_game: Average TOI per game in seconds.
        by_situation: Breakdown by situation code.
    """

    player_id: int
    season_id: int
    toi_seconds: int
    game_count: int
    avg_toi_per_game: float
    by_situation: dict[str, int] = field(default_factory=dict)


@dataclass
class LineCombinationStats:
    """Season-level line combination stats.

    Tracks TOI for a group of players together on the ice.

    Attributes:
        player_ids: Frozenset of player IDs in the combination.
        season_id: Season ID (e.g., 20242025).
        toi_together: Total seconds on ice together.
        game_count: Number of games with shared ice time.
        by_situation: Breakdown by situation code.
    """

    player_ids: frozenset[int]
    season_id: int
    toi_together: int
    game_count: int
    by_situation: dict[str, int] = field(default_factory=dict)


class AggregationService:
    """Service for flexible TOI aggregation at any level.

    Provides methods for aggregating second-by-second snapshot data
    at shift, period, game, and season levels.

    Attributes:
        db: Database service for data access.

    Example:
        >>> service = AggregationService(db)
        >>> shifts = await service.aggregate_shifts(2024020500)
        >>> print(f"Total shifts: {len(shifts)}")
    """

    def __init__(self, db: DatabaseService) -> None:
        """Initialize the AggregationService.

        Args:
            db: Database service for data access.
        """
        self.db = db

    def _build_where_clause(
        self,
        filters: AggregationFilters | None,
        *,
        game_id: int | None = None,
        season_id: int | None = None,
        table_alias: str = "",
    ) -> tuple[list[str], list[Any], int]:
        """Build WHERE clause conditions from filters.

        Args:
            filters: Aggregation filters.
            game_id: Optional game ID filter.
            season_id: Optional season ID filter.
            table_alias: Table alias prefix (e.g., "s." or "").

        Returns:
            Tuple of (conditions list, params list, next param index).
        """
        prefix = f"{table_alias}." if table_alias else ""
        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if game_id is not None:
            conditions.append(f"{prefix}game_id = ${param_idx}")
            params.append(game_id)
            param_idx += 1

        if season_id is not None:
            conditions.append(f"{prefix}season_id = ${param_idx}")
            params.append(season_id)
            param_idx += 1

        if filters:
            if filters.exclude_stoppages:
                conditions.append(f"{prefix}is_stoppage = false")

            if filters.exclude_empty_net:
                conditions.append(f"{prefix}is_empty_net = false")

            if filters.situation_codes:
                placeholders = ", ".join(
                    f"${param_idx + i}" for i in range(len(filters.situation_codes))
                )
                conditions.append(f"{prefix}situation_code IN ({placeholders})")
                params.extend(filters.situation_codes)
                param_idx += len(filters.situation_codes)

        # Default to excluding stoppages if no filter provided
        if not filters:
            conditions.append(f"{prefix}is_stoppage = false")

        return conditions, params, param_idx

    async def aggregate_shifts(
        self,
        game_id: int,
        filters: AggregationFilters | None = None,
    ) -> list[ShiftAggregation]:
        """Aggregate player TOI at shift level (T030).

        A shift is defined as a continuous sequence of seconds on ice,
        with gaps > 1 second indicating a new shift.

        Args:
            game_id: NHL game ID.
            filters: Optional aggregation filters.

        Returns:
            List of ShiftAggregation for each player shift.
        """
        conditions, params, param_idx = self._build_where_clause(
            filters, game_id=game_id
        )

        # Handle player filter if specified
        player_filter = ""
        if filters and filters.player_ids:
            player_placeholders = ", ".join(
                f"${param_idx + i}" for i in range(len(filters.player_ids))
            )
            player_filter = f"WHERE player_id IN ({player_placeholders})"
            params.extend(filters.player_ids)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Use window functions to detect shift boundaries
        query = f"""
            WITH player_seconds AS (
                -- Get all seconds each player is on ice
                SELECT
                    game_id,
                    period,
                    game_second,
                    situation_code,
                    unnest(home_skater_ids) as player_id
                FROM second_snapshots
                WHERE {where_clause}

                UNION ALL

                SELECT
                    game_id,
                    period,
                    game_second,
                    situation_code,
                    unnest(away_skater_ids) as player_id
                FROM second_snapshots
                WHERE {where_clause}
            ),
            with_gaps AS (
                -- Detect gaps in continuous ice time
                SELECT
                    *,
                    game_second - LAG(game_second, 1, game_second)
                        OVER (PARTITION BY player_id ORDER BY game_second) as gap
                FROM player_seconds
                {player_filter}
            ),
            with_shift_id AS (
                -- Assign shift IDs using cumulative sum of new shift markers
                SELECT
                    *,
                    SUM(CASE WHEN gap > 1 THEN 1 ELSE 0 END)
                        OVER (PARTITION BY player_id ORDER BY game_second) as shift_id
                FROM with_gaps
            )
            SELECT
                player_id,
                game_id,
                shift_id + 1 as shift_number,
                MIN(period) as period,
                MIN(game_second) as start_second,
                MAX(game_second) as end_second,
                COUNT(*) as toi_seconds,
                situation_code,
                COUNT(*) as situation_toi
            FROM with_shift_id
            GROUP BY player_id, game_id, shift_id, situation_code
            ORDER BY player_id, shift_id, situation_code
        """

        results = await self.db.fetch(query, *params)

        # Aggregate situation breakdowns per shift
        shift_data: dict[tuple[int, int], dict[str, Any]] = {}

        for row in results:
            key = (row["player_id"], row["shift_number"])

            if key not in shift_data:
                shift_data[key] = {
                    "player_id": row["player_id"],
                    "game_id": row["game_id"],
                    "shift_number": row["shift_number"],
                    "period": row["period"],
                    "start_second": row["start_second"],
                    "end_second": row["end_second"],
                    "toi_seconds": 0,
                    "by_situation": {},
                }

            shift_data[key]["toi_seconds"] += row["situation_toi"]
            situation = row["situation_code"]
            if situation not in shift_data[key]["by_situation"]:
                shift_data[key]["by_situation"][situation] = 0
            shift_data[key]["by_situation"][situation] += row["situation_toi"]

        return [
            ShiftAggregation(
                player_id=data["player_id"],
                game_id=data["game_id"],
                shift_number=data["shift_number"],
                period=data["period"],
                start_second=data["start_second"],
                end_second=data["end_second"],
                toi_seconds=data["toi_seconds"],
                by_situation=data["by_situation"],
            )
            for data in sorted(
                shift_data.values(), key=lambda x: (x["player_id"], x["shift_number"])
            )
        ]

    async def aggregate_periods(
        self,
        game_id: int,
        filters: AggregationFilters | None = None,
    ) -> list[PeriodAggregation]:
        """Aggregate player TOI at period level (T031).

        Args:
            game_id: NHL game ID.
            filters: Optional aggregation filters.

        Returns:
            List of PeriodAggregation for each player-period.
        """
        conditions, params, param_idx = self._build_where_clause(
            filters, game_id=game_id
        )

        # Handle player filter
        player_condition = ""
        if filters and filters.player_ids:
            player_placeholders = ", ".join(
                f"${param_idx + i}" for i in range(len(filters.player_ids))
            )
            player_condition = f"AND player_id IN ({player_placeholders})"
            params.extend(filters.player_ids)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            WITH player_seconds AS (
                SELECT
                    game_id,
                    period,
                    game_second,
                    situation_code,
                    unnest(home_skater_ids) as player_id
                FROM second_snapshots
                WHERE {where_clause}

                UNION ALL

                SELECT
                    game_id,
                    period,
                    game_second,
                    situation_code,
                    unnest(away_skater_ids) as player_id
                FROM second_snapshots
                WHERE {where_clause}
            ),
            with_gaps AS (
                SELECT
                    *,
                    game_second - LAG(game_second, 1, game_second)
                        OVER (PARTITION BY player_id, period ORDER BY game_second) as gap
                FROM player_seconds
                WHERE 1=1 {player_condition}
            ),
            with_shifts AS (
                SELECT
                    *,
                    SUM(CASE WHEN gap > 1 THEN 1 ELSE 0 END)
                        OVER (PARTITION BY player_id, period ORDER BY game_second) as shift_id
                FROM with_gaps
            )
            SELECT
                player_id,
                game_id,
                period,
                situation_code,
                COUNT(*) as toi_seconds,
                COUNT(DISTINCT shift_id) as shift_count
            FROM with_shifts
            GROUP BY player_id, game_id, period, situation_code
            ORDER BY player_id, period, situation_code
        """

        results = await self.db.fetch(query, *params)

        # Aggregate by player-period
        period_data: dict[tuple[int, int], dict[str, Any]] = {}

        for row in results:
            key = (row["player_id"], row["period"])

            if key not in period_data:
                period_data[key] = {
                    "player_id": row["player_id"],
                    "game_id": row["game_id"],
                    "period": row["period"],
                    "toi_seconds": 0,
                    "shift_count": 0,
                    "by_situation": {},
                }

            period_data[key]["toi_seconds"] += row["toi_seconds"]
            period_data[key]["shift_count"] = max(
                period_data[key]["shift_count"], row["shift_count"]
            )

            situation = row["situation_code"]
            if situation not in period_data[key]["by_situation"]:
                period_data[key]["by_situation"][situation] = 0
            period_data[key]["by_situation"][situation] += row["toi_seconds"]

        return [
            PeriodAggregation(
                player_id=data["player_id"],
                game_id=data["game_id"],
                period=data["period"],
                toi_seconds=data["toi_seconds"],
                shift_count=data["shift_count"],
                by_situation=data["by_situation"],
            )
            for data in sorted(
                period_data.values(), key=lambda x: (x["player_id"], x["period"])
            )
        ]

    async def aggregate_game(
        self,
        game_id: int,
        filters: AggregationFilters | None = None,
    ) -> list[GameAggregation]:
        """Aggregate player TOI at game level (T032).

        Args:
            game_id: NHL game ID.
            filters: Optional aggregation filters.

        Returns:
            List of GameAggregation for each player.
        """
        conditions, params, param_idx = self._build_where_clause(
            filters, game_id=game_id
        )

        # Handle player filter
        player_condition = ""
        if filters and filters.player_ids:
            player_placeholders = ", ".join(
                f"${param_idx + i}" for i in range(len(filters.player_ids))
            )
            player_condition = f"AND player_id IN ({player_placeholders})"
            params.extend(filters.player_ids)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            WITH player_seconds AS (
                SELECT
                    game_id,
                    period,
                    game_second,
                    situation_code,
                    unnest(home_skater_ids) as player_id
                FROM second_snapshots
                WHERE {where_clause}

                UNION ALL

                SELECT
                    game_id,
                    period,
                    game_second,
                    situation_code,
                    unnest(away_skater_ids) as player_id
                FROM second_snapshots
                WHERE {where_clause}
            ),
            with_gaps AS (
                SELECT
                    *,
                    game_second - LAG(game_second, 1, game_second)
                        OVER (PARTITION BY player_id ORDER BY game_second) as gap
                FROM player_seconds
                WHERE 1=1 {player_condition}
            ),
            with_shifts AS (
                SELECT
                    *,
                    SUM(CASE WHEN gap > 1 THEN 1 ELSE 0 END)
                        OVER (PARTITION BY player_id ORDER BY game_second) as shift_id
                FROM with_gaps
            )
            SELECT
                player_id,
                game_id,
                situation_code,
                COUNT(*) as toi_seconds,
                COUNT(DISTINCT period) as period_count,
                COUNT(DISTINCT shift_id) as shift_count
            FROM with_shifts
            GROUP BY player_id, game_id, situation_code
            ORDER BY player_id, situation_code
        """

        results = await self.db.fetch(query, *params)

        # Aggregate by player
        game_data: dict[int, dict[str, Any]] = {}

        for row in results:
            player_id = row["player_id"]

            if player_id not in game_data:
                game_data[player_id] = {
                    "player_id": player_id,
                    "game_id": row["game_id"],
                    "toi_seconds": 0,
                    "period_count": 0,
                    "shift_count": 0,
                    "by_situation": {},
                }

            game_data[player_id]["toi_seconds"] += row["toi_seconds"]
            game_data[player_id]["period_count"] = max(
                game_data[player_id]["period_count"], row["period_count"]
            )
            game_data[player_id]["shift_count"] = max(
                game_data[player_id]["shift_count"], row["shift_count"]
            )

            situation = row["situation_code"]
            if situation not in game_data[player_id]["by_situation"]:
                game_data[player_id]["by_situation"][situation] = 0
            game_data[player_id]["by_situation"][situation] += row["toi_seconds"]

        return [
            GameAggregation(
                player_id=data["player_id"],
                game_id=data["game_id"],
                toi_seconds=data["toi_seconds"],
                period_count=data["period_count"],
                shift_count=data["shift_count"],
                by_situation=data["by_situation"],
            )
            for data in sorted(game_data.values(), key=lambda x: -x["toi_seconds"])
        ]

    async def aggregate_season(
        self,
        season_id: int,
        filters: AggregationFilters | None = None,
    ) -> list[SeasonAggregation]:
        """Aggregate player TOI at season level.

        Args:
            season_id: Season ID (e.g., 20242025).
            filters: Optional aggregation filters.

        Returns:
            List of SeasonAggregation for each player.
        """
        conditions, params, param_idx = self._build_where_clause(
            filters, season_id=season_id
        )

        # Handle player filter
        player_condition = ""
        if filters and filters.player_ids:
            player_placeholders = ", ".join(
                f"${param_idx + i}" for i in range(len(filters.player_ids))
            )
            player_condition = f"AND player_id IN ({player_placeholders})"
            params.extend(filters.player_ids)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            WITH player_seconds AS (
                SELECT
                    game_id,
                    season_id,
                    situation_code,
                    unnest(home_skater_ids) as player_id
                FROM second_snapshots
                WHERE {where_clause}

                UNION ALL

                SELECT
                    game_id,
                    season_id,
                    situation_code,
                    unnest(away_skater_ids) as player_id
                FROM second_snapshots
                WHERE {where_clause}
            )
            SELECT
                player_id,
                season_id,
                situation_code,
                COUNT(*) as toi_seconds,
                COUNT(DISTINCT game_id) as game_count
            FROM player_seconds
            WHERE 1=1 {player_condition}
            GROUP BY player_id, season_id, situation_code
            ORDER BY player_id, situation_code
        """

        results = await self.db.fetch(query, *params)

        # Aggregate by player
        season_data: dict[int, dict[str, Any]] = {}

        for row in results:
            player_id = row["player_id"]

            if player_id not in season_data:
                season_data[player_id] = {
                    "player_id": player_id,
                    "season_id": row["season_id"],
                    "toi_seconds": 0,
                    "game_count": 0,
                    "by_situation": {},
                }

            season_data[player_id]["toi_seconds"] += row["toi_seconds"]
            season_data[player_id]["game_count"] = max(
                season_data[player_id]["game_count"], row["game_count"]
            )

            situation = row["situation_code"]
            if situation not in season_data[player_id]["by_situation"]:
                season_data[player_id]["by_situation"][situation] = 0
            season_data[player_id]["by_situation"][situation] += row["toi_seconds"]

        return [
            SeasonAggregation(
                player_id=data["player_id"],
                season_id=data["season_id"],
                toi_seconds=data["toi_seconds"],
                game_count=data["game_count"],
                avg_toi_per_game=(
                    data["toi_seconds"] / data["game_count"]
                    if data["game_count"] > 0
                    else 0.0
                ),
                by_situation=data["by_situation"],
            )
            for data in sorted(season_data.values(), key=lambda x: -x["toi_seconds"])
        ]

    async def get_line_combinations(
        self,
        season_id: int,
        *,
        min_toi: int = 300,
        min_players: int = 3,
        max_players: int = 5,
        filters: AggregationFilters | None = None,
    ) -> list[LineCombinationStats]:
        """Get season-level line combination stats (T033).

        Analyzes which player combinations have spent time on ice together.

        Args:
            season_id: Season ID (e.g., 20242025).
            min_toi: Minimum TOI in seconds to include (default 300 = 5 min).
            min_players: Minimum players in combination (default 3).
            max_players: Maximum players in combination (default 5).
            filters: Optional aggregation filters.

        Returns:
            List of LineCombinationStats sorted by TOI together.
        """
        conditions, params, param_idx = self._build_where_clause(
            filters, season_id=season_id
        )

        # Add array length filters
        conditions.append(f"array_length(home_skater_ids, 1) >= ${param_idx}")
        params.append(min_players)
        param_idx += 1

        conditions.append(f"array_length(home_skater_ids, 1) <= ${param_idx}")
        params.append(max_players)
        param_idx += 1

        # Store min_toi param index
        min_toi_idx = param_idx
        params.append(min_toi)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Query for line combinations (using sorted array for consistent grouping)
        query = f"""
            WITH line_seconds AS (
                -- Home team line combinations
                SELECT
                    game_id,
                    season_id,
                    situation_code,
                    (SELECT array_agg(x ORDER BY x) FROM unnest(home_skater_ids) x) as sorted_players
                FROM second_snapshots
                WHERE {where_clause}

                UNION ALL

                -- Away team line combinations
                SELECT
                    game_id,
                    season_id,
                    situation_code,
                    (SELECT array_agg(x ORDER BY x) FROM unnest(away_skater_ids) x) as sorted_players
                FROM second_snapshots
                WHERE {where_clause.replace("home_skater_ids", "away_skater_ids")}
            )
            SELECT
                sorted_players,
                season_id,
                situation_code,
                COUNT(*) as toi_seconds,
                COUNT(DISTINCT game_id) as game_count
            FROM line_seconds
            WHERE sorted_players IS NOT NULL
            GROUP BY sorted_players, season_id, situation_code
            HAVING COUNT(*) >= ${min_toi_idx}
            ORDER BY COUNT(*) DESC
        """

        results = await self.db.fetch(query, *params)

        # Aggregate by line combination
        line_data: dict[tuple[int, ...], dict[str, Any]] = {}

        for row in results:
            # Convert list to tuple for dict key
            players = tuple(sorted(row["sorted_players"]))

            if players not in line_data:
                line_data[players] = {
                    "player_ids": frozenset(players),
                    "season_id": row["season_id"],
                    "toi_together": 0,
                    "game_count": 0,
                    "by_situation": {},
                }

            line_data[players]["toi_together"] += row["toi_seconds"]
            line_data[players]["game_count"] = max(
                line_data[players]["game_count"], row["game_count"]
            )

            situation = row["situation_code"]
            if situation not in line_data[players]["by_situation"]:
                line_data[players]["by_situation"][situation] = 0
            line_data[players]["by_situation"][situation] += row["toi_seconds"]

        return [
            LineCombinationStats(
                player_ids=data["player_ids"],
                season_id=data["season_id"],
                toi_together=data["toi_together"],
                game_count=data["game_count"],
                by_situation=data["by_situation"],
            )
            for data in sorted(line_data.values(), key=lambda x: -x["toi_together"])
        ]

    async def get_player_toi_summary(
        self,
        player_id: int,
        season_id: int,
        filters: AggregationFilters | None = None,
    ) -> SeasonAggregation | None:
        """Get TOI summary for a single player.

        Convenience method for quick player lookups.

        Args:
            player_id: NHL player ID.
            season_id: Season ID.
            filters: Optional aggregation filters.

        Returns:
            SeasonAggregation for the player, or None if no data.
        """
        if filters is None:
            filters = AggregationFilters(player_ids=[player_id])
        else:
            filters.player_ids = [player_id]

        results = await self.aggregate_season(season_id, filters)
        return results[0] if results else None
