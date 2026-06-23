"""Character creation screen."""

import json
import os
import random

from app.tui.base_screen import BaseScreen
from app.config import DEFINITIONS_PATH, ASSETS_PATH, CS_STATS
from app.models.character import Character
from app.models.stats import CharacterStats
from app.db.file_store import save_character, load_premade_quest_templates, save_quest_templates
from app.utils.sanitize import validate_name, sanitize_name, validate_int
from app.utils.colors import PORTRAIT_COLORS
from app.utils.time_utils import now_iso


class CharacterCreateScreen(BaseScreen):
    """Multi-step character creation flow."""

    def __init__(self):
        super().__init__()
        self.step = 0  # 0=name, 1=age, 2=sex, 3=stats_method, 4=manual_stats, 5=color, 6=backstory, 7=confirm
        self.name = ""
        self.age = 0
        self.sex = "male"
        self.stats = {}
        self.stats_method = "table"  # "table" or "manual"
        self.portrait = ""
        self.portrait_color = "white"
        self.backstory = ""
        self.input_buffer = ""
        self.error = ""
        self.cursor = 0  # for selection steps
        self.stat_index = 0  # for manual stat entry

    def render(self):
        t = self.term
        print(t.move_xy(2, 1) + t.bold + t.cyan + "Create New Character" + t.normal, end="")
        print(t.move_xy(2, 2) + t.dim + "─" * 40 + t.normal, end="")

        if self.error:
            print(t.move_xy(2, 3) + t.red + self.error + t.normal, end="")

        y = 5
        if self.step == 0:
            print(t.move_xy(2, y) + "Enter character name:", end="")
            print(t.move_xy(2, y + 1) + t.white + f"> {self.input_buffer}_" + t.normal, end="")
        elif self.step == 1:
            print(t.move_xy(2, y) + "Name: " + t.bold + self.name + t.normal, end="")
            print(t.move_xy(2, y + 1) + "Enter age (10-99):", end="")
            print(t.move_xy(2, y + 2) + t.white + f"> {self.input_buffer}_" + t.normal, end="")
        elif self.step == 2:
            print(t.move_xy(2, y) + "Name: " + t.bold + self.name + t.normal + f", Age: {self.age}", end="")
            print(t.move_xy(2, y + 1) + "Select sex:", end="")
            options = ["male", "female"]
            for i, opt in enumerate(options):
                marker = " > " if i == self.cursor else "   "
                if i == self.cursor:
                    print(t.move_xy(2, y + 2 + i) + t.reverse + f"{marker}{opt}" + t.normal, end="")
                else:
                    print(t.move_xy(2, y + 2 + i) + f"{marker}{opt}", end="")
        elif self.step == 3:
            print(t.move_xy(2, y) + f"{self.name}, {self.sex}, age {self.age}", end="")
            print(t.move_xy(2, y + 1) + "How to set stats?", end="")
            options = ["Table lookup (recommended)", "Manual entry"]
            for i, opt in enumerate(options):
                marker = " > " if i == self.cursor else "   "
                if i == self.cursor:
                    print(t.move_xy(2, y + 2 + i) + t.reverse + f"{marker}{opt}" + t.normal, end="")
                else:
                    print(t.move_xy(2, y + 2 + i) + f"{marker}{opt}", end="")
        elif self.step == 4:
            print(t.move_xy(2, y) + "Enter stats manually:", end="")
            for i, stat in enumerate(CS_STATS):
                val = self.stats.get(stat, "")
                if i < self.stat_index:
                    print(t.move_xy(2, y + 1 + i) + f"  {stat}: {val}", end="")
                elif i == self.stat_index:
                    print(t.move_xy(2, y + 1 + i) + t.bold + f"> {stat}: {self.input_buffer}_" + t.normal, end="")
                else:
                    print(t.move_xy(2, y + 1 + i) + t.dim + f"  {stat}: ---" + t.normal, end="")
        elif self.step == 5:
            print(t.move_xy(2, y) + "Select portrait color:", end="")
            for i, color in enumerate(PORTRAIT_COLORS):
                marker = " > " if i == self.cursor else "   "
                color_attr = getattr(t, color, "")
                print(t.move_xy(2, y + 1 + i) + color_attr + f"{marker}{color}" + t.normal, end="")
        elif self.step == 6:
            print(t.move_xy(2, y) + "Enter backstory (optional, Enter to skip):", end="")
            print(t.move_xy(2, y + 1) + t.white + f"> {self.input_buffer}_" + t.normal, end="")
        elif self.step == 7:
            self._render_confirm(y)

    def _render_confirm(self, y):
        t = self.term
        print(t.move_xy(2, y) + t.bold + "Confirm character:" + t.normal, end="")
        print(t.move_xy(2, y + 1) + f"  Name: {self.name}", end="")
        print(t.move_xy(2, y + 2) + f"  Age: {self.age}  Sex: {self.sex}", end="")
        print(t.move_xy(2, y + 3) + f"  Color: {self.portrait_color}", end="")
        stat_str = "  ".join(f"{s}:{self.stats[s]}" for s in CS_STATS)
        print(t.move_xy(2, y + 4) + f"  Stats: {stat_str}", end="")
        if self.backstory:
            print(t.move_xy(2, y + 5) + f"  Backstory: {self.backstory[:50]}...", end="")
        print(t.move_xy(2, y + 7) + t.green + "Press Enter to create, Esc to cancel" + t.normal, end="")

    def on_key(self, key):
        t = self.term
        self.error = ""

        if self.step == 0:
            self._handle_text_input(key, self._submit_name)
        elif self.step == 1:
            self._handle_text_input(key, self._submit_age)
        elif self.step == 2:
            self._handle_selection(key, ["male", "female"], self._submit_sex)
        elif self.step == 3:
            self._handle_selection(key, ["table", "manual"], self._submit_stats_method)
        elif self.step == 4:
            self._handle_text_input(key, self._submit_stat_value)
        elif self.step == 5:
            self._handle_selection(key, PORTRAIT_COLORS, self._submit_color)
        elif self.step == 6:
            self._handle_text_input(key, self._submit_backstory)
        elif self.step == 7:
            if key.code == t.KEY_ENTER:
                self._create_character()
            elif key.code == t.KEY_ESCAPE:
                self.manager.pop()

    def _handle_text_input(self, key, submit_fn):
        t = self.term
        if key.code == t.KEY_ENTER:
            submit_fn()
        elif key.code == t.KEY_ESCAPE:
            self.manager.pop()
        elif key.code == t.KEY_BACKSPACE or key == "\x7f":
            self.input_buffer = self.input_buffer[:-1]
        elif not key.is_sequence and key.isprintable():
            self.input_buffer += str(key)

    def _handle_selection(self, key, options, submit_fn):
        t = self.term
        if key == "j" or key.code == t.KEY_DOWN:
            self.cursor = min(self.cursor + 1, len(options) - 1)
        elif key == "k" or key.code == t.KEY_UP:
            self.cursor = max(self.cursor - 1, 0)
        elif key.code == t.KEY_ENTER or key == "l":
            submit_fn(options[self.cursor])
        elif key.code == t.KEY_ESCAPE or key == "h":
            self.manager.pop()

    def _submit_name(self):
        name = sanitize_name(self.input_buffer)
        valid, err = validate_name(name)
        if not valid:
            self.error = err
            return
        self.name = name
        self.input_buffer = ""
        self.step = 1

    def _submit_age(self):
        valid, age, err = validate_int(self.input_buffer, 10, 99)
        if not valid:
            self.error = err
            return
        self.age = age
        self.input_buffer = ""
        self.cursor = 0
        self.step = 2

    def _submit_sex(self, sex):
        self.sex = sex
        self.cursor = 0
        self.step = 3

    def _submit_stats_method(self, method_label):
        if self.cursor == 0:
            # Table lookup
            self.stats_method = "table"
            self._generate_stats_from_table()
            self.step = 5
            self.cursor = 0
        else:
            # Manual
            self.stats_method = "manual"
            self.stat_index = 0
            self.input_buffer = ""
            self.step = 4

    def _submit_stat_value(self):
        valid, val, err = validate_int(self.input_buffer, 1, 100)
        if not valid:
            self.error = err
            return
        stat_name = CS_STATS[self.stat_index]
        self.stats[stat_name] = val
        self.input_buffer = ""
        self.stat_index += 1
        if self.stat_index >= len(CS_STATS):
            self.step = 5
            self.cursor = 0

    def _submit_color(self, color):
        self.portrait_color = color
        self.input_buffer = ""
        self.step = 6

    def _submit_backstory(self):
        self.backstory = self.input_buffer
        self.input_buffer = ""
        self.step = 7

    def _generate_stats_from_table(self):
        """Generate stats from age/sex table with +/-2 random variation."""
        table_file = f"stat_tables_{self.sex}.json"
        path = os.path.join(DEFINITIONS_PATH, table_file)

        with open(path, "r") as f:
            tables = json.load(f)

        # Find age bracket
        base_stats = None
        for bracket, stats in tables.items():
            parts = bracket.split("-")
            if len(parts) == 2:
                low, high = int(parts[0]), int(parts[1])
                if low <= self.age <= high:
                    base_stats = stats
                    break

        if base_stats is None:
            # Default to last bracket
            base_stats = list(tables.values())[-1]

        # Apply +/-2 random variation
        self.stats = {}
        for stat in CS_STATS:
            base = base_stats.get(stat, 10)
            variation = random.randint(-2, 2)
            self.stats[stat] = max(1, base + variation)

    def _create_character(self):
        """Create and save the character."""
        # Find a portrait
        portraits_dir = os.path.join(ASSETS_PATH, "portraits")
        portrait = ""
        if os.path.exists(portraits_dir):
            files = [f for f in os.listdir(portraits_dir) if f.endswith(".txt")]
            if files:
                portrait = random.choice(files)

        char_stats = CharacterStats(
            str=self.stats.get("str", 10),
            dex=self.stats.get("dex", 10),
            con=self.stats.get("con", 10),
            int_=self.stats.get("int", 10),
            wis=self.stats.get("wis", 10),
            cha=self.stats.get("cha", 10),
        )

        character = Character(
            name=self.name,
            age=self.age,
            sex=self.sex,
            stats=char_stats,
            backstory=self.backstory,
            portrait=portrait,
            portrait_color=self.portrait_color,
            created_at=now_iso(),
        )

        save_character(character)
        # Seed quest templates from premade list for new characters
        premade = load_premade_quest_templates()
        save_quest_templates(character.name, premade)
        # Go to main menu with new character
        from app.tui.main_menu import MainMenuScreen
        self.manager.replace(MainMenuScreen(character))
