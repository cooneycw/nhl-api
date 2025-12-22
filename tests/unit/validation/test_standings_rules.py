"""Tests for standings internal consistency validation rules."""
# mypy: disable-error-code="arg-type"

from __future__ import annotations

from typing import Any

from nhl_api.validation.rules.standings import validate_standings


class MockTeamStandings:
    """Mock team standings for testing."""

    def __init__(
        self,
        team_abbrev: str = "BOS",
        games_played: int = 20,
        wins: int = 12,
        losses: int = 5,
        ot_losses: int = 3,
        points: int = 27,  # 12*2 + 3
        goals_for: int = 60,
        goals_against: int = 45,
        goal_differential: int = 15,
        regulation_wins: int = 10,
        point_pctg: float = 67.5,
    ):
        self.team_abbrev = team_abbrev
        self.games_played = games_played
        self.wins = wins
        self.losses = losses
        self.ot_losses = ot_losses
        self.points = points
        self.goals_for = goals_for
        self.goals_against = goals_against
        self.goal_differential = goal_differential
        self.regulation_wins = regulation_wins
        self.point_pctg = point_pctg


class MockParsedStandings:
    """Mock parsed standings for testing."""

    def __init__(self, standings: list[Any], season_id: int = 20242025):
        self.standings = standings
        self.season_id = season_id


class TestGPSumValidation:
    """Tests for GP = W + L + OTL validation."""

    def test_valid_gp_sum(self):
        """GP equals W + L + OTL should pass."""
        team = MockTeamStandings(games_played=20, wins=12, losses=5, ot_losses=3)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        gp_results = [r for r in results if r.rule_name == "standings_gp_sum"]
        assert len(gp_results) == 1
        assert gp_results[0].passed is True

    def test_gp_mismatch(self):
        """GP != W + L + OTL should fail."""
        team = MockTeamStandings(
            games_played=25,  # Should be 20
            wins=12,
            losses=5,
            ot_losses=3,
        )
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        gp_results = [r for r in results if r.rule_name == "standings_gp_sum"]
        assert len(gp_results) == 1
        assert gp_results[0].passed is False
        assert gp_results[0].severity == "error"


class TestPointsCalculationValidation:
    """Tests for points = W*2 + OTL validation."""

    def test_valid_points(self):
        """Points = W*2 + OTL should pass."""
        team = MockTeamStandings(
            wins=12,
            ot_losses=3,
            points=27,  # 12*2 + 3 = 27
        )
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        pts_results = [r for r in results if r.rule_name == "standings_points_calc"]
        assert len(pts_results) == 1
        assert pts_results[0].passed is True

    def test_points_mismatch(self):
        """Points != W*2 + OTL should fail."""
        team = MockTeamStandings(
            wins=12,
            ot_losses=3,
            points=30,  # Should be 27
        )
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        pts_results = [r for r in results if r.rule_name == "standings_points_calc"]
        assert len(pts_results) == 1
        assert pts_results[0].passed is False
        assert pts_results[0].severity == "error"


class TestGoalDifferentialValidation:
    """Tests for goal_diff = GF - GA validation."""

    def test_valid_goal_diff(self):
        """Goal differential = GF - GA should pass."""
        team = MockTeamStandings(goals_for=60, goals_against=45, goal_differential=15)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        diff_results = [r for r in results if r.rule_name == "standings_goal_diff"]
        assert len(diff_results) == 1
        assert diff_results[0].passed is True

    def test_goal_diff_mismatch(self):
        """Goal differential != GF - GA should fail."""
        team = MockTeamStandings(
            goals_for=60,
            goals_against=45,
            goal_differential=20,  # Should be 15
        )
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        diff_results = [r for r in results if r.rule_name == "standings_goal_diff"]
        assert len(diff_results) == 1
        assert diff_results[0].passed is False
        assert diff_results[0].severity == "error"

    def test_negative_goal_diff(self):
        """Negative goal differential should pass if math is correct."""
        team = MockTeamStandings(goals_for=45, goals_against=60, goal_differential=-15)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        diff_results = [r for r in results if r.rule_name == "standings_goal_diff"]
        assert len(diff_results) == 1
        assert diff_results[0].passed is True


class TestWinBreakdownValidation:
    """Tests for wins >= regulation_wins validation."""

    def test_valid_win_breakdown(self):
        """Total wins >= regulation wins should pass."""
        team = MockTeamStandings(wins=12, regulation_wins=10)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        win_results = [r for r in results if r.rule_name == "standings_win_breakdown"]
        assert len(win_results) == 1
        assert win_results[0].passed is True

    def test_regulation_wins_exceed_total(self):
        """Regulation wins > total wins should fail."""
        team = MockTeamStandings(wins=10, regulation_wins=12)  # Invalid
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        win_results = [r for r in results if r.rule_name == "standings_win_breakdown"]
        assert len(win_results) == 1
        assert win_results[0].passed is False
        assert win_results[0].severity == "warning"


class TestPointPercentageValidation:
    """Tests for point percentage range validation."""

    def test_valid_point_pct(self):
        """Point percentage in 0-100 range should pass."""
        team = MockTeamStandings(point_pctg=67.5)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        pct_results = [r for r in results if r.rule_name == "standings_point_pct_range"]
        assert len(pct_results) == 1
        assert pct_results[0].passed is True

    def test_point_pct_zero(self):
        """0% point percentage should pass."""
        team = MockTeamStandings(point_pctg=0.0)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        pct_results = [r for r in results if r.rule_name == "standings_point_pct_range"]
        assert len(pct_results) == 1
        assert pct_results[0].passed is True

    def test_point_pct_100(self):
        """100% point percentage should pass."""
        team = MockTeamStandings(point_pctg=100.0)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        pct_results = [r for r in results if r.rule_name == "standings_point_pct_range"]
        assert len(pct_results) == 1
        assert pct_results[0].passed is True

    def test_point_pct_negative(self):
        """Negative point percentage should fail."""
        team = MockTeamStandings(point_pctg=-5.0)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        pct_results = [r for r in results if r.rule_name == "standings_point_pct_range"]
        assert len(pct_results) == 1
        assert pct_results[0].passed is False
        assert pct_results[0].severity == "info"

    def test_point_pct_over_100(self):
        """Point percentage > 100 should fail."""
        team = MockTeamStandings(point_pctg=105.0)
        standings = MockParsedStandings([team])
        results = validate_standings(standings)
        pct_results = [r for r in results if r.rule_name == "standings_point_pct_range"]
        assert len(pct_results) == 1
        assert pct_results[0].passed is False


class TestMultipleTeamsValidation:
    """Tests for validating multiple teams."""

    def test_all_teams_valid(self):
        """All teams with valid data should all pass."""
        teams = [
            MockTeamStandings(team_abbrev="BOS"),
            MockTeamStandings(team_abbrev="TOR"),
            MockTeamStandings(team_abbrev="MTL"),
        ]
        standings = MockParsedStandings(teams)
        results = validate_standings(standings)
        # 5 rules per team = 15 results
        assert len(results) == 15
        assert all(r.passed for r in results)

    def test_mix_of_valid_and_invalid(self):
        """Mix of valid and invalid teams."""
        teams = [
            MockTeamStandings(team_abbrev="BOS"),  # Valid
            MockTeamStandings(
                team_abbrev="TOR", games_played=25, wins=12, losses=5, ot_losses=3
            ),  # Invalid GP
        ]
        standings = MockParsedStandings(teams)
        results = validate_standings(standings)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 1
        assert failed[0].rule_name == "standings_gp_sum"
