"""QuantHockey data source downloaders.

This package provides downloaders for fetching player statistics from
quanthockey.com, including:
- Season-by-season player statistics (51 fields)
- Career/all-time player statistics
"""

from nhl_api.downloaders.sources.external.quanthockey.player_stats import (
    QuantHockeyPlayerStatsDownloader,
)

__all__ = [
    "QuantHockeyPlayerStatsDownloader",
]
