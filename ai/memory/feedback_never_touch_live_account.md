---
name: feedback-never-touch-live-account
description: "While developing write/action features, never run against the user's live mail account; use only TEST_* settings, FakeServer and separate-port servers"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 141ae72d-db86-4cc1-a0ac-5c138f465bb1
  modified: 2026-11-04T03:23:31.079Z
---

Only use `TEST_*` settings, the `FakeServer` and servers on a separate port (not 8000) with throwaway `DATABASE_URL` / `RULES_PATH`.

**Why:** Stage 6 makes the server write (move, flag) to real mailboxes for the first time; the user said "make sure to not accidentally run against the live account".

**How to apply:** Keep `ACTIONS_ENABLED` unset in dev runs, never read `.env` or stored production accounts, verify with pytest and Playwright (mocked API). See [[feedback-playwright-not-chrome]].

**Incident (2026-11-04, admin-login smoke test):** a "throwaway" server run (`env -i`, own `DATABASE_URL`, port 8766, `WATCH_ENABLED=false`) still read the repo's `.env`, because `ServerSettings` and `ImapSettings` have `env_file=".env"` relative to the working directory.
The real `IMAP_*` account was seeded into the temp database, and `/api/accounts` printed its host and username into the session.
Nothing connected to the mailbox only because `WATCH_ENABLED=false` happened to be set.
`env -i` and a custom `DATABASE_URL` do not isolate from `.env`.

**Rules from it:**
- Run any real-server smoke test from a scratch directory without a `.env` (e.g. `uv run --project <repo> python -m ...` with `cwd` in a temp dir), and give it a fake `ADMIN_*`, a generated `SECRET_KEY` and no `IMAP_*`.
- After starting it, check what got seeded (`/api/accounts`) before trusting the isolation, and never print account details.
- Set `WATCH_ENABLED=false` anyway, as a second layer.
- Do not clean up with broad globs over shared temp dirs (the auto mode classifier denied `rm -rf /var/folders/*/*/T/tmp.*`); remove only the exact directory you made, from a variable.
