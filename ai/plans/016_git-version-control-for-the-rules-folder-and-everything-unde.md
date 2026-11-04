# Git version control for the rules folder, and everything under `/data`

## Context

The rules should be versioned in git, controlled from the web UI: enable it, see whether `git init` was run, set the push credentials, switch automatic commit and push on or off with check boxes, and also commit and push by hand with buttons.
The UI shows the state (initialised, uncommitted changes, commits to push, last error).
Separately, all data of the container should live under `/data`: the rules directory next to the SQLite database.
I read "conflict files" as "config files" (the rules) and "permits" as "commits".

## Decisions (from the questions, plus defaults I chose)

- The database stays the source of truth in database mode.
  Every rules save also mirrors the rules as YAML into the rules directory, and that directory is what git tracks.
  In file mode (`RULES_PATH` set) the tracked folder is the parent of that file, no mirror is written.
  The mirror is the non-concrete dump of `db/rules.py` (`to_yaml`), so it has no YAML comments, same as today's database mode.
- New settings: `DATA_DIR` (default `data`, Docker sets `/data`) and `RULES_DIR` (default `DATA_DIR/rules`).
  `DATABASE_URL` keeps its local default; the Dockerfile already points it to `/data/db.sqlite3`.
- Git is run as the `git` binary through `asyncio.create_subprocess_exec` (no shell), one `asyncio.Lock` so operations never overlap.
  Every call passes `-C <dir> -c safe.directory=<dir>` (the volume owner may differ) and never reads global config (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0`).
- Git settings live in the database, edited in the UI: single-row table `git_settings` (`enabled`, `auto_commit`, `auto_push`, `remote_url`, `branch` default `main`, `auth_method` `none` / `https` / `ssh`, `username`, `token_encrypted`, `author_name`, `author_email`).
  The token is Fernet-encrypted with `SECRET_KEY` like the account passwords, write-only in the API (`has_token`).
- HTTPS credentials are handed to git through a `GIT_ASKPASS` helper (a small script under `DATA_DIR/git/`) that reads the username and token from the environment of that one process, so they never appear in the remote URL, the process list or the logs.
- The SSH deploy key is an ed25519 key generated server-side (`cryptography`, already a dependency) in `DATA_DIR/git/ssh/`, mode 0600.
  Only the public key is shown in the UI (to paste into GitHub or Gitea).
  Push uses `GIT_SSH_COMMAND="ssh -i <key> -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=<data>/git/ssh/known_hosts"`.
- Auto-commit runs after a successful rules save (a `BackgroundTasks` step next to `watcher.restart`) and commits with `git add -A` and the message `Update rules`; nothing to commit is not an error.
  Auto-push runs after a commit and needs auto-commit on (the UI disables the box otherwise).
  A failing auto step is stored as `last_error` (in memory, secrets redacted) and shown in the UI, it never fails the save.
- Status = `initialized`, `branch`, `changed` (files from `git status --porcelain`), `ahead` / `behind` of the upstream, `last_commit`, `remote_configured`, `last_error`.
  `behind` needs a fetch, so a "Check remote" button runs `git fetch`; a normal status call stays local and fast.
  A push that is rejected as non-fast-forward is reported as such, no force push and no automatic pull.
- Enabling git does not run `git init` silently: the UI shows "not initialised" with an "Initialise" button (`git init -b <branch>`, `user.name` / `user.email` from the settings, a `.gitignore` is not needed).
  Enabled but a git binary missing answers a clear error, the status says `git_available: false`.
- Everything under `/api/git` is behind the login (`protected` in `create_app`).

## Changes

### Backend

- `server/settings.py`: `data_dir`, `rules_dir` (property or field with the derived default).
- `db/models/git_settings.py` plus Alembic revision (`uv run alembic revision --autogenerate -m "git settings"`), registered in `db/models/__init__.py`; `db/git_settings.py` repository (`get`/`update`, defaults when no row, token encrypt/decrypt via `db/crypto.py`).
- `server/git_repo.py` (new): `GitRepo(directory, lock)` with `status()`, `init()`, `commit(message)`, `push()`, `fetch()`, `set_remote(url)`; a `GitError` with a redacted message; the env builder for askpass / ssh; `generate_ssh_key()` and `public_key()`.
- `server/rules_mirror.py` (new): `write_mirror(rules_dir, text)` using `rules_file.write_atomic`; called by `DatabaseRulesStore.save_text` after the commit and once at start-up when the file is missing.
  `RulesStore` gets `git_dir` (rules dir, or the parent of the file in file mode).
- `server/api/git.py` (new), mounted at `/api/git`:
  `GET /` (settings without secrets + status + public key), `PUT /settings`, `POST /init`, `POST /commit`, `POST /push`, `POST /fetch`, `POST /ssh-key` (generate or replace).
  Errors answer 409/422/502 with a readable `detail`.
- `server/api/editor.py`: after the save, `background.add_task(auto_git, request.app)` (commit, then push per the settings).
- `server/app.py`: build the `GitRepo` from the store, mount the router, keep it on `app.state.git`.
- `server/main.py`: log the data and rules directories at start-up.

### Frontend

- `src/model/git-api.ts` (new, uses the shared `http.ts` / `ApiError`): `fetchGit`, `saveGitSettings`, `gitInit`, `gitCommit`, `gitPush`, `gitFetch`, `generateSshKey`.
- `src/components/GitView.vue` (new) and a nav entry in `AppShell.vue` plus the route `/git` in `src/router.ts`, shown only when a server answers (like the accounts screen):
  - Status block with badges: not initialised, clean, N uncommitted files (expandable list), N to push, N behind, last commit, last error.
  - Check boxes "Enabled", "Commit automatically", "Push automatically" (the last disabled without auto-commit).
  - Remote URL, branch, author name and email, auth method (none / HTTPS token / SSH key); token field is write-only and shows "token saved"; SSH shows the public key with a copy button and a Generate / Regenerate button.
  - Buttons: Initialise, Commit now, Push now, Check remote; disabled with a reason when not applicable (nothing to commit, not initialised, no remote).
- Component styles follow the existing SCSS in `src/styles/`.

### Deployment and docs

- `Dockerfile`: `apt-get install git openssh-client` in the Python stage (no recommends, clean lists), `mkdir /data/rules /data/git`, `ENV DATA_DIR=/data RULES_DIR=/data/rules`, still uid 10001 and the `/data` volume.
- `docker-compose.coolify.yml`: pass nothing new that is required; comment that rules, git key and the database are all in the `data` volume.
- `.example-env`, `README.md` (variables, Git section, Deployment), `CLAUDE.md` (Layout: `git_repo.py`, `rules_mirror.py`, `api/git.py`, `GitView.vue`; Decisions: the git bullet above), `ai/initial.md` (new stage entry).

### Tests

- `tests/test_server_git.py`: `GitRepo` against a real `git` in `tmp_path` (init, status of dirty / clean, commit, ahead count with a local bare repo as remote, push, rejected push), askpass env contains no token in the argv, error redaction.
- API tests via the existing `make_client` pattern: login required, settings round trip with the token never returned, auto-commit after `PUT /api/editor/rules`, auto-push to a bare repo, auto-push needs auto-commit, git binary missing (monkeypatched).
- `tests/test_db_migrations.py` already checks model/migration drift; `tests/test_coolify_compose.py` stays in sync (no new required variable).
- Frontend: Vitest for `git-api.ts`; Playwright e2e for `GitView` with the mocked API (status badges, checkbox saving, disabled push, SSH key shown).
- All tests use `tmp_path`, `TEST_*` settings and `FakeServer`; no real remote, never the live account.

## Commits (lplp style, in this order)

1. `[backend] git:` settings table, `GitRepo`, rules mirror, `/api/git`, auto-commit and push, tests.
2. `[frontend] git:` `GitView`, api client, route, tests.
3. `[docker|coolify] deployment:` git and ssh in the image, `/data` layout, docs, CLAUDE.md, initial.md.

## Verification

- `uv run pytest`; `uv run python -m remote_imap_mail_rules.server.main` from a scratch directory on a separate port with throwaway settings, a local bare repo as the remote (never the live account).
- `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
- `docker build .` and run with an empty volume: rules, `git/` and `db.sqlite3` all appear under `/data`, git init, edit a rule, see the commit, then push to a bare repo mounted into the container.
