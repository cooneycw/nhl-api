"""Tests for the RateLimiter and TokenBucket."""

from __future__ import annotations

import asyncio
import time

import pytest

from nhl_api.downloaders.base.rate_limiter import (
    RateLimiter,
    TokenBucket,
)


class TestTokenBucket:
    """Tests for TokenBucket dataclass."""

    def test_initial_state(self) -> None:
        """Bucket starts with full tokens."""
        bucket = TokenBucket(capacity=10.0, refill_rate=5.0)

        assert bucket.capacity == 10.0
        assert bucket.refill_rate == 5.0
        assert bucket.tokens == 10.0

    def test_try_consume_success(self) -> None:
        """Consuming a token succeeds when available."""
        bucket = TokenBucket(capacity=5.0, refill_rate=1.0)

        assert bucket.try_consume() is True
        assert bucket.tokens == 4.0

    def test_try_consume_empty(self) -> None:
        """Consuming fails when bucket is empty."""
        bucket = TokenBucket(capacity=2.0, refill_rate=1.0)

        # Drain the bucket
        assert bucket.try_consume() is True
        assert bucket.try_consume() is True
        assert bucket.try_consume() is False

    def test_refill_over_time(self) -> None:
        """Tokens refill based on elapsed time."""
        bucket = TokenBucket(capacity=10.0, refill_rate=100.0)

        # Drain to 0
        bucket.tokens = 0.0
        bucket.last_refill = time.monotonic()

        # Simulate 0.05 seconds passing (should add 5 tokens)
        bucket.last_refill -= 0.05
        bucket.refill()

        assert bucket.tokens == pytest.approx(5.0, abs=0.5)

    def test_refill_caps_at_capacity(self) -> None:
        """Refill doesn't exceed capacity."""
        bucket = TokenBucket(capacity=5.0, refill_rate=10.0)

        # Already at capacity
        bucket.refill()
        assert bucket.tokens == 5.0

        # Even with time passing, cap at capacity
        bucket.last_refill -= 10.0  # Simulate 10 seconds
        bucket.refill()
        assert bucket.tokens == 5.0

    def test_time_until_available_immediate(self) -> None:
        """No wait time when tokens are available."""
        bucket = TokenBucket(capacity=5.0, refill_rate=1.0)

        assert bucket.time_until_available() == 0.0

    def test_time_until_available_empty(self) -> None:
        """Calculate wait time when bucket is empty."""
        bucket = TokenBucket(capacity=5.0, refill_rate=10.0)
        bucket.tokens = 0.0
        bucket.last_refill = time.monotonic()

        # Need 1 token at 10/sec = 0.1 seconds
        wait_time = bucket.time_until_available()
        assert wait_time == pytest.approx(0.1, abs=0.01)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_defaults(self) -> None:
        """Test default initialization."""
        limiter = RateLimiter()

        assert limiter.requests_per_second == 10.0
        assert limiter.burst_size == 10.0
        assert limiter.per_domain is False

    def test_init_custom(self) -> None:
        """Test custom initialization."""
        limiter = RateLimiter(
            requests_per_second=5.0,
            burst_size=20.0,
            per_domain=True,
        )

        assert limiter.requests_per_second == 5.0
        assert limiter.burst_size == 20.0
        assert limiter.per_domain is True

    def test_init_invalid_rate(self) -> None:
        """Negative rate raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            RateLimiter(requests_per_second=0)

        with pytest.raises(ValueError, match="must be positive"):
            RateLimiter(requests_per_second=-1.0)

    def test_extract_domain_full_url(self) -> None:
        """Extract domain from full URL."""
        assert (
            RateLimiter.extract_domain("https://api.nhl.com/v1/schedule")
            == "api.nhl.com"
        )
        assert (
            RateLimiter.extract_domain("http://example.com:8080/path")
            == "example.com:8080"
        )

    def test_extract_domain_simple(self) -> None:
        """Extract domain from simple host string."""
        assert RateLimiter.extract_domain("api.nhl.com") == "api.nhl.com"

    @pytest.mark.asyncio
    async def test_wait_immediate(self) -> None:
        """No wait when tokens available."""
        limiter = RateLimiter(requests_per_second=100.0)

        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start

        assert elapsed < 0.05  # Should be nearly instant

    @pytest.mark.asyncio
    async def test_wait_rate_limited(self) -> None:
        """Wait is enforced when rate limited."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=1.0)

        # First request should be immediate
        await limiter.wait()

        # Second request should wait ~100ms
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start

        assert elapsed >= 0.08  # Should wait ~100ms (with some tolerance)

    @pytest.mark.asyncio
    async def test_acquire_context_manager(self) -> None:
        """Test acquire as async context manager."""
        limiter = RateLimiter(requests_per_second=100.0)

        async with limiter.acquire():
            pass  # Should not raise

    @pytest.mark.asyncio
    async def test_callable_context_manager(self) -> None:
        """Test callable style context manager."""
        limiter = RateLimiter(requests_per_second=100.0)

        async with limiter("api.nhl.com"):
            pass  # Should not raise

    @pytest.mark.asyncio
    async def test_per_domain_limiting(self) -> None:
        """Different domains have separate limits."""
        limiter = RateLimiter(
            requests_per_second=10.0,
            burst_size=1.0,
            per_domain=True,
        )

        # First request to each domain should be immediate
        start = time.monotonic()
        await limiter.wait("api.nhl.com")
        await limiter.wait("stats.nhl.com")
        elapsed = time.monotonic() - start

        assert elapsed < 0.05  # Both should be immediate

        # Second request to first domain should wait
        start = time.monotonic()
        await limiter.wait("api.nhl.com")
        elapsed = time.monotonic() - start

        assert elapsed >= 0.08  # Should wait ~100ms

    @pytest.mark.asyncio
    async def test_per_domain_url_extraction(self) -> None:
        """Domain is extracted from full URLs."""
        limiter = RateLimiter(
            requests_per_second=10.0,
            burst_size=1.0,
            per_domain=True,
        )

        # Both URLs should go to same domain bucket
        await limiter.wait("https://api.nhl.com/v1/schedule")

        start = time.monotonic()
        await limiter.wait("https://api.nhl.com/v1/boxscore")
        elapsed = time.monotonic() - start

        assert elapsed >= 0.08  # Same domain, should wait

    def test_domain_count(self) -> None:
        """Track number of domain buckets."""
        limiter = RateLimiter(per_domain=True)

        assert limiter.domain_count == 0

        limiter._get_bucket("api.nhl.com")
        assert limiter.domain_count == 1

        limiter._get_bucket("stats.nhl.com")
        assert limiter.domain_count == 2

        # Same domain doesn't increase count
        limiter._get_bucket("api.nhl.com")
        assert limiter.domain_count == 2

    def test_get_available_tokens(self) -> None:
        """Get current token count."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=5.0)

        assert limiter.get_available_tokens() == 5.0

    @pytest.mark.asyncio
    async def test_get_available_tokens_after_consume(self) -> None:
        """Token count decreases after consumption."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=5.0)

        await limiter.wait()
        tokens = limiter.get_available_tokens()

        assert tokens == pytest.approx(4.0, abs=0.1)

    def test_reset_global(self) -> None:
        """Reset restores tokens to capacity."""
        limiter = RateLimiter(requests_per_second=10.0, burst_size=5.0)

        # Drain some tokens
        limiter._global_bucket.tokens = 1.0

        limiter.reset()

        assert limiter.get_available_tokens() == 5.0

    def test_reset_per_domain(self) -> None:
        """Reset specific domain bucket."""
        limiter = RateLimiter(per_domain=True, burst_size=5.0)

        # Create and drain domain buckets
        limiter._get_bucket("api.nhl.com").tokens = 1.0
        limiter._get_bucket("stats.nhl.com").tokens = 2.0

        # Reset one domain
        limiter.reset("api.nhl.com")

        assert limiter.get_available_tokens("api.nhl.com") == 5.0
        assert limiter.get_available_tokens("stats.nhl.com") == pytest.approx(
            2.0, abs=0.1
        )

    def test_reset_all_domains(self) -> None:
        """Reset all domain buckets when domain is None."""
        limiter = RateLimiter(per_domain=True, burst_size=5.0)

        # Create and drain domain buckets
        limiter._get_bucket("api.nhl.com").tokens = 1.0
        limiter._get_bucket("stats.nhl.com").tokens = 2.0

        # Reset all
        limiter.reset()

        assert limiter.get_available_tokens("api.nhl.com") == 5.0
        assert limiter.get_available_tokens("stats.nhl.com") == 5.0


