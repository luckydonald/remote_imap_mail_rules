# Plan: Stop "Task was destroyed but it is pending!" (Bugsink REMOTE-IMAP-MAIL-RULES-10)

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo: `21d3bc22-3197-4262-9a4d-45f2283dc2d6` (subtask of `420b2ab0-94b6-4181-a233-dd46416379cc`, "fix Bugsink issues").

## Context

Issue `e2080c65-c820-4f24-a950-c4a884dc6636` has 8 events between 2026-11-10 14:02Z and 2026-11-11 15:25Z, so it is still happening.
All of them are the asyncio log `Task was destroyed but it is pending!` for a `Task` in `aioimaplib.IMAP4.idle()` (`aioimaplib.py:777`, `await self.protocol.idle()`).
The `/api/accounts/{account_id}` transaction is only whatever request happened to run when the garbage collector hit, it is not the cause.

The release (`689a99a`) already contains `cancel_leftover_tasks` (`a59036c`, fixes REMOTE-IMAP-MAIL-RULES-3/-6), so that fix works for the connections that reach `ImapClient.close()`.
The task repr shows only the callback `set.discard()` (from `IMAP4.tasks`).
`cancel_leftover_tasks` would have added a `gather` callback, so this task never went through it: some connection that had started `IDLE` was dropped without `ImapClient.close()` running, and the connection's `tasks` set took the task with it.

## Findings (what is known, what is not)

- `IDLE` is only started in `imap/watcher.py:idle_once` (`connection.idle_start`), reached through `watch()` from `matching.follow_changes`, from `follow_folder`, from `matches()`, from `Watcher.follow`.
- `follow_changes` iterates `watch(...)` with a bare `async for`. If `follow_folder` is cancelled while the loop body is awaiting (`poll_state`, `fetch_new`, `queue.put`, …), the `watch` generator stays suspended at its `yield` and is never `aclose()`d.
  Its cleanup is left to the garbage collector's asyncgen hook, which runs at an arbitrary later time, which fits the random transactions of the events.
- `ImapClient.connect()` assigns `self.connection` only after `login` succeeded. A timeout or cancel during `wait_hello_from_server` / `login` drops the connection object without closing it (this leaks aioimaplib's own client task, not an `IDLE` task, but it is the same class of leak).
- The exact path that leaves an `IDLE` task behind is **not proven**. Reproducing it needs a real aioimaplib connection, `FakeServer` replaces `idle_start` itself.

## Changes

1. `src/remote_imap_mail_rules/matching.py` (`follow_changes`): iterate `watch(...)` under `contextlib.aclosing`, so a cancel anywhere in the loop body closes the generator deterministically, inside the task that still owns the client.
2. `src/remote_imap_mail_rules/server/watcher.py` (`Watcher.follow`) and `demo.py`: iterate `matches(...)` under `contextlib.aclosing` as well, so its `finally` (cancel and await the folder tasks) always runs and no folder task is left pending with its connection.
3. `src/remote_imap_mail_rules/imap/client.py` (`ImapClient.connect`): on any failure or cancel between creating the connection and finishing the login, close it (`cancel_leftover_tasks` plus a best-effort `logout`) before re-raising. Keep `self.connection` unset on failure.
4. `ImapClient.__del__` as a diagnostic safety net: if the client is garbage collected while `self.connection` is still set, cancel that connection's leftover tasks synchronously (`task.cancel()` is sync) and log a **warning** (not `error`/`exception`, those are Sentry events) with the `folder` and the `repr` of where it was connected.
   This both silences the leak if it comes from a path we did not find and tells us the owner next time.

## Tests (`tests/test_imap.py`, `tests/test_matching.py`)

- A `follow_changes` run cancelled while its loop body awaits leaves the `watch` generator closed (assert via `inspect.getasyncgenstate` or a wrapper that records `aclose`).
- `Watcher.follow` cancelled while `matches()` yields: the folder tasks are done afterwards (no pending task, no open fake connection).
- `connect()` with a `login` that raises or times out closes the connection (`connection.tasks` empty, `logout` called) and leaves `client.connection` `None`.
- Dropping an `ImapClient` with an open connection and a pending task cancels the task and logs one warning (`caplog`).
- Run the full suite: `uv run pytest`, then `ruff`/type checks as configured in the project.

## CLAUDE.md

Extend the "One connection and task per folder" decision with: generators over a connection are iterated under `aclosing`, `connect()` closes a half-open connection, and `ImapClient.__del__` warns about a client dropped without `close()`.

## Verification

- Unit tests above.
- Needs a deploy to verify for real: the Bugsink issue should get no new events for a day or two, and any `ImapClient dropped without close()` warning in the logs names the remaining owner.
- Never touch the live account (only `FakeServer` and separate-port servers).
