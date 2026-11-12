# Plan: loading spinner and disabled state for mail action buttons

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `fdbbd2c4-d369-4c87-99db-00061eb7d070`: button actions like _Mark read_ shall have a loading spinner, and be disabled until done.

## Context

`store.setSeen` and `store.moveTo` (`frontend/src/model/store/mail.ts`) await a server call, but the buttons in `MailMessage.vue` (`Mark read` / `Mark unread`) and `MailMoveMenu.vue` (`Move ▾` and its menu items) give no feedback while it runs.
A second click during the request sends a duplicate request, and for a move it can act on a mail that is already gone.

## Findings

- `setSeen(seen)` and `moveTo(target)` are the only user-driven write actions of the mail toolbar. Both already handle the offline queue, so "done" means the function resolved.
- There is only `MailSpinner.vue` (a block-level dancing mail with a label), too big for a button. A small inline spinner is needed.
- State belongs in the one central store (`useStore`), composed from `model/store/mail.ts`, so every consumer (full toolbar, any other place offering the same actions) shares it.

## Changes

1. `model/store/mail.ts`: add `busy = ref<'seen' | 'move' | null>(null)` and a small helper `withBusy(kind, fn)` that returns early if `busy` is already set, sets it, runs `fn` and clears it in `finally`.
   Wrap the bodies of `setSeen` and `moveTo` in it, and return `busy` from the composition (it is spread by `store/index.ts`, name `busy` is specific enough: call it `mailActionBusy` to avoid a clash).
2. New `components/ButtonSpinner.vue`: a tiny inline CSS ring (`aria-hidden`, respects `prefers-reduced-motion`), styles in `styles/main.scss` next to `.mail-spinner`.
3. `MailMessage.vue`: the seen button gets `:disabled="!store.actionsEnabled || store.mailActionBusy !== null"`, `:aria-busy`, and shows `<ButtonSpinner v-if="store.mailActionBusy === 'seen'" />` before its label.
4. `MailMoveMenu.vue`: the `Move ▾` button is disabled while busy and shows the spinner for `'move'`, and the menu items are disabled too.

## Tests

- `src/__tests__/mail-store.spec.ts`: `mailActionBusy` is set during a pending `setSeen` / `moveTo` and cleared after, also after a failure, and a second call while busy sends no second request.
- `e2e/mail.spec.ts`: with a delayed mocked flags route, `Mark read` is disabled with the spinner visible, then enabled again with the label flipped.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`; update `CLAUDE.md` (one sentence in the mail view paragraph about `mailActionBusy`).
