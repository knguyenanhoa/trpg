"""Quest Editor screen — manage per-character quest templates.

Templates are blueprints for quest lines. They exist independently from
active quests. Creating a quest from a template copies it into the live
quest list; subsequent edits to either don't affect the other.
"""

import uuid

from app.tui.base_screen import BaseScreen
from app.tui.fzf_picker import InlinePicker
from app.models.character import Character
from app.models.quest import Quest
from app.config import CS_STATS, DIFFICULTY_MIN, DIFFICULTY_MAX
from app.db.file_store import (
    load_quest_templates, save_quest_templates,
    load_premade_quest_templates, load_quests, save_quests,
)
from app.utils.sanitize import validate_name, sanitize_name, validate_float
from app.utils.time_utils import now_iso


class QuestEditorScreen(BaseScreen):
    """Quest template editor.

    Manages the character's template library. Templates are quest line
    blueprints (overquest + subquests with dependencies). They can be
    instantiated into real quests via the 'use' action.

    Modes:
    - list: browse templates
    - view: view subquests of selected template
    - create_template: form to create a new template (overquest header)
    - add_subquest: form to add a subquest to the current template
    - edit_deps: edit next_quests dependencies within a template
    - add_premade: pick from global premade templates to add to library
    - instantiate: create real quests from a template
    """

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.templates = load_quest_templates(character.name)
        self.picker = None
        self.mode = "list"
        self.message = ""
        # State for viewing a template's subquests
        self.current_template: dict | None = None
        self.sub_picker = None
        # Create form state
        self._reset_template_form()
        self._reset_subquest_form()
        # Premade picker state
        self.premade_list: list[dict] = []
        self.premade_picker = None
        # Edit deps state
        self.dep_index: int = -1  # index into current template's quests
        self.dep_picker = None
        self.dep_toggles: list[bool] = []

    # --- Form reset helpers ---

    def _reset_template_form(self):
        self.tpl_fields = {"name": "", "description": "", "difficulty": "2.0"}
        self.tpl_stat_toggles = [False] * len(CS_STATS)
        self.tpl_field_order = ["name", "difficulty", "stats", "description"]
        self.tpl_cursor = 0
        self.tpl_stat_cursor = 0

    def _reset_subquest_form(self):
        self.sq_fields = {"name": "", "description": "", "difficulty": "1.0"}
        self.sq_stat_toggles = [False] * len(CS_STATS)
        self.sq_field_order = ["name", "difficulty", "stats", "description"]
        self.sq_cursor = 0
        self.sq_stat_cursor = 0

    # --- Template list helpers ---

    def _template_display(self) -> list[str]:
        items = []
        for tmpl in self.templates:
            n_quests = len(tmpl.get("quests", []))
            items.append(f"{tmpl['name']} ({n_quests} quests)")
        items.append("+ New Template")
        items.append("+ Add from Premade")
        return items

    def _subquest_display(self) -> list[str]:
        """Display subquests of the current template."""
        if not self.current_template:
            return []
        quests = self.current_template.get("quests", [])
        items = []
        for sq in quests:
            next_names = []
            for nref in sq.get("next_quests", []):
                for other in quests:
                    if other.get("ref") == nref:
                        next_names.append(other["name"])
            dep_str = f" -> {', '.join(next_names)}" if next_names else ""
            items.append(f"  {sq['name']} (d:{sq['difficulty']}){dep_str}")
        items.append("+ Add Subquest")
        return items

    # --- Render ---

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.magenta +
              f"{self.character.name} — Quest Templates" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 50 + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 3) + t.yellow + self.message + t.normal, end="")

        if self.mode == "list":
            self._render_list()
        elif self.mode == "view":
            self._render_view()
        elif self.mode == "create_template":
            self._render_form("New Template", self.tpl_fields, self.tpl_field_order,
                              self.tpl_cursor, self.tpl_stat_toggles, self.tpl_stat_cursor)
        elif self.mode == "add_subquest":
            self._render_form("New Subquest", self.sq_fields, self.sq_field_order,
                              self.sq_cursor, self.sq_stat_toggles, self.sq_stat_cursor)
        elif self.mode == "edit_deps":
            self._render_edit_deps()
        elif self.mode == "add_premade":
            self._render_premade()

        controls = self._get_controls()
        print(t.move_xy(2, t.height - 1) + t.dim + controls + t.normal, end="")

    def _get_controls(self) -> str:
        if self.mode == "list":
            return "n:new  p:add premade  d:delete  u:use(instantiate)  Enter:view  Esc:back"
        elif self.mode == "view":
            return "a:add subquest  e:edit deps  d:delete subquest  Esc:back"
        elif self.mode in ("create_template", "add_subquest"):
            return "Tab:next  Shift-Tab:prev  Enter:submit  Esc:cancel"
        elif self.mode == "edit_deps":
            return "j/k:navigate  Space:toggle  Enter:save  Esc:cancel"
        elif self.mode == "add_premade":
            return "Enter:add  Esc:cancel"
        return ""

    def _render_list(self):
        t = self.term
        items = self._template_display()
        if self.picker is None:
            self.picker = InlinePicker(items, t, prompt="Templates:", x=2, y=5)
        else:
            self.picker.items = items
            self.picker.filtered_indices = list(range(len(items)))
        self.picker.render()

    def _render_view(self):
        t = self.term
        if not self.current_template:
            return
        oq = self.current_template.get("overquest", {})
        print(t.move_xy(2, 5) + t.bold + t.cyan + self.current_template["name"] + t.normal +
              t.dim + f" (d:{oq.get('difficulty', '?')}, "
              f"stats:{','.join(s.upper() for s in oq.get('stats', []))})" + t.normal, end="")
        desc = self.current_template.get("description", "")
        if desc:
            print(t.move_xy(2, 6) + t.dim + desc[:60] + t.normal, end="")

        items = self._subquest_display()
        start_y = 8
        if self.sub_picker is None:
            self.sub_picker = InlinePicker(items, t, prompt="Subquests:", x=2, y=start_y)
        else:
            self.sub_picker.items = items
            self.sub_picker.filtered_indices = list(range(len(items)))
        self.sub_picker.render()

    def _render_form(self, title, fields, field_order, cursor, stat_toggles, stat_cursor):
        """Render a condensed creation form."""
        t = self.term
        y = 5
        print(t.move_xy(2, y) + t.bold + title + t.normal +
              t.dim + " (Tab: next, Enter: submit)" + t.normal, end="")
        y += 1
        current_y = y

        for i, field in enumerate(field_order):
            is_active = (i == cursor)
            prefix = t.cyan + "▸ " + t.normal if is_active else "  "

            if field == "name":
                val = fields["name"]
                cc = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Name: {val}{cc}" + t.clear_eol, end="")
                current_y += 1
            elif field == "difficulty":
                val = fields["difficulty"]
                cc = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Difficulty (0-5): {val}{cc}" + t.clear_eol, end="")
                current_y += 1
            elif field == "stats":
                selected = [CS_STATS[j] for j, v in enumerate(stat_toggles) if v]
                display = (", ".join(s.upper() for s in selected)
                           if selected else t.dim + "(none)" + t.normal)
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
                cc = "█" if is_active else ""
                print(t.move_xy(2, current_y) + f"{prefix}Desc: {val}{cc}" + t.clear_eol, end="")
                current_y += 1

    def _render_edit_deps(self):
        """Render dependency editor for a subquest within the template."""
        t = self.term
        if not self.current_template or self.dep_index < 0:
            return
        quests = self.current_template.get("quests", [])
        sq = quests[self.dep_index]
        print(t.move_xy(2, 5) + t.bold + f"Edit deps for: {sq['name']}" + t.normal, end="")
        print(t.move_xy(2, 6) + t.dim + "Toggle which quests come AFTER this one:" + t.normal, end="")

        # Candidates: all other subquests in this template
        candidates = [q for i, q in enumerate(quests) if i != self.dep_index]
        items = [f"{'[x]' if self.dep_toggles[i] else '[ ]'} {c['name']}"
                 for i, c in enumerate(candidates)]

        start_y = 8
        if self.dep_picker is None:
            self.dep_picker = InlinePicker(items, t, prompt="Next quests:", x=2, y=start_y)
        else:
            self.dep_picker.items = items
            self.dep_picker.filtered_indices = list(range(len(items)))
        self.dep_picker.render()

    def _render_premade(self):
        """Render premade template picker."""
        t = self.term
        if not self.premade_list:
            self.premade_list = load_premade_quest_templates()
        # Filter out already-added templates
        existing_names = {tmpl["name"] for tmpl in self.templates}
        available = [p for p in self.premade_list if p["name"] not in existing_names]
        if not available:
            print(t.move_xy(2, 5) + t.dim + "(all premade templates already added)" + t.normal, end="")
            return
        items = [f"{p['name']} — {p['description']}" for p in available]
        if self.premade_picker is None:
            self.premade_picker = InlinePicker(items, t, prompt="Add premade template:", x=2, y=5)
        else:
            self.premade_picker.items = items
            self.premade_picker.filtered_indices = list(range(len(items)))
        self.premade_picker.render()

    # --- Key handling ---

    def on_key(self, key):
        self.message = ""
        if self.mode == "list":
            self._handle_list_key(key)
        elif self.mode == "view":
            self._handle_view_key(key)
        elif self.mode == "create_template":
            self._handle_form_key(key, self.tpl_fields, self.tpl_field_order,
                                  "tpl_cursor", "tpl_stat_toggles", "tpl_stat_cursor",
                                  self._finalize_template)
        elif self.mode == "add_subquest":
            self._handle_form_key(key, self.sq_fields, self.sq_field_order,
                                  "sq_cursor", "sq_stat_toggles", "sq_stat_cursor",
                                  self._finalize_subquest)
        elif self.mode == "edit_deps":
            self._handle_edit_deps_key(key)
        elif self.mode == "add_premade":
            self._handle_premade_key(key)

    def _handle_list_key(self, key):
        t = self.term
        if key == "q":
            self.manager.running = False
            return
        if key.code == t.KEY_ESCAPE or key == "h":
            self.manager.pop()
            return
        if key == "n":
            self.mode = "create_template"
            self._reset_template_form()
            return
        if key == "p":
            self.mode = "add_premade"
            self.premade_list = load_premade_quest_templates()
            self.premade_picker = None
            return
        if key == "d":
            self._delete_selected_template()
            return
        if key == "u":
            self._instantiate_selected_template()
            return

        if self.picker:
            result, active = self.picker.on_key(key)
            if not active and result:
                if result == "+ New Template":
                    self.mode = "create_template"
                    self._reset_template_form()
                elif result == "+ Add from Premade":
                    self.mode = "add_premade"
                    self.premade_list = load_premade_quest_templates()
                    self.premade_picker = None
                else:
                    # View the selected template
                    idx = self.picker.filtered_indices[self.picker.cursor]
                    if idx < len(self.templates):
                        self.current_template = self.templates[idx]
                        self.mode = "view"
                        self.sub_picker = None

    def _handle_view_key(self, key):
        t = self.term
        if key.code == t.KEY_ESCAPE or key == "h":
            self.mode = "list"
            self.picker = None
            self.current_template = None
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
        """Generic form key handler."""
        t = self.term
        cursor = getattr(self, cursor_attr)
        stat_toggles = getattr(self, toggles_attr)
        stat_cursor = getattr(self, stat_cursor_attr)
        current_field = field_order[cursor]

        if key.code == t.KEY_ESCAPE:
            self.mode = "view" if self.current_template else "list"
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
            self.dep_picker = None
            self.sub_picker = None
            return
        if key.code == t.KEY_ENTER:
            self._save_deps()
            return
        if key == " ":
            if self.dep_picker and self.dep_picker.filtered_indices:
                idx = self.dep_picker.filtered_indices[self.dep_picker.cursor]
                if idx < len(self.dep_toggles):
                    self.dep_toggles[idx] = not self.dep_toggles[idx]
                    self.dep_picker = None
            return
        if self.dep_picker:
            self.dep_picker.on_key(key)

    def _handle_premade_key(self, key):
        t = self.term
        if key.code == t.KEY_ESCAPE:
            self.mode = "list"
            self.picker = None
            self.premade_picker = None
            return
        if self.premade_picker:
            result, active = self.premade_picker.on_key(key)
            if not active and result:
                # Find which premade was selected
                existing_names = {tmpl["name"] for tmpl in self.templates}
                available = [p for p in self.premade_list if p["name"] not in existing_names]
                idx = self.premade_picker.filtered_indices[self.premade_picker.cursor]
                if idx < len(available):
                    self.templates.append(available[idx])
                    save_quest_templates(self.character.name, self.templates)
                    self.message = f"Template '{available[idx]['name']}' added to library."
                    self.mode = "list"
                    self.picker = None
                    self.premade_picker = None

    # --- Actions ---

    def _finalize_template(self):
        """Create a new empty template (overquest header only, no subquests yet)."""
        name = sanitize_name(self.tpl_fields["name"])
        valid, err = validate_name(name)
        if not valid:
            self.message = err or "Name is required."
            return
        valid, difficulty, err = validate_float(self.tpl_fields["difficulty"], DIFFICULTY_MIN, DIFFICULTY_MAX)
        if not valid:
            self.message = f"Difficulty: {err}"
            return
        stats = [CS_STATS[i] for i, v in enumerate(self.tpl_stat_toggles) if v]
        if not stats:
            self.message = "Select at least one stat."
            return

        template = {
            "name": name,
            "description": self.tpl_fields["description"],
            "overquest": {
                "name": name,
                "description": self.tpl_fields["description"],
                "difficulty": difficulty,
                "stats": stats,
            },
            "quests": [],
        }
        self.templates.append(template)
        save_quest_templates(self.character.name, self.templates)
        self.message = f"Template '{name}' created! Add subquests to it."
        self.current_template = template
        self.mode = "view"
        self.picker = None
        self.sub_picker = None

    def _finalize_subquest(self):
        """Add a subquest to the current template."""
        if not self.current_template:
            self.message = "No template selected."
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

        # Generate a unique ref for this subquest within the template
        existing_refs = {q.get("ref", "") for q in self.current_template.get("quests", [])}
        ref = sanitize_name(name).replace(" ", "_").lower()
        counter = 1
        base_ref = ref
        while ref in existing_refs:
            ref = f"{base_ref}_{counter}"
            counter += 1

        subquest = {
            "ref": ref,
            "name": name,
            "description": self.sq_fields["description"],
            "difficulty": difficulty,
            "stats": stats,
            "recurrence": "none",
            "next_quests": [],
        }
        if "quests" not in self.current_template:
            self.current_template["quests"] = []
        self.current_template["quests"].append(subquest)
        save_quest_templates(self.character.name, self.templates)
        self.message = f"Subquest '{name}' added to template."
        self.mode = "view"
        self.sub_picker = None

    def _start_edit_deps(self):
        """Start editing next_quests for the selected subquest in the template."""
        if not self.sub_picker or not self.current_template:
            return
        quests = self.current_template.get("quests", [])
        idx = self.sub_picker.filtered_indices[self.sub_picker.cursor]
        if idx >= len(quests):
            return
        self.dep_index = idx
        sq = quests[idx]
        # Candidates: all other subquests
        candidates = [q for i, q in enumerate(quests) if i != idx]
        current_next = sq.get("next_quests", [])
        self.dep_toggles = [c.get("ref", "") in current_next for c in candidates]
        self.dep_picker = None
        self.mode = "edit_deps"

    def _save_deps(self):
        """Save edited dependencies in the template."""
        if not self.current_template or self.dep_index < 0:
            return
        quests = self.current_template.get("quests", [])
        sq = quests[self.dep_index]
        candidates = [q for i, q in enumerate(quests) if i != self.dep_index]
        new_next = [
            candidates[i].get("ref", "")
            for i, toggled in enumerate(self.dep_toggles) if toggled
        ]
        sq["next_quests"] = new_next
        save_quest_templates(self.character.name, self.templates)
        self.message = f"Dependencies updated for '{sq['name']}'."
        self.dep_index = -1
        self.dep_picker = None
        self.mode = "view"
        self.sub_picker = None

    def _delete_selected_template(self):
        """Delete the selected template from the library."""
        if not self.picker:
            return
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(self.templates):
            return
        tmpl = self.templates[idx]
        self.templates.remove(tmpl)
        save_quest_templates(self.character.name, self.templates)
        self.message = f"Template '{tmpl['name']}' removed."
        self.picker = None

    def _delete_selected_subquest(self):
        """Delete the selected subquest from the current template."""
        if not self.sub_picker or not self.current_template:
            return
        quests = self.current_template.get("quests", [])
        idx = self.sub_picker.filtered_indices[self.sub_picker.cursor]
        if idx >= len(quests):
            return
        sq = quests[idx]
        removed_ref = sq.get("ref", "")
        quests.pop(idx)
        # Clean up references to the removed subquest
        for q in quests:
            q["next_quests"] = [r for r in q.get("next_quests", []) if r != removed_ref]
        save_quest_templates(self.character.name, self.templates)
        self.message = f"Subquest '{sq['name']}' removed from template."
        self.sub_picker = None

    def _instantiate_selected_template(self):
        """Create real quests from the selected template.

        This copies the template's overquest and subquests into the character's
        live quest list (quests.json). The template remains unchanged.
        """
        if not self.picker:
            return
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(self.templates):
            return
        template = self.templates[idx]

        quests = load_quests(self.character.name)
        oq_data = template.get("overquest", {})

        # Create overquest
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
        quests.append(overquest)

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

        quests.extend(quest_objects)
        save_quests(self.character.name, quests)
        n = len(quest_objects)
        self.message = f"Quest line '{overquest.name}' created from template! ({n} quests)"
        self.picker = None
