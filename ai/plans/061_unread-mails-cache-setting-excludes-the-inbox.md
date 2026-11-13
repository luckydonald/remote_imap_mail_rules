# Unread-mails cache setting excludes the INBOX

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `66ef1a9b`: the setting "Unread mails of the folders I opened" should say that it does not include the INBOX.
In the code it does include it, since `reasonsFor` in `frontend/src/model/offline/cache.ts` claims every unread mail of any folder with a list.
The user decided: exclude the INBOX in the code too (the INBOX is covered by the "newest N INBOX mails" setting) and say so in the label.

## Changes

- `frontend/src/model/offline/cache.ts`: in `reasonsFor`, the `unread` reason requires `!isInbox(folder)`.
  The `opened` reason stays for any folder, so an unread INBOX mail the user opens is still cached.
  Update the doc comment of `wanted` ("unread mails of opened folders, not the INBOX").
- `frontend/src/components/SettingsGeneral.vue`: label becomes "Unread mails of the folders I opened (not the INBOX)".
  The hint below keeps working, but add that the INBOX follows the newest-mails setting.
- Tests in `frontend/src/__tests__/offline-cache.spec.ts` (and `offline-store.spec.ts` if affected): adjust the cases that rely on an unread INBOX mail being cached by `cacheUnread`, and add one case: an unread INBOX mail outside the newest N is not cached by `cacheUnread`, an unread mail of another folder is.
- `CLAUDE.md`: the Offline paragraph says `unread` is "unread mail of an opened folder"; add "other than the INBOX".

## Verification

`cd frontend && yarn test`, `yarn lint`, `yarn build`; e2e `yarn test:e2e` if a spec reads the label.
