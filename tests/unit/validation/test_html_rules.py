"""Tests for HTML report internal consistency validation rules."""
# mypy: disable-error-code="arg-type,type-arg"

from __future__ import annotations

from nhl_api.validation.rules.html_reports import (
    validate_event_summary,
    validate_faceoff_summary,
    validate_game_summary,
    validate_shot_summary,
    validate_time_on_ice,
)

# ============================================================================
# Event Summary (ES) Tests
# ============================================================================


class MockPlayerStats:
    """Mock player stats for ES testing."""

    def __init__(
        self,
        number: int = 11,
        position: str = "C",
        name: str = "Test Player",
        goals: int = 1,
        assists: int = 2,
        points: int = 3,
        plus_minus: int = 1,
        pim: int = 0,
        shots: int = 5,
    ):
        self.number = number
        self.position = position
        self.name = name
        self.goals = goals
        self.assists = assists
        self.points = points
        self.plus_minus = plus_minus
        self.pim = pim
        self.shots = shots


class MockTeamEventSummary:
    """Mock team event summary for ES testing."""

    def __init__(
        self,
        team_name: str = "Boston",
        team_abbrev: str = "BOS",
        players: list | None = None,
        totals: dict | None = None,
    ):
        self.team_name = team_name
        self.team_abbrev = team_abbrev
        self.players = players or []
        # totals is a dict with .get() method
        self.totals = totals or {"goals": 0, "assists": 0, "points": 0, "shots": 0}


class MockParsedEventSummary:
    """Mock parsed event summary for testing."""

    def __init__(
        self,
        home_team: MockTeamEventSummary | None = None,
        away_team: MockTeamEventSummary | None = None,
        game_id: int = 2024020500,
    ):
        self.home_team = home_team or MockTeamEventSummary()
        self.away_team = away_team or MockTeamEventSummary(
            team_name="Toronto", team_abbrev="TOR"
        )
        self.game_id = game_id


class TestEventSummaryPlayerSumsValidation:
    """Tests for ES player stats sum to team totals validation."""

    def test_goals_match(self):
        """Player goals summing to team total should pass."""
        players = [
            MockPlayerStats(goals=2, assists=1, points=3, shots=10),
            MockPlayerStats(goals=1, assists=2, points=3, shots=8),
        ]
        home = MockTeamEventSummary(
            players=players,
            totals={"goals": 3, "assists": 3, "points": 6, "shots": 18},
        )
        away = MockTeamEventSummary(
            team_name="Toronto",
            team_abbrev="TOR",
            players=[],
            totals={"goals": 0, "assists": 0, "points": 0, "shots": 0},
        )
        es = MockParsedEventSummary(home_team=home, away_team=away)
        results = validate_event_summary(es)
        goals_results = [r for r in results if r.rule_name == "es_player_sum_goals"]
        # Both home and away should have goal validation
        assert len(goals_results) == 2
        # Home should pass (sums match)
        home_result = [r for r in goals_results if "home" in r.message][0]
        assert home_result.passed is True

    def test_goals_mismatch(self):
        """Player goals not matching team total should fail."""
        players = [
            MockPlayerStats(goals=2, assists=1, points=3, shots=10),
            MockPlayerStats(goals=1, assists=2, points=3, shots=8),
        ]
        home = MockTeamEventSummary(
            players=players,
            totals={
                "goals": 5,
                "assists": 3,
                "points": 6,
                "shots": 18,
            },  # goals should be 3
        )
        away = MockTeamEventSummary(
            team_name="Toronto",
            team_abbrev="TOR",
            players=[],
            totals={"goals": 0, "assists": 0, "points": 0, "shots": 0},
        )
        es = MockParsedEventSummary(home_team=home, away_team=away)
        results = validate_event_summary(es)
        goals_results = [r for r in results if r.rule_name == "es_player_sum_goals"]
        home_result = [r for r in goals_results if "home" in r.message][0]
        assert home_result.passed is False
        assert home_result.severity == "error"

    def test_empty_players(self):
        """Empty player list with zero totals should pass."""
        home = MockTeamEventSummary(
            players=[],
            totals={"goals": 0, "assists": 0, "points": 0, "shots": 0},
        )
        away = MockTeamEventSummary(
            team_name="Toronto",
            team_abbrev="TOR",
            players=[],
            totals={"goals": 0, "assists": 0, "points": 0, "shots": 0},
        )
        es = MockParsedEventSummary(home_team=home, away_team=away)
        results = validate_event_summary(es)
        failed = [r for r in results if not r.passed]
        # Empty players with zero totals should pass
        assert len(failed) == 0

    def test_player_points_mismatch(self):
        """Player with points != goals + assists should fail."""
        players = [
            MockPlayerStats(goals=1, assists=1, points=5),  # points should be 2
        ]
        home = MockTeamEventSummary(
            players=players,
            totals={"goals": 1, "assists": 1, "points": 5, "shots": 10},
        )
        away = MockTeamEventSummary(
            team_name="Toronto",
            team_abbrev="TOR",
            players=[],
            totals={"goals": 0, "assists": 0, "points": 0, "shots": 0},
        )
        es = MockParsedEventSummary(home_team=home, away_team=away)
        results = validate_event_summary(es)
        points_results = [r for r in results if r.rule_name == "es_player_points"]
        assert len(points_results) == 1
        assert points_results[0].passed is False


