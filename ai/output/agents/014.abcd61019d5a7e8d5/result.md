Findings for stage 3, read-only exploration. Repo root is `/Users/user/Documents/programming/Python/remote_imap_mail_rules`.

**(1) pyproject.toml** (`/Users/user/Documents/programming/Python/remote_imap_mail_rules/pyproject.toml`)
- Python is `>=3.14` (line 6). Runtime deps (lines 7-12) are `aioimaplib>=2.0.1`, `pydantic>=2.11`, `pydantic-settings>=2.8` and `pyyaml>=6.0`.
- Dev group (lines 14-19) has `pytest>=8.0`, `pytest-asyncio>=0.24` and `types-pyyaml`.
- **fastapi and uvicorn are not present.** `httpx` isn't either, and you'd need it for `TestClient`. To serve the built frontend as static files, `StaticFiles` needs no extra dependency.
- There is no `[project.scripts]` and no entry points. The build backend is hatchling, with wheel packages `src/remote_imap_mail_rules` (lines 21-26).
- pytest config (lines 28-31): `asyncio_mode = "auto"`, function loop scope, `testpaths = ["tests"]`.
- There is no `__main__.py` in the package. Everything runs as `python -m remote_imap_mail_rules.demo` or `...rules.schema`.

**(2) Settings and env**
- The settings module is `src/remote_imap_mail_rules/config.py`, not `settings.py`. `ImapSettings(BaseSettings)` is at lines 10-28 and reads `.env` from the cwd (line 17, `extra="ignore"`, case-insensitive).
- Field names map straight to env vars: `IMAP_ACCOUNT_ID`, `IMAP_ACCOUNT_NAME`, `IMAP_HOST`, `IMAP_PORT`, `IMAP_SSL`, `IMAP_USERNAME`, `IMAP_PASSWORD`, `IMAP_PAGE_SIZE`, `IMAP_POLL_INTERVAL`.
- **`RULES_PATH` already exists** as `rules_path: Path = Path("rules/example.yml")` (line 28).
- Because `ImapSettings` requires the IMAP fields, a server that only edits rules would fail to start without IMAP credentials. You'd need a separate small settings class holding just `rules_path`, or an optional watcher.
- `.example-env` has `RULES_PATH=rules/example.yml` at line 12.
- README env docs are at `README.md` lines 9-30 (the table row for `RULES_PATH` is line 28). Line 30 says tests use the `TEST_` prefix.
- `tests/settings.py` lines 6-10 defines `TestImapSettings(ImapSettings)` with `env_prefix="TEST_"` and `env_file=None`.

**(3) Rules loader and schema**
- `rules/loader.py`:
  - `RuleLoader(yaml.SafeLoader)` supports the `!var` shorthand (lines 11-21).
  - `parse_rules(text) -> RuleFile[Never]` (lines 24-28) runs `yaml.load`, then `RuleFile.model_validate(...)`, then `.concrete()`, which resolves templates.
  - `load_rules(path)` (lines 31-32) calls `parse_rules` on `path.read_text("utf-8")`.
- There is no custom error type. Errors come as `yaml.YAMLError` for syntax problems and `pydantic.ValidationError` for models. The model validators in `rules/models.py` (lines 142-307) raise `ValueError`, which pydantic wraps. A missing template variable raises `ValueError` at models.py line 65.
- There is no "validate only" or dump function. A save endpoint would call `parse_rules(text)` to validate and catch `(yaml.YAMLError, ValidationError)` to return a 422.
- `rules/schema.py`:
  - `schema_text()` (lines 17-26), `main()` with `--write-schema` / `--check` (lines 29-46), and `SCHEMA_PATH = <repo>/schemas/rules.schema.json` (line 14).
  - The frontend validates with ajv against that same JSON file.

**(4) Matching and demo startup**
- `matching.py` line 164: `async def matches(settings, rule_file, factory=connect_aioimaplib, follow=True, on_inspect=None) -> AsyncIterator[RuleMatch]`. It is an async generator with one task per folder, and its `finally` block (lines ~205-211) cancels the tasks cleanly.
- `demo.py`:
  - `parse_args` is at line 77.
  - `async main(args)` is at lines 97-116. It builds `ImapSettings()`, calls `load_rules(settings.rules_path)` once, and does `async for found in matches(...)` with prints.
  - The entry point is lines 119-125: `logging.basicConfig(...)` then `asyncio.run(main(cli_args))`.
- The server could run the watcher in the background, because it is already asyncio-native and cancellable. Use a FastAPI `lifespan` that does `asyncio.create_task(...)` around an `async for` loop over `matches(...)`, and cancel the task on shutdown. Two caveats:
  - Rules are loaded once at start, so after a save you'd have to cancel and restart the task to pick up changes.
  - The watcher needs the full IMAP settings, so it should be optional.

