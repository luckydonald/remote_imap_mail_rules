# Unwrap button for condition groups

Todo `13b0300c-4b40-46a5-8ccf-ec53d75f4fa4`: "unwrap button — delete on a wrapping element asks if we should keep the children".

## Context

The condition editor can wrap a block in `not(…)`, `all(…)` or `any(…)` (`wrap()` in `frontend/src/components/ConditionNode.vue`), but there is no way back.
The `✕` on a group removes it together with all its children, without asking.
So a mistaken wrap has to be undone by cutting and pasting every child.

## Findings

- `ConditionNode.vue` renders the node bar (type select, From mail, Cut, wrap buttons, `✕` when `removable`) and emits `update:modelValue` or `remove`.
- A group's children live in `condition/GroupEditor.vue`, which owns `remove(index)` (splice) and passes `removable` to each child `ConditionNode`.
- The parent group can only splice several children into itself, so the "keep children" logic for a removable group must live in `GroupEditor.vue`, next to `remove`.
- The root and a `not` child are not `removable`; they are replaced through `update:modelValue`.
- Dialogs: `.modal-backdrop` / `.modal` with `<Teleport to="body">` (see `MailMoveMenu.vue`), no `confirm()` anywhere.
- Undo is automatic for edits of the document (the store watches it), no extra `batch` needed for one mutation.

## Behaviour

1. A new `Unwrap` button (`⤴ Unwrap`, title "Replace this group by its children") in the node bar, shown only for `all`, `any` and `not` groups, beside the wrap buttons.
2. `Unwrap` replaces the group by its children without asking:
   - In a group parent (`removable`): the children are spliced into the parent at the group's position.
   - At the root or as a `not` child (single slot): only possible when the group has exactly one child, which then replaces the group. With several children the button is disabled with the title "Only a group with a single condition can be unwrapped here", since one slot cannot hold several conditions (wrapping them is what the group is for).
3. `✕` on a group that has children asks in a dialog: **Keep the children** (same as Unwrap), **Remove all** (old behaviour), **Cancel**.
   - A group with no children, and every non-group condition, still removes straight away.
   - For a group in a single slot (not removable) there is no `✕`, so nothing changes there.
4. The dialog is a small teleported modal, `ConfirmUnwrap.vue`, reusing `.modal-backdrop` / `.modal`.

## Implementation

- `ConditionNode.vue`:
  - New emit `unwrap`, computed `children` (the group's child expressions: `conditions`, or `[condition]` for `not`), computed `canUnwrap`.
  - `unwrap()`: if `removable` emit `unwrap` (parent splices), else if one child emit `update:modelValue` with it.
  - `✕` on a group with children sets `asking = true` and shows the dialog, whose buttons call `unwrap()` or `emit('remove')`.
- `condition/GroupEditor.vue`: handle `@unwrap` of each child with `unwrapAt(index)`, which splices the child's children in place of it (`conditions.splice(index, 1, ...kids)`, kids read from the child group).
- New `components/ConfirmUnwrap.vue` (props `count`, emits `keep`, `remove`, `cancel`), a Teleport modal with `role="dialog"`.
- No backend, schema or i18n change (the editor has no locale files).
- `CLAUDE.md`: add a sentence to the `frontend/` bullet about Unwrap and the `✕` question next to the cut/paste sentence.

## Tests

- `__tests__/components.spec.ts` (ConditionNode / GroupEditor mounts):
  - Unwrap of a nested `all` with two children inside an `any` splices both at the right position and keeps the order.
  - Unwrap of a `not` child at the root with one child replaces the root; disabled with a group of two at the root.
  - `✕` on a group with children opens the dialog; "Keep the children" splices, "Remove all" removes, "Cancel" changes nothing; `✕` on a leaf or an empty group removes at once.
- `e2e/editor.spec.ts`: wrap a condition in `all(…)`, unwrap it, check the YAML view is back to the original.

## Verification

- `cd frontend && yarn test && yarn lint && yarn build`, then `yarn test:e2e` (editor spec, Chromium).
- No Python change, so `uv run pytest` is only run once as a sanity check.
- Close per todo-loop without sync or MCP as requested: tick the checkbox in `ai/todo.md`, skip `complete_todo` and the sync script, then tag the backup and rebase into one commit.
