"""Quest data model."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Quest:
    """A quest definition."""
    id: str
    name: str
    description: str
    difficulty: float  # 0.0 to 5.0
    stats: list[str] = field(default_factory=list)  # CS stats this quest grants XP to
    recurrence: str = "none"  # none, daily, monthly
    created_at: str = ""
    active: bool = True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "difficulty": self.difficulty,
            "stats": self.stats,
            "recurrence": self.recurrence,
            "created_at": self.created_at,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Quest":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            difficulty=data.get("difficulty", 1.0),
            stats=data.get("stats", []),
            recurrence=data.get("recurrence", "none"),
            created_at=data.get("created_at", ""),
            active=data.get("active", True),
        )


@dataclass
class QuestLogEntry:
    """A record of a quest attempt (completion or failure)."""
    quest_id: str
    quest_name: str
    status: str  # "completed" or "failed"
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: int = 0
    xp_granted: float = 0.0
    stats_affected: list[str] = field(default_factory=list)
    item_dropped: Optional[str] = None  # item ID if one dropped

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "quest_id": self.quest_id,
            "quest_name": self.quest_name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "xp_granted": self.xp_granted,
            "stats_affected": self.stats_affected,
            "item_dropped": self.item_dropped,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuestLogEntry":
        """Deserialize from dictionary."""
        return cls(
            quest_id=data["quest_id"],
            quest_name=data.get("quest_name", ""),
            status=data["status"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            duration_seconds=data.get("duration_seconds", 0),
            xp_granted=data.get("xp_granted", 0.0),
            stats_affected=data.get("stats_affected", []),
            item_dropped=data.get("item_dropped"),
        )
