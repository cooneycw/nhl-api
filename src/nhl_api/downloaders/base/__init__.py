"""Base downloader components.

This module provides the foundational components for all downloaders:
- Downloader protocol (interface)
- BaseDownloader abstract base class
- DownloadResult dataclass
- DownloadStatus enum
- RateLimiter for API request throttling
- RetryHandler with exponential backoff
"""

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
    DownloadProgress,
    ProgressCallback,
)
from nhl_api.downloaders.base.protocol import (
    Downloader,
    DownloadError,
    DownloadResult,
    DownloadStatus,
    HealthCheckError,
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
    "BaseDownloader",
    "Downloader",
    "DownloaderConfig",
    "DownloadError",
    "DownloadProgress",
    "DownloadResult",
    "DownloadStatus",
    "HealthCheckError",
    "MaxRetriesExceededError",
    "ProgressCallback",
    "RateLimitError",
    "RateLimiter",
    "RetryableError",
    "RetryConfig",
    "RetryHandler",
    "RetryResult",
    "TokenBucket",
]
