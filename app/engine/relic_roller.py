"""Relic generation for faction overquest completion.

When a faction overquest completes, a relic is guaranteed to drop.
Relics award character stats (CS), not item stats. They have high modifiers.
"""

import random
import uuid

from app.config import CS_STATS
from app.models.relic import Relic
from app.utils.time_utils import now_iso

# Relic stat boost range (high modifiers)
RELIC_MIN_BOOST = 3.0
RELIC_MAX_BOOST = 10.0

# Number of stats to boost if relic_stats not specified
DEFAULT_RELIC_STAT_COUNT = 3


def roll_relic(
    faction_id: str,
    faction_name: str,
    overquest_name: str,
    relic_stats: list[str] | None = None,
    difficulty: float = 1.0,
) -> Relic:
    """Generate a relic for a completed faction overquest.

    Args:
        faction_id: The faction that awards this relic.
        faction_name: Display name of the faction.
        overquest_name: Name of the completed overquest (used in relic name).
        relic_stats: Specific CS stats to boost. If empty/None, random stats are chosen.
        difficulty: Quest difficulty (scales boost magnitude).

    Returns:
        A new Relic with stat boosts.
    """
    # Determine which stats to boost
    if relic_stats:
        stats_to_boost = relic_stats
    else:
        # Pick random stats
        count = min(DEFAULT_RELIC_STAT_COUNT, len(CS_STATS))
        stats_to_boost = random.sample(CS_STATS, count)

    # Generate boost values (scaled by difficulty)
    difficulty_scale = 1.0 + (difficulty * 0.3)  # 1.0 at d=0, 2.5 at d=5
    stat_boosts: dict[str, float] = {}
    for stat in stats_to_boost:
        base = random.uniform(RELIC_MIN_BOOST, RELIC_MAX_BOOST)
        boost = round(base * difficulty_scale, 1)
        stat_boosts[stat] = boost

    # Generate relic name
    name = f"{overquest_name} Relic"

    return Relic(
        id=str(uuid.uuid4()),
        name=name,
        faction_id=faction_id,
        faction_name=faction_name,
        stat_boosts=stat_boosts,
        description=f"Awarded by {faction_name} for completing '{overquest_name}'.",
        acquired_at=now_iso(),
    )
