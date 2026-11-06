# Track template variable renames in the GUI editor

## Context

A template variable has no rename action.
Its name is the `{var: name}` marker inside the template's `content`, edited through the name input in `FieldValue.vue` (one `update:modelValue` per keystroke).
Editing it silently breaks every use (`{type: template, ref, variables: {old: ...}}` in rules and other templates) and leaves a stale default, which the validator then reports as "template has no such variables".
The request: notice the rename, do not rename the dependents yet, show a red box that asks whether to rename the usages, and collapse it to a chip when dismissed.

## Design

**Detection** (in a new Pinia store `frontend/src/model/renames.ts`, `useRenames()`, per the Pinia-not-inject rule):
- State: `pending: Record<templateName, Array<{from, to, include}>>` and `collapsed: Record<templateName, boolean>`. `from` is the name as the variables stood when tracking began, `to` the current name.
- `observe(template, before, after)` takes the sorted `templateVariables()` before and after a change.
  Exactly one name gone and one added is a rename.
  If the gone name is the `to` of a pending entry, update that entry's `to` (typing `foobar` letter by letter is one chain, not six renames).
  If `to` becomes equal to `from`, drop the entry (reverted).
  Anything else (a name added or removed alone, or a variable that still occurs elsewhere in the content) is not a rename and only prunes entries whose `from` is no longer expected.
- Driven by a `watch` in `TemplatesView.vue` on `templateVariables(store.file, name)` per template.
  Undo/redo/load/switching documents would show up as spurious renames, so `store.restore`, `load` and `switchTo` clear the pending state (expose `reset()`), and the watch is skipped while `store` is applying a history step.
- `store.renameTemplate` moves the pending and collapsed entries to the new template key.

**Applying** (`store.renameVariables(template, pairs)` in `model/store.ts`, one undo step through a small `batch(fn)` helper that suppresses the per-mutation history watcher and pushes a single entry):
- Walk `file.rules` and `file.templates` (reusing the `walkUses` pattern from `validate.ts`, exported; the `fix` walk in `renameTemplate` is the model) and, for every use with `ref === template`, rename the key in `variables`.
- Rename the key in the template's own `defaults`.
- Skip a pair when the target name is empty or already a variable of the template.
- `countUsages(template, from)` (also in the store, next to `usesOf`) counts uses whose `variables` hold `from`; this is the badge number.
  The default is renamed together but not counted.

**UI** (`frontend/src/components/TemplateRenameBox.vue`, placed in `TemplatesView.vue` under the template header, before "Variables"):
- Open, one rename: red box with `<h4>Renaming variable</h4>`, `<code>blah</code> → <code>foobar</code>` with the count badge, then "Do you want to rename (12) usages?" and `<kbd>Yes</kbd> <kbd>No</kbd>`, plus an `✕` in the top right.
- Open, several: `Renaming variables`, a bullet per pair with the badge and a `<kbd>✓</kbd>` toggle (`include`), then "Do you want to rename all (16) usages?", where the number sums the checked pairs.
- `No` and `✕` collapse to the chip `( ▾ rename (12) )` (total of all pending), clicking the chip opens the box again.
- `Yes` applies the checked pairs, clears them, and the box disappears; unchecked pairs stay pending.
- The count badge is an Apple-style notification badge: a small filled round pill beside the text, not a superscript (new `.count-badge` rule in the existing SCSS, using the existing red/error colour tokens).
- `Yes` is disabled while a target name is empty (mid-typing).
- A count of 0 still shows the box, since the default is renamed too.

## Tests

- `src/__tests__/store.spec.ts`: `renameVariables` renames `variables` keys in rules and nested template uses and the default, in one undo step; `countUsages`.
- `src/__tests__/renames.spec.ts` (new): chain `a → ab → abc`, revert drops the entry, add/remove alone is no rename, `reset`.
- `src/__tests__/components.spec.ts`: the box states (single, multiple with a toggled ✓, collapse via No and ✕, Yes applies).
- `e2e/editor.spec.ts`: rename a variable in the Templates view, see the box with the count, collapse it, expand it, say Yes, and check the rule's template use in the YAML view.
  Run with Playwright (never the Chrome tools).

## Docs

Add a sentence to the Templates paragraph of `CLAUDE.md` (frontend section) about the pending-rename box and `useRenames`.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
