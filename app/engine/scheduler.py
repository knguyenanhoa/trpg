"""Recurring quest scheduler and failure detection."""

from app.models.quest import Quest, QuestLogEntry
from app.utils.time_utils import now, start_of_day, end_of_day, start_of_month, end_of_month, parse_iso


def check_missed_quests(
    quests: list[Quest],
    quest_log: list[QuestLogEntry],
) -> list[Quest]:
    """Check for recurring quests that have been missed.

    A daily quest is missed if not completed today (before now).
    A monthly quest is missed if not completed this month (before now).

    Returns list of quests that should be marked as failed.
    """
    current_time = now()
    missed = []

    for quest in quests:
        if not quest.active:
            continue

        if quest.recurrence == "none":
            continue

        if quest.recurrence == "daily":
            # Check if completed today
            day_start = start_of_day(current_time)
            if not _completed_in_window(quest.id, quest_log, day_start, current_time):
                # Check if today has passed (it's past end of yesterday)
                # For daily quests, we check if the previous day had no completion
                yesterday_start = start_of_day(current_time)
                from datetime import timedelta
                prev_day_start = yesterday_start - timedelta(days=1)
                prev_day_end = end_of_day(prev_day_start)
                if not _completed_in_window(quest.id, quest_log, prev_day_start, prev_day_end):
                    # Check it wasn't already failed for yesterday
                    if not _failed_in_window(quest.id, quest_log, prev_day_start, prev_day_end):
                        missed.append(quest)

        elif quest.recurrence == "monthly":
            # Check if the previous month had no completion
            month_start = start_of_month(current_time)
            from datetime import timedelta
            prev_month_end = month_start - timedelta(microseconds=1)
            prev_month_start = start_of_month(prev_month_end)
            if not _completed_in_window(quest.id, quest_log, prev_month_start, prev_month_end):
                if not _failed_in_window(quest.id, quest_log, prev_month_start, prev_month_end):
                    missed.append(quest)

    return missed


def _completed_in_window(
    quest_id: str,
    quest_log: list[QuestLogEntry],
    window_start,
    window_end,
) -> bool:
    """Check if a quest was completed within a time window."""
    for entry in quest_log:
        if entry.quest_id != quest_id:
            continue
        if entry.status != "completed":
            continue
        if entry.completed_at:
            completed = parse_iso(entry.completed_at)
            if window_start <= completed <= window_end:
                return True
    return False


def _failed_in_window(
    quest_id: str,
    quest_log: list[QuestLogEntry],
    window_start,
    window_end,
) -> bool:
    """Check if a quest was already marked failed within a time window."""
    for entry in quest_log:
        if entry.quest_id != quest_id:
            continue
        if entry.status != "failed":
            continue
        if entry.started_at:
            failed_at = parse_iso(entry.started_at)
            if window_start <= failed_at <= window_end:
                return True
    return False
