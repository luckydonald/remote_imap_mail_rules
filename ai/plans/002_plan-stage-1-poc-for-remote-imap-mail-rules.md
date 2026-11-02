# Plan: Stage 1 PoC for remote IMAP mail rules

## Context

The repo is freshly bootstrapped from `base/base` and has no application code yet.
`ai/initial.md` describes the long-term product (provider-independent mail rules over IMAP, FastAPI + Vue, multi-account, action log, rule editor).
This plan covers only "1. The basic PoC": YAML rules with pydantic and a generated JSON schema, `.env`-based single account, and a read-only async IMAP layer.
Each of the three parts is its own task and its own commit, following `/commit-with-lplp-style`, and the code follows `/code-style` (Python 3.14+, full type hints, native generics, no `_`-prefixed names, `# end if` / `# end def` block endings, tests for backend code, early returns).

Findings from exploration:
- Nothing exists yet outside the base tooling (`scripts/`, `ai/`, `docs/`); no `pyproject.toml`, no `README.md` at the root, no `.env.example`.
- `../AllMyStorage` does not exist; the sibling project is `../all_my_storage`.
  It has no pydantic → JSON schema step to copy (it only keeps an exported `openapi.json`), so the schema generation is designed from scratch here.
- Local Python is 3.12.2 and `uv` is available, so the project needs `requires-python >=3.14` with uv managing the interpreter.

## Layout

```
pyproject.toml                  # uv project, deps below
README.md                       # env var docs, how to run
.env.example
src/remote_imap_mail_rules/
  rules/models.py               # pydantic rule model
  rules/loader.py               # YAML -> model
  rules/schema.py               # model -> JSON schema
  config.py                     # pydantic-settings from .env
  imap/client.py                # async IMAP wrapper
  imap/models.py                # MailHeader / MailSummary pydantic models
  imap/watcher.py               # push/poll change notification
schemas/rules.schema.json       # generated, committed
rules/example.yml
tests/
```

Dependencies: `pydantic`, `pydantic-settings`, `pyyaml`, `aioimaplib` (async IMAP with IDLE support), dev: `pytest`, `pytest-asyncio`.

## Task 1: YAML-based rules

- `rules/models.py`: a recursive expression tree designed for the later editor.
  - Combinators `all` (AND), `any` (OR), `not`, with arbitrary nesting, as a discriminated union on a `type` field.
  - Leaf `condition` with `field` (enum, extensible, plus a `header` variant taking a header name for custom fields), `operator` and `value`.
  - Operators: textual `equals`, `contains`, `startswith`, `endswith`, `regex` with a `case_sensitive` flag; numeric/date `lt`, `gt`, `ne`, `eq`, `gte`, `lte`, `between`.
  - Fields listed in `initial.md` are enumerated now so the schema is stable, but only the header-based ones get evaluated in this stage (evaluation is out of scope).
  - Rule = `name`, optional `account`, `folder`, `when` (expression), `actions` (list; model only, nothing executed in stage 1).
- `rules/loader.py`: `load_rules(path)` parses YAML (`yaml.safe_load`) and validates into the model.
- `rules/schema.py`: `RuleFile.model_json_schema()` written to `schemas/rules.schema.json` via `python -m remote_imap_mail_rules.rules.schema`; the YAML example references it with a `# yaml-language-server: $schema=` comment.
  The loader additionally accepts validation through the same pydantic model, so schema and runtime validation share one source of truth.
- Tests: valid nested example, each operator, invalid operator/field rejected, and a test that the committed schema equals the freshly generated one.

## Task 2: Account config from `.env`

- `config.py`: `pydantic-settings` class with `IMAP_HOST`, `IMAP_PORT` (default 993), `IMAP_SSL` (default true), `IMAP_USERNAME`, `IMAP_PASSWORD` (`SecretStr`), `IMAP_FOLDER` (default `INBOX`), `IMAP_PAGE_SIZE`, `IMAP_POLL_INTERVAL`, `RULES_PATH`.
- `.env.example` plus a README section documenting each variable.
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
- Tests: unit tests against a fake `aioimaplib` protocol object (pagination boundaries, UIDVALIDITY change, IDLE → poll fallback); an opt-in integration test gated on the `.env` variables being present.

## Verification

- `uv run pytest` for the unit tests.
- `uv run python -m remote_imap_mail_rules.rules.schema` leaves `git diff` clean.
- Manual: with a real mailbox in `.env`, a small `python -m remote_imap_mail_rules.imap.demo` script lists the first page of INBOX, then prints a line when a new mail arrives (checks both IDLE and the forced-poll path).

## Process

- Three separate commits (rules, config, IMAP), each preceded by tagging the prior HEAD via `scripts/tag_backup.py` as the commit style requires; Markdown in this repo follows the sentence-end line breaking rule.
