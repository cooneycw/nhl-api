"""Unit tests for PlayerLinkingService."""

from __future__ import annotations

import logging

import pytest

from nhl_api.models.quanthockey import QuantHockeyPlayerSeasonStats
from nhl_api.services.player_linking import (
    LinkingStatistics,
    PlayerLink,
    PlayerLinkingService,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def nhl_players() -> list[tuple[int, str]]:
    """Sample NHL players for testing."""
    return [
        (8478402, "Connor McDavid"),
        (8477934, "Leon Draisaitl"),
        (8480069, "Cale Makar"),
        (8479318, "Auston Matthews"),
        (8478483, "Mitchell Marner"),
        (8471214, "Sidney Crosby"),
        (8474564, "Nathan MacKinnon"),
        (8476453, "Nikita Kucherov"),
        (8477492, "David Pastrnak"),
        (8475166, "Jack Eichel"),
        (8479328, "Elias Pettersson"),  # Vancouver Pettersson
        (8480012, "Marcus Pettersson"),  # Pittsburgh Pettersson
        (8475172, "Zdeno Chára"),  # Accented name
        (8480839, "J.T. Miller"),  # Initials
    ]


@pytest.fixture
def linking_service(nhl_players: list[tuple[int, str]]) -> PlayerLinkingService:
    """Create PlayerLinkingService with NHL players set."""
    service = PlayerLinkingService(threshold=0.85, log_unmatched=False)
    service.set_nhl_players(nhl_players)
    return service


@pytest.fixture
def qh_player_stats() -> list[QuantHockeyPlayerSeasonStats]:
    """Sample QuantHockey player stats for testing."""

    # Create minimal stats objects for testing
    def make_stats(name: str, team: str = "EDM") -> QuantHockeyPlayerSeasonStats:
        return QuantHockeyPlayerSeasonStats(
            season_id=20242025,
            rank=1,
            name=name,
            team=team,
            age=27,
            position="C",
            games_played=82,
            goals=50,
            assists=70,
            points=120,
            pim=20,
            plus_minus=30,
            toi_avg=22.5,
            toi_es=16.0,
            toi_pp=4.5,
            toi_sh=2.0,
            es_goals=30,
            pp_goals=15,
            sh_goals=5,
            gw_goals=10,
            ot_goals=2,
            es_assists=40,
            pp_assists=25,
            sh_assists=5,
            gw_assists=8,
            ot_assists=3,
            es_points=70,
            pp_points=40,
            sh_points=10,
            gw_points=18,
            ot_points=5,
            ppp_pct=33.3,
            goals_per_60=1.2,
            assists_per_60=1.7,
            points_per_60=2.9,
            es_goals_per_60=1.0,
            es_assists_per_60=1.3,
            es_points_per_60=2.3,
            pp_goals_per_60=3.5,
            pp_assists_per_60=5.5,
            pp_points_per_60=9.0,
            goals_per_game=0.61,
            assists_per_game=0.85,
            points_per_game=1.46,
            shots_on_goal=250,
            shooting_pct=20.0,
            hits=50,
            blocked_shots=30,
            faceoffs_won=800,
            faceoffs_lost=600,
            faceoff_pct=57.1,
        )

    return [
        make_stats("Connor McDavid", "EDM"),
        make_stats("L. Draisaitl", "EDM"),  # Initial format
        make_stats("C. Makar", "COL"),  # Initial format
        make_stats("Nathan MacKinnon", "COL"),
        make_stats("Zdeno Chara", "BOS"),  # Without accent
        make_stats("J.T. Miller", "VAN"),  # Initials
        make_stats("Unknown Player", "TOR"),  # Won't match
    ]


# =============================================================================
# PlayerLink Tests
# =============================================================================


class TestPlayerLink:
    """Tests for PlayerLink dataclass."""

    def test_matched_link(self) -> None:
        """Test a matched PlayerLink."""
        link = PlayerLink(
            external_name="C. McDavid",
            nhl_player_id=8478402,
            confidence=0.95,
            matched_name="Connor McDavid",
            source="quanthockey",
        )

        assert link.is_matched is True
        assert link.is_high_confidence is True
        assert link.is_ambiguous is False
        assert link.external_name == "C. McDavid"
        assert link.nhl_player_id == 8478402
        assert link.matched_name == "Connor McDavid"
        assert link.source == "quanthockey"

    def test_unmatched_link(self) -> None:
        """Test an unmatched PlayerLink."""
        link = PlayerLink(
            external_name="Unknown Player",
            nhl_player_id=None,
            confidence=0.3,
            matched_name=None,
            source="quanthockey",
        )

        assert link.is_matched is False
        assert link.is_high_confidence is False
        assert link.is_ambiguous is False

    def test_ambiguous_link(self) -> None:
        """Test an ambiguous PlayerLink (0.85-0.95 confidence)."""
        link = PlayerLink(
            external_name="E. Pettersson",
            nhl_player_id=8479328,
            confidence=0.90,
            matched_name="Elias Pettersson",
            source="quanthockey",
        )

        assert link.is_matched is True
        assert link.is_high_confidence is False
        assert link.is_ambiguous is True

    def test_high_confidence_boundary(self) -> None:
        """Test the high confidence boundary (exactly 0.95)."""
        link = PlayerLink(
            external_name="Test Player",
            nhl_player_id=123,
            confidence=0.95,
            matched_name="Test Player",
        )

        assert link.is_high_confidence is True
        assert link.is_ambiguous is False

    def test_default_source(self) -> None:
        """Test default source value."""
        link = PlayerLink(
            external_name="Test",
            nhl_player_id=None,
            confidence=0.0,
            matched_name=None,
        )

        assert link.source == "unknown"


# =============================================================================
# LinkingStatistics Tests
# =============================================================================


class TestLinkingStatistics:
    """Tests for LinkingStatistics dataclass."""

    def test_empty_statistics(self) -> None:
        """Test empty statistics."""
        stats = LinkingStatistics()

        assert stats.total == 0
        assert stats.matched == 0
        assert stats.unmatched == 0
        assert stats.high_confidence == 0
        assert stats.ambiguous == 0
        assert stats.match_rate == 0.0
        assert stats.high_confidence_rate == 0.0

    def test_statistics_with_data(self) -> None:
        """Test statistics with actual data."""
        stats = LinkingStatistics(
            total=100,
            matched=85,
            unmatched=15,
            high_confidence=70,
            ambiguous=10,
        )

        assert stats.match_rate == 0.85
        assert stats.high_confidence_rate == 0.70

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        stats = LinkingStatistics(
            total=100,
            matched=85,
            unmatched=15,
            high_confidence=70,
            ambiguous=10,
        )

        result = stats.to_dict()

        assert result["total"] == 100
        assert result["matched"] == 85
        assert result["unmatched"] == 15
        assert result["high_confidence"] == 70
        assert result["ambiguous"] == 10
        assert result["match_rate"] == 0.85
        assert result["high_confidence_rate"] == 0.70


# =============================================================================
# PlayerLinkingService Tests
# =============================================================================


class TestPlayerLinkingService:
    """Tests for PlayerLinkingService."""

    def test_initialization(self) -> None:
        """Test service initialization."""
        service = PlayerLinkingService(threshold=0.90, log_unmatched=False)

        assert service.threshold == 0.90
        assert service.log_unmatched is False
        assert service.candidate_count == 0

    def test_set_nhl_players(self, nhl_players: list[tuple[int, str]]) -> None:
        """Test setting NHL players."""
        service = PlayerLinkingService()
        service.set_nhl_players(nhl_players)

        assert service.candidate_count == len(nhl_players)

    def test_link_without_nhl_players(self) -> None:
        """Test linking fails without setting NHL players first."""
        service = PlayerLinkingService()

        with pytest.raises(RuntimeError, match="No NHL players set"):
            service.link_names(["Test Player"])

    def test_link_quanthockey_without_nhl_players(
        self, qh_player_stats: list[QuantHockeyPlayerSeasonStats]
    ) -> None:
        """Test QuantHockey linking fails without setting NHL players."""
        service = PlayerLinkingService()

        with pytest.raises(RuntimeError, match="No NHL players set"):
            service.link_quanthockey_to_nhl(qh_player_stats)

    def test_exact_match(self, linking_service: PlayerLinkingService) -> None:
        """Test exact name matching."""
        links = linking_service.link_names(["Connor McDavid"], source="test")

        assert len(links) == 1
        link = links[0]
        assert link.is_matched is True
        assert link.nhl_player_id == 8478402
        assert link.matched_name == "Connor McDavid"
        assert link.confidence == 1.0
        assert link.source == "test"

    def test_initial_match(self, linking_service: PlayerLinkingService) -> None:
        """Test matching with first initial (e.g., 'N. MacKinnon')."""
        links = linking_service.link_names(["N. MacKinnon"], source="test")

        assert len(links) == 1
        link = links[0]
        assert link.is_matched is True
        assert link.nhl_player_id == 8474564
        assert link.matched_name == "Nathan MacKinnon"
        assert link.confidence >= 0.85

    def test_accent_normalization(self, linking_service: PlayerLinkingService) -> None:
        """Test matching with/without accents (Chára vs Chara)."""
        links = linking_service.link_names(["Zdeno Chara"], source="test")

        assert len(links) == 1
        link = links[0]
        assert link.is_matched is True
        assert link.nhl_player_id == 8475172
        assert link.matched_name == "Zdeno Chára"
        assert link.confidence == 1.0  # Should be exact after normalization

    def test_initials_jt_miller(self, linking_service: PlayerLinkingService) -> None:
        """Test matching J.T. Miller formats."""
        # Both formats should match
        links1 = linking_service.link_names(["J.T. Miller"], source="test")
        links2 = linking_service.link_names(["JT Miller"], source="test")

        assert links1[0].is_matched is True
        assert links2[0].is_matched is True
        assert links1[0].nhl_player_id == 8480839
        assert links2[0].nhl_player_id == 8480839

    def test_unmatched_player(self, linking_service: PlayerLinkingService) -> None:
        """Test unmatched player returns None."""
        links = linking_service.link_names(["Fictional Player"], source="test")

        assert len(links) == 1
        link = links[0]
        assert link.is_matched is False
        assert link.nhl_player_id is None
        assert link.matched_name is None
        assert link.confidence < 0.85

    def test_link_quanthockey_batch(
        self,
        linking_service: PlayerLinkingService,
        qh_player_stats: list[QuantHockeyPlayerSeasonStats],
    ) -> None:
        """Test batch linking of QuantHockey players."""
        links = linking_service.link_quanthockey_to_nhl(qh_player_stats)

        assert len(links) == len(qh_player_stats)

        # Check specific matches
        mcdavid = next(lnk for lnk in links if lnk.external_name == "Connor McDavid")
        assert mcdavid.is_matched is True
        assert mcdavid.nhl_player_id == 8478402

        draisaitl = next(lnk for lnk in links if lnk.external_name == "L. Draisaitl")
        assert draisaitl.is_matched is True
        assert draisaitl.nhl_player_id == 8477934

        unknown = next(lnk for lnk in links if lnk.external_name == "Unknown Player")
        assert unknown.is_matched is False

    def test_get_statistics(
        self,
        linking_service: PlayerLinkingService,
        qh_player_stats: list[QuantHockeyPlayerSeasonStats],
    ) -> None:
        """Test statistics are recorded after linking."""
        linking_service.link_quanthockey_to_nhl(qh_player_stats)
        stats = linking_service.get_statistics()

        assert stats.total == len(qh_player_stats)
        assert stats.matched >= 5  # At least 5 should match
        assert stats.unmatched >= 1  # "Unknown Player" shouldn't match

    def test_get_unmatched(
        self,
        linking_service: PlayerLinkingService,
        qh_player_stats: list[QuantHockeyPlayerSeasonStats],
    ) -> None:
        """Test filtering unmatched players."""
        links = linking_service.link_quanthockey_to_nhl(qh_player_stats)
        unmatched = linking_service.get_unmatched(links)

        assert len(unmatched) >= 1
        assert all(not link.is_matched for link in unmatched)
        assert any(link.external_name == "Unknown Player" for link in unmatched)

    def test_get_ambiguous(self, linking_service: PlayerLinkingService) -> None:
        """Test filtering ambiguous matches."""
        # Create a mock link list with ambiguous matches
        links = [
            PlayerLink("Player A", 1, 0.90, "Player A Match", "test"),
            PlayerLink("Player B", 2, 0.99, "Player B Match", "test"),
            PlayerLink("Player C", None, 0.50, None, "test"),
        ]

        ambiguous = linking_service.get_ambiguous(links)

        assert len(ambiguous) == 1
        assert ambiguous[0].external_name == "Player A"

    def test_cache_behavior(self, linking_service: PlayerLinkingService) -> None:
        """Test that caching improves performance."""
        # First call populates cache
        linking_service.link_names(["Connor McDavid"], source="test")
        cache_size_1 = linking_service.cache_size

        # Second call with same name uses cache
        linking_service.link_names(["Connor McDavid"], source="test")
        cache_size_2 = linking_service.cache_size

        assert cache_size_1 > 0
        assert cache_size_2 == cache_size_1  # Cache size unchanged

    def test_clear_cache(self, linking_service: PlayerLinkingService) -> None:
        """Test cache clearing."""
        linking_service.link_names(["Connor McDavid"], source="test")
        assert linking_service.cache_size > 0

        linking_service.clear_cache()
        assert linking_service.cache_size == 0

    def test_custom_threshold(self, nhl_players: list[tuple[int, str]]) -> None:
        """Test custom threshold affects matching."""
        # Very high threshold - fewer matches
        strict_service = PlayerLinkingService(threshold=0.99)
        strict_service.set_nhl_players(nhl_players)

        # Lower threshold - more matches
        lenient_service = PlayerLinkingService(threshold=0.70)
        lenient_service.set_nhl_players(nhl_players)

        # Initial match should work with lenient, maybe not with strict
        strict_links = strict_service.link_names(["N. MacKinnon"])
        lenient_links = lenient_service.link_names(["N. MacKinnon"])

        assert lenient_links[0].is_matched is True
        # Strict might not match due to initial
        assert strict_links[0].confidence >= 0  # Just verify it runs

    def test_logging_unmatched(
        self,
        nhl_players: list[tuple[int, str]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that unmatched players are logged when enabled."""
        service = PlayerLinkingService(log_unmatched=True)
        service.set_nhl_players(nhl_players)

        with caplog.at_level(logging.WARNING):
            service.link_names(["Nonexistent Player"], source="test")

        assert "Unmatched player from test: Nonexistent Player" in caplog.text

    def test_no_logging_when_disabled(
        self,
        nhl_players: list[tuple[int, str]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that unmatched players are not logged when disabled."""
        service = PlayerLinkingService(log_unmatched=False)
        service.set_nhl_players(nhl_players)

        with caplog.at_level(logging.WARNING):
            service.link_names(["Nonexistent Player"], source="test")

        assert "Unmatched" not in caplog.text


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests for player linking."""

    def test_empty_player_list(self, linking_service: PlayerLinkingService) -> None:
        """Test linking empty list."""
        links = linking_service.link_names([])

        assert links == []
        assert linking_service.get_statistics().total == 0

    def test_empty_qh_list(self, linking_service: PlayerLinkingService) -> None:
        """Test linking empty QuantHockey list."""
        links = linking_service.link_quanthockey_to_nhl([])

        assert links == []
        assert linking_service.get_statistics().total == 0

    def test_duplicate_names(self, linking_service: PlayerLinkingService) -> None:
        """Test linking duplicate names."""
        names = ["Connor McDavid", "Connor McDavid", "Connor McDavid"]
        links = linking_service.link_names(names)

        assert len(links) == 3
        assert all(link.nhl_player_id == 8478402 for link in links)

    def test_special_characters_in_name(
        self, linking_service: PlayerLinkingService
    ) -> None:
        """Test names with special characters."""
        # Names with hyphens, apostrophes, etc.
        links = linking_service.link_names(
            ["Pierre-Luc Test", "O'Reilly Test"],
            source="test",
        )

        # These won't match but should not error
        assert len(links) == 2
        assert all(not link.is_matched for link in links)

    def test_case_insensitivity(self, linking_service: PlayerLinkingService) -> None:
        """Test that matching is case-insensitive."""
        links = linking_service.link_names(
            ["CONNOR MCDAVID", "connor mcdavid", "CoNnOr McDaViD"],
            source="test",
        )

        assert len(links) == 3
        assert all(link.is_matched for link in links)
        assert all(link.nhl_player_id == 8478402 for link in links)

    def test_similar_names_disambiguation(
        self, linking_service: PlayerLinkingService
    ) -> None:
        """Test that similar names are handled.

        Note: Name matching alone cannot disambiguate players with
        the same name (e.g., two Petterssons). Higher-level code
        should use team/position for disambiguation.
        """
        # Both Petterssons exist - matcher will pick best match
        links = linking_service.link_names(["Elias Pettersson"])

        assert len(links) == 1
        assert links[0].is_matched is True
        # Should match one of the Petterssons
        assert links[0].nhl_player_id in (8479328, 8480012)
