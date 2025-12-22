"""Shift chart internal consistency validation rules.

Validates that shift chart data is internally consistent:
- End time > start time
- Duration matches time difference
- No overlapping shifts for same player
- Valid period numbers
- Sequential shift numbers per player
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

from nhl_api.validation.constants import PERIOD_MAX_PLAYOFF, PERIOD_MIN, SOURCE_SHIFTS
from nhl_api.validation.results import (
    InternalValidationResult,
    make_failed,
    make_passed,
)

if TYPE_CHECKING:
    from nhl_api.models.shifts import ParsedShiftChart, ShiftRecord

# Regex pattern for time format (MM:SS or M:SS)
TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")

# Tolerance for duration calculation (seconds)
DURATION_TOLERANCE = 2


def validate_shift_chart(shifts: ParsedShiftChart) -> list[InternalValidationResult]:
    """Validate all internal consistency rules for shift chart data.

    Args:
        shifts: Parsed shift chart data

    Returns:
        List of validation results for all rules
    """
    results: list[InternalValidationResult] = []
    entity_id = str(shifts.game_id)

    # Skip goal events for most validations
    regular_shifts = [s for s in shifts.shifts if not s.is_goal_event]

    # Validate individual shifts
    for shift in regular_shifts:
        results.extend(_validate_shift(shift, entity_id))

    # Validate no overlapping shifts per player
    results.extend(_validate_no_overlaps(regular_shifts, entity_id))

    # Validate sequential shift numbers per player
    results.extend(_validate_shift_sequence(regular_shifts, entity_id))

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


def _validate_shift(
    shift: ShiftRecord, entity_id: str
) -> list[InternalValidationResult]:
    """Validate internal consistency for a single shift.

    Args:
        shift: Shift record
        entity_id: Game ID for context

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    shift_context = (
        f"shift {shift.shift_id} (player {shift.full_name}, period {shift.period})"
    )

    # Parse times
    start_seconds = _parse_time_to_seconds(shift.start_time)
    end_seconds = _parse_time_to_seconds(shift.end_time)

    # Rule: End time > start time (within period)
    if start_seconds is not None and end_seconds is not None:
        # Note: In hockey, time counts UP from 0:00 to 20:00
        # So end time should be >= start time
        if end_seconds < start_seconds:
            results.append(
                make_failed(
                    rule_name="shift_end_after_start",
                    source_type=SOURCE_SHIFTS,
                    message=f"{shift_context}: end_time ({shift.end_time}) < start_time ({shift.start_time})",
                    severity="error",
                    details={
                        "shift_id": shift.shift_id,
                        "player_id": shift.player_id,
                        "player_name": shift.full_name,
                        "period": shift.period,
                        "start_time": shift.start_time,
                        "end_time": shift.end_time,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="shift_end_after_start",
                    source_type=SOURCE_SHIFTS,
                    message=f"{shift_context}: end > start validation passed",
                    entity_id=entity_id,
                )
            )

        # Rule: Duration matches time difference (with tolerance)
        calculated_duration = end_seconds - start_seconds
        if abs(calculated_duration - shift.duration_seconds) > DURATION_TOLERANCE:
            results.append(
                make_failed(
                    rule_name="shift_duration_matches",
                    source_type=SOURCE_SHIFTS,
                    message=f"{shift_context}: duration ({shift.duration_seconds}s) != calculated ({calculated_duration}s)",
                    severity="warning",
                    details={
                        "shift_id": shift.shift_id,
                        "player_id": shift.player_id,
                        "duration_seconds": shift.duration_seconds,
                        "calculated_duration": calculated_duration,
                        "start_time": shift.start_time,
                        "end_time": shift.end_time,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="shift_duration_matches",
                    source_type=SOURCE_SHIFTS,
                    message=f"{shift_context}: duration validation passed",
                    entity_id=entity_id,
                )
            )
    else:
        # Invalid time format
        if start_seconds is None:
            results.append(
                make_failed(
                    rule_name="shift_end_after_start",
                    source_type=SOURCE_SHIFTS,
                    message=f"{shift_context}: invalid start_time format '{shift.start_time}'",
                    severity="warning",
                    details={
                        "shift_id": shift.shift_id,
                        "start_time": shift.start_time,
                    },
                    entity_id=entity_id,
                )
            )
        if end_seconds is None:
            results.append(
                make_failed(
                    rule_name="shift_end_after_start",
                    source_type=SOURCE_SHIFTS,
                    message=f"{shift_context}: invalid end_time format '{shift.end_time}'",
                    severity="warning",
                    details={"shift_id": shift.shift_id, "end_time": shift.end_time},
                    entity_id=entity_id,
                )
            )

    # Rule: Valid period number
    if not (PERIOD_MIN <= shift.period <= PERIOD_MAX_PLAYOFF):
        results.append(
            make_failed(
                rule_name="shift_period_valid",
                source_type=SOURCE_SHIFTS,
                message=f"{shift_context}: period {shift.period} outside valid range [{PERIOD_MIN}, {PERIOD_MAX_PLAYOFF}]",
                severity="warning",
                details={
                    "shift_id": shift.shift_id,
                    "period": shift.period,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="shift_period_valid",
                source_type=SOURCE_SHIFTS,
                message=f"{shift_context}: period validation passed",
                entity_id=entity_id,
            )
        )

    return results


def _validate_no_overlaps(
    shifts: list[ShiftRecord], entity_id: str
) -> list[InternalValidationResult]:
    """Validate that no player has overlapping shifts in the same period.

    Args:
        shifts: List of shift records
        entity_id: Game ID for context

    Returns:
        List containing single validation result
    """
    # Group shifts by player and period
    player_period_shifts: dict[tuple[int, int], list[ShiftRecord]] = defaultdict(list)
    for shift in shifts:
        key = (shift.player_id, shift.period)
        player_period_shifts[key].append(shift)

    overlaps = []
    for (player_id, period), period_shifts in player_period_shifts.items():
        # Sort by start time
        sorted_shifts = sorted(
            period_shifts,
            key=lambda s: _parse_time_to_seconds(s.start_time) or 0,
        )

        for i in range(1, len(sorted_shifts)):
            prev = sorted_shifts[i - 1]
            curr = sorted_shifts[i]

            prev_end = _parse_time_to_seconds(prev.end_time)
            curr_start = _parse_time_to_seconds(curr.start_time)

            if prev_end is not None and curr_start is not None:
                if curr_start < prev_end:
                    overlaps.append(
                        {
                            "player_id": player_id,
                            "period": period,
                            "shift1_end": prev.end_time,
                            "shift2_start": curr.start_time,
                        }
                    )

    if overlaps:
        return [
            make_failed(
                rule_name="shift_no_overlap",
                source_type=SOURCE_SHIFTS,
                message=f"Found {len(overlaps)} overlapping shift pair(s)",
                severity="warning",
                details={
                    "overlaps": overlaps[:10],  # Limit to first 10
                    "total_overlaps": len(overlaps),
                },
                entity_id=entity_id,
            )
        ]

    return [
        make_passed(
            rule_name="shift_no_overlap",
            source_type=SOURCE_SHIFTS,
            message="No overlapping shifts found",
            entity_id=entity_id,
        )
    ]


def _validate_shift_sequence(
    shifts: list[ShiftRecord], entity_id: str
) -> list[InternalValidationResult]:
    """Validate that shift numbers are sequential per player.

    Args:
        shifts: List of shift records
        entity_id: Game ID for context

    Returns:
        List containing single validation result
    """
    # Group shifts by player
    player_shifts: dict[int, list[ShiftRecord]] = defaultdict(list)
    for shift in shifts:
        player_shifts[shift.player_id].append(shift)

    sequence_issues = []
    for player_id, player_shift_list in player_shifts.items():
        # Sort by shift number
        sorted_shifts = sorted(player_shift_list, key=lambda s: s.shift_number)
        shift_numbers = [s.shift_number for s in sorted_shifts]

        # Check for gaps or duplicates
        expected = list(range(shift_numbers[0], shift_numbers[-1] + 1))
        if shift_numbers != expected:
            sequence_issues.append(
                {
                    "player_id": player_id,
                    "player_name": sorted_shifts[0].full_name
                    if sorted_shifts
                    else "Unknown",
                    "shift_numbers": shift_numbers[:20],  # Limit display
                }
            )

    if sequence_issues:
        return [
            make_failed(
                rule_name="shift_sequential_numbers",
                source_type=SOURCE_SHIFTS,
                message=f"Found {len(sequence_issues)} player(s) with non-sequential shift numbers",
                severity="info",
                details={
                    "issues": sequence_issues[:10],  # Limit to first 10
                    "total_issues": len(sequence_issues),
                },
                entity_id=entity_id,
            )
        ]

    return [
        make_passed(
            rule_name="shift_sequential_numbers",
            source_type=SOURCE_SHIFTS,
            message="Shift numbers are sequential for all players",
            entity_id=entity_id,
        )
    ]
