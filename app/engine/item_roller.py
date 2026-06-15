"""Random item generation."""

import json
import os
import random
import uuid

from app.config import (
    DEFINITIONS_PATH,
    ASSETS_PATH,
    CS_STATS,
    IS_STATS,
    ITEM_RARITIES,
    EQUIPMENT_SLOTS,
)
from app.models.item import Item
from app.models.stats import ItemStats, CharacterStats
from app.utils.time_utils import now_iso


def load_item_definitions(slot: str = None) -> list[dict]:
    """Load item definitions, optionally filtered by slot.

    Merges items.json, weapons.json, and armour.json.
    """
    all_items = []
    for filename in ["items.json", "weapons.json", "armour.json"]:
        path = os.path.join(DEFINITIONS_PATH, filename)
        if os.path.exists(path):
            with open(path, "r") as f:
                items = json.load(f)
                all_items.extend(items)

    if slot:
        all_items = [i for i in all_items if i.get("slot") == slot]

    return all_items


def roll_rarity(difficulty: float) -> str:
    """Roll item rarity, with difficulty shifting odds toward rarer items.

    Higher difficulty increases chance of rare+ drops.
    """
    # Build weights with difficulty bonus for rarer items
    rarities = list(ITEM_RARITIES.keys())
    base_weights = [ITEM_RARITIES[r]["weight"] for r in rarities]

    # Shift: each tier above normal gets a bonus proportional to difficulty
    adjusted = []
    for i, w in enumerate(base_weights):
        bonus = i * difficulty * 0.03  # higher tiers get more bonus
        adjusted.append(w + bonus)

    # Normalize
    total = sum(adjusted)
    normalized = [w / total for w in adjusted]

    return random.choices(rarities, weights=normalized, k=1)[0]


def roll_item_stats(player_level: float, player_cs: CharacterStats, rarity: str) -> ItemStats:
    """Generate random item stats weighted by player's $CS distribution.

    Rules:
    - abs(stat) in [0, max(5, player_level)]
    - Stats weighted toward player's strong CS
    - Net total is always slightly positive
    - Rarer items get a multiplier on positive stats
    """
    max_abs = max(5, int(player_level))

    # Get player CS values for weighting
    cs_values = {}
    for stat in CS_STATS:
        cs_values[stat] = player_cs.get_stat(stat)

    cs_total = sum(cs_values.values())
    if cs_total == 0:
        cs_total = 1  # avoid division by zero

    weights = {stat: cs_values[stat] / cs_total for stat in CS_STATS}

    # Rarity multiplier for positive stats
    rarity_mult = {
        "normal": 1.0,
        "uncommon": 1.2,
        "rare": 1.5,
        "epic": 1.8,
        "legendary": 2.2,
    }
    mult = rarity_mult.get(rarity, 1.0)

    stats = {}
    for i, is_stat in enumerate(IS_STATS):
        cs_stat = CS_STATS[i]
        weight = weights[cs_stat]

        # Roll with bias toward player's strong stats
        raw = random.uniform(-max_abs, max_abs) * (0.5 + weight)
        # Apply rarity multiplier to positive values
        if raw > 0:
            raw *= mult
        # Clamp to range
        raw = max(-max_abs, min(max_abs, raw))
        stats[is_stat] = round(raw, 1)

    # Ensure net positive
    total = sum(stats.values())
    if total <= 0:
        # Boost the stat with highest player weight
        best_cs = max(weights, key=weights.get)
        best_is = f"i{best_cs}"
        stats[best_is] += abs(total) + random.uniform(0.5, 2.0)
        stats[best_is] = round(min(stats[best_is], max_abs), 1)

    return ItemStats(
        istr=stats.get("istr", 0.0),
        idex=stats.get("idex", 0.0),
        icon=stats.get("icon", 0.0),
        iint=stats.get("iint", 0.0),
        iwis=stats.get("iwis", 0.0),
        icha=stats.get("icha", 0.0),
    )


def roll_item(player_level: float, player_cs: CharacterStats, difficulty: float) -> Item:
    """Roll a random item based on player stats and quest difficulty.

    Returns a fully generated Item.
    """
    # Pick rarity
    rarity = roll_rarity(difficulty)

    # Pick a random slot
    slot = random.choice(EQUIPMENT_SLOTS)

    # Try to pick a named item from definitions
    definitions = load_item_definitions(slot)
    if definitions:
        item_def = random.choice(definitions)
        name = item_def["name"]
        sprite = item_def.get("sprite", "")
    else:
        name = f"{rarity.title()} {slot.title()} Item"
        sprite = ""

    # Roll stats
    stats = roll_item_stats(player_level, player_cs, rarity)

    return Item(
        id=str(uuid.uuid4()),
        name=name,
        slot=slot,
        rarity=rarity,
        stats=stats,
        sprite=sprite,
        acquired_at=now_iso(),
        equipped=False,
    )
