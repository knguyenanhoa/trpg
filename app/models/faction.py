"""Faction data model."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Faction:
    """A faction (mirrors real-life organizations).

    Factions can award relics through their quest lines and track
    the number of quests completed for them.
    """
    id: str
    name: str
    description: str = ""
    active: bool = True  # False = inactive (hidden but restorable)
    quests_completed: int = 0  # Number of quests completed for this faction
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "active": self.active,
            "quests_completed": self.quests_completed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Faction":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            active=data.get("active", True),
            quests_completed=data.get("quests_completed", 0),
            created_at=data.get("created_at", ""),
        )
