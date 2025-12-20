"""NHL API Downloaders package.

This package contains downloaders for various NHL data sources:
- NHL JSON API (api-web.nhle.com)
- NHL HTML Reports (GS, ES, PL, FS, FC, RO, SS, TV, TH)
- NHL Shift Charts API
- QuantHockey (player stats)
- DailyFaceoff (line predictions)
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