class TestRateLimiterConcurrency:
    """Tests for concurrent access to RateLimiter."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self) -> None:
        """Multiple concurrent requests are properly rate limited."""
        limiter = RateLimiter(requests_per_second=20.0, burst_size=5.0)

        start = time.monotonic()

        # Launch 10 concurrent requests
        await asyncio.gather(*[limiter.wait() for _ in range(10)])

        elapsed = time.monotonic() - start

        # First 5 should be immediate (burst), next 5 need ~250ms total
        # (5 tokens / 20 per second = 0.25 seconds)
        assert elapsed >= 0.2
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_concurrent_different_domains(self) -> None:
        """Concurrent requests to different domains don't interfere."""
        limiter = RateLimiter(
            requests_per_second=10.0,
            burst_size=2.0,
            per_domain=True,
        )

        start = time.monotonic()

        # 2 requests each to 3 different domains = 6 total
        await asyncio.gather(
            limiter.wait("domain1.com"),
            limiter.wait("domain1.com"),
            limiter.wait("domain2.com"),
            limiter.wait("domain2.com"),
            limiter.wait("domain3.com"),
            limiter.wait("domain3.com"),
        )

        elapsed = time.monotonic() - start

        # Each domain has burst of 2, so all should be immediate
        assert elapsed < 0.1


class TestTokenBucketEdgeCases:
    """Edge case tests for TokenBucket."""

    def test_fractional_tokens(self) -> None:
        """Handle fractional token values correctly."""
        bucket = TokenBucket(capacity=1.0, refill_rate=10.0)

        # Consume the token
        bucket.try_consume()
        assert bucket.tokens == 0.0

        # Simulate 0.05 seconds (should add 0.5 tokens)
        bucket.last_refill -= 0.05
        bucket.refill()

        assert bucket.tokens == pytest.approx(0.5, abs=0.1)
        assert bucket.try_consume() is False  # Not enough for a full token

    def test_very_high_refill_rate(self) -> None:
        """Handle very high refill rates."""
        bucket = TokenBucket(capacity=1000.0, refill_rate=10000.0)

        bucket.tokens = 0.0
        bucket.last_refill -= 0.01  # 10ms ago

        bucket.refill()

        # Should have refilled ~100 tokens
        assert bucket.tokens == pytest.approx(100.0, abs=10.0)

    def test_very_low_refill_rate(self) -> None:
        """Handle very low refill rates."""
        bucket = TokenBucket(capacity=10.0, refill_rate=0.1)

        bucket.tokens = 0.0
        wait_time = bucket.time_until_available()

        # Need 1 token at 0.1/sec = 10 seconds
        assert wait_time == pytest.approx(10.0, abs=0.1)
