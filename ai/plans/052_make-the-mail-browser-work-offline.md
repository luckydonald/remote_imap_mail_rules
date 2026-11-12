# Make the mail browser work offline

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `28440a19-e45a-4c5c-9db5-c9367ce64dc4`: "make it work offline, and cache mails until marked read".

## Context

Today the frontend needs the server for everything except the open mail, which `store/mail.ts` keeps in `localStorage` for a reload.
Decisions so far:
- Actions done offline (mark read/unread, move) are queued and replayed when the connection returns.
- Cached are the unread mails of the folders opened, every mail opened while unread, and the 200 newest INBOX mails of each account.
- Each of these three rules is a toggle in the settings, and the 200 is a numeric field there.
- The cache keeps when a mail was cached and last viewed, so a periodic purge drops mails that no longer fit the rules.
- The INBOX window is a rolling "newest N" and keeps read mails too (assumption, to confirm in review).

## Design

1. **App shell / service worker.**
   Vue has no bootstrap for service workers by itself; the usual choice is `vite-plugin-pwa` (Workbox under the hood), which generates the worker and the manifest from `vite.config.ts` and gives a `virtual:pwa-register` helper.
   Use it with `registerType: 'autoUpdate'` and precache of the build output, `navigateFallback: '/index.html'` with `/api` and `/assets` excluded from the fallback, and `/api` never cached by the worker (the mail cache is ours, in IndexedDB, because it needs rules and purging).
   This avoids hand-writing a worker we would have to maintain.
   Registered from `main.ts` in production builds only.
2. **`uidvalidity` in the API.**
   It is the IMAP folder epoch: a UID is only stable while the folder's `UIDVALIDITY` is unchanged, and if the server recreates or restores a folder the same UIDs can point to different mails.
   A cache keyed by `uid` alone would then show the wrong mail, so it makes sense to expose it.
   The backend already has it (`ImapClient.build_mail` sets `Mail.uidvalidity`); add it to the folder list, the message page and the detail response in `server/api/mail.py` and `mail-api.ts`.
   When the cached value of a folder differs from the fresh one, the cache of that folder is dropped.
3. **IndexedDB.**
   New `src/model/offline/db.ts` (small wrapper, dependency free) with stores `folders` (the tree, per account), `pages`, `details` (key `accountId, folder, uid`, fields `uidvalidity`, `cachedAt`, `lastViewedAt`, `reason`: which rule keeps it) and `queue`.
   The localStorage entry for the open mail is removed: the open mail and the place come from the cache, the store keeps only the place (account, folder, uid) in localStorage.
   Attachments are not cached, only their metadata.
4. **Cache rules and purge** (`offline/cache.ts`, plain functions).
   - Settings in `store/prefs.ts` (localStorage, screen `/settings`): `cacheUnread`, `cacheOpenedUnread`, `cacheInbox` toggles and `cacheInboxCount` (default 200).
   - Write-through on every list page and every opened `Detail`.
   - A background prefetch runs a small pool (4 requests at a time) for the INBOX window and the unread mails of opened folders; it pauses while the user waits for a request of their own and stops when offline.
   - A purge runs at start and then every few minutes: a mail stays only while some enabled rule claims it; a mail marked read (here or seen on the next list reload) loses the unread rules, and one not viewed for 30 days (constant, can become a setting) and not in the INBOX window is dropped.
5. **Folder tree.**
   The folders are stored in IndexedDB per account and shown immediately from there.
   They are fetched again on page load and periodically (`reloadFolders` on a timer), and the fresh result replaces `folders` in Pinia reactively: update entries in place by name (counts, new folders added, gone folders removed) instead of assigning a new array, so the open selection and the tree state survive.
6. **Online state.**
   New `src/model/online.ts` with `useOnline()` returning one shared `isOnline` computed.
   It combines the `online`/`offline` events with the result of the last request (a network `TypeError` sets it false, any answer sets it true), because `navigator.onLine` alone lies; a failed state probes `/api/public/health` every few seconds to recover.
   `useOnline()` is module-level shared state, used by `mail.ts` for the cache fallback and by components to disable what needs the server.
