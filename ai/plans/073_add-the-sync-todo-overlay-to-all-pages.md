# Add the Sync Todo overlay to all pages

**Commit style:** Skill `/commit-with-lplp-style` is active, auto-commit following it for this implementation.

## Context

The user wants the quick-add overlay `@luckylu.cy/sync-todo-overlay` (a floating button that adds a todo to their Sync Todo account) on every page of the frontend.
This is a sync-less run of `/todo-loop`, so there is no CalDAV todo to tick and no `sync_todos.py` run.
The steps are intel, plan, implement, commit, rebase.

Findings about the package (latest dist-tag `1.0.0-2026.11.19-5.59.51-build5-31b1f6`, and also a plain `1.0.0`):

- It has a Vue 3.5 component (`@luckylu.cy/sync-todo-overlay/vue`) and a stylesheet (`@luckylu.cy/sync-todo-overlay/style`).
- It needs two props, `url` (the Sync Todo web origin) and `token` (an embed key created in Sync Todo under Settings, Embed keys).
- The embed key is readable by anyone who sees the page source, so it is not a secret in the Fernet sense, but it must not be committed to the repo.
- The default shows a floating launcher button and keeps its settings in localStorage under `sync-todo-overlay`.

## Approach

The URL and the key are deployment config, so they follow the Sentry DSN pattern: set in the environment, handed to the browser at runtime by `GET /api/public/client-config`, no build bakes them in.
Without both values nothing is mounted, so a fresh checkout and the tests behave as before.
`/api/public/*` needs no login, so the overlay is also on the login screen, which makes it really "all pages".

### Backend

- `server/settings.py`: add `sync_todo_url` and `sync_todo_embed_key` (both default empty, with descriptions).
- `server/api/public.py`: add `TodoOverlayClientConfig(url, token)` and a field `todo_overlay: TodoOverlayClientConfig | None` on `ClientConfig`, `None` unless both settings are set.
- `.example-env` and `docker-compose.coolify.yml`: add `SYNC_TODO_URL=${SYNC_TODO_URL:-}` and `SYNC_TODO_EMBED_KEY=${SYNC_TODO_EMBED_KEY:-}` (optional, no `:?`).
  `tests/test_coolify_compose.py` keeps these in sync with the settings classes.

### Frontend

- `yarn add @luckylu.cy/sync-todo-overlay` in `frontend/`, pinned to the stable `1.0.0` release unless the user prefers the newest build (the `latest` tag is a build version string).
- New `frontend/src/model/todo-overlay.ts`: `fetchTodoOverlayConfig()` mirroring `fetchSentryConfig` in `sentry.ts` (type guard, `null` on any failure).
  To avoid a second request, `client-config` is fetched once and shared: extract a small `fetchClientConfig()` that both `sentry.ts` and the overlay use.
- New `frontend/src/components/TodoOverlay.vue`: loads the config on mount, renders `<Overlay :url :token />` only when there is one, and imports the package `/style`.
  Offline or without a server it renders nothing.
- `AppShell.vue`: render `<TodoOverlay />` once at the top level, outside every screen and the login gate, so it shows on every route.
- The overlay must not cover the mail UI: check the launcher position on the mail view and the phone layout, use `position="left"` or the `--sync-todo-z-index` variable if it collides.
- Service worker: `/api` is never cached, the package JS and CSS go into the build and are precached like the rest.

### Tests

- `tests/test_server_sentry.py` asserts `client-config` is exactly `{"sentry": None}`, update it to include `"todo_overlay": None`, and add a case for both settings set and for only one set.
- Vitest `src/__tests__/todo-overlay.spec.ts`: config parsing (valid, missing, malformed, fetch failure), and the component mounting the overlay only with a config.
- Playwright (mocked `/api`): the launcher shows on `/rules` and on the login screen when the config is present, and is absent when it is not.
  The e2e tests already mock `/api`, so add `client-config` to the mock.

### Docs

`CLAUDE.md`: one sentence under Layout or Decisions about `SYNC_TODO_URL` / `SYNC_TODO_EMBED_KEY`, the optional overlay and `todo_overlay` in `client-config`.

## Verification

- `uv run pytest`, then in `frontend/`: `yarn test`, `yarn lint`, `yarn build` (type check), `yarn test:e2e`.
- Run the server on a separate port with dummy `SYNC_TODO_URL` / `SYNC_TODO_EMBED_KEY` and confirm the button in a Playwright run (never Chrome tools, never the live account).
  The real todo creation needs the user's embed key and is left to them.

## Open point

The user has to supply the Sync Todo URL and an embed key as environment values after the deploy.
