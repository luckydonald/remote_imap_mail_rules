# Do not load the email before the folders and mails lists are loaded

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `dfab6abb-e7ad-41d5-82e9-343040e8b23d` (project: this repo, `ai/todo.md`).

## Context

When the browser reopens a mail (reload, deep link `/mail/<account>/<folder>/<uid>`, back button), the mail is fetched at the same time as the first page of the message list.
The folders list is already loaded by then, but the list and the mail race each other, so the mail can appear before the list around it.
The wanted order is: folders, then the message list, then the mail.

## Findings

- `selectAccount` in `frontend/src/model/mail-store.ts` already awaits `listFolders` before it calls `selectFolder`, so the folders are in first.
- `selectFolder` runs `await Promise.all([loadMore(), uid === null ? undefined : openMessage(uid)])`, which starts the mail request in parallel with the list request.
- `goTo` for the same account reaches `selectFolder` too (folders are known there), and a plain `goTo` with only a new `uid` calls `openMessage` directly, which is fine because the list is already shown.

## Change

- In `selectFolder`, await `loadMore()` first and call `openMessage(uid)` afterwards, so the mail request only starts once the list page is in.
- A failing list does not stop the mail from opening, since `loadMore` reports its own error and does not throw.
- Guard against a stale choice: after the list is awaited, return if `folder.value !== name` (the user picked another folder meanwhile), so the old folder's mail is not opened.

## Tests

Add to `frontend/src/__tests__/mail-store.spec.ts`: restore a saved place (or `goTo` with a `uid`) with a stub server that records the request order, and expect the message request to come after the list request has resolved.
`stubServer` routes by URL, so the test wraps its `fetchMock` calls (or a deferred list response) to check that the mail is not requested while the list is pending.

## Verification

`cd frontend && yarn test`, `yarn lint`, `yarn build`, and `yarn test:e2e -- mail.spec.ts` (Playwright mocks the API).
No `CLAUDE.md` change needed beyond one clause, if any: the existing sentence about `useMailStore().goTo` stays correct.
