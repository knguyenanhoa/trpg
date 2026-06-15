"""Base screen class for all TUI screens."""


class BaseScreen:
    """Base class for all screens."""

    def __init__(self):
        self.manager = None
        self.term = None

    def render(self):
        """Render the screen. Override in subclasses."""
        pass

    def on_key(self, key):
        """Handle a keypress. Override in subclasses."""
        pass

    def on_tick(self):
        """Called periodically (every ~1s). Override for background work."""
        pass
