"""Tests for entity API endpoints."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

# =============================================================================
# Player Tests
# =============================================================================


class TestListPlayers:
    """Tests for GET /api/v1/players endpoint."""

    def test_list_players_returns_paginated_results(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test player list returns paginated response."""
        mock_db_service.fetchval = AsyncMock(return_value=100)
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "player_id": 8478402,
                    "first_name": "Connor",
                    "last_name": "McDavid",
                    "full_name": "Connor McDavid",
                    "age": 27,
                    "primary_position": "C",
                    "position_type": "F",
                    "current_team_id": 22,
                    "team_name": "Edmonton Oilers",
                    "team_abbreviation": "EDM",
                    "sweater_number": 97,
                    "headshot_url": "https://example.com/mcdavid.jpg",
                    "active": True,
                }
            ]
        )

        response = test_client.get("/api/v1/players")

        assert response.status_code == 200
        data = response.json()
        assert "players" in data
        assert "pagination" in data
        assert len(data["players"]) == 1
        assert data["players"][0]["player_id"] == 8478402
        assert data["players"][0]["full_name"] == "Connor McDavid"
        assert data["pagination"]["total_items"] == 100
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 25

    def test_list_players_with_search(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test player list with search filter."""
        mock_db_service.fetchval = AsyncMock(return_value=1)
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "player_id": 8478402,
                    "first_name": "Connor",
                    "last_name": "McDavid",
                    "full_name": "Connor McDavid",
                    "age": 27,
                    "primary_position": "C",
                    "position_type": "F",
                    "current_team_id": 22,
                    "team_name": "Edmonton Oilers",
                    "team_abbreviation": "EDM",
                    "sweater_number": 97,
                    "headshot_url": None,
                    "active": True,
                }
            ]
        )

        response = test_client.get("/api/v1/players?search=McDavid")

        assert response.status_code == 200
        data = response.json()
        assert len(data["players"]) == 1
        assert data["players"][0]["last_name"] == "McDavid"

    def test_list_players_with_position_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test player list with position filter."""
        mock_db_service.fetchval = AsyncMock(return_value=50)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/players?position=G")

        assert response.status_code == 200
        # Verify query was called with position filter
        mock_db_service.fetch.assert_called_once()

    def test_list_players_with_team_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test player list filtered by team."""
        mock_db_service.fetchval = AsyncMock(return_value=25)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/players?team_id=22")

        assert response.status_code == 200
        mock_db_service.fetch.assert_called_once()

    def test_list_players_pagination(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test player list pagination parameters."""
        mock_db_service.fetchval = AsyncMock(return_value=200)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/players?page=3&per_page=50")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 3
        assert data["pagination"]["per_page"] == 50
        assert data["pagination"]["total_pages"] == 4

    def test_list_players_empty_results(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test player list with no results."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/players?search=nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert data["players"] == []
        assert data["pagination"]["total_items"] == 0
        assert data["pagination"]["total_pages"] == 0


class TestGetPlayer:
    """Tests for GET /api/v1/players/{player_id} endpoint."""

    def test_get_player_returns_detail(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test get player returns detailed information."""
        mock_db_service.fetchrow = AsyncMock(
            return_value={
                "player_id": 8478402,
                "first_name": "Connor",
                "last_name": "McDavid",
                "full_name": "Connor McDavid",
                "birth_date": date(1997, 1, 13),
                "age": 27,
                "birth_country": "CAN",
                "nationality": "CAN",
                "height_inches": 73,
                "height_display": "6'1\"",
                "weight_lbs": 193,
                "shoots_catches": "L",
                "primary_position": "C",
                "position_type": "F",
                "roster_status": "Y",
                "current_team_id": 22,
                "team_name": "Edmonton Oilers",
                "team_abbreviation": "EDM",
                "division_name": "Pacific",
                "conference_name": "Western",
                "captain": True,
                "alternate_captain": False,
                "rookie": False,
                "nhl_experience": 9,
                "sweater_number": 97,
                "headshot_url": "https://example.com/mcdavid.jpg",
                "active": True,
                "updated_at": datetime(2024, 12, 20, 12, 0, 0),
            }
        )

        response = test_client.get("/api/v1/players/8478402")

        assert response.status_code == 200
        data = response.json()
        assert data["player_id"] == 8478402
        assert data["full_name"] == "Connor McDavid"
        assert data["captain"] is True
        assert data["height_display"] == "6'1\""
        assert data["nhl_experience"] == 9

    def test_get_player_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test get player returns 404 for non-existent player."""
        mock_db_service.fetchrow = AsyncMock(return_value=None)

        response = test_client.get("/api/v1/players/9999999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# =============================================================================
# Team Tests
# =============================================================================


class TestListTeams:
    """Tests for GET /api/v1/teams endpoint."""

    def test_list_teams_returns_grouped_by_division(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test teams are grouped by division."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "team_id": 22,
                    "name": "Edmonton Oilers",
                    "abbreviation": "EDM",
                    "team_name": "Oilers",
                    "location_name": "Edmonton",
                    "division_id": 15,
                    "division_name": "Pacific",
                    "conference_id": 5,
                    "conference_name": "Western",
                    "active": True,
                },
                {
                    "team_id": 26,
                    "name": "Los Angeles Kings",
                    "abbreviation": "LAK",
                    "team_name": "Kings",
                    "location_name": "Los Angeles",
                    "division_id": 15,
                    "division_name": "Pacific",
                    "conference_id": 5,
                    "conference_name": "Western",
                    "active": True,
                },
                {
                    "team_id": 6,
                    "name": "Boston Bruins",
                    "abbreviation": "BOS",
                    "team_name": "Bruins",
                    "location_name": "Boston",
                    "division_id": 17,
                    "division_name": "Atlantic",
                    "conference_id": 6,
                    "conference_name": "Eastern",
                    "active": True,
                },
            ]
        )

        response = test_client.get("/api/v1/teams")

        assert response.status_code == 200
        data = response.json()
        assert "divisions" in data
        assert "total_teams" in data
        assert data["total_teams"] == 3
        # Should be grouped into 2 divisions
        assert len(data["divisions"]) == 2

    def test_list_teams_includes_division_info(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test teams include division and conference info."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "team_id": 22,
                    "name": "Edmonton Oilers",
                    "abbreviation": "EDM",
                    "team_name": "Oilers",
                    "location_name": "Edmonton",
                    "division_id": 15,
                    "division_name": "Pacific",
                    "conference_id": 5,
                    "conference_name": "Western",
                    "active": True,
                }
            ]
        )

        response = test_client.get("/api/v1/teams")

        assert response.status_code == 200
        data = response.json()
        division = data["divisions"][0]
        assert division["division_name"] == "Pacific"
        assert division["conference_name"] == "Western"
        assert len(division["teams"]) == 1

    def test_list_teams_empty(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test teams list with no results."""
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/teams")

        assert response.status_code == 200
        data = response.json()
        assert data["divisions"] == []
        assert data["total_teams"] == 0

    def test_list_teams_skips_teams_without_division(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test teams without division_id are skipped in grouping."""
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "team_id": 22,
                    "name": "Edmonton Oilers",
                    "abbreviation": "EDM",
                    "team_name": "Oilers",
                    "location_name": "Edmonton",
                    "division_id": 15,
                    "division_name": "Pacific",
                    "conference_id": 5,
                    "conference_name": "Western",
                    "active": True,
                },
                {
                    "team_id": 99,
                    "name": "Test Team No Division",
                    "abbreviation": "TND",
                    "team_name": "No Division",
                    "location_name": "Nowhere",
                    "division_id": None,  # No division
                    "division_name": None,
                    "conference_id": None,
                    "conference_name": None,
                    "active": True,
                },
            ]
        )

        response = test_client.get("/api/v1/teams")

        assert response.status_code == 200
        data = response.json()
        # Total teams includes the one without division in count
        assert data["total_teams"] == 2
        # But divisions only has the one with a division
        assert len(data["divisions"]) == 1
        assert data["divisions"][0]["division_id"] == 15
        assert len(data["divisions"][0]["teams"]) == 1


