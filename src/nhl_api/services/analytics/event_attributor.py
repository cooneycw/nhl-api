"""Event attribution service for linking PBP events to second snapshots.

Joins play-by-play events to the expanded second-by-second snapshots,
attributing goals, shots, penalties, and other events to the specific
game seconds when they occurred.

The NHL API provides event times as game clock (MM:SS counting down).
This service converts those times and matches them to the corresponding
second snapshots, with fuzzy matching to handle timing discrepancies.

Example usage:
    async with DatabaseService() as db:
        attributor = EventAttributor(db)
        events = await attributor.get_game_events(game_id=2024020500)
        attributed = attributor.attribute_events(events, snapshots)

Issue: #259 - Wave 1: Core Pipeline (T008-T010)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nhl_api.services.analytics.shift_expander import (
    parse_game_clock_to_elapsed,
    period_to_game_second,
)

if TYPE_CHECKING:
    from nhl_api.services.analytics.shift_expander import ExpandedSecond
    from nhl_api.services.db.connection import DatabaseService

logger = logging.getLogger(__name__)

# Default fuzzy matching window in seconds
DEFAULT_FUZZY_WINDOW = 2

# Event types that are significant for analytics
STOPPAGE_EVENTS = frozenset(
    {
        "stoppage",
        "period-start",
        "period-end",
        "game-end",
        "delayed-penalty",
        "tv-timeout",
    }
)

GOAL_EVENTS = frozenset({"goal"})

SHOT_EVENTS = frozenset(
    {
        "shot-on-goal",
        "missed-shot",
        "blocked-shot",
        "goal",
    }
)

PENALTY_EVENTS = frozenset({"penalty"})

FACEOFF_EVENTS = frozenset({"faceoff"})


@dataclass(frozen=True, slots=True)
class GameEvent:
    """A play-by-play event from a game.

    Attributes:
        event_id: Database ID.
        game_id: NHL game ID.
        event_idx: Event index within game (for ordering).
        event_type: Type of event (goal, shot-on-goal, penalty, etc.).
        period: Period number.
        time_in_period: Game clock time (MM:SS format).
        period_second: Elapsed seconds in period.
        game_second: Total elapsed game seconds.
        team_id: Event owner team ID.
        player1_id: Primary player ID.
        player2_id: Secondary player ID.
        player3_id: Tertiary player ID.
        goalie_id: Goalie in net (for shots/goals).
        x_coord: X coordinate on ice.
        y_coord: Y coordinate on ice.
        zone: Zone (O/D/N).
        description: Event description.
    """

    event_id: int
    game_id: int
    event_idx: int
    event_type: str
    period: int
    time_in_period: str
    period_second: int
    game_second: int
    team_id: int | None = None
    player1_id: int | None = None
    player2_id: int | None = None
    player3_id: int | None = None
    goalie_id: int | None = None
    x_coord: float | None = None
    y_coord: float | None = None
    zone: str | None = None
    description: str | None = None

    @property
    def is_stoppage(self) -> bool:
        """True if this event represents a play stoppage."""
        return self.event_type in STOPPAGE_EVENTS

    @property
    def is_goal(self) -> bool:
        """True if this is a goal event."""
        return self.event_type in GOAL_EVENTS

    @property
    def is_shot(self) -> bool:
        """True if this is a shot event (including goals)."""
        return self.event_type in SHOT_EVENTS

    @property
    def is_penalty(self) -> bool:
        """True if this is a penalty event."""
        return self.event_type in PENALTY_EVENTS

    @property
    def is_faceoff(self) -> bool:
        """True if this is a faceoff event."""
        return self.event_type in FACEOFF_EVENTS


@dataclass
class EventAttribution:
    """Result of attributing an event to a second snapshot.

    Attributes:
        event: The GameEvent being attributed.
        snapshot_second: The game second the event was attributed to.
        offset: Time offset from event time to snapshot (for fuzzy matches).
        is_exact: True if exact time match.
    """

    event: GameEvent
    snapshot_second: int
    offset: int = 0
    is_exact: bool = True


@dataclass
class AttributionResult:
    """Result of attributing all events for a game.

    Attributes:
        game_id: NHL game ID.
        total_events: Total events processed.
        attributed: Number successfully attributed.
        unattributed: Number not matched to snapshots.
        attributions: List of successful attributions.
        errors: List of attribution errors/warnings.
    """

    game_id: int
    total_events: int = 0
    attributed: int = 0
    unattributed: int = 0
    attributions: list[EventAttribution] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class EventAttributor:
    """Service for attributing play-by-play events to second snapshots.

    Matches events from the game_events table to the corresponding
    second snapshots, handling time conversion and fuzzy matching.

    Attributes:
        db: Database service for querying event data.
        fuzzy_window: Seconds of tolerance for fuzzy matching.

    Example:
        >>> attributor = EventAttributor(db, fuzzy_window=2)
        >>> events = await attributor.get_game_events(2024020500)
        >>> result = attributor.attribute_to_snapshots(events, snapshots)
    """

    def __init__(
        self,
        db: DatabaseService,
        fuzzy_window: int = DEFAULT_FUZZY_WINDOW,
    ) -> None:
        """Initialize the EventAttributor.

        Args:
            db: Database service for data access.
            fuzzy_window: Seconds of tolerance for fuzzy time matching.
        """
        self.db = db
        self.fuzzy_window = fuzzy_window

    async def get_game_events(self, game_id: int) -> list[GameEvent]:
        """Fetch all events for a game from the database.

        Args:
            game_id: NHL game ID.

        Returns:
            List of GameEvent objects ordered by event_idx.
        """
        rows = await self.db.fetch(
            """
            SELECT id, game_id, event_idx, event_type, period,
                   time_in_period, event_owner_team_id,
                   player1_id, player2_id, player3_id, goalie_id,
                   x_coord, y_coord, zone, description
            FROM game_events
            WHERE game_id = $1
            ORDER BY event_idx
            """,
            game_id,
        )

        events = []
        for row in rows:
            period = row["period"]
            time_str = row["time_in_period"] or "20:00"

            # Convert game clock to elapsed seconds
            period_second = parse_game_clock_to_elapsed(time_str, period)
            game_second = period_to_game_second(period, period_second)

            event = GameEvent(
                event_id=row["id"],
                game_id=row["game_id"],
                event_idx=row["event_idx"],
                event_type=row["event_type"],
                period=period,
                time_in_period=time_str,
                period_second=period_second,
                game_second=game_second,
                team_id=row["event_owner_team_id"],
                player1_id=row["player1_id"],
                player2_id=row["player2_id"],
                player3_id=row["player3_id"],
                goalie_id=row["goalie_id"],
                x_coord=row["x_coord"],
                y_coord=row["y_coord"],
                zone=row["zone"],
                description=row["description"],
            )
            events.append(event)

        logger.info(f"Fetched {len(events)} events for game {game_id}")
        return events

    def attribute_to_snapshots(
        self,
        events: list[GameEvent],
        snapshots: list[ExpandedSecond],
    ) -> AttributionResult:
        """Attribute events to second snapshots.

        For each event, finds the corresponding snapshot using the
        event's game_second, with fuzzy matching if no exact match.

        Args:
            events: List of GameEvent objects.
            snapshots: List of ExpandedSecond objects.

        Returns:
            AttributionResult with all attributions.
        """
        if not events:
            return AttributionResult(game_id=0)

        game_id = events[0].game_id
        result = AttributionResult(game_id=game_id, total_events=len(events))

        # Build lookup map for snapshots by game_second
        snapshot_map: dict[int, ExpandedSecond] = {s.game_second: s for s in snapshots}

        for event in events:
            attribution = self._find_matching_snapshot(event, snapshot_map)
            if attribution:
                result.attributions.append(attribution)
                result.attributed += 1
            else:
                result.unattributed += 1
                result.errors.append(
                    f"Event {event.event_idx} ({event.event_type}) at "
                    f"second {event.game_second} has no matching snapshot"
                )

        logger.info(
            f"Game {game_id}: Attributed {result.attributed}/{result.total_events} "
            f"events ({result.unattributed} unattributed)"
        )

        return result

    def _find_matching_snapshot(
        self,
        event: GameEvent,
        snapshot_map: dict[int, ExpandedSecond],
    ) -> EventAttribution | None:
        """Find matching snapshot for an event.

        First tries exact match, then fuzzy match within window.

        Args:
            event: Event to match.
            snapshot_map: Map of game_second to ExpandedSecond.

        Returns:
            EventAttribution if match found, None otherwise.
        """
        target_second = event.game_second

        # Try exact match
        if target_second in snapshot_map:
            return EventAttribution(
                event=event,
                snapshot_second=target_second,
                offset=0,
                is_exact=True,
            )

        # Try fuzzy match within window
        for offset in range(1, self.fuzzy_window + 1):
            # Check before
            if target_second - offset in snapshot_map:
                return EventAttribution(
                    event=event,
                    snapshot_second=target_second - offset,
                    offset=-offset,
                    is_exact=False,
                )
            # Check after
            if target_second + offset in snapshot_map:
                return EventAttribution(
                    event=event,
                    snapshot_second=target_second + offset,
                    offset=offset,
                    is_exact=False,
                )

        return None

    def get_stoppage_seconds(
        self,
        attributions: list[EventAttribution],
    ) -> set[int]:
        """Get all game seconds that should be marked as stoppages.

        Finds seconds where stoppage events occurred, useful for
        updating the is_stoppage flag on snapshots.

        Args:
            attributions: List of event attributions.

        Returns:
            Set of game seconds with stoppages.
        """
        return {attr.snapshot_second for attr in attributions if attr.event.is_stoppage}

    def get_goalie_map(
        self,
        events: list[GameEvent],
        home_team_id: int,
        away_team_id: int,
    ) -> dict[int, tuple[int | None, int | None]]:
        """Build a map of which goalies are in net at each game second.

        Uses shot/goal events to track goalie presence. Between events,
        assumes the same goalie remains in net.

        Args:
            events: List of game events.
            home_team_id: Home team ID.
            away_team_id: Away team ID.

        Returns:
            Dict mapping game_second to (home_goalie_id, away_goalie_id).
        """
        # Extract goalie appearances from shot/goal events
        goalie_sightings: list[
            tuple[int, int, int]
        ] = []  # (game_second, team_id, goalie_id)

        for event in events:
            if event.goalie_id and event.is_shot:
                # The goalie_id is the goalie who faced the shot
                # The shooting team is the event owner, so goalie is on other team
                if event.team_id == home_team_id:
                    # Home team shot, away goalie in net
                    goalie_sightings.append(
                        (event.game_second, away_team_id, event.goalie_id)
                    )
                elif event.team_id == away_team_id:
                    # Away team shot, home goalie in net
                    goalie_sightings.append(
                        (event.game_second, home_team_id, event.goalie_id)
                    )

        if not goalie_sightings:
            return {}

        # Sort by game second
        goalie_sightings.sort(key=lambda x: x[0])

        # Track current goalies
        home_goalie: int | None = None
        away_goalie: int | None = None
        goalie_map: dict[int, tuple[int | None, int | None]] = {}

        # Find the first appearance of each goalie
        for game_sec, team_id, goalie_id in goalie_sightings:
            if team_id == home_team_id and home_goalie is None:
                home_goalie = goalie_id
            elif team_id == away_team_id and away_goalie is None:
                away_goalie = goalie_id

            goalie_map[game_sec] = (home_goalie, away_goalie)

            # Update current goalies (in case of goalie change)
            if team_id == home_team_id:
                home_goalie = goalie_id
            else:
                away_goalie = goalie_id

        return goalie_map
