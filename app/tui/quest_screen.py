"""Quest management screen — list, create, start, complete."""

import uuid

from app.tui.base_screen import BaseScreen
from app.tui.fzf_picker import InlinePicker
from app.models.character import Character
from app.models.quest import Quest
from app.config import CS_STATS, QUEST_RECURRENCE, DIFFICULTY_MIN, DIFFICULTY_MAX
from app.db.file_store import (
    load_quests, save_quests, load_active_quests, save_active_quests,
    save_character, append_quest_log, load_inventory, save_inventory,
)
from app.engine.quest_engine import start_quest, complete_quest, fail_quest
from app.utils.sanitize import validate_name, sanitize_name, validate_float
from app.utils.time_utils import now_iso


class QuestScreen(BaseScreen):
    """Quest list and management."""

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.quests = load_quests(character.name)
        self.active_quests = load_active_quests(character.name)
        self.picker = None
        self.mode = "list"  # list, create
        self.message = ""
        # Create mode fields
        self.create_step = 0
        self.create_name = ""
        self.create_desc = ""
        self.create_difficulty = 1.0
        self.create_stats = []
        self.create_recurrence = "none"
        self.input_buffer = ""
        self.cursor = 0
        self.stat_toggles = [False] * len(CS_STATS)

    def _quest_display_list(self) -> list[str]:
        """Generate display strings for quest list."""
        items = []
        for q in self.quests:
            status = ""
            if q.id in self.active_quests:
                status = " [ACTIVE]"
            elif not q.active:
                status = " [INACTIVE]"
            recur = f" ({q.recurrence})" if q.recurrence != "none" else ""
            items.append(f"{q.name} — d:{q.difficulty}{recur}{status}")
        items.append("+ New Quest")
        return items

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.cyan + f"{self.character.name} — Quests" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 50 + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 3) + t.yellow + self.message + t.normal, end="")

        if self.mode == "list":
            self._render_list()
        elif self.mode == "create":
            self._render_create()

        controls = "n: new  s: start  c: complete  d: delete  Esc: back  ?: help"
        print(t.move_xy(2, t.height - 1) + t.dim + controls + t.normal, end="")

    def _render_list(self):
        t = self.term
        items = self._quest_display_list()
        if self.picker is None:
            self.picker = InlinePicker(items, t, prompt="Quests:", x=2, y=5)
        else:
            # Refresh items
            self.picker.items = items
            self.picker.filtered_indices = list(range(len(items)))
        self.picker.render()

    def _render_create(self):
        t = self.term
        y = 5
        if self.create_step == 0:
            print(t.move_xy(2, y) + "Quest name:", end="")
            print(t.move_xy(2, y + 1) + f"> {self.input_buffer}_", end="")
        elif self.create_step == 1:
            print(t.move_xy(2, y) + "Quest description (optional):", end="")
            print(t.move_xy(2, y + 1) + f"> {self.input_buffer}_", end="")
        elif self.create_step == 2:
            print(t.move_xy(2, y) + f"Difficulty ({DIFFICULTY_MIN}-{DIFFICULTY_MAX}):", end="")
            print(t.move_xy(2, y + 1) + f"> {self.input_buffer}_", end="")
        elif self.create_step == 3:
            print(t.move_xy(2, y) + "Select stats to train (j/k, Space to toggle, Enter to confirm):", end="")
            for i, stat in enumerate(CS_STATS):
                mark = "[x]" if self.stat_toggles[i] else "[ ]"
                prefix = " > " if i == self.cursor else "   "
                print(t.move_xy(2, y + 1 + i) + f"{prefix}{mark} {stat.upper()}", end="")
        elif self.create_step == 4:
            print(t.move_xy(2, y) + "Recurrence:", end="")
            for i, rec in enumerate(QUEST_RECURRENCE):
                marker = " > " if i == self.cursor else "   "
                if i == self.cursor:
                    print(t.move_xy(2, y + 1 + i) + t.reverse + f"{marker}{rec}" + t.normal, end="")
                else:
                    print(t.move_xy(2, y + 1 + i) + f"{marker}{rec}", end="")

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

        if key == "n":
            self._start_create()
            return

        if key == "s":
            self._start_selected_quest()
            return

        if key == "c":
            self._complete_selected_quest()
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
                elif result is not None:
                    pass  # Could show quest details

    def _start_create(self):
        self.mode = "create"
        self.create_step = 0
        self.input_buffer = ""
        self.create_name = ""
        self.create_desc = ""
        self.create_difficulty = 1.0
        self.create_stats = []
        self.create_recurrence = "none"
        self.stat_toggles = [False] * len(CS_STATS)
        self.cursor = 0

    def _handle_create_key(self, key):
        t = self.term

        if key.code == t.KEY_ESCAPE:
            self.mode = "list"
            self.picker = None
            return

        if self.create_step in (0, 1, 2):
            # Text input steps
            if key.code == t.KEY_ENTER:
                self._submit_create_step()
            elif key.code == t.KEY_BACKSPACE or key == "\x7f":
                self.input_buffer = self.input_buffer[:-1]
            elif not key.is_sequence and key.isprintable():
                self.input_buffer += str(key)
        elif self.create_step == 3:
            # Stat toggle
            if key == "j" or key.code == t.KEY_DOWN:
                self.cursor = min(self.cursor + 1, len(CS_STATS) - 1)
            elif key == "k" or key.code == t.KEY_UP:
                self.cursor = max(self.cursor - 1, 0)
            elif key == " ":
                self.stat_toggles[self.cursor] = not self.stat_toggles[self.cursor]
            elif key.code == t.KEY_ENTER:
                self.create_stats = [CS_STATS[i] for i, v in enumerate(self.stat_toggles) if v]
                if not self.create_stats:
                    self.message = "Select at least one stat."
                else:
                    self.create_step = 4
                    self.cursor = 0
        elif self.create_step == 4:
            # Recurrence selection
            if key == "j" or key.code == t.KEY_DOWN:
                self.cursor = min(self.cursor + 1, len(QUEST_RECURRENCE) - 1)
            elif key == "k" or key.code == t.KEY_UP:
                self.cursor = max(self.cursor - 1, 0)
            elif key.code == t.KEY_ENTER or key == "l":
                self.create_recurrence = QUEST_RECURRENCE[self.cursor]
                self._finalize_create()

    def _submit_create_step(self):
        if self.create_step == 0:
            name = sanitize_name(self.input_buffer)
            valid, err = validate_name(name)
            if not valid:
                self.message = err
                return
            self.create_name = name
            self.input_buffer = ""
            self.create_step = 1
        elif self.create_step == 1:
            self.create_desc = self.input_buffer
            self.input_buffer = ""
            self.create_step = 2
        elif self.create_step == 2:
            valid, val, err = validate_float(self.input_buffer, DIFFICULTY_MIN, DIFFICULTY_MAX)
            if not valid:
                self.message = err
                return
            self.create_difficulty = val
            self.input_buffer = ""
            self.create_step = 3
            self.cursor = 0

    def _finalize_create(self):
        quest = Quest(
            id=str(uuid.uuid4()),
            name=self.create_name,
            description=self.create_desc,
            difficulty=self.create_difficulty,
            stats=self.create_stats,
            recurrence=self.create_recurrence,
            created_at=now_iso(),
            active=True,
        )
        self.quests.append(quest)
        save_quests(self.character.name, self.quests)
        self.message = f"Quest '{quest.name}' created!"
        self.mode = "list"
        self.picker = None

    def _start_selected_quest(self):
        if not self.picker or not self.picker.filtered_indices:
            return
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(self.quests):
            return  # it's the "+ New Quest" item
        quest = self.quests[idx]
        if quest.id in self.active_quests:
            self.message = "Quest already active."
            return
        started_at = start_quest(quest)
        self.active_quests[quest.id] = started_at
        save_active_quests(self.character.name, self.active_quests)
        self.message = f"Quest '{quest.name}' started!"
        self.picker = None

    def _complete_selected_quest(self):
        if not self.picker or not self.picker.filtered_indices:
            return
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(self.quests):
            return
        quest = self.quests[idx]
        if quest.id not in self.active_quests:
            self.message = "Start the quest first (press 's')."
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
        self.message = msg
        self.picker = None

    def _delete_selected_quest(self):
        if not self.picker or not self.picker.filtered_indices:
            return
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(self.quests):
            return
        quest = self.quests[idx]
        self.quests.remove(quest)
        if quest.id in self.active_quests:
            del self.active_quests[quest.id]
        save_quests(self.character.name, self.quests)
        save_active_quests(self.character.name, self.active_quests)
        self.message = f"Quest '{quest.name}' deleted."
        self.picker = None
