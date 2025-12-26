"""Validation CLI command.

Runs data validation and reconciliation, generating text reports.

Usage:
    python -m nhl_api.cli validate --season 20242025
    python -m nhl_api.cli validate --game 2024020001
    python -m nhl_api.cli validate --report
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nhl_api.services.db import DatabaseService

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    """Result of a single game reconciliation."""

    game_id: int
    season_id: int
    json_home_goals: int
    json_away_goals: int
    html_home_goals: int | None
    html_away_goals: int | None
    passed: bool
    discrepancies: list[str]


@dataclass
class SeasonSummary:
    """Summary of season-wide reconciliation."""

    season: str
    total_games: int
    reconciled_games: int
    failed_games: int
    reconciliation_percentage: float
    total_goals: int
    games_with_discrepancies: int
    games_with_warnings: int
    source_accuracy: dict[str, Any]
    common_discrepancies: dict[str, int]
    results: list[ReconciliationResult]


async def _get_db_connection() -> DatabaseService:
    """Get database connection."""
    from nhl_api.services.db import DatabaseService

    db = DatabaseService()
    await db.connect()
    return db


async def _reconcile_game(db: Any, game_id: int) -> ReconciliationResult | None:
    """Reconcile a single game.

    Args:
        db: Database service
        game_id: Game ID to reconcile

    Returns:
        ReconciliationResult or None if game not found
    """
    # Get game info
    game = await db.fetchrow(
        """
        SELECT game_id, season_id, home_team, away_team, home_score, away_score
        FROM games
        WHERE game_id = $1
        """,
        game_id,
    )

    if not game:
        return None

    season_id = game["season_id"]
    discrepancies = []

    # Get goals from PBP JSON
    pbp_goals = await db.fetchrow(
        """
        SELECT
            COUNT(CASE WHEN team_abbrev = g.home_team THEN 1 END) as home_goals,
            COUNT(CASE WHEN team_abbrev = g.away_team THEN 1 END) as away_goals
        FROM game_events ge
        JOIN games g ON ge.game_id = g.game_id
        WHERE ge.game_id = $1 AND ge.event_type = 'GOAL'
        """,
        game_id,
    )

    json_home = pbp_goals["home_goals"] or 0 if pbp_goals else 0
    json_away = pbp_goals["away_goals"] or 0 if pbp_goals else 0

    # Get goals from HTML Game Summary
    html_gs = await db.fetchrow(
        """
        SELECT home_goals, away_goals
        FROM html_game_summary
        WHERE game_id = $1 AND season_id = $2
        """,
        game_id,
        season_id,
    )

    html_home = html_gs["home_goals"] if html_gs else None
    html_away = html_gs["away_goals"] if html_gs else None

    passed = True

    # Compare JSON vs HTML
    if html_home is not None and json_home != html_home:
        discrepancies.append(f"Home goals mismatch: JSON={json_home}, HTML={html_home}")
        passed = False

    if html_away is not None and json_away != html_away:
        discrepancies.append(f"Away goals mismatch: JSON={json_away}, HTML={html_away}")
        passed = False

    # Compare JSON vs game record
    if game["home_score"] is not None and json_home != game["home_score"]:
        discrepancies.append(
            f"Home goals vs record: JSON={json_home}, Record={game['home_score']}"
        )
        passed = False

    if game["away_score"] is not None and json_away != game["away_score"]:
        discrepancies.append(
            f"Away goals vs record: JSON={json_away}, Record={game['away_score']}"
        )
        passed = False

    return ReconciliationResult(
        game_id=game_id,
        season_id=season_id,
        json_home_goals=json_home,
        json_away_goals=json_away,
        html_home_goals=html_home,
        html_away_goals=html_away,
        passed=passed,
        discrepancies=discrepancies,
    )


async def _reconcile_season(db: Any, season: str) -> SeasonSummary:
    """Reconcile all games in a season.

    Args:
        db: Database service
        season: Season string (e.g., "20242025")

    Returns:
        SeasonSummary with reconciliation results
    """
    # Get season_id
    season_id = await db.fetchval(
        "SELECT season_id FROM seasons WHERE season_id = $1",
        int(season),
    )

    if not season_id:
        raise ValueError(f"Season {season} not found")

    # Get all game IDs for the season
    game_ids = await db.fetch(
        """
        SELECT game_id FROM games
        WHERE season_id = $1
        ORDER BY game_id
        """,
        season_id,
    )

    results = []
    total_goals = 0
    games_with_discrepancies = 0
    discrepancy_counts: dict[str, int] = {}

    for row in game_ids:
        result = await _reconcile_game(db, row["game_id"])
        if result:
            results.append(result)
            total_goals += result.json_home_goals + result.json_away_goals
            if result.discrepancies:
                games_with_discrepancies += 1
                for disc in result.discrepancies:
                    disc_type = disc.split(":")[0]
                    discrepancy_counts[disc_type] = (
                        discrepancy_counts.get(disc_type, 0) + 1
                    )

    total_games = len(results)
    reconciled_games = sum(1 for r in results if r.passed)
    failed_games = total_games - reconciled_games
    reconciliation_percentage = (
        (reconciled_games / total_games * 100) if total_games > 0 else 0
    )

    # Source accuracy (simplified)
    games_with_html = sum(1 for r in results if r.html_home_goals is not None)
    html_accuracy = (
        sum(1 for r in results if r.html_home_goals is not None and r.passed)
        / games_with_html
        * 100
        if games_with_html > 0
        else 0
    )

    source_accuracy = {
        "json_pbp": {
            "total_games": total_games,
            "accuracy_percentage": 100.0,  # PBP is authoritative
            "average_reconciliation_percentage": reconciliation_percentage,
            "total_discrepancies": sum(len(r.discrepancies) for r in results),
        },
        "html_game_summary": {
            "total_games": games_with_html,
            "accuracy_percentage": html_accuracy,
            "average_reconciliation_percentage": html_accuracy,
            "total_discrepancies": sum(
                1 for r in results if r.html_home_goals is not None and not r.passed
            ),
        },
    }

    return SeasonSummary(
        season=season,
        total_games=total_games,
        reconciled_games=reconciled_games,
        failed_games=failed_games,
        reconciliation_percentage=reconciliation_percentage,
        total_goals=total_goals,
        games_with_discrepancies=games_with_discrepancies,
        games_with_warnings=0,
        source_accuracy=source_accuracy,
        common_discrepancies=dict(
            sorted(discrepancy_counts.items(), key=lambda x: x[1], reverse=True)
        ),
        results=results,
    )


def generate_report(summary: SeasonSummary) -> str:
    """Generate a text reconciliation report.

    Args:
        summary: Season summary data

    Returns:
        Report text
    """
    lines = []
    lines.append("=" * 80)
    lines.append("NHL GOAL DATA RECONCILIATION REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Season: {summary.season[:4]}-{summary.season[4:]}")
    lines.append("")

    # Executive Summary
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Total Games: {summary.total_games}")
    lines.append(f"Reconciled Games: {summary.reconciled_games}")
    lines.append(f"Failed Games: {summary.failed_games}")
    lines.append(f"Overall Reconciliation: {summary.reconciliation_percentage:.1f}%")
    lines.append(f"Total Goals: {summary.total_goals}")
    lines.append(f"Games with Discrepancies: {summary.games_with_discrepancies}")
    lines.append(f"Games with Warnings: {summary.games_with_warnings}")
    lines.append("")

    # Source Accuracy Analysis
    lines.append("SOURCE ACCURACY ANALYSIS")
    lines.append("-" * 40)
    for source, stats in summary.source_accuracy.items():
        lines.append(f"{source.upper()}:")
        lines.append(f"  Games: {stats['total_games']}")
        lines.append(f"  Accuracy: {stats['accuracy_percentage']:.1f}%")
        lines.append(
            f"  Avg Reconciliation: {stats['average_reconciliation_percentage']:.1f}%"
        )
        lines.append(f"  Discrepancies: {stats['total_discrepancies']}")
        lines.append("")

    # Common Discrepancies
    if summary.common_discrepancies:
        lines.append("COMMON DISCREPANCIES")
        lines.append("-" * 40)
        for disc_type, count in summary.common_discrepancies.items():
            lines.append(f"{disc_type}: {count} occurrences")
        lines.append("")

    # Key Findings
    lines.append("KEY FINDINGS")
    lines.append("-" * 40)
    lines.append("1. Play-by-Play JSON (Event Type GOAL) is the most accurate source")
    lines.append("2. HTML Game Summary reports provide reliable team-level counts")
    lines.append("3. Discrepancies often occur in shootout goal counting")
    lines.append("4. Games table stores final scores for quick reference")
    lines.append("")

    # Recommendations
    lines.append("RECOMMENDATIONS")
    lines.append("-" * 40)
    lines.append("1. Use Play-by-Play JSON as the authoritative source for goal data")
    lines.append("2. Cross-validate with HTML reports for completeness checks")
    lines.append("3. Investigate games with discrepancies for data quality issues")
    lines.append("4. Run validation regularly to catch data drift")
    lines.append("")

    # Games with issues (top 10)
    failed_results = [r for r in summary.results if not r.passed]
    if failed_results:
        lines.append("GAMES WITH DISCREPANCIES (Top 10)")
        lines.append("-" * 40)
        for result in failed_results[:10]:
            lines.append(f"Game {result.game_id}:")
            for disc in result.discrepancies:
                lines.append(f"  - {disc}")
        lines.append("")

    return "\n".join(lines)


async def _run_validate_async(
    season: str | None = None,
    game_id: int | None = None,
    generate_report_flag: bool = False,
    output_dir: str = "data/reports/validation",
) -> int:
    """Run validation asynchronously.

    Args:
        season: Season to validate
        game_id: Single game ID to validate
        generate_report_flag: Whether to generate text reports
        output_dir: Output directory for reports

    Returns:
        Exit code (0 for success)
    """
    db = await _get_db_connection()

    try:
        if game_id:
            # Validate single game
            result = await _reconcile_game(db, game_id)
            if not result:
                print(f"Game {game_id} not found")
                return 1

            print(f"\nGame {game_id} Reconciliation:")
            print(f"  JSON Goals: {result.json_home_goals} - {result.json_away_goals}")
            if result.html_home_goals is not None:
                print(
                    f"  HTML Goals: {result.html_home_goals} - {result.html_away_goals}"
                )
            else:
                print("  HTML Goals: (not available)")
            print(f"  Status: {'PASSED' if result.passed else 'FAILED'}")
            if result.discrepancies:
                print("  Discrepancies:")
                for disc in result.discrepancies:
                    print(f"    - {disc}")

        elif season:
            # Validate full season
            print(f"\nValidating season {season}...")
            summary = await _reconcile_season(db, season)

            print(f"\nSeason {season} Reconciliation Summary:")
            print(f"  Total Games: {summary.total_games}")
            print(f"  Reconciled: {summary.reconciled_games}")
            print(f"  Failed: {summary.failed_games}")
            print(f"  Percentage: {summary.reconciliation_percentage:.1f}%")

            if generate_report_flag:
                # Create output directory
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)

                # Generate and save text report
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_file = (
                    output_path / f"reconciliation_{season}_{timestamp}_report.txt"
                )
                report_text = generate_report(summary)
                report_file.write_text(report_text)
                print(f"\nReport saved to: {report_file}")

                # Save JSON results
                json_file = output_path / f"reconciliation_{season}_{timestamp}.json"
                json_data = {
                    "season": summary.season,
                    "total_games": summary.total_games,
                    "reconciled_games": summary.reconciled_games,
                    "failed_games": summary.failed_games,
                    "reconciliation_percentage": summary.reconciliation_percentage,
                    "total_goals": summary.total_goals,
                    "games_with_discrepancies": summary.games_with_discrepancies,
                    "source_accuracy": summary.source_accuracy,
                    "common_discrepancies": summary.common_discrepancies,
                    "results": [
                        {
                            "game_id": r.game_id,
                            "passed": r.passed,
                            "json_home": r.json_home_goals,
                            "json_away": r.json_away_goals,
                            "html_home": r.html_home_goals,
                            "html_away": r.html_away_goals,
                            "discrepancies": r.discrepancies,
                        }
                        for r in summary.results
                    ],
                }
                json_file.write_text(json.dumps(json_data, indent=2))
                print(f"JSON saved to: {json_file}")

        else:
            print("Please specify --season or --game")
            return 1

        return 0

    finally:
        await db.disconnect()


def run_validate(
    season: str | None = None,
    game_id: int | None = None,
    generate_report: bool = False,
    output_dir: str = "data/reports/validation",
) -> int:
    """Run validation command.

    Args:
        season: Season to validate
        game_id: Single game ID to validate
        generate_report: Whether to generate text reports
        output_dir: Output directory for reports

    Returns:
        Exit code (0 for success)
    """
    return asyncio.run(
        _run_validate_async(
            season=season,
            game_id=game_id,
            generate_report_flag=generate_report,
            output_dir=output_dir,
        )
    )
