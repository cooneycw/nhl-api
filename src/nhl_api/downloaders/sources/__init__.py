"""NHL data source downloaders.

This package contains downloaders for various NHL data sources:
- nhl_json: Official NHL JSON API (api-web.nhle.com)
- html: NHL HTML game reports (www.nhl.com/scores/htmlreports)
- dailyfaceoff: DailyFaceoff.com team lineup data
- external: Third-party sources like QuantHockey (future)
"""

from nhl_api.downloaders.sources.dailyfaceoff import (
    DAILYFACEOFF_CONFIG,
    TEAM_SLUGS,
    BaseDailyFaceoffDownloader,
    DailyFaceoffConfig,
)
from nhl_api.downloaders.sources.html import (
    HTML_DOWNLOADER_CONFIG,
    BaseHTMLDownloader,
    HTMLDownloaderConfig,
)

__all__ = [
    # HTML
    "BaseHTMLDownloader",
    "HTML_DOWNLOADER_CONFIG",
    "HTMLDownloaderConfig",
    # DailyFaceoff
    "BaseDailyFaceoffDownloader",
    "DAILYFACEOFF_CONFIG",
    "DailyFaceoffConfig",
    "TEAM_SLUGS",
]
