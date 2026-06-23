# X-LRPG Design Document

## 1. Overview

A local-first TUI RPG that tracks real-life goals as quests, granting experience and items to a DnD-style character. Built in Python with minimal dependencies.

---

## 2. Technology Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| Language | Python 3.11+ | stdlib curses, json, hashlib; rich ecosystem |
| TUI | `blessed` | Vim-key support, colors, positioning; thin wrapper over curses |
| List picker | Shell out to `fzf` binary | Zero Python deps, powerful fuzzy search |
| Database | JSON files in `db/` | Text-based, human-readable, no server |
| Hashing | `hashlib` (stdlib) | Integrity checks if needed |

No other dependencies.

---

## 3. Project Structure

```
x-lrpg/
├── main.py                         # Entry point
├── requirements.txt                # blessed (only external dep)
├── app/
│   ├── __init__.py
│   ├── config.py                   # Global config (timezone, paths)
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── screen_manager.py       # Screen stack, navigation, input loop
│   │   ├── help_screen.py          # "?" overlay with key bindings
│   │   ├── character_select.py     # Character selection at launch
│   │   ├── character_create.py     # Character creation flow
│   │   ├── stats_screen.py         # Stat viewing
│   │   ├── quest_screen.py         # Quest list, creation, completion
│   │   ├── inventory_screen.py     # Item viewing, equip/unequip
│   │   └── fzf_picker.py           # FZF floating window integration
│   ├── models/
│   │   ├── __init__.py
│   │   ├── character.py            # Character data model
│   │   ├── quest.py                # Quest data model
│   │   ├── item.py                 # Item/weapon/armour model
│   │   └── stats.py                # Stat types and constants
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── experience.py           # XP calculations
│   │   ├── leveling.py             # Level and rank-up logic
│   │   ├── item_roller.py          # Random item generation
│   │   ├── quest_engine.py         # Quest start/complete/fail logic
│   │   └── scheduler.py            # Recurring quest tick, failure detection
│   ├── db/
│   │   ├── __init__.py
│   │   └── file_store.py           # JSON CRUD helpers
│   └── utils/
│       ├── __init__.py
│       ├── sanitize.py             # Input validation and sanitization
│       ├── colors.py               # Color constants
│       └── time_utils.py           # Timezone-aware timestamp helpers
├── assets/
│   ├── portraits/                  # ASCII character portraits (.txt)
│   └── items/                      # ASCII item sprites (.txt)
├── db/                             # Runtime character data (gitignored)
│   └── .gitkeep
└── definitions/
    ├── ranks.json
    ├── items.json
    ├── weapons.json
    ├── armour.json
    ├── equipment_slots.json
    ├── stat_tables_male.json
    └── stat_tables_female.json
```

---

## 4. Character System

### 4.1 Creation

1. Player enters: name, age, sex.
2. Stats initialized via lookup table (`stat_tables_male.json` / `stat_tables_female.json`) keyed by age bracket, with ±2 random variation per stat.
3. Optional backstory (free text, sanitized).
4. ASCII portrait selected from `assets/portraits/`, player picks a color.

### 4.2 Stats

| Type | Stats | Source |
|------|-------|--------|
| Character Stats ($CS) | str, dex, con, int, wis, cha | Quest XP accumulation |
| Item Stats ($IS) | istr, idex, icon, iint, iwis, icha | Equipped items only |

**Effective stat** = $CS + $IS (used for display; $CS alone determines level).

### 4.3 Level

```
level = mean(str, dex, con, int, wis, cha)  # float
```

Encourages balanced builds.

### 4.4 Rank-Up

- Available when ALL $CS ≥ 100.
- Rank thresholds defined in `ranks.json` with minimum total $IS required.
- Ranks are enumerated and named (e.g., Novice → Apprentice → Journeyman → ...).

---

## 5. Experience System

### 5.1 XP Required to Level a Stat

```python
def xp_required(stat_value: int) -> int:
    return int(50 + 10 * (stat_value ** 1.5))
```

| Stat Value | XP Required |
|-----------|-------------|
| 1 | 60 |
| 10 | 366 |
| 25 | 1,300 |
| 50 | 3,585 |
| 75 | 6,545 |
| 99 | 9,900 |

### 5.2 XP Granted by Quest Completion

```python
def xp_granted(difficulty: float) -> int:
    return int(10 * (difficulty ** 2))
```

| Difficulty | XP |
|-----------|-----|
| 0.5 | 2 |
| 1.0 | 10 |
| 2.0 | 40 |
| 3.0 | 90 |
| 4.0 | 160 |
| 5.0 | 250 |

