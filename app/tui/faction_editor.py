"""Faction editor screen — create, edit, deactivate/restore factions."""

import uuid

from app.tui.base_screen import BaseScreen
from app.tui.fzf_picker import InlinePicker
from app.models.character import Character
from app.models.faction import Faction
from app.db.file_store import load_factions, save_factions
from app.utils.sanitize import validate_name, sanitize_name
from app.utils.time_utils import now_iso


class FactionEditorScreen(BaseScreen):
    """Faction management screen.

    Displays active and inactive factions separately.
    Supports creating factions, deactivating (hiding), and restoring them.

    Modes:
    - list: browse factions (active tab / inactive tab)
    - create: form to create a new faction
    """

    def __init__(self, character: Character):
        super().__init__()
        self.character = character
        self.factions = load_factions(character.name)
        self.picker = None
        self.tab = "active"  # active, inactive
        self.mode = "list"  # list, create
        self.message = ""
        self._reset_form()

    def _reset_form(self):
        self.form_fields = {"name": "", "description": ""}
        self.form_field_order = ["name", "description"]
        self.form_cursor = 0

    # --- Display helpers ---

    def _active_factions(self) -> list[Faction]:
        return sorted([f for f in self.factions if f.active], key=lambda f: f.name.lower())

    def _inactive_factions(self) -> list[Faction]:
        return sorted([f for f in self.factions if not f.active], key=lambda f: f.name.lower())

    def _display_list(self) -> list[str]:
        if self.tab == "active":
            factions = self._active_factions()
            items = [f"{f.name} ({f.quests_completed} quests done)" for f in factions]
            items.append("+ New Faction")
        else:
            factions = self._inactive_factions()
            items = [f"{f.name} (inactive)" for f in factions]
            if not items:
                items.append("(no inactive factions)")
        return items

    # --- Render ---

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.magenta +
              f"{self.character.name} — Factions" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 50 + t.normal, end="")

        if self.message:
            print(t.move_xy(2, 3) + t.yellow + self.message + t.normal, end="")

        # Tab indicator
        if self.tab == "active":
            print(t.move_xy(2, 4) + t.bold + "[A]ctive" + t.normal +
                  "  " + t.dim + "[I]nactive" + t.normal, end="")
        else:
            print(t.move_xy(2, 4) + t.dim + "[A]ctive" + t.normal +
                  "  " + t.bold + "[I]nactive" + t.normal, end="")

        if self.mode == "list":
            self._render_list()
        elif self.mode == "create":
            self._render_create()

        if self.mode == "list":
            if self.tab == "active":
                controls = "n:new  d:deactivate  Tab:tabs  Esc:back"
            else:
                controls = "r:restore  Tab:tabs  Esc:back"
            print(t.move_xy(2, t.height - 1) + t.dim + controls + t.normal, end="")
        else:
            print(t.move_xy(2, t.height - 1) + t.dim +
                  "Tab:next  Enter:submit  Esc:cancel" + t.normal, end="")

    def _render_list(self):
        t = self.term
        items = self._display_list()
        if self.picker is None:
            prompt = "Active Factions:" if self.tab == "active" else "Inactive Factions:"
            self.picker = InlinePicker(items, t, prompt=prompt, x=2, y=6)
        else:
            self.picker.items = items
            self.picker.filtered_indices = list(range(len(items)))
        self.picker.render()

    def _render_create(self):
        t = self.term
        y = 6
        print(t.move_xy(2, y) + t.bold + "New Faction" + t.normal +
              t.dim + " (Tab: next, Enter: submit)" + t.normal, end="")
        y += 1

        for i, fld in enumerate(self.form_field_order):
            is_active = (i == self.form_cursor)
            prefix = t.cyan + "▸ " + t.normal if is_active else "  "
            val = self.form_fields[fld]
            cc = "█" if is_active else ""
            label = "Name" if fld == "name" else "Description"
            print(t.move_xy(2, y) + f"{prefix}{label}: {val}{cc}" + t.clear_eol, end="")
            y += 1

    # --- Key handling ---

    def on_key(self, key):
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
        if key.code == t.KEY_ESCAPE or key == "h":
            self.manager.pop()
            return
        if key == "\t":
            self.tab = "inactive" if self.tab == "active" else "active"
            self.picker = None
            return

        if self.tab == "active":
            if key == "n":
                self.mode = "create"
                self._reset_form()
                return
            if key == "d":
                self._deactivate_selected()
                return
        else:
            if key == "r":
                self._restore_selected()
                return

        if self.picker:
            result, active = self.picker.on_key(key)
            if not active and result:
                if result == "+ New Faction":
                    self.mode = "create"
                    self._reset_form()

    def _handle_create_key(self, key):
        t = self.term
        current_field = self.form_field_order[self.form_cursor]

        if key.code == t.KEY_ESCAPE:
            self.mode = "list"
            self.picker = None
            return
        if key.code == t.KEY_ENTER:
            self._finalize_create()
            return
        if key == "\t":
            self.form_cursor = min(self.form_cursor + 1, len(self.form_field_order) - 1)
            return
        if key.code == t.KEY_BTAB:
            self.form_cursor = max(self.form_cursor - 1, 0)
            return

        if key.code == t.KEY_BACKSPACE or key == "\x7f":
            self.form_fields[current_field] = self.form_fields[current_field][:-1]
        elif not key.is_sequence and key.isprintable():
            self.form_fields[current_field] += str(key)

    # --- Actions ---

    def _finalize_create(self):
        name = sanitize_name(self.form_fields["name"])
        valid, err = validate_name(name)
        if not valid:
            self.message = err or "Name is required."
            return

        faction = Faction(
            id=str(uuid.uuid4()),
            name=name,
            description=self.form_fields["description"],
            active=True,
            quests_completed=0,
            created_at=now_iso(),
        )
        self.factions.append(faction)
        save_factions(self.character.name, self.factions)
        self.message = f"Faction '{faction.name}' created!"
        self.mode = "list"
        self.picker = None

    def _deactivate_selected(self):
        if not self.picker:
            return
        factions = self._active_factions()
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(factions):
            return
        faction = factions[idx]
        faction.active = False
        save_factions(self.character.name, self.factions)
        self.message = f"Faction '{faction.name}' deactivated."
        self.picker = None

    def _restore_selected(self):
        if not self.picker:
            return
        factions = self._inactive_factions()
        idx = self.picker.filtered_indices[self.picker.cursor]
        if idx >= len(factions):
            return
        faction = factions[idx]
        faction.active = True
        save_factions(self.character.name, self.factions)
        self.message = f"Faction '{faction.name}' restored!"
        self.picker = None