7. **Reading offline.**
   The read calls in `mail-api.ts` (`listFolders`, `listMessages`, `getMessage`) use a `cachedGet` helper: network first, on a network failure fall back to the cache and set offline; an `ApiError` (401, 424, ...) is never answered from the cache.
   The log of a mail (`MailLog.vue`) shows "Offline, the log is not available" instead of nothing.
   `MailView` shows a banner with the offline state and the number of queued actions.
   Clicking the number opens an overlay (`QueueOverlay.vue`, teleported to `body` like the other dialogs) listing the queued actions, debug style for now: one row per entry with kind, account, folder, uid, payload, queued time and last error, read from the `queue` store reactively.
   Read only in this version, no retry or delete buttons.
8. **Disabled while offline.**
   With `isOnline` false, disable everything that needs the server: the rule editor's server Save, dry-run and Run now, the accounts screen writes, git control, the action log screen, "Load remote images" / "Load styles", the example mail panel's loading of uncached mails, and Test connection.
   Mark read/unread and move stay enabled (they queue).
   Each disabled control gets a title "Not available offline".
9. **Offline actions.**
   `setSeen` and `moveTo` apply the change locally as today; on a network error they append an entry to the `queue` store instead of showing an error, and update the cache (read mail loses its unread claim, moved mail is removed).
   `flush()` runs on going online, after the next successful request and at start, replaying in order; success removes the entry, a 404 (mail gone) drops it, a 409 `actions_disabled` drops it and reports once, a network error keeps it and stops, a 401 stops.
   Collapsing per mail (`queue.ts`, `enqueue`): the later action wins and replaces the earlier of the same kind, nothing cancels both.
   - read then unread: only unread stays.
   - unread then read: only read stays.
   - read then read (or unread twice): one entry.
   - flag change then move: both stay (different kinds); a second move replaces the first move.
   - move then a flag change on the same mail: the flag change is dropped because the mail is gone from the source folder (the UID changes with the move).
10. **Log out.**
    Before it clears anything it checks the queue; with pending entries it asks (a dialog like `ConfirmUnwrap.vue`): "N actions have not been sent yet" with Log out anyway / Wait and send (flush now, then log out) / Cancel.
    A confirmed log out clears the IndexedDB stores with `clear()`, so mails never outlive the session.

## Files

- New: `frontend/src/model/offline/{db,cache,queue}.ts`, `frontend/src/model/online.ts`, `ConfirmLogout.vue`, `OfflineBanner.vue`, `QueueOverlay.vue`.
- Changed: `frontend/vite.config.ts`, `package.json` (`vite-plugin-pwa`, dev `fake-indexeddb`), `src/main.ts`, `src/model/mail-api.ts`, `src/model/store/{mail,prefs}.ts`, `SettingsView.vue`, `MailView.vue`, the controls listed in point 8, `server/api/mail.py` (`uidvalidity`), `CLAUDE.md`.

## Tests

- Vitest with `fake-indexeddb`: cache write-through, each rule on its own and combined (toggle off drops its mails on the next purge), the numeric INBOX window, `cachedAt` / `lastViewedAt` and the age purge, `uidvalidity` change drops a folder, folder refresh updates entries in place (selection and object identity of untouched entries kept).
- Queue, one test per collapse case listed in point 9, plus flush order and the 404 / 409 / 401 / network error outcomes.
- `useOnline`: events, request results, the health probe, one shared ref across two callers.
- Store: `setSeen` / `moveTo` queue instead of failing offline; log out with pending entries asks, each of the three answers, and a clean queue logs out directly.
- Component tests: clicking the banner's number opens the overlay with one row per queued entry; controls from point 8 are disabled offline, the log shows the offline text, settings toggles and the numeric field persist.
- Playwright (`mail.spec.ts`, mocked API, `context.setOffline`): cached list and mail open offline, mark read queues, back online it is sent.
- Python: `uidvalidity` in the three mail responses (FakeServer).

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`, then `uv run pytest`.
The service worker is checked with `yarn build` plus `yarn preview` in one e2e spec (the dev server has none).
