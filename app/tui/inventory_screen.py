"""Inventory and equipment management screen."""

from app.tui.base_screen import BaseScreen
from app.tui.fzf_picker import InlinePicker
from app.models.character import Character
from app.models.item import Item
from app.config import EQUIPMENT_SLOTS
from app.db.file_store import load_inventory, save_inventory, save_character
from app.utils.colors import RARITY_COLORS
from app.engine.economy import item_value


class InventoryScreen(BaseScreen):
    """View and manage equipment and inventory."""

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.items = load_inventory(character.name)
        self.mode = "equipped"  # equipped, backpack
        self.cursor = 0
        self.message = ""

    def _equipped_items(self) -> dict[str, Item | None]:
        """Get equipped items by slot."""
        equipped = {}
        for slot in EQUIPMENT_SLOTS:
            equipped[slot] = None
        for item in self.items:
            if item.equipped:
                equipped[item.slot] = item
        return equipped

    def _backpack_items(self) -> list[Item]:
        """Get unequipped items."""
        return [i for i in self.items if not i.equipped]

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.cyan + f"{self.character.name} — Inventory" + t.normal
              + t.yellow + f"  Coins: {self.character.coins}" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 50 + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 3) + t.yellow + self.message + t.normal, end="")

        # Tab indicator
        if self.mode == "equipped":
            print(t.move_xy(2, 4) + t.bold + "[E]quipped" + t.normal + "  " + t.dim + "[B]ackpack" + t.normal, end="")
        else:
            print(t.move_xy(2, 4) + t.dim + "[E]quipped" + t.normal + "  " + t.bold + "[B]ackpack" + t.normal, end="")

        if self.mode == "equipped":
            self._render_equipped()
        else:
            self._render_backpack()

        controls = "Tab/e/b:switch  Enter:equip/unequip  s:sell  Esc:back  ?:help"
        print(t.move_xy(2, t.height - 1) + t.dim + controls + t.normal, end="")

    def _render_equipped(self):
        t = self.term
        equipped = self._equipped_items()
        y = 6
        for i, slot in enumerate(EQUIPMENT_SLOTS):
            item = equipped[slot]
            prefix = " > " if i == self.cursor else "   "
            if item:
                color_attr = getattr(t, RARITY_COLORS.get(item.rarity, "white"), "")
                val = item_value(item)
                line = f"{prefix}{slot:10s}: " + color_attr + f"{item.name}" + t.normal + f" ({item.rarity}) [{val}c]"
            else:
                line = f"{prefix}{slot:10s}: " + t.dim + "empty" + t.normal
            print(t.move_xy(2, y + i) + line, end="")

        # Show selected item stats
        if self.cursor < len(EQUIPMENT_SLOTS):
            slot = EQUIPMENT_SLOTS[self.cursor]
            item = equipped[slot]
            if item:
                self._render_item_stats(item, y + len(EQUIPMENT_SLOTS) + 2)

    def _render_backpack(self):
        t = self.term
        backpack = self._backpack_items()
        y = 6
        if not backpack:
            print(t.move_xy(2, y) + t.dim + "No items in backpack." + t.normal, end="")
            return
        for i, item in enumerate(backpack):
            prefix = " > " if i == self.cursor else "   "
            color_attr = getattr(t, RARITY_COLORS.get(item.rarity, "white"), "")
            val = item_value(item)
            line = f"{prefix}" + color_attr + f"{item.name}" + t.normal + f" ({item.rarity}) [{item.slot}] [{val}c]"
            print(t.move_xy(2, y + i) + line, end="")

        # Show selected item stats
        if self.cursor < len(backpack):
            self._render_item_stats(backpack[self.cursor], y + len(backpack) + 2)

    def _render_item_stats(self, item: Item, y: int):
        t = self.term
        val = item_value(item)
        print(t.move_xy(2, y) + t.bold + f"  {item.name}" + t.normal + f" — {item.rarity} {item.slot} — " + t.yellow + f"Value: {val} coins" + t.normal, end="")
        stats_dict = item.stats.to_dict()
        stat_parts = []
        for stat, v in stats_dict.items():
            if v >= 0:
                stat_parts.append(t.green + f"{stat}:+{v:.1f}" + t.normal)
            else:
                stat_parts.append(t.red + f"{stat}:{v:.1f}" + t.normal)
        print(t.move_xy(2, y + 1) + "  " + "  ".join(stat_parts), end="")

    def on_key(self, key):
        t = self.term
        self.message = ""

        if key == "q":
            self.manager.running = False
            return

        if key.code == t.KEY_ESCAPE or key == "h":
            self.manager.pop()
            return

        # Tab switching
        if key == "\t":
            self.mode = "backpack" if self.mode == "equipped" else "equipped"
            self.cursor = 0
            return
        if key == "e":
            self.mode = "equipped"
            self.cursor = 0
            return
        if key == "b":
            self.mode = "backpack"
            self.cursor = 0
            return

        # Sell item
        if key == "s":
            self._sell_item()
            return

        # Navigation
        max_items = self._max_cursor()
        if key == "j" or key.code == t.KEY_DOWN:
            self.cursor = min(self.cursor + 1, max_items - 1)
        elif key == "k" or key.code == t.KEY_UP:
            self.cursor = max(self.cursor - 1, 0)
        elif key.code == t.KEY_ENTER or key == "l":
            self._toggle_equip()

    def _max_cursor(self) -> int:
        if self.mode == "equipped":
            return len(EQUIPMENT_SLOTS)
        return max(1, len(self._backpack_items()))

    def _sell_item(self):
        """Sell the currently selected item for coins."""
        if self.mode == "equipped":
            slot = EQUIPMENT_SLOTS[self.cursor]
            equipped = self._equipped_items()
            item = equipped.get(slot)
            if not item:
                self.message = "No item to sell."
                return
        else:
            backpack = self._backpack_items()
            if not backpack or self.cursor >= len(backpack):
                self.message = "No item to sell."
                return
            item = backpack[self.cursor]

        value = item_value(item)
        self.character.coins += value
        self.items.remove(item)
        save_inventory(self.character.name, self.items)
        save_character(self.character)
        self.message = f"Sold {item.name} for {value} coins."
        # Adjust cursor
        max_items = self._max_cursor()
        if self.cursor >= max_items:
            self.cursor = max(0, max_items - 1)

    def _toggle_equip(self):
        if self.mode == "equipped":
            slot = EQUIPMENT_SLOTS[self.cursor]
            equipped = self._equipped_items()
            item = equipped.get(slot)
            if item:
                item.equipped = False
                save_inventory(self.character.name, self.items)
                self.message = f"Unequipped {item.name}."
            else:
                self.message = "No item in this slot."
        else:
            backpack = self._backpack_items()
            if not backpack or self.cursor >= len(backpack):
                return
            item = backpack[self.cursor]
            for i in self.items:
                if i.equipped and i.slot == item.slot:
                    i.equipped = False
            item.equipped = True
            save_inventory(self.character.name, self.items)
            self.message = f"Equipped {item.name} in {item.slot}."
