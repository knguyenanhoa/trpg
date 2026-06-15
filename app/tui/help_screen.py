"""Help overlay screen showing key bindings."""


class HelpScreen:
    """Floating help overlay accessible from any screen via '?'."""

    def __init__(self, term):
        self.term = term

    def render(self):
        """Render the help overlay as a centered box."""
        t = self.term
        lines = [
            "╔══════════════════════════════════════╗",
            "║           KEY BINDINGS               ║",
            "╠══════════════════════════════════════╣",
            "║  h/←    Move left / Back             ║",
            "║  j/↓    Move down                    ║",
            "║  k/↑    Move up                      ║",
            "║  l/→    Move right / Enter           ║",
            "║  Enter  Select / Confirm             ║",
            "║  Esc    Back / Cancel                 ║",
            "║  q      Quit application              ║",
            "║  ?      Toggle this help              ║",
            "║  /      Search (in lists)             ║",
            "║  n      New (context-dependent)       ║",
            "║  d      Delete (context-dep.)         ║",
            "║  s      Start quest                   ║",
            "║  c      Complete quest                ║",
            "║  p      Pause/unpause quest           ║",
            "║  a/Tab  Switch tabs                   ║",
            "║  e      Equipped tab (inventory)      ║",
            "║  b      Backpack tab (inventory)      ║",
            "║  r      Rank up (stats screen)        ║",
            "╠══════════════════════════════════════╣",
            "║  Ctrl+C  Force quit                   ║",
            "╚══════════════════════════════════════╝",
        ]

        # Center the box
        box_width = len(lines[0])
        box_height = len(lines)
        start_x = max(0, (t.width - box_width) // 2)
        start_y = max(0, (t.height - box_height) // 2)

        for i, line in enumerate(lines):
            print(t.move_xy(start_x, start_y + i) + t.white + line + t.normal, end="")
