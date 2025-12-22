"""Integration tests for QuantHockey career statistics downloader.

These tests hit the live quanthockey.com website and verify that:
1. Downloaders can fetch real career leaders data
2. Parsed data structures match expected schemas
3. Rate limiting is respected
4. Known all-time leaders are correctly identified

Run with: pytest tests/integration/downloaders/sources/external/quanthockey -v -m integration

Skip in CI with: pytest -m "not integration"
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from nhl_api.downloaders.sources.external.quanthockey import (
    QuantHockeyCareerStatsDownloader,
)
from nhl_api.downloaders.sources.external.quanthockey.career_stats import (
    CareerStatCategory,
)
from nhl_api.downloaders.sources.external.quanthockey.player_stats import (
    QuantHockeyConfig,
)
from nhl_api.models.quanthockey import QuantHockeyPlayerCareerStats

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


class TestCareerStatsDownload:
    """Integration tests for QuantHockeyCareerStatsDownloader."""

    @pytest.mark.asyncio
    async def test_download_points_leaders(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
        points_category: CareerStatCategory,
    ) -> None:
        """Test downloading all-time points leaders."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                points_category,
                top_n=10,
            )

        # Should have fetched 10 players
        assert len(leaders) == 10
        assert all(isinstance(p, QuantHockeyPlayerCareerStats) for p in leaders)

    @pytest.mark.asyncio
    async def test_download_goals_leaders(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
        goals_category: CareerStatCategory,
    ) -> None:
        """Test downloading all-time goals leaders."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                goals_category,
                top_n=10,
            )

        assert len(leaders) == 10
        # Goals leaders should have significant goal counts
        for player in leaders:
            assert player.goals > 500  # Top 10 all-time should have 500+ goals

    @pytest.mark.asyncio
    async def test_download_assists_leaders(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Test downloading all-time assists leaders."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.ASSISTS,
                top_n=10,
            )

        assert len(leaders) == 10
        # Assists leaders should have significant assist counts
        for player in leaders:
            assert player.assists > 700  # Top 10 all-time should have 700+ assists


# =============================================================================
# Known Leaders Validation
# =============================================================================


class TestKnownLeaders:
    """Tests verifying known all-time leaders are correctly identified."""

    @pytest.mark.asyncio
    async def test_gretzky_is_points_leader(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Verify Wayne Gretzky is the all-time points leader."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=1,
            )

        assert len(leaders) == 1
        leader = leaders[0]
        assert "Gretzky" in leader.name, f"Expected Gretzky, got {leader.name}"
        assert leader.points >= 2857  # Gretzky's career points

    @pytest.mark.asyncio
    async def test_gretzky_is_goals_leader(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Verify Wayne Gretzky is the all-time goals leader."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.GOALS,
                top_n=1,
            )

        assert len(leaders) == 1
        leader = leaders[0]
        assert "Gretzky" in leader.name, f"Expected Gretzky, got {leader.name}"
        assert leader.goals >= 894  # Gretzky's career goals

    @pytest.mark.asyncio
    async def test_gretzky_is_assists_leader(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Verify Wayne Gretzky is the all-time assists leader."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.ASSISTS,
                top_n=1,
            )

        assert len(leaders) == 1
        leader = leaders[0]
        assert "Gretzky" in leader.name, f"Expected Gretzky, got {leader.name}"
        assert leader.assists >= 1963  # Gretzky's career assists


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestCareerStatsStructure:
    """Tests verifying career stats have expected structure."""

    @pytest.mark.asyncio
    async def test_core_fields_populated(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Verify core fields are populated for all players."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=10,
            )

        for player in leaders:
            # Identity fields
            assert player.name, "Player name should not be empty"

            # Position should be valid
            valid_positions = ["C", "LW", "RW", "D", "G", "F", "W", ""]
            assert player.position in valid_positions, (
                f"Invalid position: {player.position}"
            )

            # Games played should be significant for career leaders
            assert player.games_played > 0

    @pytest.mark.asyncio
    async def test_career_totals_populated(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Verify career total stats are properly populated."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=10,
            )

        for player in leaders:
            # Basic career stats should be non-negative
            assert player.goals >= 0
            assert player.assists >= 0
            assert player.points >= 0
            assert player.pim >= 0

            # Points should equal goals + assists
            assert player.points == player.goals + player.assists

    @pytest.mark.asyncio
    async def test_to_dict_serialization(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Verify players can be serialized to dict and back."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=3,
            )

        for player in leaders:
            # Serialize to dict
            player_dict = player.to_dict()
            assert isinstance(player_dict, dict)

            # Deserialize back
            restored = QuantHockeyPlayerCareerStats.from_dict(player_dict)
            assert restored.name == player.name
            assert restored.points == player.points
            assert restored.goals == player.goals


# =============================================================================
# Multiple Categories Tests
# =============================================================================


class TestMultipleCategories:
    """Tests for downloading multiple categories."""

    @pytest.mark.asyncio
    async def test_different_categories_different_leaders(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Verify different categories return different top 10 lists."""
        async with career_stats_downloader:
            points_leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=10,
            )
            pim_leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.PENALTY_MINUTES,
                top_n=10,
            )

        points_names = {p.name for p in points_leaders}
        pim_names = {p.name for p in pim_leaders}

        # The top 10 in each category should have minimal overlap
        # (enforcers vs scorers)
        overlap = points_names & pim_names
        assert len(overlap) < 5, (
            f"Too much overlap between points and PIM leaders: {overlap}"
        )


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests verifying rate limiting is respected."""

    @pytest.mark.asyncio
    async def test_rate_limiting_respected(
        self,
        quanthockey_config: QuantHockeyConfig,
    ) -> None:
        """Verify rate limiting is applied between requests.

        With 0.5 req/sec, multiple categories should take appropriate time.
        """
        downloader = QuantHockeyCareerStatsDownloader(quanthockey_config)

        start_time = time.monotonic()

        async with downloader:
            # Fetch two different categories
            await downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=10,
            )
            await downloader.download_leaders(
                CareerStatCategory.GOALS,
                top_n=10,
            )

        elapsed = time.monotonic() - start_time

        # At 0.5 req/sec, 2 requests should take at least 2 seconds
        assert elapsed >= 1.5, f"Requests completed too quickly: {elapsed:.2f}s"


# =============================================================================
# Pagination Tests
# =============================================================================


class TestPagination:
    """Tests for pagination handling."""

    @pytest.mark.asyncio
    async def test_pagination_fetches_multiple_pages(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Test fetching more than one page of results."""
        async with career_stats_downloader:
            # Request 25 players (more than 20 per page)
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=25,
            )

        assert len(leaders) == 25

    @pytest.mark.asyncio
    async def test_max_pages_limit(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Test that max_pages limit is respected."""
        async with career_stats_downloader:
            # Request 100 players but limit to 1 page
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=100,
                max_pages=1,
            )

        # Should only get players from first page (20 max)
        assert len(leaders) <= 20


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_zero_top_n(
        self,
        career_stats_downloader: QuantHockeyCareerStatsDownloader,
    ) -> None:
        """Test with top_n=0."""
        async with career_stats_downloader:
            leaders = await career_stats_downloader.download_leaders(
                CareerStatCategory.POINTS,
                top_n=0,
            )

        # Should return empty list
        assert len(leaders) == 0


# =============================================================================
# All Categories Test
# =============================================================================


class TestAllCategories:
    """Tests for all career stat categories."""

    @pytest.mark.asyncio
    async def test_all_categories_work(
        self,
        quanthockey_config: QuantHockeyConfig,
    ) -> None:
        """Verify all category types can be fetched.

        Note: This test is slow due to rate limiting across many categories.
        """
        downloader = QuantHockeyCareerStatsDownloader(quanthockey_config)

        # Test a subset of categories to keep test time reasonable
        categories_to_test = [
            CareerStatCategory.POINTS,
            CareerStatCategory.GOALS,
            CareerStatCategory.GAMES_PLAYED,
        ]

        async with downloader:
            for category in categories_to_test:
                leaders = await downloader.download_leaders(
                    category,
                    top_n=3,
                )
                assert len(leaders) == 3, (
                    f"Failed to fetch 3 leaders for {category.value}"
                )
