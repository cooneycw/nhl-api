"""Play-by-play internal consistency validation rules.

Validates that play-by-play data is internally consistent:
- 0-2 assists per goal
- Valid period time ranges
- Chronological event ordering
- Sequential period numbers
- Non-decreasing scores and SOG
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from nhl_api.validation.constants import (
    COORD_X_MAX,
    COORD_X_MIN,
    COORD_Y_MAX,
    COORD_Y_MIN,
    GAME_TYPE_PLAYOFF,
    MAX_ASSISTS_PER_GOAL,
    PERIOD_MAX_PLAYOFF,
    PERIOD_MAX_REG,
    PERIOD_MIN,
    PERIOD_SO,
    PERIOD_TIME_MAX_OT_PLAYOFF,
    PERIOD_TIME_MAX_OT_REG,
    PERIOD_TIME_MAX_REG,
    SOURCE_PBP,
)
from nhl_api.validation.results import (
    InternalValidationResult,
    make_failed,
    make_passed,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.nhl_json.play_by_play import (
        GameEvent,
        ParsedPlayByPlay,
    )

# Regex pattern for time format (MM:SS or M:SS)
TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")


def validate_play_by_play(pbp: ParsedPlayByPlay) -> list[InternalValidationResult]:
    """Validate all internal consistency rules for play-by-play data.

    Args:
        pbp: Parsed play-by-play data

    Returns:
        List of validation results for all rules
    """
    results: list[InternalValidationResult] = []
    entity_id = str(pbp.game_id)
    is_playoff = pbp.game_type == GAME_TYPE_PLAYOFF

    # Validate individual events
    for event in pbp.events:
        results.extend(_validate_event(event, entity_id, is_playoff))

    # Validate event ordering
    results.extend(_validate_event_ordering(pbp.events, entity_id))

    # Validate score progression
    results.extend(_validate_score_progression(pbp.events, entity_id))

    # Validate SOG progression
    results.extend(_validate_sog_progression(pbp.events, entity_id))

    # Validate period sequence
    results.extend(_validate_period_sequence(pbp.events, entity_id, is_playoff))

    return results


def _parse_time_to_seconds(time_str: str) -> int | None:
    """Parse MM:SS format to seconds.

    Args:
        time_str: Time string in MM:SS format

    Returns:
        Total seconds, or None if invalid format
    """
    match = TIME_PATTERN.match(time_str)
    if not match:
        return None
    minutes = int(match.group(1))
    seconds = int(match.group(2))
    return minutes * 60 + seconds


def _validate_event(
    event: GameEvent, entity_id: str, is_playoff: bool
) -> list[InternalValidationResult]:
    """Validate internal consistency for a single event.

    Args:
        event: Game event
        entity_id: Game ID for context
        is_playoff: Whether this is a playoff game

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []

    # Rule: Goal events should have 0-2 assists
    if event.event_type == "goal":
        assists = [p for p in event.players if p.role == "assist"]
        if len(assists) > MAX_ASSISTS_PER_GOAL:
            results.append(
                make_failed(
                    rule_name="pbp_assists_per_goal",
                    source_type=SOURCE_PBP,
                    message=f"Event {event.event_id}: goal has {len(assists)} assists (max {MAX_ASSISTS_PER_GOAL})",
                    severity="error",
                    details={
                        "event_id": event.event_id,
                        "period": event.period,
                        "time": event.time_in_period,
                        "assist_count": len(assists),
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="pbp_assists_per_goal",
                    source_type=SOURCE_PBP,
                    message=f"Event {event.event_id}: goal assists validation passed",
                    entity_id=entity_id,
                )
            )

    # Rule: Period time in valid range
    time_seconds = _parse_time_to_seconds(event.time_in_period)
    if time_seconds is not None:
        # Determine max time based on period type
        if event.period_type == "SO":
            # Shootout doesn't have traditional timing
            max_time = PERIOD_TIME_MAX_REG  # Just a sanity check
        elif event.period_type == "OT" or event.period > PERIOD_MAX_REG:
            max_time = (
                PERIOD_TIME_MAX_OT_PLAYOFF if is_playoff else PERIOD_TIME_MAX_OT_REG
            )
        else:
            max_time = PERIOD_TIME_MAX_REG

        if time_seconds < 0 or time_seconds > max_time:
            results.append(
                make_failed(
                    rule_name="pbp_period_time_range",
                    source_type=SOURCE_PBP,
                    message=f"Event {event.event_id}: time {event.time_in_period} outside valid range for period {event.period}",
                    severity="error",
                    details={
                        "event_id": event.event_id,
                        "period": event.period,
                        "period_type": event.period_type,
                        "time_in_period": event.time_in_period,
                        "time_seconds": time_seconds,
                        "max_time": max_time,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="pbp_period_time_range",
                    source_type=SOURCE_PBP,
                    message=f"Event {event.event_id}: period time validation passed",
                    entity_id=entity_id,
                )
            )
    else:
        results.append(
            make_failed(
                rule_name="pbp_period_time_range",
                source_type=SOURCE_PBP,
                message=f"Event {event.event_id}: invalid time format '{event.time_in_period}'",
                severity="warning",
                details={
                    "event_id": event.event_id,
                    "time_in_period": event.time_in_period,
                },
                entity_id=entity_id,
            )
        )

    # Rule: Coordinates in valid range (if present)
    if event.x_coord is not None:
        if not (COORD_X_MIN <= event.x_coord <= COORD_X_MAX):
            results.append(
                make_failed(
                    rule_name="pbp_coordinates_range",
                    source_type=SOURCE_PBP,
                    message=f"Event {event.event_id}: x_coord {event.x_coord} outside range [{COORD_X_MIN}, {COORD_X_MAX}]",
                    severity="info",
                    details={
                        "event_id": event.event_id,
                        "x_coord": event.x_coord,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="pbp_coordinates_range",
                    source_type=SOURCE_PBP,
                    message=f"Event {event.event_id}: x_coord validation passed",
                    entity_id=entity_id,
                )
            )

    if event.y_coord is not None:
        if not (COORD_Y_MIN <= event.y_coord <= COORD_Y_MAX):
            results.append(
                make_failed(
                    rule_name="pbp_coordinates_range",
                    source_type=SOURCE_PBP,
                    message=f"Event {event.event_id}: y_coord {event.y_coord} outside range [{COORD_Y_MIN}, {COORD_Y_MAX}]",
                    severity="info",
                    details={
                        "event_id": event.event_id,
                        "y_coord": event.y_coord,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="pbp_coordinates_range",
                    source_type=SOURCE_PBP,
                    message=f"Event {event.event_id}: y_coord validation passed",
                    entity_id=entity_id,
                )
            )

    return results


def _validate_event_ordering(
    events: list[GameEvent], entity_id: str
) -> list[InternalValidationResult]:
    """Validate that events are in chronological order by sort_order.

    Args:
        events: List of game events
        entity_id: Game ID for context

    Returns:
        List containing single validation result
    """
    if len(events) < 2:
        return [
            make_passed(
                rule_name="pbp_chronological_order",
                source_type=SOURCE_PBP,
                message="Event ordering validation passed (fewer than 2 events)",
                entity_id=entity_id,
            )
        ]

    out_of_order = []
    for i in range(1, len(events)):
        if events[i].sort_order < events[i - 1].sort_order:
            out_of_order.append((events[i - 1].event_id, events[i].event_id))

    if out_of_order:
        return [
            make_failed(
                rule_name="pbp_chronological_order",
                source_type=SOURCE_PBP,
                message=f"Events not in chronological order: {len(out_of_order)} out-of-order pairs",
                severity="warning",
                details={
                    "out_of_order_pairs": out_of_order[:10],  # Limit to first 10
                    "total_out_of_order": len(out_of_order),
                },
                entity_id=entity_id,
            )
        ]

    return [
        make_passed(
            rule_name="pbp_chronological_order",
            source_type=SOURCE_PBP,
            message="Event ordering validation passed",
            entity_id=entity_id,
        )
    ]


def _validate_score_progression(
    events: list[GameEvent], entity_id: str
) -> list[InternalValidationResult]:
    """Validate that scores never decrease during a game.

    Args:
        events: List of game events
        entity_id: Game ID for context

    Returns:
        List containing single validation result
    """
    if len(events) < 2:
        return [
            make_passed(
                rule_name="pbp_score_progression",
                source_type=SOURCE_PBP,
                message="Score progression validation passed (fewer than 2 events)",
                entity_id=entity_id,
            )
        ]

    decreases = []
    for i in range(1, len(events)):
        prev = events[i - 1]
        curr = events[i]
        if curr.home_score < prev.home_score or curr.away_score < prev.away_score:
            decreases.append(
                {
                    "prev_event": prev.event_id,
                    "curr_event": curr.event_id,
                    "prev_score": f"{prev.away_score}-{prev.home_score}",
                    "curr_score": f"{curr.away_score}-{curr.home_score}",
                }
            )

    if decreases:
        return [
            make_failed(
                rule_name="pbp_score_progression",
                source_type=SOURCE_PBP,
                message=f"Score decreased {len(decreases)} time(s) during game",
                severity="warning",
                details={
                    "decreases": decreases[:10],  # Limit to first 10
                    "total_decreases": len(decreases),
                },
                entity_id=entity_id,
            )
        ]

    return [
        make_passed(
            rule_name="pbp_score_progression",
            source_type=SOURCE_PBP,
            message="Score progression validation passed",
            entity_id=entity_id,
        )
    ]


def _validate_sog_progression(
    events: list[GameEvent], entity_id: str
) -> list[InternalValidationResult]:
    """Validate that shots on goal never decrease during a game.

    Args:
        events: List of game events
        entity_id: Game ID for context

    Returns:
        List containing single validation result
    """
    if len(events) < 2:
        return [
            make_passed(
                rule_name="pbp_sog_progression",
                source_type=SOURCE_PBP,
                message="SOG progression validation passed (fewer than 2 events)",
                entity_id=entity_id,
            )
        ]

    decreases = []
    for i in range(1, len(events)):
        prev = events[i - 1]
        curr = events[i]
        if curr.home_sog < prev.home_sog or curr.away_sog < prev.away_sog:
            decreases.append(
                {
                    "prev_event": prev.event_id,
                    "curr_event": curr.event_id,
                    "prev_sog": f"{prev.away_sog}-{prev.home_sog}",
                    "curr_sog": f"{curr.away_sog}-{curr.home_sog}",
                }
            )

    if decreases:
        return [
            make_failed(
                rule_name="pbp_sog_progression",
                source_type=SOURCE_PBP,
                message=f"SOG decreased {len(decreases)} time(s) during game",
                severity="warning",
                details={
                    "decreases": decreases[:10],  # Limit to first 10
                    "total_decreases": len(decreases),
                },
                entity_id=entity_id,
            )
        ]

    return [
        make_passed(
            rule_name="pbp_sog_progression",
            source_type=SOURCE_PBP,
            message="SOG progression validation passed",
            entity_id=entity_id,
        )
    ]


def _validate_period_sequence(
    events: list[GameEvent], entity_id: str, is_playoff: bool
) -> list[InternalValidationResult]:
    """Validate that periods appear in sequential order.

    Args:
        events: List of game events
        entity_id: Game ID for context
        is_playoff: Whether this is a playoff game

    Returns:
        List containing single validation result
    """
    if not events:
        return [
            make_passed(
                rule_name="pbp_period_sequence",
                source_type=SOURCE_PBP,
                message="Period sequence validation passed (no events)",
                entity_id=entity_id,
            )
        ]

    periods_seen = sorted({e.period for e in events})

    # Check for gaps
    gaps = []
    for i in range(1, len(periods_seen)):
        if periods_seen[i] - periods_seen[i - 1] > 1:
            gaps.append((periods_seen[i - 1], periods_seen[i]))

    # Check for invalid periods
    max_period = PERIOD_MAX_PLAYOFF if is_playoff else PERIOD_SO
    invalid_periods = [p for p in periods_seen if p < PERIOD_MIN or p > max_period]

    if gaps or invalid_periods:
        return [
            make_failed(
                rule_name="pbp_period_sequence",
                source_type=SOURCE_PBP,
                message=f"Period sequence issues: gaps={len(gaps)}, invalid={len(invalid_periods)}",
                severity="warning",
                details={
                    "periods_seen": periods_seen,
                    "gaps": gaps,
                    "invalid_periods": invalid_periods,
                    "max_period": max_period,
                },
                entity_id=entity_id,
            )
        ]

    return [
        make_passed(
            rule_name="pbp_period_sequence",
            source_type=SOURCE_PBP,
            message="Period sequence validation passed",
            entity_id=entity_id,
        )
    ]
