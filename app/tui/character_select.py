"""Character selection screen (launch screen)."""

from app.tui.base_screen import BaseScreen
from app.tui.fzf_picker import InlinePicker
from app.db.file_store import list_characters, load_character


class CharacterSelectScreen(BaseScreen):
    """Screen for selecting an existing character or creating a new one."""

    def __init__(self):
        super().__init__()
        self.picker = None
        self._refresh_list()

    def _refresh_list(self):
        """Refresh the character list."""
        folders = list_characters()
        self.char_folders = folders
        self.items = folders + ["+ New Character"]

    def render(self):
        t = self.term
        # Title
        print(t.move_xy(2, 1) + t.bold_cyan + "X-LRPG" + t.normal + " — Choose Your Character", end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 40 + t.normal, end="")

        if self.picker is None:
            self._refresh_list()
            self.picker = InlinePicker(
                self.items, t, prompt="Select character:", x=2, y=4
            )
        self.picker.render()

    def on_key(self, key):
        t = self.term

        # 'q' to quit from character select
        if not self.picker.searching and (key == "q"):
            self.manager.running = False
            return

        result, active = self.picker.on_key(key)

        if not active:
            if result is None:
                # Escaped — quit
                self.manager.running = False
            elif result == "+ New Character":
                from app.tui.character_create import CharacterCreateScreen
                self.manager.push(CharacterCreateScreen())
                self.picker = None  # refresh on return
            else:
                # Load selected character
                char = load_character(result)
                if char:
                    from app.tui.main_menu import MainMenuScreen
                    self.manager.replace(MainMenuScreen(char))

    def on_tick(self):
        """Refresh character list periodically."""
        pass
