"""DailyFaceoff Power Play Units Downloader.

This module provides a downloader for extracting power play unit configurations
from DailyFaceoff.com for all NHL teams.

Example usage:
    config = DailyFaceoffConfig()
    async with PowerPlayDownloader(config) as downloader:
        result = await downloader.download_team(6)  # Boston Bruins
        print(result.data["pp1"])  # First power play unit
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
class PowerPlayPlayer:
    """A player in a power play unit.

    Attributes:
        player_id: DailyFaceoff player ID
        name: Player's full name
        jersey_number: Player's jersey number
        position: Position identifier (sk1-sk5)
        rating: DailyFaceoff rating (0-100)
        season_goals: Goals this season
        season_assists: Assists this season
        season_points: Points this season
    """

    player_id: int
    name: str
    jersey_number: int
    position: str
    rating: float | None = None
    season_goals: int | None = None
    season_assists: int | None = None
    season_points: int | None = None


@dataclass(frozen=True, slots=True)
class PowerPlayUnit:
    """A power play unit configuration.

    Attributes:
        unit_number: Unit number (1 or 2)
        players: List of 5 players in the unit
    """

    unit_number: int
    players: tuple[PowerPlayPlayer, ...]

    def __post_init__(self) -> None:
        """Validate that unit has correct number of players."""
        if len(self.players) > 5:
            raise ValueError(
                f"Power play unit cannot have more than 5 players, got {len(self.players)}"
            )


@dataclass(frozen=True, slots=True)
class TeamPowerPlay:
    """Power play configuration for a team.

    Attributes:
        team_id: NHL team ID
        team_abbreviation: Team abbreviation (e.g., "BOS")
        pp1: First power play unit
        pp2: Second power play unit
        fetched_at: Timestamp when data was fetched
    """

    team_id: int
    team_abbreviation: str
    pp1: PowerPlayUnit | None
    pp2: PowerPlayUnit | None
    fetched_at: datetime


class PowerPlayDownloader(BaseDailyFaceoffDownloader):
    """Downloader for DailyFaceoff power play unit data.

    This downloader extracts PP1 and PP2 configurations from DailyFaceoff's
    line combinations page. The data is embedded as JSON in the page's
    __NEXT_DATA__ script tag.

    Example:
        config = DailyFaceoffConfig()
        async with PowerPlayDownloader(config) as downloader:
            # Download single team
            result = await downloader.download_team(6)  # Boston
            pp_data = result.data
            print(pp_data["pp1"]["players"])

            # Download all teams
            async for result in downloader.download_all_teams():
                print(result.data["team_abbreviation"])
    """

    @property
    def data_type(self) -> str:
        """Return data type identifier."""
        return "power_play"

    @property
    def page_path(self) -> str:
        """Return URL path for line combinations page."""
        return "line-combinations"

    async def _parse_page(self, soup: BeautifulSoup, team_id: int) -> dict[str, Any]:
        """Parse power play data from DailyFaceoff page.

        DailyFaceoff embeds lineup data as JSON in a __NEXT_DATA__ script tag.
        This method extracts that JSON and parses the PP1 and PP2 units.

        Args:
            soup: Parsed BeautifulSoup document
            team_id: NHL team ID

        Returns:
            Dictionary containing parsed power play data

        Raises:
            DownloadError: If parsing fails
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

        # Parse PP1 and PP2 units
        pp1 = self._parse_unit(players_data, "pp1", 1)
        pp2 = self._parse_unit(players_data, "pp2", 2)

        team_pp = TeamPowerPlay(
            team_id=team_id,
            team_abbreviation=abbreviation,
            pp1=pp1,
            pp2=pp2,
            fetched_at=datetime.now(UTC),
        )

        return self._to_dict(team_pp)

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

    def _parse_unit(
        self,
        players_data: list[dict[str, Any]],
        group_id: str,
        unit_number: int,
    ) -> PowerPlayUnit | None:
        """Parse a power play unit from players data.

        Args:
            players_data: List of all player dictionaries
            group_id: Group identifier ("pp1" or "pp2")
            unit_number: Unit number (1 or 2)

        Returns:
            PowerPlayUnit or None if no players found
        """
        unit_players = [p for p in players_data if p.get("groupIdentifier") == group_id]

        if not unit_players:
            return None

        # Sort by position (sk1, sk2, sk3, sk4, sk5)
        unit_players.sort(key=lambda p: p.get("positionIdentifier", "sk9"))

        parsed_players = []
        for player_data in unit_players:
            player = self._parse_player(player_data)
            if player:
                parsed_players.append(player)

        if not parsed_players:
            return None

        return PowerPlayUnit(
            unit_number=unit_number,
            players=tuple(parsed_players),
        )

    def _parse_player(self, player_data: dict[str, Any]) -> PowerPlayPlayer | None:
        """Parse a single player from player data.

        Args:
            player_data: Player dictionary from JSON

        Returns:
            PowerPlayPlayer or None if required fields missing
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

        # Extract optional season stats
        season = player_data.get("season", {}) or {}

        return PowerPlayPlayer(
            player_id=player_id,
            name=name,
            jersey_number=jersey_number if isinstance(jersey_number, int) else 0,
            position=position,
            rating=player_data.get("rating"),
            season_goals=season.get("goals"),
            season_assists=season.get("assists"),
            season_points=season.get("points"),
        )

    def _empty_result(self, team_id: int, abbreviation: str) -> dict[str, Any]:
        """Create empty result when parsing fails.

        Args:
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            Dictionary with empty power play data
        """
        team_pp = TeamPowerPlay(
            team_id=team_id,
            team_abbreviation=abbreviation,
            pp1=None,
            pp2=None,
            fetched_at=datetime.now(UTC),
        )
        return self._to_dict(team_pp)

    def _to_dict(self, team_pp: TeamPowerPlay) -> dict[str, Any]:
        """Convert TeamPowerPlay to dictionary.

        Args:
            team_pp: TeamPowerPlay dataclass

        Returns:
            Dictionary representation
        """
        return {
            "pp1": self._unit_to_dict(team_pp.pp1) if team_pp.pp1 else None,
            "pp2": self._unit_to_dict(team_pp.pp2) if team_pp.pp2 else None,
            "fetched_at": team_pp.fetched_at.isoformat(),
        }

    def _unit_to_dict(self, unit: PowerPlayUnit) -> dict[str, Any]:
        """Convert PowerPlayUnit to dictionary.

        Args:
            unit: PowerPlayUnit dataclass

        Returns:
            Dictionary representation
        """
        return {
            "unit_number": unit.unit_number,
            "players": [self._player_to_dict(p) for p in unit.players],
        }

    def _player_to_dict(self, player: PowerPlayPlayer) -> dict[str, Any]:
        """Convert PowerPlayPlayer to dictionary.

        Args:
            player: PowerPlayPlayer dataclass

        Returns:
            Dictionary representation
        """
        return {
            "player_id": player.player_id,
            "name": player.name,
            "jersey_number": player.jersey_number,
            "position": player.position,
            "rating": player.rating,
            "season_goals": player.season_goals,
            "season_assists": player.season_assists,
            "season_points": player.season_points,
        }
