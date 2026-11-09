# Plan: Track IMAP login failures per account, flag "please check", stop reporting them to Sentry

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Bugsink REMOTE-IMAP-MAIL-RULES-9 (todo `97650feb`) holds 3 events of `HTTPException 502 "The mail server failed: login failed: NO [b'authentication failed']"` on `GET /api/mail/accounts/{id}/folders`, two of them 12 s apart and one 7 hours later.
`imap_session` (`server/imap_session.py`) turns every `ImapError` into a 502, and the Sentry FastAPI/Starlette integrations report every 5xx `HTTPException` by default, 4xx are not reported.

**Is it really wrong credentials, or a library failure?**
The text is not made up by aioimaplib: `ImapClient.connect` (`imap/client.py:115`) gets a tagged `NO` answer to the `LOGIN` command, and `authentication failed` is the server's own text, so the library did its job.
But the server's `NO` does not prove the password is wrong: a server can also answer `NO` while its auth backend hiccups or rate-limits, and this one sent no response code (`[AUTHENTICATIONFAILED]`, `[UNAVAILABLE]`) to tell them apart.
The data cannot settle it either (3 events, no success recorded between them).
So the plan does not assume it: RFC 5530 codes that say "not the credentials" (`UNAVAILABLE`, `SERVERBUG`, `INUSE`, `LIMIT`) stay a transient 502 and are not counted, everything else is a login rejection, and the new history (failures, last success) shows whether it was a one-time burp or is still going on.
The server's answer text is stored too, so the next such case can be judged by looking at it.

## Data: new columns on `accounts` (migration 0007)

All on `Account` in `db/models/account.py`:

- `auth_updated_at` (DateTime tz, not null, default now): the last time username or password were set (create, or an update that changes the username or sends a password).
- `auth_failed_at` (nullable): time of the last rejected login.
- `auth_fail_count` (Integer, default 0): rejected logins since `auth_updated_at`.
- `auth_ok_at` (nullable): time of the last successful login.
- `auth_last_error` (Text, nullable): the server's answer to the last rejected login (no secrets in it, it is the server's reply).

"Please check" is derived, not stored: `auth_failed_at is not None and (auth_ok_at is None or auth_ok_at < auth_failed_at)`, so a later success clears the flag by itself while the count and last failure time stay as history.
Changing the username or password resets `auth_failed_at`, `auth_fail_count`, `auth_ok_at` and `auth_last_error` and sets `auth_updated_at = now` (in `update_account` in `db/accounts.py`, only when the username differs or a password is given; `create_account` sets `auth_updated_at`).
Host, port and ssl changes do not reset anything, the history then still tells what happened.
Migration 0007 written with `uv run alembic revision --autogenerate`, existing rows get `auth_updated_at = created_at`-ish (server default now is fine); the drift test must stay green.

## Backend

- `imap/client.py`: `class ImapLoginError(ImapError)` with `transient: bool` and the server text.
  `connect` raises it when `LOGIN` is not `OK`; `transient` is true when the answer carries one of the RFC 5530 codes above.
  Other commands keep `check()` and `ImapError`.
  Subclassing keeps every existing `except ImapError` working.
- `db/accounts.py`: `record_login(session, account_id, error: str | None)`, one function for both outcomes.
  Failure: `auth_failed_at = now`, `auth_fail_count += 1`, `auth_last_error = error`.
  Success: `auth_ok_at = now`, but only written if it is unset, older than 5 minutes, or the account is flagged (so the many connections the watcher opens do not write on every login).
  Transient errors are not recorded.
- `server/imap_session.py`: catch `ImapLoginError` before the generic branch.
  Non-transient: `record_login(error=...)`, commit that on its own (the request session is otherwise only read), answer `HTTPException(424, "The mail server rejected the login: <text>")`.
  424 and not 401, because the frontend treats 401 as "admin session expired" and shows the login screen; not 5xx, so no Sentry event.
  Transient: stays 502.
  On a successful `async with ImapClient(...)` enter, `record_login(None)`.
  Update the docstring (404 / 503 / 424 / 502 / 504).
- `server/watcher.py`: the watcher opens its own connections and already catches `ImapError` (around line 192) and retries.
  It calls `record_login` the same way (own session from `session_factory`) on `ImapLoginError` and on a successful connect, so an account nobody browses is flagged too.
  Read the surrounding code before editing and keep the retry behaviour as is.
- `server/api/accounts.py`: `AccountOut` gets `auth_updated_at`, `auth_failed_at`, `auth_fail_count`, `auth_ok_at`, `auth_last_error`, `needs_check` (computed); they are read only, `AccountIn`/`AccountUpdate` do not carry them.

## Frontend

- `model/accounts-api.ts`: add the fields to `Account`.
- `AccountsView.vue`: a "⚠ Please check" badge on an account with `needs_check`, and a details block per account with: last password/username change, last successful login, last failed login, failure count, the server's last answer.
  The mail account picker (the store's `accounts`) may show the same badge if it is cheap; if not, leave it out.
- The mail browser shows the 424 text through the existing `ApiError` (it prints `detail`), no change needed there.

## Tests

- `tests/test_server_mail.py`: login `NO` without code gives 424 and the detail has `authentication failed`; login `NO [UNAVAILABLE]` gives 502; the account row shows count 1 and `auth_last_error` after the first, nothing after the transient one.
  Check whether `FakeServer` can reject a login, else add that option.
- `tests/test_db_accounts.py` (or the existing accounts test file): `record_login` failure then success clears `needs_check` but keeps the count; the 5 minute throttle; a username or password change resets the fields and sets `auth_updated_at`, a host change does not.
- `tests/test_server_accounts.py`: the API output carries the fields and `needs_check`.
- Watcher test: a rejected login is recorded, if the existing watcher tests make that cheap.
- Frontend: a Vitest case for the badge/details of an account with `needs_check`, and the Playwright mock of `/api/accounts` gets the new fields if the types require them.
- Run `uv run pytest`, `cd frontend && yarn test && yarn lint && yarn build`, e2e for the accounts screen.

## Docs

`CLAUDE.md`: Decisions get one bullet (login rejection is 424 and recorded in the `auth_*` columns, transient codes stay 502, the reset rule, `needs_check` is derived), the layout line for `db/` and `accounts-api.ts`/`AccountsView.vue` mention it.

## Verification

Tests as above.
Bugsink can only be checked after a deploy: REMOTE-IMAP-MAIL-RULES-9 should get no new events, and the affected account shows "Please check" with its failure history in the accounts screen.
Then close the todo, sync, and rebase per the todo-loop.
