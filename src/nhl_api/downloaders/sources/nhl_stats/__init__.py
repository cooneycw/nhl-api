"""NHL Stats REST API downloaders.

This package contains downloaders for the NHL Stats REST API
at api.nhle.com/stats/rest/en/. This is a different API from
the main game data API (api-web.nhle.com).

Available data sources:
- Shift Charts: Player shift-by-shift data with start/end times

Key differences from nhl_json:
- Different base URL: api.nhle.com/stats/rest/en
- Uses Cayenne expression query parameters
- Response format: {"data": [...], "total": N}
"""

from nhl_api.downloaders.sources.nhl_stats.base_stats_downloader import (
    DEFAULT_STATS_RATE_LIMIT,
    NHL_STATS_API_BASE_URL,
    BaseStatsDownloader,
    StatsDownloaderConfig,
)
from nhl_api.downloaders.sources.nhl_stats.shift_charts import (
    ShiftChartsDownloader,
    ShiftChartsDownloaderConfig,
    create_shift_charts_downloader,
)

__all__ = [
    "BaseStatsDownloader",
    "DEFAULT_STATS_RATE_LIMIT",
    "NHL_STATS_API_BASE_URL",
    "ShiftChartsDownloader",
    "ShiftChartsDownloaderConfig",
    "StatsDownloaderConfig",
    "create_shift_charts_downloader",
]
