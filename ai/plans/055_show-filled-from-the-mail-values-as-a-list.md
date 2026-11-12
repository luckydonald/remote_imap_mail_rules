# Show "Filled from the mail" values as a list

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `ad4bd404`: in the "Add to a rule" dialog with `Template` selected, the filled variables are shown as `<code>` elements inside one `<p class="template-fill">`.
The items run together without whitespace, because the template has no space between the `<code>` elements.
They should be a list with one item per line.

## Change

- `frontend/src/components/MailRuleMenu.vue` (around line 137): keep the `Filled from the mail:` label in the `<p class="template-fill">`.
  Render the variables as a `<ul class="template-fill-list">` with one `<li>` per variable, holding `<code>{{ name }} = {{ value }}</code>`.
  The "Nothing to fill from this mail, the defaults apply." text stays as it is.
- Styling: the list gets no bullets extra padding beyond a small left indent, in the same SCSS place where `.template-fill` is already styled (found by grep before editing).
- A variable value can be an array (the `in` operator), so show it joined with `, `.

## Tests

- `frontend/e2e/mail.spec.ts` ("adds a template use to an existing rule with the variable filled from the mail"): the existing `toContainText('sender = s3@example.com')` still passes.
  Add an assertion that `.template-fill li` has one item containing it.
- No new i18n keys: the UI has no i18n.

## Verification

- `cd frontend && yarn lint && yarn test && yarn build && yarn test:e2e e2e/mail.spec.ts`
- Full backend suite `uv run pytest` stays untouched but is run once, as the todo-loop requires.

## Close

Tick the todo, `complete_todo`, sync, rebase into one commit.
