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
| `ADMIN_USERNAME` | none | Login of the server's admin. Without it and `ADMIN_PASSWORD` nobody can log in. |
| `ADMIN_PASSWORD` | none | Password of the admin. |
| `IMAP_ACCOUNT_ID` | optional, with the other required `IMAP_*` | An immutable UUID of your choosing (`uuidgen`). Rules reference the account by this id, because names can change. |
| `IMAP_ACCOUNT_NAME` | none | Display label only, never used as a reference. |
| `IMAP_HOST` | optional, see above | IMAP server host name. |
| `IMAP_PORT` | `993` | IMAP server port. |
| `IMAP_SSL` | `true` | Use TLS from the start. |
| `IMAP_USERNAME` | optional, see above | Login name. |
| `IMAP_PASSWORD` | optional, see above | Login password. |
| `IMAP_PAGE_SIZE` | `50` | Mails per page when loading a folder. |
| `IMAP_POLL_INTERVAL` | `60` | Seconds between polls when the server has no IDLE. |
| `RULES_PATH` | `rules/example.yml` for the demo, unset for the server | The YAML rules file. When set, the server edits this file; when unset, the rules live in the database. |
| `DATA_DIR` | `data` (`/data` in the container) | Where the server keeps what is not in the database: the rules mirror in `rules/` and the git credentials in `git/`. |
| `RULES_DIR` | `DATA_DIR/rules` | The folder git tracks. With `RULES_PATH` set, that file's folder is tracked instead. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./db.sqlite3` | Any async SQLAlchemy URL. The server runs the Alembic migrations at start-up. |
| `SECRET_KEY` | none | Fernet key that encrypts the account passwords in the database. Without it no password can be stored. |
| `WATCH_ENABLED` | `true` | Whether the server runs the rules in the background and writes the action log of each mail. |
| `ACTIONS_ENABLED` | `false` | Whether the watcher applies the actions of matching rules (the first matching rule wins) and logs them. Off, nothing is ever written to a mailbox. |
| `SERVER_HOST` | `127.0.0.1` | Interface of the server. Behind the admin login, but serve it over HTTPS when it is reachable from outside. |
| `SERVER_PORT` | `8000` | Port of the server. |
| `FRONTEND_DIST` | `frontend/dist` | Built editor that the server serves at `/`. |
| `SENTRY_DSN` | none | DSN of the backend project in Sentry or Bugsink. Empty switches the error reporting off. |
| `VITE_SENTRY_DSN` | none | DSN of the frontend project, usually another one. The server hands it to the browser at runtime (`/api/public/client-config`), so the name is only the convention of the `bugsink-setup` skill. |
| `SENTRY_ENVIRONMENT` | none | Environment tag, e.g. `production`. `VITE_SENTRY_ENVIRONMENT` overrides it for the frontend. |
| `SENTRY_RELEASE` | the commit | Release tag. Defaults to `SOURCE_COMMIT` (set by Coolify), else the git commit of the checkout. `VITE_SENTRY_RELEASE` overrides it for the frontend. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0` | 0 to 1, the share of requests that get a tracing span; 0 turns tracing off. `VITE_SENTRY_TRACES_SAMPLE_RATE` is the frontend's. |

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
- Git (the Git screen): the rules folder can be put under git from the browser.
  In database mode every save also writes the rules as `rules.yml` into `RULES_DIR`, and that folder is what git tracks (without YAML comments, as the database does not keep them); in file mode it is the folder of the `RULES_PATH` file.
  The screen shows whether `git init` was run, the uncommitted files, the commits waiting for a push, how far the remote is ahead (after "Check remote") and the last error.
  "Enabled", "Commit automatically" and "Push automatically" are check boxes, "Commit now" and "Push now" do it by hand.
  Pushing automatically needs committing automatically, a failing automatic step never fails the save and a rejected push is reported, never forced.
  The settings live in the database. Credentials are an HTTPS username and token (encrypted with `SECRET_KEY`, handed to git through `GIT_ASKPASS`, never in the URL) or an SSH deploy key the server generates in `DATA_DIR/git/ssh` (only the public key is shown, add it as a deploy key with write access).
  The image contains `git` and `ssh`.
- The accounts live in the database, passwords encrypted with `SECRET_KEY`.
  The account from the `IMAP_*` variables is optional: if all required ones are set it is added once at start-up and never overwritten afterwards, otherwise add accounts on the Accounts screen.
  If it differs from the variables later (e.g. a changed password), the log warns and the accounts screen shows a badge.
- Deleting an account that rules still refer to is refused.
- Everything under `/api` except `/api/auth` and `/api/public` (health check and the browser's error reporting config) needs a login (static files stay open).
  Log in with `ADMIN_USERNAME` and `ADMIN_PASSWORD`, it is a single user service and the mail accounts' credentials do not work.
  Changing either variable ends all sessions, and a wrong login is answered after a short pause.
  The session is a signed cookie, valid for 30 days.
  Without `SECRET_KEY` or the admin variables nobody can log in, the API then answers `503`.
- The Mail screen is a read-only mail client for the registered accounts: folders, the message list (newest first, paged), and the message with its attachments.
  HTML mail is sanitized (no scripts, no remote images) and shown in a sandboxed frame.
- The server watches every registered account in the background (`WATCH_ENABLED`) and keeps an action log per mail: when it was first seen, which rules matched it, what they did with it, and changes made outside the rules (read/unread, flags, mail that left the folder).
  The message view shows that log.
  Mails already in the folders when the server first runs are logged as first seen at that moment, and the watcher restarts after the accounts or the rules changed.
  Rule actions are not executed yet, so the log has no action entries so far.
- The Log screen lists the action log of all accounts, newest first, with search and filters (account, folder, rule, kind, time range); the filters are in the URL.
  An info box on top shows when the watcher last woke up (not known after a restart until it does), when it last found a change and when an action last ran.
- The editor always shows what it edits in the top bar: the rules file on the server, the database, or a file in memory (opened, dropped or new), which is never written to the server.
  The YAML view of the server's rules is a raw mode: it shows the server's own text and saves what you type as it is.
  In database mode comments end up in the rule descriptions.
- The rule editor can show a mail beside it ("Example mail") and fill conditions from it, e.g. the sender as name, email or domain.
  It works on a phone as well, where one pane shows at a time.

```bash
cd frontend && yarn install && yarn build && cd ..
uv run python -m remote_imap_mail_rules.server.main
```

Then open `http://127.0.0.1:8000`.

