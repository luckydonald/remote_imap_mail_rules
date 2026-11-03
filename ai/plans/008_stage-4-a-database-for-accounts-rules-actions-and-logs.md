# Stage 4: a database for accounts, rules, actions and logs

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Stages 1 to 3 are done: rules match against one IMAP account from `.env`, the Vue editor works on files, and the FastAPI server loads and saves the file at `RULES_PATH`.
Stage 4 of `ai/initial.md` adds a database, so several accounts can be managed in the server and rules can live in the database when no `RULES_PATH` is set.
Decisions from the questions: one database row per rule, the encryption key comes from a `SECRET_KEY` env var, and this stage includes an accounts screen in the Vue app.
Not in scope: the IMAP watcher running inside the server, executing actions, the action log tables (they come with stage 5), and Postgres or MySQL (only kept possible by the abstraction).

## Database layer (Python)

- Dependencies: `sqlalchemy[asyncio]`, `aiosqlite`, `alembic`, `cryptography`.
- New package `src/remote_imap_mail_rules/db/`, one concern per module, no underscore names:
  - `base.py`: `DeclarativeBase` with a naming convention for constraints, so Alembic can alter them on SQLite and Postgres alike.
  - `models/account.py`, `models/rule.py`, `models/template.py`: typed `Mapped[...]` models.
  - `engine.py`: `create_engine(database_url)`, an `async_sessionmaker`, and a FastAPI dependency yielding a session.
    Only the URL decides the backend, nothing else imports `aiosqlite`.
  - `crypto.py`: Fernet `encrypt(secret_key, plain) -> str` and `decrypt(...)`.
  - `migrate.py`: runs `alembic upgrade head` programmatically at server start, through `asyncio.to_thread`.
- Alembic at the repo root: `alembic.ini` and `migrations/` with an async `env.py` that reads `DATABASE_URL`, plus the first revision for the tables below.
- `ServerSettings` gets `database_url` (default `sqlite+aiosqlite:///./db.sqlite3`), `secret_key: SecretStr | None`, and `rules_path` becomes `Path | None = None`.
  An explicitly set `RULES_PATH` means file mode, otherwise database mode.
  `config.py` (the watcher's `ImapSettings`) is left alone.
- `.gitignore` gets `*.sqlite3` and `*.sqlite3-journal`, and `.example-env` documents `DATABASE_URL` and `SECRET_KEY` with the one-liner that generates a Fernet key.

### Tables

- `accounts`: `id` (UUID, primary key, immutable, equals `IMAP_ACCOUNT_ID` for the seeded one), `name`, `host`, `port`, `ssl`, `username`, `password_encrypted`, `page_size`, `poll_interval`, `created_at`, `updated_at`.
- `rules`: `id` (UUID, primary key, kept across saves so the later action log can refer to it), `position`, `name`, `enabled`, `locations` (JSON), `when` (JSON), `actions` (JSON).
  The JSON is the non-concrete pydantic dump, so template uses and `Var` survive.
- `templates`: `name` (primary key) and `definition` (JSON), the root `templates` of the rule file.

## Accounts

- `db/accounts.py` is the repository: list, get, create, update, delete, plus `seed_from_env` and the drift check.
- Seeding runs in the app lifespan after the migrations.
  If `ImapSettings` validates from the environment and the account id is not in the table, the account is inserted with the encrypted password.
  If the id exists, nothing is overwritten.
  Instead host, port, ssl, username and password are compared with the env values, and a mismatch logs a warning naming the differing fields (never the values) and is returned by the API as `env_differs: list[str]` on that account.
  Without `SECRET_KEY`, seeding is skipped with a warning, and creating or updating a password answers 503.
- `server/api/accounts.py`, mounted at `/api/accounts`:
  - `GET /` list, `POST /` create (id generated server side), `GET /{id}`, `PUT /{id}` (password optional, omitted keeps the stored one), `DELETE /{id}`.
  - Responses never contain the password, only `has_password`.
  - Deleting an account that rules still refer to answers 409 with the rule names, checked against the active rules source.

## Rules source

- `server/rules_store.py` defines a small `RulesStore` protocol (`read_text`, `save_text`, `exists`, `label`) with two implementations: `FileRulesStore` wrapping the current `rules_file.py`, and `DatabaseRulesStore`.
- `api/editor.py` talks only to the store chosen in `create_app`, so the endpoints and the editor stay as they are.
  `GET /config` additionally returns `source: "file" | "database"`, and `file_name` is null in database mode.
- `DatabaseRulesStore`:
  - `save_text` validates with `parse_rules` exactly like the file, then parses the non-concrete `RuleFile` and replaces templates and rules in one transaction, matching old rows by name so unchanged rules keep their id.
  - `read_text` builds a `RuleFile` from the rows and dumps it with `yaml.safe_dump` (`sort_keys=False`), `404` when there are no rules and no templates yet.
  - **Trade-off of one row per rule:** comments and YAML anchors are not stored, so a round trip through the database drops them.
    The editor keeps its own comments only while it holds the text, file mode is unchanged, and the plan notes this in the README.
  - Risk to check first: the dump of a template use must parse back to the same model, covered by a round-trip test.

## Frontend (accounts screen)

- `src/model/accounts-api.ts`: the `/api/accounts` client, soft failing like `api.ts`.
- `src/components/AccountsView.vue` plus a nav entry in `AppShell.vue`, shown only when a server answers: list with a drift warning badge, add and edit form (name, host, port, SSL, username, write-only password with an "unchanged" placeholder), delete with an in-page confirmation (no `window.confirm`).
- `EditorConfig` in `api.ts` gets `source`, and the save button label shows the file name or "database".
- Style follows `frontend/` (no semicolons, single quotes, SCSS, light and dark).

## Tests

- pytest: crypto round trip, migrations against a temp SQLite (upgrade works, and an autogenerate check finds no model drift, like the schema check), accounts API (CRUD, no password leak, 409, 503 without key), seeding and the drift warning, the database rules store (save, read, ids kept, template round trip, invalid YAML answers 422 and changes nothing), and file mode still passing the existing `tests/test_server.py`.
- Vitest for the accounts client and form logic, Playwright with the API mocked for list, add, edit, delete and the drift badge (`yarn test:e2e`, not the Chrome tools).

## Commits (each its own task, lplp style)

1. `[backend] db`: dependencies, `db/` package, Alembic with the first migration, settings, `.gitignore`, `.example-env`.
2. `[backend] accounts`: crypto, repository, seeding, drift check, `/api/accounts`, tests.
3. `[backend] rules store`: `RulesStore`, database mode, `source` in the config, tests.
4. `[frontend] accounts`: client, view, navigation, Vitest and Playwright.
5. `[docs]`: README, `CLAUDE.md` layout and decisions, `ai/initial.md` ticks for stage 4 and the status section.

## Verification

- `uv run pytest`, `uv run python -m remote_imap_mail_rules.server.main` against a temp `DATABASE_URL`, and `uv run alembic upgrade head` on an empty database.
- `cd frontend && yarn test && yarn test:e2e && yarn build && yarn lint`.
- Check the file mode by setting `RULES_PATH`, and database mode by unsetting it, saving a rules file through the editor and reloading.
