"""NHL Game Summary (GS) HTML Downloader.

Downloads and parses Game Summary HTML reports from the NHL website.
These reports contain scoring summaries, penalty summaries, and game metadata.

URL Pattern: https://www.nhl.com/scores/htmlreports/{season}/GS{game_suffix}.HTM

Example usage:
    config = HTMLDownloaderConfig()
    async with GameSummaryDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        summary = result.data
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.sources.html.base_html_downloader import (
    BaseHTMLDownloader,
)

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# Exception codes that indicate non-goal entries in scoring table
EXCEPTION_CODES = frozenset(
    {
        "unsuccessful penalty shot",
        "no goal",
        "missed",
        "failed",
        "penalty shot",
        "ps",
    }
)

# Pattern to extract team abbreviation from image URL
TEAM_LOGO_PATTERN = re.compile(r"logoc([a-z]{3})\.gif", re.IGNORECASE)

# Pattern to extract attendance number
ATTENDANCE_PATTERN = re.compile(r"Attendance[:\s]+([0-9,]+)", re.IGNORECASE)

# Pattern to extract game start/end times
TIME_PATTERN = re.compile(r"(\d{1,2}:\d{2})\s*(AM|PM)?", re.IGNORECASE)


@dataclass
class PlayerInfo:
    """Player information parsed from HTML."""

    number: int | None
    name: str
    season_total: int | None = None


@dataclass
class GoalInfo:
    """Goal information from scoring summary."""

    goal_number: int
    period: int
    time: str
    strength: str  # EV, PP, SH, EN
    team: str
    scorer: PlayerInfo
    assist1: PlayerInfo | None = None
    assist2: PlayerInfo | None = None
    away_on_ice: list[int] = field(default_factory=list)
    home_on_ice: list[int] = field(default_factory=list)


@dataclass
class PenaltyInfo:
    """Penalty information from penalty summary."""

    penalty_number: int
    period: int
    time: str
    team: str
    player: PlayerInfo
    pim: int
    infraction: str


@dataclass
class TeamInfo:
    """Team information from game header."""

    name: str
    abbrev: str
    goals: int
    shots: int = 0


@dataclass
class PeriodSummary:
    """Per-period statistics."""

    period: str  # "1", "2", "3", "OT", "SO"
    away_goals: int = 0
    home_goals: int = 0
    away_shots: int = 0
    home_shots: int = 0


@dataclass
class ParsedGameSummary:
    """Complete parsed game summary data."""

    game_id: int
    season_id: int
    date: str
    venue: str
    attendance: int | None
    start_time: str | None
    end_time: str | None
    away_team: TeamInfo
    home_team: TeamInfo
    goals: list[GoalInfo] = field(default_factory=list)
    penalties: list[PenaltyInfo] = field(default_factory=list)
    period_summary: list[PeriodSummary] = field(default_factory=list)
    referees: list[str] = field(default_factory=list)
    linesmen: list[str] = field(default_factory=list)


class GameSummaryDownloader(BaseHTMLDownloader):
    """Downloads and parses NHL Game Summary HTML reports.

    The Game Summary report contains:
    - Game header (teams, final score, venue, attendance)
    - Scoring summary (goals with scorers, assists, players on ice)
    - Penalty summary (penalties by period)
    - Period-by-period breakdown
    - Officials

    Example:
        config = HTMLDownloaderConfig()
        async with GameSummaryDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)

            # Access parsed data
            goals = result.data["goals"]
            penalties = result.data["penalties"]

            # Access raw HTML for reprocessing
            raw_html = result.raw_content
    """

    @property
    def report_type(self) -> str:
        """Return report type code for Game Summary."""
        return "GS"

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse Game Summary HTML into structured data.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed game summary data
        """
        season_id = self._extract_season_from_game_id(game_id)

        # Parse game header
        away_team, home_team = self._parse_teams(soup)
        date, venue, attendance = self._parse_game_info(soup)
        start_time, end_time = self._parse_times(soup)

        # Parse scoring summary
        goals = self._parse_scoring_summary(soup)

        # Parse penalty summary
        penalties = self._parse_penalty_summary(soup)

        # Parse period summary
        period_summary = self._parse_period_summary(soup)

        # Parse officials
        referees, linesmen = self._parse_officials(soup)

        # Build result
        summary = ParsedGameSummary(
            game_id=game_id,
            season_id=season_id,
            date=date,
            venue=venue,
            attendance=attendance,
            start_time=start_time,
            end_time=end_time,
            away_team=away_team,
            home_team=home_team,
            goals=goals,
            penalties=penalties,
            period_summary=period_summary,
            referees=referees,
            linesmen=linesmen,
        )

        return self._summary_to_dict(summary)

    def _parse_teams(self, soup: BeautifulSoup) -> tuple[TeamInfo, TeamInfo]:
        """Parse team information from header.

        Returns:
            Tuple of (away_team, home_team) TeamInfo objects
        """
        away_team = TeamInfo(name="", abbrev="", goals=0)
        home_team = TeamInfo(name="", abbrev="", goals=0)

        # Find visitor and home sections
        visitor_table = soup.find("table", id="Visitor")
        home_table = soup.find("table", id="Home")

        if visitor_table:
            away_team = self._parse_team_table(visitor_table)

        if home_table:
            home_team = self._parse_team_table(home_table)

        return away_team, home_team

    def _parse_team_table(self, table: Tag) -> TeamInfo:
        """Parse a single team table."""
        name = ""
        abbrev = ""
        goals = 0

        # Find team name by searching for "Game X" pattern in td cells
        game_pattern = re.compile(r"Game \d+")
        for td in table.find_all("td"):
            if hasattr(td, "get_text"):
                text = td.get_text(strip=True)
                if game_pattern.search(text):
                    # Extract team name before "Game X"
                    if "Game" in text:
                        name = text.split("Game")[0].strip()
                    break

        # Find team logo to get abbreviation
        img = table.find("img", alt=True)
        if img and isinstance(img, Tag):
            alt_text = cast(str, img.get("alt", ""))
            if alt_text:
                name = alt_text
            src = cast(str, img.get("src", ""))
            match = TEAM_LOGO_PATTERN.search(src)
            if match:
                abbrev = match.group(1).upper()

        # Find score (large font size) by checking style attribute
        for td in table.find_all("td"):
            if isinstance(td, Tag):
                style = cast(str, td.get("style", ""))
                if "font-size" in style and "40px" in style:
                    goals = self._safe_int(self._get_text(td), 0) or 0
                    break

        return TeamInfo(name=name, abbrev=abbrev, goals=goals)

    def _parse_game_info(self, soup: BeautifulSoup) -> tuple[str, str, int | None]:
        """Parse game date, venue, and attendance.

        Returns:
            Tuple of (date, venue, attendance)
        """
        date = ""
        venue = ""
        attendance = None

        # Find GameInfo table
        game_info = soup.find("table", id="GameInfo")
        if game_info:
            cells = game_info.find_all("td")
            for cell in cells:
                text = self._get_text(cell)

                # Date format: "Saturday, December 21, 2024"
                if any(
                    day in text
                    for day in [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ]
                ):
                    date = text

                # Venue and attendance
                if "Attendance" in text:
                    match = ATTENDANCE_PATTERN.search(text)
                    if match:
                        attendance = self._safe_int(match.group(1).replace(",", ""))
                    # Venue is before attendance
                    parts = text.split("Attendance")
                    if parts:
                        venue = parts[0].strip()

        return date, venue, attendance

    def _parse_times(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """Parse game start and end times.

        Returns:
            Tuple of (start_time, end_time)
        """
        start_time = None
        end_time = None

        game_info = soup.find("table", id="GameInfo")
        if game_info:
            cells = game_info.find_all("td")
            for cell in cells:
                text = self._get_text(cell)
                if "Start" in text:
                    match = TIME_PATTERN.search(text)
                    if match:
                        start_time = match.group(0)
                elif "End" in text:
                    match = TIME_PATTERN.search(text)
                    if match:
                        end_time = match.group(0)

        return start_time, end_time

    def _parse_scoring_summary(self, soup: BeautifulSoup) -> list[GoalInfo]:
        """Parse the scoring summary table.

        Returns:
            List of GoalInfo objects
        """
        goals: list[GoalInfo] = []

        # Find scoring summary section by looking for sectionheading class
        scoring_header = None
        for td in soup.find_all("td", class_="sectionheading"):
            if hasattr(td, "get_text"):
                text = td.get_text(strip=True)
                if "SCORING SUMMARY" in text.upper():
                    scoring_header = td
                    break
        if not scoring_header:
            return goals

        # Navigate to the table containing goals
        parent = scoring_header.find_parent("table")
        if not parent:
            return goals

        # Find the next table with actual goal data
        next_table = parent.find_next("table")
        if not next_table:
            return goals

        # Get all rows (skip header)
        rows = next_table.find_all("tr")
        for row in rows[1:]:  # Skip header row
            cells = row.find_all("td")
            if len(cells) < 8:
                continue

            # Check for exception codes
            goal_scorer_text = self._get_text(cells[5])
            if self._is_exception_goal(goal_scorer_text):
                continue

            try:
                goal = self._parse_goal_row(cells)
                if goal:
                    goals.append(goal)
            except (ValueError, IndexError) as e:
                logger.debug("Failed to parse goal row: %s", e)
                continue

        return goals

    def _is_exception_goal(self, text: str) -> bool:
        """Check if goal text contains exception codes."""
        text_lower = text.lower()
        return any(code in text_lower for code in EXCEPTION_CODES)

    def _parse_goal_row(self, cells: list[Tag]) -> GoalInfo | None:
        """Parse a single goal row from the scoring table."""
        if len(cells) < 8:
            return None

        goal_number = self._safe_int(self._get_text(cells[0]))
        if goal_number is None:
            return None

        period_text = self._get_text(cells[1])
        period = self._parse_period(period_text)

        time = self._get_text(cells[2])
        strength = self._get_text(cells[3])
        team = self._get_text(cells[4])

        scorer = self._parse_player_from_cell(cells[5])
        assist1 = self._parse_player_from_cell(cells[6]) if len(cells) > 6 else None
        assist2 = self._parse_player_from_cell(cells[7]) if len(cells) > 7 else None

        # Parse players on ice
        away_on_ice: list[int] = []
        home_on_ice: list[int] = []

        if len(cells) > 8:
            away_on_ice = self._parse_on_ice(cells[8])
        if len(cells) > 9:
            home_on_ice = self._parse_on_ice(cells[9])

        return GoalInfo(
            goal_number=goal_number,
            period=period,
            time=time,
            strength=strength,
            team=team,
            scorer=scorer,
            assist1=assist1,
            assist2=assist2,
            away_on_ice=away_on_ice,
            home_on_ice=home_on_ice,
        )

    def _parse_period(self, text: str) -> int:
        """Parse period number from text."""
        text = text.strip().upper()
        if text == "OT":
            return 4
        if text == "SO":
            return 5
        return self._safe_int(text, 0) or 0

    def _parse_player_from_cell(self, cell: Tag) -> PlayerInfo:
        """Parse player info from a table cell."""
        text = self._get_text(cell)
        if not text:
            return PlayerInfo(number=None, name="")

        info = self._parse_player_info(text)
        return PlayerInfo(
            number=info.get("number"),
            name=info.get("name", ""),
            season_total=info.get("stat"),
        )

    def _parse_on_ice(self, cell: Tag) -> list[int]:
        """Parse player numbers from on-ice cell."""
        numbers: list[int] = []
        fonts = cell.find_all("font")
        for font in fonts:
            text = self._get_text(font)
            num = self._safe_int(text)
            if num is not None:
                numbers.append(num)
        return numbers

    def _parse_penalty_summary(self, soup: BeautifulSoup) -> list[PenaltyInfo]:
        """Parse the penalty summary section.

        Returns:
            List of PenaltyInfo objects
        """
        penalties: list[PenaltyInfo] = []

        # Find penalty summary table
        penalty_table = soup.find("table", id="PenaltySummary")
        if not penalty_table:
            return penalties

        # Find the main penalty tables (one for visitor, one for home)
        # These are direct child tables with the oddColor/evenColor rows
        for row in penalty_table.find_all("tr", class_=["oddColor", "evenColor"]):
            # Get direct td children only (not nested table cells)
            cells = row.find_all("td", recursive=False)
            if len(cells) < 6:
                continue

            try:
                penalty = self._parse_penalty_row(cells)
                if penalty:
                    penalties.append(penalty)
            except (ValueError, IndexError) as e:
                logger.debug("Failed to parse penalty row: %s", e)
                continue

        return penalties

    def _parse_penalty_row(self, cells: list[Tag]) -> PenaltyInfo | None:
        """Parse a single penalty row."""
        if len(cells) < 6:
            return None

        penalty_number = self._safe_int(self._get_text(cells[0]))
        if penalty_number is None:
            return None

        period = self._safe_int(self._get_text(cells[1]), 0) or 0
        time = self._get_text(cells[2])

        # Player cell contains nested table with number and name
        player_cell = cells[3]
        player = self._parse_player_from_penalty_cell(player_cell)

        pim = self._safe_int(self._get_text(cells[4]), 0) or 0
        infraction = self._get_text(cells[5])

        return PenaltyInfo(
            penalty_number=penalty_number,
            period=period,
            time=time,
            team="",  # Team determined by which table
            player=player,
            pim=pim,
            infraction=infraction,
        )

    def _parse_player_from_penalty_cell(self, cell: Tag) -> PlayerInfo:
        """Parse player info from a penalty cell with nested table.

        The penalty player cell contains a nested table with structure:
        <table>
            <tr>
                <td width="15">28</td>  <!-- number -->
                <td>&nbsp;</td>
                <td>&nbsp;</td>
                <td>A.ROMANOV</td>  <!-- name -->
            </tr>
        </table>
        """
        # Try to find nested table
        nested_table = cell.find("table")
        if nested_table:
            inner_cells = nested_table.find_all("td")
            if len(inner_cells) >= 4:
                number = self._safe_int(self._get_text(inner_cells[0]))
                name = self._get_text(inner_cells[-1])  # Last cell has name
                return PlayerInfo(number=number, name=name)

        # Fallback: parse as simple text
        text = self._get_text(cell)
        info = self._parse_player_info(text)
        return PlayerInfo(
            number=info.get("number"),
            name=info.get("name", ""),
        )

    def _parse_period_summary(self, soup: BeautifulSoup) -> list[PeriodSummary]:
        """Parse period-by-period summary.

        Returns:
            List of PeriodSummary objects
        """
        # TODO: Implement period summary parsing
        # This requires finding the period totals table
        return []

    def _parse_officials(self, soup: BeautifulSoup) -> tuple[list[str], list[str]]:
        """Parse officials from the report.

        Returns:
            Tuple of (referees, linesmen)
        """
        referees: list[str] = []
        linesmen: list[str] = []

        # Find officials section
        for td in soup.find_all("td"):
            text = self._get_text(td)
            if "Referee" in text:
                # Extract referee names
                parts = text.replace("Referees:", "").replace("Referee:", "")
                for name in parts.split(","):
                    name = name.strip()
                    if name and name not in ["Referees", "Referee"]:
                        referees.append(name)
            elif "Linesmen" in text or "Linesman" in text:
                # Extract linesman names
                parts = text.replace("Linesmen:", "").replace("Linesman:", "")
                for name in parts.split(","):
                    name = name.strip()
                    if name and name not in ["Linesmen", "Linesman"]:
                        linesmen.append(name)

        return referees, linesmen

    def _summary_to_dict(self, summary: ParsedGameSummary) -> dict[str, Any]:
        """Convert ParsedGameSummary to dictionary."""
        return {
            "game_id": summary.game_id,
            "season_id": summary.season_id,
            "date": summary.date,
            "venue": summary.venue,
            "attendance": summary.attendance,
            "start_time": summary.start_time,
            "end_time": summary.end_time,
            "away_team": {
                "name": summary.away_team.name,
                "abbrev": summary.away_team.abbrev,
                "goals": summary.away_team.goals,
                "shots": summary.away_team.shots,
            },
            "home_team": {
                "name": summary.home_team.name,
                "abbrev": summary.home_team.abbrev,
                "goals": summary.home_team.goals,
                "shots": summary.home_team.shots,
            },
            "goals": [
                {
                    "goal_number": g.goal_number,
                    "period": g.period,
                    "time": g.time,
                    "strength": g.strength,
                    "team": g.team,
                    "scorer": {
                        "number": g.scorer.number,
                        "name": g.scorer.name,
                        "season_total": g.scorer.season_total,
                    },
                    "assist1": {
                        "number": g.assist1.number,
                        "name": g.assist1.name,
                        "season_total": g.assist1.season_total,
                    }
                    if g.assist1 and g.assist1.name
                    else None,
                    "assist2": {
                        "number": g.assist2.number,
                        "name": g.assist2.name,
                        "season_total": g.assist2.season_total,
                    }
                    if g.assist2 and g.assist2.name
                    else None,
                    "away_on_ice": g.away_on_ice,
                    "home_on_ice": g.home_on_ice,
                }
                for g in summary.goals
            ],
            "penalties": [
                {
                    "penalty_number": p.penalty_number,
                    "period": p.period,
                    "time": p.time,
                    "team": p.team,
                    "player": {
                        "number": p.player.number,
                        "name": p.player.name,
                    },
                    "pim": p.pim,
                    "infraction": p.infraction,
                }
                for p in summary.penalties
            ],
            "period_summary": [
                {
                    "period": ps.period,
                    "away_goals": ps.away_goals,
                    "home_goals": ps.home_goals,
                    "away_shots": ps.away_shots,
                    "home_shots": ps.home_shots,
                }
                for ps in summary.period_summary
            ],
            "referees": summary.referees,
            "linesmen": summary.linesmen,
        }

    async def persist(
        self,
        db: DatabaseService,
        summaries: list[dict[str, Any]],
    ) -> int:
        """Persist game summary data to the database.

        Stores parsed HTML game summary data including goals, penalties,
        and game metadata for cross-source validation.

        Args:
            db: Database service instance
            summaries: List of parsed game summary dictionaries

        Returns:
            Number of game summaries persisted
        """
        if not summaries:
            return 0

        count = 0
        for summary in summaries:
            game_id = summary.get("game_id")
            season_id = summary.get("season_id")

            if not game_id or not season_id:
                logger.warning("Skipping game summary without game_id or season_id")
                continue

            await db.execute(
                """
                INSERT INTO html_game_summary (
                    game_id, season_id, away_team_abbrev, home_team_abbrev,
                    away_goals, home_goals, venue, attendance, game_date,
                    start_time, end_time, goals, penalties, referees, linesmen,
                    parsed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, CURRENT_TIMESTAMP)
                ON CONFLICT (game_id, season_id) DO UPDATE SET
                    away_team_abbrev = EXCLUDED.away_team_abbrev,
                    home_team_abbrev = EXCLUDED.home_team_abbrev,
                    away_goals = EXCLUDED.away_goals,
                    home_goals = EXCLUDED.home_goals,
                    venue = EXCLUDED.venue,
                    attendance = EXCLUDED.attendance,
                    game_date = EXCLUDED.game_date,
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    goals = EXCLUDED.goals,
                    penalties = EXCLUDED.penalties,
                    referees = EXCLUDED.referees,
                    linesmen = EXCLUDED.linesmen,
                    parsed_at = CURRENT_TIMESTAMP
                """,
                game_id,
                season_id,
                summary.get("away_team", {}).get("abbrev"),
                summary.get("home_team", {}).get("abbrev"),
                summary.get("away_team", {}).get("goals"),
                summary.get("home_team", {}).get("goals"),
                summary.get("venue"),
                summary.get("attendance"),
                summary.get("date"),
                summary.get("start_time"),
                summary.get("end_time"),
                json.dumps(summary.get("goals", [])),
                json.dumps(summary.get("penalties", [])),
                json.dumps(summary.get("referees", [])),
                json.dumps(summary.get("linesmen", [])),
            )
            count += 1

        logger.info("Persisted %d HTML game summaries", count)
        return count
