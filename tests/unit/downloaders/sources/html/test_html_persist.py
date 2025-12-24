"""Unit tests for HTML downloader persist() methods.

Tests the database persistence logic for all HTML report downloaders.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from nhl_api.downloaders.sources.html import (
    EventSummaryDownloader,
    FaceoffSummaryDownloader,
    GameSummaryDownloader,
    HTMLDownloaderConfig,
    ShotSummaryDownloader,
    TimeOnIceDownloader,
)


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database service."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=None)
    return db


@pytest.fixture
def html_config() -> HTMLDownloaderConfig:
    """Create a test HTML downloader config."""
    return HTMLDownloaderConfig()


class TestGameSummaryPersist:
    """Tests for GameSummaryDownloader.persist()."""

    @pytest.mark.asyncio
    async def test_persist_empty_list(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist with empty list returns 0."""
        downloader = GameSummaryDownloader(html_config)
        result = await downloader.persist(mock_db, [])
        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_single_summary(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist a single game summary."""
        downloader = GameSummaryDownloader(html_config)
        summaries = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                "away_team": {"abbrev": "NYI", "goals": 2},
                "home_team": {"abbrev": "CAR", "goals": 4},
                "venue": "PNC Arena",
                "attendance": 18680,
                "date": "2024-01-15",
                "start_time": "7:00 PM",
                "end_time": "9:30 PM",
                "goals": [{"goal_number": 1, "period": 1}],
                "penalties": [],
                "referees": ["Chris Rooney"],
                "linesmen": ["Trent Knorr"],
            }
        ]
        result = await downloader.persist(mock_db, summaries)
        assert result == 1
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_skips_missing_ids(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist skips entries without game_id or season_id."""
        downloader = GameSummaryDownloader(html_config)
        summaries: list[dict[str, Any]] = [
            {"game_id": None, "season_id": 20242025},
            {"game_id": 2024020500, "season_id": None},
            {"away_team": {"abbrev": "NYI"}},  # Missing both
        ]
        result = await downloader.persist(mock_db, summaries)
        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_multiple_summaries(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist multiple game summaries."""
        downloader = GameSummaryDownloader(html_config)
        summaries = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                "away_team": {"abbrev": "NYI"},
                "home_team": {"abbrev": "CAR"},
            },
            {
                "game_id": 2024020501,
                "season_id": 20242025,
                "away_team": {"abbrev": "BOS"},
                "home_team": {"abbrev": "TOR"},
            },
        ]
        result = await downloader.persist(mock_db, summaries)
        assert result == 2
        assert mock_db.execute.call_count == 2


class TestEventSummaryPersist:
    """Tests for EventSummaryDownloader.persist()."""

    @pytest.mark.asyncio
    async def test_persist_empty_list(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist with empty list returns 0."""
        downloader = EventSummaryDownloader(html_config)
        result = await downloader.persist(mock_db, [])
        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_single_summary(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist a single event summary."""
        downloader = EventSummaryDownloader(html_config)
        summaries = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                "away_team": {
                    "abbrev": "NYI",
                    "players": [{"number": 20, "name": "S.AHO", "goals": 2}],
                    "goalies": [],
                    "totals": {"g": 2, "a": 3},
                },
                "home_team": {
                    "abbrev": "CAR",
                    "players": [],
                    "goalies": [],
                    "totals": {},
                },
            }
        ]
        result = await downloader.persist(mock_db, summaries)
        assert result == 1
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_serializes_json(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist correctly serializes players to JSON."""
        downloader = EventSummaryDownloader(html_config)
        summaries = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                "away_team": {
                    "abbrev": "NYI",
                    "players": [{"number": 20, "name": "S.AHO"}],
                    "goalies": [{"number": 30, "name": "F.ANDERSEN"}],
                    "totals": {"g": 2},
                },
                "home_team": {
                    "abbrev": "CAR",
                    "players": [],
                    "goalies": [],
                    "totals": {},
                },
            }
        ]
        result = await downloader.persist(mock_db, summaries)
        assert result == 1
        # Check that JSON strings were passed (not dicts)
        call_args = mock_db.execute.call_args
        assert call_args is not None
        # Positional args after the SQL query:
        # args[0]=SQL, [1]=game_id, [2]=season_id, [3]=away_abbrev, [4]=home_abbrev,
        # [5]=away_skaters, [6]=home_skaters, [7]=away_goalies, [8]=home_goalies,
        # [9]=away_totals, [10]=home_totals
        args = call_args[0]
        assert isinstance(args[5], str)  # away_skaters JSON string
        assert '"number": 20' in args[5]


class TestTimeOnIcePersist:
    """Tests for TimeOnIceDownloader.persist()."""

    @pytest.mark.asyncio
    async def test_persist_empty_list(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist with empty list returns 0."""
        downloader = TimeOnIceDownloader(html_config, side="home")
        result = await downloader.persist(mock_db, [])
        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_single_toi(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist a single TOI record."""
        downloader = TimeOnIceDownloader(html_config, side="home")
        toi_data = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                "side": "home",
                "team_abbrev": "CAR",
                "players": [
                    {"number": 20, "name": "S.AHO", "toi_total": "22:30"},
                ],
            }
        ]
        result = await downloader.persist(mock_db, toi_data)
        assert result == 1
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_requires_side(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist skips entries without side."""
        downloader = TimeOnIceDownloader(html_config, side="home")
        toi_data = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                # Missing side
                "team_abbrev": "CAR",
                "players": [],
            }
        ]
        result = await downloader.persist(mock_db, toi_data)
        assert result == 0
        mock_db.execute.assert_not_called()


class TestFaceoffSummaryPersist:
    """Tests for FaceoffSummaryDownloader.persist()."""

    @pytest.mark.asyncio
    async def test_persist_empty_list(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist with empty list returns 0."""
        downloader = FaceoffSummaryDownloader(html_config)
        result = await downloader.persist(mock_db, [])
        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_single_summary(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist a single faceoff summary."""
        downloader = FaceoffSummaryDownloader(html_config)
        summaries = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                "away_team": {
                    "abbrev": "NYI",
                    "by_period": [],
                    "by_strength": [],
                    "players": [],
                },
                "home_team": {
                    "abbrev": "CAR",
                    "by_period": [],
                    "by_strength": [],
                    "players": [],
                },
            }
        ]
        result = await downloader.persist(mock_db, summaries)
        assert result == 1
        mock_db.execute.assert_called_once()


class TestShotSummaryPersist:
    """Tests for ShotSummaryDownloader.persist()."""

    @pytest.mark.asyncio
    async def test_persist_empty_list(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist with empty list returns 0."""
        downloader = ShotSummaryDownloader(html_config)
        result = await downloader.persist(mock_db, [])
        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_single_summary(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist a single shot summary."""
        downloader = ShotSummaryDownloader(html_config)
        summaries = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                "away_team": {
                    "abbrev": "NYI",
                    "periods": [{"period": "1", "total": {"goals": 0, "shots": 12}}],
                    "players": [{"number": 13, "name": "M.BARZAL", "total_shots": 5}],
                },
                "home_team": {
                    "abbrev": "CAR",
                    "periods": [],
                    "players": [],
                },
            }
        ]
        result = await downloader.persist(mock_db, summaries)
        assert result == 1
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_multiple_summaries(
        self, mock_db: AsyncMock, html_config: HTMLDownloaderConfig
    ) -> None:
        """Persist multiple shot summaries."""
        downloader = ShotSummaryDownloader(html_config)
        summaries = [
            {
                "game_id": 2024020500,
                "season_id": 20242025,
                "away_team": {"abbrev": "NYI", "periods": [], "players": []},
                "home_team": {"abbrev": "CAR", "periods": [], "players": []},
            },
            {
                "game_id": 2024020501,
                "season_id": 20242025,
                "away_team": {"abbrev": "BOS", "periods": [], "players": []},
                "home_team": {"abbrev": "TOR", "periods": [], "players": []},
            },
        ]
        result = await downloader.persist(mock_db, summaries)
        assert result == 2
        assert mock_db.execute.call_count == 2
