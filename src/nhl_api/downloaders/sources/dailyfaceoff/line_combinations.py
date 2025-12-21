"""DailyFaceoff Line Combinations Downloader.

This module provides a downloader for extracting even-strength line combinations
(forward lines, defensive pairs, and goalie depth) from DailyFaceoff.com.

Example usage:
    config = DailyFaceoffConfig()
    async with LineCombinationsDownloader(config) as downloader:
        result = await downloader.download_team(6)  # Boston Bruins
        print(result.data["forward_lines"])
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader import (
    BaseDailyFaceoffDownloader,
)

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlayerInfo:
    """Basic player information.

    Attributes:
        player_id: DailyFaceoff player ID
        name: Player's full name
        jersey_number: Player's jersey number
        position: Position identifier (lw, c, rw, ld, rd, g1, g2)
    """

    player_id: int
    name: str
    jersey_number: int
    position: str


@dataclass(frozen=True, slots=True)
class ForwardLine:
    """A forward line with three players.

    Attributes:
        line_number: Line number (1-4)
        left_wing: Left wing player or None if empty
        center: Center player or None if empty
        right_wing: Right wing player or None if empty
    """

    line_number: int
    left_wing: PlayerInfo | None
    center: PlayerInfo | None
    right_wing: PlayerInfo | None


@dataclass(frozen=True, slots=True)
class DefensivePair:
    """A defensive pairing with two players.

    Attributes:
        pair_number: Pair number (1-3)
        left_defense: Left defenseman or None if empty
        right_defense: Right defenseman or None if empty
    """

    pair_number: int
    left_defense: PlayerInfo | None
    right_defense: PlayerInfo | None


@dataclass(frozen=True, slots=True)
class GoalieDepth:
    """Goaltender depth chart.

    Attributes:
        starter: Starting goalie or None if empty
        backup: Backup goalie or None if empty
    """

    starter: PlayerInfo | None
    backup: PlayerInfo | None


@dataclass(frozen=True, slots=True)
class TeamLineup:
    """Complete team lineup configuration.

    Attributes:
        team_id: NHL team ID
        team_abbreviation: Team abbreviation (e.g., "BOS")
        forward_lines: List of 4 forward lines
        defensive_pairs: List of 3 defensive pairs
        goalies: Goalie depth chart
        fetched_at: Timestamp when data was fetched
    """

    team_id: int
    team_abbreviation: str
    forward_lines: tuple[ForwardLine, ...]
    defensive_pairs: tuple[DefensivePair, ...]
    goalies: GoalieDepth
    fetched_at: datetime


class LineCombinationsDownloader(BaseDailyFaceoffDownloader):
    """Downloader for DailyFaceoff line combinations data.

    This downloader extracts even-strength line combinations including:
    - 4 forward lines (LW, C, RW)
    - 3 defensive pairs (LD, RD)
    - Goalie depth (starter, backup)

    The data is embedded as JSON in the page's __NEXT_DATA__ script tag.

    Example:
        config = DailyFaceoffConfig()
        async with LineCombinationsDownloader(config) as downloader:
            # Download single team
            result = await downloader.download_team(6)  # Boston
            lineup = result.data
            print(lineup["forward_lines"])

            # Download all teams
            async for result in downloader.download_all_teams():
                print(result.data["team_abbreviation"])
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
        """Parse line combinations data from DailyFaceoff page.

        Args:
            soup: Parsed BeautifulSoup document
            team_id: NHL team ID

        Returns:
            Dictionary containing parsed lineup data
        """
        abbreviation = self._get_team_abbreviation(team_id)

        # Extract __NEXT_DATA__ script content
        next_data = self._extract_next_data(soup)
        if next_data is None:
            logger.warning(
                "%s: No __NEXT_DATA__ found for team %s",
                self.source_name,
                abbreviation,
            )
            return self._empty_result(team_id, abbreviation)

        # Navigate to players array
        players_data = self._get_players_from_next_data(next_data)
        if not players_data:
            logger.warning(
                "%s: No players data found for team %s",
                self.source_name,
                abbreviation,
            )
            return self._empty_result(team_id, abbreviation)

        # Parse forward lines (f1, f2, f3, f4)
        forward_lines = tuple(
            self._parse_forward_line(players_data, f"f{i}", i) for i in range(1, 5)
        )

        # Parse defensive pairs (d1, d2, d3)
        defensive_pairs = tuple(
            self._parse_defensive_pair(players_data, f"d{i}", i) for i in range(1, 4)
        )

        # Parse goalies
        goalies = self._parse_goalies(players_data)

        lineup = TeamLineup(
            team_id=team_id,
            team_abbreviation=abbreviation,
            forward_lines=forward_lines,
            defensive_pairs=defensive_pairs,
            goalies=goalies,
            fetched_at=datetime.now(UTC),
        )

        return self._to_dict(lineup)

    def _extract_next_data(self, soup: BeautifulSoup) -> dict[str, Any] | None:
        """Extract JSON from __NEXT_DATA__ script tag.

        Args:
            soup: Parsed BeautifulSoup document

        Returns:
            Parsed JSON data or None if not found
        """
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script_tag or not script_tag.string:
            return None

        try:
            return cast(dict[str, Any], json.loads(script_tag.string))
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse __NEXT_DATA__ JSON: %s", e)
            return None

    def _get_players_from_next_data(
        self, next_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Navigate to players array in NEXT_DATA structure.

        The path is: props.pageProps.combinations.players

        Args:
            next_data: Parsed __NEXT_DATA__ JSON

        Returns:
            List of player dictionaries or empty list
        """
        try:
            players = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("combinations", {})
                .get("players", [])
            )
            return cast(list[dict[str, Any]], players)
        except (AttributeError, TypeError):
            return []

    def _parse_player(self, player_data: dict[str, Any]) -> PlayerInfo | None:
        """Parse a single player from player data.

        Args:
            player_data: Player dictionary from JSON

        Returns:
            PlayerInfo or None if required fields missing
        """
        player_id = player_data.get("playerId")
        name = player_data.get("name")
        jersey_number = player_data.get("jerseyNumber")
        position = player_data.get("positionIdentifier")

        # Require minimum fields - use isinstance checks for type safety
        if (
            not isinstance(player_id, int)
            or not isinstance(name, str)
            or not isinstance(position, str)
        ):
            return None

        return PlayerInfo(
            player_id=player_id,
            name=name,
            jersey_number=jersey_number if isinstance(jersey_number, int) else 0,
            position=position,
        )

    def _get_player_by_position(
        self,
        players_data: list[dict[str, Any]],
        group_id: str,
        position_id: str,
    ) -> PlayerInfo | None:
        """Find a player by group and position.

        Args:
            players_data: List of all player dictionaries
            group_id: Group identifier (f1, f2, d1, etc.)
            position_id: Position identifier (lw, c, rw, ld, rd, g1, g2)

        Returns:
            PlayerInfo or None if not found
        """
        for player_data in players_data:
            if (
                player_data.get("groupIdentifier") == group_id
                and player_data.get("positionIdentifier") == position_id
            ):
                return self._parse_player(player_data)
        return None

    def _parse_forward_line(
        self,
        players_data: list[dict[str, Any]],
        group_id: str,
        line_number: int,
    ) -> ForwardLine:
        """Parse a forward line from players data.

        Args:
            players_data: List of all player dictionaries
            group_id: Group identifier (f1, f2, f3, f4)
            line_number: Line number (1-4)

        Returns:
            ForwardLine with players in each position
        """
        return ForwardLine(
            line_number=line_number,
            left_wing=self._get_player_by_position(players_data, group_id, "lw"),
            center=self._get_player_by_position(players_data, group_id, "c"),
            right_wing=self._get_player_by_position(players_data, group_id, "rw"),
        )

    def _parse_defensive_pair(
        self,
        players_data: list[dict[str, Any]],
        group_id: str,
        pair_number: int,
    ) -> DefensivePair:
        """Parse a defensive pair from players data.

        Args:
            players_data: List of all player dictionaries
            group_id: Group identifier (d1, d2, d3)
            pair_number: Pair number (1-3)

        Returns:
            DefensivePair with players in each position
        """
        return DefensivePair(
            pair_number=pair_number,
            left_defense=self._get_player_by_position(players_data, group_id, "ld"),
            right_defense=self._get_player_by_position(players_data, group_id, "rd"),
        )

    def _parse_goalies(self, players_data: list[dict[str, Any]]) -> GoalieDepth:
        """Parse goalie depth from players data.

        Args:
            players_data: List of all player dictionaries

        Returns:
            GoalieDepth with starter and backup
        """
        return GoalieDepth(
            starter=self._get_player_by_position(players_data, "g", "g1"),
            backup=self._get_player_by_position(players_data, "g", "g2"),
        )

    def _empty_result(self, team_id: int, abbreviation: str) -> dict[str, Any]:
        """Create empty result when parsing fails.

        Args:
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            Dictionary with empty lineup data
        """
        empty_lines = tuple(
            ForwardLine(line_number=i, left_wing=None, center=None, right_wing=None)
            for i in range(1, 5)
        )
        empty_pairs = tuple(
            DefensivePair(pair_number=i, left_defense=None, right_defense=None)
            for i in range(1, 4)
        )
        empty_goalies = GoalieDepth(starter=None, backup=None)

        lineup = TeamLineup(
            team_id=team_id,
            team_abbreviation=abbreviation,
            forward_lines=empty_lines,
            defensive_pairs=empty_pairs,
            goalies=empty_goalies,
            fetched_at=datetime.now(UTC),
        )
        return self._to_dict(lineup)

    def _to_dict(self, lineup: TeamLineup) -> dict[str, Any]:
        """Convert TeamLineup to dictionary.

        Args:
            lineup: TeamLineup dataclass

        Returns:
            Dictionary representation
        """
        return {
            "forward_lines": [
                self._forward_line_to_dict(fl) for fl in lineup.forward_lines
            ],
            "defensive_pairs": [
                self._defensive_pair_to_dict(dp) for dp in lineup.defensive_pairs
            ],
            "goalies": self._goalies_to_dict(lineup.goalies),
            "fetched_at": lineup.fetched_at.isoformat(),
        }

    def _forward_line_to_dict(self, line: ForwardLine) -> dict[str, Any]:
        """Convert ForwardLine to dictionary.

        Args:
            line: ForwardLine dataclass

        Returns:
            Dictionary representation
        """
        return {
            "line_number": line.line_number,
            "left_wing": self._player_to_dict(line.left_wing)
            if line.left_wing
            else None,
            "center": self._player_to_dict(line.center) if line.center else None,
            "right_wing": self._player_to_dict(line.right_wing)
            if line.right_wing
            else None,
        }

    def _defensive_pair_to_dict(self, pair: DefensivePair) -> dict[str, Any]:
        """Convert DefensivePair to dictionary.

        Args:
            pair: DefensivePair dataclass

        Returns:
            Dictionary representation
        """
        return {
            "pair_number": pair.pair_number,
            "left_defense": self._player_to_dict(pair.left_defense)
            if pair.left_defense
            else None,
            "right_defense": self._player_to_dict(pair.right_defense)
            if pair.right_defense
            else None,
        }

    def _goalies_to_dict(self, goalies: GoalieDepth) -> dict[str, Any]:
        """Convert GoalieDepth to dictionary.

        Args:
            goalies: GoalieDepth dataclass

        Returns:
            Dictionary representation
        """
        return {
            "starter": self._player_to_dict(goalies.starter)
            if goalies.starter
            else None,
            "backup": self._player_to_dict(goalies.backup) if goalies.backup else None,
        }

    def _player_to_dict(self, player: PlayerInfo) -> dict[str, Any]:
        """Convert PlayerInfo to dictionary.

        Args:
            player: PlayerInfo dataclass

        Returns:
            Dictionary representation
        """
        return {
            "player_id": player.player_id,
            "name": player.name,
            "jersey_number": player.jersey_number,
            "position": player.position,
        }