# ============================================================================
# Game Summary (GS) Tests
# ============================================================================


class MockTeamInfo:
    """Mock team info for GS testing."""

    def __init__(self, name: str = "Boston", goals: int = 3):
        self.name = name
        self.goals = goals


class MockGoalInfo:
    """Mock goal info for GS testing."""

    def __init__(
        self,
        goal_number: int = 1,
        team: str = "Boston",
        period: int = 1,
        time: str = "10:30",
        scorer: str = "Player One",
        assist1: str | None = "Player Two",
        assist2: str | None = "Player Three",
    ):
        self.goal_number = goal_number
        self.team = team
        self.period = period
        self.time = time
        self.scorer = scorer
        self.assist1 = assist1
        self.assist2 = assist2


class MockParsedGameSummary:
    """Mock parsed game summary for testing."""

    def __init__(
        self,
        home_team: MockTeamInfo | None = None,
        away_team: MockTeamInfo | None = None,
        goals: list | None = None,
        game_id: int = 2024020500,
    ):
        self.home_team = home_team or MockTeamInfo()
        self.away_team = away_team or MockTeamInfo(name="Toronto", goals=2)
        self.goals = goals or []
        self.game_id = game_id


class TestGameSummaryGoalsCountValidation:
    """Tests for GS goals in list matching team total validation."""

    def test_goals_count_matches(self):
        """Goals in list matching team total should pass."""
        goals = [
            MockGoalInfo(goal_number=1, team="Boston"),
            MockGoalInfo(goal_number=2, team="Boston"),
            MockGoalInfo(goal_number=3, team="Boston"),
            MockGoalInfo(goal_number=4, team="Toronto"),
            MockGoalInfo(goal_number=5, team="Toronto"),
        ]
        home = MockTeamInfo(name="Boston", goals=3)
        away = MockTeamInfo(name="Toronto", goals=2)
        gs = MockParsedGameSummary(home_team=home, away_team=away, goals=goals)
        results = validate_game_summary(gs)
        count_results = [r for r in results if "gs_goals_count" in r.rule_name]
        assert len(count_results) == 2
        assert all(r.passed for r in count_results)

    def test_goals_count_mismatch(self):
        """Goals in list not matching team total should fail."""
        goals = [
            MockGoalInfo(goal_number=1, team="Boston"),
            MockGoalInfo(goal_number=2, team="Boston"),
        ]
        home = MockTeamInfo(name="Boston", goals=5)  # Should be 2
        away = MockTeamInfo(name="Toronto", goals=0)
        gs = MockParsedGameSummary(home_team=home, away_team=away, goals=goals)
        results = validate_game_summary(gs)
        count_results = [r for r in results if "gs_goals_count_home" in r.rule_name]
        assert len(count_results) == 1
        assert count_results[0].passed is False

    def test_goal_with_two_assists(self):
        """Goal with 2 assists should pass."""
        goals = [
            MockGoalInfo(
                goal_number=1,
                team="Boston",
                assist1="Player Two",
                assist2="Player Three",
            )
        ]
        home = MockTeamInfo(name="Boston", goals=1)
        away = MockTeamInfo(name="Toronto", goals=0)
        gs = MockParsedGameSummary(home_team=home, away_team=away, goals=goals)
        results = validate_game_summary(gs)
        assist_results = [r for r in results if r.rule_name == "gs_goal_assists"]
        assert len(assist_results) == 1
        assert assist_results[0].passed is True

    def test_unassisted_goal(self):
        """Unassisted goal should pass."""
        goals = [MockGoalInfo(goal_number=1, team="Boston", assist1=None, assist2=None)]
        home = MockTeamInfo(name="Boston", goals=1)
        away = MockTeamInfo(name="Toronto", goals=0)
        gs = MockParsedGameSummary(home_team=home, away_team=away, goals=goals)
        results = validate_game_summary(gs)
        assist_results = [r for r in results if r.rule_name == "gs_goal_assists"]
        assert len(assist_results) == 1
        assert assist_results[0].passed is True


