"""NHL Event Summary (ES) HTML Downloader.

Downloads and parses Event Summary HTML reports from the NHL website.
These reports contain comprehensive player statistics for each game including
goals, assists, +/-, PIM, TOI, shots, hits, blocks, faceoffs, and more.

URL Pattern: https://www.nhl.com/scores/htmlreports/{season}/ES{game_suffix}.HTM

Example usage:
    config = HTMLDownloaderConfig()
    async with EventSummaryDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        summary = result.data
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.sources.html.base_html_downloader import (
    BaseHTMLDownloader,
)

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)

# Pattern to extract position from player cell
POSITION_PATTERN = re.compile(r"\(([CLRWGD])\)")


@dataclass
class PlayerStats:
    """Player statistics from Event Summary.

    Contains all individual player stats tracked in the ES report.
    """

    number: int
    position: str
    name: str
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    pn: int = 0  # Penalty count
    pim: int = 0  # Penalty minutes
    toi_total: str = "0:00"  # Time on ice (MM:SS format)
    toi_ev: str = "0:00"  # Even strength TOI
    toi_pp: str = "0:00"  # Power play TOI
    toi_sh: str = "0:00"  # Shorthanded TOI
    shots: int = 0
    missed_shots: int = 0
    hits: int = 0
    giveaways: int = 0
    takeaways: int = 0
    blocked_shots: int = 0
    faceoff_wins: int = 0
    faceoff_losses: int = 0
    faceoff_pct: float | None = None


@dataclass
class GoalieStats:
    """Goalie statistics from Event Summary."""

    number: int
    name: str
    toi: str = "0:00"  # Time on ice (MM:SS format)
    shots_against: int = 0
    saves: int = 0
    goals_against: int = 0
    sv_pct: float | None = None


@dataclass
class TeamEventSummary:
    """Team event summary containing all player stats."""

    name: str
    abbrev: str
    players: list[PlayerStats] = field(default_factory=list)
    goalies: list[GoalieStats] = field(default_factory=list)
    totals: dict[str, int] = field(default_factory=dict)


@dataclass
class ParsedEventSummary:
    """Complete parsed event summary data."""

    game_id: int
    season_id: int
    away_team: TeamEventSummary
    home_team: TeamEventSummary


class EventSummaryDownloader(BaseHTMLDownloader):
    """Downloads and parses NHL Event Summary HTML reports.

    The Event Summary report contains comprehensive player statistics:
    - Goals, Assists, Points, +/-
    - Penalty count and minutes
    - Time on ice (total, EV, PP, SH)
    - Shots, missed shots, blocked shots
    - Hits, giveaways, takeaways
    - Faceoff wins/losses and percentage
    - Goalie stats (TOI, saves, goals against, save %)

    Example:
        config = HTMLDownloaderConfig()
        async with EventSummaryDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)

            # Access parsed data
            away_players = result.data["away_team"]["players"]
            home_goalies = result.data["home_team"]["goalies"]

            # Access raw HTML for reprocessing
            raw_html = result.raw_content
    """

    @property
    def report_type(self) -> str:
        """Return report type code for Event Summary."""
        return "ES"

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse Event Summary HTML into structured data.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed event summary data
        """
        season_id = self._extract_season_from_game_id(game_id)

        # Parse team data from the two main player tables
        away_team = self._parse_team_stats(soup, is_away=True)
        home_team = self._parse_team_stats(soup, is_away=False)

        # Build result
        summary = ParsedEventSummary(
            game_id=game_id,
            season_id=season_id,
            away_team=away_team,
            home_team=home_team,
        )

        return self._summary_to_dict(summary)

    def _parse_team_stats(
        self, soup: BeautifulSoup, *, is_away: bool
    ) -> TeamEventSummary:
        """Parse player statistics for one team.

        The ES report contains two main tables - one for each team.
        Tables are identified by class patterns and their position in the document.

        Args:
            soup: BeautifulSoup document
            is_away: True for away team (first table), False for home team

        Returns:
            TeamEventSummary with all player and goalie stats
        """
        team_name = ""
        team_abbrev = ""
        players: list[PlayerStats] = []
        goalies: list[GoalieStats] = []
        totals: dict[str, int] = {}

        # Find team header tables (contain team name)
        visitor_table = soup.find("table", id="Visitor")
        home_table = soup.find("table", id="Home")

        # Get team info from header
        if is_away and visitor_table:
            team_name, team_abbrev = self._extract_team_from_table(visitor_table)
        elif not is_away and home_table:
            team_name, team_abbrev = self._extract_team_from_table(home_table)

        # Find the player stats tables
        # ES report has tables with headers containing column names like "G", "A", "P", etc.
        stats_tables = self._find_player_stats_tables(soup)

        # First table is away team, second is home team
        table_index = 0 if is_away else 1
        if table_index < len(stats_tables):
            stats_table = stats_tables[table_index]
            players, goalies, totals = self._parse_stats_table(stats_table)

        return TeamEventSummary(
            name=team_name,
            abbrev=team_abbrev,
            players=players,
            goalies=goalies,
            totals=totals,
        )

    def _extract_team_from_table(self, table: Tag) -> tuple[str, str]:
        """Extract team name and abbreviation from header table.

        Args:
            table: Team header table element

        Returns:
            Tuple of (team_name, team_abbrev)
        """
        name = ""
        abbrev = ""

        # Find team logo image for abbreviation
        img = table.find("img", alt=True)
        if img:
            alt_text = str(img.get("alt", ""))
            if alt_text:
                name = alt_text
            src = str(img.get("src", ""))
            # Extract from logoccar.gif -> CAR
            match = re.search(r"logoc([a-z]{3})\.gif", src, re.IGNORECASE)
            if match:
                abbrev = match.group(1).upper()

        return name, abbrev

    def _find_player_stats_tables(self, soup: BeautifulSoup) -> list[Tag]:
        """Find tables containing player statistics.

        ES report has two team tables with headers like:
        NEW YORK ISLANDERS / CAROLINA HURRICANES followed by
        G, A, P, +/-, PN, PIM, TOI, S, A/B, MS, HT, GV, TK, BS, FW, FL, F%

        The tables have visitorsectionheading or homesectionheading classes.

        Args:
            soup: BeautifulSoup document

        Returns:
            List of table elements containing player stats
        """
        stats_tables: list[Tag] = []

        # Find tables that have section heading cells with team names
        # and contain data rows with oddColor/evenColor classes
        for table in soup.find_all("table"):
            # Check for visitor or home section heading
            section_heading = table.find(
                "td", class_=lambda c: c and "sectionheading" in c
            )
            if not section_heading:
                continue

            # Verify it has data rows with player stats
            data_rows = table.find_all("tr", class_=["oddColor", "evenColor"])
            if len(data_rows) > 0:
                # Check if first data row has expected column count (20+ cells)
                first_row = data_rows[0]
                cells = first_row.find_all("td")
                if len(cells) >= 15:  # Minimum expected columns
                    stats_tables.append(table)

        return stats_tables

    def _parse_stats_table(
        self, table: Tag
    ) -> tuple[list[PlayerStats], list[GoalieStats], dict[str, int]]:
        """Parse a team's statistics table.

        Args:
            table: Table element containing player stats

        Returns:
            Tuple of (players, goalies, totals)
        """
        players: list[PlayerStats] = []
        goalies: list[GoalieStats] = []
        totals: dict[str, int] = {}

        # Get column indices (fixed based on NHL ES report structure)
        col_indices = self._parse_header_columns(table)

        # Parse each data row
        for row in table.find_all("tr", class_=["oddColor", "evenColor"]):
            cells = row.find_all("td")
            if not cells:
                continue

            # Check if this is a team totals row or goalie row
            row_class = row.get("class")
            row_class_list = row_class if isinstance(row_class, list) else []
            is_bold_row = (
                "bold" in " ".join(row_class_list) if row_class_list else False
            )

            # First check for totals row (has TEAM TOTALS or spans columns)
            name_cell_text = self._get_text(cells[2]).upper() if len(cells) > 2 else ""

            if is_bold_row or "TEAM TOTALS" in name_cell_text:
                totals = self._parse_totals_row(cells, col_indices)
            elif self._is_goalie_row(cells, col_indices):
                goalie = self._parse_goalie_row(cells, col_indices)
                if goalie:
                    goalies.append(goalie)
            else:
                player = self._parse_player_row(cells, col_indices)
                if player:
                    players.append(player)

        return players, goalies, totals

    def _parse_header_columns(self, table: Tag) -> dict[str, int]:
        """Parse header rows to get column indices.

        The ES report has a two-row header structure:
        Row 1: Team name, G, A, P, +/-, PN, PIM, TOI (colspan=6), S, A/B, MS, HT, GV, TK, BS, FW, FL, F%
        Row 2: TOT, SHF, AVG, PP, SH, EV (TOI sub-columns)

        Data rows follow with:
        NUM, POS, NAME, G, A, P, +/-, PN, PIM, TOT, SHF, AVG, PP, SH, EV, S, A/B, MS, HT, GV, TK, BS, FW, FL, F%

        Args:
            table: Table containing header rows

        Returns:
            Dictionary mapping column name to index
        """
        # Default column indices for the standard ES report format
        # These are based on the actual NHL ES report structure
        return {
            "NUM": 0,
            "POS": 1,
            "NAME": 2,
            "G": 3,
            "A": 4,
            "P": 5,
            "+/-": 6,
            "PN": 7,
            "PIM": 8,
            "TOI": 9,  # TOT (total TOI)
            "SHF": 10,  # Shifts
            "AVG": 11,  # Average shift length
            "PP": 12,  # Power play TOI
            "SH": 13,  # Shorthanded TOI
            "EV": 14,  # Even strength TOI
            "S": 15,  # Shots
            "AB": 16,  # Attempts blocked (A/B)
            "MS": 17,  # Missed shots
            "HT": 18,  # Hits
            "GV": 19,  # Giveaways
            "TK": 20,  # Takeaways
            "BS": 21,  # Blocked shots
            "FW": 22,  # Faceoff wins
            "FL": 23,  # Faceoff losses
            "F%": 24,  # Faceoff percentage
        }

    def _is_goalie_row(self, cells: list[Tag], col_indices: dict[str, int]) -> bool:
        """Determine if a row is a goalie row.

        Goalie rows have position 'G' in the POS column.

        Args:
            cells: Table cells for the row
            col_indices: Column index mapping

        Returns:
            True if this appears to be a goalie row
        """
        if not cells:
            return False

        # Check position column (index 1 in standard ES format)
        pos_idx = col_indices.get("POS", 1)
        if pos_idx < len(cells):
            pos_text = self._get_text(cells[pos_idx]).upper().strip()
            if pos_text == "G":
                return True

        return False

    def _parse_player_row(
        self, cells: list[Tag], col_indices: dict[str, int]
    ) -> PlayerStats | None:
        """Parse a player statistics row.

        ES report format (columns 0-24):
        NUM, POS, NAME, G, A, P, +/-, PN, PIM, TOT, SHF, AVG, PP, SH, EV, S, A/B, MS, HT, GV, TK, BS, FW, FL, F%

        Args:
            cells: Table cells for the row
            col_indices: Column index mapping

        Returns:
            PlayerStats or None if parsing fails
        """
        if len(cells) < 10:
            return None

        # Get number, position, and name from their respective columns
        num_idx = col_indices.get("NUM", 0)
        pos_idx = col_indices.get("POS", 1)
        name_idx = col_indices.get("NAME", 2)

        number = (
            self._safe_int(self._get_text(cells[num_idx]))
            if num_idx < len(cells)
            else None
        )
        position = (
            self._get_text(cells[pos_idx]).strip() if pos_idx < len(cells) else ""
        )
        name = self._get_text(cells[name_idx]).strip() if name_idx < len(cells) else ""

        if number is None:
            return None

        # Helper to get cell value by column name
        def get_val(col: str, default: int = 0) -> int:
            idx = col_indices.get(col)
            if idx is not None and idx < len(cells):
                val = self._safe_int(self._get_text(cells[idx]), default)
                return val if val is not None else default
            return default

        def get_toi(col: str, default: str = "0:00") -> str:
            idx = col_indices.get(col)
            if idx is not None and idx < len(cells):
                val = self._get_text(cells[idx]).strip()
                return val if val else default
            return default

        def get_float(col: str) -> float | None:
            idx = col_indices.get(col)
            if idx is not None and idx < len(cells):
                return self._safe_float(self._get_text(cells[idx]))
            return None

        return PlayerStats(
            number=number,
            position=position,
            name=name,
            goals=get_val("G"),
            assists=get_val("A"),
            points=get_val("P"),
            plus_minus=get_val("+/-"),
            pn=get_val("PN"),
            pim=get_val("PIM"),
            toi_total=get_toi("TOI"),
            toi_ev=get_toi("EV"),
            toi_pp=get_toi("PP"),
            toi_sh=get_toi("SH"),
            shots=get_val("S"),
            missed_shots=get_val("MS"),
            hits=get_val("HT"),
            giveaways=get_val("GV"),
            takeaways=get_val("TK"),
            blocked_shots=get_val("BS"),
            faceoff_wins=get_val("FW"),
            faceoff_losses=get_val("FL"),
            faceoff_pct=get_float("F%"),
        )

    def _parse_player_cell(self, text: str) -> tuple[int | None, str, str]:
        """Parse player number, position, and name from cell text.

        Typical format: "20 S.AHO (C)" or "#20 (C) S.AHO"

        Args:
            text: Cell text containing player info

        Returns:
            Tuple of (number, position, name)
        """
        text = text.strip()

        # Extract position
        position = ""
        pos_match = POSITION_PATTERN.search(text)
        if pos_match:
            position = pos_match.group(1)
            # Remove position from text for further parsing
            text = POSITION_PATTERN.sub("", text).strip()

        # Extract number (first digits)
        num_match = re.match(r"#?(\d+)\s*", text)
        number: int | None = None
        name = text

        if num_match:
            number = int(num_match.group(1))
            name = text[num_match.end() :].strip()

        # Clean up name
        name = re.sub(r"^\s*#?\d+\s*", "", name).strip()

        return number, position, name

    def _parse_goalie_row(
        self, cells: list[Tag], col_indices: dict[str, int]
    ) -> GoalieStats | None:
        """Parse a goalie statistics row.

        In the ES report, goalies have the same column structure as players
        but most stats are blank. We extract number and name only.

        Note: Detailed goalie stats (TOI, Saves, GA, Sv%) are NOT in the ES report.
        Those are in the Game Summary (GS) or other reports.

        Args:
            cells: Table cells for the row
            col_indices: Column index mapping

        Returns:
            GoalieStats or None if parsing fails
        """
        if len(cells) < 3:
            return None

        # Get number and name from their respective columns
        num_idx = col_indices.get("NUM", 0)
        name_idx = col_indices.get("NAME", 2)

        number = (
            self._safe_int(self._get_text(cells[num_idx]))
            if num_idx < len(cells)
            else None
        )
        name = self._get_text(cells[name_idx]).strip() if name_idx < len(cells) else ""

        if number is None:
            return None

        # ES report doesn't have goalie-specific stats like SA, Saves, GA, Sv%
        # Those appear in the GS (Game Summary) report instead
        return GoalieStats(
            number=number,
            name=name,
            toi="0:00",
            shots_against=0,
            saves=0,
            goals_against=0,
            sv_pct=None,
        )

    def _parse_totals_row(
        self, cells: list[Tag], col_indices: dict[str, int]
    ) -> dict[str, int]:
        """Parse team totals row.

        Args:
            cells: Table cells for the row
            col_indices: Column index mapping

        Returns:
            Dictionary of total stats
        """
        totals: dict[str, int] = {}

        stat_columns = ["G", "A", "P", "PIM", "S", "HT", "BS", "FW", "FL"]
        for col in stat_columns:
            idx = col_indices.get(col)
            if idx is not None and idx < len(cells):
                val = self._safe_int(self._get_text(cells[idx]))
                if val is not None:
                    totals[col.lower()] = val

        return totals

    def _summary_to_dict(self, summary: ParsedEventSummary) -> dict[str, Any]:
        """Convert ParsedEventSummary to dictionary.

        Args:
            summary: Parsed event summary data

        Returns:
            Dictionary representation for JSON serialization
        """
        return {
            "game_id": summary.game_id,
            "season_id": summary.season_id,
            "away_team": self._team_to_dict(summary.away_team),
            "home_team": self._team_to_dict(summary.home_team),
        }

    def _team_to_dict(self, team: TeamEventSummary) -> dict[str, Any]:
        """Convert TeamEventSummary to dictionary.

        Args:
            team: Team event summary data

        Returns:
            Dictionary representation
        """
        return {
            "name": team.name,
            "abbrev": team.abbrev,
            "players": [
                {
                    "number": p.number,
                    "position": p.position,
                    "name": p.name,
                    "goals": p.goals,
                    "assists": p.assists,
                    "points": p.points,
                    "plus_minus": p.plus_minus,
                    "pn": p.pn,
                    "pim": p.pim,
                    "toi_total": p.toi_total,
                    "toi_ev": p.toi_ev,
                    "toi_pp": p.toi_pp,
                    "toi_sh": p.toi_sh,
                    "shots": p.shots,
                    "missed_shots": p.missed_shots,
                    "hits": p.hits,
                    "giveaways": p.giveaways,
                    "takeaways": p.takeaways,
                    "blocked_shots": p.blocked_shots,
                    "faceoff_wins": p.faceoff_wins,
                    "faceoff_losses": p.faceoff_losses,
                    "faceoff_pct": p.faceoff_pct,
                }
                for p in team.players
            ],
            "goalies": [
                {
                    "number": g.number,
                    "name": g.name,
                    "toi": g.toi,
                    "shots_against": g.shots_against,
                    "saves": g.saves,
                    "goals_against": g.goals_against,
                    "sv_pct": g.sv_pct,
                }
                for g in team.goalies
            ],
            "totals": team.totals,
        }

    async def persist(
        self,
        db: DatabaseService,
        summaries: list[dict[str, Any]],
    ) -> int:
        """Persist event summary data to the database.

        Stores parsed HTML event summary data including player statistics
        for cross-source validation.

        Args:
            db: Database service instance
            summaries: List of parsed event summary dictionaries

        Returns:
            Number of event summaries persisted
        """
        if not summaries:
            return 0

        count = 0
        for summary in summaries:
            game_id = summary.get("game_id")
            season_id = summary.get("season_id")

            if not game_id or not season_id:
                logger.warning("Skipping event summary without game_id or season_id")
                continue

            away_team = summary.get("away_team", {})
            home_team = summary.get("home_team", {})

            await db.execute(
                """
                INSERT INTO html_event_summary (
                    game_id, season_id, away_team_abbrev, home_team_abbrev,
                    away_skaters, home_skaters, away_goalies, home_goalies,
                    away_totals, home_totals, parsed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP)
                ON CONFLICT (game_id, season_id) DO UPDATE SET
                    away_team_abbrev = EXCLUDED.away_team_abbrev,
                    home_team_abbrev = EXCLUDED.home_team_abbrev,
                    away_skaters = EXCLUDED.away_skaters,
                    home_skaters = EXCLUDED.home_skaters,
                    away_goalies = EXCLUDED.away_goalies,
                    home_goalies = EXCLUDED.home_goalies,
                    away_totals = EXCLUDED.away_totals,
                    home_totals = EXCLUDED.home_totals,
                    parsed_at = CURRENT_TIMESTAMP
                """,
                game_id,
                season_id,
                away_team.get("abbrev"),
                home_team.get("abbrev"),
                json.dumps(away_team.get("players", [])),
                json.dumps(home_team.get("players", [])),
                json.dumps(away_team.get("goalies", [])),
                json.dumps(home_team.get("goalies", [])),
                json.dumps(away_team.get("totals", {})),
                json.dumps(home_team.get("totals", {})),
            )
            count += 1

        logger.info("Persisted %d HTML event summaries", count)
        return count
