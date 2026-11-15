# Remember loaded remote images and styles per mail

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `ed3e520a`: store in the browser whether a mail has its styles and remote images loaded, and load them again the next time that mail is opened.
Today `openMessage` in `frontend/src/model/store/mail.ts` starts every mail with the global policy (`prefs.remoteImages` / `prefs.mailStyles`, default `block`).
`Load styles` / `Load remote images` call `allow()`, which only changes `bodyOptions` for the open mail, so the choice is gone when the mail is opened again.
The cached `Detail` does carry `remote_images_allowed` / `styles_allowed`, but it cannot be the memory: background prefetch calls `readMail(..., {}, ...)` and overwrites the record with a blocked copy, and a mail no cache rule claims is not stored at all.

## Approach

A small separate record per mail, independent of the detail cache.

- `model/offline/db.ts`: new object store `loaded` (keyPath `key`), `VERSION` 2, created in `onupgradeneeded` (guard with `contains` so a fresh install and an upgrade both work), add it to `StoreName` and to `clearAll` (so log out wipes it).
- `model/offline/cache.ts`: `rememberLoaded(accountId, folder, uid, options)` merges `{remoteImages, styles}` (only ever sets true, stored with `at`), `loadedFor(accountId, folder, uid): Promise<BodyOptions>`, both keyed by the existing `detailKey`.
  Delete the record wherever the detail record of that mail is deleted (move in `removeMail`, `purge`, uidvalidity drop), so it does not outlive the mail.
- `model/store/mail.ts`:
  - `openMessage`: after the policy defaults, `bodyOptions` = policy OR remembered (`await loadedFor`), before the cached detail check, so the existing "skip a cached copy that holds more than is allowed" rule then accepts the cached copy that matches and the server read uses the remembered options.
  - `allow()`: call `rememberLoaded` with the merged `bodyOptions` after the server answered.
- No server change, no new setting.
  A global policy of `allow` still wins, a remembered `true` never turns something off, and the toolbar buttons behave as before.

## Tests (vitest, `fake-indexeddb/auto`)

- `offline-cache.spec.ts`: `rememberLoaded` / `loadedFor` round trip, merge keeps an earlier `true`, removed with the mail, `clearAll` wipes it.
- `mail-store.spec.ts`: `allow({styles: true})` then opening the same mail again requests `styles=true` (and not `remote_images`), another mail still blocks, a remote-images-only choice does not enable styles.
- Playwright `mail.spec.ts` case only if the existing mocks make it cheap: load images, reopen the mail, no blocked-images list.

## Docs

`CLAUDE.md`: in the Offline decision, add one sentence on the `loaded` store (per mail memory of loaded images / styles, DB version 2).

## Verification

`cd frontend && yarn test && yarn lint && yarn build`, then `yarn test:e2e` for the mail spec, and `uv run pytest` for the repo (no backend change expected).
