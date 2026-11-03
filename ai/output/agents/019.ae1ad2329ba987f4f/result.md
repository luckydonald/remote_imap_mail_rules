All paths below are under `/Users/user/Documents/programming/Python/remote_imap_mail_rules`. `src/` stands for `src/remote_imap_mail_rules`.

## (1) IMAP layer and FakeServer

**Read-only enforcement** is by convention plus one test. The code never issues a write command, and the fake blocks one at the protocol level.
- `src/imap/client.py:1` says the client is read-only. `ImapClient.examine` (`client.py:132-144`) is the only way a folder is opened.
- `examine` forces `conn.protocol.state = aioimaplib.SELECTED` (`client.py:141`), because aioimaplib only reaches SELECTED via `select()`. Write commands like STORE and EXPUNGE are therefore legal in aioimaplib's state machine, but the folder is open read-only on the server. Stage 6 needs a real `select()` for write folders.
- Every body fetch uses `BODY.PEEK`: `FETCH_FIELDS` at `client.py:22-23`, `fetch_part` at `client.py:252`, `load_bodies` at `client.py:328`.
- The generic `fetch(uid_set, fields)` at `client.py:185` calls `conn.uid("fetch", ...)`. Searches go through `conn.uid_search`.
- `ImapError` and `check(response, what)` (`client.py:29-50`) raise on any non-OK reply. `quote_folder` is at `client.py:346`.

**The connection protocol** is `src/imap/connection.py:8-26`, and its docstring says "Only read-only commands are listed on purpose". It exposes:
- `protocol` (with `capabilities` and `state`), `wait_hello_from_server`, `login`, `logout`
- `examine`, `status`, `list`, `uid_search`, `uid(command, *criteria)`, `noop`
- `idle_start`, `wait_server_push`, `idle_done`, `has_pending_idle`

For writes you would add to the protocol:
- `select`, plus `uid` (already present) for `STORE`, `COPY` and `MOVE`. aioimaplib's `uid("store", ...)` and `uid("copy", ...)` work, and `uid("move", ...)` needs the MOVE capability or a COPY plus STORE `\Deleted` plus `uid_expunge` fallback.
- `append(message_bytes, mailbox, flags, date)` for cross-account moves, `expunge`, and possibly `create`.
- Cross-account moves need a source `fetch` of `BODY.PEEK[]` (the full RFC822, which does not exist yet) and an `APPEND` to the target account. That needs a second `ImapClient` on the target account's settings, built from `db.accounts.imap_settings` with the same factory.
- The ImapClient context manager takes one `ImapSettings`, which holds `imap_account_id` (`config.py:19`).

**Connection use**
- `matching.follow_folder` (`matching.py:139-162`) opens one `ImapClient` per folder, which is used for IDLE. Do not run actions on those connections, because IDLE blocks them. Use a separate short-lived client per action batch, like the browser's `server/imap_session.py:18-33`, which creates `ImapClient(imap_settings, request.app.state.imap_factory)`.
- `imap/watcher.py` has the IDLE and poll loop. The folder must already be examined.
- Moving or flagging a mail in a watched folder triggers an IDLE push and, with CONDSTORE, a `changed` match (`matching.py:127-133`). Flag changes made by actions could therefore re-trigger rule matching. Plan idempotency or loop protection.
- UIDs change after a move, and the watcher sees the copy as a `new` mail in the target folder.

**FakeServer** is `tests/fake_imap.py`.
- It is in-memory, with `FakeMessage(uid, raw, flags: str, modseq, body, ...)` and `FakeFolder(messages, uidvalidity, modseq)` (`fake_imap.py:13-31`).
- `FakeServer.add(folder, uid, subject, flags, sender)` is at `:52` and `set_flags(folder, uid, flags)` at `:61`. `push()` is at `:71` and `connect(settings)` at `:78`. `server.commands` logs the commands (`:48`), and `push_queues` simulates IDLE.
- `FakeConnection.uid` (`:189-208`) asserts `command.lower() == "fetch"` ("read only: only FETCH is allowed"). It must be extended for store, copy and move.
- `FakeConnection.examine` only sets `self.selected`. There is no `select`, `append` or `expunge`.
- `FakeProtocol.state` mimics aioimaplib: it stays AUTH after EXAMINE, and `require_selected` checks `state == "SELECTED"` (`:119-123`).
- Flags are a plain space-separated string. A single `FakeServer` has one folder dict, so cross-account tests need two `FakeServer`s and a factory that picks one per settings, e.g. by `imap_account_id`.
- `tests/test_imap.py:82-96` asserts no `STORE/COPY/MOVE/EXPUNGE/SELECT` commands ran (`test_pages_newest_first_and_readonly`). This still holds for the read paths, but the watcher tests will need adjusting once actions run.

