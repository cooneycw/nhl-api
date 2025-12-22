"""Unit tests for HTML storage manager."""

from __future__ import annotations

from pathlib import Path

from nhl_api.utils.html_storage import HTMLStorageManager


class TestHTMLStorageManagerInit:
    """Tests for HTMLStorageManager initialization."""

    def test_default_base_dir(self) -> None:
        """Default base directory is data/html."""
        manager = HTMLStorageManager()
        assert manager.base_dir == Path("data/html")

    def test_custom_base_dir_string(self) -> None:
        """Can specify custom base directory as string."""
        manager = HTMLStorageManager(base_dir="/tmp/html")
        assert manager.base_dir == Path("/tmp/html")

    def test_custom_base_dir_path(self) -> None:
        """Can specify custom base directory as Path."""
        manager = HTMLStorageManager(base_dir=Path("/tmp/html"))
        assert manager.base_dir == Path("/tmp/html")


class TestHTMLStorageManagerGetFilePath:
    """Tests for _get_file_path method."""

    def test_file_path_structure(self, tmp_path: Path) -> None:
        """File path follows correct structure."""
        manager = HTMLStorageManager(base_dir=tmp_path)
        path = manager._get_file_path("20242025", "ES", 2024020001)

        expected = tmp_path / "20242025" / "ES" / "2024020001.HTM"
        assert path == expected

    def test_game_id_zero_padding(self, tmp_path: Path) -> None:
        """Game ID is zero-padded to 10 digits."""
        manager = HTMLStorageManager(base_dir=tmp_path)
        path = manager._get_file_path("20242025", "ES", 500)

        # Should be 0000000500.HTM
        assert path.name == "0000000500.HTM"

    def test_large_game_id(self, tmp_path: Path) -> None:
        """Large game IDs are formatted correctly."""
        manager = HTMLStorageManager(base_dir=tmp_path)
        path = manager._get_file_path("20242025", "GS", 2024030001)

        assert path.name == "2024030001.HTM"


class TestHTMLStorageManagerSave:
    """Tests for save_html method."""

    def test_save_html_string(self, tmp_path: Path) -> None:
        """Can save HTML as string."""
        manager = HTMLStorageManager(base_dir=tmp_path)
        html = "<html><body>Test</body></html>"

        path = manager.save_html("20242025", "ES", 2024020001, html)

        assert path.exists()
        assert path.read_text() == html

    def test_save_html_bytes(self, tmp_path: Path) -> None:
        """Can save HTML as bytes."""
        manager = HTMLStorageManager(base_dir=tmp_path)
        html_bytes = b"<html><body>Test</body></html>"

        path = manager.save_html("20242025", "ES", 2024020001, html_bytes)

        assert path.exists()
        assert path.read_bytes() == html_bytes

    def test_save_creates_directories(self, tmp_path: Path) -> None:
        """Saving creates parent directories if they don't exist."""
        manager = HTMLStorageManager(base_dir=tmp_path)
        html = "<html><body>Test</body></html>"

        # Parent directories don't exist yet
        assert not (tmp_path / "20242025" / "ES").exists()

        manager.save_html("20242025", "ES", 2024020001, html)

        # Parent directories were created
        assert (tmp_path / "20242025" / "ES").exists()

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Saving overwrites existing file."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        # Save initial content
        manager.save_html("20242025", "ES", 2024020001, "First version")

        # Overwrite with new content
        path = manager.save_html("20242025", "ES", 2024020001, "Second version")

        assert path.read_text() == "Second version"

    def test_save_multiple_seasons(self, tmp_path: Path) -> None:
        """Can save reports for multiple seasons."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20232024", "ES", 2023020001, "Season 2023-24")
        manager.save_html("20242025", "ES", 2024020001, "Season 2024-25")

        assert (tmp_path / "20232024" / "ES" / "2023020001.HTM").exists()
        assert (tmp_path / "20242025" / "ES" / "2024020001.HTM").exists()

    def test_save_multiple_report_types(self, tmp_path: Path) -> None:
        """Can save different report types."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20242025", "ES", 2024020001, "Event Summary")
        manager.save_html("20242025", "GS", 2024020001, "Game Summary")
        manager.save_html("20242025", "PL", 2024020001, "Play by Play")

        assert (tmp_path / "20242025" / "ES" / "2024020001.HTM").exists()
        assert (tmp_path / "20242025" / "GS" / "2024020001.HTM").exists()
        assert (tmp_path / "20242025" / "PL" / "2024020001.HTM").exists()


class TestHTMLStorageManagerLoad:
    """Tests for load_html method."""

    def test_load_existing_html(self, tmp_path: Path) -> None:
        """Can load existing HTML file."""
        manager = HTMLStorageManager(base_dir=tmp_path)
        html = "<html><body>Test</body></html>"

        manager.save_html("20242025", "ES", 2024020001, html)
        loaded = manager.load_html("20242025", "ES", 2024020001)

        assert loaded == html

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Loading nonexistent file returns None."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        result = manager.load_html("20242025", "ES", 2024020001)

        assert result is None

    def test_load_preserves_utf8(self, tmp_path: Path) -> None:
        """Loading preserves UTF-8 characters."""
        manager = HTMLStorageManager(base_dir=tmp_path)
        html = "<html><body>Zdeno Chára</body></html>"

        manager.save_html("20242025", "ES", 2024020001, html)
        loaded = manager.load_html("20242025", "ES", 2024020001)

        assert loaded == html


