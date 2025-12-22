"""HTML report internal consistency validation rules.

Validates that HTML report data is internally consistent:
- Event Summary: player stats sum to team totals
- Game Summary: period goals sum to final score
- Faceoff Summary: wins + losses = total
- Shot Summary: zone shots sum to total
- Time on Ice: shift durations sum to period TOI
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nhl_api.validation.constants import (
    SOURCE_HTML_ES,
    SOURCE_HTML_FS,
    SOURCE_HTML_GS,
    SOURCE_HTML_SS,
    SOURCE_HTML_TOI,
    TOI_TOLERANCE_SECONDS,
)
from nhl_api.validation.results import (
    InternalValidationResult,
    make_failed,
    make_passed,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.html.event_summary import (
        ParsedEventSummary,
        TeamEventSummary,
    )
    from nhl_api.downloaders.sources.html.faceoff_summary import (
        ParsedFaceoffSummary,
        TeamFaceoffSummary,
    )
    from nhl_api.downloaders.sources.html.game_summary import (
        ParsedGameSummary,
    )
    from nhl_api.downloaders.sources.html.shot_summary import (
        ParsedShotSummary,
        TeamShotSummary,
    )
    from nhl_api.downloaders.sources.html.time_on_ice import (
        ParsedTimeOnIce,
        PlayerTOI,
    )


# =============================================================================
# Event Summary (ES) Validation
# =============================================================================


def validate_event_summary(
    event_summary: ParsedEventSummary,
) -> list[InternalValidationResult]:
    """Validate internal consistency of HTML Event Summary.

    Checks that player stats sum to team totals.

    Args:
        event_summary: Parsed event summary data

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(event_summary.game_id)

    # Validate each team
    results.extend(_validate_es_team_totals(event_summary.away_team, "away", entity_id))
    results.extend(_validate_es_team_totals(event_summary.home_team, "home", entity_id))

    return results


