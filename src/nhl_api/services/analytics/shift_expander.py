"""Shift expansion service for second-by-second analytics.

Expands player shift records into granular second-by-second snapshots
tracking which players are on the ice at each moment of the game.

The NHL API provides shift data in MM:SS format representing game clock
time (counting down from 20:00). This service converts those shifts to
elapsed seconds and generates one snapshot per second of game time.

Example usage:
    async with DatabaseService() as db:
        expander = ShiftExpander(db)
        result = await expander.expand_game(game_id=2024020500)

        for second in result.seconds:
            print(f"Second {second.game_second}: {len(second.home_skaters)} home skaters")

Issue: #259 - Wave 1: Core Pipeline (T004-T007)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nhl_api.models.second_snapshots import calculate_situation_code

if TYPE_CHECKING:
    from nhl_api.services.db.connection import DatabaseService

logger = logging.getLogger(__name__)

# Period duration in seconds (20 minutes)
PERIOD_SECONDS = 1200

# Overtime period duration (5 minutes for regular season)
OT_SECONDS = 300


def parse_game_clock_to_elapsed(time_str: str, period: int) -> int:
    """Convert game clock time (MM:SS counting down) to elapsed seconds in period.

    The NHL game clock counts down from 20:00 to 00:00 for each period.
    This function converts that to elapsed seconds (0 at start of period).

    Args:
        time_str: Time in "MM:SS" format (game clock, counting down).
        period: Period number (1, 2, 3, or 4+ for OT).

    Returns:
        Elapsed seconds in the period (0 to 1200 for regulation, 0 to 300 for OT).

    Example:
        >>> parse_game_clock_to_elapsed("19:45", 1)
        15  # 15 seconds have elapsed
        >>> parse_game_clock_to_elapsed("00:30", 2)
        1170  # 30 seconds left = 1170 elapsed
    """
    if not time_str:
        return 0

    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            return 0
        minutes = int(parts[0])
        seconds = int(parts[1])
        clock_seconds = minutes * 60 + seconds

        # Period duration depends on period type
        period_duration = OT_SECONDS if period >= 4 else PERIOD_SECONDS

        # Elapsed = duration - clock time
        elapsed = period_duration - clock_seconds
        return max(0, elapsed)
    except (ValueError, AttributeError):
        return 0


def period_to_game_second(period: int, period_second: int) -> int:
    """Convert period number and period second to total game second.

    Args:
        period: Period number (1, 2, 3, 4+).
        period_second: Elapsed seconds within the period.

    Returns:
        Total elapsed game seconds.

    Example:
        >>> period_to_game_second(1, 100)
        100
        >>> period_to_game_second(2, 50)
        1250  # 1200 + 50
        >>> period_to_game_second(4, 100)
        3700  # 3600 + 100
    """
    if period <= 3:
        return (period - 1) * PERIOD_SECONDS + period_second
    else:
        # OT periods start after 3 regulation periods
        base = 3 * PERIOD_SECONDS
        ot_periods = period - 4
        return base + ot_periods * OT_SECONDS + period_second


@dataclass(frozen=True, slots=True)
class ExpandedSecond:
    """State of the ice at a single second of game time.

    Attributes:
        game_id: NHL game ID.
        season_id: Season ID (e.g., 20242025).
        period: Period number.
        period_second: Elapsed seconds in period.
        game_second: Total elapsed game seconds.
        home_skaters: Set of home team skater player IDs on ice.
        away_skaters: Set of away team skater player IDs on ice.
        home_goalie_id: Home goalie ID (None if empty net).
        away_goalie_id: Away goalie ID (None if empty net).
    """

    game_id: int
    season_id: int
    period: int
    period_second: int
    game_second: int
    home_skaters: frozenset[int]
    away_skaters: frozenset[int]
    home_goalie_id: int | None = None
    away_goalie_id: int | None = None

    @property
    def situation_code(self) -> str:
        """Calculate situation code from skater counts."""
        return calculate_situation_code(
            home_skaters=len(self.home_skaters),
            away_skaters=len(self.away_skaters),
            home_empty_net=self.home_goalie_id is None,
            away_empty_net=self.away_goalie_id is None,
        )

    @property
    def is_power_play(self) -> bool:
        """True if one team has a manpower advantage."""
        return len(self.home_skaters) != len(self.away_skaters)

    @property
    def is_empty_net(self) -> bool:
        """True if either team has pulled their goalie."""
        return self.home_goalie_id is None or self.away_goalie_id is None


@dataclass
class GameExpansionResult:
    """Result of expanding a game's shifts to second-by-second data.

    Attributes:
        game_id: NHL game ID.
        season_id: Season ID.
        home_team_id: Home team ID.
        away_team_id: Away team ID.
        total_shifts: Number of shifts processed.
        total_seconds: Total game seconds generated.
        periods: Number of periods in the game.
        seconds: List of ExpandedSecond objects, one per game second.
        errors: Any errors encountered during expansion.
    """

    game_id: int
    season_id: int
    home_team_id: int
    away_team_id: int
    total_shifts: int = 0
    total_seconds: int = 0
    periods: int = 3
    seconds: list[ExpandedSecond] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if expansion completed without critical errors."""
        return len(self.seconds) > 0 and len(self.errors) == 0


