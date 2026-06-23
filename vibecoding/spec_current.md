# Overview
This is a TUI RPG for real life, so anyone can create a character, define their starting stats and level up through achieving and recording real-life goals and objectives.

# Overall game design
- Based on DnD style games but reduced scope.
- Select character or create with name, age, sex and stats. Stats should be manually entered or estimated by table lookup (male/female and age map to stats with ±2 random variation).
- Multiple characters are supported. A character selection screen is shown at launch. Characters can be deleted by pressing 'd' on the selection screen, gated by typing the character's name to confirm.
- The app remembers the last played character and auto-loads them on startup. If no characters exist, the create screen is shown. From the main menu, "Switch Character" allows selecting a different character or creating a new one.
- A back story for the character is optional (max 500 chars). The character should be given an ascii portrait from a predefined set. Allow the player to specify the colour of the portrait from {white, green, blue, yellow, red, cyan, magenta}.
- The character's ASCII portrait is displayed on the main menu to the left of the character name, rendered in the player's chosen colour. Portraits are compact (4 lines tall) to stay proportional with the character info section.
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
- Quests can be paused. Only non-recurring quests can be paused. Pausing a quest stops it from being started or completed. Recurring quests cannot be paused because they have time-bound obligations.
- The quest screen has two tabs: Active and Completed. Active shows quests that can still be worked on. Completed shows finished non-recurring quests. Quests can be deleted from either list.
- Quest lists are sorted alphabetically.
- Quest status is color coded: green for started/active, red for paused.
- Quest creation uses a condensed single-form interface where all fields (name, difficulty, recurrence, stats, description) are visible at once. Tab moves to the next field, Shift-Tab to the previous. For recurrence, use j/k or Space to cycle through options. For stats, j/k navigates the stat list and Space toggles the selected stat. Enter submits the form.
- Non-recurring (one-time) quests, upon completion, are removed from the active list and moved to the completed list.
- Recurring quests remain in the active list after completion but enforce completion limits: daily quests can only be completed once per day, monthly quests once per month.
- Completed quests should be tracked in a log for the character, with start timestamp, completion timestamp and duration (computed from timestamps, not player-entered). Recurring quests are to be tracked separately per occurrence, not grouped.
- Recurring quests, if missed, should be marked as failed. Daily quests must be completed before 23:59:59 of the current day. Monthly quests must be completed before end of the current month. No grace period. Timezone is UTC+7 (configurable).
- Failed quests reduce experience by 1/2 of the experience that would have been gained had the quest succeeded.
- Quests have a 50% chance to drop an item on completion.

## Quest network (overquests and quest lines)
- Quests form a directed graph (quest network). Each quest can reference multiple "next" quests, and any quest can have many other quests referencing it.
- An **overquest** is a quest marked with `is_overquest=True` that groups subquests together into a quest line. It serves as the end goal of that line.
- Subquests belong to an overquest via `overquest_id`. Each subquest tracks its successors in `next_quests` (list of quest IDs).
- All quests have a `status` field: {new, in-progress, completed, paused}.
- When all terminal subquests (those with no next_quests within the same overquest) are completed, the overquest is automatically completed with a **3x XP reward multiplier**.
- An overquest must have at least 1 subquest (validated).
- Deleting an overquest deletes all subquests that exclusively belong to it. Subquests also referenced by quests outside the line are preserved.
- Inserting a new quest into the network re-links predecessors (standard linked-list insertion).
- Deleting a quest from the network reassigns its predecessors to point to its successors (dependency reassignment).
- Quests can be reassigned to a different position in the network.
- A quest cannot be started unless all of its dependencies (predecessors within the same overquest) have been completed. Locked quests display a "⊘ LOCKED" indicator.

## Quest screen UI structure
- The quest screen displays quests hierarchically in both Active and Completed tabs:
  - **Overquests** appear as top-level foldable headers with a fold icon (▼ expanded, ▶ collapsed) and a progress counter `[done/total]`.
  - **Subquests** are indented below their overquest when unfolded.
  - **Standalone quests** (no overquest) appear at top level without indent.
- Folding: press `f` or `Space` on an overquest to collapse/expand its subquests. Pressing on a subquest folds its parent.
- Status icons: ○ new, ◐ started, ● completed, ◫ paused, ⊘ locked (deps not met).
- Color indicators on the right: green "■ STARTED", red "■ PAUSED", dim "⊘ LOCKED", green "★ DONE" for completed overquests.
- Overquests cannot be started, paused, or deleted from the quest screen (use Quest Editor for that).
- The quest list shows a `+ From Template` action item alongside `+ New Quest`. Selecting it opens a template picker that lists the character's templates; choosing one instantiates a full quest line (overquest + subquests) into the live quest list.
- Completed tab uses the same hierarchy: completed overquests shown as foldable headers with their completed subquests nested inside.

## Quest editor (template manager)
- A dedicated "Quest Editor" screen accessible from the main menu manages per-character **quest templates**.
- **Templates are separate from active quests.** A template is a blueprint for a quest line. Once instantiated, the resulting quests are independent — editing a quest does not affect its source template and vice versa.
- When a new character is created, the premade templates from `definitions/premade_quests.json` are copied into the character's template library (`quest_templates.json`).
- After creation, each character can freely add/remove templates from their own library.
- Template editor modes: browse templates, view subquests of a template, create new template, add subquest, edit dependencies within a template, add from premade library.
- Press `u` on a template to **instantiate** it: this creates a real overquest + subquests in the character's live quest list (quests.json) with fresh UUIDs and proper dependency linking.
- The quest screen (Active/Completed tabs) only shows instantiated quests — never templates.
- Premade templates: Fitness Foundation, Knowledge Seeker, Social Butterfly, Daily Discipline, Creative Sprint.

