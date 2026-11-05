# Plan: "Add to existing rule" supports templates

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `587d8daf`: the `Rule ▾` > "Add to existing rule …" dialog (`MailRuleMenu.vue`) only adds plain conditions.
A rule may also hold a template use (`{type: 'template', ref, variables}`), see `rules/rules.example.yml` (`anonaddy-forward`).
The dialog should let the user add a use of a template, with the variables filled from the open mail.
Which field a variable belongs to follows from where `{var: name}` sits in the template's `content`: a leaf with a concrete `field` / `part` and a `value` that is a `Var`.
The `address` fill (`fillAddress`, granularity) already exists from the prior todo.

Note: todo sync did not run this time (`SYNC_TODO_MCP_*` unset, `sync_todo` MCP down), so the todo file is as of the last sync.

## Changes

1. `frontend/src/model/fill-from-mail.ts`: new `templateUseFor(ref, def, ctx): TemplateUse | null`.
   - Walk `def.content` (groups recursively, `not` too).
   - For each leaf whose `value` is a `Var`, and whose other discriminating props (`field`, `name`, and for address `part`) are concrete, call `fillExpression(leaf-with-value-emptied, ctx, part)` and take the resulting `value` as `variables[var.var]`.
   - A variable used by several leaves keeps the first value found.
   - Variables that cannot be derived (field itself a `Var`, mail lacks the value) are left out, so the template default applies.
   - It always returns the use with the `variables` that were filled, and the editor's variable check flags any still unbound.
   - Extend `appendCondition` call sites unchanged: a `TemplateUse` is an `Expression`, so it appends like any condition.
2. `frontend/src/components/MailRuleMenu.vue`: a new first select "Add" with `Condition` (default) / `Template`.
   - With `Template`: a select of `rules.file.templates` keys replaces the field / part selects, plus a hint line listing the variables that will be filled and their values.
   - `addTo` builds the use through `templateUseFor` and appends it with the same `appendCondition(..., path)`.
   - The "Add to existing rule" menu item stays enabled by rules; the `Template` option is disabled when `templates` is empty.
3. Tests.
   - `frontend/src/__tests__/fill-from-mail.spec.ts`: `templateUseFor` with the anonaddy template (address part and name filled, default kept when the mail has no name), a variable used twice, a `Var` field leaves the variable unset, unknown template.
   - `frontend/e2e/mail.spec.ts`: add to an existing rule as a template in the dialog and check the resulting use in the editor (reuse the existing "Add to existing rule" test setup).
4. `CLAUDE.md`: one sentence under "Fill from mail" about adding a template use and how variables are derived.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`, plus `uv run pytest` untouched (frontend only).
