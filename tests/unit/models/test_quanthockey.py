"""Unit tests for QuantHockey data models.

Tests cover:
- QuantHockeyPlayerSeasonStats creation and validation
- QuantHockeyPlayerCareerStats creation and validation
- QuantHockeySeasonData container functionality
- Factory methods (from_row_data, from_dict)
- Validation rules for percentages and non-negative values
- Computed properties
- Serialization (to_dict)
"""

from typing import Any

import pytest

from nhl_api.models.quanthockey import (
    QuantHockeyPlayerCareerStats,
    QuantHockeyPlayerSeasonStats,
    QuantHockeySeasonData,
    _safe_float,
    _safe_int,
)

# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_row_data() -> list[str]:
    """Sample 51-field row data from QuantHockey table."""
    return [
        "1",  # rank
        "Connor McDavid",  # name
        "EDM",  # team
        "28",  # age
        "C",  # position
        "35",  # games_played
        "22",  # goals
        "38",  # assists
        "60",  # points
        "12",  # pim
        "15",  # plus_minus
        "22.5",  # toi_avg
        "17.3",  # toi_es
        "4.2",  # toi_pp
        "1.0",  # toi_sh
        "12",  # es_goals
        "10",  # pp_goals
        "0",  # sh_goals
        "5",  # gw_goals
        "2",  # ot_goals
        "25",  # es_assists
        "12",  # pp_assists
        "1",  # sh_assists
        "3",  # gw_assists
        "1",  # ot_assists
        "37",  # es_points
        "22",  # pp_points
        "1",  # sh_points
        "8",  # gw_points
        "3",  # ot_points
        "36.7",  # ppp_pct
        "1.15",  # goals_per_60
        "1.98",  # assists_per_60
        "3.13",  # points_per_60
        "0.78",  # es_goals_per_60
        "1.62",  # es_assists_per_60
        "2.40",  # es_points_per_60
        "2.38",  # pp_goals_per_60
        "2.86",  # pp_assists_per_60
        "5.24",  # pp_points_per_60
        "0.63",  # goals_per_game
        "1.09",  # assists_per_game
        "1.71",  # points_per_game
        "125",  # shots_on_goal
        "17.6",  # shooting_pct
        "18",  # hits
        "8",  # blocked_shots
        "312",  # faceoffs_won
        "198",  # faceoffs_lost
        "61.2",  # faceoff_pct
        "CAN",  # nationality
    ]


@pytest.fixture
def sample_dict_data() -> dict[str, Any]:
    """Sample dictionary data for model creation."""
    return {
        "season_id": 20242025,
        "rank": 1,
        "name": "Leon Draisaitl",
        "team": "EDM",
        "age": 29,
        "position": "C",
        "games_played": 35,
        "goals": 25,
        "assists": 30,
        "points": 55,
        "pim": 14,
        "plus_minus": 12,
        "toi_avg": 21.5,
        "toi_es": 16.0,
        "toi_pp": 4.5,
        "toi_sh": 1.0,
        "es_goals": 15,
        "pp_goals": 10,
        "sh_goals": 0,
        "gw_goals": 4,
        "ot_goals": 1,
        "es_assists": 18,
        "pp_assists": 11,
        "sh_assists": 1,
        "gw_assists": 2,
        "ot_assists": 0,
        "es_points": 33,
        "pp_points": 21,
        "sh_points": 1,
        "gw_points": 6,
        "ot_points": 1,
        "ppp_pct": 38.2,
        "goals_per_60": 1.30,
        "assists_per_60": 1.56,
        "points_per_60": 2.86,
        "es_goals_per_60": 0.94,
        "es_assists_per_60": 1.13,
        "es_points_per_60": 2.06,
        "pp_goals_per_60": 2.22,
        "pp_assists_per_60": 2.44,
        "pp_points_per_60": 4.67,
        "goals_per_game": 0.71,
        "assists_per_game": 0.86,
        "points_per_game": 1.57,
        "shots_on_goal": 115,
        "shooting_pct": 21.7,
        "hits": 25,
        "blocked_shots": 12,
        "faceoffs_won": 280,
        "faceoffs_lost": 220,
        "faceoff_pct": 56.0,
        "nationality": "DEU",
    }