## (2) Action models and carrying actions

- The action models are in `src/rules/models.py:421-474`:
  - `MoveAction(folder, account_id: UUID | None)` (`:421`; None means the mail's own account)
  - `MarkReadAction` (`:432`) and `MarkUnreadAction` (`:441`)
  - `FlagAction(value: bool = True)` (`:450`, maps to `\Flagged`)
  - `KeywordAction(keyword, value: bool = True)` (`:460`)
  - `Action[V]` is a discriminated union on `type` (`:471`).
- `Rule.actions` is at `:483` with the description "Parsed only; nothing executes them yet." Update that text.
- The rules reaching the matcher are `Rule[Never]`, so templates are already resolved.
- `matching.py:31-36`: `RuleMatch` is a frozen dataclass `(rule, mail, kind: MatchKind)`. `rule.actions` is available on it directly, so no model change is needed to carry the actions.
- `match_mails` (`matching.py:63-76`) yields one `RuleMatch` per matching rule per mail. If several rules match the same mail and each moves it, ordering and conflicts matter. The list order follows `rule_file.rules`.
- `MatchKind` is `existing`, `new` or `changed` (`:24`).
- `Mail` is in `src/mail.py:~40`, with `account_id`, `folder`, `uid`, `headers`, `flags: frozenset[str]`, `uidvalidity` and `modseq`.

## (3) Watcher, events, frontend

**`src/server/watcher.py`**
- `Watcher` is at `:36`. `follow()` (`:104-141`) consumes `matches(settings, rule_file, self.imap_factory, on_inspect=...)` and puts `Seen(mail)` and `RuleMatch` entries on one `asyncio.Queue[Entry]`.
- `record()` (`:143-158`) is a single consumer that writes each entry in its own session and commit, in queue order, and logs exceptions per entry.
- `write()` (`:160-176`) does these things:
  - `Seen` writes `first_seen`, guarded by `has_event`.
  - A `RuleMatch` of kind `existing` is logged once, guarded by `has_event` for `rule_match` with the rule name.
  - New and changed matches are logged every time, with `detail={"match_kind": ...}`.
  - `add()` (`:178-190`) wraps `mail_events.record_event` and fills `message_id` from the `Message-ID` header.
- Stage 6 hook points: a new `Entry` type, or an executor step in `follow()`/`write()` after the `rule_match`. Note `existing` matches rerun on every start, so actions need a guard (e.g. `has_event(kind=action, rule_name=...)`) to avoid re-moving or re-flagging. `has_event` currently takes only `kind` and `rule_name`, so an action-type filter would go in `detail` or need a new parameter.
- `Watcher` takes `imap_factory`, `secret_key` and `session_factory`. It is built at `server/app.py:71`.

**`src/db/mail_events.py`**
- `record_event(session, account_id, folder, uid, kind, *, uidvalidity, message_id, rule_name, detail: dict)` (`:12-37`). It only flushes, so the caller commits.
- `list_events` is at `:40` and `has_event` at `:51`. `has_event` matches on account, folder, uid, kind, uidvalidity and rule_name, with `None` meaning IS NULL.

**`src/db/models/mail_event.py`**
- `EventKind` (`:15-22`) is `first_seen`, `rule_match`, `action` and `user_action`. Its docstring says "reserved".
- `MailEvent` columns (`:28-40`): `id`, `account_id` (FK with CASCADE), `folder` (String 1024), `uidvalidity`, `uid`, `message_id`, `kind` (String 32), `rule_name` (String 255), `detail` (JSON dict, default `{}`), `created_at`. Index `ix_mail_events_mail(account_id, folder, uid)`.
- `detail` is the free-form payload for the action type, its arguments, the target folder or account, the new UID, and an error or status field. No migration is needed for the kind values or for `detail`. Migrations are in `migrations/versions/0001..0003_*.py`; `0003_mail_events.py` is the latest.
- The log is keyed by `(account, folder, uid)`. After a move the UID changes, so an `action` entry for a move must be written under the source key. Consider also writing a continuation entry under the target key, linked by `message_id` and a detail field, otherwise the target mail's log starts empty. The model docstring (`:26`) says `message_id` survives moves between accounts.

**Events API**: `src/server/api/events.py:18-36`. `EventOut` has `id`, `kind`, `rule_name`, `detail` and `created_at`. It has no uid, folder or uidvalidity fields.

**Frontend**
- `frontend/src/components/MailLog.vue` is a thin `<ol>`. Each `<li>` gets `:class="event.kind"` and shows the time plus `eventLabel(event)`.
- `eventLabel` (`frontend/src/model/mail-format.ts:74-87`) is a `switch` on kind:
  - `first_seen` gives "First seen".
  - `rule_match` gives `Matched the rule "X" (match_kind)`.
  - `action` gives the placeholder `Rule "X" ran an action`.
  - `user_action` gives the placeholder "Changed by you".
  - It reads `event.detail.match_kind` only.
- Stage 6 would extend `eventLabel` to read `detail.type`, `detail.folder` and so on. The `MailEvent` TS interface is in `frontend/src/model/mail-api.ts:116-122` (`detail: Record<string, unknown>`). It already includes the `action | user_action` kinds, so only the label logic and tests need to change. There is no per-kind SCSS in the component itself.
- Frontend tests: `frontend/src/__tests__/components.spec.ts`, `mail-api.spec.ts`, `mail-store.spec.ts`, and `frontend/e2e/mail-mock.ts` and `mail.spec.ts`.

## (4) Test layout

- `tests/fake_imap.py` is the FakeServer. `tests/conftest.py` and `tests/settings.py` hold fixtures and settings.
- `tests/test_imap.py` covers the client, parsing and `watch` (see the read-only assertion above).
- `tests/test_matching.py` covers `matches()` with FakeServer (`take()` helper at `:43`).
- `tests/test_server_watcher.py` has these pieces:
  - A `StaticRules` stub (`:31`).
  - A `factory` fixture that makes a SQLite db via `upgrade`, plus an account with fixed `ACCOUNT` uuid and `KEY` (`:54`).
  - `make_watcher(factory, server, rules)` with `retry_delay=0.05` (`:68`).
  - The helper `kinds(...)` returns `(kind, rule_name)` tuples (`:73`) and `until(check)` polls with a 3 s timeout (`:80`).
  - Tests: `test_logs_first_seen_and_rule_matches` (`:89`), restart, no-rules, retries, and account and rule edits restarting the watcher.
- `tests/test_db_mail_events.py`, `tests/test_server_events.py` and `tests/test_db_migrations.py` cover events and migrations. `tests/test_rules_models.py` covers action parsing.
- The watcher test uses a single account (`ACCOUNT`). Cross-account tests need a second account row and a factory routing by `settings.imap_account_id` to two FakeServers.

## (5) ai/ folder

There is no stage-6 plan. Relevant files:
- `ai/initial.md`:
  - Lines 17-21 list the action log, including "moves between folders, read/unread states" and "either rule actions or user's own actions". Line 16 says "including moving mails between" accounts.
  - Line 96 says the action tables come with stage 5; lines 125-127 say `action`/`user_action` are not written until actions are executed.
  - Lines 161-165 ("Not built yet") list moving between accounts, executing rule actions and the action and user action entries.
  - The "## Implementation scope/stages" section starts at line 56.
- `ai/plans/011_stage-5-the-action-log-per-mail.md` is the closest template. It explicitly defers rule actions and writes. Its Decisions section says a mail is `(account_id, folder, uidvalidity, uid)` with `message_id` stored "for the later moves between accounts".
- Plans 002-010 are earlier stages; `ai/plans/` has nothing for stage 6. `ai/todo.md` has only synced meta-todos, nothing on actions.
- `CLAUDE.md:14,28,44,45,87` and `README.md` state the read-only rule and that actions are parsed only. Update these as part of the docs task: `CLAUDE.md:28` ("Writes will be added later without reshaping the interfaces, which already take account and folder"), the stage 5 log paragraph at `:45`, and the "Actions (parsed only)" line at `:87`.