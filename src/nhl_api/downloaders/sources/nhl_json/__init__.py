"""NHL JSON API downloaders.

This package contains downloaders for the NHL's public JSON API
at api-web.nhle.com/v1/.
"""

from nhl_api.downloaders.sources.nhl_json.boxscore import BoxscoreDownloader
from nhl_api.downloaders.sources.nhl_json.schedule import ScheduleDownloader

__all__ = [
    "BoxscoreDownloader",
    "ScheduleDownloader",
]
