"""NHL Faceoff Summary (FS) HTML Downloader.

Downloads and parses Faceoff Summary HTML reports from the NHL website.
These reports contain detailed faceoff statistics by player, zone, and strength.

URL Pattern: https://www.nhl.com/scores/htmlreports/{season}/FS{game_suffix}.HTM

Example usage:
    config = HTMLDownloaderConfig()
    async with FaceoffSummaryDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        summary = result.data
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

# Pattern to parse faceoff stats: "8-9/89%" -> (won=8, total=9, pct=89.0)
# Also handles: "8-9" without percentage, or "&nbsp;" for empty
FACEOFF_STAT_PATTERN = re.compile(r"(\d+)-(\d+)(?:/(\d+)%)?")

# Pattern to parse player header: "13 C BARZAL, MATHEW" -> (number, position, name)
PLAYER_HEADER_PATTERN = re.compile(r"(\d+)\s+([A-Z])\s+(.+)")


@dataclass
class FaceoffStat:
    """Single faceoff statistic (won/total/percentage)."""

    won: int = 0
    total: int = 0
    pct: float = 0.0

    @property
    def lost(self) -> int:
        """Calculate faceoffs lost."""
        return self.total - self.won


@dataclass
class ZoneFaceoffs:
    """Faceoff stats by zone."""

    offensive: FaceoffStat = field(default_factory=FaceoffStat)
    defensive: FaceoffStat = field(default_factory=FaceoffStat)
    neutral: FaceoffStat = field(default_factory=FaceoffStat)
    total: FaceoffStat = field(default_factory=FaceoffStat)


@dataclass
class StrengthFaceoffs:
    """Faceoff stats by strength situation with zone breakdown."""

    strength: str  # "5v5", "5v4", "4v5", "4v4", etc.
    zones: ZoneFaceoffs = field(default_factory=ZoneFaceoffs)


@dataclass
class PlayerFaceoffStats:
    """Complete faceoff stats for a single player."""

    number: int
    position: str
    name: str
    by_strength: list[StrengthFaceoffs] = field(default_factory=list)
    totals: ZoneFaceoffs = field(default_factory=ZoneFaceoffs)


@dataclass
class PeriodFaceoffs:
    """Faceoff stats for a single period."""

    period: str  # "1", "2", "3", "OT", "TOT"
    ev: FaceoffStat = field(default_factory=FaceoffStat)
    pp: FaceoffStat = field(default_factory=FaceoffStat)
    sh: FaceoffStat = field(default_factory=FaceoffStat)
    total: FaceoffStat = field(default_factory=FaceoffStat)


@dataclass
class TeamFaceoffSummary:
    """Complete faceoff summary for a team."""

    name: str
    by_period: list[PeriodFaceoffs] = field(default_factory=list)
    by_strength: list[StrengthFaceoffs] = field(default_factory=list)
    totals: ZoneFaceoffs = field(default_factory=ZoneFaceoffs)
    players: list[PlayerFaceoffStats] = field(default_factory=list)


@dataclass
class ParsedFaceoffSummary:
    """Complete parsed faceoff summary data."""

    game_id: int
    season_id: int
    away_team: TeamFaceoffSummary
    home_team: TeamFaceoffSummary


class FaceoffSummaryDownloader(BaseHTMLDownloader):
    """Downloads and parses NHL Faceoff Summary HTML reports.

    The Faceoff Summary report contains:
    - Team faceoff totals by period (EV/PP/SH)
    - Team faceoff totals by strength and zone
    - Per-player faceoff stats with zone/strength breakdown

    Example:
        config = HTMLDownloaderConfig()
        async with FaceoffSummaryDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)

            # Access parsed data
            away_players = result.data["teams"]["away"]["players"]
            home_totals = result.data["teams"]["home"]["totals"]

            # Access raw HTML for reprocessing
            raw_html = result.raw_content
    """

    @property
    def report_type(self) -> str:
        """Return report type code for Faceoff Summary."""
        return "FS"

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse Faceoff Summary HTML into structured data.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed faceoff summary data
        """
        season_id = self._extract_season_from_game_id(game_id)

        # Parse team summaries
        away_team, home_team = self._parse_team_summaries(soup)

        # Parse player summaries
        away_players, home_players = self._parse_player_summaries(soup)
        away_team.players = away_players
        home_team.players = home_players

        summary = ParsedFaceoffSummary(
            game_id=game_id,
            season_id=season_id,
            away_team=away_team,
            home_team=home_team,
        )

        return self._summary_to_dict(summary)

    def _parse_faceoff_stat(self, text: str) -> FaceoffStat:
        """Parse faceoff stat from text like '8-9/89%' or '8-9'.

        Args:
            text: Raw text containing faceoff stat

        Returns:
            FaceoffStat with won, total, and percentage
        """
        text = text.strip()
        if not text or text == "&nbsp;" or text == "\xa0":
            return FaceoffStat()

        match = FACEOFF_STAT_PATTERN.search(text)
        if match:
            won = int(match.group(1))
            total = int(match.group(2))
            pct = (
                float(match.group(3))
                if match.group(3)
                else ((won / total * 100) if total > 0 else 0.0)
            )
            return FaceoffStat(won=won, total=total, pct=pct)

        return FaceoffStat()

    def _parse_team_summaries(
        self, soup: BeautifulSoup
    ) -> tuple[TeamFaceoffSummary, TeamFaceoffSummary]:
        """Parse team summary sections.

        Returns:
            Tuple of (away_team, home_team) summaries
        """
        away_team = TeamFaceoffSummary(name="")
        home_team = TeamFaceoffSummary(name="")

        # Find TeamTable which contains both team summaries side by side
        team_table = soup.find("table", id="TeamTable")
        if not team_table:
            return away_team, home_team

        # Find team heading cells
        team_headings = team_table.find_all(
            "td", class_=lambda c: c and "teamHeading" in c
        )
        team_names: list[str] = []
        for heading in team_headings:
            name = self._get_text(heading)
            if name and name not in team_names:
                team_names.append(name)

        if len(team_names) >= 1:
            away_team.name = team_names[0]
        if len(team_names) >= 2:
            home_team.name = team_names[1]

        # Find all tables with period data (Per, EV, PP, SH, TOT columns)
        # and strength/zone data (Strength, Off., Def., Neu., TOT columns)
        all_tables = team_table.find_all("table")

        period_tables: list[Tag] = []
        zone_tables: list[Tag] = []

        for table in all_tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # Get text from first two rows (headers may span multiple rows)
            header_text = ""
            for row in rows[:3]:
                header_text += " " + self._get_text(row).upper()

            # Period tables have "PER" and "EV" headers
            if "PER" in header_text and "EV" in header_text:
                period_tables.append(table)
            # Zone tables have "ZONE" in first row or "STRENGTH" with "OFF"
            elif (
                "ZONE" in header_text or "STRENGTH" in header_text
            ) and "OFF" in header_text:
                zone_tables.append(table)

        # Parse period tables (first is away, second is home)
        if len(period_tables) >= 1:
            away_team.by_period = self._parse_period_table(period_tables[0])
        if len(period_tables) >= 2:
            home_team.by_period = self._parse_period_table(period_tables[1])

        # Parse zone/strength tables (first is away, second is home)
        if len(zone_tables) >= 1:
            away_team.by_strength, away_team.totals = self._parse_zone_strength_table(
                zone_tables[0]
            )
        if len(zone_tables) >= 2:
            home_team.by_strength, home_team.totals = self._parse_zone_strength_table(
                zone_tables[1]
            )

        return away_team, home_team

    def _parse_period_table(self, table: Tag) -> list[PeriodFaceoffs]:
        """Parse period-by-period faceoff table.

        Args:
            table: BeautifulSoup table element

        Returns:
            List of PeriodFaceoffs for each period
        """
        periods: list[PeriodFaceoffs] = []
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            # Check if this is a data row (first cell has period number or TOT)
            first_cell_text = self._get_text(cells[0]).strip().upper()
            if first_cell_text in ("1", "2", "3", "OT", "TOT"):
                period = PeriodFaceoffs(
                    period=first_cell_text,
                    ev=self._parse_faceoff_stat(self._get_text(cells[1])),
                    pp=self._parse_faceoff_stat(self._get_text(cells[2])),
                    sh=self._parse_faceoff_stat(self._get_text(cells[3])),
                    total=self._parse_faceoff_stat(self._get_text(cells[4])),
                )
                periods.append(period)

        return periods

    def _parse_zone_strength_table(
        self, table: Tag
    ) -> tuple[list[StrengthFaceoffs], ZoneFaceoffs]:
        """Parse zone/strength breakdown table.

        Args:
            table: BeautifulSoup table element

        Returns:
            Tuple of (list of strength breakdowns, total zones)
        """
        strengths: list[StrengthFaceoffs] = []
        totals = ZoneFaceoffs()
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            first_cell_text = self._get_text(cells[0]).strip().upper()

            # Check for strength patterns (5v5, 4v5, 5v4, 4v4, etc.)
            if re.match(r"\d+V\d+", first_cell_text):
                zones = ZoneFaceoffs(
                    offensive=self._parse_faceoff_stat(self._get_text(cells[1])),
                    defensive=self._parse_faceoff_stat(self._get_text(cells[2])),
                    neutral=self._parse_faceoff_stat(self._get_text(cells[3])),
                    total=self._parse_faceoff_stat(self._get_text(cells[4])),
                )
                strengths.append(
                    StrengthFaceoffs(strength=first_cell_text.lower(), zones=zones)
                )
            elif first_cell_text == "TOT":
                totals = ZoneFaceoffs(
                    offensive=self._parse_faceoff_stat(self._get_text(cells[1])),
                    defensive=self._parse_faceoff_stat(self._get_text(cells[2])),
                    neutral=self._parse_faceoff_stat(self._get_text(cells[3])),
                    total=self._parse_faceoff_stat(self._get_text(cells[4])),
                )

        return strengths, totals

    def _parse_player_summaries(
        self, soup: BeautifulSoup
    ) -> tuple[list[PlayerFaceoffStats], list[PlayerFaceoffStats]]:
        """Parse player faceoff summary sections.

        Returns:
            Tuple of (away_players, home_players)
        """
        away_players: list[PlayerFaceoffStats] = []
        home_players: list[PlayerFaceoffStats] = []

        # Find PlayerTable
        player_table = soup.find("table", id="PlayerTable")
        if not player_table:
            return away_players, home_players

        # Find the two team columns (left is away, right is home)
        # Look for cells with valign="top" that contain player tables
        team_columns = player_table.find_all("td", attrs={"valign": "top"})

        if len(team_columns) >= 1:
            away_players = self._parse_team_players(team_columns[0])
        if len(team_columns) >= 2:
            home_players = self._parse_team_players(team_columns[1])

        return away_players, home_players

    def _parse_team_players(self, container: Tag) -> list[PlayerFaceoffStats]:
        """Parse all players from a team's section.

        Args:
            container: Container element holding player tables

        Returns:
            List of PlayerFaceoffStats
        """
        players: list[PlayerFaceoffStats] = []

        # Find all player headers (cells with playerHeading class)
        player_headers = container.find_all(
            "td", class_=lambda c: c and "playerHeading" in c
        )

        for header in player_headers:
            player = self._parse_player_section(header)
            if player:
                players.append(player)

        return players

    def _parse_player_section(self, header: Tag) -> PlayerFaceoffStats | None:
        """Parse a single player's faceoff section.

        Args:
            header: The player header cell (contains "13 C BARZAL, MATHEW")

        Returns:
            PlayerFaceoffStats or None if parsing fails
        """
        header_text = self._get_text(header)
        match = PLAYER_HEADER_PATTERN.match(header_text)

        if not match:
            logger.debug("Failed to parse player header: %s", header_text)
            return None

        number = int(match.group(1))
        position = match.group(2)
        name = match.group(3).strip()

        player = PlayerFaceoffStats(number=number, position=position, name=name)

        # Find the parent table containing this header
        parent_table = header.find_parent("table")
        if not parent_table:
            return player

        # Get all rows after the header
        rows = parent_table.find_all("tr")
        header_found = False

        for row in rows:
            # Skip until we find our header
            header_cell = row.find("td", class_=lambda c: c and "playerHeading" in c)
            if header_cell and self._get_text(header_cell) == header_text:
                header_found = True
                continue

            if not header_found:
                continue

            # Stop if we hit another player header
            if header_cell:
                break

            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            first_cell_text = self._get_text(cells[0]).strip().upper()

            # Check for strength patterns
            if re.match(r"\d+V\d+", first_cell_text):
                zones = ZoneFaceoffs(
                    offensive=self._parse_faceoff_stat(self._get_text(cells[1])),
                    defensive=self._parse_faceoff_stat(self._get_text(cells[2])),
                    neutral=self._parse_faceoff_stat(self._get_text(cells[3])),
                    total=self._parse_faceoff_stat(self._get_text(cells[4])),
                )
                player.by_strength.append(
                    StrengthFaceoffs(strength=first_cell_text.lower(), zones=zones)
                )
            elif first_cell_text == "TOT":
                player.totals = ZoneFaceoffs(
                    offensive=self._parse_faceoff_stat(self._get_text(cells[1])),
                    defensive=self._parse_faceoff_stat(self._get_text(cells[2])),
                    neutral=self._parse_faceoff_stat(self._get_text(cells[3])),
                    total=self._parse_faceoff_stat(self._get_text(cells[4])),
                )
                break  # TOT is the last row for this player

        return player

    def _summary_to_dict(self, summary: ParsedFaceoffSummary) -> dict[str, Any]:
        """Convert ParsedFaceoffSummary to dictionary."""
        return {
            "game_id": summary.game_id,
            "season_id": summary.season_id,
            "teams": {
                "away": self._team_to_dict(summary.away_team),
                "home": self._team_to_dict(summary.home_team),
            },
        }

    def _team_to_dict(self, team: TeamFaceoffSummary) -> dict[str, Any]:
        """Convert TeamFaceoffSummary to dictionary."""
        return {
            "name": team.name,
            "by_period": [
                {
                    "period": p.period,
                    "ev": self._stat_to_dict(p.ev),
                    "pp": self._stat_to_dict(p.pp),
                    "sh": self._stat_to_dict(p.sh),
                    "total": self._stat_to_dict(p.total),
                }
                for p in team.by_period
            ],
            "by_strength": [
                {
                    "strength": s.strength,
                    "zones": self._zones_to_dict(s.zones),
                }
                for s in team.by_strength
            ],
            "totals": self._zones_to_dict(team.totals),
            "players": [self._player_to_dict(p) for p in team.players],
        }

    def _player_to_dict(self, player: PlayerFaceoffStats) -> dict[str, Any]:
        """Convert PlayerFaceoffStats to dictionary."""
        return {
            "number": player.number,
            "position": player.position,
            "name": player.name,
            "by_strength": [
                {
                    "strength": s.strength,
                    "zones": self._zones_to_dict(s.zones),
                }
                for s in player.by_strength
            ],
            "totals": self._zones_to_dict(player.totals),
        }

    def _zones_to_dict(self, zones: ZoneFaceoffs) -> dict[str, Any]:
        """Convert ZoneFaceoffs to dictionary."""
        return {
            "offensive": self._stat_to_dict(zones.offensive),
            "defensive": self._stat_to_dict(zones.defensive),
            "neutral": self._stat_to_dict(zones.neutral),
            "total": self._stat_to_dict(zones.total),
        }

    def _stat_to_dict(self, stat: FaceoffStat) -> dict[str, Any]:
        """Convert FaceoffStat to dictionary."""
        return {
            "won": stat.won,
            "lost": stat.lost,
            "total": stat.total,
            "pct": stat.pct,
        }
