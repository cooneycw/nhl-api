"""Standings internal consistency validation rules.

Validates that standings data is internally consistent:
- GP = W + L + OTL
- Points = W*2 + OTL
- Goal differential = GF - GA
- Win breakdown consistency
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nhl_api.validation.constants import PCT_MAX_100, PCT_MIN, SOURCE_STANDINGS
from nhl_api.validation.results import (
    InternalValidationResult,
    make_failed,
    make_passed,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.nhl_json.standings import (
        ParsedStandings,
        TeamStandings,
    )


def validate_standings(standings: ParsedStandings) -> list[InternalValidationResult]:
    """Validate all internal consistency rules for standings data.

    Args:
        standings: Parsed standings data

    Returns:
        List of validation results for all rules
    """
    results: list[InternalValidationResult] = []
    entity_id = str(standings.season_id)

    for team in standings.standings:
        results.extend(_validate_team_standings(team, entity_id))

    return results


def _validate_team_standings(
    team: TeamStandings, entity_id: str
) -> list[InternalValidationResult]:
    """Validate internal consistency for a single team's standings.

    Args:
        team: Team standings data
        entity_id: Season ID for context

    Returns:
        List of validation results
    """
    results: list[InternalValidationResult] = []
    team_context = f"team {team.team_abbrev}"

    # Rule: GP = W + L + OTL
    calculated_gp = team.wins + team.losses + team.ot_losses
    if team.games_played != calculated_gp:
        results.append(
            make_failed(
                rule_name="standings_gp_sum",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: GP ({team.games_played}) != W+L+OTL ({calculated_gp})",
                severity="error",
                details={
                    "team_abbrev": team.team_abbrev,
                    "games_played": team.games_played,
                    "wins": team.wins,
                    "losses": team.losses,
                    "ot_losses": team.ot_losses,
                    "calculated_gp": calculated_gp,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="standings_gp_sum",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: GP sum validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: Points = W*2 + OTL
    calculated_points = (team.wins * 2) + team.ot_losses
    if team.points != calculated_points:
        results.append(
            make_failed(
                rule_name="standings_points_calc",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: points ({team.points}) != W*2+OTL ({calculated_points})",
                severity="error",
                details={
                    "team_abbrev": team.team_abbrev,
                    "points": team.points,
                    "wins": team.wins,
                    "ot_losses": team.ot_losses,
                    "calculated_points": calculated_points,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="standings_points_calc",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: points calculation validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: Goal differential = GF - GA
    calculated_diff = team.goals_for - team.goals_against
    if team.goal_differential != calculated_diff:
        results.append(
            make_failed(
                rule_name="standings_goal_diff",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: goal_diff ({team.goal_differential}) != GF-GA ({calculated_diff})",
                severity="error",
                details={
                    "team_abbrev": team.team_abbrev,
                    "goal_differential": team.goal_differential,
                    "goals_for": team.goals_for,
                    "goals_against": team.goals_against,
                    "calculated_diff": calculated_diff,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="standings_goal_diff",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: goal differential validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: Wins >= regulation_wins (regulation wins are a subset of total wins)
    if team.wins < team.regulation_wins:
        results.append(
            make_failed(
                rule_name="standings_win_breakdown",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: wins ({team.wins}) < regulation_wins ({team.regulation_wins})",
                severity="warning",
                details={
                    "team_abbrev": team.team_abbrev,
                    "wins": team.wins,
                    "regulation_wins": team.regulation_wins,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="standings_win_breakdown",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: win breakdown validation passed",
                entity_id=entity_id,
            )
        )

    # Rule: Point percentage in valid range (0-100)
    if not (PCT_MIN <= team.point_pctg <= PCT_MAX_100):
        results.append(
            make_failed(
                rule_name="standings_point_pct_range",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: point_pctg ({team.point_pctg}) outside valid range [0-100]",
                severity="info",
                details={
                    "team_abbrev": team.team_abbrev,
                    "point_pctg": team.point_pctg,
                },
                entity_id=entity_id,
            )
        )
    else:
        results.append(
            make_passed(
                rule_name="standings_point_pct_range",
                source_type=SOURCE_STANDINGS,
                message=f"{team_context}: point percentage validation passed",
                entity_id=entity_id,
            )
        )

    return results
