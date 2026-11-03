Findings for stage 5 (read-only mail browser). No files were written.

## 1. IMAP layer (`src/remote_imap_mail_rules/imap/`)

**What exists**
- `ImapClient` (`client.py:72`) is an async context manager: `connect` (l.92) logs in, `close` (l.99) logs out, `__aenter__` (l.83) connects. It is built from `ImapSettings` and a `ConnectionFactory` (l.33, default `connect_aioimaplib`, l.36). It holds one examined folder at a time (`self.folder`, `self.state`).
- Folder listing is `list_folders(pattern="*")` (l.156), returning `FolderInfo(name, attributes, delimiter)` (`models.py:35`).
  - Attributes are lowercased, e.g. `\noselect`.
  - `FolderInfo.selectable` (`models.py:41`) is the only derived property.
  - `parse_list` is at `fetch.py:82`.
- `poll_state(folder)` (l.145) runs STATUS for UIDNEXT, UIDVALIDITY and HIGHESTMODSEQ without selecting the folder. It does not return a message count.
- `examine(folder)` (l.131) opens the folder read-only and returns a `FolderState`. It manually sets `protocol.state = SELECTED` (l.140), a workaround for aioimaplib.
- `search_uids(*criteria)` (l.180) wraps `uid_search`, and `fetch(uid_set, fields)` (l.184) wraps `uid fetch`.
- Paginated headers:
  - `iter_pages(account_id, folder, page_size)` (l.204) examines the folder, runs `SEARCH ALL`, sorts UIDs descending and yields `list[Mail]` per page.
  - `fetch_mails` (l.189) fetches `FETCH_FIELDS` (l.21: UID FLAGS INTERNALDATE RFC822.SIZE BODYSTRUCTURE BODY.PEEK[HEADER]), batched by `UID_BATCH=200` via `uid_ranges` (l.52).
  - There is no random-access page API. `iter_pages` is a forward-only generator that re-runs SEARCH every time. A viewer needs something like `list_page(folder, offset/before_uid, limit)` plus a total count.
- `build_mail` (l.232) produces a `Mail` (`mail.py:40`) with headers (a parsed `email.Message`), flags, date_received, size, mime_type, an `attachments` list of `Attachment(mime_type, filename, size, inline)` (`mail.py:11`), and a lazy `body_loader`.
- Body fetching:
  - `load_bodies(folder, uid, parts)` (l.266) fetches only the non-attachment `text/plain` and `text/html` parts, one `BODY.PEEK[n]` per part. It decodes them with `decode_part` (l.58), which handles transfer encoding and charset. It returns `Bodies(text, html)` (`mail.py:28`).
  - It re-examines the folder if `self.folder != folder`.
- `bodystructure.py`: `parse_parts` (l.102) returns a flat `list[Part]` with `number` ("1", "1.2"), `mime_type`, `params`, `encoding`, `size`, `disposition`, `filename`, plus `is_attachment` and `inline`. Multipart containers are included as parts, so check `mime_type` before fetching them. Only the `Part` list is retained, and `Mail` keeps just `Attachment` metadata without the part number.
- `connection.py:8`: `ImapConnection` is a Protocol listing only read-only commands: login, logout, examine, status, list, uid_search, uid, noop and the IDLE calls. This is a deliberate guard. Any new command (e.g. `uid fetch` with different fields) goes through `uid`, which is already available, so nothing needs adding for a viewer.
- `fetch.py`: `parse_fetch` (l.51) splits responses into `FetchedMessage` with `sections: dict[str, bytes]` (l.45), keyed by the BODY[...] section string. This handles `BODY[1.2]` as a key, so arbitrary parts are already parseable.
- `watcher.py` provides IDLE or poll change events and is not needed for a basic viewer.

**Gaps for a mail viewer**
- Folder list: no special-use attributes (`\Sent`, `\Trash`) are exposed beyond the raw lowercased set. There are no unseen/total counts (STATUS requests only UIDNEXT, UIDVALIDITY and HIGHESTMODSEQ), and no tree building from `delimiter`. The `LIST_RE` (`fetch.py:11`) does not cover modified-UTF-7 folder name decoding, so non-ASCII folder names would show encoded.
- Pagination: no total count, no offset or cursor API, and no sort or search narrowing. `iter_pages` ignores `EXAMINE`'s EXISTS count.
- Body rendering: only text/plain and text/html are decoded, concatenated with `"\n".join`. There is no `cid:` inline-image resolution and no HTML sanitising. `message/rfc822` parts are not handled. A single part cannot be fetched by number. There is no full raw `RFC822` fetch.
- Attachments: no download. A new method is needed, e.g. `fetch_part(folder, uid, part_number) -> bytes`, taking `Part` from `parse_parts`. It would use `uid fetch BODY.PEEK[n]` and decode base64 or quoted-printable, since `decode_part` only handles text. Because `Mail.attachments` drops `Part.number`, the number must be retained or the structure re-fetched. Filenames are not RFC2231/RFC2047-decoded beyond what BODYSTRUCTURE gives.
- Search: `search_uids(*criteria)` passes raw criteria strings, so `SUBJECT "x"` could be built, but there is no safe criteria builder or quoting. The fake server's `uid_search` only supports `UID n:*` and ALL.
- Concurrency and lifecycle: the client is one connection per instance, with no pooling or per-request reuse. For HTTP requests, the simplest approach is `async with ImapClient(settings)` per request.

## 2. Server (`src/remote_imap_mail_rules/server/`)

