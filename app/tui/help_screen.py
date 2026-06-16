"""Help overlay screen showing key bindings."""


class HelpScreen:
    """Floating help overlay accessible from any screen via '?'."""

    WIDTH = 42  # inner content width

    def __init__(self, term):
        self.term = term

    def render(self):
        """Render the help overlay as a centered box."""
        t = self.term
        w = self.WIDTH

        def row(text: str) -> str:
            """Pad text to fit inside the box."""
            return "║ " + text.ljust(w - 2) + " ║"

        top = "╔" + "═" * w + "╗"
        mid = "╠" + "═" * w + "╣"
        bot = "╚" + "═" * w + "╝"

        lines = [
            top,
            row("          KEY BINDINGS"),
            mid,
            row("h/←      Back / Move left"),
            row("j/↓      Move down / Next option"),
            row("k/↑      Move up / Prev option"),
            row("l/→      Move right / Select"),
            row("Enter    Select / Confirm / Submit"),
            row("Esc      Back / Cancel"),
            row("q        Quit application"),
            row("?        Toggle this help"),
            row("/        Search (in lists)"),
            row("n        New (character/quest)"),
            row("d        Delete"),
            row("s        Start quest / Sell item"),
            row("c        Complete quest"),
            row("p        Pause/unpause quest"),
            row("Tab      Next field / Switch tabs"),
            row("Shift-Tab  Previous field"),
            row("e        Equipped tab (inventory)"),
            row("b        Backpack tab (inventory)"),
            row("r        Rank up (stats screen)"),
            row("Space    Toggle selection"),
            mid,
            row("Ctrl+C   Force quit"),
            bot,
        ]

        box_width = w + 2  # +2 for the ║ borders
        box_height = len(lines)
        start_x = max(0, (t.width - box_width) // 2)
        start_y = max(0, (t.height - box_height) // 2)

        for i, line in enumerate(lines):
            print(t.move_xy(start_x, start_y + i) + t.white + line + t.normal, end="")
