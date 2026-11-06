# Cut and paste rule blocks in the rule editor

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `b0b026ed-854d-4de5-a098-067ceffb5536`: a condition block of a rule's `when` tree (or of a template's `content`) can only be added, edited, wrapped or removed.
It cannot be moved to another group or another rule.
The request is cut for any block at any level (including its sub-blocks), kept in Pinia and also copied as YAML to the real clipboard, and paste wherever a new sub-block can be added, which reads the text clipboard first.
Both clipboard directions get a user setting, because the write can spam clipboard history managers and the read can spam permission prompts.

The todo says "rule blocks", and the editor's blocks are the `Expression` nodes rendered by `ConditionNode.vue`.
Whole rules already have duplicate, move and remove in `RuleList.vue`, so they are out of scope.

## Design

**Clipboard state** (new setup store `useClipboardStore` in `frontend/src/model/clipboard.ts`, Pinia used directly per file as the project requires, no provide/inject):
- `block: Expression | null`, the last cut block as a deep copy, kept for the session only.
  It stays after a paste so one cut can be pasted several times, and it is replaced by the next cut.
- `cut(expr)`: stores `structuredClone`-style deep copy (`JSON.parse(JSON.stringify(...))`, as `duplicateRule` does) and, when the setting is on, writes `stringifyExpression(expr)` with `navigator.clipboard.writeText`.
  A rejected or missing clipboard API is swallowed, since the Pinia copy still works.
- `read(): Promise<Expression | null>`: when the read setting is on, tries `navigator.clipboard.readText()`, parses it with `parseExpressionText`, and returns the result when it is a valid expression.
  Anything else (permission denied, no API, empty, text that is not a rule block) falls back to `block`.
- `canPaste`: true when `block` exists or the read setting is on, so the Paste button shows even when only the real clipboard may hold something.

**YAML round trip** (`frontend/src/model/yaml-io.ts`, next to `parseRules` / `stringifyRules`):
- `stringifyExpression(expr)` dumps one expression as YAML.
- `parseExpressionText(text)` parses YAML and accepts it only when it is an object with a known `type` from `expressionTypes` in `catalog.ts`, then checks it with the same ajv schema validation used for rules (`validate.ts`, wrapped in a minimal rule file so the existing schema is reused and not forked).
  Invalid YAML and invalid blocks return `null`, never throw.
- Template variables (`!var`) and template uses survive through the existing yaml-io tag handling.
  A pasted block with `Var` markers into a rule is flagged by the existing template variable check, as typing one would be, and `ALLOW_VARS` already limits where they can be edited.

**Store operations** (in `useStore`, `model/store.ts`, so each is one undo step):
- Cut removes the block from its parent and pastes need the parent too, so `ConditionNode` stays dumb and the group editor does the splice, as `GroupEditor.remove` does today.
  The cut itself is therefore a `ConditionNode` event `cut` that its parent handles as `clipboard.cut(model.conditions[index])` followed by `remove(index)` inside `store.batch`, which makes it a single undo step.
- The root of a `when` or a template's `content` has no parent.
  Cut there copies the block and replaces it with `newExpression('text')`, since a rule needs a `when`.

**UI**:
- `ConditionNode.vue` node bar: a `✂ Cut` ghost button beside the wrap buttons (always visible, also on the root), emitting `cut`.
- `GroupEditor.vue`: a `Paste` button next to `+ Add condition`, shown when `clipboard.canPaste`.
  On click it calls `clipboard.read()`, then appends the block to the group's `conditions` (for `not`, which holds one child, it wraps the existing child and the pasted block in an `all`, the same rule `appendCondition` in `fill-from-mail.ts` already applies, so reuse that function with the group path rather than a new one).
  When nothing could be read it shows the existing small hint style: "Nothing to paste".
- The root-level block has no `+ Add condition`, because `ConditionNode` for the root is not inside a group.
  Pasting there is out of scope, since a root is always filled and the user pastes into a group, or wraps the root with `all(…)` first.
- Insert points between children are not added, a paste appends at the end of the group, like `+ Add condition`, and the existing wrap buttons and drag-free workflow cover reordering.
- `SettingsView.vue`: a new section "Rule editor" with two `SegmentedToggle`s, "Copy cut blocks to the clipboard" and "Paste from the clipboard", each `On` / `Off`, default On.
  Stored in `usePrefsStore` (`model/prefs.ts`) as `copyToClipboard` and `readClipboard` (booleans) next to the existing localStorage keys, with the same defensive read.
- Styles: reuse `.ghost` and `.add` from `styles/main.scss`, no new tokens.

## Files

- New: `frontend/src/model/clipboard.ts`.
- Changed: `model/yaml-io.ts`, `model/prefs.ts`, `components/ConditionNode.vue`, `components/condition/GroupEditor.vue`, `components/SettingsView.vue`, `CLAUDE.md` (a short bullet on cut and paste under the frontend layout).

## Tests

- `src/__tests__/yaml-io.spec.ts`: `stringifyExpression` / `parseExpressionText` round trip for a nested `all` with `not`, an address condition with `part`, and a template use; invalid YAML, an unknown `type` and a valid YAML scalar all return `null`.
- `src/__tests__/clipboard.spec.ts` (new): `cut` stores a copy and writes YAML to a faked `navigator.clipboard`, with the setting off it writes nothing, `read` prefers valid clipboard text, falls back to the store when the text is not a block or reading rejects.
- `src/__tests__/components.spec.ts`: cutting a child of a group removes it and one undo restores it; paste appends to an `all` / `any`, wraps in `all` for a `not`, a root cut leaves a default text condition, and the Paste button follows `canPaste`.
- `e2e/editor.spec.ts`: cut a nested group in rule A, open rule B, paste it, and check the YAML view; grant clipboard permissions for the Chromium project only, and check with the settings toggled off that the clipboard is untouched.
  Verify with Playwright, never the Chrome tools.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`, then `uv run pytest` is not needed since no backend file changes.

## Not done in this task

CalDAV completion and the `sync_todos.py` run: the `sync_todo` MCP server and `ai/.env` are missing in this session, so the todo is ticked in `ai/todo.md` only, and `complete_todo` plus the sync have to be run afterwards.