# ============================================================================
# Faceoff Summary (FS) Tests
# ============================================================================


class MockFaceoffStat:
    """Mock faceoff stat for FS testing."""

    def __init__(self, won: int = 5, lost: int = 3, total: int = 8, pct: float = 62.5):
        self.won = won
        self.lost = lost
        self.total = total
        self.pct = pct


class MockZoneFaceoffs:
    """Mock zone faceoffs (offensive/defensive/neutral) for FS testing."""

    def __init__(
        self,
        offensive: MockFaceoffStat | None = None,
        defensive: MockFaceoffStat | None = None,
        neutral: MockFaceoffStat | None = None,
        total: MockFaceoffStat | None = None,
    ):
        self.offensive = offensive or MockFaceoffStat()
        self.defensive = defensive or MockFaceoffStat()
        self.neutral = neutral or MockFaceoffStat()
        self.total = total or MockFaceoffStat()


class MockPlayerFaceoffStats:
    """Mock player faceoff stats for FS testing."""

    def __init__(
        self,
        number: int = 11,
        name: str = "Test Player",
        totals: MockZoneFaceoffs | None = None,
    ):
        self.number = number
        self.name = name
        self.totals = totals or MockZoneFaceoffs()


class MockTeamFaceoffSummary:
    """Mock team faceoff summary for FS testing."""

    def __init__(
        self,
        team_abbrev: str = "BOS",
        players: list | None = None,
    ):
        self.team_abbrev = team_abbrev
        self.players = players or []


class MockParsedFaceoffSummary:
    """Mock parsed faceoff summary for testing."""

    def __init__(
        self,
        home_team: MockTeamFaceoffSummary | None = None,
        away_team: MockTeamFaceoffSummary | None = None,
        game_id: int = 2024020500,
    ):
        self.home_team = home_team or MockTeamFaceoffSummary()
        self.away_team = away_team or MockTeamFaceoffSummary(team_abbrev="TOR")
        self.game_id = game_id


