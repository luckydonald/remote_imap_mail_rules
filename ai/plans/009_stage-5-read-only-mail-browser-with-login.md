# Stage 5: read-only mail browser with login

## Context

Stages 1 to 4 are done: rules, editor, FastAPI server, and a database holding accounts with Fernet-encrypted passwords.
Stage 5 adds a simple read-only mail client for the registered accounts, styled like Apple Mail and usable on mobile.
Scope for this run, as decided: the viewer and the login.
Fill-from-mail and the action log stay in the unchecked part of stage 5 and come later.
Login is deliberately simple: the user picks an account and enters its password, the server compares it with the stored (decrypted) password.

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
  - `POST /login` with `account_id` and `password`, compared against the decrypted stored password with `hmac.compare_digest`; 401 on mismatch.
  - On success set an HttpOnly, SameSite=Lax cookie holding a Fernet token (from `SECRET_KEY`, with a TTL) of the account id.
  - `POST /logout` clears it, `GET /me` returns the account or 401.
  - `current_account` dependency for the mail router.
  - Editor and accounts endpoints stay ungated, as today.
- `api/mail.py` at `/api/mail`, all behind `current_account`, one `async with ImapClient` per request:
  - `GET /folders`: name, display name, special use, total and unseen counts.
  - `GET /folders/{folder}/messages?before_uid=&limit=`: summaries (uid, from, subject, date, seen, flagged, has attachments, size) and the total.
  - `GET /folders/{folder}/messages/{uid}`: headers, text body, HTML body, attachment list.
  - `GET /folders/{folder}/messages/{uid}/parts/{n}`: attachment download or inline image, with a safe `Content-Disposition`.
- HTML safety: sanitize with `nh3` (new dependency) on the server, rewrite `cid:` URLs to the part endpoint, strip remote images by default, and render in a sandboxed iframe in the frontend.
- Map `ImapError`, `AioImapException`, `OSError` to 502 and `TimeoutError` to 504 with a message.

## Frontend

- `model/mail-api.ts`: copy the shape of `accounts-api.ts` (`BASE`, error class with `messages`, the `failure` helper), plus the login calls.
- `components/MailView.vue` with a folder sidebar, message list and reading pane, built from smaller components (`MailFolders`, `MailList`, `MailMessage`), and `MailLogin.vue`.
- `AppShell.vue`: widen `screen` to `'rules' | 'accounts' | 'mail'`, turn the single topbar toggle into a small nav, and add a `v-else-if` branch.
- Styles in `styles/main.scss` using the existing CSS variables and dark mode; at the existing 760px breakpoint the three panes collapse into a stack with back navigation (folders, then list, then message).
- Infinite scroll in the list via `before_uid`.
- Stay in file-only mode when no server answers, like the accounts screen.

## Tests

- Extend `tests/fake_imap.py`: list attributes, STATUS counts, multipart and attachment structures, `BODY.PEEK[1.2]` sections, `SEARCH` with `UID` ranges.
- pytest: client additions, `imap_settings`, auth (wrong password, cookie, expiry), mail router via `TestClient` with the fake factory, HTML sanitizing, error mapping.
- Vitest: `mail-api.spec.ts` and component specs.
- Playwright: `e2e/mail.spec.ts` with mocked `**/api/mail**` and `**/api/auth**`, including a mobile viewport below 760px.

## Docs

- Update the Layout and Decisions sections of `CLAUDE.md`, `ai/initial.md` (tick stage 5 items and the status lists) and `README.md`.
- Commit as separate tasks in `/commit-with-lplp-style`: IMAP additions, auth, mail API, frontend.

## Verification

- `uv run pytest`, `cd frontend && yarn lint && yarn test && yarn build && yarn test:e2e`.
- Run the server and the frontend dev server and look at the viewer through the Playwright e2e tests only (not the Chrome tools).
- Confirm that no write command reaches the fake server by checking its `commands` log in the new tests.
