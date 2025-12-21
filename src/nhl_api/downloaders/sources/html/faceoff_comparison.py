"""NHL Faceoff Comparison (FC) HTML Downloader.

Downloads and parses Faceoff Comparison HTML reports from the NHL website.
These reports contain head-to-head faceoff matchups between players.

URL Pattern: https://www.nhl.com/scores/htmlreports/{season}/FC{game_suffix}.HTM

Example usage:
    config = HTMLDownloaderConfig()
    async with FaceoffComparisonDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        matchups = result.data["matchups"]
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.sources.html.base_html_downloader import (
    BaseHTMLDownloader,
)

logger = logging.getLogger(__name__)

# Pattern to parse faceoff result: "8-9 / 89%" -> (wins=8, total=9, pct=89)
FACEOFF_RESULT_PATTERN = re.compile(r"(\d+)-(\d+)\s*/\s*(\d+)%")

# Pattern to parse player info from "vs." line: "vs. 20 C AHO, SEBASTIAN"
VS_PLAYER_PATTERN = re.compile(r"vs\.\s*(\d+)\s+([A-Z])\s+(.+)", re.IGNORECASE)

# Pattern to extract team abbreviation from logo URL
TEAM_LOGO_PATTERN = re.compile(r"logoc([a-z]{3})\.gif", re.IGNORECASE)


@dataclass
class PlayerInfo:
    """Player information for faceoff matchup."""

    number: int
    position: str
    name: str


@dataclass
class FaceoffResult:
    """Faceoff result for a specific zone or total."""

    wins: int
    total: int
    percentage: float | None = None


@dataclass
class FaceoffMatchup:
    """Head-to-head faceoff matchup between two players."""

    player: PlayerInfo
    opponent: PlayerInfo
    offensive: FaceoffResult | None = None
    defensive: FaceoffResult | None = None
    neutral: FaceoffResult | None = None
    total: FaceoffResult | None = None


@dataclass
class PlayerFaceoffSummary:
    """Summary of all faceoffs for a player."""

    player: PlayerInfo
    offensive: FaceoffResult | None = None
    defensive: FaceoffResult | None = None
    neutral: FaceoffResult | None = None
    total: FaceoffResult | None = None
    matchups: list[FaceoffMatchup] = field(default_factory=list)


@dataclass
class TeamFaceoffSummary:
    """Team faceoff summary containing all player summaries."""

    name: str
    abbrev: str
    players: list[PlayerFaceoffSummary] = field(default_factory=list)


@dataclass
class ZoneTotals:
    """Zone totals for a team."""

    wins: int = 0
    total: int = 0


@dataclass
class ParsedFaceoffComparison:
    """Complete parsed faceoff comparison data."""

    game_id: int
    season_id: int
    away_team: TeamFaceoffSummary
    home_team: TeamFaceoffSummary
    zone_summary: dict[str, dict[str, ZoneTotals]] = field(default_factory=dict)


class FaceoffComparisonDownloader(BaseHTMLDownloader):
    """Downloads and parses NHL Faceoff Comparison HTML reports.

    The Faceoff Comparison report contains:
    - Head-to-head faceoff matchups between players
    - Zone breakdown (Offensive, Defensive, Neutral)
    - Win/loss counts and percentages

    Example:
        config = HTMLDownloaderConfig()
        async with FaceoffComparisonDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)

            # Access parsed data
            matchups = result.data["matchups"]
            zone_summary = result.data["zone_summary"]

            # Access raw HTML for reprocessing
            raw_html = result.raw_content
    """

    @property
    def report_type(self) -> str:
        """Return report type code for Faceoff Comparison."""
        return "FC"

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse Faceoff Comparison HTML into structured data.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed faceoff comparison data
        """
        season_id = self._extract_season_from_game_id(game_id)

        # Parse away team data
        away_team = self._parse_team_faceoffs(soup, is_away=True)

        # Parse home team data
        home_team = self._parse_team_faceoffs(soup, is_away=False)

        # Calculate zone summary from player totals
        zone_summary = self._calculate_zone_summary(away_team, home_team)

        # Build result
        result = ParsedFaceoffComparison(
            game_id=game_id,
            season_id=season_id,
            away_team=away_team,
            home_team=home_team,
            zone_summary=zone_summary,
        )

        return self._comparison_to_dict(result)

    def _parse_team_faceoffs(
        self, soup: BeautifulSoup, *, is_away: bool
    ) -> TeamFaceoffSummary:
        """Parse faceoff data for one team.

        Args:
            soup: BeautifulSoup document
            is_away: True for away team, False for home team

        Returns:
            TeamFaceoffSummary with all player faceoff data
        """
        team_name = ""
        team_abbrev = ""
        players: list[PlayerFaceoffSummary] = []

        # Get team info from header
        header_id = "Visitor" if is_away else "Home"
        header_table = soup.find("table", id=header_id)
        if header_table:
            team_name, team_abbrev = self._extract_team_info(header_table)

        # Find the team faceoff table
        # Tables have a teamHeading with team name
        team_tables = self._find_team_faceoff_tables(soup)

        # First table is away, second is home
        table_index = 0 if is_away else 1
        if table_index < len(team_tables):
            players = self._parse_faceoff_table(team_tables[table_index])

        return TeamFaceoffSummary(
            name=team_name,
            abbrev=team_abbrev,
            players=players,
        )

    def _extract_team_info(self, table: Tag) -> tuple[str, str]:
        """Extract team name and abbreviation from header table.

        Args:
            table: Team header table element

        Returns:
            Tuple of (team_name, team_abbrev)
        """
        name = ""
        abbrev = ""

        # Find team logo image for name and abbreviation
        img = table.find("img", alt=True)
        if img:
            alt_text = str(img.get("alt", ""))
            if alt_text:
                name = alt_text
            src = str(img.get("src", ""))
            match = TEAM_LOGO_PATTERN.search(src)
            if match:
                abbrev = match.group(1).upper()

        return name, abbrev

    def _find_team_faceoff_tables(self, soup: BeautifulSoup) -> list[Tag]:
        """Find the two team faceoff tables in the document.

        The tables have a teamHeading row with the team name and contain
        player rows with faceoff data. Each team's table is in a separate
        `<td valign="top">` container.

        Args:
            soup: BeautifulSoup document

        Returns:
            List of two table elements (away, home)
        """
        tables: list[Tag] = []

        # Find all td elements with valign="top" that contain team tables
        # These are the container cells for each team's data
        for td in soup.find_all("td", attrs={"valign": "top", "width": "100%"}):
            # Look for a table with teamHeading inside this container
            for table in td.find_all("table", recursive=False):
                heading = table.find(
                    "td", class_=lambda c: c and "teamHeading" in str(c)
                )
                if heading:
                    # Verify it has playerHeading rows (actual faceoff data)
                    player_rows = table.find_all(
                        "td", class_=lambda c: c and "playerHeading" in str(c)
                    )
                    if player_rows:
                        tables.append(table)
                        break  # Only one table per container

        return tables

    def _parse_faceoff_table(self, table: Tag) -> list[PlayerFaceoffSummary]:
        """Parse a team's faceoff table.

        The table structure:
        - Player header rows (playerHeading class) contain player totals
        - Following rows contain "vs. PLAYER" matchup details
        - Spacer rows separate players

        Args:
            table: Table element containing faceoff data

        Returns:
            List of PlayerFaceoffSummary objects
        """
        players: list[PlayerFaceoffSummary] = []
        current_player: PlayerFaceoffSummary | None = None

        rows = table.find_all("tr")
        for row in rows:
            # Use recursive=False to get only direct children, not nested td elements
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue

            # Check if this is a player header row
            first_cell = cells[0]
            cell_class = str(first_cell.get("class", ""))

            if "playerHeading" in cell_class:
                # Save previous player if exists
                if current_player:
                    players.append(current_player)

                # Parse new player
                current_player = self._parse_player_header_row(cells)

            elif current_player and len(cells) >= 3:
                # Check if this is a matchup row (contains "vs.")
                # The opponent name is in a nested table in one of the cells
                # The structure has colspan=2 on first cell, so vs. table is at index 1
                for cell in cells:
                    nested_table = cell.find("table")
                    if nested_table:
                        vs_text = nested_table.get_text(strip=True)
                        if vs_text.lower().startswith("vs."):
                            matchup = self._parse_matchup_row(
                                cells, vs_text, current_player.player
                            )
                            if matchup:
                                current_player.matchups.append(matchup)
                            break

        # Don't forget the last player
        if current_player:
            players.append(current_player)

        return players

    def _parse_player_header_row(self, cells: list[Tag]) -> PlayerFaceoffSummary:
        """Parse a player header row.

        Format: #, Pos, Player, Off., Def., Neu., TOT

        Args:
            cells: Table cells for the row

        Returns:
            PlayerFaceoffSummary with player info and totals
        """
        # Extract player info
        number = self._safe_int(self._get_text(cells[0])) or 0
        position = self._get_text(cells[1]).strip() if len(cells) > 1 else ""
        name = self._get_text(cells[2]).strip() if len(cells) > 2 else ""

        player = PlayerInfo(number=number, position=position, name=name)

        # Extract zone results
        offensive = self._parse_faceoff_cell(cells[3]) if len(cells) > 3 else None
        defensive = self._parse_faceoff_cell(cells[4]) if len(cells) > 4 else None
        neutral = self._parse_faceoff_cell(cells[5]) if len(cells) > 5 else None
        total = self._parse_faceoff_cell(cells[6]) if len(cells) > 6 else None

        return PlayerFaceoffSummary(
            player=player,
            offensive=offensive,
            defensive=defensive,
            neutral=neutral,
            total=total,
        )

    def _parse_matchup_row(
        self, cells: list[Tag], vs_text: str, player: PlayerInfo
    ) -> FaceoffMatchup | None:
        """Parse a matchup row.

        The matchup row structure (6 cells due to colspan=2 on first):
        - Cell 0: empty (colspan=2)
        - Cell 1: vs. player info (nested table)
        - Cell 2: offensive zone result
        - Cell 3: defensive zone result
        - Cell 4: neutral zone result
        - Cell 5: total result

        Args:
            cells: Table cells for the row
            vs_text: Text containing "vs. # POS NAME"
            player: The player this matchup is for

        Returns:
            FaceoffMatchup or None if parsing fails
        """
        # Parse opponent from vs_text
        match = VS_PLAYER_PATTERN.match(vs_text)
        if not match:
            return None

        opponent = PlayerInfo(
            number=int(match.group(1)),
            position=match.group(2).upper(),
            name=match.group(3).strip(),
        )

        # Extract zone results - adjust indices for colspan=2 structure
        # Cells: 0=empty(colspan2), 1=vs, 2=off, 3=def, 4=neu, 5=tot
        offensive = self._parse_faceoff_cell(cells[2]) if len(cells) > 2 else None
        defensive = self._parse_faceoff_cell(cells[3]) if len(cells) > 3 else None
        neutral = self._parse_faceoff_cell(cells[4]) if len(cells) > 4 else None
        total = self._parse_faceoff_cell(cells[5]) if len(cells) > 5 else None

        return FaceoffMatchup(
            player=player,
            opponent=opponent,
            offensive=offensive,
            defensive=defensive,
            neutral=neutral,
            total=total,
        )

    def _parse_faceoff_cell(self, cell: Tag) -> FaceoffResult | None:
        """Parse a faceoff result cell.

        Format: "8-9 / 89%" or "&nbsp;" for empty

        Args:
            cell: Table cell containing faceoff result

        Returns:
            FaceoffResult or None if empty/invalid
        """
        text = self._get_text(cell).strip()
        if not text or text == "\xa0":  # &nbsp;
            return None

        match = FACEOFF_RESULT_PATTERN.match(text)
        if not match:
            return None

        wins = int(match.group(1))
        total = int(match.group(2))
        percentage = float(match.group(3))

        return FaceoffResult(wins=wins, total=total, percentage=percentage)

    def _calculate_zone_summary(
        self, away_team: TeamFaceoffSummary, home_team: TeamFaceoffSummary
    ) -> dict[str, dict[str, ZoneTotals]]:
        """Calculate zone totals from player summaries.

        Args:
            away_team: Away team faceoff summary
            home_team: Home team faceoff summary

        Returns:
            Zone summary with wins/totals for each team and zone
        """
        zones = ["offensive", "defensive", "neutral"]
        summary: dict[str, dict[str, ZoneTotals]] = {}

        for zone in zones:
            away_totals = ZoneTotals()
            home_totals = ZoneTotals()

            # Sum away team
            for player in away_team.players:
                result = getattr(player, zone, None)
                if result:
                    away_totals.wins += result.wins
                    away_totals.total += result.total

            # Sum home team
            for player in home_team.players:
                result = getattr(player, zone, None)
                if result:
                    home_totals.wins += result.wins
                    home_totals.total += result.total

            summary[zone] = {
                "away": away_totals,
                "home": home_totals,
            }

        return summary

    def _comparison_to_dict(
        self, comparison: ParsedFaceoffComparison
    ) -> dict[str, Any]:
        """Convert ParsedFaceoffComparison to dictionary.

        Args:
            comparison: Parsed faceoff comparison data

        Returns:
            Dictionary representation for JSON serialization
        """
        return {
            "game_id": comparison.game_id,
            "season_id": comparison.season_id,
            "away_team": self._team_to_dict(comparison.away_team),
            "home_team": self._team_to_dict(comparison.home_team),
            "zone_summary": {
                zone: {
                    "away": {
                        "wins": totals["away"].wins,
                        "total": totals["away"].total,
                    },
                    "home": {
                        "wins": totals["home"].wins,
                        "total": totals["home"].total,
                    },
                }
                for zone, totals in comparison.zone_summary.items()
            },
            "matchups": self._extract_all_matchups(comparison),
        }

    def _team_to_dict(self, team: TeamFaceoffSummary) -> dict[str, Any]:
        """Convert TeamFaceoffSummary to dictionary.

        Args:
            team: Team faceoff summary data

        Returns:
            Dictionary representation
        """
        return {
            "name": team.name,
            "abbrev": team.abbrev,
            "players": [
                {
                    "number": p.player.number,
                    "position": p.player.position,
                    "name": p.player.name,
                    "offensive": self._result_to_dict(p.offensive),
                    "defensive": self._result_to_dict(p.defensive),
                    "neutral": self._result_to_dict(p.neutral),
                    "total": self._result_to_dict(p.total),
                    "matchups": [
                        {
                            "opponent": {
                                "number": m.opponent.number,
                                "position": m.opponent.position,
                                "name": m.opponent.name,
                            },
                            "offensive": self._result_to_dict(m.offensive),
                            "defensive": self._result_to_dict(m.defensive),
                            "neutral": self._result_to_dict(m.neutral),
                            "total": self._result_to_dict(m.total),
                        }
                        for m in p.matchups
                    ],
                }
                for p in team.players
            ],
        }

    def _result_to_dict(self, result: FaceoffResult | None) -> dict[str, Any] | None:
        """Convert FaceoffResult to dictionary.

        Args:
            result: Faceoff result or None

        Returns:
            Dictionary representation or None
        """
        if result is None:
            return None
        return {
            "wins": result.wins,
            "total": result.total,
            "percentage": result.percentage,
        }

    def _extract_all_matchups(
        self, comparison: ParsedFaceoffComparison
    ) -> list[dict[str, Any]]:
        """Extract flattened list of all matchups for easy querying.

        This provides an alternative view of the data as a flat list
        of matchups with zone breakdowns.

        Args:
            comparison: Parsed faceoff comparison

        Returns:
            List of matchup dictionaries
        """
        matchups: list[dict[str, Any]] = []

        # Process away team matchups
        for player_summary in comparison.away_team.players:
            for matchup in player_summary.matchups:
                matchups.append(
                    {
                        "away_player": {
                            "number": matchup.player.number,
                            "name": matchup.player.name,
                        },
                        "home_player": {
                            "number": matchup.opponent.number,
                            "name": matchup.opponent.name,
                        },
                        "away_wins": matchup.total.wins if matchup.total else 0,
                        "home_wins": (
                            matchup.total.total - matchup.total.wins
                            if matchup.total
                            else 0
                        ),
                        "zones": {
                            "offensive": self._result_to_dict(matchup.offensive),
                            "defensive": self._result_to_dict(matchup.defensive),
                            "neutral": self._result_to_dict(matchup.neutral),
                        },
                    }
                )

        return matchups
