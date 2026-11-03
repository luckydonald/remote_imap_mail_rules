This is a newly bootstrapped repo, using `base/base` to get started quickly. Here's what we'll gonna build,
please follow /commit-with-lplp-style and /code-style along the way.
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

## Implementation scope

#### 1. The basic PoC
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
    - connect to an acount
    - load INBOX asyncly & ipaginated
    - load recent changes only
    - have the server notify of updates/changes
- keep in mind we need to support all the rest at a later stage, too.

## Status so far

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
  - Comments in the YAML are not kept when saving.
  - Not looked at in a browser yet, only covered by the Vitest tests, the type check and the build.

#### Not built yet

- FastAPI server, and the editor talking to it instead of working on files.
- Multiple accounts and moving mails between them.
- Executing rule actions (all IMAP access is read-only for now).
- The full action log per mail (first seen, rule matches, actions, user actions).
- Rules from a mail: filling conditions from a mail, and the "fill from mail" button on conditions.
- Easy custom fields and headers beyond the `header` condition, e.g. a picker in the editor.
