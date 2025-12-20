"""NHL JSON API Player Landing Downloader.

Downloads detailed player profile pages from the NHL JSON API, including
biographical information, career stats, season-by-season breakdowns, and
recent game performance.

API Endpoint: GET https://api-web.nhle.com/v1/player/{player_id}/landing

Example usage:
    config = PlayerLandingDownloaderConfig()
    async with PlayerLandingDownloader(config) as downloader:
        result = await downloader.download_player(8478402)  # Connor McDavid
        player = result.data
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
from nhl_api.downloaders.base.protocol import (
    DownloadError,
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


@dataclass
class PlayerLandingDownloaderConfig(DownloaderConfig):
    """Configuration for the Player Landing Downloader.

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
class DraftDetails:
    """Player draft information.

    Attributes:
        year: Draft year
        team_abbrev: Team that drafted the player
        round: Draft round
        pick_in_round: Pick within the round
        overall_pick: Overall pick number
    """

    year: int
    team_abbrev: str
    round: int
    pick_in_round: int
    overall_pick: int


@dataclass(frozen=True, slots=True)
class SkaterCareerStats:
    """Career statistics for a skater.

    Attributes:
        games_played: Total games played
        goals: Total goals
        assists: Total assists
        points: Total points
        plus_minus: Career plus/minus
        pim: Penalties in minutes
        game_winning_goals: Game winning goals
        ot_goals: Overtime goals
        shots: Total shots
        shooting_pct: Career shooting percentage
        power_play_goals: Power play goals
        power_play_points: Power play points
        shorthanded_goals: Shorthanded goals
        shorthanded_points: Shorthanded points
        avg_toi: Average time on ice (MM:SS format)
        faceoff_winning_pct: Faceoff winning percentage
    """

    games_played: int
    goals: int
    assists: int
    points: int
    plus_minus: int
    pim: int
    game_winning_goals: int
    ot_goals: int
    shots: int
    shooting_pct: float
    power_play_goals: int
    power_play_points: int
    shorthanded_goals: int
    shorthanded_points: int
    avg_toi: str
    faceoff_winning_pct: float


@dataclass(frozen=True, slots=True)
class GoalieCareerStats:
    """Career statistics for a goalie.

    Attributes:
        games_played: Total games played
        games_started: Total games started
        wins: Total wins
        losses: Total losses
        ot_losses: Overtime losses
        shutouts: Total shutouts
        goals_against_avg: Goals against average
        save_pct: Save percentage
        goals_against: Total goals against
        shots_against: Total shots against
        goals: Goalie goals scored
        assists: Goalie assists
        pim: Penalties in minutes
        time_on_ice: Total time on ice (HH:MM:SS format)
    """

    games_played: int
    games_started: int
    wins: int
    losses: int
    ot_losses: int
    shutouts: int
    goals_against_avg: float
    save_pct: float
    goals_against: int
    shots_against: int
    goals: int
    assists: int
    pim: int
    time_on_ice: str


@dataclass(frozen=True, slots=True)
class SkaterSeasonStats:
    """Season statistics for a skater.

    Attributes:
        season: Season ID (e.g., 20242025)
        game_type_id: Game type (2=regular, 3=playoffs)
        league_abbrev: League abbreviation (NHL, OHL, etc.)
        team_name: Team name
        games_played: Games played
        goals: Goals
        assists: Assists
        points: Points
        plus_minus: Plus/minus
        pim: Penalties in minutes
        game_winning_goals: Game winning goals
        power_play_goals: Power play goals
        shorthanded_goals: Shorthanded goals
        shots: Shots on goal
        shooting_pct: Shooting percentage
        avg_toi: Average time on ice
        faceoff_winning_pct: Faceoff winning percentage
        sequence: Sequence within season (for multiple teams)
    """

    season: int
    game_type_id: int
    league_abbrev: str
    team_name: str
    games_played: int
    goals: int
    assists: int
    points: int
    plus_minus: int | None
    pim: int
    game_winning_goals: int | None
    power_play_goals: int | None
    shorthanded_goals: int | None
    shots: int | None
    shooting_pct: float | None
    avg_toi: str | None
    faceoff_winning_pct: float | None
    sequence: int


