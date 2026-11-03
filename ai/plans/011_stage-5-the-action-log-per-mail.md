# Stage 5: the action log per mail

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

The last open item of `ai/initial.md` is "the full action log per mail (first seen, rule matches, actions, user actions)".
The server runs no matching in the background today (`matching.matches()` is only used by `demo.py`), so nothing could write such a log.
The chosen scope is: a log table, a background watcher in the server that records first seen and rule matches, an API, and a log section in the mail view.
Rule actions are still not executed and IMAP stays read-only, so the `action` and `user_action` kinds exist in the schema but nothing writes them yet.

## Tasks (one commit each, in this order)

1. **[db] mail events: the model and migration.**
   - `db/models/mail_event.py`: `MailEvent` with `id` (Uuid), `account_id` (FK to `accounts`, `ondelete=CASCADE`), `folder`, `uidvalidity` (nullable int), `uid`, `message_id` (nullable), `kind` (`first_seen`, `rule_match`, `action`, `user_action`), `rule_name` (nullable), `detail` (JSON), `created_at` (`utcnow`).
   - Index on `(account_id, folder, uid)`. Export it in `db/models/__init__.py`.
   - `migrations/versions/0003_mail_events.py` via `uv run alembic revision --autogenerate -m mail_events`.
   - Extend the table-name assertion in `tests/test_db_migrations.py`.
2. **[db] mail events: repository.**
   - `db/mail_events.py` as function module like `db/accounts.py`: `record_event(session, ...)`, `list_events(session, account_id, folder, uid)` (oldest first), `has_event(session, mail key, kind, rule_name)`.
   - `tests/test_db_mail_events.py`.
3. **[backend] matching: carry `uidvalidity` on `Mail`.**
   - Add `uidvalidity: int | None = None` to `Mail` in `mail.py`, set in `matching.py` from `client.state` / `poll_state` where the mails are built, so `on_inspect` and `RuleMatch.mail` have it.
   - Extend `tests/test_matching.py`.
4. **[backend] server: the watcher.**
   - `server/watcher.py`, class `Watcher` with `start()`, `stop()`, `restart()`; one task per stored account.
   - Each task builds `ImapSettings` with `db.accounts.imap_settings`, parses rules from `rules_store.read_text()` through `parse_rules`, and consumes `matches(settings, rules, factory=app.state.imap_factory, on_inspect=...)`.
   - `on_inspect` pushes mails onto a queue, the consumer records `first_seen` once per mail (`has_event` guard); matches record `rule_match` with `detail={"match_kind": ...}`, and `existing` matches are only recorded when not yet logged.
   - Errors: log and retry with backoff (the same `CryptoError` / `ImapError` family `imap_session.py` maps).
   - `restart()` is called after `PUT /api/editor/rules` and after account create / update / delete.
   - New `ServerSettings.watch_enabled` (env `WATCH_ENABLED`, default true); started in the `create_app` lifespan, stopped before `engine.dispose()`. Tests turn it off except the watcher tests.
   - `tests/test_server_watcher.py` using `FakeServer` from `tests/fake_imap.py`.
5. **[backend] server: events API.**
   - `server/api/events.py`: `GET /api/mail/accounts/{account_id}/messages/{uid}/events?folder=` returning a list of `EventOut`; mounted behind `require_login` like `mail`.
   - Test in `tests/test_server_events.py`; `test_every_route_but_auth_is_protected` picks the route up automatically.
6. **[frontend] mail: log client and store.**
   - `model/mail-api.ts`: `MailEvent` interface and `listEvents(accountId, folder, uid)`.
   - `model/mail-store.ts`: `events` state loaded with `openMessage` (stale responses dropped with a ticket, like `detailTicket`); not persisted in localStorage.
   - Vitest in `mail-api.spec.ts` and `mail-store.spec.ts`.
7. **[frontend] mail: the log section.**
   - `components/MailLog.vue` (timeline of the events: time, kind, rule name), used in `MailMessage.vue`.
   - Mock the endpoint in `e2e/mail-mock.ts`, add a case to `e2e/mail.spec.ts`; component test in `components.spec.ts`.
8. **[docs] stage 5: document the log.**
   - `CLAUDE.md` (layout and decisions: event table, watcher, `WATCH_ENABLED`, no action or user_action writes yet), `README.md` (the env var), tick the item in `ai/initial.md` and update "Status so far" / "Not built yet".

## Decisions

- A mail is identified by `(account_id, folder, uidvalidity, uid)`, with `message_id` stored for the later moves between accounts; the API looks up by `account_id`, `folder` and `uid`.
- `existing` matches are logged once, `new` and `changed` every time.
- The watcher reads the rules from `rules_store`, so file and database mode both work; the rules are not stored per event, only the rule name.

## Verification

- `uv run pytest` (including the migration drift test and `--check` of the schema), `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
- Playwright only for the frontend, not the Chrome tools.
