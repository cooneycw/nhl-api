"""NHL JSON API Gamecenter Landing Downloader.

Downloads game landing page data from the NHL JSON API, including
game overview, three stars, highlights, and matchup information.

API Endpoint: GET https://api-web.nhle.com/v1/gamecenter/{game_id}/landing

Example usage:
    config = GamecenterLandingDownloaderConfig()
    async with GamecenterLandingDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        landing = result.data
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
class GamecenterLandingDownloaderConfig(DownloaderConfig):
    """Configuration for the Gamecenter Landing Downloader.

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
class ThreeStar:
    """Three stars of the game player info.

    Attributes:
        star: Star number (1, 2, or 3)
        player_id: NHL player ID
        name: Player name
        team_abbrev: Team abbreviation
        position: Player position
        goals: Goals scored
        assists: Assists
        points: Total points
    """

    star: int
    player_id: int
    name: str
    team_abbrev: str
    position: str
    goals: int
    assists: int
    points: int


@dataclass(frozen=True, slots=True)
class GameHighlight:
    """Game highlight video information.

    Attributes:
        highlight_id: Unique highlight ID
        title: Highlight title
        description: Highlight description
        duration: Duration in seconds
        thumbnail_url: URL to thumbnail image
        video_url: URL to video
    """

    highlight_id: int
    title: str
    description: str
    duration: int
    thumbnail_url: str | None
    video_url: str | None


@dataclass(frozen=True, slots=True)
class TeamMatchup:
    """Team matchup summary info.

    Attributes:
        team_id: NHL team ID
        abbrev: Team abbreviation
        name: Team name
        record: Season record (W-L-OTL)
        goals_for: Goals for in season
        goals_against: Goals against in season
        power_play_pct: Power play percentage
        penalty_kill_pct: Penalty kill percentage
    """

    team_id: int
    abbrev: str
    name: str
    record: str
    goals_for: int
    goals_against: int
    power_play_pct: float
    penalty_kill_pct: float


@dataclass
class ParsedGamecenterLanding:
    """Parsed gamecenter landing page data.

    Attributes:
        game_id: NHL game ID
        season_id: Season ID (e.g., 20242025)
        game_type: Game type (1=pre, 2=regular, 3=playoffs)
        game_state: Game state (FUT, LIVE, OFF, FINAL)
        venue: Venue name
        attendance: Game attendance
        three_stars: List of three stars (if game completed)
        highlights: List of game highlights
        home_team: Home team matchup info
        away_team: Away team matchup info
        neutral_site: Whether game is at neutral site
        game_outcome_last_play: Description of final play
        raw_data: Raw API response (if include_raw_response=True)
    """

    game_id: int
    season_id: int
    game_type: int
    game_state: str
    venue: str | None
    attendance: int | None
    three_stars: list[ThreeStar]
    highlights: list[GameHighlight]
    home_team: TeamMatchup | None
    away_team: TeamMatchup | None
    neutral_site: bool
    game_outcome_last_play: str | None
    raw_data: dict[str, Any] | None = None


def _parse_three_star(star_data: dict[str, Any], star_num: int) -> ThreeStar:
    """Parse a three stars entry.

    Args:
        star_data: Raw star data from API
        star_num: Star number (1, 2, or 3)

    Returns:
        Parsed ThreeStar object
    """
    return ThreeStar(
        star=star_num,
        player_id=star_data.get("playerId", 0),
        name=star_data.get("name", {}).get("default", "Unknown"),
        team_abbrev=star_data.get("teamAbbrev", ""),
        position=star_data.get("position", ""),
        goals=star_data.get("goals", 0),
        assists=star_data.get("assists", 0),
        points=star_data.get("goals", 0) + star_data.get("assists", 0),
    )


def _parse_highlight(highlight_data: dict[str, Any]) -> GameHighlight:
    """Parse a highlight entry.

    Args:
        highlight_data: Raw highlight data from API

    Returns:
        Parsed GameHighlight object
    """
    return GameHighlight(
        highlight_id=highlight_data.get("id", 0),
        title=highlight_data.get("title", ""),
        description=highlight_data.get("description", ""),
        duration=highlight_data.get("duration", 0),
        thumbnail_url=highlight_data.get("thumbnail", {}).get("src"),
        video_url=highlight_data.get("playbacks", [{}])[0].get("url")
        if highlight_data.get("playbacks")
        else None,
    )


