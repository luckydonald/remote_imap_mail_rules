---
name: feedback-never-touch-live-account
description: "While developing write/action features, never run against the user's live mail account; use only TEST_* settings, FakeServer and separate-port servers"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 141ae72d-db86-4cc1-a0ac-5c138f465bb1
  modified: 2026-11-03T22:24:36.920Z
---

Only use `TEST_*` settings, the `FakeServer` and servers on a separate port (not 8000) with throwaway `DATABASE_URL` / `RULES_PATH`.

**Why:** Stage 6 makes the server write (move, flag) to real mailboxes for the first time; the user said "make sure to not accidentally run against the live account".

**How to apply:** Keep `ACTIONS_ENABLED` unset in dev runs, never read `.env` or stored production accounts, verify with pytest and Playwright (mocked API). See [[feedback-playwright-not-chrome]].
