# remote_imap_mail_rules

Runs mail rules via IMAP, so rules are independent of the mail provider.

## Setup

```bash
uv sync
cp .example-env .env   # then edit
uv run pytest
```

## Configuration

Read from the environment and from `.env` in the working directory (see `.example-env`).

| Variable | Default | Description |
|---|---|---|
| `IMAP_ACCOUNT_ID` | required | An immutable UUID of your choosing (`uuidgen`). Rules reference the account by this id, because names can change. |
| `IMAP_ACCOUNT_NAME` | none | Display label only, never used as a reference. |
| `IMAP_HOST` | required | IMAP server host name. |
| `IMAP_PORT` | `993` | IMAP server port. |
| `IMAP_SSL` | `true` | Use TLS from the start. |
| `IMAP_USERNAME` | required | Login name. |
| `IMAP_PASSWORD` | required | Login password. |
| `IMAP_PAGE_SIZE` | `50` | Mails per page when loading a folder. |
| `IMAP_POLL_INTERVAL` | `60` | Seconds between polls when the server has no IDLE. |
| `RULES_PATH` | `rules/example.yml` | The YAML rules file. |

The automated tests read the same names with a `TEST_` prefix (e.g. `TEST_IMAP_HOST`) and never read `.env`.

## Rules

Rules are YAML, validated by the pydantic model in `src/remote_imap_mail_rules/rules/models.py`.
The JSON schema for IDE completion is generated from it:

```bash
uv run python -m remote_imap_mail_rules.rules.schema --write-schema
uv run python -m remote_imap_mail_rules.rules.schema --check
```

See `rules/example.yml`.
Conditions on a field that does not exist are false for every operator, use the `presence` condition to test for that.
A relative date such as `7d` is the moment seven days before now, so `date_received lt 7d` means received more than a week ago.
