# Overview
This is a TUI RPG for real life, so anyone can create a character, define their starting stats and level up through achieving and recording real-life goals and objectives.

# Overall game design
- Based on DnD style games but reduced scope.
- Select character or create with name, age, sex and stats. Stats should be manually entered or estimated by table lookup (male/female and age map to stats with ±2 random variation).
- Multiple characters are supported. A character selection screen is shown at launch.
- A back story for the character is optional (max 500 chars). The character should be given an ascii portrait from a predefined set. Allow the player to specify the colour of the portrait from {white, green, blue, yellow, red, cyan, magenta}.
- Stats are tracked per player, and are increased by completing quests.
- Quests are self designed and assigned. Quests record difficulty, recurrence type and stat types.
- The main activities the player will be doing in the game are: stat viewing, quest viewing and creation, quest completion, inventory management and item equipment.

# Stats and player progression design
- 2 types of stats: character stats ($CS) and item stats ($IS).
- $CS increase by 1 point when enough experience has been accumulated via quest completion. The amount of experience required is: `xp_required(stat_value) = 50 + 10 * (stat_value ^ 1.5)`.
- $CS is in the list {str, dex, con, int, wis, cha}.
- $IS is in the list {istr, idex, icon, iint, iwis, icha}.
- $IS only depend on items equipped.
- Character level is the average of all $CS points (can be a float), not $IS. This encourages balanced builds.
- When every $CS reaches a minimum of 100, the player may choose to "rank up". Ranks are pulled from a list and enumerated. A player is able to rank up to a specific rank if their $IS total meets the minimum required for a certain rank.
- Ranks: Novice (0), Apprentice (50), Journeyman (150), Expert (300), Master (500), Grandmaster (800), Legend (1200). Values in parentheses are the minimum total $IS required.
- Experience for stats can increase and decrease. If it decreases below 0, it reduces the stat to the previous level. The experience at the reduced stat level should be calculated by taking the max experience for that level, subtracting any left over resulting from the decrease in experience i.e. experience decrease and increase carry over to previous or next stat levels. Stat cannot go below 1.

# Quests design
- Quests can be started manually by a player. Starting a quest records a timestamp.
- Quests can define certain $CS that, upon completion, will grant experience towards those stats. The total XP is split equally among the quest's assigned stats. The amount of experience depends on the quest difficulty.
- Quest difficulty is recorded as a float from 0.0 to 5.0. Experience granted is: `xp_granted(difficulty) = 10 * (difficulty ^ 2)`.
- Quest recurrence are of the types none, daily, monthly and should recur automatically.
- Completed quests should be tracked in a log for the character, with start timestamp, completion timestamp and duration (computed from timestamps, not player-entered). Recurring quests are to be tracked separately per occurrence, not grouped.
- Recurring quests, if missed, should be marked as failed. Daily quests must be completed before 23:59:59 of the current day. Monthly quests must be completed before end of the current month. No grace period. Timezone is UTC+7 (configurable).
- Failed quests reduce experience by 1/2 of the experience that would have been gained had the quest succeeded.
- Quests have a 50% chance to drop an item on completion.

# Items design
- Items are earned through quest completion, and rolled randomly from a list. Items have ascii sprites, and item rank in {normal, uncommon, rare, epic, legendary} with sprite colours in {white, green, blue, yellow, red}.
- Item rarity drop weights: normal 50%, uncommon 25%, rare 15%, epic 8%, legendary 2%. Higher quest difficulty shifts odds toward rarer items (bonus per tier = tier_index * difficulty * 0.03).
- Items have $IS boosts, generated randomly on generation. Values are floats clamped to abs value in [0, max(5, player_level)].
- Item stat rolls are weighted by the player's current $CS distribution. If a character has high str and low wis, items will tend to roll high istr and low iwis.
- All items have a mix of positive and negative stats. Net total $IS on any item is guaranteed to be slightly positive.
- Rarer items get a multiplier on positive stats: normal 1.0x, uncommon 1.2x, rare 1.5x, epic 1.8x, legendary 2.2x.
- If an item is acquired by a player, its stats are locked in and not changed, even if the player level changes.
- Items belong to a fixed equipment slot. Equipment slots: head, chest, legs, feet, hands, weapon, offhand, accessory (8 total). One item per slot.

# Required files and folders
- definitions/ranks.json — Player rank list with $IS thresholds.
- definitions/items.json — General items listing their names, slots, and sprite paths.
- definitions/weapons.json — Weapons listing their names and sprite paths.
- definitions/armour.json — Armour listing their names, slots, and sprite paths.
- definitions/stat_tables_male.json — Male age bracket mapping to base stats.
- definitions/stat_tables_female.json — Female age bracket mapping to base stats.
- definitions/equipment_slots.json — List of valid equipment slots.
- assets/portraits/ — ASCII character portraits (.txt files).
- assets/items/ — ASCII item sprites (.txt files).
- db/ — Runtime data, organized per character (db/characters/{name}/). Contains character.json, quests.json, quest_log.json, inventory.json, active_quests.json per character.
- db/config.json — Global configuration (timezone etc).

