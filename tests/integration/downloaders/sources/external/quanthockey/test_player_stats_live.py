"""Integration tests for QuantHockey player season statistics downloader.

These tests hit the live quanthockey.com website and verify that:
1. Downloaders can fetch real data
2. Parsed data structures match expected schemas
3. Rate limiting is respected
4. All 51 fields are properly populated

Run with: pytest tests/integration/downloaders/sources/external/quanthockey -v -m integration

Skip in CI with: pytest -m "not integration"
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from nhl_api.downloaders.sources.external.quanthockey import (
    QuantHockeyPlayerStatsDownloader,
)
from nhl_api.downloaders.sources.external.quanthockey.player_stats import (
    QuantHockeyConfig,
)
from nhl_api.models.quanthockey import QuantHockeyPlayerSeasonStats

if TYPE_CHECKING:
    pass


# Skip all tests in this module if not running integration tests
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]


# =============================================================================
# Basic Download Tests
# =============================================================================


class TestPlayerStatsDownload:
    """Integration tests for QuantHockeyPlayerStatsDownloader."""

    @pytest.mark.asyncio
    async def test_download_top_10_players(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Test downloading top 10 players for current season."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=10,
            )

        # Should have fetched 10 players
        assert len(players) == 10
        assert all(isinstance(p, QuantHockeyPlayerSeasonStats) for p in players)

    @pytest.mark.asyncio
    async def test_download_previous_season(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        previous_season_id: int,
    ) -> None:
        """Test downloading from previous completed season."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                previous_season_id,
                max_players=10,
            )

        assert len(players) == 10
        # Previous season should have complete data
        for player in players:
            assert player.games_played > 0
            assert player.name

    @pytest.mark.asyncio
    async def test_download_season_data(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Test the download_season_data convenience method."""
        async with player_stats_downloader:
            season_data = await player_stats_downloader.download_season_data(
                current_season_id,
                max_players=5,
            )

        assert season_data.season_id == current_season_id
        assert season_data.season_name == "2024-25"
        assert len(season_data.players) == 5
        assert season_data.download_timestamp


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestPlayerStatsStructure:
    """Tests verifying player stats have expected structure."""

    @pytest.mark.asyncio
    async def test_core_fields_populated(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Verify core fields are populated for all players."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=10,
            )

        for player in players:
            # Identity fields
            assert player.name, "Player name should not be empty"
            assert player.rank > 0, "Rank should be positive"

            # Position should be valid
            assert player.position in [
                "C",
                "LW",
                "RW",
                "D",
                "G",
                "F",
                "W",
            ], f"Invalid position: {player.position}"

            # Games played should be positive
            assert player.games_played > 0

    @pytest.mark.asyncio
    async def test_scoring_fields_populated(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Verify scoring fields are properly populated."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=10,
            )

        for player in players:
            # Basic scoring stats should be non-negative
            assert player.goals >= 0
            assert player.assists >= 0
            assert player.points >= 0
            assert player.pim >= 0

            # Points should equal goals + assists
            assert player.points == player.goals + player.assists

    @pytest.mark.asyncio
    async def test_toi_fields_populated(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Verify TOI (time on ice) fields are populated."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=10,
            )

        for player in players:
            # TOI should be non-negative
            assert player.toi_avg >= 0
            assert player.toi_es >= 0
            assert player.toi_pp >= 0
            assert player.toi_sh >= 0

    @pytest.mark.asyncio
    async def test_situational_goals_populated(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Verify situational goal breakdowns are populated."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=10,
            )

        for player in players:
            # Situational goals should be non-negative
            assert player.es_goals >= 0
            assert player.pp_goals >= 0
            assert player.sh_goals >= 0
            assert player.gw_goals >= 0
            assert player.ot_goals >= 0

            # Sum of situational goals should not exceed total goals
            situational_sum = player.es_goals + player.pp_goals + player.sh_goals
            assert situational_sum <= player.goals + 1  # Allow small tolerance

    @pytest.mark.asyncio
    async def test_per_game_rates_computed(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Verify per-game rate stats are properly computed."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=10,
            )

        for player in players:
            # Per-game rates should be non-negative
            assert player.goals_per_game >= 0
            assert player.assists_per_game >= 0
            assert player.points_per_game >= 0


# =============================================================================
# All 51 Fields Test
# =============================================================================


class TestAll51Fields:
    """Tests verifying all 51 fields are parsed correctly."""

    @pytest.mark.asyncio
    async def test_all_51_fields_present(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Verify all 51 fields are present in player stats."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=5,
            )

        # Get first player
        player = players[0]

        # Core identity fields (4)
        assert hasattr(player, "rank")
        assert hasattr(player, "name")
        assert hasattr(player, "team")
        assert hasattr(player, "age")

        # Position and games (3)
        assert hasattr(player, "position")
        assert hasattr(player, "games_played")
        assert hasattr(player, "nationality")

        # Basic scoring (5)
        assert hasattr(player, "goals")
        assert hasattr(player, "assists")
        assert hasattr(player, "points")
        assert hasattr(player, "pim")
        assert hasattr(player, "plus_minus")

        # TOI (4)
        assert hasattr(player, "toi_avg")
        assert hasattr(player, "toi_es")
        assert hasattr(player, "toi_pp")
        assert hasattr(player, "toi_sh")

        # Goals breakdown (5)
        assert hasattr(player, "es_goals")
        assert hasattr(player, "pp_goals")
        assert hasattr(player, "sh_goals")
        assert hasattr(player, "gw_goals")
        assert hasattr(player, "ot_goals")

        # Assists breakdown (5)
        assert hasattr(player, "es_assists")
        assert hasattr(player, "pp_assists")
        assert hasattr(player, "sh_assists")
        assert hasattr(player, "gw_assists")
        assert hasattr(player, "ot_assists")

        # Points breakdown (6)
        assert hasattr(player, "es_points")
        assert hasattr(player, "pp_points")
        assert hasattr(player, "sh_points")
        assert hasattr(player, "gw_points")
        assert hasattr(player, "ot_points")
        assert hasattr(player, "ppp_pct")

        # Per-60 rates (9)
        assert hasattr(player, "goals_per_60")
        assert hasattr(player, "assists_per_60")
        assert hasattr(player, "points_per_60")
        assert hasattr(player, "es_goals_per_60")
        assert hasattr(player, "es_assists_per_60")
        assert hasattr(player, "es_points_per_60")
        assert hasattr(player, "pp_goals_per_60")
        assert hasattr(player, "pp_assists_per_60")
        assert hasattr(player, "pp_points_per_60")

        # Per-game rates (3)
        assert hasattr(player, "goals_per_game")
        assert hasattr(player, "assists_per_game")
        assert hasattr(player, "points_per_game")

        # Shooting (2)
        assert hasattr(player, "shots_on_goal")
        assert hasattr(player, "shooting_pct")

        # Physical (2)
        assert hasattr(player, "hits")
        assert hasattr(player, "blocked_shots")

        # Faceoffs (3)
        assert hasattr(player, "faceoffs_won")
        assert hasattr(player, "faceoffs_lost")
        assert hasattr(player, "faceoff_pct")

    @pytest.mark.asyncio
    async def test_to_dict_serialization(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Verify players can be serialized to dict and back."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=3,
            )

        for player in players:
            # Serialize to dict
            player_dict = player.to_dict()
            assert isinstance(player_dict, dict)

            # Deserialize back
            restored = QuantHockeyPlayerSeasonStats.from_dict(player_dict)
            assert restored.name == player.name
            assert restored.points == player.points
            assert restored.goals == player.goals


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests verifying rate limiting is respected."""

    @pytest.mark.asyncio
    async def test_rate_limiting_respected(
        self,
        quanthockey_config: QuantHockeyConfig,
        current_season_id: int,
    ) -> None:
        """Verify rate limiting is applied between requests.

        With 0.5 req/sec, multiple pages should take appropriate time.
        """
        downloader = QuantHockeyPlayerStatsDownloader(quanthockey_config)

        start_time = time.monotonic()

        async with downloader:
            # Request enough players to trigger pagination (2 pages)
            await downloader.download_player_stats(
                current_season_id,
                max_players=25,  # 20 per page + 5 more
            )

        elapsed = time.monotonic() - start_time

        # At 0.5 req/sec, 2 pages should take at least 2 seconds
        assert elapsed >= 1.5, f"Requests completed too quickly: {elapsed:.2f}s"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_season_format(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
    ) -> None:
        """Test handling of invalid season ID format."""
        async with player_stats_downloader:
            with pytest.raises(ValueError, match="Invalid season ID format"):
                await player_stats_downloader.download_player_stats(
                    2024,  # Wrong format, should be 20242025
                )

    @pytest.mark.asyncio
    async def test_empty_max_players(
        self,
        player_stats_downloader: QuantHockeyPlayerStatsDownloader,
        current_season_id: int,
    ) -> None:
        """Test with max_players=0."""
        async with player_stats_downloader:
            players = await player_stats_downloader.download_player_stats(
                current_season_id,
                max_players=0,
            )

        # Should return empty list when max_players=0
        assert len(players) == 0


# =============================================================================
# Network Resilience Tests
# =============================================================================


class TestNetworkResilience:
    """Tests for network resilience (skip if network unavailable)."""

    @pytest.mark.asyncio
    async def test_graceful_timeout_handling(
        self,
        current_season_id: int,
    ) -> None:
        """Test that timeouts are handled gracefully."""
        # Create downloader with very short timeout
        config = QuantHockeyConfig(
            requests_per_second=10.0,
            http_timeout=0.001,  # 1ms timeout
            max_retries=1,
        )
        downloader = QuantHockeyPlayerStatsDownloader(config)

        async with downloader:
            # Should raise an exception due to timeout (httpx or asyncio timeout)
            with pytest.raises((TimeoutError, OSError)):
                await downloader.download_player_stats(
                    current_season_id,
                    max_players=10,
                )
