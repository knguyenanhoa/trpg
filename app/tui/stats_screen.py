"""Stats viewing screen."""

from app.tui.base_screen import BaseScreen
from app.models.character import Character
from app.config import CS_STATS, IS_STATS
from app.engine.experience import xp_required
from app.engine.leveling import get_current_rank_name, get_total_is, can_rank_up, perform_rank_up
from app.db.file_store import load_inventory, save_character
from app.utils.colors import stat_color


class StatsScreen(BaseScreen):
    """Display character stats, XP progress, level, and rank."""

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.message = ""

    def render(self):
        t = self.term
        char = self.character
        rank_name = get_current_rank_name(char.rank)

        print(t.move_xy(2, 1) + t.bold + t.cyan + f"{char.name} — Stats" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 50 + t.normal, end="")

        # Level and rank
        print(t.move_xy(2, 4) + "Level: " + t.bold + f"{char.level:.1f}" + t.normal, end="")
        print(t.move_xy(25, 4) + "Rank: " + t.bold + f"{rank_name} ({char.rank})" + t.normal, end="")

        # Character Stats
        print(t.move_xy(2, 6) + t.bold + "Character Stats ($CS)" + t.normal, end="")
        print(t.move_xy(2, 7) + t.dim + "─" * 40 + t.normal, end="")
        for i, stat in enumerate(CS_STATS):
            val = char.stats.get_stat(stat)
            xp = char.stats.get_xp(stat)
            xp_needed = xp_required(val)
            pct = min(100, int(xp / xp_needed * 100)) if xp_needed > 0 else 0
            bar = _progress_bar(pct, 15)
            line = f"  {stat.upper():3s}: {val:3d}  {bar} {xp:.0f}/{xp_needed}"
            print(t.move_xy(2, 8 + i) + line, end="")

        # Item Stats
        items = load_inventory(char.name)
        equipped = [it for it in items if it.equipped]
        print(t.move_xy(2, 16) + t.bold + "Item Stats ($IS) — from equipped items" + t.normal, end="")
        print(t.move_xy(2, 17) + t.dim + "─" * 40 + t.normal, end="")
        for i, is_stat in enumerate(IS_STATS):
            total = sum(it.stats.get_stat(is_stat) for it in equipped)
            color_attr = getattr(t, stat_color(total), "")
            print(t.move_xy(2, 18 + i) + f"  {is_stat.upper():4s}: " + color_attr + f"{total:+.1f}" + t.normal, end="")

        # Effective stats
        print(t.move_xy(2, 26) + t.bold + "Effective Stats ($CS + $IS)" + t.normal, end="")
        print(t.move_xy(2, 27) + t.dim + "─" * 40 + t.normal, end="")
        for i, stat in enumerate(CS_STATS):
            cs_val = char.stats.get_stat(stat)
            is_stat = IS_STATS[i]
            is_val = sum(it.stats.get_stat(is_stat) for it in equipped)
            effective = cs_val + is_val
            print(t.move_xy(2, 28 + i) + f"  {stat.upper():3s}: {effective:.1f}", end="")

        # Rank-up check
        total_is = get_total_is(items)
        print(t.move_xy(2, 36) + f"Total $IS: {total_is:.1f}", end="")
        can_ru, reason = can_rank_up(char, items)
        if can_ru:
            print(t.move_xy(2, 37) + t.green + "Press 'r' to rank up!" + t.normal, end="")
        else:
            print(t.move_xy(2, 37) + t.dim + reason + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 39) + t.yellow + self.message + t.normal, end="")

        print(t.move_xy(2, t.height - 1) + t.dim + "Esc/h: back  r: rank up  ?: help" + t.normal, end="")

    def on_key(self, key):
        t = self.term
        self.message = ""

        if key == "q":
            self.manager.running = False
        elif key.code == t.KEY_ESCAPE or key == "h":
            self.manager.pop()
        elif key == "r":
            items = load_inventory(self.character.name)
            can_ru, reason = can_rank_up(self.character, items)
            if can_ru:
                new_rank = perform_rank_up(self.character)
                save_character(self.character)
                self.message = f"Ranked up to {new_rank}!"
            else:
                self.message = reason


def _progress_bar(percent: int, width: int = 20) -> str:
    """Create a text progress bar."""
    filled = int(width * percent / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"
