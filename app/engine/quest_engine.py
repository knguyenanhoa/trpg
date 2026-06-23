"""Quest start, complete, fail, and network graph logic.

Handles individual quest lifecycle (start/complete/fail) and quest network
operations (overquest completion detection, quest insertion/deletion in
the network graph with proper dependency reassignment).
"""

from app.models.quest import Quest, QuestLogEntry
from app.models.character import Character
from app.models.item import Item
from app.models.stats import CharacterStats
from app.engine.experience import xp_granted, xp_penalty, apply_xp_gain, apply_xp_loss
from app.engine.item_roller import roll_item
from app.utils.time_utils import now_iso, parse_iso, duration_seconds

# Large reward multiplier for overquest completion
OVERQUEST_REWARD_MULTIPLIER = 3.0


def start_quest(quest: Quest) -> str:
    """Mark a quest as started. Returns the start timestamp."""
    quest.status = "in-progress"
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

    quest.status = "completed"

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


# --- Quest Network Operations ---


def get_quest_by_id(quests: list[Quest], quest_id: str) -> Quest | None:
    """Find a quest by ID in a list."""
    for q in quests:
        if q.id == quest_id:
            return q
    return None


def get_subquests(quests: list[Quest], overquest_id: str) -> list[Quest]:
    """Get all subquests belonging to an overquest."""
    return [q for q in quests if q.overquest_id == overquest_id]


def get_predecessors(quests: list[Quest], quest_id: str) -> list[Quest]:
    """Find all quests that have quest_id in their next_quests list."""
    return [q for q in quests if quest_id in q.next_quests]


def get_end_quests(quests: list[Quest], overquest_id: str) -> list[Quest]:
    """Get the terminal quests in a quest line (subquests with no next_quests
    that still belong to the same overquest)."""
    subquests = get_subquests(quests, overquest_id)
    sub_ids = {q.id for q in subquests}
    end_quests = []
    for q in subquests:
        # A quest is terminal if it has no next_quests within the same overquest
        next_in_line = [nid for nid in q.next_quests if nid in sub_ids]
        if not next_in_line:
            end_quests.append(q)
    return end_quests


def check_overquest_completion(quests: list[Quest], overquest: Quest) -> bool:
    """Check if all end quests in the overquest's line are completed.

    An overquest completes when all its terminal subquests are completed.
    """
    if not overquest.is_overquest:
        return False
    end_quests = get_end_quests(quests, overquest.id)
    if not end_quests:
        return False
    return all(q.status == "completed" for q in end_quests)


def complete_overquest(
    quests: list[Quest],
    overquest: Quest,
    character: Character,
) -> tuple[QuestLogEntry, Item | None]:
    """Complete an overquest, granting a large reward (multiplied XP).

    Called automatically when all end-quests in the line are completed.
    Returns (log_entry, item_or_none).
    """
    completed_at = now_iso()

    # Large reward: overquest difficulty * multiplier
    total_xp = xp_granted(overquest.difficulty) * OVERQUEST_REWARD_MULTIPLIER
    xp_per_stat = total_xp / max(1, len(overquest.stats))

    for stat_name in overquest.stats:
        current_stat = character.stats.get_stat(stat_name)
        current_xp = character.stats.get_xp(stat_name)
        new_stat, new_xp = apply_xp_gain(current_stat, current_xp, xp_per_stat)
        character.stats.set_stat(stat_name, new_stat)
        character.stats.set_xp(stat_name, new_xp)

    import random
    item = None
    if random.random() < 0.5:
        item = roll_item(character.level, character.stats, overquest.difficulty)

    overquest.status = "completed"
    overquest.active = False

    log_entry = QuestLogEntry(
        quest_id=overquest.id,
        quest_name=overquest.name,
        status="completed",
        started_at=overquest.created_at,
        completed_at=completed_at,
        duration_seconds=0,
        xp_granted=total_xp,
        stats_affected=overquest.stats[:],
        item_dropped=item.id if item else None,
    )

    return log_entry, item


