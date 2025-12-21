"""NHL data source downloaders.

This package contains downloaders for various NHL data sources:
- nhl_json: Official NHL JSON API (api-web.nhle.com)
- nhl_stats: NHL Stats REST API (api.nhle.com/stats/rest/en)
- html: NHL HTML game reports (www.nhl.com/scores/htmlreports)
- external: Third-party sources like QuantHockey, DailyFaceoff (future)
"""

from nhl_api.downloaders.sources.html import (
    HTML_DOWNLOADER_CONFIG,
    BaseHTMLDownloader,
    HTMLDownloaderConfig,
)
from nhl_api.downloaders.sources.nhl_stats import (
    NHL_STATS_API_BASE_URL,
    BaseStatsDownloader,
    StatsDownloaderConfig,
)

__all__ = [
    "BaseHTMLDownloader",
    "BaseStatsDownloader",
    "HTML_DOWNLOADER_CONFIG",
    "HTMLDownloaderConfig",
    "NHL_STATS_API_BASE_URL",
    "StatsDownloaderConfig",
]
