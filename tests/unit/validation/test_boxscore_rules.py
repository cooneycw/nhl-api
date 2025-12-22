"""Unit tests for boxscore validation rules."""
# mypy: disable-error-code="arg-type"

from __future__ import annotations

from nhl_api.downloaders.sources.nhl_json.boxscore import (
    GoalieStats,
    ParsedBoxscore,
    SkaterStats,
    TeamBoxscore,
)
from nhl_api.validation.rules.boxscore import validate_boxscore


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


def make_goalie(
    player_id: int = 100,
    name: str = "Test Goalie",
    sweater_number: int = 35,
    saves: int = 25,
    shots_against: int = 27,
    goals_against: int = 2,
    save_pct: float = 0.926,
    toi: str = "60:00",
    even_strength_shots_against: str = "20/22",
    power_play_shots_against: str = "3/3",
    shorthanded_shots_against: str = "2/2",
    is_starter: bool = True,
    decision: str | None = "W",
    team_id: int = 1,
) -> GoalieStats:
    """Create a GoalieStats for testing."""
    return GoalieStats(
        player_id=player_id,
        name=name,
        sweater_number=sweater_number,
        saves=saves,
        shots_against=shots_against,
        goals_against=goals_against,
        save_pct=save_pct,
        toi=toi,
        even_strength_shots_against=even_strength_shots_against,
        power_play_shots_against=power_play_shots_against,
        shorthanded_shots_against=shorthanded_shots_against,
        is_starter=is_starter,
        decision=decision,
        team_id=team_id,
    )


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


def make_boxscore(
    game_id: int = 2024020001,
    home_team: TeamBoxscore | None = None,
    away_team: TeamBoxscore | None = None,
    home_skaters: list[SkaterStats] | None = None,
    away_skaters: list[SkaterStats] | None = None,
    home_goalies: list[GoalieStats] | None = None,
    away_goalies: list[GoalieStats] | None = None,
) -> ParsedBoxscore:
    """Create a ParsedBoxscore for testing."""
    return ParsedBoxscore(
        game_id=game_id,
        season_id=20242025,
        game_date="2024-10-15",
        game_type=2,
        game_state="OFF",
        home_team=home_team or make_team(is_home=True),
        away_team=away_team or make_team(team_id=2, abbrev="MTL", is_home=False),
        home_skaters=home_skaters or [],
        away_skaters=away_skaters or [],
        home_goalies=home_goalies or [],
        away_goalies=away_goalies or [],
    )


