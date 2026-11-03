# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Other projects using this _base_ are expected to overwrite this file.**

If the primary working directory (visible in the system prompt) ends with `/base`, read `ai/°base/AGENTS.md` for full codebase guidance.

# remote_imap_mail_rules

Runs mail rules via IMAP, independent of the provider.
Python 3.14+ with `uv`, async throughout; run tests with `uv run pytest`.
Follow `/code-style`; `.env` and `.env.example` are blocked for agents, so `.example-env` is the documented template.
Planned later (not built yet): executing rule actions, moving mails between accounts and the action and user action entries of the log, see `ai/initial.md`.

## Layout

- `src/remote_imap_mail_rules/rules/`: `models.py` (pydantic rule file), `fields.py` (field and operator enums), `values.py` (dates), `extract.py` (field to mail mapping), `operators.py`, `evaluate.py`, `loader.py`, `schema.py`. Fields are `Templatable` (a value or a `Var`) and `Template` expressions are resolved by `.concrete()` in `loader.py`, see Templates below.
- `src/remote_imap_mail_rules/imap/`: `client.py` (read-only `ImapClient`), `watcher.py` (IDLE or polling), `fetch.py` / `sexpr.py` / `bodystructure.py` (response parsing), `connection.py` (the slice of `aioimaplib` used, so tests can fake it), `utf7.py` / `transfer.py` (folder names and part decoding for the mail browser). `ImapClient` also has `folder_counts`, `list_page`, `fetch_message` and `fetch_part` for the browser.
- `src/remote_imap_mail_rules/matching.py`: `matches()`, the core async generator yielding `RuleMatch` (`existing`, then `new` / `changed`). `demo.py` prints it (`--verbose` lists every inspected mail via `matches(on_inspect=...)`; `--streamer-mode` hashes titles and masks addresses, and agents must pass `--streamer-mode` or `--no-streamer-mode`).
- `src/remote_imap_mail_rules/server/`: FastAPI app (`app.py`, `create_app`), `settings.py` (`ServerSettings`, no IMAP needed), `rules_file.py` (validate and atomic write), `rules_store.py` (`RulesStore`: `FileRulesStore` or `DatabaseRulesStore`, chosen by `RULES_PATH`), `auth.py` (login session cookie, `require_login`) and `api/auth.py` (`/api/auth`), `api/accounts.py` (CRUD at `/api/accounts`), `api/mail.py` (read-only mail browser at `/api/mail`, with `imap_session.py`, `mail_view.py`, `html_sanitize.py`), `watcher.py` (`Watcher`: background `matches()` per stored account, writes the action log), `api/events.py` (`GET /api/mail/accounts/{id}/messages/{uid}/events`), `api/<area>.py` routers mounted at `/api/<area>` (`api/editor.py`: `GET /config`, `GET` and `PUT /rules` with the raw YAML as body), `main.py` (`uv run python -m remote_imap_mail_rules.server.main`). It serves `frontend/dist` at `/` when built.
- `src/remote_imap_mail_rules/db/`: async SQLAlchemy (`base.py`, `models/` for `Account`, `Rule`, `Template`, `MailEvent`, `engine.py`, `migrate.py`), `crypto.py` (Fernet), `accounts.py` (CRUD, `seed_from_env`, `env_differences`), `rules.py` (rule file to rows and back), `mail_events.py` (the action log repository). Alembic lives in `alembic.ini` and `migrations/`; `uv run alembic revision --autogenerate -m ...` after a model change, a test checks that models and migrations do not drift.
- `frontend/`: Vue 3 + TS + SCSS rule editor (Vite, Yarn 4, Vitest), no server needed (the accounts screen, `accounts-api.ts`, only shows when a server answers). `src/model/` has `yaml-io.ts` (YAML to model and back, keeps `&anchor` / `<<: *anchor` / `!var`; `comments.ts` carries the comments over by path, rule items by name, so they follow moved rules), `validate.ts` (ajv against `schemas/rules.schema.json`, imported through the `@schema` alias, plus the template variable check), `catalog.ts` (enums read from the schema), `store.ts` (undo/redo, rule operations, `serverFile` and `dirty`), `mail-api.ts` / `mail-store.ts` / `http.ts` (login and mail browser client, the Pinia store `useMailStore` cached in localStorage, and shared `ApiError`; components `MailLogin`, `MailView`, `MailFolders`, `MailList`, `MailMessage`, `MailAddCondition`), `fill-from-mail.ts` (`fillExpression` / `conditionFor` fill conditions from the open mail, mirroring `rules/extract.py`), `api.ts` (the `/api/editor` client; no server means file-only mode, with a Save button only on a server file). Navigation uses `vue-router` with real paths (`src/router.ts`: `/rules`, `/rules/templates`, `/rules/:index`, `/accounts`, `/mail/:accountId/:folder/:uid`, the folder as one encoded segment). `AppShell` keeps the route and `store.view` in sync, `MailView` (full screen only, not the side panel) keeps the route and the mail store place in sync (`useMailStore().goTo`). The server answers unknown paths with `index.html` (`SpaStaticFiles`, `/api` and `/assets` stay 404), Vite does so in dev, and the e2e tests point the Vite `/api` proxy at a closed port (`API_PROXY`) so a running server cannot change them. The Vite dev server proxies `/api` to port 8000, Playwright mocks it. A template use is `{type: template, ref, variables}` in the editor and only expands for validation. Run with `cd frontend && yarn dev`, `yarn test`, `yarn test:e2e` (Playwright, Chromium, starts vite on port 5199), `yarn build` (type checks first), `yarn lint` (oxlint + ESLint) and `yarn format` (Prettier). The setup follows `create-vue`: split tsconfigs, `@vue/tsconfig`, TypeScript `~6.0`, tests in `src/__tests__/` and `e2e/`, Prettier style (no semicolons, single quotes).
- `schemas/rules.schema.json` is generated from the pydantic model, never edited by hand: `uv run python -m remote_imap_mail_rules.rules.schema --write-schema` (`--check` fails when outdated, and a test does the same). The pattern is copied from `scripts/sync_todos.py`.

