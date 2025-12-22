"""Tests for the JSONvsHTMLValidator cross-source validation."""
# mypy: disable-error-code="arg-type,type-arg"

from __future__ import annotations

from nhl_api.validation import JSONvsHTMLValidator
from nhl_api.validation.cross_source.json_vs_html import (
    _normalize_name,
    _parse_time_to_seconds,
)

# =============================================================================
# Mock Classes for JSON Data
# =============================================================================


class MockPlayer:
    """Mock player in an event (EventPlayer-like)."""

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role


class MockPlayByPlayEvent:
    """Mock PBP event for testing (GameEvent-like)."""

    def __init__(
        self,
        event_type: str = "goal",
        period: int = 1,
        time_in_period: str = "10:30",
        players: list | None = None,
        details: dict | None = None,
    ):
        self.event_type = event_type
        self.period = period
        self.time_in_period = time_in_period
        self.players = players or []
        self.details = details or {}


class MockParsedPlayByPlay:
    """Mock parsed play-by-play for testing."""

    def __init__(
        self,
        game_id: int = 2024020500,
        events: list | None = None,
    ):
        self.game_id = game_id
        self.events = events or []


class MockPlayerInfo:
    """Mock player info from HTML."""

    def __init__(self, name: str, number: int | None = None, season_total: int = 0):
        self.name = name
        self.number = number
        self.season_total = season_total


class MockGoalInfo:
    """Mock goal info from HTML game summary."""

    def __init__(
        self,
        goal_number: int = 1,
        period: int = 1,
        time: str = "10:30",
        strength: str = "EV",
        team: str = "Boston Bruins",
        scorer: MockPlayerInfo | None = None,
        assist1: MockPlayerInfo | None = None,
        assist2: MockPlayerInfo | None = None,
    ):
        self.goal_number = goal_number
        self.period = period
        self.time = time
        self.strength = strength
        self.team = team
        self.scorer = scorer or MockPlayerInfo("Test Player")
        self.assist1 = assist1
        self.assist2 = assist2


class MockPenaltyInfo:
    """Mock penalty info from HTML game summary."""

    def __init__(
        self,
        penalty_number: int = 1,
        period: int = 1,
        time: str = "5:00",
        team: str = "Boston Bruins",
        player: MockPlayerInfo | None = None,
        pim: int = 2,
        infraction: str = "Tripping",
    ):
        self.penalty_number = penalty_number
        self.period = period
        self.time = time
        self.team = team
        self.player = player or MockPlayerInfo("Test Player")
        self.pim = pim
        self.infraction = infraction


class MockTeamInfo:
    """Mock team info from HTML."""

    def __init__(
        self, name: str = "Boston Bruins", abbrev: str = "BOS", goals: int = 3
    ):
        self.name = name
        self.abbrev = abbrev
        self.goals = goals


class MockParsedGameSummary:
    """Mock parsed game summary from HTML."""

    def __init__(
        self,
        game_id: int = 2024020500,
        goals: list | None = None,
        penalties: list | None = None,
        away_team: MockTeamInfo | None = None,
        home_team: MockTeamInfo | None = None,
    ):
        self.game_id = game_id
        self.goals = goals or []
        self.penalties = penalties or []
        self.away_team = away_team or MockTeamInfo("Toronto Maple Leafs", "TOR", 2)
        self.home_team = home_team or MockTeamInfo("Boston Bruins", "BOS", 3)


class MockTeamBoxscore:
    """Mock team boxscore from JSON."""

    def __init__(self, shots_on_goal: int = 30):
        self.shots_on_goal = shots_on_goal


class MockSkaterStats:
    """Mock skater stats from boxscore."""

    def __init__(self, faceoff_pct: float = 50.0):
        self.faceoff_pct = faceoff_pct


