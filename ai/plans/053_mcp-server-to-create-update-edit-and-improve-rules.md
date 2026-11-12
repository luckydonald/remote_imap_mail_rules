# MCP server to create, update, edit and improve rules

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `81f52e67-d921-4c4f-8ffd-e30fc734e066`: "create MCP server to easily create, update, edit, improve rules", with "tokens in user settings subpage".

## Context

Rules are only editable through the web editor or by hand-editing the YAML.
An AI client (Claude Code etc.) should be able to read the rules, validate a change, preview it against real mails and save it.
It authenticates with a token the admin creates on the settings screen, because the MCP client cannot use the login cookie.

## Decisions (recommended, change them at approval if wrong)

- The MCP server is part of the FastAPI app, mounted at `/mcp` (Streamable HTTP), so the container stays one process and it reuses `app.state.rules_store`, `watcher`, `git`, `session_factory`.
- Dependency: the official `mcp` Python SDK (`FastMCP`, stateless HTTP, mounted as an ASGI sub-app), not a hand-rolled protocol.
- Auth: bearer tokens, `Authorization: Bearer <token>`. `/mcp` is outside `/api`, so `require_login` does not apply, and the MCP app gets its own token check instead of the cookie.
- Tokens live in a new table `mcp_tokens` (`id`, `name`, `token_hash` SHA-256, `prefix` first 8 chars for display, `scope` `read` / `write`, `created_at`, `last_used_at`, `revoked_at`).
  Only the hash is stored, the plain token is shown once on creation. High-entropy random tokens, so a plain SHA-256 is enough and lookup is by hash.
- Scope `read` can only use the read tools. `write` also gets the save tools. Writes still respect that mailbox writes happen only when `ACTIONS_ENABLED`; rule saving itself is not gated, as in the editor.
- Without `SECRET_KEY`/admin variables set, `/mcp` answers 503 like the login does (no tokens can be created without the admin login anyway).

## Tools

All operate on the raw YAML through `RulesStore`, so comments and anchors survive in file mode.

- `get_rules()`: the YAML text (`store.read_text`).
- `validate_rules(yaml)`: `rules_file.validate`, returns the messages or ok. No write.
- `save_rules(yaml)` (write): `store.save_text`, then the same follow-ups as `PUT /api/editor/rules` (`watcher.restart`, `git.auto`). Extract these two background calls into a shared function in `rules_store.py` / `server/rules_save.py` used by both the endpoint and the tool.
- `get_schema()`: `schemas/rules.schema.json`, so the client knows fields and operators.
- `list_accounts()` / `list_folders(account_id)`: ids and names only (no passwords), folders via `imap_session`, so a rule can name real locations.
- `get_example_mail(account_id, folder, uid)` and `list_mails(account_id, folder, limit)`: reuse `mail_view` to show what a rule would see (read-only `EXAMINE` / `BODY.PEEK`).
- `dry_run(yaml, rule, limit)`: wraps `dry_run.py` with the `VirtualWriter`, never writes to a mailbox or the log.
- `recent_events(rule?, limit)`: the action log through `db/mail_events.py`, to improve rules from what they did.

No tool for mailbox writes or running actions (`dry-run/run`): out of scope, keeps the token safe.

## Files

- New `src/remote_imap_mail_rules/mcp/`: `server.py` (`create_mcp_app(app)`, tool definitions), `tokens.py` (generate, hash, verify, `last_used_at`, ASGI auth middleware).
- New `db/models/mcp_token.py` plus `db/mcp_tokens.py` (repository), export in `db/models/__init__.py`, migration `0009_mcp_tokens.py` via `uv run alembic revision --autogenerate`.
- New `server/api/mcp_tokens.py`: `GET /api/mcp-tokens`, `POST` (name, scope; returns the plain token once), `DELETE /{id}` (revoke). Behind `require_login`, mounted in `app.py`.
- `server/app.py`: mount `/mcp` before the static files mount; run the MCP session manager inside the existing lifespan.
- `server/api/editor.py`: use the shared save helper.
- `pyproject.toml`: add `mcp`.
- Frontend: `SettingsView.vue` gets an "MCP tokens" section (list with prefix, scope, created, last used; create form; the new token shown once with a copy button; revoke with confirm), `mcp-tokens-api.ts`, wrapped in `OnlineOnly.vue`. New UI strings follow the existing i18n setup if the project has one.
- `CLAUDE.md`: layout entry (`mcp/`) and a Decisions entry for tokens and tool scopes; `.example-env` needs nothing new.
- `tests/test_coolify_compose.py` is unaffected (no new env variables).

## Tests

- `tests/test_mcp_tokens.py`: create returns the token once, only the hash is stored, revoke blocks it, scope checks, `last_used_at` updates, login required for the token API.
- `tests/test_mcp_server.py`: no/invalid/revoked token is 401 on `/mcp`; `tools/list` per scope; `get_rules` / `validate_rules` (valid and invalid) / `save_rules` (file and database store, invalid leaves the file untouched, watcher restart called); `dry_run` and `list_mails` against `FakeServer`; no password ever in an output.
- Migration drift test (existing) must stay green.
- Frontend: Vitest for the tokens section (list, create shows token once, revoke); Playwright e2e on the settings screen with the mocked `/api`.

## Verification

`uv run pytest`, `cd frontend && yarn lint && yarn test && yarn build && yarn test:e2e`.
End to end: start the server on a separate port with a temp `DATA_DIR` and a fake/no IMAP account (never the live account), create a token in the settings screen, and call `/mcp` with the SDK's client (`initialize`, `tools/list`, `get_rules`, `validate_rules`).

## Out of scope

Running actions, mailbox writes, account editing, git control, OAuth for MCP clients.
