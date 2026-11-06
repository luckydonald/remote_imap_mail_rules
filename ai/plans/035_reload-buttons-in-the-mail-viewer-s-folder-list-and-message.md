# Reload buttons in the mail viewer's folder list and message list

## Context

Todo `42311b99`: the mail viewer only fetches folders and messages when it opens, so new mail or changed unseen counts need a full page reload.
The folder list and the message list each get a reload button.
`MailFolders` and `MailList` are shared by the full mail screen and the rule editor's "Example mail" side panel, so both get it without extra work.

## Changes

`frontend/src/model/mail-store.ts`:

- `reloadFolders()`: fetches `listFolders(accountId)` again and replaces `folders.value` (selectable only), keeping `folder` and the open mail.
  Uses `foldersLoading`, ignores the answer if `accountId` changed meanwhile, reports errors through `fail('Could not reload the folders', …)`.
- `reloadMessages()`: reloads the first page of the current folder without clearing the list first, so the view does not flash empty.
  It takes a new `listTicket`, fetches `listMessages(id, name, null)`, then replaces `messages`, `total` and `nextBefore`.
  The open mail (`detail`, `selectedUid`) stays open and is not refetched.
  It sets `loading` for the spinner, and does nothing while `loading` is already true.
- Both are exported from the store.

`frontend/src/components/MailFolders.vue`: a `↻` icon button (aria-label `Reload folders`) at the top of the nav, next to the account select, disabled while `foldersLoading`.

`frontend/src/components/MailList.vue`: a `↻` ghost button (aria-label `Reload messages`) in `.pane-head`, disabled while `loading`.

Small styling in the existing mail SCSS so the button sits right in the header.

## Tests

- `frontend/src/__tests__/mail-store.spec.ts`: `reloadFolders` picks up changed unseen counts and keeps the folder, `reloadMessages` picks up a new mail and keeps the open mail and the selection.
- `frontend/e2e/mail.spec.ts` (Chromium and `webkit-ipad`): click both buttons, the mock changes its answer, the list and badge update.
  `mail-mock.ts` gets a switchable answer if needed.

## Verification

`cd frontend && yarn test && yarn test:e2e && yarn lint && yarn build`.
Update `CLAUDE.md` with one line on the reload buttons.
