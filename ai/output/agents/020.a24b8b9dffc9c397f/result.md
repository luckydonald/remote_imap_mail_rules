Findings for stage 6b, facts only. All paths are under `/Users/user/Documents/programming/Python/remote_imap_mail_rules`. `src/` below means `src/remote_imap_mail_rules/`, and `tests/` is `/Users/user/Documents/programming/Python/remote_imap_mail_rules/tests/`.

## actions.py (`src/actions.py`)
- **Step types** (`actions.py:31-72`):
  - `StepStatus` is planned, done, noop, skipped or error (`:31-37`).
  - `Step` is a frozen dataclass: `type`, `args`, `status`, `reason`, `add`, `remove`. `changes_mail` is true only when the status is `done` (`:40-55`).
  - `Round(rule, steps)` is at `:58`.
  - `ChainResult(mail, rounds, moved_to: str | None)` is at `:65-72`. `moved_to` is only a folder string and carries no account, new UID or new uidvalidity.
- **`plan_steps`** (`:122-162`):
  - The cross-account case is at `:149-151`. If `action.account_id` is set and differs from `mail.account_id`, it sets `args["account_id"]=str(...)` and appends `Step("move", args, skipped, "cross_account_not_supported")`.
  - It does not set the local `move` variable, so the chain does not end.
  - A later same-account move in the same rule can still become the real move.
  - Otherwise: a repeat move is `skipped` with reason `superseded` (`:152`), a move to the current folder is `noop` with reason `already` (`:154`), and anything else becomes `move = Step("move", args)`, appended last (`:161`).
- **Writer protocol** (`:75-78`): `store_flags(mail, add, remove)` and `move(mail, folder)`, both returning None. There is no cross-account method and no return value.
- **`ImapWriter`** (`:81-95`) wraps one `ImapClient` and calls `client.store_flags` and `client.move(mail.folder, mail.uid, folder)`.
- **`VirtualWriter`** (`:98-108`) does nothing.
- **`execute_steps`** (`:180-211`):
  - It skips non-`planned` steps (they are copied through unchanged) and stops at the first error.
  - A move calls `writer.move` and sets `moved_to = args["folder"]` (`:195-197`).
  - It catches only `ImapError`.
- **`run_chain`** (`:224-248`): a non-None `moved_to` ends the chain (`:239-241`).
- **`ActionRunner`** (`:256-310`):
  - It holds one `ImapClient` for one account, built from `ImapSettings` (`imap_account_id`), plus `rule_file`, `factory` and `by_folder`.
  - `run(mail)` does a fresh `fetch_message` on that account and then `run_chain(..., ImapWriter(client))` (`:296-309`).
  - It has no way to reach a second account's client.
- `apply_actions` is at `:313`.

## imap/client.py (`src/imap/client.py`)
- **Write methods**:
  - `select`, `ensure_writable`, `store_flags` (`:147-172`).
  - `move(folder, uid, target)` (`:174-188`): `UID MOVE` if the server has the MOVE capability, otherwise `UID COPY` + `STORE +FLAGS.SILENT (\Deleted)` + `UID EXPUNGE`, which needs UIDPLUS. It returns nothing, so there is no `COPYUID` or `APPENDUID` parsing and no new UID.
- **Not present**: APPEND, and any raw RFC822 fetch. `grep` found no `append`, `RFC822` (other than the `RFC822.SIZE` field) or `BODY.PEEK[]` full-message fetch in the client.
- **Fetching and state**:
  - `fetch(uid_set, fields)` (`:229`) is the generic fetch.
  - `fetch_part(folder, uid, number)` (`:293`) gets one part, `load_bodies` (`:369`) the text parts. Both use `BODY.PEEK[n]`.
  - `fetch_mails` (`:234`), `fetch_message` (`:286`) and `build_mail` (`:327`) build the `Mail`.
  - `poll_state` (`:190`) is a STATUS call. `examine` and `select` return a `FolderState` with uidvalidity and uidnext.
  - `ImapClient.state` holds the last state, so a target folder's uidvalidity is available after a `select`.
