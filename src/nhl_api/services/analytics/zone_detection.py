"""Zone detection service for determining ice zone from coordinates.

NHL rink dimensions:
- Length: 200 feet (-100 to +100 on x-axis)
- Width: 85 feet (-42.5 to +42.5 on y-axis)
- Blue lines: at -25 and +25 on x-axis
- Center ice: x=0

Zone classification:
- Offensive zone (O): x > 25 for home team attacking right
- Defensive zone (D): x < -25 for home team defending left
- Neutral zone (N): -25 <= x <= 25

Note: Zone attribution depends on which team is being analyzed.
Home team attacks right (positive x) in P1/P3, left in P2.

Example usage:
    detector = ZoneDetector()
    zone = detector.get_zone(x_coord=75.0, period=1, is_home_team=True)
    # Returns Zone.OFFENSIVE

Issue: #261 - Wave 3: Matchup Analysis (T022)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nhl_api.models.matchups import Zone

if TYPE_CHECKING:
    pass


# NHL rink zone boundaries (blue lines)
BLUE_LINE_DISTANCE = 25.0  # Distance from center ice to blue line
CENTER_ICE = 0.0


@dataclass(frozen=True, slots=True)
class ZoneResult:
    """Result of zone detection.

    Attributes:
        zone: The detected zone.
        x_coord: Original x coordinate.
        y_coord: Original y coordinate.
        period: Game period.
        is_home_perspective: True if zone is from home team perspective.
    """

    zone: Zone
    x_coord: float
    y_coord: float
    period: int
    is_home_perspective: bool


class ZoneDetector:
    """Service for detecting ice zone from coordinates.

    Handles the complexity of zone attribution based on:
    - Period (home team attacks right in P1/P3, left in P2)
    - Team perspective (offensive/defensive is relative to team)

    Attributes:
        neutral_zone_width: Width of neutral zone in feet (default 50).

    Example:
        >>> detector = ZoneDetector()
        >>> zone = detector.get_zone(75.0, 10.0, period=1, is_home_team=True)
        Zone.OFFENSIVE
    """

    def __init__(self, neutral_zone_width: float = 50.0) -> None:
        """Initialize the ZoneDetector.

        Args:
            neutral_zone_width: Width of neutral zone (default 50 feet).
        """
        self.blue_line = neutral_zone_width / 2  # 25 feet from center

    def get_zone(
        self,
        x_coord: float,
        y_coord: float | None = None,
        *,
        period: int = 1,
        is_home_team: bool = True,
    ) -> Zone:
        """Determine the ice zone from coordinates.

        Args:
            x_coord: X coordinate on ice (-100 to 100).
            y_coord: Y coordinate on ice (not used but available).
            period: Game period (1, 2, 3, etc.).
            is_home_team: True if analyzing from home team perspective.

        Returns:
            Zone classification (OFFENSIVE, DEFENSIVE, or NEUTRAL).
        """
        # Handle missing coordinates
        if x_coord is None:
            return Zone.NEUTRAL

        # Determine attacking direction based on period
        # Home team attacks right (positive x) in P1, P3, OT periods
        # Home team attacks left (negative x) in P2
        home_attacks_right = period % 2 == 1  # Odd periods attack right

        # For away team, flip the direction
        team_attacks_right = (
            home_attacks_right if is_home_team else not home_attacks_right
        )

        # Neutral zone check first
        if abs(x_coord) <= self.blue_line:
            return Zone.NEUTRAL

        # Determine zone based on attacking direction
        if team_attacks_right:
            # Team attacks right (positive x)
            if x_coord > self.blue_line:
                return Zone.OFFENSIVE
            else:  # x_coord < -self.blue_line
                return Zone.DEFENSIVE
        else:
            # Team attacks left (negative x)
            if x_coord < -self.blue_line:
                return Zone.OFFENSIVE
            else:  # x_coord > self.blue_line
                return Zone.DEFENSIVE

    def get_zone_result(
        self,
        x_coord: float,
        y_coord: float | None = None,
        *,
        period: int = 1,
        is_home_team: bool = True,
    ) -> ZoneResult:
        """Get detailed zone result with context.

        Args:
            x_coord: X coordinate on ice.
            y_coord: Y coordinate on ice.
            period: Game period.
            is_home_team: True if analyzing from home team perspective.

        Returns:
            ZoneResult with full context.
        """
        zone = self.get_zone(
            x_coord,
            y_coord,
            period=period,
            is_home_team=is_home_team,
        )
        return ZoneResult(
            zone=zone,
            x_coord=x_coord,
            y_coord=y_coord or 0.0,
            period=period,
            is_home_perspective=is_home_team,
        )

    def classify_event_zone(
        self,
        x_coord: float | None,
        zone_from_api: str | None = None,
    ) -> Zone:
        """Classify zone, preferring API-provided zone if available.

        The NHL API provides a zone field (O/D/N) which is already
        calculated from the team's perspective. Use this when available.

        Args:
            x_coord: X coordinate (fallback if no API zone).
            zone_from_api: Zone string from NHL API (O/D/N).

        Returns:
            Zone classification.
        """
        # Prefer API-provided zone
        if zone_from_api:
            try:
                return Zone(zone_from_api.upper())
            except ValueError:
                pass  # Fall through to coordinate-based detection

        # Fall back to coordinate-based detection
        if x_coord is not None:
            if x_coord > self.blue_line:
                return Zone.OFFENSIVE
            elif x_coord < -self.blue_line:
                return Zone.DEFENSIVE

        return Zone.NEUTRAL

    @staticmethod
    def is_defensive_zone(zone: Zone | str) -> bool:
        """Check if zone is defensive.

        Args:
            zone: Zone enum or string.

        Returns:
            True if defensive zone.
        """
        if isinstance(zone, str):
            return zone.upper() == "D"
        return zone == Zone.DEFENSIVE

    @staticmethod
    def is_offensive_zone(zone: Zone | str) -> bool:
        """Check if zone is offensive.

        Args:
            zone: Zone enum or string.

        Returns:
            True if offensive zone.
        """
        if isinstance(zone, str):
            return zone.upper() == "O"
        return zone == Zone.OFFENSIVE

    @staticmethod
    def is_neutral_zone(zone: Zone | str) -> bool:
        """Check if zone is neutral.

        Args:
            zone: Zone enum or string.

        Returns:
            True if neutral zone.
        """
        if isinstance(zone, str):
            return zone.upper() == "N"
        return zone == Zone.NEUTRAL
