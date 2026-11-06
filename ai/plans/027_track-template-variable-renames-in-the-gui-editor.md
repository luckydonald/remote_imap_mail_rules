# Track template variable renames in the GUI editor

## Context

A template variable has no rename action.
Its name is the `{var: name}` marker inside the template's `content`, edited through the name input in `FieldValue.vue` (one `update:modelValue` per keystroke).
Editing it silently breaks every use (`{type: template, ref, variables: {old: ...}}` in rules and other templates) and leaves a stale default, which the validator then reports as "template has no such variables".
The request: notice the rename, do not rename the dependents yet, show a red box that asks whether to rename the usages, and collapse it to a chip when dismissed.

## Design

**Detection** (in the existing rules store `useStore` in `frontend/src/model/store.ts`, next to `usesOf` / `renameTemplate`, no new store):
- State: `pendingRenames: Record<templateName, Array<{from, to, include}>>` and `renamesCollapsed: Record<templateName, boolean>`, as plain refs of the setup store so they live with the document the store already keeps until saving.
  A save does not clear them, since the file is still inconsistent until the question is answered.
- The store already watches `file` for history. Beside that watcher, a sync watcher on each template's `templateVariables()` (from `validate.ts`) compares the sorted names before and after a change.
  Exactly one name gone and one added is a rename.
  If the gone name is the `to` of a pending entry, update that entry's `to` (typing `foobar` letter by letter is one chain, not six renames).
  If `to` becomes equal to `from`, drop the entry (reverted).
  Anything else (a name added or removed alone, or a variable that still occurs elsewhere in the content) is not a rename.
- The watcher is skipped while the store is applying history (`undo` / `redo` / `restore`), and `load`, `switchTo` and `openDocument` reset the pending state, because each of those starts a fresh document.
- `renameTemplate` moves the pending and collapsed entries to the new template key.

**Applying** (`store.renameVariables(template)` applies the included pending pairs, one undo step through a small `batch(fn)` helper that suppresses the per-mutation history watcher and pushes a single entry):
- Walk `file.rules` and `file.templates` (reusing the `walkUses` pattern from `validate.ts`, exported; the `fix` walk in `renameTemplate` is the model) and, for every use with `ref === template`, rename the key in `variables`.
- Rename the key in the template's own `defaults`.
- Skip a pair when the target name is empty or already a variable of the template.
- `countUsages(template, from)` (in the store) counts uses whose `variables` hold `from`; this is the badge number.
  The default is renamed together but not counted.

**UI** (`frontend/src/components/TemplateRenameBox.vue`, placed in `TemplatesView.vue` under the template header, before "Variables"):
- Open, one rename: red box with `<h4>Renaming variable</h4>`, `<code>blah</code> → <code>foobar</code>` with the count badge, then "Do you want to rename (12) usages?" and `<kbd>Yes</kbd> <kbd>No</kbd>`, plus an `✕` in the top right.
- Open, several: `Renaming variables`, a bullet per pair with the badge and a `<kbd>✓</kbd>` toggle (`include`), then "Do you want to rename all (16) usages?", where the number sums the checked pairs.
- `No` and `✕` collapse to the chip `( ▾ rename (12) )` (total of all pending), clicking the chip opens the box again.
- `Yes` applies the checked pairs, clears them, and the box disappears; unchecked pairs stay pending.
- The count badge is an Apple-style notification badge: a small filled round pill beside the text, not a superscript (new `.count-badge` rule in the existing SCSS, using the existing red/error colour tokens).
- `Yes` is disabled while a target name is empty (mid-typing).
- A count of 0 still shows the box, since the default is renamed too.

**Usage side** (`components/condition/TemplateUseEditor.vue`, the editor of a `{type: template, ref, variables}` use):
- Orphan keys: the use's `variables` keys that are not in `templateVariables(store.file, ref)` (the same set the validator reports as "template has no such variables").
  Each gets a red row, shown whether or not a rename is pending, with the stale key and its value, a dropdown of the template's existing variables to rename it to, and a delete button (`🗑`) for a version that is no longer needed.
  When a pending rename `from → to` matches the key, the dropdown is preselected to `to`.
- Store function `store.resolveOrphan(use, key, target)` does the move in one undo step, with three cases:
  - The target is unfilled in the use (absent or empty): the value moves into it and the old key goes.
  - The target already holds a value: the row asks which to keep, as three buttons: the orphan's value (`a`, shown), the target's value (`b`, shown), or `Revert`.
    `Revert` leaves the use exactly as it was, with the stale key still flagged.
  - `store.dropOrphan(use, key)` is the delete button.
- Unfilled means `undefined`, `''` or a missing key, so a variable bound to a `Var` of an enclosing template counts as filled.
- Tests: `store.spec.ts` for the three cases, `components.spec.ts` for the row and the a / b / Revert prompt, and one e2e step after the rename flow where a rule's use is fixed through the dropdown.

## Tests

- `src/__tests__/store.spec.ts`: `renameVariables` renames `variables` keys in rules and nested template uses and the default, in one undo step; `countUsages`.
- `src/__tests__/store.spec.ts`: detection chain `a → ab → abc`, revert drops the entry, add/remove alone is no rename, `reset`.
- `src/__tests__/components.spec.ts`: the box states (single, multiple with a toggled ✓, collapse via No and ✕, Yes applies).
- `e2e/editor.spec.ts`: rename a variable in the Templates view, see the box with the count, collapse it, expand it, say Yes, and check the rule's template use in the YAML view.
  Run with Playwright (never the Chrome tools).

## Docs

Add a sentence to the Templates paragraph of `CLAUDE.md` (frontend section) about the pending-rename box and `pendingRenames` in `useStore`.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
