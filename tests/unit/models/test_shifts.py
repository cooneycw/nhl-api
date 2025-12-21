"""Unit tests for shift data models.

Tests cover:
- ShiftRecord creation and properties
- ParsedShiftChart creation and helper methods
- TOI calculations
- Filtering methods
- Serialization
- Duration parsing
"""

from __future__ import annotations

import pytest

from nhl_api.models.shifts import (
    DETAIL_GOAL_EV,
    DETAIL_SHIFT,
    GOAL_TYPE_CODE,
    SHIFT_TYPE_CODE,
    ParsedShiftChart,
    ShiftRecord,
    parse_duration,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_shift() -> ShiftRecord:
    """Create a sample shift record."""
    return ShiftRecord(
        shift_id=14765329,
        game_id=2024020500,
        player_id=8470613,
        first_name="Brent",
        last_name="Burns",
        team_id=12,
        team_abbrev="CAR",
        period=1,
        shift_number=1,
        start_time="00:28",
        end_time="01:15",
        duration_seconds=47,
        type_code=SHIFT_TYPE_CODE,
        is_goal_event=False,
    )


@pytest.fixture
def goal_event_shift() -> ShiftRecord:
    """Create a goal event shift record."""
    return ShiftRecord(
        shift_id=14765400,
        game_id=2024020500,
        player_id=8471426,
        first_name="Jordan",
        last_name="Staal",
        team_id=12,
        team_abbrev="CAR",
        period=2,
        shift_number=15,
        start_time="05:00",
        end_time="05:00",
        duration_seconds=0,
        type_code=GOAL_TYPE_CODE,
        is_goal_event=True,
        event_description="EVG",
        event_details="Jordan Staal",
        detail_code=DETAIL_GOAL_EV,
    )


@pytest.fixture
def sample_shifts() -> list[ShiftRecord]:
    """Create a list of sample shifts for testing."""
    return [
        # Player 1 (Burns) - Team 12
        ShiftRecord(
            shift_id=1,
            game_id=2024020500,
            player_id=8470613,
            first_name="Brent",
            last_name="Burns",
            team_id=12,
            team_abbrev="CAR",
            period=1,
            shift_number=1,
            start_time="00:28",
            end_time="01:15",
            duration_seconds=47,
        ),
        ShiftRecord(
            shift_id=2,
            game_id=2024020500,
            player_id=8470613,
            first_name="Brent",
            last_name="Burns",
            team_id=12,
            team_abbrev="CAR",
            period=1,
            shift_number=2,
            start_time="02:00",
            end_time="02:45",
            duration_seconds=45,
        ),
        ShiftRecord(
            shift_id=3,
            game_id=2024020500,
            player_id=8470613,
            first_name="Brent",
            last_name="Burns",
            team_id=12,
            team_abbrev="CAR",
            period=2,
            shift_number=3,
            start_time="00:30",
            end_time="01:10",
            duration_seconds=40,
        ),
        # Player 2 (Staal) - Team 12
        ShiftRecord(
            shift_id=4,
            game_id=2024020500,
            player_id=8471426,
            first_name="Jordan",
            last_name="Staal",
            team_id=12,
            team_abbrev="CAR",
            period=1,
            shift_number=1,
            start_time="00:00",
            end_time="00:50",
            duration_seconds=50,
        ),
        # Player 3 (Barzal) - Team 2 (away)
        ShiftRecord(
            shift_id=5,
            game_id=2024020500,
            player_id=8478445,
            first_name="Mathew",
            last_name="Barzal",
            team_id=2,
            team_abbrev="NYI",
            period=1,
            shift_number=1,
            start_time="00:00",
            end_time="01:00",
            duration_seconds=60,
        ),
        # Goal event - not counted in TOI
        ShiftRecord(
            shift_id=6,
            game_id=2024020500,
            player_id=8471426,
            first_name="Jordan",
            last_name="Staal",
            team_id=12,
            team_abbrev="CAR",
            period=2,
            shift_number=10,
            start_time="05:00",
            end_time="05:00",
            duration_seconds=0,
            type_code=GOAL_TYPE_CODE,
            is_goal_event=True,
            event_description="EVG",
        ),
    ]


@pytest.fixture
def parsed_chart(sample_shifts: list[ShiftRecord]) -> ParsedShiftChart:
    """Create a parsed shift chart."""
    return ParsedShiftChart(
        game_id=2024020500,
        season_id=20242025,
        total_shifts=6,
        home_team_id=12,
        away_team_id=2,
        shifts=sample_shifts,
    )


# =============================================================================
# ShiftRecord Tests
# =============================================================================


class TestShiftRecord:
    """Tests for ShiftRecord dataclass."""

    def test_create_shift_record(self, sample_shift: ShiftRecord) -> None:
        """Test creating a shift record."""
        assert sample_shift.shift_id == 14765329
        assert sample_shift.game_id == 2024020500
        assert sample_shift.player_id == 8470613
        assert sample_shift.first_name == "Brent"
        assert sample_shift.last_name == "Burns"
        assert sample_shift.team_id == 12
        assert sample_shift.team_abbrev == "CAR"
        assert sample_shift.period == 1
        assert sample_shift.shift_number == 1
        assert sample_shift.start_time == "00:28"
        assert sample_shift.end_time == "01:15"
        assert sample_shift.duration_seconds == 47

    def test_default_values(self, sample_shift: ShiftRecord) -> None:
        """Test default values for optional fields."""
        assert sample_shift.type_code == SHIFT_TYPE_CODE
        assert sample_shift.is_goal_event is False
        assert sample_shift.event_description is None
        assert sample_shift.event_details is None
        assert sample_shift.detail_code == DETAIL_SHIFT
        assert sample_shift.hex_value is None

    def test_goal_event_shift(self, goal_event_shift: ShiftRecord) -> None:
        """Test goal event shift record."""
        assert goal_event_shift.type_code == GOAL_TYPE_CODE
        assert goal_event_shift.is_goal_event is True
        assert goal_event_shift.event_description == "EVG"
        assert goal_event_shift.event_details == "Jordan Staal"
        assert goal_event_shift.detail_code == DETAIL_GOAL_EV

    def test_full_name_property(self, sample_shift: ShiftRecord) -> None:
        """Test full_name property."""
        assert sample_shift.full_name == "Brent Burns"

    def test_duration_display_property(self, sample_shift: ShiftRecord) -> None:
        """Test duration_display property."""
        assert sample_shift.duration_seconds == 47
        assert sample_shift.duration_display == "00:47"

    def test_duration_display_with_minutes(self) -> None:
        """Test duration_display with minutes."""
        shift = ShiftRecord(
            shift_id=1,
            game_id=2024020500,
            player_id=123,
            first_name="Test",
            last_name="Player",
            team_id=1,
            team_abbrev="TST",
            period=1,
            shift_number=1,
            start_time="00:00",
            end_time="01:30",
            duration_seconds=90,
        )
        assert shift.duration_display == "01:30"

    def test_frozen_immutability(self, sample_shift: ShiftRecord) -> None:
        """Test that ShiftRecord is frozen (immutable)."""
        with pytest.raises(AttributeError):
            sample_shift.shift_id = 999  # type: ignore[misc]

    def test_slots_memory_efficiency(self, sample_shift: ShiftRecord) -> None:
        """Test that ShiftRecord uses slots."""
        assert hasattr(sample_shift, "__slots__")


# =============================================================================
# ParsedShiftChart Tests
# =============================================================================


class TestParsedShiftChart:
    """Tests for ParsedShiftChart dataclass."""

    def test_create_parsed_chart(self, parsed_chart: ParsedShiftChart) -> None:
        """Test creating a parsed shift chart."""
        assert parsed_chart.game_id == 2024020500
        assert parsed_chart.season_id == 20242025
        assert parsed_chart.total_shifts == 6
        assert parsed_chart.home_team_id == 12
        assert parsed_chart.away_team_id == 2
        assert len(parsed_chart.shifts) == 6

    def test_default_empty_shifts(self) -> None:
        """Test default empty shifts list."""
        chart = ParsedShiftChart(
            game_id=2024020500,
            season_id=20242025,
            total_shifts=0,
        )
        assert chart.shifts == []
        assert chart.home_team_id is None
        assert chart.away_team_id is None


class TestGetPlayerShifts:
    """Tests for get_player_shifts method."""

    def test_get_player_shifts(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting shifts for a specific player."""
        burns_shifts = parsed_chart.get_player_shifts(8470613)
        assert len(burns_shifts) == 3
        assert all(s.player_id == 8470613 for s in burns_shifts)

    def test_get_player_shifts_no_matches(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting shifts for non-existent player."""
        shifts = parsed_chart.get_player_shifts(999999)
        assert shifts == []


class TestGetPeriodShifts:
    """Tests for get_period_shifts method."""

    def test_get_period_shifts(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting shifts for a specific period."""
        p1_shifts = parsed_chart.get_period_shifts(1)
        assert len(p1_shifts) == 4
        assert all(s.period == 1 for s in p1_shifts)

    def test_get_period_shifts_period_2(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting shifts for period 2."""
        p2_shifts = parsed_chart.get_period_shifts(2)
        assert len(p2_shifts) == 2  # One shift + one goal event


class TestGetTeamShifts:
    """Tests for get_team_shifts method."""

    def test_get_home_team_shifts(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting shifts for home team."""
        home_shifts = parsed_chart.get_team_shifts(12)
        assert len(home_shifts) == 5  # Including goal event
        assert all(s.team_id == 12 for s in home_shifts)

    def test_get_away_team_shifts(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting shifts for away team."""
        away_shifts = parsed_chart.get_team_shifts(2)
        assert len(away_shifts) == 1
        assert away_shifts[0].player_id == 8478445


class TestGetPlayerToi:
    """Tests for get_player_toi method."""

    def test_get_player_toi(self, parsed_chart: ParsedShiftChart) -> None:
        """Test calculating player TOI."""
        burns_toi = parsed_chart.get_player_toi(8470613)
        # 47 + 45 + 40 = 132 seconds
        assert burns_toi == 132

    def test_get_player_toi_excludes_goal_events(
        self, parsed_chart: ParsedShiftChart
    ) -> None:
        """Test that goal events are excluded from TOI."""
        staal_toi = parsed_chart.get_player_toi(8471426)
        # Only the 50-second shift, not the goal event
        assert staal_toi == 50

    def test_get_player_toi_no_shifts(self, parsed_chart: ParsedShiftChart) -> None:
        """Test TOI for player with no shifts."""
        toi = parsed_chart.get_player_toi(999999)
        assert toi == 0


class TestGetPlayerToiByPeriod:
    """Tests for get_player_toi_by_period method."""

    def test_get_player_toi_by_period(self, parsed_chart: ParsedShiftChart) -> None:
        """Test calculating player TOI by period."""
        burns_toi = parsed_chart.get_player_toi_by_period(8470613)
        assert burns_toi[1] == 92  # 47 + 45
        assert burns_toi[2] == 40

    def test_get_player_toi_by_period_empty(
        self, parsed_chart: ParsedShiftChart
    ) -> None:
        """Test TOI by period for player with no shifts."""
        toi = parsed_chart.get_player_toi_by_period(999999)
        assert toi == {}


class TestGetPlayerShiftCount:
    """Tests for get_player_shift_count method."""

    def test_get_player_shift_count(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting shift count for a player."""
        count = parsed_chart.get_player_shift_count(8470613)
        assert count == 3

    def test_get_player_shift_count_excludes_goals(
        self, parsed_chart: ParsedShiftChart
    ) -> None:
        """Test that goal events are excluded from shift count."""
        count = parsed_chart.get_player_shift_count(8471426)
        assert count == 1  # Only the shift, not the goal


class TestGetAllPlayerIds:
    """Tests for get_all_player_ids method."""

    def test_get_all_player_ids(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting all unique player IDs."""
        player_ids = parsed_chart.get_all_player_ids()
        assert len(player_ids) == 3
        assert 8470613 in player_ids  # Burns
        assert 8471426 in player_ids  # Staal
        assert 8478445 in player_ids  # Barzal


class TestGetTeamPlayerIds:
    """Tests for get_team_player_ids method."""

    def test_get_team_player_ids(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting player IDs for a team."""
        home_players = parsed_chart.get_team_player_ids(12)
        assert len(home_players) == 2
        assert 8470613 in home_players
        assert 8471426 in home_players

    def test_get_away_team_player_ids(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting player IDs for away team."""
        away_players = parsed_chart.get_team_player_ids(2)
        assert len(away_players) == 1
        assert 8478445 in away_players


class TestGetGoalEvents:
    """Tests for get_goal_events method."""

    def test_get_goal_events(self, parsed_chart: ParsedShiftChart) -> None:
        """Test getting goal events."""
        goals = parsed_chart.get_goal_events()
        assert len(goals) == 1
        assert goals[0].is_goal_event is True
        assert goals[0].event_description == "EVG"


class TestChartProperties:
    """Tests for ParsedShiftChart properties."""

    def test_shift_count_property(self, parsed_chart: ParsedShiftChart) -> None:
        """Test shift_count property excludes goal events."""
        assert parsed_chart.shift_count == 5

    def test_goal_count_property(self, parsed_chart: ParsedShiftChart) -> None:
        """Test goal_count property."""
        assert parsed_chart.goal_count == 1


class TestToDict:
    """Tests for to_dict method."""

    def test_to_dict(self, parsed_chart: ParsedShiftChart) -> None:
        """Test converting to dictionary."""
        result = parsed_chart.to_dict()
        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert result["total_shifts"] == 6
        assert result["home_team_id"] == 12
        assert result["away_team_id"] == 2
        assert len(result["shifts"]) == 6

    def test_to_dict_shift_structure(self, parsed_chart: ParsedShiftChart) -> None:
        """Test that shifts are properly serialized."""
        result = parsed_chart.to_dict()
        shift = result["shifts"][0]
        assert "shift_id" in shift
        assert "player_id" in shift
        assert "duration_seconds" in shift
        assert "is_goal_event" in shift


# =============================================================================
# Parse Duration Tests
# =============================================================================


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_parse_duration_seconds_only(self) -> None:
        """Test parsing duration with seconds only."""
        assert parse_duration("00:47") == 47

    def test_parse_duration_with_minutes(self) -> None:
        """Test parsing duration with minutes."""
        assert parse_duration("01:30") == 90
        assert parse_duration("02:15") == 135

    def test_parse_duration_none(self) -> None:
        """Test parsing None duration."""
        assert parse_duration(None) == 0

    def test_parse_duration_empty_string(self) -> None:
        """Test parsing empty string."""
        assert parse_duration("") == 0

    def test_parse_duration_invalid_format(self) -> None:
        """Test parsing invalid format."""
        assert parse_duration("invalid") == 0
        assert parse_duration("1:2:3") == 0

    def test_parse_duration_non_numeric(self) -> None:
        """Test parsing non-numeric values."""
        assert parse_duration("ab:cd") == 0


# =============================================================================
# Module Export Tests
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_exports_from_models_init(self) -> None:
        """Test that all expected items are exported."""
        from nhl_api.models import (
            DETAIL_GOAL_EV,
            DETAIL_GOAL_PP,
            DETAIL_SHIFT,
            GOAL_TYPE_CODE,
            SHIFT_TYPE_CODE,
            ParsedShiftChart,
            ShiftRecord,
            parse_duration,
        )

        assert ShiftRecord is not None
        assert ParsedShiftChart is not None
        assert parse_duration is not None
        assert SHIFT_TYPE_CODE == 517
        assert GOAL_TYPE_CODE == 505
        assert DETAIL_SHIFT == 0
        assert DETAIL_GOAL_EV == 803
        assert DETAIL_GOAL_PP == 808
