# Plan: optional account check when creating and editing an account

Todo `77326de9-35af-42c6-8194-67746b52a1ad` (project remote_imap_mail_rules).
It is the first open todo that is not parked: the Vue-1 subtask is parked per the recent plan commits.

## Context

Today a wrong host or password is only noticed later, as "Please check" on the account after the watcher fails to log in.
The account form should be able to try the login right away.
Decision (user): a `Test connection` button, plus a check on every Save where a failed check keeps the form open and offers `Save anyway`.
Saving is therefore never blocked for good, so the check stays optional.

## Backend

- New endpoint `POST /api/accounts/check` in `src/remote_imap_mail_rules/server/api/accounts.py`, declared before the `/{account_id}` routes.
  Body `AccountCheck`: the fields of `AccountIn` plus `id: UUID | None` and `password: str | None`.
  An omitted password with an `id` of a stored account uses the stored one (`repository.get_account`, decrypted by `repository.imap_settings`); no password and no stored account is 422.
  A changed host, port, ssl or username with the stored password is fine, the stored password is just reused.
- It builds `ImapSettings` for the form values and opens an `ImapClient` with the **plain** factory, not the recording one, so the check never touches `auth_*` on the account.
  The factory is `app.state.imap_factory` today and is already wrapped by `recording_factory`; check in `server/app.py` whether the unwrapped factory is kept, and store it as `app.state.raw_imap_factory` if not.
- Answer is always 200 with `{ok: bool, kind: "ok" | "rejected" | "unreachable" | "timeout" | "no_password", message: str}`.
  Mapping reuses the logic of `imap_session`: `ImapLoginError` not `transient` is `rejected` (with `server_text`), `TimeoutError` is `timeout`, other `ImapError` / `aioimaplib.AioImapException` / `OSError` / transient login errors are `unreachable`.
  Not 4xx/5xx, because the Sentry integrations report every 5xx `HTTPException` and a failed check is an expected result.
- Behind `require_login` like the other account routes.
- Never log the password; the message contains only the server's text.

## Frontend

- `frontend/src/model/accounts-api.ts`: `checkAccount(input, id?)` and the `AccountCheckResult` type.
- `frontend/src/components/AccountsView.vue`:
  - `Test connection` button beside Save, showing a pending state and the result inline in the form (`ok` green, otherwise the message).
  - `submit()` runs the check first. On a failed check the form stays open, shows the message and the buttons `Save anyway` and `Cancel`; `Save anyway` skips the check once.
  - The check is skipped on edit when neither host, port, ssl, username nor password changed (only name, page size, poll interval or id), so renaming never needs a network call.
- Keep it in the component; no new store state (the result is component-local).

## Tests

- `tests/test_server_accounts.py`: using `FakeServer` and the `imap_factory` the app already takes
  - ok login, rejected login (kind `rejected`, text kept), timeout, unreachable;
  - edit without password uses the stored one (assert via the fake's received credentials);
  - the check leaves `auth_ok_at`, `auth_failed_at` and `auth_fail_count` untouched;
  - 401 without login; no password and no stored account.
- `frontend/src/__tests__`: `checkAccount` request shape.
- Playwright e2e (mocked `/api`): test button shows ok and failure; Save with a failing check shows `Save anyway`; renaming only skips the check.

## Docs

Add one line about `POST /api/accounts/check` (no login history written, always 200) to the Decisions in `CLAUDE.md`, and mention the form behaviour next to the accounts screen text.

## Verification

`uv run pytest`, `cd frontend && yarn lint && yarn test && yarn build && yarn test:e2e`.
Only fakes and mocks are used; the live account is never touched (see memory).

## Workflow afterwards (todo-loop)

Sync todos, then commit the work as plain commits, tick the todo, `complete_todo(7, uid)`, sync the project, tag a backup with `scripts/tag_backup.py`, rebase into one commit and verify an empty diff to the tag.
