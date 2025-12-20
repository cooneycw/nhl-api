"""Tests for the RetryHandler module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from nhl_api.downloaders.base.protocol import RateLimitError
from nhl_api.downloaders.base.retry_handler import (
    RETRYABLE_STATUS_CODES,
    MaxRetriesExceededError,
    RetryableError,
    RetryConfig,
    RetryHandler,
    RetryResult,
)


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter_factor == 0.1
        assert config.retryable_status_codes == RETRYABLE_STATUS_CODES

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter_factor=0.2,
        )

        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter_factor == 0.2

    def test_invalid_max_retries(self) -> None:
        """Test that negative max_retries raises ValueError."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            RetryConfig(max_retries=-1)

    def test_zero_max_retries_valid(self) -> None:
        """Test that zero max_retries is valid (no retries)."""
        config = RetryConfig(max_retries=0)
        assert config.max_retries == 0

    def test_invalid_base_delay(self) -> None:
        """Test that non-positive base_delay raises ValueError."""
        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=0)

        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=-1.0)

    def test_invalid_max_delay(self) -> None:
        """Test that max_delay < base_delay raises ValueError."""
        with pytest.raises(ValueError, match="max_delay must be >= base_delay"):
            RetryConfig(base_delay=10.0, max_delay=5.0)

    def test_invalid_exponential_base(self) -> None:
        """Test that exponential_base <= 1 raises ValueError."""
        with pytest.raises(ValueError, match="exponential_base must be > 1"):
            RetryConfig(exponential_base=1.0)

        with pytest.raises(ValueError, match="exponential_base must be > 1"):
            RetryConfig(exponential_base=0.5)

    def test_invalid_jitter_factor(self) -> None:
        """Test that jitter_factor outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="jitter_factor must be between 0 and 1"):
            RetryConfig(jitter_factor=-0.1)

        with pytest.raises(ValueError, match="jitter_factor must be between 0 and 1"):
            RetryConfig(jitter_factor=1.5)

    def test_config_is_frozen(self) -> None:
        """Test that config is immutable."""
        config = RetryConfig()
        with pytest.raises(AttributeError):
            config.max_retries = 10  # type: ignore[misc]


class TestRetryResult:
    """Tests for RetryResult dataclass."""

    def test_successful_result(self) -> None:
        """Test a successful retry result."""
        result = RetryResult(value="success", attempts=1, total_delay=0.0)

        assert result.value == "success"
        assert result.attempts == 1
        assert result.total_delay == 0.0
        assert result.final_error is None
        assert result.is_successful

    def test_failed_result(self) -> None:
        """Test a failed retry result."""
        error = RetryableError("Server error", status_code=500)
        result = RetryResult(
            attempts=4,
            total_delay=7.5,
            final_error=error,
        )

        assert result.value is None
        assert result.attempts == 4
        assert result.total_delay == 7.5
        assert result.final_error is error
        assert not result.is_successful


class TestRetryableError:
    """Tests for RetryableError."""

    def test_basic_error(self) -> None:
        """Test basic retryable error creation."""
        error = RetryableError("Server error", status_code=500)

        assert "Server error" in str(error)
        assert error.status_code == 500
        assert error.retry_after is None

    def test_error_with_retry_after(self) -> None:
        """Test retryable error with Retry-After."""
        error = RetryableError(
            "Rate limited",
            status_code=429,
            retry_after=30.0,
            source="nhl_api",
        )

        assert error.status_code == 429
        assert error.retry_after == 30.0
        assert error.source == "nhl_api"

    def test_error_inheritance(self) -> None:
        """Test that RetryableError inherits from DownloadError."""
        from nhl_api.downloaders.base.protocol import DownloadError

        error = RetryableError("Test", status_code=500)
        assert isinstance(error, DownloadError)


class TestMaxRetriesExceededError:
    """Tests for MaxRetriesExceededError."""

    def test_basic_error(self) -> None:
        """Test basic max retries error."""
        error = MaxRetriesExceededError("Failed", attempts=4)

        assert "Failed" in str(error)
        assert error.attempts == 4
        assert error.last_error is None

    def test_error_with_last_error(self) -> None:
        """Test max retries error with last error."""
        last = RetryableError("Final failure", status_code=503)
        error = MaxRetriesExceededError(
            "All retries failed",
            attempts=4,
            last_error=last,
            source="schedule_downloader",
        )

        assert error.attempts == 4
        assert error.last_error is last
        assert error.source == "schedule_downloader"


class TestRetryHandler:
    """Tests for RetryHandler class."""

    def test_default_config(self) -> None:
        """Test handler uses default config when none provided."""
        handler = RetryHandler()

        assert handler.config.max_retries == 3
        assert handler.config.base_delay == 1.0

    def test_custom_config(self) -> None:
        """Test handler uses provided config."""
        config = RetryConfig(max_retries=5, base_delay=0.5)
        handler = RetryHandler(config)

        assert handler.config.max_retries == 5
        assert handler.config.base_delay == 0.5

    def test_is_retryable_status(self) -> None:
        """Test status code retry detection."""
        handler = RetryHandler()

        # Retryable status codes
        assert handler.is_retryable_status(429) is True
        assert handler.is_retryable_status(500) is True
        assert handler.is_retryable_status(502) is True
        assert handler.is_retryable_status(503) is True
        assert handler.is_retryable_status(504) is True

        # Non-retryable status codes
        assert handler.is_retryable_status(200) is False
        assert handler.is_retryable_status(400) is False
        assert handler.is_retryable_status(401) is False
        assert handler.is_retryable_status(403) is False
        assert handler.is_retryable_status(404) is False

    def test_calculate_delay_basic(self) -> None:
        """Test basic delay calculation without jitter."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter_factor=0.0)
        handler = RetryHandler(config)

        # Without jitter, delay = base_delay * (base ** attempt)
        assert handler.calculate_delay(0) == 1.0  # 1.0 * 2^0 = 1.0
        assert handler.calculate_delay(1) == 2.0  # 1.0 * 2^1 = 2.0
        assert handler.calculate_delay(2) == 4.0  # 1.0 * 2^2 = 4.0
        assert handler.calculate_delay(3) == 8.0  # 1.0 * 2^3 = 8.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Test delay calculation includes jitter."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter_factor=0.1)
        handler = RetryHandler(config)

        # With jitter, delay should be between base and base * 1.1
        with patch("random.random", return_value=0.5):
            delay = handler.calculate_delay(0)
            # delay = 1.0 + (1.0 * 0.1 * 0.5) = 1.05
            assert delay == pytest.approx(1.05)

    def test_calculate_delay_caps_at_max(self) -> None:
        """Test delay is capped at max_delay."""
        config = RetryConfig(
            base_delay=10.0,
            max_delay=20.0,
            exponential_base=2.0,
            jitter_factor=0.0,
        )
        handler = RetryHandler(config)

        # Attempt 2: 10 * 2^2 = 40, but capped at 20
        assert handler.calculate_delay(2) == 20.0

    def test_calculate_delay_respects_retry_after(self) -> None:
        """Test delay uses Retry-After header value."""
        handler = RetryHandler()

        # Server says wait 30 seconds
        assert handler.calculate_delay(0, retry_after=30.0) == 30.0

        # Server says wait 120 seconds, capped at max_delay (60)
        assert handler.calculate_delay(0, retry_after=120.0) == 60.0


