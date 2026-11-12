# Plan: keep the last "Add to rule" settings in the store

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `340ec332-701e-47da-b60c-73208152b829`: keep the last _Add to rule_ settings (type, e.g. template + which) in the store, to easily add multiple mails with the same field types.

## Context

The `Rule ▾` > "Add to existing rule …" dialog (`frontend/src/components/MailRuleMenu.vue`) keeps its choices in component-local refs: `kind` (condition or template), `templateRef`, `field` and `granularity` (part of the address).
When another mail is opened the menu is recreated or the page changes, and the choices are back at `Condition` / `from` / `address`.
Adding the same kind of condition for several mails therefore means picking it again every time.

## Findings

- The four refs are the only dialog state worth keeping. `pickedRule` stays local on purpose.
- The dialog already copes with a stored choice that does not fit the open mail: `chosen` falls back to the first available field when `field` is not offered for that mail, and `chosenTemplate` falls back to the first template when `templateRef` is gone.
  The stored choice is left untouched in that case, so it comes back for the next mail that has the field.
- Project rule: one central `useStore`, new global state is a plain function file spread in `model/store/index.ts`, with specific names, never a second store or provide/inject.

## Changes

1. New `model/store/add-to-rule.ts` with `useAddToRule()` returning `addToRuleKind` (`'condition' | 'template'`, default `condition`), `addToRuleField` (default `from`), `addToRuleGranularity` (`Granularity`, default `address`) and `addToRuleTemplate` (default `''`).
   Memory only, not persisted: it is a session convenience and a stale choice after a reload would only surprise.
2. `model/store/index.ts`: spread `...useAddToRule()`.
3. `MailRuleMenu.vue`: drop the local `field`, `granularity`, `kind` and `templateRef` refs and use the store values, bound with `v-model="store.addToRuleKind"` and so on; the `computed`s keep their fallbacks.

## Tests

- `src/__tests__/` store unit test: the four values have the defaults and `useStore()` returns the same values after being set.
- `e2e/mail.spec.ts`: pick another field in the dialog, add it to a rule, open the dialog again on another mail and expect the same field (and for a template, the same template) preselected.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`; add one sentence to the "Fill from mail" paragraph of `CLAUDE.md` about the stored choices.
