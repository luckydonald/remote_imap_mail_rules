This is a not yet finished repo, using `base/base` to get started quickly.
Here's what we'll gonna build, please follow /commit-with-lplp-style and /code-style along the way.
Also, if not done already, please enable /plan mode for this.

To run it in the agent you may use `@ai/initial.md`.

# Initial plan

- the goal is to run mail rules via IMAP, so you can set rules independent of provider
- full rule expression syntax with groups, AND, OR, NOT
- vue js frontend
- fastapi server
- async imap
- imap push & poll support (automatic)
- support for multiple accounts
  - including moving mails between
- full action log for a mail
  - first seen
  - rule matches (= applied)
  - any actions (e.g. moves between folders, read/unread states, …)
    - either rule actions or user's own actions
- rule editor
  - classic operators
    - textual: exact, contains, startwith, endswith, …
      - toggle case sensitivity
      - regex operator, too
    - numeric/date/time: <, >, ≠, =, &gte;, &lte;, between, …
  - standard stuff, e.g.
    - account
    - folder
    - sender
    - receiver
    - subject
    - body
    - unread/read
  - useful suff others usually dont have
    - spam score headers
    - attachments
      - counts
      - type
      - size
      - …
  - easy to add queries for custom fields/headers
- rules from mail
  - (a) mail first
    - once you add a condition it fills default values from that mail
      - granularity choosable where it makes sense.
      - e.g. sender:
        - Sender Name + Email: ˋMax Mustermann <m.muster@example.com>ˋ
        - Sender Email: ˋm.muster@example.comˋ
        - Sender Name: ˋ Max Mustermannˋ
  - (b) rule first
    - you get a fill from mail button on conditions.
    - otherwise similar to **(a)**

# Implementation scope/stages

## 1. The basic PoC
Status: done, see "Status so far" below.

- There are to be understood as separate tasks for commiting.
1. YML based rules
  - pydanic
  - json schema generated from that & used
    - check ˋ../AllMyStorageˋ for that
2. no accout management
   - just load from ˋ.envˋ & document the vars in ˋREADME.mdˋ.
3. Async IMAP
  - we need to support for this stage (all read only):
    - connect to an account
    - load INBOX asyncly & paginated
    - load recent changes only
    - have the server notify of updates/changes
- keep in mind we need to support all the rest at a later stage, too.

## 2. The rule editor
Status: done, see this checklist; additionally "Status so far" below.

- [x] Vue 3, TypeScript, SCSS, Yarn 4
- [x] standalone, file based
- [x] open or drop a rules YML, edit rules, locations, the condition tree, actions and templates, then download or copy the YML
- [x] live validation against the generated schema
- [x] undo/redo
- [x] light and dark mode
- [x] comments in the YML are kept when saving


## 3. The initial FastAPI server
Status: done, see this checklist; additionally "Status so far" below.

- [x] FastAPI server, and the editor talking to it instead of working on files.
  - File set via env var (`RULES_PATH`, default; save writes to disk), or via the editor (upload/download; no disk write).

## 4. A database for accounts, rules, actions and logs
Status: done, see this checklist; additionally "Status so far" below.
The action and log tables are not part of it, they come with stage 5.

- [x] multiple accounts
  - [x] seeded from env vars, but editable via the server
    - [x] warn if different to the env vars (e.g. if the user changed the password)
    - [x] add, edit, delete accounts
  - [x] passwords are encrypted in the database, not stored in plain text
- [x] Editor still part of it.
- [x] If `RULES_PATH` is set, the server will use (and update) the file, otherwise the database for rules and such.
- [x] Modern async typed SQLAlchemy with Alembic for migrations.
  - sqlite for now, but the database layer is abstracted so we can switch to Postgres or MySQL later.
- [x] Database URL env var: `DATABASE_URL` (default `sqlite+aiosqlite:///./db.sqlite3`).
- [x] Gitignore `*.sqlite3` and `*.sqlite3-journal` if not already.


## 5. Mail browser for the accounts registered in the server
Status: done, see this checklist; additionally "Status so far" below.

- [x] basic mail viewer for the accounts registered in the server
  - Basically implement a simple readonly mail client
  - Style wise: Apple Mail
  - Works on mobile, too (responsive)
- [x] Needs login tech.
  - For now simple: entering the mail creds allows access.
  - Gates the whole API, the credentials of any registered account work (single user).
- [x] Rules from a mail:
  - [x] basic mail viewer for the accounts registered in the server
  - [x] filling conditions from a mail, and the "fill from mail" button on conditions
    - Side panel beside the editor, a subpage on a phone; the open mail is kept in a Pinia store cached in localStorage.
- [x] the full action log per mail (first seen, rule matches, actions, user actions)
  - First seen and rule matches are written by a background watcher in the server and shown in the message view.
  - The `action` and `user_action` kinds exist in the table, but nothing writes them until actions are executed.

## 6a. Rule actions within an account
Status: done, see this checklist; additionally "Status so far" below.
Moving between accounts and user actions are still open, see "Not built yet".

- [x] Execute the actions (`move`, `mark_read`, `mark_unread`, `flag`, `keyword`) inside one account.
  - Rules run in file order and the first matching rule wins; if it changed the mail, the rules are evaluated again from the top without refetching, a move ends the pass.
  - Off by default: `ACTIONS_ENABLED=false` means the server never writes to a mailbox.
