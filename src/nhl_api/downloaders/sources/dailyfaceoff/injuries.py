"""DailyFaceoff Injury Tracker Downloader.

Downloads injury information from DailyFaceoff.com including:
- Team-specific injuries from line combinations pages
- League-wide injury feed from the injuries news page

URL Patterns:
- Team: https://www.dailyfaceoff.com/teams/{team-slug}/line-combinations
- League: https://www.dailyfaceoff.com/hockey-player-news/injuries

Example usage:
    config = DailyFaceoffConfig()
    async with InjuryDownloader(config) as downloader:
        # Get team injuries
        result = await downloader.download_team(10)  # Toronto

        # Get league-wide injuries
        league_injuries = await downloader.download_league_injuries()
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from bs4 import BeautifulSoup, Tag

from nhl_api.downloaders.base.protocol import (
    DownloadError,
    DownloadResult,
    DownloadStatus,
)
from nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader import (
    BaseDailyFaceoffDownloader,
)

logger = logging.getLogger(__name__)


class InjuryStatus(Enum):
    """Injury status categories from DailyFaceoff."""

    IR = "ir"  # Injured Reserve
    DTD = "day-to-day"  # Day-to-Day
    OUT = "out"  # Out
    QUESTIONABLE = "questionable"  # Questionable
    GMD = "game-time-decision"  # Game-Time Decision

    @classmethod
    def from_string(cls, value: str | None) -> InjuryStatus | None:
        """Convert string to InjuryStatus enum.

        Args:
            value: Status string from DailyFaceoff

        Returns:
            InjuryStatus enum or None if not recognized
        """
        if not value:
            return None

        value_lower = value.lower().strip()

        # Direct mappings
        status_map = {
            "ir": cls.IR,
            "injured reserve": cls.IR,
            "day-to-day": cls.DTD,
            "dtd": cls.DTD,
            "out": cls.OUT,
            "questionable": cls.QUESTIONABLE,
            "game-time-decision": cls.GMD,
            "gmd": cls.GMD,
            "gtd": cls.GMD,
        }

        return status_map.get(value_lower)


@dataclass(frozen=True, slots=True)
class InjuryRecord:
    """Individual injury record.

    Attributes:
        player_name: Player's full name
        team_id: NHL team ID (0 if unknown)
        team_abbreviation: Team abbreviation (e.g., "TOR")
        injury_type: Type of injury (e.g., "upper-body", "lower-body")
        status: Injury status enum
        expected_return: Expected return timeline (e.g., "Week-to-week")
        details: Full injury details/description
        player_id: DailyFaceoff player ID
        updated_at: When the injury was last updated
    """

    player_name: str
    team_id: int
    team_abbreviation: str
    injury_type: str | None
    status: InjuryStatus | None
    expected_return: str | None
    details: str | None
    player_id: str | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class TeamInjuries:
    """Collection of injuries for a team.

    Attributes:
        team_id: NHL team ID
        team_abbreviation: Team abbreviation
        injuries: List of injury records
        fetched_at: When the data was fetched
    """

    team_id: int
    team_abbreviation: str
    injuries: tuple[InjuryRecord, ...]
    fetched_at: datetime


# Pattern to extract player ID from URL
PLAYER_ID_PATTERN = re.compile(r"/players/[^/]+/[^/]+/(\d+)")

# Pattern to extract injury type from text
INJURY_TYPE_PATTERN = re.compile(
    r"(upper[- ]?body|lower[- ]?body|head|concussion|illness|"
    r"undisclosed|personal|foot|knee|shoulder|hand|wrist|"
    r"hip|groin|back|neck|ankle|leg|arm|eye|jaw|ribs?)",
    re.IGNORECASE,
)


class InjuryDownloader(BaseDailyFaceoffDownloader):
    """Downloads injury information from DailyFaceoff.

    Provides two download methods:
    - download_team(): Get injuries from a team's line combinations page
    - download_league_injuries(): Get all injuries from the league feed

    Example:
        config = DailyFaceoffConfig()
        async with InjuryDownloader(config) as downloader:
            # Team injuries
            result = await downloader.download_team(10)

            # League injuries
            league_result = await downloader.download_league_injuries()
    """

    @property
    def data_type(self) -> str:
        """Return data type identifier."""
        return "injuries"

    @property
    def page_path(self) -> str:
        """Return URL path for line combinations page.

        Team injuries are on the line combinations page.
        """
        return "line-combinations"

    async def _parse_page(self, soup: BeautifulSoup, team_id: int) -> dict[str, Any]:
        """Parse injuries from the team's line combinations page.

        Args:
            soup: Parsed BeautifulSoup document
            team_id: NHL team ID

        Returns:
            Dictionary containing parsed injury data
        """
        abbreviation = self._get_team_abbreviation(team_id)

        # Parse injuries from the page
        injuries = self._parse_team_injuries(soup, team_id, abbreviation)

        result = TeamInjuries(
            team_id=team_id,
            team_abbreviation=abbreviation,
            injuries=tuple(injuries),
            fetched_at=datetime.now(UTC),
        )

        return self._team_injuries_to_dict(result)

    def _parse_team_injuries(
        self, soup: BeautifulSoup, team_id: int, abbreviation: str
    ) -> list[InjuryRecord]:
        """Parse injuries from team page.

        Args:
            soup: BeautifulSoup document
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            List of InjuryRecord objects
        """
        injuries: list[InjuryRecord] = []

        # Strategy 1: Parse from __NEXT_DATA__ JSON
        injuries = self._parse_injuries_from_json(soup, team_id, abbreviation)

        # Strategy 2: Parse from HTML structure if JSON didn't work
        if not injuries:
            injuries = self._parse_injuries_from_html(soup, team_id, abbreviation)

        return injuries

    def _parse_injuries_from_json(
        self, soup: BeautifulSoup, team_id: int, abbreviation: str
    ) -> list[InjuryRecord]:
        """Parse injuries from embedded JSON data.

        Args:
            soup: BeautifulSoup document
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            List of InjuryRecord objects
        """
        injuries: list[InjuryRecord] = []

        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return injuries

        try:
            data = json.loads(script.string)
            injuries = self._extract_injuries_from_next_data(
                data, team_id, abbreviation
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug("Error parsing JSON for injuries: %s", e)

        return injuries

    def _extract_injuries_from_next_data(
        self, data: dict[str, Any], team_id: int, abbreviation: str
    ) -> list[InjuryRecord]:
        """Extract injuries from Next.js data structure.

        Args:
            data: Parsed __NEXT_DATA__ JSON
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            List of InjuryRecord objects
        """
        injuries: list[InjuryRecord] = []

        try:
            props = data.get("props", {})
            page_props = props.get("pageProps", {})

            # Look for players with injury status
            # They could be in various locations
            for key in ["players", "roster", "lineup", "formations", "combinations"]:
                if key in page_props:
                    section = page_props[key]
                    injuries.extend(
                        self._find_injured_players(section, team_id, abbreviation)
                    )

            # Also search deeply for any injured players
            if not injuries:
                injuries = self._deep_search_injuries(page_props, team_id, abbreviation)

        except (KeyError, TypeError, AttributeError) as e:
            logger.debug("Error extracting injuries from Next.js data: %s", e)

        return injuries

    def _find_injured_players(
        self, data: Any, team_id: int, abbreviation: str
    ) -> list[InjuryRecord]:
        """Find players with injury status in data structure.

        Args:
            data: Data structure to search
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            List of InjuryRecord objects
        """
        injuries: list[InjuryRecord] = []

        if isinstance(data, dict):
            # Check if this is a player with injury status
            injury_status = data.get("injuryStatus")
            if injury_status:
                record = self._dict_to_injury_record(data, team_id, abbreviation)
                if record:
                    injuries.append(record)

            # Recurse into values
            for value in data.values():
                injuries.extend(
                    self._find_injured_players(value, team_id, abbreviation)
                )

        elif isinstance(data, list):
            for item in data:
                injuries.extend(self._find_injured_players(item, team_id, abbreviation))

        return injuries

    def _deep_search_injuries(
        self, data: Any, team_id: int, abbreviation: str, max_depth: int = 10
    ) -> list[InjuryRecord]:
        """Deep search for injury data in nested structure.

        Args:
            data: Data structure to search
            team_id: NHL team ID
            abbreviation: Team abbreviation
            max_depth: Maximum recursion depth

        Returns:
            List of InjuryRecord objects
        """
        if max_depth <= 0:
            return []

        injuries: list[InjuryRecord] = []

        if isinstance(data, dict):
            # Check for injury indicators
            if data.get("injuryStatus") or data.get("injury"):
                record = self._dict_to_injury_record(data, team_id, abbreviation)
                if record:
                    injuries.append(record)

            # Recurse
            for value in data.values():
                injuries.extend(
                    self._deep_search_injuries(
                        value, team_id, abbreviation, max_depth - 1
                    )
                )

        elif isinstance(data, list):
            for item in data:
                injuries.extend(
                    self._deep_search_injuries(
                        item, team_id, abbreviation, max_depth - 1
                    )
                )

        return injuries

    def _dict_to_injury_record(
        self, data: dict[str, Any], team_id: int, abbreviation: str
    ) -> InjuryRecord | None:
        """Convert player dictionary to InjuryRecord.

        Args:
            data: Player data dictionary
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            InjuryRecord or None
        """
        name = data.get("name") or data.get("playerName") or data.get("fullName") or ""
        if not name:
            return None

        # Get injury status
        status_str = data.get("injuryStatus") or data.get("status")
        status = InjuryStatus.from_string(status_str)

        # Get injury type from details or dedicated field
        details = data.get("details") or data.get("injuryDetails") or ""
        injury_type = data.get("injuryType")
        if not injury_type and details:
            injury_type = self._extract_injury_type(details)

        # Get expected return
        expected_return = (
            data.get("expectedReturn") or data.get("returnDate") or data.get("timeline")
        )

        # Get player ID
        player_id = data.get("playerId") or data.get("id")
        if player_id:
            player_id = str(player_id)

        # Get updated timestamp
        updated_str = data.get("updatedAt") or data.get("updated")
        updated_at = None
        if updated_str:
            try:
                updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return InjuryRecord(
            player_name=name,
            team_id=team_id,
            team_abbreviation=abbreviation,
            injury_type=injury_type,
            status=status,
            expected_return=expected_return,
            details=details if details else None,
            player_id=player_id,
            updated_at=updated_at,
        )

    def _extract_injury_type(self, text: str) -> str | None:
        """Extract injury type from text.

        Args:
            text: Text containing injury description

        Returns:
            Injury type or None
        """
        match = INJURY_TYPE_PATTERN.search(text)
        if match:
            return match.group(1).lower().replace(" ", "-")
        return None

    def _parse_injuries_from_html(
        self, soup: BeautifulSoup, team_id: int, abbreviation: str
    ) -> list[InjuryRecord]:
        """Parse injuries from HTML structure.

        Args:
            soup: BeautifulSoup document
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            List of InjuryRecord objects
        """
        injuries: list[InjuryRecord] = []

        # Look for injury indicators in player elements
        injury_patterns = ["ir", "out", "dtd", "injured", "injury"]

        for pattern in injury_patterns:
            elements = soup.find_all(class_=re.compile(pattern, re.IGNORECASE))
            for elem in elements:
                record = self._extract_injury_from_element(elem, team_id, abbreviation)
                if record:
                    injuries.append(record)

        # Also look for data attributes
        for attr in ["data-injury", "data-status"]:
            elements = soup.find_all(attrs={attr: True})
            for elem in elements:
                record = self._extract_injury_from_element(elem, team_id, abbreviation)
                if record:
                    injuries.append(record)

        return injuries

    def _extract_injury_from_element(
        self, element: Tag, team_id: int, abbreviation: str
    ) -> InjuryRecord | None:
        """Extract injury info from HTML element.

        Args:
            element: BeautifulSoup element
            team_id: NHL team ID
            abbreviation: Team abbreviation

        Returns:
            InjuryRecord or None
        """
        # Find player link nearby
        link = element.find("a", href=re.compile(r"/players/"))
        if not link:
            # Try parent
            parent = element.find_parent(["div", "section", "tr"])
            if parent:
                link = parent.find("a", href=re.compile(r"/players/"))

        if not link:
            return None

        name = link.get_text(strip=True)
        if not name:
            return None

        # Get player ID from link
        href = link.get("href", "")
        player_id = None
        if href:
            match = PLAYER_ID_PATTERN.search(str(href))
            if match:
                player_id = match.group(1)

        # Get status from class or data attribute
        status = None
        class_attr = element.get("class")
        classes = list(class_attr) if class_attr else []
        for cls in classes:
            status = InjuryStatus.from_string(str(cls))
            if status:
                break

        if not status:
            status_attr = element.get("data-injury") or element.get("data-status")
            if status_attr:
                status = InjuryStatus.from_string(str(status_attr))

        return InjuryRecord(
            player_name=name,
            team_id=team_id,
            team_abbreviation=abbreviation,
            injury_type=None,
            status=status,
            expected_return=None,
            details=None,
            player_id=player_id,
            updated_at=None,
        )

    async def download_league_injuries(self, max_pages: int = 1) -> DownloadResult:
        """Download league-wide injuries from the injuries feed.

        Args:
            max_pages: Maximum number of pages to fetch (default 1)

        Returns:
            DownloadResult with list of injuries

        Raises:
            DownloadError: If the download fails
        """
        url = f"{self.config.base_url}/hockey-player-news/injuries"

        logger.debug(
            "%s: Downloading league injuries (max_pages=%d)",
            self.source_name,
            max_pages,
        )

        all_injuries: list[InjuryRecord] = []

        try:
            # Fetch first page
            path = url.replace(self.config.base_url, "")
            response = await self._get(path)

            if not response.is_success:
                raise DownloadError(
                    f"Failed to fetch injuries page: HTTP {response.status}",
                    source=self.source_name,
                )

            raw_content = response.content

            if not self._validate_html(raw_content):
                raise DownloadError(
                    "Response is not valid HTML",
                    source=self.source_name,
                )

            soup = self._parse_html(raw_content)
            injuries = self._parse_league_injuries_page(soup)
            all_injuries.extend(injuries)

            # TODO: Handle pagination if max_pages > 1
            # For now, just return first page

            return DownloadResult(
                source=self.source_name,
                season_id=0,
                game_id=0,
                data={
                    "injuries": [self._injury_to_dict(inj) for inj in all_injuries],
                    "count": len(all_injuries),
                    "fetched_at": datetime.now(UTC).isoformat(),
                },
                status=DownloadStatus.COMPLETED,
                raw_content=raw_content,
            )

        except DownloadError:
            raise
        except Exception as e:
            logger.exception("%s: Error downloading league injuries", self.source_name)
            raise DownloadError(
                f"Failed to download league injuries: {e}",
                source=self.source_name,
                cause=e,
            ) from e

    def _parse_league_injuries_page(self, soup: BeautifulSoup) -> list[InjuryRecord]:
        """Parse injuries from the league injuries page.

        Args:
            soup: BeautifulSoup document

        Returns:
            List of InjuryRecord objects
        """
        injuries: list[InjuryRecord] = []

        # Try JSON first
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            try:
                data = json.loads(script.string)
                injuries = self._extract_league_injuries_from_json(data)
                if injuries:
                    return injuries
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback to HTML parsing
        injuries = self._parse_league_injuries_from_html(soup)

        return injuries

    def _extract_league_injuries_from_json(
        self, data: dict[str, Any]
    ) -> list[InjuryRecord]:
        """Extract injuries from league page JSON.

        Args:
            data: Parsed __NEXT_DATA__ JSON

        Returns:
            List of InjuryRecord objects
        """
        injuries: list[InjuryRecord] = []

        try:
            props = data.get("props", {})
            page_props = props.get("pageProps", {})

            # Look for news/injuries items
            for key in ["news", "injuries", "items", "playerNews"]:
                if key in page_props:
                    items = page_props[key]
                    if isinstance(items, list):
                        for item in items:
                            record = self._news_item_to_injury(item)
                            if record:
                                injuries.append(record)

        except (KeyError, TypeError, AttributeError) as e:
            logger.debug("Error extracting league injuries from JSON: %s", e)

        return injuries

    def _news_item_to_injury(self, item: dict[str, Any]) -> InjuryRecord | None:
        """Convert news item to InjuryRecord.

        Args:
            item: News item dictionary

        Returns:
            InjuryRecord or None
        """
        # Check if this is an injury item
        category = item.get("newsCategoryName", "").lower()
        if category != "injury":
            return None

        player_name = item.get("playerName", "")
        if not player_name:
            return None

        # Get team info
        team_abbr = item.get("teamAbbreviation", "")
        team_id = self._get_team_id_from_abbr(team_abbr)

        # Get details
        details = item.get("details", "")
        injury_type = self._extract_injury_type(details) if details else None

        # Get player ID
        player_id = item.get("playerId")
        if player_id:
            player_id = str(player_id)

        # Get timestamp
        updated_str = item.get("updatedAt") or item.get("createdAt")
        updated_at = None
        if updated_str:
            try:
                updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return InjuryRecord(
            player_name=player_name,
            team_id=team_id,
            team_abbreviation=team_abbr,
            injury_type=injury_type,
            status=None,  # Status not typically in news items
            expected_return=None,
            details=details if details else None,
            player_id=player_id,
            updated_at=updated_at,
        )

    def _get_team_id_from_abbr(self, abbr: str) -> int:
        """Get team ID from abbreviation.

        Args:
            abbr: Team abbreviation

        Returns:
            Team ID or 0 if not found
        """
        from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import (
            TEAM_ABBREVIATIONS,
        )

        for team_id, team_abbr in TEAM_ABBREVIATIONS.items():
            if team_abbr == abbr:
                return team_id
        return 0

    def _parse_league_injuries_from_html(
        self, soup: BeautifulSoup
    ) -> list[InjuryRecord]:
        """Parse injuries from HTML structure on league page.

        Args:
            soup: BeautifulSoup document

        Returns:
            List of InjuryRecord objects
        """
        injuries: list[InjuryRecord] = []

        # Look for injury entries - typically in article or card format
        entries = soup.find_all(
            ["article", "div"], class_=re.compile(r"news|injury|player", re.I)
        )

        for entry in entries:
            # Find player link
            player_link = entry.find("a", href=re.compile(r"/players/"))
            if not player_link:
                continue

            player_name = player_link.get_text(strip=True)
            if not player_name:
                continue

            # Get player ID
            href = player_link.get("href", "")
            player_id = None
            if href:
                match = PLAYER_ID_PATTERN.search(str(href))
                if match:
                    player_id = match.group(1)

            # Find team link
            team_link = entry.find("a", href=re.compile(r"/teams/"))
            team_abbr = ""
            team_id = 0
            if team_link:
                team_text = team_link.get_text(strip=True)
                # Extract abbreviation from text like "Toronto (TOR)"
                abbr_match = re.search(r"\(([A-Z]{2,3})\)", team_text)
                if abbr_match:
                    team_abbr = abbr_match.group(1)
                    team_id = self._get_team_id_from_abbr(team_abbr)

            # Get details text
            details_elem = entry.find(
                class_=re.compile(r"details|description|text", re.I)
            )
            details = details_elem.get_text(strip=True) if details_elem else None

            injury_type = self._extract_injury_type(details) if details else None

            injuries.append(
                InjuryRecord(
                    player_name=player_name,
                    team_id=team_id,
                    team_abbreviation=team_abbr,
                    injury_type=injury_type,
                    status=None,
                    expected_return=None,
                    details=details,
                    player_id=player_id,
                    updated_at=None,
                )
            )

        return injuries

    def _team_injuries_to_dict(self, team_injuries: TeamInjuries) -> dict[str, Any]:
        """Convert TeamInjuries to dictionary.

        Args:
            team_injuries: TeamInjuries dataclass

        Returns:
            Dictionary representation
        """
        return {
            "team_id": team_injuries.team_id,
            "team_abbreviation": team_injuries.team_abbreviation,
            "injuries": [self._injury_to_dict(inj) for inj in team_injuries.injuries],
            "count": len(team_injuries.injuries),
            "fetched_at": team_injuries.fetched_at.isoformat(),
        }

    def _injury_to_dict(self, injury: InjuryRecord) -> dict[str, Any]:
        """Convert InjuryRecord to dictionary.

        Args:
            injury: InjuryRecord dataclass

        Returns:
            Dictionary representation
        """
        return {
            "player_name": injury.player_name,
            "team_id": injury.team_id,
            "team_abbreviation": injury.team_abbreviation,
            "injury_type": injury.injury_type,
            "status": injury.status.value if injury.status else None,
            "expected_return": injury.expected_return,
            "details": injury.details,
            "player_id": injury.player_id,
            "updated_at": injury.updated_at.isoformat() if injury.updated_at else None,
        }