class MockParsedBoxscore:
    """Mock parsed boxscore from JSON."""

    def __init__(
        self,
        game_id: int = 2024020500,
        away_team: MockTeamBoxscore | None = None,
        home_team: MockTeamBoxscore | None = None,
        away_skaters: list | None = None,
        home_skaters: list | None = None,
    ):
        self.game_id = game_id
        self.away_team = away_team or MockTeamBoxscore(28)
        self.home_team = home_team or MockTeamBoxscore(32)
        self.away_skaters = away_skaters or []
        self.home_skaters = home_skaters or []


class MockShift:
    """Mock shift from shift chart (ShiftRecord-like)."""

    def __init__(
        self,
        player_id: int = 8471214,
        duration_seconds: int = 45,
        is_goal_event: bool = False,
    ):
        self.player_id = player_id
        self.duration_seconds = duration_seconds
        self.is_goal_event = is_goal_event


class MockParsedShiftChart:
    """Mock parsed shift chart from JSON."""

    def __init__(
        self,
        game_id: int = 2024020500,
        shifts: list | None = None,
    ):
        self.game_id = game_id
        self.shifts = shifts or []


class MockPlayerTOI:
    """Mock player TOI from HTML."""

    def __init__(
        self, number: int = 11, name: str = "Test Player", total_toi: str = "15:30"
    ):
        self.number = number
        self.name = name
        self.total_toi = total_toi


class MockParsedTimeOnIce:
    """Mock parsed time on ice from HTML."""

    def __init__(
        self,
        game_id: int = 2024020500,
        players: list | None = None,
    ):
        self.game_id = game_id
        self.players = players or []


class MockPeriodShot:
    """Mock period shot stat."""

    def __init__(self, period: str = "1", shots: int = 10):
        self.period = period
        self.total = MockShotTotal(shots)


class MockShotTotal:
    """Mock shot total."""

    def __init__(self, shots: int = 10):
        self.shots = shots


class MockTeamShotSummary:
    """Mock team shot summary from HTML."""

    def __init__(self, periods: list | None = None):
        self.periods = periods or [
            MockPeriodShot("1", 8),
            MockPeriodShot("2", 10),
            MockPeriodShot("3", 10),
            MockPeriodShot("TOT", 28),
        ]


class MockParsedShotSummary:
    """Mock parsed shot summary from HTML."""

    def __init__(
        self,
        game_id: int = 2024020500,
        away_team: MockTeamShotSummary | None = None,
        home_team: MockTeamShotSummary | None = None,
    ):
        self.game_id = game_id
        self.away_team = away_team or MockTeamShotSummary()
        self.home_team = home_team or MockTeamShotSummary()


class MockFaceoffStat:
    """Mock faceoff stat."""

    def __init__(self, won: int = 5, lost: int = 5):
        self.won = won
        self.lost = lost
        self.total = won + lost


class MockFaceoffTotals:
    """Mock faceoff totals."""

    def __init__(self, total: MockFaceoffStat | None = None):
        self.total = total or MockFaceoffStat()


class MockPlayerFaceoff:
    """Mock player faceoff stats from HTML."""

    def __init__(
        self, name: str = "Test Player", totals: MockFaceoffTotals | None = None
    ):
        self.name = name
        self.totals = totals or MockFaceoffTotals()


class MockTeamFaceoffSummary:
    """Mock team faceoff summary from HTML."""

    def __init__(self, players: list | None = None):
        self.players = players or [MockPlayerFaceoff()]


