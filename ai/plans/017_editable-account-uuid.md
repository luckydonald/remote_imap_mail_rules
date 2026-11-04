# Editable account UUID

## Context

Rules reference accounts by their immutable UUID (`account_id` in `locations` and `move` actions).
To run the same rule file on two systems, both need an account with the same UUID.
Today the id is generated on create and shown read-only in `AccountsView.vue`, and the API ignores any id.
The aim is to set the UUID in the UI, both when adding an account and when editing one.

## Changes

### Backend
- `server/api/accounts.py`
  - `AccountCreate` gets an optional `id: UUID | None`, `create_account` passes it as `account_id` (the repository already supports that).
    A taken id answers 409.
  - `AccountUpdate` gets an optional `id: UUID | None` (omitted keeps the current one).
    A changed id answers 409 if another account has it, otherwise the account is updated and the rules are rewritten (see below).
    The response carries the new id.
- `db/accounts.py`: `update_account` takes the new id and sets `account.id`.
  A new Alembic migration `0005` recreates the `mail_events.account_id` foreign key with `ON UPDATE CASCADE` (SQLite needs `batch_alter_table`), and the model gets `onupdate="CASCADE"` so the drift test stays green.
  The events then follow the id by themselves.
- `server/rules_store.py`: new `replace_account_id(store, old, new)`.
  It reads the stored text, replaces every occurrence of the old UUID string with the new one (case-insensitive, covers `locations`, `move` actions, `account_id` conditions in `where`, and template defaults and variables), and saves through `store.save_text` only if something changed.
  A plain text replacement keeps YAML comments and anchors in file mode, and works the same in database mode.
  `FileRulesStore.save_text` already validates and writes atomically, so the `.yml` file is updated, and `DatabaseRulesStore` rewrites its rows and the git mirror.
  Order: validate the new id is free, update and commit the account, then rewrite the rules; if the rewrite is rejected as invalid, roll the account back and answer 422.
  After a rules save the route also triggers the git auto-commit and `watcher.restart`, the same as the rules PUT in `api/editor.py` (reuse what it calls).
- `git_settings` and the rules tables do not reference accounts, nothing else to touch.
- Env account: `seed_from_env` in `db/accounts.py` finds the seed by `IMAP_ACCOUNT_ID`, so an account whose id was changed would be seeded a second time on the next start.
  Before inserting, it now looks for a stored account that is identical to the environment (host, port, ssl, username and the decrypted password, via the existing `env_differences` returning no differences) and skips seeding with a log line if one exists, whatever its id.
  The name, page size and poll interval are not compared, as they are not part of the identity.
  A test covers: id changed in the UI, restart, still one account.

### Frontend
- `model/accounts-api.ts`: `AccountInput` gets `id: string` (empty means generate on create, unchanged on update), sent as `null` when empty or equal to the current id.
- `components/AccountsView.vue`: an "ID (UUID)" input in the form, empty on new with placeholder "generated", prefilled on edit; client-side UUID pattern check; a hint that the rules are rewritten to the new id.
  Show the backend's 409 messages through the existing `describe`.

### Docs
- `CLAUDE.md` Decisions: the account id is "immutable" today, reword to "stable, editable in the UI, which rewrites the rules", and that the env seed is skipped when an identical account (host, port, ssl, username, password) exists under another id.

## Verification
- `tests/test_server_accounts.py`: create with an id, create with a duplicate id (409), change the id (rows and `mail_events` follow), change rewrites the id in locations, move actions and `where` conditions of the file store and of the database store (comments kept in the file), change to an existing id (409).
- Migration drift test and a migration test that `ON UPDATE CASCADE` moves `mail_events`.
- `cd frontend && yarn test && yarn lint`; extend the accounts e2e test (Playwright, mocked API) to edit the id.
- `uv run pytest`.
