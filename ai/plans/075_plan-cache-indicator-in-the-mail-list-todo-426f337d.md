# Plan: cache indicator in the mail list (todo 426f337d)

## Context

The mail list does not show which mails are in the offline cache (IndexedDB store `details`), so the user cannot tell what still opens offline.
The todo asks for something small and simple.

## Findings

- A cached mail is a record in the `details` store with the key `accountId|folder|uid` (`detailKey` in `frontend/src/model/offline/cache.ts`).
- The list (`frontend/src/components/MailList.vue`) renders `store.messages`, and `useMail` (`frontend/src/model/store/mail.ts`) owns them.
- `db.ts` only has `get`, `getAll`, `count`, `put`, `delete`, `clear`, and `getAll` would load every body, so a key-only read is needed.

## Changes

1. `model/offline/db.ts`: add `dbKeys(store, range?)` using `getAllKeys`, with the same fallback to `[]` as the other helpers.
2. `model/offline/cache.ts`: add `cachedUids(accountId, folder): Promise<Set<number>>`.
   It reads the keys in the range `accountId|folder|` up to `accountId|folder|￿` and parses the uid after the last `|`.
3. `model/store/mail.ts`: add the ref `cachedUids` (a `Set<number>`) and `refreshCached()`, guarded by a ticket so a folder switch cannot apply a stale result.
   Call it after `loadMore`, `reloadMessages`, after `openMessage` finished (the mail was written through), after `setSeen` / `moveTo` and at the end of `prefetch` and `background`.
   Return `cachedUids` and `refreshCached` from the store, with names specific enough not to clash.
4. `components/MailList.vue`: next to the 📎, show `<span v-if="store.cachedUids.has(mail.uid)" class="cached" title="Available offline" aria-label="Available offline">⬇</span>`.
5. `styles/main.scss`: `.row-mail .cached` small and muted, inherits the color on the active row.

## Tests

- `src/__tests__/offline-cache.spec.ts`: `cachedUids` returns only the uids of the given account and folder, and an empty set without IndexedDB.
- `src/__tests__/offline-store.spec.ts`: after opening a mail the list row shows the indicator, a row that is not cached has none, and after a folder switch the set matches the new folder.
- `e2e/mail.spec.ts`: the indicator shows on a cached row (mocked API), covering both Chromium and `webkit-ipad`.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
No backend change, no new i18n keys (the frontend has no i18n for mail strings).
Update the offline paragraph of `CLAUDE.md` with one sentence about `cachedUids` and the list indicator.
