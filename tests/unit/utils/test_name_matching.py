"""Unit tests for player name matching utilities."""

from __future__ import annotations

import pytest

from nhl_api.utils.name_matching import (
    MatchResult,
    PlayerNameMatcher,
    _extract_name_parts,
    _first_name_matches,
    _string_similarity,
    find_best_match,
    name_similarity,
    normalize_name,
)


class TestNormalizeName:
    """Tests for normalize_name function."""

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert normalize_name("") == ""

    def test_simple_name(self) -> None:
        """Simple name is lowercased."""
        assert normalize_name("Nathan MacKinnon") == "nathan mackinnon"

    def test_accented_characters(self) -> None:
        """Accents are removed."""
        assert normalize_name("Zdeno Chára") == "zdeno chara"
        assert normalize_name("Patrice Bergeron") == "patrice bergeron"
        assert normalize_name("André Burakovsky") == "andre burakovsky"

    def test_suffix_junior(self) -> None:
        """Jr. suffix is removed."""
        assert normalize_name("Alex Ovechkin Jr.") == "alex ovechkin"
        assert normalize_name("Alex Ovechkin Jr") == "alex ovechkin"

    def test_suffix_senior(self) -> None:
        """Sr. suffix is removed."""
        assert normalize_name("Gordie Howe Sr.") == "gordie howe"
        assert normalize_name("Gordie Howe Sr") == "gordie howe"

    def test_suffix_roman_numerals(self) -> None:
        """Roman numeral suffixes are removed."""
        assert normalize_name("Henrik Lundqvist III") == "henrik lundqvist"
        assert normalize_name("Player Name II") == "player name"
        assert normalize_name("Player Name IV") == "player name"
        assert normalize_name("Player Name V") == "player name"

    def test_hyphenated_names(self) -> None:
        """Hyphens are converted to spaces."""
        assert normalize_name("Pierre-Luc Dubois") == "pierre luc dubois"
        assert normalize_name("Jean-Gabriel Pageau") == "jean gabriel pageau"

    def test_multiple_spaces(self) -> None:
        """Multiple spaces are collapsed."""
        assert normalize_name("Nathan   MacKinnon") == "nathan mackinnon"
        assert normalize_name("  Nathan  MacKinnon  ") == "nathan mackinnon"

    def test_combined_normalizations(self) -> None:
        """Multiple normalizations work together."""
        assert normalize_name("André-Pierre Côté Jr.") == "andre pierre cote"


class TestExtractNameParts:
    """Tests for _extract_name_parts helper function."""

    def test_empty_string(self) -> None:
        """Empty string returns empty parts."""
        assert _extract_name_parts("") == ("", [])

    def test_single_name(self) -> None:
        """Single name is treated as last name."""
        assert _extract_name_parts("mackinnon") == ("mackinnon", [])

    def test_two_part_name(self) -> None:
        """Two-part name splits correctly."""
        assert _extract_name_parts("nathan mackinnon") == ("mackinnon", ["nathan"])

    def test_three_part_name(self) -> None:
        """Three-part name includes middle name."""
        assert _extract_name_parts("jonathan tanner miller") == (
            "miller",
            ["jonathan", "tanner"],
        )

    def test_hyphenated_normalized(self) -> None:
        """Pre-normalized hyphenated names split correctly."""
        assert _extract_name_parts("pierre luc dubois") == (
            "dubois",
            ["pierre", "luc"],
        )


class TestFirstNameMatches:
    """Tests for _first_name_matches helper function."""

    def test_empty_parts(self) -> None:
        """Empty parts are considered a match."""
        assert _first_name_matches([], []) is True
        assert _first_name_matches(["nathan"], []) is True
        assert _first_name_matches([], ["nathan"]) is True

    def test_exact_match(self) -> None:
        """Exact first names match."""
        assert _first_name_matches(["nathan"], ["nathan"]) is True
        assert _first_name_matches(["nathan", "cole"], ["nathan", "cole"]) is True

    def test_initial_match(self) -> None:
        """Single letter initial matches full name."""
        assert _first_name_matches(["n"], ["nathan"]) is True
        assert _first_name_matches(["nathan"], ["n"]) is True

    def test_nickname_match(self) -> None:
        """Common beginning matches (Nate/Nathan)."""
        assert _first_name_matches(["nate"], ["nathan"]) is True
        assert _first_name_matches(["nathan"], ["nate"]) is True

    def test_no_match(self) -> None:
        """Different first names don't match."""
        assert _first_name_matches(["alex"], ["nathan"]) is False
        assert _first_name_matches(["cale"], ["nathan"]) is False


