# Plan: repeat the mail preview in the "Add to a rule" overlay

## Context

Todo `dc73499f`: the "Add to a rule" dialog (`MailRuleMenu.vue`) hides the open mail behind its backdrop.
When picking field, template and place, the admin can no longer see which mail the values come from.
The dialog shall repeat a short preview of the current mail at the top.

## Findings

- The dialog is in `frontend/src/components/MailRuleMenu.vue` (Teleported to `body`, `.add-to-rule-dialog`), it receives `props.context: MailContext` with `detail` (subject, sender, to, date).
- `MailMessage.vue` renders the same facts as `h2.subject` and the `dl.meta` (From, To, Cc, Date) using `addressList` and `fullDate` from `model/mail-format.ts`.
- `MailChip.vue` is a similar one-liner, but bound to `store.fillContext` and has the detach button, so it is not reused.

## Changes

1. New `frontend/src/components/MailPreview.vue`, props `{ detail: Detail }`: subject (or `(no subject)`), then From, To and Date in a compact `dl`, long values clipped with ellipsis, `aria-label="Current mail"`.
   Uses `addressList` and `fullDate`.
2. `MailRuleMenu.vue`: render `<MailPreview :detail="context.detail" />` right below the `modal-head`, above the Kind select, so it stays visible in both drill-down steps.
3. Styles scoped in the new component, using the existing theme variables, no new global state.

## Tests

- Vitest `__tests__/mail-preview.spec.ts`: renders subject, sender and date, shows `(no subject)` for an empty one.
- Playwright `e2e/mail.spec.ts`: after opening the dialog, `Current mail` region inside the dialog shows the open mail's subject, also after drilling into a rule.
- No new i18n keys (the frontend has no locale files).

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
Update `CLAUDE.md` with one sentence on the preview in the "Add to existing rule" dialog description.
