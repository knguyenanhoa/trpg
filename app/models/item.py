"""Item data model."""

from dataclasses import dataclass, field

from app.models.stats import ItemStats


@dataclass
class Item:
    """An item that can be equipped by a character."""
    id: str
    name: str
    slot: str  # head, chest, legs, feet, hands, weapon, offhand, accessory
    rarity: str  # normal, uncommon, rare, epic, legendary
    stats: ItemStats = field(default_factory=ItemStats)
    sprite: str = ""  # path to ascii sprite file
    acquired_at: str = ""
    equipped: bool = False

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "slot": self.slot,
            "rarity": self.rarity,
            "stats": self.stats.to_dict(),
            "sprite": self.sprite,
            "acquired_at": self.acquired_at,
            "equipped": self.equipped,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            slot=data["slot"],
            rarity=data.get("rarity", "normal"),
            stats=ItemStats.from_dict(data.get("stats", {})),
            sprite=data.get("sprite", ""),
            acquired_at=data.get("acquired_at", ""),
            equipped=data.get("equipped", False),
        )
