"""DailyFaceoff Line Combinations Downloader.

Downloads and parses even-strength line combinations from DailyFaceoff.com,
including forward lines, defensive pairings, and goaltender depth.

URL Pattern: https://www.dailyfaceoff.com/teams/{team-slug}/line-combinations

Example usage:
    config = DailyFaceoffConfig()
    async with LineCombinationsDownloader(config) as downloader:
        result = await downloader.download_team(10)  # Toronto Maple Leafs
        lineup = result.data
        print(f"Line 1 LW: {lineup['forward_lines'][0]['left_wing']}")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
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
class PlayerInfo:
    """Player information from DailyFaceoff.

    Attributes:
        name: Player's full name
        jersey_number: Jersey number (if available)
        injury_status: Injury status (None, "ir", "out", "day-to-day")
        player_id: DailyFaceoff player ID (if available)
    """

    name: str
    jersey_number: int | None = None
    injury_status: str | None = None
    player_id: str | None = None


@dataclass(frozen=True, slots=True)
class ForwardLine:
    """Forward line combination.

    Attributes:
        line_number: Line number (1-4)
        left_wing: Left wing player
        center: Center player
        right_wing: Right wing player
    """

    line_number: int
    left_wing: PlayerInfo
    center: PlayerInfo
    right_wing: PlayerInfo


@dataclass(frozen=True, slots=True)
class DefensivePair:
    """Defensive pairing.

    Attributes:
        pair_number: Pair number (1-3)
        left_defense: Left defenseman
        right_defense: Right defenseman
    """

    pair_number: int
    left_defense: PlayerInfo
    right_defense: PlayerInfo


@dataclass(frozen=True, slots=True)
class GoalieDepth:
    """Goaltender depth chart.

    Attributes:
        starter: Starting goaltender
        backup: Backup goaltender
    """

    starter: PlayerInfo | None
    backup: PlayerInfo | None


@dataclass(slots=True)
class TeamLineup:
    """Complete team lineup from DailyFaceoff.

    Attributes:
        team_id: NHL team ID
        team_abbreviation: Team abbreviation (e.g., "TOR")
        forward_lines: List of 4 forward lines
        defensive_pairs: List of 3 defensive pairs
        goalies: Goaltender depth chart
        fetched_at: When the data was fetched
    """

    team_id: int
    team_abbreviation: str
    forward_lines: list[ForwardLine] = field(default_factory=list)
    defensive_pairs: list[DefensivePair] = field(default_factory=list)
    goalies: GoalieDepth | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# Pattern to extract player ID from URL: /players/news/player-name/12345
PLAYER_ID_PATTERN = re.compile(r"/players/[^/]+/[^/]+/(\d+)")

# Pattern to extract jersey number from alt text or nearby elements
JERSEY_PATTERN = re.compile(r"#(\d+)")


class LineCombinationsDownloader(BaseDailyFaceoffDownloader):
    """Downloads line combinations from DailyFaceoff.

    Parses the line combinations page to extract:
    - 4 forward lines (LW, C, RW)
    - 3 defensive pairings (LD, RD)
    - Goaltender depth (Starter, Backup)

    Example:
        config = DailyFaceoffConfig()
        async with LineCombinationsDownloader(config) as downloader:
            # Download single team
            result = await downloader.download_team(10)  # Toronto

            # Download all teams
            async for result in downloader.download_all_teams():
                print(f"{result.data['team_abbreviation']}: downloaded")
    """

    @property
    def data_type(self) -> str:
        """Return data type identifier."""
        return "line_combinations"

    @property
    def page_path(self) -> str:
        """Return URL path for line combinations page."""
        return "line-combinations"

    async def _parse_page(self, soup: BeautifulSoup, team_id: int) -> dict[str, Any]:
        """Parse line combinations page.

        Args:
            soup: Parsed BeautifulSoup document
            team_id: NHL team ID

        Returns:
            Dictionary containing parsed lineup data
        """
        abbreviation = self._get_team_abbreviation(team_id)

        # Parse forward lines
        forward_lines = self._parse_forward_lines(soup)

        # Parse defensive pairs
        defensive_pairs = self._parse_defensive_pairs(soup)

        # Parse goalies
        goalies = self._parse_goalies(soup)

        lineup = TeamLineup(
            team_id=team_id,
            team_abbreviation=abbreviation,
            forward_lines=forward_lines,
            defensive_pairs=defensive_pairs,
            goalies=goalies,
        )

        return self._to_dict(lineup)

    def _parse_forward_lines(self, soup: BeautifulSoup) -> list[ForwardLine]:
        """Parse forward lines from the page.

        Args:
            soup: BeautifulSoup document

        Returns:
            List of 4 forward lines
        """
        lines: list[ForwardLine] = []

        for line_num in range(1, 5):
            group_id = f"f{line_num}"

            lw = self._find_player_by_position(soup, group_id, "lw")
            c = self._find_player_by_position(soup, group_id, "c")
            rw = self._find_player_by_position(soup, group_id, "rw")

            if lw or c or rw:
                lines.append(
                    ForwardLine(
                        line_number=line_num,
                        left_wing=lw or PlayerInfo(name=""),
                        center=c or PlayerInfo(name=""),
                        right_wing=rw or PlayerInfo(name=""),
                    )
                )

        return lines

    def _parse_defensive_pairs(self, soup: BeautifulSoup) -> list[DefensivePair]:
        """Parse defensive pairings from the page.

        Args:
            soup: BeautifulSoup document

        Returns:
            List of 3 defensive pairs
        """
        pairs: list[DefensivePair] = []

        for pair_num in range(1, 4):
            group_id = f"d{pair_num}"

            ld = self._find_player_by_position(soup, group_id, "ld")
            rd = self._find_player_by_position(soup, group_id, "rd")

            if ld or rd:
                pairs.append(
                    DefensivePair(
                        pair_number=pair_num,
                        left_defense=ld or PlayerInfo(name=""),
                        right_defense=rd or PlayerInfo(name=""),
                    )
                )

        return pairs

    def _parse_goalies(self, soup: BeautifulSoup) -> GoalieDepth:
        """Parse goaltender depth from the page.

        Args:
            soup: BeautifulSoup document

        Returns:
            GoalieDepth with starter and backup
        """
        starter = self._find_player_by_position(soup, "g1", "g")
        backup = self._find_player_by_position(soup, "g2", "g")

        # Alternative: look for "Starting Goalie" and "Backup Goalie" text
        if not starter:
            starter = self._find_goalie_by_role(soup, "starting")
        if not backup:
            backup = self._find_goalie_by_role(soup, "backup")

        return GoalieDepth(starter=starter, backup=backup)

    def _find_player_by_position(
        self, soup: BeautifulSoup, group_id: str, position_id: str
    ) -> PlayerInfo | None:
        """Find a player by group and position identifier.

        DailyFaceoff uses data attributes like:
        - groupIdentifier: "f1", "f2", "d1", "g1", etc.
        - positionIdentifier: "lw", "c", "rw", "ld", "rd", "g"

        Args:
            soup: BeautifulSoup document
            group_id: Group identifier (e.g., "f1" for first forward line)
            position_id: Position identifier (e.g., "lw" for left wing)

        Returns:
            PlayerInfo if found, None otherwise
        """
        # Look for player cards with matching group/position
        # Try multiple selector strategies

        # Strategy 1: Look for elements with data attributes
        player_elem = soup.find(
            attrs={"data-group": group_id, "data-position": position_id}
        )

        # Strategy 2: Look for React-style data in scripts or elements
        if not player_elem:
            # Try finding by class patterns common in DailyFaceoff
            containers = soup.find_all(class_=re.compile(r"player|lineup|card", re.I))
            for container in containers:
                if group_id in str(container) and position_id in str(container):
                    player_elem = container
                    break

        # Strategy 3: Parse from table structure
        if not player_elem:
            player_elem = self._find_player_in_table(soup, group_id, position_id)

        if player_elem:
            return self._extract_player_info(player_elem)

        return None

    def _find_player_in_table(
        self, soup: BeautifulSoup, group_id: str, position_id: str
    ) -> Tag | None:
        """Find player in table-based layout.

        Args:
            soup: BeautifulSoup document
            group_id: Group identifier
            position_id: Position identifier

        Returns:
            Player element if found
        """
        # DailyFaceoff sometimes uses table layouts
        # Look for rows containing both group and position info
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                row_text = str(row).lower()
                # Check if this row matches our criteria
                if self._matches_line_criteria(row_text, group_id, position_id):
                    # Find the player link in this row
                    player_link = row.find("a", href=re.compile(r"/players/"))
                    if player_link:
                        return player_link.parent or player_link

        return None

    def _matches_line_criteria(
        self, text: str, group_id: str, position_id: str
    ) -> bool:
        """Check if text contains indicators for the specified line/position.

        Args:
            text: Text to search
            group_id: Group identifier (e.g., "f1", "d2")
            position_id: Position identifier (e.g., "lw", "c")

        Returns:
            True if text appears to match the criteria
        """
        # Map position IDs to common text representations
        position_names = {
            "lw": ["left wing", "lw", "left-wing"],
            "c": ["center", "c"],
            "rw": ["right wing", "rw", "right-wing"],
            "ld": ["left defense", "ld", "left-defense"],
            "rd": ["right defense", "rd", "right-defense"],
            "g": ["goalie", "goaltender", "g"],
        }

        # Check for group indicator
        group_num = group_id[1] if len(group_id) > 1 else ""
        group_type = group_id[0] if group_id else ""

        has_group = False
        if group_type == "f":
            has_group = f"line {group_num}" in text or f"line{group_num}" in text
        elif group_type == "d":
            has_group = f"pair {group_num}" in text or f"pair{group_num}" in text

        # Check for position
        has_position = any(
            pos_name in text for pos_name in position_names.get(position_id, [])
        )

        return has_group and has_position

    def _find_goalie_by_role(self, soup: BeautifulSoup, role: str) -> PlayerInfo | None:
        """Find goalie by role text (starting/backup).

        Args:
            soup: BeautifulSoup document
            role: "starting" or "backup"

        Returns:
            PlayerInfo if found
        """
        role_patterns = {
            "starting": ["starting goalie", "starter", "#1 goalie"],
            "backup": ["backup goalie", "backup", "#2 goalie"],
        }

        patterns = role_patterns.get(role.lower(), [])

        for pattern in patterns:
            # Find text containing the role
            elem = soup.find(string=re.compile(pattern, re.I))
            if elem:
                # Look for player link nearby
                parent = elem.parent
                if parent:
                    # Check siblings and parent for player info
                    for sibling in parent.find_all_next(limit=5):
                        player_link = sibling.find("a", href=re.compile(r"/players/"))
                        if player_link:
                            return self._extract_player_info(
                                player_link.parent or player_link
                            )

        return None

    def _extract_player_info(self, element: Tag) -> PlayerInfo:
        """Extract player information from an HTML element.

        Args:
            element: BeautifulSoup element containing player info

        Returns:
            PlayerInfo dataclass
        """
        name = ""
        jersey_number = None
        injury_status = None
        player_id = None

        # Find player link
        link = element.find("a", href=re.compile(r"/players/"))
        if link:
            name = link.get_text(strip=True)
            href = link.get("href", "")
            if href:
                match = PLAYER_ID_PATTERN.search(str(href))
                if match:
                    player_id = match.group(1)
        else:
            # Try to get name from text content
            name = element.get_text(strip=True)

        # Find jersey number
        element_text = str(element)
        jersey_match = JERSEY_PATTERN.search(element_text)
        if jersey_match:
            jersey_number = int(jersey_match.group(1))

        # Check for injury indicators
        injury_classes = ["injury", "injured", "ir", "out", "day-to-day"]
        for cls in injury_classes:
            if element.find(class_=re.compile(cls, re.I)):
                injury_status = cls
                break

        # Also check data attributes
        injury_attr = element.get("data-injury") or element.get("data-status")
        if injury_attr:
            injury_status = str(injury_attr)

        return PlayerInfo(
            name=name,
            jersey_number=jersey_number,
            injury_status=injury_status,
            player_id=player_id,
        )

    def _to_dict(self, lineup: TeamLineup) -> dict[str, Any]:
        """Convert TeamLineup to dictionary.

        Args:
            lineup: TeamLineup dataclass

        Returns:
            Dictionary representation
        """
        return {
            "team_id": lineup.team_id,
            "team_abbreviation": lineup.team_abbreviation,
            "forward_lines": [
                {
                    "line_number": line.line_number,
                    "left_wing": self._player_to_dict(line.left_wing),
                    "center": self._player_to_dict(line.center),
                    "right_wing": self._player_to_dict(line.right_wing),
                }
                for line in lineup.forward_lines
            ],
            "defensive_pairs": [
                {
                    "pair_number": pair.pair_number,
                    "left_defense": self._player_to_dict(pair.left_defense),
                    "right_defense": self._player_to_dict(pair.right_defense),
                }
                for pair in lineup.defensive_pairs
            ],
            "goalies": {
                "starter": self._player_to_dict(lineup.goalies.starter)
                if lineup.goalies and lineup.goalies.starter
                else None,
                "backup": self._player_to_dict(lineup.goalies.backup)
                if lineup.goalies and lineup.goalies.backup
                else None,
            }
            if lineup.goalies
            else None,
            "fetched_at": lineup.fetched_at.isoformat(),
        }

    def _player_to_dict(self, player: PlayerInfo | None) -> dict[str, Any] | None:
        """Convert PlayerInfo to dictionary.

        Args:
            player: PlayerInfo dataclass

        Returns:
            Dictionary representation or None
        """
        if not player or not player.name:
            return None

        return {
            "name": player.name,
            "jersey_number": player.jersey_number,
            "injury_status": player.injury_status,
            "player_id": player.player_id,
        }

    async def persist(
        self,
        db: DatabaseService,
        lineup: dict[str, Any],
        season_id: int,
        snapshot_date: date,
    ) -> int:
        """Persist line combinations to the database.

        Uses upsert (INSERT ... ON CONFLICT) to handle re-downloads gracefully.

        Args:
            db: Database service instance
            lineup: Parsed lineup dictionary from download_team()
            season_id: NHL season ID (e.g., 20242025)
            snapshot_date: Date of the snapshot

        Returns:
            Number of player positions upserted
        """
        count = 0
        team_abbrev = lineup.get("team_abbreviation", "")
        fetched_at = datetime.fromisoformat(
            lineup.get("fetched_at", datetime.now(UTC).isoformat())
        )

        # Helper to insert a player position
        async def insert_player(
            player_dict: dict[str, Any] | None,
            line_type: str,
            unit_number: int,
            position_code: str,
        ) -> bool:
            if not player_dict or not player_dict.get("name"):
                return False

            await db.execute(
                """
                INSERT INTO df_line_combinations (
                    team_abbrev, season_id, snapshot_date, fetched_at,
                    player_name, df_player_id, jersey_number,
                    line_type, unit_number, position_code, injury_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (team_abbrev, snapshot_date, player_name, line_type, unit_number, position_code)
                DO UPDATE SET
                    fetched_at = EXCLUDED.fetched_at,
                    df_player_id = EXCLUDED.df_player_id,
                    jersey_number = EXCLUDED.jersey_number,
                    injury_status = EXCLUDED.injury_status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                team_abbrev,
                season_id,
                snapshot_date,
                fetched_at,
                player_dict.get("name"),
                player_dict.get("player_id"),
                player_dict.get("jersey_number"),
                line_type,
                unit_number,
                position_code,
                player_dict.get("injury_status"),
            )
            return True

        # Insert forward lines
        for line in lineup.get("forward_lines", []):
            line_num = line.get("line_number", 0)
            if await insert_player(line.get("left_wing"), "forward", line_num, "lw"):
                count += 1
            if await insert_player(line.get("center"), "forward", line_num, "c"):
                count += 1
            if await insert_player(line.get("right_wing"), "forward", line_num, "rw"):
                count += 1

        # Insert defensive pairs
        for pair in lineup.get("defensive_pairs", []):
            pair_num = pair.get("pair_number", 0)
            if await insert_player(pair.get("left_defense"), "defense", pair_num, "ld"):
                count += 1
            if await insert_player(
                pair.get("right_defense"), "defense", pair_num, "rd"
            ):
                count += 1

        # Insert goalies
        goalies = lineup.get("goalies")
        if goalies:
            if await insert_player(goalies.get("starter"), "goalie", 1, "g"):
                count += 1
            if await insert_player(goalies.get("backup"), "goalie", 2, "g"):
                count += 1

        logger.debug(
            "Persisted %d player positions for %s on %s",
            count,
            team_abbrev,
            snapshot_date,
        )
        return count