class TestSkaterPointsValidation:
    """Tests for skater points = goals + assists rule."""

    def test_valid_points(self) -> None:
        """Points = goals + assists should pass."""
        skater = make_skater(goals=2, assists=1, points=3)
        boxscore = make_boxscore(
            home_team=make_team(score=2),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        points_results = [r for r in results if r.rule_name == "boxscore_player_points"]
        assert len(points_results) == 1
        assert points_results[0].passed is True

    def test_points_mismatch(self) -> None:
        """Points != goals + assists should fail."""
        skater = make_skater(goals=2, assists=1, points=5)  # Should be 3
        boxscore = make_boxscore(
            home_team=make_team(score=2),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        points_results = [r for r in results if r.rule_name == "boxscore_player_points"]
        assert len(points_results) == 1
        assert points_results[0].passed is False
        assert points_results[0].severity == "error"
        assert "5" in points_results[0].message  # actual points
        assert "3" in points_results[0].message  # expected

    def test_zero_points(self) -> None:
        """Zero points with zero goals/assists should pass."""
        skater = make_skater(goals=0, assists=0, points=0)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        points_results = [r for r in results if r.rule_name == "boxscore_player_points"]
        assert points_results[0].passed is True


class TestSpecialTeamsGoalsValidation:
    """Tests for PP+SH goals <= total goals rule."""

    def test_valid_special_teams(self) -> None:
        """PP + SH goals <= total should pass."""
        skater = make_skater(
            goals=3, assists=0, points=3, power_play_goals=1, shorthanded_goals=1
        )
        boxscore = make_boxscore(
            home_team=make_team(score=3),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        st_results = [
            r for r in results if r.rule_name == "boxscore_special_teams_goals"
        ]
        assert st_results[0].passed is True

    def test_special_teams_exceeds_total(self) -> None:
        """PP + SH goals > total should fail."""
        skater = make_skater(
            goals=1, assists=0, points=1, power_play_goals=1, shorthanded_goals=1
        )
        boxscore = make_boxscore(
            home_team=make_team(score=1),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        st_results = [
            r for r in results if r.rule_name == "boxscore_special_teams_goals"
        ]
        assert st_results[0].passed is False
        assert st_results[0].severity == "error"


class TestFaceoffPctValidation:
    """Tests for faceoff percentage range rule."""

    def test_valid_faceoff_pct(self) -> None:
        """Faceoff pct in 0-100 should pass."""
        skater = make_skater(faceoff_pct=55.5)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        fo_results = [r for r in results if r.rule_name == "boxscore_faceoff_pct_range"]
        assert fo_results[0].passed is True

    def test_faceoff_pct_zero(self) -> None:
        """Zero faceoff pct should pass (player took no faceoffs)."""
        skater = make_skater(faceoff_pct=0.0)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        fo_results = [r for r in results if r.rule_name == "boxscore_faceoff_pct_range"]
        assert fo_results[0].passed is True

    def test_faceoff_pct_100(self) -> None:
        """100% faceoff pct should pass."""
        skater = make_skater(faceoff_pct=100.0)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        fo_results = [r for r in results if r.rule_name == "boxscore_faceoff_pct_range"]
        assert fo_results[0].passed is True

    def test_faceoff_pct_negative(self) -> None:
        """Negative faceoff pct should fail."""
        skater = make_skater(faceoff_pct=-5.0)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        fo_results = [r for r in results if r.rule_name == "boxscore_faceoff_pct_range"]
        assert fo_results[0].passed is False
        assert fo_results[0].severity == "warning"

    def test_faceoff_pct_over_100(self) -> None:
        """Faceoff pct > 100 should fail."""
        skater = make_skater(faceoff_pct=105.0)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        fo_results = [r for r in results if r.rule_name == "boxscore_faceoff_pct_range"]
        assert fo_results[0].passed is False


class TestTOIFormatValidation:
    """Tests for TOI format validation rule."""

    def test_valid_toi_format(self) -> None:
        """Valid MM:SS format should pass."""
        skater = make_skater(toi="18:45")
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        toi_results = [r for r in results if r.rule_name == "boxscore_toi_format"]
        assert toi_results[0].passed is True

    def test_valid_single_digit_minutes(self) -> None:
        """Single digit minutes (M:SS) should pass."""
        skater = make_skater(toi="5:30")
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        toi_results = [r for r in results if r.rule_name == "boxscore_toi_format"]
        assert toi_results[0].passed is True

    def test_invalid_toi_format(self) -> None:
        """Invalid format should fail."""
        skater = make_skater(toi="invalid")
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[skater],
        )
        results = validate_boxscore(boxscore)
        toi_results = [r for r in results if r.rule_name == "boxscore_toi_format"]
        assert toi_results[0].passed is False
        assert toi_results[0].severity == "info"


class TestGoalieSavePctValidation:
    """Tests for goalie save percentage range rule."""

    def test_valid_save_pct(self) -> None:
        """Save pct in 0-1 should pass."""
        goalie = make_goalie(save_pct=0.926)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_goalies=[goalie],
        )
        results = validate_boxscore(boxscore)
        save_results = [r for r in results if r.rule_name == "boxscore_save_pct_range"]
        assert save_results[0].passed is True

    def test_save_pct_zero(self) -> None:
        """Zero save pct should pass (goalie faced no shots or let in all)."""
        goalie = make_goalie(save_pct=0.0, saves=0, shots_against=0, goals_against=0)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_goalies=[goalie],
        )
        results = validate_boxscore(boxscore)
        save_results = [r for r in results if r.rule_name == "boxscore_save_pct_range"]
        assert save_results[0].passed is True

    def test_save_pct_perfect(self) -> None:
        """Perfect save pct (1.0) should pass."""
        goalie = make_goalie(save_pct=1.0, saves=30, shots_against=30, goals_against=0)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_goalies=[goalie],
        )
        results = validate_boxscore(boxscore)
        save_results = [r for r in results if r.rule_name == "boxscore_save_pct_range"]
        assert save_results[0].passed is True

    def test_save_pct_over_one(self) -> None:
        """Save pct > 1 should fail."""
        goalie = make_goalie(save_pct=1.5)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_goalies=[goalie],
        )
        results = validate_boxscore(boxscore)
        save_results = [r for r in results if r.rule_name == "boxscore_save_pct_range"]
        assert save_results[0].passed is False
        assert save_results[0].severity == "warning"


class TestGoalieShotsMathValidation:
    """Tests for goalie saves + GA = shots_against rule."""

    def test_valid_goalie_math(self) -> None:
        """Saves + GA = shots should pass."""
        goalie = make_goalie(saves=25, goals_against=2, shots_against=27)
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_goalies=[goalie],
        )
        results = validate_boxscore(boxscore)
        math_results = [
            r for r in results if r.rule_name == "boxscore_goalie_shots_math"
        ]
        assert math_results[0].passed is True

    def test_goalie_math_mismatch(self) -> None:
        """Saves + GA != shots should fail."""
        goalie = make_goalie(
            saves=25, goals_against=2, shots_against=30
        )  # Should be 27
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_goalies=[goalie],
        )
        results = validate_boxscore(boxscore)
        math_results = [
            r for r in results if r.rule_name == "boxscore_goalie_shots_math"
        ]
        assert math_results[0].passed is False
        assert math_results[0].severity == "error"


