# Settings: stats subroute

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `c96db0d2-06f9-432c-aabe-963d1da2fc96`: "in the settings have a subroute with stats", with server stats (including the SQLite file size) and browser cache stats.

## Context

The settings screen (`SettingsView.vue`) is an iOS style index with drill-down pages (`/settings/general`, `accounts`, `git`, `log`).
There is no place to see how big the database or the offline cache has grown.
This adds `/settings/stats` with two sections: what the server holds and what this browser caches.

## Findings

- Routes are listed in `frontend/src/router.ts` and the index entries in `SettingsView.vue` (`parts`); a page is chosen by `route.name`.
- Pages that need the server are wrapped in `OnlineOnly.vue`, so the browser section can stay usable offline (it is where the stats matter most).
- Routers are mounted in `server/app.py` with `require_login` as a dependency, e.g. `api/log.py` for `/api/log/status`.
- The offline cache is IndexedDB (`model/offline/db.ts`, stores `folders`, `lists`, `details`, `queue`) plus the service worker precache and localStorage prefs.
- `db/engine.py` knows `DATABASE_URL` (default SQLite); `ServerSettings.data_dir` holds the rules mirror and git state.

## Backend

New `server/api/stats.py`, mounted at `/api/stats` behind the login like the other routers: `GET /api/stats` returns `Stats`.

- `database`: `dialect`, `size_bytes` (SQLite only, from the file path of the engine URL plus the `-wal` file when present, `null` for other databases or `:memory:`), `path` is not returned (no path leaks).
- `tables`: row counts for `accounts`, `rules`, `templates`, `mail_events` (also per `kind`), `mcp_tokens`, one `select count` each through the existing `get_session`.
- `events`: oldest and newest `created_at` of `mail_events`, so the log growth is visible (reuse `mail_events.last_event_at` style, add `first_event_at` next to it in `db/mail_events.py`).
- `data_dir_bytes`: size of `settings.data_dir` (walks the folder, runs in a thread with `asyncio.to_thread`, so the loop is not blocked).
- `watcher`: `enabled`, number of watched folders and the running jobs count, from the `Watcher` the same way `/api/log/status` does.
- `process`: `started_at` (stored on `app.state` in the lifespan) and `release` (reuse the release chain of `sentry.py`).

## Frontend

- `frontend/src/model/stats-api.ts`: typed `fetchStats()` using `failure` from `http.ts`, as `log-api.ts` does.
- `frontend/src/model/offline/stats.ts`: `cacheStats()` answers record counts per IndexedDB store, mails cached per reason (`reasons` of the records), approximate bytes (JSON length of the records, since IndexedDB has no per store size), `navigator.storage.estimate()` usage and quota when available, service worker cache names and entry count (`caches`), the localStorage size, and the length of the unsent queue.
  A `dbCount(store)` helper goes into `db.ts`; everything degrades to zeros without IndexedDB like the rest of `offline/`.
- `SettingsStats.vue`: two sections, "Server" (inside `OnlineOnly`) and "This browser", plain definition lists, a `↻` reload button, byte values through one `formatBytes` helper.
  No new store state: the numbers are page-local (`ref`s), they are a snapshot and not shared.
- Route `settings-stats` (`/settings/stats`) in `router.ts`, a "Stats" entry in `SettingsView.vue` `parts`, the page rendered there with the usual `‹ Settings` back link.

## Tests

- `tests/test_server_stats.py`: login required (401), SQLite size is positive for a file database and `null` for a non-SQLite URL, counts follow created rows, no path in the answer.
- `frontend/src/__tests__/`: `stats.spec.ts` for `cacheStats` with `fake-indexeddb/auto` (counts per store, reasons, no IndexedDB gives zeros) and `formatBytes`; a router test line for the new route if one lists the settings routes.
- `frontend/e2e/`: extend the settings spec: the index lists "Stats", the page shows both sections with the API mocked, and offline only the browser section is usable.

## Docs

`CLAUDE.md`: add `api/stats.py` to the server layout list, the `/settings/stats` page to the router sentence, and a one line Decisions entry (stats are snapshots, SQLite size only for file databases, the browser part also works offline).

## Verification

`uv run pytest`, `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e` (Chromium plus the `webkit-ipad` project only for `mail.spec.ts`).
No live account is touched: the endpoint only reads the local database and folder.
