"""Utility functions and helpers."""

from nhl_api.utils.http_client import (
    ConnectionError,
    ContentType,
    HTTPClient,
    HTTPClientConfig,
    HTTPClientError,
    HTTPResponse,
    TimeoutError,
    create_nhl_api_client,
    create_nhl_html_client,
)
from nhl_api.utils.name_matching import (
    MatchResult,
    PlayerNameMatcher,
    find_best_match,
    name_similarity,
    normalize_name,
)

__all__ = [
    # HTTP Client
    "ConnectionError",
    "ContentType",
    "HTTPClient",
    "HTTPClientConfig",
    "HTTPClientError",
    "HTTPResponse",
    "TimeoutError",
    "create_nhl_api_client",
    "create_nhl_html_client",
    # Name Matching
    "MatchResult",
    "PlayerNameMatcher",
    "find_best_match",
    "name_similarity",
    "normalize_name",
]
