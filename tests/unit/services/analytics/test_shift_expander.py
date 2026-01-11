"""Unit tests for ShiftExpander service.

Tests the time conversion and shift expansion logic without database access.

Issue: #259 - Wave 1: Core Pipeline
"""

import pytest

from nhl_api.services.analytics.shift_expander import (
    OT_SECONDS,
    PERIOD_SECONDS,
    ExpandedSecond,
    GameExpansionResult,
    parse_game_clock_to_elapsed,
    period_to_game_second,
)


class TestParseGameClockToElapsed:
    """Tests for parse_game_clock_to_elapsed function."""

    def test_full_period_start(self) -> None:
        """20:00 on game clock = 0 seconds elapsed."""
        assert parse_game_clock_to_elapsed("20:00", 1) == 0

    def test_full_period_end(self) -> None:
        """00:00 on game clock = 1200 seconds elapsed."""
        assert parse_game_clock_to_elapsed("00:00", 1) == PERIOD_SECONDS

    def test_mid_period(self) -> None:
        """19:45 = 15 seconds elapsed."""
        assert parse_game_clock_to_elapsed("19:45", 1) == 15

    def test_half_period(self) -> None:
        """10:00 = 600 seconds elapsed."""
        assert parse_game_clock_to_elapsed("10:00", 1) == 600

    def test_late_period(self) -> None:
        """00:30 = 1170 seconds elapsed."""
        assert parse_game_clock_to_elapsed("00:30", 1) == 1170

    def test_overtime_period(self) -> None:
        """OT has 5 minute (300 second) periods."""
        # 5:00 OT = 0 elapsed
        assert parse_game_clock_to_elapsed("05:00", 4) == 0
        # 0:00 OT = 300 elapsed
        assert parse_game_clock_to_elapsed("00:00", 4) == OT_SECONDS

    def test_empty_string(self) -> None:
        """Empty string returns 0."""
        assert parse_game_clock_to_elapsed("", 1) == 0

    def test_invalid_format(self) -> None:
        """Invalid format returns 0."""
        assert parse_game_clock_to_elapsed("invalid", 1) == 0
        assert parse_game_clock_to_elapsed("12", 1) == 0
        assert parse_game_clock_to_elapsed("12:34:56", 1) == 0

    def test_none_value(self) -> None:
        """None returns 0."""
        assert parse_game_clock_to_elapsed(None, 1) == 0  # type: ignore


class TestPeriodToGameSecond:
    """Tests for period_to_game_second function."""

    def test_first_period_start(self) -> None:
        """Period 1, second 0 = game second 0."""
        assert period_to_game_second(1, 0) == 0

    def test_first_period_mid(self) -> None:
        """Period 1, second 600 = game second 600."""
        assert period_to_game_second(1, 600) == 600

    def test_second_period_start(self) -> None:
        """Period 2, second 0 = game second 1200."""
        assert period_to_game_second(2, 0) == 1200

    def test_third_period_start(self) -> None:
        """Period 3, second 0 = game second 2400."""
        assert period_to_game_second(3, 0) == 2400

    def test_third_period_end(self) -> None:
        """Period 3, second 1200 = game second 3600."""
        assert period_to_game_second(3, 1200) == 3600

    def test_overtime_start(self) -> None:
        """Period 4 (OT), second 0 = game second 3600."""
        assert period_to_game_second(4, 0) == 3600

    def test_overtime_mid(self) -> None:
        """Period 4 (OT), second 150 = game second 3750."""
        assert period_to_game_second(4, 150) == 3750

    def test_double_overtime(self) -> None:
        """Period 5 (2OT), second 0 = game second 3900."""
        assert period_to_game_second(5, 0) == 3900


class TestExpandedSecond:
    """Tests for ExpandedSecond dataclass."""

    def test_situation_code_5v5(self) -> None:
        """5v5 situation code."""
        second = ExpandedSecond(
            game_id=2024020500,
            season_id=20242025,
            period=1,
            period_second=100,
            game_second=100,
            home_skaters=frozenset({1, 2, 3, 4, 5}),
            away_skaters=frozenset({10, 11, 12, 13, 14}),
            home_goalie_id=100,  # Goalie in net
            away_goalie_id=200,  # Goalie in net
        )
        assert second.situation_code == "5v5"
        assert not second.is_power_play
        assert not second.is_empty_net

    def test_situation_code_5v4(self) -> None:
        """5v4 power play situation."""
        second = ExpandedSecond(
            game_id=2024020500,
            season_id=20242025,
            period=1,
            period_second=100,
            game_second=100,
            home_skaters=frozenset({1, 2, 3, 4, 5}),
            away_skaters=frozenset({10, 11, 12, 13}),  # 4 skaters
            home_goalie_id=100,
            away_goalie_id=200,
        )
        assert second.situation_code == "5v4"
        assert second.is_power_play

    def test_situation_code_4v5(self) -> None:
        """4v5 penalty kill situation."""
        second = ExpandedSecond(
            game_id=2024020500,
            season_id=20242025,
            period=1,
            period_second=100,
            game_second=100,
            home_skaters=frozenset({1, 2, 3, 4}),  # 4 skaters
            away_skaters=frozenset({10, 11, 12, 13, 14}),
            home_goalie_id=100,
            away_goalie_id=200,
        )
        assert second.situation_code == "4v5"
        assert second.is_power_play

    def test_empty_net_home(self) -> None:
        """Empty net with home goalie pulled."""
        second = ExpandedSecond(
            game_id=2024020500,
            season_id=20242025,
            period=3,
            period_second=1150,
            game_second=3550,
            home_skaters=frozenset({1, 2, 3, 4, 5, 6}),  # 6 skaters (extra attacker)
            away_skaters=frozenset({10, 11, 12, 13, 14}),
            home_goalie_id=None,  # Pulled
            away_goalie_id=8476945,
        )
        assert second.is_empty_net

    def test_frozen_dataclass(self) -> None:
        """ExpandedSecond should be immutable."""
        second = ExpandedSecond(
            game_id=2024020500,
            season_id=20242025,
            period=1,
            period_second=100,
            game_second=100,
            home_skaters=frozenset({1, 2, 3, 4, 5}),
            away_skaters=frozenset({10, 11, 12, 13, 14}),
        )
        with pytest.raises(AttributeError):
            second.game_id = 999  # type: ignore


class TestGameExpansionResult:
    """Tests for GameExpansionResult dataclass."""

    def test_success_with_seconds(self) -> None:
        """Result is successful when it has seconds and no errors."""
        result = GameExpansionResult(
            game_id=2024020500,
            season_id=20242025,
            home_team_id=1,
            away_team_id=2,
            total_shifts=100,
            total_seconds=3600,
            seconds=[
                ExpandedSecond(
                    game_id=2024020500,
                    season_id=20242025,
                    period=1,
                    period_second=0,
                    game_second=0,
                    home_skaters=frozenset({1, 2, 3, 4, 5}),
                    away_skaters=frozenset({10, 11, 12, 13, 14}),
                    home_goalie_id=100,
                    away_goalie_id=200,
                )
            ],
        )
        assert result.success

    def test_failure_with_errors(self) -> None:
        """Result is not successful when it has errors."""
        result = GameExpansionResult(
            game_id=2024020500,
            season_id=20242025,
            home_team_id=1,
            away_team_id=2,
            errors=["No shifts found"],
        )
        assert not result.success

    def test_failure_no_seconds(self) -> None:
        """Result is not successful when it has no seconds."""
        result = GameExpansionResult(
            game_id=2024020500,
            season_id=20242025,
            home_team_id=1,
            away_team_id=2,
        )
        assert not result.success
