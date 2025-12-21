"""Team ID to DailyFaceoff URL slug mapping.

DailyFaceoff uses URL-friendly team slugs in their team pages:
https://www.dailyfaceoff.com/teams/{slug}/line-combinations

This module provides bidirectional mapping between NHL team IDs and
DailyFaceoff URL slugs.
"""

from __future__ import annotations

# NHL Team ID to DailyFaceoff URL slug mapping
# Team IDs are from the official NHL API
# Slugs are from DailyFaceoff.com team page URLs
TEAM_SLUGS: dict[int, str] = {
    1: "new-jersey-devils",
    2: "new-york-islanders",
    3: "new-york-rangers",
    4: "philadelphia-flyers",
    5: "pittsburgh-penguins",
    6: "boston-bruins",
    7: "buffalo-sabres",
    8: "montreal-canadiens",
    9: "ottawa-senators",
    10: "toronto-maple-leafs",
    12: "carolina-hurricanes",
    13: "florida-panthers",
    14: "tampa-bay-lightning",
    15: "washington-capitals",
    16: "chicago-blackhawks",
    17: "detroit-red-wings",
    18: "nashville-predators",
    19: "st-louis-blues",
    20: "calgary-flames",
    21: "colorado-avalanche",
    22: "edmonton-oilers",
    23: "vancouver-canucks",
    24: "anaheim-ducks",
    25: "dallas-stars",
    26: "los-angeles-kings",
    28: "san-jose-sharks",
    29: "columbus-blue-jackets",
    30: "minnesota-wild",
    52: "winnipeg-jets",
    53: "arizona-coyotes",  # Historical - relocated to Utah
    54: "vegas-golden-knights",
    55: "seattle-kraken",
    59: "utah-hockey-club",
}

# NHL Team ID to abbreviation mapping
TEAM_ABBREVIATIONS: dict[int, str] = {
    1: "NJD",
    2: "NYI",
    3: "NYR",
    4: "PHI",
    5: "PIT",
    6: "BOS",
    7: "BUF",
    8: "MTL",
    9: "OTT",
    10: "TOR",
    12: "CAR",
    13: "FLA",
    14: "TBL",
    15: "WSH",
    16: "CHI",
    17: "DET",
    18: "NSH",
    19: "STL",
    20: "CGY",
    21: "COL",
    22: "EDM",
    23: "VAN",
    24: "ANA",
    25: "DAL",
    26: "LAK",
    28: "SJS",
    29: "CBJ",
    30: "MIN",
    52: "WPG",
    53: "ARI",
    54: "VGK",
    55: "SEA",
    59: "UTA",
}

# Reverse mapping: slug to team ID
_SLUG_TO_ID: dict[str, int] = {slug: team_id for team_id, slug in TEAM_SLUGS.items()}


def get_team_slug(team_id: int) -> str:
    """Get DailyFaceoff URL slug for a team.

    Args:
        team_id: NHL team ID

    Returns:
        DailyFaceoff URL slug

    Raises:
        KeyError: If team_id is not recognized
    """
    if team_id not in TEAM_SLUGS:
        raise KeyError(f"Unknown team ID: {team_id}")
    return TEAM_SLUGS[team_id]


def get_team_abbreviation(team_id: int) -> str:
    """Get NHL abbreviation for a team.

    Args:
        team_id: NHL team ID

    Returns:
        Three-letter team abbreviation

    Raises:
        KeyError: If team_id is not recognized
    """
    if team_id not in TEAM_ABBREVIATIONS:
        raise KeyError(f"Unknown team ID: {team_id}")
    return TEAM_ABBREVIATIONS[team_id]


def get_team_id_from_slug(slug: str) -> int:
    """Get NHL team ID from DailyFaceoff URL slug.

    Args:
        slug: DailyFaceoff URL slug

    Returns:
        NHL team ID

    Raises:
        KeyError: If slug is not recognized
    """
    if slug not in _SLUG_TO_ID:
        raise KeyError(f"Unknown team slug: {slug}")
    return _SLUG_TO_ID[slug]
