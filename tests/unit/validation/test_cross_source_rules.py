"""Unit tests for cross-source validation rules."""
# mypy: disable-error-code="arg-type"

from __future__ import annotations

from nhl_api.downloaders.sources.nhl_json.boxscore import (
    ParsedBoxscore,
    SkaterStats,
    TeamBoxscore,
)
from nhl_api.downloaders.sources.nhl_json.play_by_play import (
    GameEvent,
    ParsedPlayByPlay,
)
from nhl_api.models.shifts import ParsedShiftChart, ShiftRecord
from nhl_api.validation import CrossSourceValidator
from nhl_api.validation.rules.cross_source import (
    validate_final_score_schedule_vs_boxscore,
    validate_goals_pbp_vs_boxscore,
    validate_shift_count_shifts_vs_boxscore,
    validate_shots_pbp_vs_boxscore,
    validate_toi_shifts_vs_boxscore,
)

# ============================================================================
# Test Fixtures - Mock Data Factories
# ============================================================================


def make_team(
    team_id: int = 1,
    abbrev: str = "TOR",
    name: str = "Maple Leafs",
    score: int = 3,
    shots_on_goal: int = 30,
    is_home: bool = True,
) -> TeamBoxscore:
    """Create a TeamBoxscore for testing."""
    return TeamBoxscore(
        team_id=team_id,
        abbrev=abbrev,
        name=name,
        score=score,
        shots_on_goal=shots_on_goal,
        is_home=is_home,
    )


def make_skater(
    player_id: int = 1,
    name: str = "Test Player",
    sweater_number: int = 10,
    position: str = "C",
    goals: int = 0,
    assists: int = 0,
    points: int = 0,
    plus_minus: int = 0,
    pim: int = 0,
    shots: int = 0,
    hits: int = 0,
    blocked_shots: int = 0,
    giveaways: int = 0,
    takeaways: int = 0,
    faceoff_pct: float = 0.0,
    toi: str = "15:00",
    shifts: int = 20,
    power_play_goals: int = 0,
    shorthanded_goals: int = 0,
    team_id: int = 1,
) -> SkaterStats:
    """Create a SkaterStats for testing."""
    return SkaterStats(
        player_id=player_id,
        name=name,
        sweater_number=sweater_number,
        position=position,
        goals=goals,
        assists=assists,
        points=points,
        plus_minus=plus_minus,
        pim=pim,
        shots=shots,
        hits=hits,
        blocked_shots=blocked_shots,
        giveaways=giveaways,
        takeaways=takeaways,
        faceoff_pct=faceoff_pct,
        toi=toi,
        shifts=shifts,
        power_play_goals=power_play_goals,
        shorthanded_goals=shorthanded_goals,
        team_id=team_id,
    )


def make_boxscore(
    game_id: int = 2024020500,
    home_score: int = 3,
    away_score: int = 2,
    home_shots: int = 30,
    away_shots: int = 25,
    home_skaters: list[SkaterStats] | None = None,
    away_skaters: list[SkaterStats] | None = None,
) -> ParsedBoxscore:
    """Create a ParsedBoxscore for testing."""
    return ParsedBoxscore(
        game_id=game_id,
        season_id=20242025,
        game_date="2024-12-22",
        game_type=2,
        game_state="FINAL",
        home_team=make_team(
            team_id=1, score=home_score, shots_on_goal=home_shots, is_home=True
        ),
        away_team=make_team(
            team_id=2,
            abbrev="MTL",
            name="Canadiens",
            score=away_score,
            shots_on_goal=away_shots,
            is_home=False,
        ),
        home_skaters=home_skaters or [],
        away_skaters=away_skaters or [],
        home_goalies=[],
        away_goalies=[],
    )


