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
    `update_account` handles a changed id: 409 if another account has the new id, and 409 with the rule names if `rules_referencing(store, old_id)` is not empty (same check and message style as delete), so a rule never silently points at a missing account.
    The response carries the new id.
- `db/accounts.py`: `update_account` takes `new_id`.
  Because `mail_events.account_id` has `ON DELETE CASCADE` but no `ON UPDATE CASCADE`, update the id with an explicit `UPDATE mail_events SET account_id=new WHERE account_id=old` plus the `accounts` row in one transaction.
  The simplest safe order: insert nothing, but run `UPDATE accounts SET id` and `UPDATE mail_events` via Core statements after temporarily relying on `defer`... if the FK blocks this on SQLite and Postgres, add an Alembic migration giving the FK `ON UPDATE CASCADE` (autogenerate, then the drift test stays green) and only update `accounts.id`.
  I will check which is needed while implementing and prefer the migration.
- `git_settings` and the rules tables do not reference accounts, nothing else to touch.
- Env account: `seed_from_env` finds the seed by `IMAP_ACCOUNT_ID`.
  If its row gets another id, the next start would seed a second account.
  Note this in the UI hint and in CLAUDE.md, no code change.

### Frontend
- `model/accounts-api.ts`: `AccountInput` gets `id: string` (empty means generate on create, unchanged on update), sent as `null` when empty or equal to the current id.
- `components/AccountsView.vue`: an "ID (UUID)" input in the form, empty on new with placeholder "generated", prefilled on edit; client-side UUID pattern check; a hint that rules using the old id must be changed first.
  Show the backend's 409 messages through the existing `describe`.

### Docs
- `CLAUDE.md` Decisions: the account id is "immutable" today, reword to "stable, editable only while no rule references it", and mention the env-seed caveat.

## Verification
- `tests/test_server_accounts.py`: create with an id, create with a duplicate id (409), change the id (rows and `mail_events` follow), change refused when a rule uses it (409 with the rule name), change to an existing id (409).
- Migration drift test if a migration is added.
- `cd frontend && yarn test && yarn lint`; extend the accounts e2e test (Playwright, mocked API) to edit the id.
- `uv run pytest`.
