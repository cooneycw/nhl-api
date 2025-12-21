"""Integration tests for DailyFaceoff downloaders.

These tests hit the live dailyfaceoff.com website and verify that:
1. Downloaders can fetch real data
2. Parsed data structures match expected schemas
3. Rate limiting is respected
4. Error handling works correctly

Run with: pytest tests/integration/downloaders/dailyfaceoff -v -m integration

Skip in CI with: pytest -m "not integration"
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from nhl_api.downloaders.base.protocol import DownloadStatus
from nhl_api.downloaders.sources.dailyfaceoff import (
    InjuryDownloader,
    LineCombinationsDownloader,
    PenaltyKillDownloader,
    PowerPlayDownloader,
    StartingGoaliesDownloader,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.dailyfaceoff import DailyFaceoffConfig


# Skip all tests in this module if not running integration tests
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]


# =============================================================================
# Line Combinations Tests
# =============================================================================


class TestLineCombinationsIntegration:
    """Integration tests for LineCombinationsDownloader."""

    @pytest.mark.asyncio
    async def test_download_single_team(
        self,
        line_combinations_downloader: LineCombinationsDownloader,
        test_team_id: int,
        test_team_abbrev: str,
    ) -> None:
        """Test downloading line combinations for a single team."""
        async with line_combinations_downloader:
            result = await line_combinations_downloader.download_team(test_team_id)

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "dailyfaceoff_line_combinations"
        assert result.data["team_id"] == test_team_id
        assert result.data["team_abbreviation"] == test_team_abbrev

        # Verify data structure
        assert "forward_lines" in result.data
        assert "defensive_pairs" in result.data
        assert "goalies" in result.data
        assert "fetched_at" in result.data

    @pytest.mark.asyncio
    async def test_forward_lines_structure(
        self,
        line_combinations_downloader: LineCombinationsDownloader,
        test_team_id: int,
    ) -> None:
        """Verify forward lines have expected structure."""
        async with line_combinations_downloader:
            result = await line_combinations_downloader.download_team(test_team_id)

        forward_lines = result.data.get("forward_lines", [])
        # Teams should have at least 2-4 forward lines
        assert len(forward_lines) >= 1

        for line in forward_lines:
            assert "line_number" in line
            assert line["line_number"] >= 1
            # Each line should have LW, C, RW positions
            assert "left_wing" in line
            assert "center" in line
            assert "right_wing" in line


# =============================================================================
# Power Play Tests
# =============================================================================


class TestPowerPlayIntegration:
    """Integration tests for PowerPlayDownloader."""

    @pytest.mark.asyncio
    async def test_download_single_team(
        self,
        power_play_downloader: PowerPlayDownloader,
        test_team_id: int,
    ) -> None:
        """Test downloading power play units for a single team."""
        async with power_play_downloader:
            result = await power_play_downloader.download_team(test_team_id)

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "dailyfaceoff_power_play"

        # Verify data structure
        assert "pp1" in result.data or "pp2" in result.data
        assert "fetched_at" in result.data

    @pytest.mark.asyncio
    async def test_power_play_unit_structure(
        self,
        power_play_downloader: PowerPlayDownloader,
        test_team_id: int,
    ) -> None:
        """Verify PP units have expected structure."""
        async with power_play_downloader:
            result = await power_play_downloader.download_team(test_team_id)

        pp1 = result.data.get("pp1")
        if pp1:
            assert "unit_number" in pp1
            assert pp1["unit_number"] == 1
            assert "players" in pp1
            # PP units typically have 5 players
            if pp1["players"]:
                player = pp1["players"][0]
                assert "name" in player
                assert "player_id" in player


# =============================================================================
# Penalty Kill Tests
# =============================================================================


class TestPenaltyKillIntegration:
    """Integration tests for PenaltyKillDownloader."""

    @pytest.mark.asyncio
    async def test_download_single_team(
        self,
        penalty_kill_downloader: PenaltyKillDownloader,
        test_team_id: int,
    ) -> None:
        """Test downloading penalty kill units for a single team."""
        async with penalty_kill_downloader:
            result = await penalty_kill_downloader.download_team(test_team_id)

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "dailyfaceoff_penalty_kill"

        # Verify data structure
        assert "pk1" in result.data or "pk2" in result.data
        assert "fetched_at" in result.data


# =============================================================================
# Injury Tests
# =============================================================================


class TestInjuryIntegration:
    """Integration tests for InjuryDownloader."""

    @pytest.mark.asyncio
    async def test_download_team_injuries(
        self,
        injury_downloader: InjuryDownloader,
        test_team_id: int,
        test_team_abbrev: str,
    ) -> None:
        """Test downloading injuries for a single team."""
        async with injury_downloader:
            result = await injury_downloader.download_team(test_team_id)

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "dailyfaceoff_injuries"
        assert result.data["team_id"] == test_team_id

        # Verify data structure
        assert "injuries" in result.data
        assert "fetched_at" in result.data

    @pytest.mark.asyncio
    async def test_download_league_injuries(
        self,
        injury_downloader: InjuryDownloader,
    ) -> None:
        """Test downloading league-wide injuries."""
        async with injury_downloader:
            result = await injury_downloader.download_league_injuries()

        assert result.status == DownloadStatus.COMPLETED

        # Verify data structure
        assert "injuries" in result.data

        # Verify injury record structure if any injuries exist
        injuries = result.data.get("injuries", [])
        if injuries:
            injury = injuries[0]
            assert "player_name" in injury
            assert "team_abbreviation" in injury


# =============================================================================
# Starting Goalies Tests
# =============================================================================


class TestStartingGoaliesIntegration:
    """Integration tests for StartingGoaliesDownloader."""

    @pytest.mark.asyncio
    async def test_download_tonight(
        self,
        starting_goalies_downloader: StartingGoaliesDownloader,
    ) -> None:
        """Test downloading tonight's starting goalies."""
        async with starting_goalies_downloader:
            result = await starting_goalies_downloader.download_tonight()

        assert result.status == DownloadStatus.COMPLETED
        assert result.source == "dailyfaceoff_starting_goalies"

        # Verify data structure
        assert "starts" in result.data
        assert "fetched_at" in result.data
        assert "game_count" in result.data

    @pytest.mark.asyncio
    async def test_goalie_start_structure(
        self,
        starting_goalies_downloader: StartingGoaliesDownloader,
    ) -> None:
        """Verify goalie starts have expected structure."""
        async with starting_goalies_downloader:
            result = await starting_goalies_downloader.download_tonight()

        starts = result.data.get("starts", [])
        # There may be no games on some days
        if starts:
            start = starts[0]
            # Required fields
            assert "goalie_name" in start
            assert "goalie_id" in start
            assert "team_abbreviation" in start
            assert "opponent_abbreviation" in start
            assert "game_time" in start
            assert "status" in start
            assert "is_home" in start

            # Status should be a valid value
            assert start["status"] in ["confirmed", "likely", "unconfirmed"]

    @pytest.mark.asyncio
    async def test_goalie_stats_present(
        self,
        starting_goalies_downloader: StartingGoaliesDownloader,
    ) -> None:
        """Verify goalie stats are included when available."""
        async with starting_goalies_downloader:
            result = await starting_goalies_downloader.download_tonight()

        starts = result.data.get("starts", [])
        if starts:
            # Verify the stat fields exist in the response
            start = starts[0]
            assert "wins" in start
            assert "losses" in start
            assert "save_pct" in start
            assert "gaa" in start


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests verifying rate limiting is respected."""

    @pytest.mark.asyncio
    async def test_rate_limiting_respected(
        self,
        dailyfaceoff_config: DailyFaceoffConfig,
    ) -> None:
        """Verify rate limiting is applied between requests.

        With 0.5 req/sec, two requests should take at least 2 seconds.
        """
        downloader = LineCombinationsDownloader(dailyfaceoff_config)

        start_time = time.monotonic()

        async with downloader:
            # Make two requests
            await downloader.download_team(10)  # Toronto
            await downloader.download_team(6)  # Boston

        elapsed = time.monotonic() - start_time

        # At 0.5 req/sec, 2 requests should take at least 2 seconds
        # Allow some tolerance for processing time
        assert elapsed >= 1.5, f"Requests completed too quickly: {elapsed:.2f}s"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_team_id_handled(
        self,
        line_combinations_downloader: LineCombinationsDownloader,
    ) -> None:
        """Test handling of invalid team ID."""
        async with line_combinations_downloader:
            # Team ID 999 doesn't exist
            with pytest.raises(KeyError):
                await line_combinations_downloader.download_team(999)


# =============================================================================
# Cross-Downloader Tests
# =============================================================================


class TestCrossDownloaderConsistency:
    """Tests verifying data consistency across downloaders."""

    @pytest.mark.asyncio
    async def test_same_team_different_downloaders(
        self,
        dailyfaceoff_config: DailyFaceoffConfig,
        test_team_id: int,
        test_team_abbrev: str,
    ) -> None:
        """Verify team identification is consistent across downloaders."""
        lines_downloader = LineCombinationsDownloader(dailyfaceoff_config)
        pp_downloader = PowerPlayDownloader(dailyfaceoff_config)

        async with lines_downloader, pp_downloader:
            lines_result = await lines_downloader.download_team(test_team_id)
            pp_result = await pp_downloader.download_team(test_team_id)

        # Team identification should be consistent
        assert lines_result.data["team_id"] == pp_result.data.get(
            "team_id", test_team_id
        )
        assert lines_result.data["team_abbreviation"] == pp_result.data.get(
            "team_abbreviation", test_team_abbrev
        )


# =============================================================================
# Bulk Download Tests
# =============================================================================


class TestBulkDownload:
    """Tests for downloading multiple teams."""

    @pytest.mark.asyncio
    async def test_download_multiple_teams(
        self,
        dailyfaceoff_config: DailyFaceoffConfig,
    ) -> None:
        """Test downloading a subset of teams.

        Note: This test is slow due to rate limiting.
        """
        # Only test 2 teams to keep test time reasonable
        team_ids = [10, 6]  # Toronto, Boston

        downloader = LineCombinationsDownloader(
            dailyfaceoff_config,
            team_ids=team_ids,
        )

        results = []
        async with downloader:
            async for result in downloader.download_all_teams():
                results.append(result)

        assert len(results) == 2

        # Verify each result
        for result in results:
            assert result.status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED]
            if result.status == DownloadStatus.COMPLETED:
                assert result.data["team_id"] in team_ids
