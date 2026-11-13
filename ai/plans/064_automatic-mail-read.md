# Automatic mail read

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `2bb01f31-66e6-4d96-bd8f-46d8abc705cc`: "add automatic mail read", settings: off / upon open / scrolled down.

## Context

Opening a mail never marks it read (`BODY.PEEK`), the user has to press `Mark read`.
A new admin setting lets the mail view do that by itself, either when the mail is opened or once it was scrolled to the end.
It is a user setting, so it lives in the database row `user_settings` and follows the admin into every browser, like the offline cache rules.
The marking itself uses the existing `setSeen` path, so queueing offline, the folder badges and the cache purge keep working, and it needs `ACTIONS_ENABLED` like the button.

## Findings

- `user_settings` is one row (`db/models/user_settings.py`, repository `db/user_settings.py`, `GET` and `PUT /api/settings` in `server/api/settings.py`), created by migration 0008.
- Migrations 0008 and 0009 are already pushed (only plan commits are unpushed), so the column needs a new migration `0010`, not an edit of an old one.
- Frontend: `settings-api.ts` (`CacheSettings`, `fetchSettings`, `saveSettings`), `store/prefs.ts` takes the server values in `loadServerSettings()` and sends changes after 500 ms, the localStorage copy is what an offline start uses.
- `components/SettingsGeneral.vue` has the "Mail view" section; `OnlineOnly` wraps what must not be changed offline (the cache settings).
- `store/mail.ts`: `setSeen(seen)` is the one write path, `openMessage(uid)` loads `detail`.
- `components/MailMessage.vue`: `.mail-message` is the one scroll column, the toolbar is hidden when `compact` (the editor's example-mail side panel).

## Backend

- `db/models/user_settings.py`: new column `auto_read: Mapped[str]` (`String(16)`, default `"off"`), documented as `off` / `open` / `scrolled`.
- `migrations/versions/0010_user_settings_auto_read.py`: `op.add_column('user_settings', sa.Column('auto_read', sa.String(16), nullable=False, server_default='off'))`, downgrade drops it; generated with `uv run alembic revision --autogenerate`, the drift test must stay green (model default and `server_default` kept consistent).
- `db/user_settings.py`: default `auto_read="off"` in the transient row.
- `server/api/settings.py`: `SettingsOut.auto_read: Literal["off", "open", "scrolled"]`, so other values are a 422.
- Tests in `tests/test_server_user_settings.py`: `DEFAULTS` gets `auto_read: "off"`, the round trip changes it, and `("auto_read", "always")` joins the invalid cases.

## Frontend

- `settings-api.ts`: rename `CacheSettings` to `UserSettings` and add `auto_read: AutoRead` (`'off' | 'open' | 'scrolled'`, the type lives in `prefs.ts`).
- `store/prefs.ts`: `autoRead` ref (default `off`, invalid values fall back to it), part of the localStorage copy and of the values `loadServerSettings` takes and the 500 ms send watcher compares (`cacheValues()` becomes `serverValues()`).
- `SettingsGeneral.vue`: new section "Mark mails read" in "Mail view", `SegmentedToggle` `Off | When opened | When scrolled to the end`, inside `OnlineOnly` like the other server settings, with a hint that it needs `ACTIONS_ENABLED` and that the side panel never does it.
- `model/auto-read.ts`: pure helpers `reachedEnd(el)` (`scrollTop + clientHeight >= scrollHeight - 8`) and `shouldAutoRead(mode, detail, actionsEnabled)`, so they are unit testable.
- `MailMessage.vue`, only when `!compact`:
  - `open`: when `detail` of the open uid arrives and `shouldAutoRead`, call `store.setSeen(true)`.
  - `scrolled`: check on `scroll` of `.mail-message` and after the iframe was fitted (`fit()`), because the height changes while it loads; a mail that fits without scrolling counts as read at once, but only after the fit, so a half-loaded height does not trigger it.
- Once per opening: the handled uid is remembered, so `Mark unread` afterwards is not undone by the same view; reopening the mail applies the setting again.
- No new store, the setting is read through `useStore()`.

## Tests

- Vitest `src/__tests__/auto-read.spec.ts`: `reachedEnd`, `shouldAutoRead` per mode, seen mail, actions disabled.
- Vitest `settings-sync.spec.ts`: `auto_read` is taken from the server and sent on change; prefs fall back to `off` on an invalid stored value.
- Playwright `e2e/mail.spec.ts` (mail mock serves `/api/settings`): with `open` an unread mail becomes read and the badge drops; with `off` nothing happens; with `scrolled` a long mail stays unread until the column is scrolled to the end; `Mark unread` after an automatic read stays unread.
- `e2e/mcp-tokens.spec.ts` mocks the settings response, add `auto_read` there.

## Also

- `CLAUDE.md`: mention `auto_read` in the `user_settings` / Offline paragraph and the once-per-open rule in the mail view paragraph.
- Preexisting bug, separate small fix commit before the feature: `prefs.ts` leaves `cacheMaxAgeDays` out of the watch that writes the localStorage copy, so an offline start does not see changes of it.

## Verification

`uv run pytest`, then `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
