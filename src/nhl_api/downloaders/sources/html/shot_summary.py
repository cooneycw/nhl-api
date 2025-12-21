"""NHL Shot Summary (SS) HTML Downloader.

Downloads and parses Shot Summary HTML reports from the NHL website.
These reports contain shot counts by period and situation for each player.

URL Pattern: https://www.nhl.com/scores/htmlreports/{season}/SS{game_suffix}.HTM

Example usage:
    config = HTMLDownloaderConfig()
    async with ShotSummaryDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        summary = result.data
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, cast

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.sources.html.base_html_downloader import (
    BaseHTMLDownloader,
)

logger = logging.getLogger(__name__)

# Pattern to extract team abbreviation from image URL
TEAM_LOGO_PATTERN = re.compile(r"logoc([a-z]{3})\.gif", re.IGNORECASE)


@dataclass
class SituationStats:
    """Goals and shots by situation (EV, PP, SH)."""

    goals: int = 0
    shots: int = 0


@dataclass
class PeriodSituationStats:
    """Per-period stats by situation."""

    period: str  # "1", "2", "3", "OT", "TOT"
    even_strength: SituationStats = field(default_factory=SituationStats)
    power_play: SituationStats = field(default_factory=SituationStats)
    shorthanded: SituationStats = field(default_factory=SituationStats)
    total: SituationStats = field(default_factory=SituationStats)


@dataclass
class PlayerShotSummary:
    """Individual player shot summary."""

    number: int
    first_name: str
    last_name: str
    periods: list[PeriodSituationStats] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def total_shots(self) -> int:
        """Total shots across all periods."""
        for period in self.periods:
            if period.period == "TOT":
                return period.total.shots
        return sum(p.total.shots for p in self.periods if p.period != "TOT")

    @property
    def total_goals(self) -> int:
        """Total goals across all periods."""
        for period in self.periods:
            if period.period == "TOT":
                return period.total.goals
        return sum(p.total.goals for p in self.periods if p.period != "TOT")


@dataclass
class TeamShotSummary:
    """Team-level shot summary."""

    name: str
    abbrev: str
    periods: list[PeriodSituationStats] = field(default_factory=list)
    players: list[PlayerShotSummary] = field(default_factory=list)

    @property
    def total_shots(self) -> int:
        """Total team shots."""
        for period in self.periods:
            if period.period == "TOT":
                return period.total.shots
        return sum(p.total.shots for p in self.periods if p.period != "TOT")

    @property
    def total_goals(self) -> int:
        """Total team goals."""
        for period in self.periods:
            if period.period == "TOT":
                return period.total.goals
        return sum(p.total.goals for p in self.periods if p.period != "TOT")


@dataclass
class ParsedShotSummary:
    """Complete parsed shot summary data."""

    game_id: int
    season_id: int
    away_team: TeamShotSummary
    home_team: TeamShotSummary


class ShotSummaryDownloader(BaseHTMLDownloader):
    """Downloads and parses NHL Shot Summary HTML reports.

    The Shot Summary report contains:
    - Team summary with goals-shots by period and situation
    - Player summary with individual shot counts by period and situation

    Shot data is presented in "goals-shots" format (e.g., "2-15" = 2 goals on 15 shots).

    Example:
        config = HTMLDownloaderConfig()
        async with ShotSummaryDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)

            # Access parsed data
            away_players = result.data["away_team"]["players"]
            home_players = result.data["home_team"]["players"]

            # Access raw HTML for reprocessing
            raw_html = result.raw_content
    """

    @property
    def report_type(self) -> str:
        """Return report type code for Shot Summary."""
        return "SS"

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse Shot Summary HTML into structured data.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed shot summary data
        """
        season_id = self._extract_season_from_game_id(game_id)

        # Parse team info from header
        away_name, away_abbrev = self._parse_team_header(soup, "Visitor")
        home_name, home_abbrev = self._parse_team_header(soup, "Home")

        # Parse team summaries (goals-shots by period)
        away_team_periods, home_team_periods = self._parse_team_summaries(soup)

        # Parse player summaries
        away_players, home_players = self._parse_player_summaries(soup)

        # Build result
        away_team = TeamShotSummary(
            name=away_name,
            abbrev=away_abbrev,
            periods=away_team_periods,
            players=away_players,
        )

        home_team = TeamShotSummary(
            name=home_name,
            abbrev=home_abbrev,
            periods=home_team_periods,
            players=home_players,
        )

        summary = ParsedShotSummary(
            game_id=game_id,
            season_id=season_id,
            away_team=away_team,
            home_team=home_team,
        )

        return self._summary_to_dict(summary)

    def _parse_team_header(self, soup: BeautifulSoup, team_id: str) -> tuple[str, str]:
        """Parse team name and abbreviation from header.

        Args:
            soup: BeautifulSoup document
            team_id: "Visitor" or "Home"

        Returns:
            Tuple of (team_name, team_abbrev)
        """
        name = ""
        abbrev = ""

        table = soup.find("table", id=team_id)
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

    def _parse_team_summaries(
        self, soup: BeautifulSoup
    ) -> tuple[list[PeriodSituationStats], list[PeriodSituationStats]]:
        """Parse team-level shot summaries.

        The team summary section has "TEAM SUMMARY (Goals-Shots)" heading
        with two columns (away/home), each containing period breakdowns.

        Returns:
            Tuple of (away_periods, home_periods)
        """
        away_periods: list[PeriodSituationStats] = []
        home_periods: list[PeriodSituationStats] = []

        # Find the team summary section
        section_heading = None
        for td in soup.find_all("td", class_="sectionheading"):
            text = self._get_text(td)
            if "TEAM SUMMARY" in text.upper():
                section_heading = td
                break

        if not section_heading:
            return away_periods, home_periods

        # Find the parent table row and then the shots summary table
        parent_row = section_heading.find_parent("tr")
        if not parent_row:
            return away_periods, home_periods

        # Get the next row which contains the actual data
        next_row = parent_row.find_next_sibling("tr")
        if not next_row:
            return away_periods, home_periods

        # Find the table with id="ShotsSummary"
        shots_table = next_row.find("table", id="ShotsSummary")
        if not shots_table:
            return away_periods, home_periods

        # Get the two columns (away and home)
        columns = shots_table.find_all("td", width="50%", recursive=False)
        if len(columns) >= 2:
            away_periods = self._parse_situation_table(columns[0])
            home_periods = self._parse_situation_table(columns[1])

        return away_periods, home_periods

    def _parse_situation_table(self, container: Tag) -> list[PeriodSituationStats]:
        """Parse a situation table (EV, PP, SH, TOT by period).

        Args:
            container: The container element with the situation table

        Returns:
            List of PeriodSituationStats
        """
        periods: list[PeriodSituationStats] = []

        # Find the first table with the EV/PP/SH/TOT headers
        tables = container.find_all("table")
        for table in tables:
            # Check if this table has the right headers
            header_row = table.find("tr", class_="heading")
            if not header_row:
                continue

            cells = header_row.find_all("td")
            headers = [self._get_text(cell) for cell in cells]

            # Look for Per, EV, PP, SH, TOT pattern
            if len(headers) >= 5 and "Per" in headers and "TOT" in headers:
                # Found the situation table
                data_rows = table.find_all("tr", class_=["oddColor", "evenColor"])
                for row in data_rows:
                    period_stats = self._parse_period_row(row)
                    if period_stats:
                        periods.append(period_stats)
                break

        return periods

    def _parse_period_row(self, row: Tag) -> PeriodSituationStats | None:
        """Parse a single period row from the situation table.

        Args:
            row: Table row element

        Returns:
            PeriodSituationStats or None if parsing fails
        """
        cells = row.find_all("td")
        if len(cells) < 5:
            return None

        period = self._get_text(cells[0])
        ev_text = self._get_text(cells[1])
        pp_text = self._get_text(cells[2])
        sh_text = self._get_text(cells[3])
        tot_text = self._get_text(cells[4])

        return PeriodSituationStats(
            period=period,
            even_strength=self._parse_goals_shots(ev_text),
            power_play=self._parse_goals_shots(pp_text),
            shorthanded=self._parse_goals_shots(sh_text),
            total=self._parse_goals_shots(tot_text),
        )

    def _parse_goals_shots(self, text: str) -> SituationStats:
        """Parse goals-shots format like '2-15' into SituationStats.

        Args:
            text: String in "goals-shots" format

        Returns:
            SituationStats with goals and shots
        """
        text = text.strip()
        if not text or text == "&nbsp;" or "-" not in text:
            return SituationStats(goals=0, shots=0)

        try:
            parts = text.split("-")
            goals = int(parts[0]) if parts[0].strip().isdigit() else 0
            shots = (
                int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0
            )
            return SituationStats(goals=goals, shots=shots)
        except (ValueError, IndexError):
            return SituationStats(goals=0, shots=0)

    def _parse_player_summaries(
        self, soup: BeautifulSoup
    ) -> tuple[list[PlayerShotSummary], list[PlayerShotSummary]]:
        """Parse player-level shot summaries.

        Returns:
            Tuple of (away_players, home_players)
        """
        away_players: list[PlayerShotSummary] = []
        home_players: list[PlayerShotSummary] = []

        # Find the player summary section
        section_heading = None
        for td in soup.find_all("td", class_="sectionheading"):
            text = self._get_text(td)
            if "PLAYER SUMMARY" in text.upper():
                section_heading = td
                break

        if not section_heading:
            return away_players, home_players

        # Find the parent table row
        parent_row = section_heading.find_parent("tr")
        if not parent_row:
            return away_players, home_players

        # Get the next row which contains the player data
        next_row = parent_row.find_next_sibling("tr")
        if not next_row:
            return away_players, home_players

        # Find the table with id="ShotsSummary" (reused id)
        shots_table = next_row.find("table", id="ShotsSummary")
        if not shots_table:
            return away_players, home_players

        # Get the two columns (away and home)
        columns = shots_table.find_all("td", width="50%", recursive=False)
        if len(columns) >= 2:
            away_players = self._parse_player_column(columns[0])
            home_players = self._parse_player_column(columns[1])

        return away_players, home_players

    def _parse_player_column(self, container: Tag) -> list[PlayerShotSummary]:
        """Parse all players from a team column.

        Args:
            container: The container element with player tables

        Returns:
            List of PlayerShotSummary
        """
        players: list[PlayerShotSummary] = []

        # Find all tables that contain player data
        # Player tables are structured as rows with:
        # - First cell: player info (number, first name, last name)
        # - Second cell: stats table
        tables = container.find_all("table", recursive=True)

        for table in tables:
            # Find rows that have the player info structure
            rows = table.find_all("tr", recursive=False)
            for row in rows:
                cells = row.find_all("td", recursive=False)
                if len(cells) < 2:
                    continue

                # Check if first cell contains player info (nested table with number/name)
                player_cell = cells[0]
                stats_cell = cells[1]

                # Player cell should have a nested table with 3 rows
                player_table = player_cell.find("table")
                if not player_table:
                    continue

                player_rows = player_table.find_all("tr")
                if len(player_rows) < 3:
                    continue

                # Extract player info
                number_text = self._get_text(player_rows[0])
                first_name = self._get_text(player_rows[1])
                last_name = self._get_text(player_rows[2])

                number = self._safe_int(number_text)
                if number is None:
                    continue

                # Parse stats from the stats cell
                periods = self._parse_player_stats_table(stats_cell)

                player = PlayerShotSummary(
                    number=number,
                    first_name=first_name,
                    last_name=last_name,
                    periods=periods,
                )
                players.append(player)

        return players

    def _parse_player_stats_table(self, cell: Tag) -> list[PeriodSituationStats]:
        """Parse the player stats table from a cell.

        Args:
            cell: The cell containing the stats table

        Returns:
            List of PeriodSituationStats
        """
        periods: list[PeriodSituationStats] = []

        stats_table = cell.find("table")
        if not stats_table:
            return periods

        # Get all data rows (oddColor/evenColor)
        data_rows = stats_table.find_all("tr", class_=["oddColor", "evenColor"])
        for row in data_rows:
            period_stats = self._parse_period_row(row)
            if period_stats:
                periods.append(period_stats)

        return periods

    def _summary_to_dict(self, summary: ParsedShotSummary) -> dict[str, Any]:
        """Convert ParsedShotSummary to dictionary."""
        return {
            "game_id": summary.game_id,
            "season_id": summary.season_id,
            "away_team": self._team_to_dict(summary.away_team),
            "home_team": self._team_to_dict(summary.home_team),
        }

    def _team_to_dict(self, team: TeamShotSummary) -> dict[str, Any]:
        """Convert TeamShotSummary to dictionary."""
        return {
            "name": team.name,
            "abbrev": team.abbrev,
            "total_shots": team.total_shots,
            "total_goals": team.total_goals,
            "periods": [self._period_to_dict(p) for p in team.periods],
            "players": [self._player_to_dict(p) for p in team.players],
        }

    def _period_to_dict(self, period: PeriodSituationStats) -> dict[str, Any]:
        """Convert PeriodSituationStats to dictionary."""
        return {
            "period": period.period,
            "even_strength": {
                "goals": period.even_strength.goals,
                "shots": period.even_strength.shots,
            },
            "power_play": {
                "goals": period.power_play.goals,
                "shots": period.power_play.shots,
            },
            "shorthanded": {
                "goals": period.shorthanded.goals,
                "shots": period.shorthanded.shots,
            },
            "total": {
                "goals": period.total.goals,
                "shots": period.total.shots,
            },
        }

    def _player_to_dict(self, player: PlayerShotSummary) -> dict[str, Any]:
        """Convert PlayerShotSummary to dictionary."""
        return {
            "number": player.number,
            "first_name": player.first_name,
            "last_name": player.last_name,
            "name": player.name,
            "total_shots": player.total_shots,
            "total_goals": player.total_goals,
            "periods": [self._period_to_dict(p) for p in player.periods],
        }
