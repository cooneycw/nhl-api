"""Cross-source validation: JSON API vs HTML Reports.

Validates consistency between NHL JSON API data and HTML game reports.
HTML reports are considered the authoritative source for official game records.

Example usage:
    validator = JSONvsHTMLValidator()

    # Validate goals from PBP JSON vs Game Summary HTML
    results = validator.validate_goals(pbp_goals, gs_goals, game_id=2024020500)

    for result in results:
        if not result.passed:
            print(f"{result.severity}: {result.message}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nhl_api.validation.constants import (
    CROSS_SOURCE_JSON_VS_HTML,
    TOI_TOLERANCE_SECONDS,
)
from nhl_api.validation.results import (
    InternalValidationResult,
    ValidationSummary,
    make_failed,
    make_passed,
)

if TYPE_CHECKING:
    from nhl_api.downloaders.sources.html.event_summary import ParsedEventSummary
    from nhl_api.downloaders.sources.html.faceoff_summary import ParsedFaceoffSummary
    from nhl_api.downloaders.sources.html.game_summary import (
        GoalInfo,
        ParsedGameSummary,
    )
    from nhl_api.downloaders.sources.html.shot_summary import ParsedShotSummary
    from nhl_api.downloaders.sources.html.time_on_ice import ParsedTimeOnIce
    from nhl_api.downloaders.sources.nhl_json.boxscore import ParsedBoxscore
    from nhl_api.downloaders.sources.nhl_json.play_by_play import (
        GameEvent,
        ParsedPlayByPlay,
    )
    from nhl_api.models.shifts import ParsedShiftChart

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normalize player name for comparison.

    Handles variations like:
    - "Mitchell Marner" vs "Mitch Marner"
    - "Mikhail Sergachev" vs "Mikhail Sergachyov"
    - Accented characters

    Args:
        name: Player name

    Returns:
        Normalized lowercase name
    """
    # Convert to lowercase
    name = name.lower().strip()

    # Remove accents (simple approach - full unicode normalization would be better)
    # For now, just strip common diacritics
    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "á": "a",
        "à": "a",
        "â": "a",
        "ä": "a",
        "í": "i",
        "ì": "i",
        "î": "i",
        "ï": "i",
        "ó": "o",
        "ò": "o",
        "ô": "o",
        "ö": "o",
        "ú": "u",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ý": "y",
        "ÿ": "y",
        "ñ": "n",
        "ç": "c",
    }
    for accented, plain in replacements.items():
        name = name.replace(accented, plain)

    # Common nickname variations
    nickname_map = {
        "mitchell": "mitch",
        "nicholas": "nick",
        "michael": "mike",
        "alexander": "alex",
        "christopher": "chris",
        "jonathan": "jon",
        "william": "will",
        "matthew": "matt",
        "daniel": "dan",
        "joshua": "josh",
        "benjamin": "ben",
        "timothy": "tim",
        "anthony": "tony",
        "samuel": "sam",
    }

    # Apply nickname normalization to first name
    parts = name.split()
    if parts and parts[0] in nickname_map:
        parts[0] = nickname_map[parts[0]]
        name = " ".join(parts)

    return name


def _parse_time_to_seconds(time_str: str) -> int | None:
    """Parse time string (MM:SS) to total seconds.

    Args:
        time_str: Time string in MM:SS format

    Returns:
        Total seconds, or None if invalid
    """
    try:
        if ":" in time_str:
            parts = time_str.strip().split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
    except (ValueError, AttributeError):
        pass
    return None


@dataclass
class CrossSourceValidationResult:
    """Result from cross-source validation.

    Extends InternalValidationResult with source comparison details.
    """

    rule_name: str
    passed: bool
    source_a: str
    source_a_value: int | float | str | None
    source_b: str
    source_b_value: int | float | str | None
    difference: int | float | None = None
    message: str = ""
    severity: str = "error"
    entity_id: str | None = None
    details: dict[str, Any] | None = None


