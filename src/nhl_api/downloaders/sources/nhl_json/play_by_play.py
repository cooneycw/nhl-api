"""NHL JSON API Play-by-Play Downloader.

Downloads detailed play-by-play event data from the NHL JSON API, including
goals, shots, hits, penalties, faceoffs, and other game events.

API Endpoint: GET https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play

Example usage:
    config = PlayByPlayDownloaderConfig()
    async with PlayByPlayDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        pbp = result.data
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import Enum
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


class EventType(str, Enum):
    """Play-by-play event types."""

    GOAL = "goal"
    SHOT_ON_GOAL = "shot-on-goal"
    MISSED_SHOT = "missed-shot"
    BLOCKED_SHOT = "blocked-shot"
    HIT = "hit"
    GIVEAWAY = "giveaway"
    TAKEAWAY = "takeaway"
    FACEOFF = "faceoff"
    PENALTY = "penalty"
    STOPPAGE = "stoppage"
    PERIOD_START = "period-start"
    PERIOD_END = "period-end"
    GAME_END = "game-end"
    SHOOTOUT_COMPLETE = "shootout-complete"
    DELAYED_PENALTY = "delayed-penalty"
    FAILED_SHOT_ATTEMPT = "failed-shot-attempt"


class PlayerRole(str, Enum):
    """Roles players can have in events."""

    SCORER = "scorer"
    ASSIST = "assist"
    GOALIE = "goalie"
    SHOOTER = "shooter"
    HITTER = "hitter"
    HITTEE = "hittee"
    BLOCKER = "blocker"
    PLAYER_GIVING = "playerGiving"
    PLAYER_TAKING = "playerTaking"
    WINNER = "winner"
    LOSER = "loser"
    PENALTY_ON = "penaltyOn"
    DREW_BY = "drewBy"
    SERVED_BY = "servedBy"


@dataclass
class PlayByPlayDownloaderConfig(DownloaderConfig):
    """Configuration for the Play-by-Play Downloader.

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
class EventPlayer:
    """Player involved in a play-by-play event.

    Attributes:
        player_id: NHL player ID
        name: Player display name
        team_id: Player's team ID
        team_abbrev: Team abbreviation
        role: Player's role in the event (scorer, assist, hitter, etc.)
        sweater_number: Jersey number
    """

    player_id: int
    name: str
    team_id: int
    team_abbrev: str
    role: str
    sweater_number: int = 0


@dataclass(frozen=True, slots=True)
class GameEvent:
    """A single play-by-play event.

    Attributes:
        event_id: Unique event ID within the game
        event_type: Type of event (goal, shot, hit, etc.)
        period: Period number (1, 2, 3, 4=OT, 5=SO)
        period_type: Period type (REG, OT, SO)
        time_in_period: Time elapsed in period (MM:SS)
        time_remaining: Time remaining in period (MM:SS)
        sort_order: Event ordering index
        players: List of players involved in the event
        x_coord: X coordinate on ice (-100 to 100)
        y_coord: Y coordinate on ice (-42.5 to 42.5)
        zone: Zone code (O=offensive, D=defensive, N=neutral)
        home_score: Home team score after event
        away_score: Away team score after event
        home_sog: Home shots on goal after event
        away_sog: Away shots on goal after event
        event_owner_team_id: Team ID of the team the event is attributed to
        description: Event description text
        details: Additional event-specific details
    """

    event_id: int
    event_type: str
    period: int
    period_type: str
    time_in_period: str
    time_remaining: str
    sort_order: int
    players: tuple[EventPlayer, ...] = ()
    x_coord: float | None = None
    y_coord: float | None = None
    zone: str | None = None
    home_score: int = 0
    away_score: int = 0
    home_sog: int = 0
    away_sog: int = 0
    event_owner_team_id: int | None = None
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedPlayByPlay:
    """Fully parsed play-by-play data for a game.

    Attributes:
        game_id: NHL game ID
        season_id: Season ID (e.g., 20242025)
        game_date: Game date (YYYY-MM-DD)
        game_type: Game type code (2=regular, 3=playoff)
        game_state: Game state (e.g., "OFF", "FINAL")
        home_team_id: Home team ID
        home_team_abbrev: Home team abbreviation
        away_team_id: Away team ID
        away_team_abbrev: Away team abbreviation
        venue_name: Venue name
        events: List of all game events
        total_events: Total number of events
    """

    game_id: int
    season_id: int
    game_date: str
    game_type: int
    game_state: str
    home_team_id: int
    home_team_abbrev: str
    away_team_id: int
    away_team_abbrev: str
    venue_name: str | None
    events: list[GameEvent] = field(default_factory=list)

    @property
    def total_events(self) -> int:
        """Total number of events."""
        return len(self.events)

    def get_events_by_type(self, event_type: str) -> list[GameEvent]:
        """Get all events of a specific type.

        Args:
            event_type: Event type to filter by

        Returns:
            List of matching events
        """
        return [e for e in self.events if e.event_type == event_type]

    def get_events_by_period(self, period: int) -> list[GameEvent]:
        """Get all events in a specific period.

        Args:
            period: Period number

        Returns:
            List of matching events
        """
        return [e for e in self.events if e.period == period]


