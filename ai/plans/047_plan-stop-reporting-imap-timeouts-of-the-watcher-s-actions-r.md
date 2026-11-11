# Plan: Stop reporting IMAP timeouts of the watcher's actions run as an error (REMOTE-IMAP-MAIL-RULES-11)

## Context

Todo `ae994924`, Bugsink issue `c77351b4` (REMOTE-IMAP-MAIL-RULES-11): one `TimeoutError`, 2026-11-11T02:54Z, release `689a99a`, transaction `/api/accounts/{account_id}`.
The transaction name is only the request that triggered `Watcher.restart()`, the failing code is the watcher's background task.

The stack is `Watcher.record` > `run_actions` > `ActionRunner.run` > `ImapClient.fetch_message` > `examine`, where aioimaplib's `wait_for` ran into the command timeout (10 s at that release).
`ActionRunner.run` already closes its connection and re-raises such errors, so the next mail reconnects.
But `Watcher.record` catches them with `except Exception: logger.exception("Could not write the action log entry")`, and that logging call is the Sentry event.
A slow or dropped IMAP server is an expected condition: `watch_account` already logs the same exception types as a warning.

The release is older than `IMAP_TIMEOUT` (60 s) and the cancel fixes, so the timeout is likelier rarer now, but the reporting path is unchanged and every future timeout in the actions run would again be an event.

## Steps

1. `src/remote_imap_mail_rules/server/watcher.py`, `Watcher.record`: add an `except (ImapError, AioImapException, OSError, TimeoutError) as error` before the generic `except Exception`.
   It logs a warning (`"Could not run the actions for %s/%s uid %s: %s"` with account id, folder, uid, error), no traceback, so Sentry gets only a breadcrumb.
   The generic branch stays for real bugs (database errors etc.).
   Behaviour is otherwise unchanged: the entry is not committed and the queue moves on, as today.
2. `tests/test_server_watcher.py`: a test that runs `record` with a fake runner whose `run` raises `TimeoutError`, queues one `Act`, waits for `queue.join()`, then asserts there is a warning and no `ERROR` record in `caplog`, and that the recorder task is still alive for the next entry.
   Parametrize over `TimeoutError` and `OSError`.
3. `CLAUDE.md`: one sentence in the Action log decision: IMAP errors of the actions run in `Watcher.record` are warnings, not exceptions.

## Verification

- `uv run pytest` (full suite) and `uv run ruff check` / type check as the project does.
- The new test fails before the change (an `ERROR` record from `logger.exception`) and passes after.
- Nothing touches a real mailbox; only `FakeServer` and fake runners are used.
