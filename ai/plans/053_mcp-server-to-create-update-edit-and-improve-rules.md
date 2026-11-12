# MCP server to create, update, edit and improve rules

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `81f52e67-d921-4c4f-8ffd-e30fc734e066`: "create MCP server to easily create, update, edit, improve rules", with "tokens in user settings subpage".
This revision follows the user's corrections: a scope model per resource with read / write / delete, and direct rule tools beside the whole-YAML ones.

## Context

Rules are only editable through the web editor or by hand-editing the YAML.
An AI client (Claude Code etc.) should be able to read the rules, change them in small steps, validate, preview against real mails and save.
It authenticates with a token the admin creates on the settings screen, because the MCP client cannot use the login cookie.

## Decisions

- The MCP server is part of the FastAPI app, mounted at `/mcp` (Streamable HTTP, stateless), so the container stays one process and it reuses `app.state.rules_store`, `watcher`, `git`, `session_factory`.
- Dependencies: the official `mcp` Python SDK (`FastMCP`, mounted as an ASGI sub-app) and `ruamel.yaml` (round-trip editing, decided by the user: comments, anchors and `!var` survive in file mode).
- Auth: `Authorization: Bearer <token>`. `/mcp` is outside `/api`, so `require_login` does not apply; the MCP app has its own token middleware. Without `SECRET_KEY` / admin variables `/mcp` answers 503 like the login.
- Tokens live in a new table `mcp_tokens` (`id`, `name`, `token_hash` SHA-256, `prefix` first 8 chars for display, `scopes` JSON list, `created_at`, `last_used_at`, `revoked_at`). Only the hash is stored, the plain token is shown once. Tokens are long random strings, so a plain SHA-256 is enough.
- A tool call needs its scope, checked per tool; `tools/list` shows only the tools the token may use.

## Scopes

Format `<resource>:<r|w|d>`; they are independent (write does not imply read), the UI offers presets (read-only, rules editor, everything).

| Scope | Meaning today |
|---|---|
| `rules:r` `rules:w` `rules:d` | read rules and templates; create / edit / save; delete a rule or template |
| `accounts:r` `accounts:w` `accounts:d` | list accounts (never the password); create / update (incl. the id); delete |
| `accounts.password:r` `accounts.password:w` | read the stored password (decrypted); set a new one. Separate, because it is the dangerous part |
| `folders:r` `folders:w` `folders:d` | `r`: list the folder tree of an account via IMAP `LIST`. `w` / `d` (create, move, rename, delete folders) are defined and storable, but no tool uses them yet because folder writing is not implemented |
| `events:r` `events:d` | read the action log; `d` clears events (all, or filtered like `GET /api/log/events`) |
| `mails:r` `mails:w` `mails:d` | reserved. No tool reads, changes or deletes mails yet. Today it only decides whether mail titles and addresses are shown in events and dry-run results |

Mail titles: `events` details and dry-run results contain subjects and addresses. Without `mails:r` those fields are replaced by a placeholder (a hash, like `--streamer-mode`), with `mails:r` they are shown.
Scope names live in one enum (`mcp/scopes.py`), the API validates against it, and the frontend reads the list from `GET /api/mcp-tokens/scopes`, so a new scope is added in one place.

## Tools

Whole-file (the YAML text through `RulesStore`):
- `get_rules_yaml` (`rules:r`), `validate_rules_yaml(yaml)` (`rules:r`, no write), `save_rules_yaml(yaml)` (`rules:w`), `get_rules_schema` (`rules:r`, the generated JSON schema so the client knows fields and operators).

Direct rule tools (the new part), all edit the ruamel document in place, validate the result with `parse_rules` before storing and answer the validation messages on failure, with the file untouched:
- `list_rules` (name, enabled, locations, action summary, index), `get_rule(name)` (`rules:r`).
- `create_rule(rule, index?)`, `update_rule(name, changes)` (partial: `name`, `enabled`, `locations`, `actions`, `when`), `set_rule_enabled(name, enabled)`, `move_rule(name, index)`, `rename_rule` is `update_rule` (`rules:w`).
- `delete_rule(name)` (`rules:d`).
- Conditions inside `when`, addressed by a path of child indexes like the editor's `appendCondition(when, added, path, index)`: `get_condition(rule, path)` (`rules:r`), `add_condition(rule, path, condition, index?)`, `replace_condition(rule, path, condition)`, `wrap_condition(rule, path, combinator)` (all / any / not), `unwrap_condition(rule, path)` (`rules:w`), `remove_condition(rule, path)` (`rules:d`).
- Actions: `add_action(rule, action, index?)`, `replace_action`, `remove_action` (`rules:w` / `rules:d` for the removal).
- Templates: `list_templates`, `get_template` (`rules:r`), `save_template(name, template)` (`rules:w`), `delete_template(name)` (`rules:d`, refused while a rule uses it, with the names).
- `dry_run(rule?, yaml?, limit)` (`rules:r`; wraps `dry_run.py` with the `VirtualWriter`, never writes to a mailbox or the log, can take unsaved YAML).