class PlayByPlayDownloader(BaseDownloader):
    """Downloads play-by-play data from the NHL JSON API.

    This downloader fetches detailed event data including:
    - Goals with assists and strength situation
    - Shots (on goal, missed, blocked)
    - Hits with hitter/hittee
    - Faceoffs with winner/loser
    - Penalties with type and duration
    - Stoppages with reason
    - Period boundaries

    Example:
        config = PlayByPlayDownloaderConfig()
        async with PlayByPlayDownloader(config) as downloader:
            # Download a single game
            result = await downloader.download_game(2024020500)

            # Access parsed data
            pbp = result.data
            goals = [e for e in pbp['events'] if e['event_type'] == 'goal']

            # Download an entire season (requires game IDs)
            downloader.set_game_ids([2024020001, 2024020002, ...])
            async for result in downloader.download_season(20242025):
                print(f"Downloaded game {result.game_id}")
    """

    def __init__(
        self,
        config: PlayByPlayDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        game_ids: list[int] | None = None,
    ) -> None:
        """Initialize the Play-by-Play Downloader.

        Args:
            config: Downloader configuration
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            game_ids: Optional list of game IDs for season download
        """
        super().__init__(
            config or PlayByPlayDownloaderConfig(),
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
        return "nhl_json_play_by_play"

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
        """Fetch play-by-play data for a single game.

        Args:
            game_id: NHL game ID

        Returns:
            Parsed play-by-play data as a dictionary

        Raises:
            DownloadError: If the fetch fails
        """
        path = f"gamecenter/{game_id}/play-by-play"
        logger.debug("%s: Fetching play-by-play for game %d", self.source_name, game_id)

        try:
            response = await self._get(path)

            if not response.is_success:
                raise DownloadError(
                    f"Failed to fetch play-by-play: HTTP {response.status}",
                    source=self.source_name,
                    game_id=game_id,
                )

            raw_data = response.json()
            parsed = self._parse_play_by_play(raw_data, game_id)

            # Convert to dict for DownloadResult
            result = self._play_by_play_to_dict(parsed)

            # Optionally include raw response
            if self._include_raw:
                result["_raw"] = raw_data

            return result

        except DownloadError:
            raise
        except ValueError as e:
            raise DownloadError(
                f"Failed to parse play-by-play JSON: {e}",
                source=self.source_name,
                game_id=game_id,
                cause=e,
            ) from e
        except Exception as e:
            raise DownloadError(
                f"Unexpected error fetching play-by-play: {e}",
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
            "%s: Downloading %d play-by-play records for season %d",
            self.source_name,
            len(self._game_ids),
            season_id,
        )

        for game_id in self._game_ids:
            yield game_id

    def _parse_play_by_play(
        self, data: dict[str, Any], game_id: int
    ) -> ParsedPlayByPlay:
        """Parse raw API response into structured play-by-play.

        Args:
            data: Raw JSON response from API
            game_id: NHL game ID

        Returns:
            Parsed play-by-play data
        """
        # Extract basic game info
        season = data.get("season", 0)
        game_date = data.get("gameDate", "")
        game_type = data.get("gameType", 2)
        game_state = data.get("gameState", "")

        # Parse venue
        venue = data.get("venue", {})
        venue_name = venue.get("default") if isinstance(venue, dict) else None

        # Parse team data
        home_team = data.get("homeTeam", {})
        away_team = data.get("awayTeam", {})

        home_team_id = home_team.get("id", 0)
        home_team_abbrev = home_team.get("abbrev", "")
        away_team_id = away_team.get("id", 0)
        away_team_abbrev = away_team.get("abbrev", "")

        # Parse events
        plays = data.get("plays", [])
        events = []

        for play in plays:
            try:
                event = self._parse_event(play, home_team_id, away_team_id)
                events.append(event)
            except Exception as e:
                logger.warning(
                    "%s: Failed to parse event in game %d: %s",
                    self.source_name,
                    game_id,
                    e,
                )

        # Sort events by sort_order
        events.sort(key=lambda e: e.sort_order)

        return ParsedPlayByPlay(
            game_id=game_id,
            season_id=season,
            game_date=game_date,
            game_type=game_type,
            game_state=game_state,
            home_team_id=home_team_id,
            home_team_abbrev=home_team_abbrev,
            away_team_id=away_team_id,
            away_team_abbrev=away_team_abbrev,
            venue_name=venue_name,
            events=events,
        )

    def _parse_event(
        self,
        play: dict[str, Any],
        home_team_id: int,
        away_team_id: int,
    ) -> GameEvent:
        """Parse a single play-by-play event.

        Args:
            play: Event data from API response
            home_team_id: Home team ID for context
            away_team_id: Away team ID for context

        Returns:
            Parsed game event
        """
        # Basic event info
        event_id = play.get("eventId", 0)
        type_desc = play.get("typeDescKey", "")
        sort_order = play.get("sortOrder", 0)

        # Period info
        period_descriptor = play.get("periodDescriptor", {})
        period = period_descriptor.get("number", 0)
        period_type = period_descriptor.get("periodType", "REG")

        # Time info
        time_in_period = play.get("timeInPeriod", "00:00")
        time_remaining = play.get("timeRemaining", "00:00")

        # Situation/score tracking
        # situationCode available but not currently used
        home_score = play.get("homeScore", 0)
        away_score = play.get("awayScore", 0)
        home_sog = play.get("homeSOG", 0)
        away_sog = play.get("awaySOG", 0)

        # Event details
        details = play.get("details", {})
        event_owner_team_id = details.get("eventOwnerTeamId")

        # Coordinates
        x_coord = details.get("xCoord")
        y_coord = details.get("yCoord")
        zone = details.get("zoneCode")

        # Description
        description = details.get("descKey", "") or details.get("reason", "")

        # Parse players
        players = self._parse_event_players(details)

        # Build additional details dict (event-specific fields)
        extra_details = self._extract_event_details(type_desc, details)

        return GameEvent(
            event_id=event_id,
            event_type=type_desc,
            period=period,
            period_type=period_type,
            time_in_period=time_in_period,
            time_remaining=time_remaining,
            sort_order=sort_order,
            players=tuple(players),
            x_coord=x_coord,
            y_coord=y_coord,
            zone=zone,
            home_score=home_score,
            away_score=away_score,
            home_sog=home_sog,
            away_sog=away_sog,
            event_owner_team_id=event_owner_team_id,
            description=description,
            details=extra_details,
        )

    def _parse_event_players(self, details: dict[str, Any]) -> list[EventPlayer]:
        """Parse players involved in an event.

        Args:
            details: Event details from API response

        Returns:
            List of players involved in the event
        """
        players = []

        # Map of detail keys to player roles
        player_mappings = [
            ("scoringPlayerId", "scorer"),
            ("assist1PlayerId", "assist1"),
            ("assist2PlayerId", "assist2"),
            ("shootingPlayerId", "shooter"),
            ("goalieInNetId", "goalie"),
            ("hittingPlayerId", "hitter"),
            ("hitteePlayerId", "hittee"),
            ("blockingPlayerId", "blocker"),
            ("playerId", "player"),
            ("winningPlayerId", "winner"),
            ("losingPlayerId", "loser"),
            ("committedByPlayerId", "penaltyOn"),
            ("drawnByPlayerId", "drewBy"),
            ("servedByPlayerId", "servedBy"),
        ]

        for key, role in player_mappings:
            player_id = details.get(key)
            if player_id:
                # Get associated team info if available
                team_id = details.get("eventOwnerTeamId", 0)
                team_abbrev = ""

                # Try to get sweater number
                sweater_number = 0
                sweater_key = key.replace("PlayerId", "PlayerSweater")
                if sweater_key in details:
                    sweater_number = details.get(sweater_key, 0)

                players.append(
                    EventPlayer(
                        player_id=player_id,
                        name="",  # Name not in play-by-play, requires separate lookup
                        team_id=team_id,
                        team_abbrev=team_abbrev,
                        role=role,
                        sweater_number=sweater_number,
                    )
                )

        return players

    def _extract_event_details(
        self, event_type: str, details: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract event-specific details.

        Args:
            event_type: Type of event
            details: Event details from API response

        Returns:
            Dictionary with event-specific fields
        """
        extra: dict[str, Any] = {}

        # Shot details
        if event_type in ("shot-on-goal", "missed-shot", "blocked-shot", "goal"):
            if "shotType" in details:
                extra["shot_type"] = details["shotType"]
            if "awaySOG" in details:
                extra["away_sog"] = details["awaySOG"]
            if "homeSOG" in details:
                extra["home_sog"] = details["homeSOG"]

        # Goal details
        if event_type == "goal":
            if "scoringPlayerTotal" in details:
                extra["scorer_season_total"] = details["scoringPlayerTotal"]
            if "assist1PlayerTotal" in details:
                extra["assist1_season_total"] = details["assist1PlayerTotal"]
            if "assist2PlayerTotal" in details:
                extra["assist2_season_total"] = details["assist2PlayerTotal"]
            if "highlightClipSharingUrl" in details:
                extra["highlight_url"] = details["highlightClipSharingUrl"]

        # Penalty details
        if event_type == "penalty":
            if "typeCode" in details:
                extra["penalty_type"] = details["typeCode"]
            if "duration" in details:
                extra["duration"] = details["duration"]
            if "descKey" in details:
                extra["penalty_desc"] = details["descKey"]

        # Faceoff details
        if event_type == "faceoff":
            if "zoneCode" in details:
                extra["zone"] = details["zoneCode"]

        # Stoppage details
        if event_type == "stoppage":
            if "reason" in details:
                extra["reason"] = details["reason"]

        return extra

    def _play_by_play_to_dict(self, pbp: ParsedPlayByPlay) -> dict[str, Any]:
        """Convert ParsedPlayByPlay to dictionary.

        Args:
            pbp: Parsed play-by-play data

        Returns:
            Dictionary representation
        """
        return {
            "game_id": pbp.game_id,
            "season_id": pbp.season_id,
            "game_date": pbp.game_date,
            "game_type": pbp.game_type,
            "game_state": pbp.game_state,
            "home_team_id": pbp.home_team_id,
            "home_team_abbrev": pbp.home_team_abbrev,
            "away_team_id": pbp.away_team_id,
            "away_team_abbrev": pbp.away_team_abbrev,
            "venue_name": pbp.venue_name,
            "total_events": pbp.total_events,
            "events": [self._event_to_dict(e) for e in pbp.events],
        }

    def _event_to_dict(self, event: GameEvent) -> dict[str, Any]:
        """Convert GameEvent to dictionary."""
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "period": event.period,
            "period_type": event.period_type,
            "time_in_period": event.time_in_period,
            "time_remaining": event.time_remaining,
            "sort_order": event.sort_order,
            "players": [self._player_to_dict(p) for p in event.players],
            "x_coord": event.x_coord,
            "y_coord": event.y_coord,
            "zone": event.zone,
            "home_score": event.home_score,
            "away_score": event.away_score,
            "home_sog": event.home_sog,
            "away_sog": event.away_sog,
            "event_owner_team_id": event.event_owner_team_id,
            "description": event.description,
            "details": event.details,
        }

    def _player_to_dict(self, player: EventPlayer) -> dict[str, Any]:
        """Convert EventPlayer to dictionary."""
        return {
            "player_id": player.player_id,
            "name": player.name,
            "team_id": player.team_id,
            "team_abbrev": player.team_abbrev,
            "role": player.role,
            "sweater_number": player.sweater_number,
        }


def create_play_by_play_downloader(
    *,
    requests_per_second: float = DEFAULT_RATE_LIMIT,
    max_retries: int = 3,
) -> PlayByPlayDownloader:
    """Factory function to create a configured PlayByPlayDownloader.

    Args:
        requests_per_second: Rate limit for API calls
        max_retries: Maximum retry attempts

    Returns:
        Configured PlayByPlayDownloader instance
    """
    config = PlayByPlayDownloaderConfig(
        base_url=NHL_API_BASE_URL,
        requests_per_second=requests_per_second,
        max_retries=max_retries,
    )
    return PlayByPlayDownloader(config)
