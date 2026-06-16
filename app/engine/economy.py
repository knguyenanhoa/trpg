"""Economy calculations — item value, selling."""

from app.models.item import Item

# Rarity tier multipliers for coin value
RARITY_MULTIPLIERS = {
    "normal": 1,
    "uncommon": 10,
    "rare": 100,
    "epic": 1000,
    "legendary": 10000,
}


def item_value(item: Item) -> int:
    """Calculate an item's coin value.

    Value = abs(sum of all stats) * tier_multiplier, rounded to nearest int.
    """
    stats_dict = item.stats.to_dict()
    abs_sum = abs(sum(stats_dict.values()))
    multiplier = RARITY_MULTIPLIERS.get(item.rarity, 1)
    return round(abs_sum * multiplier)
