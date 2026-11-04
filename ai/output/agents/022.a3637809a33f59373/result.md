The Stage 9 plan doesn't exist yet. `ai/plans` stops at `017`, and `ai/todo.md` has no Action Log entry. Nothing was written. `src` below means `/Users/user/Documents/programming/Python/remote_imap_mail_rules/src/remote_imap_mail_rules`, and `fe` means `/Users/user/Documents/programming/Python/remote_imap_mail_rules/frontend`.

## 1. Backend

**MailEvent model** (`src/db/models/mail_event.py`)
- The `EventKind` StrEnum is at lines 15-22: `first_seen`, `rule_match`, `action`, `user_action`.
- The table is `mail_events` (lines 25-40). Columns:
  - `id` (Uuid PK)
  - `account_id` (FK to `accounts.id`, CASCADE on delete and update)
  - `folder` (String 1024)
  - `uidvalidity` (nullable Integer)
  - `uid` (Integer)
  - `message_id` (nullable Text)
  - `kind` (String 32)
  - `rule_name` (nullable String 255)
  - `detail` (JSON)
  - `created_at` (DateTime tz, default `utcnow` from `account.py`)
- The only index is `ix_mail_events_mail (account_id, folder, uid)` (line 29). There is none on `created_at`, `kind` or `rule_name`.
- Index changes need a migration. Alembic's `render_as_batch` is evidently used, since 0005 uses `batch_alter_table`.

**Repository** (`src/db/mail_events.py`)
- `record_event` (12-37) does `add` and `flush`, with no commit.
- `list_events(session, account_id, folder, uid)` (40-48) returns one mail, ordered by `created_at, id`.
- `list_events_by_message_id` (51-58).
- `has_event` (61-80).
- There is no cross-account query, no pagination, no filtering and no search. You need a new function here.
- `detail` is JSON and only lightly structured. Searching it will mean a `cast(String)` LIKE, or searching `rule_name`, `folder` and `message_id` only.

**Events API** (`src/server/api/events.py`)
- The only endpoint is `GET /accounts/{account_id}/messages/{uid}/events?folder=INBOX` (lines 32-35). It returns `list[EventOut]` with `id, kind, rule_name, detail, created_at` (18-24), via `to_out`.
- It is mounted at `/api/mail` (`app.py:94`).
- `EventOut` has no `account_id`, `folder`, `uid` or `message_id`. The log screen needs those, so add a richer model such as `LogEntryOut`.
- A cleaner choice is a new router at `/api/events` or `/api/log`, since `/api/mail` is per account.

**Watcher** (`src/server/watcher.py`)
- Class `Watcher`, lines 112-402. Constructor at 115-134, with `task`, `enabled`, `actions_enabled` and `retry_delay`.
- `start/stop/restart` are at 136-156. `run()` (158) gathers one `watch_account` task per account. `watch_account` (165-180) loops, retrying `follow()` after `retry_delay`.
- `follow()` (210-261) builds a queue, starts the `record` task, then iterates `matches(...)` from `src/matching.py` (240-244).
- The real poll/IDLE loop is not in the Watcher. It is in `src/imap/watcher.py:56-78` (`watch()` yields on a push or poll event), consumed by `matching.follow_changes` (`src/matching.py:161-215`).
- `follow_changes` calls `client.poll_state` at line 176 on every wake-up. That is the true "watcher ran" tick, but `Watcher` can only see it through the callbacks `on_inspect` (`lambda mail: queue.put_nowait(Seen(mail))`) and `on_change`.
- Hook points for the three timestamps:
  - **Last watcher run:** `Watcher.run` or `follow()` start (lines 158 and 234), or a new `on_poll` callback added to `matches`/`follow_changes` (`matching.py:175-176`). Without a new callback, "last run" only means "started or crashed or retried". Note that `watch_account` returns after `follow()` ends normally.
  - **Last change found in any account:** `Watcher.write()` (351-371), `write_user_change` (373-388) and `record_event` calls. This is also derivable from `max(created_at)` of `mail_events` where kind is `rule_match`, `user_action` or `first_seen`.
  - **Last action:** `write_actions` (310-329), or `max(created_at)` where `kind='action'`.
- Reachability from `app.state`:
  - `app.state.watcher` is set at `app.py:83`.
  - An endpoint reaches it like `get_service` in `server/api/git.py:35-38`, with `request.app.state.watcher`.
  - A new `last_run: datetime | None` attribute on `Watcher` would be in-memory only, and lost on restart.
  - The DB-derived timestamps survive restarts, but they only cover change and action.