class ShiftExpander:
    """Service for expanding shifts into second-by-second snapshots.

    Takes player shift records from the database and expands each shift
    into individual seconds, tracking which players are on ice at each
    moment of game time.

    Attributes:
        db: Database service for querying shift and game data.

    Example:
        >>> expander = ShiftExpander(db)
        >>> result = await expander.expand_game(2024020500)
        >>> print(f"Generated {result.total_seconds} seconds from {result.total_shifts} shifts")
    """

    def __init__(self, db: DatabaseService) -> None:
        """Initialize the ShiftExpander.

        Args:
            db: Database service for data access.
        """
        self.db = db

    async def expand_game(self, game_id: int) -> GameExpansionResult:
        """Expand all shifts for a game into second-by-second snapshots.

        Fetches shifts from the database, expands each shift into
        individual seconds, and aggregates all players on ice at
        each game second.

        Args:
            game_id: NHL game ID to expand.

        Returns:
            GameExpansionResult with all expanded seconds.

        Raises:
            ValueError: If game not found or no shifts available.
        """
        # Get game metadata
        game_info = await self._get_game_info(game_id)
        if not game_info:
            raise ValueError(f"Game {game_id} not found in database")

        season_id = game_info["season_id"]
        home_team_id = game_info["home_team_id"]
        away_team_id = game_info["away_team_id"]
        num_periods = game_info["period"] or 3

        result = GameExpansionResult(
            game_id=game_id,
            season_id=season_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            periods=num_periods,
        )

        # Get all shifts for the game
        shifts = await self._get_game_shifts(game_id)
        if not shifts:
            result.errors.append(f"No shifts found for game {game_id}")
            return result

        result.total_shifts = len(shifts)
        logger.info(f"Expanding {len(shifts)} shifts for game {game_id}")

        # Build second-by-second player presence map
        # Key: (period, period_second), Value: {home_skaters: set, away_skaters: set}
        presence_map: dict[tuple[int, int], dict[str, set[int]]] = {}

        for shift in shifts:
            team_id = shift["team_id"]
            player_id = shift["player_id"]
            period = shift["period"]
            is_goal = shift["is_goal_event"]

            # Skip goal events (they're not actual shifts)
            if is_goal:
                continue

            # Parse start/end times to elapsed seconds
            start_elapsed = parse_game_clock_to_elapsed(shift["start_time"], period)
            end_elapsed = parse_game_clock_to_elapsed(shift["end_time"], period)

            # Ensure start < end (sometimes data has quirks)
            if start_elapsed > end_elapsed:
                start_elapsed, end_elapsed = end_elapsed, start_elapsed

            # Determine if home or away
            team_key = "home_skaters" if team_id == home_team_id else "away_skaters"

            # Mark player present for each second of the shift
            for sec in range(start_elapsed, end_elapsed + 1):
                key = (period, sec)
                if key not in presence_map:
                    presence_map[key] = {"home_skaters": set(), "away_skaters": set()}
                presence_map[key][team_key].add(player_id)

        # Convert presence map to ExpandedSecond objects
        expanded_seconds: list[ExpandedSecond] = []
        for (period, period_second), players in sorted(presence_map.items()):
            game_second = period_to_game_second(period, period_second)
            expanded = ExpandedSecond(
                game_id=game_id,
                season_id=season_id,
                period=period,
                period_second=period_second,
                game_second=game_second,
                home_skaters=frozenset(players["home_skaters"]),
                away_skaters=frozenset(players["away_skaters"]),
                # Goalies will be set by a separate step (from roster/events)
                home_goalie_id=None,
                away_goalie_id=None,
            )
            expanded_seconds.append(expanded)

        result.seconds = expanded_seconds
        result.total_seconds = len(expanded_seconds)

        logger.info(
            f"Game {game_id}: Expanded {result.total_shifts} shifts to "
            f"{result.total_seconds} seconds across {result.periods} periods"
        )

        return result

    async def _get_game_info(self, game_id: int) -> dict[str, Any] | None:
        """Get game metadata from the database.

        Args:
            game_id: NHL game ID.

        Returns:
            Dict with game info or None if not found.
        """
        row = await self.db.fetchrow(
            """
            SELECT game_id, season_id, home_team_id, away_team_id, period
            FROM games
            WHERE game_id = $1
            """,
            game_id,
        )
        if row:
            return dict(row)
        return None

    async def _get_game_shifts(self, game_id: int) -> list[dict[str, Any]]:
        """Get all shifts for a game from the database.

        Args:
            game_id: NHL game ID.

        Returns:
            List of shift records as dicts.
        """
        rows = await self.db.fetch(
            """
            SELECT shift_id, game_id, player_id, team_id, period,
                   shift_number, start_time, end_time, duration_seconds,
                   is_goal_event, event_description
            FROM game_shifts
            WHERE game_id = $1
            ORDER BY period, shift_number
            """,
            game_id,
        )
        return [dict(row) for row in rows]

    async def save_expanded_game(self, result: GameExpansionResult) -> int:
        """Save expanded seconds to the second_snapshots table.

        Args:
            result: GameExpansionResult from expand_game().

        Returns:
            Number of rows inserted.

        Raises:
            ValueError: If result has errors or no seconds.
        """
        if not result.success:
            raise ValueError(f"Cannot save failed expansion: {result.errors}")

        if not result.seconds:
            return 0

        # Prepare insert data
        insert_data = []
        for sec in result.seconds:
            insert_data.append(
                (
                    sec.game_id,
                    sec.season_id,
                    sec.period,
                    sec.period_second,
                    sec.game_second,
                    sec.situation_code,
                    len(sec.home_skaters),
                    len(sec.away_skaters),
                    list(sec.home_skaters),
                    list(sec.away_skaters),
                    sec.home_goalie_id,
                    sec.away_goalie_id,
                    False,  # is_stoppage - will be set by event attribution
                    sec.is_power_play,
                    sec.is_empty_net,
                )
            )

        # Batch insert with ON CONFLICT for idempotency
        await self.db.executemany(
            """
            INSERT INTO second_snapshots (
                game_id, season_id, period, period_second, game_second,
                situation_code, home_skater_count, away_skater_count,
                home_skater_ids, away_skater_ids,
                home_goalie_id, away_goalie_id,
                is_stoppage, is_power_play, is_empty_net
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT (game_id, game_second) DO UPDATE SET
                situation_code = EXCLUDED.situation_code,
                home_skater_count = EXCLUDED.home_skater_count,
                away_skater_count = EXCLUDED.away_skater_count,
                home_skater_ids = EXCLUDED.home_skater_ids,
                away_skater_ids = EXCLUDED.away_skater_ids,
                home_goalie_id = EXCLUDED.home_goalie_id,
                away_goalie_id = EXCLUDED.away_goalie_id,
                is_stoppage = EXCLUDED.is_stoppage,
                is_power_play = EXCLUDED.is_power_play,
                is_empty_net = EXCLUDED.is_empty_net
            """,
            insert_data,
        )

        logger.info(f"Saved {len(insert_data)} seconds for game {result.game_id}")
        return len(insert_data)
