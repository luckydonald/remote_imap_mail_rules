# Stage 3: the initial FastAPI server

## Context

Stages 1 and 2 are done: rules parse and match against IMAP, and the Vue editor works on files only (open, drop, download, copy).
Stage 3 of `ai/initial.md` adds a FastAPI server so the editor can talk to it instead of working on files.
The rules file is set by `RULES_PATH` (already in `config.py`, default `rules/example.yml`), and saving writes to disk.
Uploading and downloading in the editor stay as they are and never write to disk.
Not in scope: accounts, database, running the IMAP watcher inside the server (stage 4 and later), and executing actions.

## Server (Python)

- Dependencies in `pyproject.toml`: `fastapi` and `uvicorn` as runtime, `httpx` in the dev group for `TestClient`.
- New package `src/remote_imap_mail_rules/server/`, one concern per module, no underscore-private names:
  - `settings.py`: `ServerSettings(BaseSettings)` with `rules_path`, `server_host` (default `127.0.0.1`), `server_port` (default `8000`) and `frontend_dist` (default `frontend/dist`).
    It is separate from `ImapSettings`, because the server must start without IMAP credentials.
    It reuses the same `RULES_PATH` env var and reads `.env` like `config.py`.
  - `api.py`: the router under `/api`.
  - `app.py`: `create_app(settings) -> FastAPI`, mounts the router and serves `frontend/dist` with an index fallback when the directory exists.
  - `main.py`: `uvicorn.run(create_app(...))` with logging set up following the `uvicorn-app-logging` skill, started by `uv run python -m remote_imap_mail_rules.server.main`.
- Endpoints:
  - `GET /api/config` returns `{mode: "server", file_name, exists}`, so the editor knows it talks to a server.
  - `GET /api/rules` returns the YAML text of `RULES_PATH` as `text/plain`, 404 when the file does not exist yet.
  - `PUT /api/rules` takes the YAML text, validates it with `parse_rules` from `rules/loader.py`, and writes it atomically (temp file in the same folder, then `os.replace`).
    On `yaml.YAMLError` or `pydantic.ValidationError` it answers 422 with a readable list of messages and writes nothing.
  - The client never sends a path, so there is no path traversal surface.
  - Sync file I/O goes through `asyncio.to_thread`.
- Because the editor sends the YAML text it generated, comments, anchors and `!var` survive a save unchanged.

## Frontend

- New `src/model/api.ts`: `fetchConfig()`, `fetchRules()`, `saveRules(text)` using relative `/api` URLs, all failing softly when no server answers (file-only mode, as today).
- `store.ts`: add `serverFile` (name or null) and a `dirty` flag that is cleared on load and save.
- `AppShell.vue`: on mount call `fetchConfig`.
  When a server answers, load its rules, show a Save button and a dirty marker, and show validation or server errors in the existing notice.
  Open, Download and Copy stay available, and opening a local file leaves server mode until the next page load, so an upload never writes to disk.
- `vite.config.ts`: add `server.proxy` for `/api` to `http://localhost:8000` for development.
- Rules still validate in the browser with ajv, so Save is disabled while there are problems, and the server check is the safety net.

## Tests

- Python, in `tests/test_server.py` with `TestClient` and a `tmp_path` rules file:
  - config and GET (file present and missing), PUT valid (file written, comments kept), PUT invalid YAML and invalid schema (422, file untouched), atomic write leaves no temp files.
- Frontend Vitest: `api.ts` with a mocked `fetch`, and the store `dirty` flag.
- Playwright (`yarn test:e2e`): keep the vite-only web server and mock `/api` with `page.route`, covering load from server, edit, save request body, a 422 shown in the notice, and file-only mode when `/api/config` fails.
  No claude-in-chrome tools.

## Docs and commits

- `README.md`: server section plus `SERVER_HOST` and `SERVER_PORT`. Add them to `.example-env`.
- `CLAUDE.md`: layout and decisions for the server. `ai/initial.md`: tick the stage 3 checklist and update "Status so far".
- Commits in lplp style, as separate tasks: (1) server package with tests and deps, (2) frontend API client and Save, (3) docs.

## Verification

- `uv run pytest`, then `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
- Manually: `yarn build`, start the server with `RULES_PATH` pointing at a copy of `rules/example.yml`, open `http://127.0.0.1:8000`, edit and save, and diff the copy.
- Run `uv run python -m remote_imap_mail_rules.rules.schema --check` to confirm the schema is untouched.
