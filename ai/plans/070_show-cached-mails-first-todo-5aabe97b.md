# Show cached mails first (todo 5aabe97b)

## Context

The folder tree already shows from the IndexedDB cache at once and the server's answer replaces it (`selectAccount` in `frontend/src/model/store/mail.ts`).
The message list and the open mail do not: `loadMore` / `reloadMessages` call `readPage` and `openMessage` / `allow` call `readMail`, which are network first and only use the cache when the network fails.
So on a slow connection the list and the mail stay empty until the server answers, although a copy is on the device.
Goal: show the cached list page and the cached mail immediately, then swap in the server's answer in place.

## Changes

All in `frontend/src/model/store/mail.ts`, reusing `loadPage` and `loadDetail` from `offline/cache.ts`.

- `loadMore` and first page of `selectFolder`: when the list is empty (first page, `before === null`), read `loadPage(id, name, null)` first.
  If it returns a page, the ticket is still current and `messages` is still empty, show it (`messages`, `total`, `nextBefore`) and keep `loading` true until the network answer.
  Then `readPage` replaces `messages`, `total` and `nextBefore` in place (assignment, as `reloadMessages` does), instead of appending, when the cached page was shown.
  Later pages (`before !== null`) stay network first.
- `openMessage`: after resetting state, `loadDetail(id, name, uid)`; if present and the ticket is current, set `detail.value` to it (the pane is already `message`).
  Then `readMail` replaces it when it arrives.
  A failure of `readMail` while a cached detail is shown is silent when it is a network error (`readMail` already falls back to the cache and returns it), otherwise `fail(...)` as today.
- Cached detail was stored with whatever body options were used then.
  Show it only when it does not claim more than allowed now: skip the cached copy if `bodyOptions` wants no remote images / styles but the cached detail has them loaded (check the fields `Detail` has for this; the second todo, `ed3e520a`, covers remembering that and is out of scope here).
- `allow()` is unchanged, it keeps the old body until the new one is in.
- Do not call `touchDetail` for the early read, `readMail` does it on the fallback path and `saveDetail` refreshes on the network path.

## Tests

In `frontend/src/__tests__/offline-store.spec.ts` (has the store with fake IndexedDB and a mocked API), add cases:

- Open a cached mail with a network call that stays pending: `detail` is set from the cache before the call resolves, then replaced by the server's detail.
- Select a folder with a cached page and a pending `listMessages`: `messages` shows the cached page first, then the server's page replaces it (no duplicates).
- Cache empty: behaviour unchanged (nothing shown until the answer).
- Server error (`ApiError`) after showing the cached mail: error is reported as before.

## Verification

`cd frontend && yarn test && yarn lint && yarn build`, plus `yarn test:e2e` for `mail.spec.ts`.
Update `CLAUDE.md` (Offline paragraph: list and open mail show from the cache first, network answer replaces in place).