- `app.py:18` `create_app(settings=None, env_account=None)` builds the engine and session factory and stores `settings`, `session_factory`, `env_account` and `rules_store` on `app.state` (l.36-40). A `lifespan` (l.25) runs migrations and `seed_from_env`. Routers are included at l.41-42 with `prefix="/api/<name>"` and `tags`. A static frontend mount comes last (l.43). A new router (e.g. `api/mail.py`) would be imported at l.13 and added here.
- `settings.py:11` `ServerSettings` (pydantic-settings) has `rules_path`, `database_url`, `secret_key: SecretStr | None` (Fernet key), `server_host`, `server_port` and `frontend_dist`.
- `api/accounts.py` patterns:
  - Each router module has `router = APIRouter()`.
  - `get_session(request)` (l.45) wraps `iter_session(request.app.state.session_factory)` (`db/engine.py:20`, which commits on success).
  - `get_settings(request)` (l.52) reads `request.app.state.settings`.
  - `find()` (l.79) raises `HTTPException(404, "No such account.")`.
  - `no_key()` (l.88) returns 503 for `CryptoError`.
  - Pydantic request and response models carry no password in output.
  - `delete_account` (l.129) returns 409 with a list of strings in `detail`.
  - Handlers take `request: Request` and `Depends(get_session)`.
  - `find`, `get_session` and `get_settings` are reusable by importing from `accounts`, or can be lifted into a shared `deps.py`.
- `api/editor.py`: a small router using `get_store(request)` (l.21) that reads `app.state`, 404 for missing rules, and 422 with `detail=list[str]` for invalid input.
- Auth: none. A grep for Auth, Security, token and Depends finds only the session dependency. All endpoints are open, and the default bind is 127.0.0.1 (`settings.py:22`). A mail browser exposes mail content, so an auth decision is needed.
- Error handling is done only by raising `HTTPException` with no custom exception handlers. IMAP errors (`ImapError`, `client.py:28`, plus `aioimaplib.AioImapException`, `TimeoutError` and `OSError`) are not mapped to HTTP. A new 502 or 504 mapping is needed.

## 3. Account to IMAP settings (`db/accounts.py`, `db/crypto.py`)

- There is no function that turns an `Account` row into `ImapSettings`. `db/accounts.py` has CRUD (`get_account` l.22, `list_accounts` l.17), `env_differences` (l.94, which calls `decrypt` at l.107) and `seed_from_env` (l.118).
- `crypto.decrypt(secret_key, token)` (`crypto.py:29`) returns plaintext and raises `CryptoError` on a missing key, invalid key or `InvalidToken`. The encrypted column is `account.password_encrypted`. The `Account` model is in `db/models/`, which I did not open. Fields seen via accounts.py: id, name, host, port, ssl, username, password_encrypted, page_size, poll_interval.
- To build the settings, stage 5 needs something like `to_imap_settings(account, secret_key) -> ImapSettings`. `ImapSettings` (`config.py:10`) requires `imap_account_id`, `imap_host`, `imap_port`, `imap_ssl`, `imap_username`, `imap_password: SecretStr`, and optionally `imap_page_size` and `imap_poll_interval`. It is an env-reading BaseSettings, so construct it with `_env_file=None`, as `tests/settings.py` does with `TestImapSettings`. Map `CryptoError` to 503 as `accounts.py:88` does.

## 4. Tests

- `tests/fake_imap.py` is an in-memory `FakeServer` with `add(folder, uid, subject, flags, sender)` (l.49), `set_flags`, `push` and `connect(settings)` (l.75). The `commands` log records every command, and the fake asserts only FETCH is used via `uid` (l.183).
- `FakeConnection` limitations that matter for the viewer:
  - `list` returns `() "/" "name"` with no attributes (l.162).
  - `uid_search` supports only ALL and `UID n:*` (l.168).
  - `fetch_lines` (l.81) hard-codes a single `text/plain` BODYSTRUCTURE and a BODY[n] answer for `BODY.PEEK[<digit>]` only (no `1.2` sections, no multipart, no attachments, no RFC822).
  - There is no STATUS message count.
  - It will need extending for multipart, attachments, folder attributes and search.
- `tests/test_imap.py`:
  - It builds clients as `ImapClient(make_settings(), lambda s: server.connect(s))` (l.82-97).
  - It covers parsing (`test_parse_fetch_with_literals` l.28, `test_parse_state_and_list` l.45, `test_bodystructure_attachments` l.55, `test_decode_part_transfer_encodings` l.72), paging (l.82), lazy body loading (l.127) and recursive folder expansion (l.140).
- Server tests:
  - They use `fastapi.testclient.TestClient` in `with` blocks so the lifespan runs.
  - `tests/test_server_accounts.py:19-27` has the `make_client(tmp_path, key, env)` helper. It builds `ServerSettings(_env_file=None, rules_path=..., database_url=sqlite+aiosqlite:///tmp, frontend_dist=missing, secret_key=SecretStr(Fernet key))`. It returns `TestClient(create_app(settings, env))`. It has a `client` fixture (l.40) and a `make_env` helper (l.30) using `TestImapSettings` (`tests/settings.py`, TEST_ prefix, no .env).
  - `tests/test_server.py` is the editor test. `tests/test_server_rules_db.py` covers DB rules.
  - `tests/conftest.py` has `ACCOUNT_ID`, `make_mail` (l.28) and a `mail` fixture.
  - Injecting the fake into the app needs a seam. `create_app` has no IMAP factory parameter, so add a `ConnectionFactory` on `app.state` (default `connect_aioimaplib`) that tests replace with `server.connect`.