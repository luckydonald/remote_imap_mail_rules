# Accounts screen shares the account list with the mail store

**Commit style:** Skill `/commit-with-lplp-style` is active, auto-commit following it for this implementation.

## Context

Todo `892f49ef`: "Adding an account is not immediately reflected in the account list."
`AccountsView.vue` keeps its own `accounts` ref and calls `listAccounts()` itself, while the mail browser's account picker reads `useMailStore().accounts`.
After a create, update or delete, only the view's copy is reloaded, so the mail store's list stays old until `MailView` happens to remount and call `loadAccounts()`.
I could not reproduce a stale list on the backend (30 creates, each followed by an immediate `GET`, none missing), so the duplicate list is the cause to remove.
Decision from the user: the Accounts screen uses `useMailStore().accounts` and reloads it properly, no second copy.

## Changes

### `frontend/src/model/mail-store.ts`

Add `refreshAccounts()` to the store and export it.
It is a plain refresh and does not select an account or load folders, unlike `loadAccounts(target)` which stays as the mail screen's start-up.

- Fetch `listAccounts()` and assign `accounts.value`.
- A 401 calls `onUnauthorized()` and returns, like `fail()` does.
- Any other error is rethrown, so the Accounts screen shows it in its own `message` and the mail screen's `error` is not polluted by a screen the user is not on.
- If the selected `accountId` is no longer in the list (deleted), reset the place without touching the other state: `accountId`, `folders`, `folder`, `messages`, `total`, `nextBefore`, `detail`, `selectedUid`, `events`, then select the first remaining account via `selectAccount` when there is one.
  A renamed id (`PUT` with a new `id`) is covered by the same path, the old id is gone and the first account is chosen.
  Reuse the reset lines of `clear()` by extracting them into a small helper rather than copying them.

### `frontend/src/components/AccountsView.vue`

- Drop the local `accounts` ref and the `listAccounts` import, use `const mail = useMailStore()` and read `mail.accounts` in the template.
- `load()` calls `mail.refreshAccounts()`, keeping the `loading` flag and the `Could not load the accounts` message.
- `submit()` and `remove()` keep calling `load()` after the write, which now updates the shared list.
- The accounts already in the store (from the mail screen) show immediately while the first refresh runs.

## Tests

- Vitest, `frontend/src/__tests__/mail-store.spec.ts`:
  - `refreshAccounts` replaces `accounts` with the new server answer and does not load folders.
  - It keeps the selected account and place when that account is still listed.
  - It moves to the first remaining account when the selected one is gone.
  - It calls the unauthorized handler on a 401 and rethrows other errors.
- Playwright, `frontend/e2e/accounts.spec.ts` (first writing it to fail, then fixing): open the mail screen, go to Accounts, add an account, go back to Mail and check the folder picker lists both accounts, without a reload and without waiting on a remount fetch.
  The existing `mockServer` already follows creates, so the new account shows up in the mocked `GET`.
  The mail routes come from `e2e/mail-mock.ts`.
- Existing accounts e2e tests must stay green.

## Docs

`CLAUDE.md`, frontend paragraph: one sentence that the accounts screen and the mail browser share `useMailStore().accounts` and the screen refreshes it through `refreshAccounts()` after every write.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
No backend change, so `uv run pytest` is only run once as a sanity check.
Playwright only, never the claude-in-chrome tools, and never a server with the live account.

## Closing steps (todo-loop)

Tick the box in `ai/todo.md`, `complete_todo(7, 892f49ef-c48d-4744-91c5-b28ca614ae0d)`, re-sync with `--project remote_imap_mail_rules`, tag a backup and rebase the `ai:` commits into one work commit.
