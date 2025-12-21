"""Player name matching utilities for cross-source data linking.

Handles variations in player names across different data sources:
- NHL API: "Nathan MacKinnon"
- QuantHockey: "N. MacKinnon"
- DailyFaceoff: "Nate MacKinnon"

Supports:
- First initial vs full name matching
- Accented character normalization
- Suffix removal (Jr., Sr., III, etc.)
- Hyphenated name handling
- Middle name/initial handling
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

# Suffixes to strip from names
_SUFFIXES = frozenset(
    {
        "jr",
        "jr.",
        "sr",
        "sr.",
        "i",
        "ii",
        "iii",
        "iv",
        "v",
    }
)

# Pattern to match initials like "J." or "J.T."
_INITIAL_PATTERN = re.compile(r"^([A-Z])\.$")

# Pattern to split names on whitespace and hyphens (keeping hyphens)
_NAME_SPLIT_PATTERN = re.compile(r"[\s]+")


def normalize_name(name: str) -> str:
    """Normalize a player name for comparison.

    Performs:
    - Unicode normalization (NFD) and accent removal
    - Lowercase conversion
    - Suffix removal (Jr., Sr., III, etc.)
    - Hyphen-to-space conversion
    - Multiple space collapse
    - Strip leading/trailing whitespace

    Args:
        name: The player name to normalize.

    Returns:
        Normalized name suitable for comparison.

    Examples:
        >>> normalize_name("Zdeno Chára")
        'zdeno chara'
        >>> normalize_name("Alex Ovechkin Jr.")
        'alex ovechkin'
        >>> normalize_name("Pierre-Luc Dubois")
        'pierre luc dubois'
    """
    if not name:
        return ""

    # Unicode normalize (NFD) and remove combining characters (accents)
    normalized = unicodedata.normalize("NFD", name)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # Lowercase
    normalized = normalized.lower()

    # Replace hyphens with spaces
    normalized = normalized.replace("-", " ")

    # Remove periods (common in initials like "J.T." or "N.")
    normalized = normalized.replace(".", "")

    # Split into parts and filter suffixes
    parts = _NAME_SPLIT_PATTERN.split(normalized)
    parts = [p.strip() for p in parts if p.strip()]
    parts = [p for p in parts if p not in _SUFFIXES]

    # Rejoin and collapse multiple spaces
    result = " ".join(parts)

    return result


def _extract_name_parts(name: str) -> tuple[str, list[str]]:
    """Extract last name and first/middle name parts from a normalized name.

    Args:
        name: Normalized player name.

    Returns:
        Tuple of (last_name, [first_name, middle_names...])
    """
    parts = name.split()
    if len(parts) == 0:
        return "", []
    if len(parts) == 1:
        return parts[0], []

    # Last name is the last part, everything else is first/middle
    return parts[-1], parts[:-1]


def _first_name_matches(name1_parts: list[str], name2_parts: list[str]) -> bool:
    """Check if first name parts match, handling initials.

    Handles cases like:
    - "nathan" matches "nathan"
    - "n" matches "nathan" (initial)
    - "n" matches "nate" (initial)
    - "jt" matches ["jonathan", "tanner"] (combined initials)

    Args:
        name1_parts: First/middle name parts from first name.
        name2_parts: First/middle name parts from second name.

    Returns:
        True if the first names are considered a match.
    """
    if not name1_parts or not name2_parts:
        return True  # If either has no first name, consider it a match

    # Get first parts
    first1 = name1_parts[0]
    first2 = name2_parts[0]

    # Check for exact match
    if first1 == first2:
        return True

    # Check for initial match (single letter matches beginning of name)
    if len(first1) == 1 and first2.startswith(first1):
        return True
    if len(first2) == 1 and first1.startswith(first2):
        return True

    # Check if names share common beginning (handles Nate/Nathan)
    # Both names must be at least 3 chars and share a 3-char prefix
    if len(first1) >= 3 and len(first2) >= 3 and first1[:3] == first2[:3]:
        return True

    # Handle combined initials like "jt" matching ["jonathan", "tanner"]
    # Check if first1 is initials that match first letters of name2_parts
    if len(first1) <= 3 and len(first1) == len(name2_parts):
        if all(first1[i] == name2_parts[i][0] for i in range(len(first1))):
            return True

    # Check reverse: name1_parts initials match combined first2
    if len(first2) <= 3 and len(first2) == len(name1_parts):
        if all(first2[i] == name1_parts[i][0] for i in range(len(first2))):
            return True

    return False


def name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity score between two player names.

    Uses a combination of:
    - Exact match detection
    - Last name matching
    - First name/initial matching
    - Levenshtein-based similarity for fuzzy matching

    Args:
        name1: First player name (raw, not normalized).
        name2: Second player name (raw, not normalized).

    Returns:
        Similarity score from 0.0 (no match) to 1.0 (exact match).

    Examples:
        >>> name_similarity("Nathan MacKinnon", "Nathan MacKinnon")
        1.0
        >>> name_similarity("N. MacKinnon", "Nathan MacKinnon")
        0.95
        >>> name_similarity("Zdeno Chára", "Zdeno Chara")
        1.0
    """
    # Normalize both names
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    # Handle empty names
    if not norm1 or not norm2:
        return 0.0

    # Exact match after normalization
    if norm1 == norm2:
        return 1.0

    # Extract name parts
    last1, first1_parts = _extract_name_parts(norm1)
    last2, first2_parts = _extract_name_parts(norm2)

    # Last names must be similar
    last_name_sim = _string_similarity(last1, last2)
    if last_name_sim < 0.8:
        return last_name_sim * 0.5  # Heavily penalize last name mismatch

    # Check first name matching
    if _first_name_matches(first1_parts, first2_parts):
        # Good first name match + good last name match
        if last_name_sim >= 0.95:
            return 0.95
        return 0.85 + (last_name_sim - 0.8) * 0.5

    # Fall back to overall string similarity
    overall_sim = _string_similarity(norm1, norm2)
    return overall_sim


