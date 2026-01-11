"""Unit tests for matchup models.

Tests the PlayerMatchup, ZoneMatchup, and related models.

Issue: #261 - Wave 3: Matchup Analysis
"""

from __future__ import annotations

from nhl_api.models.matchups import (
    GameMatchupSummary,
    MatchupResult,
    MatchupType,
    PlayerMatchup,
    Zone,
    ZoneMatchup,
)


class TestPlayerMatchup:
    """Tests for PlayerMatchup model."""

    def test_basic_creation(self) -> None:
        """Should create matchup with basic attributes."""
        matchup = PlayerMatchup(
            player1_id=8478402,
            player2_id=8477934,
            matchup_type=MatchupType.TEAMMATE,
            toi_seconds=1250,
            game_count=15,
        )

        assert matchup.player1_id == 8477934  # Sorted: lower ID first
        assert matchup.player2_id == 8478402
        assert matchup.matchup_type == MatchupType.TEAMMATE
        assert matchup.toi_seconds == 1250
        assert matchup.game_count == 15

    def test_player_id_ordering(self) -> None:
        """Player IDs should be sorted (lower first)."""
        matchup = PlayerMatchup(
            player1_id=9999999,  # Higher
            player2_id=1111111,  # Lower
            matchup_type=MatchupType.OPPONENT,
        )

        assert matchup.player1_id == 1111111
        assert matchup.player2_id == 9999999

    def test_toi_minutes(self) -> None:
        """Should calculate TOI in minutes."""
        matchup = PlayerMatchup(
            player1_id=1,
            player2_id=2,
            matchup_type=MatchupType.TEAMMATE,
            toi_seconds=900,  # 15 minutes
        )

        assert matchup.toi_minutes == 15.0

    def test_toi_display(self) -> None:
        """Should format TOI as MM:SS."""
        matchup = PlayerMatchup(
            player1_id=1,
            player2_id=2,
            matchup_type=MatchupType.TEAMMATE,
            toi_seconds=905,  # 15:05
        )

        assert matchup.toi_display == "15:05"

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        matchup = PlayerMatchup(
            player1_id=8478402,
            player2_id=8477934,
            matchup_type=MatchupType.TEAMMATE,
            toi_seconds=1250,
            game_count=15,
            situation_breakdown={"5v5": 1000, "5v4": 250},
        )

        data = matchup.to_dict()

        assert data["player1_id"] == 8477934
        assert data["player2_id"] == 8478402
        assert data["matchup_type"] == "teammate"
        assert data["toi_seconds"] == 1250
        assert data["toi_minutes"] == 20.83
        assert data["game_count"] == 15
        assert data["situation_breakdown"] == {"5v5": 1000, "5v4": 250}

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        matchup = PlayerMatchup(
            player1_id=1,
            player2_id=2,
            matchup_type=MatchupType.OPPONENT,
        )

        assert matchup.toi_seconds == 0
        assert matchup.game_count == 0
        assert matchup.situation_breakdown == {}


class TestZoneMatchup:
    """Tests for ZoneMatchup model."""

    def test_basic_creation(self) -> None:
        """Should create zone matchup."""
        matchup = ZoneMatchup(
            player1_id=8478402,
            player2_id=8477934,
            matchup_type=MatchupType.OPPONENT,
            zone=Zone.DEFENSIVE,
            toi_seconds=300,
            event_count=5,
        )

        assert matchup.zone == Zone.DEFENSIVE
        assert matchup.toi_seconds == 300
        assert matchup.event_count == 5

    def test_to_dict(self) -> None:
        """Should serialize with zone."""
        matchup = ZoneMatchup(
            player1_id=1,
            player2_id=2,
            matchup_type=MatchupType.OPPONENT,
            zone=Zone.OFFENSIVE,
            toi_seconds=600,
        )

        data = matchup.to_dict()

        assert data["zone"] == "O"
        assert data["toi_seconds"] == 600
        assert data["toi_minutes"] == 10.0


class TestMatchupResult:
    """Tests for MatchupResult model."""

    def test_basic_creation(self) -> None:
        """Should create result with lists."""
        result = MatchupResult(
            player_id=8478402,
            total_games=20,
        )

        assert result.player_id == 8478402
        assert result.teammates == []
        assert result.opponents == []
        assert result.total_games == 20

    def test_top_teammates(self) -> None:
        """Should return top 5 teammates by TOI."""
        teammates = [
            PlayerMatchup(1, 10, MatchupType.TEAMMATE, toi_seconds=100),
            PlayerMatchup(1, 20, MatchupType.TEAMMATE, toi_seconds=500),
            PlayerMatchup(1, 30, MatchupType.TEAMMATE, toi_seconds=300),
            PlayerMatchup(1, 40, MatchupType.TEAMMATE, toi_seconds=200),
            PlayerMatchup(1, 50, MatchupType.TEAMMATE, toi_seconds=400),
            PlayerMatchup(1, 60, MatchupType.TEAMMATE, toi_seconds=600),
        ]

        result = MatchupResult(player_id=1, teammates=teammates)

        top = result.top_teammates
        assert len(top) == 5
        assert top[0].toi_seconds == 600
        assert top[1].toi_seconds == 500
        assert top[4].toi_seconds == 200

    def test_top_opponents(self) -> None:
        """Should return top 5 opponents by TOI."""
        opponents = [
            PlayerMatchup(1, 100, MatchupType.OPPONENT, toi_seconds=50),
            PlayerMatchup(1, 200, MatchupType.OPPONENT, toi_seconds=150),
        ]

        result = MatchupResult(player_id=1, opponents=opponents)

        top = result.top_opponents
        assert len(top) == 2
        assert top[0].toi_seconds == 150


class TestMatchupType:
    """Tests for MatchupType enum."""

    def test_teammate_value(self) -> None:
        """Teammate value should be 'teammate'."""
        assert MatchupType.TEAMMATE.value == "teammate"

    def test_opponent_value(self) -> None:
        """Opponent value should be 'opponent'."""
        assert MatchupType.OPPONENT.value == "opponent"


class TestGameMatchupSummary:
    """Tests for GameMatchupSummary model."""

    def test_basic_creation(self) -> None:
        """Should create game summary."""
        summary = GameMatchupSummary(
            game_id=2024020500,
            home_team_id=22,
            away_team_id=25,
            matchup_count=100,
        )

        assert summary.game_id == 2024020500
        assert summary.home_team_id == 22
        assert summary.away_team_id == 25
        assert summary.matchup_count == 100
        assert summary.top_matchups == []

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        summary = GameMatchupSummary(
            game_id=2024020500,
            home_team_id=22,
            away_team_id=25,
            matchup_count=50,
            top_matchups=[
                PlayerMatchup(1, 2, MatchupType.OPPONENT, toi_seconds=300),
            ],
        )

        data = summary.to_dict()

        assert data["game_id"] == 2024020500
        assert data["matchup_count"] == 50
        assert len(data["top_matchups"]) == 1
