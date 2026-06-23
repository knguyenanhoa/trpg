"""JSON file-based data storage with atomic writes."""

import json
import os
import tempfile

from app.config import DB_PATH, DEFINITIONS_PATH
from app.models.character import Character
from app.models.quest import Quest, QuestLogEntry
from app.models.item import Item
from app.utils.sanitize import name_to_folder


def _ensure_dir(path: str):
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)


def _atomic_write(path: str, data):
    """Write data atomically (write to temp, then rename)."""
    _ensure_dir(os.path.dirname(path))
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def _read_json(path: str, default=None):
    """Read JSON file, returning default if not found."""
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r") as f:
        return json.load(f)


# --- Character operations ---

def _char_dir(character_name: str) -> str:
    """Get character directory path."""
    folder = name_to_folder(character_name)
    return os.path.join(DB_PATH, "characters", folder)


def list_characters() -> list[str]:
    """List all character folder names."""
    chars_dir = os.path.join(DB_PATH, "characters")
    if not os.path.exists(chars_dir):
        return []
    return [
        d for d in os.listdir(chars_dir)
        if os.path.isdir(os.path.join(chars_dir, d))
    ]


def save_character(character: Character):
    """Save character data."""
    path = os.path.join(_char_dir(character.name), "character.json")
    _atomic_write(path, character.to_dict())


def load_character(folder_name: str) -> Character | None:
    """Load a character by folder name."""
    path = os.path.join(DB_PATH, "characters", folder_name, "character.json")
    data = _read_json(path)
    if not data:
        return None
    return Character.from_dict(data)


def delete_character(folder_name: str):
    """Delete a character's entire data folder."""
    import shutil
    char_path = os.path.join(DB_PATH, "characters", folder_name)
    if os.path.exists(char_path):
        shutil.rmtree(char_path)


# --- Quest operations ---

def save_quests(character_name: str, quests: list[Quest]):
    """Save quest list for a character."""
    path = os.path.join(_char_dir(character_name), "quests.json")
    _atomic_write(path, [q.to_dict() for q in quests])


def load_quests(character_name: str) -> list[Quest]:
    """Load quests for a character."""
    path = os.path.join(_char_dir(character_name), "quests.json")
    data = _read_json(path, default=[])
    return [Quest.from_dict(d) for d in data]


# --- Quest log operations ---

def save_quest_log(character_name: str, log: list[QuestLogEntry]):
    """Save quest log for a character."""
    path = os.path.join(_char_dir(character_name), "quest_log.json")
    _atomic_write(path, [e.to_dict() for e in log])


def load_quest_log(character_name: str) -> list[QuestLogEntry]:
    """Load quest log for a character."""
    path = os.path.join(_char_dir(character_name), "quest_log.json")
    data = _read_json(path, default=[])
    return [QuestLogEntry.from_dict(d) for d in data]


def append_quest_log(character_name: str, entry: QuestLogEntry):
    """Append a single entry to the quest log."""
    log = load_quest_log(character_name)
    log.append(entry)
    save_quest_log(character_name, log)


# --- Inventory operations ---

def save_inventory(character_name: str, items: list[Item]):
    """Save inventory for a character."""
    path = os.path.join(_char_dir(character_name), "inventory.json")
    _atomic_write(path, [i.to_dict() for i in items])


def load_inventory(character_name: str) -> list[Item]:
    """Load inventory for a character."""
    path = os.path.join(_char_dir(character_name), "inventory.json")
    data = _read_json(path, default=[])
    return [Item.from_dict(d) for d in data]


# --- Active quest tracking (started but not completed) ---

def save_active_quests(character_name: str, active: dict[str, str]):
    """Save active quest start times. Keys are quest IDs, values are ISO timestamps."""
    path = os.path.join(_char_dir(character_name), "active_quests.json")
    _atomic_write(path, active)


def load_active_quests(character_name: str) -> dict[str, str]:
    """Load active quest start times."""
    path = os.path.join(_char_dir(character_name), "active_quests.json")
    return _read_json(path, default={})


# --- Completed quests (non-recurring quests that are done) ---

def save_completed_quests(character_name: str, quests: list[Quest]):
    """Save completed quest definitions (for history viewing)."""
    path = os.path.join(_char_dir(character_name), "completed_quests.json")
    _atomic_write(path, [q.to_dict() for q in quests])


def load_completed_quests(character_name: str) -> list[Quest]:
    """Load completed quest definitions."""
    path = os.path.join(_char_dir(character_name), "completed_quests.json")
    data = _read_json(path, default=[])
    return [Quest.from_dict(d) for d in data]


# --- Global config ---

def save_global_config(config: dict):
    """Save global config."""
    path = os.path.join(DB_PATH, "config.json")
    _atomic_write(path, config)


def load_global_config() -> dict:
    """Load global config."""
    path = os.path.join(DB_PATH, "config.json")
    return _read_json(path, default={"timezone_offset": 7})


# --- Premade quest templates ---

def load_premade_quest_templates() -> list[dict]:
    """Load premade quest tree templates from definitions.

    Returns a list of template dicts, each with:
    - name: template name
    - description: template description
    - overquest: dict with overquest fields (name, description, difficulty, stats)
    - quests: list of quest dicts with ref IDs and next_quests references
    """
    path = os.path.join(DEFINITIONS_PATH, "premade_quests.json")
    data = _read_json(path, default={"templates": []})
    return data.get("templates", [])


# --- Per-character quest templates ---

def save_quest_templates(character_name: str, templates: list[dict]):
    """Save quest templates for a character.

    Templates are raw dicts (same format as premade_quests.json entries).
    They are independent from live quests — editing one does not affect the other.
    """
    path = os.path.join(_char_dir(character_name), "quest_templates.json")
    _atomic_write(path, templates)


def load_quest_templates(character_name: str) -> list[dict]:
    """Load quest templates for a character."""
    path = os.path.join(_char_dir(character_name), "quest_templates.json")
    return _read_json(path, default=[])

