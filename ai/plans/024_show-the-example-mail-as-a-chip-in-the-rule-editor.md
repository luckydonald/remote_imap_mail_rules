# Show the example mail as a chip in the rule editor

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `7742c27e-221e-4553-90ab-d9cd0029f92f`: _mail_ > _New rule from this email_: Display current chosen mail.

## Context

The rule editor fills conditions from the open mail (`useMailStore().context`), but nothing in the editor shows which mail that is, and the fill cannot be switched off without closing or changing the mail.
The todo wants a chip like `( ✉️ Title of the… | × )` in the rule editor.
The `×` removes the mail from the editor's point of view, which disables all automatic fill again.

## Findings

- `context` in `frontend/src/model/mail-store.ts` is a computed of the open mail (`detail`, `accountId`, `folder`), `null` offline or without an open mail.
- The editor consumers are `ConditionNode.vue` (new type, "From mail" button, part change), `condition/GroupEditor.vue` (add condition) and `condition/TextLikeEditor.vue` (`changeAddress`, header suggestions).
- The mail screens use the same `context` for `MailRuleMenu`, `MailAddCondition` (in `MailMessage.vue`), which must keep working, so the chip must not clear the open mail itself.
- `detail.subject` holds the title.

## Plan

1. `mail-store.ts`: add `fillDetached` (ref, false) and a computed `fillContext` that is `context` unless detached.
   `openMessage` resets `fillDetached` to false (choosing another mail attaches again), `clear` too; add both to the returned object.
   Not persisted.
2. Switch the three editor consumers (`ConditionNode.vue`, `GroupEditor.vue`, `TextLikeEditor.vue`) from `mail.context` to `mail.fillContext`.
   `MailMessage.vue`, `MailRuleMenu.vue` and `MailAddCondition.vue` keep `context`.
3. New `components/MailChip.vue` (props none, uses `useMailStore()`): shows `✉️`, the subject truncated with ellipsis (full subject in `title`), and a `×` button with `aria-label="Do not fill from this mail"`.
   Rendered at the top of `RuleEditor.vue` under the problems list, `v-if="mail.fillContext"`.
   Does not take a prop, per the Pinia convention.
4. After `×` the chip is gone, and the "From mail" button reads "Choose a mail to fill from" because `fillContext` is null.
   Selecting a mail in the panel brings the chip back.
5. SCSS next to the other component styles, using the existing tokens and no new colors.

## Tests

- `src/__tests__/mail-store.spec.ts`: `fillContext` equals `context` after `openMessage`, is null after `fillDetached = true` while `context` stays, and `openMessage` resets it.
- `src/__tests__/mail-widgets.spec.ts` (or `components.spec.ts`): the chip shows the subject, `×` sets `fillDetached`.
- `e2e/fill-from-mail.spec.ts`: open the rule and a mail, chip shows `Subject 3`, removing it makes adding a condition start empty, choosing the mail again shows the chip.
  Also the chip is absent on the phone subpage layout if it does not apply there (check while implementing).
- Run `yarn test`, `yarn test:e2e`, `yarn lint`, `yarn build` and `uv run pytest`.

## Docs

Update the "Fill from mail" paragraph of `CLAUDE.md`: the chip, `fillContext` for the editor versus `context` for the mail screens.

## Close

Tick the box in `ai/todo.md`.
`complete_todo` and the re-sync are blocked until the `sync_todo` MCP and `ai/.env` are fixed, so they are reported at the end instead.