- With `WATCH_ENABLED=false` (set by the autouse `no_watcher` fixture in `tests/conftest.py:64-68`), the watcher never starts, so the timestamps are `None`.

**App wiring** (`src/server/app.py`)
- `app.py:87` sets `protected = [Depends(require_login)]`, and routers are mounted at 88-94 with `dependencies=protected`.
- Add a new router with an import in line 16 and an include near 94. `require_login` comes from `.auth`.
- Other routers get their DB session via `from .accounts import get_session`.

**Latest migration**
- It is `migrations/versions/0005_mail_events_on_update_cascade.py`. Revision `'0005'`, down_revision `'0004'`, created 2026-11-04.
- The next one is `0006_<slug>.py` with `revision = '0006'` and `down_revision = '0005'`.
- The style is a docstring header (title, `Revision ID`, `Revises`, `Create Date`), then `revision/down_revision/branch_labels/depends_on`, then `upgrade()/downgrade()` with `# end def`. Use `op.batch_alter_table` for SQLite.
- `tests/test_db_migrations.py` exists and likely needs updating for the new head.

## 2. Tests

**API tests** (`tests/test_server_events.py`)
- The `client` fixture (19-29) builds `ServerSettings(_env_file=None, rules_path=None, database_url=sqlite+aiosqlite in tmp_path, frontend_dist=missing, secret_key=SecretStr(KEY), admin_username/password)`.
- It then runs `TestClient(create_app(settings))` with `test_client.cookies.set(SESSION_COOKIE, make_session_token(settings))`.
- `BODY` and `KEY` are imported from `tests/test_server_accounts.py`. An account is created via `client.post("/api/accounts", json=BODY)`.
- The `insert(tmp_path, account_id, folder, uid, kind, created, rule)` helper (32-45) writes raw rows through a sync SQLAlchemy engine, with `account_id.replace("-", "")` and hex ids.
- Tests are plain sync functions.
- `tests/test_server_mail.py` adds a `server` fixture of type `FakeServer` and passes `create_app(settings, imap_factory=server.connect)`. `test_mail_needs_login` is at line 72, for the 401 check.
- `tests/fake_imap.py` has `FakeServer`, `FakeConnection` and `FakeFolder`. Its API is `add(folder, uid, subject, flags=, sender=)`, `push()` and `.connect`.

**Repository tests** (`tests/test_db_mail_events.py`)
- Uses an async `session` fixture: `upgrade(url)`, `create_engine`, `create_session_factory(engine)()`, `create_account(...)`, then `record_event`.

**Watcher tests** (`tests/test_server_watcher.py`)
- An async `factory` fixture (56-68) runs `upgrade` and creates the account with `ACCOUNT` (imported from `tests/test_imap.py`).
- `StaticRules` (34-53) is a fake RulesStore.
- `make_watcher(factory, server, rules)` (71-73) builds `Watcher(factory, StaticRules(...), SecretStr(KEY), server.connect, retry_delay=0.05)`.
- The `until(check)` helper (83-89) polls with a 3 s timeout.
- The `kinds(...)` helper is at 76-80.
- Typical flow: `watcher.start()`, `await until(...)`, `server.add(...)`, `server.push()`, then `await watcher.stop()` in a `finally`.
- `asyncio_mode` is auto, since async tests carry no decorator.

## 3. Frontend

**Router** (`fe/src/router.ts`)
- The `Screen` union is at line 13: `'rules' | 'accounts' | 'git' | 'mail' | 'sample-error'`.
- Routes are at 24-65. Each is `{ path, name, component: empty, meta: { screen } }`. For example `/git` is at line 35.
- Add `'log'` to `Screen` and a route `{ path: '/log', name: 'log', component: empty, meta: { screen: 'log' } }` before the catch-all at 64.
- Query-string filters would be read from `route.query`.

**AppShell** (`fe/src/components/AppShell.vue`)
- Imports are at 4-12.
- `screen = computed(() => route.meta.screen ?? 'rules')` is at line 32.
- Nav `RouterLink`s are at 195-212, with `v-if="online"`. Each has `:class="{ current: screen === 'x' }"`. Add a "Log" link after Mail.
- Screen switching is at 267-272: a `v-if/v-else-if` chain with `MailLogin`, `SampleErrorView`, `MailView` (which takes `@unauthorized="logOut"`), `AccountsView` and `GitView`, then the rules body.
- Add `<ActionLogView v-else-if="screen === 'log'" @unauthorized="logOut" />`.
- The topbar rules-file buttons are hidden only for `screen !== 'mail'` (line 223). They would show on the Log screen unless you extend that condition.