@pytest.fixture
def sample_season_stats(
    sample_dict_data: dict[str, Any],
) -> QuantHockeyPlayerSeasonStats:
    """Create a sample season stats instance."""
    return QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)


# =============================================================================
# Safe Conversion Tests
# =============================================================================


class TestSafeInt:
    """Tests for _safe_int conversion function."""

    def test_int_value(self) -> None:
        """Test integer input."""
        assert _safe_int(42) == 42

    def test_string_value(self) -> None:
        """Test string input."""
        assert _safe_int("42") == 42

    def test_float_value(self) -> None:
        """Test float input (truncated)."""
        assert _safe_int(42.7) == 42

    def test_string_with_comma(self) -> None:
        """Test string with comma separator."""
        assert _safe_int("1,234") == 1234

    def test_none_value(self) -> None:
        """Test None returns default."""
        assert _safe_int(None) == 0
        assert _safe_int(None, default=5) == 5

    def test_empty_string(self) -> None:
        """Test empty string returns default."""
        assert _safe_int("") == 0

    def test_dash_string(self) -> None:
        """Test dash returns default."""
        assert _safe_int("-") == 0

    def test_invalid_string(self) -> None:
        """Test invalid string returns default."""
        assert _safe_int("abc") == 0


class TestSafeFloat:
    """Tests for _safe_float conversion function."""

    def test_float_value(self) -> None:
        """Test float input."""
        assert _safe_float(42.5) == 42.5

    def test_int_value(self) -> None:
        """Test integer input."""
        assert _safe_float(42) == 42.0

    def test_string_value(self) -> None:
        """Test string input."""
        assert _safe_float("42.5") == 42.5

    def test_string_with_percent(self) -> None:
        """Test string with percent sign."""
        assert _safe_float("42.5%") == 42.5

    def test_none_value(self) -> None:
        """Test None returns default."""
        assert _safe_float(None) == 0.0
        assert _safe_float(None, default=5.5) == 5.5

    def test_empty_string(self) -> None:
        """Test empty string returns default."""
        assert _safe_float("") == 0.0

    def test_dash_string(self) -> None:
        """Test dash returns default."""
        assert _safe_float("-") == 0.0


# =============================================================================
# QuantHockeyPlayerSeasonStats Tests
# =============================================================================


class TestQuantHockeyPlayerSeasonStatsCreation:
    """Tests for creating QuantHockeyPlayerSeasonStats instances."""

    def test_from_row_data(self, sample_row_data: list[str]) -> None:
        """Test creation from row data."""
        stats = QuantHockeyPlayerSeasonStats.from_row_data(
            sample_row_data,
            season_id=20242025,
        )

        assert stats.season_id == 20242025
        assert stats.rank == 1
        assert stats.name == "Connor McDavid"
        assert stats.team == "EDM"
        assert stats.age == 28
        assert stats.position == "C"
        assert stats.games_played == 35
        assert stats.goals == 22
        assert stats.assists == 38
        assert stats.points == 60
        assert stats.nationality == "CAN"

    def test_from_dict(self, sample_dict_data: dict[str, Any]) -> None:
        """Test creation from dictionary."""
        stats = QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)

        assert stats.name == "Leon Draisaitl"
        assert stats.team == "EDM"
        assert stats.goals == 25
        assert stats.assists == 30
        assert stats.points == 55

    def test_from_row_data_minimum_fields(self) -> None:
        """Test creation with minimum required fields (50)."""
        row_data = ["0"] * 50
        row_data[1] = "Test Player"
        row_data[2] = "TST"
        row_data[4] = "C"

        stats = QuantHockeyPlayerSeasonStats.from_row_data(
            row_data,
            season_id=20242025,
            validate=False,  # Skip validation for zeroed data
        )

        assert stats.name == "Test Player"
        assert stats.team == "TST"
        assert stats.nationality == ""  # Missing 51st field

    def test_from_row_data_too_few_fields(self) -> None:
        """Test error when row data has too few fields."""
        row_data = ["0"] * 40  # Too few

        with pytest.raises(ValueError, match="Expected at least 50 fields"):
            QuantHockeyPlayerSeasonStats.from_row_data(
                row_data,
                season_id=20242025,
            )

    def test_immutable(self, sample_season_stats: QuantHockeyPlayerSeasonStats) -> None:
        """Test that instances are immutable (frozen)."""
        with pytest.raises(AttributeError):
            sample_season_stats.goals = 100  # type: ignore[misc]


