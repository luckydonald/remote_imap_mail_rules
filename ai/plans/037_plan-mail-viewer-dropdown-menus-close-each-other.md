# Plan: mail viewer dropdown menus close each other

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `e5b32090-adbc-4b99-9dd6-7b990a41ebdf`: in the mail viewer the `Move ▾` and `Rule ▾` dropdowns overlap and don't close each other.
Cause: `MailMoveMenu.vue` and `MailRuleMenu.vue` each keep a private `const open = ref(false)`, close only through Esc inside their own `.menu` element or by choosing an item, and nothing closes a menu on an outside click.
So both can be open at once, and a menu stays open when the user clicks elsewhere.

## Approach

A new Pinia store `useMenuStore` in `src/model/menu.ts`, following the rule of Pinia stores instead of provide/inject for global state.
It holds `openId: string | null` and offers `isOpen(id)`, `toggle(id)`, `close(id?)`.
Opening one menu replaces `openId`, so every other menu is closed by definition.

Each menu uses a computed `open` backed by the store (`get: () => menus.openId === 'move'`, `set: (v) => v ? menus.open('move') : menus.close('move')`), so the template and the existing `open = false` assignments stay as they are.
Ids: `'move'` in `MailMoveMenu.vue`, `'rule'` in `MailRuleMenu.vue`.

Outside click closes the open menu: a small composable `useMenuDismiss(id, root)` in `src/model/menu.ts` registers a `pointerdown` listener on `document` in `onMounted` and removes it in `onBeforeUnmount`.
It closes the menu when it is the open one and the event target is not inside the `.menu` root element (template ref).
The teleported dialogs are not inside `.menu`, but the menu is already closed when they open (`open = false` on the item click), so they are unaffected.
Esc handling stays as is.

## Files

- `frontend/src/model/menu.ts` (new): the store and `useMenuDismiss`.
- `frontend/src/components/MailMoveMenu.vue`, `MailRuleMenu.vue`: use the store, add `ref="root"` on the `.menu` div.
- `CLAUDE.md`: one sentence in the frontend line that the dropdowns share `useMenuStore`, one open at a time, outside click closes.

## Tests

- Vitest `src/__tests__/menu.spec.ts`: opening `rule` closes `move`; `toggle` of the open one closes it; `close('x')` does not close a different open menu.
- Playwright `e2e/mail.spec.ts`: open `Move ▾`, then `Rule ▾`: only one `.menu-pop` is visible; click on the message body closes it; Esc still closes.

## Verification

`cd frontend && yarn test`, `yarn lint`, `yarn build`, `yarn test:e2e` (the mail spec), then `uv run pytest` for the CLAUDE.md-sync tests.
