# Plan: "New token" form becomes an overlay of its own

**Commit style:** Skill `/commit-with-lplp-style` is active, auto-commit following it for this implementation.

Todo `724a7f97-b485-4c53-8365-c55f974adf98`: "new token is an overlay of its own".

## Context

In `frontend/src/components/McpTokens.vue` the "New token" form (name, presets, scope checkboxes) sits inline under the token list, and the shown-once token is an inline box above the list.
The form is long, so on the settings page it pushes the page around.
The todo asks for it to be a dialog (overlay) of its own, like the other dialogs of the app.

## Findings

- The app's dialogs share `.modal-backdrop` / `.modal` (`frontend/src/styles/main.scss:1276`), wrapped in `<Teleport to="body">` because Safari on an iPad clips fixed dialogs to scrolling panes (see `ConfirmUnwrap.vue`, `ConfirmLogout.vue`, `MailRuleMenu.vue`).
- Existing tests: `frontend/src/__tests__/mcp-tokens.spec.ts` (mounts `McpTokens`, uses `wrapper.find('form')`, `input[type=text]`) and `frontend/e2e/mcp-tokens.spec.ts` (fills the form directly on `/settings/general`).
  A Teleported dialog is not inside `wrapper.element`, so the unit test needs `attachTo: document.body` and `document.body` queries.

## Changes

1. `McpTokens.vue`:
   - Add a `+ New token` button next to the `Tokens` heading that sets `dialog = true`.
   - Move the `<form class="token-form">` into `<Teleport to="body"><div v-if="dialog" class="modal-backdrop" @click.self="close"><div class="modal" role="dialog" aria-modal="true" aria-label="New token">`, with a `Cancel` button beside `Create token` in a `<footer>`; Esc closes it too.
   - The `h3` "New token" becomes the dialog title.
   - `create()` closes the dialog on success and still sets `created`; on error the dialog stays open and the error shows inside it (`role="alert"`).
   - Closing the dialog (Cancel, backdrop, Esc) resets name and scopes.
   - The shown-once token box stays inline (it must remain visible after the dialog closed), so that the secret is never lost by a backdrop click.
2. `main.scss` / scoped style: only if the scope fieldsets need adjusting inside `.modal` (the modal is 480px wide, `max-height: 80vh` scrolls); no new global classes otherwise.
3. Tests:
   - Unit: update `mcp-tokens.spec.ts` to open the dialog first, mount with `attachTo: document.body`, query the form through `document.body`, and add a case that Cancel closes it and clears the fields.
   - E2E: update `e2e/mcp-tokens.spec.ts` to click `+ New token` first, and assert the form is gone after creating and that the dialog is a child of `body`.
4. `CLAUDE.md`: one clause in the `McpTokens.vue` mention that the creation form is a Teleported dialog.

## Verification

- `cd frontend && yarn test`, `yarn lint`, `yarn build`, `yarn test:e2e` (the `mcp-tokens` spec at least, full run if time allows).