# Items design
- Items are earned through quest completion, and rolled randomly from a list. Items have ascii sprites, and item rank in {normal, uncommon, rare, epic, legendary} with sprite colours in {white, green, blue, yellow, red}.
- Item rarity drop weights: normal 50%, uncommon 25%, rare 15%, epic 8%, legendary 2%. Higher quest difficulty shifts odds toward rarer items (bonus per tier = tier_index * difficulty * 0.03).
- Items have $IS boosts, generated randomly on generation. Values are floats clamped to abs value in [0, max(5, player_level)].
- Item stat rolls are weighted by the player's current $CS distribution. If a character has high str and low wis, items will tend to roll high istr and low iwis.
- All items have a mix of positive and negative stats. Net total $IS on any item is guaranteed to be slightly positive.
- Rarer items get a multiplier on positive stats: normal 1.0x, uncommon 1.2x, rare 1.5x, epic 1.8x, legendary 2.2x.
- If an item is acquired by a player, its stats are locked in and not changed, even if the player level changes.
- Items belong to a fixed equipment slot. Equipment slots: head, chest, legs, feet, hands, weapon, offhand, accessory (8 total). One item per slot.

# Economy design
- Each character has a coin balance (integer, cannot be negative, starts at 0).
- Items can be sold from the inventory screen by pressing 's'.
- An item's value in coins = abs(sum of all its $IS stats) * tier_multiplier, rounded to nearest integer.
- Tier multipliers: normal=1, uncommon=10, rare=100, epic=1000, legendary=10000.
- Selling an item removes it from inventory and adds its value to the character's coin balance.
- Equipped items can also be sold (they are unequipped and removed).

# Required files and folders
- definitions/ranks.json — Player rank list with $IS thresholds.
- definitions/items.json — General items listing their names, slots, and sprite paths.
- definitions/weapons.json — Weapons listing their names and sprite paths.
- definitions/armour.json — Armour listing their names, slots, and sprite paths.
- definitions/premade_quests.json — Premade quest tree templates (overquest + subquests with dependency refs).
- definitions/stat_tables_male.json — Male age bracket mapping to base stats.
- definitions/stat_tables_female.json — Female age bracket mapping to base stats.
- assets/portraits/ — ASCII character portraits (.txt files).
- assets/items/ — ASCII item sprites (.txt files).
- db/ — Runtime data, organized per character (db/characters/{name}/). Contains character.json, quests.json, quest_log.json, inventory.json, active_quests.json, completed_quests.json, quest_templates.json per character.
- db/config.json — Global configuration (timezone, last_played character).

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
│   │   ├── main_menu.py            # Main menu (Stats/Quests/Quest Editor/Inventory)
│   │   ├── stats_screen.py         # Stat viewing with XP bars
│   │   ├── quest_screen.py         # Quest list, creation, start, complete, pause
│   │   ├── quest_editor.py         # Quest template manager: create, edit, instantiate templates
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
│   │   ├── quest_engine.py         # Quest start/complete/fail + network graph logic
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
│           ├── quest_templates.json
│           ├── inventory.json
│           ├── active_quests.json
│           └── completed_quests.json
└── definitions/
    ├── ranks.json
    ├── items.json
    ├── weapons.json
    ├── armour.json
    ├── premade_quests.json         # Premade quest tree templates for quest editor
    ├── stat_tables_male.json
    └── stat_tables_female.json
```

# Key bindings
| Key | Action |
|-----|--------|
| h / ← | Move left / Back |
| j / ↓ | Move down / Next option |
| k / ↑ | Move up / Previous option |
| l / → | Move right / Select |
| Enter | Select / Confirm / Submit form |
| Esc | Back / Cancel |
| q | Quit application |
| ? | Toggle help overlay |
| / | Search (in lists) |
| n | New (character, quest, or overquest) |
| d | Delete (character, quest, overquest, subquest) |
| s | Start quest (blocked if dependencies not met) |
| c | Complete quest |
| p | Pause/unpause quest (non-recurring only) |
| f | Fold/unfold overquest (toggle subquest visibility) |
| t | Browse premade templates (quest editor) |
| a | Add subquest (quest editor view mode) |
| u | Use/instantiate template into live quests (quest editor) |
| e | Edit dependencies (quest editor) / Switch to equipped tab (inventory) |
| Tab | Next field (form) / Switch tabs (lists) |
| Shift-Tab | Previous field (form) |
| b | Switch to backpack tab (inventory) |
| r | Rank up (stats screen) |
| Space | Toggle selection (stats in quest form, recurrence cycle, dependency toggle) |
| Ctrl+C | Force quit |

# AGENT: Implementation guidance
- Language: Python 3.11+. Do not use pure bash.
- Only external dependency: blessed==1.20.0. Use stdlib for everything else (json, os, uuid, random, hashlib, datetime).
- Use `t.attr + "text" + t.normal` pattern for blessed formatting (not `t.attr("text")` which throws TypeError).
- Remember that this is a work in progress so expect it to be iteratively improved. Set things up accordingly.
- Do not modify vibecoding/spec.md or vibecoding/spec_v2.md.
