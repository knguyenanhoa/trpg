# Overview
- This specifies overhauls to quests to support a wider variety of
  quests and mechanics.

# Object design guidelines
- Quests can reference other quests, forming a quest network.
- Any quest can have many other quests referencing it, and itself can
  reference many next quests in the tree.
- An overquest (mark it as such) is a quest that groups other quests
  together and is the end quest of a quest line. If all its dependencies
  are satisfied, then the whole quest line is completed.
- Deleting an overquest deletes all subquests that belong to it, unless
  that subquest also serves in a different quest line.
- New quests can be added to the quest network. Simply specify the next
  quests in the chain. Any quests that used to reference this next quest
  must now reference the inserted quest (standard linked list routine).
- Existing elements of the quest tree can be assigned to a different
  position in the tree using the same principle, specify the next quests
  that it should point to.
- If a quest in a quest network is deleted, its dependencies should be
  reassigned to the next quests in line. If the deleted quest has 2
  dependencies and itself points to 2 other quests, then the 2
  dependencies now point to both new next quests.
- All quests can have the following statuses: {new, in-progress,
  completed, paused}.
- When the end quest is completed, the overquest is also completed and
  this triggers a large reward (large reward modifier).
- Validate that an overquest must have at least 1 quest that belongs to
  it.

# UI design guidelines
- Create a "quest editor" view to create overquests, add/remove
  subquests, specify dependencies.
- The quest editor can also pull from a bank of premade quest trees,
  serving as a template for quick quest making
  (definitions/premade_quests.json). The UI selects the overquest and
  the corresponding quest tree is generated.