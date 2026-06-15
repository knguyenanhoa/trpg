"""Experience calculation functions."""


def xp_required(stat_value: int) -> int:
    """Calculate XP required to level up a stat from its current value.

    Formula: 50 + 10 * (stat_value ^ 1.5)
    """
    return int(50 + 10 * (stat_value ** 1.5))


def xp_granted(difficulty: float) -> int:
    """Calculate XP granted for completing a quest of given difficulty.

    Formula: 10 * (difficulty ^ 2)
    Difficulty range: 0.0 to 5.0
    """
    return int(10 * (difficulty ** 2))


def xp_penalty(difficulty: float) -> float:
    """Calculate XP penalty for failing a quest.

    Penalty is 1/2 of what would have been granted.
    """
    return xp_granted(difficulty) / 2.0


def apply_xp_gain(current_stat: int, current_xp: float, xp_amount: float) -> tuple[int, float]:
    """Apply XP gain to a stat, handling level-ups with carry-over.

    Returns (new_stat_value, new_xp).
    """
    stat = current_stat
    xp = current_xp + xp_amount

    while xp >= xp_required(stat):
        xp -= xp_required(stat)
        stat += 1

    return stat, xp


def apply_xp_loss(current_stat: int, current_xp: float, xp_amount: float) -> tuple[int, float]:
    """Apply XP loss to a stat, handling level-downs with carry-over.

    If XP goes below 0, reduce stat by 1 and carry over deficit.
    Stat cannot go below 1.

    Returns (new_stat_value, new_xp).
    """
    stat = current_stat
    xp = current_xp - xp_amount

    while xp < 0 and stat > 1:
        stat -= 1
        xp = xp_required(stat) + xp  # xp is negative, so this subtracts the deficit

    # Floor: stat 1 with 0 XP minimum
    if stat <= 1:
        stat = 1
        xp = max(0.0, xp)

    return stat, xp
