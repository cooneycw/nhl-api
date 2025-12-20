"""Retry handler with exponential backoff for failed requests.

This module provides retry logic for HTTP requests, implementing exponential
backoff with jitter to avoid thundering herd problems when multiple clients
retry simultaneously.

Example usage:
    retry_handler = RetryHandler(max_retries=3, base_delay=1.0)

    async with aiohttp.ClientSession() as session:
        result = await retry_handler.execute(
            lambda: session.get("https://api.nhle.com/v1/schedule"),
            operation_name="fetch_schedule"
        )
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from nhl_api.downloaders.base.protocol import DownloadError, RateLimitError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes that trigger automatic retry
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds before first retry (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        jitter_factor: Random jitter as fraction of delay (default: 0.1)
        retryable_status_codes: HTTP status codes that trigger retry
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.1
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: RETRYABLE_STATUS_CODES
    )

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be positive")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if self.exponential_base <= 1:
            raise ValueError("exponential_base must be > 1")
        if not 0 <= self.jitter_factor <= 1:
            raise ValueError("jitter_factor must be between 0 and 1")


@dataclass
class RetryResult:
    """Result of a retry operation.

    Attributes:
        value: The returned value if successful
        attempts: Total number of attempts made (1 = no retries)
        total_delay: Total time spent waiting between retries
        final_error: The error if all retries failed, None if successful
    """

    value: Any = None
    attempts: int = 1
    total_delay: float = 0.0
    final_error: Exception | None = None

    @property
    def is_successful(self) -> bool:
        """Check if the operation succeeded."""
        return self.final_error is None


class RetryableError(DownloadError):
    """Error that indicates the operation should be retried.

    Raised when an HTTP response has a retryable status code.
    """

    def __init__(
        self,
        message: str,
        status_code: int,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.retry_after = retry_after


class MaxRetriesExceededError(DownloadError):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.attempts = attempts
        self.last_error = last_error


class RetryHandler:
    """Handles retry logic with exponential backoff and jitter.

    This class wraps async operations and automatically retries them on
    transient failures, using exponential backoff to avoid overwhelming
    the server.

    The delay between retries follows this formula:
        delay = base_delay * (exponential_base ** attempt) + random_jitter

    Example:
        handler = RetryHandler(RetryConfig(max_retries=3, base_delay=1.0))

        try:
            result = await handler.execute(fetch_data, operation_name="fetch")
        except MaxRetriesExceededError as e:
            logger.error(f"Failed after {e.attempts} attempts")
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        """Initialize the retry handler.

        Args:
            config: Retry configuration. Uses defaults if not provided.
        """
        self.config = config or RetryConfig()

    def calculate_delay(self, attempt: int, retry_after: float | None = None) -> float:
        """Calculate delay before the next retry attempt.

        Args:
            attempt: Current attempt number (0-indexed)
            retry_after: Server-specified delay from Retry-After header

        Returns:
            Delay in seconds before next retry
        """
        if retry_after is not None:
            # Respect server's Retry-After, but cap at max_delay
            return min(retry_after, self.config.max_delay)

        # Exponential backoff: base_delay * (base ** attempt)
        delay = self.config.base_delay * (self.config.exponential_base**attempt)

        # Add jitter to prevent thundering herd
        jitter = delay * self.config.jitter_factor * random.random()  # noqa: S311
        delay += jitter

        # Cap at max_delay
        return min(delay, self.config.max_delay)

    def is_retryable_status(self, status_code: int) -> bool:
        """Check if an HTTP status code should trigger a retry.

        Args:
            status_code: HTTP response status code

        Returns:
            True if the status code is retryable
        """
        return status_code in self.config.retryable_status_codes

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        operation_name: str = "operation",
        source: str | None = None,
    ) -> T:
        """Execute an async operation with automatic retry on failure.

        Args:
            operation: Async callable to execute
            operation_name: Name for logging purposes
            source: Data source name for error context

        Returns:
            The result of the operation if successful

        Raises:
            MaxRetriesExceededError: If all retry attempts fail
            Exception: Any non-retryable exception from the operation
        """
        last_error: Exception | None = None
        total_delay = 0.0

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await operation()
                if attempt > 0:
                    logger.info(
                        f"{operation_name} succeeded after {attempt + 1} attempts "
                        f"(total delay: {total_delay:.2f}s)"
                    )
                return result

            except RetryableError as e:
                last_error = e
                if attempt >= self.config.max_retries:
                    break

                delay = self.calculate_delay(attempt, e.retry_after)
                total_delay += delay

                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}/"
                    f"{self.config.max_retries + 1}): {e} "
                    f"[status={e.status_code}]. Retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)

            except RateLimitError as e:
                last_error = e
                if attempt >= self.config.max_retries:
                    break

                delay = self.calculate_delay(attempt, e.retry_after)
                total_delay += delay

                logger.warning(
                    f"{operation_name} rate limited (attempt {attempt + 1}/"
                    f"{self.config.max_retries + 1}). Retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)

            except Exception as e:
                # Non-retryable error, propagate immediately
                logger.error(f"{operation_name} failed with non-retryable error: {e}")
                raise

        # All retries exhausted
        raise MaxRetriesExceededError(
            f"{operation_name} failed after {self.config.max_retries + 1} attempts",
            attempts=self.config.max_retries + 1,
            last_error=last_error,
            source=source,
        )

    async def execute_with_result(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        operation_name: str = "operation",
    ) -> RetryResult:
        """Execute an operation and return detailed retry statistics.

        Unlike execute(), this method never raises MaxRetriesExceededError.
        Instead, it returns a RetryResult with the error information.

        Args:
            operation: Async callable to execute
            operation_name: Name for logging purposes

        Returns:
            RetryResult with success/failure status and statistics
        """
        total_delay = 0.0

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await operation()
                return RetryResult(
                    value=result,
                    attempts=attempt + 1,
                    total_delay=total_delay,
                )

            except (RetryableError, RateLimitError) as e:
                if attempt >= self.config.max_retries:
                    return RetryResult(
                        attempts=attempt + 1,
                        total_delay=total_delay,
                        final_error=e,
                    )

                retry_after = getattr(e, "retry_after", None)
                delay = self.calculate_delay(attempt, retry_after)
                total_delay += delay

                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}/"
                    f"{self.config.max_retries + 1}): {e}. Retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)

            except Exception as e:
                # Non-retryable error
                return RetryResult(
                    attempts=attempt + 1,
                    total_delay=total_delay,
                    final_error=e,
                )

        # Should not reach here, but satisfy type checker
        return RetryResult(
            attempts=self.config.max_retries + 1,
            total_delay=total_delay,
            final_error=None,
        )
