"""Screen stack manager and main input loop."""

import sys

from blessed import Terminal

from app.tui.help_screen import HelpScreen


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

    def run(self):
        """Main application loop."""
        from app.tui.character_select import CharacterSelectScreen

        self.running = True
        # Start with character selection
        self.push(CharacterSelectScreen())

        with self.term.fullscreen(), self.term.cbreak(), self.term.hidden_cursor():
            self._render()
            while self.running:
                key = self.term.inkey(timeout=1)
                if not key:
                    # Timeout — allow screens to do periodic work
                    if self.current:
                        self.current.on_tick()
                    continue

                # Global keys — only Escape with empty stack quits at manager level
                # 'q' is handled by individual screens (they all set self.manager.running = False)
                if key.code == self.term.KEY_ESCAPE and not self.screens:
                    self.running = False
                    break

                if key == "?":
                    self.help_visible = not self.help_visible
                    self._render()
                    continue

                if self.help_visible:
                    # Any key dismisses help
                    self.help_visible = False
                    self._render()
                    continue

                # Pass to current screen
                if self.current:
                    self.current.on_key(key)
                    self._render()

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
