# Rule menu: `Select as example mail`

## Context

Todo `181001a3`: add `Select as example mail` to the `Rule ▾` menu of the mail viewer, first in the list.
It is basically _New rule from this mail_, but without creating a rule.
Today the open mail already is the editor's example (`useMailStore().context`), but the chip's × sets `fillDetached`, and only opening another mail attaches again.
So there is no way to attach the same mail again, or to go from the mail screen back to the editor with it as the example.

## Changes

- `frontend/src/components/MailRuleMenu.vue`: new first menu item `Select as example mail` calling `selectExample()`.
  It closes the menu, sets `mail.fillDetached = false` (via `useMailStore()`, used directly as the project does), and `router.push(locationOfView(rules.view))`, like `newRule` and `addTo` do.
  No rule is added and the rule file stays untouched.
- No store change: `fillContext` already follows `fillDetached` and `context`, so the chip in `RuleEditor.vue` shows the mail after the navigation.
- `CLAUDE.md`: one sentence in the "Fill from mail" decision, saying the `Rule ▾` menu's first item re-attaches the open mail and returns to the editor.

## Tests

- `frontend/e2e/mail.spec.ts`: next to `the rule button starts a rule from the mail`, a test that opens the third mail, picks `Select as example mail` and expects the URL to be the rules editor and the rule count unchanged (mock `MOVE_RULES`).
  A second case detaches via the chip's × first, then selects again, and expects the chip back.
- Unit test only if the logic ends up outside the component (it does not).

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`, then `uv run pytest` for the untouched backend.