- **Connection protocol** (`src/imap/connection.py`): `ImapConnection` exposes `select`, `examine`, `status`, `list`, `uid_search`, `uid(command, *criteria)`, `noop` and the IDLE methods. It has no `append`. Any APPEND would need the protocol extended and `tests/fake_imap.py` extended too.

## Watcher (`src/server/watcher.py`)
- **Queue entries** (`:29-43`): `Seen`, `RuleMatch` and `Act(mail)`.
- **`follow(account_id)`** (`:119-166`):
  - It loads the account and its `ImapSettings` via `account_repository.imap_settings`, reads and parses the rules, and builds a queue.
  - It builds one `ActionRunner(settings, rule_file, self.imap_factory)` per account, only if `actions_enabled` is set (`:145`).
  - It consumes `matches(...)`. For each match it queues the `RuleMatch`, and queues `Act` once per `(folder, uid, uidvalidity)` key (`pending` set).
- **`record()`** (`:168-192`):
  - A single consumer writes entries in order. On `Act` it calls `runner.run(entry.mail)` and then `write_actions`, then commits.
  - So a client exists only for its own account. `Watcher` has `imap_factory` and `session_factory` and can get settings for any account via `account_repository.get_account` and `imap_settings`, but nothing does so for a second account today.
  - Clients are per `watch_account` task and are not shared between accounts.
- **`write_actions`** (`:194-210`):
  - It writes one `EventKind.action` per step whose status is in `LOGGED_STATUSES` (done, error, skipped; `:45`).
  - The detail is `{"type", "status", **step.args, "reason"?}`, with `rule_name=round_.rule.name`.
  - The key is `result.mail`, which is the mail as it was before the move: its old folder, uid and uidvalidity. Flags are mutated in place but folder and uid are not.
  - So today a cross-account move is logged as `skipped` with `account_id` in `detail`, via `write_actions`.
- **`add()`** (`:230-242`) calls `mail_events.record_event` with `mail.account_id`, `folder`, `uid`, `uidvalidity` and `message_id` (from the `Message-ID` header).
- **`write()`** (`:212-228`) handles `Seen` and `RuleMatch`. `first_seen` is deduplicated with `has_event(... uidvalidity)` at `:215`.
- **Other callers of `write_actions`**: `src/server/api/dry_run.py:240-282` (`POST /run`, "run now"). It is gated on `settings.actions_enabled` (409 `actions_disabled`). It builds one `ActionRunner` per used account's `ImapSettings` (`used`), and calls `request.app.state.watcher.write_actions`.

## DB (`src/db/mail_events.py`, `src/db/models/mail_event.py`)
- **`EventKind`** (`mail_event.py:15-22`): `first_seen`, `rule_match`, `action`, `user_action`. The docstring says `action` and `user_action` are "reserved", which is stale now, since `action` is in use. `user_action` is defined but written nowhere.
- **`MailEvent`** (`:25-41`) is table `mail_events`.
  - Columns: `id`, `account_id` (FK accounts, cascade), `folder`, `uidvalidity` (nullable), `uid`, `message_id`, `kind`, `rule_name`, `detail` (JSON) and `created_at`.
  - The only index is `ix_mail_events_mail` on `(account_id, folder, uid)`.
  - The docstring says `message_id` "survives moves between accounts".
- **Repository** (`mail_events.py`):
  - `record_event(session, account_id, folder, uid, kind, *, uidvalidity, message_id, rule_name, detail)` flushes (`:12-37`).
  - `list_events(session, account_id, folder, uid)` filters on account, folder and uid only, not on uidvalidity, ordered by `created_at, id` (`:40-48`).
  - `has_event` takes `uidvalidity` and `rule_name` (`:51-70`).
  - There is no lookup by `message_id`, and no function that copies events to a new key.
- **Events API** (`src/server/api/events.py:32-36`): `GET /accounts/{id}/messages/{uid}/events?folder=` returns `kind`, `rule_name`, `detail` and `created_at`. It is read-only and keyed by account, folder and uid.

## Mail API (`src/server/api/mail.py`)
- It is explicitly read-only (docstring `:1`). The endpoints are:
  - `GET /accounts/{id}/folders` (`:22`)
  - `GET .../messages` (`:42`)
  - `GET .../messages/{uid}` (`:60`)
  - `GET .../messages/{uid}/parts/{part}` (`:86`)