XP is distributed equally among the quest's assigned stats.

### 5.3 XP Decrease (Failed Quests)

- Penalty = 1/2 of XP that would have been granted.
- If XP goes below 0 at current stat level:
  1. Reduce stat by 1.
  2. Set XP at new level = `xp_required(new_stat_value) - abs(remaining_deficit)`.
  3. If still negative, repeat recursively.

### 5.4 XP Increase (Stat Level-Up)

- When accumulated XP ≥ `xp_required(current_stat_value)`:
  1. Increase stat by 1.
  2. Carry over excess XP to new level.

---

## 6. Quest System

### 6.1 Quest Data Model

```json
{
    "id": "uuid",
    "name": "string",
    "description": "string",
    "difficulty": 0.0-5.0,
    "stats": ["str", "con"],
    "recurrence": "none|daily|monthly",
    "created_at": "ISO8601",
    "active": true
}
```

### 6.2 Quest Lifecycle

1. **Created** — Player defines quest.
2. **Started** — Player manually starts; `started_at` timestamp recorded.
3. **Completed** — Player marks done; `completed_at` recorded; XP + item roll triggered.
4. **Failed** — Recurring quest not completed within window; XP penalty applied.

### 6.3 Recurrence Rules

- **Daily**: Must be completed before end of current day (23:59:59 UTC+7). Checked on app launch and periodically.
- **Monthly**: Must be completed before end of current month.
- **None**: One-time quest, no failure for not completing.
- Timezone: UTC+7 (configurable in `app/config.py`).
- No grace period.

### 6.4 Quest Log

Stored per character. Each entry:

```json
{
    "quest_id": "uuid",
    "status": "completed|failed",
    "started_at": "ISO8601",
    "completed_at": "ISO8601|null",
    "duration_seconds": 3600,
    "xp_granted": 90,
    "item_dropped": "item_id|null"
}
```

Recurring quests tracked per occurrence (not grouped).

---

## 7. Item System

### 7.1 Equipment Slots

| Slot | Key |
|------|-----|
| Head | head |
| Chest | chest |
| Legs | legs |
| Feet | feet |
| Hands | hands |
| Weapon | weapon |
| Off-hand | offhand |
| Accessory | accessory |

Each item belongs to exactly one slot type.

### 7.2 Item Rarity

| Rank | Color | Drop Weight |
|------|-------|-------------|
| Normal | White | 50% |
| Uncommon | Green | 25% |
| Rare | Blue | 15% |
| Epic | Yellow | 8% |
| Legendary | Red | 2% |

Higher quest difficulty increases chance of rarer drops (shift weights by `difficulty * 0.05` toward rare).

### 7.3 Item Stat Generation

```python
def roll_item_stats(player_level: float, player_cs: dict, rarity: str) -> dict:
    max_abs = max(5, int(player_level))
    # Weight by player's $CS distribution
    cs_total = sum(player_cs.values())
    weights = {stat: player_cs[stat] / cs_total for stat in CS_STATS}

    stats = {}
    for stat in IS_STATS:
        base_stat = CS_STATS[IS_STATS.index(stat)]
        weight = weights[base_stat]
        # Roll with bias toward player's strong stats
        value = random.uniform(-max_abs, max_abs) * (0.5 + weight)
        stats[stat] = round(value, 1)

    # Ensure net positive
    total = sum(stats.values())
    if total <= 0:
        # Boost the highest-weighted stat
        best = max(weights, key=weights.get)
        stats[f"i{best}"] += abs(total) + random.uniform(0.5, 2.0)

    return stats
```

- `abs(stat) ∈ [0, max(5, player_level)]` — clamped after generation.
- Quest difficulty influences rarity, which indirectly affects stat quality (rarer items get a multiplier on positive stats).
- Stats locked on acquisition; never change.

### 7.4 Item Data Model

```json
{
    "id": "uuid",
    "name": "Iron Helm",
    "slot": "head",
    "rarity": "uncommon",
    "stats": {"istr": 3.2, "idex": -1.1, "icon": 2.0, "iint": -0.5, "iwis": 1.8, "icha": -0.3},
    "sprite": "assets/items/iron_helm.txt",
    "acquired_at": "ISO8601"
}
```

---

## 8. TUI Design

### 8.1 Navigation

- Vim keys: `h/j/k/l` for movement, `Enter` to select, `Esc` to go back.
- `q` or `Ctrl+C` — quit app.
- `?` — help overlay (accessible from any screen).
- Screen stack model: push/pop screens.

