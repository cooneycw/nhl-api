"""Tests for the Downloader protocol and data types."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from nhl_api.downloaders.base.protocol import (
    Downloader,
    DownloadError,
    DownloadResult,
    DownloadStatus,
    HealthCheckError,
    RateLimitError,
)


class TestDownloadStatus:
    """Tests for DownloadStatus enum."""

    def test_status_values(self) -> None:
        """Verify all expected status values exist."""
        assert DownloadStatus.PENDING.value == "pending"
        assert DownloadStatus.DOWNLOADING.value == "downloading"
        assert DownloadStatus.COMPLETED.value == "completed"
        assert DownloadStatus.FAILED.value == "failed"
        assert DownloadStatus.SKIPPED.value == "skipped"

    def test_status_count(self) -> None:
        """Verify the expected number of statuses."""
        assert len(DownloadStatus) == 5


class TestDownloadResult:
    """Tests for DownloadResult dataclass."""

    def test_minimal_result(self) -> None:
        """Test creating a result with required fields only."""
        result = DownloadResult(
            source="test_source",
            season_id=20242025,
            data={"key": "value"},
        )

        assert result.source == "test_source"
        assert result.season_id == 20242025
        assert result.data == {"key": "value"}
        assert result.game_id is None
        assert result.status == DownloadStatus.COMPLETED
        assert result.raw_content is None
        assert result.error_message is None
        assert result.retry_count == 0
        assert result.is_successful
        assert not result.is_game_level

    def test_full_result(self) -> None:
        """Test creating a result with all fields."""
        timestamp = datetime.now(UTC)
        result = DownloadResult(
            source="nhl_json_boxscore",
            season_id=20242025,
            game_id=2024020001,
            data={"homeTeam": {"score": 3}},
            downloaded_at=timestamp,
            status=DownloadStatus.COMPLETED,
            raw_content=b'{"json": "data"}',
            retry_count=1,
        )

        assert result.source == "nhl_json_boxscore"
        assert result.game_id == 2024020001
        assert result.downloaded_at == timestamp
        assert result.raw_content == b'{"json": "data"}'
        assert result.retry_count == 1
        assert result.is_successful
        assert result.is_game_level

    def test_failed_result_gets_default_message(self) -> None:
        """Test that failed results without message get default."""
        result = DownloadResult(
            source="test",
            season_id=20242025,
            data={},
            status=DownloadStatus.FAILED,
        )

        assert result.error_message == "Download failed with no error message"
        assert not result.is_successful

    def test_failed_result_keeps_custom_message(self) -> None:
        """Test that custom error message is preserved."""
        result = DownloadResult(
            source="test",
            season_id=20242025,
            data={},
            status=DownloadStatus.FAILED,
            error_message="Connection timeout",
        )

        assert result.error_message == "Connection timeout"

    def test_result_is_immutable(self) -> None:
        """Test that DownloadResult is frozen (immutable)."""
        result = DownloadResult(
            source="test",
            season_id=20242025,
            data={},
        )

        with pytest.raises(AttributeError):
            result.source = "modified"  # type: ignore[misc]

    def test_downloaded_at_defaults_to_now(self) -> None:
        """Test that downloaded_at defaults to current time."""
        before = datetime.now(UTC)
        result = DownloadResult(source="test", season_id=20242025, data={})
        after = datetime.now(UTC)

        assert before <= result.downloaded_at <= after


class TestDownloaderProtocol:
    """Tests for the Downloader protocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that Downloader protocol can be used with isinstance."""

        # Create a mock implementation
        class MockDownloader:
            @property
            def source_name(self) -> str:
                return "mock"

            async def download_season(
                self, season_id: int, *, force: bool = False
            ) -> AsyncIterator[DownloadResult]:
                yield DownloadResult(
                    source=self.source_name,
                    season_id=season_id,
                    data={},
                )

            async def download_game(self, game_id: int) -> DownloadResult:
                return DownloadResult(
                    source=self.source_name,
                    season_id=20242025,
                    game_id=game_id,
                    data={},
                )

            async def health_check(self) -> bool:
                return True

        downloader = MockDownloader()
        assert isinstance(downloader, Downloader)

    def test_non_downloader_fails_isinstance(self) -> None:
        """Test that non-conforming class fails isinstance check."""

        class NotADownloader:
            pass

        assert not isinstance(NotADownloader(), Downloader)

    def test_partial_implementation_fails(self) -> None:
        """Test that partial implementation fails isinstance check."""

        class PartialDownloader:
            @property
            def source_name(self) -> str:
                return "partial"

            # Missing other required methods

        assert not isinstance(PartialDownloader(), Downloader)


class TestDownloadError:
    """Tests for DownloadError and subclasses."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = DownloadError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.source is None
        assert error.game_id is None
        assert error.cause is None

    def test_error_with_context(self) -> None:
        """Test error with full context."""
        cause = ValueError("Original error")
        error = DownloadError(
            "Failed to download",
            source="nhl_json_boxscore",
            game_id=2024020001,
            cause=cause,
        )

        assert "Failed to download" in str(error)
        assert "nhl_json_boxscore" in str(error)
        assert "2024020001" in str(error)
        assert error.cause is cause

    def test_error_inheritance(self) -> None:
        """Test that DownloadError is a proper exception."""
        with pytest.raises(DownloadError):
            raise DownloadError("Test error")


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_rate_limit_with_retry_after(self) -> None:
        """Test rate limit error with retry timing."""
        error = RateLimitError(retry_after=30.0, source="nhl_api")
        assert error.retry_after == 30.0
        assert "Rate limit exceeded" in str(error)

    def test_rate_limit_inheritance(self) -> None:
        """Test that RateLimitError is a DownloadError."""
        error = RateLimitError()
        assert isinstance(error, DownloadError)


