"""Screen stack manager and main input loop."""

import sys

from blessed import Terminal

from app.tui.help_screen import HelpScreen
from app.db.file_store import (
    list_characters, load_character, load_global_config, save_global_config,
)
from app.utils.sanitize import name_to_folder


class ScreenManager:
    """Manages a stack of screens and the main input loop."""

    def __init__(self):
        self.term = Terminal()
        self.screens = []
        self.running = False
        self.help_visible = False

    def push(self, screen):
        """Push a screen onto the stack."""
        screen.manager = self
        screen.term = self.term
        self.screens.append(screen)

    def pop(self):
        """Pop the current screen."""
        if self.screens:
            self.screens.pop()
        if not self.screens:
            self.running = False

    def replace(self, screen):
        """Replace the current screen."""
        if self.screens:
            self.screens.pop()
        self.push(screen)

    @property
    def current(self):
        """Get the current screen."""
        return self.screens[-1] if self.screens else None

    def set_last_played(self, character_name: str):
        """Record last played character in global config."""
        config = load_global_config()
        config["last_played"] = name_to_folder(character_name)
        save_global_config(config)

    def run(self):
        """Main application loop."""
        self.running = True

        # Try to auto-load last played character
        start_screen = self._get_start_screen()
        self.push(start_screen)

        with self.term.fullscreen(), self.term.cbreak(), self.term.hidden_cursor():
            self._render()
            while self.running:
                key = self.term.inkey(timeout=1)
                if not key:
                    if self.current:
                        self.current.on_tick()
                    continue

                # Global: Escape with empty stack quits
                if key.code == self.term.KEY_ESCAPE and not self.screens:
                    self.running = False
                    break

                if key == "?":
                    self.help_visible = not self.help_visible
                    self._render()
                    continue

                if self.help_visible:
                    self.help_visible = False
                    self._render()
                    continue

                if self.current:
                    self.current.on_key(key)
                    self._render()

    def _get_start_screen(self):
        """Determine start screen: last played character, character select, or create."""
        characters = list_characters()

        if not characters:
            # No characters — go directly to creation
            from app.tui.character_create import CharacterCreateScreen
            return CharacterCreateScreen()

        # Check for last played
        config = load_global_config()
        last_played = config.get("last_played", "")

        if last_played and last_played in characters:
            char = load_character(last_played)
            if char:
                self.set_last_played(char.name)
                from app.tui.main_menu import MainMenuScreen
                return MainMenuScreen(char)

        # Fall back to character select
        from app.tui.character_select import CharacterSelectScreen
        return CharacterSelectScreen()

    def _render(self):
        """Render the current screen (and help overlay if visible)."""
        print(self.term.clear, end="")
        if self.current:
            self.current.render()
        if self.help_visible:
            HelpScreen(self.term).render()
        sys.stdout.flush()

    def cleanup(self):
        """Cleanup on exit."""
        pass
