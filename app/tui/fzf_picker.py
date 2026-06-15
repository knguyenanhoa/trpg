"""FZF-style list picker with fallback to built-in selection."""

import shutil
import subprocess


def pick_from_list(items: list[str], prompt: str = "> ", term=None) -> str | None:
    """Show a list for selection. Uses fzf if available, otherwise built-in.

    Args:
        items: List of string options.
        prompt: Prompt string for fzf.
        term: Blessed terminal instance (used for built-in fallback).

    Returns:
        Selected item string, or None if cancelled.
    """
    if not items:
        return None

    # Try fzf first
    fzf_path = shutil.which("fzf")
    if fzf_path:
        return _fzf_pick(items, prompt, fzf_path)

    # Fallback: built-in picker (this is handled by the TUI screens directly)
    return None


def _fzf_pick(items: list[str], prompt: str, fzf_path: str) -> str | None:
    """Use fzf binary for selection."""
    input_text = "\n".join(items)

    try:
        result = subprocess.run(
            [fzf_path, "--prompt", prompt, "--height", "40%", "--reverse"],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None  # User cancelled (Esc or Ctrl+C in fzf)
    except (subprocess.TimeoutExpired, OSError):
        return None


class InlinePicker:
    """Built-in j/k navigable list picker when fzf is not available."""

    def __init__(self, items: list[str], term, prompt: str = "Select:", x=0, y=0, max_visible=15):
        self.items = items
        self.term = term
        self.prompt = prompt
        self.cursor = 0
        self.scroll_offset = 0
        self.max_visible = min(max_visible, len(items))
        self.x = x
        self.y = y
        self.search_text = ""
        self.searching = False
        self.filtered_indices = list(range(len(items)))

    def render(self):
        """Render the picker."""
        t = self.term

        # Prompt
        print(t.move_xy(self.x, self.y) + t.bold + self.prompt + t.normal, end="")

        # Search bar
        if self.searching:
            search_line = f"/{self.search_text}_"
            print(t.move_xy(self.x, self.y + 1) + t.cyan + search_line + t.normal + t.clear_eol, end="")
        else:
            print(t.move_xy(self.x, self.y + 1) + t.clear_eol, end="")

        # Items
        visible_start = self.scroll_offset
        visible_end = min(visible_start + self.max_visible, len(self.filtered_indices))

        for i in range(self.max_visible):
            line_y = self.y + 2 + i
            if visible_start + i < visible_end:
                idx = self.filtered_indices[visible_start + i]
                item_text = self.items[idx]
                if visible_start + i == self.cursor:
                    print(t.move_xy(self.x, line_y) + t.reverse + f" > {item_text}" + t.normal + t.clear_eol, end="")
                else:
                    print(t.move_xy(self.x, line_y) + f"   {item_text}" + t.clear_eol, end="")
            else:
                print(t.move_xy(self.x, line_y) + t.clear_eol, end="")

    def on_key(self, key) -> tuple[str | None, bool]:
        """Handle keypress.

        Returns (selected_item_or_none, still_active).
        If still_active is False, the picker is done.
        """
        t = self.term

        if self.searching:
            if key.code == t.KEY_ESCAPE:
                self.searching = False
                self.search_text = ""
                self._reset_filter()
            elif key.code == t.KEY_ENTER:
                self.searching = False
            elif key.code == t.KEY_BACKSPACE or key == "\x7f":
                self.search_text = self.search_text[:-1]
                self._apply_filter()
            elif key.is_sequence:
                pass  # ignore special keys in search
            else:
                self.search_text += str(key)
                self._apply_filter()
            return None, True

        # Navigation
        if key == "j" or key.code == t.KEY_DOWN:
            self.cursor = min(self.cursor + 1, len(self.filtered_indices) - 1)
            if self.cursor >= self.scroll_offset + self.max_visible:
                self.scroll_offset += 1
        elif key == "k" or key.code == t.KEY_UP:
            self.cursor = max(self.cursor - 1, 0)
            if self.cursor < self.scroll_offset:
                self.scroll_offset = self.cursor
        elif key.code == t.KEY_ENTER or key == "l":
            if self.filtered_indices:
                idx = self.filtered_indices[self.cursor]
                return self.items[idx], False
            return None, False
        elif key.code == t.KEY_ESCAPE or key == "h":
            return None, False
        elif key == "/":
            self.searching = True
            self.search_text = ""

        return None, True

    def _apply_filter(self):
        """Filter items by search text."""
        if not self.search_text:
            self._reset_filter()
            return
        query = self.search_text.lower()
        self.filtered_indices = [
            i for i, item in enumerate(self.items)
            if query in item.lower()
        ]
        self.cursor = 0
        self.scroll_offset = 0

    def _reset_filter(self):
        """Reset filter to show all items."""
        self.filtered_indices = list(range(len(self.items)))
        self.cursor = 0
        self.scroll_offset = 0
