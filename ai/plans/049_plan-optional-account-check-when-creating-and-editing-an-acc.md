# Plan: optional account check when creating and editing an account

Todo `77326de9-35af-42c6-8194-67746b52a1ad` (project remote_imap_mail_rules).
**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

The loop first picked the `REMOTE-IMAP-MAIL-RULES-VUE-1` subtask again, but plan 046 already parks it until Bugsink has new events.
Bugsink still shows the same 2 events (last 2026-11-05) with no stack trace, so it stays parked and this run takes the next open todo.
Plan 048 for that todo was saved earlier but never implemented; this plan is that one, checked against the code.

Today a wrong host or password is only noticed later, as "Please check" on the account after the watcher fails to log in.
The account form should be able to try the login right away.
Decision (user): a `Test connection` button, plus a check on every Save where a failed check keeps the form open and offers `Save anyway`.
Saving is never blocked for good, so the check stays optional.

## Backend

- New endpoint `POST /api/accounts/check` in `src/remote_imap_mail_rules/server/api/accounts.py`, declared before the `/{account_id}` routes.
  Body `AccountCheck`: the fields of `AccountIn` plus `id: UUID | None` and `password: str | None`.
  An omitted password with an `id` of a stored account uses the stored one (`repository.get_account`, decrypted by `repository.imap_settings`).
  No password and no stored account is 422.
- It opens an `ImapClient` with the **plain** factory, not the recording one, so the check never writes `auth_*` on the account.
  `app.py:80` rebinds `imap_factory` to the `recording_factory` wrapper, so keep the original as `app.state.raw_imap_factory` before that line.
- Answer is always 200 with `{ok, kind: "ok" | "rejected" | "unreachable" | "timeout", message}`.
  Mapping follows `imap_session`: a non-transient `ImapLoginError` is `rejected` (server text kept), `TimeoutError` is `timeout`, other `ImapError` / `OSError` / transient login errors are `unreachable`.
  Not 4xx/5xx, because the Sentry integrations report every 5xx `HTTPException` and a failed check is an expected result.
- Behind `require_login` like the other account routes. The password is never logged.

## Frontend

- `frontend/src/model/accounts-api.ts`: `checkAccount(input, id?)` and the `AccountCheckResult` type.
- `frontend/src/components/AccountsView.vue`:
  - `Test connection` button beside Save, with a pending state and the result inline.
  - `submit()` runs the check first. A failed check keeps the form open, shows the message and offers `Save anyway` and `Cancel`; `Save anyway` skips the check once.
  - On edit the check is skipped when host, port, ssl, username and password are unchanged.
  - The result is component-local, no new store state.

## Tests

- `tests/test_server_accounts.py` with `FakeServer`: ok, rejected (text kept), timeout, unreachable; edit without password uses the stored one; `auth_*` fields untouched; 401 without login; no password and no stored account.
- `frontend/src/__tests__`: `checkAccount` request shape.
- Playwright e2e (mocked `/api`): test button ok and failure, `Save anyway` flow, rename-only skips the check.

## Docs

One line in the `CLAUDE.md` Decisions about `POST /api/accounts/check` (no login history written, always 200), and the form behaviour next to the accounts screen text.

## Verification

`uv run pytest`, then `cd frontend && yarn lint && yarn test && yarn build && yarn test:e2e`.
Only fakes and mocks are used; the live account is never touched.