@pytest.mark.asyncio
class TestRetryHandlerExecute:
    """Async tests for RetryHandler.execute()."""

    async def test_success_on_first_try(self) -> None:
        """Test successful operation without retries."""
        handler = RetryHandler()
        operation = AsyncMock(return_value="success")

        result = await handler.execute(operation, operation_name="test_op")

        assert result == "success"
        operation.assert_called_once()

    async def test_success_after_retry(self) -> None:
        """Test successful operation after retrying."""
        config = RetryConfig(base_delay=0.01, jitter_factor=0.0)
        handler = RetryHandler(config)

        # Fail twice, then succeed
        operation = AsyncMock(
            side_effect=[
                RetryableError("Error 1", status_code=500),
                RetryableError("Error 2", status_code=503),
                "success",
            ]
        )

        result = await handler.execute(operation, operation_name="test_op")

        assert result == "success"
        assert operation.call_count == 3

    async def test_max_retries_exceeded(self) -> None:
        """Test MaxRetriesExceededError when all retries fail."""
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter_factor=0.0)
        handler = RetryHandler(config)

        operation = AsyncMock(
            side_effect=RetryableError("Always fails", status_code=500)
        )

        with pytest.raises(MaxRetriesExceededError) as exc_info:
            await handler.execute(
                operation, operation_name="failing_op", source="test_source"
            )

        assert exc_info.value.attempts == 3  # Initial + 2 retries
        assert exc_info.value.source == "test_source"
        assert operation.call_count == 3

    async def test_rate_limit_error_triggers_retry(self) -> None:
        """Test that RateLimitError triggers retry."""
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter_factor=0.0)
        handler = RetryHandler(config)

        operation = AsyncMock(
            side_effect=[
                RateLimitError(retry_after=0.01),
                "success",
            ]
        )

        result = await handler.execute(operation)

        assert result == "success"
        assert operation.call_count == 2

    async def test_non_retryable_error_propagates(self) -> None:
        """Test that non-retryable errors propagate immediately."""
        handler = RetryHandler()

        operation = AsyncMock(side_effect=ValueError("Bad input"))

        with pytest.raises(ValueError, match="Bad input"):
            await handler.execute(operation)

        # Should not retry for non-retryable errors
        operation.assert_called_once()

    async def test_zero_retries_fails_immediately(self) -> None:
        """Test that max_retries=0 fails on first error."""
        config = RetryConfig(max_retries=0, base_delay=0.01)
        handler = RetryHandler(config)

        operation = AsyncMock(side_effect=RetryableError("Error", status_code=500))

        with pytest.raises(MaxRetriesExceededError) as exc_info:
            await handler.execute(operation)

        assert exc_info.value.attempts == 1
        operation.assert_called_once()

    async def test_retry_uses_calculated_delay(self) -> None:
        """Test that retries wait for calculated delay."""
        config = RetryConfig(
            max_retries=1,
            base_delay=0.1,
            jitter_factor=0.0,
        )
        handler = RetryHandler(config)

        operation = AsyncMock(
            side_effect=[
                RetryableError("Error", status_code=500),
                "success",
            ]
        )

        with patch.object(asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            await handler.execute(operation)

            # Should have slept for the calculated delay
            mock_sleep.assert_called_once()
            assert mock_sleep.call_args[0][0] == pytest.approx(0.1)


@pytest.mark.asyncio
class TestRetryHandlerExecuteWithResult:
    """Async tests for RetryHandler.execute_with_result()."""

    async def test_success_returns_result(self) -> None:
        """Test successful operation returns RetryResult."""
        handler = RetryHandler()
        operation = AsyncMock(return_value="success")

        result = await handler.execute_with_result(operation)

        assert result.is_successful
        assert result.value == "success"
        assert result.attempts == 1
        assert result.total_delay == 0.0
        assert result.final_error is None

    async def test_failure_returns_result_with_error(self) -> None:
        """Test failed operation returns RetryResult with error."""
        config = RetryConfig(max_retries=1, base_delay=0.01, jitter_factor=0.0)
        handler = RetryHandler(config)

        error = RetryableError("Always fails", status_code=500)
        operation = AsyncMock(side_effect=error)

        result = await handler.execute_with_result(operation)

        assert not result.is_successful
        assert result.value is None
        assert result.attempts == 2
        assert result.final_error is error

    async def test_non_retryable_error_in_result(self) -> None:
        """Test non-retryable error captured in result."""
        handler = RetryHandler()

        error = ValueError("Bad input")
        operation = AsyncMock(side_effect=error)

        result = await handler.execute_with_result(operation)

        assert not result.is_successful
        assert result.attempts == 1
        assert result.final_error is error

    async def test_result_tracks_total_delay(self) -> None:
        """Test that total_delay accumulates across retries."""
        config = RetryConfig(
            max_retries=2,
            base_delay=0.05,
            jitter_factor=0.0,
        )
        handler = RetryHandler(config)

        operation = AsyncMock(
            side_effect=[
                RetryableError("Error", status_code=500),
                RetryableError("Error", status_code=500),
                "success",
            ]
        )

        result = await handler.execute_with_result(operation)

        assert result.is_successful
        assert result.attempts == 3
        # Delays: 0.05 * 2^0 + 0.05 * 2^1 = 0.05 + 0.1 = 0.15
        assert result.total_delay == pytest.approx(0.15)


class TestRetryableStatusCodes:
    """Tests for default retryable status codes."""

    def test_default_retryable_codes(self) -> None:
        """Test that default retryable codes are correct."""
        expected = frozenset({429, 500, 502, 503, 504})
        assert RETRYABLE_STATUS_CODES == expected

    def test_429_is_rate_limit(self) -> None:
        """Test that 429 Too Many Requests is retryable."""
        assert 429 in RETRYABLE_STATUS_CODES

    def test_500_server_errors_retryable(self) -> None:
        """Test that 5xx server errors are retryable."""
        assert 500 in RETRYABLE_STATUS_CODES  # Internal Server Error
        assert 502 in RETRYABLE_STATUS_CODES  # Bad Gateway
        assert 503 in RETRYABLE_STATUS_CODES  # Service Unavailable
        assert 504 in RETRYABLE_STATUS_CODES  # Gateway Timeout

    def test_501_not_implemented_not_retryable(self) -> None:
        """Test that 501 Not Implemented is NOT retryable (intentional)."""
        assert 501 not in RETRYABLE_STATUS_CODES