@lru_cache(maxsize=10000)
def _string_similarity(s1: str, s2: str) -> float:
    """Calculate string similarity using Levenshtein distance.

    Uses a simple implementation that's sufficient for name matching.
    Results are cached for performance.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Similarity score from 0.0 to 1.0.
    """
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Calculate Levenshtein distance
    len1, len2 = len(s1), len(s2)

    # Use two-row approach for memory efficiency
    prev_row = list(range(len2 + 1))
    curr_row = [0] * (len2 + 1)

    for i in range(1, len1 + 1):
        curr_row[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr_row[j] = min(
                prev_row[j] + 1,  # deletion
                curr_row[j - 1] + 1,  # insertion
                prev_row[j - 1] + cost,  # substitution
            )
        prev_row, curr_row = curr_row, prev_row

    distance = prev_row[len2]
    max_len = max(len1, len2)

    return 1.0 - (distance / max_len)


def find_best_match(
    name: str,
    candidates: list[str],
    threshold: float = 0.85,
) -> str | None:
    """Find the best matching name from a list of candidates.

    Args:
        name: The name to match.
        candidates: List of candidate names to search.
        threshold: Minimum similarity score to accept (0.0 to 1.0).

    Returns:
        The best matching candidate name, or None if no match meets threshold.

    Examples:
        >>> candidates = ["Nathan MacKinnon", "Cale Makar", "Mikko Rantanen"]
        >>> find_best_match("N. MacKinnon", candidates)
        'Nathan MacKinnon'
        >>> find_best_match("Sidney Crosby", candidates)  # No match
        None
    """
    if not name or not candidates:
        return None

    best_match: str | None = None
    best_score = threshold

    for candidate in candidates:
        score = name_similarity(name, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match


@dataclass
class MatchResult:
    """Result of a name matching operation."""

    matched_name: str | None
    """The matched candidate name, or None if no match."""

    score: float
    """Similarity score (0.0 to 1.0)."""

    @property
    def is_match(self) -> bool:
        """Whether a match was found."""
        return self.matched_name is not None


@dataclass
class PlayerNameMatcher:
    """Batch player name matching with caching for performance.

    Designed for matching player names across data sources where the same
    candidates are matched against many input names.

    Attributes:
        threshold: Minimum similarity score to accept a match (default 0.85).
        candidates: List of candidate names to match against.

    Example:
        >>> matcher = PlayerNameMatcher(threshold=0.85)
        >>> matcher.set_candidates(["Nathan MacKinnon", "Cale Makar"])
        >>> result = matcher.match("N. MacKinnon")
        >>> result.matched_name
        'Nathan MacKinnon'
        >>> result.score
        0.95
    """

    threshold: float = 0.85
    candidates: list[str] = field(default_factory=list)
    _normalized_candidates: dict[str, str] = field(
        default_factory=dict, init=False, repr=False
    )
    _cache: dict[str, MatchResult] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize normalized candidates mapping."""
        if self.candidates:
            self._build_candidate_index()

    def set_candidates(self, candidates: list[str]) -> None:
        """Set the list of candidate names to match against.

        Clears any cached results and rebuilds the candidate index.

        Args:
            candidates: List of candidate names.
        """
        self.candidates = candidates
        self._cache.clear()
        self._build_candidate_index()

    def _build_candidate_index(self) -> None:
        """Build normalized name to original name mapping."""
        self._normalized_candidates = {}
        for candidate in self.candidates:
            norm = normalize_name(candidate)
            self._normalized_candidates[norm] = candidate

    def match(self, name: str) -> MatchResult:
        """Find the best match for a name among candidates.

        Results are cached for repeated lookups of the same name.

        Args:
            name: The name to match.

        Returns:
            MatchResult with the matched name and score.
        """
        # Check cache first
        norm_name = normalize_name(name)
        if norm_name in self._cache:
            return self._cache[norm_name]

        # Check for exact normalized match first (fast path)
        if norm_name in self._normalized_candidates:
            result = MatchResult(
                matched_name=self._normalized_candidates[norm_name],
                score=1.0,
            )
            self._cache[norm_name] = result
            return result

        # Find best match
        best_match: str | None = None
        best_score = 0.0

        for candidate in self.candidates:
            score = name_similarity(name, candidate)
            if score > best_score:
                best_score = score
                best_match = candidate

        # Apply threshold
        if best_score < self.threshold:
            result = MatchResult(matched_name=None, score=best_score)
        else:
            result = MatchResult(matched_name=best_match, score=best_score)

        self._cache[norm_name] = result
        return result

    def match_all(self, names: list[str]) -> list[MatchResult]:
        """Match multiple names against candidates.

        Args:
            names: List of names to match.

        Returns:
            List of MatchResult objects in the same order as input names.
        """
        return [self.match(name) for name in names]

    def clear_cache(self) -> None:
        """Clear the match result cache."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Number of cached match results."""
        return len(self._cache)