## Decisions

- Everything IMAP is read-only for now: `EXAMINE` only, `BODY.PEEK`, no store/move/expunge. Writes will be added later without reshaping the interfaces, which already take account and folder.
- Accounts are referenced by an immutable UUID (`IMAP_ACCOUNT_ID`, `account_id` in rules), never by name, because names can change. `IMAP_ACCOUNT_NAME` is a display label only.
- A rule has several `locations` (`account_id`, `folder` default `INBOX`, `recursive` default false), so equal rules for several inboxes need no duplicates. Recursive folders are expanded once at start-up via `LIST`; missing folders are skipped with a warning.
- Env vars are unprefixed (`IMAP_HOST`, ...). Only automated tests use the `TEST_` prefix, via `tests/settings.py`, and they never read `.env`.
- One connection and task per folder, because IDLE blocks its connection. Headers, flags, size and `BODYSTRUCTURE` are fetched up front, bodies lazily and only when a rule needs `body_text` / `body_html`.
- Change detection: IDLE push when the server has it (renewed before 29 minutes), else polling every `IMAP_POLL_INTERVAL`. New mails by UID, flag changes via `CONDSTORE` `CHANGEDSINCE` when available, a changed `UIDVALIDITY` reloads the folder.
- A field that does not exist makes every operator false, even negating ones like `ne`. Only `presence` with `value: false` and the `not` combinator can express absence. `body_text` never falls back to `body_html`.
- Dates are a discriminated union on the bool `relative`: `AbsoluteTime` (datetime, naive means UTC) or `RelativeDuration` (`7d`, units `s m h d w`, measured back from now). `date_received lt 7d` means received more than a week ago. There is no `age` field, a relative duration replaces it.
- IMAP has no last-modified date; `modseq` is only a change counter (CONDSTORE).
- Folder names are used as the server sends them (modified UTF-7), not decoded.
- Templates: root `templates` holds definitions (`type: template`, `defaults`, `content` with `{var: name}` / `!var name` markers). A use is `<<: *anchor` plus `variables`, valid wherever an expression is, checked by pydantic (every variable bound, none unknown). `parse_rules` returns `.concrete()` rules, so evaluator and matching never see a `Var` or `Template`: the models are generic in `V = Var` (`Templatable[T, V] = T | V`), `.concrete()` returns the `[Never]` form (`RuleFile[Never]`, `Rule[Never]`, `Expression[Never]`, where `T | Never` is just `T`), and consumers annotate with that form. YAML anchors may not contain `.`.
- The server edits only the file at `RULES_PATH` (file mode), or the database when it is unset (database mode); the client never sends a path. `PUT` validates with `parse_rules` first (422 with messages, file untouched) and replaces the file atomically. Files opened in the editor never write to disk.
- Accounts live in the database (`DATABASE_URL`, default SQLite, Alembic migrations run at server start). Passwords are Fernet-encrypted with `SECRET_KEY`, never returned by the API. The env account is seeded once and never overwritten, a difference is only reported (`env_differs`, field names only).
- Database mode stores one row per rule and per template as the non-concrete dump, so `Var` and template uses survive, but YAML comments and anchors do not. A rule keeps its row id across saves by name.
- Login gates all of `/api` except `/api/auth/*` (`require_login` is set per router in `create_app`). The credentials of any stored account unlock it (single user), the session is a Fernet token of `SECRET_KEY` in an HttpOnly cookie; without the key the gated routes answer 503. `fetchConfig()` in the frontend returns `'login'` for 401 / 503, `null` still means file-only mode.
- The mail browser opens one IMAP connection per request (`imap_session`, factory on `app.state.imap_factory` so tests use `FakeServer`), the folder is a query parameter, paging uses a `before_uid` cursor. Mail HTML is sanitized with `nh3` (remote images dropped, `cid:` rewritten to the part URL) and shown in an iframe sandboxed without `allow-scripts`; parts other than a few image types and PDF are forced to download with a `sandbox` CSP.
- `actions` are parsed and validated but nothing executes them yet.
- Action log: table `mail_events` (`kind` `first_seen` / `rule_match` / `action` / `user_action`), a mail is `(account_id, folder, uidvalidity, uid)` with `message_id` kept; `Mail.uidvalidity` is set by `ImapClient.build_mail`. The `Watcher` (started in the `create_app` lifespan unless `WATCH_ENABLED=false`, which the tests set) logs `first_seen` via `matches(on_inspect=...)` and `rule_match` per match (`existing` only once, `new` / `changed` every time) and restarts, as a background task after the commit, on account create / update / delete and on a rules save. `action` and `user_action` are reserved, nothing writes them yet. SQLite foreign keys are switched on per connection so `ON DELETE CASCADE` works. The frontend keeps the log of the open mail in `useMailStore().events` (not persisted) and shows it in `MailLog.vue`.
- Fill from mail: the editor has an "Example mail" side panel (a subpage on a phone) that reuses the mail browser. A condition's "From mail" button and "+ Add condition" take their value from `useMailStore().context` (the open mail, `null` offline), and the address part follows the condition's `part`. The `in` operator takes all values, otherwise the first. `GET /api/mail/.../messages/{uid}` also returns all headers, flags, keywords and the other address headers for this. The mail store is the only Pinia store, the rule store stays on provide/inject.

