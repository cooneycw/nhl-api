"""DailyFaceoff Penalty Kill Units Downloader.

Downloads and parses penalty kill unit configurations from DailyFaceoff.com,
including PK1 and PK2 units with their forward and defenseman assignments.

URL Pattern: https://www.dailyfaceoff.com/teams/{team-slug}/line-combinations

The penalty kill data is on the same page as line combinations, extracted from
the data-group="pk1" and data-group="pk2" sections.

Example usage:
    config = DailyFaceoffConfig()
    async with PenaltyKillDownloader(config) as downloader:
        result = await downloader.download_team(10)  # Toronto Maple Leafs
        pk_data = result.data
        print(f"PK1 Forwards: {pk_data['pk1']['forwards']}")
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader import (
    BaseDailyFaceoffDownloader,
)

if TYPE_CHECKING:
    from datetime import date

    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PKPlayer:
    """Player in a penalty kill unit.

    Attributes:
        name: Player's full name
        jersey_number: Jersey number (if available)
        position: Player position (F for forward, D for defenseman)
        player_id: DailyFaceoff player ID (if available)
    """

    name: str
    jersey_number: int | None = None
    position: str | None = None
    player_id: str | None = None


@dataclass(frozen=True, slots=True)
class PenaltyKillUnit:
    """A single penalty kill unit (PK1 or PK2).

    Attributes:
        unit_number: Unit number (1 or 2)
        forwards: List of forwards on this PK unit (typically 2)
        defensemen: List of defensemen on this PK unit (typically 2)
    """

    unit_number: int
    forwards: tuple[PKPlayer, ...]
    defensemen: tuple[PKPlayer, ...]


@dataclass(frozen=True, slots=True)
class TeamPenaltyKill:
    """Complete penalty kill configuration for a team.

    Attributes:
        team_id: NHL team ID
        team_abbreviation: Team abbreviation (e.g., "TOR")
        pk1: First penalty kill unit
        pk2: Second penalty kill unit
        fetched_at: When the data was fetched
    """

    team_id: int
    team_abbreviation: str
    pk1: PenaltyKillUnit | None
    pk2: PenaltyKillUnit | None
    fetched_at: datetime


# Pattern to extract player ID from URL
PLAYER_ID_PATTERN = re.compile(r"/players/[^/]+/[^/]+/(\d+)")

# Pattern to extract jersey number
JERSEY_PATTERN = re.compile(r"#(\d+)")


class PenaltyKillDownloader(BaseDailyFaceoffDownloader):
    """Downloads penalty kill unit configurations from DailyFaceoff.

    Parses the line combinations page to extract:
    - PK1: First penalty kill unit (2F + 2D)
    - PK2: Second penalty kill unit (2F + 2D)

    Example:
        config = DailyFaceoffConfig()
        async with PenaltyKillDownloader(config) as downloader:
            # Download single team
            result = await downloader.download_team(10)  # Toronto

            # Download all teams
            async for result in downloader.download_all_teams():
                print(f"{result.data['team_abbreviation']}: downloaded")
    """

    @property
    def data_type(self) -> str:
        """Return data type identifier."""
        return "penalty_kill"

    @property
    def page_path(self) -> str:
        """Return URL path for line combinations page.

        PK data is on the same page as line combinations.
        """
        return "line-combinations"

    async def _parse_page(self, soup: BeautifulSoup, team_id: int) -> dict[str, Any]:
        """Parse penalty kill units from the line combinations page.

        Args:
            soup: Parsed BeautifulSoup document
            team_id: NHL team ID

        Returns:
            Dictionary containing parsed PK data
        """
        abbreviation = self._get_team_abbreviation(team_id)

        # Parse PK units from embedded JSON data or HTML structure
        pk1 = self._parse_pk_unit(soup, 1)
        pk2 = self._parse_pk_unit(soup, 2)

        result = TeamPenaltyKill(
            team_id=team_id,
            team_abbreviation=abbreviation,
            pk1=pk1,
            pk2=pk2,
            fetched_at=datetime.now(UTC),
        )

        return self._to_dict(result)

    def _parse_pk_unit(
        self, soup: BeautifulSoup, unit_number: int
    ) -> PenaltyKillUnit | None:
        """Parse a single penalty kill unit.

        Args:
            soup: BeautifulSoup document
            unit_number: Unit number (1 or 2)

        Returns:
            PenaltyKillUnit or None if not found
        """
        group_id = f"pk{unit_number}"

        # Strategy 1: Look for embedded JSON data in script tags
        players = self._parse_from_json(soup, group_id)

        # Strategy 2: Look for data attributes in HTML
        if not players:
            players = self._parse_from_html_data(soup, group_id)

        # Strategy 3: Look for table/div structure
        if not players:
            players = self._parse_from_structure(soup, group_id)

        if not players:
            logger.warning("Could not find PK%d unit data", unit_number)
            return None

        # Separate forwards and defensemen
        forwards = [p for p in players if self._is_forward(p)]
        defensemen = [p for p in players if self._is_defenseman(p)]

        return PenaltyKillUnit(
            unit_number=unit_number,
            forwards=tuple(forwards),
            defensemen=tuple(defensemen),
        )

    def _parse_from_json(self, soup: BeautifulSoup, group_id: str) -> list[PKPlayer]:
        """Parse PK data from embedded JSON in script tags.

        DailyFaceoff often includes player data in __NEXT_DATA__ or similar.

        Args:
            soup: BeautifulSoup document
            group_id: Group identifier (e.g., "pk1")

        Returns:
            List of PKPlayer objects
        """
        players: list[PKPlayer] = []

        # Look for Next.js data
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            try:
                data = json.loads(script.string)
                players = self._extract_pk_from_next_data(data, group_id)
                if players:
                    return players
            except (json.JSONDecodeError, KeyError):
                pass

        # Look for other JSON-like script content
        for script in soup.find_all("script"):
            if not script.string:
                continue

            # Search for groupIdentifier pattern
            if f'"groupIdentifier":"{group_id}"' in script.string:
                players = self._extract_players_from_script(script.string, group_id)
                if players:
                    return players

        return players

    def _extract_pk_from_next_data(
        self, data: dict[str, Any], group_id: str
    ) -> list[PKPlayer]:
        """Extract PK players from Next.js data structure.

        Args:
            data: Parsed __NEXT_DATA__ JSON
            group_id: Group identifier

        Returns:
            List of PKPlayer objects
        """
        players: list[PKPlayer] = []

        # Navigate the nested structure - this varies by page
        try:
            props = data.get("props", {})
            page_props = props.get("pageProps", {})

            # Look for lineup or formations data
            for key in ["lineup", "formations", "penaltyKill", "specialTeams"]:
                if key in page_props:
                    section = page_props[key]
                    players = self._search_for_group(section, group_id)
                    if players:
                        return players

            # Deep search for the group
            players = self._deep_search_group(page_props, group_id)

        except (KeyError, TypeError, AttributeError) as e:
            logger.debug("Error extracting from Next.js data: %s", e)

        return players

    def _search_for_group(self, data: Any, group_id: str) -> list[PKPlayer]:
        """Search for a specific group in data structure.

        Args:
            data: Data structure to search
            group_id: Group identifier to find

        Returns:
            List of PKPlayer objects
        """
        players: list[PKPlayer] = []

        if isinstance(data, dict):
            if data.get("groupIdentifier") == group_id:
                # Found the group, extract players
                return self._extract_players_from_group(data)

            for value in data.values():
                result = self._search_for_group(value, group_id)
                if result:
                    return result

        elif isinstance(data, list):
            for item in data:
                result = self._search_for_group(item, group_id)
                if result:
                    return result

        return players

    def _deep_search_group(
        self, data: Any, group_id: str, max_depth: int = 10
    ) -> list[PKPlayer]:
        """Deep search for group data in nested structure.

        Args:
            data: Data structure to search
            group_id: Group identifier
            max_depth: Maximum recursion depth

        Returns:
            List of PKPlayer objects
        """
        if max_depth <= 0:
            return []

        if isinstance(data, dict):
            # Check if this dict has the groupIdentifier
            if data.get("groupIdentifier") == group_id:
                return self._extract_players_from_group(data)

            # Recurse into values
            for value in data.values():
                result = self._deep_search_group(value, group_id, max_depth - 1)
                if result:
                    return result

        elif isinstance(data, list):
            for item in data:
                result = self._deep_search_group(item, group_id, max_depth - 1)
                if result:
                    return result

        return []

    def _extract_players_from_group(self, group: dict[str, Any]) -> list[PKPlayer]:
        """Extract players from a group dictionary.

        Args:
            group: Group data containing players

        Returns:
            List of PKPlayer objects
        """
        players: list[PKPlayer] = []

        # Look for players in various possible structures
        player_data = group.get("players", [])
        if not player_data:
            player_data = group.get("skaters", [])
        if not player_data:
            # Try looking at position slots
            for key in ["sk1", "sk2", "sk3", "sk4"]:
                if key in group:
                    player_data.append(group[key])

        for p in player_data:
            if isinstance(p, dict):
                player = self._dict_to_player(p)
                if player:
                    players.append(player)

        return players

    def _dict_to_player(self, p: dict[str, Any]) -> PKPlayer | None:
        """Convert player dictionary to PKPlayer.

        Args:
            p: Player data dictionary

        Returns:
            PKPlayer or None
        """
        name = p.get("name") or p.get("playerName") or p.get("fullName", "")
        if not name:
            return None

        jersey = p.get("jerseyNumber") or p.get("number")
        if isinstance(jersey, str) and jersey.isdigit():
            jersey = int(jersey)

        position = p.get("position") or p.get("positionCode")
        player_id = p.get("playerId") or p.get("id")
        if player_id:
            player_id = str(player_id)

        return PKPlayer(
            name=name,
            jersey_number=jersey if isinstance(jersey, int) else None,
            position=position,
            player_id=player_id,
        )

    def _extract_players_from_script(
        self, script_content: str, group_id: str
    ) -> list[PKPlayer]:
        """Extract players from inline script content.

        Args:
            script_content: Script text content
            group_id: Group identifier

        Returns:
            List of PKPlayer objects
        """
        players: list[PKPlayer] = []

        # Find the section containing our group
        pattern = rf'"groupIdentifier"\s*:\s*"{group_id}"[^}}]*'
        match = re.search(pattern, script_content)
        if not match:
            return players

        # Find the containing object - look for player names nearby
        start_pos = match.start()

        # Look backwards for object start
        brace_count = 0
        obj_start = start_pos
        for i in range(start_pos, max(0, start_pos - 5000), -1):
            if script_content[i] == "}":
                brace_count += 1
            elif script_content[i] == "{":
                if brace_count == 0:
                    obj_start = i
                    break
                brace_count -= 1

        # Look forwards for object end
        brace_count = 0
        obj_end = start_pos
        for i in range(start_pos, min(len(script_content), start_pos + 5000)):
            if script_content[i] == "{":
                brace_count += 1
            elif script_content[i] == "}":
                if brace_count == 0:
                    obj_end = i + 1
                    break
                brace_count -= 1

        # Try to parse this section as JSON
        section = script_content[obj_start:obj_end]
        try:
            data = json.loads(section)
            players = self._extract_players_from_group(data)
        except json.JSONDecodeError:
            # Fallback: extract player names with regex
            players = self._extract_names_from_text(section)

        return players

    def _extract_names_from_text(self, text: str) -> list[PKPlayer]:
        """Extract player names from text using regex patterns.

        Args:
            text: Text containing player data

        Returns:
            List of PKPlayer objects with names only
        """
        players: list[PKPlayer] = []

        # Look for playerName or name patterns
        name_pattern = r'"(?:playerName|name|fullName)"\s*:\s*"([^"]+)"'
        for match in re.finditer(name_pattern, text):
            name = match.group(1)
            if name and len(name) > 2:
                players.append(PKPlayer(name=name))

        return players

    def _parse_from_html_data(
        self, soup: BeautifulSoup, group_id: str
    ) -> list[PKPlayer]:
        """Parse PK data from HTML data attributes.

        Args:
            soup: BeautifulSoup document
            group_id: Group identifier

        Returns:
            List of PKPlayer objects
        """
        players: list[PKPlayer] = []

        # Look for elements with data-group or similar attributes
        containers = soup.find_all(attrs={"data-group": group_id})

        for container in containers:
            # Look for player links within this container
            links = container.find_all("a", href=re.compile(r"/players/"))
            for link in links:
                player = self._extract_player_from_element(link)
                if player:
                    players.append(player)

            # If no links found, try the container itself
            if not players:
                player = self._extract_player_from_element(container)
                if player:
                    players.append(player)

        # Also try data-groupidentifier
        if not players:
            containers = soup.find_all(attrs={"data-groupidentifier": group_id})
            for container in containers:
                # Look for player links within
                links = container.find_all("a", href=re.compile(r"/players/"))
                for link in links:
                    player = self._extract_player_from_element(link)
                    if player:
                        players.append(player)

        return players

    def _parse_from_structure(
        self, soup: BeautifulSoup, group_id: str
    ) -> list[PKPlayer]:
        """Parse PK data from page structure (sections, divs, etc.).

        Args:
            soup: BeautifulSoup document
            group_id: Group identifier

        Returns:
            List of PKPlayer objects
        """
        players: list[PKPlayer] = []

        # Map group_id to display text patterns
        unit_num = group_id[-1]  # "pk1" -> "1"
        patterns = [
            f"{unit_num}st penalty kill",
            f"{unit_num}nd penalty kill",
            f"pk{unit_num}",
            f"penalty kill {unit_num}",
            f"pk unit {unit_num}",
        ]

        # Find section headers or labels
        for pattern in patterns:
            header = soup.find(string=re.compile(pattern, re.I))
            if header:
                # Look for player links in the containing section
                parent = header.find_parent(["div", "section", "table", "tr"])
                if parent:
                    players = self._extract_players_from_section(parent)
                    if players:
                        return players

        return players

    def _extract_players_from_section(self, section: Tag) -> list[PKPlayer]:
        """Extract players from an HTML section.

        Args:
            section: BeautifulSoup Tag representing a section

        Returns:
            List of PKPlayer objects
        """
        players: list[PKPlayer] = []

        # Find all player links
        links = section.find_all("a", href=re.compile(r"/players/"))

        for link in links:
            player = self._extract_player_from_element(link)
            if player:
                players.append(player)

        return players

    def _extract_player_from_element(self, element: Tag) -> PKPlayer | None:
        """Extract player info from an HTML element.

        Args:
            element: BeautifulSoup element

        Returns:
            PKPlayer or None
        """
        name = ""
        jersey_number = None
        position = None
        player_id = None

        # Get name from link text or data attribute
        if isinstance(element, Tag):
            link = element if element.name == "a" else element.find("a")
            if link:
                name = link.get_text(strip=True)
                href = link.get("href", "")
                if href:
                    match = PLAYER_ID_PATTERN.search(str(href))
                    if match:
                        player_id = match.group(1)
            else:
                name = element.get_text(strip=True)

            # Try data attributes
            if not name:
                name = str(element.get("data-name", ""))
            if not player_id:
                player_id = str(element.get("data-player-id", "")) or None

            # Get jersey number
            element_text = str(element)
            jersey_match = JERSEY_PATTERN.search(element_text)
            if jersey_match:
                jersey_number = int(jersey_match.group(1))

            # Get position from data attribute or class
            position = str(element.get("data-position", "")) or None
            if not position:
                class_attr = element.get("class")
                classes: list[str] = list(class_attr) if class_attr else []
                for cls in classes:
                    cls_lower = str(cls).lower()
                    if cls_lower in ("forward", "f", "lw", "c", "rw"):
                        position = "F"
                        break
                    elif cls_lower in ("defense", "d", "ld", "rd"):
                        position = "D"
                        break

        if not name:
            return None

        return PKPlayer(
            name=name,
            jersey_number=jersey_number,
            position=position,
            player_id=player_id,
        )

    def _is_forward(self, player: PKPlayer) -> bool:
        """Check if player is a forward.

        Args:
            player: PKPlayer to check

        Returns:
            True if player appears to be a forward
        """
        if player.position:
            pos_upper = player.position.upper()
            return pos_upper in ("F", "LW", "C", "RW", "CENTER", "FORWARD")
        # Default: if we don't know, assume first 2 are forwards
        return True

    def _is_defenseman(self, player: PKPlayer) -> bool:
        """Check if player is a defenseman.

        Args:
            player: PKPlayer to check

        Returns:
            True if player appears to be a defenseman
        """
        if player.position:
            pos_upper = player.position.upper()
            return pos_upper in ("D", "LD", "RD", "DEFENSE", "DEFENSEMAN")
        return False

    def _to_dict(self, pk: TeamPenaltyKill) -> dict[str, Any]:
        """Convert TeamPenaltyKill to dictionary.

        Args:
            pk: TeamPenaltyKill dataclass

        Returns:
            Dictionary representation
        """
        return {
            "team_id": pk.team_id,
            "team_abbreviation": pk.team_abbreviation,
            "pk1": self._unit_to_dict(pk.pk1) if pk.pk1 else None,
            "pk2": self._unit_to_dict(pk.pk2) if pk.pk2 else None,
            "fetched_at": pk.fetched_at.isoformat(),
        }

    def _unit_to_dict(self, unit: PenaltyKillUnit) -> dict[str, Any]:
        """Convert PenaltyKillUnit to dictionary.

        Args:
            unit: PenaltyKillUnit dataclass

        Returns:
            Dictionary representation
        """
        return {
            "unit_number": unit.unit_number,
            "forwards": [self._player_to_dict(p) for p in unit.forwards],
            "defensemen": [self._player_to_dict(p) for p in unit.defensemen],
        }

    def _player_to_dict(self, player: PKPlayer) -> dict[str, Any]:
        """Convert PKPlayer to dictionary.

        Args:
            player: PKPlayer dataclass

        Returns:
            Dictionary representation
        """
        return {
            "name": player.name,
            "jersey_number": player.jersey_number,
            "position": player.position,
            "player_id": player.player_id,
        }

    async def persist(
        self,
        db: DatabaseService,
        pk_data: dict[str, Any],
        team_abbrev: str,
        season_id: int,
        snapshot_date: date,
    ) -> int:
        """Persist penalty kill units to the database.

        Uses upsert (INSERT ... ON CONFLICT) to handle re-downloads gracefully.

        Args:
            db: Database service instance
            pk_data: Parsed penalty kill dictionary from download_team()
            team_abbrev: Team abbreviation (e.g., "BOS")
            season_id: NHL season ID (e.g., 20242025)
            snapshot_date: Date of the snapshot

        Returns:
            Number of player positions upserted
        """
        count = 0
        fetched_at = datetime.fromisoformat(
            pk_data.get("fetched_at", datetime.now(UTC).isoformat())
        )

        async def insert_unit(unit_data: dict[str, Any] | None) -> int:
            if not unit_data:
                return 0

            unit_num = unit_data.get("unit_number", 0)
            inserted = 0

            # Insert forwards
            for player in unit_data.get("forwards", []):
                if not player.get("name"):
                    continue

                await db.execute(
                    """
                    INSERT INTO df_penalty_kill_units (
                        team_abbrev, season_id, snapshot_date, fetched_at,
                        unit_number, player_name, df_player_id, jersey_number,
                        position_type
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (team_abbrev, snapshot_date, unit_number, player_name)
                    DO UPDATE SET
                        fetched_at = EXCLUDED.fetched_at,
                        df_player_id = EXCLUDED.df_player_id,
                        jersey_number = EXCLUDED.jersey_number,
                        position_type = EXCLUDED.position_type,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    team_abbrev,
                    season_id,
                    snapshot_date,
                    fetched_at,
                    unit_num,
                    player.get("name"),
                    player.get("player_id"),
                    player.get("jersey_number"),
                    "forward",
                )
                inserted += 1

            # Insert defensemen
            for player in unit_data.get("defensemen", []):
                if not player.get("name"):
                    continue

                await db.execute(
                    """
                    INSERT INTO df_penalty_kill_units (
                        team_abbrev, season_id, snapshot_date, fetched_at,
                        unit_number, player_name, df_player_id, jersey_number,
                        position_type
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (team_abbrev, snapshot_date, unit_number, player_name)
                    DO UPDATE SET
                        fetched_at = EXCLUDED.fetched_at,
                        df_player_id = EXCLUDED.df_player_id,
                        jersey_number = EXCLUDED.jersey_number,
                        position_type = EXCLUDED.position_type,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    team_abbrev,
                    season_id,
                    snapshot_date,
                    fetched_at,
                    unit_num,
                    player.get("name"),
                    player.get("player_id"),
                    player.get("jersey_number"),
                    "defense",
                )
                inserted += 1

            return inserted

        # Insert PK1 and PK2
        count += await insert_unit(pk_data.get("pk1"))
        count += await insert_unit(pk_data.get("pk2"))

        logger.debug(
            "Persisted %d penalty kill players for %s on %s",
            count,
            team_abbrev,
            snapshot_date,
        )
        return count
