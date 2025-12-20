"""Progress tracking for NHL data downloads.

This module provides in-memory progress tracking with database persistence
for resumable downloads.

Example usage:
    from nhl_api.downloaders.progress import ProgressTracker, ProgressState
    from nhl_api.services.db import DatabaseService, ProgressRepository

    async with DatabaseService() as db:
        repo = ProgressRepository(db)
        tracker = ProgressTracker(repo, source_id=1, season_id=20242025)

        # Resume from last successful point
        await tracker.load_state()

        # Track progress
        for game_id in games:
            await tracker.start_item(str(game_id))
            # ... download logic ...
            await tracker.complete_item(str(game_id))
"""

from nhl_api.downloaders.progress.tracker import (
    ProgressCallback,
    ProgressEvent,
    ProgressState,
    ProgressStats,
    ProgressTracker,
)

__all__ = [
    "ProgressCallback",
    "ProgressEvent",
    "ProgressState",
    "ProgressStats",
    "ProgressTracker",
]
