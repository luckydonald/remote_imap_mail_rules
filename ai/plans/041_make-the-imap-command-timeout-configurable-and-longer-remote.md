# Make the IMAP command timeout configurable and longer (REMOTE-IMAP-MAIL-RULES-2/-7/-8)

## Context

Todo `8377cbe7-5136-4b98-8bd0-5a517495c160`, subtask of "fix Bugsink issues".
The decision from the review of the first plan: fix the cause by giving slow servers more time, instead of hiding the reports.

Findings:

- All three issues are aioimaplib's default command timeout of 10 s (`asyncio.wait_for(..., self.timeout)`, event variable `timeout: "10.0"`).
- **-2 and -8** (`TimeoutError`): the watcher's `ActionRunner.run` → `ImapClient.fetch_message` → `examine` times out.
  `Watcher.record` logs it with `logger.exception`, which Sentry reports.
  The `transaction` `/api/editor/rules` of -8 is only the ambient scope of the background task, not a request failure.
- **-7** (`HTTPException` 504): `imap_session` maps the same `TimeoutError` to 504 for the mail browser.
- The timeout is never set by the project: `connect_aioimaplib` (`imap/client.py:38`) builds `aioimaplib.IMAP4_SSL(...)` / `IMAP4(...)` without `timeout`, so every connection (watcher, browser, action runner, dry run) gets the 10 s default.

## Changes

1. `config.py`, `ImapSettings`: new field `imap_timeout: float = Field(default=60.0, gt=0, description="Seconds to wait for the server to answer one IMAP command.")`, next to `imap_poll_interval`.
   Env var `IMAP_TIMEOUT`, like the other unprefixed names.
2. `imap/client.py`, `connect_aioimaplib`: pass `timeout=settings.imap_timeout` to both `IMAP4_SSL` and `IMAP4` (aioimaplib's constructors take `timeout`).
   `idle_start` / `wait_server_push` keep their own explicit timeouts, so IDLE renewal is unchanged.
3. `.example-env`: `IMAP_TIMEOUT=60` with a comment, after `IMAP_POLL_INTERVAL`.
4. `docker-compose.coolify.yml`: `- IMAP_TIMEOUT=${IMAP_TIMEOUT:-60}` after the poll interval line (`tests/test_coolify_compose.py` keeps these in sync with the settings classes).
5. `CLAUDE.md`: a sentence under "Decisions" next to the poll interval: `IMAP_TIMEOUT` (default 60 s) is aioimaplib's per command timeout for all connections, a timeout is still a `TimeoutError` (504 in the browser, a failed actions run in the watcher).

The 60 s default is a deliberate choice: six times the old limit covers a slow `EXAMINE` / `FETCH` on a loaded server, while the mail browser still answers 504 within a minute on a dead one.
Not changed on purpose: the logging of a timeout in `Watcher.record` and the 504 reporting stay as they are, so a server that is really down is still visible in Bugsink.

## Tests

- `tests/test_imap_client.py` (or the file that already tests `connect_aioimaplib`, to be found): monkeypatch `aioimaplib.IMAP4_SSL` / `IMAP4` with a recorder and assert `connect_aioimaplib` passes `timeout` from the settings, for ssl and plain.
- `tests/test_config.py` (if present, else next to the existing settings tests): `imap_timeout` defaults to 60 and rejects 0 / negative values.
- `tests/test_coolify_compose.py` must stay green, that checks the compose file and the setting name.

## Verification

`uv run pytest` (full suite) and the lint/type checks configured in `pyproject.toml`.
No frontend change.
Not verifiable locally: that the timeouts stop on the real slow server, which needs a deploy.
The user resolves the three Bugsink issues after the deploy and watches for a recurrence.