class TestFaceoffSummaryMathValidation:
    """Tests for FS wins + losses = total validation."""

    def test_faceoff_math_valid(self):
        """Wins + losses = total should pass."""
        # Create valid stats for each zone
        valid_stat = MockFaceoffStat(won=5, lost=3, total=8)
        zone_totals = MockZoneFaceoffs(
            offensive=valid_stat,
            defensive=valid_stat,
            neutral=valid_stat,
        )
        player = MockPlayerFaceoffStats(totals=zone_totals)
        home = MockTeamFaceoffSummary(players=[player])
        away = MockTeamFaceoffSummary(team_abbrev="TOR", players=[])
        fs = MockParsedFaceoffSummary(home_team=home, away_team=away)
        results = validate_faceoff_summary(fs)
        math_results = [r for r in results if r.rule_name == "fs_faceoff_math"]
        # 3 zones checked per player
        assert len(math_results) == 3
        assert all(r.passed for r in math_results)

    def test_faceoff_math_invalid(self):
        """Wins + losses != total should fail."""
        # Create invalid stat for offensive zone
        invalid_stat = MockFaceoffStat(won=5, lost=3, total=10)  # Should be 8
        valid_stat = MockFaceoffStat(won=5, lost=3, total=8)
        zone_totals = MockZoneFaceoffs(
            offensive=invalid_stat,
            defensive=valid_stat,
            neutral=valid_stat,
        )
        player = MockPlayerFaceoffStats(totals=zone_totals)
        home = MockTeamFaceoffSummary(players=[player])
        away = MockTeamFaceoffSummary(team_abbrev="TOR", players=[])
        fs = MockParsedFaceoffSummary(home_team=home, away_team=away)
        results = validate_faceoff_summary(fs)
        math_results = [r for r in results if r.rule_name == "fs_faceoff_math"]
        failed = [r for r in math_results if not r.passed]
        assert len(failed) == 1
        assert failed[0].severity == "error"

    def test_empty_players(self):
        """Empty player list should pass (no validations)."""
        home = MockTeamFaceoffSummary(players=[])
        away = MockTeamFaceoffSummary(team_abbrev="TOR", players=[])
        fs = MockParsedFaceoffSummary(home_team=home, away_team=away)
        results = validate_faceoff_summary(fs)
        # Empty players = no faceoff math validations
        assert len(results) == 0


# ============================================================================
# Shot Summary (SS) Tests
# ============================================================================


class MockShotStat:
    """Mock shot stat for SS testing."""

    def __init__(
        self, shots: int = 10, goals: int = 2, missed: int = 5, blocked: int = 3
    ):
        self.shots = shots
        self.goals = goals
        self.missed = missed
        self.blocked = blocked


class MockPlayerPeriodShots:
    """Mock player period shots for SS testing."""

    def __init__(self, period: str = "1", total: MockShotStat | None = None):
        self.period = period
        self.total = total or MockShotStat()


class MockPlayerShotStats:
    """Mock player shot stats for SS testing."""

    def __init__(
        self,
        number: int = 11,
        name: str = "Test Player",
        total_shots: int = 10,
        periods: list | None = None,
    ):
        self.number = number
        self.name = name
        self.total_shots = total_shots
        self.periods = periods or []


class MockPeriodShots:
    """Mock period shots for SS testing."""

    def __init__(self, period: str = "TOT", total: MockShotStat | None = None):
        self.period = period
        self.total = total or MockShotStat()


class MockTeamShotSummary:
    """Mock team shot summary for SS testing."""

    def __init__(
        self,
        team_abbrev: str = "BOS",
        players: list | None = None,
        periods: list | None = None,
    ):
        self.team_abbrev = team_abbrev
        self.players = players or []
        self.periods = periods or []


class MockParsedShotSummary:
    """Mock parsed shot summary for testing."""

    def __init__(
        self,
        home_team: MockTeamShotSummary | None = None,
        away_team: MockTeamShotSummary | None = None,
        game_id: int = 2024020500,
    ):
        self.home_team = home_team or MockTeamShotSummary()
        self.away_team = away_team or MockTeamShotSummary(team_abbrev="TOR")
        self.game_id = game_id


