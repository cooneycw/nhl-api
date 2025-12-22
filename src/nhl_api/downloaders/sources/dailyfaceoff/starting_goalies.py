"""DailyFaceoff Starting Goalies Downloader.

Downloads confirmed and expected starting goalies for tonight's games
from DailyFaceoff.com.

URL Pattern: https://www.dailyfaceoff.com/starting-goalies

Example usage:
    config = DailyFaceoffConfig()
    async with StartingGoaliesDownloader(config) as downloader:
        result = await downloader.download_tonight()
        for start in result.data["starts"]:
            print(f"{start['goalie_name']} ({start['status']})")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from nhl_api.downloaders.base.protocol import (
    DownloadError,
    DownloadResult,
    DownloadStatus,
)
from nhl_api.downloaders.sources.dailyfaceoff.base_dailyfaceoff_downloader import (
    BaseDailyFaceoffDownloader,
    DailyFaceoffConfig,
)
from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import (
    TEAM_ABBREVIATIONS,
)

if TYPE_CHECKING:
    from datetime import date

    from bs4 import BeautifulSoup

    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)


class ConfirmationStatus(Enum):
    """Goalie start confirmation status from DailyFaceoff.

    Attributes:
        CONFIRMED: Officially confirmed by team or reporter
        LIKELY: Expected to start based on analysis
        UNCONFIRMED: No confirmation available
    """

    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNCONFIRMED = "unconfirmed"

    @classmethod
    def from_strength_id(cls, strength_id: int | None) -> ConfirmationStatus:
        """Convert DailyFaceoff newsStrengthId to ConfirmationStatus.

        Args:
            strength_id: DailyFaceoff newsStrengthId value

        Returns:
            ConfirmationStatus enum value
        """
        if strength_id == 2:
            return cls.CONFIRMED
        elif strength_id == 3:
            return cls.LIKELY
        return cls.UNCONFIRMED

    @classmethod
    def from_string(cls, value: str | None) -> ConfirmationStatus:
        """Convert string to ConfirmationStatus.

        Args:
            value: Status string from DailyFaceoff

        Returns:
            ConfirmationStatus enum value
        """
        if not value:
            return cls.UNCONFIRMED

        value_lower = value.lower().strip()
        if value_lower == "confirmed":
            return cls.CONFIRMED
        elif value_lower in ("likely", "expected"):
            return cls.LIKELY
        return cls.UNCONFIRMED


@dataclass(frozen=True, slots=True)
class GoalieStart:
    """Individual goalie start record.

    Attributes:
        goalie_name: Goalie's full name
        goalie_id: DailyFaceoff goalie ID
        team_id: NHL team ID
        team_abbreviation: Team abbreviation (e.g., "TOR")
        opponent_id: Opponent NHL team ID
        opponent_abbreviation: Opponent abbreviation
        game_time: Scheduled game start time (UTC)
        status: Confirmation status
        is_home: Whether this goalie is the home team
        wins: Season wins
        losses: Season losses
        otl: Overtime losses
        save_pct: Save percentage
        gaa: Goals against average
        shutouts: Season shutouts
    """

    goalie_name: str
    goalie_id: int
    team_id: int
    team_abbreviation: str
    opponent_id: int
    opponent_abbreviation: str
    game_time: datetime
    status: ConfirmationStatus
    is_home: bool
    wins: int | None = None
    losses: int | None = None
    otl: int | None = None
    save_pct: float | None = None
    gaa: float | None = None
    shutouts: int | None = None


@dataclass(slots=True)
class TonightsGoalies:
    """Collection of tonight's starting goalies.

    Attributes:
        starts: List of goalie start records
        game_date: Date of the games
        fetched_at: When the data was fetched
    """

    starts: list[GoalieStart] = field(default_factory=list)
    game_date: datetime | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# Reverse mapping: abbreviation -> team_id
ABBREV_TO_TEAM_ID: dict[str, int] = {
    abbrev: team_id for team_id, abbrev in TEAM_ABBREVIATIONS.items()
}


class StartingGoaliesDownloader(BaseDailyFaceoffDownloader):
    """Downloads starting goalie information from DailyFaceoff.

    This downloader fetches the starting-goalies page which shows
    all games for tonight with their confirmed/expected starters.

    Unlike other DailyFaceoff downloaders, this is NOT team-based.
    Use download_tonight() to get all games at once.

    Example:
        config = DailyFaceoffConfig()
        async with StartingGoaliesDownloader(config) as downloader:
            result = await downloader.download_tonight()
            for start in result.data["starts"]:
                status = start["status"]
                name = start["goalie_name"]
                team = start["team_abbreviation"]
                print(f"{name} ({team}) - {status}")
    """

    @property
    def data_type(self) -> str:
        """Return data type identifier."""
        return "starting_goalies"

    @property
    def page_path(self) -> str:
        """Return URL path.

        Note: This is not used for starting goalies since it's
        a league-wide page, not team-specific.
        """
        return "starting-goalies"

    async def _parse_page(self, soup: BeautifulSoup, team_id: int) -> dict[str, Any]:
        """Not used for starting goalies.

        Starting goalies uses download_tonight() instead of team-based download.

        Args:
            soup: Parsed BeautifulSoup document
            team_id: Not used

        Returns:
            Empty dict
        """
        return {}

    async def download_tonight(self) -> DownloadResult:
        """Download tonight's starting goalies.

        Fetches the starting-goalies page and parses all game matchups
        with their confirmed or expected starters.

        Returns:
            DownloadResult with list of goalie starts

        Raises:
            DownloadError: If the download fails
        """
        url = f"{self.config.base_url}/starting-goalies"

        logger.debug("%s: Downloading tonight's starting goalies", self.source_name)

        try:
            path = url.replace(self.config.base_url, "")
            response = await self._get(path)

            if not response.is_success:
                raise DownloadError(
                    f"Failed to fetch starting goalies page: HTTP {response.status}",
                    source=self.source_name,
                )

            raw_content = response.content

            # Validate HTML
            if not self._validate_html(raw_content):
                raise DownloadError(
                    "Response is not valid HTML",
                    source=self.source_name,
                )

            # Parse HTML
            soup = self._parse_html(raw_content)

            # Extract goalie data
            tonights_goalies = self._parse_starting_goalies(soup)

            return DownloadResult(
                source=self.source_name,
                season_id=0,
                game_id=0,
                data=self._to_dict(tonights_goalies),
                status=DownloadStatus.COMPLETED,
                raw_content=raw_content,
            )

        except DownloadError:
            raise
        except Exception as e:
            logger.exception(
                "%s: Error downloading starting goalies",
                self.source_name,
            )
            raise DownloadError(
                f"Failed to download starting goalies: {e}",
                source=self.source_name,
                cause=e,
            ) from e

    def _parse_starting_goalies(self, soup: BeautifulSoup) -> TonightsGoalies:
        """Parse starting goalies from the page.

        Extracts data from the __NEXT_DATA__ JSON embedded in the page.

        Args:
            soup: Parsed BeautifulSoup document

        Returns:
            TonightsGoalies with all starts
        """
        # Extract __NEXT_DATA__ JSON
        next_data = self._extract_next_data(soup)
        if next_data is None:
            logger.warning("%s: No __NEXT_DATA__ found", self.source_name)
            return TonightsGoalies()

        # Navigate to games array
        games = self._get_games_from_next_data(next_data)
        if not games:
            logger.warning("%s: No games found in data", self.source_name)
            return TonightsGoalies()

        # Parse each game's goalies
        starts: list[GoalieStart] = []
        game_date: datetime | None = None

        for game in games:
            # Parse away goalie
            away_goalie = self._parse_goalie_from_game(game, is_home=False)
            if away_goalie:
                starts.append(away_goalie)
                if game_date is None:
                    game_date = away_goalie.game_time

            # Parse home goalie
            home_goalie = self._parse_goalie_from_game(game, is_home=True)
            if home_goalie:
                starts.append(home_goalie)
                if game_date is None:
                    game_date = home_goalie.game_time

        return TonightsGoalies(
            starts=starts,
            game_date=game_date,
            fetched_at=datetime.now(UTC),
        )

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

    def _get_games_from_next_data(
        self, next_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Navigate to games array in NEXT_DATA structure.

        The path is: props.pageProps.games

        Args:
            next_data: Parsed __NEXT_DATA__ JSON

        Returns:
            List of game dictionaries or empty list
        """
        try:
            games = next_data.get("props", {}).get("pageProps", {}).get("games", [])
            return cast(list[dict[str, Any]], games)
        except (AttributeError, TypeError):
            return []

    def _parse_goalie_from_game(
        self, game: dict[str, Any], is_home: bool
    ) -> GoalieStart | None:
        """Parse a goalie from game data.

        Args:
            game: Game dictionary from JSON
            is_home: True for home goalie, False for away

        Returns:
            GoalieStart or None if goalie data not available
        """
        prefix = "home" if is_home else "away"
        opponent_prefix = "away" if is_home else "home"

        # Get goalie name and ID
        goalie_name = game.get(f"{prefix}GoalieName")
        goalie_id = game.get(f"{prefix}GoalieId")

        if not goalie_name or not goalie_id:
            return None

        # Get team info
        team_slug = game.get(f"{prefix}TeamSlug", "")
        opponent_slug = game.get(f"{opponent_prefix}TeamSlug", "")

        # Try to get team ID from slug mapping
        team_id = self._get_team_id_from_slug(team_slug)
        opponent_id = self._get_team_id_from_slug(opponent_slug)

        # Get abbreviations
        team_abbrev = self._get_abbrev_from_slug(team_slug)
        opponent_abbrev = self._get_abbrev_from_slug(opponent_slug)

        # Parse game time
        game_time_str = game.get("dateGmt")
        game_time = self._parse_game_time(game_time_str)

        # Parse confirmation status
        status = ConfirmationStatus.from_strength_id(
            game.get(f"{prefix}NewsStrengthId")
        )

        # Also check newsStrengthName if ID didn't give us a clear answer
        if status == ConfirmationStatus.UNCONFIRMED:
            status = ConfirmationStatus.from_string(
                game.get(f"{prefix}NewsStrengthName")
            )

        # Parse goalie stats
        wins = self._safe_int(game.get(f"{prefix}GoalieWins"))
        losses = self._safe_int(game.get(f"{prefix}GoalieLosses"))
        otl = self._safe_int(game.get(f"{prefix}GoalieOtl"))
        shutouts = self._safe_int(game.get(f"{prefix}GoalieShutouts"))
        save_pct = self._safe_float(game.get(f"{prefix}GoalieSavePct"))
        gaa = self._safe_float(game.get(f"{prefix}GoalieGaa"))

        return GoalieStart(
            goalie_name=str(goalie_name),
            goalie_id=int(goalie_id),
            team_id=team_id,
            team_abbreviation=team_abbrev,
            opponent_id=opponent_id,
            opponent_abbreviation=opponent_abbrev,
            game_time=game_time,
            status=status,
            is_home=is_home,
            wins=wins,
            losses=losses,
            otl=otl,
            save_pct=save_pct,
            gaa=gaa,
            shutouts=shutouts,
        )

    def _get_team_id_from_slug(self, slug: str) -> int:
        """Get NHL team ID from DailyFaceoff slug.

        Args:
            slug: DailyFaceoff team slug (e.g., "toronto-maple-leafs")

        Returns:
            NHL team ID or 0 if not found
        """
        # Import here to avoid circular import
        from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import (
            TEAM_SLUGS,
        )

        for team_id, team_slug in TEAM_SLUGS.items():
            if team_slug == slug:
                return team_id
        return 0

    def _get_abbrev_from_slug(self, slug: str) -> str:
        """Get team abbreviation from slug.

        Args:
            slug: DailyFaceoff team slug

        Returns:
            Team abbreviation or empty string
        """
        team_id = self._get_team_id_from_slug(slug)
        if team_id:
            return TEAM_ABBREVIATIONS.get(team_id, "")
        return ""

    def _parse_game_time(self, time_str: str | None) -> datetime:
        """Parse game time from ISO format.

        Args:
            time_str: ISO format time string (e.g., "2025-12-21T18:00:00.000Z")

        Returns:
            Parsed datetime or current time if parsing fails
        """
        if not time_str:
            return datetime.now(UTC)

        try:
            # Handle ISO format with milliseconds and Z suffix
            clean_str = time_str.replace("Z", "+00:00")
            if "." in clean_str:
                # Remove milliseconds for fromisoformat
                parts = clean_str.split(".")
                clean_str = parts[0] + "+00:00"
            return datetime.fromisoformat(clean_str)
        except (ValueError, AttributeError):
            logger.warning("Failed to parse game time: %s", time_str)
            return datetime.now(UTC)

    def _safe_int(self, value: Any) -> int | None:
        """Safely convert value to int.

        Args:
            value: Value to convert

        Returns:
            Integer or None
        """
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _safe_float(self, value: Any) -> float | None:
        """Safely convert value to float.

        Args:
            value: Value to convert

        Returns:
            Float or None
        """
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _to_dict(self, tonights_goalies: TonightsGoalies) -> dict[str, Any]:
        """Convert TonightsGoalies to dictionary.

        Args:
            tonights_goalies: TonightsGoalies dataclass

        Returns:
            Dictionary representation
        """
        return {
            "starts": [self._goalie_start_to_dict(s) for s in tonights_goalies.starts],
            "game_date": tonights_goalies.game_date.isoformat()
            if tonights_goalies.game_date
            else None,
            "fetched_at": tonights_goalies.fetched_at.isoformat(),
            "game_count": len({s.game_time for s in tonights_goalies.starts}),
        }

    def _goalie_start_to_dict(self, start: GoalieStart) -> dict[str, Any]:
        """Convert GoalieStart to dictionary.

        Args:
            start: GoalieStart dataclass

        Returns:
            Dictionary representation
        """
        return {
            "goalie_name": start.goalie_name,
            "goalie_id": start.goalie_id,
            "team_id": start.team_id,
            "team_abbreviation": start.team_abbreviation,
            "opponent_id": start.opponent_id,
            "opponent_abbreviation": start.opponent_abbreviation,
            "game_time": start.game_time.isoformat(),
            "status": start.status.value,
            "is_home": start.is_home,
            "wins": start.wins,
            "losses": start.losses,
            "otl": start.otl,
            "save_pct": start.save_pct,
            "gaa": start.gaa,
            "shutouts": start.shutouts,
        }

    async def persist(
        self,
        db: DatabaseService,
        goalie_data: dict[str, Any],
        game_date: date,
    ) -> int:
        """Persist starting goalies to the database.

        Uses upsert (INSERT ... ON CONFLICT) to handle re-downloads gracefully.

        Args:
            db: Database service instance
            goalie_data: Parsed goalie dictionary from download_tonight()
            game_date: Date of the games

        Returns:
            Number of goalie starts upserted
        """
        count = 0
        fetched_at = datetime.fromisoformat(
            goalie_data.get("fetched_at", datetime.now(UTC).isoformat())
        )

        for start in goalie_data.get("starts", []):
            if not start.get("goalie_name"):
                continue

            # Parse game_time if available
            game_time = None
            if start.get("game_time"):
                try:
                    game_time = datetime.fromisoformat(start["game_time"])
                except (ValueError, TypeError):
                    pass

            await db.execute(
                """
                INSERT INTO df_starting_goalies (
                    game_date, fetched_at,
                    team_abbrev, opponent_abbrev, is_home, game_time,
                    goalie_name, df_goalie_id, confirmation_status,
                    wins, losses, otl, save_pct, gaa, shutouts
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (game_date, team_abbrev, goalie_name)
                DO UPDATE SET
                    fetched_at = EXCLUDED.fetched_at,
                    opponent_abbrev = EXCLUDED.opponent_abbrev,
                    is_home = EXCLUDED.is_home,
                    game_time = EXCLUDED.game_time,
                    df_goalie_id = EXCLUDED.df_goalie_id,
                    confirmation_status = EXCLUDED.confirmation_status,
                    wins = EXCLUDED.wins,
                    losses = EXCLUDED.losses,
                    otl = EXCLUDED.otl,
                    save_pct = EXCLUDED.save_pct,
                    gaa = EXCLUDED.gaa,
                    shutouts = EXCLUDED.shutouts,
                    updated_at = CURRENT_TIMESTAMP
                """,
                game_date,
                fetched_at,
                start.get("team_abbreviation"),
                start.get("opponent_abbreviation"),
                start.get("is_home"),
                game_time,
                start.get("goalie_name"),
                start.get("goalie_id"),
                start.get("status"),
                start.get("wins"),
                start.get("losses"),
                start.get("otl"),
                start.get("save_pct"),
                start.get("gaa"),
                start.get("shutouts"),
            )
            count += 1

        logger.debug(
            "Persisted %d starting goalies for %s",
            count,
            game_date,
        )
        return count


def create_starting_goalies_downloader(
    config: DailyFaceoffConfig | None = None,
) -> StartingGoaliesDownloader:
    """Factory function to create a StartingGoaliesDownloader.

    Args:
        config: Optional configuration

    Returns:
        Configured StartingGoaliesDownloader instance
    """
    return StartingGoaliesDownloader(config)