def insert_quest_in_network(
    quests: list[Quest],
    new_quest: Quest,
    before_quest_ids: list[str],
) -> list[Quest]:
    """Insert a quest into the network before specified quests.

    Any quest that previously pointed to one of before_quest_ids will now
    point to new_quest instead. new_quest.next_quests is set to before_quest_ids.
    Standard linked-list insertion.
    """
    new_quest.next_quests = before_quest_ids[:]

    # Re-link predecessors: anything that pointed to a before_quest now points to new_quest
    for q in quests:
        updated_next = []
        for nid in q.next_quests:
            if nid in before_quest_ids:
                if new_quest.id not in updated_next:
                    updated_next.append(new_quest.id)
            else:
                updated_next.append(nid)
        q.next_quests = updated_next

    quests.append(new_quest)
    return quests


def delete_quest_from_network(quests: list[Quest], quest_id: str) -> list[Quest]:
    """Delete a quest from the network, reassigning dependencies.

    If the deleted quest has predecessors and successors, each predecessor
    now points to all of the deleted quest's next_quests.
    """
    quest = get_quest_by_id(quests, quest_id)
    if not quest:
        return quests

    successor_ids = quest.next_quests[:]
    predecessors = get_predecessors(quests, quest_id)

    # Reassign: each predecessor now points to the deleted quest's successors
    for pred in predecessors:
        pred.next_quests = [
            nid for nid in pred.next_quests if nid != quest_id
        ] + successor_ids
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for nid in pred.next_quests:
            if nid not in seen:
                seen.add(nid)
                deduped.append(nid)
        pred.next_quests = deduped

    quests.remove(quest)
    return quests


def delete_overquest(quests: list[Quest], overquest_id: str) -> list[Quest]:
    """Delete an overquest and all subquests that exclusively belong to it.

    Subquests that also serve in a different quest line (have a different
    overquest_id or are referenced by quests outside this line) are kept.
    """
    overquest = get_quest_by_id(quests, overquest_id)
    if not overquest or not overquest.is_overquest:
        return quests

    subquests = get_subquests(quests, overquest_id)
    to_remove = []

    for sq in subquests:
        # Check if this subquest is referenced by quests outside this overquest
        external_refs = [
            q for q in quests
            if q.overquest_id != overquest_id and sq.id in q.next_quests
        ]
        if not external_refs:
            to_remove.append(sq.id)

    # Remove subquests (with proper network reassignment)
    for sq_id in to_remove:
        quests = delete_quest_from_network(quests, sq_id)

    # Remove the overquest itself
    quests = [q for q in quests if q.id != overquest_id]
    return quests


def reassign_quest_position(
    quests: list[Quest],
    quest_id: str,
    new_next_quest_ids: list[str],
) -> list[Quest]:
    """Move a quest to a different position in the network.

    Removes it from its current position (reassigning its old predecessors
    to its old successors), then re-inserts it before new_next_quest_ids.
    """
    quest = get_quest_by_id(quests, quest_id)
    if not quest:
        return quests

    old_successors = quest.next_quests[:]
    predecessors = get_predecessors(quests, quest_id)

    # Unlink from current position: predecessors point to old successors
    for pred in predecessors:
        pred.next_quests = [
            nid for nid in pred.next_quests if nid != quest_id
        ] + old_successors
        # Deduplicate
        seen = set()
        deduped = []
        for nid in pred.next_quests:
            if nid not in seen:
                seen.add(nid)
                deduped.append(nid)
        pred.next_quests = deduped

    # Re-link at new position
    quest.next_quests = new_next_quest_ids[:]

    # Anything that pointed to new_next_quest_ids now points to quest
    for q in quests:
        if q.id == quest_id:
            continue
        updated_next = []
        for nid in q.next_quests:
            if nid in new_next_quest_ids:
                if quest_id not in updated_next:
                    updated_next.append(quest_id)
            else:
                updated_next.append(nid)
        q.next_quests = updated_next

    return quests


def validate_overquest(quests: list[Quest], overquest: Quest) -> tuple[bool, str]:
    """Validate that an overquest has at least 1 subquest."""
    if not overquest.is_overquest:
        return False, "Not an overquest."
    subquests = get_subquests(quests, overquest.id)
    if not subquests:
        return False, "An overquest must have at least 1 subquest."
    return True, ""
