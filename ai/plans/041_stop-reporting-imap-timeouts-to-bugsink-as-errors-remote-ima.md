# Stop reporting IMAP timeouts to Bugsink as errors (REMOTE-IMAP-MAIL-RULES-2/-7/-8)

## Context

Todo `8377cbe7-5136-4b98-8bd0-5a517495c160`, subtask of "fix Bugsink issues".
All three Bugsink issues are the same expected failure, a slow IMAP server (aioimaplib's 10 s command timeout), reported by two different paths.

Findings:

- **-2 and -8** (`TimeoutError`, 3 + 1 events): the watcher's `Watcher.record` (`server/watcher.py:321`) queues `Act` entries.
  `run_actions` → `ActionRunner.run` (`actions.py:404`) → `ImapClient.fetch_message` → `examine` hits the 10 s timeout.
  `ActionRunner.run` closes the connection and re-raises, as designed.
  `record` catches it with a bare `except Exception` and calls `logger.exception("Could not write the action log entry")`, and the Sentry logging integration turns that into an event.
  The `transaction` `/api/editor/rules` of -8 is only the ambient scope of the background task that a rules save restarted, not a request failure.
- **-7** (`HTTPException` 504 "The mail server did not answer in time."): `imap_session` (`server/imap_session.py:35`) correctly maps `TimeoutError` to 504 for the browser.
  `FastApiIntegration` / `StarletteIntegration` report every `HTTPException` with a 5xx status by default (`failed_request_status_codes`), so the 504 becomes an event as well.

A slow mail server is not a bug in this app: the user sees the 504 in the UI, and the watcher retries on the next mail or restart.
The events carry no information we can act on, so they should be a log warning and not a Bugsink issue.

## Changes

1. `server/watcher.py`, `Watcher.record`: add `except (ImapError, AioImapException, OSError, TimeoutError) as error:` before `except Exception`, which does `logger.warning("Could not run the actions for %s/%s: %s", ...)` with the folder and uid of an `Act` (for a log entry write the generic text).
   Only the genuinely unexpected failures (database, bugs) stay `logger.exception`.
   The imports `ImapError` and `AioImapException` are already in that file (used at line 192).
2. `server/sentry.py`, `init_sentry`: pass `failed_request_status_codes` to `StarletteIntegration` and `FastApiIntegration`, a set of all 5xx except 504 (`{*range(500, 600)} - {504}`, named constant `REPORTED_STATUS_CODES` with a docstring saying why).
   502 stays reported for now, REMOTE-IMAP-MAIL-RULES-9 (login failed) is its own todo and will refine it.
3. Regenerate nothing: no schema or model change.
4. `CLAUDE.md`: one sentence under the error reporting decision: expected IMAP failures (timeouts) are warnings and 504 is not reported, so they never reach Bugsink.

## Tests

- `tests/test_server_watcher.py`: a new test where `ActionRunner.run` raises `TimeoutError` (reuse the fixtures of `test_running_actions_is_a_job_until_it_ends`, which already has a failing variant at line 245): assert with `caplog` that the record is a `WARNING`, that no `ERROR` record from `logger.exception` is made, and that the queue keeps being processed (next entry written).
- `tests/test_server_sentry.py`: assert that `init_sentry` passes `failed_request_status_codes` without 504 and with 500 and 502 (the file already monkeypatches `sentry_sdk.init` and inspects its kwargs for the other init tests; check the integrations' attribute `failed_request_status_codes`).
- Existing `tests/test_server_mail.py:156` keeps asserting 504 for the API.

## Verification

`uv run pytest` (full suite), plus `uv run ruff`/type check if the project has them configured in `pyproject.toml`; no frontend change, so no yarn run.
Not verifiable locally: that Bugsink stops receiving the events, which needs a deploy and a slow server.
The Bugsink issues will be resolved by the user after the deploy (the MCP is read-only).

## Leftover, not part of this todo

A timed-out `Act` loses its actions for that mail until the next restart (it was like this before, only the report changes).
No retry is added here.