# Architecture and required tech stack
- Language: Python 3.11+.
- Single external dependency: blessed (TUI rendering with color and positioning support).
- FZF integration via subprocess for list selection. Built-in j/k picker as fallback when fzf is not installed.
- Database is JSON files in db/. All file writes are atomic (write to temp, then rename). Custom file_store.py handles CRUD.
- Local-first, no networking required.
- TUI with vim-like movement (h/j/k/l). Map the key "?" to a help screen, accessible from any screen, listing key mappings. Do not support custom key binding.
- FZF-style floating list selection with "/" for search.
- Assets (ascii sprites) under assets/.
- The app should terminate on Ctrl + C or the key "q".
- Must support colours.

# Overall design principle
- All files should be named with underscore format e.g. sample_file.txt
- Any user input must be properly sanitized and type checked e.g. disallow string in a stat, these should be integers or floats.
- Player input of any kind must not contain special characters. When it is used internally as variables or file names, make sure it is sanitized and converted properly. Names: alphanumeric + spaces only, max 30 chars. File names derived from input: lowercase, underscores, no specials.
- Properly consider security. Disallow executing custom scripts anywhere in the app. No eval(), exec(), or subprocess with user-provided strings. FZF only receives predefined values.
- Properly consider performance.

# Project file structure
```
x-lrpg/
├── main.py                         # Entry point
├── requirements.txt                # blessed==1.20.0
├── app/
│   ├── __init__.py
│   ├── config.py                   # Global config (timezone, paths, constants)
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── base_screen.py          # BaseScreen class
│   │   ├── screen_manager.py       # Screen stack, navigation, input loop
│   │   ├── help_screen.py          # "?" overlay with key bindings
│   │   ├── character_select.py     # Character selection at launch
│   │   ├── character_create.py     # Character creation flow
│   │   ├── main_menu.py            # Main menu (Stats/Quests/Inventory)
│   │   ├── stats_screen.py         # Stat viewing with XP bars
│   │   ├── quest_screen.py         # Quest list, creation, start, complete
│   │   ├── inventory_screen.py     # Item viewing, equip/unequip
│   │   └── fzf_picker.py           # FZF integration + built-in fallback
│   ├── models/
│   │   ├── __init__.py
│   │   ├── character.py            # Character data model
│   │   ├── quest.py                # Quest and QuestLogEntry models
│   │   ├── item.py                 # Item model
│   │   └── stats.py                # CharacterStats and ItemStats classes
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── experience.py           # XP formulas (required, granted, penalty)
│   │   ├── leveling.py             # Level and rank-up logic
│   │   ├── item_roller.py          # Random item generation
│   │   ├── quest_engine.py         # Quest start/complete/fail logic
│   │   └── scheduler.py            # Recurring quest failure detection
│   ├── db/
│   │   ├── __init__.py
│   │   └── file_store.py           # JSON CRUD with atomic writes
│   └── utils/
│       ├── __init__.py
│       ├── sanitize.py             # Input validation and sanitization
│       ├── colors.py               # Color constants and helpers
│       └── time_utils.py           # Timezone-aware timestamp helpers (UTC+7)
├── assets/
│   ├── portraits/                  # ASCII character portraits (.txt)
│   │   ├── mage.txt
│   │   ├── warrior.txt
│   │   └── rogue.txt
│   └── items/                      # ASCII item sprites (.txt)
│       ├── iron_sword.txt
│       ├── iron_helm.txt
│       └── buckler.txt
├── db/                             # Runtime character data (gitignored)
│   └── characters/
│       └── {character_folder}/
│           ├── character.json
│           ├── quests.json
│           ├── quest_log.json
│           ├── inventory.json
│           └── active_quests.json
└── definitions/
    ├── ranks.json
    ├── items.json
    ├── weapons.json
    ├── armour.json
    ├── equipment_slots.json
    ├── stat_tables_male.json
    └── stat_tables_female.json
```

# Key bindings
| Key | Action |
|-----|--------|
| h / ← | Move left / Back |
| j / ↓ | Move down |
| k / ↑ | Move up |
| l / → | Move right / Select |
| Enter | Select / Confirm |
| Esc | Back / Cancel |
| q | Quit application |
| ? | Toggle help overlay |
| / | Search (in lists) |
| n | New (context-dependent) |
| d | Delete (context-dependent) |
| s | Start quest |
| c | Complete quest |
| e | Switch to equipped tab |
| b | Switch to backpack tab |
| r | Rank up (stats screen) |
| Space | Toggle selection (stat picker) |
| Ctrl+C | Force quit |

# AGENT: Implementation guidance
- Language: Python 3.11+. Do not use pure bash.
- Only external dependency: blessed==1.20.0. Use stdlib for everything else (json, os, uuid, random, hashlib, datetime).
- Use `t.attr + "text" + t.normal` pattern for blessed formatting (not `t.attr("text")` which throws TypeError).
- Remember that this is a work in progress so expect it to be iteratively improved. Set things up accordingly.
- Do not modify vibecoding/spec.md or vibecoding/spec_v2.md.
