"""NHL data source downloaders.

This package contains downloaders for various NHL data sources:
- nhl_json: Official NHL JSON API (api-web.nhle.com)
- html: NHL HTML game reports (www.nhl.com/scores/htmlreports)
- external: Third-party sources like QuantHockey, DailyFaceoff (future)
"""

from nhl_api.downloaders.sources.html import (
    HTML_DOWNLOADER_CONFIG,
    BaseHTMLDownloader,
    HTMLDownloaderConfig,
)

__all__ = [
    "BaseHTMLDownloader",
    "HTML_DOWNLOADER_CONFIG",
    "HTMLDownloaderConfig",
]
