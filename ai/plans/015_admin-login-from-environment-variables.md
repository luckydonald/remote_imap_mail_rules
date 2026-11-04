# Admin login from environment variables

## Context

Today the login accepts the username and password of any stored IMAP account, and the Coolify deploy is blocked until a first `IMAP_*` account is set, because without one nobody could log in.
That couples "who may use the service" to "which mailboxes exist".
This change adds a real admin user configured through `ADMIN_USERNAME` and `ADMIN_PASSWORD` (set in Coolify), makes it the only way to log in, and makes the `IMAP_*` seed account optional.
Mail accounts are then added in the accounts screen after the first login.

## Decisions (defaults I chose, say if you want otherwise)

- Single admin user, plain `ADMIN_PASSWORD` in the environment, compared in constant time (`hmac.compare_digest` on both fields, no short-circuit).
  No hashed variant for now, Coolify secrets are already the trust boundary, and `SECRET_KEY` is the same kind of secret.
- Mail account credentials no longer unlock the service.
- Without `ADMIN_USERNAME` and `ADMIN_PASSWORD` the gated routes and `/api/auth/login` answer `503` with a clear message, like today for a missing `SECRET_KEY`.
- `SECRET_KEY` stays required: it signs the session and encrypts the stored account passwords.
- The session token binds to the admin: its content is an HMAC (keyed with `SECRET_KEY`) of the username and password, so changing either variable in Coolify logs everybody out.
- A failed login waits about half a second before answering, a cheap brake on guessing.
  No per-IP state.

## Changes

### Backend

- `server/settings.py`: add `admin_username: str | None` and `admin_password: SecretStr | None`.
- `server/auth.py`:
  - `make_session_token(settings)` encrypts the fingerprint instead of the constant `TOKEN_CONTENT`, raising `CryptoError` / a new error when the admin is not configured.
  - `is_logged_in` compares the decrypted token to the current fingerprint in constant time.
  - `require_login` returns `503` when `secret_key` or the admin variables are missing.
  - New `check_admin_credentials(settings, username, password) -> bool`.
- `server/api/auth.py`: `login` drops the DB session and `find_by_credentials`, uses `check_admin_credentials`, sleeps on failure.
- `db/accounts.py`: remove `find_by_credentials` (now unused) and its tests.
- `config.py`: `ImapSettings` gets `env_ignore_empty=True`, so optional empty `IMAP_*` lines in the compose file count as unset and `load_env_account` returns `None` as before.
  Check that `TEST_`-prefixed subclass behaviour is unaffected.
- `app.py` / `main.py`: no structural change, seeding stays optional (`env_account` may be `None`).
  `main.py` logs at start-up whether an admin is configured (never the password).

### Frontend

- `MailLogin.vue`: hint text changes from "any account registered on this server" to "the administrator login of this server".
- Check the mail screen and the accounts screen have a sensible empty state when no account exists yet (a pointer to the accounts screen), add one if missing.
- Update `e2e/mail-mock.ts` / specs only where the wording is asserted.

### Deployment and docs

- `docker-compose.coolify.yml`: `ADMIN_USERNAME=${ADMIN_USERNAME:?}`, `ADMIN_PASSWORD=${ADMIN_PASSWORD:?}`; the `IMAP_*` lines become optional (`${VAR:-}`, `IMAP_PORT` / `IMAP_SSL` / sizes keep their defaults), comment says the first account can also be added in the UI.
- `.example-env`, `README.md` (variable table, Server section, Deployment section, local docker example), `CLAUDE.md` (Decisions: login line, Layout settings mention), `ai/initial.md` (new stage entry and status line).

### Tests

- `tests/test_server_auth.py`: fixture sets admin settings; cases: right login, wrong user, wrong password, any mail account's credentials rejected, `503` without admin variables, changing the password invalidates an existing cookie, failed login still `401`.
- Shared helpers in `test_server_accounts.py` (`make_client`) and the other server tests that call `make_session_token(settings)`: give their `ServerSettings` admin values.
  Files: `test_server.py`, `test_server_events.py`, `test_server_watcher.py`, `test_server_dry_run.py`, `test_server_mail.py`, `test_server_rules_db.py`, `test_server_sentry.py`.
- `tests/test_coolify_compose.py`: required list becomes `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`; new test that no `IMAP_*` variable is required.
- A test that the server starts and logs in with no `IMAP_*` account at all.

## Commits (lplp style, in this order)

1. `[backend] login:` admin user from environment, tests.
2. `[frontend] login:` wording and empty state.
3. `[docker|coolify] deployment:` compose, example env, README, CLAUDE.md, initial.md.

## Verification

- `uv run pytest`, `uv run python -m remote_imap_mail_rules.server.main` on a separate port with `TEST_`-style throwaway settings only (never the live account).
- `cd frontend && yarn test && yarn lint && yarn build`, then `yarn test:e2e` for the login flow (Playwright, no Chrome tools).
- `docker compose --env-file /dev/null -f docker-compose.coolify.yml config` fails without the three required variables and passes with them and no `IMAP_*`.
