# Plan: Stop `Watcher.record` being cancelled in the middle of a database write (REMOTE-IMAP-MAIL-RULES-1)

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `d1caceac-5747-42e2-8e47-d4113963d02b`, Bugsink issue `9e33ac27-0ddd-437e-867c-93644c9cd983`.

## Context

Bugsink REMOTE-IMAP-MAIL-RULES-1 is one event, 2026-11-04, transaction `/api/editor/rules`.
It is not a raised exception but a log record: logger `sqlalchemy.pool.impl.AsyncAdaptedQueuePool`, message "Exception during reset or similar", level error, carrying a `CancelledError`.
The stack runs `_finalize_fairy` > `_reset` > `do_rollback` > aiosqlite `rollback`, so a task was cancelled while its connection was being returned to the pool and rolled back.
The breadcrumbs are `mail_events` SELECT/INSERT pairs, so the cancelled task was a `Watcher.record` task writing the action log.
A rules save calls `Watcher.restart()` as a background task, which cancels `follow()`, whose `finally` does `recorder.cancel()` (`server/watcher.py`, `follow` and `record`).
If the recorder is in the middle of `async with self.session_factory()` at that moment, the cancel lands inside SQLAlchemy's connection reset.
SQLAlchemy logs that at error level and the Sentry logging integration turns it into an event, although nothing is wrong beyond one entry being abandoned.

A throwaway script that cancels tasks at random points of an aiosqlite transaction hung instead of reproducing the log line, so the same weak spot is real, but the exact log line is not yet reproduced.
The implementation must try to reproduce it in a test first (cancel `record` at varying delays with the log captured), and adjust the fix if the test shows more.

## Approach

Cancelling the recorder is fine while it waits (`queue.get()`) or runs IMAP actions, but not inside a database write.
Make the database part of one entry non-cancellable and let the cancel arrive right after it.

In `src/remote_imap_mail_rules/server/watcher.py`:

- Split `record` in two parts per entry.
  For an `Act` entry, `run_actions(runner, entry.mail, own)` runs first without a session (it needs only the runner), still cancellable, since it is IMAP work and a restart should abort it.
  Then the write (`write_actions` or `write`, plus `commit`) happens in a new method, e.g. `commit_entry(entry, results)`, which owns the `async with self.session_factory()` block.
- `record` awaits `commit_entry` through `asyncio.shield` on its own task, and when it is cancelled meanwhile, it waits for that write to finish and then re-raises `CancelledError`.
  A small helper such as `async def uncancellable(coro)` in `watcher.py` keeps this in one place.
- Keep `queue.task_done()` in the `finally`, and keep `logger.exception("Could not write the action log entry")` for real failures only.
  A `CancelledError` must keep propagating, as it does now.
- `follow`'s `finally` stays as is, `recorder.cancel()` then `await recorder`, the shield makes it wait for a running write (milliseconds) instead of cutting it.

`stop()` cancels the whole `run` task, whose cancellation reaches `follow` and then the same `finally`, so a stop at shutdown is covered too.
`lookup_settings` and `allow_move` run inside the recorder's action run and would still be cancellable, they are read-only selects and a cancelled rollback of a read-only connection is the same pool path, so they get the same shield (they are tiny).

Not changed: no sentry filter and no logger suppression, because hiding the log would also hide real pool failures.

## Tests (`tests/test_server_watcher.py`)

- A test that fills the queue, cancels `record` while a (slowed-down) `write` is in progress, using a `write` that waits on an `asyncio.Event`, and checks that the write completes and is committed (the entry is in `mail_events`) before the `CancelledError` surfaces.
- A test that cancels `record` while `run_actions` is running (an `ActionRunner` fake that blocks), and checks it is cancelled promptly and nothing is written.
- A test over several cancel delays (as in the throwaway script) with `caplog` at `ERROR` on `sqlalchemy.pool`, asserting no record is logged, to the extent the reproduction shows one without the fix.
- The existing restart tests (`test_restart_does_not_log_existing_mails_twice`, `test_a_restart_does_not_repeat_actions`) must stay green.

## Docs

`CLAUDE.md`, Decisions, Action log entry: one sentence that the recorder never gets cancelled inside a database write, the cancel waits for the write.

## Verification

- `uv run pytest tests/test_server_watcher.py`, then the full `uv run pytest`.
- Lint/format as the project's code-style demands (`ruff` if configured, `end` comments on blocks).
- The Bugsink issue can only be confirmed fixed after a deploy: save the rules a few times while mails are being logged and watch for a new event.
