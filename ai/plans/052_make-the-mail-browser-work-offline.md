# Make the mail browser work offline

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `28440a19-e45a-4c5c-9db5-c9367ce64dc4`: "make it work offline, and cache mails until marked read".

## Context

Today the frontend needs the server for everything except the open mail, which `store/mail.ts` keeps in `localStorage` for a reload.
The decisions from the user:
- The scope includes **queueing actions offline** (mark read/unread, move), replayed when the connection returns.
- The cache holds the unread mails of the folders opened, every mail opened while unread, and the **200 newest INBOX mails of each account**.
- A cached mail leaves the cache once it is marked read (here or on the server), except for the INBOX window, which is a rolling "200 newest" and is kept whether read or not (assumption, flag it in the review).

## Design

1. **App shell**: a hand-written `frontend/public/sw.js` (no new dependency), registered from `main.ts` in production builds only.
   Cache-first for the hashed `/assets/*` files and a network-first `index.html` fallback (the server already answers unknown paths with `index.html`), never touching `/api`.
   The static files stay served by `SpaStaticFiles`, so the worker needs no server change except that `sw.js` must be served from `/` with `Cache-Control: no-cache`.
2. **Mail cache**: new `src/model/offline/db.ts`, a small IndexedDB wrapper (stores `folders`, `pages`, `details`, `queue`), keyed by `accountId`, `folder`, `uid` and `uidvalidity`-free because the API does not expose it.
   Stored are the folder list, the message list pages and the `Detail` of each cached mail (default body options, so remote images stay blocked).
   Attachments are not cached, only their metadata.
3. **Cache policy**: new `src/model/offline/cache.ts`.
   - Every list page and every opened `Detail` is written through on success.
   - After the folders and the INBOX list loaded, a throttled background job (one request at a time, stops when offline or when the user navigates to a mail) fetches the details of the 200 newest INBOX mails per account, and of the unread mails of the folders opened.
   - On every list reload, mails now seen or gone are dropped from the cache unless they are in the INBOX window.
4. **Reading offline**: `mail-api.ts` read calls (`listFolders`, `listMessages`, `getMessage`, `listEvents`) go through one `cachedGet` helper: network first, on a network failure (`TypeError` from `fetch`, not `navigator.onLine`, which lies) fall back to the cache and flag `offline = true`; an `ApiError` (401, 424, ...) is never answered from the cache.
   `useMail` gets `offline` (ref) and shows a banner in `MailView`; the log of a mail is just empty offline.
5. **Offline actions**: `setSeen` and `moveTo` in `store/mail.ts` apply the change locally as today, and when the request fails with a network error they append `{id, accountId, folder, uid, kind, payload}` to the `queue` store instead of showing an error.
   The cache entry is updated the same way (a mail marked read leaves the cache, a moved one is removed).
   A `flush()` runs on the `online` event, on the next successful request and on start; it replays in order, drops an entry on success, on a 404 (mail gone) or on a 409 `actions_disabled` (reported once), keeps it on a network error, stops on 401.
   A queued entry for one mail collapses (read then unread cancels, later move wins).
   The queue length shows next to the offline banner.
6. **Logout** clears the IndexedDB stores together with `clear()` of the store, so mails never outlive the session.
7. `useMail` stays the single place for the logic; `offline/` holds only plain functions, no second Pinia store.

## Files

- New: `frontend/public/sw.js`, `frontend/src/model/offline/{db,cache,queue}.ts`, a banner component (`OfflineBanner.vue`).
- Changed: `frontend/src/main.ts`, `frontend/src/model/mail-api.ts`, `frontend/src/model/store/mail.ts`, `frontend/src/components/MailView.vue`, `src/remote_imap_mail_rules/server/app.py` (headers for `sw.js`), `CLAUDE.md`.

## Tests

- Vitest with `fake-indexeddb` (dev dependency): cache write-through and the policy (200 INBOX window, unread kept, seen dropped), `cachedGet` fallback only on network errors, queue collapse and flush order, 404/409/401 handling, logout clearing.
- `mail-store.spec.ts`: `setSeen` / `moveTo` queue instead of failing when `fetch` rejects.
- Playwright (`mail.spec.ts`, mocked API): load the inbox, switch the context offline (`context.setOffline(true)`), reload, the cached list and mail still open, mark read queues, go online, the request is sent.
- Python: a test that `sw.js` is served with `no-cache`.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`, then `uv run pytest`.
The service worker itself cannot run under Playwright's mocked dev server, so it is checked by a `yarn build` plus `yarn preview` run in one e2e spec.
