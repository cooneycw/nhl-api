"""NHL Time on Ice (TH/TV) HTML Downloader.

Downloads and parses Time on Ice HTML reports from the NHL website.
These reports contain shift-by-shift data and per-period TOI summaries
for each player.

URL Patterns:
    Home team:  https://www.nhl.com/scores/htmlreports/{season}/TH{game_suffix}.HTM
    Away team:  https://www.nhl.com/scores/htmlreports/{season}/TV{game_suffix}.HTM

Example usage:
    # Home team TOI
    config = HTMLDownloaderConfig()
    async with TimeOnIceDownloader(config, side="home") as downloader:
        result = await downloader.download_game(2024020500)

    # Away team TOI
    async with TimeOnIceDownloader(config, side="away") as downloader:
        result = await downloader.download_game(2024020500)

Note:
    The 'G' column in these reports indicates players on ice during goals,
    NOT the scorers themselves. This is important for analytics.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.sources.html.base_html_downloader import (
    BaseHTMLDownloader,
    HTMLDownloaderConfig,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.base.rate_limiter import RateLimiter
    from nhl_api.downloaders.base.retry_handler import RetryHandler
    from nhl_api.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

# Pattern to extract team abbreviation from image URL
TEAM_LOGO_PATTERN = re.compile(r"logoc([a-z]{3})\.gif", re.IGNORECASE)

# Pattern to parse player heading: "4 GOSTISBEHERE, SHAYNE"
PLAYER_HEADING_PATTERN = re.compile(r"(\d+)\s+(.+)")


@dataclass
class ShiftInfo:
    """Individual shift information.

    Attributes:
        shift_number: Shift number for the player in this game
        period: Period number (1, 2, 3, or OT)
        start_elapsed: Start time (elapsed in period) in "M:SS" format
        start_game: Start time (remaining in period) in "M:SS" format
        end_elapsed: End time (elapsed in period) in "M:SS" format
        end_game: End time (remaining in period) in "M:SS" format
        duration: Shift duration in "MM:SS" format
        event: Event during shift ('G' for goal, 'P' for penalty, or empty)
    """

    shift_number: int
    period: str
    start_elapsed: str
    start_game: str
    end_elapsed: str
    end_game: str
    duration: str
    event: str = ""


@dataclass
class PeriodTOI:
    """Time on ice for a single period.

    Attributes:
        period: Period identifier ('1', '2', '3', 'OT', 'TOT')
        shifts: Number of shifts in this period
        avg_shift: Average shift length in "MM:SS" format
        toi: Total time on ice in "MM:SS" format
        ev_toi: Even strength TOI in "MM:SS" format
        pp_toi: Power play TOI in "MM:SS" format
        sh_toi: Shorthanded TOI in "MM:SS" format
    """

    period: str
    shifts: int
    avg_shift: str
    toi: str
    ev_toi: str
    pp_toi: str
    sh_toi: str


@dataclass
class PlayerTOI:
    """Complete time on ice data for a player.

    Attributes:
        number: Jersey number
        name: Player name (LAST, FIRST format)
        shifts_detail: List of individual shift information
        periods: List of per-period TOI summaries
    """

    number: int
    name: str
    shifts_detail: list[ShiftInfo] = field(default_factory=list)
    periods: list[PeriodTOI] = field(default_factory=list)

    @property
    def total_shifts(self) -> int:
        """Total number of shifts."""
        for period in self.periods:
            if period.period == "TOT":
                return period.shifts
        return sum(p.shifts for p in self.periods if p.period not in ("TOT", "OT"))

    @property
    def total_toi(self) -> str:
        """Total time on ice."""
        for period in self.periods:
            if period.period == "TOT":
                return period.toi
        return "00:00"

    @property
    def ev_toi(self) -> str:
        """Even strength TOI."""
        for period in self.periods:
            if period.period == "TOT":
                return period.ev_toi
        return "00:00"

    @property
    def pp_toi(self) -> str:
        """Power play TOI."""
        for period in self.periods:
            if period.period == "TOT":
                return period.pp_toi
        return "00:00"

    @property
    def sh_toi(self) -> str:
        """Shorthanded TOI."""
        for period in self.periods:
            if period.period == "TOT":
                return period.sh_toi
        return "00:00"

    @property
    def avg_shift(self) -> str:
        """Average shift length."""
        for period in self.periods:
            if period.period == "TOT":
                return period.avg_shift
        return "00:00"

    @property
    def toi_by_period(self) -> dict[str, dict[str, Any]]:
        """TOI breakdown by period."""
        result: dict[str, dict[str, Any]] = {}
        for period in self.periods:
            if period.period != "TOT":
                result[period.period] = {
                    "shifts": period.shifts,
                    "toi": period.toi,
                }
        return result

    @property
    def goals_on_ice(self) -> int:
        """Number of goals scored while this player was on ice."""
        return sum(1 for shift in self.shifts_detail if "G" in shift.event)

    @property
    def penalties_on_ice(self) -> int:
        """Number of penalties taken while this player was on ice."""
        return sum(1 for shift in self.shifts_detail if "P" in shift.event)


@dataclass
class ParsedTimeOnIce:
    """Complete parsed Time on Ice data.

    Attributes:
        game_id: NHL game ID
        season_id: Season ID (e.g., 20242025)
        team: Team name
        team_abbrev: Team abbreviation
        side: 'home' or 'away'
        players: List of player TOI data
    """

    game_id: int
    season_id: int
    team: str
    team_abbrev: str
    side: str
    players: list[PlayerTOI] = field(default_factory=list)


class TimeOnIceDownloader(BaseHTMLDownloader):
    """Downloads and parses NHL Time on Ice HTML reports.

    A single class handles both TH (home) and TV (away) reports based on
    the `side` parameter.

    The Time on Ice report contains:
    - Individual shift data for each player (shift timing, duration, events)
    - Per-period TOI summaries (shifts, avg, TOI, EV/PP/SH breakdown)

    Important: The 'G' column indicates players on ice during goals,
    NOT the scorers themselves.

    Example:
        # Home team
        config = HTMLDownloaderConfig()
        async with TimeOnIceDownloader(config, side="home") as downloader:
            result = await downloader.download_game(2024020500)
            home_toi = result.data

        # Away team
        async with TimeOnIceDownloader(config, side="away") as downloader:
            result = await downloader.download_game(2024020500)
            away_toi = result.data
    """

    def __init__(
        self,
        config: HTMLDownloaderConfig | None = None,
        side: str = "home",
        *,
        http_client: HTTPClient | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_handler: RetryHandler | None = None,
        progress_callback: Callable[..., None] | None = None,
        game_ids: list[int] | None = None,
    ) -> None:
        """Initialize the Time on Ice downloader.

        Args:
            config: Downloader configuration
            side: 'home' for TH reports, 'away' for TV reports
            http_client: Optional custom HTTP client
            rate_limiter: Optional custom rate limiter
            retry_handler: Optional custom retry handler
            progress_callback: Optional callback for progress updates
            game_ids: Optional list of game IDs for season download
        """
        # Set _side BEFORE calling super().__init__() because source_name
        # property (accessed during parent init) depends on it
        self._side = side.lower()
        if self._side not in ("home", "away"):
            raise ValueError(f"Invalid side: {side}. Must be 'home' or 'away'.")

        super().__init__(
            config,
            http_client=http_client,
            rate_limiter=rate_limiter,
            retry_handler=retry_handler,
            progress_callback=progress_callback,
            game_ids=game_ids,
        )

    @property
    def report_type(self) -> str:
        """Return report type code for Time on Ice.

        Returns:
            'TH' for home team, 'TV' for away (visitor) team
        """
        return "TH" if self._side == "home" else "TV"

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source.

        Returns:
            'html_th' for home, 'html_tv' for away
        """
        return f"html_{self.report_type.lower()}"

    @property
    def side(self) -> str:
        """Return the side (home or away) this downloader handles."""
        return self._side

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse Time on Ice HTML into structured data.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed TOI data
        """
        season_id = self._extract_season_from_game_id(game_id)

        # Parse team info from header
        team_name, team_abbrev = self._parse_team_header(soup)

        # Parse all player TOI data
        players = self._parse_players(soup)

        # Build result
        result = ParsedTimeOnIce(
            game_id=game_id,
            season_id=season_id,
            team=team_name,
            team_abbrev=team_abbrev,
            side=self._side,
            players=players,
        )

        return self._to_dict(result)

    def _parse_team_header(self, soup: BeautifulSoup) -> tuple[str, str]:
        """Parse team name and abbreviation from header.

        Args:
            soup: BeautifulSoup document

        Returns:
            Tuple of (team_name, team_abbrev)
        """
        name = ""
        abbrev = ""

        # For TH (home), look for "Home" table; for TV (away), look for "Visitor"
        table_id = "Home" if self._side == "home" else "Visitor"
        table = soup.find("table", id=table_id)
        if not table:
            return name, abbrev

        # Find team logo to get name and abbreviation
        img = table.find("img", alt=True)
        if img and isinstance(img, Tag):
            alt_text = cast(str, img.get("alt", ""))
            if alt_text:
                name = alt_text
            src = cast(str, img.get("src", ""))
            match = TEAM_LOGO_PATTERN.search(src)
            if match:
                abbrev = match.group(1).upper()

        return name, abbrev

    def _parse_players(self, soup: BeautifulSoup) -> list[PlayerTOI]:
        """Parse all player TOI data from the report.

        Args:
            soup: BeautifulSoup document

        Returns:
            List of PlayerTOI objects
        """
        players: list[PlayerTOI] = []

        # Find all player heading cells (class contains "playerHeading")
        # They have format: "4 GOSTISBEHERE, SHAYNE"
        player_headings = soup.find_all(
            "td", class_=lambda c: c and "playerHeading" in c
        )

        for heading in player_headings:
            heading_text = self._get_text(heading)
            if not heading_text:
                continue

            # Parse player number and name
            match = PLAYER_HEADING_PATTERN.match(heading_text)
            if not match:
                continue

            number = int(match.group(1))
            name = match.group(2).strip()

            # Find the parent table that contains this player's data
            player_table = heading.find_parent("table")
            if not player_table:
                continue

            # Parse shift details
            shifts = self._parse_shifts(player_table)

            # Parse period summary
            periods = self._parse_period_summary(player_table)

            player = PlayerTOI(
                number=number,
                name=name,
                shifts_detail=shifts,
                periods=periods,
            )
            players.append(player)

        return players

    def _parse_shifts(self, player_table: Tag) -> list[ShiftInfo]:
        """Parse individual shift data for a player.

        Args:
            player_table: The table element containing the player's data

        Returns:
            List of ShiftInfo objects
        """
        shifts: list[ShiftInfo] = []

        # Find shift rows (have oddColor or evenColor class and contain shift data)
        # Shift rows have 6 columns: Shift #, Per, Start, End, Duration, Event
        rows = player_table.find_all("tr", class_=["oddColor", "evenColor"])

        for row in rows:
            cells = row.find_all("td")
            # Shift rows have exactly 6 cells; summary rows have 7 cells
            if len(cells) != 6:
                continue

            shift_num_text = self._get_text(cells[0])
            period_text = self._get_text(cells[1])
            start_text = self._get_text(cells[2])
            end_text = self._get_text(cells[3])
            duration_text = self._get_text(cells[4])
            event_text = self._get_text(cells[5])

            # Validate shift number is numeric
            shift_num = self._safe_int(shift_num_text)
            if shift_num is None:
                continue

            # Parse start/end times (format: "0:28 / 19:32")
            start_elapsed, start_game = self._parse_time_pair(start_text)
            end_elapsed, end_game = self._parse_time_pair(end_text)

            shift = ShiftInfo(
                shift_number=shift_num,
                period=period_text,
                start_elapsed=start_elapsed,
                start_game=start_game,
                end_elapsed=end_elapsed,
                end_game=end_game,
                duration=duration_text,
                event=event_text.strip(),
            )
            shifts.append(shift)

        return shifts

    def _parse_time_pair(self, text: str) -> tuple[str, str]:
        """Parse time pair from format 'elapsed / game'.

        Args:
            text: Text like "0:28 / 19:32"

        Returns:
            Tuple of (elapsed_time, game_time)
        """
        if "/" not in text:
            return text, ""

        parts = text.split("/")
        elapsed = parts[0].strip()
        game = parts[1].strip() if len(parts) > 1 else ""
        return elapsed, game

    def _parse_period_summary(self, player_table: Tag) -> list[PeriodTOI]:
        """Parse per-period TOI summary for a player.

        Args:
            player_table: The table element containing the player's data

        Returns:
            List of PeriodTOI objects
        """
        periods: list[PeriodTOI] = []

        # Find nested summary table (has 7 columns: Per, SHF, AVG, TOI, EV, PP, SH)
        # It's inside a nested table structure
        nested_tables = player_table.find_all("table")

        for table in nested_tables:
            # Check if this table has the summary header
            header_row = table.find("tr", class_="heading")
            if header_row:
                cells = header_row.find_all("td")
                headers = [self._get_text(cell) for cell in cells]
                # Looking for: Per, SHF, AVG, TOI, EV TOT, PP TOT, SH TOT
                if len(headers) >= 7 and "Per" in headers and "SHF" in headers:
                    # Found the summary table
                    data_rows = table.find_all("tr", class_=["oddColor", "evenColor"])
                    for row in data_rows:
                        period_toi = self._parse_period_row(row)
                        if period_toi:
                            periods.append(period_toi)
                    break

            # Also check for tables without heading class
            first_row = table.find("tr")
            if first_row:
                cells = first_row.find_all("td")
                headers = [self._get_text(cell) for cell in cells]
                if len(headers) >= 7 and "Per" in headers[0] and "SHF" in headers[1]:
                    # Found the summary table
                    data_rows = table.find_all("tr", class_=["oddColor", "evenColor"])
                    for row in data_rows:
                        period_toi = self._parse_period_row(row)
                        if period_toi:
                            periods.append(period_toi)
                    break

        return periods

    def _parse_period_row(self, row: Tag) -> PeriodTOI | None:
        """Parse a single period row from the summary table.

        Args:
            row: Table row element

        Returns:
            PeriodTOI or None if parsing fails
        """
        cells = row.find_all("td")
        if len(cells) < 7:
            return None

        period = self._get_text(cells[0])
        shifts = self._safe_int(self._get_text(cells[1])) or 0
        avg_shift = self._get_text(cells[2])
        toi = self._get_text(cells[3])
        ev_toi = self._get_text(cells[4])
        pp_toi = self._get_text(cells[5])
        sh_toi = self._get_text(cells[6])

        return PeriodTOI(
            period=period,
            shifts=shifts,
            avg_shift=avg_shift,
            toi=toi,
            ev_toi=ev_toi,
            pp_toi=pp_toi,
            sh_toi=sh_toi,
        )

    def _to_dict(self, data: ParsedTimeOnIce) -> dict[str, Any]:
        """Convert ParsedTimeOnIce to dictionary.

        Args:
            data: Parsed TOI data

        Returns:
            Dictionary representation
        """
        return {
            "game_id": data.game_id,
            "season_id": data.season_id,
            "team": data.team,
            "team_abbrev": data.team_abbrev,
            "side": data.side,
            "players": [self._player_to_dict(p) for p in data.players],
        }

    def _player_to_dict(self, player: PlayerTOI) -> dict[str, Any]:
        """Convert PlayerTOI to dictionary.

        Args:
            player: Player TOI data

        Returns:
            Dictionary representation
        """
        return {
            "number": player.number,
            "name": player.name,
            "shifts": player.total_shifts,
            "toi_total": player.total_toi,
            "toi_avg_per_shift": player.avg_shift,
            "ev_toi": player.ev_toi,
            "pp_toi": player.pp_toi,
            "sh_toi": player.sh_toi,
            "toi_by_period": player.toi_by_period,
            "goals_on_ice": player.goals_on_ice,
            "penalties_on_ice": player.penalties_on_ice,
            "shifts_detail": [self._shift_to_dict(s) for s in player.shifts_detail],
            "periods": [self._period_to_dict(p) for p in player.periods],
        }

    def _shift_to_dict(self, shift: ShiftInfo) -> dict[str, Any]:
        """Convert ShiftInfo to dictionary.

        Args:
            shift: Shift information

        Returns:
            Dictionary representation
        """
        return {
            "shift_number": shift.shift_number,
            "period": shift.period,
            "start_elapsed": shift.start_elapsed,
            "start_game": shift.start_game,
            "end_elapsed": shift.end_elapsed,
            "end_game": shift.end_game,
            "duration": shift.duration,
            "event": shift.event,
        }

    def _period_to_dict(self, period: PeriodTOI) -> dict[str, Any]:
        """Convert PeriodTOI to dictionary.

        Args:
            period: Period TOI data

        Returns:
            Dictionary representation
        """
        return {
            "period": period.period,
            "shifts": period.shifts,
            "avg_shift": period.avg_shift,
            "toi": period.toi,
            "ev_toi": period.ev_toi,
            "pp_toi": period.pp_toi,
            "sh_toi": period.sh_toi,
        }
