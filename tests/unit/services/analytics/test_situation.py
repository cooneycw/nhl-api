"""Unit tests for SituationCalculator service.

Tests situation code calculation and analysis logic.

Issue: #259 - Wave 1: Core Pipeline
"""

import pytest

from nhl_api.services.analytics.situation import (
    SituationCalculator,
    SituationType,
    calculate_situation_code,
    is_power_play_situation,
)


class TestSituationCalculator:
    """Tests for SituationCalculator class."""

    @pytest.fixture
    def calc(self) -> SituationCalculator:
        """Create a SituationCalculator instance."""
        return SituationCalculator()

    # Basic situation codes
    def test_calculate_5v5(self, calc: SituationCalculator) -> None:
        """5v5 even strength."""
        assert calc.calculate(5, 5) == "5v5"

    def test_calculate_5v4(self, calc: SituationCalculator) -> None:
        """5v4 power play for home."""
        assert calc.calculate(5, 4) == "5v4"

    def test_calculate_4v5(self, calc: SituationCalculator) -> None:
        """4v5 penalty kill for home."""
        assert calc.calculate(4, 5) == "4v5"

    def test_calculate_5v3(self, calc: SituationCalculator) -> None:
        """5v3 two-man advantage."""
        assert calc.calculate(5, 3) == "5v3"

    def test_calculate_3v5(self, calc: SituationCalculator) -> None:
        """3v5 two-man disadvantage."""
        assert calc.calculate(3, 5) == "3v5"

    def test_calculate_4v4(self, calc: SituationCalculator) -> None:
        """4v4 matching minors."""
        assert calc.calculate(4, 4) == "4v4"

    def test_calculate_3v3(self, calc: SituationCalculator) -> None:
        """3v3 overtime."""
        assert calc.calculate(3, 3) == "3v3"

    def test_calculate_4v3(self, calc: SituationCalculator) -> None:
        """4v3 power play during 4v4."""
        assert calc.calculate(4, 3) == "4v3"

    # Empty net situations
    def test_calculate_empty_net_home(self, calc: SituationCalculator) -> None:
        """Home team pulled goalie (6 attackers)."""
        assert calc.calculate(6, 5, home_empty_net=True) == "EN7v5"

    def test_calculate_empty_net_away(self, calc: SituationCalculator) -> None:
        """Away team pulled goalie."""
        assert calc.calculate(5, 6, away_empty_net=True) == "5v7EN"

    def test_calculate_empty_net_during_pp(self, calc: SituationCalculator) -> None:
        """Empty net during power play."""
        # 5v4 PP, home pulls goalie for extra attacker
        assert calc.calculate(6, 4, home_empty_net=True) == "EN7v4"


class TestSituationAnalysis:
    """Tests for full situation analysis."""

    @pytest.fixture
    def calc(self) -> SituationCalculator:
        """Create a SituationCalculator instance."""
        return SituationCalculator()

    def test_analyze_5v5(self, calc: SituationCalculator) -> None:
        """5v5 analysis."""
        situation = calc.analyze(5, 5, home_goalie=100, away_goalie=200)
        assert situation.code == "5v5"
        assert situation.situation_type == SituationType.EVEN_STRENGTH
        assert not situation.is_power_play
        assert not situation.is_empty_net
        assert situation.is_even_strength
        assert situation.home_advantage == 0
        assert situation.is_regulation

    def test_analyze_5v4(self, calc: SituationCalculator) -> None:
        """5v4 power play analysis."""
        situation = calc.analyze(5, 4, home_goalie=100, away_goalie=200)
        assert situation.code == "5v4"
        assert situation.situation_type == SituationType.POWER_PLAY_HOME
        assert situation.is_power_play
        assert situation.is_special_teams
        assert situation.home_advantage == 1
        assert not situation.is_regulation

    def test_analyze_4v5(self, calc: SituationCalculator) -> None:
        """4v5 penalty kill analysis."""
        situation = calc.analyze(4, 5, home_goalie=100, away_goalie=200)
        assert situation.code == "4v5"
        assert situation.situation_type == SituationType.POWER_PLAY_AWAY
        assert situation.is_power_play
        assert situation.home_advantage == -1

    def test_analyze_4v4(self, calc: SituationCalculator) -> None:
        """4v4 analysis."""
        situation = calc.analyze(4, 4, home_goalie=100, away_goalie=200)
        assert situation.code == "4v4"
        assert situation.situation_type == SituationType.FOUR_ON_FOUR
        assert not situation.is_power_play
        assert situation.is_four_on_four
        assert (
            not situation.is_even_strength
        )  # 4v4 is not "even strength" in hockey terms

    def test_analyze_3v3(self, calc: SituationCalculator) -> None:
        """3v3 overtime analysis."""
        situation = calc.analyze(3, 3, home_goalie=100, away_goalie=200)
        assert situation.code == "3v3"
        assert situation.situation_type == SituationType.THREE_ON_THREE
        assert situation.is_three_on_three

    def test_analyze_empty_net_home(self, calc: SituationCalculator) -> None:
        """Empty net home analysis."""
        situation = calc.analyze(6, 5, home_goalie=None, away_goalie=200)
        assert situation.code == "EN7v5"
        assert situation.situation_type == SituationType.EMPTY_NET_HOME
        assert situation.is_empty_net
        assert situation.home_goalie_id is None
        assert situation.away_goalie_id == 200

    def test_analyze_empty_net_away(self, calc: SituationCalculator) -> None:
        """Empty net away analysis."""
        situation = calc.analyze(5, 6, home_goalie=100, away_goalie=None)
        assert situation.code == "5v7EN"
        assert situation.situation_type == SituationType.EMPTY_NET_AWAY
        assert situation.is_empty_net


