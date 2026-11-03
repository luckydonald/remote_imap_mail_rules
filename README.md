# remote_imap_mail_rules

Runs mail rules via IMAP, so rules are independent of the mail provider.

## Setup

```bash
uv sync
cp .example-env .env   # then edit
uv run pytest
```

## Configuration

Read from the environment and from `.env` in the working directory (see `.example-env`).

| Variable | Default | Description |
|---|---|---|
| `IMAP_ACCOUNT_ID` | required | An immutable UUID of your choosing (`uuidgen`). Rules reference the account by this id, because names can change. |
| `IMAP_ACCOUNT_NAME` | none | Display label only, never used as a reference. |
| `IMAP_HOST` | required | IMAP server host name. |
| `IMAP_PORT` | `993` | IMAP server port. |
| `IMAP_SSL` | `true` | Use TLS from the start. |
| `IMAP_USERNAME` | required | Login name. |
| `IMAP_PASSWORD` | required | Login password. |
| `IMAP_PAGE_SIZE` | `50` | Mails per page when loading a folder. |
| `IMAP_POLL_INTERVAL` | `60` | Seconds between polls when the server has no IDLE. |
| `RULES_PATH` | `rules/example.yml` for the demo, unset for the server | The YAML rules file. When set, the server edits this file; when unset, the rules live in the database. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./db.sqlite3` | Any async SQLAlchemy URL. The server runs the Alembic migrations at start-up. |
| `SECRET_KEY` | none | Fernet key that encrypts the account passwords in the database. Without it no password can be stored. |
| `SERVER_HOST` | `127.0.0.1` | Interface of the server. It has no login yet, so only expose it on a trusted network. |
| `SERVER_PORT` | `8000` | Port of the server. |
| `FRONTEND_DIST` | `frontend/dist` | Built editor that the server serves at `/`. |

The automated tests read the same names with a `TEST_` prefix (e.g. `TEST_IMAP_HOST`) and never read `.env`.

## Rules

Rules are YAML, validated by the pydantic model in `src/remote_imap_mail_rules/rules/models.py`.
The JSON schema for IDE completion is generated from it:

```bash
uv run python -m remote_imap_mail_rules.rules.schema --write-schema
uv run python -m remote_imap_mail_rules.rules.schema --check
```

See `rules/example.yml`.
Conditions on a field that does not exist are false for every operator, use the `presence` condition to test for that.
A relative date such as `7d` is the moment seven days before now, so `date_received lt 7d` means received more than a week ago.

### Rule editor

A visual editor for the rules file lives in `frontend/`.
It runs in the browser without a server: open or drop a rules file, edit rules, conditions, actions and templates, then download the YAML.

```bash
cd frontend
yarn install
yarn dev
```

The editor validates against `schemas/rules.schema.json`, and keeps the comments of the opened YAML.

### Server

The FastAPI server serves the built editor and lets it load and save the rules, and manages the accounts.
It needs no IMAP credentials.
Generate a `SECRET_KEY` once with `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

- The rules are stored in the file at `RULES_PATH` when that is set, otherwise in the database, one row per rule.
  A file keeps comments and YAML anchors, the database does not, because it stores the parsed rules.
- The accounts live in the database, passwords encrypted with `SECRET_KEY`.
  The account from the `IMAP_*` variables is added once at start-up, and never overwritten afterwards.
  If it differs from the variables later (e.g. a changed password), the log warns and the accounts screen shows a badge.
- Deleting an account that rules still refer to is refused.

```bash
cd frontend && yarn install && yarn build && cd ..
uv run python -m remote_imap_mail_rules.server.main
```

Then open `http://127.0.0.1:8000`.
Save writes the file after the server validated it, and a rejected file is reported in the editor and not written.
Opening or dropping a file in the editor leaves the server file alone, those only ever download.
For development run the server and `yarn dev` side by side, the dev server proxies `/api` to port 8000.

## IMAP

Everything is read-only and async: folders are only opened with `EXAMINE`, mails are fetched with `BODY.PEEK`, and nothing writes to the mailbox.
Headers, flags, size and structure are loaded per page (newest first), bodies are downloaded lazily and only when a rule needs `body_text` or `body_html`.
New mails are noticed via `IDLE` push when the server supports it, otherwise by polling every `IMAP_POLL_INTERVAL` seconds; flag changes are detected with `CONDSTORE`, where available.
A location with `recursive: true` covers the folder and the folders below it as they exist at start-up; folders that do not exist are skipped with a warning.
Folder names are used as the server sends them (modified UTF-7 for non-ASCII names).

`matching.matches()` is the core async generator: it yields every mail that matches a rule, first the existing ones, then new and changed ones as they arrive.

```bash
uv run python -m remote_imap_mail_rules.demo
```

prints those matches for the account in `.env`.
`tests/test_integration.py` runs against a real server if the `TEST_IMAP_*` variables are set.
