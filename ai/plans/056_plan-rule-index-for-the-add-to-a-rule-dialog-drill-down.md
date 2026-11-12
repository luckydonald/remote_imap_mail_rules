# Plan: rule index for the "Add to a rule" dialog (drill-down)

## Context

Todo `cbf5477d`: the "Add to a rule" dialog shows every rule as nested boxes under "Click where it should go", so with many rules the list is long.
The todo asked for a table of contents.
The note on this run says a sub menu drill down probably makes more sense, so instead of a ToC above one long list, the dialog gets two steps, like the iOS style settings pages.
Note that `sync_todos.py` failed with "SSE stream ended without a response", so `ai/todo.md` is the last synced state.

## Design

- Step 1, the rule index: a list of buttons, one per rule (name, `(disabled)` hint, `describeExpression` one-liner of the root), under the "Click where it should go" title.
- Step 2, after a click: the dialog shows only that rule's insert picker, with a `‹ All rules` back link.
  The field controls above stay in place in both steps.
- A single rule skips step 1 and opens its picker directly.
- Picking a place still calls `addTo` with `{ruleIndex, path, index}`, closing the dialog.
- The chosen rule is local state of `MailRuleMenu.vue` (`pickedRule: number | null`), reset when the dialog opens.
  It is not global state, so no store change.

## Files

- `frontend/src/components/RuleInsertPicker.vue`: add an optional prop `only?: number`, which renders just that rule, keeping the emitted `ruleIndex` the real one.
  Without it the behaviour is unchanged, so `rule-insert-picker.spec.ts` stays valid.
- `frontend/src/components/RuleIndex.vue` (new, small): the list of rules, emits `open(ruleIndex)`.
- `frontend/src/components/MailRuleMenu.vue`: the `pickedRule` ref, the back button, and the switch between `RuleIndex` and `RuleInsertPicker :only`.
- Styles next to the existing `.insert-*` rules.
- `CLAUDE.md`: extend the sentence about the `Rule ▾` > "Add to existing rule" dialog (picker now reached through a rule list).

## Tests

- Vitest: `RuleInsertPicker` with `only` renders one rule and emits the real `ruleIndex`; `RuleIndex` emits `open`.
- Existing Playwright test for the dialog in `frontend/e2e/mail.spec.ts` is updated for the extra click (choose the rule first), plus a case for the single rule shortcut and the back link.
- Run `yarn test`, `yarn test:e2e`, `yarn lint`, `yarn build` in `frontend/`.

## Open point

Reading the note as "drill down instead of ToC".
If a ToC with anchors was still wanted, say so, as that is a different layout.
