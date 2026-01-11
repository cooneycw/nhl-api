"""NHL JSON API Right Rail Downloader.

Downloads game right rail (sidebar) data from the NHL JSON API, including
TV broadcast info, quick stats, and game context information.

API Endpoint: GET https://api-web.nhle.com/v1/gamecenter/{game_id}/right-rail

Example usage:
    config = RightRailDownloaderConfig()
    async with RightRailDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        right_rail = result.data
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import DownloadError

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com"

# Default rate limit for NHL API (requests per second)
DEFAULT_RATE_LIMIT = 5.0


@dataclass
class RightRailDownloaderConfig(DownloaderConfig):
    """Configuration for the Right Rail Downloader.

    Attributes:
        base_url: Base URL for the NHL API
        requests_per_second: Rate limit for API requests
        max_retries: Maximum retry attempts for failed requests
        retry_base_delay: Initial delay between retries in seconds
        http_timeout: HTTP request timeout in seconds
        health_check_url: URL path for health check endpoint
        include_raw_response: Whether to include raw JSON in results
    """

    base_url: str = NHL_API_BASE_URL
    requests_per_second: float = DEFAULT_RATE_LIMIT
    max_retries: int = 3
    retry_base_delay: float = 1.0
    http_timeout: float = 30.0
    health_check_url: str = "/v1/schedule/now"
    include_raw_response: bool = False


@dataclass(frozen=True, slots=True)
class BroadcastInfo:
    """TV/streaming broadcast information.

    Attributes:
        network: Network name (e.g., "ESPN+", "TNT")
        country_code: Country code (e.g., "US", "CA")
        broadcast_type: Type (national, home, away)
        start_time: Broadcast start time
    """

    network: str
    country_code: str
    broadcast_type: str
    start_time: str | None


@dataclass(frozen=True, slots=True)
class TeamSeasonSeries:
    """Head-to-head season series info.

    Attributes:
        team_id: NHL team ID
        abbrev: Team abbreviation
        wins: Wins in season series
        losses: Losses in season series
        ot_losses: OT losses in season series
    """

    team_id: int
    abbrev: str
    wins: int
    losses: int
    ot_losses: int


@dataclass(frozen=True, slots=True)
class LastGame:
    """Info about last game between teams.

    Attributes:
        game_id: Game ID
        game_date: Date of game
        home_team_abbrev: Home team abbreviation
        away_team_abbrev: Away team abbreviation
        home_score: Home team score
        away_score: Away team score
    """

    game_id: int
    game_date: str
    home_team_abbrev: str
    away_team_abbrev: str
    home_score: int
    away_score: int


@dataclass
class ParsedRightRail:
    """Parsed right rail data.

    Attributes:
        game_id: NHL game ID
        season_id: Season ID
        broadcasts: List of broadcast info
        home_series: Home team season series record
        away_series: Away team season series record
        last_games: List of recent games between teams
        game_info: Additional game context
        raw_data: Raw API response (if include_raw_response=True)
    """

    game_id: int
    season_id: int
    broadcasts: list[BroadcastInfo]
    home_series: TeamSeasonSeries | None
    away_series: TeamSeasonSeries | None
    last_games: list[LastGame]
    game_info: dict[str, Any]
    raw_data: dict[str, Any] | None = None


def _parse_broadcast(broadcast_data: dict[str, Any]) -> BroadcastInfo:
    """Parse a broadcast entry.

    Args:
        broadcast_data: Raw broadcast data from API

    Returns:
        Parsed BroadcastInfo object
    """
    return BroadcastInfo(
        network=broadcast_data.get("network", ""),
        country_code=broadcast_data.get("countryCode", ""),
        broadcast_type=broadcast_data.get("type", ""),
        start_time=broadcast_data.get("startTime"),
    )


def _parse_season_series(
    team_data: dict[str, Any], team_id: int, abbrev: str
) -> TeamSeasonSeries:
    """Parse season series for a team.

    Args:
        team_data: Raw team series data
        team_id: Team ID
        abbrev: Team abbreviation

    Returns:
        Parsed TeamSeasonSeries object
    """
    return TeamSeasonSeries(
        team_id=team_id,
        abbrev=abbrev,
        wins=team_data.get("wins", 0),
        losses=team_data.get("losses", 0),
        ot_losses=team_data.get("otLosses", 0),
    )


def _parse_last_game(game_data: dict[str, Any]) -> LastGame:
    """Parse a last game entry.

    Args:
        game_data: Raw game data

    Returns:
        Parsed LastGame object
    """
    return LastGame(
        game_id=game_data.get("id", 0),
        game_date=game_data.get("gameDate", ""),
        home_team_abbrev=game_data.get("homeTeam", {}).get("abbrev", ""),
        away_team_abbrev=game_data.get("awayTeam", {}).get("abbrev", ""),
        home_score=game_data.get("homeTeam", {}).get("score", 0),
        away_score=game_data.get("awayTeam", {}).get("score", 0),
    )


def _parse_right_rail(
    data: dict[str, Any], include_raw: bool = False
) -> ParsedRightRail:
    """Parse the full right rail response.

    Args:
        data: Raw API response
        include_raw: Whether to include raw data in result

    Returns:
        Parsed ParsedRightRail object
    """
    # Parse broadcasts
    broadcasts = []
    for bc in data.get("broadcasts", []):
        broadcasts.append(_parse_broadcast(bc))

    # Parse season series
    season_series = data.get("seasonSeries", {})
    home_series = None
    away_series = None

    if series_data := season_series.get("series"):
        # Get team info from first entry if available
        if len(series_data) >= 2:
            home_data = series_data[0]
            away_data = series_data[1]
            home_series = _parse_season_series(
                home_data,
                home_data.get("teamId", 0),
                home_data.get("teamAbbrev", ""),
            )
            away_series = _parse_season_series(
                away_data,
                away_data.get("teamId", 0),
                away_data.get("teamAbbrev", ""),
            )

    # Parse last games between teams
    last_games = []
    for game in data.get("seasonSeriesWins", {}).get("games", []):
        last_games.append(_parse_last_game(game))

    # Extract game info
    game_info = {
        "ticketLink": data.get("ticketLink"),
        "ticketText": data.get("ticketText"),
        "gameCenterLink": data.get("gameCenterLink"),
    }

    return ParsedRightRail(
        game_id=data.get("id", 0),
        season_id=data.get("season", 0),
        broadcasts=broadcasts,
        home_series=home_series,
        away_series=away_series,
        last_games=last_games,
        game_info=game_info,
        raw_data=data if include_raw else None,
    )


class RightRailDownloader(BaseDownloader):
    """Downloads NHL game right rail (sidebar) data.

    The right rail contains sidebar content including:
    - TV/streaming broadcast information
    - Season series between teams
    - Recent games between teams
    - Ticket and link information

    Example:
        config = RightRailDownloaderConfig()
        async with RightRailDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)
            right_rail = result.data
    """

    def __init__(
        self,
        config: RightRailDownloaderConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the downloader.

        Args:
            config: Downloader configuration
            **kwargs: Additional arguments passed to BaseDownloader
        """
        if config is None:
            config = RightRailDownloaderConfig()
        self._include_raw = config.include_raw_response
        super().__init__(config, **kwargs)

    @property
    def source_name(self) -> str:
        """Return unique identifier for this source."""
        return "nhl_json_right_rail"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Fetch right rail data for a specific game.

        Args:
            game_id: NHL game ID

        Returns:
            Parsed right rail data as a dictionary

        Raises:
            DownloadError: If the fetch fails
        """
        logger.debug("Fetching right rail for game %d", game_id)

        response = await self._get(f"/v1/gamecenter/{game_id}/right-rail")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch right rail for game {game_id}: HTTP {response.status}",
                source=self.source_name,
                game_id=game_id,
            )

        data = response.json()
        parsed = _parse_right_rail(data, include_raw=self._include_raw)

        return {
            "game_id": parsed.game_id,
            "season_id": parsed.season_id,
            "broadcasts": [
                {
                    "network": b.network,
                    "country_code": b.country_code,
                    "broadcast_type": b.broadcast_type,
                    "start_time": b.start_time,
                }
                for b in parsed.broadcasts
            ],
            "home_series": {
                "team_id": parsed.home_series.team_id,
                "abbrev": parsed.home_series.abbrev,
                "wins": parsed.home_series.wins,
                "losses": parsed.home_series.losses,
                "ot_losses": parsed.home_series.ot_losses,
            }
            if parsed.home_series
            else None,
            "away_series": {
                "team_id": parsed.away_series.team_id,
                "abbrev": parsed.away_series.abbrev,
                "wins": parsed.away_series.wins,
                "losses": parsed.away_series.losses,
                "ot_losses": parsed.away_series.ot_losses,
            }
            if parsed.away_series
            else None,
            "last_games": [
                {
                    "game_id": g.game_id,
                    "game_date": g.game_date,
                    "home_team_abbrev": g.home_team_abbrev,
                    "away_team_abbrev": g.away_team_abbrev,
                    "home_score": g.home_score,
                    "away_score": g.away_score,
                }
                for g in parsed.last_games
            ],
            "game_info": parsed.game_info,
            "raw_data": parsed.raw_data,
        }

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Yield game IDs for a season.

        This downloader relies on the schedule to provide game IDs.

        Args:
            season_id: NHL season ID (e.g., 20242025)

        Yields:
            Game IDs for the season
        """
        from nhl_api.downloaders.sources.nhl_json.schedule import (
            create_schedule_downloader,
        )

        schedule_dl = create_schedule_downloader()
        async with schedule_dl:
            games = await schedule_dl.get_season_schedule(season_id)
            self.set_total_items(len(games))
            for game in games:
                yield game.game_id

    async def get_right_rail(self, game_id: int) -> ParsedRightRail:
        """Get parsed right rail data for a game.

        Convenience method that returns typed data.

        Args:
            game_id: NHL game ID

        Returns:
            Parsed right rail data
        """
        response = await self._get(f"/v1/gamecenter/{game_id}/right-rail")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch right rail for game {game_id}: HTTP {response.status}",
                source=self.source_name,
                game_id=game_id,
            )

        return _parse_right_rail(response.json(), include_raw=self._include_raw)

    async def persist(
        self,
        db: DatabaseService,
        right_rail: ParsedRightRail,
    ) -> int:
        """Persist right rail data to the database.

        Stores broadcast info and season series data.

        Args:
            db: Database service instance
            right_rail: Parsed right rail data

        Returns:
            Number of records upserted
        """
        count = 0

        # Insert broadcasts
        for broadcast in right_rail.broadcasts:
            await db.execute(
                """
                INSERT INTO game_broadcasts (
                    game_id, network, country_code, broadcast_type
                ) VALUES ($1, $2, $3, $4)
                ON CONFLICT (game_id, network, country_code) DO UPDATE SET
                    broadcast_type = EXCLUDED.broadcast_type,
                    updated_at = CURRENT_TIMESTAMP
                """,
                right_rail.game_id,
                broadcast.network,
                broadcast.country_code,
                broadcast.broadcast_type,
            )
            count += 1

        logger.info("Persisted %d records for game %d", count, right_rail.game_id)
        return count


def create_right_rail_downloader(
    *,
    requests_per_second: float = DEFAULT_RATE_LIMIT,
    max_retries: int = 3,
    include_raw_response: bool = False,
) -> RightRailDownloader:
    """Factory function to create a configured RightRailDownloader.

    Args:
        requests_per_second: Rate limit for API calls
        max_retries: Maximum retry attempts
        include_raw_response: Whether to include raw JSON in results

    Returns:
        Configured RightRailDownloader instance
    """
    config = RightRailDownloaderConfig(
        requests_per_second=requests_per_second,
        max_retries=max_retries,
        include_raw_response=include_raw_response,
    )
    return RightRailDownloader(config)
