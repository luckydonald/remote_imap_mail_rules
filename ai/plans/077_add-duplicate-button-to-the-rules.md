# Add Duplicate button to the rules.

Todo: `todo:d6f53d4b-60c1-4583-a6bd-b34ae84c0819` (calendar 7, tags mailRules, vue, python, programming).

> Add Duplicate button to the rules.

## Context

The user clarified that the button belongs on the graphical condition blocks, next to `✂ Cut`, `Wrap`, `⤴ Unwrap` and `✕` in the node bar of `ConditionNode.vue`.
The rule list's `⧉` button (`RuleList.vue`, `store.duplicateRule`) already exists and stays as is.

## Findings

- `ConditionNode.vue` renders the node bar and emits `remove` and `unwrap` to its parent `GroupEditor.vue`, which owns the `conditions` array (`remove(index)`, `unwrapAt(index)`).
- Only a node in an all/any list (`removable`) has a slot for a sibling.
  The root and the child of a `not` hold exactly one expression, so there the button is hidden, like `✕`.
- `clipboard.ts` has a private `copyOf` (JSON deep copy); `duplicateRule` in `store/rules.ts` does the same inline.

## Changes

1. `frontend/src/components/ConditionNode.vue`: new emit `duplicate: []`, and a `⧉ Duplicate` ghost button (class `duplicate`, title `Duplicate this block`) after `✂ Cut`, shown `v-if="removable"`.
2. `frontend/src/components/condition/GroupEditor.vue`: `duplicateAt(index)` inserts a deep copy (`structuredClone(toRaw(...))` or a JSON copy, as the code around it does) at `index + 1`; wire `@duplicate="duplicateAt(index)"`.
   One splice is one reactive change, so undo reverts it in one step.
3. `CLAUDE.md`: add one sentence to the cut / paste / unwrap passage about `⧉ Duplicate` (all/any parents only).

No backend change, no new i18n keys (the editor strings are plain English), no schema change.

## Tests

- Playwright in `frontend/e2e/editor.spec.ts`, next to the unwrap test: duplicate a leaf in an all group, expect two equal conditions; duplicate a group, expect an independent deep copy (editing the copy leaves the original); the button is absent on the root.
- Run `yarn test`, `yarn test:e2e`, `yarn lint`, `yarn build` in `frontend/`, and `uv run pytest` from the root.

## Verification

Run the e2e suite (Playwright, never Chrome tools) and check the three cases above.

## Closing

Commit with `/commit-with-lplp-style` ("Closes `todo:d6f53d4b-60c1-4583-a6bd-b34ae84c0819`"), tick the box, `complete_todo` on calendar 7, sync, then rebase into one work commit.
