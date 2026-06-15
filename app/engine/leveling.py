"""Level and rank-up logic."""

import json
import os

from app.config import DEFINITIONS_PATH
from app.models.character import Character
from app.models.item import Item


def load_ranks() -> list[dict]:
    """Load rank definitions."""
    path = os.path.join(DEFINITIONS_PATH, "ranks.json")
    with open(path, "r") as f:
        return json.load(f)


def get_current_rank_name(rank_number: int) -> str:
    """Get rank name by number."""
    ranks = load_ranks()
    for r in ranks:
        if r["rank"] == rank_number:
            return r["name"]
    return "Unknown"


def get_total_is(items: list[Item]) -> float:
    """Calculate total $IS from equipped items."""
    total = 0.0
    for item in items:
        if item.equipped:
            total += item.stats.total()
    return total


def can_rank_up(character: Character, equipped_items: list[Item]) -> tuple[bool, str]:
    """Check if character can rank up.

    Requirements:
    - All $CS >= 100
    - Total $IS meets minimum for next rank

    Returns (can_rank, reason).
    """
    if not character.can_rank_up():
        return False, "All character stats must be at least 100 to rank up."

    ranks = load_ranks()
    next_rank = character.rank + 1

    # Find next rank requirements
    next_rank_data = None
    for r in ranks:
        if r["rank"] == next_rank:
            next_rank_data = r
            break

    if next_rank_data is None:
        return False, "Already at maximum rank."

    total_is = get_total_is(equipped_items)
    if total_is < next_rank_data["min_is_total"]:
        return False, (
            f"Need total item stats of {next_rank_data['min_is_total']} "
            f"(currently {total_is:.1f}) to reach {next_rank_data['name']}."
        )

    return True, f"Ready to rank up to {next_rank_data['name']}!"


def perform_rank_up(character: Character) -> str:
    """Perform rank up. Returns new rank name."""
    character.rank += 1
    return get_current_rank_name(character.rank)
