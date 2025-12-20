"""Base downloader components.

This module provides the foundational components for all downloaders:
- Downloader protocol (interface)
- DownloadResult dataclass
- DownloadStatus enum
- RateLimiter for API request throttling
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

__all__ = [
    "Downloader",
    "DownloadError",
    "DownloadResult",
    "DownloadStatus",
    "RateLimitError",
    "RateLimiter",
    "TokenBucket",
]