class TestShotSummaryValidation:
    """Tests for SS validation."""

    def test_player_shots_match_team(self):
        """Player shots summing to team total should pass."""
        players = [
            MockPlayerShotStats(total_shots=15, periods=[]),
            MockPlayerShotStats(total_shots=15, periods=[]),
        ]
        periods = [MockPeriodShots(period="TOT", total=MockShotStat(shots=30))]
        home = MockTeamShotSummary(players=players, periods=periods)
        away = MockTeamShotSummary(team_abbrev="TOR", players=[], periods=[])
        ss = MockParsedShotSummary(home_team=home, away_team=away)
        results = validate_shot_summary(ss)
        sum_results = [r for r in results if r.rule_name == "ss_player_sum_shots"]
        home_result = [r for r in sum_results if "home" in r.message][0]
        assert home_result.passed is True

    def test_player_shots_mismatch_team(self):
        """Player shots not summing to team total should fail."""
        players = [MockPlayerShotStats(total_shots=10, periods=[])]
        periods = [
            MockPeriodShots(period="TOT", total=MockShotStat(shots=30))
        ]  # Mismatch
        home = MockTeamShotSummary(players=players, periods=periods)
        away = MockTeamShotSummary(team_abbrev="TOR", players=[], periods=[])
        ss = MockParsedShotSummary(home_team=home, away_team=away)
        results = validate_shot_summary(ss)
        sum_results = [r for r in results if r.rule_name == "ss_player_sum_shots"]
        home_result = [r for r in sum_results if "home" in r.message][0]
        assert home_result.passed is False

    def test_player_period_sum_matches(self):
        """Player period shots summing to total should pass."""
        player_periods = [
            MockPlayerPeriodShots(period="1", total=MockShotStat(shots=5)),
            MockPlayerPeriodShots(period="2", total=MockShotStat(shots=3)),
            MockPlayerPeriodShots(period="3", total=MockShotStat(shots=2)),
        ]
        players = [MockPlayerShotStats(total_shots=10, periods=player_periods)]
        home = MockTeamShotSummary(players=players, periods=[])
        away = MockTeamShotSummary(team_abbrev="TOR", players=[], periods=[])
        ss = MockParsedShotSummary(home_team=home, away_team=away)
        results = validate_shot_summary(ss)
        period_results = [r for r in results if r.rule_name == "ss_player_period_sum"]
        assert len(period_results) == 1
        assert period_results[0].passed is True


# ============================================================================
# Time on Ice (TH/TV) Tests
# ============================================================================


class MockShiftInfo:
    """Mock shift info for TH/TV testing."""

    def __init__(
        self,
        shift_number: int = 1,
        period: int = 1,
        duration: str = "1:00",
    ):
        self.shift_number = shift_number
        self.period = period
        self.duration = duration


class MockPlayerTOI:
    """Mock player TOI for TH/TV testing."""

    def __init__(
        self,
        number: int = 11,
        name: str = "Test Player",
        shifts_detail: list | None = None,
        total_toi: str | None = None,  # MM:SS format, None means no total
    ):
        self.number = number
        self.name = name
        self.shifts_detail = shifts_detail or []
        self._total_toi = total_toi

    @property
    def total_toi(self) -> str | None:
        """Return total TOI as string or None."""
        return self._total_toi


class MockParsedTimeOnIce:
    """Mock parsed time on ice for testing."""

    def __init__(
        self,
        team_abbrev: str = "BOS",
        players: list | None = None,
        game_id: int = 2024020500,
    ):
        self.team_abbrev = team_abbrev
        self.players = players or []
        self.game_id = game_id


