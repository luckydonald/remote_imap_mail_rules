# Plan: Stop reporting IMAP login failures of the mail browser to Sentry

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Bugsink REMOTE-IMAP-MAIL-RULES-9 (todo `97650feb`) holds 3 events of `HTTPException 502 "The mail server failed: login failed: NO [b'authentication failed']"` on `GET /api/mail/accounts/{id}/folders`.
A wrong password stored for an account is a user-config problem, not a bug of the app, so it should not be a Sentry event.

Cause: `imap_session` in `src/remote_imap_mail_rules/server/imap_session.py` turns every `ImapError` into `HTTPException(502)`.
The Sentry `FastApiIntegration` / `StarletteIntegration` report every `HTTPException` with a 5xx status by default (`failed_request_status_codes`), 4xx are not reported.
The login failure comes from `check(await connection.login(...), "login")` in `ImapClient.connect` (`imap/client.py:115`), which raises the same generic `ImapError` as every other failed command, so the session cannot tell it apart.

## Changes

- `imap/client.py`: add `class ImapLoginError(ImapError)`.
  `connect` raises it when the `LOGIN` response is not `OK` (keep the message `login failed: NO [...]`), other commands keep raising `ImapError` through `check`.
  Because it is a subclass, the watcher and every other `except ImapError` keep working unchanged.
- `server/imap_session.py`: catch `ImapLoginError` before the generic `ImapError` branch and answer `HTTPException(424, "The mail server rejected the login: ...")`, so the user sees the server's reason in the UI and Sentry does not get an event.
  424 (Failed Dependency) rather than 401, because the frontend treats 401 as "admin session expired" and would show the login screen.
  Update the docstring of `imap_session` (404 / 503 / 424 / 502 / 504).
- `CLAUDE.md`: one sentence in the mail browser Decision: a rejected IMAP login answers 424, not 502, because 5xx `HTTPException`s become Sentry events.

## Out of scope

The watcher also logs a failing login for such an account on its own; only the browser route was reported in the issue, so I leave that alone and look at it if it shows up in Bugsink.

## Tests

- `tests/test_server_mail.py`: new case beside `test_imap_failures`, using the same broken-factory pattern, with a connection whose `login` returns a `NO` response (reuse `FakeServer` if it can reject a login, otherwise a small stub), asserting status 424 and that the detail contains `authentication failed`.
- A test on the Sentry side is not needed: assert the status is below 500, which is what keeps it out of the integration.
- `uv run pytest` and the frontend suite stay green (no frontend change; `ApiError` already shows the `detail` text).

## Verification

`uv run pytest`, then close the todo, sync, and rebase per the todo-loop.
Bugsink can only be checked after a deploy: REMOTE-IMAP-MAIL-RULES-9 should stop getting new events.