### 8.2 Screens

1. **Character Select** — List existing characters + "New Character" option (FZF picker).
2. **Main Menu** — Stats | Quests | Inventory | Settings.
3. **Stats Screen** — Display all $CS, $IS, effective stats, level, rank.
4. **Quest Screen** — Active quests list, create new, start/complete/view log.
5. **Inventory Screen** — Equipped items by slot, unequipped inventory, equip/unequip.
6. **Help Screen** — Floating overlay listing all key bindings.

### 8.3 FZF Integration

- Lists (characters, quests, items) piped to `fzf` via subprocess.
- Displayed in a floating terminal window.
- Returns selected item ID.
- Fallback: if `fzf` not installed, use built-in j/k list with simple search.

### 8.4 Colors

- Blessed terminal colors.
- Portrait colors: player-selected from palette.
- Item colors: determined by rarity.
- Stats: green for positive, red for negative.

---

## 9. Data Storage (db/)

### 9.1 Folder Structure

```
db/
├── characters/
│   ├── hero_mcgee/
│   │   ├── character.json      # Core character data
│   │   ├── inventory.json      # All items (equipped + unequipped)
│   │   ├── quests.json         # Active quest definitions
│   │   └── quest_log.json      # Completed/failed quest history
│   └── another_char/
│       └── ...
└── config.json                 # Global config (timezone, etc.)
```

### 9.2 File Operations

- All reads/writes through `app/db/file_store.py`.
- Atomic writes (write to temp file, then rename) to prevent corruption.
- Character folder name = sanitized character name (lowercase, underscores, no specials).

---

## 10. Input Sanitization

### Rules

1. Names: alphanumeric + spaces only, max 30 chars.
2. Backstory: printable ASCII only, max 500 chars, no control chars.
3. Numeric inputs: type-checked, range-validated before acceptance.
4. File/folder names derived from input: stripped of all non-alphanumeric, lowercased, spaces→underscores.
5. No eval(), exec(), or subprocess with user-provided strings.
6. FZF input: only predefined values piped, never raw user text.

---

## 11. Security Considerations

- No network access.
- No execution of external scripts.
- File paths constructed only from sanitized identifiers; no path traversal.
- JSON parsing with stdlib only (no pickle, no yaml with unsafe loader).
- Subprocess calls limited to `fzf` with predefined arguments only.

---

## 12. Configuration

```python
# app/config.py
TIMEZONE_OFFSET = 7  # UTC+7, modifiable
DB_PATH = "db/"
ASSETS_PATH = "assets/"
DEFINITIONS_PATH = "definitions/"
MAX_NAME_LENGTH = 30
MAX_BACKSTORY_LENGTH = 500
```

---

## 13. Definition File Schemas

### ranks.json
```json
[
    {"rank": 1, "name": "Novice", "min_is_total": 0},
    {"rank": 2, "name": "Apprentice", "min_is_total": 50},
    {"rank": 3, "name": "Journeyman", "min_is_total": 150},
    {"rank": 4, "name": "Expert", "min_is_total": 300},
    {"rank": 5, "name": "Master", "min_is_total": 500},
    {"rank": 6, "name": "Grandmaster", "min_is_total": 800},
    {"rank": 7, "name": "Legend", "min_is_total": 1200}
]
```

### stat_tables_male.json / stat_tables_female.json
```json
{
    "10-15": {"str": 8, "dex": 10, "con": 9, "int": 7, "wis": 5, "cha": 8},
    "16-20": {"str": 12, "dex": 12, "con": 11, "int": 10, "wis": 7, "cha": 10},
    "21-30": {"str": 14, "dex": 13, "con": 13, "int": 12, "wis": 10, "cha": 11},
    "31-40": {"str": 13, "dex": 11, "con": 12, "int": 13, "wis": 13, "cha": 11},
    "41-50": {"str": 11, "dex": 10, "con": 11, "int": 13, "wis": 14, "cha": 10},
    "51+":   {"str": 9, "dex": 8, "con": 9, "int": 12, "wis": 15, "cha": 10}
}
```

### equipment_slots.json
```json
["head", "chest", "legs", "feet", "hands", "weapon", "offhand", "accessory"]
```

---

## 14. Open Items for Future Iterations

- Item reforging / discard mechanics.
- Item inventory.
- Quest chains (multi-step quests).
- Achievement system.
- Character export/import.
- Party system (multiple characters cooperating).
- More portrait/sprite variety.
- Sound effects via terminal bell.
