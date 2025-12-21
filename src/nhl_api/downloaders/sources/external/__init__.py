"""External source downloaders for third-party data.

This package contains base classes and utilities for downloading data
from external (non-NHL) sources like QuantHockey and DailyFaceoff.

External sources require more conservative rate limiting and custom
User-Agent headers to respect third-party site policies.

Subpackages (future):
- quanthockey: QuantHockey historical statistics
- dailyfaceoff: DailyFaceoff lineup and injury data

Example usage:
    from nhl_api.downloaders.sources.external import (
        BaseExternalDownloader,
        ExternalDownloaderConfig,
    )

    class QuantHockeyDownloader(BaseExternalDownloader):
        @property
        def source_name(self) -> str:
            return "quanthockey_stats"

        async def _parse_response(
            self, response: HTTPResponse, context: dict[str, Any]
        ) -> dict[str, Any]:
            # Parse QuantHockey HTML
            ...

    config = ExternalDownloaderConfig(
        base_url="https://www.quanthockey.com",
        requests_per_second=0.5,
    )
    async with QuantHockeyDownloader(config) as downloader:
        result = await downloader.fetch_resource("/stats/page")
"""

from nhl_api.downloaders.sources.external.base_external_downloader import (
    BaseExternalDownloader,
    ContentParsingError,
    ExternalDownloaderConfig,
    ExternalSourceError,
    ValidationError,
)

__all__ = [
    "BaseExternalDownloader",
    "ContentParsingError",
    "ExternalDownloaderConfig",
    "ExternalSourceError",
    "ValidationError",
]
