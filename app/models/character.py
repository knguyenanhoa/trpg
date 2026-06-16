"""Character data model."""

from dataclasses import dataclass, field
from typing import Optional

from app.models.stats import CharacterStats


@dataclass
class Character:
    """A player character."""
    name: str
    age: int
    sex: str  # "male" or "female"
    stats: CharacterStats = field(default_factory=CharacterStats)
    backstory: str = ""
    portrait: str = ""  # filename in assets/portraits/
    portrait_color: str = "white"
    rank: int = 1
    coins: int = 0
    created_at: str = ""

    @property
    def level(self) -> float:
        """Character level (average of all CS)."""
        return self.stats.level()

    def can_rank_up(self) -> bool:
        """Check if character meets minimum CS requirement for rank-up."""
        return self.stats.all_at_min(100)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "age": self.age,
            "sex": self.sex,
            "stats": self.stats.to_dict(),
            "backstory": self.backstory,
            "portrait": self.portrait,
            "portrait_color": self.portrait_color,
            "rank": self.rank,
            "coins": self.coins,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            age=data["age"],
            sex=data["sex"],
            stats=CharacterStats.from_dict(data.get("stats", {})),
            backstory=data.get("backstory", ""),
            portrait=data.get("portrait", ""),
            portrait_color=data.get("portrait_color", "white"),
            rank=data.get("rank", 1),
            coins=data.get("coins", 0),
            created_at=data.get("created_at", ""),
        )
