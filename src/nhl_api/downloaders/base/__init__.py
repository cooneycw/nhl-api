"""Base downloader components.

This module provides the foundational components for all downloaders:
- Downloader protocol (interface)
- DownloadResult dataclass
- DownloadStatus enum
"""

from nhl_api.downloaders.base.protocol import (
    Downloader,
    DownloadResult,
    DownloadStatus,
)

__all__ = [
    "Downloader",
    "DownloadResult",
    "DownloadStatus",
]