Every write goes through one helper `save_rules_text` that also does what `PUT /api/editor/rules` does after saving (`watcher.restart`, `git.auto`), extracted from `server/api/editor.py` and used by both.

Other resources:
- `list_accounts`, `get_account` (`accounts:r`), `create_account`, `update_account` (`accounts:w`, an id change rewrites the rules as the API does), `delete_account` (`accounts:d`, refused while rules reference it like the API), all through `db/accounts.py` and the `replace_account_id` / `rules_referencing` helpers.
- `get_account_password` (`accounts.password:r`), `set_account_password` (`accounts.password:w`, resets the login history like the API); `create_account` / `update_account` take a password only with `accounts.password:w`.
- `list_folders(account_id)` (`folders:r`).
- `list_events(filters...)` (`events:r`, same filters and cursor as `GET /api/log/events`), `clear_events(filters...)` (`events:d`).

Not built: running actions (`dry-run/run`), mail reading or writing, folder writing, git control. The scope names for mails and folders writes exist so tokens can be issued for them later.

## Files

- New package `src/remote_imap_mail_rules/mcp/`: `server.py` (`create_mcp_app`, registration), `scopes.py`, `tokens.py` (generate, hash, verify, `last_used_at`, ASGI middleware, per-tool scope check), `tools_rules.py` and `rule_document.py` (ruamel editing: find a rule by name, path into `when`, insert / replace / remove), `tools_accounts.py`, `tools_events.py`, `redact.py` (mail title masking).
- New `db/models/mcp_token.py`, `db/mcp_tokens.py`, export in `db/models/__init__.py`, migration `0009_mcp_tokens.py` via `uv run alembic revision --autogenerate`.
- New `server/api/mcp_tokens.py`: `GET /api/mcp-tokens`, `GET /scopes`, `POST` (name, scopes; returns the plain token once), `DELETE /{id}` (revoke), mounted behind `require_login`.
- `server/app.py` mounts `/mcp` before the static files and runs the MCP session manager in the lifespan; `server/api/editor.py` uses the shared save helper.
- `pyproject.toml`: `mcp`, `ruamel.yaml`.
- Frontend: `SettingsView.vue` section "MCP tokens" (list with prefix, scopes, created, last used; create form with scope checkboxes grouped per resource and the presets; the new token shown once with a copy button; revoke with confirm), `mcp-tokens-api.ts`, inside `OnlineOnly.vue`; new strings in the project's i18n files if it has them.
- `CLAUDE.md`: layout entry for `mcp/` and a Decisions entry for tokens, scopes, redaction.

## Tests

- `tests/test_mcp_tokens.py`: plain token returned once and only the hash stored, revoke, scope validation, `last_used_at`, the token API needs the login.
- `tests/test_mcp_scopes.py`: every tool refuses without its scope and `tools/list` is filtered; `accounts.password` is separate from `accounts:w`; redaction of titles with and without `mails:r`; no password in any output except `get_account_password`.
- `tests/test_mcp_rules.py`: each direct tool against a file store and a database store; comments and anchors survive in the file; invalid edits leave the store untouched; `delete_template` refused while used; save triggers the watcher restart.
- `tests/test_mcp_server.py`: 401 for no / invalid / revoked token, 503 unconfigured, `initialize` and `tools/list` over HTTP with the SDK client, `dry_run` against `FakeServer`.
- The existing migration drift test must stay green.
- Frontend: Vitest for the tokens section; Playwright e2e on the settings screen with the mocked `/api`.

## Verification

`uv run pytest`, `cd frontend && yarn lint && yarn test && yarn build && yarn test:e2e`.
End to end: start the server on a separate port with a temp `DATA_DIR` and no live IMAP account, create a token in the settings screen, call `/mcp` with the SDK client (`initialize`, `tools/list`, `list_rules`, `update_rule`, `validate_rules_yaml`).
