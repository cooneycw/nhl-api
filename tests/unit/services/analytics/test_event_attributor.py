"""Unit tests for EventAttributor service.

Tests event matching and attribution logic without database access.

Issue: #259 - Wave 1: Core Pipeline
"""

import pytest

from nhl_api.services.analytics.event_attributor import (
    AttributionResult,
    EventAttribution,
    EventAttributor,
    GameEvent,
)
from nhl_api.services.analytics.shift_expander import ExpandedSecond


class TestGameEvent:
    """Tests for GameEvent dataclass."""

    def test_is_goal(self) -> None:
        """Goal events are properly detected."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=10,
            event_type="goal",
            period=1,
            time_in_period="15:30",
            period_second=270,
            game_second=270,
        )
        assert event.is_goal
        assert event.is_shot  # Goals are also shots

    def test_is_shot(self) -> None:
        """Shot events are properly detected."""
        for event_type in ["shot-on-goal", "missed-shot", "blocked-shot", "goal"]:
            event = GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=10,
                event_type=event_type,
                period=1,
                time_in_period="15:30",
                period_second=270,
                game_second=270,
            )
            assert event.is_shot

    def test_is_stoppage(self) -> None:
        """Stoppage events are properly detected."""
        for event_type in ["stoppage", "period-start", "period-end"]:
            event = GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=10,
                event_type=event_type,
                period=1,
                time_in_period="15:30",
                period_second=270,
                game_second=270,
            )
            assert event.is_stoppage

    def test_is_penalty(self) -> None:
        """Penalty events are properly detected."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=10,
            event_type="penalty",
            period=1,
            time_in_period="15:30",
            period_second=270,
            game_second=270,
        )
        assert event.is_penalty

    def test_is_faceoff(self) -> None:
        """Faceoff events are properly detected."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=10,
            event_type="faceoff",
            period=1,
            time_in_period="15:30",
            period_second=270,
            game_second=270,
        )
        assert event.is_faceoff


class TestEventAttribution:
    """Tests for EventAttribution matching."""

    def test_exact_match(self) -> None:
        """Exact time match is detected."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=10,
            event_type="goal",
            period=1,
            time_in_period="15:30",
            period_second=270,
            game_second=270,
        )
        attribution = EventAttribution(
            event=event,
            snapshot_second=270,
            offset=0,
            is_exact=True,
        )
        assert attribution.is_exact
        assert attribution.offset == 0

    def test_fuzzy_match(self) -> None:
        """Fuzzy match with offset is tracked."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=10,
            event_type="goal",
            period=1,
            time_in_period="15:30",
            period_second=270,
            game_second=270,
        )
        attribution = EventAttribution(
            event=event,
            snapshot_second=271,  # 1 second offset
            offset=1,
            is_exact=False,
        )
        assert not attribution.is_exact
        assert attribution.offset == 1


class TestEventAttributorMatching:
    """Tests for EventAttributor fuzzy matching logic."""

    @pytest.fixture
    def sample_snapshots(self) -> list[ExpandedSecond]:
        """Create sample snapshots for testing."""
        return [
            ExpandedSecond(
                game_id=2024020500,
                season_id=20242025,
                period=1,
                period_second=sec,
                game_second=sec,
                home_skaters=frozenset({1, 2, 3, 4, 5}),
                away_skaters=frozenset({10, 11, 12, 13, 14}),
            )
            for sec in [100, 101, 102, 103, 104, 105, 200, 201, 202]
        ]

    @pytest.fixture
    def mock_db(self):
        """Create a mock database service."""
        # We'll test the matching logic directly without DB
        return None

    def test_attribute_exact_match(
        self, sample_snapshots: list[ExpandedSecond]
    ) -> None:
        """Events with exact time match are attributed correctly."""
        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="goal",
                period=1,
                time_in_period="18:20",
                period_second=100,
                game_second=100,
            )
        ]

        # Test the matching logic directly
        attributor = EventAttributor(None, fuzzy_window=2)  # type: ignore
        result = attributor.attribute_to_snapshots(events, sample_snapshots)

        assert result.attributed == 1
        assert result.unattributed == 0
        assert result.attributions[0].is_exact
        assert result.attributions[0].snapshot_second == 100

    def test_attribute_fuzzy_match(
        self, sample_snapshots: list[ExpandedSecond]
    ) -> None:
        """Events with close time match are fuzzy matched."""
        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="goal",
                period=1,
                time_in_period="18:20",
                period_second=106,  # No exact match, but 105 is within window
                game_second=106,
            )
        ]

        attributor = EventAttributor(None, fuzzy_window=2)  # type: ignore
        result = attributor.attribute_to_snapshots(events, sample_snapshots)

        assert result.attributed == 1
        assert not result.attributions[0].is_exact
        assert result.attributions[0].snapshot_second == 105
        assert result.attributions[0].offset == -1

    def test_attribute_no_match(self, sample_snapshots: list[ExpandedSecond]) -> None:
        """Events with no matching snapshot are unattributed."""
        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="goal",
                period=1,
                time_in_period="18:20",
                period_second=150,  # No snapshot near this time
                game_second=150,
            )
        ]

        attributor = EventAttributor(None, fuzzy_window=2)  # type: ignore
        result = attributor.attribute_to_snapshots(events, sample_snapshots)

        assert result.attributed == 0
        assert result.unattributed == 1
        assert len(result.errors) == 1

    def test_attribute_multiple_events(
        self, sample_snapshots: list[ExpandedSecond]
    ) -> None:
        """Multiple events are attributed correctly."""
        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="shot-on-goal",
                period=1,
                time_in_period="18:20",
                period_second=100,
                game_second=100,
            ),
            GameEvent(
                event_id=2,
                game_id=2024020500,
                event_idx=2,
                event_type="goal",
                period=1,
                time_in_period="16:40",
                period_second=200,
                game_second=200,
            ),
            GameEvent(
                event_id=3,
                game_id=2024020500,
                event_idx=3,
                event_type="penalty",
                period=1,
                time_in_period="15:00",
                period_second=300,  # No match
                game_second=300,
            ),
        ]

        attributor = EventAttributor(None, fuzzy_window=2)  # type: ignore
        result = attributor.attribute_to_snapshots(events, sample_snapshots)

        assert result.total_events == 3
        assert result.attributed == 2
        assert result.unattributed == 1


class TestStoppageDetection:
    """Tests for stoppage second detection."""

    def test_get_stoppage_seconds(self) -> None:
        """Stoppage events are extracted correctly."""
        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="stoppage",
                period=1,
                time_in_period="18:20",
                period_second=100,
                game_second=100,
            ),
            GameEvent(
                event_id=2,
                game_id=2024020500,
                event_idx=2,
                event_type="goal",
                period=1,
                time_in_period="16:40",
                period_second=200,
                game_second=200,
            ),
            GameEvent(
                event_id=3,
                game_id=2024020500,
                event_idx=3,
                event_type="period-end",
                period=1,
                time_in_period="00:00",
                period_second=1200,
                game_second=1200,
            ),
        ]

        attributions = [
            EventAttribution(event=events[0], snapshot_second=100),
            EventAttribution(event=events[1], snapshot_second=200),
            EventAttribution(event=events[2], snapshot_second=1200),
        ]

        attributor = EventAttributor(None)  # type: ignore
        stoppages = attributor.get_stoppage_seconds(attributions)

        assert 100 in stoppages  # stoppage event
        assert 200 not in stoppages  # goal is not a stoppage
        assert 1200 in stoppages  # period-end is a stoppage


class TestAttributionResult:
    """Tests for AttributionResult dataclass."""

    def test_empty_result(self) -> None:
        """Empty result has correct defaults."""
        result = AttributionResult(game_id=2024020500)
        assert result.total_events == 0
        assert result.attributed == 0
        assert result.unattributed == 0
        assert len(result.attributions) == 0
        assert len(result.errors) == 0

    def test_result_with_data(self) -> None:
        """Result with data is correctly populated."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=1,
            event_type="goal",
            period=1,
            time_in_period="18:20",
            period_second=100,
            game_second=100,
        )
        result = AttributionResult(
            game_id=2024020500,
            total_events=2,
            attributed=1,
            unattributed=1,
            attributions=[EventAttribution(event=event, snapshot_second=100)],
            errors=["Event not matched"],
        )
        assert result.total_events == 2
        assert result.attributed == 1
        assert len(result.attributions) == 1
        assert len(result.errors) == 1