def make_event(
    event_id: int = 1,
    event_type: str = "goal",
    period: int = 1,
    period_type: str = "REG",
    time_in_period: str = "10:00",
    event_owner_team_id: int = 1,
    home_score: int = 1,
    away_score: int = 0,
) -> GameEvent:
    """Create a GameEvent for testing."""
    return GameEvent(
        event_id=event_id,
        event_type=event_type,
        period=period,
        period_type=period_type,
        time_in_period=time_in_period,
        time_remaining="10:00",
        sort_order=event_id,
        event_owner_team_id=event_owner_team_id,
        home_score=home_score,
        away_score=away_score,
    )


def make_pbp(
    game_id: int = 2024020500,
    home_team_id: int = 1,
    away_team_id: int = 2,
    events: list[GameEvent] | None = None,
) -> ParsedPlayByPlay:
    """Create a ParsedPlayByPlay for testing."""
    return ParsedPlayByPlay(
        game_id=game_id,
        season_id=20242025,
        game_date="2024-12-22",
        game_type=2,
        game_state="FINAL",
        home_team_id=home_team_id,
        home_team_abbrev="TOR",
        away_team_id=away_team_id,
        away_team_abbrev="MTL",
        venue_name="Scotiabank Arena",
        events=events or [],
    )


def make_shift(
    shift_id: int = 1,
    game_id: int = 2024020500,
    player_id: int = 1,
    first_name: str = "Test",
    last_name: str = "Player",
    team_id: int = 1,
    period: int = 1,
    shift_number: int = 1,
    start_time: str = "00:00",
    end_time: str = "00:45",
    duration_seconds: int = 45,
    is_goal_event: bool = False,
) -> ShiftRecord:
    """Create a ShiftRecord for testing."""
    return ShiftRecord(
        shift_id=shift_id,
        game_id=game_id,
        player_id=player_id,
        first_name=first_name,
        last_name=last_name,
        team_id=team_id,
        team_abbrev="TOR",
        period=period,
        shift_number=shift_number,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration_seconds,
        is_goal_event=is_goal_event,
    )


def make_shift_chart(
    game_id: int = 2024020500,
    shifts: list[ShiftRecord] | None = None,
) -> ParsedShiftChart:
    """Create a ParsedShiftChart for testing."""
    shift_list = shifts or []
    return ParsedShiftChart(
        game_id=game_id,
        season_id=20242025,
        total_shifts=len(shift_list),
        shifts=shift_list,
    )


# ============================================================================
# Tests for validate_goals_pbp_vs_boxscore
# ============================================================================


