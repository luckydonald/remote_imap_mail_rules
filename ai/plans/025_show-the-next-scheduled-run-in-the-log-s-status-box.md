# Show the next scheduled run in the log's status box

## Context

Todo `81134170-a498-495e-b001-7325c8fbce4d`: the info box at the top of the action log (`ActionLogView.vue`) shows "Watcher last ran", and should also show when the watcher runs next.
The watcher has no schedule of its own.
Each folder either waits in IMAP `IDLE` (woken by a server push, no planned time) or, without `IDLE`, sleeps `IMAP_POLL_INTERVAL` between polls (`imap/watcher.py`, `watch()`).
So a "next run" exists only for polling folders, and the box has to say "on change (IDLE)" for push folders.

The sync of todos failed in this session (`SYNC_TODO_MCP_URL` / `SYNC_TODO_MCP_TOKEN` unset, MCP not connected), so the todo can be ticked in `ai/todo.md` but not completed on CalDAV.

## Design

- `imap/watcher.py`: `watch()` gets an optional `on_schedule: Callable[[datetime | None], None]`.
  The polling branch calls it with `now + poll_interval` before `asyncio.sleep`, the `IDLE` branch calls it with `None` once before waiting (an `IDLE` renewal after 28 minutes is no run, so it is not reported).
- `matching.py`: a `ScheduleCallback = Callable[[str, datetime | None], None]` taking the folder, passed from `matches()` through `follow_folder` and `follow_changes` into `watch()`, next to `on_poll`.
- `server/watcher.py`: `Watcher.due: dict[tuple[UUID, str], datetime | None]` filled by an `on_schedule` lambda in `follow()` (keyed by account and folder), cleared in `stop()`.
  `Watcher.next_run()` returns the earliest `due` in the future (a past one means the poll is running right now), and `Watcher.push_folders()` is true when some folder waits in `IDLE`.
  In memory only, like `last_run`.
- `server/api/log.py`: `LogStatus` gets `next_run: datetime | None` and `push: bool`.
- Frontend: `LogStatus` in `log-api.ts` gets both fields, `ActionLogView.vue` gets a `<div>` "Next scheduled run" with `data-test="next-run"` after "Watcher last ran".
  Text: the time when `next_run` is set, plus " (and on server push)" when `push` is also true; "on change (server push)" when only `push`; "watcher is switched off" when disabled; "not scheduled yet" otherwise (e.g. right after a start).
  The box refreshes already through the existing timer, so a passed time updates by itself.

## Tests

- `tests/test_imap.py`: `watch()` calls `on_schedule` with a time about `poll_interval` ahead when polling, and with `None` under `IDLE`.
- `tests/test_server_watcher.py`: `next_run()` is `None` before anything, the earliest future due afterwards, `push_folders()` follows `IDLE`.
- `tests/test_server_log.py`: the status answer has the new keys (the empty case lists `next_run: None, push: False`).
- `frontend/src/__tests__/action-log.spec.ts` and `log-api.spec.ts`: the new fields in the stub, the four texts of the box.
- Regenerate nothing: the rules schema is not touched.

## Docs

`CLAUDE.md`, "Action log screen": `GET /api/log/status` also has `next_run` and `push`, both from `Watcher` in memory.

## Verification

`uv run pytest`, then `cd frontend && yarn test && yarn lint && yarn build`.
The e2e tests mock `/api`, so a Playwright run of `log` specs is enough for the UI (`yarn test:e2e`), no live account is touched.