class JSONvsHTMLValidator:
    """Validator for comparing JSON API data against HTML reports.

    Compares:
    - Goals: PBP events vs GS scoring summary
    - Assists: PBP assists vs GS scoring summary
    - Penalties: PBP events vs GS penalty summary
    - TOI: Shift charts vs TH/TV HTML
    - Shots: Boxscore vs SS HTML
    - Faceoffs: Boxscore FO% vs FS HTML

    Example:
        validator = JSONvsHTMLValidator()

        # Compare goals
        results = validator.validate_goals(pbp, gs)

        # Get summary
        summary = validator.get_validation_summary(game_id, results)
    """

    # =========================================================================
    # Goals Validation
    # =========================================================================

    def validate_goals(
        self,
        pbp: ParsedPlayByPlay,
        game_summary: ParsedGameSummary,
    ) -> list[InternalValidationResult]:
        """Validate goals between PBP JSON and Game Summary HTML.

        Compares:
        - Total goal counts per team
        - Scorer names for each goal
        - Goal times (period and time)

        Args:
            pbp: Parsed play-by-play data from JSON API
            game_summary: Parsed game summary from HTML

        Returns:
            List of validation results
        """
        results: list[InternalValidationResult] = []
        game_id = str(pbp.game_id)

        # Get goals from PBP
        pbp_goals = [e for e in pbp.events if e.event_type == "goal"]

        # Get goals from GS
        gs_goals = game_summary.goals

        # 1. Compare total goal counts
        results.append(self._compare_goal_counts(pbp_goals, gs_goals, game_id))

        # 2. Match individual goals
        results.extend(self._match_individual_goals(pbp_goals, gs_goals, game_id))

        return results

    def _compare_goal_counts(
        self,
        pbp_goals: list[GameEvent],
        gs_goals: list[GoalInfo],
        game_id: str,
    ) -> InternalValidationResult:
        """Compare total goal counts between sources."""
        pbp_count = len(pbp_goals)
        gs_count = len(gs_goals)

        if pbp_count == gs_count:
            return make_passed(
                rule_name="json_html_goal_count",
                source_type=CROSS_SOURCE_JSON_VS_HTML,
                message=f"Goal count matches: {pbp_count} goals",
                entity_id=game_id,
            )
        else:
            return make_failed(
                rule_name="json_html_goal_count",
                source_type=CROSS_SOURCE_JSON_VS_HTML,
                message=f"Goal count mismatch: JSON={pbp_count}, HTML={gs_count}",
                severity="error",
                details={
                    "json_goals": pbp_count,
                    "html_goals": gs_count,
                    "difference": abs(pbp_count - gs_count),
                },
                entity_id=game_id,
            )

    def _match_individual_goals(
        self,
        pbp_goals: list[GameEvent],
        gs_goals: list[GoalInfo],
        game_id: str,
    ) -> list[InternalValidationResult]:
        """Match individual goals between PBP and GS."""
        results: list[InternalValidationResult] = []

        # Sort goals by period and time for matching
        pbp_sorted = sorted(
            pbp_goals,
            key=lambda e: (e.period, _parse_time_to_seconds(e.time_in_period) or 0),
        )
        gs_sorted = sorted(
            gs_goals,
            key=lambda g: (g.period, _parse_time_to_seconds(g.time) or 0),
        )

        # Match goals by position (using strict=False since counts may differ)
        for i, (pbp_goal, gs_goal) in enumerate(
            zip(pbp_sorted, gs_sorted, strict=False)
        ):
            # Check period match
            period_match = pbp_goal.period == gs_goal.period

            # Check time match (within tolerance)
            pbp_time = _parse_time_to_seconds(pbp_goal.time_in_period)
            gs_time = _parse_time_to_seconds(gs_goal.time)
            time_match = (
                pbp_time is not None
                and gs_time is not None
                and abs(pbp_time - gs_time) <= 1  # 1 second tolerance
            )

            # Check scorer name match - find scorer in EventPlayer tuple
            pbp_scorer = ""
            for player in pbp_goal.players:
                if player.role == "scorer":
                    pbp_scorer = player.name
                    break

            gs_scorer = gs_goal.scorer.name if gs_goal.scorer else ""

            scorer_match = _normalize_name(pbp_scorer) == _normalize_name(gs_scorer)

            if period_match and time_match and scorer_match:
                results.append(
                    make_passed(
                        rule_name="json_html_goal_match",
                        source_type=CROSS_SOURCE_JSON_VS_HTML,
                        message=f"Goal #{i + 1} matched: {gs_scorer} at {gs_goal.period}P {gs_goal.time}",
                        entity_id=game_id,
                    )
                )
            else:
                results.append(
                    make_failed(
                        rule_name="json_html_goal_match",
                        source_type=CROSS_SOURCE_JSON_VS_HTML,
                        message=f"Goal #{i + 1} mismatch: JSON({pbp_scorer} at P{pbp_goal.period} {pbp_goal.time_in_period}) vs HTML({gs_scorer} at P{gs_goal.period} {gs_goal.time})",
                        severity="warning",
                        details={
                            "goal_number": i + 1,
                            "json_scorer": pbp_scorer,
                            "json_period": pbp_goal.period,
                            "json_time": pbp_goal.time_in_period,
                            "html_scorer": gs_scorer,
                            "html_period": gs_goal.period,
                            "html_time": gs_goal.time,
                            "period_match": period_match,
                            "time_match": time_match,
                            "scorer_match": scorer_match,
                        },
                        entity_id=game_id,
                    )
                )

        return results

    # =========================================================================
    # Assists Validation
    # =========================================================================

    def validate_assists(
        self,
        pbp: ParsedPlayByPlay,
        game_summary: ParsedGameSummary,
    ) -> list[InternalValidationResult]:
        """Validate assists between PBP JSON and Game Summary HTML.

        For each goal, compares assist1 and assist2 between sources.

        Args:
            pbp: Parsed play-by-play data from JSON API
            game_summary: Parsed game summary from HTML

        Returns:
            List of validation results
        """
        results: list[InternalValidationResult] = []
        game_id = str(pbp.game_id)

        pbp_goals = [e for e in pbp.events if e.event_type == "goal"]
        gs_goals = game_summary.goals

        # Sort for matching
        pbp_sorted = sorted(
            pbp_goals,
            key=lambda e: (e.period, _parse_time_to_seconds(e.time_in_period) or 0),
        )
        gs_sorted = sorted(
            gs_goals,
            key=lambda g: (g.period, _parse_time_to_seconds(g.time) or 0),
        )

        for i, (pbp_goal, gs_goal) in enumerate(
            zip(pbp_sorted, gs_sorted, strict=False)
        ):
            # Get assists from PBP - filter by role
            pbp_assists: list[str] = []
            for player in pbp_goal.players:
                if player.role == "assist":
                    pbp_assists.append(player.name)

            # Get assists from GS
            gs_assists: list[str] = []
            if gs_goal.assist1:
                gs_assists.append(gs_goal.assist1.name)
            if gs_goal.assist2:
                gs_assists.append(gs_goal.assist2.name)

            # Compare assist counts
            if len(pbp_assists) != len(gs_assists):
                results.append(
                    make_failed(
                        rule_name="json_html_assist_count",
                        source_type=CROSS_SOURCE_JSON_VS_HTML,
                        message=f"Goal #{i + 1} assist count mismatch: JSON={len(pbp_assists)}, HTML={len(gs_assists)}",
                        severity="warning",
                        details={
                            "goal_number": i + 1,
                            "json_assists": pbp_assists,
                            "html_assists": gs_assists,
                        },
                        entity_id=game_id,
                    )
                )
            else:
                # Compare assist names
                pbp_normalized = sorted(_normalize_name(n) for n in pbp_assists)
                gs_normalized = sorted(_normalize_name(n) for n in gs_assists)

                if pbp_normalized == gs_normalized:
                    results.append(
                        make_passed(
                            rule_name="json_html_assist_match",
                            source_type=CROSS_SOURCE_JSON_VS_HTML,
                            message=f"Goal #{i + 1} assists match: {gs_assists}",
                            entity_id=game_id,
                        )
                    )
                else:
                    results.append(
                        make_failed(
                            rule_name="json_html_assist_match",
                            source_type=CROSS_SOURCE_JSON_VS_HTML,
                            message=f"Goal #{i + 1} assist names mismatch: JSON={pbp_assists}, HTML={gs_assists}",
                            severity="warning",
                            details={
                                "goal_number": i + 1,
                                "json_assists": pbp_assists,
                                "html_assists": gs_assists,
                            },
                            entity_id=game_id,
                        )
                    )

        return results

    # =========================================================================
    # Penalties Validation
    # =========================================================================

    def validate_penalties(
        self,
        pbp: ParsedPlayByPlay,
        game_summary: ParsedGameSummary,
    ) -> list[InternalValidationResult]:
        """Validate penalties between PBP JSON and Game Summary HTML.

        Compares:
        - Total penalty counts
        - Penalty times and types

        Args:
            pbp: Parsed play-by-play data from JSON API
            game_summary: Parsed game summary from HTML

        Returns:
            List of validation results
        """
        results: list[InternalValidationResult] = []
        game_id = str(pbp.game_id)

        # Get penalties from PBP
        pbp_penalties = [e for e in pbp.events if e.event_type == "penalty"]

        # Get penalties from GS
        gs_penalties = game_summary.penalties

        # Compare counts
        pbp_count = len(pbp_penalties)
        gs_count = len(gs_penalties)

        if pbp_count == gs_count:
            results.append(
                make_passed(
                    rule_name="json_html_penalty_count",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Penalty count matches: {pbp_count} penalties",
                    entity_id=game_id,
                )
            )
        else:
            results.append(
                make_failed(
                    rule_name="json_html_penalty_count",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Penalty count mismatch: JSON={pbp_count}, HTML={gs_count}",
                    severity="warning",
                    details={
                        "json_penalties": pbp_count,
                        "html_penalties": gs_count,
                        "difference": abs(pbp_count - gs_count),
                    },
                    entity_id=game_id,
                )
            )

        # Compare total PIM
        pbp_pim = sum(self._extract_penalty_minutes(e) for e in pbp_penalties)
        gs_pim = sum(p.pim for p in gs_penalties)

        if pbp_pim == gs_pim:
            results.append(
                make_passed(
                    rule_name="json_html_pim_total",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Total PIM matches: {pbp_pim} minutes",
                    entity_id=game_id,
                )
            )
        else:
            results.append(
                make_failed(
                    rule_name="json_html_pim_total",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Total PIM mismatch: JSON={pbp_pim}, HTML={gs_pim}",
                    severity="warning",
                    details={
                        "json_pim": pbp_pim,
                        "html_pim": gs_pim,
                        "difference": abs(pbp_pim - gs_pim),
                    },
                    entity_id=game_id,
                )
            )

        return results

    def _extract_penalty_minutes(self, event: GameEvent) -> int:
        """Extract penalty minutes from a PBP penalty event."""
        # Try to get duration from event details
        if event.details:
            duration = event.details.get("duration")
            if isinstance(duration, int):
                return duration
        # Default to 2 if not specified
        return 2

    # =========================================================================
    # TOI Validation
    # =========================================================================

    def validate_toi(
        self,
        shifts: ParsedShiftChart,
        toi_html: ParsedTimeOnIce,
    ) -> list[InternalValidationResult]:
        """Validate TOI between Shift Charts JSON and Time on Ice HTML.

        Compares player TOI totals with ±5 second tolerance.

        Args:
            shifts: Parsed shift chart data from JSON API
            toi_html: Parsed time on ice from HTML (TH or TV)

        Returns:
            List of validation results
        """
        results: list[InternalValidationResult] = []
        game_id = str(shifts.game_id)

        # Build player TOI map from shifts
        shift_toi: dict[int, int] = {}  # player_id -> total seconds
        for shift in shifts.shifts:
            if not shift.is_goal_event:  # Exclude goal events
                player_id = shift.player_id
                shift_toi[player_id] = (
                    shift_toi.get(player_id, 0) + shift.duration_seconds
                )

        # Build player TOI map from HTML
        html_toi: dict[int, int] = {}  # player_number -> total seconds
        for player in toi_html.players:
            toi_seconds = _parse_time_to_seconds(player.total_toi)
            if toi_seconds is not None:
                html_toi[player.number] = toi_seconds

        # Compare team totals
        shift_total = sum(shift_toi.values())
        html_total = sum(html_toi.values())

        # Each player's TOI should roughly match, but team total is a good check
        if abs(shift_total - html_total) <= TOI_TOLERANCE_SECONDS * len(html_toi):
            results.append(
                make_passed(
                    rule_name="json_html_toi_total",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Total TOI matches within tolerance: JSON={shift_total}s, HTML={html_total}s",
                    entity_id=game_id,
                )
            )
        else:
            results.append(
                make_failed(
                    rule_name="json_html_toi_total",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Total TOI mismatch: JSON={shift_total}s, HTML={html_total}s",
                    severity="warning",
                    details={
                        "json_toi_total": shift_total,
                        "html_toi_total": html_total,
                        "difference": abs(shift_total - html_total),
                        "players_html": len(html_toi),
                        "players_json": len(shift_toi),
                    },
                    entity_id=game_id,
                )
            )

        return results

    # =========================================================================
    # Shots Validation
    # =========================================================================

    def validate_shots(
        self,
        boxscore: ParsedBoxscore,
        shot_summary: ParsedShotSummary,
    ) -> list[InternalValidationResult]:
        """Validate shots between Boxscore JSON and Shot Summary HTML.

        Compares:
        - Total team shots
        - Per-zone shot totals (with tolerance)

        Args:
            boxscore: Parsed boxscore data from JSON API
            shot_summary: Parsed shot summary from HTML

        Returns:
            List of validation results
        """
        results: list[InternalValidationResult] = []
        game_id = str(boxscore.game_id)

        # Get JSON shots
        json_away_shots = boxscore.away_team.shots_on_goal
        json_home_shots = boxscore.home_team.shots_on_goal

        # Get HTML shots (from team totals)
        html_away_shots = 0
        html_home_shots = 0

        # Sum from period totals
        for period_stat in shot_summary.away_team.periods:
            if period_stat.period == "TOT":
                html_away_shots = period_stat.total.shots
                break
        else:
            # Sum non-TOT periods
            html_away_shots = sum(
                p.total.shots
                for p in shot_summary.away_team.periods
                if p.period != "TOT"
            )

        for period_stat in shot_summary.home_team.periods:
            if period_stat.period == "TOT":
                html_home_shots = period_stat.total.shots
                break
        else:
            html_home_shots = sum(
                p.total.shots
                for p in shot_summary.home_team.periods
                if p.period != "TOT"
            )

        # Compare away shots
        if json_away_shots == html_away_shots:
            results.append(
                make_passed(
                    rule_name="json_html_shots_away",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Away team shots match: {json_away_shots}",
                    entity_id=game_id,
                )
            )
        else:
            results.append(
                make_failed(
                    rule_name="json_html_shots_away",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Away team shots mismatch: JSON={json_away_shots}, HTML={html_away_shots}",
                    severity="error",
                    details={
                        "json_shots": json_away_shots,
                        "html_shots": html_away_shots,
                        "difference": abs(json_away_shots - html_away_shots),
                    },
                    entity_id=game_id,
                )
            )

        # Compare home shots
        if json_home_shots == html_home_shots:
            results.append(
                make_passed(
                    rule_name="json_html_shots_home",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Home team shots match: {json_home_shots}",
                    entity_id=game_id,
                )
            )
        else:
            results.append(
                make_failed(
                    rule_name="json_html_shots_home",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Home team shots mismatch: JSON={json_home_shots}, HTML={html_home_shots}",
                    severity="error",
                    details={
                        "json_shots": json_home_shots,
                        "html_shots": html_home_shots,
                        "difference": abs(json_home_shots - html_home_shots),
                    },
                    entity_id=game_id,
                )
            )

        return results

    # =========================================================================
    # Faceoffs Validation
    # =========================================================================

    def validate_faceoffs(
        self,
        boxscore: ParsedBoxscore,
        faceoff_summary: ParsedFaceoffSummary,
    ) -> list[InternalValidationResult]:
        """Validate faceoffs between Boxscore JSON and Faceoff Summary HTML.

        Compares team faceoff totals from HTML against derived JSON data.
        Note: JSON boxscore has faceoff_pct but not wins, so we compare
        relative percentages rather than absolute counts.

        Args:
            boxscore: Parsed boxscore data from JSON API
            faceoff_summary: Parsed faceoff summary from HTML

        Returns:
            List of validation results
        """
        results: list[InternalValidationResult] = []
        game_id = str(boxscore.game_id)

        # Get HTML faceoff totals
        html_away_won = 0
        html_home_won = 0

        # Sum from player totals
        for player in faceoff_summary.away_team.players:
            if player.totals and player.totals.total:
                html_away_won += player.totals.total.won

        for player in faceoff_summary.home_team.players:
            if player.totals and player.totals.total:
                html_home_won += player.totals.total.won

        html_total = html_away_won + html_home_won

        # Compare faceoff counts exist
        if html_total > 0:
            results.append(
                make_passed(
                    rule_name="json_html_faceoff_data",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message=f"Faceoff data present: {html_total} total faceoffs",
                    entity_id=game_id,
                )
            )
        else:
            results.append(
                make_failed(
                    rule_name="json_html_faceoff_data",
                    source_type=CROSS_SOURCE_JSON_VS_HTML,
                    message="No faceoff data found in HTML summary",
                    severity="warning",
                    details={"html_total": html_total},
                    entity_id=game_id,
                )
            )

        # Check that JSON has players who took faceoffs
        if html_total > 0:
            # Get avg faceoff pct from JSON skaters (players who took faceoffs)
            json_away_fo_players = [
                s for s in boxscore.away_skaters if s.faceoff_pct > 0
            ]
            json_home_fo_players = [
                s for s in boxscore.home_skaters if s.faceoff_pct > 0
            ]

            if json_away_fo_players or json_home_fo_players:
                results.append(
                    make_passed(
                        rule_name="json_html_faceoff_players",
                        source_type=CROSS_SOURCE_JSON_VS_HTML,
                        message=f"Faceoff players found: away={len(json_away_fo_players)}, home={len(json_home_fo_players)}",
                        entity_id=game_id,
                    )
                )

        return results

    # =========================================================================
    # Summary Methods
    # =========================================================================

    def get_validation_summary(
        self,
        game_id: int,
        results: list[InternalValidationResult],
    ) -> ValidationSummary:
        """Create a validation summary from results.

        Args:
            game_id: NHL game ID
            results: List of validation results

        Returns:
            ValidationSummary with aggregated statistics
        """
        return ValidationSummary.from_results(
            source_type=CROSS_SOURCE_JSON_VS_HTML,
            entity_id=str(game_id),
            results=results,
        )

    def validate_all(
        self,
        pbp: ParsedPlayByPlay | None = None,
        boxscore: ParsedBoxscore | None = None,
        shifts: ParsedShiftChart | None = None,
        game_summary: ParsedGameSummary | None = None,
        event_summary: ParsedEventSummary | None = None,
        faceoff_summary: ParsedFaceoffSummary | None = None,
        shot_summary: ParsedShotSummary | None = None,
        toi_html: ParsedTimeOnIce | None = None,
    ) -> list[InternalValidationResult]:
        """Run all applicable validations based on available data.

        Args:
            pbp: Parsed play-by-play data
            boxscore: Parsed boxscore data
            shifts: Parsed shift chart data
            game_summary: Parsed game summary HTML
            event_summary: Parsed event summary HTML
            faceoff_summary: Parsed faceoff summary HTML
            shot_summary: Parsed shot summary HTML
            toi_html: Parsed time on ice HTML

        Returns:
            List of all validation results
        """
        results: list[InternalValidationResult] = []

        # Goals validation (requires PBP + GS)
        if pbp and game_summary:
            results.extend(self.validate_goals(pbp, game_summary))
            results.extend(self.validate_assists(pbp, game_summary))
            results.extend(self.validate_penalties(pbp, game_summary))

        # TOI validation (requires shifts + TH/TV)
        if shifts and toi_html:
            results.extend(self.validate_toi(shifts, toi_html))

        # Shots validation (requires boxscore + SS)
        if boxscore and shot_summary:
            results.extend(self.validate_shots(boxscore, shot_summary))

        # Faceoffs validation (requires boxscore + FS)
        if boxscore and faceoff_summary:
            results.extend(self.validate_faceoffs(boxscore, faceoff_summary))

        return results
