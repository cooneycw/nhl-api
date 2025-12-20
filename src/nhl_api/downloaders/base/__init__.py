"""Base downloader components.

This module provides the foundational components for all downloaders:
- Downloader protocol (interface)
- DownloadResult dataclass
- DownloadStatus enum
- RateLimiter for API request throttling
- RetryHandler with exponential backoff
"""

from nhl_api.downloaders.base.protocol import (
    Downloader,
    DownloadError,
    DownloadResult,
    DownloadStatus,
    RateLimitError,
)
from nhl_api.downloaders.base.rate_limiter import (
    RateLimiter,
    TokenBucket,
)
from nhl_api.downloaders.base.retry_handler import (
    MaxRetriesExceededError,
    RetryableError,
    RetryConfig,
    RetryHandler,
    RetryResult,
)

__all__ = [
    "Downloader",
    "DownloadError",
    "DownloadResult",
    "DownloadStatus",
    "MaxRetriesExceededError",
    "RateLimitError",
    "RateLimiter",
    "RetryableError",
    "RetryConfig",
    "RetryHandler",
    "RetryResult",
    "TokenBucket",
]