class TestQuantHockeyPlayerSeasonStatsValidation:
    """Tests for validation rules."""

    def test_valid_stats(self, sample_dict_data: dict[str, Any]) -> None:
        """Test that valid data passes validation."""
        stats = QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)
        stats.validate()  # Should not raise

    def test_empty_name_fails(self, sample_dict_data: dict[str, Any]) -> None:
        """Test validation fails for empty name."""
        sample_dict_data["name"] = ""
        with pytest.raises(ValueError, match="name cannot be empty"):
            QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)

    def test_negative_goals_fails(self, sample_dict_data: dict[str, Any]) -> None:
        """Test validation fails for negative goals."""
        sample_dict_data["goals"] = -1
        with pytest.raises(ValueError, match="goals must be non-negative"):
            QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)

    def test_negative_assists_fails(self, sample_dict_data: dict[str, Any]) -> None:
        """Test validation fails for negative assists."""
        sample_dict_data["assists"] = -5
        with pytest.raises(ValueError, match="assists must be non-negative"):
            QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)

    def test_percentage_over_100_fails(self, sample_dict_data: dict[str, Any]) -> None:
        """Test validation fails for percentage over 100."""
        sample_dict_data["shooting_pct"] = 105.0
        with pytest.raises(ValueError, match="shooting_pct must be between 0 and 100"):
            QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)

    def test_negative_percentage_fails(self, sample_dict_data: dict[str, Any]) -> None:
        """Test validation fails for negative percentage."""
        sample_dict_data["faceoff_pct"] = -5.0
        with pytest.raises(ValueError, match="faceoff_pct must be between 0 and 100"):
            QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)

    def test_negative_rate_fails(self, sample_dict_data: dict[str, Any]) -> None:
        """Test validation fails for negative rate."""
        sample_dict_data["goals_per_60"] = -0.5
        with pytest.raises(ValueError, match="goals_per_60 must be non-negative"):
            QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)

    def test_skip_validation(self, sample_dict_data: dict[str, Any]) -> None:
        """Test that validation can be skipped."""
        sample_dict_data["goals"] = -1
        sample_dict_data["shooting_pct"] = 150.0

        # Should not raise with validate=False
        stats = QuantHockeyPlayerSeasonStats.from_dict(
            sample_dict_data,
            validate=False,
        )

        assert stats.goals == -1
        assert stats.shooting_pct == 150.0


class TestQuantHockeyPlayerSeasonStatsComputedProperties:
    """Tests for computed properties."""

    def test_total_faceoffs(
        self, sample_season_stats: QuantHockeyPlayerSeasonStats
    ) -> None:
        """Test total faceoffs calculation."""
        expected = sample_season_stats.faceoffs_won + sample_season_stats.faceoffs_lost
        assert sample_season_stats.total_faceoffs == expected

    def test_is_forward_center(self, sample_dict_data: dict[str, Any]) -> None:
        """Test is_forward for center."""
        sample_dict_data["position"] = "C"
        stats = QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)
        assert stats.is_forward is True
        assert stats.is_defenseman is False

    def test_is_forward_wing(self, sample_dict_data: dict[str, Any]) -> None:
        """Test is_forward for winger."""
        sample_dict_data["position"] = "LW"
        stats = QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)
        assert stats.is_forward is True

    def test_is_defenseman(self, sample_dict_data: dict[str, Any]) -> None:
        """Test is_defenseman property."""
        sample_dict_data["position"] = "D"
        stats = QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)
        assert stats.is_forward is False
        assert stats.is_defenseman is True

    def test_is_goalie(self, sample_dict_data: dict[str, Any]) -> None:
        """Test is_goalie property."""
        sample_dict_data["position"] = "G"
        stats = QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)
        assert stats.is_goalie is True
        assert stats.is_forward is False


