"""NHL JSON API Boxscore Downloader.

Downloads game boxscores from the NHL JSON API, including team statistics,
player statistics for skaters and goalies, and game metadata.

API Endpoint: GET https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore

Example usage:
    config = BoxscoreDownloaderConfig()
    async with BoxscoreDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        boxscore = result.data
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import DownloadError

if TYPE_CHECKING:
    from nhl_api.downloaders.base.rate_limiter import RateLimiter
    from nhl_api.downloaders.base.retry_handler import RetryHandler
    from nhl_api.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com"

# Default rate limit for NHL API (requests per second)
DEFAULT_RATE_LIMIT = 5.0


@dataclass
class BoxscoreDownloaderConfig(DownloaderConfig):
    """Configuration for the Boxscore Downloader.

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
class TeamBoxscore:
    """Team-level boxscore statistics.

    Attributes:
        team_id: NHL team ID
        abbrev: Team abbreviation (e.g., "TOR", "MTL")
        name: Team common name
        score: Final score
        shots_on_goal: Total shots on goal
        is_home: Whether this is the home team
    """

    team_id: int
    abbrev: str
    name: str
    score: int
    shots_on_goal: int
    is_home: bool


@dataclass(frozen=True, slots=True)
class SkaterStats:
    """Individual skater game statistics.

    Attributes:
        player_id: NHL player ID
        name: Player display name
        sweater_number: Jersey number
        position: Position code (C, L, R, D)
        goals: Goals scored
        assists: Assists
        points: Total points (goals + assists)
        plus_minus: Plus/minus rating
        pim: Penalties in minutes
        shots: Shots on goal
        hits: Hits
        blocked_shots: Blocked shots
        giveaways: Giveaways
        takeaways: Takeaways
        faceoff_pct: Faceoff winning percentage (0-100)
        toi: Time on ice (MM:SS format)
        shifts: Number of shifts
        power_play_goals: Power play goals
        shorthanded_goals: Shorthanded goals
        team_id: Player's team ID
    """

    player_id: int
    name: str
    sweater_number: int
    position: str
    goals: int
    assists: int
    points: int
    plus_minus: int
    pim: int
    shots: int
    hits: int
    blocked_shots: int
    giveaways: int
    takeaways: int
    faceoff_pct: float
    toi: str
    shifts: int
    power_play_goals: int
    shorthanded_goals: int
    team_id: int


@dataclass(frozen=True, slots=True)
class GoalieStats:
    """Individual goalie game statistics.

    Attributes:
        player_id: NHL player ID
        name: Player display name
        sweater_number: Jersey number
        saves: Total saves
        shots_against: Total shots faced
        goals_against: Goals allowed
        save_pct: Save percentage (0.0-1.0)
        toi: Time on ice (MM:SS format)
        even_strength_shots_against: Even strength shots (saves/shots format)
        power_play_shots_against: Power play shots (saves/shots format)
        shorthanded_shots_against: Shorthanded shots (saves/shots format)
        is_starter: Whether goalie started the game
        decision: Game decision (W, L, OTL, or None)
        team_id: Player's team ID
    """

    player_id: int
    name: str
    sweater_number: int
    saves: int
    shots_against: int
    goals_against: int
    save_pct: float
    toi: str
    even_strength_shots_against: str
    power_play_shots_against: str
    shorthanded_shots_against: str
    is_starter: bool
    decision: str | None
    team_id: int


@dataclass
class ParsedBoxscore:
    """Fully parsed boxscore data.

    Attributes:
        game_id: NHL game ID
        season_id: Season ID (e.g., 20242025)
        game_date: Game date (YYYY-MM-DD)
        game_type: Game type code (2=regular, 3=playoff)
        game_state: Game state (e.g., "OFF", "FINAL")
        home_team: Home team boxscore
        away_team: Away team boxscore
        home_skaters: List of home team skater stats
        away_skaters: List of away team skater stats
        home_goalies: List of home team goalie stats
        away_goalies: List of away team goalie stats
        venue_name: Venue name
        is_overtime: Whether game went to overtime
        is_shootout: Whether game was decided in shootout
    """

    game_id: int
    season_id: int
    game_date: str
    game_type: int
    game_state: str
    home_team: TeamBoxscore
    away_team: TeamBoxscore
    home_skaters: list[SkaterStats] = field(default_factory=list)
    away_skaters: list[SkaterStats] = field(default_factory=list)
    home_goalies: list[GoalieStats] = field(default_factory=list)
    away_goalies: list[GoalieStats] = field(default_factory=list)
    venue_name: str | None = None
    is_overtime: bool = False
    is_shootout: bool = False


