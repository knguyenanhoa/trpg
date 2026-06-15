"""Quest management screen — list, create, start, complete, pause."""

import uuid

from app.tui.base_screen import BaseScreen
from app.tui.fzf_picker import InlinePicker
from app.models.character import Character
from app.models.quest import Quest
from app.config import CS_STATS, QUEST_RECURRENCE, DIFFICULTY_MIN, DIFFICULTY_MAX
from app.db.file_store import (
    load_quests, save_quests, load_active_quests, save_active_quests,
    save_character, append_quest_log, load_inventory, save_inventory,
    load_completed_quests, save_completed_quests, load_quest_log,
)
from app.engine.quest_engine import start_quest, complete_quest
from app.utils.sanitize import validate_name, sanitize_name, validate_float
from app.utils.time_utils import now_iso, now, start_of_day, end_of_day, start_of_month, end_of_month, parse_iso


class QuestScreen(BaseScreen):
    """Quest list and management with active/completed tabs."""

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.quests = load_quests(character.name)
        self.active_quests = load_active_quests(character.name)
        self.completed_quests = load_completed_quests(character.name)
        self.picker = None
        self.tab = "active"  # active, completed
        self.mode = "list"  # list, create
        self.message = ""
        # Create mode fields (condensed single form)
        self._reset_create_form()

    def _reset_create_form(self):
        self.create_fields = {
            "name": "",
            "description": "",
            "difficulty": "1.0",
            "recurrence": "none",
        }
        self.create_stat_toggles = [False] * len(CS_STATS)
        self.create_field_order = ["name", "difficulty", "recurrence", "stats", "description"]
        self.create_cursor = 0  # which field row is active
        self.create_stat_cursor = 0  # sub-cursor within stats field
        self.create_recurrence_cursor = 0  # sub-cursor within recurrence

    def _sorted_quests(self) -> list[Quest]:
        """Return active quests sorted alphabetically."""
        return sorted(self.quests, key=lambda q: q.name.lower())

    def _sorted_completed(self) -> list[Quest]:
        """Return completed quests sorted alphabetically."""
        return sorted(self.completed_quests, key=lambda q: q.name.lower())

    def _quest_display_list(self) -> list[str]:
        """Generate display strings for active quest list."""
        items = []
        for q in self._sorted_quests():
            recur = f"({q.recurrence})" if q.recurrence != "none" else ""
            items.append(f"{q.name} — d:{q.difficulty} {recur}")
        items.append("+ New Quest")
        return items

    def _completed_display_list(self) -> list[str]:
        """Generate display strings for completed quest list."""
        items = []
        for q in self._sorted_completed():
            recur = f"({q.recurrence})" if q.recurrence != "none" else ""
            items.append(f"{q.name} — d:{q.difficulty} {recur}")
        if not items:
            items.append("(no completed quests)")
        return items

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.cyan + f"{self.character.name} — Quests" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 50 + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 3) + t.yellow + self.message + t.normal, end="")

        # Tab indicator
        if self.tab == "active":
            print(t.move_xy(2, 4) + t.bold + "[A]ctive" + t.normal + "  " + t.dim + "[C]ompleted" + t.normal, end="")
        else:
            print(t.move_xy(2, 4) + t.dim + "[A]ctive" + t.normal + "  " + t.bold + "[C]ompleted" + t.normal, end="")

        if self.mode == "list":
            self._render_list()
        elif self.mode == "create":
            self._render_create()

        if self.mode == "list":
            if self.tab == "active":
                controls = "n:new s:start c:complete p:pause d:delete Tab:tabs Esc:back"
            else:
                controls = "d:delete  Tab:switch tabs  Esc:back  ?:help"
            print(t.move_xy(2, t.height - 1) + t.dim + controls + t.normal, end="")
        else:
            print(t.move_xy(2, t.height - 1) + t.dim + "Tab:next field  Shift-Tab:prev  Enter:submit  Esc:cancel" + t.normal, end="")

    def _render_list(self):
        t = self.term
        if self.tab == "active":
            items = self._quest_display_list()
            sorted_q = self._sorted_quests()
            if self.picker is None:
                self.picker = InlinePicker(items, t, prompt="Active Quests:", x=2, y=6)
            else:
                self.picker.items = items
                self.picker.filtered_indices = list(range(len(items)))
            self.picker.render()
            self._render_quest_status_colors(sorted_q, 6 + 2)
        else:
            items = self._completed_display_list()
            if self.picker is None:
                self.picker = InlinePicker(items, t, prompt="Completed Quests:", x=2, y=6)
            else:
                self.picker.items = items
                self.picker.filtered_indices = list(range(len(items)))
            self.picker.render()

    def _render_quest_status_colors(self, sorted_quests: list[Quest], list_start_y: int):
        """Render color indicators next to quest entries."""
        t = self.term
        visible_start = self.picker.scroll_offset
        visible_end = min(visible_start + self.picker.max_visible, len(self.picker.filtered_indices))
        for i in range(visible_start, visible_end):
            if i >= len(self.picker.filtered_indices):
                break
            idx = self.picker.filtered_indices[i]
            if idx >= len(sorted_quests):
                break
            quest = sorted_quests[idx]
            line_y = list_start_y + (i - visible_start)
            indicator_x = 55
            if quest.paused:
                print(t.move_xy(indicator_x, line_y) + t.red + "■ PAUSED" + t.normal, end="")
            elif quest.id in self.active_quests:
                print(t.move_xy(indicator_x, line_y) + t.green + "■ STARTED" + t.normal, end="")

    def _render_create(self):
        """Render condensed single-form quest creation."""
        t = self.term
        y = 6
        print(t.move_xy(2, y) + t.bold + "New Quest" + t.normal + t.dim + " (Tab: next, Enter: submit)" + t.normal, end="")
        y += 1
        current_y = y

        for i, field in enumerate(self.create_field_order):
            is_active = (i == self.create_cursor)
            prefix = t.cyan + "▸ " + t.normal if is_active else "  "

            if field == "name":
                val = self.create_fields["name"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Name: {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1

            elif field == "difficulty":
                val = self.create_fields["difficulty"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Difficulty (0-5): {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1

            elif field == "recurrence":
                # Show all options inline, highlight current
                print(t.move_xy(2, current_y) + f"{prefix}Recurrence: ", end="")
                for ri, rec in enumerate(QUEST_RECURRENCE):
                    if rec == self.create_fields["recurrence"]:
                        print(t.reverse + f" {rec} " + t.normal, end=" ")
                    else:
                        print(t.dim + rec + t.normal, end=" ")
                print(t.clear_eol, end="")
                current_y += 1

            elif field == "stats":
                selected = [CS_STATS[j] for j, v in enumerate(self.create_stat_toggles) if v]
                display = ", ".join(s.upper() for s in selected) if selected else t.dim + "(none)" + t.normal
                print(t.move_xy(2, current_y) + f"{prefix}Stats: {display}" + t.clear_eol, end="")
                current_y += 1
                # If this field is active, show the stat toggles
                if is_active:
                    for j, stat in enumerate(CS_STATS):
                        mark = t.green + "[x]" + t.normal if self.create_stat_toggles[j] else "[ ]"
                        stat_prefix = t.cyan + "> " + t.normal if j == self.create_stat_cursor else "  "
                        print(t.move_xy(6, current_y) + f"{stat_prefix}{mark} {stat.upper()}" + t.clear_eol, end="")
                        current_y += 1

            elif field == "description":
                val = self.create_fields["description"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Desc: {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1

    def on_key(self, key):
        t = self.term
        self.message = ""

        if self.mode == "list":
            self._handle_list_key(key)
        elif self.mode == "create":
            self._handle_create_key(key)

    def _handle_list_key(self, key):
        t = self.term

        if key == "q":
            self.manager.running = False
            return

        # Tab switching between active/completed
        if key == "\t":
            self.tab = "completed" if self.tab == "active" else "active"
            self.picker = None
            return

        if self.tab == "completed":
            if key == "d":
                self._delete_completed_quest()
                return
            if key.code == t.KEY_ESCAPE or key == "h":
                self.manager.pop()
                return
            if self.picker:
                self.picker.on_key(key)
            return

        # Active tab controls
        if key == "n":
            self._start_create()
            return
        if key == "s":
            self._start_selected_quest()
            return
        if key == "c":
            self._complete_selected_quest()
            return
        if key == "p":
            self._pause_selected_quest()
            return
        if key == "d":
            self._delete_selected_quest()
            return
        if key.code == t.KEY_ESCAPE or key == "h":
            self.manager.pop()
            return

        if self.picker:
            result, active = self.picker.on_key(key)
            if not active:
                if result == "+ New Quest":
                    self._start_create()

    def _start_create(self):
        self.mode = "create"
        self._reset_create_form()

    def _handle_create_key(self, key):
        t = self.term
        current_field = self.create_field_order[self.create_cursor]

        # Escape always cancels
        if key.code == t.KEY_ESCAPE:
            self.mode = "list"
            self.picker = None
            return

        # Enter submits the form (from any field)
        if key.code == t.KEY_ENTER:
            self._finalize_create()
            return

        # Tab moves to next field
        if key == "\t":
            self.create_cursor = min(self.create_cursor + 1, len(self.create_field_order) - 1)
            return

        # Shift-Tab (KEY_BTAB) moves to previous field
        if key.code == t.KEY_BTAB:
            self.create_cursor = max(self.create_cursor - 1, 0)
            return

        # Field-specific input handling
        if current_field in ("name", "difficulty", "description"):
            # Text input
            if key.code == t.KEY_BACKSPACE or key == "\x7f":
                self.create_fields[current_field] = self.create_fields[current_field][:-1]
            elif not key.is_sequence and key.isprintable():
                self.create_fields[current_field] += str(key)

        elif current_field == "recurrence":
            # Left/right or j/k to cycle through options
            if key == "j" or key.code == t.KEY_DOWN or key == "l" or key.code == t.KEY_RIGHT:
                idx = QUEST_RECURRENCE.index(self.create_fields["recurrence"])
                idx = (idx + 1) % len(QUEST_RECURRENCE)
                self.create_fields["recurrence"] = QUEST_RECURRENCE[idx]
            elif key == "k" or key.code == t.KEY_UP or key == "h" or key.code == t.KEY_LEFT:
                idx = QUEST_RECURRENCE.index(self.create_fields["recurrence"])
                idx = (idx - 1) % len(QUEST_RECURRENCE)
                self.create_fields["recurrence"] = QUEST_RECURRENCE[idx]
            elif key == " ":
                # Space also cycles forward
                idx = QUEST_RECURRENCE.index(self.create_fields["recurrence"])
                idx = (idx + 1) % len(QUEST_RECURRENCE)
                self.create_fields["recurrence"] = QUEST_RECURRENCE[idx]

        elif current_field == "stats":
            # Navigate through stats with j/k, toggle with space
            if key == "j" or key.code == t.KEY_DOWN:
                self.create_stat_cursor = min(self.create_stat_cursor + 1, len(CS_STATS) - 1)
            elif key == "k" or key.code == t.KEY_UP:
                self.create_stat_cursor = max(self.create_stat_cursor - 1, 0)
            elif key == " ":
                self.create_stat_toggles[self.create_stat_cursor] = not self.create_stat_toggles[self.create_stat_cursor]

    def _finalize_create(self):
        # Validate
        name = sanitize_name(self.create_fields["name"])
        valid, err = validate_name(name)
        if not valid:
            self.message = err or "Name is required."
            return

        valid, difficulty, err = validate_float(
            self.create_fields["difficulty"], DIFFICULTY_MIN, DIFFICULTY_MAX
        )
        if not valid:
            self.message = f"Difficulty: {err}"
            return

        stats = [CS_STATS[i] for i, v in enumerate(self.create_stat_toggles) if v]
        if not stats:
            self.message = "Select at least one stat."
            return

        quest = Quest(
            id=str(uuid.uuid4()),
            name=name,
            description=self.create_fields["description"],
            difficulty=difficulty,
            stats=stats,
            recurrence=self.create_fields["recurrence"],
            created_at=now_iso(),
            active=True,
        )
        self.quests.append(quest)
        save_quests(self.character.name, self.quests)
        self.message = f"Quest '{quest.name}' created!"
        self.mode = "list"
        self.picker = None

    def _get_selected_quest(self) -> Quest | None:
        """Get the currently selected quest from the sorted active list."""
        if not self.picker or not self.picker.filtered_indices:
            return None
        idx = self.picker.filtered_indices[self.picker.cursor]
        sorted_q = self._sorted_quests()
        if idx >= len(sorted_q):
            return None
        return sorted_q[idx]

    def _start_selected_quest(self):
        quest = self._get_selected_quest()
        if not quest:
            return
        if quest.paused:
            self.message = "Cannot start a paused quest. Unpause first (press 'p')."
            return
        if quest.id in self.active_quests:
            self.message = "Quest already started."
            return
        started_at = start_quest(quest)
        self.active_quests[quest.id] = started_at
        save_active_quests(self.character.name, self.active_quests)
        self.message = f"Quest '{quest.name}' started!"
        self.picker = None

    def _complete_selected_quest(self):
        quest = self._get_selected_quest()
        if not quest:
            return
        if quest.id not in self.active_quests:
            self.message = "Start the quest first (press 's')."
            return

        if not self._can_complete_recurring(quest):
            return

        started_at = self.active_quests.pop(quest.id)
        save_active_quests(self.character.name, self.active_quests)

        log_entry, item = complete_quest(quest, self.character, started_at)
        save_character(self.character)
        append_quest_log(self.character.name, log_entry)

        msg = f"Quest '{quest.name}' completed! +{log_entry.xp_granted:.0f} XP"
        if item:
            inventory = load_inventory(self.character.name)
            inventory.append(item)
            save_inventory(self.character.name, inventory)
            msg += f" | Item: {item.name} ({item.rarity})"

        # Move non-recurring quests to completed list
        if quest.recurrence == "none":
            self.quests.remove(quest)
            quest.active = False
            self.completed_quests.append(quest)
            save_completed_quests(self.character.name, self.completed_quests)

        save_quests(self.character.name, self.quests)
        self.message = msg
        self.picker = None

    def _can_complete_recurring(self, quest: Quest) -> bool:
        """Check if a recurring quest can be completed now."""
        if quest.recurrence == "none":
            return True

        current_time = now()
        quest_log = load_quest_log(self.character.name)

        if quest.recurrence == "daily":
            day_start = start_of_day(current_time)
            day_end = end_of_day(current_time)
            for entry in quest_log:
                if entry.quest_id != quest.id or entry.status != "completed":
                    continue
                if entry.completed_at:
                    completed = parse_iso(entry.completed_at)
                    if day_start <= completed <= day_end:
                        self.message = "Daily quest already completed today."
                        return False

        elif quest.recurrence == "monthly":
            month_start = start_of_month(current_time)
            month_end = end_of_month(current_time)
            for entry in quest_log:
                if entry.quest_id != quest.id or entry.status != "completed":
                    continue
                if entry.completed_at:
                    completed = parse_iso(entry.completed_at)
                    if month_start <= completed <= month_end:
                        self.message = "Monthly quest already completed this month."
                        return False

        return True

    def _pause_selected_quest(self):
        quest = self._get_selected_quest()
        if not quest:
            return

        if not quest.can_pause():
            self.message = "Recurring quests cannot be paused."
            return

        quest.paused = not quest.paused
        if quest.paused and quest.id in self.active_quests:
            del self.active_quests[quest.id]
            save_active_quests(self.character.name, self.active_quests)

        save_quests(self.character.name, self.quests)
        status = "paused" if quest.paused else "unpaused"
        self.message = f"Quest '{quest.name}' {status}."
        self.picker = None

    def _delete_selected_quest(self):
        quest = self._get_selected_quest()
        if not quest:
            return
        self.quests.remove(quest)
        if quest.id in self.active_quests:
            del self.active_quests[quest.id]
        save_quests(self.character.name, self.quests)
        save_active_quests(self.character.name, self.active_quests)
        self.message = f"Quest '{quest.name}' deleted."
        self.picker = None

    def _delete_completed_quest(self):
        """Delete a quest from the completed list."""
        if not self.picker or not self.picker.filtered_indices:
            return
        idx = self.picker.filtered_indices[self.picker.cursor]
        sorted_c = self._sorted_completed()
        if idx >= len(sorted_c):
            return
        quest = sorted_c[idx]
        self.completed_quests.remove(quest)
        save_completed_quests(self.character.name, self.completed_quests)
        self.message = f"Removed '{quest.name}' from completed list."
        self.picker = None
