"""Rate limiter for API requests using token bucket algorithm.

This module implements a token bucket rate limiter that supports:
- Configurable requests per second
- Per-domain rate limiting
- Async-compatible (asyncio)
- Burst capacity for handling request spikes

Example usage:
    limiter = RateLimiter(requests_per_second=10.0)

    async with limiter.acquire():
        response = await client.get(url)

    # Or with per-domain limiting:
    limiter = RateLimiter(requests_per_second=5.0, per_domain=True)

    async with limiter.acquire(domain="api.nhl.com"):
        response = await client.get(url)
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    The bucket fills with tokens at a constant rate up to a maximum capacity.
    Each request consumes one token. If no tokens are available, the caller
    must wait until tokens are replenished.

    Attributes:
        capacity: Maximum number of tokens the bucket can hold
        tokens: Current number of tokens available
        refill_rate: Tokens added per second
        last_refill: Timestamp of last refill operation
    """

    capacity: float
    refill_rate: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the bucket with full tokens."""
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def try_consume(self) -> bool:
        """Try to consume one token.

        Returns:
            True if a token was consumed, False if no tokens available.
        """
        self.refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def time_until_available(self) -> float:
        """Calculate time until at least one token is available.

        Returns:
            Seconds to wait, or 0.0 if a token is available now.
        """
        self.refill()
        if self.tokens >= 1.0:
            return 0.0
        tokens_needed = 1.0 - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """Async-compatible rate limiter using token bucket algorithm.

    Supports both global rate limiting and per-domain rate limiting.
    When per_domain is enabled, each domain gets its own token bucket.

    Attributes:
        requests_per_second: Maximum requests allowed per second
        burst_size: Maximum burst capacity (defaults to requests_per_second)
        per_domain: If True, maintain separate limits per domain
    """

    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: float | None = None,
        per_domain: bool = False,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            requests_per_second: Maximum sustained request rate
            burst_size: Maximum burst capacity. Defaults to requests_per_second,
                        allowing brief bursts up to this limit.
            per_domain: If True, maintain separate rate limits per domain
        """
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")

        self.requests_per_second = requests_per_second
        self.burst_size = burst_size if burst_size is not None else requests_per_second
        self.per_domain = per_domain

        # Lock to ensure thread-safe bucket access
        self._lock = asyncio.Lock()

        # Global bucket (used when per_domain is False)
        self._global_bucket = TokenBucket(
            capacity=self.burst_size,
            refill_rate=self.requests_per_second,
        )

        # Per-domain buckets (used when per_domain is True)
        self._domain_buckets: dict[str, TokenBucket] = {}

    def _get_bucket(self, domain: str | None = None) -> TokenBucket:
        """Get the appropriate token bucket.

        Args:
            domain: Domain name for per-domain limiting

        Returns:
            TokenBucket for the given domain or global bucket
        """
        if not self.per_domain or domain is None:
            return self._global_bucket

        if domain not in self._domain_buckets:
            self._domain_buckets[domain] = TokenBucket(
                capacity=self.burst_size,
                refill_rate=self.requests_per_second,
            )
        return self._domain_buckets[domain]

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from a URL.

        Args:
            url: Full URL string

        Returns:
            Domain portion of the URL
        """
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split("/")[0]

    async def wait(self, domain: str | None = None) -> float:
        """Wait until a request is allowed.

        Args:
            domain: Domain name for per-domain limiting, or URL to extract from

        Returns:
            Time waited in seconds
        """
        # Extract domain from URL if provided
        if domain and ("://" in domain or "/" in domain):
            domain = self.extract_domain(domain)

        total_wait = 0.0

        async with self._lock:
            bucket = self._get_bucket(domain)

            while not bucket.try_consume():
                wait_time = bucket.time_until_available()
                if wait_time > 0:
                    total_wait += wait_time
                    # Release lock while sleeping
                    self._lock.release()
                    try:
                        await asyncio.sleep(wait_time)
                    finally:
                        await self._lock.acquire()
                    # Retry consumption after wait

        return total_wait

    @asynccontextmanager
    async def acquire(self, domain: str | None = None) -> AsyncIterator[None]:
        """Context manager for rate-limited operations.

        Usage:
            async with limiter.acquire():
                await make_request()

            # With domain:
            async with limiter.acquire(domain="api.nhl.com"):
                await make_request()

        Args:
            domain: Domain name for per-domain limiting

        Yields:
            None after acquiring permission to proceed
        """
        await self.wait(domain)
        yield

    # Make acquire work as an async context manager
    def __call__(self, domain: str | None = None) -> _RateLimitContext:
        """Allow using limiter as a callable context manager.

        Usage:
            async with limiter("api.nhl.com"):
                await make_request()
        """
        return _RateLimitContext(self, domain)

    @property
    def domain_count(self) -> int:
        """Return the number of tracked domains."""
        return len(self._domain_buckets)

    def get_available_tokens(self, domain: str | None = None) -> float:
        """Get the current number of available tokens.

        Args:
            domain: Domain name for per-domain limiting

        Returns:
            Current token count (may be fractional)
        """
        bucket = self._get_bucket(domain)
        bucket.refill()
        return bucket.tokens

    def reset(self, domain: str | None = None) -> None:
        """Reset a bucket to full capacity.

        Args:
            domain: Domain to reset, or None for global bucket.
                   If per_domain is True and domain is None, resets all buckets.
        """
        if domain is not None:
            bucket = self._get_bucket(domain)
            bucket.tokens = bucket.capacity
            bucket.last_refill = time.monotonic()
        elif self.per_domain:
            # Reset all domain buckets
            for bucket in self._domain_buckets.values():
                bucket.tokens = bucket.capacity
                bucket.last_refill = time.monotonic()
        else:
            # Reset global bucket
            self._global_bucket.tokens = self._global_bucket.capacity
            self._global_bucket.last_refill = time.monotonic()


class _RateLimitContext:
    """Async context manager wrapper for rate limiter."""

    def __init__(self, limiter: RateLimiter, domain: str | None = None) -> None:
        self._limiter = limiter
        self._domain = domain

    async def __aenter__(self) -> None:
        await self._limiter.wait(self._domain)

    async def __aexit__(self, *args: object) -> None:
        pass
