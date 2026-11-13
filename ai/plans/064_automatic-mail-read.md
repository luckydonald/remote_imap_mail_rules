# Automatic mail read

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `2bb01f31-66e6-4d96-bd8f-46d8abc705cc`: "add automatic mail read", settings: off / upon open / scrolled down.

## Context

Opening a mail never marks it read (`BODY.PEEK`), the user has to press `Mark read`.
A new browser setting lets the mail view do that by itself, either when the mail is opened or once it was scrolled to the end.
It only uses the existing `setSeen` path, so queueing offline, the folder badges and the cache purge keep working, and it needs `ACTIONS_ENABLED` like the button.

## Findings

- `frontend/src/model/store/prefs.ts`: view settings in localStorage (`bodyMode`, `remoteImages`, `mailStyles`), composed into `useStore` by `store/index.ts`.
- `frontend/src/components/SettingsGeneral.vue`, section "Mail view", uses `SegmentedToggle` for each of these.
- `frontend/src/model/store/mail.ts`: `openMessage(uid)` loads `detail`, `setSeen(seen)` is the one write path (busy lock, queue on network error, `countUnseen`, `purge`).
- `frontend/src/components/MailMessage.vue`: `.mail-message` is the one scroll column, the toolbar (and so the manual button) is hidden when `compact` (the editor's example-mail side panel).

## Design

- New pref `autoRead: 'off' | 'open' | 'scrolled'` in `prefs.ts`, default `off`, saved in localStorage like the other view settings (invalid values fall back to `off`), returned from `usePrefs`.
- Settings screen: a new section "Mark mails read" in "Mail view" with a `SegmentedToggle` `Off | When opened | When scrolled to the end`, and a hint that it needs `ACTIONS_ENABLED` and that the side panel never does it.
- Logic in `MailMessage.vue`, only when `!compact`, `store.actionsEnabled` and `store.detail` is unseen:
  - `open`: once `detail` for the open uid is there, call `store.setSeen(true)`.
  - `scrolled`: on `scroll` of `.mail-message` (and after `fit()` of the iframe, since the height changes while it loads) check `scrollTop + clientHeight >= scrollHeight - 8`; a mail that fits without scrolling counts as scrolled to the end, but only after the iframe was fitted so the half-loaded height does not trigger it.
- Once per opening: remember the uid that was already handled (`autoReadUid`), so `Mark unread` afterwards is not undone, and reopening the mail marks it again by the setting (opening is the trigger).
- The logic goes into a small function file `model/auto-read.ts` (pure helper `reachedEnd(el)`, and the decision `shouldAutoRead(mode, detail, actionsEnabled)`), the component only wires events, so it is unit testable.
- No new store, no server change, no schema change.

## Tests

- Vitest `src/__tests__/auto-read.spec.ts`: `reachedEnd` (fits, at end, not at end, slack), `shouldAutoRead` for each mode, seen mail, actions disabled; prefs default and invalid value fallback.
- Playwright `e2e/mail.spec.ts`: with `open` the opened unread mail becomes read and the folder badge drops; with `off` nothing happens; with `scrolled` a long mail stays unread until scrolled to the end; `Mark unread` after an automatic read stays unread.
- Settings e2e/component check that the toggle persists (follow the existing `bodyMode` test pattern).

## Also

- Update `CLAUDE.md` (mail view settings: `autoRead`, the once-per-open rule).
- Preexisting, separate small fix commit: `prefs.ts` leaves `cacheMaxAgeDays` out of the watch that writes localStorage, so an offline start does not see changes of it; add it to the watch list.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`, and `uv run pytest` is untouched but run once for the full suite.