class TestStringSimilarity:
    """Tests for _string_similarity helper function."""

    def test_identical_strings(self) -> None:
        """Identical strings have similarity 1.0."""
        assert _string_similarity("mackinnon", "mackinnon") == 1.0

    def test_empty_strings(self) -> None:
        """Empty strings have similarity 0.0."""
        assert _string_similarity("", "") == 1.0  # Both empty = identical
        assert _string_similarity("test", "") == 0.0
        assert _string_similarity("", "test") == 0.0

    def test_single_character_difference(self) -> None:
        """Single character difference reduces similarity."""
        sim = _string_similarity("mackinnon", "mackinon")  # Missing 'n'
        assert 0.8 < sim < 1.0

    def test_completely_different(self) -> None:
        """Completely different strings have low similarity."""
        sim = _string_similarity("abcd", "wxyz")
        assert sim < 0.5

    def test_caching(self) -> None:
        """Results are cached for repeated calls."""
        # First call
        sim1 = _string_similarity("test", "tset")
        # Second call should use cache
        sim2 = _string_similarity("test", "tset")
        assert sim1 == sim2


class TestNameSimilarity:
    """Tests for name_similarity function."""

    def test_exact_match(self) -> None:
        """Exact match returns 1.0."""
        assert name_similarity("Nathan MacKinnon", "Nathan MacKinnon") == 1.0

    def test_case_insensitive(self) -> None:
        """Matching is case insensitive."""
        assert name_similarity("Nathan MacKinnon", "nathan mackinnon") == 1.0

    def test_accent_insensitive(self) -> None:
        """Matching ignores accents."""
        assert name_similarity("Zdeno Chára", "Zdeno Chara") == 1.0

    def test_initial_match(self) -> None:
        """Initial matches full first name."""
        sim = name_similarity("N. MacKinnon", "Nathan MacKinnon")
        assert sim >= 0.95

    def test_suffix_ignored(self) -> None:
        """Suffixes are ignored in matching."""
        sim = name_similarity("Alex Ovechkin Jr.", "Alex Ovechkin")
        assert sim >= 0.95

    def test_different_last_names(self) -> None:
        """Different last names have low similarity."""
        sim = name_similarity("Nathan MacKinnon", "Nathan Crosby")
        assert sim < 0.5

    def test_empty_names(self) -> None:
        """Empty names return 0.0 similarity."""
        assert name_similarity("", "Nathan MacKinnon") == 0.0
        assert name_similarity("Nathan MacKinnon", "") == 0.0
        assert name_similarity("", "") == 0.0

    def test_hyphenated_name(self) -> None:
        """Hyphenated names match non-hyphenated."""
        sim = name_similarity("Pierre-Luc Dubois", "Pierre Luc Dubois")
        assert sim >= 0.95

    def test_middle_initial(self) -> None:
        """Names with middle initials match when initials match name parts."""
        # J.T. Miller = Jonathan Tanner Miller (J and T are first+middle initials)
        sim = name_similarity("J.T. Miller", "Jonathan Tanner Miller")
        assert sim >= 0.85

        # Single initial still works
        sim = name_similarity("J. Miller", "Jonathan Miller")
        assert sim >= 0.85


