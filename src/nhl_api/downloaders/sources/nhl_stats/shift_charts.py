"""NHL Stats API Shift Charts Downloader.

Downloads shift-by-shift tracking data for skaters in each game,
including shift start/end times, duration, and player identification.

API Endpoint: GET https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={game_id}

Example usage:
    async with create_shift_charts_downloader() as downloader:
        # Set game IDs (typically from Schedule downloader)
        downloader.set_game_ids([2024020500, 2024020501])

        # Download season data
        async for result in downloader.download_season(20242025):
            if result.is_successful:
                print(f"Downloaded {len(result.data['shifts'])} shifts")
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nhl_api.downloaders.base.protocol import DownloadError
from nhl_api.downloaders.sources.nhl_stats.base_stats_downloader import (
    DEFAULT_STATS_RATE_LIMIT,
    NHL_STATS_API_BASE_URL,
    BaseStatsDownloader,
    StatsDownloaderConfig,
)
from nhl_api.models.shifts import (
    GOAL_TYPE_CODE,
    ParsedShiftChart,
    ShiftRecord,
    parse_duration,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from nhl_api.downloaders.base.rate_limiter import RateLimiter
    from nhl_api.downloaders.base.retry_handler import RetryHandler
    from nhl_api.services.db import DatabaseService
    from nhl_api.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)


@dataclass
class ShiftChartsDownloaderConfig(StatsDownloaderConfig):
    """Configuration for Shift Charts downloader.

    Attributes:
        base_url: NHL Stats API base URL
        requests_per_second: Rate limit (default: 5.0)
        max_retries: Maximum retry attempts
        retry_base_delay: Initial delay between retries
        http_timeout: HTTP request timeout
        include_raw_response: Whether to include raw JSON in results
    """

    base_url: str = NHL_STATS_API_BASE_URL
    requests_per_second: float = DEFAULT_STATS_RATE_LIMIT
    include_raw_response: bool = False


class ShiftChartsDownloader(BaseStatsDownloader):
    """Downloader for NHL shift chart data.

    Fetches shift-by-shift data for all players in a game from the
    NHL Stats REST API.

    Example:
        async with create_shift_charts_downloader() as downloader:
            downloader.set_game_ids([2024020500])
            async for result in downloader.download_season(20242025):
                chart = result.data
                print(f"Game {chart['game_id']}: {chart['total_shifts']} shifts")
    """

    def __init__(
        self,
        config: ShiftChartsDownloaderConfig | None = None,
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        game_ids: list[int] | None = None,
    ) -> None:
        """Initialize the shift charts downloader.

        Args:
            config: Downloader configuration
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            game_ids: Optional list of game IDs to download
        """
        super().__init__(
            config or ShiftChartsDownloaderConfig(),
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
            game_ids=game_ids,
        )
        self._config: ShiftChartsDownloaderConfig = self.config  # type: ignore[assignment]

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source.

        Matches 'shift_chart' in data_sources table (source_id=16).
        """
        return "shift_chart"

    async def _fetch_game(self, game_id: int) -> dict[str, Any]:
        """Fetch and parse shift chart data for a single game.

        Args:
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed shift chart data

        Raises:
            DownloadError: If the fetch or parse fails
        """
        path = self._build_cayenne_path("/shiftcharts", game_id=game_id)

        logger.debug("%s: Fetching shifts for game %d", self.source_name, game_id)
        response = await self._get(path)

        if not response.is_success:
            raise DownloadError(
                f"Failed to fetch shift charts: HTTP {response.status}",
                source=self.source_name,
                game_id=game_id,
            )

        raw_data = response.json()
        records = self._validate_stats_response(raw_data, game_id=game_id)

        parsed = self._parse_shift_chart(records, game_id)

        result = parsed.to_dict()

        if self._config.include_raw_response:
            result["_raw"] = raw_data

        logger.debug(
            "%s: Parsed %d shifts for game %d",
            self.source_name,
            len(parsed.shifts),
            game_id,
        )

        return result

    async def _fetch_season_games(self, season_id: int) -> AsyncGenerator[int, None]:
        """Yield game IDs for a season.

        Game IDs should be set via set_game_ids() before calling.
        Typically populated from the Schedule downloader.

        Args:
            season_id: NHL season ID (e.g., 20242025)

        Yields:
            Game IDs for the season
        """
        if not self._game_ids:
            logger.warning(
                "%s: No game IDs set for season %d. Use set_game_ids().",
                self.source_name,
                season_id,
            )
            return

        self.set_total_items(len(self._game_ids))
        for game_id in self._game_ids:
            yield game_id

    def _parse_shift_chart(
        self,
        records: list[dict[str, Any]],
        game_id: int,
    ) -> ParsedShiftChart:
        """Parse API response into ParsedShiftChart.

        Args:
            records: List of shift records from API
            game_id: NHL game ID

        Returns:
            ParsedShiftChart with all shift data
        """
        shifts: list[ShiftRecord] = []
        team_ids: set[int] = set()

        for record in records:
            shift = self._parse_shift_record(record, game_id)
            shifts.append(shift)
            team_ids.add(shift.team_id)

        # Determine home/away teams
        # In NHL Stats API, the team with more shifts is usually home
        # but we can't reliably determine this without additional data
        home_team_id = None
        away_team_id = None
        if len(team_ids) == 2:
            team_list = list(team_ids)
            # Just assign arbitrarily - caller should use game data for accurate info
            home_team_id = team_list[0]
            away_team_id = team_list[1]

        # Extract season_id from game_id
        season_start = game_id // 1000000
        season_id = season_start * 10000 + season_start + 1

        return ParsedShiftChart(
            game_id=game_id,
            season_id=season_id,
            total_shifts=len(shifts),
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            shifts=shifts,
        )

    def _parse_shift_record(
        self,
        record: dict[str, Any],
        game_id: int,
    ) -> ShiftRecord:
        """Parse a single shift record from API response.

        Args:
            record: Raw shift record from API
            game_id: NHL game ID

        Returns:
            ShiftRecord dataclass
        """
        type_code = record.get("typeCode", 517)
        is_goal_event = type_code == GOAL_TYPE_CODE

        return ShiftRecord(
            shift_id=record.get("id", 0),
            game_id=game_id,
            player_id=record.get("playerId", 0),
            first_name=record.get("firstName", ""),
            last_name=record.get("lastName", ""),
            team_id=record.get("teamId", 0),
            team_abbrev=record.get("teamAbbrev", ""),
            period=record.get("period", 0),
            shift_number=record.get("shiftNumber", 0),
            start_time=record.get("startTime", "00:00"),
            end_time=record.get("endTime", "00:00"),
            duration_seconds=parse_duration(record.get("duration")),
            type_code=type_code,
            is_goal_event=is_goal_event,
            event_description=record.get("eventDescription"),
            event_details=record.get("eventDetails"),
            detail_code=record.get("detailCode", 0),
            hex_value=record.get("hexValue"),
        )

    async def persist(
        self,
        db: DatabaseService,
        shift_charts: list[ParsedShiftChart | dict[str, Any]],
    ) -> int:
        """Persist shift charts to database.

        Args:
            db: Database service
            shift_charts: List of parsed shift charts or dicts

        Returns:
            Number of shifts upserted
        """
        count = 0
        for chart_data in shift_charts:
            if isinstance(chart_data, ParsedShiftChart):
                shifts = chart_data.shifts
            else:
                # Convert dict back to ShiftRecord objects
                shifts = [
                    ShiftRecord(**s) if isinstance(s, dict) else s
                    for s in chart_data.get("shifts", [])
                ]

            for shift in shifts:
                await db.execute(
                    """
                    INSERT INTO game_shifts (
                        shift_id, game_id, player_id, team_id, period,
                        shift_number, start_time, end_time, duration_seconds,
                        is_goal_event, event_description, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
                    ON CONFLICT (shift_id) DO UPDATE SET
                        duration_seconds = EXCLUDED.duration_seconds,
                        updated_at = NOW()
                    """,
                    shift.shift_id,
                    shift.game_id,
                    shift.player_id,
                    shift.team_id,
                    shift.period,
                    shift.shift_number,
                    shift.start_time,
                    shift.end_time,
                    shift.duration_seconds,
                    shift.is_goal_event,
                    shift.event_description,
                )
                count += 1

        logger.info(
            "%s: Persisted %d shifts to database",
            self.source_name,
            count,
        )
        return count


def create_shift_charts_downloader(
    *,
    requests_per_second: float = DEFAULT_STATS_RATE_LIMIT,
    max_retries: int = 3,
    include_raw_response: bool = False,
) -> ShiftChartsDownloader:
    """Create a configured ShiftChartsDownloader.

    Args:
        requests_per_second: Rate limit for API requests
        max_retries: Maximum retry attempts
        include_raw_response: Whether to include raw JSON in results

    Returns:
        Configured ShiftChartsDownloader instance
    """
    config = ShiftChartsDownloaderConfig(
        base_url=NHL_STATS_API_BASE_URL,
        requests_per_second=requests_per_second,
        max_retries=max_retries,
        include_raw_response=include_raw_response,
    )
    return ShiftChartsDownloader(config)