@dataclass(frozen=True, slots=True)
class GoalieSeasonStats:
    """Season statistics for a goalie.

    Attributes:
        season: Season ID (e.g., 20242025)
        game_type_id: Game type (2=regular, 3=playoffs)
        league_abbrev: League abbreviation (NHL, OHL, etc.)
        team_name: Team name
        games_played: Games played
        games_started: Games started
        wins: Wins
        losses: Losses
        ot_losses: Overtime losses
        shutouts: Shutouts
        goals_against: Goals against
        goals_against_avg: Goals against average
        shots_against: Shots against
        save_pct: Save percentage
        time_on_ice: Total time on ice
        sequence: Sequence within season (for multiple teams)
    """

    season: int
    game_type_id: int
    league_abbrev: str
    team_name: str
    games_played: int
    games_started: int | None
    wins: int | None
    losses: int | None
    ot_losses: int | None
    shutouts: int | None
    goals_against: int | None
    goals_against_avg: float | None
    shots_against: int | None
    save_pct: float | None
    time_on_ice: str | None
    sequence: int


@dataclass(frozen=True, slots=True)
class RecentGame:
    """Recent game performance for a player.

    Attributes:
        game_id: NHL game ID
        game_date: Game date (YYYY-MM-DD)
        opponent_abbrev: Opponent team abbreviation
        home_road_flag: H for home, R for road
        team_abbrev: Player's team abbreviation
    """

    game_id: int
    game_date: str
    opponent_abbrev: str
    home_road_flag: str
    team_abbrev: str


@dataclass(frozen=True, slots=True)
class SkaterRecentGame(RecentGame):
    """Recent game for a skater with stats.

    Attributes:
        goals: Goals in game
        assists: Assists in game
        points: Points in game
        plus_minus: Plus/minus in game
        pim: Penalties in minutes
        shots: Shots on goal
        toi: Time on ice (MM:SS format)
        shifts: Number of shifts
        power_play_goals: Power play goals
        shorthanded_goals: Shorthanded goals
    """

    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    pim: int = 0
    shots: int = 0
    toi: str = "0:00"
    shifts: int = 0
    power_play_goals: int = 0
    shorthanded_goals: int = 0


@dataclass(frozen=True, slots=True)
class GoalieRecentGame(RecentGame):
    """Recent game for a goalie with stats.

    Attributes:
        decision: Game decision (W, L, OTL, or None)
        goals_against: Goals against
        saves: Saves made (derived from shots - goals)
        shots_against: Shots against
        save_pct: Save percentage
        toi: Time on ice (MM:SS format)
        games_started: 1 if started, 0 otherwise
    """

    decision: str | None = None
    goals_against: int = 0
    saves: int = 0
    shots_against: int = 0
    save_pct: float = 0.0
    toi: str = "0:00"
    games_started: int = 0


@dataclass
class ParsedPlayerLanding:
    """Fully parsed player landing page data.

    Attributes:
        player_id: NHL player ID
        is_active: Whether player is currently active
        first_name: Player first name
        last_name: Player last name
        full_name: Full display name
        current_team_id: Current team ID (None if no current team)
        current_team_abbrev: Current team abbreviation
        sweater_number: Jersey number
        position: Position code (C, L, R, D, G)
        shoots_catches: Handedness (L/R)
        height_inches: Height in inches
        height_cm: Height in centimeters
        weight_lbs: Weight in pounds
        weight_kg: Weight in kilograms
        birth_date: Birth date (YYYY-MM-DD)
        birth_city: Birth city
        birth_state_province: Birth state/province (if applicable)
        birth_country: Birth country code
        headshot_url: URL to player headshot
        hero_image_url: URL to player action shot
        draft_details: Draft information (None if undrafted)
        in_top_100_all_time: Whether player is in NHL top 100 all-time
        in_hhof: Whether player is in Hockey Hall of Fame
        career_regular_season: Career regular season stats
        career_playoffs: Career playoff stats
        season_stats: List of season-by-season stats
        last_5_games: List of recent games
        is_goalie: Whether player is a goalie
    """

    player_id: int
    is_active: bool
    first_name: str
    last_name: str
    full_name: str
    current_team_id: int | None
    current_team_abbrev: str | None
    sweater_number: int | None
    position: str
    shoots_catches: str
    height_inches: int
    height_cm: int
    weight_lbs: int
    weight_kg: int
    birth_date: str
    birth_city: str
    birth_state_province: str | None
    birth_country: str
    headshot_url: str | None
    hero_image_url: str | None
    draft_details: DraftDetails | None
    in_top_100_all_time: bool
    in_hhof: bool
    career_regular_season: SkaterCareerStats | GoalieCareerStats | None = None
    career_playoffs: SkaterCareerStats | GoalieCareerStats | None = None
    season_stats: list[SkaterSeasonStats | GoalieSeasonStats] = field(
        default_factory=list
    )
    last_5_games: list[SkaterRecentGame | GoalieRecentGame] = field(
        default_factory=list
    )
    is_goalie: bool = False


