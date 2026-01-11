"""Integration tests for event attribution validation (T018).

Validates that event attribution to second snapshots is accurate
by comparing against official scorer records.

The key validation is:
- Events are attributed to the correct game seconds
- Event player IDs match official records
- Fuzzy matching window is appropriate

Issue: #260 - Wave 2: Validation & Quality (T018)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from nhl_api.services.analytics.event_attributor import (
    EventAttribution,
    EventAttributor,
    GameEvent,
)
from tests.integration.analytics.conftest import make_record

if TYPE_CHECKING:
    pass


class TestEventAttributorFetch:
    """Tests for fetching game events from database."""

    @pytest.mark.asyncio
    async def test_get_game_events(self) -> None:
        """Should fetch and parse game events correctly."""
        db = AsyncMock()
        db.fetch = AsyncMock(
            return_value=[
                make_record(
                    {
                        "id": 1,
                        "game_id": 2024020500,
                        "event_idx": 1,
                        "event_type": "faceoff",
                        "period": 1,
                        "time_in_period": "20:00",
                        "event_owner_team_id": 22,
                        "player1_id": 8478402,
                        "player2_id": 8477846,
                        "player3_id": None,
                        "goalie_id": None,
                        "x_coord": 0.0,
                        "y_coord": 0.0,
                        "zone": "N",
                        "description": "Faceoff",
                    }
                ),
                make_record(
                    {
                        "id": 2,
                        "game_id": 2024020500,
                        "event_idx": 2,
                        "event_type": "shot-on-goal",
                        "period": 1,
                        "time_in_period": "18:30",
                        "event_owner_team_id": 22,
                        "player1_id": 8478402,
                        "player2_id": None,
                        "player3_id": None,
                        "goalie_id": 8477970,
                        "x_coord": 75.0,
                        "y_coord": 10.0,
                        "zone": "O",
                        "description": "Shot on goal",
                    }
                ),
            ]
        )

        attributor = EventAttributor(db)
        events = await attributor.get_game_events(game_id=2024020500)

        assert len(events) == 2
        assert all(isinstance(e, GameEvent) for e in events)

        # Check first event
        assert events[0].event_type == "faceoff"
        assert events[0].period == 1
        assert events[0].game_second == 0  # 20:00 in period 1 = 0s elapsed

        # Check second event
        assert events[1].event_type == "shot-on-goal"
        assert events[1].period == 1
        assert events[1].game_second == 90  # 18:30 in period 1 = 90s elapsed

    @pytest.mark.asyncio
    async def test_get_game_events_empty(self) -> None:
        """Should return empty list for game with no events."""
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])

        attributor = EventAttributor(db)
        events = await attributor.get_game_events(game_id=2024020500)

        assert events == []


class TestEventAttribution:
    """Tests for attributing events to snapshots."""

    def test_exact_match_attribution(self) -> None:
        """Should attribute events with exact time match."""
        from dataclasses import dataclass

        @dataclass
        class MockSnapshot:
            game_second: int

        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="shot-on-goal",
                period=1,
                time_in_period="18:30",
                period_second=90,
                game_second=90,
                team_id=22,
                player1_id=8478402,
            ),
        ]

        snapshots = [
            MockSnapshot(game_second=90),
        ]

        attributor = EventAttributor(AsyncMock())
        result = attributor.attribute_to_snapshots(events, snapshots)

        assert result.total_events == 1
        assert result.attributed == 1
        assert result.unattributed == 0
        assert len(result.attributions) == 1
        assert result.attributions[0].is_exact
        assert result.attributions[0].offset == 0

    def test_fuzzy_match_attribution(self) -> None:
        """Should attribute events with fuzzy time match."""
        from dataclasses import dataclass

        @dataclass
        class MockSnapshot:
            game_second: int

        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="shot-on-goal",
                period=1,
                time_in_period="18:30",
                period_second=90,
                game_second=90,
                team_id=22,
                player1_id=8478402,
            ),
        ]

        # Snapshot is 1 second off
        snapshots = [
            MockSnapshot(game_second=91),
        ]

        attributor = EventAttributor(AsyncMock(), fuzzy_window=2)
        result = attributor.attribute_to_snapshots(events, snapshots)

        assert result.attributed == 1
        assert not result.attributions[0].is_exact
        assert result.attributions[0].offset == 1

    def test_no_match_attribution(self) -> None:
        """Should not attribute events without matching snapshot."""
        from dataclasses import dataclass

        @dataclass
        class MockSnapshot:
            game_second: int

        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="shot-on-goal",
                period=1,
                time_in_period="18:30",
                period_second=90,
                game_second=90,
                team_id=22,
                player1_id=8478402,
            ),
        ]

        # Snapshot is too far away
        snapshots = [
            MockSnapshot(game_second=100),
        ]

        attributor = EventAttributor(AsyncMock(), fuzzy_window=2)
        result = attributor.attribute_to_snapshots(events, snapshots)

        assert result.unattributed == 1
        assert len(result.errors) == 1
        assert "no matching snapshot" in result.errors[0]

    def test_empty_events_attribution(self) -> None:
        """Should handle empty events list."""
        attributor = EventAttributor(AsyncMock())
        result = attributor.attribute_to_snapshots([], [])

        assert result.total_events == 0
        assert result.attributed == 0


class TestEventTypes:
    """Tests for event type classification."""

    def test_goal_is_shot(self) -> None:
        """Goals should be classified as shots."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=1,
            event_type="goal",
            period=1,
            time_in_period="15:00",
            period_second=300,
            game_second=300,
        )

        assert event.is_goal
        assert event.is_shot  # Goals are also shots

    def test_stoppage_events(self) -> None:
        """Should correctly identify stoppage events."""
        stoppage_types = [
            "stoppage",
            "period-start",
            "period-end",
            "game-end",
            "delayed-penalty",
            "tv-timeout",
        ]

        for event_type in stoppage_types:
            event = GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type=event_type,
                period=1,
                time_in_period="10:00",
                period_second=600,
                game_second=600,
            )
            assert event.is_stoppage, f"{event_type} should be stoppage"

    def test_shot_events(self) -> None:
        """Should correctly identify shot events."""
        shot_types = [
            "shot-on-goal",
            "missed-shot",
            "blocked-shot",
            "goal",
        ]

        for event_type in shot_types:
            event = GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type=event_type,
                period=1,
                time_in_period="10:00",
                period_second=600,
                game_second=600,
            )
            assert event.is_shot, f"{event_type} should be shot"

    def test_penalty_event(self) -> None:
        """Should correctly identify penalty events."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=1,
            event_type="penalty",
            period=1,
            time_in_period="10:00",
            period_second=600,
            game_second=600,
        )
        assert event.is_penalty

    def test_faceoff_event(self) -> None:
        """Should correctly identify faceoff events."""
        event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=1,
            event_type="faceoff",
            period=1,
            time_in_period="20:00",
            period_second=0,
            game_second=0,
        )
        assert event.is_faceoff


class TestStoppageSeconds:
    """Tests for extracting stoppage seconds."""

    def test_get_stoppage_seconds(self) -> None:
        """Should extract seconds with stoppages."""
        stoppage_event = GameEvent(
            event_id=1,
            game_id=2024020500,
            event_idx=1,
            event_type="stoppage",
            period=1,
            time_in_period="15:00",
            period_second=300,
            game_second=300,
        )

        shot_event = GameEvent(
            event_id=2,
            game_id=2024020500,
            event_idx=2,
            event_type="shot-on-goal",
            period=1,
            time_in_period="14:30",
            period_second=330,
            game_second=330,
        )

        attributions = [
            EventAttribution(event=stoppage_event, snapshot_second=300),
            EventAttribution(event=shot_event, snapshot_second=330),
        ]

        attributor = EventAttributor(AsyncMock())
        stoppage_seconds = attributor.get_stoppage_seconds(attributions)

        assert stoppage_seconds == {300}


class TestGoalieMap:
    """Tests for building goalie map from events."""

    def test_get_goalie_map(self) -> None:
        """Should build correct goalie map from shot events."""
        events = [
            GameEvent(
                event_id=1,
                game_id=2024020500,
                event_idx=1,
                event_type="shot-on-goal",
                period=1,
                time_in_period="18:00",
                period_second=120,
                game_second=120,
                team_id=22,  # Home team shooting
                player1_id=8478402,
                goalie_id=8477970,  # Away goalie
            ),
            GameEvent(
                event_id=2,
                game_id=2024020500,
                event_idx=2,
                event_type="shot-on-goal",
                period=1,
                time_in_period="16:00",
                period_second=240,
                game_second=240,
                team_id=25,  # Away team shooting
                player1_id=8477846,
                goalie_id=8479973,  # Home goalie
            ),
        ]

        attributor = EventAttributor(AsyncMock())
        goalie_map = attributor.get_goalie_map(
            events,
            home_team_id=22,
            away_team_id=25,
        )

        # Should have entries for both game seconds
        assert 120 in goalie_map
        assert 240 in goalie_map

        # First shot: home team shot, so away goalie sighting
        # Second shot: away team shot, so home goalie sighting
        assert goalie_map[240][0] == 8479973  # Home goalie
        assert goalie_map[120][1] == 8477970  # Away goalie


class TestEventAttributionValidation:
    """Integration tests for event attribution validation."""

    @pytest.mark.asyncio
    async def test_validate_event_attribution(self, sample_game_info: dict) -> None:
        """Should validate that events are attributed to correct seconds."""
        db = AsyncMock()

        # Mock events
        db.fetch = AsyncMock(
            return_value=[
                make_record(
                    {
                        "id": 1,
                        "game_id": 2024020500,
                        "event_idx": 1,
                        "event_type": "goal",
                        "period": 1,
                        "time_in_period": "15:00",
                        "event_owner_team_id": 22,
                        "player1_id": 8478402,
                        "player2_id": 8477934,
                        "player3_id": None,
                        "goalie_id": 8477970,
                        "x_coord": 80.0,
                        "y_coord": 5.0,
                        "zone": "O",
                        "description": "Goal",
                    }
                ),
            ]
        )

        attributor = EventAttributor(db)
        events = await attributor.get_game_events(game_id=2024020500)

        assert len(events) == 1
        assert events[0].event_type == "goal"
        assert events[0].player1_id == 8478402
        # At 15:00, 5 minutes elapsed = 300 seconds
        assert events[0].game_second == 300

    @pytest.mark.asyncio
    async def test_attribution_with_multiple_periods(self) -> None:
        """Should handle events across multiple periods."""
        db = AsyncMock()

        db.fetch = AsyncMock(
            return_value=[
                make_record(
                    {
                        "id": 1,
                        "game_id": 2024020500,
                        "event_idx": 1,
                        "event_type": "goal",
                        "period": 1,
                        "time_in_period": "10:00",
                        "event_owner_team_id": 22,
                        "player1_id": 8478402,
                        "player2_id": None,
                        "player3_id": None,
                        "goalie_id": 8477970,
                        "x_coord": None,
                        "y_coord": None,
                        "zone": None,
                        "description": None,
                    }
                ),
                make_record(
                    {
                        "id": 2,
                        "game_id": 2024020500,
                        "event_idx": 50,
                        "event_type": "goal",
                        "period": 2,
                        "time_in_period": "10:00",
                        "event_owner_team_id": 25,
                        "player1_id": 8477846,
                        "player2_id": None,
                        "player3_id": None,
                        "goalie_id": 8479973,
                        "x_coord": None,
                        "y_coord": None,
                        "zone": None,
                        "description": None,
                    }
                ),
            ]
        )

        attributor = EventAttributor(db)
        events = await attributor.get_game_events(game_id=2024020500)

        assert len(events) == 2

        # Period 1, 10:00 remaining = 600s elapsed in period 1
        assert events[0].game_second == 600

        # Period 2, 10:00 remaining = 1200 (P1) + 600 (P2) = 1800s
        assert events[1].game_second == 1800


# Fixtures for integration with analytics validator
@pytest.fixture
def sample_game_info() -> dict:
    """Sample game metadata."""
    return {
        "game_id": 2024020500,
        "season_id": 20242025,
        "home_team_id": 22,
        "away_team_id": 25,
        "period": 3,
    }