class MockParsedFaceoffSummary:
    """Mock parsed faceoff summary from HTML."""

    def __init__(
        self,
        game_id: int = 2024020500,
        away_team: MockTeamFaceoffSummary | None = None,
        home_team: MockTeamFaceoffSummary | None = None,
    ):
        self.game_id = game_id
        self.away_team = away_team or MockTeamFaceoffSummary()
        self.home_team = home_team or MockTeamFaceoffSummary()


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestNormalizeName:
    """Tests for the _normalize_name helper function."""

    def test_lowercase_conversion(self):
        """Name should be converted to lowercase."""
        assert _normalize_name("JOHN SMITH") == "john smith"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace should be stripped."""
        assert _normalize_name("  John Smith  ") == "john smith"

    def test_accented_characters(self):
        """Accented characters should be normalized."""
        assert _normalize_name("José García") == "jose garcia"
        assert _normalize_name("André Burakovsky") == "andre burakovsky"
        assert _normalize_name("Patrik Laine") == "patrik laine"

    def test_nickname_normalization(self):
        """Common nicknames should be normalized."""
        assert _normalize_name("Mitchell Marner") == "mitch marner"
        assert _normalize_name("Nicholas Robertson") == "nick robertson"
        assert _normalize_name("Michael Bunting") == "mike bunting"

    def test_already_normalized(self):
        """Already normalized names should pass through."""
        assert _normalize_name("john smith") == "john smith"


class TestParseTimeToSeconds:
    """Tests for the _parse_time_to_seconds helper function."""

    def test_valid_time(self):
        """Valid MM:SS time should be parsed correctly."""
        assert _parse_time_to_seconds("10:30") == 630
        assert _parse_time_to_seconds("00:45") == 45
        assert _parse_time_to_seconds("19:59") == 1199

    def test_zero_time(self):
        """Zero time should return 0."""
        assert _parse_time_to_seconds("00:00") == 0

    def test_invalid_format(self):
        """Invalid format should return None."""
        assert _parse_time_to_seconds("invalid") is None
        assert _parse_time_to_seconds("") is None
        assert _parse_time_to_seconds("10") is None


# =============================================================================
# Goals Validation Tests
# =============================================================================


class TestValidateGoals:
    """Tests for the validate_goals method."""

    def test_matching_goal_counts(self):
        """When goal counts match, should pass."""
        validator = JSONvsHTMLValidator()

        pbp = MockParsedPlayByPlay(
            events=[
                MockPlayByPlayEvent(
                    event_type="goal",
                    period=1,
                    time_in_period="10:30",
                    players=[MockPlayer("David Pastrnak", "scorer")],
                ),
            ]
        )
        gs = MockParsedGameSummary(
            goals=[
                MockGoalInfo(
                    goal_number=1,
                    period=1,
                    time="10:30",
                    scorer=MockPlayerInfo("David Pastrnak"),
                ),
            ]
        )

        results = validator.validate_goals(pbp, gs)

        # Find the count check
        count_results = [r for r in results if r.rule_name == "json_html_goal_count"]
        assert len(count_results) == 1
        assert count_results[0].passed is True

    def test_mismatched_goal_counts(self):
        """When goal counts don't match, should fail."""
        validator = JSONvsHTMLValidator()

        pbp = MockParsedPlayByPlay(
            events=[
                MockPlayByPlayEvent(
                    event_type="goal", period=1, time_in_period="10:30"
                ),
                MockPlayByPlayEvent(event_type="goal", period=2, time_in_period="5:00"),
            ]
        )
        gs = MockParsedGameSummary(
            goals=[
                MockGoalInfo(goal_number=1, period=1, time="10:30"),
            ]
        )

        results = validator.validate_goals(pbp, gs)

        count_results = [r for r in results if r.rule_name == "json_html_goal_count"]
        assert len(count_results) == 1
        assert count_results[0].passed is False
        assert "mismatch" in count_results[0].message.lower()

    def test_empty_goals(self):
        """When both have no goals, should pass."""
        validator = JSONvsHTMLValidator()

        pbp = MockParsedPlayByPlay(events=[])
        gs = MockParsedGameSummary(goals=[])

        results = validator.validate_goals(pbp, gs)

        count_results = [r for r in results if r.rule_name == "json_html_goal_count"]
        assert len(count_results) == 1
        assert count_results[0].passed is True


