"""NHL Schedule Downloader.

Downloads game schedules from the NHL JSON API (api-web.nhle.com/v1/).
Provides methods to fetch schedules by date, team, or full season.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.base_downloader import (
    BaseDownloader,
    DownloaderConfig,
)
from nhl_api.downloaders.base.protocol import DownloadError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# NHL JSON API base URL
NHL_API_BASE_URL = "https://api-web.nhle.com/v1"

# Map numeric game type to string code for database
GAME_TYPE_MAP = {
    1: "PR",  # Preseason
    2: "R",  # Regular season
    3: "P",  # Playoffs
    4: "A",  # All-Star
}


@dataclass
class GameInfo:
    """Parsed game information from schedule response."""

    game_id: int
    season_id: int
    game_type: int  # 1=preseason, 2=regular, 3=playoffs, 4=allstar
    game_date: date
    start_time_utc: datetime | None
    venue_name: str | None
    home_team_id: int
    home_team_abbrev: str
    home_score: int | None
    away_team_id: int
    away_team_abbrev: str
    away_score: int | None
    game_state: str  # FUT, LIVE, OFF, FINAL, etc.
    period: int | None = None
    is_overtime: bool = False
    is_shootout: bool = False


def _parse_game(game_data: dict[str, Any]) -> GameInfo:
    """Parse a single game from the schedule response.

    Args:
        game_data: Raw game data from API

    Returns:
        Parsed GameInfo object
    """
    # Parse start time
    start_time_str = game_data.get("startTimeUTC")
    start_time = None
    if start_time_str:
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Failed to parse start time: %s", start_time_str)

    # Parse game date from start time or game ID
    game_id = game_data["id"]
    if start_time:
        game_date = start_time.date()
    else:
        # Extract from game ID: 2024020521 -> assume current season
        game_date = date.today()

    # Get team info
    home_team = game_data.get("homeTeam", {})
    away_team = game_data.get("awayTeam", {})

    # Determine overtime/shootout from period info
    period = game_data.get("period")
    period_type = game_data.get("periodDescriptor", {}).get("periodType", "")
    is_overtime = period is not None and period > 3
    is_shootout = period_type == "SO"

    return GameInfo(
        game_id=game_id,
        season_id=game_data.get("season", 0),
        game_type=game_data.get("gameType", 2),
        game_date=game_date,
        start_time_utc=start_time,
        venue_name=game_data.get("venue", {}).get("default"),
        home_team_id=home_team.get("id", 0),
        home_team_abbrev=home_team.get("abbrev", ""),
        home_score=home_team.get("score"),
        away_team_id=away_team.get("id", 0),
        away_team_abbrev=away_team.get("abbrev", ""),
        away_score=away_team.get("score"),
        game_state=game_data.get("gameState", "FUT"),
        period=period,
        is_overtime=is_overtime,
        is_shootout=is_shootout,
    )


class ScheduleDownloader(BaseDownloader):
    """Downloads NHL game schedules.

    Supports multiple access patterns:
    - Single date: get_schedule_for_date()
    - Date range: download games between two dates
    - Full season: download_season()

    Example:
        config = DownloaderConfig(base_url=NHL_API_BASE_URL)
        async with ScheduleDownloader(config) as downloader:
            # Get today's games
            games = await downloader.get_schedule_for_date(date.today())

            # Download full season
            async for result in downloader.download_season(20242025):
                print(f"Downloaded game {result.game_id}")
    """

    @property
    def source_name(self) -> str:
        """Return unique identifier for this source."""
        return "nhl_json_schedule"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Fetch schedule data for a specific game.

        For schedule data, we return the game info from the schedule API
        rather than a separate game endpoint.

        Args:
            game_id: NHL game ID

        Returns:
            Game data dictionary
        """
        # Extract date from game ID to fetch the schedule
        # Game ID format: YYYYTTNNNN where TT=type (02=regular), NNNN=game number
        season_start_year = game_id // 1000000
        game_type = (game_id // 10000) % 100

        # For now, we can't easily derive the exact date from game ID
        # This method is called for individual game fetches
        # We'll return minimal data - the full data comes from schedule endpoints
        return {
            "id": game_id,
            "season": season_start_year * 10000 + season_start_year + 1,
            "gameType": game_type,
            "_source": "schedule_downloader",
            "_note": "Use get_schedule_for_date for full game data",
        }

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Yield all game IDs for a season.

        Fetches the season schedule and yields each game ID.

        Args:
            season_id: Season ID (e.g., 20242025)

        Yields:
            Game IDs for the season
        """
        games = await self.get_season_schedule(season_id)
        self.set_total_items(len(games))

        for game in games:
            yield game.game_id

    async def get_schedule_for_date(self, target_date: date) -> list[GameInfo]:
        """Get all games scheduled for a specific date.

        Args:
            target_date: Date to fetch schedule for

        Returns:
            List of GameInfo objects for games on that date
        """
        date_str = target_date.isoformat()
        logger.debug("Fetching schedule for %s", date_str)

        response = await self._get(f"schedule/{date_str}")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch schedule for {date_str}: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        games: list[GameInfo] = []

        # Parse games from gameWeek structure
        for week in data.get("gameWeek", []):
            if week.get("date") == date_str:
                for game_data in week.get("games", []):
                    try:
                        games.append(_parse_game(game_data))
                    except Exception as e:
                        logger.warning(
                            "Failed to parse game: %s - %s",
                            game_data.get("id"),
                            e,
                        )

        logger.info("Found %d games for %s", len(games), date_str)
        return games

    async def get_schedule_for_week(self, anchor_date: date) -> list[GameInfo]:
        """Get all games for the week containing the anchor date.

        The NHL API returns a full week of games when querying any date.
        This method extracts ALL days from the gameWeek response.

        Args:
            anchor_date: Any date in the week to fetch

        Returns:
            List of GameInfo objects for all games in that week
        """
        date_str = anchor_date.isoformat()
        logger.debug("Fetching week schedule anchored at %s", date_str)

        response = await self._get(f"schedule/{date_str}")

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch schedule for {date_str}: HTTP {response.status}",
                source=self.source_name,
            )

        data = response.json()
        games: list[GameInfo] = []

        # Parse games from ALL days in gameWeek structure
        for day in data.get("gameWeek", []):
            for game_data in day.get("games", []):
                try:
                    games.append(_parse_game(game_data))
                except Exception as e:
                    logger.warning(
                        "Failed to parse game: %s - %s",
                        game_data.get("id"),
                        e,
                    )

        logger.debug("Found %d games for week of %s", len(games), date_str)
        return games

    async def get_season_schedule(
        self,
        season_id: int,
        *,
        game_type: int | None = None,
    ) -> list[GameInfo]:
        """Get complete schedule for a season.

        Iterates through all dates in the season to collect games.

        Args:
            season_id: Season ID (e.g., 20242025)
            game_type: Optional filter (1=pre, 2=regular, 3=playoffs)

        Returns:
            List of all games in the season
        """
        # Determine season date range
        start_year = season_id // 10000
        # Regular season typically Oct 1 - Apr 15, playoffs through June
        season_start = date(start_year, 9, 15)  # Early for preseason
        season_end = date(start_year + 1, 6, 30)

        logger.info(
            "Fetching season %d schedule (%s to %s)",
            season_id,
            season_start,
            season_end,
        )

        all_games: list[GameInfo] = []
        seen_game_ids: set[int] = set()
        current_date = season_start

        while current_date <= season_end:
            try:
                # Use get_schedule_for_week to fetch all games in the week
                week_games = await self.get_schedule_for_week(current_date)

                for game in week_games:
                    # Filter by game type if specified
                    if game_type is not None and game.game_type != game_type:
                        continue

                    # Skip if we've already seen this game
                    if game.game_id in seen_game_ids:
                        continue

                    # Verify it's from the correct season
                    if game.season_id != season_id:
                        continue

                    seen_game_ids.add(game.game_id)
                    all_games.append(game)

            except DownloadError as e:
                # Log but continue - some dates may have no games
                logger.debug("No schedule data for %s: %s", current_date, e)

            # Move to next week (schedule API returns a week at a time)
            current_date += timedelta(days=7)

        logger.info(
            "Found %d total games for season %d",
            len(all_games),
            season_id,
        )

        return sorted(all_games, key=lambda g: (g.game_date, g.game_id))

    async def get_games_in_range(
        self,
        start_date: date,
        end_date: date,
    ) -> list[GameInfo]:
        """Get all games in a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of games in the date range
        """
        all_games: list[GameInfo] = []
        seen_game_ids: set[int] = set()
        current_date = start_date

        while current_date <= end_date:
            try:
                date_games = await self.get_schedule_for_date(current_date)

                for game in date_games:
                    if game.game_id not in seen_game_ids:
                        seen_game_ids.add(game.game_id)
                        all_games.append(game)

            except DownloadError:
                pass  # Some dates may have no games

            current_date += timedelta(days=7)

        return sorted(all_games, key=lambda g: (g.game_date, g.game_id))

    async def persist(
        self,
        db: DatabaseService,
        games: list[GameInfo],
    ) -> int:
        """Persist downloaded games to the database.

        Uses upsert (INSERT ... ON CONFLICT) to handle re-downloads gracefully.
        Updates scores and game state for games that already exist.

        Args:
            db: Database service instance
            games: List of GameInfo objects to persist

        Returns:
            Number of games upserted
        """
        if not games:
            return 0

        count = 0
        for game in games:
            # Convert game_type int to string code
            game_type_str = GAME_TYPE_MAP.get(game.game_type, "R")

            # Extract time from start_time_utc if available
            game_time: time | None = None
            if game.start_time_utc:
                game_time = game.start_time_utc.timetz()

            # Determine game outcome from state
            game_outcome: str | None = None
            if game.game_state in ("OFF", "FINAL"):
                if game.is_shootout:
                    game_outcome = "SO"
                elif game.is_overtime:
                    game_outcome = "OT"
                else:
                    game_outcome = "REG"

            await db.execute(
                """
                INSERT INTO games (
                    game_id, season_id, game_type, game_date, game_time,
                    home_team_id, away_team_id, home_score, away_score,
                    period, game_state, is_overtime, is_shootout, game_outcome
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (game_id, season_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    period = EXCLUDED.period,
                    game_state = EXCLUDED.game_state,
                    is_overtime = EXCLUDED.is_overtime,
                    is_shootout = EXCLUDED.is_shootout,
                    game_outcome = EXCLUDED.game_outcome,
                    updated_at = CURRENT_TIMESTAMP
                """,
                game.game_id,
                game.season_id,
                game_type_str,
                game.game_date,
                game_time,
                game.home_team_id,
                game.away_team_id,
                game.home_score,
                game.away_score,
                game.period,
                game.game_state,
                game.is_overtime,
                game.is_shootout,
                game_outcome,
            )
            count += 1

        logger.info("Persisted %d games to database", count)
        return count


def create_schedule_downloader(
    *,
    requests_per_second: float = 5.0,
    max_retries: int = 3,
) -> ScheduleDownloader:
    """Factory function to create a configured ScheduleDownloader.

    Args:
        requests_per_second: Rate limit for API calls
        max_retries: Maximum retry attempts

    Returns:
        Configured ScheduleDownloader instance
    """
    config = DownloaderConfig(
        base_url=NHL_API_BASE_URL,
        requests_per_second=requests_per_second,
        max_retries=max_retries,
        health_check_url="schedule/now",
    )
    return ScheduleDownloader(config)
