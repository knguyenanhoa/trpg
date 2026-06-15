# Overview
This is a TUI RPG for real life, so anyone can create a character, define their starting stats and level up through achieving and recording real-life goals and objectives.

# Overall game design
- Based on DnD style games but reduced scope.
- Select character or create with name, age, sex and stats. Stats should be manually entered or estimated by table lookup (male/female and age map to stats with minor random variation).
- A back story for the character is optional. The character should be given an ascii portrait from a predefined set. Allow the player to specify the colour of the portrait.
- Stats are tracked per player, and are increased by completing quests.
- Quests are self designed and assigned. Quests record difficulty, recurrence type and stat types.
- The main activities the player will be doing in the game are: stat viewing, quest viewing and creation, quest completion, inventory management and item equipment.

# Stats and player progression design
- 2 types of stats: character stats ($CS) and item stats ($IS).
- $CS increase by 1 point when enough experience has been accumulated via quest completion. The amount of experience required a function of the current stat value (please suggest a function).
- $CS is in the list {str, dex, con, int, wis, cha}.
- $IS is in the list {istr, idex, icon, iint, iwis, icha}.
- $IS only depend on items equipped.
- Character level is the average of all $CS points (can be a float), not $IS.
- When every $CS reaches a minimum of 100, the player may choose to "rank up". Ranks are pulled from a list and enumerated. A player is able to rank up to a specific rank if their $IS total meets the minimum required for a certain rank.
- Experience for stats can increase and decrease. If it decreases below 0, it reduces the stat to the previous level. The experience at the reduced stat level should be calculated by taking the max experience for that level, subtracting any left over resulting from the decrease in experience i.e. experience decrease and increase carry over to previous or next stat levels.

# Quests design
- Quests can be started manually by a player.
- Quests can define certain $CS that, upon completion, will grant experience towards those stats. The amount of experience depends on the quest difficulty.
- Quest difficulty is recorded as a float from 0.0 to 5.0. Experience granted should be calculated as a function of the difficulty value (please suggest a function).
- Quest recurrence are of the types none, daily, monthly and should recur automatically.
- Completed quests should be tracked in a log for the character, with completion time and duration. Recurring quests are to be tracked separately per occurance, not grouped.
- Recurring quests, if missed, should be marked as failed.
- Failed quests reduce experience by 1/10th of the experience that would have been gained had the quest succeeded.

# Items design
- Items are earned through quest completion, and rolled randomly from a list. Items have ascii sprites, and item rank in {normal, uncommon, rare, epic, legendary} with sprite colours in {white, green, blue, yellow, red}.
- Items have $IS boosts, also generated randomly on generation. Values are floats from -100.0 to 100.0.
- Item stat rolls are limited by player level, and its absolute value cannot exceed current player level.
- All items have a mix of positive and negative stats.
- If an item is acquired by a player, its stats are locked in and not changed, even if the player level changes.

# Required files and folders
- Player rank list.
- Items file listing their names and their related stats.
- Weapons file listing their names and related stats.
- Armour file listing their names and related stats.
- Male age mapping to stats.
- Female age mapping to stats.
- assets/ folder to hold ascii assets.
- db/ folder to hold data. This should hold files of data for characters and should be organized per character.
- definitions/ folder to hold definition files such as those listed above.

# Architecture and required tech stack
- The architecture should contain as few as possible dependencies. Dependencies should be to address security concerns e.g. do not implement hashing algorithms yourself, but use a library. Dependencies should be as atomic as possible i.e. only does 1 thing.
- Database should be implemented in a folder called db/, and should be text based only such as json or plain text.
- Create functions to work with these files. Do not use something like MySql.
- Local-first, no networking required.
- TUI with vim-like movement. Map the key "?" to a help screen, accessible from any screen, listing key mappings. Do not support custom key binding.
- I suggest a similar approach to FZF where selectable lists are shown in separate floating window. I further suggest using FZF to pipe list input so you can search the list and select as necessary.
- Assets (such as ascii sprites) should be under the folder assets/.
- The app should terminate on Ctrl + C or the key "q".
- Must support colours.

# Overall design principle
- All files should be named with underscore format e.g. sample_file.txt
- Any user input must be properly sanitized and type checked e.g. disallow string in a stat, these should be integers or floats.
- Player input of any kind must not contain special characters. When it is used internally as variables or file names, make sure it is sanitized and converted properly.
- Properly consider security. Disallow executing custom scripts anywhere in the app.
- Properly consider performance.
- 

# Planning requirements for review before implementation
- Please suggest the language to use such as python or ruby. Do not use pure bash.
- Suggest the project file structure.
- Review the rules for levels, experience, stats, and highlight and potential imbalances along with suggestions to fix.
- Remember that this is a work in progress so expect it to be iteratively improved. Set things up accordingly.
- Ask at least 3 questions to clarify requirements.

# Do not modify this file