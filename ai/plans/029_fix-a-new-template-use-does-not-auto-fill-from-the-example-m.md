# Fix: a new template use does not auto-fill from the example mail

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `98e90741-4a7d-4d83-a9be-7b78680ed135`: "fix new template not auto-filling from example mail".

## Context

With an example mail open, a new condition starts filled from it.
Choosing the type `template` for a condition does not do that, and neither does a template picked in the "Template" select afterwards.
`templateUseFor(ref, def, ctx)` in `frontend/src/model/fill-from-mail.ts` already fills a template use's variables from a mail (used by the `Rule ▾` > "Add to existing rule" dialog), but the normal editor never calls it.

Root cause, found by reading the code:

- `ConditionNode.vue` `changeType()` makes `newExpression(type, templateNames)` (a template use with `ref` = first template and empty `variables`), then `fillExpression(created, ctx)`.
  `fillExpression` returns template uses unchanged (`default:` branch: "Groups and template uses have no value of their own"), so `variables` stay empty.
- `TemplateUseEditor.vue` binds the `<select v-model="model.ref">` directly, so switching the template never fills the variables either.
- `GroupEditor.vue` `add()` only creates `text`, which is fine.

## Changes

1. `frontend/src/model/fill-from-mail.ts`: `fillExpression` gets a template-use case, since it needs the template definitions, add an optional parameter instead of changing the signature's meaning:
   `fillExpression(expr, ctx, granularity, templates?: Record<string, TemplateDef>)`.
   For `expr.type === 'template'` with a known `templates[expr.ref]`, return `templateUseFor(expr.ref, def, ctx)`, keeping variables already set on `expr` (`{ ...filled.variables, ...expr.variables }` is wrong for a ref change, so only merge in `fillTemplateUse` below).
   Add `refillTemplateUse(use, ref, templates, ctx)`: returns the use with the new `ref` and its variables taken from the mail; variables the user typed by hand for the old ref are dropped, as a different template has different variables.
   Without a context or without the template, the use is returned as it is.
2. `ConditionNode.vue` `changeType()`: pass `store.file.templates` to `fillExpression`, so a new template use starts filled.
3. `TemplateUseEditor.vue`: replace `v-model="model.ref"` with `:value` plus `@change` that calls `refillTemplateUse` when `useMailStore().fillContext` is set (else only sets `ref`, as before).
   One assignment of the node, so it is one undo step.
4. `frontend/src/__tests__/fill-from-mail.test.ts`: cases for `fillExpression` on a template use (filled, unknown template stays as is, no context stays as is) and for `refillTemplateUse` (new ref replaces old variables).
   A component test for `TemplateUseEditor` (changing the select with a mail open fills the inputs) and for `ConditionNode` (type to `template` fills), next to the existing component tests; look at `src/__tests__/` for the nearest one.
5. `CLAUDE.md` "Fill from mail" decision: add one sentence that a new template use and a changed template are filled by `templateUseFor` too.

## Verification

- `cd frontend && yarn test`, `yarn lint`, `yarn build` (type check).
- `yarn test:e2e` for the mail and editor specs, if a spec for the editor with an open mail exists; only mocked API, never the live account.
- No backend change, so `uv run pytest` only as a final full run.