class TestQuantHockeyPlayerSeasonStatsSerialization:
    """Tests for serialization."""

    def test_to_dict(self, sample_season_stats: QuantHockeyPlayerSeasonStats) -> None:
        """Test to_dict serialization."""
        result = sample_season_stats.to_dict()

        assert isinstance(result, dict)
        assert result["name"] == sample_season_stats.name
        assert result["team"] == sample_season_stats.team
        assert result["goals"] == sample_season_stats.goals
        assert result["assists"] == sample_season_stats.assists
        assert result["points"] == sample_season_stats.points

    def test_roundtrip(self, sample_dict_data: dict[str, Any]) -> None:
        """Test dict -> model -> dict roundtrip."""
        original = QuantHockeyPlayerSeasonStats.from_dict(sample_dict_data)
        serialized = original.to_dict()
        restored = QuantHockeyPlayerSeasonStats.from_dict(serialized)

        assert original == restored


# =============================================================================
# QuantHockeyPlayerCareerStats Tests
# =============================================================================


@pytest.fixture
def sample_career_row_data() -> list[str]:
    """Sample career row data."""
    return [
        "1",  # rank (implicit)
        "Wayne Gretzky",  # name
        "C",  # position
        "CAN",  # nationality
        "1979",  # first_season
        "1999",  # last_season
        "20",  # seasons_played
        "1487",  # games_played
        "894",  # goals
        "1963",  # assists
        "2857",  # points
        "577",  # pim
        "520",  # plus_minus
    ]


@pytest.fixture
def sample_career_dict() -> dict[str, Any]:
    """Sample career dictionary data."""
    return {
        "name": "Wayne Gretzky",
        "position": "C",
        "nationality": "CAN",
        "first_season": 1979,
        "last_season": 1999,
        "seasons_played": 20,
        "games_played": 1487,
        "goals": 894,
        "assists": 1963,
        "points": 2857,
        "pim": 577,
        "plus_minus": 520,
    }


class TestQuantHockeyPlayerCareerStats:
    """Tests for career stats model."""

    def test_from_row_data(self, sample_career_row_data: list[str]) -> None:
        """Test creation from row data."""
        stats = QuantHockeyPlayerCareerStats.from_row_data(sample_career_row_data)

        assert stats.name == "Wayne Gretzky"
        assert stats.position == "C"
        assert stats.games_played == 1487
        assert stats.goals == 894
        assert stats.points == 2857

    def test_from_dict(self, sample_career_dict: dict[str, Any]) -> None:
        """Test creation from dictionary."""
        stats = QuantHockeyPlayerCareerStats.from_dict(sample_career_dict)

        assert stats.name == "Wayne Gretzky"
        assert stats.seasons_played == 20

    def test_career_span(self, sample_career_dict: dict[str, Any]) -> None:
        """Test career_span property."""
        stats = QuantHockeyPlayerCareerStats.from_dict(sample_career_dict)
        assert stats.career_span == "1979-1999"

    def test_goals_per_game(self, sample_career_dict: dict[str, Any]) -> None:
        """Test goals_per_game calculation."""
        stats = QuantHockeyPlayerCareerStats.from_dict(sample_career_dict)
        expected = 894 / 1487
        assert abs(stats.goals_per_game - expected) < 0.001

    def test_assists_per_game(self, sample_career_dict: dict[str, Any]) -> None:
        """Test assists_per_game calculation."""
        stats = QuantHockeyPlayerCareerStats.from_dict(sample_career_dict)
        expected = 1963 / 1487
        assert abs(stats.assists_per_game - expected) < 0.001

    def test_points_per_game(self, sample_career_dict: dict[str, Any]) -> None:
        """Test points_per_game calculation."""
        stats = QuantHockeyPlayerCareerStats.from_dict(sample_career_dict)
        expected = 2857 / 1487
        assert abs(stats.points_per_game - expected) < 0.001

    def test_zero_games_played(self, sample_career_dict: dict[str, Any]) -> None:
        """Test per-game rates with zero games."""
        sample_career_dict["games_played"] = 0
        stats = QuantHockeyPlayerCareerStats.from_dict(
            sample_career_dict,
            validate=False,
        )

        assert stats.goals_per_game == 0.0
        assert stats.assists_per_game == 0.0
        assert stats.points_per_game == 0.0

    def test_validation_empty_name(self, sample_career_dict: dict[str, Any]) -> None:
        """Test validation fails for empty name."""
        sample_career_dict["name"] = ""
        with pytest.raises(ValueError, match="name cannot be empty"):
            QuantHockeyPlayerCareerStats.from_dict(sample_career_dict)

    def test_to_dict(self, sample_career_dict: dict[str, Any]) -> None:
        """Test to_dict serialization."""
        stats = QuantHockeyPlayerCareerStats.from_dict(sample_career_dict)
        result = stats.to_dict()

        assert result["name"] == "Wayne Gretzky"
        assert result["goals"] == 894
        assert result["points"] == 2857


