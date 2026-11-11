# Plan: close REMOTE-IMAP-MAIL-RULES-10 as covered by `a59036c`, no new code

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo: `21d3bc22-3197-4262-9a4d-45f2283dc2d6` (subtask of `420b2ab0-94b6-4181-a233-dd46416379cc`, "fix Bugsink issues").

## Context

Bugsink issue `e2080c65-c820-4f24-a950-c4a884dc6636` ("Task was destroyed but it is pending!", an `IMAP4.idle()` task) has 8 events up to 2026-11-11 15:25Z, all with release `689a99a`.
`689a99a` is the tip of `origin/mane` (2026-11-06 02:55).
The fix `a59036c` (`cancel_leftover_tasks`, 2026-11-06 21:35) is newer, unpushed and not deployed, so the events come from a build without it.

## The two chains I suspected, checked against `a59036c`

1. `follow_changes` iterates `watch()` with a bare `async for`, so a cancel while the loop body awaits leaves the generator suspended.
   Probe (`/tmp/leakcheck/probe.py`, real `ImapClient` and `watch()` with `FakeServer`, cancelled while the body sleeps): no connection task is left pending after `async with ImapClient` exits.
   The suspended generator is parked at its `yield`, not inside `idle_once`, so it owns no `IDLE` task. `close()` cancels the connection's tasks regardless of the generator.
   Verdict: no leak. `aclosing` would only be tidiness.
2. `ImapClient.connect()` does not close a connection whose login fails or is cancelled.
   That leaks aioimaplib's own client task, never an `IDLE` task (`IDLE` starts only after a successful login and `examine`), so it cannot be this issue.
   Verdict: a different and unobserved leak, not worth code now.

## Comparison

- `a59036c` (cancel the tasks in `IMAP4.tasks` in `ImapClient.close()`): addresses the exact object in the event, covers every path that ends in `close()`, which is every `ImapClient` user (`async with`, `ActionRunner.close()`).
- `aclosing` / `connect()` cleanup: defence for paths that do not hold an `IDLE` task, no observed failure. Adding them would be speculative code.
- `ImapClient.__del__` warning: only useful if events continue after the deploy.

## Steps

1. Complete subtask `21d3bc22` with a note "covered by `a59036c`, verify after the deploy"; complete parent `420b2ab0` only if the user agrees all subtasks are done.
2. Rebase away the two plan-051 hook commits (`41b885e`, `4c05e86`) after a backup tag, or keep this plan as the record, user's choice.
3. After the next deploy, check Bugsink: no new events for -10 in a day or two means done, otherwise reopen and add the `__del__` diagnostic.