class TestEmptyNetDetection:
    """Tests for empty net detection from skater counts."""

    @pytest.fixture
    def calc(self) -> SituationCalculator:
        """Create a SituationCalculator instance."""
        return SituationCalculator()

    def test_no_empty_net(self, calc: SituationCalculator) -> None:
        """Normal 5v5, no empty net."""
        home_en, away_en = calc.detect_empty_net(5, 5)
        assert not home_en
        assert not away_en

    def test_home_empty_net(self, calc: SituationCalculator) -> None:
        """6 home skaters indicates empty net."""
        home_en, away_en = calc.detect_empty_net(6, 5)
        assert home_en
        assert not away_en

    def test_away_empty_net(self, calc: SituationCalculator) -> None:
        """6 away skaters indicates empty net."""
        home_en, away_en = calc.detect_empty_net(5, 6)
        assert not home_en
        assert away_en


class TestPowerPlayDetection:
    """Tests for power play detection."""

    @pytest.fixture
    def calc(self) -> SituationCalculator:
        """Create a SituationCalculator instance."""
        return SituationCalculator()

    def test_is_power_play_5v4(self, calc: SituationCalculator) -> None:
        """5v4 is a power play."""
        assert calc.is_power_play_code("5v4")

    def test_is_power_play_4v5(self, calc: SituationCalculator) -> None:
        """4v5 is a power play (for away team)."""
        assert calc.is_power_play_code("4v5")

    def test_is_not_power_play_5v5(self, calc: SituationCalculator) -> None:
        """5v5 is not a power play."""
        assert not calc.is_power_play_code("5v5")

    def test_is_not_power_play_4v4(self, calc: SituationCalculator) -> None:
        """4v4 is not a power play."""
        assert not calc.is_power_play_code("4v4")

    def test_is_power_play_with_en(self, calc: SituationCalculator) -> None:
        """EN6v5 is a power play (man advantage)."""
        assert calc.is_power_play_code("EN6v5")

    def test_get_pp_team_home(self, calc: SituationCalculator) -> None:
        """5v4 means home is on power play."""
        assert calc.get_power_play_team("5v4") == "home"

    def test_get_pp_team_away(self, calc: SituationCalculator) -> None:
        """4v5 means away is on power play."""
        assert calc.get_power_play_team("4v5") == "away"

    def test_get_pp_team_none(self, calc: SituationCalculator) -> None:
        """5v5 has no team on power play."""
        assert calc.get_power_play_team("5v5") is None


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_calculate_situation_code(self) -> None:
        """Module function calculates correctly."""
        assert calculate_situation_code(5, 5) == "5v5"
        assert calculate_situation_code(5, 4) == "5v4"
        assert calculate_situation_code(6, 5, home_empty_net=True) == "EN7v5"

    def test_is_power_play_situation(self) -> None:
        """Module function detects power plays."""
        assert is_power_play_situation("5v4")
        assert not is_power_play_situation("5v5")
