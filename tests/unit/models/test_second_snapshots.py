"""Unit tests for second-by-second analytics snapshot models.

Tests cover:
- SecondSnapshot creation and properties
- Player lookup methods
- Situation code calculation
- Serialization
- Module exports

Issue: #259 - Wave 1: Core Pipeline
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nhl_api.models.second_snapshots import (
    SITUATION_3V3,
    SITUATION_4V4,
    SITUATION_4V5,
    SITUATION_5V4,
    SITUATION_5V5,
    SecondSnapshot,
    calculate_situation_code,
    is_power_play_situation,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_snapshot() -> SecondSnapshot:
    """Create a sample second snapshot."""
    return SecondSnapshot(
        snapshot_id=1,
        game_id=2024020500,
        season_id=20242025,
        period=1,
        period_second=300,
        game_second=300,
        situation_code="5v5",
        home_skater_count=5,
        away_skater_count=5,
        home_skater_ids=(8470613, 8471426, 8478445, 8479318, 8480039),
        away_skater_ids=(8475166, 8476454, 8477956, 8478402, 8479337),
        home_goalie_id=8476341,
        away_goalie_id=8477424,
        is_stoppage=False,
        is_power_play=False,
        is_empty_net=False,
        created_at=datetime(2026, 1, 11, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def power_play_snapshot() -> SecondSnapshot:
    """Create a power play snapshot (5v4)."""
    return SecondSnapshot(
        snapshot_id=2,
        game_id=2024020500,
        season_id=20242025,
        period=2,
        period_second=600,
        game_second=1800,
        situation_code="5v4",
        home_skater_count=5,
        away_skater_count=4,
        home_skater_ids=(8470613, 8471426, 8478445, 8479318, 8480039),
        away_skater_ids=(8475166, 8476454, 8477956, 8478402),
        home_goalie_id=8476341,
        away_goalie_id=8477424,
        is_stoppage=False,
        is_power_play=True,
        is_empty_net=False,
    )


@pytest.fixture
def empty_net_snapshot() -> SecondSnapshot:
    """Create an empty net snapshot."""
    return SecondSnapshot(
        snapshot_id=3,
        game_id=2024020500,
        season_id=20242025,
        period=3,
        period_second=1150,
        game_second=3550,
        situation_code="EN6v5",
        home_skater_count=6,
        away_skater_count=5,
        home_skater_ids=(8470613, 8471426, 8478445, 8479318, 8480039, 8475000),
        away_skater_ids=(8475166, 8476454, 8477956, 8478402, 8479337),
        home_goalie_id=None,  # Empty net
        away_goalie_id=8477424,
        is_stoppage=False,
        is_power_play=False,
        is_empty_net=True,
    )


# =============================================================================
# SecondSnapshot Tests
# =============================================================================


class TestSecondSnapshot:
    """Tests for SecondSnapshot dataclass."""

    def test_create_snapshot(self, sample_snapshot: SecondSnapshot) -> None:
        """Test creating a second snapshot."""
        assert sample_snapshot.snapshot_id == 1
        assert sample_snapshot.game_id == 2024020500
        assert sample_snapshot.season_id == 20242025
        assert sample_snapshot.period == 1
        assert sample_snapshot.period_second == 300
        assert sample_snapshot.game_second == 300
        assert sample_snapshot.situation_code == "5v5"

    def test_skater_counts(self, sample_snapshot: SecondSnapshot) -> None:
        """Test skater count fields."""
        assert sample_snapshot.home_skater_count == 5
        assert sample_snapshot.away_skater_count == 5
        assert len(sample_snapshot.home_skater_ids) == 5
        assert len(sample_snapshot.away_skater_ids) == 5

    def test_goalie_fields(self, sample_snapshot: SecondSnapshot) -> None:
        """Test goalie ID fields."""
        assert sample_snapshot.home_goalie_id == 8476341
        assert sample_snapshot.away_goalie_id == 8477424

    def test_empty_net_goalie(self, empty_net_snapshot: SecondSnapshot) -> None:
        """Test empty net has None goalie."""
        assert empty_net_snapshot.home_goalie_id is None
        assert empty_net_snapshot.away_goalie_id == 8477424
        assert empty_net_snapshot.is_empty_net is True

    def test_frozen_immutability(self, sample_snapshot: SecondSnapshot) -> None:
        """Test that SecondSnapshot is frozen (immutable)."""
        with pytest.raises(AttributeError):
            sample_snapshot.snapshot_id = 999  # type: ignore[misc]

    def test_slots_memory_efficiency(self, sample_snapshot: SecondSnapshot) -> None:
        """Test that SecondSnapshot uses slots."""
        assert hasattr(sample_snapshot, "__slots__")


class TestSecondSnapshotProperties:
    """Tests for SecondSnapshot properties."""

    def test_all_skater_ids(self, sample_snapshot: SecondSnapshot) -> None:
        """Test all_skater_ids property."""
        all_skaters = sample_snapshot.all_skater_ids
        assert len(all_skaters) == 10
        # Includes both home and away
        assert 8470613 in all_skaters  # Home
        assert 8475166 in all_skaters  # Away

    def test_all_player_ids(self, sample_snapshot: SecondSnapshot) -> None:
        """Test all_player_ids property includes goalies."""
        all_players = sample_snapshot.all_player_ids
        assert len(all_players) == 12  # 10 skaters + 2 goalies
        assert 8476341 in all_players  # Home goalie
        assert 8477424 in all_players  # Away goalie

    def test_all_player_ids_empty_net(self, empty_net_snapshot: SecondSnapshot) -> None:
        """Test all_player_ids with empty net excludes None goalie."""
        all_players = empty_net_snapshot.all_player_ids
        # 6 home skaters + 5 away skaters + 1 away goalie = 12
        assert len(all_players) == 12
        assert empty_net_snapshot.home_goalie_id is None

    def test_total_skaters(self, sample_snapshot: SecondSnapshot) -> None:
        """Test total_skaters property."""
        assert sample_snapshot.total_skaters == 10

    def test_total_skaters_power_play(
        self, power_play_snapshot: SecondSnapshot
    ) -> None:
        """Test total_skaters during power play."""
        assert power_play_snapshot.total_skaters == 9

    def test_time_display(self, sample_snapshot: SecondSnapshot) -> None:
        """Test time_display property."""
        assert sample_snapshot.time_display == "P1 05:00"

    def test_time_display_period_2(self, power_play_snapshot: SecondSnapshot) -> None:
        """Test time_display for period 2."""
        assert power_play_snapshot.time_display == "P2 10:00"


class TestPlayerLookup:
    """Tests for player lookup methods."""

    def test_is_player_on_ice_home_skater(
        self, sample_snapshot: SecondSnapshot
    ) -> None:
        """Test detecting home skater on ice."""
        assert sample_snapshot.is_player_on_ice(8470613) is True

    def test_is_player_on_ice_away_skater(
        self, sample_snapshot: SecondSnapshot
    ) -> None:
        """Test detecting away skater on ice."""
        assert sample_snapshot.is_player_on_ice(8475166) is True

    def test_is_player_on_ice_home_goalie(
        self, sample_snapshot: SecondSnapshot
    ) -> None:
        """Test detecting home goalie on ice."""
        assert sample_snapshot.is_player_on_ice(8476341) is True

    def test_is_player_on_ice_away_goalie(
        self, sample_snapshot: SecondSnapshot
    ) -> None:
        """Test detecting away goalie on ice."""
        assert sample_snapshot.is_player_on_ice(8477424) is True

    def test_is_player_on_ice_not_found(self, sample_snapshot: SecondSnapshot) -> None:
        """Test player not on ice."""
        assert sample_snapshot.is_player_on_ice(999999) is False

    def test_is_home_player_skater(self, sample_snapshot: SecondSnapshot) -> None:
        """Test is_home_player for skater."""
        assert sample_snapshot.is_home_player(8470613) is True
        assert sample_snapshot.is_home_player(8475166) is False

    def test_is_home_player_goalie(self, sample_snapshot: SecondSnapshot) -> None:
        """Test is_home_player for goalie."""
        assert sample_snapshot.is_home_player(8476341) is True
        assert sample_snapshot.is_home_player(8477424) is False

    def test_is_away_player_skater(self, sample_snapshot: SecondSnapshot) -> None:
        """Test is_away_player for skater."""
        assert sample_snapshot.is_away_player(8475166) is True
        assert sample_snapshot.is_away_player(8470613) is False

    def test_is_away_player_goalie(self, sample_snapshot: SecondSnapshot) -> None:
        """Test is_away_player for goalie."""
        assert sample_snapshot.is_away_player(8477424) is True
        assert sample_snapshot.is_away_player(8476341) is False


class TestToDict:
    """Tests for to_dict serialization."""

    def test_to_dict_basic_fields(self, sample_snapshot: SecondSnapshot) -> None:
        """Test basic fields in to_dict."""
        result = sample_snapshot.to_dict()
        assert result["snapshot_id"] == 1
        assert result["game_id"] == 2024020500
        assert result["season_id"] == 20242025
        assert result["period"] == 1
        assert result["situation_code"] == "5v5"

    def test_to_dict_arrays_as_lists(self, sample_snapshot: SecondSnapshot) -> None:
        """Test that tuple arrays are converted to lists."""
        result = sample_snapshot.to_dict()
        assert isinstance(result["home_skater_ids"], list)
        assert isinstance(result["away_skater_ids"], list)
        assert len(result["home_skater_ids"]) == 5

    def test_to_dict_datetime_serialization(
        self, sample_snapshot: SecondSnapshot
    ) -> None:
        """Test datetime serialization."""
        result = sample_snapshot.to_dict()
        assert result["created_at"] == "2026-01-11T12:00:00+00:00"

    def test_to_dict_none_datetime(self, power_play_snapshot: SecondSnapshot) -> None:
        """Test None datetime serialization."""
        result = power_play_snapshot.to_dict()
        assert result["created_at"] is None


# =============================================================================
# Situation Code Tests
# =============================================================================


class TestCalculateSituationCode:
    """Tests for calculate_situation_code function."""

    def test_even_strength_5v5(self) -> None:
        """Test 5v5 even strength."""
        assert calculate_situation_code(5, 5) == "5v5"

    def test_even_strength_4v4(self) -> None:
        """Test 4v4 even strength."""
        assert calculate_situation_code(4, 4) == "4v4"

    def test_even_strength_3v3(self) -> None:
        """Test 3v3 overtime."""
        assert calculate_situation_code(3, 3) == "3v3"

    def test_power_play_5v4(self) -> None:
        """Test 5v4 power play."""
        assert calculate_situation_code(5, 4) == "5v4"

    def test_power_play_4v5(self) -> None:
        """Test 4v5 (penalty kill)."""
        assert calculate_situation_code(4, 5) == "4v5"

    def test_power_play_5v3(self) -> None:
        """Test 5v3 two-man advantage."""
        assert calculate_situation_code(5, 3) == "5v3"

    def test_empty_net_home(self) -> None:
        """Test empty net for home team (extra attacker)."""
        assert calculate_situation_code(5, 5, home_empty_net=True) == "EN6v5"

    def test_empty_net_away(self) -> None:
        """Test empty net for away team (extra attacker)."""
        assert calculate_situation_code(5, 5, away_empty_net=True) == "5v6EN"

    def test_empty_net_with_power_play(self) -> None:
        """Test empty net during power play."""
        assert calculate_situation_code(5, 4, home_empty_net=True) == "EN6v4"


class TestIsPowerPlaySituation:
    """Tests for is_power_play_situation function."""

    def test_5v5_not_power_play(self) -> None:
        """Test 5v5 is not power play."""
        assert is_power_play_situation("5v5") is False

    def test_4v4_not_power_play(self) -> None:
        """Test 4v4 is not power play."""
        assert is_power_play_situation("4v4") is False

    def test_3v3_not_power_play(self) -> None:
        """Test 3v3 is not power play."""
        assert is_power_play_situation("3v3") is False

    def test_5v4_is_power_play(self) -> None:
        """Test 5v4 is power play."""
        assert is_power_play_situation("5v4") is True

    def test_4v5_is_power_play(self) -> None:
        """Test 4v5 is power play."""
        assert is_power_play_situation("4v5") is True

    def test_5v3_is_power_play(self) -> None:
        """Test 5v3 is power play."""
        assert is_power_play_situation("5v3") is True

    def test_empty_net_not_power_play(self) -> None:
        """Test empty net situations."""
        assert is_power_play_situation("EN6v5") is True  # Uneven numbers
        assert is_power_play_situation("5v6EN") is True

    def test_invalid_format(self) -> None:
        """Test invalid format returns False."""
        assert is_power_play_situation("invalid") is False
        assert is_power_play_situation("") is False
        assert is_power_play_situation("5") is False


# =============================================================================
# Situation Code Constants Tests
# =============================================================================


class TestSituationCodeConstants:
    """Tests for situation code constants."""

    def test_even_strength_constants(self) -> None:
        """Test even strength constants."""
        assert SITUATION_5V5 == "5v5"
        assert SITUATION_4V4 == "4v4"
        assert SITUATION_3V3 == "3v3"

    def test_power_play_constants(self) -> None:
        """Test power play constants."""
        assert SITUATION_5V4 == "5v4"
        assert SITUATION_4V5 == "4v5"


# =============================================================================
# Module Export Tests
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_exports_from_models_init(self) -> None:
        """Test that all expected items are exported from models."""
        from nhl_api.models import (
            SITUATION_3V3,
            SITUATION_4V4,
            SITUATION_4V5,
            SITUATION_5V4,
            SITUATION_5V5,
            SecondSnapshot,
            calculate_situation_code,
            is_power_play_situation,
        )

        assert SecondSnapshot is not None
        assert calculate_situation_code is not None
        assert is_power_play_situation is not None
        assert SITUATION_5V5 == "5v5"
        assert SITUATION_5V4 == "5v4"
        assert SITUATION_4V5 == "4v5"
        assert SITUATION_4V4 == "4v4"
        assert SITUATION_3V3 == "3v3"