- It has no write endpoint, so nothing records a user action.
- **Per-request client**: `src/server/imap_session.py` `imap_session(request, session, account_id)` opens an `ImapClient` per account and request. It maps errors to 404, 503, 502 or 504. This is the existing mechanism for getting a client for any account.
- **User-driven change detection**: the watcher's `matches(... kind: existing/new/changed)` in `src/matching.py` (`MatchKind`) yields flag changes via CONDSTORE `fetch_changed`. Changes that rule actions caused are indistinguishable from user changes there. Nothing separates the two today.

## dry_run.py (`src/dry_run.py`)
- It runs `run_chain` with `VirtualWriter` on `replace(mail)` copies (`:62-71`).
- It only inspects the mails of one account per `ImapSettings` (`dry_run_page` and `dry_run_account` take a single settings object). `rules_by_folder` skips locations of other accounts (`src/matching.py:~48`).
- A cross-account move shows up as a `skipped` step with reason `cross_account_not_supported` and `args["account_id"]`.
  - `as_planned` only converts `done` to `planned`, so skipped steps stay skipped (`:115-117`).
  - `summarize` groups by type, status, folder, keyword and reason (`:162-176`). It ignores `args["account_id"]`.
- **Frontend**: `frontend/src/model/dry-run.ts:138` maps the reason to the text "moving to another account is not supported yet". `frontend/src/__tests__/dry-run.spec.ts:37` has a fixture using it.

## FakeServer (`tests/fake_imap.py`)
- **Commands**:
  - `login`, `logout`, `examine`, `select`, `status`, `list`, `uid_search`, `noop`, and the IDLE methods.
  - `uid()` supports fetch, store, copy, move and expunge. It asserts `name in {"store","copy","move","expunge"}` at `:~208`, so any other command raises an AssertionError.
- **No APPEND**: `FakeConnection` has no `append` method.
- **Write behaviour**: it requires SELECTED state and a writable folder. The `NO [READ-ONLY]` response is returned if the folder was only examined.
- **Copy and move**:
  - They create the new message with `uid = max(target uids)+1`, copy `raw`, `flags` and `body` (not `parts`, `structure` or `internaldate`), and bump the target's `modseq`.
  - They return no `COPYUID`. A plain `OK done`.
- **No raw RFC822 fetch**: `uid_fetch` handles `BODY.PEEK[HEADER]`, `BODY.PEEK[n]` and flags only.
  - `message.raw` holds only headers (`From`, `Subject` and a blank line), and `body` is a separate field.
- **Per-account setup**: `FakeServer.connect(settings)` ignores the settings. One `FakeServer` is one mailbox, so a cross-account test would need two servers and a factory that picks by `settings.imap_account_id`.
- **Other fields**: `FakeFolder.uidvalidity` defaults to 1. `FakeServer.commands` is a log of command strings.

## Existing tests
- **`tests/test_actions.py`** (7 tests):
  - `test_plan_marks_noops_and_puts_the_move_last` (`:55`) includes the cross-account skipped step (`:61-68`).
  - `test_apply_changes_the_mailbox` (`:75`).
  - The chain tests: first match wins, re-evaluation after a change, a noop winner stops, errors stop later steps, `VirtualWriter` changes nothing.
- **`tests/test_imap_write.py`**: `store_flags` selects the folder, `examine` makes the folder read-only again, and move with MOVE, with copy plus expunge, and refused without either capability.
- **`tests/test_server_watcher.py`**: `test_actions_are_applied_and_logged_when_enabled` (`:254`), `test_nothing_is_written_when_actions_are_disabled` (`:276`), `test_a_restart_does_not_repeat_actions` (`:292`), plus first_seen and match logging and retries.
- **`tests/test_server_dry_run.py`**: summarize and list without writing, the unsaved file, the login requirement, the config's `actions_enabled`, run-now refused while disabled, `test_run_now_applies_and_logs` (`:124`) and paging.
- **Other IMAP fake users**: `tests/test_server_mail.py`, `test_imap.py`, `test_matching.py`, `test_imap_viewer.py` and `test_demo.py` also use the fake server.