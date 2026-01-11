"""Situation calculator for determining game state from player counts.

Calculates situation codes (5v5, 5v4, etc.) from the number of skaters
on ice for each team, and detects special situations like power plays
and empty net scenarios.

The situation code format is:
- Regular: "{home}v{away}" (e.g., "5v5", "5v4", "4v4")
- Empty net home: "EN{home+1}v{away}" (e.g., "EN6v5")
- Empty net away: "{home}v{away+1}EN" (e.g., "5v6EN")

Example usage:
    calc = SituationCalculator()
    code = calc.calculate(home_skaters=5, away_skaters=4)
    # Returns "5v4"

    situation = calc.analyze(
        home_skaters=6, away_skaters=5,
        home_goalie=None, away_goalie=8476945
    )
    # Returns Situation with code="EN6v5", is_empty_net=True

Issue: #259 - Wave 1: Core Pipeline (T011-T013)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SituationType(str, Enum):
    """Types of game situations."""

    EVEN_STRENGTH = "even"
    POWER_PLAY_HOME = "pp_home"
    POWER_PLAY_AWAY = "pp_away"
    EMPTY_NET_HOME = "en_home"
    EMPTY_NET_AWAY = "en_away"
    FOUR_ON_FOUR = "4v4"
    THREE_ON_THREE = "3v3"


@dataclass(frozen=True, slots=True)
class Situation:
    """Complete situation analysis for a game second.

    Attributes:
        code: Situation code string (e.g., "5v5", "5v4", "EN6v5").
        home_skaters: Number of home skaters on ice.
        away_skaters: Number of away skaters on ice.
        home_goalie_id: Home goalie ID (None if empty net).
        away_goalie_id: Away goalie ID (None if empty net).
        situation_type: Classified situation type.
        is_power_play: True if one team has a manpower advantage.
        is_empty_net: True if either team pulled their goalie.
        is_even_strength: True if both teams have equal skaters (excluding 4v4/3v3).
        home_advantage: +N if home has N more skaters, -N if away has more.
    """

    code: str
    home_skaters: int
    away_skaters: int
    home_goalie_id: int | None
    away_goalie_id: int | None
    situation_type: SituationType
    is_power_play: bool
    is_empty_net: bool
    is_even_strength: bool
    home_advantage: int

    @property
    def is_regulation(self) -> bool:
        """True if this is a standard 5v5 situation."""
        return self.code == "5v5"

    @property
    def is_special_teams(self) -> bool:
        """True if this is a power play or penalty kill situation."""
        return self.is_power_play

    @property
    def is_four_on_four(self) -> bool:
        """True if 4v4 situation."""
        return self.code == "4v4"

    @property
    def is_three_on_three(self) -> bool:
        """True if 3v3 situation (overtime)."""
        return self.code == "3v3"


class SituationCalculator:
    """Calculator for game situation analysis.

    Determines situation codes and game state from player counts
    and goalie presence.

    Example:
        >>> calc = SituationCalculator()
        >>> calc.calculate(5, 5)
        '5v5'
        >>> calc.calculate(5, 4)
        '5v4'
        >>> calc.calculate(6, 5, home_empty_net=True)
        'EN6v5'
    """

    def calculate(
        self,
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

    def analyze(
        self,
        home_skaters: int,
        away_skaters: int,
        home_goalie: int | None = None,
        away_goalie: int | None = None,
    ) -> Situation:
        """Perform complete situation analysis.

        Args:
            home_skaters: Number of home skaters on ice.
            away_skaters: Number of away skaters on ice.
            home_goalie: Home goalie ID (None if pulled).
            away_goalie: Away goalie ID (None if pulled).

        Returns:
            Situation object with full analysis.
        """
        home_empty_net = home_goalie is None
        away_empty_net = away_goalie is None

        code = self.calculate(
            home_skaters, away_skaters, home_empty_net, away_empty_net
        )

        advantage = home_skaters - away_skaters
        is_power_play = advantage != 0
        is_empty_net = home_empty_net or away_empty_net
        is_even = home_skaters == away_skaters and home_skaters == 5

        # Determine situation type
        if home_empty_net:
            situation_type = SituationType.EMPTY_NET_HOME
        elif away_empty_net:
            situation_type = SituationType.EMPTY_NET_AWAY
        elif home_skaters == 4 and away_skaters == 4:
            situation_type = SituationType.FOUR_ON_FOUR
        elif home_skaters == 3 and away_skaters == 3:
            situation_type = SituationType.THREE_ON_THREE
        elif advantage > 0:
            situation_type = SituationType.POWER_PLAY_HOME
        elif advantage < 0:
            situation_type = SituationType.POWER_PLAY_AWAY
        else:
            situation_type = SituationType.EVEN_STRENGTH

        return Situation(
            code=code,
            home_skaters=home_skaters,
            away_skaters=away_skaters,
            home_goalie_id=home_goalie,
            away_goalie_id=away_goalie,
            situation_type=situation_type,
            is_power_play=is_power_play,
            is_empty_net=is_empty_net,
            is_even_strength=is_even,
            home_advantage=advantage,
        )

    def detect_empty_net(
        self,
        home_skaters: int,
        away_skaters: int,
        expected_skaters: int = 5,
    ) -> tuple[bool, bool]:
        """Detect empty net from skater counts.

        If a team has 6 skaters, it's likely an empty net situation.

        Args:
            home_skaters: Number of home skaters.
            away_skaters: Number of away skaters.
            expected_skaters: Normal number of skaters (default 5).

        Returns:
            Tuple of (home_empty_net, away_empty_net).
        """
        home_en = home_skaters > expected_skaters
        away_en = away_skaters > expected_skaters
        return (home_en, away_en)

    def is_power_play_code(self, code: str) -> bool:
        """Check if a situation code represents a power play.

        Args:
            code: Situation code to check.

        Returns:
            True if one team has an advantage.
        """
        # Remove EN prefix/suffix for comparison
        clean = code.replace("EN", "").strip()
        try:
            parts = clean.split("v")
            if len(parts) != 2:
                return False
            home = int(parts[0])
            away = int(parts[1])
            return home != away
        except (ValueError, IndexError):
            return False

    def get_power_play_team(
        self,
        code: str,
    ) -> str | None:
        """Determine which team is on the power play.

        Args:
            code: Situation code to analyze.

        Returns:
            "home" if home team has advantage, "away" if away,
            None if even strength.
        """
        clean = code.replace("EN", "").strip()
        try:
            parts = clean.split("v")
            if len(parts) != 2:
                return None
            home = int(parts[0])
            away = int(parts[1])
            if home > away:
                return "home"
            elif away > home:
                return "away"
            return None
        except (ValueError, IndexError):
            return None


# Default calculator instance for simple use cases
_default_calculator = SituationCalculator()


def calculate_situation_code(
    home_skaters: int,
    away_skaters: int,
    home_empty_net: bool = False,
    away_empty_net: bool = False,
) -> str:
    """Calculate situation code (module-level convenience function).

    See SituationCalculator.calculate() for details.
    """
    return _default_calculator.calculate(
        home_skaters, away_skaters, home_empty_net, away_empty_net
    )


def is_power_play_situation(situation_code: str) -> bool:
    """Check if situation code is a power play (module-level convenience function).

    See SituationCalculator.is_power_play_code() for details.
    """
    return _default_calculator.is_power_play_code(situation_code)