**Screen structure** (`fe/src/components/GitView.vue`)
- Script setup, local `ref`s, `onMounted(() => void load())`.
- A `message` ref shown as `<p class="message" @click="message = ''">`, and `describeError(error)` from `@/model/http`.
- Template is `<section class="git">` with `<header class="row"><h2>…`, and badges `.badge.ok/.error`, `.hint.mono`.
- Styles live in the single `fe/src/styles/main.scss` (`.git` block at about line 427, `.mail-log` at about 759).
- `AccountsView.vue` follows the same pattern.

**API client pattern**
- `fe/src/model/http.ts`: `ApiError(messages, status)`, `failure(response)` and `describeError`.
- `fe/src/model/git-api.ts` is the template: `const BASE = '/api/git'`, typed interfaces, and plain `fetch` with `if (!response.ok) throw await failure(response)`.
- `fe/src/model/mail-api.ts` has `const MAIL = '/api/mail'` and a `json<T>()` helper.
- `fe/src/model/mail-api.ts` has the `MailEvent` interface (116-122) and `listEvents` (124-133), using `URLSearchParams` for the query.
- `fe/src/model/accounts-api.ts` has `listAccounts()` (46), which you need for the account filter dropdown.
- `fe/src/model/mail-api.ts` also exports `logout`, `ApiError` and `getMessage`.

**MailLog and wording**
- `fe/src/components/MailLog.vue` is 18 lines. It takes `events: MailEvent[]` and renders `<details class="mail-log" open><ol><li :class="event.kind"><time :datetime>{{ fullDate(created_at) }}</time><span class="what">{{ eventLabel(event) }}</span>`.
- Wording comes from three functions:
  - `eventLabel` (`fe/src/model/mail-format.ts:108-121`): `first_seen` gives "First seen", `rule_match` gives `Matched the rule "x" (new)`, `action` gives `${describeLoggedAction(detail)} by the rule "x"`, `user_action` gives `describeUserAction`.
  - `describeUserAction` (`mail-format.ts:96-106`).
  - `describeLoggedAction` (`fe/src/model/dry-run.ts:159`).
- `fullDate` is at `mail-format.ts:52`, and `shortDate` at 42.
- All of these take only `{kind, rule_name, detail}`, so a new log row type can reuse them directly.
- To reuse the component itself, extend it or add a new row component. MailLog is wrapped in a `<details>` and has no account/folder columns.

**Vitest** (`fe/vitest.config.ts`, jsdom, excludes `e2e/**`)
- Specs are in `fe/src/__tests__/*.spec.ts`: `git-api.spec.ts`, `mail-api.spec.ts`, `accounts-api.spec.ts` and others.
- API spec pattern: `vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(data), { status })))`, then assert `fetchMock` was called with the exact URL, and `afterEach(() => vi.unstubAllGlobals())`.
- Component tests are in `components.spec.ts` (MailLog tests at about lines 117-128). Label tests are in `dry-run.spec.ts`, which calls `eventLabel`.
- Scripts are `yarn test` (vitest run) and `yarn test:e2e` (playwright).

**Playwright e2e** (`fe/e2e/*.spec.ts`)
- Each spec defines its own `mockServer(page)` using `page.route('**/api/...', route => route.fulfill({ json }))`.
- Every one stubs `**/api/editor/config` (`{mode:'server', source:'database', file_name:null, exists:false}`) so that `online` becomes true.
- It also stubs `**/api/editor/rules` with a 404.
- `fe/e2e/git.spec.ts:29-70` is the stateful-mock template.
- `fe/e2e/mail-mock.ts` is shared: `ACCOUNT_ID`, `mockServer(page, wrongPassword, rulesYaml)` with a login state machine (401 on the config until `/api/auth/login`), plus the `/api/accounts` and `/api/mail/**` stubs, including `/events` returning `EVENTS`.
- A Log e2e needs a new route handler for the new endpoint, ordered before or after the broad `**/api/mail/**` depending on the path. If you use `/api/events`, there is no clash.

## Things to decide
- **Watcher timestamp storage:** in-memory attributes on `Watcher`, or a new persisted table or column (a new 0006 migration). The in-memory option needs no migration but resets on restart.
- **Where "last run" ticks:** Today the Watcher cannot see a poll or IDLE wake-up unless you add a callback through `matches()` and `follow_changes()`.
- **New query indexes:** probably an index on `created_at` (and maybe `kind`) for the cross-account list.