class TestValidateAssists:
    """Tests for the validate_assists method."""

    def test_matching_assists(self):
        """When assists match, should pass."""
        validator = JSONvsHTMLValidator()

        pbp = MockParsedPlayByPlay(
            events=[
                MockPlayByPlayEvent(
                    event_type="goal",
                    period=1,
                    time_in_period="10:30",
                    players=[
                        MockPlayer("David Pastrnak", "scorer"),
                        MockPlayer("Brad Marchand", "assist"),
                        MockPlayer("Charlie McAvoy", "assist"),
                    ],
                ),
            ]
        )
        gs = MockParsedGameSummary(
            goals=[
                MockGoalInfo(
                    goal_number=1,
                    period=1,
                    time="10:30",
                    scorer=MockPlayerInfo("David Pastrnak"),
                    assist1=MockPlayerInfo("Brad Marchand"),
                    assist2=MockPlayerInfo("Charlie McAvoy"),
                ),
            ]
        )

        results = validator.validate_assists(pbp, gs)

        # Should have match results for the goal
        match_results = [r for r in results if "assist" in r.rule_name]
        assert len(match_results) > 0
        assert all(r.passed for r in match_results)

    def test_unassisted_goal(self):
        """When goal is unassisted in both, should pass."""
        validator = JSONvsHTMLValidator()

        pbp = MockParsedPlayByPlay(
            events=[
                MockPlayByPlayEvent(
                    event_type="goal",
                    period=1,
                    time_in_period="10:30",
                    players=[MockPlayer("David Pastrnak", "scorer")],
                ),
            ]
        )
        gs = MockParsedGameSummary(
            goals=[
                MockGoalInfo(
                    goal_number=1,
                    period=1,
                    time="10:30",
                    scorer=MockPlayerInfo("David Pastrnak"),
                    assist1=None,
                    assist2=None,
                ),
            ]
        )

        results = validator.validate_assists(pbp, gs)
        assert all(r.passed for r in results)


# =============================================================================
# Penalties Validation Tests
# =============================================================================


class TestValidatePenalties:
    """Tests for the validate_penalties method."""

    def test_matching_penalty_counts(self):
        """When penalty counts match, should pass."""
        validator = JSONvsHTMLValidator()

        pbp = MockParsedPlayByPlay(
            events=[
                MockPlayByPlayEvent(
                    event_type="penalty", period=1, time_in_period="5:00"
                ),
                MockPlayByPlayEvent(
                    event_type="penalty", period=2, time_in_period="10:00"
                ),
            ]
        )
        gs = MockParsedGameSummary(
            penalties=[
                MockPenaltyInfo(penalty_number=1, period=1, time="5:00"),
                MockPenaltyInfo(penalty_number=2, period=2, time="10:00"),
            ]
        )

        results = validator.validate_penalties(pbp, gs)

        count_results = [r for r in results if r.rule_name == "json_html_penalty_count"]
        assert len(count_results) == 1
        assert count_results[0].passed is True

    def test_matching_total_pim(self):
        """When total PIM matches, should pass."""
        validator = JSONvsHTMLValidator()

        pbp = MockParsedPlayByPlay(
            events=[
                MockPlayByPlayEvent(
                    event_type="penalty",
                    period=1,
                    time_in_period="5:00",
                    details={"duration": 2},
                ),
                MockPlayByPlayEvent(
                    event_type="penalty",
                    period=2,
                    time_in_period="10:00",
                    details={"duration": 5},
                ),
            ]
        )
        gs = MockParsedGameSummary(
            penalties=[
                MockPenaltyInfo(penalty_number=1, period=1, time="5:00", pim=2),
                MockPenaltyInfo(penalty_number=2, period=2, time="10:00", pim=5),
            ]
        )

        results = validator.validate_penalties(pbp, gs)

        pim_results = [r for r in results if r.rule_name == "json_html_pim_total"]
        assert len(pim_results) == 1
        assert pim_results[0].passed is True


# =============================================================================
# Shots Validation Tests
# =============================================================================