class TestHTMLStorageManagerExists:
    """Tests for exists method."""

    def test_exists_for_saved_file(self, tmp_path: Path) -> None:
        """Returns True for saved file."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20242025", "ES", 2024020001, "Test")

        assert manager.exists("20242025", "ES", 2024020001) is True

    def test_exists_for_missing_file(self, tmp_path: Path) -> None:
        """Returns False for missing file."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        assert manager.exists("20242025", "ES", 2024020001) is False


class TestHTMLStorageManagerDelete:
    """Tests for delete method."""

    def test_delete_existing_file(self, tmp_path: Path) -> None:
        """Can delete existing file."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20242025", "ES", 2024020001, "Test")
        result = manager.delete("20242025", "ES", 2024020001)

        assert result is True
        assert not manager.exists("20242025", "ES", 2024020001)

    def test_delete_nonexistent_returns_false(self, tmp_path: Path) -> None:
        """Deleting nonexistent file returns False."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        result = manager.delete("20242025", "ES", 2024020001)

        assert result is False


class TestHTMLStorageManagerListReports:
    """Tests for list_reports method."""

    def test_list_empty_storage(self, tmp_path: Path) -> None:
        """Empty storage returns empty list."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        reports = manager.list_reports()

        assert reports == []

    def test_list_all_reports(self, tmp_path: Path) -> None:
        """Can list all stored reports."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20242025", "ES", 2024020001, "Test 1")
        manager.save_html("20242025", "GS", 2024020002, "Test 2")
        manager.save_html("20232024", "ES", 2023020001, "Test 3")

        reports = manager.list_reports()

        assert len(reports) == 3
        assert ("20232024", "ES", 2023020001) in reports
        assert ("20242025", "ES", 2024020001) in reports
        assert ("20242025", "GS", 2024020002) in reports

    def test_list_filtered_by_season(self, tmp_path: Path) -> None:
        """Can filter reports by season."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20242025", "ES", 2024020001, "Test 1")
        manager.save_html("20242025", "GS", 2024020002, "Test 2")
        manager.save_html("20232024", "ES", 2023020001, "Test 3")

        reports = manager.list_reports(season="20242025")

        assert len(reports) == 2
        assert ("20242025", "ES", 2024020001) in reports
        assert ("20242025", "GS", 2024020002) in reports
        assert ("20232024", "ES", 2023020001) not in reports

    def test_list_filtered_by_season_and_type(self, tmp_path: Path) -> None:
        """Can filter reports by season and report type."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20242025", "ES", 2024020001, "Test 1")
        manager.save_html("20242025", "ES", 2024020002, "Test 2")
        manager.save_html("20242025", "GS", 2024020003, "Test 3")

        reports = manager.list_reports(season="20242025", report_type="ES")

        assert len(reports) == 2
        assert ("20242025", "ES", 2024020001) in reports
        assert ("20242025", "ES", 2024020002) in reports
        assert ("20242025", "GS", 2024020003) not in reports

    def test_list_nonexistent_season(self, tmp_path: Path) -> None:
        """Filtering by nonexistent season returns empty list."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20242025", "ES", 2024020001, "Test")

        reports = manager.list_reports(season="20192020")

        assert reports == []

    def test_list_reports_sorted(self, tmp_path: Path) -> None:
        """Reports are returned sorted."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        # Add in random order
        manager.save_html("20242025", "GS", 2024020002, "Test 2")
        manager.save_html("20232024", "ES", 2023020001, "Test 1")
        manager.save_html("20242025", "ES", 2024020001, "Test 3")

        reports = manager.list_reports()

        # Should be sorted
        expected = [
            ("20232024", "ES", 2023020001),
            ("20242025", "ES", 2024020001),
            ("20242025", "GS", 2024020002),
        ]
        assert reports == expected


class TestHTMLStorageManagerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_large_html_content(self, tmp_path: Path) -> None:
        """Can handle large HTML content."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        # Create ~1MB HTML file
        large_html = "<html><body>" + "X" * 1_000_000 + "</body></html>"

        manager.save_html("20242025", "ES", 2024020001, large_html)
        loaded = manager.load_html("20242025", "ES", 2024020001)

        assert loaded == large_html
        assert len(loaded) > 1_000_000

    def test_special_characters_in_html(self, tmp_path: Path) -> None:
        """Can handle special characters in HTML."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        html = "<html>Zdeno Chára & André 'Pierre' Côté</html>"

        manager.save_html("20242025", "ES", 2024020001, html)
        loaded = manager.load_html("20242025", "ES", 2024020001)

        assert loaded == html

    def test_empty_html_content(self, tmp_path: Path) -> None:
        """Can save and load empty HTML content."""
        manager = HTMLStorageManager(base_dir=tmp_path)

        manager.save_html("20242025", "ES", 2024020001, "")
        loaded = manager.load_html("20242025", "ES", 2024020001)

        assert loaded == ""
