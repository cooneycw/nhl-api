"""Cross-source validation rules for JSON API data.

Validates consistency across multiple JSON API sources for the same game:
- Goals: PBP events vs Boxscore scores
- Shots: PBP shot events vs Boxscore team shots
- TOI: Shift chart vs Boxscore player TOI
- Shift count: Shift chart vs Boxscore player shifts
- Final score: Schedule vs Boxscore scores

Each rule compares data from two sources and returns validation results.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from nhl_api.validation.constants import (
    CROSS_SOURCE_SHIFT_COUNT_TOLERANCE,
    CROSS_SOURCE_SHOT_TOLERANCE,
    SOURCE_CROSS,
    TOI_TOLERANCE_SECONDS,
)
from nhl_api.validation.results import (
    InternalValidationResult,
    make_failed,
    make_passed,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.nhl_json.boxscore import (
        ParsedBoxscore,
        SkaterStats,
    )
    from nhl_api.downloaders.sources.nhl_json.play_by_play import ParsedPlayByPlay
    from nhl_api.downloaders.sources.nhl_json.schedule import GameInfo
    from nhl_api.models.shifts import ParsedShiftChart

# Regex pattern for TOI format (MM:SS or M:SS)
TOI_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")

# Period type for shootout - goals in shootout don't count toward team score
PERIOD_TYPE_SHOOTOUT = "SO"


def _toi_to_seconds(toi: str) -> int | None:
    """Convert TOI string (MM:SS) to seconds.

    Args:
        toi: Time on ice in MM:SS format

    Returns:
        TOI in seconds, or None if format is invalid
    """
    match = TOI_PATTERN.match(toi)
    if not match:
        return None
    minutes, seconds = int(match.group(1)), int(match.group(2))
    return minutes * 60 + seconds


def validate_goals_pbp_vs_boxscore(
    pbp: ParsedPlayByPlay,
    boxscore: ParsedBoxscore,
) -> list[InternalValidationResult]:
    """Validate goals match between PBP events and Boxscore scores.

    Counts goal events in PBP (excluding shootout) and compares to team scores
    in the boxscore. Goals must match exactly.

    Args:
        pbp: Parsed play-by-play data
        boxscore: Parsed boxscore data

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(boxscore.game_id)

    # Count goals from PBP (excluding shootout goals)
    home_goals_pbp = 0
    away_goals_pbp = 0

    for event in pbp.events:
        if event.event_type != "goal":
            continue
        # Skip shootout goals - they don't count toward final score
        if event.period_type == PERIOD_TYPE_SHOOTOUT:
            continue

        if event.event_owner_team_id == pbp.home_team_id:
            home_goals_pbp += 1
        elif event.event_owner_team_id == pbp.away_team_id:
            away_goals_pbp += 1

    # Get boxscore scores
    home_goals_box = boxscore.home_team.score
    away_goals_box = boxscore.away_team.score

    # Validate home team goals
    if home_goals_pbp == home_goals_box:
        results.append(
            make_passed(
                rule_name="cross_source_pbp_boxscore_goals_home",
                source_type=SOURCE_CROSS,
                message=f"Home team goals match: PBP={home_goals_pbp}, Boxscore={home_goals_box}",
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_failed(
                rule_name="cross_source_pbp_boxscore_goals_home",
                source_type=SOURCE_CROSS,
                message=f"Home team goals mismatch: PBP={home_goals_pbp}, Boxscore={home_goals_box}",
                severity="error",
                details={
                    "home_team_id": pbp.home_team_id,
                    "home_team_abbrev": pbp.home_team_abbrev,
                    "pbp_goals": home_goals_pbp,
                    "boxscore_goals": home_goals_box,
                    "difference": home_goals_pbp - home_goals_box,
                },
                entity_id=entity_id,
            )
        )

    # Validate away team goals
    if away_goals_pbp == away_goals_box:
        results.append(
            make_passed(
                rule_name="cross_source_pbp_boxscore_goals_away",
                source_type=SOURCE_CROSS,
                message=f"Away team goals match: PBP={away_goals_pbp}, Boxscore={away_goals_box}",
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_failed(
                rule_name="cross_source_pbp_boxscore_goals_away",
                source_type=SOURCE_CROSS,
                message=f"Away team goals mismatch: PBP={away_goals_pbp}, Boxscore={away_goals_box}",
                severity="error",
                details={
                    "away_team_id": pbp.away_team_id,
                    "away_team_abbrev": pbp.away_team_abbrev,
                    "pbp_goals": away_goals_pbp,
                    "boxscore_goals": away_goals_box,
                    "difference": away_goals_pbp - away_goals_box,
                },
                entity_id=entity_id,
            )
        )

    return results


def validate_shots_pbp_vs_boxscore(
    pbp: ParsedPlayByPlay,
    boxscore: ParsedBoxscore,
    tolerance: int = CROSS_SOURCE_SHOT_TOLERANCE,
) -> list[InternalValidationResult]:
    """Validate shots approximately match between PBP and Boxscore.

    Counts shot-on-goal and goal events in PBP and compares to team shots
    in the boxscore. Allows a tolerance for timing edge cases.

    Args:
        pbp: Parsed play-by-play data
        boxscore: Parsed boxscore data
        tolerance: Maximum allowed shot difference (default 2)

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(boxscore.game_id)

    # Count shots from PBP (shot-on-goal + goal = total shots on goal)
    home_shots_pbp = 0
    away_shots_pbp = 0

    for event in pbp.events:
        # Count shots-on-goal and goals (both count as SOG)
        if event.event_type not in ("shot-on-goal", "goal"):
            continue
        # Skip shootout - not counted in regular SOG
        if event.period_type == PERIOD_TYPE_SHOOTOUT:
            continue

        if event.event_owner_team_id == pbp.home_team_id:
            home_shots_pbp += 1
        elif event.event_owner_team_id == pbp.away_team_id:
            away_shots_pbp += 1

    # Get boxscore shots
    home_shots_box = boxscore.home_team.shots_on_goal
    away_shots_box = boxscore.away_team.shots_on_goal

    # Validate home team shots
    home_diff = abs(home_shots_pbp - home_shots_box)
    if home_diff == 0:
        results.append(
            make_passed(
                rule_name="cross_source_pbp_boxscore_shots_home",
                source_type=SOURCE_CROSS,
                message=f"Home team shots match exactly: {home_shots_pbp}",
                entity_id=entity_id,
            )
        )
    elif home_diff <= tolerance:
        results.append(
            make_passed(
                rule_name="cross_source_pbp_boxscore_shots_home",
                source_type=SOURCE_CROSS,
                message=f"Home team shots within tolerance: PBP={home_shots_pbp}, Box={home_shots_box} (diff={home_diff})",
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_failed(
                rule_name="cross_source_pbp_boxscore_shots_home",
                source_type=SOURCE_CROSS,
                message=f"Home team shots outside tolerance: PBP={home_shots_pbp}, Box={home_shots_box} (diff={home_diff})",
                severity="warning",
                details={
                    "home_team_id": pbp.home_team_id,
                    "home_team_abbrev": pbp.home_team_abbrev,
                    "pbp_shots": home_shots_pbp,
                    "boxscore_shots": home_shots_box,
                    "difference": home_diff,
                    "tolerance": tolerance,
                },
                entity_id=entity_id,
            )
        )

    # Validate away team shots
    away_diff = abs(away_shots_pbp - away_shots_box)
    if away_diff == 0:
        results.append(
            make_passed(
                rule_name="cross_source_pbp_boxscore_shots_away",
                source_type=SOURCE_CROSS,
                message=f"Away team shots match exactly: {away_shots_pbp}",
                entity_id=entity_id,
            )
        )
    elif away_diff <= tolerance:
        results.append(
            make_passed(
                rule_name="cross_source_pbp_boxscore_shots_away",
                source_type=SOURCE_CROSS,
                message=f"Away team shots within tolerance: PBP={away_shots_pbp}, Box={away_shots_box} (diff={away_diff})",
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_failed(
                rule_name="cross_source_pbp_boxscore_shots_away",
                source_type=SOURCE_CROSS,
                message=f"Away team shots outside tolerance: PBP={away_shots_pbp}, Box={away_shots_box} (diff={away_diff})",
                severity="warning",
                details={
                    "away_team_id": pbp.away_team_id,
                    "away_team_abbrev": pbp.away_team_abbrev,
                    "pbp_shots": away_shots_pbp,
                    "boxscore_shots": away_shots_box,
                    "difference": away_diff,
                    "tolerance": tolerance,
                },
                entity_id=entity_id,
            )
        )

    return results


def validate_toi_shifts_vs_boxscore(
    shifts: ParsedShiftChart,
    boxscore: ParsedBoxscore,
    tolerance_seconds: int = TOI_TOLERANCE_SECONDS,
) -> list[InternalValidationResult]:
    """Validate player TOI matches between Shift Chart and Boxscore.

    For each skater in the boxscore, compares their TOI from shift chart
    calculations with the TOI reported in the boxscore.

    Args:
        shifts: Parsed shift chart data
        boxscore: Parsed boxscore data
        tolerance_seconds: Maximum allowed TOI difference in seconds (default 5)

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(boxscore.game_id)

    # Get all skaters from boxscore
    all_skaters: list[SkaterStats] = boxscore.home_skaters + boxscore.away_skaters

    players_checked = 0
    players_matched = 0
    players_mismatched: list[dict[str, object]] = []

    for skater in all_skaters:
        # Parse boxscore TOI
        boxscore_toi = _toi_to_seconds(skater.toi)
        if boxscore_toi is None:
            # Skip players with invalid TOI format
            continue

        # Get shift-based TOI
        shift_toi = shifts.get_player_toi(skater.player_id)

        players_checked += 1
        toi_diff = abs(shift_toi - boxscore_toi)

        if toi_diff <= tolerance_seconds:
            players_matched += 1
        else:
            players_mismatched.append(
                {
                    "player_id": skater.player_id,
                    "player_name": skater.name,
                    "shift_toi_seconds": shift_toi,
                    "boxscore_toi_seconds": boxscore_toi,
                    "difference_seconds": toi_diff,
                }
            )

    # Create summary result
    if players_checked == 0:
        results.append(
            make_passed(
                rule_name="cross_source_shifts_boxscore_toi",
                source_type=SOURCE_CROSS,
                message="No players to validate TOI",
                entity_id=entity_id,
            )
        )
    elif not players_mismatched:
        results.append(
            make_passed(
                rule_name="cross_source_shifts_boxscore_toi",
                source_type=SOURCE_CROSS,
                message=f"All {players_matched} player TOI values match within {tolerance_seconds}s tolerance",
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_failed(
                rule_name="cross_source_shifts_boxscore_toi",
                source_type=SOURCE_CROSS,
                message=f"{len(players_mismatched)} of {players_checked} players have TOI mismatch beyond {tolerance_seconds}s",
                severity="warning",
                details={
                    "players_checked": players_checked,
                    "players_matched": players_matched,
                    "players_mismatched": len(players_mismatched),
                    "tolerance_seconds": tolerance_seconds,
                    "mismatched_players": players_mismatched[:5],  # First 5 for brevity
                },
                entity_id=entity_id,
            )
        )

    return results


def validate_shift_count_shifts_vs_boxscore(
    shifts: ParsedShiftChart,
    boxscore: ParsedBoxscore,
    tolerance: int = CROSS_SOURCE_SHIFT_COUNT_TOLERANCE,
) -> list[InternalValidationResult]:
    """Validate player shift counts match between Shift Chart and Boxscore.

    For each skater in the boxscore, compares their shift count from the
    shift chart with the shifts reported in the boxscore.

    Args:
        shifts: Parsed shift chart data
        boxscore: Parsed boxscore data
        tolerance: Maximum allowed shift count difference (default 1)

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(boxscore.game_id)

    # Get all skaters from boxscore
    all_skaters: list[SkaterStats] = boxscore.home_skaters + boxscore.away_skaters

    players_checked = 0
    players_matched = 0
    players_mismatched: list[dict[str, object]] = []

    for skater in all_skaters:
        # Get shift counts from both sources
        boxscore_shifts = skater.shifts
        shift_chart_shifts = shifts.get_player_shift_count(skater.player_id)

        players_checked += 1
        shift_diff = abs(shift_chart_shifts - boxscore_shifts)

        if shift_diff <= tolerance:
            players_matched += 1
        else:
            players_mismatched.append(
                {
                    "player_id": skater.player_id,
                    "player_name": skater.name,
                    "shift_chart_shifts": shift_chart_shifts,
                    "boxscore_shifts": boxscore_shifts,
                    "difference": shift_diff,
                }
            )

    # Create summary result
    if players_checked == 0:
        results.append(
            make_passed(
                rule_name="cross_source_shifts_boxscore_shift_count",
                source_type=SOURCE_CROSS,
                message="No players to validate shift count",
                entity_id=entity_id,
            )
        )
    elif not players_mismatched:
        results.append(
            make_passed(
                rule_name="cross_source_shifts_boxscore_shift_count",
                source_type=SOURCE_CROSS,
                message=f"All {players_matched} player shift counts match within tolerance of {tolerance}",
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_failed(
                rule_name="cross_source_shifts_boxscore_shift_count",
                source_type=SOURCE_CROSS,
                message=f"{len(players_mismatched)} of {players_checked} players have shift count mismatch",
                severity="warning",
                details={
                    "players_checked": players_checked,
                    "players_matched": players_matched,
                    "players_mismatched": len(players_mismatched),
                    "tolerance": tolerance,
                    "mismatched_players": players_mismatched[:5],  # First 5 for brevity
                },
                entity_id=entity_id,
            )
        )

    return results


def validate_final_score_schedule_vs_boxscore(
    schedule: GameInfo,
    boxscore: ParsedBoxscore,
) -> list[InternalValidationResult]:
    """Validate final score matches between Schedule and Boxscore.

    Compares the final scores reported in the schedule with those in the
    boxscore. Scores must match exactly.

    Args:
        schedule: Game info from schedule
        boxscore: Parsed boxscore data

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(boxscore.game_id)

    # Get scores from both sources
    # Handle nullable schedule scores (pre-game has None)
    schedule_home = schedule.home_score if schedule.home_score is not None else -1
    schedule_away = schedule.away_score if schedule.away_score is not None else -1
    boxscore_home = boxscore.home_team.score
    boxscore_away = boxscore.away_team.score

    # Check if schedule has valid scores
    if schedule_home < 0 or schedule_away < 0:
        results.append(
            make_passed(
                rule_name="cross_source_schedule_boxscore_score",
                source_type=SOURCE_CROSS,
                message="Schedule scores not available (pre-game or incomplete)",
                entity_id=entity_id,
            )
        )
        return results

    # Validate scores match
    home_match = schedule_home == boxscore_home
    away_match = schedule_away == boxscore_away

    if home_match and away_match:
        results.append(
            make_passed(
                rule_name="cross_source_schedule_boxscore_score",
                source_type=SOURCE_CROSS,
                message=f"Final score matches: {boxscore_away}-{boxscore_home}",
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_failed(
                rule_name="cross_source_schedule_boxscore_score",
                source_type=SOURCE_CROSS,
                message=f"Score mismatch: Schedule={schedule_away}-{schedule_home}, Boxscore={boxscore_away}-{boxscore_home}",
                severity="error",
                details={
                    "schedule_home_score": schedule_home,
                    "schedule_away_score": schedule_away,
                    "boxscore_home_score": boxscore_home,
                    "boxscore_away_score": boxscore_away,
                    "home_match": home_match,
                    "away_match": away_match,
                },
                entity_id=entity_id,
            )
        )

    return results