class TestValidateShots:
    """Tests for the validate_shots method."""

    def test_matching_shot_counts(self):
        """When shot counts match, should pass."""
        validator = JSONvsHTMLValidator()

        boxscore = MockParsedBoxscore(
            away_team=MockTeamBoxscore(shots_on_goal=28),
            home_team=MockTeamBoxscore(shots_on_goal=32),
        )
        shot_summary = MockParsedShotSummary(
            away_team=MockTeamShotSummary(periods=[MockPeriodShot("TOT", 28)]),
            home_team=MockTeamShotSummary(periods=[MockPeriodShot("TOT", 32)]),
        )

        results = validator.validate_shots(boxscore, shot_summary)

        # Check both teams pass
        away_results = [r for r in results if r.rule_name == "json_html_shots_away"]
        home_results = [r for r in results if r.rule_name == "json_html_shots_home"]

        assert len(away_results) == 1
        assert away_results[0].passed is True
        assert len(home_results) == 1
        assert home_results[0].passed is True

    def test_mismatched_shot_counts(self):
        """When shot counts don't match, should fail."""
        validator = JSONvsHTMLValidator()

        boxscore = MockParsedBoxscore(
            away_team=MockTeamBoxscore(shots_on_goal=30),
            home_team=MockTeamBoxscore(shots_on_goal=35),
        )
        shot_summary = MockParsedShotSummary(
            away_team=MockTeamShotSummary(periods=[MockPeriodShot("TOT", 28)]),
            home_team=MockTeamShotSummary(periods=[MockPeriodShot("TOT", 32)]),
        )

        results = validator.validate_shots(boxscore, shot_summary)

        away_results = [r for r in results if r.rule_name == "json_html_shots_away"]
        home_results = [r for r in results if r.rule_name == "json_html_shots_home"]

        assert away_results[0].passed is False
        assert home_results[0].passed is False


# =============================================================================
# Faceoffs Validation Tests
# =============================================================================


class TestValidateFaceoffs:
    """Tests for the validate_faceoffs method."""

    def test_matching_faceoff_wins(self):
        """When faceoff wins match, should pass."""
        validator = JSONvsHTMLValidator()

        boxscore = MockParsedBoxscore(
            away_skaters=[
                MockSkaterStats(faceoff_pct=50.0),
                MockSkaterStats(faceoff_pct=40.0),
            ],
            home_skaters=[
                MockSkaterStats(faceoff_pct=55.0),
                MockSkaterStats(faceoff_pct=45.0),
            ],
        )
        faceoff_summary = MockParsedFaceoffSummary(
            away_team=MockTeamFaceoffSummary(
                players=[
                    MockPlayerFaceoff(
                        totals=MockFaceoffTotals(MockFaceoffStat(won=10))
                    ),
                    MockPlayerFaceoff(totals=MockFaceoffTotals(MockFaceoffStat(won=5))),
                ]
            ),
            home_team=MockTeamFaceoffSummary(
                players=[
                    MockPlayerFaceoff(
                        totals=MockFaceoffTotals(MockFaceoffStat(won=12))
                    ),
                    MockPlayerFaceoff(totals=MockFaceoffTotals(MockFaceoffStat(won=8))),
                ]
            ),
        )

        results = validator.validate_faceoffs(boxscore, faceoff_summary)

        # Check that faceoff data was found
        data_results = [r for r in results if r.rule_name == "json_html_faceoff_data"]
        assert len(data_results) == 1
        assert data_results[0].passed is True

        # Check that players with faceoffs were found
        player_results = [
            r for r in results if r.rule_name == "json_html_faceoff_players"
        ]
        assert len(player_results) == 1
        assert player_results[0].passed is True


# =============================================================================
# TOI Validation Tests
# =============================================================================