#### Error reporting

Set `SENTRY_DSN` and `VITE_SENTRY_DSN` to report errors of the server and of the browser to Sentry or Bugsink, both stay off while empty.
The browser talks to the DSN host directly, there is no tunnel, so the host needs HTTPS (if the app is served over HTTPS) and CORS headers, which Bugsink sends.
Check both sides by logging in and opening `/sample-error`, which raises a recognizable error in the backend (`GET /api/sample-error`) and in the page.
A failing start-up, such as a broken migration, is reported too.

Save writes the file after the server validated it, and a rejected file is reported in the editor and not written.
Opening or dropping a file in the editor leaves the server file alone, those only ever download.
For development run the server and `yarn dev` side by side, the dev server proxies `/api` to port 8000.

## Deployment (Coolify)

`docker-compose.coolify.yml` and the `Dockerfile` build the editor and the server into one image.
In Coolify create a Docker Compose resource from this repository, point it at the compose file and assign the domain to the `app` service.
`SERVICE_FQDN_APP_8000` routes the proxy to port 8000, and `FORWARDED_ALLOW_IPS=*` lets the server see HTTPS behind it, so the session cookie becomes `Secure`.

- Required, the deploy is blocked until it is set: `SECRET_KEY` (a Fernet key, see above; Coolify cannot generate one, and a regenerated key would lock the stored passwords).
- The login is `ADMIN_USERNAME` and `ADMIN_PASSWORD`, which the compose file fills from Coolify's magic variables `SERVICE_USER_ADMIN` and `SERVICE_PASSWORD_ADMIN`.
  Coolify generates them on the first deploy, read (or change) them in the environment variables of the resource.
- The `IMAP_*` variables are optional, add the mail accounts on the Accounts screen after logging in.
- All data lives in the `data` volume at `/data`: the SQLite database (`DATABASE_URL=sqlite+aiosqlite:////data/db.sqlite3`), the rules folder `/data/rules` and the git credentials `/data/git`.
- `ACTIONS_ENABLED` stays `false` until you set it.
- Run exactly one container, the watcher runs inside the server.
- `SENTRY_DSN`, `VITE_SENTRY_DSN` and the other `SENTRY_*` variables are optional, `SOURCE_COMMIT` (set by Coolify) becomes the release.
- The health check is `GET /api/public/health`, which touches neither the database nor IMAP.

To try the image locally: `docker build -t mail-rules .` and `docker run --rm -p 8000:8000 -e SECRET_KEY=… -e ADMIN_USERNAME=… -e ADMIN_PASSWORD=… -e WATCH_ENABLED=false mail-rules`.

## IMAP

Reading is async and read-only: folders are opened with `EXAMINE` and mails are fetched with `BODY.PEEK`.
The only writes are the actions of rules (`STORE` for flags and keywords, `MOVE` or `COPY` + `UID EXPUNGE` for moves) and they only run when `ACTIONS_ENABLED=true`; by default the server never writes to a mailbox.
The first matching rule (in file order) wins; if it changed the mail the rules are evaluated again from the top, and a move ends the pass.
In the rule editor the **Dry run** button of a rule shows what the rules would do to the mails it covers, without changing anything; **Run now** applies it once the server is allowed to.
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