class PlayerLandingDownloader(BaseDownloader):
    """Downloads player landing pages from the NHL JSON API.

    This downloader fetches detailed player profile pages including
    biographical information, career stats, season breakdowns, and
    recent game performance.

    The landing endpoint provides:
    - Full biographical details (name, height, weight, birth info)
    - Draft information (year, round, pick, team)
    - Career totals (regular season and playoffs)
    - Season-by-season stats (NHL and other leagues)
    - Last 5 games played

    Example:
        config = PlayerLandingDownloaderConfig()
        async with PlayerLandingDownloader(config) as downloader:
            # Download a single player
            result = await downloader.download_player(8478402)  # McDavid

            # Access parsed data
            player = result.data
            print(f"Player: {player['full_name']}")
            print(f"Career Points: {player['career_regular_season']['points']}")

            # Download multiple players
            downloader.set_player_ids([8478402, 8479318, 8477492])
            async for result in downloader.download_all():
                print(f"Downloaded {result.data['full_name']}")
    """

    def __init__(
        self,
        config: PlayerLandingDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        player_ids: list[int] | None = None,
    ) -> None:
        """Initialize the Player Landing Downloader.

        Args:
            config: Downloader configuration
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            player_ids: Optional list of player IDs to download
        """
        super().__init__(
            config or PlayerLandingDownloaderConfig(),
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
        )
        self._player_ids: list[int] = player_ids or []
        self._include_raw = getattr(config, "include_raw_response", False)

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "nhl_json_player_landing"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Not implemented - this downloader works with players, not games.

        Use download_player() instead.

        Raises:
            NotImplementedError: Always raised
        """
        raise NotImplementedError(
            "PlayerLandingDownloader works with players, not games. "
            "Use download_player() instead."
        )

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Not implemented - this downloader works with players, not games.

        Use download_all() with set_player_ids() instead.

        Raises:
            NotImplementedError: Always raised
        """
        raise NotImplementedError(
            "PlayerLandingDownloader works with players, not games. "
            "Use download_all() with set_player_ids() instead."
        )
        # Make it a proper generator
        if False:  # pragma: no cover
            yield 0

    def set_player_ids(self, player_ids: list[int]) -> None:
        """Set player IDs for batch download.

        This method allows setting the list of player IDs to download.
        Typically these come from the Roster Downloader.

        Args:
            player_ids: List of NHL player IDs
        """
        self._player_ids = list(player_ids)
        logger.debug(
            "%s: Set %d player IDs for download",
            self.source_name,
            len(self._player_ids),
        )

    async def download_player(self, player_id: int) -> DownloadResult:
        """Download landing page for a single player.

        Args:
            player_id: NHL player ID

        Returns:
            DownloadResult with parsed player data

        Raises:
            DownloadError: If the download fails
        """
        data = await self._fetch_player(player_id)
        return DownloadResult(
            source=self.source_name,
            season_id=0,  # Not applicable for player data
            data=data,
            status=DownloadStatus.COMPLETED,
        )

    async def download_all(self) -> AsyncGenerator[DownloadResult, None]:
        """Download landing pages for all configured player IDs.

        Yields:
            DownloadResult for each player

        Note:
            Set player IDs first with set_player_ids() or pass them to constructor.
        """
        if not self._player_ids:
            logger.warning(
                "%s: No player IDs set. Use set_player_ids() first.",
                self.source_name,
            )
            return

        self.set_total_items(len(self._player_ids))

        logger.info(
            "%s: Downloading landing pages for %d players",
            self.source_name,
            len(self._player_ids),
        )

        for player_id in self._player_ids:
            try:
                result = await self.download_player(player_id)
                yield result
            except DownloadError as e:
                logger.warning(
                    "%s: Failed to download player %d: %s",
                    self.source_name,
                    player_id,
                    e,
                )
                yield DownloadResult(
                    source=self.source_name,
                    season_id=0,
                    data={"player_id": player_id},
                    status=DownloadStatus.FAILED,
                    error_message=str(e),
                )

    async def _fetch_player(self, player_id: int) -> dict[str, Any]:
        """Fetch landing page data for a single player.

        Args:
            player_id: NHL player ID

        Returns:
            Parsed player data as a dictionary

        Raises:
            DownloadError: If the fetch fails
        """
        path = f"/v1/player/{player_id}/landing"
        logger.debug("%s: Fetching landing for player %d", self.source_name, player_id)

        try:
            response = await self._get(path)

            if not response.is_success:
                raise DownloadError(
                    f"Failed to fetch player {player_id} landing: HTTP {response.status}",
                    source=self.source_name,
                )

            raw_data = response.json()
            parsed = self._parse_player_landing(raw_data)

            # Convert to dict for DownloadResult
            result = self._player_to_dict(parsed)

            # Optionally include raw response
            if self._include_raw:
                result["_raw"] = raw_data

            return result

        except DownloadError:
            raise
        except ValueError as e:
            raise DownloadError(
                f"Failed to parse player {player_id} landing JSON: {e}",
                source=self.source_name,
                cause=e,
            ) from e
        except Exception as e:
            raise DownloadError(
                f"Unexpected error fetching player {player_id} landing: {e}",
                source=self.source_name,
                cause=e,
            ) from e

    def _parse_player_landing(self, data: dict[str, Any]) -> ParsedPlayerLanding:
        """Parse raw API response into structured player data.

        Args:
            data: Raw JSON response from API

        Returns:
            Parsed player landing data
        """
        # Determine if player is a goalie
        position = data.get("position", "")
        is_goalie = position == "G"

        # Extract basic info
        player_id = data.get("playerId", 0)
        is_active = data.get("isActive", False)

        # Parse name
        first_name = self._get_localized(data.get("firstName", {}))
        last_name = self._get_localized(data.get("lastName", {}))
        full_name = f"{first_name} {last_name}"

        # Parse team info
        current_team_id = data.get("currentTeamId")
        current_team_abbrev = data.get("currentTeamAbbrev")
        sweater_number = data.get("sweaterNumber")

        # Parse physical attributes
        height_inches = data.get("heightInInches", 0)
        height_cm = data.get("heightInCentimeters", 0)
        weight_lbs = data.get("weightInPounds", 0)
        weight_kg = data.get("weightInKilograms", 0)

        # Parse birth info
        birth_date = data.get("birthDate", "")
        birth_city = self._get_localized(data.get("birthCity", {}))
        birth_state_province = (
            self._get_localized(data.get("birthStateProvince", {})) or None
        )
        birth_country = data.get("birthCountry", "")

        # Parse draft details
        draft_data = data.get("draftDetails")
        draft_details = None
        if draft_data:
            draft_details = DraftDetails(
                year=draft_data.get("year", 0),
                team_abbrev=draft_data.get("teamAbbrev", ""),
                round=draft_data.get("round", 0),
                pick_in_round=draft_data.get("pickInRound", 0),
                overall_pick=draft_data.get("overallPick", 0),
            )

        # Parse images
        headshot_url = data.get("headshot")
        hero_image_url = data.get("heroImage")

        # Parse career stats
        career_totals = data.get("careerTotals", {})
        career_regular_season: SkaterCareerStats | GoalieCareerStats | None = None
        career_playoffs: SkaterCareerStats | GoalieCareerStats | None = None

        if is_goalie:
            if career_totals.get("regularSeason"):
                career_regular_season = self._parse_goalie_career_stats(
                    career_totals["regularSeason"]
                )
            if career_totals.get("playoffs"):
                career_playoffs = self._parse_goalie_career_stats(
                    career_totals["playoffs"]
                )
        else:
            if career_totals.get("regularSeason"):
                career_regular_season = self._parse_skater_career_stats(
                    career_totals["regularSeason"]
                )
            if career_totals.get("playoffs"):
                career_playoffs = self._parse_skater_career_stats(
                    career_totals["playoffs"]
                )

        # Parse season stats
        season_stats: list[SkaterSeasonStats | GoalieSeasonStats] = []
        for season_data in data.get("seasonTotals", []):
            if is_goalie:
                season_stats.append(self._parse_goalie_season_stats(season_data))
            else:
                season_stats.append(self._parse_skater_season_stats(season_data))

        # Parse last 5 games
        last_5_games: list[SkaterRecentGame | GoalieRecentGame] = []
        for game_data in data.get("last5Games", []):
            if is_goalie:
                last_5_games.append(self._parse_goalie_recent_game(game_data))
            else:
                last_5_games.append(self._parse_skater_recent_game(game_data))

        return ParsedPlayerLanding(
            player_id=player_id,
            is_active=is_active,
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            current_team_id=current_team_id,
            current_team_abbrev=current_team_abbrev,
            sweater_number=sweater_number,
            position=position,
            shoots_catches=data.get("shootsCatches", ""),
            height_inches=height_inches,
            height_cm=height_cm,
            weight_lbs=weight_lbs,
            weight_kg=weight_kg,
            birth_date=birth_date,
            birth_city=birth_city,
            birth_state_province=birth_state_province,
            birth_country=birth_country,
            headshot_url=headshot_url,
            hero_image_url=hero_image_url,
            draft_details=draft_details,
            in_top_100_all_time=bool(data.get("inTop100AllTime", 0)),
            in_hhof=bool(data.get("inHHOF", 0)),
            career_regular_season=career_regular_season,
            career_playoffs=career_playoffs,
            season_stats=season_stats,
            last_5_games=last_5_games,
            is_goalie=is_goalie,
        )

    def _get_localized(
        self, value: dict[str, str] | str | None, key: str = "default"
    ) -> str:
        """Extract localized string value.

        Args:
            value: Localized string dict or plain string
            key: Locale key to extract (default: "default")

        Returns:
            Extracted string or empty string
        """
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return str(value.get(key, ""))
        return ""

    def _parse_skater_career_stats(self, data: dict[str, Any]) -> SkaterCareerStats:
        """Parse skater career statistics."""
        return SkaterCareerStats(
            games_played=data.get("gamesPlayed", 0),
            goals=data.get("goals", 0),
            assists=data.get("assists", 0),
            points=data.get("points", 0),
            plus_minus=data.get("plusMinus", 0),
            pim=data.get("pim", 0),
            game_winning_goals=data.get("gameWinningGoals", 0),
            ot_goals=data.get("otGoals", 0),
            shots=data.get("shots", 0),
            shooting_pct=data.get("shootingPctg", 0.0),
            power_play_goals=data.get("powerPlayGoals", 0),
            power_play_points=data.get("powerPlayPoints", 0),
            shorthanded_goals=data.get("shorthandedGoals", 0),
            shorthanded_points=data.get("shorthandedPoints", 0),
            avg_toi=data.get("avgToi", "0:00"),
            faceoff_winning_pct=data.get("faceoffWinningPctg", 0.0),
        )

    def _parse_goalie_career_stats(self, data: dict[str, Any]) -> GoalieCareerStats:
        """Parse goalie career statistics."""
        return GoalieCareerStats(
            games_played=data.get("gamesPlayed", 0),
            games_started=data.get("gamesStarted", 0),
            wins=data.get("wins", 0),
            losses=data.get("losses", 0),
            ot_losses=data.get("otLosses", 0),
            shutouts=data.get("shutouts", 0),
            goals_against_avg=data.get("goalsAgainstAvg", 0.0),
            save_pct=data.get("savePctg", 0.0),
            goals_against=data.get("goalsAgainst", 0),
            shots_against=data.get("shotsAgainst", 0),
            goals=data.get("goals", 0),
            assists=data.get("assists", 0),
            pim=data.get("pim", 0),
            time_on_ice=data.get("timeOnIce", "0:00"),
        )

    def _parse_skater_season_stats(self, data: dict[str, Any]) -> SkaterSeasonStats:
        """Parse skater season statistics."""
        team_name = self._get_localized(data.get("teamName", {}))

        return SkaterSeasonStats(
            season=data.get("season", 0),
            game_type_id=data.get("gameTypeId", 2),
            league_abbrev=data.get("leagueAbbrev", ""),
            team_name=team_name,
            games_played=data.get("gamesPlayed", 0),
            goals=data.get("goals", 0),
            assists=data.get("assists", 0),
            points=data.get("points", 0),
            plus_minus=data.get("plusMinus"),
            pim=data.get("pim", 0),
            game_winning_goals=data.get("gameWinningGoals"),
            power_play_goals=data.get("powerPlayGoals"),
            shorthanded_goals=data.get("shorthandedGoals"),
            shots=data.get("shots"),
            shooting_pct=data.get("shootingPctg"),
            avg_toi=data.get("avgToi"),
            faceoff_winning_pct=data.get("faceoffWinningPctg"),
            sequence=data.get("sequence", 1),
        )

    def _parse_goalie_season_stats(self, data: dict[str, Any]) -> GoalieSeasonStats:
        """Parse goalie season statistics."""
        team_name = self._get_localized(data.get("teamName", {}))

        return GoalieSeasonStats(
            season=data.get("season", 0),
            game_type_id=data.get("gameTypeId", 2),
            league_abbrev=data.get("leagueAbbrev", ""),
            team_name=team_name,
            games_played=data.get("gamesPlayed", 0),
            games_started=data.get("gamesStarted"),
            wins=data.get("wins"),
            losses=data.get("losses"),
            ot_losses=data.get("otLosses"),
            shutouts=data.get("shutouts"),
            goals_against=data.get("goalsAgainst"),
            goals_against_avg=data.get("goalsAgainstAvg"),
            shots_against=data.get("shotsAgainst"),
            save_pct=data.get("savePctg"),
            time_on_ice=data.get("timeOnIce"),
            sequence=data.get("sequence", 1),
        )

    def _parse_skater_recent_game(self, data: dict[str, Any]) -> SkaterRecentGame:
        """Parse skater recent game data."""
        return SkaterRecentGame(
            game_id=data.get("gameId", 0),
            game_date=data.get("gameDate", ""),
            opponent_abbrev=data.get("opponentAbbrev", ""),
            home_road_flag=data.get("homeRoadFlag", ""),
            team_abbrev=data.get("teamAbbrev", ""),
            goals=data.get("goals", 0),
            assists=data.get("assists", 0),
            points=data.get("points", 0),
            plus_minus=data.get("plusMinus", 0),
            pim=data.get("pim", 0),
            shots=data.get("shots", 0),
            toi=data.get("toi", "0:00"),
            shifts=data.get("shifts", 0),
            power_play_goals=data.get("powerPlayGoals", 0),
            shorthanded_goals=data.get("shorthandedGoals", 0),
        )

    def _parse_goalie_recent_game(self, data: dict[str, Any]) -> GoalieRecentGame:
        """Parse goalie recent game data."""
        shots_against = data.get("shotsAgainst", 0)
        goals_against = data.get("goalsAgainst", 0)
        saves = shots_against - goals_against

        return GoalieRecentGame(
            game_id=data.get("gameId", 0),
            game_date=data.get("gameDate", ""),
            opponent_abbrev=data.get("opponentAbbrev", ""),
            home_road_flag=data.get("homeRoadFlag", ""),
            team_abbrev=data.get("teamAbbrev", ""),
            decision=data.get("decision"),
            goals_against=goals_against,
            saves=saves,
            shots_against=shots_against,
            save_pct=data.get("savePctg", 0.0),
            toi=data.get("toi", "0:00"),
            games_started=data.get("gamesStarted", 0),
        )

    def _player_to_dict(self, player: ParsedPlayerLanding) -> dict[str, Any]:
        """Convert ParsedPlayerLanding to dictionary.

        Args:
            player: Parsed player data

        Returns:
            Dictionary representation
        """
        result: dict[str, Any] = {
            "player_id": player.player_id,
            "is_active": player.is_active,
            "first_name": player.first_name,
            "last_name": player.last_name,
            "full_name": player.full_name,
            "current_team_id": player.current_team_id,
            "current_team_abbrev": player.current_team_abbrev,
            "sweater_number": player.sweater_number,
            "position": player.position,
            "shoots_catches": player.shoots_catches,
            "height_inches": player.height_inches,
            "height_cm": player.height_cm,
            "weight_lbs": player.weight_lbs,
            "weight_kg": player.weight_kg,
            "birth_date": player.birth_date,
            "birth_city": player.birth_city,
            "birth_state_province": player.birth_state_province,
            "birth_country": player.birth_country,
            "headshot_url": player.headshot_url,
            "hero_image_url": player.hero_image_url,
            "in_top_100_all_time": player.in_top_100_all_time,
            "in_hhof": player.in_hhof,
            "is_goalie": player.is_goalie,
        }

        # Draft details
        if player.draft_details:
            result["draft_details"] = {
                "year": player.draft_details.year,
                "team_abbrev": player.draft_details.team_abbrev,
                "round": player.draft_details.round,
                "pick_in_round": player.draft_details.pick_in_round,
                "overall_pick": player.draft_details.overall_pick,
            }
        else:
            result["draft_details"] = None

        # Career stats
        if player.is_goalie:
            result["career_regular_season"] = (
                self._goalie_career_to_dict(player.career_regular_season)
                if player.career_regular_season
                else None
            )
            result["career_playoffs"] = (
                self._goalie_career_to_dict(player.career_playoffs)
                if player.career_playoffs
                else None
            )
        else:
            result["career_regular_season"] = (
                self._skater_career_to_dict(player.career_regular_season)
                if player.career_regular_season
                else None
            )
            result["career_playoffs"] = (
                self._skater_career_to_dict(player.career_playoffs)
                if player.career_playoffs
                else None
            )

        # Season stats
        if player.is_goalie:
            result["season_stats"] = [
                self._goalie_season_to_dict(s) for s in player.season_stats
            ]
            result["last_5_games"] = [
                self._goalie_game_to_dict(g) for g in player.last_5_games
            ]
        else:
            result["season_stats"] = [
                self._skater_season_to_dict(s) for s in player.season_stats
            ]
            result["last_5_games"] = [
                self._skater_game_to_dict(g) for g in player.last_5_games
            ]

        return result

    def _skater_career_to_dict(
        self, stats: SkaterCareerStats | GoalieCareerStats | None
    ) -> dict[str, Any] | None:
        """Convert skater career stats to dictionary."""
        if not stats or not isinstance(stats, SkaterCareerStats):
            return None
        return {
            "games_played": stats.games_played,
            "goals": stats.goals,
            "assists": stats.assists,
            "points": stats.points,
            "plus_minus": stats.plus_minus,
            "pim": stats.pim,
            "game_winning_goals": stats.game_winning_goals,
            "ot_goals": stats.ot_goals,
            "shots": stats.shots,
            "shooting_pct": stats.shooting_pct,
            "power_play_goals": stats.power_play_goals,
            "power_play_points": stats.power_play_points,
            "shorthanded_goals": stats.shorthanded_goals,
            "shorthanded_points": stats.shorthanded_points,
            "avg_toi": stats.avg_toi,
            "faceoff_winning_pct": stats.faceoff_winning_pct,
        }

    def _goalie_career_to_dict(
        self, stats: SkaterCareerStats | GoalieCareerStats | None
    ) -> dict[str, Any] | None:
        """Convert goalie career stats to dictionary."""
        if not stats or not isinstance(stats, GoalieCareerStats):
            return None
        return {
            "games_played": stats.games_played,
            "games_started": stats.games_started,
            "wins": stats.wins,
            "losses": stats.losses,
            "ot_losses": stats.ot_losses,
            "shutouts": stats.shutouts,
            "goals_against_avg": stats.goals_against_avg,
            "save_pct": stats.save_pct,
            "goals_against": stats.goals_against,
            "shots_against": stats.shots_against,
            "goals": stats.goals,
            "assists": stats.assists,
            "pim": stats.pim,
            "time_on_ice": stats.time_on_ice,
        }

    def _skater_season_to_dict(
        self, stats: SkaterSeasonStats | GoalieSeasonStats
    ) -> dict[str, Any]:
        """Convert skater season stats to dictionary."""
        if not isinstance(stats, SkaterSeasonStats):
            return {}
        return {
            "season": stats.season,
            "game_type_id": stats.game_type_id,
            "league_abbrev": stats.league_abbrev,
            "team_name": stats.team_name,
            "games_played": stats.games_played,
            "goals": stats.goals,
            "assists": stats.assists,
            "points": stats.points,
            "plus_minus": stats.plus_minus,
            "pim": stats.pim,
            "game_winning_goals": stats.game_winning_goals,
            "power_play_goals": stats.power_play_goals,
            "shorthanded_goals": stats.shorthanded_goals,
            "shots": stats.shots,
            "shooting_pct": stats.shooting_pct,
            "avg_toi": stats.avg_toi,
            "faceoff_winning_pct": stats.faceoff_winning_pct,
            "sequence": stats.sequence,
        }

    def _goalie_season_to_dict(
        self, stats: SkaterSeasonStats | GoalieSeasonStats
    ) -> dict[str, Any]:
        """Convert goalie season stats to dictionary."""
        if not isinstance(stats, GoalieSeasonStats):
            return {}
        return {
            "season": stats.season,
            "game_type_id": stats.game_type_id,
            "league_abbrev": stats.league_abbrev,
            "team_name": stats.team_name,
            "games_played": stats.games_played,
            "games_started": stats.games_started,
            "wins": stats.wins,
            "losses": stats.losses,
            "ot_losses": stats.ot_losses,
            "shutouts": stats.shutouts,
            "goals_against": stats.goals_against,
            "goals_against_avg": stats.goals_against_avg,
            "shots_against": stats.shots_against,
            "save_pct": stats.save_pct,
            "time_on_ice": stats.time_on_ice,
            "sequence": stats.sequence,
        }

    def _skater_game_to_dict(
        self, game: SkaterRecentGame | GoalieRecentGame
    ) -> dict[str, Any]:
        """Convert skater recent game to dictionary."""
        if not isinstance(game, SkaterRecentGame):
            return {}
        return {
            "game_id": game.game_id,
            "game_date": game.game_date,
            "opponent_abbrev": game.opponent_abbrev,
            "home_road_flag": game.home_road_flag,
            "team_abbrev": game.team_abbrev,
            "goals": game.goals,
            "assists": game.assists,
            "points": game.points,
            "plus_minus": game.plus_minus,
            "pim": game.pim,
            "shots": game.shots,
            "toi": game.toi,
            "shifts": game.shifts,
            "power_play_goals": game.power_play_goals,
            "shorthanded_goals": game.shorthanded_goals,
        }

    def _goalie_game_to_dict(
        self, game: SkaterRecentGame | GoalieRecentGame
    ) -> dict[str, Any]:
        """Convert goalie recent game to dictionary."""
        if not isinstance(game, GoalieRecentGame):
            return {}
        return {
            "game_id": game.game_id,
            "game_date": game.game_date,
            "opponent_abbrev": game.opponent_abbrev,
            "home_road_flag": game.home_road_flag,
            "team_abbrev": game.team_abbrev,
            "decision": game.decision,
            "goals_against": game.goals_against,
            "saves": game.saves,
            "shots_against": game.shots_against,
            "save_pct": game.save_pct,
            "toi": game.toi,
            "games_started": game.games_started,
        }
