"""NHL JSON API Player Game Log Downloader.

Downloads game-by-game statistics for individual players from the NHL JSON API.
Supports both skaters and goalies with position-appropriate stat fields.

API Endpoint: GET https://api-web.nhle.com/v1/player/{player_id}/game-log/{season}/{game_type}

Game Types:
    - 2 = Regular season
    - 3 = Playoffs

Example usage:
    config = PlayerGameLogDownloaderConfig()
    async with PlayerGameLogDownloader(config) as downloader:
        result = await downloader.download_player_season(8478402, 20242025, 2)
        for game in result.data.games:
            print(f"{game.game_date}: {game.goals}G {game.assists}A")
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import (
    DownloadResult,
    DownloadStatus,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.base.rate_limiter import RateLimiter
    from nhl_api.downloaders.base.retry_handler import RetryHandler
    from nhl_api.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com"

# Default rate limit for NHL API (requests per second)
DEFAULT_RATE_LIMIT = 5.0

# Game type constants
REGULAR_SEASON = 2
PLAYOFFS = 3


@dataclass
class PlayerGameLogDownloaderConfig(DownloaderConfig):
    """Configuration for the Player Game Log Downloader.

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
class SkaterGameStats:
    """Game statistics for a skater.

    Attributes:
        game_id: Unique game identifier
        game_date: Date of the game
        team_abbrev: Player's team abbreviation
        opponent_abbrev: Opponent team abbreviation
        home_road_flag: 'H' for home, 'R' for road
        goals: Goals scored
        assists: Assists recorded
        points: Total points
        plus_minus: Plus/minus rating
        pim: Penalties in minutes
        shots: Shots on goal
        shifts: Number of shifts played
        toi: Time on ice (MM:SS format)
        power_play_goals: Power play goals
        power_play_points: Power play points
        shorthanded_goals: Shorthanded goals
        shorthanded_points: Shorthanded points
        game_winning_goals: Game-winning goals
        ot_goals: Overtime goals
    """

    game_id: int
    game_date: date
    team_abbrev: str
    opponent_abbrev: str
    home_road_flag: str
    goals: int
    assists: int
    points: int
    plus_minus: int
    pim: int
    shots: int
    shifts: int
    toi: str
    power_play_goals: int
    power_play_points: int
    shorthanded_goals: int
    shorthanded_points: int
    game_winning_goals: int
    ot_goals: int


@dataclass(frozen=True, slots=True)
class GoalieGameStats:
    """Game statistics for a goalie.

    Attributes:
        game_id: Unique game identifier
        game_date: Date of the game
        team_abbrev: Player's team abbreviation
        opponent_abbrev: Opponent team abbreviation
        home_road_flag: 'H' for home, 'R' for road
        games_started: 1 if started, 0 otherwise
        decision: 'W', 'L', 'O' (overtime loss), or None
        shots_against: Total shots faced
        goals_against: Goals allowed
        save_pct: Save percentage
        shutouts: 1 if shutout, 0 otherwise
        toi: Time on ice (MM:SS format)
        goals: Goalie goals scored (rare)
        assists: Goalie assists
        pim: Penalties in minutes
    """

    game_id: int
    game_date: date
    team_abbrev: str
    opponent_abbrev: str
    home_road_flag: str
    games_started: int
    decision: str | None
    shots_against: int
    goals_against: int
    save_pct: float
    shutouts: int
    toi: str
    goals: int
    assists: int
    pim: int


@dataclass(frozen=True, slots=True)
class ParsedPlayerGameLog:
    """Complete game log for a player's season.

    Attributes:
        player_id: NHL player ID
        season_id: Season ID (e.g., 20242025)
        game_type: Game type (2 = regular season, 3 = playoffs)
        is_goalie: Whether this player is a goalie
        games: Tuple of game stats (SkaterGameStats or GoalieGameStats)
    """

    player_id: int
    season_id: int
    game_type: int
    is_goalie: bool
    games: tuple[SkaterGameStats | GoalieGameStats, ...]

    @property
    def game_count(self) -> int:
        """Return number of games in the log."""
        return len(self.games)

    @property
    def total_goals(self) -> int:
        """Return total goals scored across all games."""
        return sum(g.goals for g in self.games)

    @property
    def total_assists(self) -> int:
        """Return total assists across all games."""
        return sum(g.assists for g in self.games)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "player_id": self.player_id,
            "season_id": self.season_id,
            "game_type": self.game_type,
            "is_goalie": self.is_goalie,
            "game_count": self.game_count,
            "games": [self._game_to_dict(g) for g in self.games],
        }

    @staticmethod
    def _game_to_dict(game: SkaterGameStats | GoalieGameStats) -> dict[str, Any]:
        """Convert a game stat to dictionary."""
        result: dict[str, Any] = {
            "game_id": game.game_id,
            "game_date": game.game_date.isoformat(),
            "team_abbrev": game.team_abbrev,
            "opponent_abbrev": game.opponent_abbrev,
            "home_road_flag": game.home_road_flag,
            "goals": game.goals,
            "assists": game.assists,
            "pim": game.pim,
            "toi": game.toi,
        }
        if isinstance(game, SkaterGameStats):
            result.update(
                {
                    "points": game.points,
                    "plus_minus": game.plus_minus,
                    "shots": game.shots,
                    "shifts": game.shifts,
                    "power_play_goals": game.power_play_goals,
                    "power_play_points": game.power_play_points,
                    "shorthanded_goals": game.shorthanded_goals,
                    "shorthanded_points": game.shorthanded_points,
                    "game_winning_goals": game.game_winning_goals,
                    "ot_goals": game.ot_goals,
                }
            )
        else:
            result.update(
                {
                    "games_started": game.games_started,
                    "decision": game.decision,
                    "shots_against": game.shots_against,
                    "goals_against": game.goals_against,
                    "save_pct": game.save_pct,
                    "shutouts": game.shutouts,
                }
            )
        return result


