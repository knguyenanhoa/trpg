# Overview
- Add factions to the game. This would mirror organizations in real life.
  Factions can award writs and medals, and have their own quest lines. This
  mirrors qualifications/tests from organizations in real life.

# Object design guidelines
- Factions have their own set of items called relics. Relics are separate from
  normal items (separate model, db) as they award character stats, not item
  stats. Relics also have high stat modifiers.
- Relics cannot be sold or deleted.
- When creating a quest over overquest in the quest editor, allow specifying
  the faction to which it relates. Both overquests and quests are allowed to
  belong to a faction. Single faction quests behave like normal quests.
- When specifying a faction for an overquest, you can optionally specify
  specific stats that the corresponding relic drop will increase. Only
  overquests can drop relics.
- When a faction overquest is completed, it is guaranteed to drop a relic.
- Factions track the number of quests you have completed for them.
- Factions cannot be deleted, only moved to inactive. They can be restored at
  any time.

# UI design guidelines
- Faction editor. Display active and inactive factions separately.
- Faction quests display in the same space as normal quests.
- Faction quests and overquests are coloured purple.
- Relics do not have to be equipped to have an effect.
- Relics show in a separate tab in the inventory menu, in purple.
