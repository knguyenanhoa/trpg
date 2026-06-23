"""Main menu screen."""

import os

from app.tui.base_screen import BaseScreen
from app.models.character import Character
from app.engine.leveling import get_current_rank_name
from app.config import ASSETS_PATH


class MainMenuScreen(BaseScreen):
    """Main menu after character is selected."""

    MENU_ITEMS = [
        "Stats",
        "Quests",
        "Quest Editor",
        "Inventory",
        "Switch Character",
    ]

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.cursor = 0
        self.portrait_lines = self._load_portrait()

    def _load_portrait(self) -> list[str]:
        """Load the character's ASCII portrait from file."""
        if not self.character.portrait:
            return []
        path = os.path.join(ASSETS_PATH, "portraits", self.character.portrait)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r") as f:
                lines = f.read().rstrip("\n").split("\n")
            return lines
        except OSError:
            return []

    def render(self):
        t = self.term
        rank_name = get_current_rank_name(self.character.rank)
        level = self.character.level

        # Render portrait on the left side
        portrait_width = 0
        color_attr = getattr(t, self.character.portrait_color, "")
        if self.portrait_lines:
            portrait_width = max(len(line) for line in self.portrait_lines) + 2
            for i, line in enumerate(self.portrait_lines):
                print(t.move_xy(2, 1 + i) + color_attr + line + t.normal, end="")

        # Character info to the right of portrait
        info_x = 2 + portrait_width
        print(t.move_xy(info_x, 1) + t.bold + t.cyan + self.character.name + t.normal, end="")
        print(t.move_xy(info_x, 2) + t.dim + f"Level {level:.1f} | {rank_name}" + t.normal, end="")
        print(t.move_xy(info_x, 3) + t.dim + f"Age {self.character.age} | {self.character.sex}" + t.normal, end="")
        print(t.move_xy(info_x, 4) + t.yellow + f"Coins: {self.character.coins}" + t.normal, end="")

        # Menu items below portrait or info, whichever is taller
        menu_start_y = max(len(self.portrait_lines) + 2, 6)
        print(t.move_xy(2, menu_start_y - 1) + t.dim + "─" * 40 + t.normal, end="")

        for i, item in enumerate(self.MENU_ITEMS):
            y = menu_start_y + i
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
            # Go to character select
            from app.tui.character_select import CharacterSelectScreen
            self.manager.replace(CharacterSelectScreen())

    def _select_item(self):
        choice = self.MENU_ITEMS[self.cursor]
        if choice == "Stats":
            from app.tui.stats_screen import StatsScreen
            self.manager.push(StatsScreen(self.character))
        elif choice == "Quests":
            from app.tui.quest_screen import QuestScreen
            self.manager.push(QuestScreen(self.character))
        elif choice == "Quest Editor":
            from app.tui.quest_editor import QuestEditorScreen
            self.manager.push(QuestEditorScreen(self.character))
        elif choice == "Inventory":
            from app.tui.inventory_screen import InventoryScreen
            self.manager.push(InventoryScreen(self.character))
        elif choice == "Switch Character":
            from app.tui.character_select import CharacterSelectScreen
            self.manager.replace(CharacterSelectScreen())
