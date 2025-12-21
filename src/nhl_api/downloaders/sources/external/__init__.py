"""External source downloaders for third-party data.

This package contains base classes and utilities for downloading data
from external (non-NHL) sources like QuantHockey and DailyFaceoff.

External sources require more conservative rate limiting and custom
User-Agent headers to respect third-party site policies.

Subpackages:
- quanthockey: QuantHockey historical statistics
- dailyfaceoff: DailyFaceoff lineup and injury data (future)

Example usage:
    from nhl_api.downloaders.sources.external import (
        QuantHockeyPlayerStatsDownloader,
        QuantHockeyConfig,
    )

    config = QuantHockeyConfig()
    async with QuantHockeyPlayerStatsDownloader(config) as downloader:
        stats = await downloader.download_season(20242025, max_players=100)
        for player in stats:
            print(f"{player.name}: {player.points} points")
"""

from nhl_api.downloaders.sources.external.base_external_downloader import (
    BaseExternalDownloader,
    ContentParsingError,
    ExternalDownloaderConfig,
    ExternalSourceError,
    ValidationError,
)
from nhl_api.downloaders.sources.external.quanthockey import (
    QuantHockeyPlayerStatsDownloader,
)
from nhl_api.downloaders.sources.external.quanthockey.player_stats import (
    QuantHockeyConfig,
)

__all__ = [
    # Base classes
    "BaseExternalDownloader",
    "ContentParsingError",
    "ExternalDownloaderConfig",
    "ExternalSourceError",
    "ValidationError",
    # QuantHockey
    "QuantHockeyConfig",
    "QuantHockeyPlayerStatsDownloader",
]