class TestTeamGoalsSumValidation:
    """Tests for team goals = sum of player goals rule."""

    def test_valid_team_goals_sum(self) -> None:
        """Sum of player goals = team score should pass."""
        skaters = [
            make_skater(player_id=1, goals=2, assists=0, points=2),
            make_skater(player_id=2, goals=1, assists=1, points=2),
        ]
        boxscore = make_boxscore(
            home_team=make_team(score=3),
            home_skaters=skaters,
        )
        results = validate_boxscore(boxscore)
        sum_results = [r for r in results if r.rule_name == "boxscore_team_goals_sum"]
        # Should have results for both home and away
        home_result = [r for r in sum_results if "home" in r.message][0]
        assert home_result.passed is True

    def test_team_goals_sum_mismatch(self) -> None:
        """Sum of player goals != team score should fail."""
        skaters = [
            make_skater(player_id=1, goals=1, assists=0, points=1),
            make_skater(player_id=2, goals=1, assists=0, points=1),
        ]
        boxscore = make_boxscore(
            home_team=make_team(score=5),  # Team score is 5, but players only have 2
            home_skaters=skaters,
        )
        results = validate_boxscore(boxscore)
        sum_results = [r for r in results if r.rule_name == "boxscore_team_goals_sum"]
        home_result = [r for r in sum_results if "home" in r.message][0]
        assert home_result.passed is False
        assert home_result.severity == "error"

    def test_empty_roster(self) -> None:
        """Empty roster with zero team score should pass."""
        boxscore = make_boxscore(
            home_team=make_team(score=0),
            home_skaters=[],
        )
        results = validate_boxscore(boxscore)
        sum_results = [r for r in results if r.rule_name == "boxscore_team_goals_sum"]
        home_result = [r for r in sum_results if "home" in r.message][0]
        assert home_result.passed is True


class TestShotsGteGoalsValidation:
    """Tests for team shots >= goals rule."""

    def test_shots_greater_than_goals(self) -> None:
        """Shots > goals should pass."""
        boxscore = make_boxscore(
            home_team=make_team(score=3, shots_on_goal=30),
        )
        results = validate_boxscore(boxscore)
        shots_results = [
            r for r in results if r.rule_name == "boxscore_shots_gte_goals"
        ]
        home_result = [r for r in shots_results if "home" in r.message][0]
        assert home_result.passed is True

    def test_shots_equal_goals(self) -> None:
        """Shots = goals (perfect efficiency) should pass."""
        boxscore = make_boxscore(
            home_team=make_team(score=3, shots_on_goal=3),
        )
        results = validate_boxscore(boxscore)
        shots_results = [
            r for r in results if r.rule_name == "boxscore_shots_gte_goals"
        ]
        home_result = [r for r in shots_results if "home" in r.message][0]
        assert home_result.passed is True

    def test_shots_less_than_goals(self) -> None:
        """Shots < goals should fail (impossible)."""
        boxscore = make_boxscore(
            home_team=make_team(score=5, shots_on_goal=3),
        )
        results = validate_boxscore(boxscore)
        shots_results = [
            r for r in results if r.rule_name == "boxscore_shots_gte_goals"
        ]
        home_result = [r for r in shots_results if "home" in r.message][0]
        assert home_result.passed is False
        assert home_result.severity == "warning"


class TestMultiplePlayersValidation:
    """Tests for validating multiple players at once."""

    def test_multiple_skaters(self) -> None:
        """All validation rules should apply to each skater."""
        skaters = [
            make_skater(player_id=1, goals=2, assists=1, points=3),
            make_skater(player_id=2, goals=1, assists=2, points=3),
            make_skater(player_id=3, goals=0, assists=0, points=0),
        ]
        boxscore = make_boxscore(
            home_team=make_team(score=3),
            home_skaters=skaters,
        )
        results = validate_boxscore(boxscore)

        # Should have 4 rules per skater: points, special_teams, faceoff_pct, toi
        points_results = [r for r in results if r.rule_name == "boxscore_player_points"]
        assert len(points_results) == 3  # One per skater
        assert all(r.passed for r in points_results)

    def test_mix_of_valid_and_invalid(self) -> None:
        """Should catch invalid players while passing valid ones."""
        skaters = [
            make_skater(player_id=1, goals=2, assists=1, points=3),  # Valid
            make_skater(player_id=2, goals=1, assists=2, points=5),  # Invalid points
        ]
        boxscore = make_boxscore(
            home_team=make_team(score=3),
            home_skaters=skaters,
        )
        results = validate_boxscore(boxscore)

        points_results = [r for r in results if r.rule_name == "boxscore_player_points"]
        assert len(points_results) == 2
        passed = [r for r in points_results if r.passed]
        failed = [r for r in points_results if not r.passed]
        assert len(passed) == 1
        assert len(failed) == 1
