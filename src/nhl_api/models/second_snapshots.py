"""Data models for second-by-second analytics snapshots.

This module defines dataclass models for granular game state tracking,
capturing which players are on the ice for every second of play.

Example usage:
    # Create a snapshot from database record
    snapshot = SecondSnapshot.from_record(record)

    # Check if a player was on ice
    if snapshot.is_player_on_ice(8470613):
        print(f"Player on ice at {snapshot.game_second}s")

    # Get all on-ice players
    all_players = snapshot.all_skater_ids

Issue: #259 - Wave 1: Core Pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Situation code constants
SITUATION_5V5 = "5v5"
SITUATION_5V4 = "5v4"
SITUATION_4V5 = "4v5"
SITUATION_5V3 = "5v3"
SITUATION_3V5 = "3v5"
SITUATION_4V4 = "4v4"
SITUATION_4V3 = "4v3"
SITUATION_3V4 = "3v4"
SITUATION_3V3 = "3v3"

# Empty net variations
SITUATION_EN_6V5 = "EN6v5"  # Home empty net, attacking
SITUATION_EN_5V6 = "5v6EN"  # Away empty net, attacking
SITUATION_EN_6V4 = "EN6v4"
SITUATION_EN_4V6 = "4v6EN"


@dataclass(frozen=True, slots=True)
class SecondSnapshot:
    """Single second of game state with all on-ice players.

    Represents the complete game state at a specific second, including
    which players are on the ice for both teams.

    Frozen and slotted for memory efficiency when storing many snapshots.

    Attributes:
        snapshot_id: Unique identifier (database primary key).
        game_id: NHL game ID.
        season_id: Season ID in YYYYYYYY format (e.g., 20242025).
        period: Game period (1, 2, 3, 4 for OT, 5 for 2OT/SO).
        period_second: Seconds elapsed in current period (0-1200).
        game_second: Total elapsed game seconds (0-3600+).
        situation_code: Manpower situation (e.g., "5v5", "5v4").
        home_skater_count: Number of home skaters on ice (0-6).
        away_skater_count: Number of away skaters on ice (0-6).
        home_skater_ids: List of home skater player IDs.
        away_skater_ids: List of away skater player IDs.
        home_goalie_id: Home goalie player ID (None if empty net).
        away_goalie_id: Away goalie player ID (None if empty net).
        is_stoppage: True during stoppages (faceoff pending, TV timeout).
        is_power_play: True if either team is on power play.
        is_empty_net: True if either team has pulled goalie.
        created_at: Timestamp of record creation.
    """

    snapshot_id: int
    game_id: int
    season_id: int
    period: int
    period_second: int
    game_second: int
    situation_code: str
    home_skater_count: int
    away_skater_count: int
    home_skater_ids: tuple[int, ...] = field(default_factory=tuple)
    away_skater_ids: tuple[int, ...] = field(default_factory=tuple)
    home_goalie_id: int | None = None
    away_goalie_id: int | None = None
    is_stoppage: bool = False
    is_power_play: bool = False
    is_empty_net: bool = False
    created_at: datetime | None = None

    @classmethod
    def from_record(cls, record: Any) -> SecondSnapshot:
        """Create a SecondSnapshot from an asyncpg Record.

        Args:
            record: An asyncpg Record object from the database.

        Returns:
            A SecondSnapshot instance.
        """
        # Convert arrays to tuples for immutability
        home_skaters = tuple(record["home_skater_ids"] or [])
        away_skaters = tuple(record["away_skater_ids"] or [])

        return cls(
            snapshot_id=record["snapshot_id"],
            game_id=record["game_id"],
            season_id=record["season_id"],
            period=record["period"],
            period_second=record["period_second"],
            game_second=record["game_second"],
            situation_code=record["situation_code"],
            home_skater_count=record["home_skater_count"],
            away_skater_count=record["away_skater_count"],
            home_skater_ids=home_skaters,
            away_skater_ids=away_skaters,
            home_goalie_id=record["home_goalie_id"],
            away_goalie_id=record["away_goalie_id"],
            is_stoppage=record["is_stoppage"],
            is_power_play=record["is_power_play"],
            is_empty_net=record["is_empty_net"],
            created_at=record["created_at"],
        )

    @property
    def all_skater_ids(self) -> tuple[int, ...]:
        """Get all skater IDs (both teams)."""
        return self.home_skater_ids + self.away_skater_ids

    @property
    def all_player_ids(self) -> tuple[int, ...]:
        """Get all player IDs including goalies."""
        players = list(self.all_skater_ids)
        if self.home_goalie_id is not None:
            players.append(self.home_goalie_id)
        if self.away_goalie_id is not None:
            players.append(self.away_goalie_id)
        return tuple(players)

    @property
    def total_skaters(self) -> int:
        """Total number of skaters on ice (both teams)."""
        return self.home_skater_count + self.away_skater_count

    @property
    def time_display(self) -> str:
        """Display time as P{period} MM:SS."""
        minutes = self.period_second // 60
        seconds = self.period_second % 60
        return f"P{self.period} {minutes:02d}:{seconds:02d}"

    def is_player_on_ice(self, player_id: int) -> bool:
        """Check if a player is on the ice.

        Args:
            player_id: NHL player ID to check.

        Returns:
            True if the player is on ice (as skater or goalie).
        """
        return (
            player_id in self.home_skater_ids
            or player_id in self.away_skater_ids
            or player_id == self.home_goalie_id
            or player_id == self.away_goalie_id
        )

    def is_home_player(self, player_id: int) -> bool:
        """Check if a player is on the home team.

        Args:
            player_id: NHL player ID to check.

        Returns:
            True if the player is a home skater or goalie.
        """
        return player_id in self.home_skater_ids or player_id == self.home_goalie_id

    def is_away_player(self, player_id: int) -> bool:
        """Check if a player is on the away team.

        Args:
            player_id: NHL player ID to check.

        Returns:
            True if the player is an away skater or goalie.
        """
        return player_id in self.away_skater_ids or player_id == self.away_goalie_id

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "snapshot_id": self.snapshot_id,
            "game_id": self.game_id,
            "season_id": self.season_id,
            "period": self.period,
            "period_second": self.period_second,
            "game_second": self.game_second,
            "situation_code": self.situation_code,
            "home_skater_count": self.home_skater_count,
            "away_skater_count": self.away_skater_count,
            "home_skater_ids": list(self.home_skater_ids),
            "away_skater_ids": list(self.away_skater_ids),
            "home_goalie_id": self.home_goalie_id,
            "away_goalie_id": self.away_goalie_id,
            "is_stoppage": self.is_stoppage,
            "is_power_play": self.is_power_play,
            "is_empty_net": self.is_empty_net,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def calculate_situation_code(
    home_skaters: int,
    away_skaters: int,
    home_empty_net: bool = False,
    away_empty_net: bool = False,
) -> str:
    """Calculate situation code from player counts.

    Args:
        home_skaters: Number of home skaters (excluding goalie).
        away_skaters: Number of away skaters (excluding goalie).
        home_empty_net: True if home team pulled goalie.
        away_empty_net: True if away team pulled goalie.

    Returns:
        Situation code string (e.g., "5v5", "5v4", "EN6v5").

    Example:
        >>> calculate_situation_code(5, 5)
        '5v5'
        >>> calculate_situation_code(5, 4)
        '5v4'
        >>> calculate_situation_code(6, 5, home_empty_net=True)
        'EN6v5'
    """
    # Add extra attacker if empty net
    home_display = home_skaters + (1 if home_empty_net else 0)
    away_display = away_skaters + (1 if away_empty_net else 0)

    if home_empty_net:
        return f"EN{home_display}v{away_display}"
    elif away_empty_net:
        return f"{home_display}v{away_display}EN"
    else:
        return f"{home_skaters}v{away_skaters}"


def is_power_play_situation(situation_code: str) -> bool:
    """Check if a situation code represents a power play.

    Args:
        situation_code: Situation code to check.

    Returns:
        True if one team has a manpower advantage.

    Example:
        >>> is_power_play_situation("5v4")
        True
        >>> is_power_play_situation("5v5")
        False
    """
    # Extract numbers, ignoring EN prefix/suffix
    code = situation_code.replace("EN", "").strip()
    try:
        parts = code.split("v")
        if len(parts) != 2:
            return False
        home = int(parts[0])
        away = int(parts[1])
        return home != away
    except (ValueError, IndexError):
        return False
