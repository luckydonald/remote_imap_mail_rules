# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Other projects using this _base_ are expected to overwrite this file.**

If the primary working directory (visible in the system prompt) ends with `/base`, read `ai/°base/AGENTS.md` for full codebase guidance.

# remote_imap_mail_rules

Runs mail rules via IMAP, independent of the provider.
Python 3.14+ with `uv`, async throughout; run tests with `uv run pytest`.
Follow `/code-style`; `.env` and `.env.example` are blocked for agents, so `.example-env` is the documented template.
Planned later (not built yet): FastAPI server, Vue frontend, multi-account management, rule actions, the per-mail action log and the rule editor, see `ai/initial.md`.

## Layout

- `src/remote_imap_mail_rules/rules/`: `models.py` (pydantic rule file), `fields.py` (field and operator enums), `values.py` (dates), `extract.py` (field to mail mapping), `operators.py`, `evaluate.py`, `loader.py`, `schema.py`.
- `src/remote_imap_mail_rules/imap/`: `client.py` (read-only `ImapClient`), `watcher.py` (IDLE or polling), `fetch.py` / `sexpr.py` / `bodystructure.py` (response parsing), `connection.py` (the slice of `aioimaplib` used, so tests can fake it).
- `src/remote_imap_mail_rules/matching.py`: `matches()`, the core async generator yielding `RuleMatch` (`existing`, then `new` / `changed`). `demo.py` prints it.
- `schemas/rules.schema.json` is generated from the pydantic model, never edited by hand: `uv run python -m remote_imap_mail_rules.rules.schema --write-schema` (`--check` fails when outdated, and a test does the same). The pattern is copied from `scripts/sync_todos.py`.

## Decisions

- Everything IMAP is read-only for now: `EXAMINE` only, `BODY.PEEK`, no store/move/expunge. Writes will be added later without reshaping the interfaces, which already take account and folder.
- Accounts are referenced by an immutable UUID (`IMAP_ACCOUNT_ID`, `account_id` in rules), never by name, because names can change. `IMAP_ACCOUNT_NAME` is a display label only.
- A rule has several `locations` (`account_id`, `folder` default `INBOX`, `recursive` default false), so equal rules for several inboxes need no duplicates. Recursive folders are expanded once at start-up via `LIST`; missing folders are skipped with a warning.
- Env vars are unprefixed (`IMAP_HOST`, ...). Only automated tests use the `TEST_` prefix, via `tests/settings.py`, and they never read `.env`.
- One connection and task per folder, because IDLE blocks its connection. Headers, flags, size and `BODYSTRUCTURE` are fetched up front, bodies lazily and only when a rule needs `body_text` / `body_html`.
- Change detection: IDLE push when the server has it (renewed before 29 minutes), else polling every `IMAP_POLL_INTERVAL`. New mails by UID, flag changes via `CONDSTORE` `CHANGEDSINCE` when available, a changed `UIDVALIDITY` reloads the folder.
- A field that does not exist makes every operator false, even negating ones like `ne`. Only `presence` with `value: false` and the `not` combinator can express absence. `body_text` never falls back to `body_html`.
- Dates are a discriminated union on the bool `relative`: `AbsoluteTime` (datetime, naive means UTC) or `RelativeDuration` (`7d`, units `s m h d w`, measured back from now). `date_received lt 7d` means received more than a week ago. There is no `age` field, a relative duration replaces it.
- IMAP has no last-modified date; `modseq` is only a change counter (CONDSTORE).
- Folder names are used as the server sends them (modified UTF-7), not decoded.
- `actions` are parsed and validated but nothing executes them yet.

## Rule expressions

Rule file: `rules:` list of `name`, `enabled` (default true), `locations`, `when`, `actions`. The `when` tree is a discriminated union on `type`:

- Combinators: `all` and `any` (`conditions`, at least one), `not` (`condition`). Nest freely.
- `text`: `field`, `operator`, `value`, `case_sensitive` (default false, valid for every operator), `quantifier`.
- `address`: like `text` plus `part` (`full`, `name`, `address` (default), `local_part`, `domain`).
- `header`: like `text` but with a header `name` instead of a field, for custom headers.
- `number`: `field`, `operator`, `value` (a `[low, high]` pair for `between`), `quantifier`.
- `date`: `field`, `operator`, `value` (`TimeValue`, or a pair for `between`).
- `bool`: `field`, `value` (default true), `quantifier`.
- `presence`: exactly one of `field` / `header`, `operator` `exists` (default) or `empty`, `value` (default true).

Operators:

- text: `equals`, `contains`, `startswith`, `endswith`, `regex` (search), `glob`, `in` (value is a list).
- number and date: `eq`, `ne`, `lt`, `gt`, `gte`, `lte`, `between` (inclusive).
- Quantifier for multi-valued fields: `any` (default), `all`, `none`. No values at all counts as missing, so false.

Fields and where they come from:

| Type | Fields | Source |
|---|---|---|
| text | `account_id`, `folder` | location / fetch context |
| text | `subject`, `message_id`, `in_reply_to`, `references`, `list_id`, `auto_submitted`, `precedence`, `importance` | headers (RFC 2047 decoded) |
| text | `body_text`, `body_html` | `text/plain` / `text/html` parts, lazy; a missing part is a missing field |
| text | `mime_type`, `keywords` | top `BODYSTRUCTURE` type, flags minus system flags |
| text | `auth_spf`, `auth_dkim`, `auth_dmarc` | `Authentication-Results` |
| text | `attachment_mime_type`, `attachment_filename`, `attachment_extension` | `BODYSTRUCTURE`, one value per attachment |
| address | `from`, `sender`, `reply_to` (`Reply-To`), `return_path`, `to`, `cc`, `bcc`, `recipients` (to+cc+bcc), `delivered_to` | headers; `in_reply_to` is separate from `reply_to` |
| number | `size` | `RFC822.SIZE` |
| number | `spam_score` | first of `X-Spam-Score`, `X-Rspamd-Score`, `X-Spam-Status` (`score=`), `X-Spam-Level` (star count) |
| number | `attachments_count`, `attachment_size`, `uid`, `modseq` | `BODYSTRUCTURE` / fetch |
| date | `date_sent` | `Date:` header |
| date | `date_received` | `INTERNALDATE` |
| bool | `seen`, `flagged`, `answered`, `draft`, `deleted` | `FLAGS` |
| bool | `spam_flag` | `X-Spam-Flag`, else `X-Spam-Status` starting with `Yes` |
| bool | `is_reply`, `has_list_unsubscribe`, `attachment_inline` | `In-Reply-To` / `References`, `List-Unsubscribe`, `BODYSTRUCTURE` |

Actions (parsed only): `move` (`folder`, optional `account_id`), `mark_read`, `mark_unread`, `flag`, `keyword`.

To add a field: extend the enum in `rules/fields.py`, map it in `rules/extract.py`, then regenerate the schema and add a test case in `tests/test_rules_evaluate.py`.
