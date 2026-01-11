"""Analytics services for second-by-second game analysis.

This package provides services for expanding player shifts into
granular second-by-second snapshots for advanced analytics.

Example usage:
    from nhl_api.services.analytics import ShiftExpander, EventAttributor

    async with DatabaseService() as db:
        expander = ShiftExpander(db)
        result = await expander.expand_game(game_id=2024020500)

        attributor = EventAttributor(db)
        events = await attributor.get_game_events(game_id=2024020500)

Issue: #259 - Second-by-Second Analytics
"""

from nhl_api.services.analytics.event_attributor import (
    AttributionResult,
    EventAttribution,
    EventAttributor,
    GameEvent,
)
from nhl_api.services.analytics.shift_expander import (
    ExpandedSecond,
    GameExpansionResult,
    ShiftExpander,
)
from nhl_api.services.analytics.situation import (
    Situation,
    SituationCalculator,
    SituationType,
)

__all__ = [
    # Shift expansion
    "ShiftExpander",
    "ExpandedSecond",
    "GameExpansionResult",
    # Event attribution
    "EventAttributor",
    "EventAttribution",
    "AttributionResult",
    "GameEvent",
    # Situation calculation
    "SituationCalculator",
    "Situation",
    "SituationType",
]
