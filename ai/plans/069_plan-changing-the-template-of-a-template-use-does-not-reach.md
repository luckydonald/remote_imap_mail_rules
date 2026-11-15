# Plan: Changing the template of a template use does not reach the YAML

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `8d1f240d`: "changing the template in the editor does not update the yml".
The user's repro: add a template use to a rule, save, then pick another template in the use's `Template` select, with an example mail selected.
The YAML stays as it was, and after switching views and back the old template is shown again, so the change never reached `useStore().file`.
The user says it already behaved this way before the "template in template" change, so that commit is not the cause.

## Findings

- The store is fine.
  Throwaway probes showed that changing a use's `ref`, a template's content or its defaults updates `store.yaml`, in file-only and in server mode.
- `TemplateUseEditor.vue` `changeRef()` has two branches.
  Without an example mail it mutates in place (`model.value.ref = ref`), which works because the node is the store's reactive object.
  With an example mail (`store.fillContext`) it assigns the whole model (`model.value = refillTemplateUse(...)`), which emits `update:node`.
- `ConditionNode.vue` (line 186) renders `<TemplateUseEditor :node="node" />` and does not listen for `update:node`.
  `defineModel` on a parent-controlled prop keeps no local copy, so the assignment is lost: the select snaps back, the store keeps the old `ref`, the YAML does not change.
- `AddressEditor` right above it has `@update:node="emit('update:modelValue', $event)"` since `99d6759` (2026-11-05); `TemplateUseEditor` was missed.

## Changes (test first)

1. Red: add a test to `frontend/src/__tests__/components.spec.ts`, in the `template use with an example mail` block, next to `fills a template use created by changing the type`.
   Mount `ConditionNode` with a reactive `all` group holding `{type: 'template', ref: 't1', variables: {}}`, add `t1` and `t2` with the existing `addTemplates`, call `openMail()`, set the `Template` select to `t2`, `flushPromises()`, and assert the node's `ref` is `t2`.
   Run `yarn vitest run src/__tests__/components.spec.ts` and confirm it fails for this reason (the `ref` stays `t1`), then commit nothing yet.
2. Green: in `frontend/src/components/ConditionNode.vue` add `@update:node="emit('update:modelValue', $event)"` to `<TemplateUseEditor>`.
   Rerun the test and see it pass.
3. Sanity: temporarily revert the one line (stash) to prove the test fails again, then restore it.

## Verification

- `cd frontend && yarn test`, `yarn lint`, `yarn build` (type check), `yarn test:e2e` (chromium).
- `uv run pytest` once as the todo-loop's full-suite gate, the backend is untouched.
- `CLAUDE.md` gets one sentence only if useful: an editor that assigns its whole model needs its `update:node` forwarded by `ConditionNode`.

## Close

Tick the todo, `complete_todo(7, 8d1f240d-2fde-4768-a2e4-3f78e79eceaa)`, sync with `--project remote_imap_mail_rules`, tag the backup, rebase into one work commit and verify `git diff <bak-tag> HEAD` is empty.
