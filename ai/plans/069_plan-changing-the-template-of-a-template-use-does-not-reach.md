# Plan: Changing the template of a template use does not reach the YAML

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `8d1f240d`: "changing the template in the editor does not update the yml".
The user's repro: add a template use to a rule, save, then pick another template in the use's `Template` select.
The YAML stays as it was, and after switching views and back the old template is shown again, so the change never reached `useStore().file`.
The user says it already behaved this way before the "template in template" change, so that commit is not the cause.

## Findings

- The store is fine.
  Throwaway vitest probes showed that mutating `rule.when.ref`, a template's content or its defaults changes `store.yaml`, with and without comments, and a Playwright probe in server mode (open the Templates view, change an operator, YAML view, Save) produced the right text and PUT body.
- `TemplateUseEditor.vue` `changeRef()` has two branches.
  Without an example mail it mutates in place (`model.value.ref = ref`), which works because the node is the store's reactive object.
  With an example mail open (`store.fillContext`) it assigns the whole model (`model.value = refillTemplateUse(...)`), which emits `update:node`.
- `ConditionNode.vue` (line 186) renders `<TemplateUseEditor :node="node" />` and does not listen for `update:node`.
  `defineModel` with a parent-controlled prop does not keep a local copy, so the assignment is lost: the select snaps back, the store keeps the old `ref`, and the YAML does not change.
- `AddressEditor` right above it already has `@update:node="emit('update:modelValue', $event)"`.
  It was added in `99d6759` (2026-11-05, address conditions filled from the example mail), and `TemplateUseEditor` was missed.
  Same family: `TextLikeEditor.vue` line 33 and `TemplateUseEditor.vue` line 46 are the only places that assign `model.value` as a whole, the other editors mutate in place.
- Not yet confirmed: whether the no-mail case also fails in the real UI after a save.
  The store probes say it should work, so the reported failure most likely happened with the example mail panel or chip open, which the editor attaches by default whenever a mail was opened before.

## Changes

1. `frontend/src/components/ConditionNode.vue`: add `@update:node="emit('update:modelValue', $event)"` to `<TemplateUseEditor>`, the same as `AddressEditor` has.
   No other file needs a code change.
2. Write the tests first and watch the first one fail before the fix:
   - `frontend/src/__tests__/components.spec.ts`, in the `template use with an example mail` block: mount `ConditionNode` with a template use `{type: 'template', ref: 't1', variables: {}}` under a reactive `all` group, add `t1` and `t2` with `addTemplates`, `openMail()`, change the `Template` select to `t2`, and assert the node's `ref` is `t2` and the select shows `t2`.
   - A second case in the same block without `openMail()`, to settle the unconfirmed point.
     If it fails too, the plan grows by whatever that finds (most likely the object handed to the editor after a save is not the live one), and I will say so before changing more.
   - `frontend/e2e/server.spec.ts`: server mock with two templates and a rule using one, open a mail in the example panel is heavy, so keep this one to the YAML-view round trip only if the component tests do not already cover the reported flow (switch view and back keeps the new template).

## Verification

- `cd frontend && yarn test`, `yarn lint`, `yarn build` (type check), `yarn test:e2e` (chromium; `webkit-ipad` only runs `mail.spec.ts`).
- Backend untouched, but run `uv run pytest` once as the todo-loop's full-suite gate.
- Update `CLAUDE.md` only with one line if useful: components that assign a whole model must have their `update:node` forwarded by `ConditionNode`.

## Close

Tick the todo, `complete_todo(7, 8d1f240d-2fde-4768-a2e4-3f78e79eceaa)`, sync with `--project remote_imap_mail_rules`, then tag the backup and rebase into one work commit.