class TestFindBestMatch:
    """Tests for find_best_match function."""

    @pytest.fixture
    def nhl_players(self) -> list[str]:
        """Sample NHL player names."""
        return [
            "Nathan MacKinnon",
            "Cale Makar",
            "Mikko Rantanen",
            "Sidney Crosby",
            "Alex Ovechkin",
            "Pierre-Luc Dubois",
        ]

    def test_exact_match(self, nhl_players: list[str]) -> None:
        """Exact match is found."""
        result = find_best_match("Nathan MacKinnon", nhl_players)
        assert result == "Nathan MacKinnon"

    def test_initial_match(self, nhl_players: list[str]) -> None:
        """Initial matches full name."""
        result = find_best_match("N. MacKinnon", nhl_players)
        assert result == "Nathan MacKinnon"

    def test_no_match_below_threshold(self, nhl_players: list[str]) -> None:
        """No match returns None when below threshold."""
        result = find_best_match("Wayne Gretzky", nhl_players)
        assert result is None

    def test_custom_threshold(self, nhl_players: list[str]) -> None:
        """Custom threshold affects matching."""
        # Very low threshold should match more
        result = find_best_match("MacKinnon", nhl_players, threshold=0.5)
        assert result == "Nathan MacKinnon"

    def test_empty_candidates(self) -> None:
        """Empty candidates returns None."""
        result = find_best_match("Nathan MacKinnon", [])
        assert result is None

    def test_empty_name(self, nhl_players: list[str]) -> None:
        """Empty name returns None."""
        result = find_best_match("", nhl_players)
        assert result is None

    def test_hyphenated_match(self, nhl_players: list[str]) -> None:
        """Hyphenated name matches."""
        result = find_best_match("Pierre Luc Dubois", nhl_players)
        assert result == "Pierre-Luc Dubois"


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_successful_match(self) -> None:
        """Successful match has is_match True."""
        result = MatchResult(matched_name="Nathan MacKinnon", score=0.95)
        assert result.is_match is True
        assert result.matched_name == "Nathan MacKinnon"
        assert result.score == 0.95

    def test_no_match(self) -> None:
        """No match has is_match False."""
        result = MatchResult(matched_name=None, score=0.5)
        assert result.is_match is False
        assert result.matched_name is None


class TestPlayerNameMatcher:
    """Tests for PlayerNameMatcher class."""

    @pytest.fixture
    def matcher(self) -> PlayerNameMatcher:
        """Create a matcher with sample candidates."""
        candidates = [
            "Nathan MacKinnon",
            "Cale Makar",
            "Mikko Rantanen",
            "Sidney Crosby",
            "Alex Ovechkin",
        ]
        return PlayerNameMatcher(threshold=0.85, candidates=candidates)

    def test_exact_match(self, matcher: PlayerNameMatcher) -> None:
        """Exact match returns 1.0 score."""
        result = matcher.match("Nathan MacKinnon")
        assert result.matched_name == "Nathan MacKinnon"
        assert result.score == 1.0

    def test_initial_match(self, matcher: PlayerNameMatcher) -> None:
        """Initial matches full name."""
        result = matcher.match("N. MacKinnon")
        assert result.matched_name == "Nathan MacKinnon"
        assert result.score >= 0.95

    def test_no_match(self, matcher: PlayerNameMatcher) -> None:
        """No match when below threshold."""
        result = matcher.match("Wayne Gretzky")
        assert result.matched_name is None
        assert result.is_match is False

    def test_caching(self, matcher: PlayerNameMatcher) -> None:
        """Results are cached."""
        # First call
        result1 = matcher.match("N. MacKinnon")
        cache_size1 = matcher.cache_size

        # Second call should use cache
        result2 = matcher.match("N. MacKinnon")
        cache_size2 = matcher.cache_size

        assert result1.matched_name == result2.matched_name
        assert result1.score == result2.score
        assert cache_size1 == cache_size2  # No new cache entry

    def test_set_candidates(self) -> None:
        """set_candidates updates candidates and clears cache."""
        matcher = PlayerNameMatcher(threshold=0.85)
        matcher.set_candidates(["Nathan MacKinnon", "Cale Makar"])

        result = matcher.match("Nathan MacKinnon")
        assert result.matched_name == "Nathan MacKinnon"
        assert matcher.cache_size == 1

        # Set new candidates should clear cache
        matcher.set_candidates(["Sidney Crosby"])
        assert matcher.cache_size == 0

        result = matcher.match("Nathan MacKinnon")
        assert result.matched_name is None

    def test_match_all(self, matcher: PlayerNameMatcher) -> None:
        """match_all returns results for all names."""
        names = ["Nathan MacKinnon", "N. MacKinnon", "Wayne Gretzky"]
        results = matcher.match_all(names)

        assert len(results) == 3
        assert results[0].matched_name == "Nathan MacKinnon"
        assert results[1].matched_name == "Nathan MacKinnon"
        assert results[2].matched_name is None

    def test_clear_cache(self, matcher: PlayerNameMatcher) -> None:
        """clear_cache empties the cache."""
        matcher.match("Nathan MacKinnon")
        assert matcher.cache_size > 0

        matcher.clear_cache()
        assert matcher.cache_size == 0

    def test_empty_candidates(self) -> None:
        """Empty candidates list works."""
        matcher = PlayerNameMatcher()
        result = matcher.match("Nathan MacKinnon")
        assert result.matched_name is None

    def test_custom_threshold(self) -> None:
        """Custom threshold affects matching."""
        candidates = ["Nathan MacKinnon"]

        # High threshold - initial might not match
        high_matcher = PlayerNameMatcher(threshold=0.99, candidates=candidates)
        result = high_matcher.match("N. MacKinnon")
        assert result.matched_name is None  # 0.95 < 0.99

        # Lower threshold - should match
        low_matcher = PlayerNameMatcher(threshold=0.85, candidates=candidates)
        result = low_matcher.match("N. MacKinnon")
        assert result.matched_name == "Nathan MacKinnon"


