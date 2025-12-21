"""NHL data source downloaders.

This package contains downloaders for various NHL data sources:
- nhl_json: Official NHL JSON API (api-web.nhle.com)
- nhl_stats: NHL Stats REST API (api.nhle.com/stats/rest/en)
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
from nhl_api.downloaders.sources.nhl_stats import (
    NHL_STATS_API_BASE_URL,
    BaseStatsDownloader,
    StatsDownloaderConfig,
)

__all__ = [
    # HTML
    "BaseHTMLDownloader",
    "HTML_DOWNLOADER_CONFIG",
    "HTMLDownloaderConfig",
    # NHL Stats API
    "BaseStatsDownloader",
    "NHL_STATS_API_BASE_URL",
    "StatsDownloaderConfig",
    # DailyFaceoff
    "BaseDailyFaceoffDownloader",
    "DAILYFACEOFF_CONFIG",
    "DailyFaceoffConfig",
    "TEAM_SLUGS",
]