- [x] `action` entries in the log of a mail, shown in the message view.
- [x] Dry run in the rule editor: a summary of what the actions would do, a drill-down into the affected mails, and "Run now" (disabled with a hint while `ACTIONS_ENABLED` is off).

## 6b. Moving mails between accounts
Status: done, see this checklist; additionally "Status so far" below.
`user_action` entries are still open, see "Not built yet".

- [x] A `move` action with another `account_id` copies the whole mail to the target account (`APPEND`, with its flags and date) and deletes the original only afterwards.
  - A failure in between leaves a duplicate, never a lost mail; a restarted move does not copy twice (found by `Message-ID`).
  - Needs `UIDPLUS` at the source for the delete.
- [x] The log of a moved mail continues under its new folder and UID (`moved_in` entry, linked by `message_id`).
- [x] A mail that rules moved five times is not moved again (`move_loop`), so rules cannot ping-pong it.

## 7. User actions and the header picker
Status: done, see this checklist; additionally "Status so far" below.

- [x] `user_action` entries in the log of a mail: flag changes and mails that left the folder, made by the user or another client.
  - Found by the server watcher from a snapshot per folder; what rule actions did is not logged as the user's.
  - A mail that left the folder cannot be told apart as moved or deleted.
- [x] Header name suggestions on `header` conditions: the headers of the open example mail, then common ones.

# Status so far
#### Done

- YAML rules with pydantic, and the JSON schema generated from it (`schemas/rules.schema.json`, checked by a test).
  - Full expression syntax: `all` / `any` / `not`, text, address, header, number, date, bool and presence conditions, with the operators and quantifiers listed in `CLAUDE.md`.
  - Rule templates with `Var`, `Template` and `.concrete()`, so the evaluator never sees a variable.
  - Several `locations` per rule (account, folder, recursive).
  - `actions` are parsed and validated only.
- No account management: one account loaded from the environment, documented in `README.md`.
- Async, read-only IMAP: `EXAMINE` and `BODY.PEEK` only, one connection per folder, lazy body fetch, IDLE push with polling as the fallback, change detection via UID, `CONDSTORE` and `UIDVALIDITY`.
- `matches()` yields the existing, new and changed matches, and `demo.py` prints them (`--verbose`, `--streamer-mode`).
- Vue rule editor in `frontend/` (Vue 3, TypeScript, SCSS, Yarn 4), standalone and file-based:
  - Open or drop a rules YAML, edit rules, locations, the condition tree, actions and templates, then download or copy the YAML.
  - Live validation against the generated schema, undo/redo, light and dark mode.
  - Comments in the YAML are kept when saving, matched by path (rules by name), so they follow moved rules and vanish with removed ones.
  - Covered by Vitest and by Playwright end-to-end tests (`yarn test:e2e`) that drive the real app: open, drop, edit, validation, undo/redo, download, copy and the color scheme.
  - Light and dark mode follow the system; there is no manual toggle.
- FastAPI server (`server/`, started with `python -m remote_imap_mail_rules.server.main`) that serves the built editor:
  - `/api/editor` loads and saves the file at `RULES_PATH`, validating first and writing atomically.
  - The editor shows a Save button with a dirty marker when a server answers, and stays file based otherwise.
  - Covered by pytest (`TestClient`), Vitest and Playwright with the API mocked.
- Database (`db/`, async SQLAlchemy, Alembic, SQLite by default via `DATABASE_URL`) holding the accounts, and the rules when `RULES_PATH` is not set (one row per rule, so no YAML comments or anchors there).
  - Accounts are seeded once from the env vars, editable via `/api/accounts`, passwords Fernet-encrypted with `SECRET_KEY`, and a difference to the env vars is warned about and shown as a badge.
  - The editor has an accounts screen (add, edit, delete) when a server answers.

- Login (`/api/auth`, a signed cookie) in front of the whole API, and a read-only mail browser (`/api/mail`, the Mail screen): folders with counts, paged message list, message view with attachments, sanitized and sandboxed HTML, one pane at a time on a phone.

- Rules from a mail: an "Example mail" panel beside the editor, a "From mail" button on conditions and mail-first filling (`+ Add condition`, "Add to the rule"), with the part of an address choosable.
  The mail detail API returns all headers and flags for it, and the mail state is a Pinia store cached in localStorage.

- Action log per mail (`mail_events`): a background watcher (`WATCH_ENABLED`) runs the rules on every stored account and records first seen and rule matches, the message view shows them.

- Rule actions inside one account (`actions.py`): first matching rule wins with re-evaluation, `ImapClient` write methods, `ACTIONS_ENABLED` (default off), `action` log entries, and a dry run with "Run now" in the editor.

- Moves between accounts (`ImapClient.append` / `delete` / `fetch_raw`, `ImapWriter.move_across`), the `moved_in` log entry under the new key and the `move_loop` guard.

- `user_action` entries (`matches(on_change=...)`, `OwnChanges` in the `Watcher`): flag changes and vanished mails the user made, worded in the message view.
- A header name picker (`<datalist>`) on `header` conditions.

#### Not built yet

- Nothing from the plan; ideas are e.g. telling a user move from a delete, or a picker for custom fields beyond headers.
