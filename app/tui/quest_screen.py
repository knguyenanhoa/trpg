"""Quest management screen — list, create, start, complete, pause.

Displays quests in a hierarchical structure:
- Overquests appear as top-level foldable headers
- Subquests are nested under their overquest (indented)
- Standalone quests (no overquest) appear at top level
- Both Active and Completed tabs use this structure
"""

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
    load_quest_templates,
)
from app.engine.quest_engine import (
    start_quest, complete_quest, check_overquest_completion,
    complete_overquest, get_quest_by_id, get_subquests, get_predecessors,
)
from app.utils.sanitize import validate_name, sanitize_name, validate_float
from app.utils.time_utils import (
    now_iso, now, start_of_day, end_of_day,
    start_of_month, end_of_month, parse_iso,
)


class QuestScreen(BaseScreen):
    """Quest list and management with active/completed tabs.

    The list is structured hierarchically:
    - Overquests are shown as foldable top-level entries (▶/▼ prefix)
    - Subquests are nested below their overquest when unfolded
    - Standalone quests appear at top level without indent
    """

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.quests = load_quests(character.name)
        self.active_quests = load_active_quests(character.name)
        self.completed_quests = load_completed_quests(character.name)
        self.picker = None
        self.tab = "active"  # active, completed
        self.mode = "list"  # list, create, from_template
        self.message = ""
        # Folding state: set of overquest IDs that are folded (collapsed)
        self.folded: set[str] = set()
        # Flat list mapping picker index -> Quest or None (for "+ New Quest" entry)
        self._display_quests: list[Quest | None] = []
        # Template picker state (for "from template" mode)
        self._templates: list[dict] = []
        self._template_picker = None
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
        self.create_cursor = 0
        self.create_stat_cursor = 0
        self.create_recurrence_cursor = 0

    # --- Hierarchical list building ---

    def _build_active_display(self) -> tuple[list[str], list[Quest | None]]:
        """Build hierarchical display for the active tab.

        Returns (display_strings, quest_objects) where quest_objects[i]
        is the Quest for display row i, or None for action rows like "+ New Quest".
        """
        items: list[str] = []
        quests: list[Quest | None] = []
        all_quests = self.quests

        # Gather overquests (active, not completed)
        overquests = sorted(
            [q for q in all_quests if q.is_overquest and q.status != "completed"],
            key=lambda q: q.name.lower(),
        )
        # Gather standalone quests (not overquest, no overquest_id)
        standalone = sorted(
            [q for q in all_quests if not q.is_overquest and not q.overquest_id],
            key=lambda q: q.name.lower(),
        )

        # Render overquests with their subquests
        for oq in overquests:
            subs = sorted(
                get_subquests(all_quests, oq.id),
                key=lambda q: q.name.lower(),
            )
            done = sum(1 for s in subs if s.status == "completed")
            is_folded = oq.id in self.folded
            fold_icon = "▶" if is_folded else "▼"
            items.append(f"{fold_icon} {oq.name} [{done}/{len(subs)}]")
            quests.append(oq)

            if not is_folded:
                for sq in subs:
                    if sq.status == "completed" and sq.recurrence == "none":
                        continue  # Skip completed one-time subquests in active tab
                    recur = f"({sq.recurrence})" if sq.recurrence != "none" else ""
                    status = self._status_icon(sq)
                    items.append(f"    {status} {sq.name} — d:{sq.difficulty} {recur}")
                    quests.append(sq)

        # Render standalone quests
        for sq in standalone:
            recur = f"({sq.recurrence})" if sq.recurrence != "none" else ""
            status = self._status_icon(sq)
            items.append(f"{status} {sq.name} — d:{sq.difficulty} {recur}")
            quests.append(sq)

        items.append("+ New Quest")
        quests.append(None)
        items.append("+ From Template")
        quests.append(None)
        return items, quests

    def _build_completed_display(self) -> tuple[list[str], list[Quest | None]]:
        """Build hierarchical display for the completed tab.

        Shows completed overquests with their completed subquests nested,
        plus standalone completed quests.
        """
        items: list[str] = []
        quests: list[Quest | None] = []

        # Completed overquests from the main quests list
        completed_overquests = sorted(
            [q for q in self.quests if q.is_overquest and q.status == "completed"],
            key=lambda q: q.name.lower(),
        )
        # Also check the completed_quests store for overquests
        for cq in self.completed_quests:
            if cq.is_overquest and cq.id not in {oq.id for oq in completed_overquests}:
                completed_overquests.append(cq)
        completed_overquests.sort(key=lambda q: q.name.lower())

        # Gather completed subquests that belong to an overquest
        sub_ids_shown: set[str] = set()

        for oq in completed_overquests:
            # Find subquests from both quests and completed_quests
            subs = [q for q in self.quests if q.overquest_id == oq.id and q.status == "completed"]
            for cq in self.completed_quests:
                if cq.overquest_id == oq.id and cq.id not in {s.id for s in subs}:
                    subs.append(cq)
            subs.sort(key=lambda q: q.name.lower())

            is_folded = oq.id in self.folded
            fold_icon = "▶" if is_folded else "▼"
            items.append(f"{fold_icon} {oq.name} [completed]")
            quests.append(oq)

            if not is_folded:
                for sq in subs:
                    items.append(f"    ● {sq.name} — d:{sq.difficulty}")
                    quests.append(sq)
                    sub_ids_shown.add(sq.id)

        # Standalone completed quests (no overquest_id, or overquest not completed yet)
        standalone_completed = sorted(
            [q for q in self.completed_quests
             if not q.is_overquest and q.id not in sub_ids_shown
             and not q.overquest_id],
            key=lambda q: q.name.lower(),
        )
        # Also include subquests whose overquest is still active (completed individually)
        for cq in self.completed_quests:
            if cq.overquest_id and cq.id not in sub_ids_shown:
                # Check if overquest is still active (not in completed_overquests)
                if cq.overquest_id not in {oq.id for oq in completed_overquests}:
                    oq = get_quest_by_id(self.quests, cq.overquest_id)
                    if oq and oq.status != "completed":
                        standalone_completed.append(cq)
        # Deduplicate
        seen_ids: set[str] = set()
        deduped: list[Quest] = []
        for q in standalone_completed:
            if q.id not in seen_ids:
                seen_ids.add(q.id)
                deduped.append(q)
        standalone_completed = sorted(deduped, key=lambda q: q.name.lower())

        for sq in standalone_completed:
            recur = f"({sq.recurrence})" if sq.recurrence != "none" else ""
            items.append(f"● {sq.name} — d:{sq.difficulty} {recur}")
            quests.append(sq)

        if not items:
            items.append("(no completed quests)")
            quests.append(None)

        return items, quests

    def _status_icon(self, quest: Quest) -> str:
        """Return a status icon for a quest."""
        if quest.paused:
            return "◫"
        if quest.id in self.active_quests:
            return "◐"
        if quest.status == "completed":
            return "●"
        return "○"

    def _deps_satisfied(self, quest: Quest) -> bool:
        """Check if all predecessors (quests that point to this one) are completed.

        A quest can only be started if every quest that has it in its
        next_quests list is already completed.
        """
        if not quest.overquest_id:
            return True  # Standalone quests have no network dependencies
        predecessors = get_predecessors(self.quests, quest.id)
        # Only consider predecessors within the same overquest
        for pred in predecessors:
            if pred.overquest_id == quest.overquest_id:
                if pred.status != "completed":
                    return False
        return True

    # --- Render ---

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.cyan +
              f"{self.character.name} — Quests" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 50 + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 3) + t.yellow + self.message + t.normal, end="")

        # Tab indicator
        if self.tab == "active":
            print(t.move_xy(2, 4) + t.bold + "[A]ctive" + t.normal +
                  "  " + t.dim + "[C]ompleted" + t.normal, end="")
        else:
            print(t.move_xy(2, 4) + t.dim + "[A]ctive" + t.normal +
                  "  " + t.bold + "[C]ompleted" + t.normal, end="")

        if self.mode == "list":
            self._render_list()
        elif self.mode == "create":
            self._render_create()
        elif self.mode == "from_template":
            self._render_template_picker()

        if self.mode == "list":
            if self.tab == "active":
                controls = "n:new s:start c:complete p:pause d:delete f:fold Tab:tabs Esc:back"
            else:
                controls = "d:delete  f:fold  Tab:switch tabs  Esc:back  ?:help"
            print(t.move_xy(2, t.height - 1) + t.dim + controls + t.normal, end="")
        elif self.mode == "from_template":
            print(t.move_xy(2, t.height - 1) + t.dim +
                  "Enter:create from template  Esc:cancel" + t.normal, end="")
        else:
            print(t.move_xy(2, t.height - 1) + t.dim +
                  "Tab:next field  Shift-Tab:prev  Enter:submit  Esc:cancel" + t.normal, end="")

    def _render_list(self):
        t = self.term
        if self.tab == "active":
            items, self._display_quests = self._build_active_display()
        else:
            items, self._display_quests = self._build_completed_display()

        if self.picker is None:
            prompt = "Active Quests:" if self.tab == "active" else "Completed Quests:"
            self.picker = InlinePicker(items, t, prompt=prompt, x=2, y=6)
        else:
            self.picker.items = items
            self.picker.filtered_indices = list(range(len(items)))
            # Clamp cursor if list shrank
            if self.picker.cursor >= len(items):
                self.picker.cursor = max(0, len(items) - 1)
        self.picker.render()

        # Color indicators for active tab
        if self.tab == "active":
            self._render_status_colors()

    def _render_status_colors(self):
        """Render color indicators next to quest entries in active tab."""
        t = self.term
        if not self.picker:
            return
        visible_start = self.picker.scroll_offset
        visible_end = min(
            visible_start + self.picker.max_visible,
            len(self.picker.filtered_indices),
        )
        list_start_y = 6 + 2  # prompt line + search line

        for i in range(visible_start, visible_end):
            if i >= len(self.picker.filtered_indices):
                break
            idx = self.picker.filtered_indices[i]
            if idx >= len(self._display_quests):
                break
            quest = self._display_quests[idx]
            if quest is None:
                continue
            line_y = list_start_y + (i - visible_start)
            indicator_x = 60
            if quest.is_overquest:
                # Show overquest status
                if quest.status == "completed":
                    print(t.move_xy(indicator_x, line_y) + t.green + "★ DONE" + t.normal, end="")
            else:
                if quest.paused:
                    print(t.move_xy(indicator_x, line_y) + t.red + "■ PAUSED" + t.normal, end="")
                elif quest.id in self.active_quests:
                    print(t.move_xy(indicator_x, line_y) + t.green + "■ STARTED" + t.normal, end="")
                elif not self._deps_satisfied(quest):
                    print(t.move_xy(indicator_x, line_y) + t.dim + "⊘ LOCKED" + t.normal, end="")

    def _render_create(self):
        """Render condensed single-form quest creation."""
        t = self.term
        y = 6
        print(t.move_xy(2, y) + t.bold + "New Quest" + t.normal +
              t.dim + " (Tab: next, Enter: submit)" + t.normal, end="")
        y += 1
        current_y = y

        for i, field in enumerate(self.create_field_order):
            is_active = (i == self.create_cursor)
            prefix = t.cyan + "▸ " + t.normal if is_active else "  "

            if field == "name":
                val = self.create_fields["name"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) +
                      f"{prefix}Name: {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1
            elif field == "difficulty":
                val = self.create_fields["difficulty"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) +
                      f"{prefix}Difficulty (0-5): {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1
            elif field == "recurrence":
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
                display = (", ".join(s.upper() for s in selected)
                           if selected else t.dim + "(none)" + t.normal)
                print(t.move_xy(2, current_y) +
                      f"{prefix}Stats: {display}" + t.clear_eol, end="")
                current_y += 1
                if is_active:
                    for j, stat in enumerate(CS_STATS):
                        mark = (t.green + "[x]" + t.normal
                                if self.create_stat_toggles[j] else "[ ]")
                        sp = (t.cyan + "> " + t.normal
                              if j == self.create_stat_cursor else "  ")
                        print(t.move_xy(6, current_y) +
                              f"{sp}{mark} {stat.upper()}" + t.clear_eol, end="")
                        current_y += 1
            elif field == "description":
                val = self.create_fields["description"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) +
                      f"{prefix}Desc: {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1

    # --- Key handling ---

    def on_key(self, key):
        self.message = ""
        if self.mode == "list":
            self._handle_list_key(key)
        elif self.mode == "create":
            self._handle_create_key(key)
        elif self.mode == "from_template":
            self._handle_template_key(key)

    def _handle_list_key(self, key):
        t = self.term

        if key == "q":
            self.manager.running = False
            return

        # Tab switching
        if key == "\t":
            self.tab = "completed" if self.tab == "active" else "active"
            self.picker = None
            return

        # Fold/unfold toggle
        if key == "f" or key == " ":
            self._toggle_fold()
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
                elif result == "+ From Template":
                    self._start_from_template()

    def _toggle_fold(self):
        """Toggle fold state of the currently selected overquest."""
        quest = self._get_selected_quest()
        if not quest:
            return
        # If it's an overquest, fold/unfold it
        if quest.is_overquest:
            if quest.id in self.folded:
                self.folded.discard(quest.id)
            else:
                self.folded.add(quest.id)
            self.picker = None  # Force rebuild
            return
        # If it's a subquest, fold/unfold its parent overquest
        if quest.overquest_id:
            if quest.overquest_id in self.folded:
                self.folded.discard(quest.overquest_id)
            else:
                self.folded.add(quest.overquest_id)
            self.picker = None

    def _start_create(self):
        self.mode = "create"
        self._reset_create_form()

    def _handle_create_key(self, key):
        t = self.term
        current_field = self.create_field_order[self.create_cursor]

        if key.code == t.KEY_ESCAPE:
            self.mode = "list"
            self.picker = None
            return

        if key.code == t.KEY_ENTER:
            self._finalize_create()
            return

        if key == "\t":
            self.create_cursor = min(self.create_cursor + 1, len(self.create_field_order) - 1)
            return

        if key.code == t.KEY_BTAB:
            self.create_cursor = max(self.create_cursor - 1, 0)
            return

        if current_field in ("name", "difficulty", "description"):
            if key.code == t.KEY_BACKSPACE or key == "\x7f":
                self.create_fields[current_field] = self.create_fields[current_field][:-1]
            elif not key.is_sequence and key.isprintable():
                self.create_fields[current_field] += str(key)
        elif current_field == "recurrence":
            if key == "j" or key.code == t.KEY_DOWN or key == "l" or key.code == t.KEY_RIGHT:
                idx = QUEST_RECURRENCE.index(self.create_fields["recurrence"])
                idx = (idx + 1) % len(QUEST_RECURRENCE)
                self.create_fields["recurrence"] = QUEST_RECURRENCE[idx]
            elif key == "k" or key.code == t.KEY_UP or key == "h" or key.code == t.KEY_LEFT:
                idx = QUEST_RECURRENCE.index(self.create_fields["recurrence"])
                idx = (idx - 1) % len(QUEST_RECURRENCE)
                self.create_fields["recurrence"] = QUEST_RECURRENCE[idx]
            elif key == " ":
                idx = QUEST_RECURRENCE.index(self.create_fields["recurrence"])
                idx = (idx + 1) % len(QUEST_RECURRENCE)
                self.create_fields["recurrence"] = QUEST_RECURRENCE[idx]
        elif current_field == "stats":
            if key == "j" or key.code == t.KEY_DOWN:
                self.create_stat_cursor = min(self.create_stat_cursor + 1, len(CS_STATS) - 1)
            elif key == "k" or key.code == t.KEY_UP:
                self.create_stat_cursor = max(self.create_stat_cursor - 1, 0)
            elif key == " ":
                self.create_stat_toggles[self.create_stat_cursor] = (
                    not self.create_stat_toggles[self.create_stat_cursor]
                )

    def _finalize_create(self):
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
        """Get the quest at the current picker cursor position."""
        if not self.picker or not self.picker.filtered_indices:
            return None
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(self._display_quests):
            return None
        return self._display_quests[idx]

    def _start_selected_quest(self):
        quest = self._get_selected_quest()
        if not quest:
            return
        if quest.is_overquest:
            # Proxy: start the first available (deps satisfied, not started, not paused) subquest
            subs = sorted(
                [q for q in self.quests if q.overquest_id == quest.id],
                key=lambda q: q.name.lower(),
            )
            target = None
            for sq in subs:
                if sq.status == "completed":
                    continue
                if sq.paused:
                    continue
                if sq.id in self.active_quests:
                    continue
                if self._deps_satisfied(sq):
                    target = sq
                    break
            if not target:
                self.message = "No available subquest to start (all started, completed, or locked)."
                return
            quest = target
        if quest.paused:
            self.message = "Cannot start a paused quest. Unpause first (press 'p')."
            return
        if quest.id in self.active_quests:
            self.message = "Quest already started."
            return
        # Dependency check: all predecessors must be completed
        if not self._deps_satisfied(quest):
            self.message = "Cannot start: prerequisite quests not yet completed."
            return
        started_at = start_quest(quest)
        self.active_quests[quest.id] = started_at
        save_active_quests(self.character.name, self.active_quests)
        save_quests(self.character.name, self.quests)
        self.message = f"Quest '{quest.name}' started!"
        self.picker = None

    def _complete_selected_quest(self):
        quest = self._get_selected_quest()
        if not quest:
            return
        if quest.is_overquest:
            self.message = "Overquests complete automatically when all subquests are done."
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

        # Check if this completion triggers an overquest completion
        # (must check BEFORE removing quest from self.quests)
        overquest_completed = False
        if quest.overquest_id:
            overquest = get_quest_by_id(self.quests, quest.overquest_id)
            if overquest and check_overquest_completion(self.quests, overquest):
                overquest_completed = True

        # Move non-recurring quests to completed list
        if quest.recurrence == "none":
            self.quests.remove(quest)
            quest.active = False
            self.completed_quests.append(quest)
            save_completed_quests(self.character.name, self.completed_quests)

        save_quests(self.character.name, self.quests)

        # Handle overquest completion (move entire quest line to completed)
        if overquest_completed:
            oq_log, oq_item = complete_overquest(
                self.quests, overquest, self.character
            )
            save_character(self.character)
            append_quest_log(self.character.name, oq_log)

            # Move overquest and all its subquests to completed list
            subs_to_move = [q for q in self.quests if q.overquest_id == overquest.id]
            for sq in subs_to_move:
                sq.active = False
                if sq not in self.completed_quests:
                    self.completed_quests.append(sq)
                if sq in self.quests:
                    self.quests.remove(sq)
            overquest.active = False
            if overquest in self.quests:
                self.quests.remove(overquest)
            self.completed_quests.append(overquest)
            save_completed_quests(self.character.name, self.completed_quests)
            save_quests(self.character.name, self.quests)

            msg += (f"\n  ★ Quest line '{overquest.name}' COMPLETED!"
                    f" +{oq_log.xp_granted:.0f} XP")
            if oq_item:
                inventory = load_inventory(self.character.name)
                inventory.append(oq_item)
                save_inventory(self.character.name, inventory)
                msg += f" | Item: {oq_item.name} ({oq_item.rarity})"

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
        if quest.is_overquest:
            # Proxy: pause/unpause the first active (started) subquest
            subs = sorted(
                [q for q in self.quests if q.overquest_id == quest.id],
                key=lambda q: q.name.lower(),
            )
            # Find first started subquest to pause, or first paused to unpause
            started = [sq for sq in subs if sq.id in self.active_quests and not sq.paused]
            paused = [sq for sq in subs if sq.paused]
            if started:
                quest = started[0]
            elif paused:
                quest = paused[0]
            else:
                self.message = "No subquest to pause/unpause."
                return
        if not quest.can_pause():
            self.message = "Recurring quests cannot be paused."
            return

        quest.paused = not quest.paused
        if quest.paused:
            quest.status = "paused"
            if quest.id in self.active_quests:
                del self.active_quests[quest.id]
                save_active_quests(self.character.name, self.active_quests)
        else:
            quest.status = "new"

        save_quests(self.character.name, self.quests)
        status = "paused" if quest.paused else "unpaused"
        self.message = f"Quest '{quest.name}' {status}."
        self.picker = None

    def _delete_selected_quest(self):
        quest = self._get_selected_quest()
        if not quest:
            return
        if quest.is_overquest:
            # Delete overquest and all its subquests
            sub_ids = {q.id for q in self.quests if q.overquest_id == quest.id}
            self.quests = [q for q in self.quests if q.id != quest.id and q.id not in sub_ids]
            for sid in sub_ids:
                self.active_quests.pop(sid, None)
            self.active_quests.pop(quest.id, None)
            save_quests(self.character.name, self.quests)
            save_active_quests(self.character.name, self.active_quests)
            self.message = f"Quest line '{quest.name}' and its subquests deleted."
            self.picker = None
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
        quest = self._get_selected_quest()
        if not quest:
            return
        if quest.is_overquest:
            # Delete overquest and all its subquests from completed list
            sub_ids = {q.id for q in self.completed_quests if q.overquest_id == quest.id}
            self.completed_quests = [
                q for q in self.completed_quests if q.id != quest.id and q.id not in sub_ids
            ]
            save_completed_quests(self.character.name, self.completed_quests)
            self.message = f"Quest line '{quest.name}' removed from completed list."
            self.picker = None
            return
        if quest in self.completed_quests:
            self.completed_quests.remove(quest)
            save_completed_quests(self.character.name, self.completed_quests)
            self.message = f"Removed '{quest.name}' from completed list."
            self.picker = None

    # --- From Template mode ---

    def _start_from_template(self):
        """Switch to template picker mode."""
        self._templates = load_quest_templates(self.character.name)
        if not self._templates:
            self.message = "No templates available. Add some in the Quest Editor."
            return
        self._template_picker = None
        self.mode = "from_template"

    def _render_template_picker(self):
        """Render the template selection list."""
        t = self.term
        items = [f"{tmpl['name']} ({len(tmpl.get('quests', []))} quests)"
                 for tmpl in self._templates]
        if self._template_picker is None:
            self._template_picker = InlinePicker(
                items, t, prompt="Create from template:", x=2, y=6
            )
        else:
            self._template_picker.items = items
            self._template_picker.filtered_indices = list(range(len(items)))
        self._template_picker.render()

    def _handle_template_key(self, key):
        """Handle keys in from_template mode."""
        t = self.term
        if key.code == t.KEY_ESCAPE:
            self.mode = "list"
            self.picker = None
            self._template_picker = None
            return
        if key == "q":
            self.manager.running = False
            return
        if self._template_picker:
            result, active = self._template_picker.on_key(key)
            if not active and result:
                idx = self._template_picker.filtered_indices[self._template_picker.cursor]
                if idx < len(self._templates):
                    self._instantiate_template(self._templates[idx])

    def _instantiate_template(self, template: dict):
        """Create real quests from a template and add them to the quest list."""
        oq_data = template.get("overquest", {})

        overquest = Quest(
            id=str(uuid.uuid4()),
            name=oq_data.get("name", template["name"]),
            description=oq_data.get("description", ""),
            difficulty=oq_data.get("difficulty", 1.0),
            stats=oq_data.get("stats", []),
            recurrence="none",
            created_at=now_iso(),
            active=True,
            is_overquest=True,
            status="new",
        )
        self.quests.append(overquest)

        # Map template refs to real IDs
        ref_to_id: dict[str, str] = {}
        quest_objects: list[Quest] = []

        for sq_data in template.get("quests", []):
            sq_id = str(uuid.uuid4())
            ref_to_id[sq_data.get("ref", "")] = sq_id
            sq = Quest(
                id=sq_id,
                name=sq_data["name"],
                description=sq_data.get("description", ""),
                difficulty=sq_data.get("difficulty", 1.0),
                stats=sq_data.get("stats", []),
                recurrence=sq_data.get("recurrence", "none"),
                created_at=now_iso(),
                active=True,
                is_overquest=False,
                overquest_id=overquest.id,
                next_quests=[],
                status="new",
            )
            quest_objects.append(sq)

        # Resolve next_quests refs to real IDs
        for i, sq_data in enumerate(template.get("quests", [])):
            quest_objects[i].next_quests = [
                ref_to_id[ref] for ref in sq_data.get("next_quests", [])
                if ref in ref_to_id
            ]

        self.quests.extend(quest_objects)
        save_quests(self.character.name, self.quests)

        n = len(quest_objects)
        self.message = f"Quest line '{overquest.name}' created from template! ({n} quests)"
        self.mode = "list"
        self.picker = None
        self._template_picker = None
