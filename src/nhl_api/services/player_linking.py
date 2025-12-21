"""Player linking service for cross-source data matching.

Links players from external sources (QuantHockey, DailyFaceoff) to their
official NHL API player IDs using fuzzy name matching.

The matching process:
1. Normalize names (remove accents, lowercase, strip suffixes)
2. Match last names with high confidence
3. Match first names/initials with flexibility
4. Return confidence scores for each match

Example usage:
    # Create service with NHL players as candidates
    service = PlayerLinkingService()
    nhl_players = [(8478402, "Connor McDavid"), (8477934, "Leon Draisaitl")]
    service.set_nhl_players(nhl_players)

    # Link QuantHockey players
    qh_players = [qh_stats_1, qh_stats_2, ...]
    links = service.link_quanthockey_to_nhl(qh_players)

    # Check results
    for link in links:
        if link.nhl_player_id:
            print(f"{link.external_name} -> {link.matched_name} ({link.confidence:.0%})")
        else:
            print(f"{link.external_name} -> NO MATCH")
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nhl_api.utils.name_matching import MatchResult, PlayerNameMatcher

if TYPE_CHECKING:
    from nhl_api.models.quanthockey import (
        QuantHockeyPlayerCareerStats,
        QuantHockeyPlayerSeasonStats,
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlayerLink:
    """Result of linking an external player to an NHL player ID.

    Attributes:
        external_name: The player name from the external source.
        nhl_player_id: The matched NHL API player ID, or None if unmatched.
        confidence: Match confidence score (0.0 to 1.0).
        matched_name: The NHL player name that was matched, or None.
        source: The external data source (e.g., "quanthockey", "dailyfaceoff").
    """

    external_name: str
    nhl_player_id: int | None
    confidence: float
    matched_name: str | None
    source: str = "unknown"

    @property
    def is_matched(self) -> bool:
        """Whether a match was found."""
        return self.nhl_player_id is not None

    @property
    def is_high_confidence(self) -> bool:
        """Whether the match is high confidence (>= 0.95)."""
        return self.confidence >= 0.95

    @property
    def is_ambiguous(self) -> bool:
        """Whether the match might be ambiguous (0.85-0.95)."""
        return self.is_matched and 0.85 <= self.confidence < 0.95


@dataclass
class LinkingStatistics:
    """Statistics about a batch linking operation.

    Attributes:
        total: Total number of players processed.
        matched: Number of players successfully matched.
        unmatched: Number of players without matches.
        high_confidence: Number of high confidence matches (>= 0.95).
        ambiguous: Number of potentially ambiguous matches (0.85-0.95).
    """

    total: int = 0
    matched: int = 0
    unmatched: int = 0
    high_confidence: int = 0
    ambiguous: int = 0

    @property
    def match_rate(self) -> float:
        """Percentage of players matched (0.0 to 1.0)."""
        if self.total == 0:
            return 0.0
        return self.matched / self.total

    @property
    def high_confidence_rate(self) -> float:
        """Percentage of high confidence matches (0.0 to 1.0)."""
        if self.total == 0:
            return 0.0
        return self.high_confidence / self.total

    def to_dict(self) -> dict[str, int | float]:
        """Convert to dictionary for serialization."""
        return {
            "total": self.total,
            "matched": self.matched,
            "unmatched": self.unmatched,
            "high_confidence": self.high_confidence,
            "ambiguous": self.ambiguous,
            "match_rate": self.match_rate,
            "high_confidence_rate": self.high_confidence_rate,
        }


@dataclass
class PlayerLinkingService:
    """Service for linking external player names to NHL API player IDs.

    Uses fuzzy name matching to handle variations in player names across
    different data sources (QuantHockey, DailyFaceoff, etc.).

    Attributes:
        threshold: Minimum confidence score to accept a match (default 0.85).
        log_unmatched: Whether to log warnings for unmatched players.
    """

    threshold: float = 0.85
    log_unmatched: bool = True

    # Internal state
    _matcher: PlayerNameMatcher = field(init=False, repr=False)
    _name_to_id: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _last_stats: LinkingStatistics = field(
        default_factory=LinkingStatistics, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Initialize the name matcher."""
        self._matcher = PlayerNameMatcher(threshold=self.threshold)

    def set_nhl_players(self, players: list[tuple[int, str]]) -> None:
        """Set the list of NHL players to match against.

        This must be called before any linking operations.

        Args:
            players: List of (player_id, name) tuples from NHL API.

        Example:
            service.set_nhl_players([
                (8478402, "Connor McDavid"),
                (8477934, "Leon Draisaitl"),
            ])
        """
        self._name_to_id = {name: player_id for player_id, name in players}
        candidate_names = [name for _, name in players]
        self._matcher.set_candidates(candidate_names)

        logger.debug("Set %d NHL players as matching candidates", len(players))

    def _link_name(self, name: str, source: str) -> PlayerLink:
        """Link a single external name to an NHL player.

        Args:
            name: The external player name to match.
            source: The data source (for logging/tracking).

        Returns:
            PlayerLink with match result.
        """
        result: MatchResult = self._matcher.match(name)

        if result.matched_name is not None:
            player_id = self._name_to_id.get(result.matched_name)
            return PlayerLink(
                external_name=name,
                nhl_player_id=player_id,
                confidence=result.score,
                matched_name=result.matched_name,
                source=source,
            )

        return PlayerLink(
            external_name=name,
            nhl_player_id=None,
            confidence=result.score,
            matched_name=None,
            source=source,
        )

    def link_quanthockey_to_nhl(
        self,
        qh_players: Sequence[
            QuantHockeyPlayerSeasonStats | QuantHockeyPlayerCareerStats
        ],
    ) -> list[PlayerLink]:
        """Link QuantHockey players to NHL player IDs.

        Args:
            qh_players: List of QuantHockey player stats objects.

        Returns:
            List of PlayerLink objects with match results.

        Raises:
            RuntimeError: If set_nhl_players() was not called first.
        """
        if not self._name_to_id:
            raise RuntimeError(
                "No NHL players set. Call set_nhl_players() before linking."
            )

        links: list[PlayerLink] = []
        stats = LinkingStatistics(total=len(qh_players))

        for qh_player in qh_players:
            link = self._link_name(qh_player.name, source="quanthockey")
            links.append(link)

            # Update statistics
            if link.is_matched:
                stats.matched += 1
                if link.is_high_confidence:
                    stats.high_confidence += 1
                elif link.is_ambiguous:
                    stats.ambiguous += 1
            else:
                stats.unmatched += 1
                if self.log_unmatched:
                    logger.warning(
                        "Unmatched QuantHockey player: %s (best score: %.2f)",
                        qh_player.name,
                        link.confidence,
                    )

        self._last_stats = stats

        logger.info(
            "Linked %d/%d QuantHockey players (%.1f%% match rate, %.1f%% high confidence)",
            stats.matched,
            stats.total,
            stats.match_rate * 100,
            stats.high_confidence_rate * 100,
        )

        return links

    def link_names(self, names: list[str], source: str = "unknown") -> list[PlayerLink]:
        """Link a list of player names to NHL player IDs.

        Generic method for linking any list of names, regardless of source.

        Args:
            names: List of player names to match.
            source: The data source identifier.

        Returns:
            List of PlayerLink objects with match results.

        Raises:
            RuntimeError: If set_nhl_players() was not called first.
        """
        if not self._name_to_id:
            raise RuntimeError(
                "No NHL players set. Call set_nhl_players() before linking."
            )

        links: list[PlayerLink] = []
        stats = LinkingStatistics(total=len(names))

        for name in names:
            link = self._link_name(name, source=source)
            links.append(link)

            if link.is_matched:
                stats.matched += 1
                if link.is_high_confidence:
                    stats.high_confidence += 1
                elif link.is_ambiguous:
                    stats.ambiguous += 1
            else:
                stats.unmatched += 1
                if self.log_unmatched:
                    logger.warning(
                        "Unmatched player from %s: %s (best score: %.2f)",
                        source,
                        name,
                        link.confidence,
                    )

        self._last_stats = stats

        logger.info(
            "Linked %d/%d players from %s (%.1f%% match rate)",
            stats.matched,
            stats.total,
            source,
            stats.match_rate * 100,
        )

        return links

    def get_statistics(self) -> LinkingStatistics:
        """Get statistics from the last linking operation.

        Returns:
            LinkingStatistics from the most recent link_* call.
        """
        return self._last_stats

    def get_unmatched(self, links: list[PlayerLink]) -> list[PlayerLink]:
        """Get only unmatched players from link results.

        Args:
            links: List of PlayerLink objects.

        Returns:
            List of unmatched PlayerLink objects.
        """
        return [link for link in links if not link.is_matched]

    def get_ambiguous(self, links: list[PlayerLink]) -> list[PlayerLink]:
        """Get potentially ambiguous matches from link results.

        Ambiguous matches are those with confidence between 0.85 and 0.95.
        These may need manual review.

        Args:
            links: List of PlayerLink objects.

        Returns:
            List of ambiguous PlayerLink objects.
        """
        return [link for link in links if link.is_ambiguous]

    @property
    def candidate_count(self) -> int:
        """Number of NHL player candidates set."""
        return len(self._name_to_id)

    @property
    def cache_size(self) -> int:
        """Number of cached match results."""
        return self._matcher.cache_size

    def clear_cache(self) -> None:
        """Clear the name matching cache."""
        self._matcher.clear_cache()