class TestGetTeam:
    """Tests for GET /api/v1/teams/{team_id} endpoint."""

    def test_get_team_returns_detail_with_roster(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test get team returns details with roster."""
        # First call: team details
        team_row = {
            "team_id": 22,
            "franchise_id": 25,
            "name": "Edmonton Oilers",
            "abbreviation": "EDM",
            "team_name": "Oilers",
            "location_name": "Edmonton",
            "division_id": 15,
            "division_name": "Pacific",
            "conference_id": 5,
            "conference_name": "Western",
            "venue_id": 5100,
            "venue_name": "Rogers Place",
            "first_year_of_play": 1979,
            "official_site_url": "https://www.nhl.com/oilers",
            "active": True,
            "updated_at": datetime(2024, 12, 20, 12, 0, 0),
        }

        # Second call: roster
        roster_rows = [
            {
                "player_id": 8478402,
                "first_name": "Connor",
                "last_name": "McDavid",
                "full_name": "Connor McDavid",
                "age": 27,
                "primary_position": "C",
                "position_type": "F",
                "current_team_id": 22,
                "team_name": "Edmonton Oilers",
                "team_abbreviation": "EDM",
                "sweater_number": 97,
                "headshot_url": None,
                "active": True,
            }
        ]

        mock_db_service.fetchrow = AsyncMock(return_value=team_row)
        mock_db_service.fetch = AsyncMock(return_value=roster_rows)

        response = test_client.get("/api/v1/teams/22")

        assert response.status_code == 200
        data = response.json()
        assert "team" in data
        assert "roster" in data
        assert data["team"]["team_id"] == 22
        assert data["team"]["name"] == "Edmonton Oilers"
        assert data["team"]["venue_name"] == "Rogers Place"
        assert len(data["roster"]) == 1
        assert data["roster"][0]["full_name"] == "Connor McDavid"

    def test_get_team_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test get team returns 404 for non-existent team."""
        mock_db_service.fetchrow = AsyncMock(return_value=None)

        response = test_client.get("/api/v1/teams/9999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# =============================================================================
# Game Tests
# =============================================================================


class TestListGames:
    """Tests for GET /api/v1/games endpoint."""

    def test_list_games_returns_paginated_results(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test games list returns paginated response."""
        mock_db_service.fetchval = AsyncMock(return_value=1312)
        mock_db_service.fetch = AsyncMock(
            return_value=[
                {
                    "game_id": 2024020500,
                    "season_id": 20242025,
                    "season_name": "20242025",
                    "game_type": "R",
                    "game_type_name": "Regular Season",
                    "game_date": date(2024, 12, 20),
                    "game_time": "19:00:00",
                    "venue_name": "Rogers Place",
                    "home_team_id": 22,
                    "home_team_name": "Edmonton Oilers",
                    "home_team_abbr": "EDM",
                    "home_score": 4,
                    "away_team_id": 20,
                    "away_team_name": "Calgary Flames",
                    "away_team_abbr": "CGY",
                    "away_score": 2,
                    "game_state": "Final",
                    "is_overtime": False,
                    "is_shootout": False,
                    "winner_abbr": "EDM",
                }
            ]
        )

        response = test_client.get("/api/v1/games")

        assert response.status_code == 200
        data = response.json()
        assert "games" in data
        assert "pagination" in data
        assert len(data["games"]) == 1
        assert data["games"][0]["game_id"] == 2024020500
        assert data["games"][0]["home_team_abbr"] == "EDM"
        assert data["games"][0]["winner_abbr"] == "EDM"

    def test_list_games_with_season_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test games list filtered by season."""
        mock_db_service.fetchval = AsyncMock(return_value=82)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/games?season=20242025")

        assert response.status_code == 200
        mock_db_service.fetch.assert_called_once()

    def test_list_games_with_team_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test games list filtered by team."""
        mock_db_service.fetchval = AsyncMock(return_value=82)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/games?team_id=22")

        assert response.status_code == 200
        mock_db_service.fetch.assert_called_once()

    def test_list_games_with_date_range(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test games list filtered by date range."""
        mock_db_service.fetchval = AsyncMock(return_value=10)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get(
            "/api/v1/games?start_date=2024-12-01&end_date=2024-12-31"
        )

        assert response.status_code == 200
        mock_db_service.fetch.assert_called_once()

    def test_list_games_with_game_type_filter(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test games list filtered by game type."""
        mock_db_service.fetchval = AsyncMock(return_value=16)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/games?game_type=P")

        assert response.status_code == 200
        mock_db_service.fetch.assert_called_once()

    def test_list_games_empty(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test games list with no results."""
        mock_db_service.fetchval = AsyncMock(return_value=0)
        mock_db_service.fetch = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/games?team_id=9999")

        assert response.status_code == 200
        data = response.json()
        assert data["games"] == []
        assert data["pagination"]["total_items"] == 0


class TestGetGame:
    """Tests for GET /api/v1/games/{game_id} endpoint."""

    def test_get_game_returns_detail(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test get game returns detailed information."""
        mock_db_service.fetchrow = AsyncMock(
            return_value={
                "game_id": 2024020500,
                "season_id": 20242025,
                "season_name": "20242025",
                "game_type": "R",
                "game_type_name": "Regular Season",
                "game_date": date(2024, 12, 20),
                "game_time": "19:00:00",
                "venue_id": 5100,
                "venue_name": "Rogers Place",
                "venue_city": "Edmonton",
                "home_team_id": 22,
                "home_team_name": "Edmonton Oilers",
                "home_team_abbr": "EDM",
                "home_score": 4,
                "away_team_id": 20,
                "away_team_name": "Calgary Flames",
                "away_team_abbr": "CGY",
                "away_score": 2,
                "final_period": 3,
                "game_state": "Final",
                "is_overtime": False,
                "is_shootout": False,
                "game_outcome": "REG",
                "winner_team_id": 22,
                "winner_abbr": "EDM",
                "goal_differential": 2,
                "attendance": 18347,
                "game_duration_minutes": 150,
                "updated_at": datetime(2024, 12, 20, 22, 30, 0),
            }
        )

        response = test_client.get("/api/v1/games/2024020500")

        assert response.status_code == 200
        data = response.json()
        assert data["game_id"] == 2024020500
        assert data["home_score"] == 4
        assert data["away_score"] == 2
        assert data["winner_team_id"] == 22
        assert data["attendance"] == 18347
        assert data["venue_city"] == "Edmonton"

    def test_get_game_overtime(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test get game with overtime result."""
        mock_db_service.fetchrow = AsyncMock(
            return_value={
                "game_id": 2024020501,
                "season_id": 20242025,
                "season_name": "20242025",
                "game_type": "R",
                "game_type_name": "Regular Season",
                "game_date": date(2024, 12, 21),
                "game_time": "20:00:00",
                "venue_id": 5100,
                "venue_name": "Rogers Place",
                "venue_city": "Edmonton",
                "home_team_id": 22,
                "home_team_name": "Edmonton Oilers",
                "home_team_abbr": "EDM",
                "home_score": 3,
                "away_team_id": 25,
                "away_team_name": "Dallas Stars",
                "away_team_abbr": "DAL",
                "away_score": 2,
                "final_period": 4,
                "game_state": "Final",
                "is_overtime": True,
                "is_shootout": False,
                "game_outcome": "OT",
                "winner_team_id": 22,
                "winner_abbr": "EDM",
                "goal_differential": 1,
                "attendance": 18347,
                "game_duration_minutes": 165,
                "updated_at": datetime(2024, 12, 21, 23, 0, 0),
            }
        )

        response = test_client.get("/api/v1/games/2024020501")

        assert response.status_code == 200
        data = response.json()
        assert data["is_overtime"] is True
        assert data["final_period"] == 4

    def test_get_game_not_found(
        self, test_client: TestClient, mock_db_service: MagicMock
    ) -> None:
        """Test get game returns 404 for non-existent game."""
        mock_db_service.fetchrow = AsyncMock(return_value=None)

        response = test_client.get("/api/v1/games/9999999999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
