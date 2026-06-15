"""Stat types, constants, and helper structures."""

from dataclasses import dataclass, field
from app.config import CS_STATS, IS_STATS


@dataclass
class CharacterStats:
    """Character stats with current values and experience tracking."""
    str: int = 1
    dex: int = 1
    con: int = 1
    int_: int = 1  # 'int' is reserved in Python
    wis: int = 1
    cha: int = 1

    # Experience accumulated toward next level for each stat
    str_xp: float = 0.0
    dex_xp: float = 0.0
    con_xp: float = 0.0
    int_xp: float = 0.0
    wis_xp: float = 0.0
    cha_xp: float = 0.0

    def get_stat(self, stat_name: str) -> int:
        """Get stat value by name."""
        if stat_name == "int":
            return self.int_
        return getattr(self, stat_name)

    def set_stat(self, stat_name: str, value: int):
        """Set stat value by name."""
        if stat_name == "int":
            self.int_ = value
        else:
            setattr(self, stat_name, value)

    def get_xp(self, stat_name: str) -> float:
        """Get current XP for a stat."""
        key = f"{stat_name}_xp"
        return getattr(self, key)

    def set_xp(self, stat_name: str, value: float):
        """Set XP for a stat."""
        key = f"{stat_name}_xp"
        setattr(self, key, value)

    def level(self) -> float:
        """Calculate character level as average of all CS."""
        total = self.str + self.dex + self.con + self.int_ + self.wis + self.cha
        return total / 6.0

    def all_at_min(self, minimum: int = 100) -> bool:
        """Check if all stats are at or above minimum."""
        return all(
            self.get_stat(s) >= minimum for s in CS_STATS
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "str": self.str,
            "dex": self.dex,
            "con": self.con,
            "int": self.int_,
            "wis": self.wis,
            "cha": self.cha,
            "str_xp": self.str_xp,
            "dex_xp": self.dex_xp,
            "con_xp": self.con_xp,
            "int_xp": self.int_xp,
            "wis_xp": self.wis_xp,
            "cha_xp": self.cha_xp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CharacterStats":
        """Deserialize from dictionary."""
        return cls(
            str=data.get("str", 1),
            dex=data.get("dex", 1),
            con=data.get("con", 1),
            int_=data.get("int", 1),
            wis=data.get("wis", 1),
            cha=data.get("cha", 1),
            str_xp=data.get("str_xp", 0.0),
            dex_xp=data.get("dex_xp", 0.0),
            con_xp=data.get("con_xp", 0.0),
            int_xp=data.get("int_xp", 0.0),
            wis_xp=data.get("wis_xp", 0.0),
            cha_xp=data.get("cha_xp", 0.0),
        )


@dataclass
class ItemStats:
    """Item stat boosts."""
    istr: float = 0.0
    idex: float = 0.0
    icon: float = 0.0
    iint: float = 0.0
    iwis: float = 0.0
    icha: float = 0.0

    def get_stat(self, stat_name: str) -> float:
        """Get item stat by name."""
        return getattr(self, stat_name, 0.0)

    def total(self) -> float:
        """Sum of all item stats."""
        return self.istr + self.idex + self.icon + self.iint + self.iwis + self.icha

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "istr": self.istr,
            "idex": self.idex,
            "icon": self.icon,
            "iint": self.iint,
            "iwis": self.iwis,
            "icha": self.icha,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ItemStats":
        """Deserialize from dictionary."""
        return cls(
            istr=data.get("istr", 0.0),
            idex=data.get("idex", 0.0),
            icon=data.get("icon", 0.0),
            iint=data.get("iint", 0.0),
            iwis=data.get("iwis", 0.0),
            icha=data.get("icha", 0.0),
        )
