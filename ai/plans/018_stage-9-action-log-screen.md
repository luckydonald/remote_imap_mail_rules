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
4. Frontend (own commit, requested additionally): raw mode for the server-side rules `.yml`, see below.
5. Docs: `CLAUDE.md` layout and decisions, `README.md` if endpoints are listed there, and tick stage 9 in `ai/initial.md`.

## Raw mode for the server-side YAML

`YamlPanel.vue` (view `{kind: 'yaml'}`) already has a textarea with Apply and Reset, but it shows the regenerated YAML, and `store.load()` drops `serverFile`, so Save vanishes after Apply.
Backend needs no change: `PUT /api/editor/rules` already takes the raw text and validates it (422 with a message list), and `FileRulesStore` writes it verbatim.

- **Draft source:** when a server file is open and not dirty, the textarea starts from the server's last text (`store.savedYaml`, set by `markSaved`), otherwise from `store.yaml`.
- **Apply keeps the server file:** a new `store.applyText(text)` in `model/store.ts` that loads like `load()` but keeps `serverFile` (and `savedYaml`), so the file stays dirty-tracked and Save stays available.
- **Save raw:** a "Save" button in `YamlPanel.vue` that sends the draft verbatim through `saveRules` (`model/api.ts`), without a round trip through the model, so comments, anchors and formatting stay as typed in file mode.
  On success it re-fetches (`fetchRules`) and `markSaved`s, so database mode shows what the server stored; on a 422 the `SaveError.messages` show inline under the textarea (the same `.message.error` as parse errors).
  Parse and schema problems of the draft show live (`parseRulesWithComments` + `validateRules`, reusing the problem list markup of `YamlPanel.vue`) and do not block Save, the server is the judge.
- **Database mode hint:** a note that comments there end up in the rule descriptions and anchors are not kept (`DatabaseRulesStore.save_text` and `append_comments`); the hint reads `EditorConfig.source`.
- **Paste:** works through the textarea; the panel needs no extra drop handling, the shell's drop handler still opens files.
- **Tests:** Vitest for `applyText` (`store.spec.ts`, keeps `serverFile`) and the panel (`components.spec.ts`); Playwright in `e2e/server.spec.ts` style (`mockServer` records the PUT body: raw text with a comment is sent unchanged, a 422 is shown inline).

## Verification

- `uv run pytest`, then `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
- Playwright only, no Chrome tools; no live mailbox is touched (only `FakeServer` / `TEST_*`).