class TestRealWorldExamples:
    """Integration tests with real NHL player name variations."""

    @pytest.fixture
    def nhl_roster(self) -> list[str]:
        """A sample of real NHL API player names."""
        return [
            "Nathan MacKinnon",
            "Sidney Crosby",
            "Alex Ovechkin",
            "Connor McDavid",
            "Auston Matthews",
            "Pierre-Luc Dubois",
            "Jean-Gabriel Pageau",
            "Zdeno Chara",
            "Jonathan Tanner Miller",
            "Patrick Kane",
            "Leon Draisaitl",
            "Artemi Panarin",
        ]

    def test_quanthockey_format(self, nhl_roster: list[str]) -> None:
        """QuantHockey uses first initial format."""
        matcher = PlayerNameMatcher(threshold=0.85, candidates=nhl_roster)

        # QuantHockey format: "N. MacKinnon"
        result = matcher.match("N. MacKinnon")
        assert result.matched_name == "Nathan MacKinnon"

        result = matcher.match("S. Crosby")
        assert result.matched_name == "Sidney Crosby"

        result = matcher.match("C. McDavid")
        assert result.matched_name == "Connor McDavid"

    def test_accented_names(self, nhl_roster: list[str]) -> None:
        """Accented characters in names."""
        matcher = PlayerNameMatcher(threshold=0.85, candidates=nhl_roster)

        # With accent
        result = matcher.match("Zdeno Chára")
        assert result.matched_name == "Zdeno Chara"

    def test_hyphenated_names(self, nhl_roster: list[str]) -> None:
        """Hyphenated names match both formats."""
        matcher = PlayerNameMatcher(threshold=0.85, candidates=nhl_roster)

        # Without hyphen
        result = matcher.match("Pierre Luc Dubois")
        assert result.matched_name == "Pierre-Luc Dubois"

        result = matcher.match("Jean Gabriel Pageau")
        assert result.matched_name == "Jean-Gabriel Pageau"

    def test_jt_miller(self, nhl_roster: list[str]) -> None:
        """J.T. Miller matches Jonathan Tanner Miller."""
        matcher = PlayerNameMatcher(threshold=0.85, candidates=nhl_roster)

        result = matcher.match("J.T. Miller")
        assert result.matched_name == "Jonathan Tanner Miller"

    def test_batch_matching(self, nhl_roster: list[str]) -> None:
        """Batch matching works for multiple names."""
        matcher = PlayerNameMatcher(threshold=0.85, candidates=nhl_roster)

        # DailyFaceoff format names
        df_names = [
            "N. MacKinnon",
            "P. Kane",
            "L. Draisaitl",
            "A. Panarin",
            "Unknown Player",
        ]

        results = matcher.match_all(df_names)

        assert results[0].matched_name == "Nathan MacKinnon"
        assert results[1].matched_name == "Patrick Kane"
        assert results[2].matched_name == "Leon Draisaitl"
        assert results[3].matched_name == "Artemi Panarin"
        assert results[4].matched_name is None
