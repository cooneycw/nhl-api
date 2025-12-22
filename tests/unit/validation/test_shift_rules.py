"""Tests for shift chart internal consistency validation rules."""

from __future__ import annotations

from typing import Any

from nhl_api.validation.rules.shift_chart import validate_shift_chart


class MockShiftRecord:
    """Mock shift record for testing."""

    def __init__(
        self,
        shift_id: int = 1,
        player_id: int = 8471214,
        full_name: str = "Test Player",
        period: int = 1,
        shift_number: int = 1,
        start_time: str = "0:00",
        end_time: str = "0:45",
        duration_seconds: int = 45,
        is_goal_event: bool = False,
    ):
        self.shift_id = shift_id
        self.player_id = player_id
        self.full_name = full_name
        self.period = period
        self.shift_number = shift_number
        self.start_time = start_time
        self.end_time = end_time
        self.duration_seconds = duration_seconds
        self.is_goal_event = is_goal_event


class MockParsedShiftChart:
    """Mock parsed shift chart for testing."""

    def __init__(self, shifts: list[Any], game_id: int = 2024020500):
        self.shifts = shifts
        self.game_id = game_id


class TestShiftEndAfterStartValidation:
    """Tests for end_time > start_time validation."""

    def test_valid_shift_timing(self):
        """End time after start time should pass."""
        shift = MockShiftRecord(start_time="0:00", end_time="0:45")
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        timing_results = [r for r in results if r.rule_name == "shift_end_after_start"]
        assert len(timing_results) == 1
        assert timing_results[0].passed is True

    def test_end_before_start(self):
        """End time before start time should fail."""
        shift = MockShiftRecord(start_time="5:00", end_time="4:30")
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        timing_results = [r for r in results if r.rule_name == "shift_end_after_start"]
        assert len(timing_results) == 1
        assert timing_results[0].passed is False
        assert timing_results[0].severity == "error"

    def test_same_start_and_end(self):
        """Same start and end time should pass (zero duration shift)."""
        shift = MockShiftRecord(start_time="5:00", end_time="5:00", duration_seconds=0)
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        timing_results = [r for r in results if r.rule_name == "shift_end_after_start"]
        assert len(timing_results) == 1
        assert timing_results[0].passed is True


class TestShiftDurationMatchesValidation:
    """Tests for duration matching time difference validation."""

    def test_duration_matches(self):
        """Duration matches end - start should pass."""
        shift = MockShiftRecord(start_time="0:00", end_time="0:45", duration_seconds=45)
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        dur_results = [r for r in results if r.rule_name == "shift_duration_matches"]
        assert len(dur_results) == 1
        assert dur_results[0].passed is True

    def test_duration_mismatch(self):
        """Duration not matching should fail."""
        shift = MockShiftRecord(
            start_time="0:00",
            end_time="0:45",
            duration_seconds=60,  # Should be 45
        )
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        dur_results = [r for r in results if r.rule_name == "shift_duration_matches"]
        assert len(dur_results) == 1
        assert dur_results[0].passed is False
        assert dur_results[0].severity == "warning"

    def test_duration_within_tolerance(self):
        """Duration within 2-second tolerance should pass."""
        shift = MockShiftRecord(
            start_time="0:00",
            end_time="0:45",
            duration_seconds=46,  # 1 second off
        )
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        dur_results = [r for r in results if r.rule_name == "shift_duration_matches"]
        assert len(dur_results) == 1
        assert dur_results[0].passed is True


class TestShiftPeriodValidation:
    """Tests for valid period number validation."""

    def test_valid_period_1(self):
        """Period 1 should pass."""
        shift = MockShiftRecord(period=1)
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        period_results = [r for r in results if r.rule_name == "shift_period_valid"]
        assert len(period_results) == 1
        assert period_results[0].passed is True

    def test_valid_period_3(self):
        """Period 3 should pass."""
        shift = MockShiftRecord(period=3)
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        period_results = [r for r in results if r.rule_name == "shift_period_valid"]
        assert len(period_results) == 1
        assert period_results[0].passed is True

    def test_valid_overtime_period(self):
        """Period 4 (OT) should pass."""
        shift = MockShiftRecord(period=4)
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        period_results = [r for r in results if r.rule_name == "shift_period_valid"]
        assert len(period_results) == 1
        assert period_results[0].passed is True

    def test_invalid_period_zero(self):
        """Period 0 should fail."""
        shift = MockShiftRecord(period=0)
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        period_results = [r for r in results if r.rule_name == "shift_period_valid"]
        assert len(period_results) == 1
        assert period_results[0].passed is False
        assert period_results[0].severity == "warning"

    def test_invalid_period_negative(self):
        """Negative period should fail."""
        shift = MockShiftRecord(period=-1)
        shifts = MockParsedShiftChart([shift])
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        period_results = [r for r in results if r.rule_name == "shift_period_valid"]
        assert len(period_results) == 1
        assert period_results[0].passed is False


