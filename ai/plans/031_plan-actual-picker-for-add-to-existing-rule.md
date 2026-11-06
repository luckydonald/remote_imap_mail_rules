# Plan: Actual picker for _Add to existing rule …_

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `a8a6cdf8-c935-4b71-b19c-898cfb094062`.
The `Rule ▾` > _Add to existing rule …_ dialog (`frontend/src/components/MailRuleMenu.vue`) picks the target with two `<select>`s (rule, then group by a label like `any (child 1.2)`), which does not show where in the rule a condition lands.
The todo wants a view of the rules with big empty areas at every insert point that can be clicked, as an overlay, and full screen with a "< back" on mobile.

## Findings

- `appendCondition(when, added, path?)` in `model/fill-from-mail.ts` only appends to the end of a group, `groupsOf` lists the groups with their path.
- The dialog is teleported to `body` (iPad Safari clip, checked by `e2e/mail.spec.ts` "the rule menu is fully visible and its dialog on top"), uses `.modal-backdrop` / `.modal` from `styles/main.scss`, and `addTo()` then opens `/rules/<index>`.
- Other e2e tests (`e2e/mail.spec.ts` template test, `e2e/fill-from-mail.spec.ts` "adds a condition from the mail with the chosen part of the address") use `getByLabel('Kind of condition')`, `.template-fill`, `getByLabel('Field', {exact: true})`, `getByLabel('Part of the address')` and `.add-condition`.
- There is no one-line description of an expression yet.

## Design

Keep the "what to add" part of the dialog (kind, template, field, address part) and replace the two selects by a picker, in the same `.modal` (title and aria-label `Add to a rule` stay).

1. **Insert at an index.** Extend `appendCondition(when, added, path?, index?)` in `model/fill-from-mail.ts`: with an `index` the condition is inserted at that position in the group at `path` instead of appended (clamped).
   For a `not` the index is ignored (it still wraps the child in an `all`, with the new condition after it for index 1 and before it for index 0).
   Existing behaviour without `index` stays.
2. **Describe an expression.** New `describeExpression(expr)` in `model/fill-from-mail.ts`, a one-line text such as `from.address contains "foo"`, `seen = true`, `template by-sender (sender = "x")`, `header X-Foo exists`, groups as `all of 3` / `any of 2` / `not`.
3. **Picker component** `components/RuleInsertPicker.vue` (props: `rules`, emits `pick({ruleIndex, path, index})`).
   - Lists every rule as a card (name, enabled state), its `when` rendered as a nested tree: a group is a bordered box with its type, the leaves are one-line `describeExpression` rows.
   - Between every two children of a group, and before the first and after the last, a tall (about 28px, dashed, `+ Insert here`) button, so an empty group has one big area too. A rule whose `when` is a leaf gets one area before and one after it, which wraps it in an `all` through `path []`.
   - Plain buttons with `aria-label` such as `Insert into <rule name>, <group>, position <n>`, keyboard reachable.
4. **Dialog.** `MailRuleMenu.vue` drops `ruleIndex`, `groupKey`, `groups`, `groupLabel` and the two selects.
   The picker sits under the "what to add" fields, a click on an insert point runs `addTo(target)` (build the condition as now, `appendCondition(rule.when, condition, path, index)`, go to `/rules/<index>`).
   The `Add condition` footer button goes away (the click is the action), `Cancel` stays.
   The `.add-condition` class moves to the insert buttons so the other e2e tests keep working with a click on the first one of the first rule's root group end.
5. **Mobile.** Below 700px the `.modal` becomes full screen (`width/height 100dvh`, no radius) with a `‹ Back` button in a sticky header in place of the footer's Cancel; the picker scrolls inside.
   Overlay, not a new route, so the example mail stays open underneath.
6. The `.modal` stays directly in `body` and without a clipping ancestor, and the `.modal` max-height/overflow stay so the existing e2e check holds. The dialog widens on desktop (`min(720px, …)`) through a modifier class.

## Tests

- Vitest (`src/__tests__/fill-from-mail.spec.ts`): `appendCondition` with `index` (start, middle, end, clamp, `not`, bad path), `describeExpression` for each type.
- Vitest component test for `RuleInsertPicker`: insert points per group count `children + 1`, an empty-ish rule, emitted payload.
- Playwright: update `e2e/mail.spec.ts` (template test and dialog test) and `e2e/fill-from-mail.spec.ts` to the picker, add one test that inserts between two conditions of the second rule and checks the order, and one at 390px width that checks the full-screen dialog and `‹ Back` closes it.
- Full run: `yarn test`, `yarn test:e2e` (Chromium and `webkit-ipad`), `yarn lint`, `yarn build`.

## Docs

Update the "Fill from mail" / `MailRuleMenu` passages in `CLAUDE.md` (the picker, `appendCondition` `index`, mobile full screen). No backend change, no i18n (strings are English literals in this project).

## Out of scope

Drag and drop, moving existing conditions, picking a location inside a template's content.