class TestGoalsValidation:
    """Tests for PBP goals vs Boxscore goals."""

    def test_goals_match_exactly(self) -> None:
        """PBP goal count = Boxscore score should pass."""
        # Create PBP with 3 home goals and 2 away goals
        events = [
            make_event(event_id=1, event_type="goal", event_owner_team_id=1),
            make_event(event_id=2, event_type="goal", event_owner_team_id=1),
            make_event(event_id=3, event_type="goal", event_owner_team_id=1),
            make_event(event_id=4, event_type="goal", event_owner_team_id=2),
            make_event(event_id=5, event_type="goal", event_owner_team_id=2),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(home_score=3, away_score=2)

        results = validate_goals_pbp_vs_boxscore(pbp, boxscore)

        assert len(results) == 2
        assert all(r.passed for r in results)
        assert results[0].rule_name == "cross_source_pbp_boxscore_goals_home"
        assert results[1].rule_name == "cross_source_pbp_boxscore_goals_away"

    def test_goals_mismatch_home(self) -> None:
        """PBP home goals != Boxscore home score should fail."""
        events = [
            make_event(event_id=1, event_type="goal", event_owner_team_id=1),
            make_event(event_id=2, event_type="goal", event_owner_team_id=1),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(
            home_score=3, away_score=0
        )  # Boxscore says 3, PBP says 2

        results = validate_goals_pbp_vs_boxscore(pbp, boxscore)

        home_result = next(r for r in results if "home" in r.rule_name)
        assert not home_result.passed
        assert home_result.severity == "error"
        assert home_result.details is not None
        assert home_result.details["pbp_goals"] == 2
        assert home_result.details["boxscore_goals"] == 3

    def test_goals_mismatch_away(self) -> None:
        """PBP away goals != Boxscore away score should fail."""
        events = [
            make_event(event_id=1, event_type="goal", event_owner_team_id=2),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(
            home_score=0, away_score=3
        )  # Boxscore says 3, PBP says 1

        results = validate_goals_pbp_vs_boxscore(pbp, boxscore)

        away_result = next(r for r in results if "away" in r.rule_name)
        assert not away_result.passed
        assert away_result.severity == "error"

    def test_shootout_goals_excluded(self) -> None:
        """Shootout goals should not count toward score."""
        events = [
            make_event(
                event_id=1, event_type="goal", event_owner_team_id=1, period_type="REG"
            ),
            make_event(
                event_id=2, event_type="goal", event_owner_team_id=1, period_type="REG"
            ),
            make_event(
                event_id=3, event_type="goal", event_owner_team_id=2, period_type="REG"
            ),
            # Shootout goals - should not count
            make_event(
                event_id=4,
                event_type="goal",
                event_owner_team_id=1,
                period=5,
                period_type="SO",
            ),
            make_event(
                event_id=5,
                event_type="goal",
                event_owner_team_id=2,
                period=5,
                period_type="SO",
            ),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(home_score=2, away_score=1)

        results = validate_goals_pbp_vs_boxscore(pbp, boxscore)

        assert all(r.passed for r in results)

    def test_no_goals(self) -> None:
        """Game with no goals should match 0-0 boxscore."""
        pbp = make_pbp(events=[])
        boxscore = make_boxscore(home_score=0, away_score=0)

        results = validate_goals_pbp_vs_boxscore(pbp, boxscore)

        assert all(r.passed for r in results)


# ============================================================================
# Tests for validate_shots_pbp_vs_boxscore
# ============================================================================


class TestShotsValidation:
    """Tests for PBP shots vs Boxscore shots."""

    def test_shots_match_exactly(self) -> None:
        """PBP shots = Boxscore shots should pass."""
        events = [
            make_event(event_id=1, event_type="shot-on-goal", event_owner_team_id=1),
            make_event(event_id=2, event_type="shot-on-goal", event_owner_team_id=1),
            make_event(
                event_id=3, event_type="goal", event_owner_team_id=1
            ),  # Goals count as SOG
            make_event(event_id=4, event_type="shot-on-goal", event_owner_team_id=2),
            make_event(event_id=5, event_type="shot-on-goal", event_owner_team_id=2),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(home_shots=3, away_shots=2)

        results = validate_shots_pbp_vs_boxscore(pbp, boxscore)

        assert all(r.passed for r in results)

    def test_shots_within_tolerance(self) -> None:
        """PBP shots within +/-2 of Boxscore should pass."""
        events = [
            make_event(event_id=1, event_type="shot-on-goal", event_owner_team_id=1),
            make_event(event_id=2, event_type="shot-on-goal", event_owner_team_id=1),
            make_event(event_id=3, event_type="shot-on-goal", event_owner_team_id=1),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(home_shots=5, away_shots=0)  # Off by 2

        results = validate_shots_pbp_vs_boxscore(pbp, boxscore)

        home_result = next(r for r in results if "home" in r.rule_name)
        assert home_result.passed  # Within tolerance

    def test_shots_outside_tolerance(self) -> None:
        """PBP shots more than 2 off Boxscore should fail."""
        events = [
            make_event(event_id=1, event_type="shot-on-goal", event_owner_team_id=1),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(home_shots=10, away_shots=0)  # Off by 9

        results = validate_shots_pbp_vs_boxscore(pbp, boxscore)

        home_result = next(r for r in results if "home" in r.rule_name)
        assert not home_result.passed
        assert home_result.severity == "warning"  # Not error since shots can vary

    def test_shootout_shots_excluded(self) -> None:
        """Shootout shots should not count toward SOG."""
        events = [
            make_event(
                event_id=1,
                event_type="shot-on-goal",
                event_owner_team_id=1,
                period_type="REG",
            ),
            make_event(
                event_id=2,
                event_type="shot-on-goal",
                event_owner_team_id=1,
                period=5,
                period_type="SO",
            ),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(home_shots=1, away_shots=0)

        results = validate_shots_pbp_vs_boxscore(pbp, boxscore)

        assert all(r.passed for r in results)


# ============================================================================
# Tests for validate_toi_shifts_vs_boxscore
# ============================================================================


class TestTOIValidation:
    """Tests for Shift Chart TOI vs Boxscore TOI."""

    def test_toi_matches_within_tolerance(self) -> None:
        """TOI within 5 seconds should pass."""
        # Create shifts totaling 15:00 (900 seconds)
        shifts = [
            make_shift(shift_id=1, player_id=1, duration_seconds=450),  # 7:30
            make_shift(
                shift_id=2, player_id=1, shift_number=2, duration_seconds=450
            ),  # 7:30
        ]
        shift_chart = make_shift_chart(shifts=shifts)

        # Boxscore says 15:03 (903 seconds) - within tolerance
        skater = make_skater(player_id=1, toi="15:03")
        boxscore = make_boxscore(home_skaters=[skater])

        results = validate_toi_shifts_vs_boxscore(shift_chart, boxscore)

        assert len(results) == 1
        assert results[0].passed
        assert "match" in results[0].message.lower()

    def test_toi_outside_tolerance(self) -> None:
        """TOI more than 5 seconds off should fail."""
        # Create shifts totaling 15:00 (900 seconds)
        shifts = [
            make_shift(shift_id=1, player_id=1, duration_seconds=900),
        ]
        shift_chart = make_shift_chart(shifts=shifts)

        # Boxscore says 16:00 (960 seconds) - outside tolerance by 60s
        skater = make_skater(player_id=1, toi="16:00")
        boxscore = make_boxscore(home_skaters=[skater])

        results = validate_toi_shifts_vs_boxscore(shift_chart, boxscore)

        assert len(results) == 1
        assert not results[0].passed
        assert results[0].severity == "warning"

    def test_toi_multiple_players(self) -> None:
        """Multiple players should each be validated."""
        shifts = [
            make_shift(shift_id=1, player_id=1, duration_seconds=900),
            make_shift(shift_id=2, player_id=2, duration_seconds=600),
        ]
        shift_chart = make_shift_chart(shifts=shifts)

        skater1 = make_skater(player_id=1, toi="15:00")  # Matches
        skater2 = make_skater(player_id=2, toi="10:00")  # Matches
        boxscore = make_boxscore(home_skaters=[skater1, skater2])

        results = validate_toi_shifts_vs_boxscore(shift_chart, boxscore)

        assert len(results) == 1
        assert results[0].passed

    def test_toi_excludes_goal_events(self) -> None:
        """Goal event records should not count toward TOI."""
        shifts = [
            make_shift(
                shift_id=1, player_id=1, duration_seconds=900, is_goal_event=False
            ),
            make_shift(
                shift_id=2, player_id=1, duration_seconds=100, is_goal_event=True
            ),  # Goal event
        ]
        shift_chart = make_shift_chart(shifts=shifts)

        skater = make_skater(player_id=1, toi="15:00")  # Should match 900s, not 1000s
        boxscore = make_boxscore(home_skaters=[skater])

        results = validate_toi_shifts_vs_boxscore(shift_chart, boxscore)

        assert results[0].passed


# ============================================================================
# Tests for validate_shift_count_shifts_vs_boxscore
# ============================================================================


class TestShiftCountValidation:
    """Tests for shift count matching."""

    def test_shift_count_matches(self) -> None:
        """Shift counts should match exactly."""
        shifts = [
            make_shift(shift_id=i, player_id=1, shift_number=i) for i in range(1, 21)
        ]
        shift_chart = make_shift_chart(shifts=shifts)

        skater = make_skater(player_id=1, shifts=20)
        boxscore = make_boxscore(home_skaters=[skater])

        results = validate_shift_count_shifts_vs_boxscore(shift_chart, boxscore)

        assert len(results) == 1
        assert results[0].passed

    def test_shift_count_within_tolerance(self) -> None:
        """Shift count off by 1 should pass (tolerance)."""
        shifts = [
            make_shift(shift_id=i, player_id=1, shift_number=i)
            for i in range(1, 20)  # 19 shifts
        ]
        shift_chart = make_shift_chart(shifts=shifts)

        skater = make_skater(player_id=1, shifts=20)  # Boxscore says 20
        boxscore = make_boxscore(home_skaters=[skater])

        results = validate_shift_count_shifts_vs_boxscore(shift_chart, boxscore)

        assert results[0].passed  # Off by 1, within tolerance

    def test_shift_count_mismatch(self) -> None:
        """Shift count off by more than tolerance should fail."""
        shifts = [
            make_shift(shift_id=i, player_id=1, shift_number=i)
            for i in range(1, 16)  # 15 shifts
        ]
        shift_chart = make_shift_chart(shifts=shifts)

        skater = make_skater(player_id=1, shifts=20)  # Off by 5
        boxscore = make_boxscore(home_skaters=[skater])

        results = validate_shift_count_shifts_vs_boxscore(shift_chart, boxscore)

        assert not results[0].passed
        assert results[0].severity == "warning"

    def test_shift_count_excludes_goal_events(self) -> None:
        """Goal event records should not count as shifts."""
        shifts = [
            make_shift(shift_id=i, player_id=1, shift_number=i, is_goal_event=False)
            for i in range(1, 21)
        ]
        # Add goal event records
        shifts.extend(
            [
                make_shift(shift_id=100, player_id=1, is_goal_event=True),
                make_shift(shift_id=101, player_id=1, is_goal_event=True),
            ]
        )
        shift_chart = make_shift_chart(shifts=shifts)

        skater = make_skater(player_id=1, shifts=20)  # Should be 20, not 22
        boxscore = make_boxscore(home_skaters=[skater])

        results = validate_shift_count_shifts_vs_boxscore(shift_chart, boxscore)

        assert results[0].passed


# ============================================================================
# Tests for validate_final_score_schedule_vs_boxscore
# ============================================================================


class TestFinalScoreValidation:
    """Tests for Schedule vs Boxscore score matching."""

    def test_score_matches(self) -> None:
        """Schedule and Boxscore scores should match."""
        # Create a simple schedule-like object with required attributes
        from dataclasses import dataclass

        @dataclass
        class MockGameInfo:
            home_score: int | None
            away_score: int | None

        schedule = MockGameInfo(home_score=3, away_score=2)
        boxscore = make_boxscore(home_score=3, away_score=2)

        results = validate_final_score_schedule_vs_boxscore(schedule, boxscore)

        assert len(results) == 1
        assert results[0].passed
        assert "match" in results[0].message.lower()

    def test_score_mismatch(self) -> None:
        """Schedule and Boxscore score mismatch should fail."""
        from dataclasses import dataclass

        @dataclass
        class MockGameInfo:
            home_score: int | None
            away_score: int | None

        schedule = MockGameInfo(home_score=3, away_score=2)
        boxscore = make_boxscore(home_score=4, away_score=2)  # Home score differs

        results = validate_final_score_schedule_vs_boxscore(schedule, boxscore)

        assert len(results) == 1
        assert not results[0].passed
        assert results[0].severity == "error"

    def test_schedule_scores_null(self) -> None:
        """Pre-game schedule (null scores) should pass."""
        from dataclasses import dataclass

        @dataclass
        class MockGameInfo:
            home_score: int | None
            away_score: int | None

        schedule = MockGameInfo(home_score=None, away_score=None)
        boxscore = make_boxscore(home_score=3, away_score=2)

        results = validate_final_score_schedule_vs_boxscore(schedule, boxscore)

        assert len(results) == 1
        assert results[0].passed
        assert "not available" in results[0].message.lower()


# ============================================================================
# Tests for CrossSourceValidator class
# ============================================================================


class TestCrossSourceValidator:
    """Tests for the CrossSourceValidator class."""

    def test_validate_pbp_vs_boxscore(self) -> None:
        """Test validate_pbp_vs_boxscore method."""
        events = [
            make_event(event_id=1, event_type="goal", event_owner_team_id=1),
            make_event(event_id=2, event_type="shot-on-goal", event_owner_team_id=1),
        ]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(home_score=1, home_shots=2, away_score=0, away_shots=0)

        validator = CrossSourceValidator()
        results = validator.validate_pbp_vs_boxscore(pbp, boxscore)

        assert len(results) == 4  # 2 goals + 2 shots rules
        assert all(r.passed for r in results)

    def test_validate_shifts_vs_boxscore(self) -> None:
        """Test validate_shifts_vs_boxscore method."""
        shifts = [
            make_shift(shift_id=i, player_id=1, shift_number=i, duration_seconds=45)
            for i in range(1, 21)
        ]
        shift_chart = make_shift_chart(shifts=shifts)

        skater = make_skater(player_id=1, toi="15:00", shifts=20)
        boxscore = make_boxscore(home_skaters=[skater])

        validator = CrossSourceValidator()
        results = validator.validate_shifts_vs_boxscore(shift_chart, boxscore)

        assert len(results) == 2  # TOI + shift count
        assert all(r.passed for r in results)

    def test_validate_all_with_all_sources(self) -> None:
        """Test validate_all with all sources provided."""
        events = [make_event(event_id=1, event_type="goal", event_owner_team_id=1)]
        pbp = make_pbp(events=events)

        shifts = [make_shift(shift_id=1, player_id=1, duration_seconds=900)]
        shift_chart = make_shift_chart(shifts=shifts)

        skater = make_skater(player_id=1, toi="15:00", shifts=1)
        boxscore = make_boxscore(
            home_score=1,
            home_shots=1,
            away_score=0,
            away_shots=0,
            home_skaters=[skater],
        )

        from dataclasses import dataclass

        @dataclass
        class MockGameInfo:
            home_score: int | None
            away_score: int | None

        schedule = MockGameInfo(home_score=1, away_score=0)

        validator = CrossSourceValidator()
        results = validator.validate_all(
            pbp=pbp,
            boxscore=boxscore,
            shifts=shift_chart,
            schedule=schedule,
        )

        # Should have results from all validator pairs
        assert len(results) >= 5  # At least goals, shots, TOI, shifts, score

    def test_validate_all_with_no_boxscore(self) -> None:
        """Test validate_all returns empty when boxscore is missing."""
        validator = CrossSourceValidator()
        results = validator.validate_all(pbp=make_pbp(), boxscore=None)

        assert results == []

    def test_validate_all_with_partial_sources(self) -> None:
        """Test validate_all with only some sources provided."""
        boxscore = make_boxscore()

        validator = CrossSourceValidator()
        results = validator.validate_all(boxscore=boxscore)

        # No other sources, so no validations
        assert results == []

    def test_get_summary(self) -> None:
        """Test get_summary method."""
        events = [make_event(event_id=1, event_type="goal", event_owner_team_id=1)]
        pbp = make_pbp(events=events)
        boxscore = make_boxscore(home_score=1, home_shots=1, away_score=0, away_shots=0)

        validator = CrossSourceValidator()
        results = validator.validate_pbp_vs_boxscore(pbp, boxscore)
        summary = validator.get_summary(2024020500, results)

        assert summary.source_type == "cross_source"
        assert summary.entity_id == "2024020500"
        assert summary.total_checks == len(results)