def _parse_team_matchup(team_data: dict[str, Any]) -> TeamMatchup:
    """Parse team matchup data.

    Args:
        team_data: Raw team data from API

    Returns:
        Parsed TeamMatchup object
    """
    record = team_data.get("record", "0-0-0")
    return TeamMatchup(
        team_id=team_data.get("id", 0),
        abbrev=team_data.get("abbrev", ""),
        name=team_data.get("name", {}).get("default", ""),
        record=record,
        goals_for=team_data.get("seasonSeriesWins", {}).get("goalsFor", 0),
        goals_against=team_data.get("seasonSeriesWins", {}).get("goalsAgainst", 0),
        power_play_pct=team_data.get("powerPlayPct", 0.0),
        penalty_kill_pct=team_data.get("penaltyKillPct", 0.0),
    )


def _parse_landing(
    data: dict[str, Any], include_raw: bool = False
) -> ParsedGamecenterLanding:
    """Parse the full landing page response.

    Args:
        data: Raw API response
        include_raw: Whether to include raw data in result

    Returns:
        Parsed ParsedGamecenterLanding object
    """
    # Parse three stars
    three_stars = []
    for i, star_key in enumerate(["firstStar", "secondStar", "thirdStar"], 1):
        if star_data := data.get(star_key):
            three_stars.append(_parse_three_star(star_data, i))

    # Parse highlights
    highlights = []
    for hl in data.get("summary", {}).get("gameVideo", {}).get("condensedGame", []):
        highlights.append(_parse_highlight(hl))

    # Parse team matchup info
    home_team = None
    away_team = None
    if home_data := data.get("homeTeam"):
        home_team = _parse_team_matchup(home_data)
    if away_data := data.get("awayTeam"):
        away_team = _parse_team_matchup(away_data)

    return ParsedGamecenterLanding(
        game_id=data.get("id", 0),
        season_id=data.get("season", 0),
        game_type=data.get("gameType", 2),
        game_state=data.get("gameState", "FUT"),
        venue=data.get("venue", {}).get("default"),
        attendance=data.get("attendance"),
        three_stars=three_stars,
        highlights=highlights,
        home_team=home_team,
        away_team=away_team,
        neutral_site=data.get("neutralSite", False),
        game_outcome_last_play=data.get("summary", {})
        .get("gameOutcome", {})
        .get("lastPeriodType"),
        raw_data=data if include_raw else None,
    )


