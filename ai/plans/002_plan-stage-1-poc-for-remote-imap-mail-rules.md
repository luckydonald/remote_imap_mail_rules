# Plan: Stage 1 PoC for remote IMAP mail rules

## Context

The repo is freshly bootstrapped from `base/base` and has no application code yet.
`ai/initial.md` describes the long-term product (provider-independent mail rules over IMAP, FastAPI + Vue, multi-account, action log, rule editor).
This plan covers only "1. The basic PoC": YAML rules with pydantic and a generated JSON schema, `.env`-based single account, and a read-only async IMAP layer.
Each of the three parts is its own task and its own commit, following `/commit-with-lplp-style`, and the code follows `/code-style` (Python 3.14+, full type hints, native generics, no `_`-prefixed names, `# end if` / `# end def` block endings, tests for backend code, early returns).

Findings from exploration:
- Nothing exists yet outside the base tooling (`scripts/`, `ai/`, `docs/`); no `pyproject.toml`, no `README.md` at the root, no `.example-env`.
- `../AllMyStorage` does not exist (it is `../all_my_storage`) and has no schema step; the pattern to copy is `../base/scripts/sync_todos.py` (see `_schema_text`, `--write-schema`).
  There a pydantic `Config` has a `schema_: str | None = Field(alias="$schema")`, `model_json_schema(by_alias=True)` is wrapped with the draft 2020-12 `$schema`, `$id` and title header, and the file lives next to the config (`ai/settings/sync_todos.schema.json`).
  `../DockerTgBot/sync_todo/` is a further reference.
- Local Python is 3.12.2 and `uv` is available, so the project needs `requires-python >=3.14` with uv managing the interpreter.

## Layout

```
pyproject.toml                  # uv project, deps below
README.md                       # env var docs, how to run
.example-env                    # `.env` and `.env.example` are blocked for agents
src/remote_imap_mail_rules/
  rules/models.py               # pydantic rule model
  rules/loader.py               # YAML -> model
  rules/schema.py               # model -> JSON schema
  config.py                     # pydantic-settings from .env
  imap/client.py                # async IMAP wrapper
  imap/models.py                # MailHeader / MailSummary pydantic models
  imap/watcher.py               # push/poll change notification
  rules/evaluate.py             # expression evaluator
  matching.py                   # async generator of rule matches
  demo.py                       # prints matches, existing and new
schemas/rules.schema.json       # generated, committed
rules/example.yml
tests/
```

Dependencies: `pydantic`, `pydantic-settings`, `pyyaml`, `aioimaplib` (async IMAP with IDLE support), dev: `pytest`, `pytest-asyncio`.

## Task 1: YAML-based rules

