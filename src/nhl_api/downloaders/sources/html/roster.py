"""NHL Roster Report (RO) HTML Downloader.

Downloads and parses Roster Report HTML reports from the NHL website.
These reports contain team rosters, scratches, coaches, and officials.

URL Pattern: https://www.nhl.com/scores/htmlreports/{season}/RO{game_suffix}.HTM

Example usage:
    config = HTMLDownloaderConfig()
    async with RosterDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        roster = result.data
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

# Pattern for captain designation: "ANDERS LEE  (C)" or "BROCK NELSON  (A)"
CAPTAIN_PATTERN = re.compile(r"(.+?)\s*\(([CA])\)\s*$")


@dataclass
class PlayerRoster:
    """Player information from roster report."""

    number: int
    position: str  # C, L, R, D, G
    name: str
    is_starter: bool = False
    is_captain: bool = False
    is_alternate: bool = False


@dataclass
class CoachInfo:
    """Coach information."""

    name: str
    role: str = "Head Coach"


@dataclass
class OfficialInfo:
    """Official information."""

    number: int | None
    name: str
    role: str  # "Referee" or "Linesman"


@dataclass
class TeamRoster:
    """Complete roster for one team."""

    name: str
    abbrev: str
    skaters: list[PlayerRoster] = field(default_factory=list)
    goalies: list[PlayerRoster] = field(default_factory=list)
    scratches: list[PlayerRoster] = field(default_factory=list)
    coaches: list[CoachInfo] = field(default_factory=list)


@dataclass
class ParsedRoster:
    """Complete parsed roster data."""

    game_id: int
    season_id: int
    date: str
    venue: str
    attendance: int | None
    away_team: TeamRoster
    home_team: TeamRoster
    referees: list[OfficialInfo] = field(default_factory=list)
    linesmen: list[OfficialInfo] = field(default_factory=list)


class RosterDownloader(BaseHTMLDownloader):
    """Downloads and parses NHL Roster Report HTML reports.

    The Roster Report contains:
    - Team rosters (skaters and goalies)
    - Starting lineup indicators (bold text)
    - Captain/Alternate captain designations
    - Scratches
    - Head coaches
    - Officials (referees and linesmen)

    Example:
        config = HTMLDownloaderConfig()
        async with RosterDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)

            # Access parsed data
            away_roster = result.data["away_team"]
            home_roster = result.data["home_team"]

            # Access raw HTML for reprocessing
            raw_html = result.raw_content
    """

    @property
    def report_type(self) -> str:
        """Return report type code for Roster Report."""
        return "RO"

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse Roster Report HTML into structured data.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed roster data
        """
        season_id = self._extract_season_from_game_id(game_id)

        # Parse game info
        date, venue, attendance = self._parse_game_info(soup)

        # Parse team info from header
        away_abbrev, home_abbrev = self._parse_team_abbrevs(soup)
        away_name, home_name = self._parse_team_names(soup)

        # Parse player rosters
        away_players, home_players = self._parse_player_rosters(soup)

        # Separate skaters and goalies
        away_skaters = [p for p in away_players if p.position != "G"]
        away_goalies = [p for p in away_players if p.position == "G"]
        home_skaters = [p for p in home_players if p.position != "G"]
        home_goalies = [p for p in home_players if p.position == "G"]

        # Parse scratches
        away_scratches, home_scratches = self._parse_scratches(soup)

        # Parse coaches
        away_coaches, home_coaches = self._parse_coaches(soup)

        # Parse officials
        referees, linesmen = self._parse_officials(soup)

        # Build team rosters
        away_team = TeamRoster(
            name=away_name,
            abbrev=away_abbrev,
            skaters=away_skaters,
            goalies=away_goalies,
            scratches=away_scratches,
            coaches=away_coaches,
        )

        home_team = TeamRoster(
            name=home_name,
            abbrev=home_abbrev,
            skaters=home_skaters,
            goalies=home_goalies,
            scratches=home_scratches,
            coaches=home_coaches,
        )

        # Build result
        roster = ParsedRoster(
            game_id=game_id,
            season_id=season_id,
            date=date,
            venue=venue,
            attendance=attendance,
            away_team=away_team,
            home_team=home_team,
            referees=referees,
            linesmen=linesmen,
        )

        return self._roster_to_dict(roster)

    def _parse_game_info(self, soup: BeautifulSoup) -> tuple[str, str, int | None]:
        """Parse game date, venue, and attendance.

        Returns:
            Tuple of (date, venue, attendance)
        """
        date = ""
        venue = ""
        attendance = None

        game_info = soup.find("table", id="GameInfo")
        if not game_info:
            return date, venue, attendance

        cells = game_info.find_all("td")
        for cell in cells:
            text = self._get_text(cell)

            # Date format: "Tuesday, December 17, 2024"
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

            # Attendance and venue: "Attendance 18,700 at Lenovo Center"
            if "Attendance" in text:
                # Extract attendance number
                match = re.search(r"Attendance\s*([\d,]+)", text)
                if match:
                    attendance = self._safe_int(match.group(1).replace(",", ""))

                # Extract venue (after "at")
                at_match = re.search(r"at\s+(.+)$", text)
                if at_match:
                    venue = at_match.group(1).strip()

        return date, venue, attendance

    def _parse_team_abbrevs(self, soup: BeautifulSoup) -> tuple[str, str]:
        """Parse team abbreviations from logo URLs.

        Returns:
            Tuple of (away_abbrev, home_abbrev)
        """
        away_abbrev = ""
        home_abbrev = ""

        # Pattern for logo URL: logocnyi.gif -> NYI
        logo_pattern = re.compile(r"logoc([a-z]{3})\.gif", re.IGNORECASE)

        visitor_table = soup.find("table", id="Visitor")
        if visitor_table:
            img = visitor_table.find("img", alt=True)
            if img and isinstance(img, Tag):
                src = cast(str, img.get("src", ""))
                match = logo_pattern.search(src)
                if match:
                    away_abbrev = match.group(1).upper()

        home_table = soup.find("table", id="Home")
        if home_table:
            img = home_table.find("img", alt=True)
            if img and isinstance(img, Tag):
                src = cast(str, img.get("src", ""))
                match = logo_pattern.search(src)
                if match:
                    home_abbrev = match.group(1).upper()

        return away_abbrev, home_abbrev

    def _parse_team_names(self, soup: BeautifulSoup) -> tuple[str, str]:
        """Parse team names from header.

        Returns:
            Tuple of (away_name, home_name)
        """
        away_name = ""
        home_name = ""

        # Find team heading cells
        team_headings = soup.find_all("td", class_=re.compile(r"teamHeading"))
        if len(team_headings) >= 2:
            away_name = self._get_text(team_headings[0])
            home_name = self._get_text(team_headings[1])

        return away_name, home_name

    def _parse_player_rosters(
        self, soup: BeautifulSoup
    ) -> tuple[list[PlayerRoster], list[PlayerRoster]]:
        """Parse player rosters for both teams.

        Returns:
            Tuple of (away_players, home_players)
        """
        away_players: list[PlayerRoster] = []
        home_players: list[PlayerRoster] = []

        # Find the main roster section (before scratches)
        # It's a table with two columns containing player tables
        main_tables = self._find_roster_tables(soup)

        if len(main_tables) >= 2:
            away_players = self._parse_player_table(main_tables[0])
            home_players = self._parse_player_table(main_tables[1])

        return away_players, home_players

    def _find_roster_tables(self, soup: BeautifulSoup) -> list[Tag]:
        """Find the main roster tables (excluding scratches).

        Returns:
            List of player roster tables
        """
        tables: list[Tag] = []

        # Find all tables with player roster structure (# | Pos | Name header)
        for table in soup.find_all("table"):
            # Check if this table has the roster header
            header_row = table.find("tr")
            if not header_row:
                continue

            cells = header_row.find_all("td")
            if len(cells) >= 3:
                headers = [self._get_text(c) for c in cells[:3]]
                if headers == ["#", "Pos", "Name"]:
                    # Check if this is NOT inside the scratches section
                    parent = table.find_parent("tr", id="Scratches")
                    if parent is None:
                        tables.append(table)

        return tables[:2]  # Return first two (away and home)

    def _parse_player_table(self, table: Tag) -> list[PlayerRoster]:
        """Parse a single player roster table.

        Args:
            table: BeautifulSoup table element

        Returns:
            List of PlayerRoster objects
        """
        players: list[PlayerRoster] = []

        rows = table.find_all("tr")
        for row in rows[1:]:  # Skip header row
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            player = self._parse_player_row(cells)
            if player:
                players.append(player)

        return players

    def _parse_player_row(self, cells: list[Tag]) -> PlayerRoster | None:
        """Parse a single player row.

        Args:
            cells: List of td elements

        Returns:
            PlayerRoster object or None
        """
        if len(cells) < 3:
            return None

        # Get raw text
        number_text = self._get_text(cells[0])
        position = self._get_text(cells[1])
        name_text = self._get_text(cells[2])

        # Parse number
        number = self._safe_int(number_text)
        if number is None:
            return None

        # Validate position
        if position not in ("C", "L", "R", "D", "G"):
            return None

        # Check for captain designation
        is_captain = False
        is_alternate = False
        name = name_text

        captain_match = CAPTAIN_PATTERN.match(name_text)
        if captain_match:
            name = captain_match.group(1).strip()
            designation = captain_match.group(2)
            if designation == "C":
                is_captain = True
            elif designation == "A":
                is_alternate = True

        # Check if starter (bold class)
        is_starter = self._is_starter(cells[0])

        return PlayerRoster(
            number=number,
            position=position,
            name=name,
            is_starter=is_starter,
            is_captain=is_captain,
            is_alternate=is_alternate,
        )

    def _is_starter(self, cell: Tag) -> bool:
        """Check if a cell has the 'bold' class indicating starter.

        Args:
            cell: BeautifulSoup element

        Returns:
            True if player is a starter
        """
        class_attr = cell.get("class")
        if class_attr is None:
            return False
        if isinstance(class_attr, list):
            # Check if "bold" is in the class list
            return "bold" in class_attr
        if isinstance(class_attr, str):
            return "bold" in class_attr
        return False

    def _parse_scratches(
        self, soup: BeautifulSoup
    ) -> tuple[list[PlayerRoster], list[PlayerRoster]]:
        """Parse scratches for both teams.

        Returns:
            Tuple of (away_scratches, home_scratches)
        """
        away_scratches: list[PlayerRoster] = []
        home_scratches: list[PlayerRoster] = []

        # Find scratches section by id
        scratches_row = soup.find("tr", id="Scratches")
        if not scratches_row:
            return away_scratches, home_scratches

        # Find tables within scratches section
        tables = scratches_row.find_all("table")

        # Filter to tables with roster structure
        roster_tables = []
        for table in tables:
            header_row = table.find("tr")
            if header_row:
                cells = header_row.find_all("td")
                if len(cells) >= 3:
                    headers = [self._get_text(c) for c in cells[:3]]
                    if headers == ["#", "Pos", "Name"]:
                        roster_tables.append(table)

        if len(roster_tables) >= 2:
            away_scratches = self._parse_player_table(roster_tables[0])
            home_scratches = self._parse_player_table(roster_tables[1])

        return away_scratches, home_scratches

    def _parse_coaches(
        self, soup: BeautifulSoup
    ) -> tuple[list[CoachInfo], list[CoachInfo]]:
        """Parse head coaches for both teams.

        Returns:
            Tuple of (away_coaches, home_coaches)
        """
        away_coaches: list[CoachInfo] = []
        home_coaches: list[CoachInfo] = []

        # Find head coaches section by id
        coaches_row = soup.find("tr", id="HeadCoaches")
        if not coaches_row:
            return away_coaches, home_coaches

        # Find tables within coaches section
        tables = coaches_row.find_all("table")
        if len(tables) >= 2:
            # First table is away, second is home
            away_name = self._get_text(tables[0].find("td"))
            if away_name:
                away_coaches.append(CoachInfo(name=away_name, role="Head Coach"))

            home_name = self._get_text(tables[1].find("td"))
            if home_name:
                home_coaches.append(CoachInfo(name=home_name, role="Head Coach"))

        return away_coaches, home_coaches

    def _parse_officials(
        self, soup: BeautifulSoup
    ) -> tuple[list[OfficialInfo], list[OfficialInfo]]:
        """Parse officials (referees and linesmen).

        Returns:
            Tuple of (referees, linesmen)
        """
        referees: list[OfficialInfo] = []
        linesmen: list[OfficialInfo] = []

        # Find officials section by header text
        for td in soup.find_all("td", class_=re.compile(r"header")):
            if self._get_text(td) == "Officials":
                # Find the table containing officials
                parent_row = td.find_parent("tr")
                if parent_row:
                    next_row = parent_row.find_next_sibling("tr")
                    if next_row:
                        officials_table = next_row.find("table")
                        if officials_table:
                            referees, linesmen = self._parse_officials_table(
                                officials_table
                            )
                break

        return referees, linesmen

    def _parse_officials_table(
        self, table: Tag
    ) -> tuple[list[OfficialInfo], list[OfficialInfo]]:
        """Parse the officials table.

        The table structure is:
        - Row 1: "Referee" | "Linesperson" headers
        - Row 2: nested table with refs | nested table with linesmen
        - Row 3+: may have "Standby" headers and empty tables

        Args:
            table: BeautifulSoup table element

        Returns:
            Tuple of (referees, linesmen)
        """
        referees: list[OfficialInfo] = []
        linesmen: list[OfficialInfo] = []

        # Pattern to extract official: "#7 Garrett Rank"
        official_pattern = re.compile(r"#(\d+)\s+(.+)")

        # Find the header row to identify column positions
        rows = table.find_all("tr", recursive=False)
        referee_col = None
        linesperson_col = None

        for row in rows:
            # Get direct td children only
            cells = row.find_all("td", recursive=False)

            # Check for header row
            cell_texts = [self._get_text(c) for c in cells]
            if "Referee" in cell_texts:
                referee_col = cell_texts.index("Referee")
            if "Linesperson" in cell_texts:
                linesperson_col = cell_texts.index("Linesperson")

            # Parse officials from cells with nested tables
            for idx, cell in enumerate(cells):
                # Skip header cells
                text = self._get_text(cell)
                if text in ("Referee", "Linesperson", "Standby", ""):
                    continue

                # Determine role based on column position
                role = None
                if idx == referee_col:
                    role = "Referee"
                elif idx == linesperson_col:
                    role = "Linesman"

                if role is None:
                    continue

                # Look for nested table with officials
                nested_table = cell.find("table")
                if nested_table:
                    for nested_td in nested_table.find_all("td"):
                        official_text = self._get_text(nested_td)
                        match = official_pattern.match(official_text)
                        if match:
                            official = OfficialInfo(
                                number=int(match.group(1)),
                                name=match.group(2).strip(),
                                role=role,
                            )
                            if role == "Referee":
                                referees.append(official)
                            else:
                                linesmen.append(official)

        return referees, linesmen

    def _roster_to_dict(self, roster: ParsedRoster) -> dict[str, Any]:
        """Convert ParsedRoster to dictionary."""
        return {
            "game_id": roster.game_id,
            "season_id": roster.season_id,
            "date": roster.date,
            "venue": roster.venue,
            "attendance": roster.attendance,
            "away_team": self._team_roster_to_dict(roster.away_team),
            "home_team": self._team_roster_to_dict(roster.home_team),
            "referees": [
                {"number": r.number, "name": r.name, "role": r.role}
                for r in roster.referees
            ],
            "linesmen": [
                {"number": lm.number, "name": lm.name, "role": lm.role}
                for lm in roster.linesmen
            ],
        }

    def _team_roster_to_dict(self, team: TeamRoster) -> dict[str, Any]:
        """Convert TeamRoster to dictionary."""
        return {
            "name": team.name,
            "abbrev": team.abbrev,
            "skaters": [self._player_to_dict(p) for p in team.skaters],
            "goalies": [self._player_to_dict(p) for p in team.goalies],
            "scratches": [self._player_to_dict(p) for p in team.scratches],
            "coaches": [{"name": c.name, "role": c.role} for c in team.coaches],
        }

    def _player_to_dict(self, player: PlayerRoster) -> dict[str, Any]:
        """Convert PlayerRoster to dictionary."""
        return {
            "number": player.number,
            "position": player.position,
            "name": player.name,
            "is_starter": player.is_starter,
            "is_captain": player.is_captain,
            "is_alternate": player.is_alternate,
        }