class GamecenterLandingDownloader(BaseDownloader):
    """Downloads NHL gamecenter landing page data.

    The landing page contains game overview information including:
    - Three stars of the game
    - Highlights and video links
    - Team matchup summaries
    - Game metadata (venue, attendance, etc.)

    Example:
        config = GamecenterLandingDownloaderConfig()
        async with GamecenterLandingDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)
            landing = result.data
    """

    def __init__(
        self,
        config: GamecenterLandingDownloaderConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the downloader.

        Args:
            config: Downloader configuration
            **kwargs: Additional arguments passed to BaseDownloader
        """
        if config is None:
            config = GamecenterLandingDownloaderConfig()
        self._include_raw = config.include_raw_response
        super().__init__(config, **kwargs)

    @property
    def source_name(self) -> str:
        """Return unique identifier for this source."""
        return "nhl_json_gamecenter_landing"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Fetch landing page data for a specific game.

        Args:
            game_id: NHL game ID

        Returns:
            Parsed landing page data as a dictionary

        Raises:
            DownloadError: If the fetch fails
        """
        logger.debug("Fetching gamecenter landing for game %d", game_id)

        response = await self._get(f"/v1/gamecenter/{game_id}/landing")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch landing for game {game_id}: HTTP {response.status}",
                source=self.source_name,
                game_id=game_id,
            )

        data = response.json()
        parsed = _parse_landing(data, include_raw=self._include_raw)

        return {
            "game_id": parsed.game_id,
            "season_id": parsed.season_id,
            "game_type": parsed.game_type,
            "game_state": parsed.game_state,
            "venue": parsed.venue,
            "attendance": parsed.attendance,
            "three_stars": [
                {
                    "star": s.star,
                    "player_id": s.player_id,
                    "name": s.name,
                    "team_abbrev": s.team_abbrev,
                    "position": s.position,
                    "goals": s.goals,
                    "assists": s.assists,
                    "points": s.points,
                }
                for s in parsed.three_stars
            ],
            "highlights": [
                {
                    "highlight_id": h.highlight_id,
                    "title": h.title,
                    "description": h.description,
                    "duration": h.duration,
                    "thumbnail_url": h.thumbnail_url,
                    "video_url": h.video_url,
                }
                for h in parsed.highlights
            ],
            "home_team": {
                "team_id": parsed.home_team.team_id,
                "abbrev": parsed.home_team.abbrev,
                "name": parsed.home_team.name,
                "record": parsed.home_team.record,
            }
            if parsed.home_team
            else None,
            "away_team": {
                "team_id": parsed.away_team.team_id,
                "abbrev": parsed.away_team.abbrev,
                "name": parsed.away_team.name,
                "record": parsed.away_team.record,
            }
            if parsed.away_team
            else None,
            "neutral_site": parsed.neutral_site,
            "game_outcome_last_play": parsed.game_outcome_last_play,
            "raw_data": parsed.raw_data,
        }

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Yield game IDs for a season.

        This downloader relies on the schedule to provide game IDs.
        Import and use ScheduleDownloader to get the list.

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

    async def get_landing(self, game_id: int) -> ParsedGamecenterLanding:
        """Get parsed landing page data for a game.

        Convenience method that returns typed data.

        Args:
            game_id: NHL game ID

        Returns:
            Parsed landing page data
        """
        response = await self._get(f"/v1/gamecenter/{game_id}/landing")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch landing for game {game_id}: HTTP {response.status}",
                source=self.source_name,
                game_id=game_id,
            )

        return _parse_landing(response.json(), include_raw=self._include_raw)

    async def persist(
        self,
        db: DatabaseService,
        landing: ParsedGamecenterLanding,
    ) -> int:
        """Persist landing data to the database.

        Stores three stars and game metadata.

        Args:
            db: Database service instance
            landing: Parsed landing data

        Returns:
            Number of records upserted
        """
        count = 0

        # Update game record with attendance and venue if available
        if landing.attendance or landing.venue:
            await db.execute(
                """
                UPDATE games
                SET attendance = COALESCE($2, attendance),
                    venue = COALESCE($3, venue),
                    updated_at = CURRENT_TIMESTAMP
                WHERE game_id = $1
                """,
                landing.game_id,
                landing.attendance,
                landing.venue,
            )
            count += 1

        # Insert three stars
        for star in landing.three_stars:
            await db.execute(
                """
                INSERT INTO game_three_stars (
                    game_id, star_number, player_id, goals, assists
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (game_id, star_number) DO UPDATE SET
                    player_id = EXCLUDED.player_id,
                    goals = EXCLUDED.goals,
                    assists = EXCLUDED.assists,
                    updated_at = CURRENT_TIMESTAMP
                """,
                landing.game_id,
                star.star,
                star.player_id,
                star.goals,
                star.assists,
            )
            count += 1

        logger.info("Persisted %d records for game %d", count, landing.game_id)
        return count


def create_gamecenter_landing_downloader(
    *,
    requests_per_second: float = DEFAULT_RATE_LIMIT,
    max_retries: int = 3,
    include_raw_response: bool = False,
) -> GamecenterLandingDownloader:
    """Factory function to create a configured GamecenterLandingDownloader.

    Args:
        requests_per_second: Rate limit for API calls
        max_retries: Maximum retry attempts
        include_raw_response: Whether to include raw JSON in results

    Returns:
        Configured GamecenterLandingDownloader instance
    """
    config = GamecenterLandingDownloaderConfig(
        requests_per_second=requests_per_second,
        max_retries=max_retries,
        include_raw_response=include_raw_response,
    )
    return GamecenterLandingDownloader(config)
