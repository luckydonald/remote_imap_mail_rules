# Stage 6b: moving mails between accounts

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Stage 6a executes rule actions inside one account.
A `move` with an `account_id` of another account is currently planned as `skipped` (`cross_account_not_supported`, `actions.py:149`).
This stage makes it real and writes the moved mail's log under its new key.
`user_action` entries are out of scope and stay in "Not built yet" (decided with the user).
Delivery is APPEND first, then delete at the source, so a failure in between leaves a duplicate and never loses the mail.
All tests use `FakeServer` only, never a real account.

## Commits (separate tasks, in this order)

1. **IMAP layer**: raw fetch, APPEND, delete, new-UID results.
   - `imap/connection.py`: add `append(...)` to the `ImapConnection` protocol (aioimaplib has it).
   - `imap/client.py`: `fetch_raw(folder, uid)` (`BODY.PEEK[]`, plus flags and `INTERNALDATE`), `append(folder, raw, flags, internaldate) -> Moved`, `delete(folder, uid)` (`\Deleted` + `UID EXPUNGE`, refused without `UIDPLUS`; refactor the copy fallback of `move` to use it), and `find_message_id(folder, message_id)` via `UID SEARCH HEADER Message-ID`.
   - `move` returns a `Moved(folder, uid, uidvalidity)` parsed from `COPYUID` / `APPENDUID` when the server sends it, else `uid=None`.
   - `tests/fake_imap.py`: `append`, full `BODY.PEEK[]`, and `COPYUID` / `APPENDUID` responses; extend the `uid()` assertion.
   - Tests in `tests/test_imap_write.py`.
2. **Actions**: `actions.py`.
   - `plan_steps`: a move to another account becomes a normal `move` step (last, ends the chain, only the first move counts); drop `cross_account_not_supported`.
   - `Writer.move(mail, folder, account_id=None) -> Moved | None`; `Moved` also carries `account_id`.
   - `ChainResult.moved_to` becomes `moved: Moved | None`; update `run_chain`, `execute_steps`, the dry run and the frontend mapping that read `moved_to`.
   - `ImapWriter` gets a `target(account_id)` async callable returning a second `ImapClient`.
   - Cross-account sequence: skip APPEND if `find_message_id` already finds it in the target (restart safe), `fetch_raw`, `append` with the original flags and `INTERNALDATE`, then `delete` at the source.
   - If the delete fails the step is `error` with reason `source_not_deleted` and the new location is still returned, so the log stays honest.
   - Unknown target account: `error` step, reason `unknown_account`.
   - Loop guard: more than a few moves of one `message_id` (counted in `mail_events`) end in an `error` step with reason `move_loop`, so rules A to B and B to A cannot ping-pong.
   - `ActionRunner` keeps a small per-run cache of target clients built from `account_repository.imap_settings`; `VirtualWriter` only reports planned steps.
3. **Log continuation**: `server/watcher.py` `write_actions`, `db/mail_events.py`.
   - After a `done` (or `source_not_deleted`) move with a known new UID, also write an `action` event under the target key `(account_id, folder, uidvalidity, uid)` with detail `{type: moved_in, from: {account_id, folder, uid}}`, same `message_id`.
   - Add `list_events_by_message_id` so the message view can show the earlier history; `GET .../events` unchanged unless the user wants it merged (to confirm during implementation, default: append "earlier events" section only if cheap).
   - `first_seen` at the target stays with the target folder's watcher, deduplicated by `has_event`.
   - `server/api/dry_run.py` run-now passes the same `write_actions`, so no extra work.
4. **Frontend**: `frontend/src/model/dry-run.ts` text for cross-account moves (shows the target account), update the fixture in `src/__tests__/dry-run.spec.ts`, show `moved_in` in `MailLog.vue`.
5. **Docs**: `CLAUDE.md` (Decisions: actions, action log, dry run), `ai/initial.md` (close 6b, trim "Not built yet"), `README.md` if it lists actions; fix the stale `EventKind` docstring in `db/models/mail_event.py`.

## Reuse

- `ImapClient.move`, `select`, `ensure_writable`, `fetch_message` / `build_mail` in `imap/client.py`.
- `imap_session` factory on `app.state.imap_factory` and `account_repository.imap_settings` for per-account clients.
- `record_event` / `has_event` in `db/mail_events.py`; the `LOGGED_STATUSES` filter and `write_actions` in `server/watcher.py`.
- `FakeServer` (one instance per mailbox) with a factory that picks by `settings.imap_account_id`.

## Verification

- `uv run pytest`: new tests in `test_actions.py` (cross-account plan and apply, delete failure, unknown account, loop guard, restart does not duplicate), `test_imap_write.py` (append, raw fetch, `COPYUID` / `APPENDUID`), `test_server_watcher.py` (events under both keys, `message_id` linked), `test_server_dry_run.py` (dry run shows a planned cross-account move, writes nothing).
- `uv run python -m remote_imap_mail_rules.rules.schema --check` stays green (no model change expected).
- `cd frontend && yarn test && yarn lint && yarn build`, and `yarn test:e2e` for the dry run panel (Playwright, not Chrome).
- No run against a real mailbox; `ACTIONS_ENABLED` stays false by default.
