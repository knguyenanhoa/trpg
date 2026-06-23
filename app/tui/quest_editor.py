"""Quest Editor screen — create overquests, manage subquests, edit dependencies, use templates."""

import uuid

from app.tui.base_screen import BaseScreen
from app.tui.fzf_picker import InlinePicker
from app.models.character import Character
from app.models.quest import Quest
from app.config import CS_STATS, DIFFICULTY_MIN, DIFFICULTY_MAX
from app.db.file_store import (
    load_quests, save_quests, load_premade_quest_templates,
)
from app.engine.quest_engine import (
    get_subquests, get_quest_by_id, delete_quest_from_network,
    delete_overquest, insert_quest_in_network, validate_overquest,
)
from app.utils.sanitize import validate_name, sanitize_name, validate_float
from app.utils.time_utils import now_iso


class QuestEditorScreen(BaseScreen):
    """Quest editor for managing overquests and quest networks.

    Modes:
    - list: browse overquests
    - view: view subquests of selected overquest
    - create_overquest: form to create a new overquest
    - add_subquest: form to add a subquest to the current overquest
    - edit_deps: edit next_quests dependencies for a subquest
    - templates: pick from premade quest tree templates
    """

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.quests = load_quests(character.name)
        self.picker = None
        self.mode = "list"
        self.message = ""
        # State for viewing an overquest's subquests
        self.current_overquest: Quest | None = None
        self.sub_picker = None
        # Create form state
        self._reset_overquest_form()
        self._reset_subquest_form()
        # Template state
        self.templates = []
        self.template_picker = None
        # Edit deps state
        self.dep_quest: Quest | None = None
        self.dep_picker = None
        self.dep_toggles: list[bool] = []
        self.dep_candidates: list[Quest] = []

    # --- Form reset helpers ---

    def _reset_overquest_form(self):
        self.oq_fields = {"name": "", "description": "", "difficulty": "2.0"}
        self.oq_stat_toggles = [False] * len(CS_STATS)
        self.oq_field_order = ["name", "difficulty", "stats", "description"]
        self.oq_cursor = 0
        self.oq_stat_cursor = 0

    def _reset_subquest_form(self):
        self.sq_fields = {"name": "", "description": "", "difficulty": "1.0"}
        self.sq_stat_toggles = [False] * len(CS_STATS)
        self.sq_field_order = ["name", "difficulty", "stats", "description"]
        self.sq_cursor = 0
        self.sq_stat_cursor = 0

    # --- Overquest list helpers ---

    def _overquests(self) -> list[Quest]:
        """Get all overquests sorted alphabetically."""
        return sorted(
            [q for q in self.quests if q.is_overquest],
            key=lambda q: q.name.lower()
        )

    def _overquest_display(self) -> list[str]:
        items = []
        for oq in self._overquests():
            subs = get_subquests(self.quests, oq.id)
            done = sum(1 for s in subs if s.status == "completed")
            items.append(f"{oq.name} [{done}/{len(subs)}]")
        items.append("+ New Overquest")
        items.append("+ From Template")
        return items

    def _subquest_display(self) -> list[str]:
        """Display subquests of the current overquest."""
        if not self.current_overquest:
            return []
        subs = get_subquests(self.quests, self.current_overquest.id)
        subs_sorted = sorted(subs, key=lambda q: q.name.lower())
        items = []
        for sq in subs_sorted:
            next_names = []
            for nid in sq.next_quests:
                nq = get_quest_by_id(self.quests, nid)
                if nq:
                    next_names.append(nq.name)
            dep_str = f" -> {', '.join(next_names)}" if next_names else ""
            status_char = {"new": "○", "in-progress": "◐", "completed": "●", "paused": "◫"}.get(sq.status, "○")
            items.append(f"{status_char} {sq.name} (d:{sq.difficulty}){dep_str}")
        items.append("+ Add Subquest")
        return items

    # --- Render ---

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.magenta + "Quest Editor" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 50 + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 3) + t.yellow + self.message + t.normal, end="")

        if self.mode == "list":
            self._render_list()
        elif self.mode == "view":
            self._render_view()
        elif self.mode == "create_overquest":
            self._render_create_form("New Overquest", self.oq_fields, self.oq_field_order,
                                     self.oq_cursor, self.oq_stat_toggles, self.oq_stat_cursor)
        elif self.mode == "add_subquest":
            self._render_create_form("New Subquest", self.sq_fields, self.sq_field_order,
                                     self.sq_cursor, self.sq_stat_toggles, self.sq_stat_cursor)
        elif self.mode == "edit_deps":
            self._render_edit_deps()
        elif self.mode == "templates":
            self._render_templates()

        # Controls bar
        controls = self._get_controls()
        print(t.move_xy(2, t.height - 1) + t.dim + controls + t.normal, end="")

    def _get_controls(self) -> str:
        if self.mode == "list":
            return "n:new  t:template  d:delete  Enter:view  Esc:back  ?:help"
        elif self.mode == "view":
            return "a:add subquest  e:edit deps  d:delete  Esc:back"
        elif self.mode in ("create_overquest", "add_subquest"):
            return "Tab:next field  Shift-Tab:prev  Enter:submit  Esc:cancel"
        elif self.mode == "edit_deps":
            return "j/k:navigate  Space:toggle  Enter:save  Esc:cancel"
        elif self.mode == "templates":
            return "Enter:select  Esc:cancel"
        return ""

    def _render_list(self):
        t = self.term
        items = self._overquest_display()
        if self.picker is None:
            self.picker = InlinePicker(items, t, prompt="Quest Lines:", x=2, y=5)
        else:
            self.picker.items = items
            self.picker.filtered_indices = list(range(len(items)))
        self.picker.render()

    def _render_view(self):
        t = self.term
        if not self.current_overquest:
            return
        oq = self.current_overquest
        print(t.move_xy(2, 5) + t.bold + t.cyan + oq.name + t.normal +
              t.dim + f" (d:{oq.difficulty}, stats:{','.join(s.upper() for s in oq.stats)})" + t.normal, end="")
        if oq.description:
            print(t.move_xy(2, 6) + t.dim + oq.description[:60] + t.normal, end="")

        items = self._subquest_display()
        start_y = 8
        if self.sub_picker is None:
            self.sub_picker = InlinePicker(items, t, prompt="Subquests:", x=2, y=start_y)
        else:
            self.sub_picker.items = items
            self.sub_picker.filtered_indices = list(range(len(items)))
        self.sub_picker.render()

    def _render_create_form(self, title, fields, field_order, cursor, stat_toggles, stat_cursor):
        """Render a condensed quest creation form (reused for overquest and subquest)."""
        t = self.term
        y = 5
        print(t.move_xy(2, y) + t.bold + title + t.normal + t.dim + " (Tab: next, Enter: submit)" + t.normal, end="")
        y += 1
        current_y = y

        for i, field in enumerate(field_order):
            is_active = (i == cursor)
            prefix = t.cyan + "▸ " + t.normal if is_active else "  "

            if field == "name":
                val = fields["name"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Name: {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1
            elif field == "difficulty":
                val = fields["difficulty"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Difficulty (0-5): {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1
            elif field == "stats":
                selected = [CS_STATS[j] for j, v in enumerate(stat_toggles) if v]
                display = ", ".join(s.upper() for s in selected) if selected else t.dim + "(none)" + t.normal
                print(t.move_xy(2, current_y) + f"{prefix}Stats: {display}" + t.clear_eol, end="")
                current_y += 1
                if is_active:
                    for j, stat in enumerate(CS_STATS):
                        mark = t.green + "[x]" + t.normal if stat_toggles[j] else "[ ]"
                        sp = t.cyan + "> " + t.normal if j == stat_cursor else "  "
                        print(t.move_xy(6, current_y) + f"{sp}{mark} {stat.upper()}" + t.clear_eol, end="")
                        current_y += 1
            elif field == "description":
                val = fields["description"]
                cursor_char = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Desc: {val}{cursor_char}" + t.clear_eol, end="")
                current_y += 1

    def _render_edit_deps(self):
        """Render dependency editor: toggle which quests come after the selected subquest."""
        t = self.term
        if not self.dep_quest:
            return
        print(t.move_xy(2, 5) + t.bold + f"Edit dependencies for: {self.dep_quest.name}" + t.normal, end="")
        print(t.move_xy(2, 6) + t.dim + "Toggle which quests come AFTER this one:" + t.normal, end="")

        start_y = 8
        if self.dep_picker is None:
            items = [f"{'[x]' if self.dep_toggles[i] else '[ ]'} {c.name}"
                     for i, c in enumerate(self.dep_candidates)]
            self.dep_picker = InlinePicker(items, t, prompt="Next quests:", x=2, y=start_y)
        else:
            items = [f"{'[x]' if self.dep_toggles[i] else '[ ]'} {c.name}"
                     for i, c in enumerate(self.dep_candidates)]
            self.dep_picker.items = items
            self.dep_picker.filtered_indices = list(range(len(items)))
        self.dep_picker.render()

    def _render_templates(self):
        """Render premade template selection."""
        t = self.term
        if not self.templates:
            self.templates = load_premade_quest_templates()
        items = [f"{tmpl['name']} — {tmpl['description']}" for tmpl in self.templates]
        if not items:
            print(t.move_xy(2, 5) + t.dim + "(no templates available)" + t.normal, end="")
            return
        if self.template_picker is None:
            self.template_picker = InlinePicker(items, t, prompt="Select a template:", x=2, y=5)
        else:
            self.template_picker.items = items
            self.template_picker.filtered_indices = list(range(len(items)))
        self.template_picker.render()

    # --- Key handling ---

    def on_key(self, key):
        self.message = ""
        if self.mode == "list":
            self._handle_list_key(key)
        elif self.mode == "view":
            self._handle_view_key(key)
        elif self.mode == "create_overquest":
            self._handle_form_key(key, self.oq_fields, self.oq_field_order,
                                  "oq_cursor", "oq_stat_toggles", "oq_stat_cursor",
                                  self._finalize_overquest)
        elif self.mode == "add_subquest":
            self._handle_form_key(key, self.sq_fields, self.sq_field_order,
                                  "sq_cursor", "sq_stat_toggles", "sq_stat_cursor",
                                  self._finalize_subquest)
        elif self.mode == "edit_deps":
            self._handle_edit_deps_key(key)
        elif self.mode == "templates":
            self._handle_template_key(key)

    def _handle_list_key(self, key):
        t = self.term
        if key == "q":
            self.manager.running = False
            return
        if key.code == t.KEY_ESCAPE or key == "h":
            self.manager.pop()
            return
        if key == "n":
            self.mode = "create_overquest"
            self._reset_overquest_form()
            return
        if key == "t":
            self.mode = "templates"
            self.templates = load_premade_quest_templates()
            self.template_picker = None
            return
        if key == "d":
            self._delete_selected_overquest()
            return

        if self.picker:
            result, active = self.picker.on_key(key)
            if not active and result:
                if result == "+ New Overquest":
                    self.mode = "create_overquest"
                    self._reset_overquest_form()
                elif result == "+ From Template":
                    self.mode = "templates"
                    self.templates = load_premade_quest_templates()
                    self.template_picker = None
                else:
                    # View the selected overquest
                    overquests = self._overquests()
                    idx = self.picker.filtered_indices[self.picker.cursor]
                    if idx < len(overquests):
                        self.current_overquest = overquests[idx]
                        self.mode = "view"
                        self.sub_picker = None

    def _handle_view_key(self, key):
        t = self.term
        if key.code == t.KEY_ESCAPE or key == "h":
            self.mode = "list"
            self.picker = None
            self.current_overquest = None
            return
        if key == "q":
            self.manager.running = False
            return
        if key == "a":
            self.mode = "add_subquest"
            self._reset_subquest_form()
            return
        if key == "e":
            self._start_edit_deps()
            return
        if key == "d":
            self._delete_selected_subquest()
            return

        if self.sub_picker:
            result, active = self.sub_picker.on_key(key)
            if not active and result:
                if result == "+ Add Subquest":
                    self.mode = "add_subquest"
                    self._reset_subquest_form()

    def _handle_form_key(self, key, fields, field_order, cursor_attr, toggles_attr, stat_cursor_attr, finalize_fn):
        """Generic form key handler for overquest/subquest creation forms."""
        t = self.term
        cursor = getattr(self, cursor_attr)
        stat_toggles = getattr(self, toggles_attr)
        stat_cursor = getattr(self, stat_cursor_attr)
        current_field = field_order[cursor]

        if key.code == t.KEY_ESCAPE:
            self.mode = "view" if self.current_overquest else "list"
            self.picker = None
            self.sub_picker = None
            return

        if key.code == t.KEY_ENTER:
            finalize_fn()
            return

        if key == "\t":
            setattr(self, cursor_attr, min(cursor + 1, len(field_order) - 1))
            return
        if key.code == t.KEY_BTAB:
            setattr(self, cursor_attr, max(cursor - 1, 0))
            return

        if current_field in ("name", "difficulty", "description"):
            if key.code == t.KEY_BACKSPACE or key == "\x7f":
                fields[current_field] = fields[current_field][:-1]
            elif not key.is_sequence and key.isprintable():
                fields[current_field] += str(key)
        elif current_field == "stats":
            if key == "j" or key.code == t.KEY_DOWN:
                setattr(self, stat_cursor_attr, min(stat_cursor + 1, len(CS_STATS) - 1))
            elif key == "k" or key.code == t.KEY_UP:
                setattr(self, stat_cursor_attr, max(stat_cursor - 1, 0))
            elif key == " ":
                stat_toggles[getattr(self, stat_cursor_attr)] = not stat_toggles[getattr(self, stat_cursor_attr)]

    def _handle_edit_deps_key(self, key):
        t = self.term
        if key.code == t.KEY_ESCAPE:
            self.mode = "view"
            self.dep_quest = None
            self.dep_picker = None
            self.sub_picker = None
            return
        if key.code == t.KEY_ENTER:
            self._save_deps()
            return
        if key == " ":
            # Toggle the current dep
            if self.dep_picker and self.dep_picker.filtered_indices:
                idx = self.dep_picker.filtered_indices[self.dep_picker.cursor]
                if idx < len(self.dep_toggles):
                    self.dep_toggles[idx] = not self.dep_toggles[idx]
                    self.dep_picker = None  # force re-render
            return

        if self.dep_picker:
            self.dep_picker.on_key(key)

    def _handle_template_key(self, key):
        t = self.term
        if key.code == t.KEY_ESCAPE:
            self.mode = "list"
            self.picker = None
            self.template_picker = None
            return
        if self.template_picker:
            result, active = self.template_picker.on_key(key)
            if not active and result:
                # Find the selected template
                idx = self.template_picker.filtered_indices[self.template_picker.cursor]
                if idx < len(self.templates):
                    self._apply_template(self.templates[idx])

    # --- Actions ---

    def _finalize_overquest(self):
        name = sanitize_name(self.oq_fields["name"])
        valid, err = validate_name(name)
        if not valid:
            self.message = err or "Name is required."
            return
        valid, difficulty, err = validate_float(self.oq_fields["difficulty"], DIFFICULTY_MIN, DIFFICULTY_MAX)
        if not valid:
            self.message = f"Difficulty: {err}"
            return
        stats = [CS_STATS[i] for i, v in enumerate(self.oq_stat_toggles) if v]
        if not stats:
            self.message = "Select at least one stat."
            return

        overquest = Quest(
            id=str(uuid.uuid4()),
            name=name,
            description=self.oq_fields["description"],
            difficulty=difficulty,
            stats=stats,
            recurrence="none",
            created_at=now_iso(),
            active=True,
            is_overquest=True,
            status="new",
        )
        self.quests.append(overquest)
        save_quests(self.character.name, self.quests)
        self.message = f"Overquest '{overquest.name}' created! Add subquests to it."
        self.current_overquest = overquest
        self.mode = "view"
        self.picker = None
        self.sub_picker = None

    def _finalize_subquest(self):
        if not self.current_overquest:
            self.message = "No overquest selected."
            self.mode = "list"
            return

        name = sanitize_name(self.sq_fields["name"])
        valid, err = validate_name(name)
        if not valid:
            self.message = err or "Name is required."
            return
        valid, difficulty, err = validate_float(self.sq_fields["difficulty"], DIFFICULTY_MIN, DIFFICULTY_MAX)
        if not valid:
            self.message = f"Difficulty: {err}"
            return
        stats = [CS_STATS[i] for i, v in enumerate(self.sq_stat_toggles) if v]
        if not stats:
            self.message = "Select at least one stat."
            return

        subquest = Quest(
            id=str(uuid.uuid4()),
            name=name,
            description=self.sq_fields["description"],
            difficulty=difficulty,
            stats=stats,
            recurrence="none",
            created_at=now_iso(),
            active=True,
            is_overquest=False,
            overquest_id=self.current_overquest.id,
            status="new",
        )
        self.quests.append(subquest)
        save_quests(self.character.name, self.quests)
        self.message = f"Subquest '{subquest.name}' added."
        self.mode = "view"
        self.sub_picker = None

    def _start_edit_deps(self):
        """Start editing next_quests for the selected subquest."""
        if not self.sub_picker or not self.current_overquest:
            return
        idx = self.sub_picker.filtered_indices[self.sub_picker.cursor]
        subs = sorted(
            get_subquests(self.quests, self.current_overquest.id),
            key=lambda q: q.name.lower()
        )
        if idx >= len(subs):
            return
        self.dep_quest = subs[idx]
        # Candidates: all other subquests in the same overquest
        self.dep_candidates = [s for s in subs if s.id != self.dep_quest.id]
        self.dep_toggles = [
            c.id in self.dep_quest.next_quests for c in self.dep_candidates
        ]
        self.dep_picker = None
        self.mode = "edit_deps"

    def _save_deps(self):
        """Save edited dependencies."""
        if not self.dep_quest:
            return
        new_next = [
            self.dep_candidates[i].id
            for i, toggled in enumerate(self.dep_toggles) if toggled
        ]
        self.dep_quest.next_quests = new_next
        save_quests(self.character.name, self.quests)
        self.message = f"Dependencies updated for '{self.dep_quest.name}'."
        self.dep_quest = None
        self.dep_picker = None
        self.mode = "view"
        self.sub_picker = None

    def _delete_selected_overquest(self):
        """Delete the selected overquest and its exclusive subquests."""
        if not self.picker:
            return
        overquests = self._overquests()
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(overquests):
            return
        oq = overquests[idx]
        self.quests = delete_overquest(self.quests, oq.id)
        save_quests(self.character.name, self.quests)
        self.message = f"Overquest '{oq.name}' and its subquests deleted."
        self.picker = None

    def _delete_selected_subquest(self):
        """Delete the selected subquest from the network."""
        if not self.sub_picker or not self.current_overquest:
            return
        idx = self.sub_picker.filtered_indices[self.sub_picker.cursor]
        subs = sorted(
            get_subquests(self.quests, self.current_overquest.id),
            key=lambda q: q.name.lower()
        )
        if idx >= len(subs):
            return
        sq = subs[idx]
        self.quests = delete_quest_from_network(self.quests, sq.id)
        save_quests(self.character.name, self.quests)
        self.message = f"Subquest '{sq.name}' removed (dependencies reassigned)."
        self.sub_picker = None

    def _apply_template(self, template: dict):
        """Generate an overquest and its subquests from a premade template."""
        oq_data = template["overquest"]
        overquest = Quest(
            id=str(uuid.uuid4()),
            name=oq_data["name"],
            description=oq_data.get("description", ""),
            difficulty=oq_data["difficulty"],
            stats=oq_data["stats"],
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

        for sq_data in template["quests"]:
            sq_id = str(uuid.uuid4())
            ref_to_id[sq_data["ref"]] = sq_id
            sq = Quest(
                id=sq_id,
                name=sq_data["name"],
                description=sq_data.get("description", ""),
                difficulty=sq_data["difficulty"],
                stats=sq_data["stats"],
                recurrence=sq_data.get("recurrence", "none"),
                created_at=now_iso(),
                active=True,
                is_overquest=False,
                overquest_id=overquest.id,
                next_quests=[],  # Will resolve after all refs are mapped
                status="new",
            )
            quest_objects.append(sq)

        # Resolve next_quests refs to real IDs
        for i, sq_data in enumerate(template["quests"]):
            quest_objects[i].next_quests = [
                ref_to_id[ref] for ref in sq_data.get("next_quests", [])
                if ref in ref_to_id
            ]

        self.quests.extend(quest_objects)
        save_quests(self.character.name, self.quests)
        self.message = f"Template '{template['name']}' applied! ({len(quest_objects)} subquests created)"
        self.mode = "list"
        self.picker = None
        self.template_picker = None
