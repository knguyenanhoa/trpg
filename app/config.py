"""Global configuration for X-LRPG."""

import os

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db")
ASSETS_PATH = os.path.join(BASE_DIR, "assets")
DEFINITIONS_PATH = os.path.join(BASE_DIR, "definitions")

# Timezone
TIMEZONE_OFFSET = 7  # UTC+7

# Input limits
MAX_NAME_LENGTH = 30
MAX_BACKSTORY_LENGTH = 500

# Character stats
CS_STATS = ["str", "dex", "con", "int", "wis", "cha"]
IS_STATS = ["istr", "idex", "icon", "iint", "iwis", "icha"]

# Equipment slots
EQUIPMENT_SLOTS = ["head", "chest", "legs", "feet", "hands", "weapon", "offhand", "accessory"]

# Item rarities with drop weights
ITEM_RARITIES = {
    "normal": {"weight": 0.50, "color": "white"},
    "uncommon": {"weight": 0.25, "color": "green"},
    "rare": {"weight": 0.15, "color": "blue"},
    "epic": {"weight": 0.08, "color": "yellow"},
    "legendary": {"weight": 0.02, "color": "red"},
}

# Quest recurrence types
QUEST_RECURRENCE = ["none", "daily", "monthly"]

# Difficulty range
DIFFICULTY_MIN = 0.0
DIFFICULTY_MAX = 5.0