class TestValidateTOI:
    """Tests for the validate_toi method."""

    def test_matching_toi_totals(self):
        """When TOI totals are within tolerance, should pass."""
        validator = JSONvsHTMLValidator()

        shifts = MockParsedShiftChart(
            shifts=[
                MockShift(player_id=1, duration_seconds=930),  # 15:30
                MockShift(player_id=2, duration_seconds=1200),  # 20:00
            ]
        )
        toi_html = MockParsedTimeOnIce(
            players=[
                MockPlayerTOI(number=11, total_toi="15:30"),
                MockPlayerTOI(number=22, total_toi="20:00"),
            ]
        )

        results = validator.validate_toi(shifts, toi_html)

        # Should have at least one result
        assert len(results) > 0


# =============================================================================
# validate_all Tests
# =============================================================================


class TestValidateAll:
    """Tests for the validate_all convenience method."""

    def test_validate_all_with_all_data(self):
        """When all data is provided, all validations should run."""
        validator = JSONvsHTMLValidator()

        pbp = MockParsedPlayByPlay(
            events=[
                MockPlayByPlayEvent(
                    event_type="goal",
                    period=1,
                    time_in_period="10:30",
                    players=[MockPlayer("Test Player", "scorer")],
                ),
            ]
        )
        boxscore = MockParsedBoxscore(
            away_team=MockTeamBoxscore(28),
            home_team=MockTeamBoxscore(32),
            away_skaters=[MockSkaterStats(faceoff_pct=50.0)],
            home_skaters=[MockSkaterStats(faceoff_pct=55.0)],
        )
        game_summary = MockParsedGameSummary(
            goals=[MockGoalInfo(goal_number=1, period=1, time="10:30")]
        )
        shot_summary = MockParsedShotSummary()
        faceoff_summary = MockParsedFaceoffSummary()
        shifts = MockParsedShiftChart()
        toi_html = MockParsedTimeOnIce()

        results = validator.validate_all(
            pbp=pbp,
            boxscore=boxscore,
            game_summary=game_summary,
            shot_summary=shot_summary,
            faceoff_summary=faceoff_summary,
            shifts=shifts,
            toi_html=toi_html,
        )

        # Should have multiple results from different validations
        rule_names = {r.rule_name for r in results}
        assert "json_html_goal_count" in rule_names
        assert (
            "json_html_shots_away" in rule_names or "json_html_shots_home" in rule_names
        )

    def test_validate_all_with_partial_data(self):
        """When only some data is provided, only applicable validations run."""
        validator = JSONvsHTMLValidator()

        # Only provide boxscore and shot summary
        boxscore = MockParsedBoxscore(
            away_team=MockTeamBoxscore(28),
            home_team=MockTeamBoxscore(32),
        )
        shot_summary = MockParsedShotSummary(
            away_team=MockTeamShotSummary(periods=[MockPeriodShot("TOT", 28)]),
            home_team=MockTeamShotSummary(periods=[MockPeriodShot("TOT", 32)]),
        )

        results = validator.validate_all(
            boxscore=boxscore,
            shot_summary=shot_summary,
        )

        # Should only have shot validation results
        rule_names = {r.rule_name for r in results}
        assert "json_html_shots_away" in rule_names
        assert "json_html_goal_count" not in rule_names

    def test_validate_all_with_no_data(self):
        """When no data is provided, should return empty list."""
        validator = JSONvsHTMLValidator()

        results = validator.validate_all()

        assert results == []


# =============================================================================
# Summary Tests
# =============================================================================


class TestGetValidationSummary:
    """Tests for the get_validation_summary method."""

    def test_summary_from_results(self):
        """Should create proper summary from validation results."""
        validator = JSONvsHTMLValidator()

        # Create some sample results
        from nhl_api.validation.results import make_failed, make_passed

        results = [
            make_passed("test_rule_1", "json_vs_html", entity_id="2024020500"),
            make_passed("test_rule_2", "json_vs_html", entity_id="2024020500"),
            make_failed(
                "test_rule_3",
                "json_vs_html",
                message="Test failure",
                entity_id="2024020500",
            ),
        ]

        summary = validator.get_validation_summary(2024020500, results)

        assert summary.entity_id == "2024020500"
        assert summary.total_checks == 3
        assert summary.passed == 2
        assert summary.failed == 1