**(5) Frontend** (`frontend/`)
- There is no `App.vue`. The root is `src/components/AppShell.vue`, mounted in `src/main.ts` line 5.
- Source layout:
  - `src/components/` holds ActionsEditor, AppShell, ConditionNode, FieldValue, LocationsEditor, RuleEditor, RuleList, TemplatesView and YamlPanel.
  - `src/model/` holds catalog, comments, context, store, types, validate, values and yaml-io.
  - `src/__tests__/` holds the vitest specs, and `src/styles/main.scss` holds the styles.
- File I/O, all in `AppShell.vue`:
  - `openFile(file)` (lines 17-24) does `store.load(await file.text(), file.name)` and sets `notice`.
  - `onPick` / `onDrop` / `onDragOver` handle the file input and drag-and-drop (lines 26-43).
  - The "Open…" button and the hidden `<input type=file>` are at lines 87-88.
  - `download()` (lines 45-52) builds a Blob from `store.yaml.value` and clicks an `<a download=store.fileName.value>`.
  - The Download button is at line 109. `copy()` is at line 54.
  - There is no disk write, and there is no `fetch` anywhere in `src/`.
- `src/model/store.ts`:
  - `createStore()` is at line 25, with `fileName = ref('rules.yml')` at line 29.
  - `load(text, name?)` is at lines 86-95. It calls `parseRulesWithComments` and switches the view.
  - `yaml` is a computed `stringifyRules(file, comments.value)` (line 98). Undo/redo history is a JSON-snapshot watch.
  - It doesn't track a dirty flag or a server origin. A save button would POST `store.yaml.value`, and loading would call `store.load(text, name)`.
- `src/model/yaml-io.ts` exports `RulesParseError` (line 26), `parseRules` (57), `parseRulesWithComments` (61), `stringifyRules` (82) and `expandRules` (146). It uses the `yaml` library and keeps comments.
- `src/model/validate.ts` exports `validateRules(file): Problem[]` (line 65).
- `frontend/vite.config.ts`:
  - Plugins are vue and vueDevTools.
  - Aliases: `@` for `src` and `@schema` for `../schemas/rules.schema.json`.
  - `server.fs.allow: ['..']`.
  - There is **no `base` and no `server.proxy`**. For dev against FastAPI you'd add `server.proxy: {'/api': 'http://localhost:8000'}`. Relative `/api` calls work in production when FastAPI serves `dist/`.
- `package.json` scripts:
  - Build: `build` (runs `type-check` and `build-only`) and `build-only` (`vite build`).
  - Dev and test: `dev`, `preview`, `test` (`vitest run`), `test:unit`, `test:e2e` (`playwright test`) and `type-check` (`vue-tsc --build`).
  - Lint and format: `lint` (oxlint and eslint) and `format`.
  - Yarn 4.12 is the package manager.
- E2E:
  - `playwright.config.ts` uses `testDir ./e2e`, port 5199, and `webServer: yarn vite --port 5199 --strictPort`.
  - `baseURL` is `http://localhost:5199`, with a chromium project only.
  - `e2e/editor.spec.ts` (183 lines) goes to `/` and covers open, drop, edit, undo and YAML-view tests.
  - `vitest.config.ts` merges the vite config, uses jsdom, and excludes `e2e/**`.

**(6) Python tests** (`tests/`)
- Files: `conftest.py`, `fake_imap.py`, `settings.py`, `test_config.py`, `test_demo.py`, `test_imap.py`, `test_integration.py`, `test_matching.py`, `test_rules_evaluate.py`, `test_rules_models.py`, `test_rules_readme.py` and `test_rules_templates.py`.
- `conftest.py` has `ACCOUNT_ID`, `NOW`, the `RAW` mail text, `make_mail()` (line 28) and a `mail` fixture. It has no app or client fixtures.
- Async tests run through pytest-asyncio auto mode. `test_matching.py` uses `asyncio.wait_for` and `create_task` against `fake_imap.py`, a fake IMAP server.
- **No httpx or `TestClient` use anywhere.** You'd add `httpx` to the dev group.

**(7) Docker and logging**
- There is no Dockerfile or compose file in the repo root.
- Logging is `logging.getLogger(__name__)` in `matching.py` (line 18) and `demo.py` (line 23). The only `basicConfig` is in `demo.py` line 121, with DEBUG if `--verbose`, else INFO. No other setup exists.
- The repo has a `uvicorn-app-logging` skill (`.claude/skills/uvicorn-app-logging`) that fits the FastAPI plus `uvicorn.run()` logging setup.

**Other facts relevant to stage 3**
- The `rules/` directory holds `example.yml`, `rules.example.yml`, `rules.local*.yml` and `README.md`.
- The previous plans are `ai/plans/005_plan-vue-frontend-for-the-rules-file.md` and `006_stage-2-rule-editor-...md`.