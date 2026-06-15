"""Character selection screen (launch screen)."""

from app.tui.base_screen import BaseScreen
from app.tui.fzf_picker import InlinePicker
from app.db.file_store import list_characters, load_character, delete_character


class CharacterSelectScreen(BaseScreen):
    """Screen for selecting an existing character or creating a new one."""

    def __init__(self):
        super().__init__()
        self.picker = None
        self.mode = "select"  # select, confirm_delete
        self.delete_target = ""  # folder name of character to delete
        self.delete_char_name = ""  # display name for confirmation
        self.confirm_buffer = ""
        self.message = ""
        self._refresh_list()

    def _refresh_list(self):
        """Refresh the character list."""
        folders = list_characters()
        self.char_folders = folders
        self.items = folders + ["+ New Character"]

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.cyan + "X-LRPG" + t.normal + " — Choose Your Character", end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 40 + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 3) + t.yellow + self.message + t.normal, end="")

        if self.mode == "select":
            if self.picker is None:
                self._refresh_list()
                self.picker = InlinePicker(
                    self.items, t, prompt="Select character:", x=2, y=5
                )
            self.picker.render()
            print(t.move_xy(2, t.height - 1) + t.dim + "Enter:select  n:new  d:delete  q:quit  ?:help" + t.normal, end="")

        elif self.mode == "confirm_delete":
            y = 5
            print(t.move_xy(2, y) + t.red + t.bold + "Delete Character" + t.normal, end="")
            print(t.move_xy(2, y + 1) + f"Type the character name to confirm deletion:", end="")
            print(t.move_xy(2, y + 2) + t.bold + f"  {self.delete_char_name}" + t.normal, end="")
            print(t.move_xy(2, y + 4) + f"> {self.confirm_buffer}_", end="")
            print(t.move_xy(2, y + 6) + t.dim + "Enter: confirm  Esc: cancel" + t.normal, end="")

    def on_key(self, key):
        t = self.term
        self.message = ""

        if self.mode == "select":
            self._handle_select_key(key)
        elif self.mode == "confirm_delete":
            self._handle_confirm_delete_key(key)

    def _handle_select_key(self, key):
        t = self.term

        if not self.picker.searching and key == "q":
            self.manager.running = False
            return

        if not self.picker.searching and key == "d":
            self._initiate_delete()
            return

        if not self.picker.searching and key == "n":
            from app.tui.character_create import CharacterCreateScreen
            self.manager.push(CharacterCreateScreen())
            self.picker = None
            return

        result, active = self.picker.on_key(key)

        if not active:
            if result is None:
                self.manager.running = False
            elif result == "+ New Character":
                from app.tui.character_create import CharacterCreateScreen
                self.manager.push(CharacterCreateScreen())
                self.picker = None
            else:
                char = load_character(result)
                if char:
                    from app.tui.main_menu import MainMenuScreen
                    self.manager.replace(MainMenuScreen(char))

    def _initiate_delete(self):
        """Start the delete confirmation flow for the selected character."""
        if not self.picker or not self.picker.filtered_indices:
            return
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(self.char_folders):
            return  # Can't delete "+ New Character"
        folder = self.char_folders[idx]
        char = load_character(folder)
        if not char:
            return
        self.delete_target = folder
        self.delete_char_name = char.name
        self.confirm_buffer = ""
        self.mode = "confirm_delete"

    def _handle_confirm_delete_key(self, key):
        t = self.term

        if key.code == t.KEY_ESCAPE:
            self.mode = "select"
            self.picker = None
            return

        if key.code == t.KEY_ENTER:
            if self.confirm_buffer == self.delete_char_name:
                delete_character(self.delete_target)
                self.message = f"Character '{self.delete_char_name}' deleted."
                self.mode = "select"
                self.picker = None
                self._refresh_list()
            else:
                self.message = "Name doesn't match. Deletion cancelled."
                self.mode = "select"
                self.picker = None
            return

        if key.code == t.KEY_BACKSPACE or key == "\x7f":
            self.confirm_buffer = self.confirm_buffer[:-1]
        elif not key.is_sequence and key.isprintable():
            self.confirm_buffer += str(key)

    def on_tick(self):
        pass
