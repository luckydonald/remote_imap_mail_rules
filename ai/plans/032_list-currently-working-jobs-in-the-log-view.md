# List currently working jobs in the Log view

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `ae83447e-1a4c-4dc0-ad2f-c8d3d3ea8b3d`: in the _Log_ view, list the currently working jobs under the info box.

## Context

The Log screen (`ActionLogView.vue`) shows when the watcher last ran, the next run, the last change and the last action, but not what the server is busy with right now.
"Jobs" is not defined in the todo, so this plan takes it to mean the two kinds of work the `Watcher` does that can take noticeable time:

- **Checking a folder**: the first load of a folder's existing mails, or a poll / IDLE wake-up that inspects mails.
- **Running actions**: the rule chain (`ActionRunner.run`) being applied to one mail, including a cross-account move.

Waiting folders (IDLE or a planned poll) are not working jobs, they stay summarised by the existing "Next scheduled run" box.

## Design

State lives in memory on the `Watcher`, like `last_run` and `due`, and is therefore empty after a restart.
No change to `matching.py` is needed.

- New frozen dataclass `Job` in `server/watcher.py`: `kind` (`"folder"` or `"actions"`), `account_id`, `folder`, `uid: int | None`, `started_at`.
- `Watcher.jobs: dict[tuple, Job]`, keyed by `("folder", account_id, folder)` and `("actions", account_id, folder, uid)`.
- **Folder jobs**: the `on_inspect` callback in `Watcher.follow` (today `queue.put_nowait(Seen(mail))`) also calls `self.working(account_id, mail.folder)`, which adds a `folder` job if missing.
  `Watcher.scheduled()` (called by `watch()` before each sleep or IDLE) removes it, because the folder is idle again.
  The job is dropped as well in `stop()` (next to `due.clear()`).
- **Action jobs**: `run_actions` adds an `actions` job before `runner.run(mail)` and removes it in the `finally`, next to the existing `own.acting` handling.
- `Watcher.working_jobs()` returns the jobs sorted by `started_at`.

API: `GET /api/log/status` gets a new field `jobs: list[LogJob]` (`kind`, `account_id`, `folder`, `uid`, `started_at`), filled from `watcher.working_jobs()`.
The existing `test_status` expects an exact dict, so it gets `"jobs": []`.

Frontend:

- `LogStatus` and a `LogJob` type in `frontend/src/model/log-api.ts`.
- `ActionLogView.vue` renders, below the `<dl class="info">`, a `<section aria-label="Working jobs">` with a heading, a list (`data-test="jobs"`) and an empty state "Nothing is running right now."
  Each row: label (`Checking folder` / `Running rules on mail`), account name via the existing `accountNames` map, folder, uid with a `RouterLink` to the mail for action jobs, and the start time via `fullDate`.
- The status is only fetched on mount and on Refresh today.
  A working-jobs list that never updates would be misleading, so `loadStatus` is also polled every 5 seconds while the screen is open (timer cleared in `onBeforeUnmount`), without touching the entries list.

## Tests

- `tests/test_watcher*.py` (next to the existing Watcher tests): a folder job exists while mails are inspected and is gone after `scheduled()`; an action job exists during `run_actions` (use a runner whose `run` waits on an event) and is gone afterwards, also when `run` raises.
- `tests/test_server_log.py`: `test_status` with `jobs: []`, and one test that sets `watcher.jobs` and checks the serialised answer.
- `frontend/src/__tests__/` and `frontend/e2e/` (the log spec that mocks `/api/log/status`): jobs listed with account name and link, empty state, polling refreshes the list.

## Docs

- `CLAUDE.md`: extend the "Action log screen" decision with `jobs` in `/api/log/status` (in memory, from `Watcher.jobs`).
- No i18n files in this project, strings are plain English like the rest of the view.

## Verification

- `uv run pytest`, `cd frontend && yarn test && yarn lint && yarn build`, and `yarn test:e2e` for the log spec.
- Only fakes (`FakeServer`) and Playwright mocks, never the live account.