def _parse_date(date_str: str | None) -> date | None:
    """Parse a date string to date object.

    Args:
        date_str: ISO format date string (YYYY-MM-DD)

    Returns:
        Parsed date or None if parsing fails
    """
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        logger.warning("Failed to parse date: %s", date_str)
        return None


def _get_localized(obj: dict[str, Any] | str | None, key: str = "default") -> str:
    """Get localized string from object or return string directly.

    Args:
        obj: Either a dict with localized values or a plain string
        key: The locale key to use (default: 'default')

    Returns:
        The localized string or empty string if not found
    """
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    return str(obj.get(key, ""))


class PlayerGameLogDownloader(BaseDownloader):
    """Downloads player game logs from the NHL JSON API.

    This downloader fetches game-by-game statistics for individual players,
    supporting both skaters and goalies with appropriate stat fields.

    Example:
        config = PlayerGameLogDownloaderConfig()
        async with PlayerGameLogDownloader(config) as downloader:
            # Download single player's season
            result = await downloader.download_player_season(8478402, 20242025, 2)

            # Download all players in batch
            downloader.set_players([
                (8478402, 20242025, 2),  # McDavid regular season
                (8477424, 20242025, 2),  # Saros regular season
            ])
            async for result in downloader.download_all():
                print(f"Downloaded {result.data.player_id}")
    """

    def __init__(
        self,
        config: PlayerGameLogDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        players: list[tuple[int, int, int]] | None = None,
    ) -> None:
        """Initialize the Player Game Log Downloader.

        Args:
            config: Downloader configuration
            http_client: Optional HTTP client (created if not provided)
            rate_limiter: Optional rate limiter (created if not provided)
            retry_handler: Optional retry handler (created if not provided)
            players: Optional list of (player_id, season_id, game_type) tuples
        """
        super().__init__(
            config or PlayerGameLogDownloaderConfig(),
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
        )
        self._players: list[tuple[int, int, int]] = list(players) if players else []
        self._include_raw = getattr(self.config, "include_raw_response", False)

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "nhl_json_player_game_log"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Not implemented - this downloader works with player seasons, not games.

        Use download_player_season() instead.

        Raises:
            NotImplementedError: Always raised
        """
        raise NotImplementedError(
            "PlayerGameLogDownloader works with player seasons, not games. "
            "Use download_player_season() instead."
        )

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Not implemented - this downloader works with player seasons, not games.

        Use download_all() with set_players() instead.

        Raises:
            NotImplementedError: Always raised
        """
        raise NotImplementedError(
            "PlayerGameLogDownloader works with player seasons, not games. "
            "Use download_all() with set_players() instead."
        )
        # Make it a proper generator
        if False:  # pragma: no cover
            yield 0

    def set_players(self, players: list[tuple[int, int, int]]) -> None:
        """Set the list of players to download.

        Args:
            players: List of (player_id, season_id, game_type) tuples
        """
        self._players = list(players)

    async def download_player_season(
        self,
        player_id: int,
        season_id: int,
        game_type: int = REGULAR_SEASON,
    ) -> DownloadResult:
        """Download game log for a specific player's season.

        Args:
            player_id: NHL player ID
            season_id: Season ID (e.g., 20242025)
            game_type: Game type (2 = regular season, 3 = playoffs)

        Returns:
            DownloadResult containing the parsed game log
        """
        path = f"/v1/player/{player_id}/game-log/{season_id}/{game_type}"

        try:
            response = await self._get(path)
            raw_data = response.json()

            parsed = self._parse_game_log(raw_data, player_id, season_id, game_type)

            return DownloadResult(
                source=self.source_name,
                season_id=season_id,
                data=parsed.to_dict(),
                status=DownloadStatus.COMPLETED,
                raw_content=None,
            )
        except Exception as e:
            error_msg = f"Failed to download game log for player {player_id}: {e}"
            logger.exception(error_msg)
            return DownloadResult(
                source=self.source_name,
                season_id=season_id,
                data={},
                status=DownloadStatus.FAILED,
                error_message=error_msg,
            )

    async def download_all(
        self,
    ) -> AsyncGenerator[DownloadResult, None]:
        """Download game logs for all configured players.

        Yields:
            DownloadResult for each player
        """
        if not self._players:
            logger.warning("No players configured for download")
            return

        for player_id, season_id, game_type in self._players:
            result = await self.download_player_season(player_id, season_id, game_type)
            yield result

    def _parse_game_log(
        self,
        data: dict[str, Any],
        player_id: int,
        season_id: int,
        game_type: int,
    ) -> ParsedPlayerGameLog:
        """Parse game log response into structured data.

        Args:
            data: Raw API response
            player_id: NHL player ID
            season_id: Season ID
            game_type: Game type

        Returns:
            Parsed game log
        """
        game_log = data.get("gameLog", [])

        if not game_log:
            return ParsedPlayerGameLog(
                player_id=player_id,
                season_id=season_id,
                game_type=game_type,
                is_goalie=False,
                games=(),
            )

        # Determine if goalie based on presence of goalie-specific fields
        first_game = game_log[0] if game_log else {}
        is_goalie = "shotsAgainst" in first_game or "decision" in first_game

        games: tuple[SkaterGameStats | GoalieGameStats, ...]
        if is_goalie:
            games = tuple(self._parse_goalie_game(g) for g in game_log)
        else:
            games = tuple(self._parse_skater_game(g) for g in game_log)

        return ParsedPlayerGameLog(
            player_id=player_id,
            season_id=season_id,
            game_type=game_type,
            is_goalie=is_goalie,
            games=games,
        )

    def _parse_skater_game(self, data: dict[str, Any]) -> SkaterGameStats:
        """Parse a single skater game entry.

        Args:
            data: Game entry from API response

        Returns:
            Parsed skater game stats
        """
        game_date = _parse_date(data.get("gameDate"))
        if game_date is None:
            game_date = date(1900, 1, 1)  # Fallback for missing dates

        return SkaterGameStats(
            game_id=data.get("gameId", 0),
            game_date=game_date,
            team_abbrev=data.get("teamAbbrev", ""),
            opponent_abbrev=data.get("opponentAbbrev", ""),
            home_road_flag=data.get("homeRoadFlag", ""),
            goals=data.get("goals", 0),
            assists=data.get("assists", 0),
            points=data.get("points", 0),
            plus_minus=data.get("plusMinus", 0),
            pim=data.get("pim", 0),
            shots=data.get("shots", 0),
            shifts=data.get("shifts", 0),
            toi=data.get("toi", "00:00"),
            power_play_goals=data.get("powerPlayGoals", 0),
            power_play_points=data.get("powerPlayPoints", 0),
            shorthanded_goals=data.get("shorthandedGoals", 0),
            shorthanded_points=data.get("shorthandedPoints", 0),
            game_winning_goals=data.get("gameWinningGoals", 0),
            ot_goals=data.get("otGoals", 0),
        )

    def _parse_goalie_game(self, data: dict[str, Any]) -> GoalieGameStats:
        """Parse a single goalie game entry.

        Args:
            data: Game entry from API response

        Returns:
            Parsed goalie game stats
        """
        game_date = _parse_date(data.get("gameDate"))
        if game_date is None:
            game_date = date(1900, 1, 1)  # Fallback for missing dates

        return GoalieGameStats(
            game_id=data.get("gameId", 0),
            game_date=game_date,
            team_abbrev=data.get("teamAbbrev", ""),
            opponent_abbrev=data.get("opponentAbbrev", ""),
            home_road_flag=data.get("homeRoadFlag", ""),
            games_started=data.get("gamesStarted", 0),
            decision=data.get("decision"),
            shots_against=data.get("shotsAgainst", 0),
            goals_against=data.get("goalsAgainst", 0),
            save_pct=data.get("savePctg", 0.0),
            shutouts=data.get("shutouts", 0),
            toi=data.get("toi", "00:00"),
            goals=data.get("goals", 0),
            assists=data.get("assists", 0),
            pim=data.get("pim", 0),
        )


def create_player_game_log_downloader(
    *,
    base_url: str = NHL_API_BASE_URL,
    requests_per_second: float = DEFAULT_RATE_LIMIT,
    max_retries: int = 3,
    include_raw_response: bool = False,
    players: list[tuple[int, int, int]] | None = None,
) -> PlayerGameLogDownloader:
    """Factory function to create a PlayerGameLogDownloader with common settings.

    Args:
        base_url: Base URL for the NHL API
        requests_per_second: Rate limit for API requests
        max_retries: Maximum retry attempts
        include_raw_response: Whether to include raw JSON in results
        players: List of (player_id, season_id, game_type) tuples

    Returns:
        Configured PlayerGameLogDownloader instance
    """
    config = PlayerGameLogDownloaderConfig(
        base_url=base_url,
        requests_per_second=requests_per_second,
        max_retries=max_retries,
        include_raw_response=include_raw_response,
    )
    return PlayerGameLogDownloader(config, players=players)
