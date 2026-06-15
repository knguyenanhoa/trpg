"""Quest start, complete, and fail logic."""

from app.models.quest import Quest, QuestLogEntry
from app.models.character import Character
from app.models.item import Item
from app.models.stats import CharacterStats
from app.engine.experience import xp_granted, xp_penalty, apply_xp_gain, apply_xp_loss
from app.engine.item_roller import roll_item
from app.utils.time_utils import now_iso, parse_iso, duration_seconds


def start_quest(quest: Quest) -> str:
    """Mark a quest as started. Returns the start timestamp."""
    return now_iso()


def complete_quest(
    quest: Quest,
    character: Character,
    started_at: str,
) -> tuple[QuestLogEntry, Item | None]:
    """Complete a quest, granting XP and potentially an item.

    Returns (log_entry, item_or_none).
    """
    completed_at = now_iso()
    start_dt = parse_iso(started_at)
    end_dt = parse_iso(completed_at)
    duration = duration_seconds(start_dt, end_dt)

    # Calculate XP
    total_xp = xp_granted(quest.difficulty)
    xp_per_stat = total_xp / max(1, len(quest.stats))

    # Apply XP to each stat
    for stat_name in quest.stats:
        current_stat = character.stats.get_stat(stat_name)
        current_xp = character.stats.get_xp(stat_name)
        new_stat, new_xp = apply_xp_gain(current_stat, current_xp, xp_per_stat)
        character.stats.set_stat(stat_name, new_stat)
        character.stats.set_xp(stat_name, new_xp)

    # Roll for item drop (50% chance on completion)
    import random
    item = None
    if random.random() < 0.5:
        item = roll_item(character.level, character.stats, quest.difficulty)

    # Create log entry
    log_entry = QuestLogEntry(
        quest_id=quest.id,
        quest_name=quest.name,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration,
        xp_granted=total_xp,
        stats_affected=quest.stats[:],
        item_dropped=item.id if item else None,
    )

    return log_entry, item


def fail_quest(quest: Quest, character: Character) -> QuestLogEntry:
    """Fail a quest, applying XP penalty.

    Penalty is 1/2 of XP that would have been granted.
    Returns a log entry.
    """
    penalty = xp_penalty(quest.difficulty)
    penalty_per_stat = penalty / max(1, len(quest.stats))

    # Apply penalty to each stat
    for stat_name in quest.stats:
        current_stat = character.stats.get_stat(stat_name)
        current_xp = character.stats.get_xp(stat_name)
        new_stat, new_xp = apply_xp_loss(current_stat, current_xp, penalty_per_stat)
        character.stats.set_stat(stat_name, new_stat)
        character.stats.set_xp(stat_name, new_xp)

    log_entry = QuestLogEntry(
        quest_id=quest.id,
        quest_name=quest.name,
        status="failed",
        started_at=now_iso(),
        completed_at=now_iso(),
        duration_seconds=0,
        xp_granted=-penalty,
        stats_affected=quest.stats[:],
        item_dropped=None,
    )

    return log_entry
