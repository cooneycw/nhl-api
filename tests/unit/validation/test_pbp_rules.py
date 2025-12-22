"""Tests for play-by-play internal consistency validation rules."""
# mypy: disable-error-code="arg-type,type-arg"

from __future__ import annotations

from typing import Any

from nhl_api.validation.rules.play_by_play import validate_play_by_play


class MockPlayer:
    """Mock player for events."""

    def __init__(
        self, player_id: int = 8471214, name: str = "Test Player", role: str = "scorer"
    ):
        self.player_id = player_id
        self.name = name
        self.role = role


class MockGameEvent:
    """Mock game event for testing."""

    def __init__(
        self,
        event_id: int = 1,
        event_type: str = "shot",
        period: int = 1,
        period_type: str = "REG",
        time_in_period: str = "10:30",
        sort_order: int = 1,
        home_score: int = 0,
        away_score: int = 0,
        home_sog: int = 5,
        away_sog: int = 3,
        x_coord: float | None = 50.0,
        y_coord: float | None = 20.0,
        players: list | None = None,
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.period = period
        self.period_type = period_type
        self.time_in_period = time_in_period
        self.sort_order = sort_order
        self.home_score = home_score
        self.away_score = away_score
        self.home_sog = home_sog
        self.away_sog = away_sog
        self.x_coord = x_coord
        self.y_coord = y_coord
        self.players = players or []


class MockParsedPlayByPlay:
    """Mock parsed play-by-play for testing."""

    def __init__(
        self, events: list[Any], game_id: int = 2024020500, game_type: int = 2
    ):
        self.events = events
        self.game_id = game_id
        self.game_type = game_type


class TestAssistsPerGoalValidation:
    """Tests for 0-2 assists per goal validation."""

    def test_goal_with_two_assists(self):
        """Goal with 2 assists should pass."""
        event = MockGameEvent(
            event_type="goal",
            players=[
                MockPlayer(role="scorer"),
                MockPlayer(role="assist"),
                MockPlayer(role="assist"),
            ],
        )
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        assist_results = [r for r in results if r.rule_name == "pbp_assists_per_goal"]
        assert len(assist_results) == 1
        assert assist_results[0].passed is True

    def test_goal_with_one_assist(self):
        """Goal with 1 assist should pass."""
        event = MockGameEvent(
            event_type="goal",
            players=[MockPlayer(role="scorer"), MockPlayer(role="assist")],
        )
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        assist_results = [r for r in results if r.rule_name == "pbp_assists_per_goal"]
        assert len(assist_results) == 1
        assert assist_results[0].passed is True

    def test_unassisted_goal(self):
        """Unassisted goal (0 assists) should pass."""
        event = MockGameEvent(
            event_type="goal",
            players=[MockPlayer(role="scorer")],
        )
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        assist_results = [r for r in results if r.rule_name == "pbp_assists_per_goal"]
        assert len(assist_results) == 1
        assert assist_results[0].passed is True

    def test_goal_with_three_assists(self):
        """Goal with 3 assists should fail."""
        event = MockGameEvent(
            event_type="goal",
            players=[
                MockPlayer(role="scorer"),
                MockPlayer(role="assist"),
                MockPlayer(role="assist"),
                MockPlayer(role="assist"),
            ],
        )
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        assist_results = [r for r in results if r.rule_name == "pbp_assists_per_goal"]
        assert len(assist_results) == 1
        assert assist_results[0].passed is False
        assert assist_results[0].severity == "error"


class TestPeriodTimeRangeValidation:
    """Tests for period time range validation."""

    def test_valid_regulation_time(self):
        """Time within 0:00-20:00 in regulation should pass."""
        event = MockGameEvent(period=1, period_type="REG", time_in_period="15:30")
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        time_results = [r for r in results if r.rule_name == "pbp_period_time_range"]
        assert len(time_results) == 1
        assert time_results[0].passed is True

    def test_valid_start_of_period(self):
        """Time at 0:00 should pass."""
        event = MockGameEvent(period=1, period_type="REG", time_in_period="0:00")
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        time_results = [r for r in results if r.rule_name == "pbp_period_time_range"]
        assert len(time_results) == 1
        assert time_results[0].passed is True

    def test_valid_end_of_period(self):
        """Time at 20:00 should pass."""
        event = MockGameEvent(period=1, period_type="REG", time_in_period="20:00")
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        time_results = [r for r in results if r.rule_name == "pbp_period_time_range"]
        assert len(time_results) == 1
        assert time_results[0].passed is True

    def test_overtime_regular_season(self):
        """OT time within 0:00-5:00 (regular season) should pass."""
        event = MockGameEvent(period=4, period_type="OT", time_in_period="3:30")
        pbp = MockParsedPlayByPlay([event], game_type=2)  # Regular season
        results = validate_play_by_play(pbp)
        time_results = [r for r in results if r.rule_name == "pbp_period_time_range"]
        assert len(time_results) == 1
        assert time_results[0].passed is True

    def test_invalid_time_format(self):
        """Invalid time format should fail."""
        event = MockGameEvent(period=1, period_type="REG", time_in_period="invalid")
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        time_results = [r for r in results if r.rule_name == "pbp_period_time_range"]
        assert len(time_results) == 1
        assert time_results[0].passed is False
        assert time_results[0].severity == "warning"


class TestChronologicalOrderValidation:
    """Tests for chronological event ordering."""

    def test_events_in_order(self):
        """Events with increasing sort_order should pass."""
        events = [
            MockGameEvent(event_id=1, sort_order=1),
            MockGameEvent(event_id=2, sort_order=2),
            MockGameEvent(event_id=3, sort_order=3),
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        order_results = [r for r in results if r.rule_name == "pbp_chronological_order"]
        assert len(order_results) == 1
        assert order_results[0].passed is True

    def test_events_out_of_order(self):
        """Events with decreasing sort_order should fail."""
        events = [
            MockGameEvent(event_id=1, sort_order=3),
            MockGameEvent(event_id=2, sort_order=1),  # Out of order
            MockGameEvent(event_id=3, sort_order=2),
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        order_results = [r for r in results if r.rule_name == "pbp_chronological_order"]
        assert len(order_results) == 1
        assert order_results[0].passed is False

    def test_single_event(self):
        """Single event should pass."""
        events = [MockGameEvent(event_id=1, sort_order=1)]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        order_results = [r for r in results if r.rule_name == "pbp_chronological_order"]
        assert len(order_results) == 1
        assert order_results[0].passed is True


class TestScoreProgressionValidation:
    """Tests for score never decreases validation."""

    def test_score_increases(self):
        """Score that increases should pass."""
        events = [
            MockGameEvent(event_id=1, home_score=0, away_score=0, sort_order=1),
            MockGameEvent(event_id=2, home_score=1, away_score=0, sort_order=2),
            MockGameEvent(event_id=3, home_score=1, away_score=1, sort_order=3),
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        score_results = [r for r in results if r.rule_name == "pbp_score_progression"]
        assert len(score_results) == 1
        assert score_results[0].passed is True

    def test_score_stays_same(self):
        """Score that stays same should pass."""
        events = [
            MockGameEvent(event_id=1, home_score=1, away_score=1, sort_order=1),
            MockGameEvent(event_id=2, home_score=1, away_score=1, sort_order=2),
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        score_results = [r for r in results if r.rule_name == "pbp_score_progression"]
        assert len(score_results) == 1
        assert score_results[0].passed is True

    def test_score_decreases(self):
        """Score that decreases should fail."""
        events = [
            MockGameEvent(event_id=1, home_score=2, away_score=1, sort_order=1),
            MockGameEvent(
                event_id=2, home_score=1, away_score=1, sort_order=2
            ),  # Decreased
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        score_results = [r for r in results if r.rule_name == "pbp_score_progression"]
        assert len(score_results) == 1
        assert score_results[0].passed is False
        assert score_results[0].severity == "warning"


class TestSOGProgressionValidation:
    """Tests for SOG never decreases validation."""

    def test_sog_increases(self):
        """SOG that increases should pass."""
        events = [
            MockGameEvent(event_id=1, home_sog=5, away_sog=3, sort_order=1),
            MockGameEvent(event_id=2, home_sog=6, away_sog=4, sort_order=2),
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        sog_results = [r for r in results if r.rule_name == "pbp_sog_progression"]
        assert len(sog_results) == 1
        assert sog_results[0].passed is True

    def test_sog_decreases(self):
        """SOG that decreases should fail."""
        events = [
            MockGameEvent(event_id=1, home_sog=10, away_sog=8, sort_order=1),
            MockGameEvent(
                event_id=2, home_sog=9, away_sog=8, sort_order=2
            ),  # Decreased
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        sog_results = [r for r in results if r.rule_name == "pbp_sog_progression"]
        assert len(sog_results) == 1
        assert sog_results[0].passed is False


class TestCoordinatesRangeValidation:
    """Tests for coordinate range validation."""

    def test_valid_coordinates(self):
        """Coordinates within range should pass."""
        event = MockGameEvent(x_coord=50.0, y_coord=20.0)
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        coord_results = [r for r in results if r.rule_name == "pbp_coordinates_range"]
        assert all(r.passed for r in coord_results)

    def test_x_coord_out_of_range(self):
        """X coordinate > 100 should fail."""
        event = MockGameEvent(x_coord=150.0, y_coord=20.0)
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        coord_results = [r for r in results if r.rule_name == "pbp_coordinates_range"]
        x_failed = [r for r in coord_results if "x_coord" in r.message and not r.passed]
        assert len(x_failed) == 1

    def test_y_coord_out_of_range(self):
        """Y coordinate > 42.5 should fail."""
        event = MockGameEvent(x_coord=50.0, y_coord=50.0)
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        coord_results = [r for r in results if r.rule_name == "pbp_coordinates_range"]
        y_failed = [r for r in coord_results if "y_coord" in r.message and not r.passed]
        assert len(y_failed) == 1

    def test_null_coordinates(self):
        """Null coordinates should not generate validation results."""
        event = MockGameEvent(x_coord=None, y_coord=None)
        pbp = MockParsedPlayByPlay([event])
        results = validate_play_by_play(pbp)
        coord_results = [r for r in results if r.rule_name == "pbp_coordinates_range"]
        assert len(coord_results) == 0


class TestPeriodSequenceValidation:
    """Tests for period sequence validation."""

    def test_valid_three_periods(self):
        """Periods 1, 2, 3 should pass."""
        events = [
            MockGameEvent(event_id=1, period=1, sort_order=1),
            MockGameEvent(event_id=2, period=2, sort_order=2),
            MockGameEvent(event_id=3, period=3, sort_order=3),
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        period_results = [r for r in results if r.rule_name == "pbp_period_sequence"]
        assert len(period_results) == 1
        assert period_results[0].passed is True

    def test_period_gap(self):
        """Gap in periods (1, 3 missing 2) should fail."""
        events = [
            MockGameEvent(event_id=1, period=1, sort_order=1),
            MockGameEvent(event_id=2, period=3, sort_order=2),  # Missing period 2
        ]
        pbp = MockParsedPlayByPlay(events)
        results = validate_play_by_play(pbp)
        period_results = [r for r in results if r.rule_name == "pbp_period_sequence"]
        assert len(period_results) == 1
        assert period_results[0].passed is False

    def test_empty_events(self):
        """No events should pass."""
        pbp = MockParsedPlayByPlay([])
        results = validate_play_by_play(pbp)
        period_results = [r for r in results if r.rule_name == "pbp_period_sequence"]
        assert len(period_results) == 1
        assert period_results[0].passed is True
