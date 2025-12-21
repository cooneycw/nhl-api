"""NHL Play-by-Play (PL) HTML Downloader.

Downloads and parses Play-by-Play HTML reports from the NHL website.
These reports contain event-level data for every play in a game.

URL Pattern: https://www.nhl.com/scores/htmlreports/{season}/PL{game_suffix}.HTM

Example usage:
    config = HTMLDownloaderConfig()
    async with PlayByPlayDownloader(config) as downloader:
        result = await downloader.download_game(2024020500)
        events = result.data["events"]
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

# Event type codes in NHL HTML reports
EVENT_TYPES = frozenset(
    {
        "PGSTR",  # Pre-game start
        "PGEND",  # Pre-game end
        "ANTHEM",  # National anthem
        "PSTR",  # Period start
        "PEND",  # Period end
        "FAC",  # Faceoff
        "SHOT",  # Shot on goal
        "GOAL",  # Goal scored
        "MISS",  # Missed shot
        "BLOCK",  # Blocked shot
        "HIT",  # Hit
        "GIVE",  # Giveaway
        "TAKE",  # Takeaway
        "PENL",  # Penalty
        "STOP",  # Stoppage
        "GEND",  # Game end
        "SOC",  # Shootout complete
        "EISTR",  # Early intermission start
        "EIEND",  # Early intermission end
        "EGPID",  # Emergency goalie pulled
        "CHL",  # Challenge
        "DELPEN",  # Delayed penalty
    }
)

# Pattern for player info in descriptions: "#37 SVECHNIKOV" or "#37 SVECHNIKOV(12)"
PLAYER_DESC_PATTERN = re.compile(
    r"#(\d+)\s+([A-Z][A-Z.\s'-]+?)(?:\((\d+)\))?(?=,|$|\s)"
)

# Pattern for zone: "Off. Zone", "Def. Zone", "Neu. Zone"
ZONE_PATTERN = re.compile(r"(Off\.|Def\.|Neu\.)\s*Zone", re.IGNORECASE)

# Pattern for shot distance: "6 ft."
DISTANCE_PATTERN = re.compile(r"(\d+)\s*ft\.?", re.IGNORECASE)

# Pattern for shot type: "Wrist", "Snap", "Slap", "Backhand", "Tip-In", "Wrap-around"
SHOT_TYPE_PATTERN = re.compile(
    r"(Wrist|Snap|Slap|Backhand|Tip-In|Wrap-around|Deflected|Poke)", re.IGNORECASE
)

# Pattern for faceoff: "CAR won Neu. Zone - NYI #14 HORVAT vs CAR #82 KOTKANIEMI"
FACEOFF_PATTERN = re.compile(
    r"(\w+)\s+won\s+(Off\.|Def\.|Neu\.)\s*Zone\s*-\s*"
    r"(\w+)\s+#(\d+)\s+([A-Z.\s'-]+?)\s+vs\s+"
    r"(\w+)\s+#(\d+)\s+([A-Z.\s'-]+)",
    re.IGNORECASE,
)

# Pattern for penalty: "NYI #28 ROMANOV High-sticking(2 min)"
PENALTY_PATTERN = re.compile(
    r"(\w+)\s+#(\d+)\s+([A-Z.\s'-]+?)\s+(.+?)\((\d+)\s*min\)",
    re.IGNORECASE,
)

# Pattern for "Drawn By": "Drawn By: CAR #50 ROBINSON"
DRAWN_BY_PATTERN = re.compile(
    r"Drawn\s+By:\s*(\w+)\s+#(\d+)\s+([A-Z.\s'-]+)",
    re.IGNORECASE,
)

# Pattern for assists: "Assists: #20 AHO(24); #4 GOSTISBEHERE(20)"
ASSISTS_PATTERN = re.compile(
    r"Assists?:\s*(.+)",
    re.IGNORECASE,
)

# Pattern for individual assist: "#20 AHO(24)"
ASSIST_PLAYER_PATTERN = re.compile(r"#(\d+)\s+([A-Z][A-Z.\s'-]*)(?:\((\d+)\))?")


@dataclass
class PlayerOnIce:
    """Player on ice information."""

    number: int
    position: str
    name: str = ""


@dataclass
class EventPlayer:
    """Player involved in an event."""

    number: int
    name: str
    team: str = ""
    role: str = ""  # scorer, assist1, assist2, winner, loser, etc.
    stat: int | None = None  # season total for goals/assists


@dataclass
class PlayByPlayEvent:
    """Single play-by-play event."""

    event_number: int
    period: int
    strength: str  # EV, PP, SH, or empty
    time_elapsed: str  # "MM:SS" elapsed in period
    time_remaining: str  # "MM:SS" remaining in period
    event_type: str  # FACEOFF, SHOT, GOAL, etc.
    description: str
    team: str | None = None  # Team code for team-specific events
    zone: str | None = None  # Off, Def, Neu
    shot_type: str | None = None  # Wrist, Snap, Slap, etc.
    distance: int | None = None  # Distance in feet
    players: list[EventPlayer] = field(default_factory=list)
    away_on_ice: list[PlayerOnIce] = field(default_factory=list)
    home_on_ice: list[PlayerOnIce] = field(default_factory=list)


@dataclass
class ParsedPlayByPlay:
    """Complete parsed play-by-play data."""

    game_id: int
    season_id: int
    away_team: str
    home_team: str
    events: list[PlayByPlayEvent] = field(default_factory=list)


class PlayByPlayDownloader(BaseHTMLDownloader):
    """Downloads and parses NHL Play-by-Play HTML reports.

    The Play-by-Play report contains:
    - Every event in the game (faceoffs, shots, goals, hits, etc.)
    - Players on ice for each event
    - Event timing and zone information

    Example:
        config = HTMLDownloaderConfig()
        async with PlayByPlayDownloader(config) as downloader:
            result = await downloader.download_game(2024020500)

            # Access parsed data
            events = result.data["events"]

            # Filter by event type
            goals = [e for e in events if e["event_type"] == "GOAL"]

            # Access raw HTML for reprocessing
            raw_html = result.raw_content
    """

    @property
    def report_type(self) -> str:
        """Return report type code for Play-by-Play."""
        return "PL"

    async def _parse_report(self, soup: BeautifulSoup, game_id: int) -> dict[str, Any]:
        """Parse Play-by-Play HTML into structured data.

        Args:
            soup: Parsed BeautifulSoup document
            game_id: NHL game ID

        Returns:
            Dictionary containing parsed play-by-play data
        """
        season_id = self._extract_season_from_game_id(game_id)

        # Parse team info from header
        away_team, home_team = self._parse_teams(soup)

        # Parse all events
        events = self._parse_events(soup, away_team, home_team)

        # Build result
        result = ParsedPlayByPlay(
            game_id=game_id,
            season_id=season_id,
            away_team=away_team,
            home_team=home_team,
            events=events,
        )

        return self._to_dict(result)

    def _parse_teams(self, soup: BeautifulSoup) -> tuple[str, str]:
        """Parse team abbreviations from header.

        Returns:
            Tuple of (away_team, home_team) abbreviations
        """
        away_team = ""
        home_team = ""

        # Find visitor and home tables
        visitor_table = soup.find("table", id="Visitor")
        home_table = soup.find("table", id="Home")

        if visitor_table:
            img = visitor_table.find("img", alt=True)
            if img and isinstance(img, Tag):
                alt = img.get("alt", "")
                if alt:
                    # Extract abbreviation from full name
                    away_team = self._team_name_to_abbrev(str(alt))

        if home_table:
            img = home_table.find("img", alt=True)
            if img and isinstance(img, Tag):
                alt = img.get("alt", "")
                if alt:
                    home_team = self._team_name_to_abbrev(str(alt))

        return away_team, home_team

    def _team_name_to_abbrev(self, name: str) -> str:
        """Convert team name to 3-letter abbreviation.

        This is a simplified mapping for common teams.
        """
        # Common team name to abbreviation mappings
        mappings = {
            "ANAHEIM DUCKS": "ANA",
            "ARIZONA COYOTES": "ARI",
            "BOSTON BRUINS": "BOS",
            "BUFFALO SABRES": "BUF",
            "CALGARY FLAMES": "CGY",
            "CAROLINA HURRICANES": "CAR",
            "CHICAGO BLACKHAWKS": "CHI",
            "COLORADO AVALANCHE": "COL",
            "COLUMBUS BLUE JACKETS": "CBJ",
            "DALLAS STARS": "DAL",
            "DETROIT RED WINGS": "DET",
            "EDMONTON OILERS": "EDM",
            "FLORIDA PANTHERS": "FLA",
            "LOS ANGELES KINGS": "LAK",
            "MINNESOTA WILD": "MIN",
            "MONTREAL CANADIENS": "MTL",
            "NASHVILLE PREDATORS": "NSH",
            "NEW JERSEY DEVILS": "NJD",
            "NEW YORK ISLANDERS": "NYI",
            "NEW YORK RANGERS": "NYR",
            "OTTAWA SENATORS": "OTT",
            "PHILADELPHIA FLYERS": "PHI",
            "PITTSBURGH PENGUINS": "PIT",
            "SAN JOSE SHARKS": "SJS",
            "SEATTLE KRAKEN": "SEA",
            "ST. LOUIS BLUES": "STL",
            "TAMPA BAY LIGHTNING": "TBL",
            "TORONTO MAPLE LEAFS": "TOR",
            "UTAH HOCKEY CLUB": "UTA",
            "VANCOUVER CANUCKS": "VAN",
            "VEGAS GOLDEN KNIGHTS": "VGK",
            "WASHINGTON CAPITALS": "WSH",
            "WINNIPEG JETS": "WPG",
        }
        return mappings.get(name.upper().strip(), name[:3].upper())

    def _parse_events(
        self, soup: BeautifulSoup, away_team: str, home_team: str
    ) -> list[PlayByPlayEvent]:
        """Parse all event rows from the play-by-play table.

        Args:
            soup: BeautifulSoup document
            away_team: Away team abbreviation
            home_team: Home team abbreviation

        Returns:
            List of PlayByPlayEvent objects
        """
        events: list[PlayByPlayEvent] = []

        # Find all event rows (have id like "PL-1", "PL-2", etc.)
        for row in soup.find_all("tr", id=lambda x: x and x.startswith("PL-")):
            try:
                event = self._parse_event_row(row, away_team, home_team)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug("Failed to parse event row: %s", e)
                continue

        return events

    def _parse_event_row(
        self, row: Tag, away_team: str, home_team: str
    ) -> PlayByPlayEvent | None:
        """Parse a single event row.

        Args:
            row: Table row element
            away_team: Away team abbreviation
            home_team: Home team abbreviation

        Returns:
            PlayByPlayEvent or None if row is invalid
        """
        cells = row.find_all("td")
        if len(cells) < 6:
            return None

        # Extract basic event info
        event_number = self._safe_int(self._get_text(cells[0]))
        if event_number is None:
            return None

        period = self._safe_int(self._get_text(cells[1]), 0) or 0
        strength = self._get_text(cells[2])

        # Parse time - format is "elapsed\nremaining" or "elapsed<br>remaining"
        time_cell = cells[3]
        time_text = self._get_text(time_cell)
        # Handle br tags
        for br in time_cell.find_all("br"):
            br.replace_with("\n")
        time_text = time_cell.get_text(strip=True)

        time_parts = time_text.split()
        time_elapsed = time_parts[0] if time_parts else "0:00"
        time_remaining = time_parts[1] if len(time_parts) > 1 else "0:00"

        event_type = self._get_text(cells[4]).upper()
        description = self._get_text(cells[5])

        # Parse players on ice
        away_on_ice: list[PlayerOnIce] = []
        home_on_ice: list[PlayerOnIce] = []

        if len(cells) > 6:
            away_on_ice = self._parse_players_on_ice(cells[6])
        if len(cells) > 7:
            home_on_ice = self._parse_players_on_ice(cells[7])

        # Parse event-specific details
        team: str | None = None
        zone: str | None = None
        shot_type: str | None = None
        distance: int | None = None
        players: list[EventPlayer] = []

        # Extract zone
        zone_match = ZONE_PATTERN.search(description)
        if zone_match:
            zone_text = zone_match.group(1).lower()
            if "off" in zone_text:
                zone = "Off"
            elif "def" in zone_text:
                zone = "Def"
            elif "neu" in zone_text:
                zone = "Neu"

        # Extract shot type
        shot_match = SHOT_TYPE_PATTERN.search(description)
        if shot_match:
            shot_type = shot_match.group(1).title()

        # Extract distance
        dist_match = DISTANCE_PATTERN.search(description)
        if dist_match:
            distance = self._safe_int(dist_match.group(1))

        # Parse event-type specific details
        if event_type == "FAC":
            team, players = self._parse_faceoff(description)
        elif event_type == "GOAL":
            team, players = self._parse_goal(description)
        elif event_type in ("SHOT", "MISS"):
            team, players = self._parse_shot(description)
        elif event_type == "BLOCK":
            team, players = self._parse_block(description)
        elif event_type == "HIT":
            team, players = self._parse_hit(description)
        elif event_type in ("GIVE", "TAKE"):
            team, players = self._parse_giveaway_takeaway(description, event_type)
        elif event_type == "PENL":
            team, players = self._parse_penalty(description)

        return PlayByPlayEvent(
            event_number=event_number,
            period=period,
            strength=strength,
            time_elapsed=time_elapsed,
            time_remaining=time_remaining,
            event_type=event_type,
            description=description,
            team=team,
            zone=zone,
            shot_type=shot_type,
            distance=distance,
            players=players,
            away_on_ice=away_on_ice,
            home_on_ice=home_on_ice,
        )

    def _parse_players_on_ice(self, cell: Tag) -> list[PlayerOnIce]:
        """Parse players on ice from a table cell.

        Players are in nested tables with <font> tags containing
        player number and title with position and name.
        """
        players: list[PlayerOnIce] = []

        # Find all font tags with title attribute
        for font in cell.find_all("font", title=True):
            number_text = self._get_text(font)
            number = self._safe_int(number_text)
            if number is None:
                continue

            title = str(font.get("title", ""))
            # Title format: "Center - BO HORVAT" or "Defense - ADAM PELECH"
            position = ""
            name = ""
            if " - " in title:
                pos_part, name = title.split(" - ", 1)
                # Map position names to codes
                pos_lower = pos_part.lower()
                if "center" in pos_lower:
                    position = "C"
                elif "right" in pos_lower:
                    position = "R"
                elif "left" in pos_lower:
                    position = "L"
                elif "defense" in pos_lower:
                    position = "D"
                elif "goalie" in pos_lower:
                    position = "G"
                else:
                    position = pos_part[:1].upper()

            players.append(PlayerOnIce(number=number, position=position, name=name))

        return players

    def _parse_faceoff(self, description: str) -> tuple[str | None, list[EventPlayer]]:
        """Parse faceoff description.

        Format: "CAR won Neu. Zone - NYI #14 HORVAT vs CAR #82 KOTKANIEMI"
        """
        players: list[EventPlayer] = []
        winning_team: str | None = None

        match = FACEOFF_PATTERN.search(description)
        if match:
            winning_team = match.group(1).upper()
            # loser_team = match.group(3).upper()
            loser_number = int(match.group(4))
            loser_name = match.group(5).strip()
            winner_team = match.group(6).upper()
            winner_number = int(match.group(7))
            winner_name = match.group(8).strip()

            players.append(
                EventPlayer(
                    number=winner_number,
                    name=winner_name,
                    team=winner_team,
                    role="winner",
                )
            )
            players.append(
                EventPlayer(
                    number=loser_number,
                    name=loser_name,
                    team=match.group(3).upper(),
                    role="loser",
                )
            )

        return winning_team, players

    def _parse_goal(self, description: str) -> tuple[str | None, list[EventPlayer]]:
        """Parse goal description.

        Format: "CAR #37 SVECHNIKOV(12), Wrist , Off. Zone, 6 ft.
                 Assists: #20 AHO(24); #4 GOSTISBEHERE(20)"
        """
        players: list[EventPlayer] = []
        team: str | None = None

        # Split description to get scorer and assists separately
        lines = description.replace("<br>", "\n").split("\n")
        scorer_line = lines[0] if lines else description

        # Parse scorer: "CAR #37 SVECHNIKOV(12)"
        scorer_match = re.match(
            r"(\w+)\s+#(\d+)\s+([A-Z.\s'-]+?)(?:\((\d+)\))?(?:,|$)",
            scorer_line.strip(),
        )
        if scorer_match:
            team = scorer_match.group(1).upper()
            players.append(
                EventPlayer(
                    number=int(scorer_match.group(2)),
                    name=scorer_match.group(3).strip(),
                    team=team,
                    role="scorer",
                    stat=self._safe_int(scorer_match.group(4)),
                )
            )

        # Parse assists
        assists_match = ASSISTS_PATTERN.search(description)
        if assists_match:
            assists_text = assists_match.group(1)
            # Split on semicolon or comma
            assist_parts = re.split(r"[;,]", assists_text)
            for i, part in enumerate(assist_parts[:2]):  # Max 2 assists
                assist_match = ASSIST_PLAYER_PATTERN.search(part)
                if assist_match:
                    players.append(
                        EventPlayer(
                            number=int(assist_match.group(1)),
                            name=assist_match.group(2).strip(),
                            team=team or "",
                            role=f"assist{i + 1}",
                            stat=self._safe_int(assist_match.group(3)),
                        )
                    )

        return team, players

    def _parse_shot(self, description: str) -> tuple[str | None, list[EventPlayer]]:
        """Parse shot/miss description.

        Format: "CAR ONGOAL - #48 MARTINOOK, Backhand , Off. Zone, 23 ft."
        or: "NYI #14 HORVAT, Wrist, Wide of Net, Off. Zone, 43 ft."
        """
        players: list[EventPlayer] = []
        team: str | None = None

        # Try ONGOAL format first
        ongoal_match = re.match(
            r"(\w+)\s+ONGOAL\s*-\s*#(\d+)\s+([A-Z.\s'-]+?)(?:,|$)",
            description.strip(),
        )
        if ongoal_match:
            team = ongoal_match.group(1).upper()
            players.append(
                EventPlayer(
                    number=int(ongoal_match.group(2)),
                    name=ongoal_match.group(3).strip(),
                    team=team,
                    role="shooter",
                )
            )
        else:
            # Try regular shot format
            shot_match = re.match(
                r"(\w+)\s+#(\d+)\s+([A-Z.\s'-]+?)(?:,|$)",
                description.strip(),
            )
            if shot_match:
                team = shot_match.group(1).upper()
                players.append(
                    EventPlayer(
                        number=int(shot_match.group(2)),
                        name=shot_match.group(3).strip(),
                        team=team,
                        role="shooter",
                    )
                )

        return team, players

    def _parse_block(self, description: str) -> tuple[str | None, list[EventPlayer]]:
        """Parse blocked shot description.

        Format: "NYI #7 TSYPLAKOV BLOCKED BY CAR #82 KOTKANIEMI, Wrist, Def. Zone"
        or: "NYI #8 DOBSON BLOCKED BY TEAMMATE, Snap, Def. Zone"
        """
        players: list[EventPlayer] = []
        team: str | None = None

        # Match shooter
        shooter_match = re.match(
            r"(\w+)\s+#(\d+)\s+([A-Z.\s'-]+?)\s+(?:OPPONENT-)?BLOCKED",
            description.strip(),
            re.IGNORECASE,
        )
        if shooter_match:
            team = shooter_match.group(1).upper()
            players.append(
                EventPlayer(
                    number=int(shooter_match.group(2)),
                    name=shooter_match.group(3).strip(),
                    team=team,
                    role="shooter",
                )
            )

        # Match blocker
        blocker_match = re.search(
            r"BLOCKED\s+BY\s+(\w+)\s+#(\d+)\s+([A-Z.\s'-]+?)(?:,|$)",
            description,
            re.IGNORECASE,
        )
        if blocker_match:
            players.append(
                EventPlayer(
                    number=int(blocker_match.group(2)),
                    name=blocker_match.group(3).strip(),
                    team=blocker_match.group(1).upper(),
                    role="blocker",
                )
            )

        return team, players

    def _parse_hit(self, description: str) -> tuple[str | None, list[EventPlayer]]:
        """Parse hit description.

        Format: "CAR #37 SVECHNIKOV HIT NYI #8 DOBSON, Neu. Zone"
        """
        players: list[EventPlayer] = []
        team: str | None = None

        hit_match = re.match(
            r"(\w+)\s+#(\d+)\s+([A-Z.\s'-]+?)\s+HIT\s+(\w+)\s+#(\d+)\s+([A-Z.\s'-]+?)(?:,|$)",
            description.strip(),
            re.IGNORECASE,
        )
        if hit_match:
            team = hit_match.group(1).upper()
            players.append(
                EventPlayer(
                    number=int(hit_match.group(2)),
                    name=hit_match.group(3).strip(),
                    team=team,
                    role="hitter",
                )
            )
            players.append(
                EventPlayer(
                    number=int(hit_match.group(5)),
                    name=hit_match.group(6).strip(),
                    team=hit_match.group(4).upper(),
                    role="hittee",
                )
            )

        return team, players

    def _parse_giveaway_takeaway(
        self, description: str, event_type: str
    ) -> tuple[str | None, list[EventPlayer]]:
        """Parse giveaway/takeaway description.

        Format: "CAR GIVEAWAY - #4 GOSTISBEHERE, Def. Zone"
        or: "CAR TAKEAWAY - #20 AHO, Off. Zone"
        """
        players: list[EventPlayer] = []
        team: str | None = None

        pattern = rf"(\w+)\s+{event_type}AWAY\s*-\s*#(\d+)\s+([A-Z.\s'-]+?)(?:,|$)"
        match = re.match(pattern, description.strip(), re.IGNORECASE)
        if match:
            team = match.group(1).upper()
            role = "giver" if event_type == "GIVE" else "taker"
            players.append(
                EventPlayer(
                    number=int(match.group(2)),
                    name=match.group(3).strip(),
                    team=team,
                    role=role,
                )
            )

        return team, players

    def _parse_penalty(self, description: str) -> tuple[str | None, list[EventPlayer]]:
        """Parse penalty description.

        Format: "NYI #28 ROMANOV High-sticking(2 min), Def. Zone Drawn By: CAR #50 ROBINSON"
        """
        players: list[EventPlayer] = []
        team: str | None = None

        # Parse penalized player
        penalty_match = PENALTY_PATTERN.search(description)
        if penalty_match:
            team = penalty_match.group(1).upper()
            players.append(
                EventPlayer(
                    number=int(penalty_match.group(2)),
                    name=penalty_match.group(3).strip(),
                    team=team,
                    role="penalized",
                )
            )

        # Parse drawn by
        drawn_match = DRAWN_BY_PATTERN.search(description)
        if drawn_match:
            players.append(
                EventPlayer(
                    number=int(drawn_match.group(2)),
                    name=drawn_match.group(3).strip(),
                    team=drawn_match.group(1).upper(),
                    role="drew_penalty",
                )
            )

        return team, players

    def _to_dict(self, result: ParsedPlayByPlay) -> dict[str, Any]:
        """Convert ParsedPlayByPlay to dictionary."""
        return {
            "game_id": result.game_id,
            "season_id": result.season_id,
            "away_team": result.away_team,
            "home_team": result.home_team,
            "events": [
                {
                    "event_number": e.event_number,
                    "period": e.period,
                    "strength": e.strength,
                    "time_elapsed": e.time_elapsed,
                    "time_remaining": e.time_remaining,
                    "event_type": e.event_type,
                    "description": e.description,
                    "team": e.team,
                    "zone": e.zone,
                    "shot_type": e.shot_type,
                    "distance": e.distance,
                    "players": [
                        {
                            "number": p.number,
                            "name": p.name,
                            "team": p.team,
                            "role": p.role,
                            "stat": p.stat,
                        }
                        for p in e.players
                    ],
                    "away_on_ice": [
                        {
                            "number": p.number,
                            "position": p.position,
                            "name": p.name,
                        }
                        for p in e.away_on_ice
                    ],
                    "home_on_ice": [
                        {
                            "number": p.number,
                            "position": p.position,
                            "name": p.name,
                        }
                        for p in e.home_on_ice
                    ],
                }
                for e in result.events
            ],
        }