- `rules/models.py`: a recursive expression tree designed for the later editor.
  - Combinators `all` (AND), `any` (OR), `not`, with arbitrary nesting, as a discriminated union on a `type` field.
  - Leaf `condition` with `field` (enum, extensible, plus a `header` variant taking a header name for custom fields), `operator` and `value`.
  - Operators: textual `equals`, `contains`, `startswith`, `endswith`, `regex`, all of them carrying a `case_sensitive` flag; numeric/date `lt`, `gt`, `ne`, `eq`, `gte`, `lte`, `between`.
  - Fields listed in `initial.md` are enumerated now so the schema is stable; the evaluator (below) implements them properly, with the fields the read-only fetch can supply (account, folder, sender, receiver, subject, body, read/unread, date, size, spam score headers, attachments count/type/size, custom headers).
  - Rule = `name`, `locations` (list of `{account_id (UUID), folder = INBOX, recursive = false}`, so one rule covers e.g. two accounts' inboxes without duplicating), `when` (expression), `actions` (list; model only, nothing executed in stage 1).
- `rules/evaluate.py`: a full evaluator `evaluate(expr, mail) -> bool` for the whole tree (AND/OR/NOT, every textual operator incl. regex and the case flag, every numeric/date operator incl. `between`), not a stub; it works on a typed `Mail` model with lazy field access.
- `rules/loader.py`: `load_rules(path)` parses YAML (`yaml.safe_load`) and validates into the model.
- `rules/schema.py`: modelled on `base/scripts/sync_todos.py`: `RuleFile` has a `$schema` alias field, `model_json_schema(by_alias=True)` gets the draft/`$id`/title header and is written to `schemas/rules.schema.json` via `--write-schema` (and a `--check` mode); the YAML example references it with a `# yaml-language-server: $schema=` comment.
  The loader additionally accepts validation through the same pydantic model, so schema and runtime validation share one source of truth.
- Tests: valid nested example, each operator and combinator against fixture mails (case sensitive and insensitive), invalid operator/field rejected, and a test that the committed schema equals the freshly generated one.

## Rule fields and how they map to the email

Fetch strategy: one cheap pass per mail gets `UID FLAGS INTERNALDATE RFC822.SIZE BODYSTRUCTURE BODY.PEEK[HEADER]`; the body text is fetched lazily with `BODY.PEEK[<part>]` only when a rule needs it, so rules on cheap fields never download bodies.
Parsing uses the stdlib `email` package (`email.policy.default`, which decodes RFC 2047 headers), and `email.utils.getaddresses` for address lists.

| Field | Source on the wire | Notes |
|---|---|---|
| `account_id`, `folder` | rule location / fetch context | not part of the message; folder is the full IMAP path |
| `from`, `sender`, `reply_to` (`Reply-To:`), `return_path` | header | address parts: `name`, `address`, `local_part`, `domain` |
| `to`, `cc`, `bcc`, `recipients` (to+cc+bcc), `delivered_to` | header | lists, so a quantifier (`any` default / `all` / `none`) is needed |
| `subject` | header, RFC 2047 decoded | |
| `date_sent` | `Date:` header | |
| `date_received` | `INTERNALDATE` | |
| `age` | now minus `date_received` | relative operators |
| `size` | `RFC822.SIZE` | bytes |
| `seen`, `flagged`, `answered`, `draft`, `deleted` | `FLAGS` | booleans |
| `keywords` | `FLAGS` minus system flags | list |
| `body_text` | `text/plain` part(s), lazy | charset decoded; missing part means false, use `exists` to test |
| `body_html` | `text/html` part(s), lazy | separate field; `body_text` never falls back to it |
| `attachments.count` | `BODYSTRUCTURE` | parts with disposition attachment or a filename |
| `attachments.mime_type`, `.filename`, `.extension`, `.size`, `.inline` | `BODYSTRUCTURE` | list, quantified |
| `header` (name) | any header | multi-valued, case-insensitive name, existence testable |
| `spam_score` | first of `X-Spam-Score`, `X-Rspamd-Score`, `X-Spam-Status` (`score=`) | configurable header list; numeric |
| `spam_flag` | `X-Spam-Flag`, `X-Spam-Status` (`Yes`) | boolean |
| `auth_spf`, `auth_dkim`, `auth_dmarc` | `Authentication-Results` | enum pass/fail/none/… |
| `message_id`, `in_reply_to` (`In-Reply-To:`, distinct from `reply_to`), `references` | headers | `is_reply` is derived from the latter two |
| `modseq` | `MODSEQ` (CONDSTORE only) | a change counter, not a time; IMAP has no last-modified date |
| `list_id`, `has_list_unsubscribe` | `List-Id`, `List-Unsubscribe` | newsletter detection |
| `auto_submitted`, `precedence`, `importance` | headers | bulk / auto-reply detection |
| `mime_type`, `uid` | `BODYSTRUCTURE`, fetch | |

Operators:
- text: `equals`, `contains`, `startswith`, `endswith`, `regex`, `glob`, `in` (value list), all with `case_sensitive`.
- number / date: `eq`, `ne`, `lt`, `gt`, `gte`, `lte`, `between`.
  Date values are a pydantic discriminated union on a bool field `relative`: `AbsoluteTime` (`relative: false`, a datetime) and `RelativeDuration` (`relative: true`, e.g. `7d`, `12h`, measured back from now), each its own subclass.
- presence: `exists`, `empty` (for headers and lists).
- boolean: `is_true`.
- Missing value rule: a field that does not exist makes every operator false except `exists: false` (applies to `body_text` too); `NOT` is the only way to negate, so no `not_contains` variants.

## Task 2: Account config from `.env`

- `config.py`: `pydantic-settings` class; unprefixed env vars read from `.env`: `IMAP_HOST`, `IMAP_PORT` (default 993), `IMAP_SSL` (default true), `IMAP_USERNAME`, `IMAP_PASSWORD` (`SecretStr`), `IMAP_PAGE_SIZE`, `IMAP_POLL_INTERVAL`, `RULES_PATH`.
  Only the automated tests use `TEST_`-prefixed variables (e.g. `TEST_IMAP_HOST`), so tests never touch the real account.
  The account has an immutable `IMAP_ACCOUNT_ID` (a UUID, generated by the user once and documented in the README) which is what rule `locations` reference, because a user-given name can change.
  An optional `IMAP_ACCOUNT_NAME` is only a display label and is never used as a reference.
- `.example-env` plus a README section documenting each variable.
- Keep the settings object shaped as a single "account" so multi-account later means a list of these.
- Tests: defaults, required vars missing, secret not leaked in `repr`.

## Task 3: Async IMAP (read-only)

- `imap/client.py`: `ImapClient` async context manager wrapping `aioimaplib`; always selects folders read-only (`EXAMINE`) and never issues store/move/expunge.
  - `connect()` / `close()`.
  - `iter_pages(folder, page_size)` – async generator over UIDs newest-first, fetching headers with `UID FETCH ... (FLAGS BODY.PEEK[HEADER.FIELDS (...)])` in pages.
  - `fetch_changes(folder, since_uid, since_modseq=None)` – new UIDs above `since_uid`; uses `CONDSTORE` `CHANGEDSINCE` when the server advertises it so flag changes are also returned.
  - Track `UIDVALIDITY`; if it changes, signal a full resync.
- `imap/watcher.py`: `watch(folder)` async generator yielding change events; uses `IDLE` when the server advertises it and automatically falls back to polling every `IMAP_POLL_INTERVAL` seconds, with IDLE re-issued before the 29 minute limit.
- Interfaces return pydantic models and take a `folder` / account parameter so multi-account, writes and moves can be added without reshaping them.
- Everything stays async (no sync wrappers or threads).
- `matching.py` (core): `async def matches(...) -> AsyncIterator[RuleMatch]` combines the pager and the watcher and yields mails matching the rules, first the existing ones, then new ones as they arrive.
  It uses the full evaluator from task 1, and `recursive` folders are expanded via `LIST`.
- Tests: unit tests against a fake `aioimaplib` protocol object (pagination boundaries, UIDVALIDITY change, IDLE → poll fallback); an opt-in integration test gated on the `TEST_` variables being present.

## Verification

- `uv run pytest` for the unit tests.
- `uv run python -m remote_imap_mail_rules.rules.schema` leaves `git diff` clean.
- Manual: with a real mailbox in `.env` (agents can't read it; the user runs it), `python -m remote_imap_mail_rules.demo` consumes the `matches()` generator and prints every mail matching the rules, existing ones first, then new ones as they arrive (checks both IDLE and the forced-poll path).

## Process

- Three separate commits (rules, config, IMAP), each preceded by tagging the prior HEAD via `scripts/tag_backup.py` as the commit style requires; Markdown in this repo follows the sentence-end line breaking rule.
