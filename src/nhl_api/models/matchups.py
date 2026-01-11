"""Data models for player matchup analysis.

This module defines dataclass models for tracking player matchups,
including time-on-ice together/against and zone-based metrics.

Example usage:
    # Get matchup data
    matchup = PlayerMatchup(
        player1_id=8478402,
        player2_id=8477934,
        matchup_type=MatchupType.TEAMMATE,
        toi_seconds=1250,
    )

Issue: #261 - Wave 3: Matchup Analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MatchupType(str, Enum):
    """Type of player matchup."""

    TEAMMATE = "teammate"  # Players on same team
    OPPONENT = "opponent"  # Players on opposing teams


class Zone(str, Enum):
    """Ice zone classification."""

    OFFENSIVE = "O"  # Attacking zone
    DEFENSIVE = "D"  # Defending zone
    NEUTRAL = "N"  # Neutral zone


@dataclass(frozen=True, slots=True)
class PlayerMatchup:
    """A matchup record between two players.

    Represents shared ice time between two players, either as
    teammates or opponents.

    Attributes:
        player1_id: First player ID (lower ID for consistency).
        player2_id: Second player ID (higher ID for consistency).
        matchup_type: Whether players are teammates or opponents.
        toi_seconds: Total time on ice together in seconds.
        game_count: Number of games with shared ice time.
        situation_breakdown: TOI by situation code (e.g., {"5v5": 800}).
    """

    player1_id: int
    player2_id: int
    matchup_type: MatchupType
    toi_seconds: int = 0
    game_count: int = 0
    situation_breakdown: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure player1_id < player2_id for consistency."""
        if self.player1_id > self.player2_id:
            # Swap using object.__setattr__ since frozen
            # Must save both values first before swapping
            p1, p2 = self.player1_id, self.player2_id
            object.__setattr__(self, "player1_id", p2)
            object.__setattr__(self, "player2_id", p1)

    @property
    def toi_minutes(self) -> float:
        """Time on ice in minutes."""
        return self.toi_seconds / 60.0

    @property
    def toi_display(self) -> str:
        """Display time as MM:SS."""
        minutes = self.toi_seconds // 60
        seconds = self.toi_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "matchup_type": self.matchup_type.value,
            "toi_seconds": self.toi_seconds,
            "toi_minutes": round(self.toi_minutes, 2),
            "game_count": self.game_count,
            "situation_breakdown": self.situation_breakdown,
        }


@dataclass(frozen=True, slots=True)
class ZoneMatchup:
    """A zone-specific matchup record.

    Extends PlayerMatchup with zone-based time tracking.

    Attributes:
        player1_id: First player ID.
        player2_id: Second player ID.
        matchup_type: Whether players are teammates or opponents.
        zone: The zone where this matchup occurred.
        toi_seconds: Time on ice in this zone.
        event_count: Number of events in this zone during matchup.
    """

    player1_id: int
    player2_id: int
    matchup_type: MatchupType
    zone: Zone
    toi_seconds: int = 0
    event_count: int = 0

    @property
    def toi_minutes(self) -> float:
        """Time on ice in minutes."""
        return self.toi_seconds / 60.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "matchup_type": self.matchup_type.value,
            "zone": self.zone.value,
            "toi_seconds": self.toi_seconds,
            "toi_minutes": round(self.toi_minutes, 2),
            "event_count": self.event_count,
        }


@dataclass
class MatchupResult:
    """Result of querying matchup data.

    Attributes:
        player_id: The focus player.
        teammates: List of teammate matchups.
        opponents: List of opponent matchups.
        total_games: Total games in the dataset.
        filters_applied: Filters used in the query.
    """

    player_id: int
    teammates: list[PlayerMatchup] = field(default_factory=list)
    opponents: list[PlayerMatchup] = field(default_factory=list)
    total_games: int = 0
    filters_applied: dict[str, Any] = field(default_factory=dict)

    @property
    def top_teammates(self) -> list[PlayerMatchup]:
        """Get top 5 teammates by TOI."""
        return sorted(self.teammates, key=lambda m: m.toi_seconds, reverse=True)[:5]

    @property
    def top_opponents(self) -> list[PlayerMatchup]:
        """Get top 5 opponents by TOI."""
        return sorted(self.opponents, key=lambda m: m.toi_seconds, reverse=True)[:5]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "player_id": self.player_id,
            "teammates": [m.to_dict() for m in self.teammates],
            "opponents": [m.to_dict() for m in self.opponents],
            "total_games": self.total_games,
            "filters_applied": self.filters_applied,
        }


@dataclass
class GameMatchupSummary:
    """Summary of matchups for a single game.

    Attributes:
        game_id: NHL game ID.
        home_team_id: Home team ID.
        away_team_id: Away team ID.
        matchup_count: Total number of unique matchups.
        top_matchups: Top matchups by TOI.
    """

    game_id: int
    home_team_id: int
    away_team_id: int
    matchup_count: int = 0
    top_matchups: list[PlayerMatchup] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "game_id": self.game_id,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "matchup_count": self.matchup_count,
            "top_matchups": [m.to_dict() for m in self.top_matchups],
        }
