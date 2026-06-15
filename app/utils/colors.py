"""Color constants and helpers for TUI rendering."""

# ANSI color names compatible with blessed terminal
COLORS = {
    "white": "white",
    "green": "green",
    "blue": "blue",
    "yellow": "yellow",
    "red": "red",
    "cyan": "cyan",
    "magenta": "magenta",
    "black": "black",
}

# Rarity to color mapping
RARITY_COLORS = {
    "normal": "white",
    "uncommon": "green",
    "rare": "blue",
    "epic": "yellow",
    "legendary": "red",
}

# Stat display colors
STAT_POSITIVE_COLOR = "green"
STAT_NEGATIVE_COLOR = "red"
STAT_NEUTRAL_COLOR = "white"

# Portrait color options available to player
PORTRAIT_COLORS = ["white", "green", "blue", "yellow", "red", "cyan", "magenta"]


def stat_color(value: float) -> str:
    """Return color name based on stat value."""
    if value > 0:
        return STAT_POSITIVE_COLOR
    elif value < 0:
        return STAT_NEGATIVE_COLOR
    return STAT_NEUTRAL_COLOR
