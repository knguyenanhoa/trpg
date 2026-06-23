"""Relic data model.

Relics are faction-specific items that award character stats (not item stats).
They cannot be sold or deleted, and do not need to be equipped to have effect.
They have high stat modifiers compared to regular items.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Relic:
    """A faction relic that permanently boosts character stats.

    Unlike regular items:
    - Awards CS (character stats), not IS (item stats)
    - Cannot be sold or deleted
    - Does not need to be equipped — always active
    - Dropped guaranteed on faction overquest completion
    """
    id: str
    name: str
    faction_id: str  # The faction that awarded this relic
    faction_name: str = ""  # Denormalized for display
    # Character stat boosts (these are permanent passive bonuses)
    stat_boosts: dict[str, float] = field(default_factory=dict)  # e.g. {"str": 5.0, "int": 3.0}
    description: str = ""
    acquired_at: str = ""

    def total_boost(self) -> float:
        """Sum of all stat boosts."""
        return sum(self.stat_boosts.values())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "faction_id": self.faction_id,
            "faction_name": self.faction_name,
            "stat_boosts": self.stat_boosts,
            "description": self.description,
            "acquired_at": self.acquired_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Relic":
        return cls(
            id=data["id"],
            name=data["name"],
            faction_id=data["faction_id"],
            faction_name=data.get("faction_name", ""),
            stat_boosts=data.get("stat_boosts", {}),
            description=data.get("description", ""),
            acquired_at=data.get("acquired_at", ""),
        )