class BoxscoreDownloader(BaseDownloader):
    """Downloads game boxscores from the NHL JSON API.

    This downloader fetches boxscore data including team statistics,
    player statistics for skaters and goalies, and game metadata.

    The boxscore endpoint provides:
    - Team-level stats (score, shots on goal)
    - Individual player stats (goals, assists, +/-, TOI, etc.)
    - Goalie stats (saves, goals against, save %)
    - Game metadata (venue, game state, overtime/shootout flags)

    Example:
        config = BoxscoreDownloaderConfig()
        async with BoxscoreDownloader(config) as downloader:
            # Download a single game
            result = await downloader.download_game(2024020500)

            # Access parsed data
            boxscore = result.data
            print(f"Score: {boxscore['away_team']['score']}-{boxscore['home_team']['score']}")

            # Download an entire season (requires game IDs)
            downloader.set_game_ids([2024020001, 2024020002, ...])
            async for result in downloader.download_season(20242025):
                print(f"Downloaded game {result.game_id}")
    """

    def __init__(
        self,
        config: BoxscoreDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        game_ids: list[int] | None = None,
    ) -> None:
        """Initialize the Boxscore Downloader.

        Args:
            config: Downloader configuration
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            game_ids: Optional list of game IDs for season download
        """
        super().__init__(
            config or BoxscoreDownloaderConfig(),
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
        )
        self._game_ids: list[int] = game_ids or []
        self._include_raw = getattr(config, "include_raw_response", False)

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "nhl_json_boxscore"

    def set_game_ids(self, game_ids: list[int]) -> None:
        """Set game IDs for season download.

        This method allows setting the list of game IDs to download
        when calling download_season(). Typically these come from
        the Schedule Downloader.

        Args:
            game_ids: List of NHL game IDs
        """
        self._game_ids = list(game_ids)
        logger.debug(
            "%s: Set %d game IDs for download",
            self.source_name,
            len(self._game_ids),
        )

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Fetch boxscore data for a single game.

        Args:
            game_id: NHL game ID

        Returns:
            Parsed boxscore data as a dictionary

        Raises:
            DownloadError: If the fetch fails
        """
        path = f"/v1/gamecenter/{game_id}/boxscore"
        logger.debug("%s: Fetching boxscore for game %d", self.source_name, game_id)

        try:
            response = await self._get(path)

            if not response.is_success:
                raise DownloadError(
                    f"Failed to fetch boxscore: HTTP {response.status}",
                    source=self.source_name,
                    game_id=game_id,
                )

            raw_data = response.json()
            parsed = self._parse_boxscore(raw_data, game_id)

            # Convert to dict for DownloadResult
            result = self._boxscore_to_dict(parsed)

            # Optionally include raw response
            if self._include_raw:
                result["_raw"] = raw_data

            return result

        except DownloadError:
            raise
        except ValueError as e:
            raise DownloadError(
                f"Failed to parse boxscore JSON: {e}",
                source=self.source_name,
                game_id=game_id,
                cause=e,
            ) from e
        except Exception as e:
            raise DownloadError(
                f"Unexpected error fetching boxscore: {e}",
                source=self.source_name,
                game_id=game_id,
                cause=e,
            ) from e

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Yield game IDs for a season.

        This method yields the game IDs set via set_game_ids().
        Typically, game IDs come from the Schedule Downloader.

        Args:
            season_id: NHL season ID (e.g., 20242025)

        Yields:
            Game IDs for the season
        """
        if not self._game_ids:
            logger.warning(
                "%s: No game IDs set for season %d. "
                "Use set_game_ids() or get IDs from Schedule Downloader.",
                self.source_name,
                season_id,
            )
            return

        # Update total for progress tracking
        self.set_total_items(len(self._game_ids))

        logger.info(
            "%s: Downloading %d boxscores for season %d",
            self.source_name,
            len(self._game_ids),
            season_id,
        )

        for game_id in self._game_ids:
            yield game_id

    def _parse_boxscore(self, data: dict[str, Any], game_id: int) -> ParsedBoxscore:
        """Parse raw API response into structured boxscore.

        Args:
            data: Raw JSON response from API
            game_id: NHL game ID

        Returns:
            Parsed boxscore data
        """
        # Extract basic game info
        season = data.get("season", 0)
        game_date = data.get("gameDate", "")
        game_type = data.get("gameType", 2)
        game_state = data.get("gameState", "")

        # Parse venue
        venue = data.get("venue", {})
        venue_name = venue.get("default") if isinstance(venue, dict) else None

        # Parse overtime/shootout from gameOutcome
        game_outcome = data.get("gameOutcome", {})
        last_period_type = game_outcome.get("lastPeriodType", "REG")
        is_overtime = last_period_type in ("OT", "SO")
        is_shootout = last_period_type == "SO"

        # Parse team data
        home_team_data = data.get("homeTeam", {})
        away_team_data = data.get("awayTeam", {})

        home_team = self._parse_team(home_team_data, is_home=True)
        away_team = self._parse_team(away_team_data, is_home=False)

        # Parse player stats
        player_stats = data.get("playerByGameStats", {})

        home_stats = player_stats.get("homeTeam", {})
        away_stats = player_stats.get("awayTeam", {})

        home_skaters = self._parse_skaters(home_stats, home_team.team_id)
        away_skaters = self._parse_skaters(away_stats, away_team.team_id)
        home_goalies = self._parse_goalies(home_stats, home_team.team_id)
        away_goalies = self._parse_goalies(away_stats, away_team.team_id)

        return ParsedBoxscore(
            game_id=game_id,
            season_id=season,
            game_date=game_date,
            game_type=game_type,
            game_state=game_state,
            home_team=home_team,
            away_team=away_team,
            home_skaters=home_skaters,
            away_skaters=away_skaters,
            home_goalies=home_goalies,
            away_goalies=away_goalies,
            venue_name=venue_name,
            is_overtime=is_overtime,
            is_shootout=is_shootout,
        )

    def _parse_team(self, data: dict[str, Any], *, is_home: bool) -> TeamBoxscore:
        """Parse team boxscore data.

        Args:
            data: Team data from API response
            is_home: Whether this is the home team

        Returns:
            Parsed team boxscore
        """
        return TeamBoxscore(
            team_id=data.get("id", 0),
            abbrev=data.get("abbrev", ""),
            name=data.get("commonName", {}).get("default", ""),
            score=data.get("score", 0),
            shots_on_goal=data.get("sog", 0),
            is_home=is_home,
        )

    def _parse_skaters(
        self, team_stats: dict[str, Any], team_id: int
    ) -> list[SkaterStats]:
        """Parse skater statistics for a team.

        Args:
            team_stats: Team player stats from API response
            team_id: NHL team ID

        Returns:
            List of skater stats
        """
        skaters = []

        # Combine forwards and defense
        forwards = team_stats.get("forwards", [])
        defense = team_stats.get("defense", [])

        for player in forwards + defense:
            skaters.append(self._parse_single_skater(player, team_id))

        return skaters

    def _parse_single_skater(self, player: dict[str, Any], team_id: int) -> SkaterStats:
        """Parse a single skater's statistics.

        Args:
            player: Player data from API response
            team_id: NHL team ID

        Returns:
            Parsed skater stats
        """
        name_data = player.get("name", {})
        name = name_data.get("default", "") if isinstance(name_data, dict) else ""

        return SkaterStats(
            player_id=player.get("playerId", 0),
            name=name,
            sweater_number=player.get("sweaterNumber", 0),
            position=player.get("position", ""),
            goals=player.get("goals", 0),
            assists=player.get("assists", 0),
            points=player.get("points", 0),
            plus_minus=player.get("plusMinus", 0),
            pim=player.get("pim", 0),
            shots=player.get("sog", 0),
            hits=player.get("hits", 0),
            blocked_shots=player.get("blockedShots", 0),
            giveaways=player.get("giveaways", 0),
            takeaways=player.get("takeaways", 0),
            faceoff_pct=player.get("faceoffWinningPctg", 0.0),
            toi=player.get("toi", "0:00"),
            shifts=player.get("shifts", 0),
            power_play_goals=player.get("powerPlayGoals", 0),
            shorthanded_goals=player.get("shorthandedGoals", 0),
            team_id=team_id,
        )

    def _parse_goalies(
        self, team_stats: dict[str, Any], team_id: int
    ) -> list[GoalieStats]:
        """Parse goalie statistics for a team.

        Args:
            team_stats: Team player stats from API response
            team_id: NHL team ID

        Returns:
            List of goalie stats
        """
        goalies = []

        for player in team_stats.get("goalies", []):
            goalies.append(self._parse_single_goalie(player, team_id))

        return goalies

    def _parse_single_goalie(self, player: dict[str, Any], team_id: int) -> GoalieStats:
        """Parse a single goalie's statistics.

        Args:
            player: Player data from API response
            team_id: NHL team ID

        Returns:
            Parsed goalie stats
        """
        name_data = player.get("name", {})
        name = name_data.get("default", "") if isinstance(name_data, dict) else ""

        # Parse saves from "saveShotsAgainst" format like "25/27"
        save_shots = player.get("saveShotsAgainst", "0/0")
        if isinstance(save_shots, str) and "/" in save_shots:
            parts = save_shots.split("/")
            saves = int(parts[0]) if parts[0].isdigit() else 0
            shots_against = (
                int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            )
        else:
            saves = player.get("saves", 0)
            shots_against = player.get("shotsAgainst", 0)

        return GoalieStats(
            player_id=player.get("playerId", 0),
            name=name,
            sweater_number=player.get("sweaterNumber", 0),
            saves=saves,
            shots_against=shots_against,
            goals_against=player.get("goalsAgainst", 0),
            save_pct=player.get("savePctg", 0.0),
            toi=player.get("toi", "0:00"),
            even_strength_shots_against=player.get("evenStrengthShotsAgainst", "0/0"),
            power_play_shots_against=player.get("powerPlayShotsAgainst", "0/0"),
            shorthanded_shots_against=player.get("shorthandedShotsAgainst", "0/0"),
            is_starter=player.get("starter", False),
            decision=player.get("decision"),
            team_id=team_id,
        )

    def _boxscore_to_dict(self, boxscore: ParsedBoxscore) -> dict[str, Any]:
        """Convert ParsedBoxscore to dictionary.

        Args:
            boxscore: Parsed boxscore data

        Returns:
            Dictionary representation
        """
        return {
            "game_id": boxscore.game_id,
            "season_id": boxscore.season_id,
            "game_date": boxscore.game_date,
            "game_type": boxscore.game_type,
            "game_state": boxscore.game_state,
            "venue_name": boxscore.venue_name,
            "is_overtime": boxscore.is_overtime,
            "is_shootout": boxscore.is_shootout,
            "home_team": {
                "team_id": boxscore.home_team.team_id,
                "abbrev": boxscore.home_team.abbrev,
                "name": boxscore.home_team.name,
                "score": boxscore.home_team.score,
                "shots_on_goal": boxscore.home_team.shots_on_goal,
            },
            "away_team": {
                "team_id": boxscore.away_team.team_id,
                "abbrev": boxscore.away_team.abbrev,
                "name": boxscore.away_team.name,
                "score": boxscore.away_team.score,
                "shots_on_goal": boxscore.away_team.shots_on_goal,
            },
            "home_skaters": [self._skater_to_dict(s) for s in boxscore.home_skaters],
            "away_skaters": [self._skater_to_dict(s) for s in boxscore.away_skaters],
            "home_goalies": [self._goalie_to_dict(g) for g in boxscore.home_goalies],
            "away_goalies": [self._goalie_to_dict(g) for g in boxscore.away_goalies],
        }

    def _skater_to_dict(self, skater: SkaterStats) -> dict[str, Any]:
        """Convert SkaterStats to dictionary."""
        return {
            "player_id": skater.player_id,
            "name": skater.name,
            "sweater_number": skater.sweater_number,
            "position": skater.position,
            "goals": skater.goals,
            "assists": skater.assists,
            "points": skater.points,
            "plus_minus": skater.plus_minus,
            "pim": skater.pim,
            "shots": skater.shots,
            "hits": skater.hits,
            "blocked_shots": skater.blocked_shots,
            "giveaways": skater.giveaways,
            "takeaways": skater.takeaways,
            "faceoff_pct": skater.faceoff_pct,
            "toi": skater.toi,
            "shifts": skater.shifts,
            "power_play_goals": skater.power_play_goals,
            "shorthanded_goals": skater.shorthanded_goals,
            "team_id": skater.team_id,
        }

    def _goalie_to_dict(self, goalie: GoalieStats) -> dict[str, Any]:
        """Convert GoalieStats to dictionary."""
        return {
            "player_id": goalie.player_id,
            "name": goalie.name,
            "sweater_number": goalie.sweater_number,
            "saves": goalie.saves,
            "shots_against": goalie.shots_against,
            "goals_against": goalie.goals_against,
            "save_pct": goalie.save_pct,
            "toi": goalie.toi,
            "even_strength_shots_against": goalie.even_strength_shots_against,
            "power_play_shots_against": goalie.power_play_shots_against,
            "shorthanded_shots_against": goalie.shorthanded_shots_against,
            "is_starter": goalie.is_starter,
            "decision": goalie.decision,
            "team_id": goalie.team_id,
        }