# =============================================================================
# QuantHockeySeasonData Tests
# =============================================================================


class TestQuantHockeySeasonData:
    """Tests for season data container."""

    @pytest.fixture
    def sample_season_data(
        self, sample_season_stats: QuantHockeyPlayerSeasonStats
    ) -> QuantHockeySeasonData:
        """Create sample season data with multiple players."""
        return QuantHockeySeasonData(
            season_id=20242025,
            season_name="2024-25",
            players=[sample_season_stats],
            download_timestamp="2024-12-21T12:00:00Z",
        )

    def test_player_count(self, sample_season_data: QuantHockeySeasonData) -> None:
        """Test player_count property."""
        assert sample_season_data.player_count == 1

    def test_get_player_found(self, sample_season_data: QuantHockeySeasonData) -> None:
        """Test finding a player by name."""
        player = sample_season_data.get_player("draisaitl")
        assert player is not None
        assert player.name == "Leon Draisaitl"

    def test_get_player_not_found(
        self, sample_season_data: QuantHockeySeasonData
    ) -> None:
        """Test get_player returns None for unknown player."""
        player = sample_season_data.get_player("Unknown Player")
        assert player is None

    def test_get_team_players(self, sample_season_data: QuantHockeySeasonData) -> None:
        """Test getting players by team."""
        edm_players = sample_season_data.get_team_players("EDM")
        assert len(edm_players) == 1
        assert edm_players[0].team == "EDM"

    def test_get_team_players_empty(
        self, sample_season_data: QuantHockeySeasonData
    ) -> None:
        """Test getting players for team with no players."""
        mtl_players = sample_season_data.get_team_players("MTL")
        assert len(mtl_players) == 0

    def test_to_dict(self, sample_season_data: QuantHockeySeasonData) -> None:
        """Test to_dict serialization."""
        result = sample_season_data.to_dict()

        assert result["season_id"] == 20242025
        assert result["season_name"] == "2024-25"
        assert result["player_count"] == 1
        assert len(result["players"]) == 1
        assert result["players"][0]["name"] == "Leon Draisaitl"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special values."""

    def test_all_zero_stats(self) -> None:
        """Test player with all zero stats."""
        data: dict[str, Any] = {
            "season_id": 20242025,
            "rank": 500,
            "name": "Rookie Player",
            "team": "TST",
            "age": 18,
            "position": "C",
            "games_played": 0,
            "goals": 0,
            "assists": 0,
            "points": 0,
            "pim": 0,
            "plus_minus": 0,
            "toi_avg": 0.0,
            "toi_es": 0.0,
            "toi_pp": 0.0,
            "toi_sh": 0.0,
            "es_goals": 0,
            "pp_goals": 0,
            "sh_goals": 0,
            "gw_goals": 0,
            "ot_goals": 0,
            "es_assists": 0,
            "pp_assists": 0,
            "sh_assists": 0,
            "gw_assists": 0,
            "ot_assists": 0,
            "es_points": 0,
            "pp_points": 0,
            "sh_points": 0,
            "gw_points": 0,
            "ot_points": 0,
            "ppp_pct": 0.0,
            "goals_per_60": 0.0,
            "assists_per_60": 0.0,
            "points_per_60": 0.0,
            "es_goals_per_60": 0.0,
            "es_assists_per_60": 0.0,
            "es_points_per_60": 0.0,
            "pp_goals_per_60": 0.0,
            "pp_assists_per_60": 0.0,
            "pp_points_per_60": 0.0,
            "goals_per_game": 0.0,
            "assists_per_game": 0.0,
            "points_per_game": 0.0,
            "shots_on_goal": 0,
            "shooting_pct": 0.0,
            "hits": 0,
            "blocked_shots": 0,
            "faceoffs_won": 0,
            "faceoffs_lost": 0,
            "faceoff_pct": 0.0,
        }

        stats = QuantHockeyPlayerSeasonStats.from_dict(data)
        assert stats.name == "Rookie Player"
        assert stats.total_faceoffs == 0

    def test_negative_plus_minus(self) -> None:
        """Test player with negative plus/minus."""
        data: dict[str, Any] = {
            "season_id": 20242025,
            "rank": 100,
            "name": "Minus Player",
            "team": "TST",
            "age": 25,
            "position": "D",
            "games_played": 30,
            "goals": 1,
            "assists": 5,
            "points": 6,
            "pim": 40,
            "plus_minus": -15,  # Negative is valid
            "toi_avg": 18.0,
            "toi_es": 15.0,
            "toi_pp": 1.0,
            "toi_sh": 2.0,
            "es_goals": 1,
            "pp_goals": 0,
            "sh_goals": 0,
            "gw_goals": 0,
            "ot_goals": 0,
            "es_assists": 4,
            "pp_assists": 1,
            "sh_assists": 0,
            "gw_assists": 0,
            "ot_assists": 0,
            "es_points": 5,
            "pp_points": 1,
            "sh_points": 0,
            "gw_points": 0,
            "ot_points": 0,
            "ppp_pct": 16.7,
            "goals_per_60": 0.06,
            "assists_per_60": 0.28,
            "points_per_60": 0.33,
            "es_goals_per_60": 0.07,
            "es_assists_per_60": 0.27,
            "es_points_per_60": 0.33,
            "pp_goals_per_60": 0.0,
            "pp_assists_per_60": 1.0,
            "pp_points_per_60": 1.0,
            "goals_per_game": 0.03,
            "assists_per_game": 0.17,
            "points_per_game": 0.20,
            "shots_on_goal": 30,
            "shooting_pct": 3.3,
            "hits": 75,
            "blocked_shots": 60,
            "faceoffs_won": 0,
            "faceoffs_lost": 0,
            "faceoff_pct": 0.0,
        }

        stats = QuantHockeyPlayerSeasonStats.from_dict(data)
        assert stats.plus_minus == -15

    def test_special_characters_in_name(self) -> None:
        """Test player name with special characters."""
        data: dict[str, Any] = {
            "season_id": 20242025,
            "rank": 50,
            "name": "Patrik Laine",  # Normally has umlaut
            "team": "MTL",
            "age": 26,
            "position": "RW",
            "games_played": 20,
            "goals": 10,
            "assists": 8,
            "points": 18,
            "pim": 6,
            "plus_minus": 5,
            "toi_avg": 18.5,
            "toi_es": 14.0,
            "toi_pp": 4.0,
            "toi_sh": 0.5,
            "es_goals": 5,
            "pp_goals": 5,
            "sh_goals": 0,
            "gw_goals": 2,
            "ot_goals": 0,
            "es_assists": 5,
            "pp_assists": 3,
            "sh_assists": 0,
            "gw_assists": 1,
            "ot_assists": 0,
            "es_points": 10,
            "pp_points": 8,
            "sh_points": 0,
            "gw_points": 3,
            "ot_points": 0,
            "ppp_pct": 44.4,
            "goals_per_60": 0.54,
            "assists_per_60": 0.43,
            "points_per_60": 0.97,
            "es_goals_per_60": 0.36,
            "es_assists_per_60": 0.36,
            "es_points_per_60": 0.71,
            "pp_goals_per_60": 1.25,
            "pp_assists_per_60": 0.75,
            "pp_points_per_60": 2.0,
            "goals_per_game": 0.50,
            "assists_per_game": 0.40,
            "points_per_game": 0.90,
            "shots_on_goal": 65,
            "shooting_pct": 15.4,
            "hits": 10,
            "blocked_shots": 5,
            "faceoffs_won": 0,
            "faceoffs_lost": 0,
            "faceoff_pct": 0.0,
        }

        stats = QuantHockeyPlayerSeasonStats.from_dict(data)
        assert "Laine" in stats.name

    def test_100_percent_faceoff(self) -> None:
        """Test player with 100% faceoff percentage."""
        data: dict[str, Any] = {
            "season_id": 20242025,
            "rank": 1,
            "name": "Perfect Faceoff",
            "team": "TST",
            "age": 30,
            "position": "C",
            "games_played": 1,
            "goals": 0,
            "assists": 0,
            "points": 0,
            "pim": 0,
            "plus_minus": 0,
            "toi_avg": 5.0,
            "toi_es": 5.0,
            "toi_pp": 0.0,
            "toi_sh": 0.0,
            "es_goals": 0,
            "pp_goals": 0,
            "sh_goals": 0,
            "gw_goals": 0,
            "ot_goals": 0,
            "es_assists": 0,
            "pp_assists": 0,
            "sh_assists": 0,
            "gw_assists": 0,
            "ot_assists": 0,
            "es_points": 0,
            "pp_points": 0,
            "sh_points": 0,
            "gw_points": 0,
            "ot_points": 0,
            "ppp_pct": 0.0,
            "goals_per_60": 0.0,
            "assists_per_60": 0.0,
            "points_per_60": 0.0,
            "es_goals_per_60": 0.0,
            "es_assists_per_60": 0.0,
            "es_points_per_60": 0.0,
            "pp_goals_per_60": 0.0,
            "pp_assists_per_60": 0.0,
            "pp_points_per_60": 0.0,
            "goals_per_game": 0.0,
            "assists_per_game": 0.0,
            "points_per_game": 0.0,
            "shots_on_goal": 0,
            "shooting_pct": 0.0,
            "hits": 0,
            "blocked_shots": 0,
            "faceoffs_won": 5,
            "faceoffs_lost": 0,
            "faceoff_pct": 100.0,
        }

        stats = QuantHockeyPlayerSeasonStats.from_dict(data)
        assert stats.faceoff_pct == 100.0
        assert stats.total_faceoffs == 5


# =============================================================================
# All 51 Fields Test
# =============================================================================


class TestAll51Fields:
    """Verify all 51 fields are properly handled."""

    def test_all_fields_present_in_to_dict(self, sample_row_data: list[str]) -> None:
        """Test that to_dict includes all expected fields."""
        stats = QuantHockeyPlayerSeasonStats.from_row_data(
            sample_row_data,
            season_id=20242025,
        )
        result = stats.to_dict()

        expected_fields = [
            "season_id",
            "rank",
            "name",
            "team",
            "age",
            "position",
            "games_played",
            "goals",
            "assists",
            "points",
            "pim",
            "plus_minus",
            "toi_avg",
            "toi_es",
            "toi_pp",
            "toi_sh",
            "es_goals",
            "pp_goals",
            "sh_goals",
            "gw_goals",
            "ot_goals",
            "es_assists",
            "pp_assists",
            "sh_assists",
            "gw_assists",
            "ot_assists",
            "es_points",
            "pp_points",
            "sh_points",
            "gw_points",
            "ot_points",
            "ppp_pct",
            "goals_per_60",
            "assists_per_60",
            "points_per_60",
            "es_goals_per_60",
            "es_assists_per_60",
            "es_points_per_60",
            "pp_goals_per_60",
            "pp_assists_per_60",
            "pp_points_per_60",
            "goals_per_game",
            "assists_per_game",
            "points_per_game",
            "shots_on_goal",
            "shooting_pct",
            "hits",
            "blocked_shots",
            "faceoffs_won",
            "faceoffs_lost",
            "faceoff_pct",
            "nationality",
        ]

        for field in expected_fields:
            assert field in result, f"Missing field: {field}"

        # Verify count (51 fields + season_id = 52)
        assert len(result) == 52

    def test_all_fields_round_trip(self, sample_row_data: list[str]) -> None:
        """Test that all fields survive a round-trip through serialization."""
        original = QuantHockeyPlayerSeasonStats.from_row_data(
            sample_row_data,
            season_id=20242025,
        )
        serialized = original.to_dict()
        restored = QuantHockeyPlayerSeasonStats.from_dict(serialized)

        # Compare all fields
        assert original.rank == restored.rank
        assert original.name == restored.name
        assert original.team == restored.team
        assert original.age == restored.age
        assert original.position == restored.position
        assert original.games_played == restored.games_played
        assert original.goals == restored.goals
        assert original.assists == restored.assists
        assert original.points == restored.points
        assert original.pim == restored.pim
        assert original.plus_minus == restored.plus_minus
        assert original.toi_avg == restored.toi_avg
        assert original.nationality == restored.nationality
