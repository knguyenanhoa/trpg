"""Main menu screen."""

from app.tui.base_screen import BaseScreen
from app.models.character import Character
from app.engine.leveling import get_current_rank_name


class MainMenuScreen(BaseScreen):
    """Main menu after character is selected."""

    MENU_ITEMS = [
        "Stats",
        "Quests",
        "Inventory",
        "Back to Characters",
    ]

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.cursor = 0

    def render(self):
        t = self.term
        # Header with character info
        rank_name = get_current_rank_name(self.character.rank)
        level = self.character.level
        print(t.move_xy(2, 1) + t.bold + t.cyan + self.character.name + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + f"Level {level:.1f} | {rank_name}" + t.normal, end="")
        print(t.move_xy(2, 3) + t.dim + "─" * 40 + t.normal, end="")

        # Menu items
        for i, item in enumerate(self.MENU_ITEMS):
            y = 5 + i
            if i == self.cursor:
                print(t.move_xy(2, y) + t.reverse + f" > {item} " + t.normal, end="")
            else:
                print(t.move_xy(2, y) + f"   {item}", end="")

    def on_key(self, key):
        t = self.term

        if key == "q":
            self.manager.running = False
            return

        if key == "j" or key.code == t.KEY_DOWN:
            self.cursor = min(self.cursor + 1, len(self.MENU_ITEMS) - 1)
        elif key == "k" or key.code == t.KEY_UP:
            self.cursor = max(self.cursor - 1, 0)
        elif key.code == t.KEY_ENTER or key == "l":
            self._select_item()
        elif key.code == t.KEY_ESCAPE or key == "h":
            self.manager.pop()

    def _select_item(self):
        choice = self.MENU_ITEMS[self.cursor]
        if choice == "Stats":
            from app.tui.stats_screen import StatsScreen
            self.manager.push(StatsScreen(self.character))
        elif choice == "Quests":
            from app.tui.quest_screen import QuestScreen
            self.manager.push(QuestScreen(self.character))
        elif choice == "Inventory":
            from app.tui.inventory_screen import InventoryScreen
            self.manager.push(InventoryScreen(self.character))
        elif choice == "Back to Characters":
            self.manager.pop()
