"""Matchup analysis service for player pair ice time tracking.

Provides functionality for analyzing player matchups including:
- Time on ice together (teammates)
- Time on ice against (opponents)
- Zone-based matchup filtering
- Situation-based breakdowns

The service queries the second_snapshots table to calculate
shared ice time between player pairs.

Example usage:
    async with DatabaseService() as db:
        service = MatchupService(db)

        # Get all matchups for a player
        result = await service.get_player_matchups(
            player_id=8478402,
            season_id=20242025,
        )

        # Get defensive zone matchups only
        def_matchups = await service.get_defensive_zone_matchups(
            player_id=8478402,
            game_id=2024020500,
        )

Issue: #261 - Wave 3: Matchup Analysis (T019-T023)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nhl_api.models.matchups import (
    GameMatchupSummary,
    MatchupResult,
    MatchupType,
    PlayerMatchup,
    Zone,
    ZoneMatchup,
)
from nhl_api.services.analytics.zone_detection import ZoneDetector

if TYPE_CHECKING:
    from nhl_api.services.db.connection import DatabaseService

logger = logging.getLogger(__name__)


@dataclass
class MatchupQueryFilters:
    """Filters for matchup queries.

    Attributes:
        game_id: Filter to specific game.
        season_id: Filter to specific season.
        situation_codes: Filter to specific situations (e.g., ["5v5"]).
        zone: Filter to specific zone.
        min_toi_seconds: Minimum TOI threshold.
        exclude_empty_net: Exclude empty net situations.
    """

    game_id: int | None = None
    season_id: int | None = None
    situation_codes: list[str] | None = None
    zone: Zone | None = None
    min_toi_seconds: int = 0
    exclude_empty_net: bool = False


@dataclass
class MatchupAggregation:
    """Aggregated matchup data for a player pair.

    Attributes:
        player1_id: First player ID.
        player2_id: Second player ID.
        matchup_type: Teammate or opponent.
        total_toi: Total time on ice together.
        game_count: Number of games with shared ice time.
        by_situation: Breakdown by situation code.
        by_zone: Breakdown by zone.
    """

    player1_id: int
    player2_id: int
    matchup_type: MatchupType
    total_toi: int = 0
    game_count: int = 0
    by_situation: dict[str, int] = field(default_factory=dict)
    by_zone: dict[str, int] = field(default_factory=dict)


class MatchupService:
    """Service for analyzing player matchups.

    Provides methods for querying and aggregating player pair
    ice time from second_snapshots data.

    Attributes:
        db: Database service for data access.
        zone_detector: Zone detection service.

    Example:
        >>> service = MatchupService(db)
        >>> matchups = await service.get_player_matchups(8478402)
        >>> print(f"Top opponent: {matchups.top_opponents[0]}")
    """

    def __init__(self, db: DatabaseService) -> None:
        """Initialize the MatchupService.

        Args:
            db: Database service for data access.
        """
        self.db = db
        self.zone_detector = ZoneDetector()

    async def get_player_matchups(
        self,
        player_id: int,
        *,
        season_id: int | None = None,
        game_id: int | None = None,
        situation_codes: list[str] | None = None,
        min_toi_seconds: int = 60,
    ) -> MatchupResult:
        """Get all matchups for a player.

        Returns both teammate and opponent matchups with TOI.

        Args:
            player_id: The player to analyze.
            season_id: Filter to specific season.
            game_id: Filter to specific game.
            situation_codes: Filter to specific situations.
            min_toi_seconds: Minimum TOI threshold (default 60s).

        Returns:
            MatchupResult with teammates and opponents.
        """
        filters = MatchupQueryFilters(
            game_id=game_id,
            season_id=season_id,
            situation_codes=situation_codes,
            min_toi_seconds=min_toi_seconds,
        )

        # Get teammate matchups
        teammates = await self._get_teammate_matchups(player_id, filters)

        # Get opponent matchups
        opponents = await self._get_opponent_matchups(player_id, filters)

        # Get game count
        game_count = await self._get_game_count(player_id, filters)

        return MatchupResult(
            player_id=player_id,
            teammates=teammates,
            opponents=opponents,
            total_games=game_count,
            filters_applied={
                "season_id": season_id,
                "game_id": game_id,
                "situation_codes": situation_codes,
                "min_toi_seconds": min_toi_seconds,
            },
        )

    async def get_ice_time_together(
        self,
        player1_id: int,
        player2_id: int,
        *,
        season_id: int | None = None,
        game_id: int | None = None,
        situation_code: str | None = None,
    ) -> int:
        """Calculate total ice time together for two players.

        Works for both teammates and opponents.

        Args:
            player1_id: First player ID.
            player2_id: Second player ID.
            season_id: Filter to specific season.
            game_id: Filter to specific game.
            situation_code: Filter to specific situation.

        Returns:
            Total seconds on ice together.
        """
        # Build WHERE clause
        conditions = ["1=1"]
        params: list[Any] = []
        param_idx = 1

        if game_id:
            conditions.append(f"game_id = ${param_idx}")
            params.append(game_id)
            param_idx += 1

        if season_id:
            conditions.append(f"season_id = ${param_idx}")
            params.append(season_id)
            param_idx += 1

        if situation_code:
            conditions.append(f"situation_code = ${param_idx}")
            params.append(situation_code)
            param_idx += 1

        # Check both players on ice (either team)
        conditions.append(
            f"(${param_idx} = ANY(home_skater_ids) OR ${param_idx} = ANY(away_skater_ids))"
        )
        params.append(player1_id)
        param_idx += 1

        conditions.append(
            f"(${param_idx} = ANY(home_skater_ids) OR ${param_idx} = ANY(away_skater_ids))"
        )
        params.append(player2_id)

        query = f"""
            SELECT COUNT(*) as toi_seconds
            FROM second_snapshots
            WHERE {" AND ".join(conditions)}
        """

        result = await self.db.fetchval(query, *params)
        return result or 0

    async def get_defensive_zone_matchups(
        self,
        player_id: int,
        *,
        game_id: int | None = None,
        season_id: int | None = None,
    ) -> list[ZoneMatchup]:
        """Get matchups in defensive zone only.

        Filters to seconds where events occurred in the player's
        defensive zone.

        Args:
            player_id: The player to analyze.
            game_id: Filter to specific game.
            season_id: Filter to specific season.

        Returns:
            List of ZoneMatchup objects for defensive zone.
        """
        # Get game info to determine which team the player is on
        filters = MatchupQueryFilters(game_id=game_id, season_id=season_id)

        # For defensive zone, we need to join with game_events
        # and filter by zone = 'D' from the player's perspective
        opponents = await self._get_zone_matchups(
            player_id,
            filters,
            zone=Zone.DEFENSIVE,
            matchup_type=MatchupType.OPPONENT,
        )

        return opponents

    async def get_game_matchup_summary(
        self,
        game_id: int,
    ) -> GameMatchupSummary:
        """Get matchup summary for a game.

        Args:
            game_id: NHL game ID.

        Returns:
            GameMatchupSummary with top matchups.
        """
        # Get game info
        game_info = await self.db.fetchrow(
            """
            SELECT game_id, home_team_id, away_team_id
            FROM games WHERE game_id = $1
            """,
            game_id,
        )

        if not game_info:
            raise ValueError(f"Game {game_id} not found")

        # Get all opponent matchups for this game
        matchups = await self._get_all_opponent_matchups(game_id)

        # Sort by TOI and get top 10
        top_matchups = sorted(matchups, key=lambda m: m.toi_seconds, reverse=True)[:10]

        return GameMatchupSummary(
            game_id=game_id,
            home_team_id=game_info["home_team_id"],
            away_team_id=game_info["away_team_id"],
            matchup_count=len(matchups),
            top_matchups=top_matchups,
        )

    async def aggregate_matchups(
        self,
        player_id: int,
        filters: MatchupQueryFilters,
    ) -> list[MatchupAggregation]:
        """Aggregate matchup data with multiple breakdowns.

        Args:
            player_id: Player to analyze.
            filters: Query filters.

        Returns:
            List of MatchupAggregation objects.
        """
        # Get raw matchup data
        opponents = await self._get_opponent_matchups(player_id, filters)
        teammates = await self._get_teammate_matchups(player_id, filters)

        aggregations = []

        for matchup in opponents:
            aggregations.append(
                MatchupAggregation(
                    player1_id=matchup.player1_id,
                    player2_id=matchup.player2_id,
                    matchup_type=MatchupType.OPPONENT,
                    total_toi=matchup.toi_seconds,
                    game_count=matchup.game_count,
                    by_situation=matchup.situation_breakdown,
                )
            )

        for matchup in teammates:
            aggregations.append(
                MatchupAggregation(
                    player1_id=matchup.player1_id,
                    player2_id=matchup.player2_id,
                    matchup_type=MatchupType.TEAMMATE,
                    total_toi=matchup.toi_seconds,
                    game_count=matchup.game_count,
                    by_situation=matchup.situation_breakdown,
                )
            )

        return aggregations

    async def _get_teammate_matchups(
        self,
        player_id: int,
        filters: MatchupQueryFilters,
    ) -> list[PlayerMatchup]:
        """Get teammate matchups for a player.

        Args:
            player_id: Player to analyze.
            filters: Query filters.

        Returns:
            List of PlayerMatchup for teammates.
        """
        # Build WHERE clause
        conditions = ["is_stoppage = false"]
        params: list[Any] = []
        param_idx = 1

        if filters.game_id:
            conditions.append(f"game_id = ${param_idx}")
            params.append(filters.game_id)
            param_idx += 1

        if filters.season_id:
            conditions.append(f"season_id = ${param_idx}")
            params.append(filters.season_id)
            param_idx += 1

        if filters.situation_codes:
            placeholders = ", ".join(
                f"${param_idx + i}" for i in range(len(filters.situation_codes))
            )
            conditions.append(f"situation_code IN ({placeholders})")
            params.extend(filters.situation_codes)
            param_idx += len(filters.situation_codes)

        if filters.exclude_empty_net:
            conditions.append("is_empty_net = false")

        # Query for home team teammates
        home_query = f"""
            SELECT
                unnest(home_skater_ids) as teammate_id,
                situation_code,
                COUNT(*) as toi_seconds,
                COUNT(DISTINCT game_id) as game_count
            FROM second_snapshots
            WHERE {" AND ".join(conditions)}
                AND ${param_idx} = ANY(home_skater_ids)
            GROUP BY teammate_id, situation_code
            HAVING unnest(home_skater_ids) != ${param_idx}
        """

        # Query for away team teammates
        away_query = f"""
            SELECT
                unnest(away_skater_ids) as teammate_id,
                situation_code,
                COUNT(*) as toi_seconds,
                COUNT(DISTINCT game_id) as game_count
            FROM second_snapshots
            WHERE {" AND ".join(conditions)}
                AND ${param_idx} = ANY(away_skater_ids)
            GROUP BY teammate_id, situation_code
            HAVING unnest(away_skater_ids) != ${param_idx}
        """

        params.append(player_id)

        # Execute both queries
        home_results = await self.db.fetch(home_query, *params)
        away_results = await self.db.fetch(away_query, *params)

        # Combine results
        teammate_data: dict[int, dict[str, Any]] = {}

        for row in list(home_results) + list(away_results):
            teammate_id = row["teammate_id"]
            situation = row["situation_code"]
            toi = row["toi_seconds"]
            games = row["game_count"]

            if teammate_id not in teammate_data:
                teammate_data[teammate_id] = {
                    "toi_seconds": 0,
                    "game_count": 0,
                    "situations": {},
                }

            teammate_data[teammate_id]["toi_seconds"] += toi
            teammate_data[teammate_id]["game_count"] = max(
                teammate_data[teammate_id]["game_count"], games
            )
            if situation not in teammate_data[teammate_id]["situations"]:
                teammate_data[teammate_id]["situations"][situation] = 0
            teammate_data[teammate_id]["situations"][situation] += toi

        # Convert to PlayerMatchup objects
        matchups = []
        for teammate_id, data in teammate_data.items():
            if data["toi_seconds"] >= filters.min_toi_seconds:
                matchups.append(
                    PlayerMatchup(
                        player1_id=player_id,
                        player2_id=teammate_id,
                        matchup_type=MatchupType.TEAMMATE,
                        toi_seconds=data["toi_seconds"],
                        game_count=data["game_count"],
                        situation_breakdown=data["situations"],
                    )
                )

        return matchups

    async def _get_opponent_matchups(
        self,
        player_id: int,
        filters: MatchupQueryFilters,
    ) -> list[PlayerMatchup]:
        """Get opponent matchups for a player.

        Args:
            player_id: Player to analyze.
            filters: Query filters.

        Returns:
            List of PlayerMatchup for opponents.
        """
        # Build WHERE clause
        conditions = ["is_stoppage = false"]
        params: list[Any] = []
        param_idx = 1

        if filters.game_id:
            conditions.append(f"game_id = ${param_idx}")
            params.append(filters.game_id)
            param_idx += 1

        if filters.season_id:
            conditions.append(f"season_id = ${param_idx}")
            params.append(filters.season_id)
            param_idx += 1

        if filters.situation_codes:
            placeholders = ", ".join(
                f"${param_idx + i}" for i in range(len(filters.situation_codes))
            )
            conditions.append(f"situation_code IN ({placeholders})")
            params.extend(filters.situation_codes)
            param_idx += len(filters.situation_codes)

        if filters.exclude_empty_net:
            conditions.append("is_empty_net = false")

        # Query: player on home team, get away opponents
        home_query = f"""
            SELECT
                unnest(away_skater_ids) as opponent_id,
                situation_code,
                COUNT(*) as toi_seconds,
                COUNT(DISTINCT game_id) as game_count
            FROM second_snapshots
            WHERE {" AND ".join(conditions)}
                AND ${param_idx} = ANY(home_skater_ids)
            GROUP BY opponent_id, situation_code
        """

        # Query: player on away team, get home opponents
        away_query = f"""
            SELECT
                unnest(home_skater_ids) as opponent_id,
                situation_code,
                COUNT(*) as toi_seconds,
                COUNT(DISTINCT game_id) as game_count
            FROM second_snapshots
            WHERE {" AND ".join(conditions)}
                AND ${param_idx} = ANY(away_skater_ids)
            GROUP BY opponent_id, situation_code
        """

        params.append(player_id)

        # Execute both queries
        home_results = await self.db.fetch(home_query, *params)
        away_results = await self.db.fetch(away_query, *params)

        # Combine results
        opponent_data: dict[int, dict[str, Any]] = {}

        for row in list(home_results) + list(away_results):
            opponent_id = row["opponent_id"]
            situation = row["situation_code"]
            toi = row["toi_seconds"]
            games = row["game_count"]

            if opponent_id not in opponent_data:
                opponent_data[opponent_id] = {
                    "toi_seconds": 0,
                    "game_count": 0,
                    "situations": {},
                }

            opponent_data[opponent_id]["toi_seconds"] += toi
            opponent_data[opponent_id]["game_count"] = max(
                opponent_data[opponent_id]["game_count"], games
            )
            if situation not in opponent_data[opponent_id]["situations"]:
                opponent_data[opponent_id]["situations"][situation] = 0
            opponent_data[opponent_id]["situations"][situation] += toi

        # Convert to PlayerMatchup objects
        matchups = []
        for opponent_id, data in opponent_data.items():
            if data["toi_seconds"] >= filters.min_toi_seconds:
                matchups.append(
                    PlayerMatchup(
                        player1_id=player_id,
                        player2_id=opponent_id,
                        matchup_type=MatchupType.OPPONENT,
                        toi_seconds=data["toi_seconds"],
                        game_count=data["game_count"],
                        situation_breakdown=data["situations"],
                    )
                )

        return matchups

    async def _get_zone_matchups(
        self,
        player_id: int,
        filters: MatchupQueryFilters,
        zone: Zone,
        matchup_type: MatchupType,
    ) -> list[ZoneMatchup]:
        """Get zone-specific matchups.

        Joins with game_events to filter by zone.

        Args:
            player_id: Player to analyze.
            filters: Query filters.
            zone: Zone to filter to.
            matchup_type: Teammate or opponent.

        Returns:
            List of ZoneMatchup objects.
        """
        # Build WHERE clause for snapshots
        conditions = ["s.is_stoppage = false"]
        params: list[Any] = []
        param_idx = 1

        if filters.game_id:
            conditions.append(f"s.game_id = ${param_idx}")
            params.append(filters.game_id)
            param_idx += 1

        if filters.season_id:
            conditions.append(f"s.season_id = ${param_idx}")
            params.append(filters.season_id)
            param_idx += 1

        # Zone filter on events
        conditions.append(f"e.zone = ${param_idx}")
        params.append(zone.value)
        param_idx += 1

        # Player on ice
        params.append(player_id)
        player_param = param_idx

        if matchup_type == MatchupType.OPPONENT:
            # Get opponents when player on home
            query = f"""
                SELECT
                    unnest(s.away_skater_ids) as other_player_id,
                    COUNT(DISTINCT e.id) as event_count,
                    COUNT(*) as toi_seconds
                FROM second_snapshots s
                JOIN game_events e ON s.game_id = e.game_id
                    AND s.game_second = (
                        (e.period - 1) * 1200 +
                        (1200 - CAST(SPLIT_PART(e.time_in_period, ':', 1) AS INTEGER) * 60
                         - CAST(SPLIT_PART(e.time_in_period, ':', 2) AS INTEGER))
                    )
                WHERE {" AND ".join(conditions)}
                    AND ${player_param} = ANY(s.home_skater_ids)
                GROUP BY other_player_id

                UNION ALL

                SELECT
                    unnest(s.home_skater_ids) as other_player_id,
                    COUNT(DISTINCT e.id) as event_count,
                    COUNT(*) as toi_seconds
                FROM second_snapshots s
                JOIN game_events e ON s.game_id = e.game_id
                    AND s.game_second = (
                        (e.period - 1) * 1200 +
                        (1200 - CAST(SPLIT_PART(e.time_in_period, ':', 1) AS INTEGER) * 60
                         - CAST(SPLIT_PART(e.time_in_period, ':', 2) AS INTEGER))
                    )
                WHERE {" AND ".join(conditions)}
                    AND ${player_param} = ANY(s.away_skater_ids)
                GROUP BY other_player_id
            """
        else:
            # Get teammates
            query = f"""
                SELECT
                    unnest(s.home_skater_ids) as other_player_id,
                    COUNT(DISTINCT e.id) as event_count,
                    COUNT(*) as toi_seconds
                FROM second_snapshots s
                JOIN game_events e ON s.game_id = e.game_id
                    AND s.game_second = (
                        (e.period - 1) * 1200 +
                        (1200 - CAST(SPLIT_PART(e.time_in_period, ':', 1) AS INTEGER) * 60
                         - CAST(SPLIT_PART(e.time_in_period, ':', 2) AS INTEGER))
                    )
                WHERE {" AND ".join(conditions)}
                    AND ${player_param} = ANY(s.home_skater_ids)
                GROUP BY other_player_id
                HAVING unnest(s.home_skater_ids) != ${player_param}

                UNION ALL

                SELECT
                    unnest(s.away_skater_ids) as other_player_id,
                    COUNT(DISTINCT e.id) as event_count,
                    COUNT(*) as toi_seconds
                FROM second_snapshots s
                JOIN game_events e ON s.game_id = e.game_id
                    AND s.game_second = (
                        (e.period - 1) * 1200 +
                        (1200 - CAST(SPLIT_PART(e.time_in_period, ':', 1) AS INTEGER) * 60
                         - CAST(SPLIT_PART(e.time_in_period, ':', 2) AS INTEGER))
                    )
                WHERE {" AND ".join(conditions)}
                    AND ${player_param} = ANY(s.away_skater_ids)
                GROUP BY other_player_id
                HAVING unnest(s.away_skater_ids) != ${player_param}
            """

        results = await self.db.fetch(query, *params)

        # Aggregate by player
        player_data: dict[int, dict[str, int]] = {}
        for row in results:
            pid = row["other_player_id"]
            if pid not in player_data:
                player_data[pid] = {"toi_seconds": 0, "event_count": 0}
            player_data[pid]["toi_seconds"] += row["toi_seconds"]
            player_data[pid]["event_count"] += row["event_count"]

        # Convert to ZoneMatchup objects
        return [
            ZoneMatchup(
                player1_id=player_id,
                player2_id=pid,
                matchup_type=matchup_type,
                zone=zone,
                toi_seconds=data["toi_seconds"],
                event_count=data["event_count"],
            )
            for pid, data in player_data.items()
        ]

    async def _get_all_opponent_matchups(
        self,
        game_id: int,
    ) -> list[PlayerMatchup]:
        """Get all opponent matchups for a game.

        Args:
            game_id: NHL game ID.

        Returns:
            List of all opponent PlayerMatchups.
        """
        query = """
            WITH home_vs_away AS (
                SELECT
                    h.player_id as home_player,
                    a.player_id as away_player,
                    s.situation_code,
                    COUNT(*) as toi_seconds
                FROM second_snapshots s
                CROSS JOIN LATERAL unnest(s.home_skater_ids) AS h(player_id)
                CROSS JOIN LATERAL unnest(s.away_skater_ids) AS a(player_id)
                WHERE s.game_id = $1
                    AND s.is_stoppage = false
                GROUP BY h.player_id, a.player_id, s.situation_code
            )
            SELECT
                home_player,
                away_player,
                SUM(toi_seconds) as total_toi
            FROM home_vs_away
            GROUP BY home_player, away_player
            ORDER BY total_toi DESC
        """

        results = await self.db.fetch(query, game_id)

        return [
            PlayerMatchup(
                player1_id=row["home_player"],
                player2_id=row["away_player"],
                matchup_type=MatchupType.OPPONENT,
                toi_seconds=row["total_toi"],
                game_count=1,
            )
            for row in results
        ]

    async def _get_game_count(
        self,
        player_id: int,
        filters: MatchupQueryFilters,
    ) -> int:
        """Get number of games with player appearances.

        Args:
            player_id: Player ID.
            filters: Query filters.

        Returns:
            Count of games.
        """
        conditions = ["1=1"]
        params: list[Any] = []
        param_idx = 1

        if filters.game_id:
            conditions.append(f"game_id = ${param_idx}")
            params.append(filters.game_id)
            param_idx += 1

        if filters.season_id:
            conditions.append(f"season_id = ${param_idx}")
            params.append(filters.season_id)
            param_idx += 1

        params.append(player_id)

        query = f"""
            SELECT COUNT(DISTINCT game_id)
            FROM second_snapshots
            WHERE {" AND ".join(conditions)}
                AND (${param_idx} = ANY(home_skater_ids)
                     OR ${param_idx} = ANY(away_skater_ids))
        """

        result = await self.db.fetchval(query, *params)
        return result or 0
