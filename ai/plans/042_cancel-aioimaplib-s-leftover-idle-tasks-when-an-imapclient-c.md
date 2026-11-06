# Cancel aioimaplib's leftover IDLE tasks when an `ImapClient` closes (REMOTE-IMAP-MAIL-RULES-3/-6)

## Context

Todo `0775f42d-504f-436e-873e-870afea6b4fa`, subtask of "fix Bugsink issues".
Bugsink -3 (5 events) and -6 (2 events, ambient transaction `/api/editor/rules`) are the same asyncio log message: `Task was destroyed but it is pending!`.
Both name the task `<Task pending coro=<IMAP4.idle() running at aioimaplib.py:777> wait_for=<Future pending> cb=[set.discard()]>`.
The `cb=[set.discard()]` is the done callback `idle_start` adds with `self.tasks.add(idle); idle.add_done_callback(self.tasks.discard)`, so the task lives in `IMAP4.tasks`.
Sentry's logging integration turns asyncio's log record into an event, no exception is involved.

Findings:

- `IMAP4.idle_start()` (aioimaplib 2.0.3) starts `idle()` and `wait_for_idle_response()` as tasks and then `await asyncio.wait({idle, wait_for_ack}, FIRST_COMPLETED)`.
  Cancelling the caller there does not cancel those two tasks, and `has_pending_idle()` is still false because the server has not sent `+ idling` yet.
- `ImapClient.close()` only calls `idle_done()` if `has_pending_idle()`, then `logout()`.
  So a connection closed while `idle_start` was in flight (a rules save restarts the watcher, `Watcher.stop()` cancels the task, `matches()` cancels the folder tasks) keeps its `idle` task pending, and when the connection is garbage collected asyncio logs the message.
  The -6 events at `/api/editor/rules` match exactly that: the rules save restarts the watcher.
- The same happens if `logout()` raises `TimeoutError` / `OSError` (swallowed in `close()`) while `IDLE` has not ended.
- Not a missing `await` of our own tasks: `Watcher.stop()`, `follow()`'s `recorder` and `matches()`'s folder tasks are all cancelled and awaited already.

## Changes

1. `imap/connection.py`: add `tasks: set[asyncio.Future[Any]]` to the `ImapConnection` protocol (the slice of `aioimaplib.IMAP4` we use, so the fake can provide it).
2. `imap/client.py`, `ImapClient.close()`: after the `logout` attempt, in a `finally`, cancel every task still in `connection.tasks` and `await asyncio.gather(*tasks, return_exceptions=True)`.
   `logout` itself stays as it is, so a clean `IDLE` still ends with `DONE` + `LOGOUT` and the tasks are already finished by then (their done callback removes them from the set, so the loop is a no-op).
   Iterate over a copy of the set, since the done callbacks mutate it.
3. `tests/fake_imap.py`: `FakeConnection.tasks = set()`, and its `idle_start` registers a task the way aioimaplib does, so the test can leave one pending.
4. `CLAUDE.md`: one sentence under the `imap/` layout or the "one connection and task per folder" decision: `ImapClient.close()` cancels the tasks aioimaplib left in `IMAP4.tasks`, otherwise a connection closed during `idle_start` logs "Task was destroyed but it is pending!" to Sentry.

Not changed on purpose: no logging filter that hides the asyncio message, the cause is fixed instead (same decision as for the timeouts).

## Tests

- `tests/test_imap.py`: close an `ImapClient` whose fake connection has a pending task in `connection.tasks` (cancelled while `idle_start` was in flight) and assert the task is cancelled and the set empty afterwards.
- Same with `logout()` raising `TimeoutError`: `close()` still cancels the tasks and does not raise.
- A watcher test in the style of the existing `watch` ones: cancel the `watch()` consumer while `idle_start` is pending, and assert no task is left in `connection.tasks`.
- A reproduction against the real `aioimaplib.IMAP4` is not possible offline, so the unit tests use the fake plus one throwaway script in the scratchpad that builds a real `IMAP4` on a local asyncio server which never answers `IDLE`, cancels during `idle_start`, closes the client and checks `gc` produces no "Task was destroyed" record (run before and after the fix, not committed).

## Verification

`uv run pytest` (full suite) and the lint/type checks configured in `pyproject.toml`.
No frontend change.
Not verifiable locally: that the Bugsink events stop on the real server, which needs a deploy.
The user resolves -3 and -6 after the deploy and watches for a recurrence.
