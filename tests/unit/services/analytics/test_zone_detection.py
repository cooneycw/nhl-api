"""Unit tests for zone detection service.

Tests the ZoneDetector's ability to correctly classify ice zones
based on coordinates and game context.

Issue: #261 - Wave 3: Matchup Analysis (T022)
"""

from __future__ import annotations

import pytest

from nhl_api.services.analytics.zone_detection import Zone, ZoneDetector, ZoneResult


class TestZoneDetector:
    """Tests for ZoneDetector zone classification."""

    def test_neutral_zone_center_ice(self) -> None:
        """Center ice should be neutral zone."""
        detector = ZoneDetector()
        zone = detector.get_zone(0.0, 0.0, period=1, is_home_team=True)
        assert zone == Zone.NEUTRAL

    def test_neutral_zone_near_blue_line(self) -> None:
        """Just inside blue line should be neutral zone."""
        detector = ZoneDetector()

        # Just inside left blue line
        zone = detector.get_zone(-24.0, 0.0, period=1, is_home_team=True)
        assert zone == Zone.NEUTRAL

        # Just inside right blue line
        zone = detector.get_zone(24.0, 0.0, period=1, is_home_team=True)
        assert zone == Zone.NEUTRAL

    def test_offensive_zone_period_1_home(self) -> None:
        """Home team attacks right in period 1."""
        detector = ZoneDetector()

        # Positive x past blue line = offensive for home in P1
        zone = detector.get_zone(75.0, 10.0, period=1, is_home_team=True)
        assert zone == Zone.OFFENSIVE

    def test_defensive_zone_period_1_home(self) -> None:
        """Home team defends left in period 1."""
        detector = ZoneDetector()

        # Negative x past blue line = defensive for home in P1
        zone = detector.get_zone(-75.0, 10.0, period=1, is_home_team=True)
        assert zone == Zone.DEFENSIVE

    def test_offensive_zone_period_2_home(self) -> None:
        """Home team attacks left in period 2 (sides switch)."""
        detector = ZoneDetector()

        # Negative x past blue line = offensive for home in P2
        zone = detector.get_zone(-75.0, 10.0, period=2, is_home_team=True)
        assert zone == Zone.OFFENSIVE

    def test_defensive_zone_period_2_home(self) -> None:
        """Home team defends right in period 2."""
        detector = ZoneDetector()

        # Positive x past blue line = defensive for home in P2
        zone = detector.get_zone(75.0, 10.0, period=2, is_home_team=True)
        assert zone == Zone.DEFENSIVE

    def test_period_3_same_as_period_1(self) -> None:
        """Period 3 should have same orientation as period 1."""
        detector = ZoneDetector()

        zone_p1 = detector.get_zone(75.0, 0.0, period=1, is_home_team=True)
        zone_p3 = detector.get_zone(75.0, 0.0, period=3, is_home_team=True)
        assert zone_p1 == zone_p3 == Zone.OFFENSIVE

    def test_away_team_opposite_of_home(self) -> None:
        """Away team zones are opposite of home team."""
        detector = ZoneDetector()

        # Same location, different team perspective
        home_zone = detector.get_zone(75.0, 0.0, period=1, is_home_team=True)
        away_zone = detector.get_zone(75.0, 0.0, period=1, is_home_team=False)

        assert home_zone == Zone.OFFENSIVE
        assert away_zone == Zone.DEFENSIVE

    def test_none_coordinate_returns_neutral(self) -> None:
        """Missing coordinates should return neutral zone."""
        detector = ZoneDetector()
        zone = detector.get_zone(None, 0.0, period=1, is_home_team=True)
        assert zone == Zone.NEUTRAL

    def test_overtime_same_as_period_2(self) -> None:
        """Overtime (period 4) matches period 2 orientation (even periods)."""
        detector = ZoneDetector()

        # Period 4 is even (4 % 2 = 0), so it matches period 2
        zone_p2 = detector.get_zone(75.0, 0.0, period=2, is_home_team=True)
        zone_ot = detector.get_zone(75.0, 0.0, period=4, is_home_team=True)
        assert zone_p2 == zone_ot == Zone.DEFENSIVE


class TestZoneDetectorResult:
    """Tests for detailed zone result."""

    def test_get_zone_result_includes_context(self) -> None:
        """Zone result should include full context."""
        detector = ZoneDetector()
        result = detector.get_zone_result(
            75.0, 10.0, period=2, is_home_team=True
        )

        assert isinstance(result, ZoneResult)
        assert result.zone == Zone.DEFENSIVE
        assert result.x_coord == 75.0
        assert result.y_coord == 10.0
        assert result.period == 2
        assert result.is_home_perspective is True

    def test_zone_result_with_none_y(self) -> None:
        """Should handle None y_coord."""
        detector = ZoneDetector()
        result = detector.get_zone_result(50.0, None, period=1, is_home_team=True)

        assert result.y_coord == 0.0
        assert result.zone == Zone.OFFENSIVE


class TestClassifyEventZone:
    """Tests for API zone classification."""

    def test_prefers_api_zone(self) -> None:
        """Should prefer API-provided zone over coordinates."""
        detector = ZoneDetector()

        # API says defensive, coords would say offensive
        zone = detector.classify_event_zone(75.0, "D")
        assert zone == Zone.DEFENSIVE

    def test_falls_back_to_coords(self) -> None:
        """Should use coords when no API zone."""
        detector = ZoneDetector()

        zone = detector.classify_event_zone(75.0, None)
        assert zone == Zone.OFFENSIVE

        zone = detector.classify_event_zone(-75.0, None)
        assert zone == Zone.DEFENSIVE

    def test_handles_invalid_api_zone(self) -> None:
        """Should fall back on invalid API zone."""
        detector = ZoneDetector()

        zone = detector.classify_event_zone(75.0, "X")  # Invalid
        assert zone == Zone.OFFENSIVE

    def test_neutral_on_missing_coords(self) -> None:
        """Should return neutral with no valid data."""
        detector = ZoneDetector()

        zone = detector.classify_event_zone(None, None)
        assert zone == Zone.NEUTRAL


class TestZoneHelpers:
    """Tests for zone helper methods."""

    def test_is_defensive_zone(self) -> None:
        """Test defensive zone detection."""
        assert ZoneDetector.is_defensive_zone(Zone.DEFENSIVE)
        assert ZoneDetector.is_defensive_zone("D")
        assert not ZoneDetector.is_defensive_zone(Zone.OFFENSIVE)
        assert not ZoneDetector.is_defensive_zone("O")

    def test_is_offensive_zone(self) -> None:
        """Test offensive zone detection."""
        assert ZoneDetector.is_offensive_zone(Zone.OFFENSIVE)
        assert ZoneDetector.is_offensive_zone("O")
        assert not ZoneDetector.is_offensive_zone(Zone.DEFENSIVE)
        assert not ZoneDetector.is_offensive_zone("D")

    def test_is_neutral_zone(self) -> None:
        """Test neutral zone detection."""
        assert ZoneDetector.is_neutral_zone(Zone.NEUTRAL)
        assert ZoneDetector.is_neutral_zone("N")
        assert not ZoneDetector.is_neutral_zone(Zone.OFFENSIVE)