class TestNoOverlappingShiftsValidation:
    """Tests for no overlapping shifts per player validation."""

    def test_no_overlaps(self):
        """Non-overlapping shifts should pass."""
        shifts_data = [
            MockShiftRecord(
                shift_id=1,
                player_id=100,
                period=1,
                shift_number=1,
                start_time="0:00",
                end_time="0:45",
            ),
            MockShiftRecord(
                shift_id=2,
                player_id=100,
                period=1,
                shift_number=2,
                start_time="1:00",
                end_time="1:45",
            ),
        ]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        overlap_results = [r for r in results if r.rule_name == "shift_no_overlap"]
        assert len(overlap_results) == 1
        assert overlap_results[0].passed is True

    def test_overlapping_shifts(self):
        """Overlapping shifts for same player should fail."""
        shifts_data = [
            MockShiftRecord(
                shift_id=1,
                player_id=100,
                period=1,
                shift_number=1,
                start_time="0:00",
                end_time="1:00",
            ),
            MockShiftRecord(
                shift_id=2,
                player_id=100,
                period=1,
                shift_number=2,
                start_time="0:30",  # Overlaps with previous shift
                end_time="1:30",
            ),
        ]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        overlap_results = [r for r in results if r.rule_name == "shift_no_overlap"]
        assert len(overlap_results) == 1
        assert overlap_results[0].passed is False
        assert overlap_results[0].severity == "warning"

    def test_different_players_can_overlap(self):
        """Overlapping shifts for different players should pass."""
        shifts_data = [
            MockShiftRecord(
                shift_id=1,
                player_id=100,
                period=1,
                shift_number=1,
                start_time="0:00",
                end_time="1:00",
            ),
            MockShiftRecord(
                shift_id=2,
                player_id=200,  # Different player
                period=1,
                shift_number=1,
                start_time="0:30",
                end_time="1:30",
            ),
        ]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        overlap_results = [r for r in results if r.rule_name == "shift_no_overlap"]
        assert len(overlap_results) == 1
        assert overlap_results[0].passed is True

    def test_different_periods_can_overlap_time(self):
        """Same time in different periods should pass."""
        shifts_data = [
            MockShiftRecord(
                shift_id=1,
                player_id=100,
                period=1,
                shift_number=1,
                start_time="0:00",
                end_time="1:00",
            ),
            MockShiftRecord(
                shift_id=2,
                player_id=100,
                period=2,  # Different period
                shift_number=2,
                start_time="0:00",
                end_time="1:00",
            ),
        ]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        overlap_results = [r for r in results if r.rule_name == "shift_no_overlap"]
        assert len(overlap_results) == 1
        assert overlap_results[0].passed is True


class TestSequentialShiftNumbersValidation:
    """Tests for sequential shift numbers per player validation."""

    def test_sequential_shifts(self):
        """Sequential shift numbers should pass."""
        shifts_data = [
            MockShiftRecord(player_id=100, shift_number=1),
            MockShiftRecord(player_id=100, shift_number=2),
            MockShiftRecord(player_id=100, shift_number=3),
        ]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        seq_results = [r for r in results if r.rule_name == "shift_sequential_numbers"]
        assert len(seq_results) == 1
        assert seq_results[0].passed is True

    def test_gap_in_shift_numbers(self):
        """Gap in shift numbers should fail."""
        shifts_data = [
            MockShiftRecord(player_id=100, shift_number=1),
            MockShiftRecord(player_id=100, shift_number=3),  # Missing 2
        ]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        seq_results = [r for r in results if r.rule_name == "shift_sequential_numbers"]
        assert len(seq_results) == 1
        assert seq_results[0].passed is False
        assert seq_results[0].severity == "info"

    def test_single_shift(self):
        """Single shift should pass."""
        shifts_data = [MockShiftRecord(player_id=100, shift_number=1)]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        seq_results = [r for r in results if r.rule_name == "shift_sequential_numbers"]
        assert len(seq_results) == 1
        assert seq_results[0].passed is True


class TestGoalEventsExcluded:
    """Tests that goal events are excluded from most validations."""

    def test_goal_events_excluded(self):
        """Goal events should not be validated as shifts."""
        shifts_data = [
            MockShiftRecord(
                shift_id=1,
                period=1,
                start_time="10:00",
                end_time="10:00",
                duration_seconds=0,
                is_goal_event=True,
            )
        ]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        # Goal events are filtered out, so no shift validations should run
        shift_results = [
            r
            for r in results
            if r.rule_name in ("shift_end_after_start", "shift_duration_matches")
        ]
        assert len(shift_results) == 0


class TestMultiplePlayersValidation:
    """Tests for validating multiple players."""

    def test_multiple_players_all_valid(self):
        """Multiple players with valid shifts should all pass."""
        shifts_data = [
            MockShiftRecord(
                player_id=100,
                shift_number=1,
                shift_id=1,
                start_time="0:00",
                end_time="0:45",
            ),
            MockShiftRecord(
                player_id=100,
                shift_number=2,
                shift_id=2,
                start_time="1:00",
                end_time="1:45",
            ),
            MockShiftRecord(
                player_id=200,
                shift_number=1,
                shift_id=3,
                start_time="0:00",
                end_time="0:45",
            ),
            MockShiftRecord(
                player_id=200,
                shift_number=2,
                shift_id=4,
                start_time="1:00",
                end_time="1:45",
            ),
        ]
        shifts = MockParsedShiftChart(shifts_data)
        results = validate_shift_chart(shifts)  # type: ignore[arg-type]
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0
