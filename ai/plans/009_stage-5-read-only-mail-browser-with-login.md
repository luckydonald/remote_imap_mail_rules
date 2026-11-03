# Stage 5: read-only mail browser with login

## Context

Stages 1 to 4 are done: rules, editor, FastAPI server, and a database holding accounts with Fernet-encrypted passwords.
Stage 5 adds a simple read-only mail client for the registered accounts, styled like Apple Mail and usable on mobile.
Scope for this run, as decided: the viewer and the login.
Fill-from-mail and the action log stay in the unchecked part of stage 5 and come later.
Login is deliberately simple and guards the whole API: this is a single-user service, so the credentials of any registered account unlock everything.
The server compares the entered username and password with the stored (decrypted) ones.
Only static files and `/api/auth/*` stay open.

## Backend

### IMAP layer (`imap/`)

- `models.py`, `client.py`: add `folder_counts(folder)` (STATUS `MESSAGES UNSEEN`) for the folder list badges.
- `client.py`: add `list_page(folder, before_uid=None, limit)` returning `(mails, total)`, newest first, built on the existing `search_uids` / `fetch_mails` / `uid_ranges`, so the viewer does not need the forward-only `iter_pages`.
- `client.py`: add `fetch_part(folder, uid, part_number)` returning decoded bytes plus the `Part` (base64 / quoted-printable aware, `BODY.PEEK[n]`), reusing `parse_fetch` sections and `bodystructure.parse_parts`.
- `mail.py`: keep the part number on `Attachment`, so the API can link to the download.
- Special-use detection (`\sent`, `\trash`, ...) from the existing lowercased `FolderInfo.attributes`, plus a display name decoded from modified UTF-7 (API only, the wire name stays as the server sends it, per the CLAUDE.md decision).
- Everything stays read-only: `EXAMINE`, `BODY.PEEK`, nothing added to the `ImapConnection` protocol.

### Server (`server/`)

- `db/accounts.py`: add `imap_settings(account, secret_key)` building `ImapSettings` (with `_env_file=None`) from an `Account` row; `CryptoError` maps to 503 like in `api/accounts.py`.
- `app.py`: put an IMAP `ConnectionFactory` on `app.state` (default `connect_aioimaplib`), the seam for tests.
- `server/auth.py` and `api/auth.py` at `/api/auth`:
  - `POST /login` with `username` and `password`; it matches against all accounts (username plus decrypted password, `hmac.compare_digest`), 401 on no match.
  - On success set an HttpOnly, SameSite=Lax cookie holding a Fernet token (from `SECRET_KEY`, with a TTL).
    The token only says "logged in", it grants no per-account scope.
  - `POST /logout` clears it, `GET /me` returns 200 or 401.
  - A `require_login` dependency is applied at `include_router` time in `app.py` to `accounts`, `editor` and `mail`, so a new router cannot forget it.
  - Without `SECRET_KEY` login is impossible (503, same as the accounts API), and a fresh database is covered because the env account is seeded.
- `api/mail.py` at `/api/mail`, behind `require_login`, with `account_id` in the path (`/accounts/{account_id}/folders`, ...), one `async with ImapClient` per request:
  - `GET /accounts/{account_id}/folders`: name, display name, special use, total and unseen counts.
  - `GET /accounts/{account_id}/folders/{folder}/messages?before_uid=&limit=`: summaries (uid, from, subject, date, seen, flagged, has attachments, size) and the total.
  - `GET .../messages/{uid}`: headers, text body, HTML body, attachment list.
  - `GET .../messages/{uid}/parts/{n}`: attachment download or inline image, with a safe `Content-Disposition`.
- HTML safety: sanitize with `nh3` (new dependency) on the server, rewrite `cid:` URLs to the part endpoint, strip remote images by default, and render in a sandboxed iframe in the frontend.
- Map `ImapError`, `AioImapException`, `OSError` to 502 and `TimeoutError` to 504 with a message.

## Frontend

- `model/mail-api.ts`: copy the shape of `accounts-api.ts` (`BASE`, error class with `messages`, the `failure` helper), plus the login calls.
- `components/MailView.vue` with a folder sidebar, message list and reading pane, built from smaller components (`MailFolders`, `MailList`, `MailMessage`), and `MailLogin.vue`.
- `AppShell.vue`: widen `screen` to `'rules' | 'accounts' | 'mail'`, turn the single topbar toggle into a small nav, and add a `v-else-if` branch.
- Styles in `styles/main.scss` using the existing CSS variables and dark mode; at the existing 760px breakpoint the three panes collapse into a stack with back navigation (folders, then list, then message).
- Infinite scroll in the list via `before_uid`.
- Login gating changes how the shell probes the server: `GET /api/editor/config` answering 401 means "server present, log in", while a network error or 404 still means file-only mode.
  `AppShell` shows `MailLogin` on 401 and loads the rules and accounts after login; a 401 later sends the user back to it.
- Stay in file-only mode when no server answers, like today.

## Tests

- Extend `tests/fake_imap.py`: list attributes, STATUS counts, multipart and attachment structures, `BODY.PEEK[1.2]` sections, `SEARCH` with `UID` ranges.
- pytest: client additions, `imap_settings`, auth (wrong password, any account works, cookie, expiry, every non-auth `/api` route returns 401 without it; existing server tests log in first), mail router via `TestClient` with the fake factory, HTML sanitizing, error mapping.
- Vitest: `mail-api.spec.ts` and component specs.
- Playwright: `e2e/mail.spec.ts` with mocked `**/api/mail**` and `**/api/auth**`, including a mobile viewport below 760px.

## Docs

- Update the Layout and Decisions sections of `CLAUDE.md`, `ai/initial.md` (tick stage 5 items and the status lists) and `README.md`.
- Commit as separate tasks in `/commit-with-lplp-style`: IMAP additions, auth, mail API, frontend.

## Verification

- `uv run pytest`, `cd frontend && yarn lint && yarn test && yarn build && yarn test:e2e`.
- Run the server and the frontend dev server and look at the viewer through the Playwright e2e tests only (not the Chrome tools).
- Confirm that no write command reaches the fake server by checking its `commands` log in the new tests.
