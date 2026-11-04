# Stage 9: Action Log screen

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.
No `Claude-Session` or `Co-Authored-By` trailers, the repo hook rejects them.

## Context

Stage 9 of `ai/initial.md` asks for a dedicated screen for the action log with filters and search, and an info box on top.
Today the log (`mail_events`) is only visible per mail in `MailLog.vue`, and nothing exposes when the watcher last ran.
The info box shows the last time the watcher ran, the last time it found a change in any account, and the last time an action ran.

## Decisions

- **Timestamps:** "last change" and "last action" are derived from the database (`max(created_at)` of `first_seen` / `rule_match` / `user_action`, and of `action`), so they survive restarts and need no migration.
- "Last watcher run" has no database trace, so it is an in-memory `Watcher.last_run` set on every poll or IDLE wake-up, through a new `on_poll` callback on `matches()` / `follow_changes()` (`matching.py`, where `client.poll_state` is called).
  It is `None` after a restart until the first tick, and with `WATCH_ENABLED=false`; the box says so.
- **API:** a new router `server/api/log.py` at `/api/log` (behind `require_login`, mounted in `create_app` next to the others), because `/api/mail` is per account.
  - `GET /api/log/events`: filters `account_id`, `folder`, `kind` (repeatable), `rule`, `since`, `until`, free text `q`; paging with a `before` cursor `(created_at, id)` and `limit` (default 50).
  - `q` searches `rule_name`, `folder`, `message_id` and the JSON `detail` as text (`cast(String)` LIKE, case-insensitive).
  - Rows carry `id, account_id, folder, uid, message_id, kind, rule_name, detail, created_at`, so the screen can link to the mail.
  - `GET /api/log/status`: `{watcher_enabled, last_run, last_change, last_action}`.
- **Repository:** a new `list_log(...)` and `last_event_at(kinds)` in `db/mail_events.py`.
- **Index:** migration `0006` adds an index on `mail_events.created_at` (`batch_alter_table`, same style as `0005`), `tests/test_db_migrations.py` and the drift test updated.
- **Frontend:** new `ActionLogView.vue` (route `/log`, `Screen` gets `'log'`, nav link after Mail, `@unauthorized="logOut"` like `MailView`), `log-api.ts`, and a filter bar kept in the query string (`route.query`) so a view is linkable.
  - Rows reuse `eventLabel` / `fullDate` from `mail-format.ts` and add account, folder and a link to `/mail/:accountId/:folder/:uid`; account names come from `listAccounts()`.
  - "Load more" pages with the cursor; the info box refreshes with the list.
  - The topbar rules-file buttons stay hidden on this screen (extend the `screen !== 'mail'` condition in `AppShell.vue`).
  - Styles go into `styles/main.scss`, responsive like the mail view.

## Steps, one commit each

1. Backend: `Watcher.last_run` + `on_poll` plumbing, with a watcher test in `tests/test_server_watcher.py`.
2. Backend: migration `0006`, `list_log` / `last_event_at`, `/api/log` router and tests (`tests/test_db_mail_events.py`, new `tests/test_server_log.py` after the pattern of `test_server_events.py`, including the 401 case).
3. Frontend: `log-api.ts` + Vitest spec, `ActionLogView.vue`, route and nav, component spec, Playwright `e2e/log.spec.ts` (mocking `/api/log/**`; no clash with `/api/mail/**`).
4. Docs: `CLAUDE.md` layout and decisions, `README.md` if endpoints are listed there, and tick stage 9 in `ai/initial.md`.

## Verification

- `uv run pytest`, then `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
- Playwright only, no Chrome tools; no live mailbox is touched (only `FakeServer` / `TEST_*`).
