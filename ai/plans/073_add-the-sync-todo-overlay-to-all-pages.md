# Add the Sync Todo overlay to all pages

**Commit style:** Skill `/commit-with-lplp-style` is active, auto-commit following it for this implementation.

## Context

The user wants the quick-add overlay `@luckylu.cy/sync-todo-overlay` (a floating button that adds a todo to their Sync Todo account) on every page of the frontend.
This is a sync-less run of `/todo-loop`, so there is no CalDAV todo to tick and no `sync_todos.py` run.
The steps are intel, plan, implement, commit, rebase.

Decisions from the user:

- An environment variable guards whether the button is shown or included at all.
- The URL and the embed key are optional environment values.
  When one or both are unset they are not filled in, and the overlay falls back to its own localStorage based settings dialog (the gear inside the overlay).

Findings about the package (latest dist-tag `1.0.0-2026.11.19-5.59.51-build5-31b1f6`, and also a plain `1.0.0`):

- It has a Vue 3.5 component (`@luckylu.cy/sync-todo-overlay/vue`) and a stylesheet (`@luckylu.cy/sync-todo-overlay/style`).
- Props `url` and `token` are optional: "Saved value or blank", and settings supplied by the host are locked, so passing nothing keeps the settings dialog editable.
- It keeps its settings in localStorage under `sync-todo-overlay` (`persist` defaults to true).
- The embed key is readable by anyone who sees the page source, so it is not committed to the repo, only set per deployment.

## Approach

Config follows the Sentry DSN pattern: environment, handed to the browser at runtime by `GET /api/public/client-config`, no build bakes it in.
`/api/public/*` needs no login, so the overlay is also on the login screen, which makes it really "all pages".

Env variables (all optional, default off):

- `SYNC_TODO_OVERLAY_ENABLE` (bool, default `false`): the guard, nothing is mounted unless it is true.
- `SYNC_TODO_URL` and `SYNC_TODO_TOKEN` (strings, default empty): passed to the overlay only when non-empty, each one independently.

### Backend

- `server/settings.py`: add the three settings with descriptions.
- `server/api/public.py`: add `TodoOverlayClientConfig(url: str | None, token: str | None)` and a field `todo_overlay: TodoOverlayClientConfig | None` on `ClientConfig`.
  It is `None` when the guard is off, else an object whose empty values are `None`.

- `.example-env` and `docker-compose.coolify.yml`: add the three variables, optional (`${VAR:-}`, no `:?`, the guard as `${SYNC_TODO_OVERLAY_ENABLE:-false}`).
  `tests/test_coolify_compose.py` keeps these in sync with the settings classes.

### Frontend

- Pin `@luckylu.cy/sync-todo-overlay` to `1.0.0-2026.11.19-5.59.51-build5-31b1f6`, which ships the Vue component and stylesheet missing from the `1.0.0` archive.
- Share one fetch of `client-config`: extract `fetchClientConfig()` (memoised promise, `null` on any failure) that `sentry.ts` and the overlay both use, so there is no second request.
- New `frontend/src/components/TodoOverlay.vue`: awaits the config, renders `<Overlay>` only when `todo_overlay` is not `null`, and binds `url` / `token` only when they are set (so unset means the localStorage settings dialog).
  The package CSS is imported there.
  Offline or without a server it renders nothing.
- `AppShell.vue`: render `<TodoOverlay />` once at the top level, outside every screen and the login gate, so it shows on every route.
- Check the launcher position against the mail UI and the phone layout, use `position="left"` or `--sync-todo-z-index` if it collides.
- Service worker: `/api` is never cached, the package JS and CSS go into the build and are precached like the rest.

### Tests

- `tests/test_server_sentry.py` asserts `client-config` is exactly `{"sentry": None}`, update it to include `"todo_overlay": None`.
  Add cases: guard off with url and key set gives `None`, guard on with both, with only one, and with neither.
- Vitest `src/__tests__/todo-overlay.spec.ts`: config parsing (valid, partial, malformed, fetch failure), and the component mounting the overlay only with a config and binding only the set props.
- Playwright (mocked `/api`): the launcher shows on `/rules` and on the login screen when the guard is on, is absent when it is off, and with no url or key the overlay's settings dialog opens from the gear.

### Docs

`CLAUDE.md`: one sentence under Layout or Decisions about the three variables, the guard, the localStorage fallback and `todo_overlay` in `client-config`.

## Verification

- `uv run pytest`, then in `frontend/`: `yarn test`, `yarn lint`, `yarn build` (type check), `yarn test:e2e`.
- Check in Playwright against a mocked API only (never Chrome tools, never the live account).
  Real todo creation needs the user's Sync Todo URL and embed key and is left to them.
