"""NHL JSON API downloaders.

This package contains downloaders for the NHL JSON API (api-web.nhle.com/v1/).
"""

from nhl_api.downloaders.sources.nhl_json.boxscore import BoxscoreDownloader

__all__ = [
    "BoxscoreDownloader",
]
