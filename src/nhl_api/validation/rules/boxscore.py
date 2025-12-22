"""Boxscore internal consistency validation rules.

Validates that boxscore data is internally consistent:
- Player points = goals + assists
- Team goals = sum of player goals
- Shots >= goals
- PP/SH goals <= total goals
- Valid percentage ranges
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from nhl_api.validation.constants import (
    PCT_MAX_1,
    PCT_MAX_100,
    PCT_MIN,
    SOURCE_BOXSCORE,
)
from nhl_api.validation.results import (
    InternalValidationResult,
    make_failed,
    make_passed,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.nhl_json.boxscore import (
        GoalieStats,
        ParsedBoxscore,
        SkaterStats,
        TeamBoxscore,
    )

# Regex pattern for TOI format (MM:SS or M:SS)
TOI_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")


def validate_boxscore(boxscore: ParsedBoxscore) -> list[InternalValidationResult]:
    """Validate all internal consistency rules for boxscore data.

    Args:
        boxscore: Parsed boxscore data

    Returns:
        List of validation results for all rules
    """
    results: list[InternalValidationResult] = []
    entity_id = str(boxscore.game_id)

    # Validate each skater
    all_skaters = boxscore.home_skaters + boxscore.away_skaters
    for skater in all_skaters:
        results.extend(_validate_skater(skater, entity_id))

    # Validate each goalie
    all_goalies = boxscore.home_goalies + boxscore.away_goalies
    for goalie in all_goalies:
        results.extend(_validate_goalie(goalie, entity_id))

    # Validate team-level consistency
    results.extend(
        _validate_team_goals_sum(
            boxscore.home_team, boxscore.home_skaters, "home", entity_id
        )
    )
    results.extend(
        _validate_team_goals_sum(
            boxscore.away_team, boxscore.away_skaters, "away", entity_id
        )
    )

    # Validate shots >= goals for each team
    results.append(_validate_shots_gte_goals(boxscore.home_team, "home", entity_id))
    results.append(_validate_shots_gte_goals(boxscore.away_team, "away", entity_id))

    return results


def _validate_skater(
    skater: SkaterStats, entity_id: str
) -> list[InternalValidationResult]:
    """Validate internal consistency for a single skater.

    Args:
        skater: Skater statistics
        entity_id: Game ID for context

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    player_context = f"player {skater.name} (#{skater.sweater_number})"

    # Rule: points = goals + assists
    expected_points = skater.goals + skater.assists
    if skater.points != expected_points:
        results.append(
            make_failed(
                rule_name="boxscore_player_points",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: points ({skater.points}) != goals + assists ({expected_points})",
                severity="error",
                details={
                    "player_id": skater.player_id,
                    "player_name": skater.name,
                    "points": skater.points,
                    "goals": skater.goals,
                    "assists": skater.assists,
                    "expected_points": expected_points,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="boxscore_player_points",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: points validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: PP goals + SH goals <= total goals
    special_teams_goals = skater.power_play_goals + skater.shorthanded_goals
    if special_teams_goals > skater.goals:
        results.append(
            make_failed(
                rule_name="boxscore_special_teams_goals",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: PP+SH goals ({special_teams_goals}) > total goals ({skater.goals})",
                severity="error",
                details={
                    "player_id": skater.player_id,
                    "player_name": skater.name,
                    "power_play_goals": skater.power_play_goals,
                    "shorthanded_goals": skater.shorthanded_goals,
                    "total_goals": skater.goals,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="boxscore_special_teams_goals",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: special teams goals validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: faceoff_pct in valid range (0-100)
    # Note: Players who took no faceoffs may have 0.0
    if not (PCT_MIN <= skater.faceoff_pct <= PCT_MAX_100):
        results.append(
            make_failed(
                rule_name="boxscore_faceoff_pct_range",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: faceoff_pct ({skater.faceoff_pct}) outside valid range [0-100]",
                severity="warning",
                details={
                    "player_id": skater.player_id,
                    "player_name": skater.name,
                    "faceoff_pct": skater.faceoff_pct,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="boxscore_faceoff_pct_range",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: faceoff_pct validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: TOI is valid MM:SS format
    if not TOI_PATTERN.match(skater.toi):
        results.append(
            make_failed(
                rule_name="boxscore_toi_format",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: TOI '{skater.toi}' is not valid MM:SS format",
                severity="info",
                details={
                    "player_id": skater.player_id,
                    "player_name": skater.name,
                    "toi": skater.toi,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="boxscore_toi_format",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: TOI format validation passed",
                entity_id=entity_id,
            )
        )

    return results


def _validate_goalie(
    goalie: GoalieStats, entity_id: str
) -> list[InternalValidationResult]:
    """Validate internal consistency for a single goalie.

    Args:
        goalie: Goalie statistics
        entity_id: Game ID for context

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    player_context = f"goalie {goalie.name} (#{goalie.sweater_number})"

    # Rule: save_pct in valid range (0.0-1.0)
    # Note: Goalies with no shots may have 0.0
    if not (PCT_MIN <= goalie.save_pct <= PCT_MAX_1):
        results.append(
            make_failed(
                rule_name="boxscore_save_pct_range",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: save_pct ({goalie.save_pct}) outside valid range [0-1]",
                severity="warning",
                details={
                    "player_id": goalie.player_id,
                    "player_name": goalie.name,
                    "save_pct": goalie.save_pct,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="boxscore_save_pct_range",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: save_pct validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: saves + goals_against = shots_against
    calculated_shots = goalie.saves + goalie.goals_against
    if calculated_shots != goalie.shots_against:
        results.append(
            make_failed(
                rule_name="boxscore_goalie_shots_math",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: saves + GA ({calculated_shots}) != shots_against ({goalie.shots_against})",
                severity="error",
                details={
                    "player_id": goalie.player_id,
                    "player_name": goalie.name,
                    "saves": goalie.saves,
                    "goals_against": goalie.goals_against,
                    "shots_against": goalie.shots_against,
                    "calculated_shots": calculated_shots,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="boxscore_goalie_shots_math",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: goalie shots math validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: TOI is valid MM:SS format
    if not TOI_PATTERN.match(goalie.toi):
        results.append(
            make_failed(
                rule_name="boxscore_toi_format",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: TOI '{goalie.toi}' is not valid MM:SS format",
                severity="info",
                details={
                    "player_id": goalie.player_id,
                    "player_name": goalie.name,
                    "toi": goalie.toi,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="boxscore_toi_format",
                source_type=SOURCE_BOXSCORE,
                message=f"{player_context}: TOI format validation passed",
                entity_id=entity_id,
            )
        )

    return results


def _validate_team_goals_sum(
    team: TeamBoxscore,
    skaters: list[SkaterStats],
    side: str,
    entity_id: str,
) -> list[InternalValidationResult]:
    """Validate that player goals sum to team score.

    Args:
        team: Team boxscore data
        skaters: List of skater stats for the team
        side: "home" or "away"
        entity_id: Game ID for context

    Returns:
        List containing single validation result
    """
    player_goals_sum = sum(s.goals for s in skaters)

    if player_goals_sum != team.score:
        return [
            make_failed(
                rule_name="boxscore_team_goals_sum",
                source_type=SOURCE_BOXSCORE,
                message=f"{side} team: sum of player goals ({player_goals_sum}) != team score ({team.score})",
                severity="error",
                details={
                    "side": side,
                    "team_abbrev": team.abbrev,
                    "team_score": team.score,
                    "player_goals_sum": player_goals_sum,
                    "player_count": len(skaters),
                },
                entity_id=entity_id,
            )
        ]
    return [
        make_passed(
            rule_name="boxscore_team_goals_sum",
            source_type=SOURCE_BOXSCORE,
            message=f"{side} team: team goals sum validation passed",
            entity_id=entity_id,
        )
    ]


def _validate_shots_gte_goals(
    team: TeamBoxscore,
    side: str,
    entity_id: str,
) -> InternalValidationResult:
    """Validate that team shots >= team goals (can't score without shooting).

    Args:
        team: Team boxscore data
        side: "home" or "away"
        entity_id: Game ID for context

    Returns:
        Single validation result
    """
    if team.shots_on_goal < team.score:
        return make_failed(
            rule_name="boxscore_shots_gte_goals",
            source_type=SOURCE_BOXSCORE,
            message=f"{side} team: shots ({team.shots_on_goal}) < goals ({team.score})",
            severity="warning",
            details={
                "side": side,
                "team_abbrev": team.abbrev,
                "shots_on_goal": team.shots_on_goal,
                "score": team.score,
            },
            entity_id=entity_id,
        )
    return make_passed(
        rule_name="boxscore_shots_gte_goals",
        source_type=SOURCE_BOXSCORE,
        message=f"{side} team: shots >= goals validation passed",
        entity_id=entity_id,
    )