class TestHealthCheckError:
    """Tests for HealthCheckError."""

    def test_health_check_error(self) -> None:
        """Test health check error creation."""
        error = HealthCheckError("Service unavailable", source="nhl_api")
        assert "Service unavailable" in str(error)
        assert error.source == "nhl_api"

    def test_health_check_inheritance(self) -> None:
        """Test that HealthCheckError is a DownloadError."""
        error = HealthCheckError("Test")
        assert isinstance(error, DownloadError)


@pytest.mark.asyncio
class TestDownloaderIntegration:
    """Integration tests for Downloader implementations."""

    async def test_download_season_yields_results(self) -> None:
        """Test that download_season properly yields results."""

        class TestDownloader:
            @property
            def source_name(self) -> str:
                return "test"

            async def download_season(
                self, season_id: int, *, force: bool = False
            ) -> AsyncIterator[DownloadResult]:
                for i in range(3):
                    yield DownloadResult(
                        source=self.source_name,
                        season_id=season_id,
                        game_id=season_id * 1000 + i,
                        data={"game_number": i},
                    )

            async def download_game(self, game_id: int) -> DownloadResult:
                return DownloadResult(
                    source=self.source_name,
                    season_id=20242025,
                    game_id=game_id,
                    data={},
                )

            async def health_check(self) -> bool:
                return True

        downloader = TestDownloader()
        results = [result async for result in downloader.download_season(20242025)]

        assert len(results) == 3
        assert all(r.source == "test" for r in results)
        assert all(r.season_id == 20242025 for r in results)
        assert [r.data["game_number"] for r in results] == [0, 1, 2]

    async def test_download_game_returns_result(self) -> None:
        """Test that download_game returns a proper result."""

        class TestDownloader:
            @property
            def source_name(self) -> str:
                return "test"

            async def download_season(
                self, season_id: int, *, force: bool = False
            ) -> AsyncIterator[DownloadResult]:
                yield DownloadResult(
                    source=self.source_name, season_id=season_id, data={}
                )

            async def download_game(self, game_id: int) -> DownloadResult:
                return DownloadResult(
                    source=self.source_name,
                    season_id=20242025,
                    game_id=game_id,
                    data={"home_score": 3, "away_score": 2},
                )

            async def health_check(self) -> bool:
                return True

        downloader = TestDownloader()
        result = await downloader.download_game(2024020001)

        assert result.game_id == 2024020001
        assert result.data["home_score"] == 3
        assert result.is_game_level
