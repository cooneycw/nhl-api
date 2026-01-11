"""CLI entry point for nhl_api.

Usage:
    python -m nhl_api.cli validate --season 20242025
    python -m nhl_api.cli validate --game 2024020001
    python -m nhl_api.cli validate --report
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="nhl-api",
        description="NHL API command-line tools",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Run data validation and reconciliation",
    )
    validate_parser.add_argument(
        "--season",
        type=str,
        help="Season to validate (e.g., 20242025)",
    )
    validate_parser.add_argument(
        "--game",
        type=int,
        help="Single game ID to validate",
    )
    validate_parser.add_argument(
        "--report",
        action="store_true",
        help="Generate text reports",
    )
    validate_parser.add_argument(
        "--output-dir",
        type=str,
        default="data/reports/validation",
        help="Output directory for reports (default: data/reports/validation)",
    )

    args = parser.parse_args()

    if args.command == "validate":
        from nhl_api.cli.validate import run_validate

        return run_validate(
            season=args.season,
            game_id=args.game,
            generate_report=args.report,
            output_dir=args.output_dir,
        )
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