def _validate_es_team_totals(
    team: TeamEventSummary, side: str, entity_id: str
) -> list[InternalValidationResult]:
    """Validate that player stats sum to team totals.

    Args:
        team: Team event summary
        side: "away" or "home"
        entity_id: Game ID for context

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []

    # Sum player stats (excluding goalies)
    players = team.players
    totals = team.totals

    # Check goals
    player_goals = sum(p.goals for p in players)
    team_goals = totals.get("goals", 0) if totals else 0

    if player_goals != team_goals:
        results.append(
            make_failed(
                rule_name="es_player_sum_goals",
                source_type=SOURCE_HTML_ES,
                message=f"{side} team: sum of player goals ({player_goals}) != team total ({team_goals})",
                severity="error",
                details={
                    "side": side,
                    "player_goals_sum": player_goals,
                    "team_goals": team_goals,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="es_player_sum_goals",
                source_type=SOURCE_HTML_ES,
                message=f"{side} team: goals sum validation passed",
                entity_id=entity_id,
            )
        )

    # Check assists
    player_assists = sum(p.assists for p in players)
    team_assists = totals.get("assists", 0) if totals else 0

    if player_assists != team_assists:
        results.append(
            make_failed(
                rule_name="es_player_sum_assists",
                source_type=SOURCE_HTML_ES,
                message=f"{side} team: sum of player assists ({player_assists}) != team total ({team_assists})",
                severity="error",
                details={
                    "side": side,
                    "player_assists_sum": player_assists,
                    "team_assists": team_assists,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="es_player_sum_assists",
                source_type=SOURCE_HTML_ES,
                message=f"{side} team: assists sum validation passed",
                entity_id=entity_id,
            )
        )

    # Check points = goals + assists for each player
    for player in players:
        expected_points = player.goals + player.assists
        if player.points != expected_points:
            results.append(
                make_failed(
                    rule_name="es_player_points",
                    source_type=SOURCE_HTML_ES,
                    message=f"{side} player {player.name}: points ({player.points}) != G+A ({expected_points})",
                    severity="error",
                    details={
                        "player_name": player.name,
                        "goals": player.goals,
                        "assists": player.assists,
                        "points": player.points,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="es_player_points",
                    source_type=SOURCE_HTML_ES,
                    message=f"{side} player {player.name}: points validation passed",
                    entity_id=entity_id,
                )
            )

    return results


# =============================================================================
# Game Summary (GS) Validation
# =============================================================================


def validate_game_summary(
    game_summary: ParsedGameSummary,
) -> list[InternalValidationResult]:
    """Validate internal consistency of HTML Game Summary.

    Checks that period goals sum to final score.

    Args:
        game_summary: Parsed game summary data

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(game_summary.game_id)

    # Count goals from goals list for each team
    away_goals_from_list = sum(
        1 for g in game_summary.goals if g.team == game_summary.away_team.name
    )
    home_goals_from_list = sum(
        1 for g in game_summary.goals if g.team == game_summary.home_team.name
    )

    # Compare to team info
    if game_summary.away_team.goals != away_goals_from_list:
        results.append(
            make_failed(
                rule_name="gs_goals_count_away",
                source_type=SOURCE_HTML_GS,
                message=f"away team: goals in list ({away_goals_from_list}) != team total ({game_summary.away_team.goals})",
                severity="error",
                details={
                    "goals_in_list": away_goals_from_list,
                    "team_goals": game_summary.away_team.goals,
                    "team_name": game_summary.away_team.name,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="gs_goals_count_away",
                source_type=SOURCE_HTML_GS,
                message="away team: goals count validation passed",
                entity_id=entity_id,
            )
        )

    if game_summary.home_team.goals != home_goals_from_list:
        results.append(
            make_failed(
                rule_name="gs_goals_count_home",
                source_type=SOURCE_HTML_GS,
                message=f"home team: goals in list ({home_goals_from_list}) != team total ({game_summary.home_team.goals})",
                severity="error",
                details={
                    "goals_in_list": home_goals_from_list,
                    "team_goals": game_summary.home_team.goals,
                    "team_name": game_summary.home_team.name,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="gs_goals_count_home",
                source_type=SOURCE_HTML_GS,
                message="home team: goals count validation passed",
                entity_id=entity_id,
            )
        )

    # Validate goal assists (0-2 per goal)
    for goal in game_summary.goals:
        assist_count = 0
        if goal.assist1:
            assist_count += 1
        if goal.assist2:
            assist_count += 1

        if assist_count > 2:
            results.append(
                make_failed(
                    rule_name="gs_goal_assists",
                    source_type=SOURCE_HTML_GS,
                    message=f"Goal #{goal.goal_number}: has {assist_count} assists (max 2)",
                    severity="error",
                    details={
                        "goal_number": goal.goal_number,
                        "assist_count": assist_count,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="gs_goal_assists",
                    source_type=SOURCE_HTML_GS,
                    message=f"Goal #{goal.goal_number}: assist count validation passed",
                    entity_id=entity_id,
                )
            )

    return results


# =============================================================================
# Faceoff Summary (FS) Validation
# =============================================================================


def validate_faceoff_summary(
    faceoff_summary: ParsedFaceoffSummary,
) -> list[InternalValidationResult]:
    """Validate internal consistency of HTML Faceoff Summary.

    Checks that wins + losses = total for faceoff stats.

    Args:
        faceoff_summary: Parsed faceoff summary data

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(faceoff_summary.game_id)

    # Validate each team
    results.extend(_validate_fs_team(faceoff_summary.away_team, "away", entity_id))
    results.extend(_validate_fs_team(faceoff_summary.home_team, "home", entity_id))

    return results


def _validate_fs_team(
    team: TeamFaceoffSummary, side: str, entity_id: str
) -> list[InternalValidationResult]:
    """Validate faceoff summary for a team.

    Args:
        team: Team faceoff summary
        side: "away" or "home"
        entity_id: Game ID for context

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []

    # Validate totals for each player (check each zone)
    for player in team.players:
        zone_totals = player.totals
        if zone_totals:
            # Check each zone's faceoff math
            for zone_name, zone_stat in [
                ("offensive", zone_totals.offensive),
                ("defensive", zone_totals.defensive),
                ("neutral", zone_totals.neutral),
            ]:
                if zone_stat and zone_stat.total > 0:
                    calculated_total = zone_stat.won + zone_stat.lost
                    if calculated_total != zone_stat.total:
                        results.append(
                            make_failed(
                                rule_name="fs_faceoff_math",
                                source_type=SOURCE_HTML_FS,
                                message=f"{side} player {player.name} {zone_name}: won+lost ({calculated_total}) != total ({zone_stat.total})",
                                severity="error",
                                details={
                                    "player_name": player.name,
                                    "zone": zone_name,
                                    "won": zone_stat.won,
                                    "lost": zone_stat.lost,
                                    "total": zone_stat.total,
                                },
                                entity_id=entity_id,
                            )
                        )
                    else:
                        results.append(
                            make_passed(
                                rule_name="fs_faceoff_math",
                                source_type=SOURCE_HTML_FS,
                                message=f"{side} player {player.name} {zone_name}: faceoff math validation passed",
                                entity_id=entity_id,
                            )
                        )

    return results


# =============================================================================
# Shot Summary (SS) Validation
# =============================================================================


def validate_shot_summary(
    shot_summary: ParsedShotSummary,
) -> list[InternalValidationResult]:
    """Validate internal consistency of HTML Shot Summary.

    Checks that player shots sum to team totals.

    Args:
        shot_summary: Parsed shot summary data

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(shot_summary.game_id)

    # Validate each team
    results.extend(_validate_ss_team(shot_summary.away_team, "away", entity_id))
    results.extend(_validate_ss_team(shot_summary.home_team, "home", entity_id))

    return results


def _validate_ss_team(
    team: TeamShotSummary, side: str, entity_id: str
) -> list[InternalValidationResult]:
    """Validate shot summary for a team.

    Args:
        team: Team shot summary
        side: "away" or "home"
        entity_id: Game ID for context

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []

    # Sum player shots
    player_shots = sum(p.total_shots for p in team.players)

    # Get team total (from TOT period if available)
    team_shots = 0
    for period_stat in team.periods:
        if period_stat.period == "TOT":
            team_shots = period_stat.total.shots
            break

    if team_shots > 0 and player_shots != team_shots:
        results.append(
            make_failed(
                rule_name="ss_player_sum_shots",
                source_type=SOURCE_HTML_SS,
                message=f"{side} team: sum of player shots ({player_shots}) != team total ({team_shots})",
                severity="warning",
                details={
                    "side": side,
                    "player_shots_sum": player_shots,
                    "team_shots": team_shots,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="ss_player_sum_shots",
                source_type=SOURCE_HTML_SS,
                message=f"{side} team: shots sum validation passed",
                entity_id=entity_id,
            )
        )

    # Validate each player's period sums = total
    for player in team.players:
        # Sum shots across all non-TOT periods
        period_sum = 0
        for period_stat in player.periods:
            if period_stat.period != "TOT":
                period_sum += period_stat.total.shots

        if period_sum != player.total_shots:
            results.append(
                make_failed(
                    rule_name="ss_player_period_sum",
                    source_type=SOURCE_HTML_SS,
                    message=f"{side} player {player.name}: period shots ({period_sum}) != total ({player.total_shots})",
                    severity="warning",
                    details={
                        "player_name": player.name,
                        "period_sum": period_sum,
                        "total_shots": player.total_shots,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="ss_player_period_sum",
                    source_type=SOURCE_HTML_SS,
                    message=f"{side} player {player.name}: period sum validation passed",
                    entity_id=entity_id,
                )
            )

    return results


# =============================================================================
# Time on Ice (TH/TV) Validation
# =============================================================================


def validate_time_on_ice(toi: ParsedTimeOnIce) -> list[InternalValidationResult]:
    """Validate internal consistency of HTML Time on Ice.

    Checks that shift durations sum to period TOI.

    Args:
        toi: Parsed time on ice data

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    entity_id = str(toi.game_id)

    # Validate each player
    for player in toi.players:
        results.extend(_validate_toi_player(player, entity_id))

    return results


def _parse_toi_to_seconds(toi_str: str) -> int | None:
    """Parse TOI string (MM:SS) to seconds.

    Args:
        toi_str: Time on ice string

    Returns:
        Total seconds, or None if invalid
    """
    try:
        parts = toi_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, AttributeError):
        pass
    return None


def _validate_toi_player(
    player: PlayerTOI, entity_id: str
) -> list[InternalValidationResult]:
    """Validate time on ice for a single player.

    Args:
        player: Player TOI data
        entity_id: Game ID for context

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []

    # Sum shift durations
    shift_toi_seconds = 0
    for shift in player.shifts_detail:
        shift_duration = _parse_toi_to_seconds(shift.duration)
        if shift_duration is not None:
            shift_toi_seconds += shift_duration

    # Get total TOI from summary
    total_toi_str = player.total_toi
    total_toi_seconds = _parse_toi_to_seconds(total_toi_str)

    if total_toi_seconds is not None:
        diff = abs(shift_toi_seconds - total_toi_seconds)
        if diff > TOI_TOLERANCE_SECONDS:
            results.append(
                make_failed(
                    rule_name="toi_shift_duration_sum",
                    source_type=SOURCE_HTML_TOI,
                    message=f"Player {player.number} {player.name}: shift sum ({shift_toi_seconds}s) != total ({total_toi_seconds}s)",
                    severity="warning",
                    details={
                        "player_number": player.number,
                        "player_name": player.name,
                        "shift_sum_seconds": shift_toi_seconds,
                        "total_toi_seconds": total_toi_seconds,
                        "difference": diff,
                    },
                    entity_id=entity_id,
                )
            )
        else:
            results.append(
                make_passed(
                    rule_name="toi_shift_duration_sum",
                    source_type=SOURCE_HTML_TOI,
                    message=f"Player {player.number} {player.name}: TOI sum validation passed",
                    entity_id=entity_id,
                )
            )
    else:
        results.append(
            make_passed(
                rule_name="toi_shift_duration_sum",
                source_type=SOURCE_HTML_TOI,
                message=f"Player {player.number}: no total TOI to validate",
                entity_id=entity_id,
            )
        )

    return results
