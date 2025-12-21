"""Unit tests for DailyFaceoff team mapping."""

from __future__ import annotations

import pytest

from nhl_api.downloaders.sources.dailyfaceoff.team_mapping import (
    TEAM_ABBREVIATIONS,
    TEAM_SLUGS,
    get_team_abbreviation,
    get_team_id_from_slug,
    get_team_slug,
)


class TestTeamSlugs:
    """Tests for TEAM_SLUGS mapping."""

    def test_all_32_teams_present(self) -> None:
        """Verify all 32 current NHL teams are mapped."""
        # Current active teams (excluding historical Arizona at ID 53)
        expected_ids = {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,  # Eastern originals
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,  # More Eastern/Central
            21,
            22,
            23,
            24,
            25,
            26,
            28,
            29,
            30,  # Western
            52,
            53,
            54,
            55,
            59,  # Expansion/relocation
        }
        assert set(TEAM_SLUGS.keys()) == expected_ids

    def test_slug_format(self) -> None:
        """Verify all slugs are lowercase with hyphens."""
        for team_id, slug in TEAM_SLUGS.items():
            assert slug == slug.lower(), f"Team {team_id} slug not lowercase: {slug}"
            assert " " not in slug, f"Team {team_id} slug has spaces: {slug}"
            assert slug.replace("-", "").isalpha(), (
                f"Team {team_id} slug has invalid chars: {slug}"
            )

    def test_specific_teams(self) -> None:
        """Verify specific team mappings."""
        assert TEAM_SLUGS[1] == "new-jersey-devils"
        assert TEAM_SLUGS[10] == "toronto-maple-leafs"
        assert TEAM_SLUGS[19] == "st-louis-blues"
        assert TEAM_SLUGS[54] == "vegas-golden-knights"
        assert TEAM_SLUGS[55] == "seattle-kraken"
        assert TEAM_SLUGS[59] == "utah-hockey-club"

    def test_historical_arizona(self) -> None:
        """Verify Arizona Coyotes still in mapping for historical data."""
        assert 53 in TEAM_SLUGS
        assert TEAM_SLUGS[53] == "arizona-coyotes"


class TestTeamAbbreviations:
    """Tests for TEAM_ABBREVIATIONS mapping."""

    def test_all_teams_have_abbreviations(self) -> None:
        """Verify abbreviations match slugs."""
        assert set(TEAM_ABBREVIATIONS.keys()) == set(TEAM_SLUGS.keys())

    def test_abbreviation_format(self) -> None:
        """Verify all abbreviations are 3 uppercase letters."""
        for team_id, abbrev in TEAM_ABBREVIATIONS.items():
            assert len(abbrev) == 3, f"Team {team_id} abbrev wrong length: {abbrev}"
            assert abbrev == abbrev.upper(), f"Team {team_id} abbrev not uppercase"
            assert abbrev.isalpha(), f"Team {team_id} abbrev not alphabetic: {abbrev}"

    def test_specific_abbreviations(self) -> None:
        """Verify specific team abbreviations."""
        assert TEAM_ABBREVIATIONS[1] == "NJD"
        assert TEAM_ABBREVIATIONS[10] == "TOR"
        assert TEAM_ABBREVIATIONS[26] == "LAK"
        assert TEAM_ABBREVIATIONS[54] == "VGK"
        assert TEAM_ABBREVIATIONS[59] == "UTA"


class TestGetTeamSlug:
    """Tests for get_team_slug function."""

    def test_valid_team_id(self) -> None:
        """Test getting slug for valid team ID."""
        assert get_team_slug(10) == "toronto-maple-leafs"
        assert get_team_slug(6) == "boston-bruins"

    def test_invalid_team_id(self) -> None:
        """Test that invalid team ID raises KeyError."""
        with pytest.raises(KeyError, match="Unknown team ID: 999"):
            get_team_slug(999)

    def test_missing_team_id_11(self) -> None:
        """Test that team ID 11 (unused) raises KeyError."""
        with pytest.raises(KeyError, match="Unknown team ID: 11"):
            get_team_slug(11)


class TestGetTeamAbbreviation:
    """Tests for get_team_abbreviation function."""

    def test_valid_team_id(self) -> None:
        """Test getting abbreviation for valid team ID."""
        assert get_team_abbreviation(10) == "TOR"
        assert get_team_abbreviation(6) == "BOS"

    def test_invalid_team_id(self) -> None:
        """Test that invalid team ID raises KeyError."""
        with pytest.raises(KeyError, match="Unknown team ID: 999"):
            get_team_abbreviation(999)


class TestGetTeamIdFromSlug:
    """Tests for get_team_id_from_slug function."""

    def test_valid_slug(self) -> None:
        """Test getting team ID from valid slug."""
        assert get_team_id_from_slug("toronto-maple-leafs") == 10
        assert get_team_id_from_slug("boston-bruins") == 6

    def test_invalid_slug(self) -> None:
        """Test that invalid slug raises KeyError."""
        with pytest.raises(KeyError, match="Unknown team slug: invalid-team"):
            get_team_id_from_slug("invalid-team")

    def test_all_slugs_reversible(self) -> None:
        """Test that all slugs can be reversed to team IDs."""
        for team_id, slug in TEAM_SLUGS.items():
            assert get_team_id_from_slug(slug) == team_id
