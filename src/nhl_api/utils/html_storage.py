"""HTML report file storage manager.

This module provides utilities for persisting NHL HTML reports to disk
for cross-source validation and comparison.

Storage Structure:
    data/html/{season}/{report_type}/{game_id}.HTM

Example:
    data/html/20242025/ES/2024020001.HTM
    data/html/20242025/GS/2024020500.HTM
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class HTMLStorageManager:
    """Manage HTML report file storage.

    This class handles saving and loading raw NHL HTML reports to/from disk.
    Files are organized by season and report type for easy navigation and
    validation workflows.

    Example:
        manager = HTMLStorageManager()

        # Save HTML report
        path = manager.save_html(
            season="20242025",
            report_type="ES",
            game_id=2024020001,
            html="<html>...</html>"
        )

        # Load HTML report
        html = manager.load_html(
            season="20242025",
            report_type="ES",
            game_id=2024020001
        )
    """

    def __init__(self, base_dir: Path | str | None = None) -> None:
        """Initialize the HTML storage manager.

        Args:
            base_dir: Base directory for HTML storage. Defaults to ./data/html
        """
        if base_dir is None:
            base_dir = Path("data/html")
        self.base_dir = Path(base_dir)
        logger.debug("HTMLStorageManager initialized with base_dir=%s", self.base_dir)

    def _get_file_path(self, season: str, report_type: str, game_id: int) -> Path:
        """Build file path for HTML report.

        Args:
            season: NHL season ID (e.g., "20242025")
            report_type: Report type code (ES, GS, PL, etc.)
            game_id: NHL game ID

        Returns:
            Path object for the HTML file
        """
        # Format game_id as 10-digit zero-padded string
        game_id_str = f"{game_id:010d}"
        return self.base_dir / season / report_type / f"{game_id_str}.HTM"

    def save_html(
        self, season: str, report_type: str, game_id: int, html: str | bytes
    ) -> Path:
        """Save raw HTML to disk.

        Creates necessary directories if they don't exist.

        Args:
            season: NHL season ID (e.g., "20242025")
            report_type: Report type code (ES, GS, PL, etc.)
            game_id: NHL game ID
            html: Raw HTML content (string or bytes)

        Returns:
            Path object where the file was saved

        Raises:
            OSError: If file cannot be written
        """
        file_path = self._get_file_path(season, report_type, game_id)

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write HTML to file
        if isinstance(html, bytes):
            file_path.write_bytes(html)
        else:
            file_path.write_text(html, encoding="utf-8")

        logger.debug(
            "Saved HTML report: season=%s, report_type=%s, game_id=%d, path=%s",
            season,
            report_type,
            game_id,
            file_path,
        )

        return file_path

    def load_html(self, season: str, report_type: str, game_id: int) -> str | None:
        """Load raw HTML from disk.

        Args:
            season: NHL season ID (e.g., "20242025")
            report_type: Report type code (ES, GS, PL, etc.)
            game_id: NHL game ID

        Returns:
            HTML content as string, or None if file doesn't exist

        Raises:
            OSError: If file exists but cannot be read
        """
        file_path = self._get_file_path(season, report_type, game_id)

        if not file_path.exists():
            logger.debug(
                "HTML report not found: season=%s, report_type=%s, game_id=%d, path=%s",
                season,
                report_type,
                game_id,
                file_path,
            )
            return None

        html = file_path.read_text(encoding="utf-8")

        logger.debug(
            "Loaded HTML report: season=%s, report_type=%s, game_id=%d, size=%d bytes",
            season,
            report_type,
            game_id,
            len(html),
        )

        return html

    def exists(self, season: str, report_type: str, game_id: int) -> bool:
        """Check if HTML report exists on disk.

        Args:
            season: NHL season ID (e.g., "20242025")
            report_type: Report type code (ES, GS, PL, etc.)
            game_id: NHL game ID

        Returns:
            True if file exists, False otherwise
        """
        file_path = self._get_file_path(season, report_type, game_id)
        return file_path.exists()

    def delete(self, season: str, report_type: str, game_id: int) -> bool:
        """Delete HTML report from disk.

        Args:
            season: NHL season ID (e.g., "20242025")
            report_type: Report type code (ES, GS, PL, etc.)
            game_id: NHL game ID

        Returns:
            True if file was deleted, False if it didn't exist

        Raises:
            OSError: If file exists but cannot be deleted
        """
        file_path = self._get_file_path(season, report_type, game_id)

        if not file_path.exists():
            return False

        file_path.unlink()

        logger.debug(
            "Deleted HTML report: season=%s, report_type=%s, game_id=%d",
            season,
            report_type,
            game_id,
        )

        return True

    def list_reports(
        self, season: str | None = None, report_type: str | None = None
    ) -> list[tuple[str, str, int]]:
        """List all stored HTML reports.

        Args:
            season: Optional season filter (e.g., "20242025")
            report_type: Optional report type filter (ES, GS, etc.)

        Returns:
            List of (season, report_type, game_id) tuples for all matching reports
        """
        reports: list[tuple[str, str, int]] = []

        if season and report_type:
            # List specific season + report type
            search_path = self.base_dir / season / report_type
        elif season:
            # List all report types for a season
            search_path = self.base_dir / season
        else:
            # List all reports
            search_path = self.base_dir

        if not search_path.exists():
            return reports

        # Find all .HTM files
        for htm_file in search_path.rglob("*.HTM"):
            # Extract season, report_type, game_id from path
            # Path structure: base_dir/season/report_type/game_id.HTM
            try:
                parts = htm_file.relative_to(self.base_dir).parts
                if len(parts) == 3:
                    file_season, file_report_type, filename = parts
                    game_id = int(filename.replace(".HTM", ""))
                    reports.append((file_season, file_report_type, game_id))
            except (ValueError, IndexError):
                logger.warning("Skipping invalid HTML file path: %s", htm_file)
                continue

        return sorted(reports)
