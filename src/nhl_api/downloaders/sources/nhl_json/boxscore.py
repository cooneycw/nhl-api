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
    from nhl_api.services.db import DatabaseService
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

    @staticmethod
    def _toi_to_seconds(toi: str) -> int:
        """Convert time on ice from MM:SS format to seconds.

        Args:
            toi: Time on ice string like "15:30"

        Returns:
            Total seconds
        """
        if not toi or ":" not in toi:
            return 0
        try:
            parts = toi.split(":")
            minutes = int(parts[0])
            seconds = int(parts[1]) if len(parts) > 1 else 0
            return minutes * 60 + seconds
        except (ValueError, IndexError):
            return 0

    @staticmethod
    def _parse_saves_shots(save_shots: str) -> tuple[int, int]:
        """Parse saves/shots format like '25/27'.

        Args:
            save_shots: String in 'saves/shots' format

        Returns:
            Tuple of (saves, shots)
        """
        if not save_shots or "/" not in save_shots:
            return 0, 0
        try:
            parts = save_shots.split("/")
            saves = int(parts[0]) if parts[0].isdigit() else 0
            shots = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            return saves, shots
        except (ValueError, IndexError):
            return 0, 0

    def _dict_to_boxscore(self, data: dict[str, Any]) -> ParsedBoxscore:
        """Convert dictionary back to ParsedBoxscore.

        Args:
            data: Dictionary from DownloadResult.data

        Returns:
            ParsedBoxscore object
        """
        home_team_data = data.get("home_team", {})
        away_team_data = data.get("away_team", {})

        home_team = TeamBoxscore(
            team_id=home_team_data.get("team_id", 0),
            abbrev=home_team_data.get("abbrev", ""),
            name=home_team_data.get("name", ""),
            score=home_team_data.get("score", 0),
            shots_on_goal=home_team_data.get("shots_on_goal", 0),
            is_home=True,
        )
        away_team = TeamBoxscore(
            team_id=away_team_data.get("team_id", 0),
            abbrev=away_team_data.get("abbrev", ""),
            name=away_team_data.get("name", ""),
            score=away_team_data.get("score", 0),
            shots_on_goal=away_team_data.get("shots_on_goal", 0),
            is_home=False,
        )

        home_skaters = [
            SkaterStats(
                player_id=s.get("player_id", 0),
                name=s.get("name", ""),
                sweater_number=s.get("sweater_number", 0),
                position=s.get("position", ""),
                goals=s.get("goals", 0),
                assists=s.get("assists", 0),
                points=s.get("points", 0),
                plus_minus=s.get("plus_minus", 0),
                pim=s.get("pim", 0),
                shots=s.get("shots", 0),
                hits=s.get("hits", 0),
                blocked_shots=s.get("blocked_shots", 0),
                giveaways=s.get("giveaways", 0),
                takeaways=s.get("takeaways", 0),
                faceoff_pct=s.get("faceoff_pct", 0.0),
                toi=s.get("toi", "0:00"),
                shifts=s.get("shifts", 0),
                power_play_goals=s.get("power_play_goals", 0),
                shorthanded_goals=s.get("shorthanded_goals", 0),
                team_id=s.get("team_id", home_team.team_id),
            )
            for s in data.get("home_skaters", [])
        ]

        away_skaters = [
            SkaterStats(
                player_id=s.get("player_id", 0),
                name=s.get("name", ""),
                sweater_number=s.get("sweater_number", 0),
                position=s.get("position", ""),
                goals=s.get("goals", 0),
                assists=s.get("assists", 0),
                points=s.get("points", 0),
                plus_minus=s.get("plus_minus", 0),
                pim=s.get("pim", 0),
                shots=s.get("shots", 0),
                hits=s.get("hits", 0),
                blocked_shots=s.get("blocked_shots", 0),
                giveaways=s.get("giveaways", 0),
                takeaways=s.get("takeaways", 0),
                faceoff_pct=s.get("faceoff_pct", 0.0),
                toi=s.get("toi", "0:00"),
                shifts=s.get("shifts", 0),
                power_play_goals=s.get("power_play_goals", 0),
                shorthanded_goals=s.get("shorthanded_goals", 0),
                team_id=s.get("team_id", away_team.team_id),
            )
            for s in data.get("away_skaters", [])
        ]

        home_goalies = [
            GoalieStats(
                player_id=g.get("player_id", 0),
                name=g.get("name", ""),
                sweater_number=g.get("sweater_number", 0),
                saves=g.get("saves", 0),
                shots_against=g.get("shots_against", 0),
                goals_against=g.get("goals_against", 0),
                save_pct=g.get("save_pct", 0.0),
                toi=g.get("toi", "0:00"),
                even_strength_shots_against=g.get("even_strength_shots_against", "0/0"),
                power_play_shots_against=g.get("power_play_shots_against", "0/0"),
                shorthanded_shots_against=g.get("shorthanded_shots_against", "0/0"),
                is_starter=g.get("is_starter", False),
                decision=g.get("decision"),
                team_id=g.get("team_id", home_team.team_id),
            )
            for g in data.get("home_goalies", [])
        ]

        away_goalies = [
            GoalieStats(
                player_id=g.get("player_id", 0),
                name=g.get("name", ""),
                sweater_number=g.get("sweater_number", 0),
                saves=g.get("saves", 0),
                shots_against=g.get("shots_against", 0),
                goals_against=g.get("goals_against", 0),
                save_pct=g.get("save_pct", 0.0),
                toi=g.get("toi", "0:00"),
                even_strength_shots_against=g.get("even_strength_shots_against", "0/0"),
                power_play_shots_against=g.get("power_play_shots_against", "0/0"),
                shorthanded_shots_against=g.get("shorthanded_shots_against", "0/0"),
                is_starter=g.get("is_starter", False),
                decision=g.get("decision"),
                team_id=g.get("team_id", away_team.team_id),
            )
            for g in data.get("away_goalies", [])
        ]

        return ParsedBoxscore(
            game_id=data.get("game_id", 0),
            season_id=data.get("season_id", 0),
            game_date=data.get("game_date", ""),
            game_type=data.get("game_type", 2),
            game_state=data.get("game_state", ""),
            home_team=home_team,
            away_team=away_team,
            home_skaters=home_skaters,
            away_skaters=away_skaters,
            home_goalies=home_goalies,
            away_goalies=away_goalies,
            venue_name=data.get("venue_name"),
            is_overtime=data.get("is_overtime", False),
            is_shootout=data.get("is_shootout", False),
        )

    async def persist(
        self,
        db: DatabaseService,
        boxscores: list[ParsedBoxscore] | list[dict[str, Any]],
    ) -> int:
        """Persist boxscore data to the database.

        Persists:
        - Team stats to game_team_stats
        - Skater stats to game_skater_stats
        - Goalie stats to game_goalie_stats

        Args:
            db: Database service instance
            boxscores: List of ParsedBoxscore objects or dicts to persist

        Returns:
            Number of boxscores persisted
        """
        if not boxscores:
            return 0

        # Convert dicts to ParsedBoxscore if needed
        parsed_boxscores: list[ParsedBoxscore] = []
        for item in boxscores:
            if isinstance(item, dict):
                parsed_boxscores.append(self._dict_to_boxscore(item))
            else:
                parsed_boxscores.append(item)

        count = 0
        for boxscore in parsed_boxscores:
            # Persist team stats for both teams
            for team, skaters in [
                (boxscore.home_team, boxscore.home_skaters),
                (boxscore.away_team, boxscore.away_skaters),
            ]:
                # Aggregate stats from players
                total_hits = sum(s.hits for s in skaters)
                total_blocked = sum(s.blocked_shots for s in skaters)
                total_takeaways = sum(s.takeaways for s in skaters)
                total_giveaways = sum(s.giveaways for s in skaters)
                total_pim = sum(s.pim for s in skaters)
                pp_goals = sum(s.power_play_goals for s in skaters)

                await db.execute(
                    """
                    INSERT INTO game_team_stats (
                        game_id, season_id, team_id, is_home,
                        goals, shots, pim, power_play_goals,
                        blocked_shots, hits, takeaways, giveaways
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (game_id, season_id, team_id) DO UPDATE SET
                        goals = EXCLUDED.goals,
                        shots = EXCLUDED.shots,
                        pim = EXCLUDED.pim,
                        power_play_goals = EXCLUDED.power_play_goals,
                        blocked_shots = EXCLUDED.blocked_shots,
                        hits = EXCLUDED.hits,
                        takeaways = EXCLUDED.takeaways,
                        giveaways = EXCLUDED.giveaways,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    boxscore.game_id,
                    boxscore.season_id,
                    team.team_id,
                    team.is_home,
                    team.score,
                    team.shots_on_goal,
                    total_pim,
                    pp_goals,
                    total_blocked,
                    total_hits,
                    total_takeaways,
                    total_giveaways,
                )

            # Persist skater stats
            all_skaters = boxscore.home_skaters + boxscore.away_skaters
            for skater in all_skaters:
                toi_seconds = self._toi_to_seconds(skater.toi)
                await db.execute(
                    """
                    INSERT INTO game_skater_stats (
                        game_id, season_id, player_id, team_id, position,
                        goals, assists, points, plus_minus, pim,
                        shots, hits, blocked_shots, giveaways, takeaways,
                        faceoff_pct, toi_seconds, shifts,
                        power_play_goals, shorthanded_goals
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
                    )
                    ON CONFLICT (game_id, season_id, player_id) DO UPDATE SET
                        goals = EXCLUDED.goals,
                        assists = EXCLUDED.assists,
                        points = EXCLUDED.points,
                        plus_minus = EXCLUDED.plus_minus,
                        pim = EXCLUDED.pim,
                        shots = EXCLUDED.shots,
                        hits = EXCLUDED.hits,
                        blocked_shots = EXCLUDED.blocked_shots,
                        giveaways = EXCLUDED.giveaways,
                        takeaways = EXCLUDED.takeaways,
                        faceoff_pct = EXCLUDED.faceoff_pct,
                        toi_seconds = EXCLUDED.toi_seconds,
                        shifts = EXCLUDED.shifts,
                        power_play_goals = EXCLUDED.power_play_goals,
                        shorthanded_goals = EXCLUDED.shorthanded_goals,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    boxscore.game_id,
                    boxscore.season_id,
                    skater.player_id,
                    skater.team_id,
                    skater.position,
                    skater.goals,
                    skater.assists,
                    skater.points,
                    skater.plus_minus,
                    skater.pim,
                    skater.shots,
                    skater.hits,
                    skater.blocked_shots,
                    skater.giveaways,
                    skater.takeaways,
                    skater.faceoff_pct if skater.faceoff_pct > 0 else None,
                    toi_seconds,
                    skater.shifts,
                    skater.power_play_goals,
                    skater.shorthanded_goals,
                )

            # Persist goalie stats
            all_goalies = boxscore.home_goalies + boxscore.away_goalies
            for goalie in all_goalies:
                toi_seconds = self._toi_to_seconds(goalie.toi)
                es_saves, es_shots = self._parse_saves_shots(
                    goalie.even_strength_shots_against
                )
                pp_saves, pp_shots = self._parse_saves_shots(
                    goalie.power_play_shots_against
                )
                sh_saves, sh_shots = self._parse_saves_shots(
                    goalie.shorthanded_shots_against
                )

                await db.execute(
                    """
                    INSERT INTO game_goalie_stats (
                        game_id, season_id, player_id, team_id,
                        saves, shots_against, goals_against, save_pct,
                        toi_seconds, even_strength_saves, even_strength_shots,
                        power_play_saves, power_play_shots,
                        shorthanded_saves, shorthanded_shots,
                        is_starter, decision
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17
                    )
                    ON CONFLICT (game_id, season_id, player_id) DO UPDATE SET
                        saves = EXCLUDED.saves,
                        shots_against = EXCLUDED.shots_against,
                        goals_against = EXCLUDED.goals_against,
                        save_pct = EXCLUDED.save_pct,
                        toi_seconds = EXCLUDED.toi_seconds,
                        even_strength_saves = EXCLUDED.even_strength_saves,
                        even_strength_shots = EXCLUDED.even_strength_shots,
                        power_play_saves = EXCLUDED.power_play_saves,
                        power_play_shots = EXCLUDED.power_play_shots,
                        shorthanded_saves = EXCLUDED.shorthanded_saves,
                        shorthanded_shots = EXCLUDED.shorthanded_shots,
                        is_starter = EXCLUDED.is_starter,
                        decision = EXCLUDED.decision,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    boxscore.game_id,
                    boxscore.season_id,
                    goalie.player_id,
                    goalie.team_id,
                    goalie.saves,
                    goalie.shots_against,
                    goalie.goals_against,
                    goalie.save_pct if goalie.save_pct > 0 else None,
                    toi_seconds,
                    es_saves,
                    es_shots,
                    pp_saves,
                    pp_shots,
                    sh_saves,
                    sh_shots,
                    goalie.is_starter,
                    goalie.decision,
                )

            count += 1

        logger.info(
            "Persisted %d boxscores (%d skater stats, %d goalie stats)",
            count,
            sum(len(b.home_skaters) + len(b.away_skaters) for b in parsed_boxscores),
            sum(len(b.home_goalies) + len(b.away_goalies) for b in parsed_boxscores),
        )
        return count