class TestTimeOnIceShiftDurationSumValidation:
    """Tests for TH/TV shift durations sum to period TOI validation."""

    def test_shift_durations_match_total(self):
        """Shift durations summing to total TOI should pass."""
        shifts = [
            MockShiftInfo(shift_number=1, duration="1:00"),  # 60s
            MockShiftInfo(shift_number=2, duration="1:00"),  # 60s
            MockShiftInfo(shift_number=3, duration="1:00"),  # 60s
        ]
        player = MockPlayerTOI(shifts_detail=shifts, total_toi="3:00")  # 180s
        toi = MockParsedTimeOnIce(players=[player])
        results = validate_time_on_ice(toi)
        toi_results = [r for r in results if r.rule_name == "toi_shift_duration_sum"]
        assert len(toi_results) == 1
        assert toi_results[0].passed is True

    def test_shift_durations_mismatch_total(self):
        """Shift durations not summing to total TOI should fail."""
        shifts = [
            MockShiftInfo(shift_number=1, duration="1:00"),  # 60s
            MockShiftInfo(shift_number=2, duration="1:00"),  # 60s
        ]
        player = MockPlayerTOI(
            shifts_detail=shifts, total_toi="5:00"
        )  # 300s (mismatch)
        toi = MockParsedTimeOnIce(players=[player])
        results = validate_time_on_ice(toi)
        toi_results = [r for r in results if r.rule_name == "toi_shift_duration_sum"]
        assert len(toi_results) == 1
        assert toi_results[0].passed is False
        assert toi_results[0].severity == "warning"

    def test_empty_players(self):
        """Empty player list should pass."""
        toi = MockParsedTimeOnIce(players=[])
        results = validate_time_on_ice(toi)
        # Empty data should not produce failures
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_no_total_toi(self):
        """Player without total_toi should pass (nothing to validate against)."""
        shifts = [MockShiftInfo(shift_number=1, duration="1:00")]
        player = MockPlayerTOI(shifts_detail=shifts, total_toi=None)
        toi = MockParsedTimeOnIce(players=[player])
        results = validate_time_on_ice(toi)
        toi_results = [r for r in results if r.rule_name == "toi_shift_duration_sum"]
        # With total_toi=None, produces a pass result indicating nothing to validate
        assert len(toi_results) == 1
        assert toi_results[0].passed is True


# ============================================================================
# Integration Tests
# ============================================================================


class TestHTMLReportIntegration:
    """Integration tests for HTML report validation."""

    def test_all_validators_return_results(self):
        """All validators should return list of results."""
        # Create properly structured mocks
        es = MockParsedEventSummary(
            home_team=MockTeamEventSummary(
                players=[], totals={"goals": 0, "assists": 0, "points": 0, "shots": 0}
            ),
            away_team=MockTeamEventSummary(
                team_name="Toronto",
                team_abbrev="TOR",
                players=[],
                totals={"goals": 0, "assists": 0, "points": 0, "shots": 0},
            ),
        )
        gs = MockParsedGameSummary(
            home_team=MockTeamInfo(name="Boston", goals=0),
            away_team=MockTeamInfo(name="Toronto", goals=0),
            goals=[],
        )
        fs = MockParsedFaceoffSummary(
            home_team=MockTeamFaceoffSummary(players=[]),
            away_team=MockTeamFaceoffSummary(team_abbrev="TOR", players=[]),
        )
        ss = MockParsedShotSummary(
            home_team=MockTeamShotSummary(players=[], periods=[]),
            away_team=MockTeamShotSummary(team_abbrev="TOR", players=[], periods=[]),
        )
        toi = MockParsedTimeOnIce(players=[])

        es_results = validate_event_summary(es)
        gs_results = validate_game_summary(gs)
        fs_results = validate_faceoff_summary(fs)
        ss_results = validate_shot_summary(ss)
        toi_results = validate_time_on_ice(toi)

        # All should return lists (possibly empty)
        assert isinstance(es_results, list)
        assert isinstance(gs_results, list)
        assert isinstance(fs_results, list)
        assert isinstance(ss_results, list)
        assert isinstance(toi_results, list)

    def test_results_have_required_fields(self):
        """All results should have required fields."""
        players = [MockPlayerStats(goals=1, assists=1, points=2)]
        es = MockParsedEventSummary(
            home_team=MockTeamEventSummary(
                players=players,
                totals={"goals": 1, "assists": 1, "points": 2, "shots": 5},
            ),
            away_team=MockTeamEventSummary(
                team_name="Toronto",
                team_abbrev="TOR",
                players=[],
                totals={"goals": 0, "assists": 0, "points": 0, "shots": 0},
            ),
        )
        results = validate_event_summary(es)

        for result in results:
            assert hasattr(result, "rule_name")
            assert hasattr(result, "passed")
            assert hasattr(result, "severity")
            assert hasattr(result, "message")
            assert hasattr(result, "source_type")