## Rule expressions

Rule file: `rules:` list of `name`, `enabled` (default true), `locations`, `when`, `actions`. The `when` tree is a discriminated union on `type`:

- Combinators: `all` and `any` (`conditions`, at least one), `not` (`condition`). Nest freely.
- `text`: `field`, `operator`, `value`, `case_sensitive` (default false, valid for every operator), `quantifier`.
- `address`: like `text` plus `part` (`full`, `name`, `address` (default), `local_part`, `domain`).
- `header`: like `text` but with a header `name` instead of a field, for custom headers.
- `number`: `field`, `operator`, `value` (a `[low, high]` pair for `between`), `quantifier`.
- `date`: `field`, `operator`, `value` (`TimeValue`, or a pair for `between`).
- `bool`: `field`, `value` (default true), `quantifier`.
- `presence`: exactly one of `field` / `header`, `operator` `exists` (default) or `empty`, `value` (default true).

Operators:

- text: `equals`, `contains`, `startswith`, `endswith`, `regex` (search), `glob`, `in` (value is a list).
- number and date: `eq`, `ne`, `lt`, `gt`, `gte`, `lte`, `between` (inclusive).
- Quantifier for multi-valued fields: `any` (default), `all`, `none`. No values at all counts as missing, so false.

Fields and where they come from:

| Type | Fields | Source |
|---|---|---|
| text | `account_id`, `folder` | location / fetch context |
| text | `subject`, `message_id`, `in_reply_to`, `references`, `list_id`, `auto_submitted`, `precedence`, `importance` | headers (RFC 2047 decoded) |
| text | `body_text`, `body_html` | `text/plain` / `text/html` parts, lazy; a missing part is a missing field |
| text | `mime_type`, `keywords` | top `BODYSTRUCTURE` type, flags minus system flags |
| text | `auth_spf`, `auth_dkim`, `auth_dmarc` | `Authentication-Results` |
| text | `attachment_mime_type`, `attachment_filename`, `attachment_extension` | `BODYSTRUCTURE`, one value per attachment |
| address | `from`, `sender`, `reply_to` (`Reply-To`), `return_path`, `to`, `cc`, `bcc`, `recipients` (to+cc+bcc), `delivered_to` | headers; `in_reply_to` is separate from `reply_to` |
| number | `size` | `RFC822.SIZE` |
| number | `spam_score` | first of `X-Spam-Score`, `X-Rspamd-Score`, `X-Spam-Status` (`score=`), `X-Spam-Level` (star count) |
| number | `attachments_count`, `attachment_size`, `uid`, `modseq` | `BODYSTRUCTURE` / fetch |
| date | `date_sent` | `Date:` header |
| date | `date_received` | `INTERNALDATE` |
| bool | `seen`, `flagged`, `answered`, `draft`, `deleted` | `FLAGS` |
| bool | `spam_flag` | `X-Spam-Flag`, else `X-Spam-Status` starting with `Yes` |
| bool | `is_reply`, `has_list_unsubscribe`, `attachment_inline` | `In-Reply-To` / `References`, `List-Unsubscribe`, `BODYSTRUCTURE` |

Actions (parsed only): `move` (`folder`, optional `account_id`), `mark_read`, `mark_unread`, `flag`, `keyword`.

To add a field: extend the enum in `rules/fields.py`, map it in `rules/extract.py`, then regenerate the schema and add a test case in `tests/test_rules_evaluate.py`.
